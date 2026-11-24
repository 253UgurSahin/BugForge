#!/usr/bin/env python3
"""Access-control check on YOUR OWN running app: can user B, or a visitor without a session, read what is user A's?

Each path in --urls is loaded three times with GET: as user A, as user B and without cookies. User A must get 200,
else the path is listed as "could not check". A 401, 403, 404 or a redirect for the others is a pass, and so is a
login page shown in place. A finding when B or the visitor gets a 2xx page close to A's (about the same size and at
least 90% the same words). A page that is the same for everyone, such as a public page, is flagged too, so list
only private paths: A's booking, A's invoice, an API route with A's id. Findings, by their name in the output:
other_user_reads (critical), anonymous_reads (critical), anonymous_200 (high: 200 without a login, other content).

It runs only where scope.py (next to this file) allows active tests: localhost, private networks, container names,
or a domain listed as yours in forge-work/scope.json. Any other target is refused before one request is sent; no
flag turns that off. GET only, no redirect followed, a timeout and size cap per request, a request cap per run.
Cookies are read from files and never printed; response bodies are never printed either.

Usage:
    python3 authz.py http://localhost:8080 --urls private.txt --a alice.txt --b bob.txt [--scope FILE]
                     [--max-requests N] [--json] [--fail-on medium]

--urls: a text file with one path per line, like /bookings/41 or /api/invoices/7?format=json.
--a, --b: the sessions of two different users. Either a text file with one name=value cookie per line (a line
"Authorization: Bearer ..." is sent as that header), or a Playwright storageState file such as e2e/.auth/alice.json.
Exit codes: 0 = every path checked, nothing at or above --fail-on (default: high); 1 = a finding at or above it;
2 = refused (target not in scope), bad input, app not reachable, or a path could not be checked (also after a
finding). Never a pass. --json prints the report on stdout, but that of a run with a path not checked on stderr:
a file that stdout is saved in then stays empty, so only a finished run ever counts as the evidence of level 4.
"""

import difflib
import http.client
import json
import re
import sys
import time
import urllib.parse
import urllib.request

from _http import (SEVERITIES, KeepEveryAnswer, Stop, active_parser, add_limits, app_address,  # next to this script
                   finding_lines, in_scope, print_active, refused, show, tally)

USER_AGENT = "forge-authz (self-check of your own app)"
TIMEOUT, BODY_CAP, PAUSE = 10, 200000, 0.1  # seconds per request, bytes read of an answer, seconds between requests
WORDS, ALIKE = 2000, 0.9  # words of each body that are compared, and the share that must match to count as the same
LOGIN_PAGE = re.compile(r"type\s*=\s*[\"']?password", re.I)  # a password field: the app shows its login page in place
LISTED = "a page that is the same for everyone is flagged too: list only private paths"
FIX = ("check on the server, in this route, that the record belongs to the logged-in user (a policy, or a query "
       "limited to that user), and answer 403 or 404 otherwise")
RULES = {  # check: (severity, title, why, fix)
    "other_user_reads": ("critical", "Another user can see this private page", "user B got the same content as user A: "
                         "one customer can read another customer's data (%s)" % LISTED, FIX),
    "anonymous_reads": ("critical", "Anyone can see this private page without logging in", "a visitor without a "
                        "session got the same content as user A (%s)" % LISTED, "require a login on this route; " + FIX),
    "anonymous_200": ("high", "A private path answers 200 without a login", "the content differs from user A's, so it "
                      "may be an error page, but a stranger should not get a 200 here and it may still leak parts",
                      "answer 401, 403 or 404, or redirect to the login page; look at what this page shows"),
}
WHO = {"b": ("user B", "other_user_reads", None), "anonymous": ("a visitor without a session", "anonymous_reads",
                                                               "anonymous_200")}

