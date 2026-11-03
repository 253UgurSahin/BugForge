#!/usr/bin/env python3
"""Is the work of one forge phase there and finished? These are the exit checks the forge gate runs
before it records a phase as done: `gate.py check PHASE` and `gate.py done PHASE` run this script.
Run it from the project root. It reads files and runs the other skills' scripts; it changes nothing.

Usage:
    python3 phasecheck.py plan
    python3 phasecheck.py secure --since 2026-10-27T09:51:44+00:00 --json

--since TIME: the phase's report (secure: forge-work/security.md) must be newer than TIME, the last go
before the phase, so a report from the build or from an earlier round does not count.

Exit codes:
    0  every exit check passes
    1  a check fails: the output says which and why
    2  bad usage: an unknown phase, or a TIME that is not like 2026-10-27T09:51:44+00:00
"""

import argparse
import csv
import datetime
import json
import os
import re
import shlex
import subprocess
import sys

TIMEOUT = 600  # seconds per script: a secret scan of a big project takes a while
PACK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")  # the forge skill pack
PYTHON = shlex.quote(sys.executable) if os.name == "nt" and sys.executable else "python3"  # no python3 on Windows
FEATURES_HEADER = ["feature", "area", "priority", "original", "clone", "notes"]
VALUES = (("priority", 2, ("must", "should", "could")), ("original", 3, ("yes", "no", "")),
          ("clone", 4, ("yes", "partial", "no", "skip", "")))  # as parity.py reads them: empty is yes, no
COMPOSE = ("compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml")
PLAN_SECTIONS = ("Entities and schema", "Routes and API", "Build order", "Decisions log")  # of forge-plan/plan.md
COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.S)
UNSEEN = re.compile(r"<!--.*?(?:-->|\Z)|^ {0,3}(`{3,}|~{3,}).*?(?:^ {0,3}\1|\Z)", re.S | re.M)  # comments, code
TODO = re.compile(r"\{\{[^\s{}][^{}\n]{0,80}\}\}")  # a template's {{...}}; Blade and Jinja write {{ x }}
CHOICE = re.compile(r"<[^<>\n]*\|[^<>\n]*>")  # a template's <a|b>, as in forge-design/components.md
FRESH = {"secure": "forge-work/security.md"}  # the report that --since applies to


def read_text(*parts):
    """The text of the file at PARTS. A missing file raises FileNotFoundError: run_checks says so."""
    with open(os.path.join(*parts), encoding="utf-8-sig") as handle:
        return handle.read()


def check_file(root, *names):
    """One of NAMES exists and has text. A pattern after the names finds a template's placeholders: none
    may be left outside comments and code blocks (those may hold `{{ }}` of their own, as in Blade)."""
    names, todo = (names, None) if isinstance(names[-1], str) else (names[:-1], names[-1])
    found = [name for name in names if os.path.isfile(os.path.join(root, name))]
    if not found:
        return False, "%s is missing" % " or ".join(names)
    text = read_text(root, found[0])
    left = todo.findall(UNSEEN.sub("", text)) if todo else []
    if left:
        return False, "%s still has %d template placeholder(s), such as %s" % (found[0], len(left), left[0][:60])
    return bool(text.strip()), "%s %s" % (found[0], "exists" if text.strip() else "is empty")


def cut(lines):
    """At most 12 lines: the start says what is wrong; the rest is one command away."""
    return lines if len(lines) <= 12 else lines[:11] + ["... %d more lines: run it to see them" % (len(lines) - 11)]


def csv_rows(text):
    reader = csv.reader(text.splitlines(True))
    return [(reader.line_num, [cell.strip() for cell in row]) for row in reader]  # (line number, cells)


