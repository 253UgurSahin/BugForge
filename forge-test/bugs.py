#!/usr/bin/env python3
"""List the open bugs in forge-work/bugs.md and fail when one is too serious to move on.

forge-test writes the title "# Bugs", then one heading per bug in exactly this form:

    ## B001 [high] [open] Login fails when the email has capitals

The severity is critical, high, medium or low. The status is open, fixed or wontfix.
The only other "##" heading allowed is "## To check" (things not reproduced yet).
The lines under a heading (steps, expected, actual, evidence) are free text.

The check is strict, because a bug that cannot be read could hide a critical one. These
are errors, never skipped (exit 2, and the output names each line):
- any other "##" heading ("## Bug 1: login is broken", "## Notes"), and a bug heading with
  something before or right after the ##: "### B002", "  ## B002", "> ## B002", "##B002";
- any line, also in a list, quote, table or code block, that holds a bracketed severity or
  status ([high], [open]) but is not a bug heading, or that starts with a bug ID (B001,
  #B001, Bug 1, BUG-001) and a severity: "- B006 high ...", "| B007 | critical | ... |";
- a code block that is never closed, and a file without the "# Bugs" title.
Bug headings inside code blocks count too, so keep example headings out of bugs.md.
Invisible characters (a byte order mark, zero-width spaces) are removed first. UTF-16 and
UTF-32 with a byte order mark (PowerShell's `>`) are read too; other NUL bytes are an error.

Usage:
    python3 bugs.py forge-work/bugs.md                    list open bugs, fail on high or worse
    python3 bugs.py forge-work/bugs.md --fail-on medium   fail on open medium bugs too
    python3 bugs.py forge-work/bugs.md --json             machine-readable output

Exit codes:
    0  no open bug at or above --fail-on (default: high)
    1  at least one open bug at or above --fail-on
    2  bad usage, the file is missing, unreadable or not text, or it breaks one of the
       rules above (the output names each such line and what is wrong with it)
"""

import argparse
import codecs
import json
import os
import re
import sys

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
STATUSES = ["open", "fixed", "wontfix"]
MEANING = {"critical": "stop: data loss, account takeover, money at risk or a legal problem",
           "high": "fix before anyone else uses it", "medium": "fix soon",
           "low": "worth fixing when convenient"}  # rules.md section 8
EXAMPLE = "## B001 [high] [open] Login fails when the email has capitals"

INVISIBLE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")  # zero-width spaces, direction marks, BOM
# What Markdown can put in front of a line's text: indent, quote >, table |, bold **, a list
# marker (- * + 1. 1)) and a task box [ ]. Removed before looking, so "> ## B001" is seen.
PREFIX = re.compile(r"^(?:\s+|>|\||\*\*|__|[-*+](?=\s)|\d{1,9}[.)](?=\s)|\[[ xX]\](?=\s))*")
BUG_ID = re.compile(r"#?\s*b(?:ug)?(?:\s*[-_#])?\s*\d+(?!\w)", re.IGNORECASE)  # B001 #B001 Bug 1 BUG-1
TAG = re.compile(r"\[\s*(?:critical|high|medium|low|open|fixed|wontfix|won'?t\s*fix|s[1-4])\s*\]"
                 r"(?!\()", re.IGNORECASE)  # [high] or [open], but not a link such as [open](url)
SEVERITY_NEXT = re.compile(r"[\s:|*_()\[\],.-]*(?:critical|high|medium|low)\b", re.IGNORECASE)
SEVERITY_WORD = re.compile(r"\b(?:critical|high|medium|low)\b", re.IGNORECASE)
STATUS_WORD = re.compile(r"\b(?:open|fixed|wontfix)\b", re.IGNORECASE)
TITLE = re.compile(r"#[ \t]+bugs\b", re.IGNORECASE)
TO_CHECK = re.compile(r"##[ \t]+to check\b", re.IGNORECASE)
FENCE = re.compile(r"```|~~~")


def found(text):
    """How to show what was found where something else was expected."""
    return "'%s'" % text if text else "nothing"


def looks_like_bug(text, in_fence):
    """Is this text (its Markdown prefix removed) probably meant as a bug heading?"""
    if TAG.search(text):
        return True
    hashes = len(text) - len(text.lstrip("#"))
    body = text.lstrip("#").strip()
    start = BUG_ID.match(body)
    if hashes and not in_fence and (start or body.startswith("[")):
        return True  # a heading that starts with a bug ID or a [bracket]
    if not start:
        return False
    rest = body[start.end():]  # a bug ID, then a severity right away or a severity and a status
    return bool(SEVERITY_NEXT.match(rest) or (SEVERITY_WORD.search(rest) and STATUS_WORD.search(rest)))


