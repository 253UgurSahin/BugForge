#!/usr/bin/env python3
"""Feature parity: how much of the original app your clone already does, and what is missing.

Reads the feature matrix that forge-recon made and forge-build keeps up to date. Prints a
score, the must-haves done, each area weakest first and the missing features in build order.
With --visual it also folds in the layout scores of imgdiff.py --json. --markdown writes UTF-8.

Usage:
    python3 parity.py forge-work/features.csv
    python3 parity.py forge-work/features.csv --visual forge-work/screens/*.diff.json
    python3 parity.py forge-work/features.csv --markdown > forge-work/parity.md
    python3 parity.py forge-work/features.csv --json
    python3 parity.py forge-work/features.csv --fail-under 80

Columns (extra columns are ignored; area, original and notes may be left out):
    feature   what it does, in plain words ("reschedule a booking")
    area      the screen or flow it belongs to ("booking page")
    priority  must, should or could
    original  yes or no: does the original have it (empty means yes)
    clone     yes, partial, no or skip (empty means no)
    notes     free text. A skip row must say why ("licensed content, out of scope")

Score: must weighs 3, should 2, could 1; yes counts in full, partial half, no not at all.
skip rows and your own extras (original "no") are listed but not scored; a skipped must-have
gets a warning. With --visual the overall score is 80% features and 20% the average layout
score. Scores have one decimal, rounded down: 79.96 is 79.9, never 80.0.

Exit codes:
    0  every scored must-have is done (and the overall score reaches --fail-under)
    1  a must-have is not done (no or partial), no must-have is scored at all, or the
       overall score is under --fail-under
    2  bad input: a missing file, a file not saved as UTF-8 CSV with commas, a missing column,
       an unknown value, a skip without a reason, nothing to score, or a --visual file that
       is not imgdiff.py output
"""

import argparse
import csv
import io
import json
import math
import re
import sys

WEIGHT = {"must": 3, "should": 2, "could": 1}
CREDIT = {"yes": 1.0, "partial": 0.5, "no": 0.0}
STATUS = {"yes": "built", "partial": "half built", "no": "not built", "skip": "left out"}
NEEDED_COLUMNS = ("feature", "priority", "clone")
SAVE_AS = "in Excel use Save As > CSV UTF-8 (Comma delimited)"
MARKDOWN_SIGNS = re.compile(r"([\\`*_\[\]<>|!#])")  # characters that change how markdown looks


class MatrixError(Exception):
    """The matrix or a --visual file cannot be used as it is."""


def rounded_down(value):
    """One decimal, never rounded up: 79.96 is 79.9."""
    return math.floor(value * 10 + 1e-6) / 10.0


