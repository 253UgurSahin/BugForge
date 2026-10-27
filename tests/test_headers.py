"""Tests for forge-secure/headers.py.

No real network: checks run on header lists, on saved header files, and on a
small local web server on 127.0.0.1 that runs in a thread.
"""

import ast
import contextlib
import http.server
import io
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `python3 -m unittest tests.test_headers` works
from _load import load  # noqa: E402

mod = load("forge-secure", "headers")

HTTPS_URL = "https://example.com/"

# A response that passes every check.
GOOD = [
    ("strict-transport-security", "max-age=31536000; includeSubDomains"),
    ("content-security-policy", "default-src 'self'; frame-ancestors 'self'"),
    ("x-content-type-options", "nosniff"),
    ("referrer-policy", "strict-origin-when-cross-origin"),
    ("permissions-policy", "camera=(), microphone=()"),
    ("set-cookie", "sid=v1; Path=/; Secure; HttpOnly; SameSite=Lax"),
    ("server", "nginx"),
]
GOOD_TEXT = "HTTP/1.1 200 OK\n" + "".join("%s: %s\n" % pair for pair in GOOD)
NO_HTTPS = ("high", "Page not served over HTTPS")


def replace(name, value=None):
    """GOOD with one header removed, or replaced when a value is given."""
    headers = [(k, v) for k, v in GOOD if k != name]
    return headers + [(name, value)] if value is not None else headers


def found(headers, url=HTTPS_URL, status=None):
    """The findings as (severity, title) pairs."""
    return [(f["severity"], f["title"]) for f in mod.check(headers, url, status)]