def feature_rows(root, name):
    """The rows below the contract header as (line, cells), or else a failed check's answer: a row that is
    not 6 cells, a value not in VALUES, an empty feature name or a skip without a reason."""
    rows, problems = csv_rows(read_text(root, name)), []
    if not rows or [cell.lower() for cell in rows[0][1]] != FEATURES_HEADER:
        return None, (False, "the first line of %s is not exactly %s" % (name, ",".join(FEATURES_HEADER)))
    body = [(line, row) for line, row in rows[1:] if any(row)]
    for line, row in body:
        if len(row) != 6:
            problems.append("line %d has %d cells, not 6: put text with a comma in double quotes" % (line, len(row)))
            continue
        problems += ["line %d: %s '%s' is not one of %s" % (line, label, row[at], ", ".join(filter(None, allowed)))
                     for label, at, allowed in VALUES if row[at].lower() not in allowed]
        if not row[0]:
            problems.append("line %d: the feature name is empty" % line)
        if row[4].lower() == "skip" and not row[5]:
            problems.append("line %d: %s is skipped without a reason in notes" % (line, row[0]))
    if problems:
        return None, (False, "%s breaks the contract in %d place(s)" % (name, len(problems)), cut(problems))
    return body, None


def check_features(root, name, theirs=False):
    """Every row in the contract, not only rows of the template's example, and a must-have that is not
    skipped. THEIRS (recon): one the original has (original yes), so parity.py has something to score."""
    body, failed = feature_rows(root, name)
    if failed:
        return failed
    example = os.path.join(PACK, "forge-recon", "features.csv")
    examples = [row for _, row in csv_rows(read_text(example))] if os.path.isfile(example) else []
    if body and all(row in examples for _, row in body):
        return False, "%s has only example rows of ../forge-recon/features.csv, not this app's features" % name
    musts = sum(1 for _, row in body if row[2].lower() == "must" and row[4].lower() != "skip"
                and not (theirs and row[3].lower() == "no"))
    return musts > 0, "%s has the contract header and %d row(s) with priority must, not skipped%s" % (
        name, musts, ", that the original has" if theirs else "")


def check_built(root, name):
    """Each must-have is built (clone yes), or partial or skip with a note on what is missing or why, and
    at least one is built. Idea mode has no diff phase: nothing after this checks the clone column."""
    body, failed = feature_rows(root, name)
    if failed:
        return failed
    musts = [(line, row, row[4].lower()) for line, row in body if row[2].lower() == "must"]
    built = sum(1 for _, _, clone in musts if clone == "yes")
    left = ["line %d: %s, clone %s" % (line, row[0], "partial, no note" if clone == "partial" else clone or "empty")
            for line, row, clone in musts if clone in ("no", "") or (clone == "partial" and not row[5])]
    if left or not built:
        return False, "%s: %d of %d must-have(s) built. Each needs clone yes, or partial or skip with a note on " \
                      "what is missing or why" % (name, built, len(musts)), cut(left)
    return True, "%s: %d of %d must-have(s) built, the rest partial or skipped with a note" % (name, built, len(musts))


def check_sections(root, name, *titles):
    """Each of TITLES starts a `## ` heading in NAME with text under it. Code blocks count as text (a
    schema is often only SQL), comments do not."""
    parts = re.split(r"(?m)^ {0,3}#{1,2}[ \t]+(.*)$", COMMENT.sub("", read_text(root, name)))
    sections = [(head.strip().lower(), body.strip()) for head, body in zip(parts[1::2], parts[2::2])]
    empty = [title for title in titles if not any(head.startswith(title.lower()) and body for head, body in sections)]
    if empty:
        return False, "%s needs text under ## %s, as in ../forge-plan/plan.md" % (name, ", ## ".join(empty))
    return True, "%s has text under ## %s" % (name, ", ## ".join(titles))


