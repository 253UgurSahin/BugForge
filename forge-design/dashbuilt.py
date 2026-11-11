#!/usr/bin/env python3
"""Is the dashboard level built into the app? Reads ## Built of each dashboard report and checks each place.

/forge-design dashboard (Step 11) writes under "## Built" of forge-work/dashboard.md where the app does each
item of the dashboard level table, up to the level: a path from the project root, a colon and a line number.

    | item | where | how |
    | --- | --- | --- |
    | crosshair | app/stats/Crosshair.tsx:32 | one month index moves the line on every chart of that axis |
    | leader lines | none: the side panels are not parts of the main chart | |

A table row, a list item (with the lines under it) or a paragraph is one entry. A table row names an item by its
first cell only: the rows whose first cell is the item's name decide it, whatever other entries say; else the rows
whose first cell holds its words and is not another item's name ("main chart", never "3D-styled charts"); with no
such row, the list items and paragraphs that hold its words. The items:
    1  numbers, chart, table                2  sparkline, period filter, states
    3  draws in and morphs, drill-down, comparison, value matrix, live refresh
    4  readout strip, leader lines, crosshair, 3D-styled charts, sequence log
    5  data scene, camera, table one key away
For each item up to the level it reports, as high: no entry names it (no-item); its entries name no file and
line of the app's own (no-place): a file under the project root that has that line, not in forge-work,
node_modules, a build or a test folder, not a note (.md, .txt) and not one of the scene kit's own files (name
the app's file that mounts or styles it); for seven items, no file named for it holds the code it needs (no-code): draws in (an animation,
a transition, @keyframes, stroke-dashoffset, .animate), live refresh (a timer, EventSource, WebSocket, a
refresh interval, visibilitychange), readout strip (a <dl>), 3D-styled charts (perspective, preserve-3d,
rotateX/Y/Z, skewX/Y, translateZ, matrix3d or a canvas getContext), data scene (datascape), camera
(setProgress) and table one key away (aria-keyshortcuts). Leader lines join a main panel to the panels that
split its numbers: a screen without such panels writes "none" and why, in three words or more. A report
without ## Built is no-built. The project root is the folder that holds forge-work, for a report inside it;
else the current folder. Next to a dashboard.md every dashboard-<screen>.md is read too: one report per screen
of numbers, each checked the same way. Comments and code blocks are not read.

--level N (1 to 5, the dashboard level of ../forge/levels.md), or auto: the dashboard level in
forge-work/levels.json (next to the report when it sits in forge-work, else under the current folder), which
../forge/level.py writes.

Usage:
    python3 dashbuilt.py forge-work/dashboard.md --level auto
    python3 dashbuilt.py forge-work/dashboard.md --level 4 --json

--json prints {"level", "reports": [{"file", "items": [{"level", "item", "built", "places"}]}], "findings":
[{"rule", "severity", "what", "where", "line", "why", "fix"}], "summary": {"reports", "items", "built", "high",
"failed"}}.

Exit codes:
    0  every item of the level and below is built where each report says
    1  an item is not named, has no place in the app's own code, or none of its files holds the code it needs
    2  could not check: a report is missing, unreadable, over 1 MB or holds NUL bytes; or --level auto found
       no dashboard level (no forge-work/levels.json, none in it, or it is a link): ask the user. Never a pass.
"""

import argparse
import glob
import json
import os
import re
import sys

MAX_BYTES = 1000000
KIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenes")  # the scene kit, copied into apps
SKIP = {".git", "node_modules", "vendor", "venv", ".venv", "__pycache__", "dist", "build", ".next", ".nuxt", "out",
        "coverage", "forge-work", "e2e", "tests", "test", "__tests__"}  # tests prove an item; they do not build it
