#!/usr/bin/env python3
"""Second, deeper pass for risky code in PHP (Laravel), Python (Django, Flask, FastAPI) and JS/TS
(Next.js, Express). codecheck.py reads one line at a time; this looks at the lines around it:
- request input that reaches a dangerous call a few lines on: a query, a shell command, a file path,
  the address of an outgoing call, a redirect, raw HTML, loading of objects;
- a handler that uses a record by an id from the request with no sign of a login or owner check;
- uploads stored unchecked or under the visitor's file name; weak hashes, random numbers, JWT, cipher
  and TLS settings that codecheck.py does not have; a whole request written into a record; secrets in logs.
It is a heuristic, not a data-flow engine: it follows one variable name (and one copy of it) inside one
function, or 40 lines, of one file. A cast, a file-name or allow-list check on the way, or a validator
call in the function, clears the value. It misses input that travels through other functions, files or
templates, and it can flag safe code: read each finding as "check that ...". The rules are in flows.json,
next to this script. Lines containing forge:allow are not checked (for a handler: its first line too);
a line is read up to 2,000 characters. Walks like codecheck.py: no symlinks, node_modules, vendor, build,
cache or forge-work folders; big or binary files are listed as skipped; anything that cannot be read
makes the scan INCOMPLETE: exit 2, never a pass.

Usage: python3 flowcheck.py PATH [--json] [--fail-on critical|high|medium|low], for example
    python3 flowcheck.py . --fail-on medium     (also fail on medium findings)
Exit codes: 0 nothing at or above --fail-on (default: high); 1 at least one finding at or above it;
2 the path does not exist or cannot be checked, something under it could not be read (an incomplete
scan), or flows.json is missing or broken.
"""

import argparse
import json
import os
import re
import sys

import _walk
from _walk import SEVERITIES

SKIP_DIRS = {".git", "node_modules", "vendor", "venv", ".venv", "__pycache__", "dist", "build", ".next", ".nuxt",
             "out", "coverage", "storage/framework", ".cache", ".idea", ".vscode", "forge-work"}
