#!/usr/bin/env python3
"""Is a phase's work there, besides its report? The forge gate's checks of the work files: the feature
list, the design tokens, the end-to-end specs, the screenshots forge-check diff compared and the app's new
name. phasecheck.py runs it for the exit checks of a phase. Run it from the project root. It reads
files; it changes nothing.

Usage:
    python3 workcheck.py features forge-work/features.csv --theirs
    python3 workcheck.py built forge-work/features.csv
    python3 workcheck.py tokens forge-work/design/tokens.json ../forge-design/tokens.json
    python3 workcheck.py specs 'e2e/**/*.spec.*' 'e2e/**/*.test.*'
    python3 workcheck.py compared forge-work/screens
    python3 workcheck.py named forge-work/brand.json --json

features FILE: features.csv in the contract: the header feature,area,priority,original,clone,notes,
  6 cells a row, values parity.py reads (empty is yes for original, no for clone), a feature name, a
  reason for each skip; not only the example rows of ../forge-research/features.csv; and a must-have
  that is not skipped. --theirs: one that the original has (original yes), so parity.py can score it.
built FILE: each must-have is built (clone yes), or partial or skip with a note on what is missing or
  why, and at least one is built.
tokens FILE TEMPLATE: the JSON FILE holds values of its own, not every value of TEMPLATE (keys that
  start with _ are notes).
specs PATTERN...: a file like one of the patterns (** is any folders), outside node_modules.
compared FOLDER: when FOLDER holds reference screenshots (S07.png, S07-mobile.png), forge-check diff
  compared them: one .diff.json at least, and each one a JSON object. No reference screenshot
  (recon could take none): nothing to compare.
named FILE: the "name" in the JSON FILE (brand.json) is in a file of the app, in any case: outside
  forge-work/, dependencies, builds, e2e/, .env files, links and FILE itself.

Exit codes:
    0  the check passes
    1  it fails: the output says what and how to fix it
    2  a file it needs cannot be read
"""

import argparse
import csv
import glob
import json
import os
import re
import sys

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the forge skill pack
HEADER = ["feature", "area", "priority", "original", "clone", "notes"]
VALUES = (("priority", 2, ("must", "should", "could")), ("original", 3, ("yes", "no", "")),
          ("clone", 4, ("yes", "partial", "no", "skip", "")))  # as parity.py reads them: empty is yes, no
SKIP = {".git", "node_modules", "vendor", "venv", ".venv", "__pycache__", ".next", "dist", "build", "out",
        "coverage", "forge-work", "e2e"}  # dependencies, builds, notes and tests: not the app people see


def read(path):
    with open(path, encoding="utf-8-sig") as handle:  # Excel saves CSV with a BOM
        return handle.read()


def cut(lines):
    """At most 12 lines: the start says what is wrong; the rest is one command away."""
    return lines if len(lines) <= 12 else lines[:11] + ["... %d more lines: run it to see them" % (len(lines) - 11)]


def csv_rows(text):
    reader = csv.reader(text.splitlines(True))
    return [(reader.line_num, [cell.strip() for cell in row]) for row in reader]  # (line number, cells)


def feature_rows(name):
    """The rows below the contract header as (line, cells), or else a failed check: a row that is not 6
    cells, a value not in VALUES, an empty feature name or a skip without a reason."""
    rows, problems = csv_rows(read(name)), []
    if not rows or [cell.lower() for cell in rows[0][1]] != HEADER:
        return None, (False, "the first line of %s is not exactly %s" % (name, ",".join(HEADER)), [])
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


def check_features(name, theirs=False):
    body, failed = feature_rows(name)
    if failed:
        return failed
    example = os.path.join(PACK, "forge-research", "features.csv")
    examples = [row for _, row in csv_rows(read(example))] if os.path.isfile(example) else []
    if body and all(row in examples for _, row in body):
        return False, "%s has only example rows of ../forge-research/features.csv, not this app's features" % name, []
    musts = sum(1 for _, row in body if row[2].lower() == "must" and row[4].lower() != "skip"
                and not (theirs and row[3].lower() == "no"))
    return musts > 0, "%s has the contract header and %d row(s) with priority must, not skipped%s" % (
        name, musts, ", that the original has" if theirs else ""), []


def check_built(name):
    """Idea mode has no diff phase: nothing after the build checks the clone column."""
    body, failed = feature_rows(name)
    if failed:
        return failed
    musts = [(line, row, row[4].lower()) for line, row in body if row[2].lower() == "must"]
    built = sum(1 for _, _, clone in musts if clone == "yes")
    left = ["line %d: %s, clone %s" % (line, row[0], "partial, no note" if clone == "partial" else clone or "empty")
            for line, row, clone in musts if clone in ("no", "") or (clone == "partial" and not row[5])]
    if left or not built:
        return False, "%s: %d of %d must-have(s) built. Each needs clone yes, or partial or skip with a note on " \
                      "what is missing or why" % (name, built, len(musts)), cut(left)
    return True, "%s: %d of %d must-have(s) built, the rest partial or skipped with a note" % (
        name, built, len(musts)), []