class Client:
    """Sends the GETs: only to the app itself, counted, paused and capped."""
    def __init__(self, base, limit):
        self.base, self.limit, self.count = base, limit, 0
        self.opener = urllib.request.build_opener(KeepEveryAnswer, urllib.request.ProxyHandler({}))  # direct, no proxy
    def get(self, path, session=None):
        """(status, text) of one GET with the headers of a session (None: no cookies). Raises Stop at the cap."""
        if not path.startswith("/"):
            raise ValueError("refused: only paths on the app itself")
        if self.count >= self.limit:
            raise Stop()
        self.count += 1
        time.sleep(PAUSE)
        request = urllib.request.Request(self.base + path, headers=dict(session or {}, **{"User-Agent": USER_AGENT}))
        with self.opener.open(request, timeout=TIMEOUT) as answer:
            return answer.status, answer.read(BODY_CAP).decode("utf-8", errors="replace")

def load_session(path, host):
    """The request headers ({"Cookie": ..., "Authorization": ...}) in a session file. A ValueError never holds a value."""
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        text = handle.read(1024 * 1024)
    pairs, headers = [], {}
    if text.lstrip().startswith("{"):  # Playwright storageState: {"cookies": [{"name", "value", "domain", ...}]}
        try:
            for cookie in json.loads(text)["cookies"]:
                domain = cookie.get("domain", "").lstrip(".").lower()
                if host == domain or host.endswith("." + domain):
                    pairs.append((str(cookie["name"]), str(cookie["value"])))
        except (ValueError, RecursionError, LookupError, TypeError, AttributeError):
            raise ValueError("%s is not a Playwright storageState file with a cookies list" % show(path))
    for number, line in enumerate([] if pairs or text.lstrip().startswith("{") else text.splitlines(), 1):
        name, equals, value = line.strip().partition("=")
        if line.strip().lower().startswith("authorization:"):
            headers["Authorization"] = line.split(":", 1)[1].strip()
        elif equals and name.strip():
            pairs.append((name.strip(), value.strip()))
        elif line.strip() and not line.lstrip().startswith("#"):
            raise ValueError("%s line %d: write one cookie per line as name=value" % (show(path), number))
    if pairs:
        headers["Cookie"] = "; ".join("%s=%s" % pair for pair in pairs)
    if not headers:
        raise ValueError("%s holds no cookie for %s (use the host name the session was made on)" % (show(path), host))
    if any(not ch.isprintable() or ord(ch) > 255 for value in headers.values() for ch in value):
        raise ValueError("%s holds a cookie with characters that cannot be sent" % show(path))
    return headers

def load_paths(path):
    """The paths in a --urls file, in order, without doubles. ValueError names a wrong line."""
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        lines = handle.read(1024 * 1024).splitlines()
    paths = []
    for number, line in enumerate(lines, 1):
        line = urllib.parse.quote(line.split("#")[0].strip(), safe="/?&=%+,;:@~!$*()'")  # a # starts a comment
        if line and (not line.startswith("/") or line.startswith("//")):
            raise ValueError("%s line %d: write a path that starts with one /, like /bookings/41" % (show(path), number))
        paths += [line] if line and line not in paths else []
    if not paths:
        raise ValueError("%s lists no paths" % show(path))
    return paths

def alike(mine, theirs):
    """True when two bodies are nearly the same page: about the same size and ALIKE of the same words in order."""
    if mine == theirs:
        return True
    if not mine or not theirs or not 0.8 <= len(mine) / float(len(theirs)) <= 1.25:
        return False
    words = [re.findall(r"\w+", text)[:WORDS] for text in (mine, theirs)]
    match = difflib.SequenceMatcher(None, words[0], words[1], autojunk=False)
    return match.quick_ratio() >= ALIKE and match.ratio() >= ALIKE

