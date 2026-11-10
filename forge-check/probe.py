#!/usr/bin/env python3
"""Actively probe YOUR OWN running app for common web holes before a release. Harmless requests only.

It runs only where scope.py (next to this file) allows active tests: localhost, private networks, container names,
or a domain listed as yours in forge-work/scope.json. Any other target is refused before one request is sent; no
flag turns that off. It sends GETs and one TRACE. Nothing changes or deletes data: a hole shows as a harmless
marker echoed back, or an error text after one single quote. No redirect is followed, every request has a
timeout and a size cap, and the run stops at --max-requests. Bodies and cookies are never printed.
Checks, by their name in the output: exposed_file, dir_listing, debug_page, reflected_input, sql_error,
open_redirect, cors, csrf_form, trace. What was skipped is listed under "Not checked".

Usage:
    python3 probe.py http://localhost:8080 [--paths paths.txt] [--scope FILE] [--max-requests N] [--json]
                     [--fail-on medium]

--paths: a text file, one path per line with an optional query string (/search?q=tea). Each page is loaded and
each query parameter tested; without it only / is loaded.
Exit codes: 0 = nothing at or above --fail-on (default: high); 1 = a finding at or above it;
2 = refused (target not in scope), bad input, app not reachable, or the run was cut short. Never a pass.
"""

import argparse
import html.parser
import http.client
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
USER_AGENT = "forge-probe (self-check of your own app)"
TIMEOUT, BODY_CAP, PAUSE = 10, 200000, 0.1  # seconds per request, bytes read of an answer, seconds between requests
ELSEWHERE = "https://example.invalid"  # .invalid names never exist: nothing is ever sent there
CSRF_NAME = re.compile(r"csrf|xsrf|_token|authenticity|nonce|requestverification", re.I)
REDIRECT_NAME = re.compile(r"next|url|redirect|return|continue|dest|goto|target", re.I)
GONE_ELSEWHERE = re.compile(r"(https?:)?//example\.invalid(/|$)", re.I)  # a Location header that leaves the app
LISTING = re.compile(r"<title>\s*(Index of /|Directory listing for)", re.I)
SQL_ERROR = re.compile(  # MySQL and MariaDB, PostgreSQL, SQLite, then what frameworks wrap them in
    r"error in your SQL syntax|MariaDB server version|mysqli?_\w+\(\)|syntax error at or near|unterminated quoted "
    r"string|PG::\w+|psycopg2?\.|SQLITE_ERROR|sqlite3\.\w+Error|unrecognized token|near \"[^\"]*\": syntax error|"
    r"SQLSTATE\[|QueryException|Unclosed quotation mark", re.I)
DEBUG_PAGE = re.compile(  # Django, Laravel, Flask, Python, PHP, Java, Node and Rails debug output
    r"DEBUG = True|vendor/laravel/framework|Illuminate\\+[A-Z]\w+\\|Whoops, looks like something went wrong|"
    r"Werkzeug Debugger|Traceback \(most recent call last\)|<b>(Fatal error|Warning|Notice)</b>:|Stack trace:|"
    r"\bat [\w.$]+\(\w+\.java:\d+\)|\n\s+at [^\n]+:\d+:\d+\)|Action Controller: Exception")
