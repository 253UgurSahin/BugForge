"""Shared by the scripts in this folder that print a report of findings (codecheck.py, flowcheck.py, deps.py,
headers.py, pagecheck.py): printing it to a reader that may stop early, and the blocks people read.

Not a script: no command line. The scripts next to it import it by name, which works because Python puts a
script's own folder first on sys.path. Standard library only.
"""

import errno
import os
import sys

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first


def print_report(text):
    """Print TEXT. When the reader stopped early (| head), end quietly, without a traceback."""
    try:
        print(text, flush=True)
    except OSError as error:
        if error.errno not in (errno.EPIPE, errno.EINVAL):  # EINVAL: what Windows says there
            raise
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())


def format_findings(findings, summary, intro):
    """The report for people: the intro, one block per finding, then a one-line summary."""
    lines = [intro, ""]
    for f in findings:
        lines.append("%-8s  %s\n          where: %s\n          why:   %s\n          fix:   %s\n"
                     % (f["severity"].upper(), f["title"], f["where"], f["why"], f["fix"]))
    counts = ", ".join("%d %s" % (summary[sev], sev) for sev in SEVERITIES if summary[sev])
    noun = "finding" if len(findings) == 1 else "findings"
    lines.append("%d %s: %s." % (len(findings), noun, counts) if findings else "No findings.")
    return "\n".join(lines)
