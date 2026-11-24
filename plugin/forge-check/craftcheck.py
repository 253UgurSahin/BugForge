#!/usr/bin/env python3
"""Measure a codebase against the code-craft rules of craft.md: long functions, many arguments, flag
arguments, deep nesting, long switch and if/else chains, classes with many methods, errors caught and
ignored, duplicated code, commented-out code and chains of getters through other objects.

Python is read with its own parser (ast); JavaScript, TypeScript, PHP, Java, C#, Go, Kotlin, Swift, C,
C++ and Rust by braces and indentation, which is close but not exact: each finding names file and line,
so read it before you report it. Limits, words and folders to skip are in craft.json next to this
script. Generated, minified and library code, tests (unless --tests) and files over 1 MB are left out.
It never prints file contents, only names, lines and numbers.

Usage:
    python3 craftcheck.py PATH [--json] [--fail-on medium] [--tests]

Exit codes: 0 = nothing at or above --fail-on (default: high; craft findings are medium or low, so a
scan passes unless you ask for --fail-on medium or low); 1 = a finding at or above it; 2 = PATH is not a
folder, or craft.json is broken.
"""

import argparse
import ast
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEVERITIES = ["critical", "high", "medium", "low"]
MAX_BYTES = 1024 * 1024
GENERATED = re.compile(r"(?<![\"'])(?:@generated|DO NOT EDIT|\bGenerated (by|for|from)\b)|webpackBootstrap|\A\s*/\*!", re.M)
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec|specs|e2e|cypress)/|(^|/)test_[^/]*\.py$|_test\.(py|go)$"
                       r"|\.(test|spec)\.[cm]?[jt]sx?$|Tests?\.(php|java|cs)$")
KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "new", "else", "do", "try", "foreach", "elseif",
            "using", "lock", "with", "typeof", "sizeof", "function", "match", "when", "fixed", "unless"}
FUNC_STARTS = [re.compile(pattern) for pattern in (
    r"\bfunction\s*\*?\s*&?\s*([A-Za-z_$][\w$]*)\s*\(",
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*(?::[^=]+)?=>|[A-Za-z_$][\w$]*\s*=>)",
    r"\bfunc\s*(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\(", r"\bfun\s+(?:<[^>]*>\s*)?([A-Za-z_]\w*)\s*\(", r"\bfn\s+([A-Za-z_]\w*)",
    r"^\s*(?:(?:public|private|protected|internal|static|final|abstract|async|override|virtual|export|default|"
    r"readonly|synchronized|unsafe|extern|inline)\s+)*(?:[\w<>\[\],.?*&]+\s+)?([A-Za-z_$][\w$]*)\s*"
    r"\((?:[^;()]|\([^()]*\))*(?:\)\s*(?::\s*[\w<>\[\],.?| ]+)?\s*(?:throws [\w., ]+)?\{\s*$|[(,]\s*$)")]
CONTROL = re.compile(r"^\s*(?:\}\s*)?(?:else\s+)?(?:if|for|foreach|while|switch|try|do|catch|else|match)\b")
BRANCH = re.compile(r"^\s*(?:\}\s*)?(?:case\b|else\s*if\b|elseif\b|default\s*:|_\s*=>)")
FLAG = re.compile(r"=\s*(?:true|false|True|False)\b|:\s*bool(?:ean)?\b|\b(?:bool|boolean|Boolean)\s+\$?\w+")
EMPTY_CATCH = re.compile(r"catch\s*(?:\([^)]*\))?\s*\{\s*\}|\.catch\(\s*\(?\s*\w*\s*\)?\s*=>\s*\{\s*\}\s*\)")
GETTERS = re.compile(r"(?:(?:\.|->)\s*get[A-Z_]\w*\s*\([^()]*\)\s*){3,}")
COMMENT = re.compile(r"^\s*(?:#(?![!\[])|//)\s?(.*)$")  # # and // lines; doc blocks hold examples, not dead code
CODE_LIKE = re.compile(r"[;{}]\s*$|^\s*(?:if|for|while|return|def|function|var|let|const|import|from|print)\b"
                       r"|^\s*\$?\w+(?:\.\w+)*\s*=[^=]|^\s*\w+(?:\.\w+)*\([^)]*\)\s*;?\s*$")

