#!/usr/bin/env python3
"""Compare two rounds of the walk's screenshots and list the screens whose layout changed.

e2e/walk.spec.ts saves one full-page PNG per route, width and colour scheme in
forge-work/test/shots/<round>/. For every PNG with the same name in both folders this script runs
../forge-diff/imgdiff.py, which scores the layout from 0 to 100 (where the outlines of boxes, text
and buttons are; colour does not count, so a colour-only change is not seen here). A pair that
scores under --min is listed as changed, with where on the screen it differs. Shots that only one
round has are listed too. Two files with the same bytes are the same without a comparison.
A change is not always a bug: after a fix it may be the fix itself. Look at each one.

Usage:
    python3 shotcheck.py forge-work/test/shots/r1 forge-work/test/shots/r2
    python3 shotcheck.py BEFORE_DIR AFTER_DIR [--min 90] [--timeout 180] [--json]

Exit codes:
    0  every shot is in both rounds and none changed
    1  a shot changed, or is in only one of the two rounds
    2  could not compare: a folder is missing or has no PNG, or imgdiff.py failed or took too
       long on a pair (the output names it)
"""

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

IMGDIFF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "forge-diff", "imgdiff.py")
MAX_SHOTS = 2000  # more PNGs than this in one folder is not a round of screenshots
MAX_SAME = 50 * 1000 * 1000  # bigger files are not read to see if they are the same bytes
WORKERS = 4  # pairs compared at the same time


def shots(folder):
    """{file name: path} of the PNG files directly in FOLDER. Links are not followed."""
    found = {}
    with os.scandir(folder) as entries:
        for entry in entries:
            if entry.name.lower().endswith(".png") and entry.is_file(follow_symlinks=False):
                found[entry.name] = entry.path
            if len(found) > MAX_SHOTS:
                raise OSError(0, "more than %d PNG files" % MAX_SHOTS, folder)
    return found


def same_bytes(before, after):
    try:
        if os.path.getsize(before) != os.path.getsize(after) or os.path.getsize(before) > MAX_SAME:
            return False
        with open(before, "rb") as one, open(after, "rb") as two:
            return one.read() == two.read()
    except OSError:
        return False


def compare(name, before, after, timeout):
    """One pair: {"name", "score", ...} from imgdiff.py, or {"name", "error"} when it could not run."""
    if same_bytes(before, after):
        return {"name": name, "score": 100.0, "verdict": "matches", "regions": [], "height_delta_pct": 0.0}
    try:
        done = subprocess.run([sys.executable, IMGDIFF, before, after, "--json"], timeout=timeout,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.TimeoutExpired:
        return {"name": name, "error": "imgdiff.py took longer than %d seconds" % timeout}
    except OSError as error:
        return {"name": name, "error": "imgdiff.py could not start (%s)" % (error.strerror or error)}
    try:
        if done.returncode != 0:
            raise ValueError
        report = json.loads(done.stdout.decode("utf-8", errors="replace"))
        return {"name": name, "score": float(report["score"]), "verdict": str(report["verdict"]),
                "regions": [{key: region.get(key) for key in ("where", "x", "y", "w", "h")}
                            for region in report.get("regions", [])[:5]],
                "height_delta_pct": report.get("height_delta_pct", 0.0)}
    except (ValueError, KeyError, TypeError, AttributeError):
        said = done.stderr.decode("utf-8", errors="replace").strip().splitlines()
        return {"name": name, "error": said[-1][:300] if said else "imgdiff.py gave no result (exit %d)" % done.returncode}


def main(argv=None):
    """Compare from the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):  # a cp1252 pipe gets escapes, not a crash
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("before", metavar="BEFORE_DIR", help="the earlier round, such as forge-work/test/shots/r1")
    parser.add_argument("after", metavar="AFTER_DIR", help="the later round, such as forge-work/test/shots/r2")
    parser.add_argument("--min", type=float, default=90.0, metavar="SCORE",
                        help="a pair that scores under this has changed (default: 90, imgdiff's 'matches')")
    parser.add_argument("--timeout", type=int, default=180, metavar="SECONDS",
                        help="the longest one pair may take (default: 180)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    if not 0 <= args.min <= 100 or args.timeout <= 0:
        parser.error("--min is a score from 0 to 100 and --timeout a number of seconds above 0")
    try:
        before, after = shots(args.before), shots(args.after)
        if not os.path.isfile(IMGDIFF):
            raise OSError(0, "imgdiff.py is missing: shotcheck.py needs the whole forge pack", IMGDIFF)
        for folder, found in ((args.before, before), (args.after, after)):
            if not found:
                raise OSError(0, "no PNG files in it (the first round is the baseline: nothing to compare yet)",
                              folder)
    except OSError as error:
        print("error: cannot compare %s: %s" % (error.filename or "the folders", error.strerror or error),
              file=sys.stderr)
        return 2
    both = sorted(set(before) & set(after))
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        pairs = list(pool.map(lambda name: compare(name, before[name], after[name], args.timeout), both))
    errors = [pair for pair in pairs if "error" in pair]
    changed = sorted((pair for pair in pairs if "error" not in pair and pair["score"] < args.min),
                     key=lambda pair: pair["score"])
    same = [pair["name"] for pair in pairs if "error" not in pair and pair["score"] >= args.min]
    only_before, only_after = sorted(set(before) - set(after)), sorted(set(after) - set(before))
    differs = bool(changed or only_before or only_after)
    report = {"before": args.before, "after": args.after, "min": args.min, "changed": changed, "same": same,
              "only_before": only_before, "only_after": only_after, "errors": errors,
              "summary": {"compared": len(pairs) - len(errors), "changed": len(changed), "same": len(same),
                          "only_before": len(only_before), "only_after": len(only_after),
                          "errors": len(errors), "differs": differs}}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for pair in changed:
            print("CHANGED  %s  layout score %.1f (%s)" % (pair["name"], pair["score"], pair["verdict"]))
            for region in pair["regions"]:
                print("         differs at {where}: x={x} y={y} w={w} h={h}".format(**region))
            if abs(pair["height_delta_pct"] or 0) >= 5:
                print("         the page is %.0f%% %s than before" % (
                    abs(pair["height_delta_pct"]), "taller" if pair["height_delta_pct"] > 0 else "shorter"))
        for name in only_before:
            print("MISSING  %s  was in %s, is not in %s: was the route removed or not walked?"
                  % (name, args.before, args.after))
        for name in only_after:
            print("NEW      %s  is only in %s: nothing to compare it with" % (name, args.after))
        print("%d compared: %d changed, %d the same; %d missing, %d new." % (
            report["summary"]["compared"], len(changed), len(same), len(only_before), len(only_after)))
        if changed:
            print("Open both PNGs of each changed shot. Meant by a fix: note it in test-plan.md. "
                  "Not meant: a bug for forge-work/bugs.md, with both files as evidence.")
    for pair in errors:
        print("error: %s could not be compared: %s" % (pair["name"], pair["error"]), file=sys.stderr)
    if errors:
        return 2
    return 1 if differs else 0


if __name__ == "__main__":
    sys.exit(main())