MAX_LINE = 2000  # characters read per line: minified code is not followed
WINDOW = 40  # lines a value is followed, and a function is read, below its start
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flows.json")
FOOTER = "A heuristic that follows one variable name: it can miss problems and flag safe code. Check each finding."
STRING = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`[^`]*`')  # a quoted string or a `template`
PASTED = re.compile(r"\$?\{[^{}]*\}|\$\w+(?:->\w+)*")  # what a string pastes in: {x}, ${x}, $x
PATTERNS = ("pattern", "unless", "unless_file", "file_has")  # the patterns a check in flows.json can have
CACHE = {}  # the compiled rules, read once

def load_rules(path=None):
    """Read flows.json: {language: its patterns, compiled, and its checks}. ValueError if missing or broken."""
    try:
        with open(path or DATA, encoding="utf-8") as handle:
            data = json.load(handle)
        langs = {}
        for name, parts in data["languages"].items():
            ready = {key: re.compile(parts[key]) for key in ("source", "clean", "header", "assign", "join")}
            ready["blanket"] = re.compile(data["blanket"])
            langs[name] = dict(parts, sink=[], line=[], scope=[], names={}, **ready)
        for check in data["checks"]:
            info = dict(data["rules"][check["rule"]], rule=check["rule"])
            info.update({key: check[key] for key in ("severity", "title") if key in check})
            if info["severity"] not in SEVERITIES or not all(info[key].strip() for key in ("title", "why", "fix")):
                raise ValueError("rule %s needs a severity, title, why and fix" % check["rule"])
            ready = dict(check, info=info, near=[re.compile(item) for item in check.get("near", [])])
            ready.update({key: re.compile(check[key]) if check.get(key) else None for key in PATTERNS})
            langs[check["lang"]][check["kind"]].append(ready)
        return langs
    except (OSError, ValueError, LookupError, TypeError, AttributeError, re.error) as error:
        raise ValueError("the rule file %s is missing or broken (%s)" % (path or DATA, error))

def rules():
    """The compiled rules, read from flows.json the first time."""
    return CACHE or CACHE.update(load_rules()) or CACHE

def uses(lang, name, kind):
    """The pattern of one kind (var, glue, start, lead, member) for the variable called `name`."""
    if (kind, name) not in lang["names"]:
        lang["names"][(kind, name)] = re.compile(lang[kind].replace("VAR", re.escape(name)))
    return lang["names"][(kind, name)]

def pasted(lang, name, text):
    """True when the variable is pasted into a string in `text`: "...{x}...", or glued on with + . or %."""
    inside = " ".join(PASTED.findall(" ".join(STRING.findall(text))))
    return bool(uses(lang, name, "glue").search(text) or uses(lang, name, "var").search(inside))

def targets(assigned):
    """The names an assignment sets: one name, or those in a JS pattern like { a, b: c }."""
    many = assigned.group(2) if assigned.re.groups > 1 else None
    names = [part.split(":")[-1].split("=")[0].strip() for part in (many or "").split(",") if part.strip()]
    return [assigned.group(1)] if many is None else names

def bounds(lines, heads, index):
    """(top, bottom) of the function around a line: its first line (or decorator) to the next one, WINDOW lines at most."""
    top = index
    while top > 0 and not heads[top] and index - top < 60:
        top -= 1
    if not heads[top]:
        top = max(0, index - WINDOW)
    while top > 0 and lines[top - 1].lstrip().startswith("@"):
        top -= 1
    bottom = index + 1
    while bottom < len(lines) and bottom <= index + WINDOW and not heads[bottom]:
        bottom += 1
    return top, bottom

def finding(info, where, index, *words):
    """One finding on line `index` (counted from 0); `words` fill the {0} {1} of its title."""
    place = {"where": "%s:%d" % (where, index + 1), "file": where, "line": index + 1}
    return dict(info, title=info["title"].format(*words), **place)

def direct(lang, check, line, match):
    """The request input used straight inside a sink call on this line, uncleaned; else None."""
    rest = line[match.end():]
    source = lang["source"].search(rest)
    if not source or not check.get("direct", True) or lang["clean"].search(line):
        return None
    before = rest[:source.start()]  # glued: pasted into a string; start: the first thing the call is given
    fits = {"any": True, "glued": re.search(r"(?:[+%{]|format\()\s*\(?\s*$", before),
            "start": re.match(r"[\s\d,]*(?:f?[\"'`]\$?\{)?\s*(?:await\s+)?$", before)}[check["use"]]
    return source.group(0) if fits else None

def follow(lang, lines, heads, start, first, where):
    """Findings for request input put in the variable `first` on line `start`: follow the name, and one
    or two copies of it, to the end of the function, until something cleans or replaces it."""
    top, bottom = bounds(lines, heads, start)
    if any(lang["blanket"].search(line) for line in lines[top:start]):
        return []  # a validator or allow-list earlier in the function
    found, todo = [], [(first, start, False, True, 0)]  # name, line, built into a string, leads it, copies
    while todo:
        name, begin, built, lead, depth = todo.pop()
        var = uses(lang, name, "var")
        for index in range(begin + 1, bottom):
            line = lines[index]
            is_open = line.count("(") > line.count(")") or line.count("`") % 2  # the call goes on below
            text = "\n".join(lines[index:index + 4]) if is_open else line
            assigned = lang["assign"].search(line)
            rhs = line[assigned.end():] if assigned else ""
            if lang["blanket"].search(line) or (var.search(line) and lang["clean"].search(line)) or (
                    assigned and name in targets(assigned) and not var.search(rhs)):
                break  # checked, cleaned or given a new value: safe from here on
            if "forge:allow" in line or not var.search(text):
                continue
            for check in lang["sink"]:
                match, use = check["pattern"].search(line), check["use"]
                tail = text[match.start():] if match else ""  # the call and what it is given
                if var.search(tail) and (use == "any" or (built or pasted(lang, name, tail) if use == "glued" else
                                                      lead and uses(lang, name, "start").match(text[match.end():]))):
                    found.append(finding(check["info"], where, index, first, start + 1))
            if var.search(rhs) and depth < 2 and name not in targets(assigned):  # a copy: x = data["url"], "..." + x
                if uses(lang, name, "member").match(rhs):
                    todo += [(target, index, built, lead, depth + 1) for target in targets(assigned)]
                elif pasted(lang, name, rhs) or lang["join"].search(rhs):
                    leads = lead and bool(uses(lang, name, "lead").match(rhs))
                    todo += [(target, index, True, leads, depth + 1) for target in targets(assigned)]
    return found