def plural(count, word):
    """'1 feature', '2 features'."""
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def load(path):
    """The CSV rows as dicts with lower-case column names, values with their spaces and line
    breaks tidied, and the line number. Rows without any value are left out."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
        if b"\0" in data:  # UTF-16, or not text at all
            raise UnicodeError
        text = data.decode("utf-8-sig")  # -sig: Excel's byte order mark
    except OSError as error:
        raise MatrixError("cannot read %s (%s)" % (path, error.strerror))
    except UnicodeError:
        raise MatrixError("%s is not saved as UTF-8 text: %s" % (path, SAVE_AS))
    reader = csv.DictReader(io.StringIO(text, newline=""))
    columns = [(name or "").strip().lower() for name in reader.fieldnames or []]
    if not columns:
        raise MatrixError("%s is empty" % path)
    if "feature" not in columns and ";" in ",".join(columns):
        raise MatrixError("%s has semicolons between the columns (Excel with Dutch settings does "
                          "that): %s, or replace the semicolons with commas" % (path, SAVE_AS))
    for need in NEEDED_COLUMNS:
        if need not in columns:
            raise MatrixError("%s has no '%s' column. The columns are: "
                              "feature,area,priority,original,clone,notes" % (path, need))
    rows = []
    for raw in reader:
        if None in raw:  # more cells than columns: usually a comma in unquoted text
            raise MatrixError("%s line %d has more cells than there are columns: put text "
                              "that holds a comma in double quotes" % (path, reader.line_num))
        row = {key.strip().lower(): " ".join((value or "").split()) for key, value in raw.items()}
        if any(row.values()):  # a row of only commas is left out
            row["line"] = reader.line_num
            rows.append(row)
    return rows


def check_row(row):
    """Plain words for each value in a row that is not in the contract."""
    line, problems = row["line"], []
    priority, original, clone = (row.get(name, "") for name in ("priority", "original", "clone"))
    if not row.get("feature"):
        problems.append("line %d: the feature name is empty" % line)
    if priority.lower() not in WEIGHT:
        problems.append("line %d: priority '%s' is not must, should or could" % (line, priority))
    if original.lower() not in ("yes", "no", ""):
        problems.append("line %d: original '%s' is not yes or no" % (line, original))
    if clone.lower() not in ("yes", "partial", "no", "skip", ""):
        problems.append("line %d: clone '%s' is not yes, partial, no or skip" % (line, clone))
    if clone.lower() == "skip" and not row.get("notes"):
        problems.append("line %d: '%s' is skipped without a reason: say why in notes"
                        % (line, row.get("feature")))
    return problems


def brief(row):
    """The parts of a row that the report shows."""
    return {"feature": row.get("feature", ""), "area": row.get("area", ""), "priority": row["priority"],
            "clone": row["clone"], "notes": row.get("notes", ""), "line": row["line"]}


def score(rows):
    """Score the rows: feature_score, points, counted, must_have_done, must_have_total,
    must_have_skipped, by_area (weakest first), missing (in build order), skipped, extras and
    problems. A value outside the contract is a problem, counted as could or no."""
    counted, skipped, extras, problems = [], [], [], []
    for row in rows:
        problems += check_row(row)
        priority, clone = row.get("priority", "").lower(), row.get("clone", "").lower() or "no"
        item = dict(row, priority=priority if priority in WEIGHT else "could", clone=clone,
                    weight=WEIGHT.get(priority, 1), credit=CREDIT.get(clone, 0.0))
        if row.get("original", "").lower() == "no":
            extras.append(item)
        elif clone == "skip":
            skipped.append(item)
        else:
            counted.append(item)
    areas = {}  # area name -> [points earned, points possible, number of features]
    for item in counted:
        totals = areas.setdefault(item.get("area") or "(no area)", [0.0, 0, 0])
        totals[0] += item["weight"] * item["credit"]
        totals[1] += item["weight"]
        totals[2] += 1
    by_area = [{"area": name, "score": rounded_down(100.0 * earned / possible), "features": count}
               for name, (earned, possible, count) in areas.items()]
    by_area.sort(key=lambda area: (area["score"], area["area"]))

    missing = [item for item in counted if item["credit"] < 1.0]
    # Build order: must before should before could, not started before partial.
    missing.sort(key=lambda item: (-item["weight"], item["credit"], item.get("area", ""), item["feature"]))
    musts = [item for item in counted if item["priority"] == "must"]
    possible = sum(item["weight"] for item in counted)
    earned = sum(item["weight"] * item["credit"] for item in counted)
    return {"feature_score": rounded_down(100.0 * earned / possible) if possible else 0.0,
            "points": {"earned": earned, "possible": possible},
            "counted": len(counted),
            "must_have_done": len([item for item in musts if item["credit"] == 1.0]),
            "must_have_total": len(musts),
            "must_have_skipped": len([item for item in skipped if item["priority"] == "must"]),
            "by_area": by_area,
            "missing": [brief(item) for item in missing],
            "skipped": [brief(item) for item in skipped],
            "extras": [brief(item) for item in extras],
            "problems": problems}


def visual_scores(paths):
    """The layout score of each screen, from files written by imgdiff.py --json."""
    screens = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except OSError as error:
            raise MatrixError("cannot read %s (%s)" % (path, error.strerror))
        except ValueError:  # also a file that is not UTF-8
            raise MatrixError("%s is not JSON. Did imgdiff.py stop with an error?" % path)
        value = data.get("score") if isinstance(data, dict) else None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
            raise MatrixError("%s is not imgdiff.py --json output (no score from 0 to 100)" % path)
        files = data.get("files") if isinstance(data.get("files"), dict) else {}
        screens.append({"file": str(files.get("clone", path)), "score": float(value)})
    return screens


def combine(result, screens):
    """Add the layout scores and the overall score: 80% features and 20% layout, worked out
    from the exact scores and only then rounded down."""
    points = result["points"]
    features = 100.0 * points["earned"] / points["possible"] if points["possible"] else 0.0
    result["overall"] = rounded_down(features)
    if screens:
        layout = sum(screen["score"] for screen in screens) / len(screens)
        result["visual"] = screens
        result["layout_score"] = rounded_down(layout)
        result["overall"] = rounded_down(0.8 * features + 0.2 * layout)
    result["all_must_haves_done"] = result["must_have_total"] > 0 and (
        result["must_have_done"] == result["must_have_total"])
    return result


def render(result, markdown=False):
    """The report as plain text, or as markdown for forge-work/parity.md."""
    head = "## " if markdown else ""

    def cell(text):  # text from the matrix: in markdown, signs that change the layout are escaped
        return MARKDOWN_SIGNS.sub(r"\\\1", text) if markdown else text

    lines = ["# Parity", ""] if markdown else []
    done, total, left_out = result["must_have_done"], result["must_have_total"], result["must_have_skipped"]
    lines += ["Parity: %.1f / 100" % result["overall"],
              "- features: %.1f  (%s scored, must-haves %d of %d done%s)"
              % (result["feature_score"], plural(result["counted"], "feature"), done, total,
                 ", %d left out" % left_out if left_out else "")]
    if "layout_score" in result:
        lines.append("- layout:   %.1f  (%s compared)"
                     % (result["layout_score"], plural(len(result["visual"]), "screen")))
    lines.append("")
    if not total:
        lines.append("Not shippable: no must-have feature is scored, so parity cannot be measured. "
                     "Mark what the clone cannot do without as must in features.csv.")
    elif done < total:
        lines.append("Not shippable yet: %s not done." % ("1 must-have feature is" if total - done == 1
                                                         else "%d must-have features are" % (total - done)))
    else:
        lines.append("Every %smust-have feature is done." % ("scored " if left_out else ""))
    if left_out:
        lines.append("Warning: %s left out on purpose (skip). Each needs the user's agreement, "
                     "written in notes." % plural(left_out, "must-have feature"))

    lines += ["", head + "By area, weakest first"]
    for area in result["by_area"]:
        lines.append("- %-28s %5.1f  (%s)"
                     % (cell(area["area"]), area["score"], plural(area["features"], "feature")))
    lines += ["", head + "Missing, in build order"]
    if not result["missing"]:
        lines.append("- nothing: every scored feature is done.")
    for item in result["missing"]:
        note = ": " + cell(item["notes"]) if item["notes"] else ""
        status = STATUS.get(item["clone"], "not built")
        lines.append("- [%s] %s: %s (%s%s)" % (item["priority"], cell(item["area"]) or "-", cell(item["feature"]),
                                              status, note))
    if result["skipped"]:
        lines += ["", head + "Left out on purpose (not scored)"]
        lines += ["- [%s] %s: %s" % (item["priority"], cell(item["feature"]), cell(item["notes"]))
                  for item in result["skipped"]]
    if result["extras"]:
        lines += ["", head + "Yours, not in the original (not scored)"]
        lines += ["- %s (%s)" % (cell(item["feature"]), STATUS.get(item["clone"], "not built"))
                  for item in result["extras"]]
    if result.get("visual"):
        lines += ["", head + "Screens, lowest layout score first"]
        for screen in sorted(result["visual"], key=lambda screen: screen["score"]):
            lines.append("- %-40s %5.1f" % (cell(screen["file"]), screen["score"]))
    return "\n".join(lines)


def main(argv=None):
    """Run the score from the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: escapes, no crash
    parser = argparse.ArgumentParser(description="Feature parity score from forge-work/features.csv.")
    parser.add_argument("matrix", help="the feature matrix, normally forge-work/features.csv")
    parser.add_argument("--visual", nargs="+", default=[], metavar="JSON",
                        help="files written by imgdiff.py --json, to fold in the layout scores")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="print machine-readable JSON")
    output.add_argument("--markdown", action="store_true", help="print markdown for forge-work/parity.md")
    parser.add_argument("--fail-under", type=float, metavar="SCORE",
                        help="also exit 1 when the overall score (rounded down) is under this number")
    args = parser.parse_args(argv)
    if args.markdown:  # parity.md is read as UTF-8, also where pipes are cp1252 (Windows)
        getattr(sys.stdout, "reconfigure", lambda **_: None)(encoding="utf-8", errors="backslashreplace")
    if args.fail_under is not None and not 0 <= args.fail_under <= 100:  # also catches nan
        parser.error("--fail-under takes a score from 0 to 100")
    try:
        result = score(load(args.matrix))
        if result["problems"]:
            raise MatrixError("fix these in %s:\n  %s" % (args.matrix, "\n  ".join(result["problems"])))
        if not result["counted"]:
            raise MatrixError("%s has no rows to score (skip rows and your own extras do not count)"
                              % args.matrix)
        result = combine(result, visual_scores(args.visual))
    except (MatrixError, csv.Error) as error:  # csv.Error: only for odd files, such as a huge cell
        name = "" if isinstance(error, MatrixError) else args.matrix + ": "
        print("error: %s%s" % (name, error), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2) if args.json else render(result, markdown=args.markdown))
    under = args.fail_under is not None and result["overall"] < args.fail_under
    return 0 if result["all_must_haves_done"] and not under else 1


if __name__ == "__main__":
    sys.exit(main())