DUMP, LITE, INFO, LIST = r"(?i)CREATE TABLE|INSERT INTO", r"^SQLite format 3", r"phpinfo\(\)|PHP Version", LISTING
GIT = "the git folder: all source code and its history"
FILES = [  # (path, severity, sign of the real thing in the answer, what it is); a path ending in / is a folder
    ("/.env", "critical", r"(?m)^\s*[A-Z][A-Z0-9_]*\s*=", "the environment file with passwords and keys"),
    ("/.git/HEAD", "critical", r"^(ref: |[0-9a-f]{40})", GIT), ("/.git/config", "critical", r"\[core\]", GIT),
    ("/backup.sql", "critical", DUMP, "a database dump"), ("/dump.sql", "critical", DUMP, "a database dump"),
    ("/db.sqlite3", "critical", LITE, "the database file"), ("/backup.zip", "critical", r"^PK\x03\x04", "a backup archive"),
    ("/database/database.sqlite", "critical", LITE, "the database file"),
    ("/.aws/credentials", "critical", r"aws_access_key_id", "cloud account keys"),
    ("/storage/logs/laravel.log", "high", r"\[\d{4}-\d\d-\d\d[^\]]*\] \w+\.[A-Z]+:", "the application log"),
    ("/phpinfo.php", "high", INFO, "a phpinfo page: server settings"), ("/info.php", "high", INFO, "a phpinfo page"),
    ("/telescope", "high", r"(?i)<title>[^<]*Telescope", "Laravel Telescope: every request, query and mail"),
    ("/_ignition/health-check", "high", r"can_execute_commands", "the Laravel Ignition debug endpoint"),
    ("/.DS_Store", "low", r"Bud1", "a macOS folder file that lists file names"),
    ("/uploads/", "medium", LIST, "folder listing"), ("/storage/", "medium", LIST, "folder listing"),
    ("/static/", "medium", LIST, "folder listing"), ("/assets/", "medium", LIST, "folder listing"),
]
RULES = {  # check: (severity, title, why, fix)
    "exposed_file": ("critical", "A file that must stay private is served", "anyone can download it: passwords, keys, "
                     "source code or customer data", "block it in the web server or move it out of the web root, "
                     "then replace every secret that was in it"),
    "dir_listing": ("medium", "A folder shows a list of its files", "visitors can browse and download everything in it",
                    "switch folder listings off (nginx: autoindex off; Apache: Options -Indexes)"),
    "debug_page": ("high", "A debug page or stack trace is shown to visitors", "it shows code, settings and sometimes "
                   "secrets", "switch debug off (Laravel: APP_DEBUG=false, Django: DEBUG = False); show a plain error page"),
    "reflected_input": ("high", "Input comes back in the page unescaped (reflected XSS)", "a crafted link runs script "
                        "in a visitor's browser, as that visitor", "escape it in the template; no {!! !!}, |safe or "
                        "innerHTML for anything a visitor can send"),
    "sql_error": ("critical", "A database error appears after a single quote (SQL injection likely)", "input ends up "
                  "inside the SQL text: an attacker may read or change the database", "use the ORM or placeholders, "
                  "never glue input into SQL; hide database errors from visitors"),
    "open_redirect": ("medium", "The app redirects to any site named in a parameter", "a link to your site can send "
                      "people to a fake login page", "only redirect to paths on your own site, or to a fixed list"),
    "cors": ("high", "Any website may read answers with the visitor's login (CORS)", "the app repeats any Origin and "
             "allows credentials: a hostile site reads a logged-in visitor's data", "allow only your own origins"),
    "csrf_form": ("medium", "Check: a form posts without a hidden CSRF token", "another site could submit it as the "
                  "logged-in visitor", "add the CSRF field (@csrf, {% csrf_token %}); SameSite cookies or a token in "
                  "a header also protect, so check which you have"),
    "trace": ("low", "The TRACE method is allowed", "it echoes request headers back, which helps steal cookies",
              "switch TRACE off in the web server (Apache: TraceEnable off)"),
}
SKIPPED = [  # the notes under "Not checked": the first only when no query parameter was given, the rest always
    "reflected input, SQL errors, open redirect: no query parameters given; add lines like /search?q=tea to --paths",
    "stored XSS, blind or time-based SQL injection, POST bodies and JSON input: only query parameters are tested",
    "pages behind a login: no cookies are sent; for access control between users run authz.py",
    "login rate limit (it needs POSTs), cookie flags (headers.py reports them), source maps",
]

class Stop(Exception):
    """The request cap is reached: the run ends here."""

class KeepEveryAnswer(urllib.request.HTTPErrorProcessor):  # no redirect is followed; a 404 or 500 is not an error
    def http_response(self, request, response):
        return response
    https_response = http_response

class Forms(html.parser.HTMLParser):
    """Collects the forms of a page: ({"method", "action", "fields": [(type, name, value)]}, ...)."""
    forms = ()
    def handle_starttag(self, tag, attrs):
        a = {key: value or "" for key, value in attrs}
        if tag == "form":
            self.forms += ({"method": a.get("method", "get").lower(), "action": a.get("action", ""), "fields": []},)
        elif tag == "input" and self.forms:
            self.forms[-1]["fields"].append((a.get("type", "text").lower(), a.get("name", ""), a.get("value", "")))

