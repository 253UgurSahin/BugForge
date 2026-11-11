#!/usr/bin/env python3
"""Check the numbers a dashboard shows, as written down in forge-work/dashboard.md.

/forge-design dashboard lists every number of the dashboard in one table under "## Numbers":

    | number | definition | source | unit | period | compared with | form |
    | --- | --- | --- | --- | --- | --- | --- |
    | Revenue | sum of paid orders, refunds taken off | `orders` where status = paid | EUR | this month | last month | tile + line |

This script reads that table and reports:
    high    a number with no definition or no source: nobody can trace it back to data
    high    a source that says sample, fake, lorem, random, dummy, mock, placeholder, made up or
            hardcoded: invented data shown as if it were real (seed data is fine: label it "seed")
    medium  a number with no unit
    medium  more than 9 numbers on one dashboard: the ones that matter drown
    medium  a form that misleads: a pie or donut with more than 5 parts, 3D, a gauge, a dual axis;
            each finding names the better form
Empty means nothing, "-", "?", "tbd", "todo", "n/a", "none" or a <placeholder>. A row with
`forge:allow` in it is not checked. Tables inside code blocks are not read. Next to a dashboard.md it
also reads every dashboard-<screen>.md (one report per screen of numbers), each checked on its own.

--level N (1 to 5, the dashboard level of ../forge/levels.md) also reports, as high: a count of
numbers that does not fit the level (3 to 5 at level 1, at most 7 at level 2, at most 9 from level
3; this replaces the medium rule); from level 3, no form cell that names a form that moves or drills
down ("draws in", "morphs", "animated", "drill-down", "click-through"); and a file without exactly
one line `Level: N` for that level outside comments and code blocks (`Level: 4 (Showpiece)` is fine).
From level 4 a 3D form whose cell also names a table is no finding: the table carries the values.
--level auto reads the dashboard level from forge-work/levels.json (next to DASHBOARD.md when that
sits in forge-work, else under the current folder), which ../forge/level.py writes. None: exit 2.

Usage:
    python3 dashcheck.py forge-work/dashboard.md                    fail on high or worse
    python3 dashcheck.py forge-work/dashboard.md --fail-on medium   fail on medium findings too
    python3 dashcheck.py forge-work/dashboard.md --level auto       also check the chosen level
    python3 dashcheck.py forge-work/dashboard.md --json             machine-readable output

--json prints {"file", "numbers": [{"line", "number", "definition", "source", "unit", "period",
"compared with", "form"}], "findings": [{"rule", "severity", "what", "where", "line", "why",
"fix"}], "summary": {"numbers", "level" (null without --level), "critical", "high", "medium", "low",
"fail_on", "failed"}, "reports": [the same four keys for each report read, this one first]}.

Exit codes:
    0  no finding at or above --fail-on (default: high), in any report read
    1  at least one finding at or above --fail-on
    2  the check could not run: a report is missing, unreadable or too big, it has no
       "## Numbers" section, or that section has no table with the columns number, definition,
       source, unit and form, or the table has no rows; or --level auto found no dashboard level
       (no forge-work/levels.json, none in it, or it is a link): ask the user. Never a pass.
"""

import argparse
import glob
import json
import os
import re
import sys

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
MAX_BYTES, MAX_NUMBERS = 1000000, 9
COLUMNS = ["number", "definition", "source", "unit", "period", "compared with", "form"]
NEEDED = ["number", "definition", "source", "unit", "form"]
EMPTY = re.compile(r"^(?:|-+|\?+|tbd|todo|n/?a|none|<[^>]*>)$", re.IGNORECASE)
INVENTED = re.compile(r"\b(sample|fake|lorem|random|dummy|mock(?:ed)?|placeholder|made[- ]up|hard-?coded)\b",
                      re.IGNORECASE)
