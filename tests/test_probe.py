"""Tests for forge-check/probe.py.

No real network: a small web server on 127.0.0.1 (port 0, in a thread) plays an app. Each test switches on the
holes it wants, so every check is shown to fire and to stay quiet. A public-looking target must be refused
before any request is sent.
"""

import contextlib
import html
import http.server
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
import urllib.parse
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `python3 -m unittest tests.test_probe` works
from _load import ROOT, load, run_cp1252  # noqa: E402

mod = load("forge-check", "probe")
mod.PAUSE = 0  # the pause between requests is for real apps, not for the tests

ALL_CHECKS = ["exposed_file", "dir_listing", "debug_page", "reflected_input", "sql_error", "open_redirect", "cors",
              "csrf_form", "trace"]
PATHS = ["/search?q=tea&page=2", "/api/search?q=tea", "/item?id=7", "/go?next=/home", "/crash", "/docs"]
ENV_BODY = "APP_" + "NAME=shop\nDB_" + "HOST=db-internal-host\n"  # in pieces: the repo's own scanners stay quiet
SQL_TEXT = "You have an error in your SQL " + "syntax; check the manual"
TRACEBACK = "Traceback (most recent " + "call last):\n  File app.py, line 7"
SHELL = "<html><body><div id=app>the app shell, served for every unknown path</div></body></html>"


class App(http.server.BaseHTTPRequestHandler):
    """An app with switchable holes. Without any, it is a safe single-page app that answers 200 to every path."""
    holes = frozenset()
    seen = []

    def log_message(self, *args):
        pass

    def answer(self, status, body, kind="text/html; charset=utf-8", headers=()):
        data = body.encode("utf-8")
        self.send_response(status)
        origin = self.headers.get("Origin") if "cors" in self.holes else "https://app.example.test"
        for name, value in [("Content-Type", kind), ("Content-Length", str(len(data))),
                            ("Access-Control-Allow-Origin", origin or "*"),
                            ("Access-Control-Allow-Credentials", "true")] + list(headers):
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.seen.append(("GET", self.path))
        path, _, query = self.path.partition("?")
        asked = dict(urllib.parse.parse_qsl(query))
        hole = lambda name: name in self.holes  # noqa: E731
        if path == "/":
            token = "" if hole("csrf_form") else '<input type="hidden" name="_token" value="abc">'
            self.answer(200, '<form method="POST" action="/book">%s<input name="room"></form>'
                             '<form action="/search"><input name="q"></form>' % token)
        elif path == "/search":
            value = asked.get("q", "")
            self.answer(200, "<p>You searched for %s</p>" % (value if hole("reflected_input") else html.escape(value)))
        elif path == "/api/search":  # JSON is not a page: an echo here is not a finding
            self.answer(200, json.dumps({"q": asked.get("q", "")}), "application/json")
        elif path == "/item" and "'" in asked.get("id", "") and hole("sql_error"):
            self.answer(500, "<p>%s</p>" % SQL_TEXT)
        elif path == "/docs":  # a page that always talks about SQL errors: not caused by the quote
            self.answer(200, "<p>Our manual explains: %s</p>" % SQL_TEXT)
        elif path == "/go":
            self.answer(302, "", headers=[("Location", asked.get("next", "/") if hole("open_redirect") else "/home")])
        elif path == "/crash":
            self.answer(500, "<pre>%s</pre>" % TRACEBACK if hole("debug_page") else "<p>Something went wrong.</p>")
        elif path == "/.env" and hole("exposed_file"):
            self.answer(200, ENV_BODY, "text/plain")
        elif path == "/.git/HEAD" and hole("exposed_file"):
            self.answer(200, "ref: refs/heads/main\n", "text/plain")
        elif path == "/uploads/" and hole("dir_listing"):
            self.answer(200, "<html><title>Index of /uploads/</title><a href=passport.pdf>passport.pdf</a></html>")
        elif hole("debug_404"):
            self.answer(404, "<p>You're seeing this error because you have <code>DEBUG = True</code></p>")
        elif hole("plain_404"):
            self.answer(404, "<p>Not found</p>")
        else:
            self.answer(200, SHELL)

    def do_TRACE(self):
        self.seen.append(("TRACE", self.path))
        if "trace" in self.holes:
            self.answer(200, "TRACE / HTTP/1.1\r\nCookie: echoed\r\n", "message/http")
        else:
            self.answer(405, "<p>Method not allowed</p>")

    def do_POST(self):
        self.seen.append(("POST", self.path))
        self.answer(200, "posted")

    do_DELETE = do_PUT = do_PATCH = do_POST


@contextlib.contextmanager
def serve(*holes):
    """Run the app with these holes; gives (its address, the list of requests it saw)."""
    app = type("AppWithHoles", (App,), {"holes": frozenset(holes), "seen": []})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), app)
    threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True).start()
    try:
        yield "http://127.0.0.1:%d" % server.server_address[1], app.seen
    finally:
        server.shutdown()
        server.server_close()