class Run:
    """One probe run: sends the requests (only to the app itself, counted, paused, capped) and keeps the findings."""
    def __init__(self, base, limit):
        self.base, self.limit, self.count, self.cut_short, self.findings, self.notes = base, limit, 0, False, [], []
        self.opener = urllib.request.build_opener(KeepEveryAnswer, urllib.request.ProxyHandler({}))  # direct, no proxy
    def send(self, path, headers=None, method="GET"):
        """(status, [(lowercase header, value)], text) of one request to the app itself. Raises Stop at the cap."""
        if method not in ("GET", "TRACE") or not path.startswith("/"):
            raise ValueError("refused: only GET or TRACE, and only to a path on the app itself")
        if self.count >= self.limit:
            raise Stop()
        self.count += 1
        time.sleep(PAUSE)
        request = urllib.request.Request(self.base + path, method=method,
                                         headers=dict(headers or {}, **{"User-Agent": USER_AGENT}))
        with self.opener.open(request, timeout=TIMEOUT) as answer:
            text = answer.read(BODY_CAP).decode("utf-8", errors="replace")
            return answer.status, [(key.lower(), value) for key, value in answer.headers.items()], text
    def ask(self, path, headers=None, method="GET"):
        """send(), or None when no answer came: that is noted and the run counts as cut short."""
        try:
            return self.send(path, headers, method)
        except (OSError, http.client.HTTPException, ValueError) as error:
            self.cut_short = True
            self.notes.append("%s %s: no answer (%s)" % (method, show(path.split("?")[0]), show(error)))
    def add(self, check, where, once=False, severity=None):
        """Record one finding. The same one is kept once; with once=True a check is reported once per run."""
        default, title, why, fix = RULES[check]
        if not any(f["check"] == check and (once or f["where"] == where) for f in self.findings):
            self.findings.append({"check": check, "severity": severity or default, "title": title, "where": where,
                                  "why": why, "fix": fix})

def show(text, limit=80):  # text from a server or a file made safe to print: no control characters, not too long
    text = "".join(ch if ch.isprintable() else "?" for ch in str(text))
    return text if len(text) <= limit else text[:limit] + "..."
def get(headers, name):  # all values of one header (lowercase name) joined with ", ", or "" when missing
    return ", ".join(value for key, value in headers if key == name)

def forms_of(text):
    parser = Forms()
    parser.feed(text)
    return parser.forms

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

def check_answer(run, label, got):
    """What any answer can show: a debug page or stack trace, a folder listing, CORS open to every site."""
    status, headers, text = got
    if DEBUG_PAGE.search(text):
        run.add("debug_page", "%s answered %d" % (label, status), once=True)
    if LISTING.search(text):
        run.add("dir_listing", label)
    if (get(headers, "access-control-allow-origin").strip() == ELSEWHERE
            and get(headers, "access-control-allow-credentials").strip().lower() == "true"):
        run.add("cors", "%s, sent with Origin: %s" % (label, ELSEWHERE), once=True)

def check_page(run, page, mark):
    """Load one page, look at its forms, and test each of its query parameters."""
    path, _, query = page.partition("?")
    label = "GET " + show(path)
    got = run.ask(page, headers={"Origin": ELSEWHERE})
    if not got:
        return
    status, headers, text = got
    check_answer(run, label, got)
    if 300 <= status < 400:
        run.notes.append("%s is a redirect to %s: not followed; add that path to --paths if it is on your app"
                         % (label, show(get(headers, "location").split("?")[0])))
    for form in forms_of(text) if "html" in get(headers, "content-type").lower() else []:
        if form["method"] == "post" and not any(k == "hidden" and CSRF_NAME.search(n) for k, n, _ in form["fields"]):
            run.add("csrf_form", "%s, the form that posts to %s" % (label, show(form["action"]) or "the same page"))
    params = urllib.parse.parse_qsl(query, keep_blank_values=True)
    for index, (name, _) in enumerate(params):
        where = "%s, parameter %s" % (label, show(name, 40))
        changed = [urllib.parse.urlencode(params[:index] + [(name, value)] + params[index + 1:])
                   for value in (mark + "<\"'>", ELSEWHERE + "/")]  # a harmless marker with < " ' >, and a made-up site
        got = run.ask(path + "?" + changed[0])
        if got:
            check_answer(run, where + " with a single quote in it", got)
            if "html" in get(got[1], "content-type").lower() and re.search(mark + r'(<|&lt;")', got[2]):
                run.add("reflected_input", where)
            if SQL_ERROR.search(got[2]) and not SQL_ERROR.search(text):
                run.add("sql_error", where)
        got = run.ask(path + "?" + changed[1]) if REDIRECT_NAME.search(name) else None
        if got and 300 <= got[0] < 400 and GONE_ELSEWHERE.match(get(got[1], "location").strip()):
            run.add("open_redirect", where)

def probe(run, pages):
    """All checks in order: the fixed ones first, then the pages, so a long --paths cannot crowd them out."""
    mark = "fprobe" + os.urandom(4).hex()
    missing = "/forge-probe-" + mark  # a page that does not exist: shows the app's error page
    check_answer(run, "GET %s (a page that does not exist)" % missing, run.send(missing))
    for path, severity, sign, what in FILES:
        got = run.ask(path)
        if got and got[0] == 200 and re.search(sign, got[2]):
            check = "dir_listing" if path.endswith("/") else "exposed_file"
            run.add(check, "GET %s answered 200 (%s)" % (path, what), severity=severity)
    got = run.ask("/", method="TRACE")
    if got and got[0] == 200 and ("message/http" in get(got[1], "content-type") or got[2].startswith("TRACE ")):
        run.add("trace", "TRACE / answered 200")
    for page in pages:
        check_page(run, page, mark)

