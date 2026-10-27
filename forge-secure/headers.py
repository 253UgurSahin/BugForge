#!/usr/bin/env python3
"""Check a site's HTTP security headers, passively: exactly one GET, like one visitor, body unread.

Checks https, HSTS, Content-Security-Policy, clickjacking, nosniff, Referrer-Policy, Permissions-Policy,
cookie flags and versions in Server or X-Powered-By. Redirects are not followed: the report says where
one points. Cookie values, passwords and query strings are never printed. forge:allow does not apply.

Usage:
    python3 headers.py https://example.com [--json] [--fail-on medium]
    python3 headers.py --file saved.txt [--url http://example.com]    (no network)

--file reads saved headers (`curl -sIL URL > saved.txt` or the browser's network tab). With --url (the address
you loaded) a saved redirect chain is followed on paper; without it, https is assumed. <meta> policies are not seen.
Exit codes: 0 = nothing at or above --fail-on (default: high); 1 = a finding at or above it;
2 = bad input: not an http(s) URL, unreadable --file, or the site could not be reached.
"""

import argparse
import http.client
import json
import os
import re
import socket
import ssl
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
USER_AGENT = "forge-headers (passive check)"
TIMEOUT = 15  # seconds for the whole answer
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")  # plain http is fine here
HALF_YEAR = 15552000  # seconds: the shortest HSTS max-age worth having
STATUS_LINE = re.compile(r"HTTP/[0-9.]+ +([0-9]{3})\b")  # "HTTP/1.1 200 OK", "HTTP/2 301"
MORE_FOLLOWS = set(range(100, 200)) | set(range(300, 400))  # in a saved chain, after 1xx and redirects
# Session cookies: PHPSESSID, laravel_session, auth, access_token, connect.sid ("sid" only as its own word).
SESSION_NAME = re.compile(r"sess|auth|token|(?<![a-z])sid(?![a-z])", re.I)
CSRF_NAME = re.compile(r"csrf|xsrf", re.I)  # CSRF cookies are meant to be read by JavaScript
VERSION = re.compile(r"\d+\.\d+")  # nginx/1.25.3, PHP/8.2.1
PLAIN_ERRORS = [  # (kind of network error, what it means in plain words)
    (ssl.SSLCertVerificationError, "its https certificate is not trusted (expired, self-signed or for another name?): "
     "visitors see a warning. If all https sites fail, add root certificates (macOS: Install Certificates.command)"),
    (socket.gaierror, "that name was not found: check the spelling (or the domain has no DNS record)"),
    (ConnectionRefusedError, "nothing answered there (connection refused): check the address and the port"),
    ((socket.timeout, TimeoutError), "no complete answer within %d seconds" % TIMEOUT),
]
RULES = {  # rule: (severity, title, why, fix)
    "no_https": ("high", "Page not served over HTTPS", "people on the same wifi can read or change it, logins too",
                 "serve it over https and redirect every http address to its https twin (301)"),
    "no_hsts": ("medium", "No Strict-Transport-Security header", "a hostile network can push browsers back to http",
                "add: Strict-Transport-Security: max-age=31536000; includeSubDomains"),
    "short_hsts": ("low", "Short Strict-Transport-Security max-age", "browsers soon stop insisting on https",
                   "use max-age=31536000 (one year); under 180 days is too short"),
    "no_csp": ("medium", "No Content-Security-Policy that limits scripts", "injected script (XSS) runs freely",
               "add Content-Security-Policy-Report-Only: default-src 'self'; object-src 'none'; base-uri 'self', "
               "fix what the browser console says it would block, then rename it to Content-Security-Policy"),
    "unsafe_csp": ("low", "Content-Security-Policy allows unsafe scripts", "an injected script still runs",
                   "move inline scripts into .js files (or allow them with nonces or hashes); stop using eval"),
    "no_frame": ("medium", "No clickjacking protection", "other sites can frame the page and trick people into clicks",
                 "add Content-Security-Policy: frame-ancestors 'self' (or X-Frame-Options: DENY)"),
    "no_nosniff": ("low", "X-Content-Type-Options is not nosniff", "browsers may run an uploaded file as script",
                   "add: X-Content-Type-Options: nosniff"),
    "no_referrer": ("low", "No Referrer-Policy header", "full addresses (with ids or tokens) leak to other sites",
                    "add: Referrer-Policy: strict-origin-when-cross-origin"),
    "no_permissions": ("low", "No Permissions-Policy header", "nothing limits camera, microphone or location use",
                       "switch off what the site does not use: Permissions-Policy: camera=(), microphone=()"),
    "no_secure": ("medium", "Cookie without Secure", "it also goes over plain http, where others can read it",
                  "add the Secure flag to this cookie"),
    "no_httponly": ("low", "Cookie readable by JavaScript (no HttpOnly)", "injected script (XSS) can steal it",
                    "add HttpOnly (leave it off only if your own JavaScript must read this cookie)"),
    "no_samesite": ("low", "Cookie without SameSite", "older browsers send it on requests from other sites (CSRF)",
                    "add SameSite=Lax (or Strict); SameSite=None only together with Secure"),
    "version": ("low", "Server software version is visible", "attackers can look up known holes for that version",
                "hide it (nginx: server_tokens off; Apache: ServerTokens Prod; PHP: expose_php = Off)"),
}