def run(*args):
    """Run main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = mod.main(list(args))
    return code, out.getvalue(), err.getvalue()


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.paths = self.write("paths.txt", "# my pages\n" + "\n".join(PATHS) + "\n\n/crash\n")

    def tearDown(self):
        shutil.rmtree(self.folder)

    def write(self, name, text):
        path = os.path.join(self.folder, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def probe(self, *holes, extra=()):
        """(exit code, report, requests seen) of one --json run against the app with these holes. A run cut short
        prints its report on stderr: a file that stdout is saved in stays empty, so it never counts as evidence."""
        with serve(*holes) as (url, seen):
            code, out, err = run(url, "--paths", self.paths, "--json", *extra)
        report = json.loads(err if code == 2 else out)
        self.assertEqual(out if code == 2 else err, "")
        self.assertEqual(code == 2, report["summary"]["incomplete"])
        return code, report, seen

    def checks(self, *holes):
        return sorted({finding["check"] for finding in self.probe(*holes)[1]["findings"]})

    def test_safe_app_has_no_findings(self):
        code, report, seen = self.probe()
        self.assertEqual((code, report["findings"]), (0, []))
        self.assertFalse(report["summary"]["incomplete"])
        self.assertEqual(report["summary"]["requests"], len(seen))

    def test_each_hole_gives_exactly_its_own_check(self):
        for check in ALL_CHECKS:
            with self.subTest(check=check):
                self.assertEqual(self.checks(check), [check])

    def test_vulnerable_app_fires_every_check(self):
        code, report, _ = self.probe(*ALL_CHECKS)
        self.assertEqual(code, 1)
        self.assertEqual(sorted({f["check"] for f in report["findings"]}), sorted(ALL_CHECKS))
        self.assertEqual(sorted(mod.RULES), sorted(ALL_CHECKS))  # no rule without a test
        severities = [mod.SEVERITIES.index(f["severity"]) for f in report["findings"]]
        self.assertEqual(severities, sorted(severities))  # worst first

    def test_findings_say_where_in_plain_words(self):
        where = {f["check"]: f["where"] for f in self.probe(*ALL_CHECKS)[1]["findings"]}
        self.assertEqual(where["reflected_input"], "GET /search, parameter q")
        self.assertEqual(where["sql_error"], "GET /item, parameter id")
        self.assertEqual(where["open_redirect"], "GET /go, parameter next")
        self.assertIn("form that posts to /book", where["csrf_form"])
        self.assertIn("GET /uploads/ answered 200", where["dir_listing"])
        self.assertIn("/crash", where["debug_page"])

    def test_severities(self):
        severity = {f["check"]: f["severity"] for f in self.probe(*ALL_CHECKS)[1]["findings"]}
        self.assertEqual(severity, {"exposed_file": "critical", "sql_error": "critical", "debug_page": "high",
                                    "reflected_input": "high", "cors": "high", "dir_listing": "medium",
                                    "open_redirect": "medium", "csrf_form": "medium", "trace": "low"})

    def test_django_debug_404_is_a_debug_page(self):
        self.assertEqual(self.checks("debug_404"), ["debug_page"])
        self.assertEqual(self.checks("plain_404"), [])

    def test_json_shape(self):
        code, report, _ = self.probe("csrf_form")
        self.assertEqual(sorted(report), ["findings", "not_checked", "summary"])
        self.assertEqual(sorted(report["findings"][0]), ["check", "fix", "severity", "title", "where", "why"])
        self.assertEqual(sorted(report["summary"]), sorted(mod.SEVERITIES + ["total", "url", "requests", "fail_on",
                                                                            "failed", "incomplete"]))
        self.assertEqual((code, report["summary"]["medium"], report["summary"]["failed"]), (0, 1, False))

    def test_fail_on(self):
        self.assertEqual(self.probe("csrf_form", extra=["--fail-on", "medium"])[0], 1)
        self.assertEqual(self.probe("trace", extra=["--fail-on", "medium"])[0], 0)
        self.assertEqual(self.probe("trace", extra=["--fail-on", "low"])[0], 1)

    def test_not_checked_lists_what_was_skipped(self):
        notes = " ".join(self.probe()[1]["not_checked"])
        for words in ["login rate limit", "cookie flags", "stored XSS", "authz.py", "GET /go is a redirect to /home"]:
            self.assertIn(words, notes)
        self.assertNotIn("no query parameters given", notes)
        with serve() as (url, _):
            code, out, _ = run(url)
        self.assertEqual(code, 0)
        self.assertIn("no query parameters given", out)
        self.assertIn("Not checked:", out)

    def test_only_harmless_requests_and_only_to_the_app(self):
        hosts = []
        connect = socket.create_connection

        def watched(address, *args, **kwargs):
            hosts.append(address[0])
            return connect(address, *args, **kwargs)

        with mock.patch("socket.create_connection", watched):
            _, report, seen = self.probe(*ALL_CHECKS)
        self.assertEqual(set(hosts), {"127.0.0.1"})  # the redirect to example.invalid was never followed
        self.assertEqual({method for method, _ in seen}, {"GET", "TRACE"})
        self.assertEqual([path for method, path in seen if method == "TRACE"], ["/"])
        sent = urllib.parse.unquote(" ".join(path for _, path in seen)).lower()
        for word in ["drop", "sleep", "union", "select", ";", "--", "<script"]:
            self.assertNotIn(word, sent)
        self.assertLessEqual(len(seen), 150)

    def test_send_refuses_other_methods_and_other_hosts(self):
        run_ = mod.Run("http://127.0.0.1:9", 5)
        for path, method in [("/", "DELETE"), ("/", "PUT"), ("/", "PATCH"), ("/", "POST"), ("@example.com/", "GET"),
                             (".example.com/", "GET")]:
            with self.assertRaises(ValueError):
                run_.send(path, method=method)
        self.assertEqual(run_.count, 0)

    def test_request_cap_stops_the_run_and_is_not_a_pass(self):
        code, report, seen = self.probe(extra=["--max-requests", "5"])
        self.assertEqual((code, len(seen)), (2, 5))
        self.assertTrue(report["summary"]["incomplete"])
        self.assertIn("request cap of 5", " ".join(report["not_checked"]))
        code, report, seen = self.probe("exposed_file", extra=["--max-requests", "5"])
        self.assertEqual((code, len(seen)), (2, 5))  # cut short wins: the paths after the cap were never probed
        self.assertEqual({finding["check"] for finding in report["findings"]}, {"exposed_file"})  # still reported

    def test_bodies_are_never_printed(self):
        with serve(*ALL_CHECKS) as (url, _):
            code, out, err = run(url, "--paths", self.paths)
        self.assertEqual(code, 1)
        for secret in ["db-internal-host", "passport.pdf", "File app.py", "check the manual"]:
            self.assertNotIn(secret, out + err)
        self.assertIn("CRITICAL  A file that must stay private is served [exposed_file]", out)
        self.assertIn("where: GET /.env answered 200", out)
        self.assertTrue(all(ord(ch) < 128 for ch in out))

    def test_public_host_is_refused_before_any_request(self):
        with mock.patch.object(mod.Run, "send", side_effect=AssertionError("a request was sent")), \
                mock.patch("socket.create_connection", side_effect=AssertionError("a connection was made")):
            for target in ["http://example.com/", "https://www.example.org/login", "http://93.184.216.34/",
                           "http://2130706433/", "http://127.0.0.1.nip.io/", "http://169.254.169.254/"]:
                with self.subTest(target=target):
                    code, out, err = run(target, "--json")
                    self.assertEqual((code, out), (2, ""))
                    self.assertIn("refused", err)
                    self.assertIn("Nothing was sent", err)

    def test_scope_file_decides_for_a_domain(self):
        scope = self.write("scope.json", json.dumps({"own_domains": ["example.com"]}))
        self.assertTrue(mod.in_scope("shop.example.com", scope)[0])
        self.assertFalse(mod.in_scope("shop.example.com")[0])
        self.assertFalse(mod.in_scope("shop.example.org", scope)[0])
        self.assertFalse(mod.in_scope("127.0.0.1", os.path.join(self.folder, "missing.json"))[0])
        with mock.patch.object(mod.Run, "send", side_effect=AssertionError("a request was sent")):
            code, _, err = run("http://127.0.0.1:9/", "--scope", os.path.join(self.folder, "missing.json"))
        self.assertEqual(code, 2)
        self.assertIn("refused", err)

    def test_bad_input_is_exit_2(self):
        with serve() as (url, seen):
            bad_paths = [self.write("bad%d.txt" % number, text) for number, text in
                         enumerate(["http://example.com/x\n", "//example.com/x\n", "search?q=1\n"])]
            cases = [["ftp://127.0.0.1/"], ["http://user:" + "pw@127.0.0.1/"], ["127.0.0.1"], ["http://127.0.0.1:99999/"],
                     [url, "--paths", os.path.join(self.folder, "missing.txt")], [url, "--max-requests", "0"],
                     [url, "--max-requests", "501"]] + [[url, "--paths", path] for path in bad_paths]
            for args in cases:
                with self.subTest(args=args):
                    code, out, err = run(*args)
                    self.assertEqual((code, out), (2, ""))
                    self.assertTrue(err.startswith("error: "))
                    self.assertNotIn("pw", err)
            self.assertEqual(seen, [])

    def test_app_that_is_not_running_is_exit_2(self):
        with socket.socket() as free:
            free.bind(("127.0.0.1", 0))
            port = free.getsockname()[1]
        code, out, err = run("http://127.0.0.1:%d/" % port)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("could not reach", err)

    def test_command_line(self):
        script = os.path.join(ROOT, "forge-check", "probe.py")
        code, out, _ = run_cp1252(script, "--help")
        self.assertEqual(code, 0)
        for words in ["Usage:", "Exit codes:", "--paths", "--max-requests", "--fail-on"]:
            self.assertIn(words, out)
        code, out, err = run_cp1252(script, "http://example.com/")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("refused", err)
        with serve("exposed_file") as (url, _):
            code, out, err = run_cp1252(script, url)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("exposed_file", out)


if __name__ == "__main__":
    unittest.main()