def load_paths(path, first):
    """The pages to load: FIRST, then the paths in a --paths file, without doubles. ValueError names a wrong line."""
    with open(path or os.devnull, encoding="utf-8-sig", errors="replace") as handle:
        lines = handle.read(1024 * 1024).splitlines()
    pages = [first]
    for number, line in enumerate(lines, 1):
        line = urllib.parse.quote(line.split("#")[0].strip(), safe="/?&=%+,;:@~!$*()'")  # a # starts a comment
        if line and (not line.startswith("/") or line.startswith("//")):
            raise ValueError("--paths line %d: write a path that starts with one /, like /search?q=tea" % number)
        pages += [line] if line and line not in pages else []
    return pages

def main(argv=None):
    """Read the command line, ask scope.py, probe, print the report and return the exit code."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: escapes, no crash
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("url", help="http:// or https:// address of your own running app")
    parser.add_argument("--paths", metavar="FILE", help="text file: one path per line, query string allowed")
    parser.add_argument("--scope", metavar="FILE", help="scope file for scope.py (default: forge-work/scope.json)")
    parser.add_argument("--max-requests", type=int, default=150, metavar="N", help="request cap, 1 to 500 (default: 150)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high",
                        help="exit 1 when a finding is this bad or worse (default: high)")
    args = parser.parse_args(argv)
    try:
        parts = urllib.parse.urlsplit(args.url)
        if parts.scheme not in ("http", "https") or not parts.hostname or "@" in parts.netloc or (parts.port or 1) < 1:
            raise ValueError("give an http:// or https:// address, without a user name or password in it")
        if not 1 <= args.max_requests <= 500:
            raise ValueError("--max-requests must be from 1 to 500: this is a check, not a load test")
        first = urllib.parse.quote(parts.path or "/", safe="/%") + ("?" + parts.query if parts.query else "")
        pages = load_paths(args.paths, first)
    except (OSError, ValueError) as error:
        print("error: %s" % show(error, 300), file=sys.stderr)
        return 2
    allowed, said = in_scope(parts.hostname, args.scope)  # asked about the host the requests would go to
    if not allowed:
        print("refused: active tests may not run against %s. Nothing was sent.\nscope.py says: %s"
              % (show(parts.hostname), said), file=sys.stderr)
        return 2
    run = Run("%s://%s" % (parts.scheme, parts.netloc), args.max_requests)
    try:
        probe(run, pages)
    except Stop:
        run.cut_short = True
        run.notes.append("the request cap of %d was reached, the rest was not checked: raise --max-requests" % run.limit)
    except (OSError, http.client.HTTPException) as error:
        print("error: could not reach %s: %s" % (show(run.base), show(error, 200)), file=sys.stderr)
        return 2
    run.notes += SKIPPED[1 if "?" in "".join(pages) else 0:]
    run.findings.sort(key=lambda f: SEVERITIES.index(f["severity"]))
    failed = any(SEVERITIES.index(f["severity"]) <= SEVERITIES.index(args.fail_on) for f in run.findings)
    summary = {sev: sum(f["severity"] == sev for f in run.findings) for sev in SEVERITIES}
    summary.update(total=len(run.findings), url=show(run.base), requests=run.count, fail_on=args.fail_on,
                   failed=failed, incomplete=run.cut_short)
    lines = ["Probed %s with %d requests." % (summary["url"], run.count), ""]
    lines += ["%-8s  %s [%s]\n          where: %s\n          why:   %s\n          fix:   %s\n" % (f["severity"].upper(),
              f["title"], f["check"], f["where"], f["why"], f["fix"]) for f in run.findings]
    counts = ", ".join("%d %s" % (summary[sev], sev) for sev in SEVERITIES if summary[sev])
    lines += ["%d finding(s): %s." % (len(run.findings), counts) if run.findings else "No findings.", "", "Not checked:"]
    lines += ["- " + note for note in run.notes]
    lines += ["", "The run was cut short (see Not checked): not a pass. Fix that and run again."] if run.cut_short else []
    report = {"findings": run.findings, "not_checked": run.notes, "summary": summary}
    print(json.dumps(report, indent=2) if args.json else "\n".join(lines), flush=True)
    return 1 if failed else 2 if run.cut_short else 0

if __name__ == "__main__":
    sys.exit(main())