PARTS = re.compile(r"(\d+)\s*(?:parts|slices|segments|categories|pieces|wedges)", re.IGNORECASE)
FORMS = [  # rule, pattern in the form cell, why it misleads, the better form
    ("form-3d", re.compile(r"\b3-?d\b", re.IGNORECASE),
     "depth distorts the sizes, so the eye reads wrong values",
     "a flat bar chart (comparison) or line chart (over time)"),
    ("form-gauge", re.compile(r"\b(?:gauge|speedometer|dial)\b", re.IGNORECASE),
     "a gauge uses a whole panel for one value and hides its history",
     "the number itself with its target next to it, or a bullet bar (a bar with a target mark)"),
    ("form-dual-axis", re.compile(r"\b(?:dual|double|two|second(?:ary)?)[- ](?:y[- ])?ax[ei]s\b", re.IGNORECASE),
     "two scales in one chart make lines cross where nothing happens: the picture depends on the scales chosen",
     "two small charts under each other on one time axis, or both series indexed to 100"),
]
SPAN = re.compile(r"`[^`]*`|\\\|")  # code spans and escaped pipes: a | inside them does not split a cell
COUNTS = {1: (3, 5), 2: (1, 7), 3: (1, 9), 4: (1, 9), 5: (1, 9)}  # numbers on screen per dashboard level
NAMES = {1: ("Subtle", "Subtiel"), 2: ("Polished", "Verzorgd"), 3: ("Expressive", "Expressief"),
         4: ("Showpiece", "Showpiece"), 5: ("Cinematic", "Cinematisch")}
MOVES = re.compile(r"\b(?:draw(?:s|n)?[- ](?:in|on)|morph\w*|animat\w*|drill(?:s|ed|ing)?[- ]?(?:down|through)"
                   r"|clicks?[- ]through)\b", re.IGNORECASE)
TABLE = re.compile(r"\btables?\b", re.IGNORECASE)
UNSEEN = re.compile(r"<!--.*?(?:-->|\Z)|^ {0,3}(`{3,}|~{3,}).*?(?:^ {0,3}\1|\Z)", re.S | re.M)  # comments, code
ABOUT = re.compile(r"(?im)^[ \t>#*_]*level[ \t*_]*:.*$")  # a line about the level, decorated or not
ASK = ("Ask the user how rich the dashboard should be, 1 to 5 (python3 ../forge/level.py show dashboard has "
       "the table), then record it: python3 ../forge/level.py set dashboard N --said '<their words>'")


def cells(line):
    """The cells of one table row. A | inside `code` or written as \\| stays inside its cell."""
    kept = []

    def keep(match):
        kept.append(match.group(0))
        return "\x00%d\x00" % (len(kept) - 1)
    row = SPAN.sub(keep, line.strip())
    row = row[1:] if row.startswith("|") else row
    row = row[:-1] if row.endswith("|") else row
    return [re.sub(r"\x00(\d+)\x00", lambda match: kept[int(match.group(1))], cell).strip() for cell in row.split("|")]