def hit(rule, where, severity=None):  # one finding for a rule from RULES
    default_severity, title, why, fix = RULES[rule]
    return {"severity": severity or default_severity, "title": title, "where": where, "why": why, "fix": fix}

def show(text, limit=80):  # text from a server made safe to print: no control characters, not too long
    text = "".join(ch if ch.isprintable() else "?" for ch in str(text))
    return text if len(text) <= limit else text[:limit] + "..."

def safe_url(url):
    """url fit to print (None stays None): a user:password, ;jsessionid=, ?query or #part becomes ****."""
    if url is not None:
        url = re.sub(r"//[^/?#]*@", "//****@", url, count=1)
        return show(re.sub(r"([;?#]).*", r"\1****", url, count=1, flags=re.S))

def url_problem(url):
    """Say in plain words why url cannot be checked, or return None for a plain http(s) address."""
    try:
        parts = urllib.parse.urlsplit(url)
        parts.port  # raises ValueError when the port is not a number from 0 to 65535
    except ValueError:
        return "that is not a valid web address"
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return "only http:// and https:// addresses can be checked, for example https://example.com"
    if "@" in parts.netloc:
        return "remove the username and password from the address: never put credentials in a URL"

def parse_raw_headers(text):
    """Saved answers [(status or None, [(lowercase name, value)]), ...]; a chain goes on after 1xx or redirects."""
    answers, ended = [], False  # ended: the blank line after the current answer's headers was seen
    for line in text.splitlines():
        status = STATUS_LINE.match(line)
        if status and (not answers or (ended and answers[-1][0] in MORE_FOLLOWS)):
            answers.append((int(status.group(1)), []))
            ended = False
        elif not line.strip():
            ended = bool(answers)
        elif ended:
            break  # the body: even text in it that looks like headers is not read
        elif ":" in line and not line.startswith(":"):  # ":status" is an HTTP/2 pseudo-header
            if not answers:
                answers.append((None, []))  # saved without a status line
            name, value = line.split(":", 1)
            answers[-1][1].append((name.strip().lower(), value.strip()))
    return answers

def get(headers, name):  # all values of one header (lowercase name) joined with ", ", or "" when missing
    return ", ".join(value for key, value in headers if key == name)

def where(headers, name):  # 'Name: value' for a header that is there (shortened), or 'Name (missing)'
    value = get(headers, name.lower())
    return name + ": " + show(value) if value else name + " (missing)"

def redirect_target(url, status, headers):
    """Where a redirect answer sends the visitor, or None. Browsers ignore Location on other answers."""
    locations = [value for key, value in headers if key == "location"]
    if not locations or (status is not None and status not in range(300, 400)):
        return None
    try:
        return urllib.parse.urljoin(url or "", locations[0].strip())
    except ValueError:  # a broken address
        return None

