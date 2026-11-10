#!/usr/bin/env python3
"""Check the numbers a dashboard shows, as written down in forge-work/dashboard.md.

forge-dashboard lists every number of the dashboard in one table under "## Numbers":

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
`forge:allow` in it is not checked. Tables inside code blocks are not read.

Usage:
    python3 dashcheck.py forge-work/dashboard.md                    fail on high or worse
    python3 dashcheck.py forge-work/dashboard.md --fail-on medium   fail on medium findings too
    python3 dashcheck.py forge-work/dashboard.md --json             machine-readable output

--json prints {"file", "numbers": [{"line", "number", "definition", "source", "unit", "period",
"compared with", "form"}], "findings": [{"rule", "severity", "what", "where", "line", "why",
"fix"}], "summary": {"numbers", "critical", "high", "medium", "low", "fail_on", "failed"}}.

Exit codes:
    0  no finding at or above --fail-on (default: high)
    1  at least one finding at or above --fail-on
    2  the check could not run: the file is missing, unreadable or too big, it has no
       "## Numbers" section, or that section has no table with the columns number, definition,
       source, unit and form, or the table has no rows. Never a pass.
"""

import argparse
import json
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


def check(rows, path):
    """The findings for the rows of the Numbers table, in table order."""
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
            if pattern.search(form):
                add(row, rule, "medium", "'%s' is shown as '%s'" % (name, form), why, better)
    if len(checked) > MAX_NUMBERS:
        add(checked[MAX_NUMBERS], "too-many-numbers", "medium",
            "%d numbers on one dashboard (at most %d)" % (len(checked), MAX_NUMBERS),
            "with this many numbers nothing stands out, and the ones that drive a decision drown",
            "keep the 5 to 7 that change what the reader does; move the rest to a detail page or a table")
    return findings


def say(text, stream=None):
    """Print TEXT so that a Windows cp1252 pipe cannot crash on it: anything else becomes an escape."""
    stream = stream or sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    print(text.encode(encoding, "backslashreplace").decode(encoding), file=stream)


def format_human(findings, summary, path):
    lines = []
    for item in findings:
        lines += ["%-8s  %s" % (item["severity"].upper(), item["what"]), "          where: %s" % item["where"],
                  "          why:   %s" % item["why"], "          fix:   %s" % item["fix"], ""]
    counts = ", ".join("%d %s" % (summary[name], name) for name in SEVERITIES if summary[name]) or "no findings"
    lines.append("%s: %d number%s, %s." % (path, summary["numbers"], "" if summary["numbers"] == 1 else "s", counts))
    lines.append("FAIL: at least one finding is %s or worse." % summary["fail_on"] if summary["failed"]
                 else "PASS: no finding is %s or worse." % summary["fail_on"])
    return "\n".join(lines)


def main(argv=None):
    """Run the check from the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("file", metavar="DASHBOARD.md", help="normally forge-work/dashboard.md")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high",
                        help="exit 1 when a finding is this bad or worse (default: high)")
    args = parser.parse_args(argv)
    try:
        with open(args.file, "rb") as handle:
            data = handle.read(MAX_BYTES + 1)
    except OSError as error:
        say("error: cannot read %s: %s. forge-dashboard writes it in Step 1." % (args.file, error.strerror or error),
            sys.stderr)
        return 2
    problem = "it is larger than %d bytes" % MAX_BYTES if len(data) > MAX_BYTES else (
        "it holds NUL bytes: save it as UTF-8 text" if b"\x00" in data else "")
    rows = []
    if not problem:
        rows, problem = read_numbers(data.decode("utf-8-sig", errors="replace"))
    if problem:
        say("error: %s cannot be checked: %s. The numbers were not checked, so this is not a pass."
            % (args.file, problem), sys.stderr)
        return 2
    findings = check(rows, args.file)
    worst = SEVERITIES.index(args.fail_on)
    summary = {name: len([item for item in findings if item["severity"] == name]) for name in SEVERITIES}
    summary.update(numbers=len(rows), fail_on=args.fail_on,
                   failed=any(SEVERITIES.index(item["severity"]) <= worst for item in findings))
    if args.json:
        numbers = [{key: value for key, value in row.items() if key != "raw"} for row in rows]
        say(json.dumps({"file": args.file, "numbers": numbers, "findings": findings, "summary": summary}, indent=2))
    else:
        say(format_human(findings, summary, args.file))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