def read_numbers(text):
    """(rows, problem). Each row is a dict of the table's columns plus "line"; problem is '' or why
    the table cannot be read."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start = next((index for index, line in enumerate(lines) if re.match(r"##[ \t]+numbers\b", line, re.IGNORECASE)), None)
    if start is None:
        return [], 'there is no "## Numbers" section'
    header, rows, in_fence = None, [], False
    for number in range(start + 1, len(lines)):
        line = lines[number]
        if re.match(r"\s*(```|~~~)", line):
            in_fence = not in_fence
        if in_fence or not line.strip().startswith("|"):
            if re.match(r"##?[ \t]", line) and not in_fence:
                break  # the next section
            if header and line.strip() and not in_fence:
                break  # the table has ended
            continue
        row = cells(line)
        if header is None:
            header = [cell.lower().strip("*_ ") for cell in row]
            missing = [name for name in NEEDED if name not in header]
            if missing:
                return [], "the table under ## Numbers has no column %s (line %d)" % (", ".join(missing), number + 1)
        elif not all(re.match(r"^:?-+:?$", cell) for cell in row) and any(row):
            found = dict(zip(header, row + [""] * len(header)))
            rows.append(dict({name: found.get(name, "") for name in COLUMNS}, line=number + 1, raw=line))
    if header is None:
        return [], "the ## Numbers section has no table: | %s |" % " | ".join(COLUMNS)
    return rows, "" if rows else "the table under ## Numbers has no rows: list each number the dashboard shows"


def check(rows, path, level=None, text=""):
    """The findings for the rows of the Numbers table, in table order; with LEVEL also those of that
    dashboard level, TEXT being the whole file (for its `Level: N` line)."""
    findings = []

    def add(row, rule, severity, what, why, fix):
        findings.append({"rule": rule, "severity": severity, "what": what, "line": row["line"],
                         "where": "%s:%d" % (path, row["line"]), "why": why, "fix": fix})
    checked = [row for row in rows if "forge:allow" not in row["raw"]]
    for row in checked:
        name = row["number"] or "(no name)"
        if EMPTY.match(row["definition"]):
            add(row, "no-definition", "high", "'%s' has no definition" % name,
                "two people will read two different things into it (with or without refunds, tax, test accounts?)",
                "write exactly what is counted or added up, and what is left out")
        if EMPTY.match(row["source"]):
            add(row, "no-source", "high", "'%s' has no source" % name,
                "a number nobody can trace back to data cannot be checked or trusted",
                "name the table and the query or filter it comes from; drop the number when there is none")
        invented = INVENTED.search(row["source"])
        if invented:
            add(row, "invented-source", "high", "the source of '%s' says '%s'" % (name, invented.group(0).lower()),
                "invented data shown as a real number misleads everyone who decides on it",
                "read it from the app's own database; seed data is fine when the source says seed and the "
                "screen labels it; no data yet is an empty state, not a made-up number")
        if EMPTY.match(row["unit"]):
            add(row, "no-unit", "medium", "'%s' has no unit" % name,
                "1,200 can be euros, cents, orders or percent; the reader has to guess",
                "write the unit: EUR, %, percentage points, ms, or the thing counted (orders, users)")
        form, parts = row["form"], PARTS.search(row["form"])
        if re.search(r"\b(?:pie|donut|doughnut)\b", form, re.IGNORECASE) and parts and int(parts.group(1)) > 5:
            add(row, "form-pie-parts", "medium", "'%s' is a %s" % (name, form),
                "nobody can compare more than 5 slices by eye, and the small ones cannot be labelled",
                "a horizontal bar chart sorted by value; or the top 4 parts plus Other")
        for rule, pattern, why, better in FORMS:
            if pattern.search(form) and not (rule == "form-3d" and (level or 0) >= 4 and TABLE.search(form)):
                add(row, rule, "medium", "'%s' is shown as '%s'" % (name, form), why, better)
    if level is None and len(checked) > MAX_NUMBERS:
        add(checked[MAX_NUMBERS], "too-many-numbers", "medium",
            "%d numbers on one dashboard (at most %d)" % (len(checked), MAX_NUMBERS),
            "with this many numbers nothing stands out, and the ones that drive a decision drown",
            "keep the 5 to 7 that change what the reader does; move the rest to a detail page or a table")
    if level is not None and rows:
        findings.extend(level_findings(rows, checked, path, level, text))
    return findings


def level_findings(rows, checked, path, level, text):
    """The findings of the dashboard LEVEL: the count of numbers, a form that moves, the report's line."""
    (found, (low, high)), first = ([], COUNTS[level]), (checked or rows)[0]

    def add(line, rule, what, why, fix):
        found.append({"rule": rule, "severity": "high", "what": what, "line": line,
                      "where": "%s:%d" % (path, line), "why": why, "fix": fix})
    if not low <= len(checked) <= high:
        wanted = "%d to %d" % (low, high) if low > 1 else "at most %d" % high
        add(checked[high]["line"] if len(checked) > high else first["line"], "level-numbers",
            "%d numbers on a level %d dashboard (%s)" % (len(checked), level, wanted),
            "the level is a promise both ways: a calm dashboard with too many numbers is not calm, and one "
            "with too few shows less than the level asks",
            "keep the %s numbers that change what the reader does; the rest go to a detail page or a table; "
            "another level is the user's call" % wanted)
    if level >= 3 and not any(MOVES.search(row["form"]) for row in checked):
        add(first["line"], "level-form", "no form on this level %d dashboard moves or drills down" % level,
            "from level 3 charts draw in and morph between periods, and a number clicks through to its rows",
            "build it, then name it in the form column: 'line, draws in, morphs between periods; drill-down "
            "to the orders'")
    seen = UNSEEN.sub(lambda match: "\n" * match.group(0).count("\n"), text.replace("\r\n", "\n"))
    lines = [(index + 1, line.rstrip()) for index, line in enumerate(seen.split("\n")) if ABOUT.match(line)]
    names = "|".join(re.escape(name) for name in NAMES[level])  # the same test as ../forge/level.py check
    if len(lines) != 1 or not re.match(r"Level: *%d(?: *\(?(?i:%s)\)?)?\Z" % (level, names), lines[0][1]):
        add(lines[0][0] if lines else 1, "level-report",
            "the report needs exactly one line `Level: %d (%s)` (found: %s)"
            % (level, NAMES[level][0], " / ".join(line for _, line in lines)[:120] or "none"),
            "the report must say which level the work was done at, so the gate can check it",
            "do the work of level %d, then write the one line `Level: %d (%s)` near the top" % (level, level, NAMES[level][0]))
    return found


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


