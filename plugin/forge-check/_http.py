"""Shared by the scripts in this folder that send HTTP requests: getpage.py and headers.py (one passive GET
under one deadline), and authz.py and probe.py (active tests of the user's own app, only where scope.py allows).

Not a script: no command line of its own. The scripts next to it import it by name, which works because Python
puts a script's own folder first on sys.path. Standard library only.
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import urllib.parse
import urllib.request

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first


class KeepEveryAnswer(urllib.request.HTTPErrorProcessor):
    """Hand back every answer as it is: no redirect is followed, and a 404 or 500 is not an error."""

    def http_response(self, request, response):
        return response

    https_response = http_response


class Stop(Exception):
    """The request cap is reached: the run ends here."""


def within(seconds, work):
    """Run WORK() in a thread of its own under one deadline of SECONDS, so that a slow server cannot stall it:
    what WORK returns, or the error it raised, raised again here. TimeoutError when it did not finish in time."""
    outcome = []  # (True, what it returned) or (False, the error)

    def run():
        try:
            outcome.append((True, work()))
        except Exception as error:  # raised again below, in the caller's thread
            outcome.append((False, error))

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(seconds)
    if not outcome:
        raise TimeoutError("no complete answer within %d seconds" % seconds)
    finished, value = outcome[0]
    if not finished:
        raise value
    return value


def show(text, limit=80):
    """Text from a server or a file made safe to print: no control characters, not too long."""
    text = "".join(ch if ch.isprintable() else "?" for ch in str(text))
    return text if len(text) <= limit else text[:limit] + "..."


def in_scope(host, scope_file=None):
    """(allowed, what scope.py said). scope.py next to this file decides; only its exit 0 means yes."""
    command = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scope.py"), host]
    try:
        done = subprocess.run(command + (["--scope", scope_file] if scope_file else []), timeout=30,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, subprocess.SubprocessError) as error:
        return False, "scope.py could not be run: %s" % show(error)
    said = (done.stdout + done.stderr).decode("utf-8", errors="replace").splitlines()
    return done.returncode == 0, show(" / ".join(said[:2]), 300)


def active_parser(doc):
    """The command line of an active test, up to its own options: the url of the app. Sets stdout to print what
    it cannot show as escapes (cp1252 pipes), not a crash. Add the options, then the limits with add_limits()."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=doc)
    parser.add_argument("url", help="http:// or https:// address of your own running app")
    return parser


def add_limits(parser):
    """The options every active test ends with: --scope, --max-requests, --json and --fail-on."""
    parser.add_argument("--scope", metavar="FILE", help="scope file for scope.py (default: forge-work/scope.json)")
    parser.add_argument("--max-requests", type=int, default=150, metavar="N", help="request cap, 1 to 500 (default: 150)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high",
                        help="exit 1 when a finding is this bad or worse (default: high)")


def app_address(args):
    """The parts (urllib.parse.urlsplit) of the app's address in ARGS. ValueError for an address that is not
    http:// or https://, holds a user name or password, or a --max-requests outside 1 to 500."""
    parts = urllib.parse.urlsplit(args.url)
    if parts.scheme not in ("http", "https") or not parts.hostname or "@" in parts.netloc or (parts.port or 1) < 1:
        raise ValueError("give an http:// or https:// address, without a user name or password in it")
    if not 1 <= args.max_requests <= 500:
        raise ValueError("--max-requests must be from 1 to 500: this is a check, not a load test")
    return parts


def refused(host, scope_file):
    """True, after saying so on stderr, when scope.py does not allow active tests against HOST."""
    allowed, said = in_scope(host, scope_file)  # asked about the host the requests would go to
    if not allowed:
        print("refused: active tests may not run against %s. Nothing was sent.\nscope.py says: %s"
              % (show(host), said), file=sys.stderr)
    return not allowed


def tally(findings, fail_on):
    """Sort FINDINGS most severe first. Returns (one is at or above FAIL_ON, {severity: count})."""
    findings.sort(key=lambda f: SEVERITIES.index(f["severity"]))
    failed = any(SEVERITIES.index(f["severity"]) <= SEVERITIES.index(fail_on) for f in findings)
    return failed, {sev: sum(f["severity"] == sev for f in findings) for sev in SEVERITIES}


def finding_lines(findings, summary, notes):
    """The report's lines for people: one block per finding, the counts, and what was not checked."""
    lines = ["%-8s  %s [%s]\n          where: %s\n          why:   %s\n          fix:   %s\n" % (f["severity"].upper(),
             f["title"], f["check"], f["where"], f["why"], f["fix"]) for f in findings]
    counts = ", ".join("%d %s" % (summary[sev], sev) for sev in SEVERITIES if summary[sev])
    lines += ["%d finding(s): %s." % (len(findings), counts) if findings else "No findings.", "", "Not checked:"]
    return lines + ["- " + note for note in notes]


def print_active(report, lines, as_json, unfinished):
    """Print the report: JSON with AS_JSON, else LINES. An UNFINISHED run's JSON goes to stderr, so that it never
    ends up in a saved report."""
    print(json.dumps(report, indent=2) if as_json else "\n".join(lines), flush=True,
          file=sys.stderr if as_json and unfinished else sys.stdout)