NOTES = (".md", ".markdown", ".txt", ".rst", ".log")  # a note about the code is not the code
ITEMS = [  # level, item, the words that name it in an entry, the code a file named for it holds and in plain words
    (1, "numbers", r"numbers?|tiles?|readouts?|kpis?", None, ""),
    (1, "chart", r"charts?|graphs?", None, ""),
    (1, "table", r"tables?", None, ""),
    (2, "sparkline", r"spark-?lines?", None, ""),
    (2, "period filter", r"periods?|filters?", None, ""),
    (2, "states", r"states?|skeletons?", None, ""),
    (3, "draws in and morphs", r"draws? in|drawn in|draw-in|morph\w*",
     r"animation|transition|@keyframes|stroke-dashoffset|\.animate\(", "an animation or a transition"),
    (3, "drill-down", r"drill[\w-]*|clicks?[- ]through", None, ""),
    (3, "comparison", r"compar\w*", None, ""),
    (3, "value matrix", r"matrix|heat ?map", None, ""),
    (3, "live refresh", r"live|refresh\w*", r"setInterval|setTimeout|EventSource|WebSocket|refreshInterval|"
     r"refetchInterval|visibilitychange", "a timer, server-sent events or a refresh interval"),
    (4, "readout strip", r"readouts?", r"<dl\b", "a <dl>"),
    (4, "leader lines", r"leader", None, ""),
    (4, "crosshair", r"cross-?hairs?", None, ""),
    (4, "3D-styled charts", r"3-?d|depth|isometric", r"perspective|preserve-3d|rotate[XYZ]\(|rotate3d|skew[XY]?\("
     r"|translateZ|matrix3d|getContext\(", "CSS 3D or a canvas (perspective, preserve-3d, rotateX, skewX, getContext)"),
    (4, "sequence log", r"logs?|sequence", None, ""),
    (5, "data scene", r"data ?scene|datascape|webgl", r"datascape", "the scene kit's datascape"),
    (5, "camera", r"camera", r"setProgress", "setProgress, which moves the camera"),
    (5, "table one key away", r"one key|key ?press|shortcuts?|aria-keyshortcuts", r"aria-keyshortcuts",
     "aria-keyshortcuts"),
]
WORDS = [re.compile(r"(?<![\w-])(?:%s)(?!\w)" % words, re.I) for _, _, words, _, _ in ITEMS]
NAMES = {item.lower() for _, item, _, _, _ in ITEMS}  # a row of another item's own name never stands in
CODE = [re.compile(code, re.I) if code else None for _, _, _, code, _ in ITEMS]
PLACE = re.compile(r"(?<![\w/.-])([\w@+~()\[\].-]+(?:/[\w@+~()\[\].-]+)*\.[A-Za-z]\w*):(\d+)")  # app/x.tsx:41
NONE = re.compile(r"\bnone\b\W+\w+(?:\W+\w+){2,}", re.I)  # "none" and why, in three words or more
UNSEEN = re.compile(r"<!--.*?(?:-->|\Z)|^ {0,3}(`{3,}|~{3,}).*?(?:^ {0,3}\1|\Z)", re.S | re.M)  # comments, code
ASK = ("Ask the user how rich the dashboard should be, 1 to 5 (python3 ../forge/level.py show dashboard has "
       "the table), then record it: python3 ../forge/level.py set dashboard N --said '<their words>'")


def reports(path):
    """PATH and, when it is a dashboard.md, every dashboard-<screen>.md next to it."""
    folder, name = os.path.split(path)
    others = glob.glob(os.path.join(glob.escape(folder), "dashboard-*.md")) if name == "dashboard.md" else []
    return [path] + sorted(other for other in others if os.path.isfile(other))


def entries(text):
    """(the line of ## Built, [(line, text)] of each entry under it); (None, []) when there is no such section."""
    lines = UNSEEN.sub(lambda match: "\n" * match.group(0).count("\n"), text).split("\n")
    start = next((index for index, line in enumerate(lines) if re.match(r" {0,3}##[ \t]+built\b", line, re.I)), None)
    if start is None:
        return None, []
    found = [None]
    for number in range(start + 1, len(lines)):
        line = lines[number]
        if re.match(r" {0,3}#{1,2}[ \t]", line):
            break
        if not line.strip() or re.match(r" {0,3}#{3,6}[ \t]|\s*\|?\s*:?-{3,}", line):  # blank, a sub-heading, a rule
            found.append(None)
        elif line.lstrip().startswith("|") or re.match(r"\s*(?:[-*+]|\d+[.)])\s", line) or found[-1] is None:
            found.append([number + 1, line.strip()])
        else:
            found[-1][1] += " " + line.strip()
    return start + 1, [tuple(entry) for entry in found if entry]