def check_page(headers):
    """Headers that protect a page: Content-Security-Policy, framing, nosniff, Referrer- and Permissions-Policy."""
    csp = {}  # directive -> sources, all policies together; the first copy of a directive wins
    for part in get(headers, "content-security-policy").lower().replace(",", ";").split(";"):
        words = part.split()
        if words and words[0] not in csp:
            csp[words[0]] = words[1:]
    script_rule = "script-src" if "script-src" in csp else "default-src"  # what browsers use for scripts
    sources = csp.get(script_rule, [])
    found = [] if script_rule in csp else [hit("no_csp", where(headers, "Content-Security-Policy"))]
    nonce_or_hash = any(s.startswith(("'nonce-", "'sha")) for s in sources)  # then 'unsafe-inline' is ignored
    unsafe = [s for s in sources if s == "'unsafe-eval'" or (s == "'unsafe-inline'" and not nonce_or_hash)]
    if unsafe:
        found.append(hit("unsafe_csp", "Content-Security-Policy: %s %s" % (script_rule, " ".join(unsafe))))
    frame_options = {value.strip().lower() for value in get(headers, "x-frame-options").split(",")}
    if "frame-ancestors" not in csp and not frame_options & {"deny", "sameorigin"}:  # browsers ignore ALLOW-FROM
        found.append(hit("no_frame", where(headers, "X-Frame-Options") + ", no CSP frame-ancestors"))
    if get(headers, "x-content-type-options").split(",")[0].strip().lower() != "nosniff":  # the first value counts
        found.append(hit("no_nosniff", where(headers, "X-Content-Type-Options")))
    for name, rule in [("Referrer-Policy", "no_referrer"), ("Permissions-Policy", "no_permissions")]:
        if not get(headers, name.lower()).strip():
            found.append(hit(rule, name + " (missing)"))
    return found

def check_cookie(cookie, https):
    """Flags on one Set-Cookie header. Only the cookie's name is ever shown, never its value."""
    parts = cookie.split(";")
    name = parts[0].split("=", 1)[0].strip() if "=" in parts[0] else ""  # without "=" it is all value
    flags = {part.split("=", 1)[0].strip().lower() for part in parts[1:]}
    where = "Set-Cookie: " + (show(name, 40) or "(no name)")
    found = [hit("no_secure", where)] if https and "secure" not in flags else []
    if "httponly" not in flags and not CSRF_NAME.search(name):
        found.append(hit("no_httponly", where, "medium" if SESSION_NAME.search(name) else "low"))
    if "samesite" not in flags:
        found.append(hit("no_samesite", where))
    return found

def check(headers, url=None, status=None):
    """Findings for one answer, most severe first (url None: https assumed). A redirect gets redirect checks only."""
    target = redirect_target(url, status, headers)
    https = urllib.parse.urlsplit(url or "").scheme != "http"
    landing = urllib.parse.urlsplit(target or url or "")  # where the visitor ends up
    found = [] if target else check_page(headers)
    if landing.scheme == "http" and landing.hostname not in LOCAL_HOSTS:
        found.append(hit("no_https", "redirect to " + safe_url(target) if target else safe_url(url)))
    hsts = get(headers, "strict-transport-security")
    max_age = re.search(r"max-age\s*=\s*\"?([0-9]+)", hsts, re.I)
    digits = max_age.group(1).lstrip("0") if max_age else ""
    if https and not hsts:
        found.append(hit("no_hsts", "Strict-Transport-Security (missing)"))
    elif https and len(digits) <= 8 and int(digits or "0") < HALF_YEAR:  # count digits first: int() refuses 4300+
        found.append(hit("short_hsts", where(headers, "Strict-Transport-Security")))
    for cookie in [value for key, value in headers if key == "set-cookie"]:
        found += check_cookie(cookie, https)
    for name in ["Server", "X-Powered-By"]:
        if VERSION.search(get(headers, name.lower())):
            found.append(hit("version", where(headers, name)))
    return sorted(found, key=lambda f: SEVERITIES.index(f["severity"]))

class KeepEveryAnswer(urllib.request.HTTPErrorProcessor):
    """Hand back every answer as it is: no redirect is followed, and a 404 or 500 is not an error."""
    def http_response(self, request, response):
        return response
    https_response = http_response

def fetch(url):
    """The one passive GET: (status, headers), body unread. One deadline for it all: slow headers cannot stall it."""
    outcome = []  # (status, headers), or the error
    def get_once():
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.build_opener(KeepEveryAnswer).open(request, timeout=TIMEOUT) as answer:
                outcome.append((answer.status, [(name.lower(), value) for name, value in answer.headers.items()]))
        except Exception as error:  # raised again below, in the caller's thread
            outcome.append(error)
    worker = threading.Thread(target=get_once, daemon=True)
    worker.start()
    worker.join(TIMEOUT)
    if not outcome:
        raise TimeoutError("no complete answer within %d seconds" % TIMEOUT)
    if isinstance(outcome[0], Exception):
        raise outcome[0]
    return outcome[0]