def cases(text):
    """The rows of the first table in TEXT with the columns case and result, as dicts (its line 2 is ---)."""
    for table in re.findall(r"(?m)(?:^[ \t]*\|.*\n?)+", text):
        rows = [[cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
                for line in table.splitlines()]
        header = [cell.lower() for cell in rows[0]]
        if {"case", "result"} <= set(header):
            return [dict(zip(header, row + [""] * len(header))) for row in rows[2:] if any(row)]
    return []


def check_cases(root, name):
    """The test plan's Cases table holds this app's cases, not only the example rows of the template, and
    every row has a result: the plan was made and run."""
    rows, example = cases(UNSEEN.sub("", read_text(root, name))), os.path.join(PACK, "forge-test", "test-plan.md")
    examples = cases(read_text(example)) if os.path.isfile(example) else []
    if not rows:
        return False, "%s has no Cases table with rows: | case | ... | result |" % name
    if all(row in examples for row in rows):
        return False, "%s has only the example rows of ../forge-test/test-plan.md, not this app's cases" % name
    left = [row.get("case") or "(no case ID)" for row in rows if not row.get("result")]
    if left:
        return False, "%s has %d case row(s) without a result: %s" % (name, len(left), ", ".join(left)[:120])
    return True, "%s has %d case row(s), each with a result" % (name, len(rows))


def check_line(root, name, label, *allowed):
    """Exactly one line about LABEL outside comments and code blocks, and it is `LABEL: value` with a value
    from ALLOWED. `**Label:** x`, `## label: x` and `> Label : x` are lines about it too, so they count."""
    text = UNSEEN.sub("", read_text(root, name))
    found = [line.rstrip() for line in re.findall(r"(?im)^[ \t>#*_]*%s[ \t*_]*:.*$" % label, text)]
    if len(found) == 1 and found[0].startswith(label + ":") and found[0][len(label) + 1:].strip() in allowed:
        return True, "%s says %s" % (name, found[0])
    return False, "%s needs exactly one line `%s: %s`, outside comments and code blocks (found: %s)" % (
        name, label, "|".join(allowed), " / ".join(found)[:120] or "none")


def check_json(root, name, *keys):
    """A JSON object (json.loads says where it breaks) with each of KEYS filled in: name a text, others a list."""
    data = json.loads(read_text(root, name))
    if not isinstance(data, dict):
        return False, "%s is not a JSON object" % name
    wrong = [key for key in keys if not isinstance(data.get(key), str if key == "name" else list)
             or not (data[key].strip() if key == "name" else data[key])]
    return not wrong, "%s parses" % name + "".join(', but "%s" is missing, empty or not a %s'
                                                   % (key, "text" if key == "name" else "list") for key in wrong)


def check_run(root, script, *args):
    """Run another forge skill's script in ROOT. Passes when it exits 0 and printed its report; else shows
    its output. Every forge script prints what it checked, so no output means it checked nothing."""
    shown = " ".join([PYTHON, "../" + script] + list(args))
    try:  # the script writes UTF-8 and is read as such, also where pipes are cp1252 (Windows)
        done = subprocess.run([sys.executable, os.path.join(PACK, script)] + list(args), cwd=root, timeout=TIMEOUT,
                              stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8", errors="replace",
                              env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    except subprocess.TimeoutExpired:
        return False, "%s did not finish within %d seconds" % (shown, TIMEOUT)
    if done.returncode == 0 and done.stdout.strip():
        return True, "%s exits 0" % shown
    meaning = ("it crashed: this is a bug in that script" if "Traceback (most recent call last)" in done.stderr
               else "it printed nothing, so it checked nothing" if done.returncode == 0
               else {1: "it found problems", 2: "it could not check"}.get(done.returncode, "it stopped"))
    lines = [line.rstrip()[:200] for line in (done.stderr + done.stdout).splitlines() if line.strip()]
    return False, "%s exits %d: %s" % (shown, done.returncode, meaning), cut(lines)


def check_fresh(root, name, since):
    """NAME was written after SINCE, the last go before this phase: an older report says nothing of now."""
    if os.path.getmtime(os.path.join(root, name)) >= datetime.datetime.fromisoformat(since).timestamp():
        return True, "%s is newer than the last go (%s)" % (name, since)
    return False, "%s is older than the last go (%s): the app may have changed since. Run the phase's " \
                  "skill again in full, so it writes a new one" % (name, since)


# The exit checks of each phase: (check function, its arguments...), run in the project root.
CHECKS = {
    "recon": [(check_file, "forge-work/recon.md", TODO), (check_features, "forge-work/features.csv", True)],
    "compare": [(check_file, "forge-work/compare.md")],
    "plan": [(check_file, "forge-work/plan.md", TODO), (check_features, "forge-work/features.csv"),
             (check_line, "forge-work/plan.md", "Profile", "laravel", "django", "next", "static"),
             (check_line, "forge-work/plan.md", "PWA", "yes", "no"),
             (check_sections, "forge-work/plan.md") + PLAN_SECTIONS],
    "design": [(check_json, "forge-work/design/tokens.json"),
               (check_run, "forge-design/contrast.py", "forge-work/design/tokens.json"),
               (check_file, "forge-work/design/components.md", CHOICE)],
    "build": [(check_file, "forge-work/build-log.md"), (check_built, "forge-work/features.csv"),
              (check_file,) + COMPOSE],  # forge-build starts the app in its compose stack
    "test": [(check_file, "forge-work/test-plan.md", TODO), (check_cases, "forge-work/test-plan.md"),
             (check_run, "forge-test/bugs.py", "forge-work/bugs.md")],
    "diff": [(check_run, "forge-diff/parity.py", "forge-work/features.csv")],
    "brand": [(check_json, "forge-work/brand.json", "name", "avoid"),
              (check_run, "forge-brand/sweep.py", ".", "--config", "forge-work/brand.json")],
    "launch": [(check_file, "forge-work/launch.md", TODO)],
    "secure": [(check_line, "forge-work/security.md", "Verdict", "PASS"),
               (check_run, "forge-secure/secretscan.py", ".")],
    "pack": [(check_file, "Dockerfile"), (check_file,) + COMPOSE,
             (check_file, ".env.example"), (check_file, ".dockerignore"), (check_run, "forge-pack/packcheck.py", "."),
             (check_run, "forge-secure/secretscan.py", ".")],  # pack writes files after secure
    "audit": [(check_file, "forge-work/audit.md")],
    "inspect": [(check_file, "forge-work/inspect.md")],
    "improve": [(check_file, "forge-work/improve.md"), (check_run, "forge/gitguard.py", ".")],
}


def run_checks(root, phase, since=None):
    """Every exit check of PHASE in ROOT, plus the age of its report when SINCE is given: a list of
    {"ok", "what", "output"}. A missing file is named once, not once per check that reads it."""
    fresh = [(check_fresh, FRESH[phase], since)] if since and phase in FRESH else []
    results = []
    for check, *args in CHECKS[phase] + fresh:
        try:
            answer = check(root, *args)
        except FileNotFoundError:
            answer = False, "%s is missing" % args[0]
        except (OSError, ValueError, RecursionError, csv.Error) as error:  # a folder, not UTF-8, JSON or CSV
            answer = False, "%s cannot be read: %s" % (args[0], error)
        if answer[1] not in [item["what"] for item in results]:
            results.append({"ok": answer[0], "what": answer[1], "output": answer[2] if len(answer) > 2 else []})
    return results


def show_checks(phase, results, as_json=False):
    """Print the results, in plain words or as JSON. Returns 0 when every check passed, else 1."""
    ok = all(item["ok"] for item in results)
    if as_json:
        print(json.dumps({"phase": phase, "ok": ok, "checks": results}, indent=2))
        return 0 if ok else 1
    print("Exit checks for %s:" % phase)
    for item in results:
        print("\n".join(["  %-4s  %s" % ("ok" if item["ok"] else "FAIL", item["what"])]
                        + ["          " + line for line in item["output"]]))
    print("PASS: every exit check of %s passes." % phase if ok else "FAIL: %s is not finished. Fix what "
          "FAIL names within the phase, or ask the user. Never work around the gate." % phase)
    return 0 if ok else 1


def a_time(text):
    """argparse type for --since: an ISO 8601 time, as gate.py writes it."""
    try:
        datetime.datetime.fromisoformat(text).timestamp()
    except ValueError:
        raise argparse.ArgumentTypeError("not a time like 2026-10-27T09:51:44+00:00: %r" % text)
    return text


def main(argv=None):
    """Run the exit checks of one phase. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):  # what the console cannot show comes out as \u escapes, not a crash
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("phase", choices=list(CHECKS))
    parser.add_argument("--since", type=a_time, metavar="TIME", help="the report must be newer than this time")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    return show_checks(args.phase, run_checks(os.getcwd(), args.phase, args.since), args.json)


if __name__ == "__main__":
    sys.exit(main())