def load_rules():
    with open(os.path.join(HERE, "craft.json"), encoding="utf-8") as handle:
        rules = json.load(handle)
    for key in ("limits", "rules", "severity_for", "languages", "skip_folders"):
        if key not in rules:
            raise ValueError("craft.json has no %r" % key)
    return rules

def sources(root, rules, tests):
    """(relative path, language, text) of each source file to measure."""
    skip = set(rules["skip_folders"])
    for folder, subfolders, files in os.walk(root):
        subfolders[:] = sorted(name for name in subfolders if name not in skip
                               and not os.path.isfile(os.path.join(folder, name, "pyvenv.cfg")))
        for name in sorted(files):
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            language = rules["languages"].get(os.path.splitext(name)[1].lower())
            if not language or os.path.islink(path) or name.endswith((".min.js", ".d.ts")) \
                    or (not tests and TEST_PATH.search(rel)) or os.path.getsize(path) > MAX_BYTES:
                continue
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            lines = text.count("\n") + 1
            if GENERATED.search(text[:1024]) or len(text) / lines > 300:
                continue
            yield rel, language, text

def python_units(text):
    """(functions, classes, empty except lines) of Python source; ([], [], []) when it does not parse."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return [], [], []
    functions, classes, empties = [], [], []
    def depth(node, level=0):  # an elif stays at the level of its if
        here = level + isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.AsyncFor, ast.AsyncWith))
        return max([here] + [depth(child, level if isinstance(node, ast.If) and node.orelse == [child] else here)
                             for child in ast.iter_child_nodes(node)
                             if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))])

    def chain(node):
        count = 1
        while len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            node, count = node.orelse[0], count + 1
        return count + bool(node.orelse)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
            names = [arg.arg for arg in args if arg.arg not in ("self", "cls")]
            defaults = node.args.defaults + [d for d in node.args.kw_defaults if d is not None]
            flags = any(isinstance(d, ast.Constant) and isinstance(d.value, bool) for d in defaults)
            cases = sum(len(m.cases) for m in ast.walk(node) if type(m).__name__ == "Match")
            branches = max([chain(n) for n in ast.walk(node) if isinstance(n, ast.If)] + [cases, 0])
            functions.append({"name": node.name, "line": node.lineno, "lines": node.end_lineno - node.lineno + 1,
                              "params": len(names), "flag": flags, "nesting": depth(node), "branches": branches})
        elif isinstance(node, ast.ClassDef):
            methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            classes.append({"name": node.name, "line": node.lineno, "methods": len(methods)})
        elif isinstance(node, ast.ExceptHandler) and all(
                isinstance(s, ast.Pass) or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
                for s in node.body):
            empties.append(node.lineno)
    return functions, classes, empties

def brace_depths(text):
    """The brace depth at the start of each line (1-based list), skipping strings and // and /* */ comments."""
    depths, depth, quote, block, i = [0, 0], 0, None, False, 0
    while i < len(text):
        ch, two = text[i], text[i:i + 2]
        if ch == "\n":
            depths.append(depth)
            quote = None if quote in ("'", '"') else quote
        elif block:
            block, i = (False, i + 1) if two == "*/" else (True, i)
        elif quote:
            i += ch == "\\"
            quote = None if ch == quote else quote
        elif two == "/*":
            block, i = True, i + 1
        elif two == "//":
            end = text.find("\n", i)
            i = (len(text) if end < 0 else end) - 1
        elif ch in "'\"`":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        i += 1
    return depths + [depth]