def nearby(lang, lines, heads, text, where):
    """Findings of the line and scope checks: `pattern` on a line, every `near` and no `unless` on
    that line (kind line) or in the function around it (kind scope, one finding per function)."""
    found = []
    for check in lang["line"] + lang["scope"]:
        if (check["unless_file"] and check["unless_file"].search(text)) or (
                check["file_has"] and not check["file_has"].search(text)):
            continue
        skip_to = 0
        for index, line in enumerate(lines):
            if index < skip_to or "forge:allow" in line or not check["pattern"].search(line):
                continue
            top, bottom = bounds(lines, heads, index) if check["kind"] == "scope" else (index, index + 1)
            around = "\n".join(lines[top:bottom])
            if check.get("code_only"):  # without the text of its strings; what they paste in ({x}, $x) stays
                around = STRING.sub(lambda quoted: " ".join(PASTED.findall(quoted.group(0))), around)
            if ("forge:allow" not in lines[top] and all(item.search(around) for item in check["near"])
                    and not (check["unless"] and check["unless"].search(around))):
                found.append(finding(check["info"], where, index))
                skip_to = bottom
    return found

def scan_text(text, language, where):
    """Check the text of one file. `where` is the path shown in the report. No file access."""
    lang = rules()[language]
    lines = [line[:MAX_LINE] for line in re.split(r"\r\n?|\n", text)]
    heads = [bool(lang["header"].search(line)) for line in lines]
    found = nearby(lang, lines, heads, "\n".join(lines), where)
    for index, line in enumerate(lines):
        if "forge:allow" in line:
            continue
        assigned = lang["assign"].search(line)
        rhs = line[assigned.end():] if assigned else ""
        if lang["source"].search(rhs) and not lang["clean"].search(rhs):
            for name in targets(assigned):
                found += follow(lang, lines, heads, index, name, where)
        top = bounds(lines, heads, index)[0] if lang["source"].search(line) else index
        for check in lang["sink"]:
            match = check["pattern"].search(line)
            source = direct(lang, check, line, match) if match else None
            if source and not any(lang["blanket"].search(above) for above in lines[top:index + 1]):
                found.append(finding(check["info"], where, index, source, index + 1))
    unique = {(item["rule"], item["line"]): item for item in reversed(found)}  # the first one wins
    return sorted(unique.values(), key=lambda item: (item["line"], item["rule"]))

def scan_path(path):
    """(findings, stats) for a file or folder; stats: files_checked, files_skipped, unreadable. ValueError, also
    for a broken flows.json (read first)."""
    rules()
    return _walk.scan_path(path, scan_text, SKIP_DIRS, open)  # open as this script sees it

def format_human(findings, summary):
    """One block per finding, then a one-line summary and the footer."""
    lines = []
    for item in findings:
        pad = " " * (len(item["severity"]) + 2)
        lines += ["%s  %s [%s]" % (item["severity"].upper(), item["title"], item["rule"])]
        lines += [pad + "%-7s%s" % (key + ":", item[key]) for key in ("where", "why", "fix")] + [""]
    lines += _walk.result_lines(summary)
    return "\n".join(lines + [FOOTER])

def main(argv=None):
    """Check the path from the command line, print the report and return the exit code."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: escapes, no crash
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("path", help="file or folder to check")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high", help="exit 1 at this severity or worse")
    args = parser.parse_args(argv)
    return _walk.run(scan_path, args, FOOTER, format_human)

if __name__ == "__main__":
    sys.exit(main())