def first_cell(entry):
    """The first cell of a table row, plain and in lower case; None for a list item or a paragraph."""
    return " ".join(re.sub(r"[`*]", "", entry.strip("|").split("|")[0]).lower().split()) if entry.startswith(
        "|") else None


def named(index, found, cells):
    """The entries that name ITEMS[INDEX]: the rows whose first cell is its name, else the rows whose first cell
    holds its words and is not another item's name, else the list items and paragraphs that hold its words."""
    words, name = WORDS[index], ITEMS[index][1].lower()
    return ([entry for entry, cell in zip(found, cells) if cell == name]
            or [entry for entry, cell in zip(found, cells) if cell not in NAMES | {None} and words.search(cell)]
            or [entry for entry, cell in zip(found, cells) if cell is None and words.search(entry[1])])


def where(root, path, line, kit):
    """('', its text) when PATH:LINE is a file and line of the app's own under ROOT, else (why not, None)."""
    full = next((os.path.join(root, name) for name in (path, path.lstrip("([")) if os.path.isfile(os.path.join(
        root, name))), None)
    if full is None:
        return "no such file from the project root", None
    try:
        parts = os.path.relpath(os.path.realpath(full), os.path.realpath(root)).replace(os.sep, "/").split("/")
    except ValueError:  # another drive (Windows)
        parts = [".."]
    if parts[0] == "..":
        return "outside the project", None
    if SKIP & set(parts[:-1]) or parts[-1].lower().endswith(NOTES):
        return "%s, not the app's own code" % ("a note" if parts[-1].lower().endswith(NOTES) else "in " + "/".join(
            parts[:-1])), None
    if parts[-1] in kit and any("scene" in part.lower() for part in parts[:-1]):
        return "a file of the scene kit itself, not the app's file that mounts or styles it", None
    try:
        with open(full, "rb") as handle:
            data = handle.read(MAX_BYTES + 1)
    except OSError as error:
        return "cannot be read (%s)" % (error.strerror or error), None
    count = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
    if not 1 <= int(line) <= count and len(data) <= MAX_BYTES:
        return "it has %d lines" % count, None
    return "", data.decode("utf-8", "replace")


def check(path, text, level, root, kit):
    """(items, findings) of one report at LEVEL."""
    (items, findings), (heading, found) = ([], []), entries(text)

    def add(line, rule, what, why, fix):
        findings.append({"rule": rule, "severity": "high", "what": what, "line": line,
                         "where": "%s:%d" % (path, line), "why": why, "fix": fix})
    if heading is None:
        add(1, "no-built", "%s has no ## Built section" % path,
            "the report must tie each item of the level to the place in the app that does it, or nothing shows "
            "that the level was built", "build each item of the level table up to level %d, then write ## Built "
            "with one row per item: | item | path from the project root:line | how |" % level)
        return items, findings
    cells = [first_cell(entry) for _, entry in found]
    for index, (number, item, _, _, needs) in enumerate(ITEMS):
        if number > level:
            continue
        own = named(index, found, cells)
        places, missed, code = [], [], False
        for line, entry in own:
            for match in PLACE.finditer(re.sub(r"(?<=\w)\\(?=\w)", "/", entry)):  # app\stats\Chart.tsx: Windows
                why, data = where(root, match.group(1), match.group(2), kit)
                shown = "%s:%s" % (match.group(1).lstrip("(["), match.group(2))
                if why:
                    missed.append("%s (%s)" % (shown, why))
                else:
                    places.append(shown)
                    code = code or bool(CODE[index] and CODE[index].search(data))
        loose = item == "leader lines" and any(NONE.search(entry) for _, entry in own)
        built = bool(places and (code or not CODE[index])) or loose
        items.append({"level": number, "item": item, "built": built, "places": places})
        at = own[0][0] if own else heading
        if not own:
            add(at, "no-item", "no entry under ## Built names the %s (level %d)" % (item, number),
                "the level promises it, and only the report ties it to the code (a table row names its item in "
                "its first cell)", "build it, then add the row | %s | <path from the project root>:<line> | how "
                "it works |" % item)
        elif not places and not loose:
            add(at, "no-place", "the %s (level %d) has no file and line of the app: %s" % (
                item, number, "; ".join(missed)[:300] or "no path:line in its entry"),
                "a place nobody can open cannot prove the item is built",
                "write where it is built as a path from the project root and a line, such as app/stats/Chart.tsx:41"
                + ("; a screen without it writes none and why" if item == "leader lines" else ""))
        elif not built:
            add(at, "no-code", "no file named for the %s (level %d) holds %s" % (item, number, needs),
                "the %s needs that code; the files named (%s) do not have it" % (item, ", ".join(places)[:200]),
                "name the file that does it, or build it there")
    return items, findings