def must_be_a_bug(line, in_fence):
    """Lines that must be a valid bug heading: every plain ## heading outside a code block
    (except ## To check), and every other line that looks like an attempt at one."""
    text = PREFIX.sub("", line, count=1)
    plain_level_2 = text == line and re.match(r"##(?!#)", line)
    if plain_level_2 and not in_fence and not TO_CHECK.match(line):
        return True
    return looks_like_bug(text, in_fence)


def heading_problem(line):
    """What is wrong with a line that must be a bug heading, in plain words. '' when it is fine."""
    text = PREFIX.sub("", line, count=1)
    if len(text) - len(text.lstrip("#")) != 2:
        return "a bug heading starts with exactly two # signs and a space"
    if text != line:
        return "put the ## at the very start of the line: no space, tab, >, -, 1. or | before it"
    if not line.startswith("## "):
        return "put one space after the ## (not a tab, and not nothing)"
    parts = line[3:].split(None, 3) + ["", "", "", ""]  # ID, [severity], [status], title
    bug_id, severity, status, title = parts[:4]
    if not re.match(r"B[0-9]{3,}$", bug_id):
        if BUG_ID.match(bug_id):
            return "the ID must be a capital B and three digits, like B001 (found %s)" % found(bug_id)
        return ("every ## heading is either a bug that starts with an ID like B001, or ## To check "
                "(found %s)" % found(bug_id))
    if severity not in ["[%s]" % word for word in SEVERITIES]:
        return ("after the ID comes the severity: [critical], [high], [medium] or [low] (found %s)"
                % found(severity))
    if status not in ["[%s]" % word for word in STATUSES]:
        return ("after the severity comes the status: [open], [fixed] or [wontfix] (found %s)"
                % found(status))
    if not title.strip():
        return "the title is missing: say in a few words what is wrong"
    return ""


def parse(text):
    """Read the text of bugs.md. Pure: no file access, so tests can call it directly.
    Returns (bugs, problems). A bug is a dict with id, severity, status, title and line.
    A problem is (line number, the line, what is wrong with it)."""
    bugs, problems, first_line = [], [], {}
    lines = [INVISIBLE.sub("", line).rstrip() for line in re.split(r"\r\n|\r|\n", text)]
    in_fence, fence, has_title = False, (0, ""), False
    for number, line in enumerate(lines, start=1):
        if FENCE.match(PREFIX.sub("", line, count=1)):
            in_fence, fence = not in_fence, (number, line)
            continue
        has_title = has_title or (not in_fence and bool(TITLE.match(line)))
        if not must_be_a_bug(line, in_fence):
            continue
        problem = heading_problem(line)
        if not problem:
            bug_id, severity, status, title = line[3:].split(None, 3)
            if bug_id in first_line:
                problem = "%s is already used on line %d: give each bug its own ID" % (
                    bug_id, first_line[bug_id])
            else:
                first_line[bug_id] = number
                bugs.append({"id": bug_id, "severity": severity[1:-1], "status": status[1:-1],
                             "title": title.strip(), "line": number})
        if problem:
            problems.append((number, line, problem))
    if in_fence:
        problems.append(fence + ("this code block is never closed: end it with a line of ```",))
    if not has_title:
        problems.insert(0, (1, lines[0], "bugs.md starts with the title '# Bugs'; without it this "
                                         "may be an empty, cut-off or wrong file"))
    return bugs, problems


def summarize(bugs, path, fail_on):
    """The open bugs as findings, most severe first, and the counts."""
    for bug in bugs:
        bug["where"] = "%s:%d" % (path, bug["line"])
    findings = []
    for bug in sorted(bugs, key=lambda bug: (SEVERITIES.index(bug["severity"]), bug["line"])):
        if bug["status"] == "open":
            blocks = SEVERITIES.index(bug["severity"]) <= SEVERITIES.index(fail_on)
            why = "an open %s bug%s (%s)" % (bug["severity"], " blocks the test phase" if blocks else "",
                                            MEANING[bug["severity"]])
            fix = "write a test that fails, fix the bug, then mark it [fixed] with the commit"
            findings.append(dict(bug, why=why, fix=fix, blocks=blocks))
    summary = {word: len([bug for bug in bugs if bug["status"] == word]) for word in STATUSES}
    summary.update(total=len(bugs), fail_on=fail_on, failed=any(bug["blocks"] for bug in findings))
    for name, items in (("all_by_severity", bugs), ("open_by_severity", findings)):
        summary[name] = {sev: len([bug for bug in items if bug["severity"] == sev]) for sev in SEVERITIES}
    return findings, summary


def bug_block(bug):
    """Two lines for one bug: severity, ID and title, then where its details are."""
    return ["%-8s  %s  %s" % (bug["severity"].upper(), bug["id"], bug["title"]),
            "          details: %s, line %d" % (bug["where"].rsplit(":", 1)[0], bug["line"]), ""]