def explain(error):
    """A plain reason why the headers could not be read."""
    reason = error.reason if isinstance(error, urllib.error.URLError) else error  # urllib wraps the real error
    for kind, words in PLAIN_ERRORS:
        if isinstance(reason, kind):
            return words
    return show(reason.strerror if isinstance(reason, OSError) and reason.strerror else reason, 200)

def load_saved(path, url):
    """(status, headers, url) of the last saved answer; a saved redirect chain is followed on paper to its url."""
    with open(path, "rb") as handle:
        data = handle.read(1024 * 1024)
    utf16 = data.startswith((b"\xff\xfe", b"\xfe\xff"))  # byte order marks: Windows PowerShell saves UTF-16
    answers = parse_raw_headers(data.decode("utf-16" if utf16 else "utf-8-sig", errors="replace"))
    if not answers or not answers[-1][1]:
        raise ValueError("no 'Name: value' header lines found")
    for status, headers in answers[:-1]:
        url = redirect_target(url, status, headers) or url
    return answers[-1][0], answers[-1][1], url

def format_human(findings, summary, intro):
    """The report for people: the intro, one block per finding, then a one-line summary."""
    lines = [intro, ""]
    for f in findings:
        lines.append("%-8s  %s\n          where: %s\n          why:   %s\n          fix:   %s\n"
                     % (f["severity"].upper(), f["title"], f["where"], f["why"], f["fix"]))
    counts = ", ".join("%d %s" % (summary[sev], sev) for sev in SEVERITIES if summary[sev])
    noun = "finding" if len(findings) == 1 else "findings"
    lines.append("%d %s: %s." % (len(findings), noun, counts) if findings else "No findings.")
    return "\n".join(lines)

def main(argv=None):
    """Read the command line, get the headers once, print the report and return the exit code."""
    parser = argparse.ArgumentParser(description="Passive check of a site's HTTP security headers (one GET).")
    parser.add_argument("url", nargs="?", help="http:// or https:// address to load once and check")
    parser.add_argument("--file", help="check saved headers instead (no network)")
    parser.add_argument("--url", dest="file_url", metavar="URL", help="with --file: the address you loaded")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high",
                        help="exit 1 when a finding is this bad or worse (default: high)")
    args = parser.parse_args(argv)
    if bool(args.url) == bool(args.file) or (args.url and args.file_url):  # one or the other
        parser.error("give one URL to load, or --file SAVED_HEADERS with an optional --url")
    start = args.url or args.file_url  # None for --file without --url
    problem = url_problem(start) if start else None
    if problem:
        print("error: " + problem, file=sys.stderr)
        return 2
    try:
        if args.file:
            status, headers, url = load_saved(args.file, start)
            intro = "Checked saved headers from %s (%s)." % (show(args.file), safe_url(url) or "https assumed")
        else:
            url, (status, headers) = start, fetch(start)
            intro = "Checked %s (HTTP %s) with one passive GET." % (safe_url(url), status)
    except (OSError, http.client.HTTPException, ValueError) as error:
        source = show(args.file) if args.file else safe_url(start)
        print("error: could not get headers from %s: %s" % (source, explain(error)), file=sys.stderr)
        return 2
    target = redirect_target(url, status, headers)
    if target:
        intro += " It is a redirect to %s: that page was not checked, check it next." % safe_url(target)
    findings = check(headers, url, status)
    failed = any(SEVERITIES.index(f["severity"]) <= SEVERITIES.index(args.fail_on) for f in findings)
    summary = {sev: sum(f["severity"] == sev for f in findings) for sev in SEVERITIES}
    summary.update(total=len(findings), url=safe_url(url), status=status, redirect_to=safe_url(target),
                   fail_on=args.fail_on, failed=failed)
    try:
        print(json.dumps({"findings": findings, "summary": summary}, indent=2) if args.json
              else format_human(findings, summary, intro), flush=True)
    except BrokenPipeError:  # the reader stopped early (| head): end quietly, no traceback
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
