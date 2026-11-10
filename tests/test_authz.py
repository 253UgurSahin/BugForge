"""Tests for forge-secure/authz.py.

No real network: a small web server on 127.0.0.1 (port 0, in a thread) plays an app with two users, alice and
bob. Some of its paths guard alice's data well and some do not, so each finding is shown to fire and to stay
quiet. A public-looking target must be refused before any request is sent, and no cookie value is ever printed.
"""

import contextlib
import http.server
import io
import itertools
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `python3 -m unittest tests.test_authz` works
from _load import ROOT, load, run_cp1252  # noqa: E402

mod = load("forge-secure", "authz")
mod.PAUSE = 0  # the pause between requests is for real apps, not for the tests

ALICE, BOB = "alice-" + "cookie-value-1", "bob-" + "cookie-value-2"  # the session values that must never be printed
USERS = {"sid=" + ALICE: "alice", "sid=" + BOB: "bob"}
BEARER = {"Bearer " + ALICE: "alice", "Bearer " + BOB: "bob"}
PRIVATE = "<html><h1>Booking 41</h1><p>%s</p></html>" % " ".join(
    "Guest Alice Example, room %d, passport NL%d, paid by card" % (number, 1000 + number) for number in range(30))
NOT_YOURS = "<html><h1>Sorry</h1><p>This booking is not yours.</p></html>"
LOGIN = '<html><form method="post"><input name="email"><input type="password" name="password"></form></html>'
COUNTER = itertools.count()


class App(http.server.BaseHTTPRequestHandler):
    """Every path belongs to alice. The first part of the path says how well it is guarded."""
    seen = []

    def log_message(self, *args):
        pass

    def answer(self, status, body="", location=None):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if location:
            self.send_header("Location", location)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        cookie = self.headers.get("Cookie", "")
        user = USERS.get(cookie) or BEARER.get(self.headers.get("Authorization", ""))
        self.seen.append((self.path, user))
        kind = self.path.split("/")[1]
        if kind == "public":  # no check at all: the same page for everyone
            self.answer(200, PRIVATE)
        elif kind == "dynamic":  # no check, and a new token in every answer
            self.answer(200, PRIVATE + "<input type=hidden name=_token value=t%d>" % next(COUNTER))
        elif user is None:
            if kind == "shell":  # a 200 "please log in" page without a form
                self.answer(200, "<html><p>Please log in first.</p></html>")
            elif kind == "inplace":  # the login page shown in place, with 200
                self.answer(200, LOGIN)
            elif kind == "api":
                self.answer(401, '{"error": "log in"}')
            else:
                self.answer(302, location="/login")
        elif kind == "leaky":  # logged in is enough: bob reads alice's booking
            self.answer(200, PRIVATE)
        elif user == "alice":
            self.answer(404 if kind == "gone" else 200, PRIVATE)
        elif kind == "boom":
            self.answer(500, "<p>error</p>")
        elif kind in ("soft", "shell"):  # bob gets 200 with a "not yours" page
            self.answer(200, NOT_YOURS)
        else:
            self.answer(404 if kind == "hidden" else 403, NOT_YOURS)


