"""Tests for forge-inspect/getpage.py.

No real network: the one GET goes to a small web server on 127.0.0.1 that runs in a thread, and the
DNS and certificate errors are made up with mock.
"""

import contextlib
import http.server
import io
import json
import os
import shutil
import socket
import ssl
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `python3 -m unittest tests.test_getpage` works
from _load import load, run_cp1252  # noqa: E402

mod = load("forge-inspect", "getpage")

PAGE = "<!doctype html><html lang='en'><head><title>A page</title></head><body><h1>Hi</h1></body></html>"
BIG_BODY = 64 * 1024 * 1024  # bytes: far more than socket buffers hold


def run(*args):
    """Run main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = mod.main(list(args))
    return code, out.getvalue(), err.getvalue()


class LocalServer(http.server.BaseHTTPRequestHandler):
    """Answers like a small site. Remembers every request it gets."""

    requests = []
    body_sent = None
    done = threading.Event()
    routes = {
        "/": (200, [("Content-Type", "text/html; charset=utf-8")], PAGE),
        "/old": (301, [("Location", "/new?session=s3cr3t")], "<html>moved</html>"),
        "/broken-redirect": (302, [("Location", "http://[::1/x")], ""),
        "/missing": (404, [("Content-Type", "text/html")], "<html>not found</html>"),
        "/packed": (200, [("Content-Type", "text/html"), ("Content-Encoding", "gzip")], "\x1f\x8b not really"),
        "/data.json": (200, [("Content-Type", "application/json")], "{}"),
        "/big": (200, [("Content-Type", "text/html")], PAGE + "<p>x</p>" * 2000),
    }

    def do_GET(self):
        LocalServer.requests.append((self.command, self.path, self.headers.get("User-Agent")))
        if self.path == "/trickle":
            return self.trickle()
        if self.path == "/report.pdf":
            return self.big_pdf()
        status, headers, body = self.routes.get(self.path.split("?")[0], (200, [], PAGE))
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def trickle(self):
        """The status line, then one header line every 0.2 seconds for 4 seconds."""
        try:
            self.wfile.write(b"HTTP/1.1 200 OK\r\n")
            for number in range(20):
                time.sleep(0.2)
                self.wfile.write(b"X-Slow-%d: a\r\n" % number)
        except OSError:
            pass

    def big_pdf(self):
        """A huge file that is not HTML: a client that reads it would waste time and memory."""
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(BIG_BODY))
        self.end_headers()
        sent = 0
        try:
            while sent < BIG_BODY:
                self.wfile.write(b"x" * 65536)
                sent += 65536
        except OSError:
            pass
        LocalServer.body_sent = sent
        LocalServer.done.set()

    def log_message(self, *args):  # keep test output quiet
        pass


class GetPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), LocalServer)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        LocalServer.requests = []
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.out = os.path.join(self.dir, "page.html")
        patcher = mock.patch.dict(os.environ, {"no_proxy": "*", "NO_PROXY": "*"})  # never via a proxy
        patcher.start()
        self.addCleanup(patcher.stop)

    def paths(self):
        return [path for _, path, _ in LocalServer.requests]

    def test_one_passive_get_saves_the_page(self):
        code, out, err = run(self.base + "/", self.out)
        self.assertEqual(code, 0, err)
        self.assertEqual(LocalServer.requests, [("GET", "/", "forge-pagecheck (passive check)")])
        with open(self.out, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), PAGE)
        self.assertEqual(out, "Saved %s/ (HTTP 200, %.1f KB) in %s.\n" % (self.base, len(PAGE) / 1024.0, self.out))

    def test_a_cp1252_pipe_gets_escapes_not_a_crash(self):
        """Windows pipes are cp1252 (no arrow): the arrow prints as \\u2192, no crash."""
        out = os.path.join(self.dir, "caf\u00e9 \u2192.html")
        code, stdout, err = run_cp1252(mod.__file__, self.base + "/", out)
        self.assertEqual(code, 0, err)
        self.assertIn(" in %s." % out.replace("\u2192", "\\u2192"), stdout)

    def test_json_output(self):
        code, out, err = run(self.base + "/", self.out, "--json")
        summary = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(summary, {"url": self.base + "/", "saved": self.out, "status": 200,
                                   "bytes": len(PAGE), "cut": False})

    def test_an_existing_file_is_never_replaced(self):
        with open(self.out, "w") as handle:
            handle.write("keep me")
        code, out, err = run(self.base + "/", self.out)
        self.assertEqual(code, 2)
        self.assertIn("exists already", err)
        self.assertEqual(self.paths(), [])  # checked before the request
        with open(self.out) as handle:
            self.assertEqual(handle.read(), "keep me")

    def test_redirects_are_not_followed_and_named_in_json(self):
        code, out, err = run(self.base + "/old", self.out, "--json")
        self.assertEqual((code, self.paths()), (2, ["/old"]))
        self.assertIn("redirect (HTTP 301) to %s/new?****" % self.base, err)
        summary = json.loads(out)
        self.assertEqual((summary["status"], summary["redirect_to"]), (301, self.base + "/new?****"))
        self.assertNotIn("s3cr3t", out + err)
        self.assertFalse(os.path.exists(self.out))

    def test_a_broken_redirect_still_says_redirect(self):
        code, out, err = run(self.base + "/broken-redirect", self.out)
        self.assertEqual(code, 2)
        self.assertIn("it is a redirect (HTTP 302) to a broken address", err)

    def test_error_status(self):
        code, out, err = run(self.base + "/missing", self.out)
        self.assertEqual(code, 2)
        self.assertIn("answered HTTP 404", err)

    def test_files_that_are_not_web_pages_are_refused_unread(self):
        LocalServer.done.clear()
        code, out, err = run(self.base + "/report.pdf", self.out)
        self.assertEqual(code, 2)
        self.assertIn("it is application/pdf, not a web page", err)
        self.assertNotIn("--file", err)  # saving a PDF as a page would not help
        self.assertTrue(LocalServer.done.wait(10))
        self.assertLess(LocalServer.body_sent, BIG_BODY)
        self.assertIn("not a web page", run(self.base + "/data.json", self.out)[2])

    def test_a_compressed_answer_is_named_as_such(self):
        code, out, err = run(self.base + "/packed", self.out)
        self.assertEqual(code, 2)
        self.assertIn("it came compressed", err)
        self.assertNotIn("text/html", err)

    def test_only_the_first_part_is_kept(self):
        with mock.patch.object(mod, "MAX_BYTES", 3000):
            code, out, err = run(self.base + "/big", self.out, "--json")
        summary = json.loads(out)
        self.assertEqual((summary["bytes"], summary["cut"]), (3000, True))
        self.assertEqual(os.path.getsize(self.out), 3000)

    def test_one_deadline_covers_a_slowly_trickled_answer(self):
        with mock.patch.object(mod, "TIMEOUT", 1):
            started = time.time()
            code, out, err = run(self.base + "/trickle", self.out)
        self.assertLess(time.time() - started, 3)
        self.assertEqual(code, 2)
        self.assertIn("no complete answer", err)

    def test_spaces_and_letters_like_u_umlaut_are_encoded_and_the_query_stays_masked(self):
        secret = "SECRET" + "VALUE123"
        code, out, err = run(self.base + "/über?token=" + secret + " x", self.out)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.paths(), ["/%C3%BCber?token=" + secret + "%20x"])
        self.assertNotIn(secret, out + err)

    def test_bad_addresses_exit_2_without_any_request(self):
        for url in ["ftp://example.com/", "file:///etc/passwd", "data:,hi", "example.com", "http://[::1",
                    "http://127.0.0.1:99999/", "http://example.com:0/", "http://example.com:abc/",
                    "http://exa mple.com/"]:
            code, out, err = run(url, self.out)
            self.assertEqual(code, 2, url)
            self.assertIn("error:", err)
        self.assertIn("only http:// and https://", run("example.com", self.out)[2])
        self.assertEqual(self.paths(), [])

    def test_credentials_in_the_address_are_refused_and_never_printed(self):
        login = "Hunter2" + "-Prod-Passw0rd"
        code, out, err = run("https://admin:" + login + "@shop.example.com/", self.out, "--json")
        self.assertEqual(code, 2)
        self.assertIn("remove the username and password", err)
        self.assertNotIn(login, out + err)
        self.assertEqual(self.paths(), [])

    def test_a_refused_connection_is_said_in_plain_words(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            closed_port = probe.getsockname()[1]
        code, out, err = run("http://127.0.0.1:%d/" % closed_port, self.out)
        self.assertEqual(code, 2)
        self.assertIn("nothing answered there (connection refused)", err)
        self.assertNotIn("Errno", err)


class RefusingProxy(http.server.BaseHTTPRequestHandler):
    """A proxy that says no to every site, like some company and sandbox networks do."""

    asked = []

    def do_CONNECT(self):
        RefusingProxy.asked.append(self.path)
        self.send_response(403)
        self.end_headers()

    def log_message(self, *args):  # keep test output quiet
        pass


class ProxyTests(unittest.TestCase):
    def test_a_proxy_that_refuses_the_site_is_said_in_plain_words(self):  # dogfood: raw urllib text before
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RefusingProxy)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        proxy = "http://127.0.0.1:%d" % server.server_address[1]
        with mock.patch.dict(os.environ, {"https_proxy": proxy, "HTTPS_PROXY": proxy, "no_proxy": "", "NO_PROXY": ""}):
            code, out, err = run("https://shop.example.com/", os.path.join(folder, "page.html"))
        self.assertEqual((code, RefusingProxy.asked), (2, ["shop.example.com:443"]))
        self.assertIn("a proxy on this network refused that site (HTTP 403 from the proxy, not from the site): "
                      "save the page from your browser instead", err)
        self.assertNotIn("Tunnel connection failed", err)
        self.assertFalse(os.listdir(folder))


class PlainWordsTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def failing_fetch(self, error):
        with mock.patch.object(mod, "fetch", side_effect=error):
            return run("https://shop.example.com/", os.path.join(self.dir, "page.html"))

    def test_dns_and_certificate_errors(self):
        code, out, err = self.failing_fetch(urllib.error.URLError(socket.gaierror(-2, "Name or service not known")))
        self.assertEqual(code, 2)
        self.assertIn("that name was not found", err)
        certificate = ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] self-signed (_ssl.c:1032)")
        code, out, err = self.failing_fetch(urllib.error.URLError(certificate))
        self.assertIn("certificate is not trusted", err)
        self.assertNotIn("_ssl.c", err)

    def test_a_proxy_that_wants_a_login(self):
        tunnel = OSError("Tunnel connection failed: 407 Proxy Authentication Required")
        code, out, err = self.failing_fetch(urllib.error.URLError(tunnel))
        self.assertEqual(code, 2)
        self.assertIn("refused that site (HTTP 407 from the proxy, not from the site)", err)


class ConventionTests(unittest.TestCase):
    def test_docstring_main_and_limits(self):
        with open(mod.__file__) as handle:
            source = handle.read()
        self.assertTrue(source.startswith("#!/usr/bin/env python3\n"))
        self.assertLessEqual(len(source.splitlines()), 300)
        for word in ["Usage", "Exit codes", "forge:allow"]:
            self.assertIn(word, mod.__doc__)
        self.assertIn("timeout=TIMEOUT", source)
        self.assertEqual((mod.USER_AGENT, mod.TIMEOUT, mod.MAX_BYTES), ("forge-pagecheck (passive check)", 15,
                                                                       5 * 1024 * 1024))


if __name__ == "__main__":
    unittest.main()