def counts(numbers):
    """'1 critical, 2 low' from {'critical': 1, 'high': 0, 'low': 2}."""
    return ", ".join("%d %s" % (numbers[sev], sev) for sev in SEVERITIES if numbers.get(sev))


def format_human(findings, summary, bugs=()):
    """The plain-text report: the open bugs, the serious ones the user accepted, the counts and
    the verdict."""
    lines = []
    for bug in findings:
        lines += bug_block(bug)
    accepted = [bug for bug in bugs if bug["status"] == "wontfix" and bug["severity"] in ("critical", "high")]
    if accepted:  # serious bugs the user chose to keep: shown every time, never only counted
        lines.append("Accepted by the user as wontfix, so still in the app:")
        for bug in accepted:
            lines += bug_block(bug)
    closed = "%d fixed, %d wontfix" % (summary["fixed"], summary["wontfix"])
    if not summary["total"]:
        lines.append("No bugs listed.")
    else:
        lines.append("%d bug%s listed: %s." % (summary["total"], "" if summary["total"] == 1 else "s",
                                                counts(summary["all_by_severity"])))
        if summary["open"]:
            lines.append("%d open (%s), %s." % (summary["open"], counts(summary["open_by_severity"]), closed))
        else:
            lines.append("No open bugs, %s." % closed)
    if summary["failed"]:
        lines.append("FAIL: at least one open bug is %s or worse. Fix it with a test, then mark it "
                     "[fixed]." % summary["fail_on"])
    else:
        lines.append("PASS: no open bug is %s or worse." % summary["fail_on"])
    return "\n".join(lines)


def format_problems(path, problems):
    """The error report for a file that cannot be read as a bug list."""
    lines = ["error: %s cannot be read as forge's bug list. Fix these lines:" % path]
    for number, line, problem in problems:
        shown = line if len(line) <= 120 else line[:117] + "..."
        lines += ["  line %d: %s" % (number, shown or "(empty)"), "          " + problem]
    lines += ["The form is: " + EXAMPLE,
              "Run bugs.py again after the fix. Until then the bug count cannot be trusted."]
    return "\n".join(lines)


def read_text(path):
    """The text of the file. UTF-16 and UTF-32 need a byte order mark; other NUL bytes mean
    the file is not text (ValueError). Bytes that are not UTF-8 are replaced, not fatal."""
    with open(path, "rb") as handle:
        data = handle.read()
    for mark, codec in ((codecs.BOM_UTF32_LE, "utf-32"), (codecs.BOM_UTF32_BE, "utf-32"),
                        (codecs.BOM_UTF16_LE, "utf-16"), (codecs.BOM_UTF16_BE, "utf-16")):
        if data.startswith(mark):  # UTF-32 first: its little-endian mark starts like UTF-16's
            return data.decode(codec, errors="replace")
    if b"\x00" in data:
        raise ValueError("it holds NUL bytes (UTF-16 without a byte order mark?), save it as UTF-8")
    return data.decode("utf-8-sig", errors="replace")  # -sig: skip a byte order mark


def say(text, stream=None):
    """Print text. Characters the terminal cannot show (an emoji in a title) come out as
    escapes such as \\U0001f600. A reader that stops early (`| head`) is fine, not a crash."""
    stream = stream or sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        print(text.encode(encoding, "backslashreplace").decode(encoding), file=stream)
        stream.flush()
    except BrokenPipeError:  # send the rest to nowhere, so the exit code still tells the verdict
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), stream.fileno())
        except (OSError, ValueError, AttributeError):
            pass


def main(argv=None):
    """Run the check from the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    parser = argparse.ArgumentParser(description="List the open bugs in forge-work/bugs.md and "
                                                 "fail when one is too serious to move on.")
    parser.add_argument("file", help="the bug list, normally forge-work/bugs.md")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high",
                        help="exit 1 when an open bug is this bad or worse (default: high)")
    args = parser.parse_args(argv)
    try:
        text = read_text(args.file)
    except (OSError, ValueError) as error:  # missing, a folder, no permission, not text
        say("error: cannot read %s: %s. forge-test always writes it as text, also when there are "
            "no bugs." % (args.file, getattr(error, "strerror", None) or error), sys.stderr)
        return 2
    bugs, problems = parse(text)
    if problems:
        say(format_problems(args.file, problems), sys.stderr)
        return 2
    findings, summary = summarize(bugs, args.file, args.fail_on)
    if args.json:
        say(json.dumps({"findings": findings, "bugs": bugs, "summary": summary}, indent=2))
    else:
        say(format_human(findings, summary, bugs))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
