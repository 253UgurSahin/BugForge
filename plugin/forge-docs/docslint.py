#!/usr/bin/env python3
"""Check the documentation forge-docs wrote: every part's file is there with its headings and diagrams,
every Mermaid block is of a known kind and not empty, every relative link and every file name in
backticks exists, no placeholder or secret-looking value is left, and the TO-FILL lines are counted.

Reads README.md and every .md under docs/ in PATH (the project root). What each part needs is in
docs.json next to this script. File names in backticks are looked for from the project root, then next
to the doc, then as the end of a path in the repository (forge/gate.py for plugin/forge/gate.py); a bare
name (nginx.conf), routes (/bookings), URLs and forge-work/ are not file paths. Code blocks are skipped for
links, file names and placeholders, never for secrets; inline code is skipped for placeholders and
TO-FILL (a command's <slot> is not one). It prints names and line numbers, never a
secret-looking value.

Usage:
    python3 docslint.py PATH [--parts readme,architecture,...] [--json] [--fail-on low]

Exit codes: 0 = nothing at or above --fail-on (default: medium; TO-FILL lines are low, for the user);
1 = a finding at or above it; 2 = PATH is not a folder, an unknown part, or docs.json is broken.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEVERITIES = ["critical", "high", "medium", "low"]
FENCE = re.compile(r"^\s*(```|~~~)\s*([\w-]*)")
LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
TICKED = re.compile(r"`([^`\s]+)`")
FILE_NAME = re.compile(r"^(?:\.{1,2}/)*[\w.@-]+(?:/[\w.@-]+)+\.\w{1,8}$")  # a path; a bare name like nginx.conf is no claim
NOT_FILES = ("forge-work/", "node_modules/", "vendor/", "http://", "https://", "/", "~")
HEADING = re.compile(r"^#{2,3}\s+(.+?)\s*#*\s*$")


def load_rules():
    with open(os.path.join(HERE, "docs.json"), encoding="utf-8") as handle:
        rules = json.load(handle)
    for key in ("parts", "default_parts", "mermaid_kinds", "placeholders", "secret"):
        if key not in rules:
            raise ValueError("docs.json has no %r" % key)
    rules["placeholder_res"] = [re.compile(pattern, re.I) for pattern in rules["placeholders"]]
    rules["secret_re"] = re.compile(rules["secret"])
    return rules


def doc_files(root):
    """README.md and every .md under docs/, relative to ROOT, sorted."""
    found = ["README.md"] if os.path.isfile(os.path.join(root, "README.md")) else []
    for folder, subfolders, files in os.walk(os.path.join(root, "docs")):
        subfolders.sort()
        found += sorted(os.path.relpath(os.path.join(folder, name), root).replace(os.sep, "/")
                        for name in files if name.lower().endswith(".md"))
    return found


def read(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as handle:
        return handle.read()


def repo_files(root):
    """Every file below ROOT as a /-path, for names that leave out a leading folder (forge/gate.py)."""
    found = []
    for folder, subfolders, files in os.walk(root):
        subfolders[:] = [name for name in subfolders if name not in (".git", "node_modules", "vendor")]
        found += [os.path.relpath(os.path.join(folder, name), root).replace(os.sep, "/") for name in files]
    return found


def exists(root, rel, name, known):
    """NAME is a file from ROOT, next to the doc REL, or the end of a known path."""
    return any(os.path.exists(os.path.normpath(os.path.join(base, name)))
               for base in (root, os.path.join(root, os.path.dirname(rel)))) \
        or any(path.endswith("/" + name.lstrip("./")) for path in known)


def lint_file(root, rel, text, rules, known=()):
    """Findings of one doc: [(rule, severity, where)], and the Mermaid kinds and headings it holds."""
    found, kinds, headings = [], [], []
    fence, block, start = None, [], 0
    for number, line in enumerate(text.split("\n"), 1):
        where = "%s:%d" % (rel, number)
        if rules["secret_re"].search(line):
            found.append(("secret", "high", where))
        opened = FENCE.match(line)
        if fence:
            if opened and opened.group(1) == fence[0] and not opened.group(2):
                if fence[1] == "mermaid":
                    body = [b.strip() for b in block if b.strip() and not b.strip().startswith("%%")]
                    kind = body[0].split()[0].rstrip(":;") if body else ""
                    if not body:
                        found.append(("empty_diagram", "medium", "%s:%d" % (rel, start)))
                    elif kind not in rules["mermaid_kinds"]:
                        found.append(("unknown_diagram", "medium", "%s:%d" % (rel, start)))
                    else:
                        kinds.append(kind if kind != "graph" else "flowchart")
                fence, block = None, []
            else:
                block.append(line)
            continue
        if opened:
            fence, start = (opened.group(1), opened.group(2).lower()), number
            continue
        heading = HEADING.match(line)
        if heading:
            headings.append(heading.group(1).strip())
        outside = re.sub(r"`[^`]*`", "", line)  # inline code: commands and names, with their own <slots>
        if "TO-FILL:" in outside:  # a question in the form TO-FILL: <what>, not a mention of the word
            found.append(("to_fill", "low", where))
        for pattern in rules["placeholder_res"]:
            if pattern.search(outside.replace("TO-FILL", "")):
                found.append(("placeholder", "medium", where))
                break
        for target in LINK.findall(outside):
            path = target.split("#")[0].split("?")[0]
            if path and not re.match(r"[a-z][a-z0-9+.-]*:", path, re.I) \
                    and not os.path.exists(os.path.normpath(os.path.join(root, os.path.dirname(rel), path))):
                found.append(("broken_link", "medium", where))
        for name in TICKED.findall(line):
            if FILE_NAME.match(name) and not name.startswith(NOT_FILES) and not exists(root, rel, name, known):
                found.append(("missing_file", "medium", where))
    if fence:
        found.append(("open_fence", "medium", "%s:%d" % (rel, start)))
    return found, kinds, headings


def part_files(root, part):
    """The files of a part that exist: one name, a list of choices, or a folder of .md files."""
    names = part["file"] if isinstance(part["file"], list) else [part["file"]]
    for name in names:
        full = os.path.join(root, name)
        if os.path.isdir(full):
            return sorted("%s/%s" % (name, f) for f in os.listdir(full) if f.lower().endswith(".md"))
        if os.path.isfile(full):
            return [name]
    return []


WORDS = {
    "missing_part": ("A doc of this part is missing", "write it as ../forge-docs/views.md says"),
    "missing_heading": ("A doc lacks a section its part needs", "add the section (views.md has the template)"),
    "missing_diagram": ("A doc lacks a diagram its part needs", "add the Mermaid diagram from the code"),
    "unknown_diagram": ("A Mermaid block of an unknown kind", "start it with flowchart, classDiagram, sequenceDiagram ..."),
    "empty_diagram": ("An empty Mermaid block", "draw the diagram or remove the block"),
    "open_fence": ("A code block that is never closed", "close it with ``` on a line of its own"),
    "broken_link": ("A link to a file that is not there", "fix the path, relative to the doc"),
    "missing_file": ("A file name that is not in the repository", "use the real path, as the code has it"),
    "placeholder": ("A placeholder left in a doc", "write the real text, or TO-FILL: <what> for the user"),
    "secret": ("A value that looks like a password, token or key", "remove it; document the variable's name only"),
    "to_fill": ("Questions left for the user (TO-FILL)", "ask the user, then replace each TO-FILL line"),
}


def check(root, parts, rules):
    """(findings, summary): one finding per rule, with every place it was seen."""
    hits = {}

    def add(rule, severity, where):
        hits.setdefault(rule, [severity, []])[1].append(where)

    linted, known = {}, repo_files(root)
    for rel in doc_files(root):
        found, kinds, headings = lint_file(root, rel, read(root, rel), rules, known)
        linted[rel] = (kinds, headings)
        for rule, severity, where in found:
            add(rule, severity, where)
    for name in parts:
        part, files = rules["parts"][name], part_files(root, rules["parts"][name])
        if not files:
            add("missing_part", "high", "%s: %s" % (name, " or ".join(part["file"]) if isinstance(part["file"], list)
                                                         else part["file"]))
        for rel in files:
            kinds, headings = linted.get(rel) or lint_file(root, rel, read(root, rel), rules)[1:]
            for heading in part["headings"]:
                if not any(h.lower().startswith(heading.lower()) for h in headings):
                    add("missing_heading", "medium", "%s: ## %s" % (rel, heading))
            for kind in part["diagrams"]:
                if kind not in kinds:
                    add("missing_diagram", "medium", "%s: %s" % (rel, kind))
    findings = [dict(rule=rule, severity=severity, title=WORDS[rule][0], fix=WORDS[rule][1], count=len(where),
                     where=where[:50]) for rule, (severity, where) in hits.items()]
    findings.sort(key=lambda f: (SEVERITIES.index(f["severity"]), f["rule"]))
    kinds = [kind for k, _ in linted.values() for kind in k]
    summary = {"docs": len(linted), "diagrams": len(kinds), "kinds": sorted(set(kinds)), "parts": parts,
               "to_fill": len(hits.get("to_fill", [None, []])[1])}
    return findings, summary


def main(argv=None):
    """Read the command line, check the docs, print the report and return the exit code."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: no crash
    parser = argparse.ArgumentParser(description="Check the documentation forge-docs wrote.")
    parser.add_argument("path", help="the project root")
    parser.add_argument("--parts", help="comma-separated parts to require (default: all but comments)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="medium", help="exit 1 at this or a worse one")
    args = parser.parse_args(argv)
    try:
        rules = load_rules()
        parts = [p.strip() for p in args.parts.split(",") if p.strip()] if args.parts else rules["default_parts"]
        unknown = [p for p in parts if p not in rules["parts"]]
        if unknown:
            raise ValueError("unknown part %r; known: %s" % (unknown[0], ", ".join(rules["parts"])))
        if not os.path.isdir(args.path):
            raise ValueError("%s is not a folder" % args.path)
    except (OSError, ValueError, re.error) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    findings, summary = check(args.path, parts, rules)
    failed = any(SEVERITIES.index(f["severity"]) <= SEVERITIES.index(args.fail_on) for f in findings)
    summary.update(fail_on=args.fail_on, failed=failed)
    if args.json:
        print(json.dumps({"findings": findings, "summary": summary}, indent=2))
    else:
        print("%d doc(s), %d diagram(s) (%s), parts: %s." % (summary["docs"], summary["diagrams"],
              ", ".join(summary["kinds"]) or "none", ", ".join(parts)))
        for f in findings:
            print("\n%-6s %s: %d\n       fix: %s" % (f["severity"].upper(), f["title"], f["count"], f["fix"]))
            for where in f["where"][:8]:
                print("       - %s" % where)
        print("\n%s" % ("Docs pass." if not failed else "Fix the findings above and run it again."))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
