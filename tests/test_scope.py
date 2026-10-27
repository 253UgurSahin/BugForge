"""Tests for forge-secure/scope.py.

Most tests call decide() directly with a list of own domains. The scope file
tests write small JSON files in a temporary folder. Nothing here uses DNS or
the network.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

# Lets "python3 -m unittest tests.test_scope" find _load too, not only "discover -s tests".
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _load import load  # noqa: E402

mod = load("forge-secure", "scope")
SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "forge-secure", "scope.py")
OWN = ["example.com", "app.example.org", "xn--bcher-kva.de"]  # as load_scope returns them
PW = "hun" + "ter" + "42"  # a fake password, built at runtime so secretscan.py finds no literal


def allowed(target, own=OWN):
    """True for ALLOWED, False for PASSIVE ONLY."""
    return mod.decide(target, own)["allowed"]


def host_and_verdict(target, own=OWN):
    """(host, allowed) as decide() reads the target."""
    result = mod.decide(target, own)
    return result["host"], result["allowed"]


def reason(target, own=OWN):
    return mod.decide(target, own)["reason"]


def run(*args):
    """Run main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = mod.main(list(args))
        except SystemExit as stop:  # argparse usage errors
            code = stop.code
    return code, out.getvalue(), err.getvalue()


class TempFolderTest(unittest.TestCase):
    """Each test gets an empty temporary folder (self.tmp) and a write() helper."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def write(self, content, name="scope.json"):
        path = os.path.join(self.tmp, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content if isinstance(content, str) else json.dumps(content))
        return path

    def go_to_tmp(self):
        old = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, old)


class AllowedTests(unittest.TestCase):
    def assert_allowed(self, targets):
        for target in targets:
            self.assertTrue(allowed(target), target)

    def test_localhost_and_test_names(self):
        self.assert_allowed(["localhost", "app.localhost", "a.b.localhost", "myapp.test", "http://shop.test:8000/"])

    def test_loopback_ips(self):
        self.assert_allowed(["127.0.0.1", "127.255.10.3", "::1", "[::1]", "[::1]:8080", "http://[::1]:3000/x"])

    def test_private_ranges_and_zero(self):
        self.assert_allowed(["10.0.0.1", "10.255.255.255", "172.16.0.1", "172.31.255.255", "192.168.1.20",
                             "fc00::1", "fd12:3456::1", "0.0.0.0", "http://0.0.0.0:8000"])

    def test_container_and_compose_names(self):
        self.assert_allowed(["db", "web", "my_api", "web-1", "redis:6379", "postgres://db:5432/app", "DB",
                             "app", "a" + "b" * 62])

    def test_own_domain_and_subdomains(self):
        self.assert_allowed(["example.com", "www.example.com", "a.b.example.com", "app.example.org",
                             "https://staging.example.com/login?next=/", "example.com:8443"])

    def test_ipv4_mapped_ipv6_of_a_local_ip(self):
        self.assert_allowed(["::ffff:127.0.0.1", "::ffff:192.168.0.1", "[::ffff:10.0.0.1]:80"])

    def test_reasons_name_the_rule(self):
        self.assertIn("this machine", reason("localhost"))
        self.assertIn("private", reason("10.1.2.3"))
        self.assertIn("docker network", reason("db"))
        self.assertIn("example.com (with its subdomains) is listed", reason("www.example.com"))


class PassiveOnlyTests(unittest.TestCase):
    def assert_passive(self, targets, own=OWN):
        for target in targets:
            self.assertFalse(allowed(target, own), target)

    def test_public_ips_and_domains(self):
        self.assert_passive(["8.8.8.8", "1.1.1.1", "172.32.0.1", "192.169.0.1", "11.0.0.1", "2001:4860:4860::8888",
                             "evil.net", "https://google.com/", "::"])

    def test_cloud_metadata_link_local(self):
        self.assert_passive(["169.254.169.254", "http://169.254.169.254/latest/meta-data/", "fe80::1",
                             "[fe80::1]:80", "febf::1"])
        self.assertIn("metadata", reason("169.254.169.254"))

    def test_carrier_grade_nat(self):
        self.assert_passive(["100.64.0.1", "100.127.255.255"])
        self.assertIn("carrier", reason("100.64.0.1"))

    def test_ipv4_mapped_ipv6_of_a_public_ip(self):
        self.assert_passive(["::ffff:8.8.8.8", "[::ffff:169.254.169.254]", "::ffff:808:808"])

    def test_integer_hex_and_octal_ips(self):
        for target in ["2130706433", "0x7f000001", "017700000001", "0177.0.0.1", "0x7f.0.0.1", "127.1",
                       "127.0.0.01", "0", "http://2130706433/", "0X7F000001", "999.1.1.1"]:
            self.assertFalse(allowed(target), target)
            self.assertIn("unusual way", reason(target), target)

    def test_look_alike_domains(self):
        self.assert_passive(["evilexample.com", "example.com.attacker.net", "example.co", "examp1e.com",
                             "example.org"])
        self.assertIn("only looks like example.com", reason("evilexample.com"))

    def test_userinfo_tricks_use_the_real_host(self):
        for target in ["http://example.com@evil.net", "http://localhost@evil.net/", "https://a@b@evil.net",
                       "localhost@evil.net",
                       # "user:password@" logins, built at runtime so secretscan.py finds no literal in this repo
                       "http://user:" + PW + "@evil.net:80/", "http://127.0.0.1:" + "80@evil.net"]:
            self.assertEqual(host_and_verdict(target), ("evil.net", False), target)
            self.assertIn("login name", reason(target))
        self.assertEqual(host_and_verdict("http://evil.net@localhost:8080/"), ("localhost", True))

    def test_ipv6_zone_id_cannot_hide_the_real_host(self):
        # Python reads "::1%@evil.net" as ::1 with zone "@evil.net"; curl reads login "::1%" and host evil.net.
        for target in ["::1%@evil.net", "fc00::1%x@evil.net", "::ffff:127.0.0.1%@evil.net", "::1%@evil.net:8080",
                       "http://[::1]%@evil.net", "10.0.0.1%@evil.net"]:
            self.assertEqual(host_and_verdict(target), ("evil.net", False), target)

    def test_host_ends_before_path_query_and_fragment(self):
        self.assertEqual(host_and_verdict("http://evil.net#@localhost"), ("evil.net", False))
        self.assertEqual(host_and_verdict("http://evil.net?@localhost"), ("evil.net", False))
        self.assertEqual(host_and_verdict("http://evil.net/@localhost"), ("evil.net", False))
        self.assertEqual(host_and_verdict("localhost:8080/go?to=http://evil.net"), ("localhost", True))

    def test_wildcard_dns_helpers(self):
        for target in ["127.0.0.1.nip.io", "10.0.0.1.sslip.io", "http://app.192.168.1.2.nip.io/"]:
            self.assertFalse(allowed(target), target)
            self.assertIn("wildcard DNS", reason(target))

    def test_localhost_must_be_the_last_part(self):
        self.assert_passive(["localhost.evil.net", "localhost.com", "test.evil.net", "evil.net.test.com"])

    def test_top_level_domains_are_not_container_names(self):
        for target in ["com", "ai", "io", "nl", "COM", "com.", "http://ai/"]:
            self.assertFalse(allowed(target), target)
            self.assertIn("top-level internet domain", reason(target), target)

    def test_single_names_that_do_not_start_with_a_letter(self):
        self.assert_passive(["1db", "_db", "9"])

    def test_no_own_domains_means_every_domain_is_passive(self):
        self.assertFalse(allowed("example.com", []))
        self.assertTrue(allowed("localhost", []))


class NormalisingTests(unittest.TestCase):
    def test_trailing_dot_and_uppercase(self):
        self.assertEqual(host_and_verdict("EXAMPLE.COM."), ("example.com", True))
        self.assertEqual(host_and_verdict("https://WWW.Example.Com./"), ("www.example.com", True))
        self.assertEqual(host_and_verdict("LOCALHOST."), ("localhost", True))
        self.assertEqual(host_and_verdict("evilexample.com."), ("evilexample.com", False))

    def test_international_names_become_punycode(self):
        self.assertEqual(host_and_verdict("bücher.de"), ("xn--bcher-kva.de", True))
        self.assertEqual(host_and_verdict("https://shop.BÜCHER.de/"), ("shop.xn--bcher-kva.de", True))
        self.assertEqual(host_and_verdict("bucher.de"), ("bucher.de", False))
        self.assertEqual(host_and_verdict("exämple.com"), ("xn--exmple-cua.com", False))

    def test_fullwidth_letters_and_dots_are_folded(self):
        self.assertEqual(host_and_verdict("ｌｏｃａｌｈｏｓｔ"), ("localhost", True))
        self.assertEqual(host_and_verdict("example。com"), ("example.com", True))
        self.assertEqual(host_and_verdict("１２７.０.０.１"), ("127.0.0.1", True))

    def test_ipv6_is_shown_in_short_form(self):
        self.assertEqual(mod.decide("[0:0:0:0:0:0:0:1]", OWN)["host"], "::1")


class BadTargetTests(unittest.TestCase):
    def test_unreadable_targets_raise(self):
        for target in ["", "http://", "http:///evil.net", "http:/evil.net", "//evil.net", "local host",
                       "exa\tmple.com", "exam\u200bple.com", "http://evil.net\\@localhost", "a..b", ".example.com",
                       "[127.0.0.1]", "[]", "http://[::1", "[::1", "[::1]x80", "localhost:", "localhost:0",
                       "localhost:99999", "localhost:http", "ex%61mple.com", "-x", "a" * 64 + ".com", "a" * 64,
                       "faß.de", "ΣΊΣΥΦΟς.gr", "http://::1/", "user@::1", "a:b:c"]:
            with self.assertRaises(ValueError, msg=repr(target)):
                mod.decide(target, OWN)

    def test_ipv6_zone_ids_are_refused(self):
        for target in ["fe80::1%eth0", "::1%eth0", "::1%", "[::1%25eth0]", "[fe80::1%eth0]:80",
                       "http://[::1%25lo]:8080/"]:
            with self.assertRaises(ValueError, msg=target) as caught:
                mod.decide(target, OWN)
            self.assertIn("zone id", str(caught.exception))
        self.assertEqual(run("::1%eth0")[0], 2)

    def test_bad_target_exits_2_and_says_why(self):
        code, out, err = run("local host")
        self.assertEqual((code, out), (2, ""))
        self.assertIn('cannot read target "local host"', err)
        self.assertIn("spaces", err)

    def test_error_shows_letters_as_they_are_and_invisible_characters_as_codes(self):
        self.assertIn('"bücher de"', run("bücher de")[2])
        self.assertIn('"exam<U+200B>ple.com"', run("exam\u200bple.com")[2])

    def test_missing_target_is_a_usage_error(self):
        self.assertEqual(run()[0], 2)


class SecretTests(TempFolderTest):
    """A password inside the target never reaches the output."""

    def setUp(self):
        super().setUp()
        self.scope = self.write({"own_domains": ["example.com"]})

    def test_human_and_json_output_hide_the_login(self):
        target = "https://admin:" + PW + "@staging.example.com/"
        code, out, err = run(target, "--scope", self.scope)
        self.assertEqual(code, 0)
        self.assertNotIn(PW, out + err)
        code, out, err = run(target, "--scope", self.scope, "--json")
        self.assertNotIn(PW, out + err)
        self.assertEqual(json.loads(out)["target"], "****@staging.example.com/")

    def test_error_message_hides_the_login(self):
        code, out, err = run("postgres://app:" + PW + "@db host/x")
        self.assertEqual(code, 2)
        self.assertNotIn(PW, err)
        self.assertIn('"****@db host/x"', err)

    def test_password_with_a_slash_is_hidden_too(self):
        code, out, err = run("postgres://app:a/" + PW + "@db/x")
        self.assertEqual(code, 2)
        self.assertNotIn(PW, err)


class ScopeFileTests(TempFolderTest):
    def test_entries_are_normalised(self):
        path = self.write({"own_domains": ["Example.COM.", "bücher.de", "app.example.org"], "note": "extra keys ok"})
        self.assertEqual(mod.load_scope(path), ["example.com", "xn--bcher-kva.de", "app.example.org"])

    def test_empty_list_and_bom_are_fine(self):
        self.assertEqual(mod.load_scope(self.write({"own_domains": []})), [])
        self.assertEqual(mod.load_scope(self.write('\ufeff{"own_domains": ["example.com"]}')), ["example.com"])

    def test_missing_default_file_means_no_own_domains(self):
        self.go_to_tmp()
        code, out, err = run("example.com")
        self.assertEqual(code, 1)
        self.assertIn("not found: no domain is yours", out)
        self.assertEqual(run("localhost")[0], 0)

    def test_missing_named_file_exits_2(self):
        code, out, err = run("localhost", "--scope", os.path.join(self.tmp, "nope.json"))
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)

    def test_invalid_json_and_wrong_shape_exit_2(self):
        for content in ["{not json", "", '["example.com"]', '{"own_domains": "example.com"}', "{}",
                        '{"own_domain": ["example.com"]}', "null"]:
            code, out, err = run("localhost", "--scope", self.write(content))
            self.assertEqual(code, 2, content)
            self.assertIn("error: scope file:", err)

    def test_deeply_nested_json_exits_2(self):
        deep = '{"own_domains": ' + "[" * 100000 + "]" * 100000 + "}"
        code, out, err = run("localhost", "--scope", self.write(deep))
        self.assertEqual(code, 2)
        self.assertIn("not valid JSON", err)
        self.write(deep, os.path.join("forge-work", "scope.json"))
        self.go_to_tmp()
        self.assertEqual(run("127.0.0.1")[0], 2)

    def test_bad_entries_exit_2_and_name_the_entry(self):
        bad = {"*.example.com": "wildcard", "https://example.com": "https://", "example.com/shop": "path",
               "example.com:8443": "port", "localhost": "at least one dot", "1.2.3.4": "not an IP",
               "0x7f.1": "not an IP", "exa mple.com": "not a valid host name", 42: "text string",
               "user@example.com": "only the domain name", "": "not a valid host name"}
        for entry, words in bad.items():
            code, out, err = run("localhost", "--scope", self.write({"own_domains": ["ok.com", entry]}))
            self.assertEqual(code, 2, entry)
            self.assertIn(json.dumps(entry), err)
            self.assertIn(words, err)

    def test_names_many_owners_share_are_refused(self):
        for entry in ["github.io", "herokuapp.com", "vercel.app", "co.uk", "com.au", "nip.io", "GitHub.IO.",
                      "8.8.8.8.nip.io", "app-10-0-0-1.sslip.io"]:
            code, out, err = run("localhost", "--scope", self.write({"own_domains": [entry]}))
            self.assertEqual(code, 2, entry)
            self.assertIn("shared by many owners", err)

    def test_your_own_part_of_a_shared_name_is_fine(self):
        own = mod.load_scope(self.write({"own_domains": ["myapp.github.io"]}))
        self.assertTrue(allowed("myapp.github.io", own))
        self.assertTrue(allowed("x.myapp.github.io", own))
        self.assertFalse(allowed("someone-else.github.io", own))

    def test_default_file_is_read_from_the_current_folder(self):
        self.write({"own_domains": ["mysite.nl"]}, os.path.join("forge-work", "scope.json"))
        self.go_to_tmp()
        self.assertEqual(run("https://www.mysite.nl/")[0], 0)
        self.assertEqual(run("mysite.nl.evil.net")[0], 1)
        self.write("{broken", os.path.join("forge-work", "scope.json"))
        self.assertEqual(run("localhost")[0], 2)


class OutputTests(TempFolderTest):
    def setUp(self):
        super().setUp()
        self.scope = self.write({"own_domains": ["example.com"]})

    def test_output_into_a_closed_pipe_ends_quietly(self):
        # Regression (dogfood): `scope.py ... | head` printed a BrokenPipeError traceback.
        done = subprocess.Popen([sys.executable, SCRIPT, "mysite.nl", "--scope", self.scope],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        done.stdout.close()  # the reader is gone before anything is printed
        error = done.stderr.read().decode()
        done.stderr.close()
        self.assertEqual(done.wait(timeout=60), 1)
        self.assertNotIn("Traceback", error)

    def test_allowed_human_output(self):
        code, out, err = run("http://localhost:8080/", "--scope", self.scope)
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.startswith("ALLOWED: localhost\nreason: localhost always means this machine\n"))
        self.assertIn("(own domains: 1)", out)
        self.assertNotIn("passive", out.lower())
        self.assertNotIn("fix:", out)

    def test_passive_human_output(self):
        code, out, err = run("http://example.com@evil.net", "--scope", self.scope)
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("PASSIVE ONLY: evil.net\nreason: "))
        self.assertIn("login name", out)
        self.assertIn("no scans, fuzzing", out)

    def test_passive_domain_says_how_to_add_it(self):
        code, out, err = run("mysite.nl", "--scope", self.scope)
        self.assertEqual(code, 1)
        self.assertIn("fix: if you own or control mysite.nl and allow active tests on it, add it to the scope file", out)
        self.assertIn('{"own_domains": ["mysite.nl"]}', out)
        for target in ["8.8.8.8", "169.254.169.254", "evilexample.com", "1db", "com", "127.0.0.1.nip.io"]:
            self.assertNotIn("fix:", run(target, "--scope", self.scope)[1], target)

    def test_json_output_shape(self):
        code, out, err = run("WWW.example.com.", "--scope", self.scope, "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["verdict"], "ALLOWED")
        self.assertIs(data["allowed"], True)
        self.assertEqual(data["host"], "www.example.com")
        self.assertEqual(data["target"], "WWW.example.com.")
        self.assertEqual(data["own_domains"], ["example.com"])
        self.assertIs(data["scope_file_found"], True)
        self.assertEqual(data["fix"], "")
        self.assertTrue(data["reason"])
        code, out, err = run("mysite.nl", "--scope", self.scope, "--json")
        data = json.loads(out)
        self.assertEqual((code, data["verdict"], data["allowed"]), (1, "PASSIVE ONLY", False))
        self.assertIn("mysite.nl", data["fix"])

    def test_runs_as_a_script(self):
        result = subprocess.run([sys.executable, SCRIPT, "127.0.0.1", "--scope", self.scope],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ALLOWED", result.stdout)
        result = subprocess.run([sys.executable, SCRIPT, "0x7f000001", "--scope", self.scope],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 1)

    def test_conventions(self):
        with open(SCRIPT, encoding="utf-8") as handle:
            source = handle.read()
        self.assertTrue(source.startswith("#!/usr/bin/env python3\n"))
        self.assertLessEqual(len(source.splitlines()), 300)  # the spec's hard limit
        self.assertLessEqual(max(len(line) for line in source.splitlines()), 100)
        for words in ("Usage", "Exit codes", "own_domains"):
            self.assertIn(words, mod.__doc__)


if __name__ == "__main__":
    unittest.main()
