"""Shared by scripts that read the code of a project: codecheck.py and flowcheck.py walk a folder for PHP,
Python and JS/TS files and read each one; trackers.py here and ../forge-design/motioncheck.py read a file to
check with the same limit.

Not a script: no command line. The scripts next to it import it by name, which works because Python puts a
script's own folder first on sys.path; motioncheck.py puts this folder on sys.path. Standard library only.
"""

import json
import os
import sys

from _report import print_report

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
MAX_BYTES = 1024 * 1024  # bigger files are not checked
LANGUAGES = {".php": "php", ".py": "python", ".js": "js", ".jsx": "js", ".ts": "js", ".tsx": "js",
             ".mjs": "js", ".cjs": "js", ".vue": "js", ".svelte": "js"}
TOO_BIG = " (binary, or over 1 MB)"


def language_of(path):
    """Return "php", "python" or "js" for a file type we check, else None."""
    return LANGUAGES.get(os.path.splitext(path)[1].lower())


def shown_path(full, folder):
    """The path as the report shows it: relative to the scanned folder, always printable."""
    shown = os.path.relpath(full, folder).replace(os.sep, "/")
    return os.fsencode(folder if shown == "." else shown).decode("utf-8", errors="backslashreplace")


def files_under(folder, unreadable, skip_dirs):
    """Yield (full path, path shown in the report) for each file of a known type under folder, outside the
    folders in SKIP_DIRS (a name, or parent/name). A folder that cannot be opened (the folder itself too) goes on
    the unreadable list."""
    def cannot_open(error):  # os.walk calls this for a folder it cannot list
        unreadable.append((shown_path(error.filename or folder, folder), error.strerror or "error"))
    for parent, dirs, files in os.walk(folder, onerror=cannot_open):
        here = os.path.basename(os.path.abspath(parent))  # to spot storage/framework
        dirs[:] = sorted(d for d in dirs if d not in skip_dirs and here + "/" + d not in skip_dirs)
        for name in sorted(files):  # os.walk skips symlinked folders; we skip symlinked files
            full = os.path.join(parent, name)
            if language_of(name) and os.path.isfile(full) and not os.path.islink(full):
                yield full, shown_path(full, folder)


def scan_path(path, scan_text, skip_dirs, opener=open):
    """Return (findings, stats) for a file or folder: SCAN_TEXT(text, language, shown path) on each file, read
    with OPENER (the script's open). stats: files_checked, files_skipped (binary or over 1 MB) and unreadable, a
    list of (path, reason). Raises ValueError."""
    is_file = os.path.isfile(path)
    if not is_file and not os.path.isdir(path):
        raise ValueError("%s does not exist, or is not a file or folder" % path)
    if is_file and not language_of(path):
        raise ValueError("%s is not a PHP, Python or JS/TS file" % path)
    findings, checked, skipped, unreadable = [], 0, [], []
    shown_file = os.fsencode(path).decode("utf-8", errors="backslashreplace")
    for full, shown in [(path, shown_file)] if is_file else files_under(path, unreadable, skip_dirs):
        try:
            with opener(full, "rb") as handle:
                data = handle.read(MAX_BYTES + 1)
        except OSError as error:
            unreadable.append((shown, error.strerror or "error"))
            continue
        if len(data) > MAX_BYTES or b"\0" in data[:8192]:
            skipped.append(shown)
            continue
        findings += scan_text(data.decode("utf-8", errors="replace"), language_of(full), shown)
        checked += 1
    if is_file and skipped:
        raise ValueError("%s is a binary file or over 1 MB, so it cannot be checked" % path)
    return findings, {"files_checked": checked, "files_skipped": skipped, "unreadable": sorted(unreadable)}


def run(scan_path, args, footer, format_human):
    """Scan args.path with SCAN_PATH, print the report (JSON with --json, else FORMAT_HUMAN's) and return the exit
    code: 2 for a path that cannot be checked or code that was not read, 1 for a finding at or above --fail-on."""
    try:
        findings, stats = scan_path(args.path)
    except ValueError as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    findings.sort(key=lambda f: (SEVERITIES.index(f["severity"]), f["file"], f["line"]))
    summary = {s: sum(f["severity"] == s for f in findings) for s in SEVERITIES}
    summary.update(stats, total=len(findings), incomplete=bool(stats["unreadable"]))
    shown = dict(summary, unreadable=[{"path": p, "reason": r} for p, r in stats["unreadable"]])
    print_report(json.dumps({"findings": findings, "summary": shown, "note": footer}, indent=2)
                 if args.json else format_human(findings, summary))
    if stats["unreadable"]:
        return 2  # some code was never read, so the result cannot be trusted
    return int(any(SEVERITIES.index(f["severity"]) <= SEVERITIES.index(args.fail_on) for f in findings))


def result_lines(summary):
    """The lines under the findings: how many there are of each severity, what was checked, skipped and not read."""
    total, checked = summary["total"], summary["files_checked"]
    counts = ", ".join("%d %s" % (summary[s], s) for s in SEVERITIES if summary[s])
    result = "No findings in the files that were read." if summary["unreadable"] else "No findings."
    if not checked:
        result = "Nothing was checked: no PHP, Python or JS/TS file was found and read."
    elif total:
        result = "%d %s: %s." % (total, "finding" if total == 1 else "findings", counts)
    lines = [result, "Files checked: %d (PHP, Python, JS/TS)." % checked]
    if summary["files_skipped"]:
        lines.append("Skipped (binary or over 1 MB): " + ", ".join(summary["files_skipped"]))
    if summary["unreadable"]:
        could_not = ", ".join("%s (%s)" % pair for pair in summary["unreadable"])
        lines.append("INCOMPLETE, so not a pass. Could not read: " + could_not)
    return lines


def read_code(path, not_checked, named):
    """The text of one file to check, or None. A file that cannot be read goes on NOT_CHECKED; one that is binary
    or over 1 MB is skipped with a word on stderr, and goes on NOT_CHECKED too when the user NAMED it."""
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_BYTES + 1)
    except OSError:
        not_checked.append(path)
        return None
    if len(data) > MAX_BYTES or b"\0" in data[:8192]:  # too big, or binary (a NUL byte)
        print("skipped: %s%s" % (path, TOO_BIG), file=sys.stderr)
        not_checked += [path + TOO_BIG] if named else []
        return None
    return data.decode("utf-8", errors="replace")
