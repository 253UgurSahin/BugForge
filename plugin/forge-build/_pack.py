"""Shared by the scripts in this folder (composecheck.py, packcheck.py): the rule for a secret written into a
container file, reading a file of the project, and the command line and report both checks have.

Not a script: no command line of its own. The scripts next to it import it by name, which works because Python
puts a script's own folder first on sys.path. Standard library only.
"""

import argparse
import json
import os
import re
import sys

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
MAX_BYTES = 1024 * 1024
COMPOSE_FILE = re.compile(r"^(?:docker-)?compose(?:\.[\w.-]+)?\.ya?ml$")
# As in secretscan.py, a name that ENDS in a secret word holds a secret: DB_PASSWORD, SMTP_PASS, NPM_TOKEN,
# APP_KEY; TOKEN_URL and DB_PASSWORD_FILE do not.
SECRET_NAME = re.compile(r"(?i)(?:passw(?:or)?d|^pass|[_.-]pass|[_.-]pwd|secret|token"
                         r"|(?:api|app|auth|access|private|secret|encryption|signing|master)[_-]?key)\d*$")
SWITCH_NAME = re.compile(r"(?i)RANDOM|ALLOW_EMPTY")  # MARIADB_RANDOM_ROOT_PASSWORD: a yes/no switch
SWITCH_VALUES = ("", "yes", "no", "true", "false", "on", "off", "null", "~", "0", "1")
FALLBACK = re.compile(r"\$\{\w+:?-([^$}][^}]*)\}")  # ${DB_PASSWORD:-hunter2}: hunter2 is written here
FILE_PATH = re.compile(r"^\.?/[\w.-]+(?:/[\w.-]+)+$")  # /run/secrets/db says where a secret is


def unquote(text):
    return text.strip().strip("'\"").strip()


def is_written_secret(name, value):
    """True for a secret-looking NAME with its value written out. References (${DB_PASSWORD}),
    switches (yes, 1) and file paths are fine; the fallback in ${DB_PASSWORD:-hunter2} is not."""
    value = unquote(value)
    if not SECRET_NAME.search(name) or SWITCH_NAME.search(name):
        return False
    reference = (value.startswith("$") or "${" in value) and not FALLBACK.search(value)
    return not (reference or value.lower() in SWITCH_VALUES or FILE_PATH.match(value))


def read(root, name):
    """The text of ROOT/NAME: a regular file of at most 1 MB inside ROOT. A BOM is dropped."""
    path, real_root = os.path.join(root, name), os.path.realpath(root)
    real = os.path.realpath(path)
    elsewhere = os.path.splitdrive(real)[0] != os.path.splitdrive(real_root)[0]  # on another drive (Windows)
    if elsewhere or os.path.commonpath([real, real_root]) != real_root:  # commonpath() fails across drives
        raise ValueError("%s is a link to a file outside %s" % (name, root))
    if not os.path.isfile(path) or os.path.getsize(path) > MAX_BYTES:
        raise ValueError("%s is not a regular file of at most 1 MB" % name)
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        return handle.read()


def format_human(findings, summary):
    lines = []
    for f in findings:
        lines += ["%-8s  %s" % (f["severity"].upper(), f["title"]), "          where: " + f["where"],
                  "          why:   " + f["why"], "          fix:   " + f["fix"], ""]
    counts = ", ".join("%d %s" % (summary[sev], sev) for sev in SEVERITIES if summary[sev])
    noun = "finding" if len(findings) == 1 else "findings"
    lines.append("Checked: %s." % ", ".join(summary["checked"]))
    lines.append("%d %s: %s." % (len(findings), noun, counts) if findings else "No findings.")
    lines.append(("FAIL: at least one finding is %s or worse." if summary["failed"]
                  else "PASS: nothing is %s or worse.") % summary["fail_on"])
    return "\n".join(lines)


def arguments(description, argv=None):
    """The command line of a check: path, --json and --fail-on. Sets stdout to print what it cannot show as
    escapes (cp1252 pipes), not a crash."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("path", help="the project folder")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high",
                        help="exit 1 when a finding is this bad or worse (default: high)")
    return parser.parse_args(argv)


def report(findings, checked, args, **more):
    """Print the report of FINDINGS (as JSON with --json) and return the exit code: 1 when one is at or above
    --fail-on, else 0. MORE goes into the summary after the counts."""
    too_bad = any(SEVERITIES.index(f["severity"]) <= SEVERITIES.index(args.fail_on) for f in findings)
    summary = {sev: len([f for f in findings if f["severity"] == sev]) for sev in SEVERITIES}
    summary.update(total=len(findings), checked=checked, fail_on=args.fail_on, failed=too_bad, **more)
    print(json.dumps({"findings": findings, "summary": summary}, indent=2) if args.json
          else format_human(findings, summary))
    return 1 if too_bad else 0