def brace_units(text):
    """(functions, classes, empty catch lines) of a brace language, found line by line."""
    lines, depths = text.split("\n"), brace_depths(text)
    functions, classes = [], []
    for index, line in enumerate(lines):
        number = index + 1
        name = next((m.group(1) for m in (p.search(line) for p in FUNC_STARTS) if m and m.group(1) not in KEYWORDS
                     and not re.search(r"\bnew\s+$", line[:m.start(1)])), None)
        opened = next((n for n in range(number, min(number + 6, len(lines)) + 1) if depths[n + 1] > depths[n]
                       or "{" in lines[n - 1]), None)
        if re.search(r"\bclass\s+([A-Za-z_]\w*)", line) and opened:
            end = next((n for n in range(opened + 1, len(lines) + 1) if depths[n + 1] <= depths[number]), len(lines))
            classes.append({"name": re.search(r"\bclass\s+([A-Za-z_]\w*)", line).group(1), "line": number,
                            "span": (number, end)})
            continue
        if not name or not opened or ";" in "".join(lines[index:opened - 1]):
            continue
        base = depths[number]
        end = next((n for n in range(opened + 1, len(lines) + 1) if depths[n + 1] <= base), len(lines))
        head = " ".join(lines[index:opened])
        inside = head[head.find("(") + 1:head.rfind(")")] if "(" in head and ")" in head else ""
        params = [p for p in re.split(r",(?![^<(\[{]*[>)\]}])", inside) if p.strip() and p.strip() not in ("this", "self", "&self")]
        body = range(opened, end + 1)
        functions.append({"name": name, "line": number, "lines": end - number + 1, "params": len(params),
                          "flag": any(FLAG.search(p) for p in params),
                          "nesting": max([depths[n] - base for n in body if CONTROL.match(lines[n - 1])] + [0]),
                          "branches": sum(bool(BRANCH.match(lines[n - 1])) for n in body)})
    for cls in classes:
        cls["methods"] = sum(cls["span"][0] < f["line"] <= cls["span"][1] for f in functions)
    empties = [text.count("\n", 0, m.start()) + 1 for m in EMPTY_CATCH.finditer(text)]
    return functions, classes, empties

def line_rules(lines, limits):
    """(commented-out code runs, getter chains): the first line of each."""
    runs, run, chains = [], [], []
    for number, line in enumerate(lines, 1):
        comment = COMMENT.match(line)
        if comment and CODE_LIKE.search(comment.group(1)) and "@" not in comment.group(1)[:2]:
            run.append(number)
        else:
            runs += [run[0]] if len(run) >= limits["commented_code"] else []
            run = []
        if GETTERS.search(line) and len(re.findall(r"get[A-Z_]\w*\s*\(", line)) >= limits["getter_chain"]:
            chains.append(number)
    return runs + ([run[0]] if len(run) >= limits["commented_code"] else []), chains

def duplicates(files, size):
    """Places where the same SIZE meaningful lines appear twice: [(path:line, path:line)]."""
    seen, pairs, taken = {}, [], set()
    for rel, text in files:
        kept = [(n, re.sub(r"\s+", " ", line.strip())) for n, line in enumerate(text.split("\n"), 1)]
        kept = [(n, line) for n, line in kept if len(line) > 3 and not re.match(r"^([{}()\[\];,]+|#|//|/?\*|import |from |use |require)", line)]
        for i in range(len(kept) - size + 1):
            key = hashlib.sha1("\n".join(line for _, line in kept[i:i + size]).encode()).hexdigest()
            here = (rel, kept[i][0])
            if key in seen and seen[key][0] != here[0] or key in seen and kept[i][0] - seen[key][1] >= size * 2:
                if seen[key] not in taken and here not in taken:
                    pairs.append(("%s:%d" % seen[key], "%s:%d" % here))
                    taken.update({seen[key], here})
            else:
                seen.setdefault(key, here)
    merged, last = [], None
    for a, b in pairs:  # one pair per duplicated block, not one per window inside it
        key = (a.rsplit(":", 1)[0], b.rsplit(":", 1)[0])
        if last and key == last[0] and int(a.rsplit(":", 1)[1]) - last[1] <= size:
            last = (key, int(a.rsplit(":", 1)[1]))
            continue
        merged.append((a, b))
        last = (key, int(a.rsplit(":", 1)[1]))
    return merged