def level_on_record(path):
    """The dashboard level in forge-work/levels.json (see the top). ValueError, saying to ask, when there is none."""
    folder = os.path.dirname(os.path.abspath(path))
    record = os.path.join(folder if os.path.basename(folder) == "forge-work" else "forge-work", "levels.json")
    try:
        if os.path.islink(os.path.dirname(os.path.abspath(record))) or os.path.islink(record):
            raise ValueError("it is a link, so it was not read: tell the user")
        if not os.path.isfile(record) or os.path.getsize(record) > MAX_BYTES:
            raise ValueError("there is no such file (of at most 1 MB)")
        with open(record, encoding="utf-8", errors="replace") as handle:
            level = json.load(handle)["dashboard"]["level"]
        if type(level) is int and 1 <= level <= 5:
            return level
        raise ValueError("its dashboard level is %r, not 1 to 5" % (level,))
    except (OSError, ValueError, LookupError, TypeError, RecursionError) as error:
        raise ValueError("no dashboard level on record in %s (%s). %s" % (record, error, ASK))


def project_root(path):
    """The folder that holds forge-work, for a report inside it; else the current folder."""
    folder = os.path.dirname(os.path.abspath(path))
    return os.path.dirname(folder) if os.path.basename(folder) == "forge-work" else os.getcwd()


def main(argv=None):
    """Run the check from the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):  # what the console cannot show comes out as \u escapes, not a crash
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("file", metavar="DASHBOARD.md", help="normally forge-work/dashboard.md")
    parser.add_argument("--level", required=True, choices=["1", "2", "3", "4", "5", "auto"], metavar="N|auto",
                        help="the dashboard level, 1 to 5, or auto: the one in forge-work/levels.json")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        level = level_on_record(args.file) if args.level == "auto" else int(args.level)
    except ValueError as error:
        print("error: %s Nothing was checked, so this is not a pass." % error, file=sys.stderr)
        return 2
    kit = set(os.listdir(KIT)) if os.path.isdir(KIT) else set()
    done, findings = [], []
    for path in reports(args.file):
        try:
            with open(path, "rb") as handle:
                data = handle.read(MAX_BYTES + 1)
        except OSError as error:
            print("error: cannot read %s: %s. /forge-design dashboard writes it, ## Built in Step 11. Nothing was "
                  "checked, so this is not a pass." % (path, error.strerror or error), file=sys.stderr)
            return 2
        if len(data) > MAX_BYTES or b"\x00" in data:
            print("error: %s is over %d bytes or holds NUL bytes: save it as UTF-8 text. Nothing was checked, so "
                  "this is not a pass." % (path, MAX_BYTES), file=sys.stderr)
            return 2
        items, found = check(path, data.decode("utf-8-sig", "replace").replace("\r\n", "\n"), level,
                             project_root(path), kit)
        done.append({"file": path, "items": items})
        findings += found
    total = sum(len(report["items"]) for report in done)
    built = sum(item["built"] for report in done for item in report["items"])
    summary = {"reports": len(done), "items": total, "built": built, "high": len(findings), "failed": bool(findings)}
    if args.json:
        print(json.dumps({"level": level, "reports": done, "findings": findings, "summary": summary}, indent=2))
        return 1 if findings else 0
    for item in findings:
        print("\n".join(["%-8s  %s" % (item["severity"].upper(), item["what"]), "          where: " + item["where"],
                         "          why:   " + item["why"], "          fix:   " + item["fix"], ""]))
    for report in done:
        print("%s: %d of %d items of dashboard level %d and below built." % (
            report["file"], sum(item["built"] for item in report["items"]), len(report["items"]), level))
    print("FAIL: %d finding%s: the level is not built where the report says." % (len(findings), "" if len(
        findings) == 1 else "s") if findings else "PASS: every item of level %d and below is built where the report "
          "says, in the app's own code." % level)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
