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
import subprocess
import sys

TIMEOUT = 600  # seconds per script: a secret scan of a big project takes a while
PACK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")  # the forge skill pack
FEATURES_HEADER = ["feature", "area", "priority", "original", "clone", "notes"]
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


def csv_rows(text):
    return [[cell.strip() for cell in row] for row in csv.reader(text.splitlines(True))]


def check_features(root, name):
    """The contract header and at least one must-have row, and not only rows of the template's example."""
    rows, example = csv_rows(read_text(root, name)), os.path.join(PACK, "forge-recon", "features.csv")
    if not rows or [cell.lower() for cell in rows[0]] != FEATURES_HEADER:
        return False, "the first line of %s is not exactly %s" % (name, ",".join(FEATURES_HEADER))
    body = [row for row in rows[1:] if any(row)]
    examples = csv_rows(read_text(example)) if os.path.isfile(example) else []
    if body and all(row in examples for row in body):
        return False, "%s has only example rows of ../forge-recon/features.csv, not this app's features" % name
    musts = sum(1 for row in body if len(row) > 2 and row[2].lower() == "must")
    return musts > 0, "%s has the contract header and %d row(s) with priority must" % (name, musts)


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
    shown = " ".join(["python3", "../" + script] + list(args))
    try:
        done = subprocess.run([sys.executable, os.path.join(PACK, script)] + list(args), cwd=root, timeout=TIMEOUT,
                              stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return False, "%s did not finish within %d seconds" % (shown, TIMEOUT)
    if done.returncode == 0 and done.stdout.strip():
        return True, "%s exits 0" % shown
    meaning = ("it crashed: this is a bug in that script" if "Traceback (most recent call last)" in done.stderr
               else "it printed nothing, so it checked nothing" if done.returncode == 0
               else {1: "it found problems", 2: "it could not check"}.get(done.returncode, "it stopped"))
    lines = [line.rstrip()[:200] for line in (done.stderr + done.stdout).splitlines() if line.strip()]
    if len(lines) > 12:  # the start says what is wrong; the rest is one command away
        lines = lines[:11] + ["... %d more lines: run it to see them" % (len(lines) - 11)]
    return False, "%s exits %d: %s" % (shown, done.returncode, meaning), lines


def check_fresh(root, name, since):
    """NAME was written after SINCE, the last go before this phase: an older report says nothing of now."""
    if os.path.getmtime(os.path.join(root, name)) >= datetime.datetime.fromisoformat(since).timestamp():
        return True, "%s is newer than the last go (%s)" % (name, since)
    return False, "%s is older than the last go (%s): the app may have changed since. Run the phase's " \
                  "skill again in full, so it writes a new one" % (name, since)


# The exit checks of each phase: (check function, its arguments...), run in the project root.
CHECKS = {
    "recon": [(check_file, "forge-work/recon.md", TODO), (check_features, "forge-work/features.csv")],
    "compare": [(check_file, "forge-work/compare.md")],
    "plan": [(check_file, "forge-work/plan.md", TODO), (check_features, "forge-work/features.csv"),
             (check_line, "forge-work/plan.md", "Profile", "laravel", "django", "next", "static"),
             (check_line, "forge-work/plan.md", "PWA", "yes", "no")],
    "design": [(check_json, "forge-work/design/tokens.json"),
               (check_run, "forge-design/contrast.py", "forge-work/design/tokens.json"),
               (check_file, "forge-work/design/components.md", CHOICE)],
    "build": [(check_file, "forge-work/build-log.md")],
    "test": [(check_file, "forge-work/test-plan.md", TODO), (check_run, "forge-test/bugs.py", "forge-work/bugs.md")],
    "diff": [(check_run, "forge-diff/parity.py", "forge-work/features.csv")],
    "brand": [(check_json, "forge-work/brand.json", "name", "avoid"),
              (check_run, "forge-brand/sweep.py", ".", "--config", "forge-work/brand.json")],
    "launch": [(check_file, "forge-work/launch.md", TODO)],
    "secure": [(check_line, "forge-work/security.md", "Verdict", "PASS"),
               (check_run, "forge-secure/secretscan.py", ".")],
    "pack": [(check_file, "Dockerfile"),
             (check_file, "compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"),
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