def run(*args):
    """Run main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = mod.main(list(args))
    return code, out.getvalue(), err.getvalue()


class AuthzTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), App)
        cls.url = "http://127.0.0.1:%d" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, args=(0.01,), daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        App.seen = []
        self.folder = tempfile.mkdtemp()
        self.alice = self.write("alice.txt", "# alice\nsid=%s\n" % ALICE)
        self.bob = self.write("bob.txt", "sid=%s\n" % BOB)

    def tearDown(self):
        shutil.rmtree(self.folder)

    def write(self, name, text):
        path = os.path.join(self.folder, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def check(self, *paths, a=None, b=None, extra=()):
        """(exit code, report) of one --json run over these private paths."""
        urls = self.write("urls.txt", "\n".join(paths) + "\n")
        code, out, err = run(self.url, "--urls", urls, "--a", a or self.alice, "--b", b or self.bob, "--json", *extra)
        self.assertEqual(err, "")
        self.assertNotIn(ALICE, out)
        self.assertNotIn(BOB, out)
        self.assertNotIn("passport NL", out)  # no response body in the report
        return code, json.loads(out)

    def found(self, path):
        code, report = self.check(path)
        return code, [(f["check"], f["severity"]) for f in report["findings"]]

    def test_guarded_paths_pass(self):
        code, report = self.check("/bookings/41", "/hidden/41", "/api/bookings/41?format=json", "/inplace/41")
        self.assertEqual((code, report["findings"]), (0, []))
        self.assertEqual(report["paths"][0], {"path": "/bookings/41", "a": 200, "b": 403, "anonymous": 302,
                                              "result": "pass"})
        self.assertEqual([(row["b"], row["anonymous"], row["result"]) for row in report["paths"][1:]],
                         [(404, 302, "pass"), (403, 401, "pass"), (403, 200, "pass")])
        self.assertFalse(report["summary"]["incomplete"])
        self.assertEqual(App.seen[:3], [("/bookings/41", "alice"), ("/bookings/41", "bob"), ("/bookings/41", None)])

    def test_other_user_reads_is_critical(self):
        self.assertEqual(self.found("/leaky/41"), (1, [("other_user_reads", "critical")]))

    def test_no_check_at_all_is_two_critical_findings(self):
        self.assertEqual(self.found("/public/41"),
                         (1, [("other_user_reads", "critical"), ("anonymous_reads", "critical")]))

    def test_nearly_the_same_page_counts_as_the_same(self):
        self.assertEqual(self.found("/dynamic/41"),
                         (1, [("other_user_reads", "critical"), ("anonymous_reads", "critical")]))

    def test_200_without_login_is_high_and_a_soft_refusal_is_a_note(self):
        code, report = self.check("/shell/41")
        self.assertEqual([(f["check"], f["severity"]) for f in report["findings"]], [("anonymous_200", "high")])
        self.assertEqual(code, 1)
        self.assertIn("user B got 200 with other content", " ".join(report["not_checked"]))
        code, report = self.check("/soft/41", extra=["--fail-on", "critical"])
        self.assertEqual((code, report["findings"]), (0, []))
        self.assertIn("look at it by hand", " ".join(report["not_checked"]))
        self.assertEqual(self.check("/shell/41", extra=["--fail-on", "critical"])[0], 0)

    def test_path_that_user_a_cannot_load_is_not_a_pass(self):
        code, report = self.check("/bookings/41", "/gone/41")
        self.assertEqual((code, report["findings"]), (2, []))
        self.assertEqual(report["paths"][1], {"path": "/gone/41", "a": 404, "b": None, "anonymous": None,
                                              "result": "could not check"})
        self.assertIn("/gone/41: user A got 404", " ".join(report["not_checked"]))
        self.assertTrue(report["summary"]["incomplete"])
        self.assertEqual(len([path for path, _ in App.seen if path == "/gone/41"]), 1)

    def test_server_error_for_b_is_not_a_pass_and_a_finding_wins(self):
        code, report = self.check("/boom/41")
        self.assertEqual((code, report["paths"][0]["result"]), (2, "could not check"))
        self.assertEqual(self.check("/boom/41", "/leaky/41")[0], 1)

    def test_expired_session_for_a_cannot_check(self):
        stale = self.write("stale.txt", "sid=long-gone\n")
        code, report = self.check("/bookings/41", a=stale)
        self.assertEqual((code, report["paths"][0]["a"]), (2, 302))

    def test_playwright_storage_state_and_bearer_lines(self):
        def state(value, domain="127.0.0.1"):
            return json.dumps({"cookies": [{"name": "sid", "value": value, "domain": domain, "path": "/"},
                                           {"name": "other", "value": "x", "domain": "elsewhere.test"}],
                               "origins": []})
        alice, bob = self.write("alice.json", state(ALICE)), self.write("bob.json", state(BOB))
        self.assertEqual(self.found("/leaky/41"), (1, [("other_user_reads", "critical")]))
        code, report = self.check("/leaky/41", "/bookings/41", a=alice, b=bob)
        self.assertEqual((code, [row["result"] for row in report["paths"]]), (1, ["finding", "pass"]))
        self.assertIn(("/leaky/41", "bob"), App.seen)
        alice = self.write("alice.token", "Authorization: Bearer %s\n" % ALICE)
        bob = self.write("bob.token", "authorization: Bearer %s\n" % BOB)
        code, report = self.check("/bookings/41", "/leaky/41", a=alice, b=bob)
        self.assertEqual((code, [row["result"] for row in report["paths"]]), (1, ["pass", "finding"]))
        wrong_host = self.write("wrong.json", state(ALICE, "localhost"))
        code, out, err = run(self.url, "--urls", self.write("u.txt", "/x\n"), "--a", wrong_host, "--b", self.bob)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("holds no cookie for 127.0.0.1", err)

    def test_bad_input_is_exit_2_and_shows_no_cookie(self):
        urls = self.write("u.txt", "/bookings/41\n")
        cases = {
            "same session": ["--a", self.alice, "--b", self.alice],
            "missing file": ["--a", os.path.join(self.folder, "none.txt"), "--b", self.bob],
            "not name=value": ["--a", self.write("bad.txt", ALICE + "\n"), "--b", self.bob],
            "broken json": ["--a", self.write("bad.json", '{"cookies": "%s"' % ALICE), "--b", self.bob],
            "no cookies list": ["--a", self.write("odd.json", '{"sid": "%s"}' % ALICE), "--b", self.bob],
            "control character": ["--a", self.write("ctl.txt", "sid=%s\x01x\n" % ALICE), "--b", self.bob],
            "empty": ["--a", self.write("empty.txt", "\n# nothing\n"), "--b", self.bob],
        }
        for name, args in cases.items():
            with self.subTest(case=name):
                code, out, err = run(self.url, "--urls", urls, *args)
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(err.startswith("error: "), err)
                self.assertNotIn(ALICE, err)
        for text in ["", "http://example.com/x\n", "//example.com/x\n", "bookings/41\n"]:
            with self.subTest(urls=text):
                code, out, err = run(self.url, "--urls", self.write("bad-urls.txt", text), "--a", self.alice,
                                     "--b", self.bob)
                self.assertEqual((code, out), (2, ""))
        for url in ["ftp://127.0.0.1/", "http://user:" + "pw@127.0.0.1/", "127.0.0.1"]:
            self.assertEqual(run(url, "--urls", urls, "--a", self.alice, "--b", self.bob)[0], 2)
        self.assertEqual(run(self.url, "--urls", urls, "--a", self.alice, "--b", self.bob, "--max-requests", "0")[0], 2)
        self.assertEqual(App.seen, [])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            mod.main([self.url, "--urls", urls, "--a", self.alice])  # --b is required

    def test_public_host_is_refused_before_any_request(self):
        urls = self.write("u.txt", "/bookings/41\n")
        with mock.patch.object(mod.Client, "get", side_effect=AssertionError("a request was sent")), \
                mock.patch("socket.create_connection", side_effect=AssertionError("a connection was made")):
            for target in ["http://example.com/", "https://shop.example.org/", "http://93.184.216.34/",
                           "http://127.0.0.1.nip.io/", "http://169.254.169.254/"]:
                with self.subTest(target=target):
                    state = self.write("s.json", json.dumps({"cookies": [{"name": "sid", "value": ALICE,
                                                                          "domain": target.split("/")[2]}]}))
                    code, out, err = run(target, "--urls", urls, "--a", state, "--b", self.bob)
                    self.assertEqual((code, out), (2, ""))
                    self.assertIn("refused", err)
                    self.assertNotIn(ALICE, err)
            code, _, err = run(self.url, "--urls", urls, "--a", self.alice, "--b", self.bob,
                               "--scope", os.path.join(self.folder, "missing.json"))
            self.assertEqual(code, 2)
            self.assertIn("refused", err)
        self.assertEqual(App.seen, [])

    def test_scope_file_decides_for_a_domain(self):
        scope = self.write("scope.json", json.dumps({"own_domains": ["example.com"]}))
        self.assertTrue(mod.in_scope("shop.example.com", scope)[0])
        self.assertFalse(mod.in_scope("shop.example.com")[0])

    def test_request_cap_is_not_a_pass(self):
        code, report = self.check("/bookings/41", "/hidden/41", extra=["--max-requests", "4"])
        self.assertEqual((code, len(App.seen)), (2, 4))
        self.assertIn("request cap of 4", " ".join(report["not_checked"]))
        self.assertEqual(len(report["paths"]), 1)

    def test_only_get_and_no_redirect_followed(self):
        self.check("/bookings/41")
        self.assertNotIn("/login", [path for path, _ in App.seen])
        with self.assertRaises(ValueError):
            mod.Client(self.url, 5).get("@example.com/")
        self.assertFalse(hasattr(mod.Client, "post"))

    def test_alike(self):
        self.assertTrue(mod.alike(PRIVATE, PRIVATE))
        self.assertTrue(mod.alike(PRIVATE + " token 123", PRIVATE + " token 987"))
        self.assertFalse(mod.alike(PRIVATE, NOT_YOURS))
        self.assertFalse(mod.alike(PRIVATE, PRIVATE.replace("Alice Example", "Bob Sample").replace("NL1", "BE7")))
        self.assertFalse(mod.alike(PRIVATE, ""))
        self.assertTrue(mod.alike("", ""))

    def test_json_shape_and_human_report(self):
        code, report = self.check("/leaky/41")
        self.assertEqual(sorted(report), ["findings", "not_checked", "paths", "summary"])
        self.assertEqual(sorted(report["findings"][0]), ["check", "fix", "severity", "title", "where", "why"])
        self.assertEqual(report["findings"][0]["where"], "GET /leaky/41 as user B answered 200 (user A: 200)")
        self.assertEqual(sorted(report["summary"]), sorted(mod.SEVERITIES + ["total", "url", "requests", "paths",
                                                                            "fail_on", "failed", "incomplete"]))
        self.assertIn("session was not verified", " ".join(report["not_checked"]))
        urls = self.write("urls.txt", "/leaky/41\n/bookings/41\n")
        code, out, err = run(self.url, "--urls", urls, "--a", self.alice, "--b", self.bob)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("CRITICAL  Another user can see this private page [other_user_reads]", out)
        self.assertIn("PASS            /bookings/41  (A 200, B 403, no session 302)", out)
        self.assertIn("list only private paths", out)
        self.assertNotIn(ALICE, out)
        self.assertNotIn("passport NL", out)
        self.assertTrue(all(ord(ch) < 128 for ch in out))

    def test_command_line(self):
        script = os.path.join(ROOT, "forge-secure", "authz.py")
        code, out, _ = run_cp1252(script, "--help")
        self.assertEqual(code, 0)
        for words in ["Usage:", "Exit codes:", "--urls", "--a", "--b", "storageState"]:
            self.assertIn(words, out)
        urls = self.write("urls.txt", "/leaky/41\n")
        code, out, err = run_cp1252(script, self.url, "--urls", urls, "--a", self.alice, "--b", self.bob)
        self.assertEqual((code, err), (1, ""))
        self.assertNotIn(ALICE, out)
        code, out, err = run_cp1252(script, "http://example.com/", "--urls", urls, "--a", self.alice, "--b", self.bob)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("refused", err)


if __name__ == "__main__":
    unittest.main()