def run(*args):
    """Run main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = mod.main(list(args))
    return code, out.getvalue(), err.getvalue()


def usage_error(*args):
    """argparse usage errors exit 2 through SystemExit."""
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            mod.main(list(args))
        except SystemExit as stop:
            return stop.code
    return None


class TransportTests(unittest.TestCase):
    def test_good_https_response_has_no_findings(self):
        self.assertEqual(found(GOOD), [])

    def test_plain_http_page_is_high(self):
        findings = mod.check(GOOD, "http://example.com/")
        self.assertIn(NO_HTTPS, [(f["severity"], f["title"]) for f in findings])
        self.assertEqual(findings[0]["where"], "http://example.com/")

    def test_localhost_may_use_http(self):
        for url in ["http://localhost:8080/", "http://127.0.0.1/", "http://[::1]:3000/"]:
            self.assertEqual(found(GOOD, url), [], url)

    def test_saved_redirect_to_https_is_fine_but_to_http_is_not(self):
        to_https = GOOD + [("location", "HTTPS://example.com/")]
        self.assertEqual(found(to_https, "http://example.com/"), [])
        self.assertEqual(found(to_https, "http://example.com/", 301), [])
        to_http = GOOD + [("location", "http://www.example.com/")]
        self.assertIn(NO_HTTPS, found(to_http, "http://example.com/", 302))

    def test_location_on_a_normal_answer_is_not_a_redirect(self):
        stray = GOOD + [("location", "https://example.com/")]
        self.assertIn(NO_HTTPS, found(stray, "http://example.com/login", 200))
        self.assertIn(NO_HTTPS, found(stray, "http://example.com/login", 201))

    def test_https_page_that_redirects_to_http_is_high(self):
        findings = mod.check(GOOD + [("location", "http://example.com/login")], HTTPS_URL, 302)
        self.assertEqual((findings[0]["severity"], findings[0]["title"]), NO_HTTPS)
        self.assertEqual(findings[0]["where"], "redirect to http://example.com/login")

    def test_a_redirect_gets_only_the_checks_that_matter_for_a_redirect(self):
        redirect = [("location", "https://www.example.com/"), ("server", "nginx/1.25.3"), ("set-cookie", "a=1")]
        self.assertEqual(found(redirect, HTTPS_URL, 301), [
            ("medium", "No Strict-Transport-Security header"),  # browsers do honour HSTS on a redirect
            ("medium", "Cookie without Secure"),
            ("low", "Cookie readable by JavaScript (no HttpOnly)"),
            ("low", "Cookie without SameSite"),
            ("low", "Server software version is visible"),
        ])  # no CSP, framing, nosniff, Referrer- or Permissions-Policy findings: they do nothing on a redirect

    def test_unknown_address_counts_as_https(self):
        self.assertEqual(found(GOOD, None), [])
        self.assertIn(("medium", "No Strict-Transport-Security header"),
                      found(replace("strict-transport-security"), None))


class HeaderRuleTests(unittest.TestCase):
    def test_hsts(self):
        self.assertIn(("medium", "No Strict-Transport-Security header"), found(replace("strict-transport-security")))
        short = found(replace("strict-transport-security", "max-age=3600"))
        self.assertIn(("low", "Short Strict-Transport-Security max-age"), short)
        no_age = found(replace("strict-transport-security", "includeSubDomains"))
        self.assertIn(("low", "Short Strict-Transport-Security max-age"), no_age)
        self.assertEqual(found(replace("strict-transport-security", 'MAX-AGE="15552000"')), [])

    def test_hsts_with_a_huge_max_age_does_not_crash(self):
        self.assertEqual(found(replace("strict-transport-security", "max-age=" + "9" * 5000)), [])
        tiny = "max-age=" + "0" * 5000 + "1"
        self.assertEqual(found(replace("strict-transport-security", tiny)),
                         [("low", "Short Strict-Transport-Security max-age")])

    def test_hsts_is_not_checked_on_plain_http(self):
        titles = [t for s, t in found(replace("strict-transport-security"), "http://localhost/")]
        self.assertNotIn("No Strict-Transport-Security header", titles)

    def test_missing_csp_is_medium(self):
        headers = replace("content-security-policy") + [("x-frame-options", "DENY")]
        self.assertEqual(found(headers), [("medium", "No Content-Security-Policy that limits scripts")])
        self.assertEqual(mod.check(headers, HTTPS_URL)[0]["where"], "Content-Security-Policy (missing)")

    def test_csp_fix_says_to_try_it_as_report_only_first(self):
        self.assertIn("Content-Security-Policy-Report-Only", mod.RULES["no_csp"][3])

    def test_report_only_or_a_csp_without_script_rules_does_not_count(self):
        report_only = replace("content-security-policy") + [
            ("content-security-policy-report-only", "default-src 'self'"), ("x-frame-options", "DENY")]
        self.assertEqual(found(report_only), [("medium", "No Content-Security-Policy that limits scripts")])
        upgrade_only = replace("content-security-policy", "upgrade-insecure-requests") + [("x-frame-options", "DENY")]
        self.assertEqual(found(upgrade_only), [("medium", "No Content-Security-Policy that limits scripts")])

    def test_two_csp_headers_are_read_together(self):
        two = replace("content-security-policy") + [("content-security-policy", "default-src 'self'"),
                                                   ("content-security-policy", "frame-ancestors 'none'")]
        self.assertEqual(found(two), [])

    def test_unsafe_script_sources(self):
        findings = mod.check(replace("content-security-policy",
                                     "default-src 'self' 'unsafe-inline' 'unsafe-eval'; frame-ancestors 'none'"),
                             HTTPS_URL)
        self.assertEqual([(f["severity"], f["title"]) for f in findings],
                         [("low", "Content-Security-Policy allows unsafe scripts")])
        self.assertEqual(findings[0]["where"], "Content-Security-Policy: default-src 'unsafe-inline' 'unsafe-eval'")

    def test_unsafe_inline_next_to_a_nonce_or_hash_is_ignored(self):
        nonce = "script-src 'nonce-r4nd0m' 'unsafe-inline'; frame-ancestors 'self'"
        self.assertEqual(found(replace("content-security-policy", nonce)), [])
        hashed = "script-src 'sha256-abc=' 'unsafe-inline' 'unsafe-eval'; frame-ancestors 'self'"
        where = mod.check(replace("content-security-policy", hashed), HTTPS_URL)[0]["where"]
        self.assertEqual(where, "Content-Security-Policy: script-src 'unsafe-eval'")

    def test_script_src_wins_over_default_src(self):
        safe_scripts = "default-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'self'"
        self.assertEqual(found(replace("content-security-policy", safe_scripts)), [])
        unsafe_scripts = "default-src 'self'; script-src 'self' 'unsafe-inline'; frame-ancestors 'self'"
        where = mod.check(replace("content-security-policy", unsafe_scripts), HTTPS_URL)[0]["where"]
        self.assertEqual(where, "Content-Security-Policy: script-src 'unsafe-inline'")

    def test_clickjacking(self):
        no_frame_rule = replace("content-security-policy", "default-src 'self'")
        self.assertEqual(found(no_frame_rule), [("medium", "No clickjacking protection")])
        for value in ["SAMEORIGIN", "deny", "SAMEORIGIN, SAMEORIGIN"]:
            self.assertEqual(found(no_frame_rule + [("x-frame-options", value)]), [], value)

    def test_x_frame_options_values_browsers_ignore_do_not_protect(self):
        no_frame_rule = replace("content-security-policy", "default-src 'self'")
        for value in ["ALLOW-FROM https://partner.example", "ALLOWALL", ""]:
            findings = mod.check(no_frame_rule + [("x-frame-options", value)], HTTPS_URL)
            self.assertEqual([f["title"] for f in findings], ["No clickjacking protection"], value)
        where = mod.check(no_frame_rule + [("x-frame-options", "ALLOWALL")], HTTPS_URL)[0]["where"]
        self.assertEqual(where, "X-Frame-Options: ALLOWALL, no CSP frame-ancestors")

    def test_nosniff(self):
        self.assertEqual(found(replace("x-content-type-options")), [("low", "X-Content-Type-Options is not nosniff")])
        self.assertEqual(found(replace("x-content-type-options", "sniff")),
                         [("low", "X-Content-Type-Options is not nosniff")])
        self.assertEqual(found(replace("x-content-type-options", " NoSniff ")), [])
        wheres = [f["where"] for f in mod.check(replace("x-content-type-options", "sniff"), HTTPS_URL)]
        self.assertEqual(wheres, ["X-Content-Type-Options: sniff"])

    def test_nosniff_sent_twice_is_fine(self):
        self.assertEqual(found(GOOD + [("x-content-type-options", "nosniff")]), [])
        self.assertEqual(found(replace("x-content-type-options", "nosniff, nosniff")), [])

    def test_referrer_and_permissions_policy(self):
        self.assertEqual(found(replace("referrer-policy")), [("low", "No Referrer-Policy header")])
        self.assertEqual(found(replace("permissions-policy")), [("low", "No Permissions-Policy header")])

    def test_version_numbers(self):
        self.assertEqual(found(replace("server", "nginx/1.25.3")), [("low", "Server software version is visible")])
        powered = mod.check(GOOD + [("x-powered-by", "PHP/8.2.1")], HTTPS_URL)
        self.assertEqual(powered[0]["where"], "X-Powered-By: PHP/8.2.1")
        for quiet in ["nginx", "cloudflare", "Apache", "ECS (dcb/7F84)"]:
            self.assertEqual(found(replace("server", quiet)), [], quiet)

    def test_findings_are_sorted_most_severe_first(self):
        findings = mod.check([("server", "Apache/2.4.1")], "http://example.com/")
        order = [mod.SEVERITIES.index(f["severity"]) for f in findings]
        self.assertEqual(order, sorted(order))
        self.assertEqual(findings[0]["severity"], "high")


class CookieTests(unittest.TestCase):
    def cookie(self, value, url=HTTPS_URL):
        return found(replace("set-cookie", value), url)

    def test_every_missing_flag(self):
        self.assertEqual(self.cookie("theme=dark"), [
            ("medium", "Cookie without Secure"),
            ("low", "Cookie readable by JavaScript (no HttpOnly)"),
            ("low", "Cookie without SameSite"),
        ])

    def test_secure_is_only_asked_for_on_https(self):
        titles = [t for s, t in self.cookie("theme=dark", "http://localhost/")]
        self.assertNotIn("Cookie without Secure", titles)

    def test_flags_are_case_insensitive(self):
        self.assertEqual(self.cookie("theme=dark; SECURE; HTTPONLY; SAMESITE=Strict"), [])

    def test_session_cookies_without_httponly_are_medium(self):
        for name in ["laravel_session", "PHPSESSID", "sessionid", "connect.sid", "sid", "auth", "access_token"]:
            self.assertIn(("medium", "Cookie readable by JavaScript (no HttpOnly)"),
                          self.cookie(name + "=v1; Secure; SameSite=Lax"), name)

    def test_other_cookies_without_httponly_are_low(self):
        for name in ["theme", "sidebar_state", "consider", "lang"]:
            self.assertEqual(self.cookie(name + "=v1; Secure; SameSite=Lax"),
                             [("low", "Cookie readable by JavaScript (no HttpOnly)")], name)

    def test_csrf_cookies_may_be_read_by_javascript(self):
        for name in ["csrftoken", "XSRF-TOKEN"]:
            self.assertEqual(self.cookie(name + "=v1; Secure; SameSite=Lax"), [], name)

    def test_each_cookie_is_checked_and_only_its_name_is_shown(self):
        headers = GOOD + [("set-cookie", "a=1; Secure; HttpOnly"), ("set-cookie", "b=2; Secure; HttpOnly")]
        wheres = [f["where"] for f in mod.check(headers, HTTPS_URL)]
        self.assertEqual(wheres, ["Set-Cookie: a", "Set-Cookie: b"])

    def test_a_cookie_without_equals_sign_is_all_value_and_never_shown(self):
        value = "abcdef" + "SECRETVALUE" + "1234567890"
        findings = mod.check(replace("set-cookie", value), HTTPS_URL)
        self.assertEqual(len(findings), 3)
        self.assertEqual({f["where"] for f in findings}, {"Set-Cookie: (no name)"})


class ParseTests(unittest.TestCase):
    def test_status_line_is_optional_and_names_are_lowercased(self):
        text = "Content-Security-Policy: default-src 'self'\nX-Frame-Options:DENY\n"
        expected = [("content-security-policy", "default-src 'self'"), ("x-frame-options", "DENY")]
        self.assertEqual(mod.parse_raw_headers(text), [(None, expected)])
        crlf = "HTTP/1.1 200 OK\r\n" + text.replace("\n", "\r\n")
        self.assertEqual(mod.parse_raw_headers(crlf), [(200, expected)])

    def test_repeated_set_cookie_is_kept(self):
        answers = mod.parse_raw_headers("Set-Cookie: a=1\nset-cookie: b=2\n")
        self.assertEqual(answers, [(None, [("set-cookie", "a=1"), ("set-cookie", "b=2")])])

    def test_a_saved_redirect_chain_is_kept_in_order(self):
        text = ("HTTP/1.1 301 Moved\nLocation: https://example.com/\n\n"
                "HTTP/2 200\nserver: nginx\n\n<p>color: red</p>\nSet-Cookie: fake=1\n")
        self.assertEqual(mod.parse_raw_headers(text),
                         [(301, [("location", "https://example.com/")]), (200, [("server", "nginx")])])

    def test_interim_answers_are_skipped(self):
        text = "HTTP/1.1 103 Early Hints\nLink: </a.css>; rel=preload\n\nHTTP/1.1 200 OK\nServer: x\n"
        self.assertEqual(mod.parse_raw_headers(text)[-1], (200, [("server", "x")]))

    def test_body_text_that_looks_like_headers_is_never_read(self):
        body = ("Welcome to our API docs. Example response:\nHTTP/1.1 200 OK\n"
                "Strict-Transport-Security: max-age=31536000\nContent-Security-Policy: default-src 'self'\n")
        text = "HTTP/1.1 200 OK\nServer: nginx/1.18.0\nSet-Cookie: PHPSESSID=abc\n\n" + body
        self.assertEqual(mod.parse_raw_headers(text),
                         [(200, [("server", "nginx/1.18.0"), ("set-cookie", "PHPSESSID=abc")])])
        starts_like_headers = "HTTP/1.1 200 OK\nServer: a\n\nHTTP/1.1 200 OK\nServer: fake\n"
        self.assertEqual(mod.parse_raw_headers(starts_like_headers), [(200, [("server", "a")])])

    def test_http2_pseudo_headers_and_noise_are_skipped(self):
        self.assertEqual(mod.parse_raw_headers("\n:status: 200\nnot a header\nserver: x\n"), [(None, [("server", "x")])])

    def test_header_names_are_case_insensitive_end_to_end(self):
        text = GOOD_TEXT.upper().replace("MAX-AGE", "max-age")
        status, headers = mod.parse_raw_headers(text)[-1]
        self.assertEqual(mod.check(headers, HTTPS_URL, status), [])


class UrlTests(unittest.TestCase):
    def test_http_and_https_are_accepted(self):
        for url in ["http://example.com", "https://example.com:8443/a?b=c", "HTTP://EXAMPLE.COM/",
                    "http://[::1]:8080/"]:
            self.assertIsNone(mod.url_problem(url), url)

    def test_everything_else_is_refused(self):
        for url in ["ftp://example.com/", "file:///etc/passwd", "data:text/html,hi", "javascript:alert(1)",
                    "example.com", "https://", "http://[::1", "gopher://example.com/", "http://example.com:99999/",
                    "https://user:pa/ss@example.com/"]:
            self.assertIsNotNone(mod.url_problem(url), url)

    def test_credentials_in_url_are_refused(self):
        with_password = "https://admin:" + "hunter2" + "@example.com/"  # glued so secretscan stays quiet
        self.assertIn("credentials", mod.url_problem(with_password))

    def test_printed_urls_hide_passwords_session_ids_and_queries(self):
        self.assertEqual(mod.safe_url("https://a:" + "b@example.com/x"), "https://****@example.com/x")
        self.assertEqual(mod.safe_url("https://example.com/p;jsessionid=" + "ABC?x=1"), "https://example.com/p;****")
        self.assertEqual(mod.safe_url("https://example.com/?token=" + "abc#frag"), "https://example.com/?****")
        self.assertEqual(mod.safe_url("http://example.com/"), "http://example.com/")
        self.assertIsNone(mod.safe_url(None))


class ErrorTextTests(unittest.TestCase):
    def test_network_errors_are_explained_in_plain_words(self):
        bad_cert = ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
        self.assertIn("certificate is not trusted", mod.explain(urllib.error.URLError(bad_cert)))
        no_name = socket.gaierror(-2, "Name or service not known")
        self.assertIn("name was not found", mod.explain(urllib.error.URLError(no_name)))
        refused = ConnectionRefusedError(111, "Connection refused")
        self.assertIn("connection refused", mod.explain(urllib.error.URLError(refused)))
        self.assertIn("no complete answer", mod.explain(socket.timeout("timed out")))
        self.assertEqual(mod.explain(FileNotFoundError(2, "No such file or directory")), "No such file or directory")


class TempFolder(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, text, name="headers.txt"):
        return self.write_bytes(text.encode("utf-8"), name)

    def write_bytes(self, data, name="headers.txt"):
        path = os.path.join(self.dir, name)
        with open(path, "wb") as handle:
            handle.write(data)
        return path


class CliTests(TempFolder):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(mod, "fetch", side_effect=AssertionError("no network in --file mode"))
        self.fetch = patcher.start()
        self.addCleanup(patcher.stop)

    def test_output_into_a_closed_pipe_ends_quietly(self):
        # Regression (dogfood): the scripts printed a BrokenPipeError traceback into `| head`.
        path = self.write("HTTP/1.1 200 OK\n" + "Set-Cookie: a=b\n" * 2000)
        done = subprocess.Popen([sys.executable, mod.__file__, "--file", path, "--url", HTTPS_URL],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        done.stdout.close()  # the reader is gone before anything is printed
        error = done.stderr.read().decode()
        done.stderr.close()
        self.assertEqual(done.wait(timeout=60), 0)  # nothing high: missing headers and cookie flags
        self.assertNotIn("Traceback", error)

    def test_clean_file(self):
        code, out, err = run("--file", self.write(GOOD_TEXT), "--url", HTTPS_URL)
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("Checked saved headers from "))
        self.assertIn("(https://example.com/)", out)
        self.assertTrue(out.strip().endswith("No findings."))

    def test_human_output(self):
        secret_value = "s3ss10n" + "v4lue"
        path = self.write(GOOD_TEXT + "Set-Cookie: PHPSESSID=" + secret_value + "; path=/; Secure; SameSite=Lax\n")
        code, out, err = run("--file", path, "--url", HTTPS_URL)
        self.assertEqual(code, 0)  # medium is below the default gate (high)
        self.assertIn("MEDIUM    Cookie readable by JavaScript (no HttpOnly)\n", out)
        self.assertIn("          where: Set-Cookie: PHPSESSID\n", out)
        self.assertIn("          why:   ", out)
        self.assertIn("          fix:   ", out)
        self.assertTrue(out.strip().endswith("1 finding: 1 medium."))
        self.assertNotIn(secret_value, out)

    def test_json_output(self):
        path = self.write("Server: Apache/2.4.1\n")
        code, out, err = run("--file", path, "--url", "http://example.com/", "--json")
        data = json.loads(out)
        self.assertEqual(code, 1)
        for finding in data["findings"]:
            self.assertEqual(sorted(finding), ["fix", "severity", "title", "where", "why"])
        summary = data["summary"]
        self.assertEqual(summary["high"], 1)
        self.assertEqual(summary["total"], len(data["findings"]))
        self.assertEqual(summary["url"], "http://example.com/")
        self.assertIsNone(summary["redirect_to"])
        self.assertTrue(summary["failed"])
        self.assertEqual(summary["fail_on"], "high")

    def test_without_url_https_is_assumed(self):
        code, out, err = run("--file", self.write(GOOD_TEXT.replace("strict-transport-security", "x-old")))
        self.assertIn("(https assumed)", out)
        self.assertIn("No Strict-Transport-Security header", out)

    def test_curl_L_chain_is_followed_on_paper(self):
        last = [pair for pair in GOOD if pair[0] not in ("strict-transport-security", "set-cookie")]
        text = ("HTTP/1.1 301 Moved Permanently\nLocation: https://shop.example.com/\n\nHTTP/2 200\n"
                + "".join("%s: %s\n" % pair for pair in last) + "set-cookie: sid=abc; HttpOnly; SameSite=Lax\n")
        code, out, err = run("--file", self.write(text), "--url", "http://shop.example.com/", "--fail-on", "low")
        self.assertIn("(https://shop.example.com/)", out)
        self.assertNotIn("Page not served over HTTPS", out)
        self.assertIn("No Strict-Transport-Security header", out)
        self.assertIn("Cookie without Secure", out)
        self.assertEqual(code, 1)

    def test_saved_redirect_alone_says_the_page_was_not_checked(self):
        path = self.write("HTTP/1.1 301 Moved Permanently\nServer: nginx\nLocation: https://example.com/\n")
        code, out, err = run("--file", path, "--url", "http://example.com/", "--fail-on", "low")
        self.assertIn("It is a redirect to https://example.com/: that page was not checked", out)
        self.assertTrue(out.strip().endswith("No findings."))
        self.assertEqual(code, 0)
        code, out, err = run("--file", path, "--url", "http://example.com/", "--json")
        self.assertEqual(json.loads(out)["summary"]["redirect_to"], "https://example.com/")

    def test_stray_location_on_a_200_does_not_hide_plain_http(self):
        path = self.write("HTTP/1.1 200 OK\r\nLocation: https://example.com/\r\nContent-Type: text/html\r\n\r\n")
        code, out, err = run("--file", path, "--url", "http://shop.example.com/login")
        self.assertIn("HIGH      Page not served over HTTPS", out)
        self.assertEqual(code, 1)

    def test_page_body_cannot_hide_findings(self):
        body = "Example response:\nHTTP/1.1 200 OK\n" + "".join("%s: %s\n" % pair for pair in GOOD)
        path = self.write("HTTP/1.1 200 OK\nServer: nginx/1.18.0\nSet-Cookie: PHPSESSID=abc\n\n" + body)
        code, out, err = run("--file", path, "--fail-on", "low")
        self.assertIn("No Strict-Transport-Security header", out)
        self.assertEqual(code, 1)

    def test_huge_hsts_max_age_does_not_crash(self):
        path = self.write("HTTP/1.1 200 OK\nStrict-Transport-Security: max-age=" + "9" * 5000 + "\n")
        code, out, err = run("--file", path)
        self.assertEqual(code, 0)
        self.assertNotIn("Strict-Transport-Security max-age", out)
        self.assertNotIn("No Strict-Transport-Security", out)

    def test_utf16_and_bom_files_are_read(self):
        for data in [GOOD_TEXT.encode("utf-16"), b"\xef\xbb\xbf" + GOOD_TEXT[16:].encode()]:
            code, out, err = run("--file", self.write_bytes(data), "--fail-on", "low")
            self.assertTrue(out.strip().endswith("No findings."), out)
            self.assertEqual(code, 0)

    def test_fail_on(self):
        medium = self.write("\n".join("%s: %s" % pair for pair in replace("content-security-policy")) + "\n")
        self.assertEqual(run("--file", medium)[0], 0)  # default gate: high
        self.assertEqual(run("--file", medium, "--fail-on", "medium")[0], 1)
        self.assertEqual(run("--file", medium, "--fail-on", "low")[0], 1)
        high = self.write(GOOD_TEXT, "high.txt")
        self.assertEqual(run("--file", high, "--url", "http://example.com/")[0], 1)
        self.assertEqual(run("--file", high, "--url", "http://example.com/", "--fail-on", "critical")[0], 0)

    def test_server_text_cannot_mess_up_the_terminal(self):
        path = self.write(GOOD_TEXT + "X-Powered-By: PHP/8.1 \x1b[2J\x07" + "A" * 300 + "\n")
        code, out, err = run("--file", path)
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\x07", out)
        self.assertNotIn("A" * 100, out)

    def test_secrets_in_the_address_are_never_printed(self):
        login = "Hunter2" + "-Prod-Passw0rd"  # glued so secretscan stays quiet
        code, out, err = run("https://admin:" + login + "@shop.example.com/")
        self.assertEqual(code, 2)
        self.assertIn("credentials", err)
        token = "ghp_" + "SecretTokenValue123"
        code, out, err = run("--file", self.write(GOOD_TEXT), "--url", "https://deploy:" + token + "@example.com/")
        self.assertEqual(code, 2)
        session = "S3SS" + "ION1D"
        code, out, err = run("--file", self.write(GOOD_TEXT), "--url", "http://shop.example.com/a;jsessionid="
                             + session + "?token=" + session, "--json")
        self.assertEqual(json.loads(out)["summary"]["url"], "http://shop.example.com/a;****")
        code, human, err = run("--file", self.write(GOOD_TEXT), "--url", "http://shop.example.com/?t=" + session)
        for text in [out + err, human]:
            self.assertNotIn(login, text)
            self.assertNotIn(token, text)
            self.assertNotIn(session, text)

    def test_usage_errors_exit_2(self):
        path = self.write(GOOD_TEXT)
        self.assertEqual(usage_error(), 2)
        self.assertEqual(usage_error(HTTPS_URL, "--file", path), 2)
        self.assertEqual(usage_error(HTTPS_URL, "--url", HTTPS_URL), 2)
        self.assertEqual(usage_error("--url", HTTPS_URL), 2)
        self.assertEqual(usage_error("--file", path, "--fail-on", "urgent"), 2)

    def test_bad_urls_exit_2_without_any_request(self):
        for url in ["ftp://example.com/", "file:///etc/passwd", "data:,hi", "example.com",
                    "http://u:" + "p@example.com/"]:
            code, out, err = run(url)
            self.assertEqual(code, 2, url)
            self.assertIn("error:", err)
        self.assertEqual(run("--file", self.write(GOOD_TEXT), "--url", "ftp://example.com/")[0], 2)
        self.fetch.assert_not_called()

    def test_unreadable_or_empty_file_exits_2(self):
        code, out, err = run("--file", os.path.join(self.dir, "nope.txt"))
        self.assertEqual(code, 2)
        self.assertIn("No such file or directory", err)
        self.assertEqual(run("--file", self.dir)[0], 2)
        code, out, err = run("--file", self.write("<html>no headers here</html>\n"))
        self.assertEqual(code, 2)
        self.assertIn("no 'Name: value' header lines", err)


BIG_BODY = 64 * 1024 * 1024  # bytes: far more than socket buffers hold


class LocalServer(http.server.BaseHTTPRequestHandler):
    """Answers like a small site. Remembers every request it gets."""

    requests = []
    body_sent = None
    done = threading.Event()
    routes = {
        "/": (200, GOOD[:5] + [("Set-Cookie", "laravel_session=v1; path=/")]),
        "/old": (301, [("Location", "/")]),
        "/loop": (302, [("Location", "/loop")]),
        "/moved-308": (308, [("Location", "/")]),
        "/to-metadata": (302, [("Location", "http://169.254.169.254/latest/meta-data/")]),
        "/to-file": (302, [("Location", "file:///etc/passwd")]),
        "/to-ftp": (302, [("Location", "ftp://127.0.0.1/file")]),
        "/missing": (404, GOOD[:5]),
    }

    def do_GET(self):
        LocalServer.requests.append((self.command, self.path, self.headers.get("User-Agent")))
        if self.path == "/trickle":
            return self.trickle()
        if self.path == "/big-redirect":
            return self.big_redirect()
        status, headers = self.routes.get(self.path.split("?")[0], (500, []))
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(b"<html>body that is never read</html>")

    def trickle(self):
        """The status line, then one header line every 0.2 seconds for 4 seconds."""
        try:
            self.wfile.write(b"HTTP/1.1 200 OK\r\n")
            for number in range(20):
                time.sleep(0.2)
                self.wfile.write(b"X-Slow-%d: a\r\n" % number)
        except OSError:
            pass

    def big_redirect(self):
        """A redirect with a huge body: a client that reads it would fill its memory."""
        self.send_response(302)
        self.send_header("Location", "/")
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


class LiveTests(unittest.TestCase):
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
        patcher = mock.patch.dict(os.environ, {"no_proxy": "*", "NO_PROXY": "*"})  # never via a proxy
        patcher.start()
        self.addCleanup(patcher.stop)

    def paths(self):
        return [path for _, path, _ in LocalServer.requests]

    def test_one_passive_get(self):
        code, out, err = run(self.base + "/")
        self.assertEqual(LocalServer.requests, [("GET", "/", "forge-headers (passive check)")])
        self.assertTrue(out.startswith("Checked %s/ (HTTP 200) with one passive GET." % self.base))
        self.assertIn("MEDIUM    Cookie readable by JavaScript (no HttpOnly)", out)
        self.assertNotIn("Page not served over HTTPS", out)  # 127.0.0.1 may use http
        self.assertEqual(code, 0)

    def test_redirects_are_not_followed(self):
        code, out, err = run(self.base + "/old", "--json")
        self.assertEqual(self.paths(), ["/old"])
        summary = json.loads(out)["summary"]
        self.assertEqual((summary["url"], summary["status"], summary["redirect_to"]),
                         (self.base + "/old", 301, self.base + "/"))
        code, out, err = run(self.base + "/old")
        self.assertIn("It is a redirect to %s/: that page was not checked, check it next." % self.base, out)

    def test_loops_308_and_internal_targets_get_exactly_one_get(self):
        for path in ["/loop", "/moved-308", "/to-metadata", "/big-redirect"]:
            LocalServer.requests = []
            started = time.time()
            code, out, err = run(self.base + path, "--json")
            self.assertEqual(self.paths(), [path], path)
            self.assertLess(time.time() - started, 5, path)
            self.assertIn(json.loads(out)["summary"]["status"], (302, 308), path)

    def test_a_redirect_body_is_never_downloaded(self):
        LocalServer.done.clear()
        run(self.base + "/big-redirect")
        self.assertTrue(LocalServer.done.wait(10))
        self.assertLess(LocalServer.body_sent, BIG_BODY)

    def test_redirect_to_a_file_address_is_reported_not_checked(self):
        code, out, err = run(self.base + "/to-file", "--json")
        summary = json.loads(out)["summary"]
        self.assertEqual((summary["url"], summary["redirect_to"]), (self.base + "/to-file", "file:///etc/passwd"))
        self.assertTrue(run(self.base + "/to-file")[1].startswith("Checked %s/to-file (HTTP 302)" % self.base))

    def test_error_pages_are_checked_too(self):
        code, out, err = run(self.base + "/missing", "--json")
        self.assertEqual(json.loads(out)["summary"]["status"], 404)
        self.assertEqual(code, 0)

    def test_redirect_to_ftp_is_not_followed(self):
        code, out, err = run(self.base + "/to-ftp", "--json")
        self.assertEqual(len(LocalServer.requests), 1)
        self.assertEqual(json.loads(out)["summary"]["status"], 302)

    def test_query_strings_are_not_printed(self):
        token = "t0k3n" + "VALUE"
        code, out, err = run(self.base + "/?token=" + token)
        self.assertEqual(self.paths(), ["/?token=" + token])
        self.assertNotIn(token, out + err)

    def test_one_deadline_covers_a_slowly_trickled_answer(self):
        with mock.patch.object(mod, "TIMEOUT", 1):
            started = time.time()
            code, out, err = run(self.base + "/trickle")
        self.assertLess(time.time() - started, 3)
        self.assertEqual(code, 2)
        self.assertIn("no complete answer", err)

    def test_unreachable_site_exits_2(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            closed_port = probe.getsockname()[1]
        code, out, err = run("http://127.0.0.1:%d/" % closed_port)
        self.assertEqual(code, 2)
        self.assertIn("could not get headers", err)
        self.assertIn("connection refused", err)


class ConventionTests(unittest.TestCase):
    def setUp(self):
        with open(mod.__file__) as handle:
            self.source = handle.read()

    def test_script_header_and_size(self):
        self.assertTrue(self.source.startswith("#!/usr/bin/env python3\n"))
        self.assertLessEqual(len(self.source.splitlines()), 300)  # the spec's hard limit
        for word in ["Usage", "Exit codes", "forge:allow"]:
            self.assertIn(word, mod.__doc__)
        self.assertEqual(mod.USER_AGENT, "forge-headers (passive check)")
        self.assertEqual(mod.TIMEOUT, 15)

    def test_main_and_footer(self):
        self.assertIn("\ndef main(argv=None):\n", self.source)
        self.assertTrue(self.source.endswith('\nif __name__ == "__main__":\n    sys.exit(main())\n'))

    def test_nothing_risky_and_standard_library_only(self):
        self.assertIsNone(re.search(r"shell\s*=\s*True|\beval\(|\bexec\(|pickle|os\.system", self.source))
        imported = set()
        for node in ast.walk(ast.parse(self.source)):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module.split(".")[0])
        stdlib = getattr(sys, "stdlib_module_names",
                         {"argparse", "http", "json", "os", "re", "socket", "ssl", "sys", "threading", "urllib"})
        self.assertLessEqual(imported, set(stdlib))

    def test_the_get_uses_the_timeout(self):
        self.assertIn("timeout=TIMEOUT", self.source)
        self.assertIn("join(TIMEOUT)", self.source)


if __name__ == "__main__":
    unittest.main()