def check_path(client, path, sessions, findings, notes):
    """Load one path as A, as B and without a session. Returns its row for the report."""
    row = {"path": show(path), "a": None, "b": None, "anonymous": None, "result": "could not check"}
    row["a"], mine = client.get(path, sessions["a"])
    if row["a"] != 200:
        notes.append("%s: user A got %d, not 200, so it could not be checked (is the session in --a still valid, "
                     "and the path right?)" % (row["path"], row["a"]))
        return row
    row["result"] = "pass"
    for who in ("b", "anonymous"):
        name, same_check, other_check = WHO[who]
        status, theirs = client.get(path, sessions.get(who))
        row[who] = status
        if status >= 500:
            row["result"] = "could not check"
            notes.append("%s: %s got %d, an error, so it could not be judged; look at the app's log"
                         % (row["path"], name, status))
        elif 200 <= status < 300 and (LOGIN_PAGE.search(mine) or not LOGIN_PAGE.search(theirs)):  # not a login page
            check = same_check if alike(mine, theirs) else other_check
            if check:
                severity, title, why, fix = RULES[check]
                findings.append({"check": check, "severity": severity, "title": title, "why": why, "fix": fix,
                                 "where": "GET %s as %s answered %d (user A: 200)" % (row["path"], name, status)})
                row["result"] = "finding"
            else:
                notes.append("%s: %s got %d with other content than user A: probably a 'not yours' page, but look at "
                             "it by hand; a 403 or 404 is clearer" % (row["path"], name, status))
    return row

def main(argv=None):
    """Read the command line, ask scope.py, check each path, print the report and return the exit code."""
    parser = active_parser(__doc__)
    parser.add_argument("--urls", required=True, metavar="FILE", help="text file: one private path of user A per line")
    parser.add_argument("--a", required=True, metavar="COOKIES_A", help="session file of user A, who owns the paths")
    parser.add_argument("--b", required=True, metavar="COOKIES_B", help="session file of user B, another user")
    add_limits(parser)
    args = parser.parse_args(argv)
    try:
        parts = app_address(args)
        paths = load_paths(args.urls)
        sessions = {"a": load_session(args.a, parts.hostname), "b": load_session(args.b, parts.hostname)}
        if sessions["a"] == sessions["b"]:
            raise ValueError("--a and --b hold the same session: log in as two different users")
    except (OSError, ValueError) as error:
        print("error: %s" % show(error, 300), file=sys.stderr)
        return 2
    if refused(parts.hostname, args.scope):
        return 2
    client = Client("%s://%s" % (parts.scheme, parts.netloc), args.max_requests)
    findings, notes, rows = [], [], []
    try:
        for path in paths:
            rows.append(check_path(client, path, sessions, findings, notes))
    except Stop:
        notes.append("the request cap of %d was reached: %d of %d paths were not checked; raise --max-requests"
                     % (client.limit, len(paths) - len(rows), len(paths)))
    except (OSError, http.client.HTTPException) as error:
        print("error: no answer from %s after %d requests: %s" % (show(client.base), client.count - 1, show(error, 200)),
              file=sys.stderr)
        return 2
    incomplete = len(rows) < len(paths) or any(row["result"] == "could not check" for row in rows)
    notes.append("user B's session was not verified: with an expired session B is just a visitor and all looks fine; "
                 "log both users in again shortly before the run")
    failed, summary = tally(findings, args.fail_on)
    summary.update(total=len(findings), url=show(client.base), requests=client.count, paths=len(paths),
                   fail_on=args.fail_on, failed=failed, incomplete=incomplete)
    lines = ["Checked %d of %d private paths on %s." % (len(rows), len(paths), summary["url"])]
    lines += ["  %-15s %s  (A %s, B %s, no session %s)" % (row["result"].upper(), row["path"], row["a"], row["b"],
              row["anonymous"]) for row in rows] + [""]
    lines += finding_lines(findings, summary, notes)
    lines += ["", "Not every path could be checked (see Not checked): not a pass. Run again."] if incomplete else []
    report = {"findings": findings, "paths": rows, "not_checked": notes, "summary": summary}
    print_active(report, lines, args.json, incomplete)  # not finished: never in a saved report
    return 2 if incomplete else 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