def reports(path):
    """PATH and, when it is a dashboard.md, every dashboard-<screen>.md next to it."""
    folder, name = os.path.split(path)
    others = glob.glob(os.path.join(glob.escape(folder), "dashboard-*.md")) if name == "dashboard.md" else []
    return [path] + sorted(other for other in others if os.path.isfile(other))


def format_human(findings, summary, path):
    lines = []
    for item in findings:
        lines += ["%-8s  %s" % (item["severity"].upper(), item["what"]), "          where: %s" % item["where"],
                  "          why:   %s" % item["why"], "          fix:   %s" % item["fix"], ""]
    counts = ", ".join("%d %s" % (summary[name], name) for name in SEVERITIES if summary[name]) or "no findings"
    if summary["level"]:
        lines.append("Checked at dashboard level %d (%s)" % (summary["level"], NAMES[summary["level"]][0]))
    lines.append("%s: %d number%s, %s." % (path, summary["numbers"], "" if summary["numbers"] == 1 else "s", counts))
    lines.append("FAIL: at least one finding is %s or worse." % summary["fail_on"] if summary["failed"]
                 else "PASS: no finding is %s or worse." % summary["fail_on"])
    return "\n".join(lines)


def main(argv=None):
    """Run the check from the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):  # what a cp1252 pipe cannot show comes out as \u escapes, not a crash
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("file", metavar="DASHBOARD.md", help="normally forge-work/dashboard.md")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high",
                        help="exit 1 when a finding is this bad or worse (default: high)")
    parser.add_argument("--level", choices=["1", "2", "3", "4", "5", "auto"], metavar="N|auto",
                        help="also check the dashboard level, 1 to 5, or auto: the one in forge-work/levels.json")
    args = parser.parse_args(argv)
    try:
        level = level_on_record(args.file) if args.level == "auto" else int(args.level or 0) or None
    except ValueError as error:
        print("error: %s The level was not checked, so this is not a pass." % error, file=sys.stderr)
        return 2
    done, worst = [], SEVERITIES.index(args.fail_on)
    for path in reports(args.file):
        try:
            with open(path, "rb") as handle:
                data = handle.read(MAX_BYTES + 1)
            problem = "it is larger than %d bytes" % MAX_BYTES if len(data) > MAX_BYTES else (
                "it holds NUL bytes: save it as UTF-8 text" if b"\x00" in data else "")
        except OSError as error:
            data, problem = b"", "cannot read it (%s); /forge-design dashboard writes it in Step 3" % (error.strerror or error)
        rows, text = [], data.decode("utf-8-sig", errors="replace")
        if not problem:
            rows, problem = read_numbers(text)
        if problem:
            print("error: %s cannot be checked: %s. The numbers were not checked, so this is not a pass."
                  % (path, problem), file=sys.stderr)
            return 2
        findings = check(rows, path, level, text)
        summary = {name: len([item for item in findings if item["severity"] == name]) for name in SEVERITIES}
        summary.update(numbers=len(rows), level=level, fail_on=args.fail_on,
                       failed=any(SEVERITIES.index(item["severity"]) <= worst for item in findings))
        numbers = [{key: value for key, value in row.items() if key != "raw"} for row in rows]
        done.append({"file": path, "numbers": numbers, "findings": findings, "summary": summary})
    if args.json:
        print(json.dumps(dict(done[0], reports=done), indent=2))
    else:
        print("\n\n".join(format_human(item["findings"], item["summary"], item["file"]) for item in done))
    return 1 if any(item["summary"]["failed"] for item in done) else 0


if __name__ == "__main__":
    sys.exit(main())