def check(root, rules, tests=False):
    """(findings, summary) for the folder ROOT."""
    limits, hits, files, counted = rules["limits"], {rule: [] for rule in rules["rules"]}, [], []

    def level(value, limit):
        return "medium" if value > limits[limit]["medium"] else "low" if value > limits[limit]["low"] else None

    for rel, language, text in sources(root, rules, tests):
        files.append((rel, text))
        functions, classes, empties = python_units(text) if language == "python" else brace_units(text)
        counted += functions
        for f in functions:
            where = "%s:%d %s" % (rel, f["line"], f["name"])
            for rule, value, limit, unit in (("long_function", f["lines"], "function_lines", "lines"),
                                             ("many_params", f["params"], "params", "arguments"),
                                             ("deep_nesting", f["nesting"], "nesting", "levels deep"),
                                             ("type_switch", f["branches"], "branches", "branches")):
                if level(value, limit):
                    hits[rule].append((level(value, limit), "%s (%d %s)" % (where, value, unit), value))
            if f["flag"]:
                hits["flag_param"].append(("low", where, 0))
        for c in classes:
            if level(c["methods"], "class_methods"):
                hits["large_class"].append((level(c["methods"], "class_methods"),
                                            "%s:%d %s (%d methods)" % (rel, c["line"], c["name"], c["methods"]), c["methods"]))
        hits["swallowed_error"] += [("medium", "%s:%d" % (rel, n), 0) for n in empties]
        runs, chains = line_rules(text.split("\n"), limits)
        hits["commented_code"] += [("low", "%s:%d" % (rel, n), 0) for n in runs]
        hits["train_wreck"] += [("low", "%s:%d" % (rel, n), 0) for n in chains]
    hits["duplicate"] = [("medium", "%s and %s" % pair, 0) for pair in duplicates(files, limits["duplicate_lines"])]
    findings = []
    for rule, entries in hits.items():
        if entries:
            entries.sort(key=lambda e: (SEVERITIES.index(e[0]), -e[2]))
            severity = rules["severity_for"].get(rule) or entries[0][0]
            findings.append(dict(rules["rules"][rule], rule=rule, severity=severity, count=len(entries),
                                 where=[e[1] for e in entries[:50]]))
    findings.sort(key=lambda f: (SEVERITIES.index(f["severity"]), -f["count"]))
    lengths = [f["lines"] for f in counted]
    summary = {"files": len(files), "functions": len(counted),
               "average_function_lines": round(sum(lengths) / len(lengths), 1) if lengths else 0,
               "functions_over_limit": sum(n > limits["function_lines"]["low"] for n in lengths)}
    return findings, summary

def main(argv=None):
    """Read the command line, measure the folder, print the report and return the exit code."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Measure code against the code-craft rules of craft.md.")
    parser.add_argument("path", help="the project folder")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high", help="exit 1 at this or a worse one")
    parser.add_argument("--tests", action="store_true", help="measure test files too")
    args = parser.parse_args(argv)
    try:
        if not os.path.isdir(args.path):
            raise ValueError("%s is not a folder" % args.path)
        rules = load_rules()
    except (OSError, ValueError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    findings, summary = check(args.path, rules, args.tests)
    failed = any(SEVERITIES.index(f["severity"]) <= SEVERITIES.index(args.fail_on) for f in findings)
    summary.update(fail_on=args.fail_on, failed=failed)
    if args.json:
        print(json.dumps({"findings": findings, "summary": summary}, indent=2))
    else:
        print("%d files, %d functions, %s lines per function on average, %d over %d lines." % (
            summary["files"], summary["functions"], summary["average_function_lines"],
            summary["functions_over_limit"], rules["limits"]["function_lines"]["low"]))
        for f in findings:
            print("\n%-6s %s %s: %d found\n       why: %s\n       fix: %s" % (
                f["severity"].upper(), f["id"], f["title"], f["count"], f["why"], f["fix"]))
            for where in f["where"][:5]:
                print("       - %s" % where)
            if f["count"] > 5:
                print("       and %d more (--json lists up to 50)" % (f["count"] - 5))
        print("\n%d finding(s). Rules and sources: ../forge-check/craft.md" % len(findings))
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