def check_tokens(name, template):
    mine, theirs = json.loads(read(name)), json.loads(read(template))
    values = [{key: value for key, value in data.items() if not key.startswith("_")} if isinstance(data, dict)
              else data for data in (mine, theirs)]
    if values[0] == values[1]:
        return False, "%s still holds every value of %s" % (name, shown(template)), [
            "Fill in the app's own: measured from the original in clone mode, designed fresh in idea mode."]
    return True, "%s holds values of its own" % name, []


def check_specs(*patterns):
    for pattern in patterns:
        found = sorted(path for path in glob.glob(pattern, recursive=True) if os.path.isfile(path)
                       and "node_modules" not in os.path.normpath(path).split(os.sep))
        if found:
            return True, "end-to-end specs: %s" % found[0].replace(os.sep, "/"), []
    return False, "no end-to-end spec: no file like %s" % " or ".join(patterns), [
        "Write one spec per flow, set up as the top of ../forge-check/e2e.example.spec.ts says."]


def check_compared(folder):
    names = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    shots = [name for name in names if re.match(r"S\d+.*\.png$", name) and not name.endswith(".diff.png")]
    diffs = [name for name in names if name.endswith(".diff.json")]
    if shots and not diffs:
        return False, "%s has %d reference screenshot(s) and no .diff.json" % (folder, len(shots)), [
            "Compare each reference screenshot with the clone's of the same name: ../forge-check/imgdiff.py --json."]
    broken = []
    for name in diffs:
        try:
            broken += [] if isinstance(json.loads(read(os.path.join(folder, name))), dict) else [name]
        except ValueError:
            broken.append(name)
    if broken:
        return False, "%s: %s is not the JSON imgdiff.py writes" % (folder, ", ".join(broken)), [
            "Take the two screenshots again and compare them again, or delete the file."]
    if not shots:
        return True, "%s holds no reference screenshot, so there is no layout to compare" % folder, []
    return True, "%s: %d comparison(s) of %d reference screenshot(s)" % (folder, len(diffs), len(shots)), []


def check_named(config):
    name = json.loads(read(config)).get("name")
    name = name.strip() if isinstance(name, str) else ""
    for folder, subfolders, files in os.walk(".") if name else ():
        subfolders[:] = sorted(sub for sub in subfolders if sub not in SKIP)
        for file in sorted(entry for entry in files if not entry.startswith(".env")):  # the user's secrets
            path = os.path.join(folder, file)
            if os.path.islink(path) or os.path.realpath(path) == os.path.realpath(config):  # as sweep.py
                continue  # a link may point out of the project; the brand file itself is not the app
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    if name.lower() in handle.read(1048576).lower():
                        return True, "the app carries the name %s: %s has it" % (
                            name, os.path.relpath(path).replace(os.sep, "/")), []
            except OSError:
                continue
    return False, "the name %s from %s is in no file of the app" % (name or "(none)", config), [
        "Put it in the app name setting, the titles, the manifest and the README (forge-design brand Step 6)."]


def shown(path):
    """A path the way the skills write it: ../forge-design/tokens.json for a file of the pack."""
    try:
        inside = os.path.relpath(os.path.abspath(path), PACK)
    except ValueError:  # Windows: on another drive than the pack
        return path
    return path if inside.startswith("..") else "../" + inside.replace(os.sep, "/")


def main(argv=None):
    """Run one check. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):  # what the console cannot show comes out as \u escapes, not a crash
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", metavar="CHECK", required=True)
    for command, arguments, words in (
            ("features", ["file"], "features.csv in the contract, with a must-have"),
            ("built", ["file"], "each must-have built, or partial or skipped with a note"),
            ("tokens", ["file", "template"], "tokens with values of their own"),
            ("specs", ["pattern"], "an end-to-end spec"), ("compared", ["folder"], "the screenshots compared"),
            ("named", ["file"], "the app carries the name in brand.json")):
        sub = commands.add_parser(command, help=words)
        for argument in arguments:
            sub.add_argument(argument, nargs="+" if argument == "pattern" else None)
        sub.add_argument("--json", action="store_true", help="print machine-readable JSON")
        if command == "features":
            sub.add_argument("--theirs", action="store_true", help="a must-have the original has")
    args = parser.parse_args(argv)
    run = {"features": lambda: check_features(args.file, args.theirs), "built": lambda: check_built(args.file),
           "tokens": lambda: check_tokens(args.file, args.template), "specs": lambda: check_specs(*args.pattern),
           "compared": lambda: check_compared(args.folder), "named": lambda: check_named(args.file)}
    try:
        ok, what, output = run[args.command]()
    except (OSError, ValueError, RecursionError, csv.Error) as error:  # missing, a folder, not UTF-8, JSON or CSV
        print("error: %s" % error, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"check": args.command, "ok": ok, "checks": [{"ok": ok, "what": what, "output": output}]},
                         indent=2))
    else:
        print("\n".join(["%-4s  %s" % ("ok" if ok else "FAIL", what)] + ["      " + line for line in output]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
