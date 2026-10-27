"""Tests for forge-secure/secretscan.py.

Fake secrets are glued together at runtime, so this file never contains a
secret-looking literal: the repo itself is scanned with secretscan.py in CI.
"""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import load  # noqa: E402

mod = load("forge-secure", "secretscan")

STRIPE_LIVE = "sk_" + "live_" + "a1B2c3D4e5F6g7H8i9J0k1L2"
STRIPE_RESTRICTED = "rk_" + "live_" + "Z9y8X7w6V5u4T3s2R1q0P9o8"
STRIPE_TEST = "sk_" + "test_" + "m1N2b3V4c5X6z7L8k9J0h1G2"
AWS_ID = "AKIA" + "Z7QW4RT2YP8MXN3K"
PEM_HEADER = "-----BEGIN RSA " + "PRIVATE KEY-----"
GITHUB_BODY = "A1b2C3d4E5f6G7h8I9j0" * 2
GITHUB_CLASSIC = "ghp_" + GITHUB_BODY
GITHUB_FINE = "github_" + "pat_" + "11ABCDEFG0123456789_abcdefghijklmnop"
SLACK = "xox" + "b-" + "123456789012-" + "AbCdEfGhIjKlMnOp"
GOOGLE = "AIza" + "Sy" + "A1b2C3d4E5" * 3 + "xyz"
PASS_VALUE = "Tr0ub4dor" + "-and-3"
DB_URL = "postgres://admin:" + "Pr0dDbPassw0rd" + "@db.internal:5432/app"
HARD = "Password or secret written in the code"
CONN = "Password inside a connection string"


def write(folder, relative_path, content):
    path = os.path.join(folder, relative_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(content, bytes) else "w") as handle:
        handle.write(content)
    return path


def run(*args):
    """Run main() and return (exit code, stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = mod.main(list(args))
    return code, out.getvalue()


def titles(text):
    return [f["title"] for f in mod.scan_text(text, "x.txt")]


class TempFolder(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)


class RuleTests(unittest.TestCase):
    def test_each_rule_finds_its_secret(self):
        cases = [
            ("$key = '" + STRIPE_LIVE + "';", "Stripe live secret key", "critical"),
            ("KEY=" + STRIPE_RESTRICTED, "Stripe live secret key", "critical"),
            ("aws_access_key_id = " + AWS_ID, "AWS access key id", "critical"),
            (PEM_HEADER, "Private key", "critical"),
            ("-----BEGIN OPENSSH " + "PRIVATE KEY-----", "Private key", "critical"),
            ("-----BEGIN " + "PRIVATE KEY-----", "Private key", "critical"),
            ("git clone https://" + GITHUB_CLASSIC + "@github.com/a/b", "GitHub token", "critical"),
            ("GH=" + GITHUB_FINE, "GitHub token", "critical"),
            ("slack = '" + SLACK + "'", "Slack token", "high"),
            ("<script src='maps.js?key=" + GOOGLE + "'>", "Google API key", "high"),
            ("stripe.api_key = '" + STRIPE_TEST + "'", "Stripe test secret key", "medium"),
            ("url = '" + DB_URL + "'", CONN, "high"),
            ("REDIS_URL=redis://:" + PASS_VALUE + "@cache:6379", CONN, "high"),
            ("$password = '" + PASS_VALUE + "';", HARD, "medium"),
            ("'db_password' => '" + PASS_VALUE + "',", HARD, "medium"),
            ('{"client_secret": "' + PASS_VALUE + '"}', HARD, "medium"),
            ("const apiKey = `x`; const authKey = '" + PASS_VALUE + "'", HARD, "medium"),
            ("ACCESS_TOKEN: str = '" + PASS_VALUE + "'", HARD, "medium"),
            ("aws_secret_access_key = '" + PASS_VALUE + "'", HARD, "medium"),
            ("headers = {'x-api-key': '" + PASS_VALUE + "'}", HARD, "medium"),
            ("define( 'DB_PASSWORD', '" + PASS_VALUE + "' );", HARD, "medium"),
            ('define("SECURE_AUTH_KEY", "' + "Gh7#kP2q" + 'L9wZt5Vm");', HARD, "medium"),
        ]
        for prefix in ["gho_", "ghs_", "ghu_"]:
            cases.append(("t = " + prefix + GITHUB_BODY, "GitHub token", "critical"))
        for letter in "aprs":
            cases.append(("t = xox" + letter + "-" + "123456789012-" + "AbCdEfGhIjKl", "Slack token", "high"))
        for line, title, severity in cases:
            with self.subTest(line=line):
                findings = mod.scan_text(line, "app.php")
                self.assertEqual([(f["title"], f["severity"]) for f in findings], [(title, severity)])

    def test_secret_is_masked(self):
        finding = mod.scan_text("key = " + STRIPE_LIVE, "a.py")[0]
        self.assertEqual(finding["match"], "sk_l****")
        self.assertNotIn(STRIPE_LIVE, json.dumps(finding))

    def test_private_key_shows_its_type(self):
        self.assertEqual(mod.scan_text(PEM_HEADER, "id_rsa")[0]["match"], "RSA ****")

    def test_short_secret_shows_at_most_a_third(self):
        finding = mod.scan_text("mysql://root:" + "Qz7#kw" + "@localhost/db", "a.py")[0]
        self.assertEqual(finding["match"], "Qz****")

    def test_line_number_and_where(self):
        findings = mod.scan_text("first\nsecond\nkey = " + AWS_ID + "\n", "app/config.php")
        self.assertEqual(findings[0]["line"], 3)
        self.assertEqual(findings[0]["where"], "app/config.php:3")

    def test_old_mac_line_endings(self):
        # Regression: CR-only files were one long line, so one forge:allow hid the whole file.
        text = "DEMO = 1  # forge:allow\r\r\rSTRIPE_KEY = '" + STRIPE_LIVE + "'\r"
        self.assertEqual([f["line"] for f in mod.scan_text(text, "a.py")], [4])

    def test_known_key_is_not_reported_twice(self):
        self.assertEqual(titles("api_key = '" + STRIPE_LIVE + "'"), ["Stripe live secret key"])
        self.assertEqual(titles("u = 'https://bot:" + GITHUB_CLASSIC + "@github.com'"), ["GitHub token"])

    def test_two_keys_on_one_line(self):
        self.assertEqual(len(mod.scan_text(AWS_ID + " " + STRIPE_LIVE, "a")), 2)

    def test_key_does_not_hide_a_password_on_the_same_line(self):
        # Regression: a medium test key used to hide a high connection-string password.
        line = '{"stripe_key": "' + STRIPE_TEST + '", "database_url": "' + DB_URL + '"}'
        self.assertEqual(sorted(titles(line)), sorted([CONN, "Stripe test secret key"]))
        line = '{"maps":"' + GOOGLE + '","db_password":"' + PASS_VALUE + '"}'
        self.assertEqual(sorted(titles(line)), sorted(["Google API key", HARD]))

    def test_real_passwords_with_brackets_dollars_or_words_are_found(self):
        # Regression: any '{', '<', '$' or 'your' in a value used to make it a "placeholder".
        for value in ["kT9#x{" + "Lq2!vR8m", "Zp4<Wn8" + "sQ1rT6y", "$ecr3t" + "Passw0rd",
                      "Yourstruly" + "2024!", "Sampler" + "!8842", "Dummy88" + "12Kq"]:
            with self.subTest(value=value):
                self.assertEqual(titles("DB_PASSWORD = '" + value + "'"), [HARD])
        self.assertEqual(titles("postgres://app:" + "Xy{9kL2m" + "@db/app"), [CONN])

    def test_long_minified_lines_stay_fast(self):
        # These took minutes with unbounded regex parts (quadratic backtracking).
        for text in ["token" * 40000, "a." * 100000, "x://a:" * 30000, "secret: " * 25000,
                     "define('" * 20000, "password = '" * 20000]:
            started = time.time()
            mod.scan_text(text, "bundle.min.js")
            self.assertLess(time.time() - started, 5, text[:20])


class FalsePositiveTests(unittest.TestCase):
    def test_placeholders_are_skipped(self):
        lines = [
            "password = 'changeme123'",
            "api_key = 'your-api-key-here'",
            "secret = '${APP_SECRET}'",
            "password = '$DB_PASSWORD'",
            "password = '<password>'",
            "password = '%(password)s'",
            "password: '%env(DB_PASSWORD)%'",
            "password = 'process.env.DB_PASSWORD'",
            "token = 'xxxxxxxxxxxx'",
            "password = '********'",
            "auth_key = 'example-auth-key'",
            "csrf_token = '{{ csrf_token() }}'",
            "csrf_token = '{{csrf_token}}'",
            "'password' => 'required|string|min:8|confirmed',",
            "return ['password' => 'string|min:8|confirmed'];",
            "TOKEN_URL = 'https://oauth2.googleapis.com/token'",
            "password_hint = 'at least 8 characters long'",
            "postgres://user:password@localhost:5432/app",
            "postgres://user:pass@localhost/app",
            "dsn = 'mysql://%s:%s@%s/%s'",
            "url = f'postgresql://{user}:{password}@{host}/db'",
            "DATABASE_URL=postgres://app:${DB_PASS}@db/app",
            "if password == 'abcdefgh123':",
            "password = getenv('DB_PASSWORD')",
            "STRIPE_KEY = os.environ['STRIPE_SECRET_KEY']",
            "publishable = 'pk_" + "live_" + "a1B2c3D4e5F6g7H8i9J0k1L2'",
            "id = 'AKIA" + "IOSFODNN7" + "EXAMPLE'",
            "token = 'xoxb-your-token-here'",
            "http://localhost:3000/login",
            "git@github.com:owner/repo.git",
            "('GitHub token', 'critical')",
            "tokenizer = 'bert-base'",
        ]
        for line in lines:
            with self.subTest(line=line):
                self.assertEqual(titles(line), [])

    def test_fake_keys_are_skipped(self):
        for key in ["sk_" + "live_" + "placeholder123", "sk_" + "live_" + "yourstripekey",
                    "sk_" + "live_" + "YOURSECRETKEYHERE", "ghp_" + "your_github_token_goes_here_1234567"]:
            with self.subTest(key=key):
                self.assertEqual(titles("KEY=" + key), [])

    def test_names_that_only_start_with_a_secret_word(self):
        # Regression: these were all reported as hard-coded secrets.
        lines = [
            'TOKENIZER_NAME = "bert-base-uncased"',
            '"TOKEN_TYPE_CLAIM": "token_type",',
            '"TOKEN_OBTAIN_SERIALIZER": "rest_framework_simplejwt.serializers.TokenObtainPairSerializer",',
            "const TOKEN_STORAGE_KEY = 'access_token';",
            'const tokenEndpoint = "/oauth/token";',
            "password_confirmation = 'confirmed'",
        ]
        for line in lines:
            with self.subTest(line=line):
                self.assertEqual(titles(line), [])

    def test_docker_image_digest_is_not_a_password(self):
        # Regression: name:tag@sha256:... was read as user:password@host (high).
        line = "      - uses: docker://alpine:3.18@sha256:" + "48d9183eb12a05c99bcc0bf44a003607" * 2
        self.assertEqual(titles(line), [])

    def test_forge_allow_skips_the_line(self):
        self.assertEqual(titles("key = '" + STRIPE_LIVE + "'  # forge:allow test fixture"), [])
        self.assertEqual(len(titles("# forge:allow\nkey = '" + STRIPE_LIVE + "'")), 1)


class EnvFileTests(TempFolder):
    def test_real_env_names(self):
        for name in [".env", ".env.local", ".env.production", ".env.testing"]:
            self.assertTrue(mod.is_real_env_file(name), name)
        for name in [".env.example", ".env.sample", ".env.dist", ".env.template",
                     ".env.local.example", ".envrc", "env.py", "x.env"]:
            self.assertFalse(mod.is_real_env_file(name), name)

    def test_env_is_high_and_its_lines_are_scanned(self):
        write(self.dir, ".env", "STRIPE_SECRET=" + STRIPE_LIVE + "\n")
        findings, _ = mod.scan_path(self.dir)
        self.assertEqual([f["severity"] for f in findings], ["critical", "high"])
        self.assertEqual(findings[1]["title"], "Real .env file in the project")

    def test_env_named_in_gitignore_is_still_high_and_scanned(self):
        # Regression: a .gitignore that seemed to name .env (but did not, or the file was already
        # tracked) made the .env low and its live key was never read.
        for pattern in [".env\n", "config/.env\n", "/.env\n", ".env/\n"]:
            with self.subTest(pattern=pattern):
                write(self.dir, ".gitignore", pattern)
                write(self.dir, "api/.env", "STRIPE_SECRET=" + STRIPE_LIVE + "\n")
                findings, _ = mod.scan_path(self.dir)
                self.assertEqual([f["severity"] for f in findings], ["critical", "high"])
                self.assertEqual(run(self.dir)[0], 1)

    def test_env_templates_are_scanned_like_normal_files(self):
        fake = "sk_" + "live_" + "yourstripekeyhere"
        write(self.dir, ".env.example", "STRIPE_SECRET=" + fake + "\nDB_PASSWORD=\n")
        self.assertEqual(mod.scan_path(self.dir)[0], [])
        write(self.dir, ".env.example", "STRIPE_SECRET=" + STRIPE_LIVE + "\n")
        self.assertEqual([f["title"] for f in mod.scan_path(self.dir)[0]], ["Stripe live secret key"])


class WalkTests(TempFolder):
    def test_skipped_folders(self):
        line = "key = '" + STRIPE_LIVE + "'\n"
        for folder in sorted(mod.SKIP_FOLDERS) + ["node_modules/pkg", "storage/framework/views"]:
            write(self.dir, folder + "/leak.js", line)
        write(self.dir, "storage/app/leak.txt", line)  # storage itself is not skipped
        findings, stats = mod.scan_path(self.dir)
        self.assertEqual([f["file"] for f in findings],
                         [os.path.join(self.dir, "storage", "app", "leak.txt")])
        self.assertEqual(stats["files_checked"], 1)

    def test_binary_and_big_files_are_skipped_and_counted_as_skipped(self):
        write(self.dir, "image.png", b"\x89PNG\0\0" + STRIPE_LIVE.encode())
        write(self.dir, "big.sql", "key = " + STRIPE_LIVE + "\n" + "x" * (1024 * 1024))
        findings, stats = mod.scan_path(self.dir)
        self.assertEqual(findings, [])
        self.assertEqual((stats["files_checked"], stats["files_skipped"]), (0, 2))
        self.assertIn("Files checked: 0, skipped: 2 (binary or over 1 MB). No findings.", run(self.dir)[1])

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symlinks")
    def test_symlinks_are_not_followed(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)
        write(outside, "leak.txt", "key = " + STRIPE_LIVE + "\n")
        os.symlink(os.path.join(outside, "leak.txt"), os.path.join(self.dir, "link.txt"))
        os.symlink(outside, os.path.join(self.dir, "linked_folder"))
        self.assertEqual(mod.scan_path(self.dir),
                         ([], {"files_checked": 0, "files_skipped": 0, "unreadable": []}))

    def test_unreadable_folder_makes_the_scan_incomplete(self):
        # Regression: os.walk dropped folders it could not open without a word, and exit was 0.
        write(self.dir, "ok.py", "x = 1\n")
        locked = os.path.dirname(write(self.dir, "locked/keys.py", "key = " + STRIPE_LIVE + "\n"))
        real_scandir = os.scandir

        def fake_scandir(path):
            if path == locked:
                raise PermissionError(13, "Permission denied", path)
            return real_scandir(path)

        with mock.patch("os.scandir", fake_scandir):
            code, out = run(self.dir)
            data = json.loads(run(self.dir, "--json")[1])
        self.assertEqual(code, 2)
        self.assertIn("INCOMPLETE, so not a pass. Could not read: " + locked, out)
        self.assertEqual(data["summary"]["unreadable"], [locked])
        self.assertTrue(data["summary"]["failed"])

    def test_unreadable_file_makes_the_scan_incomplete(self):
        write(self.dir, "ok.py", "x = 1\n")
        locked = write(self.dir, "locked.py", "key = " + STRIPE_LIVE + "\n")
        real_open = open

        def fake_open(path, *args, **kwargs):
            if path == locked:
                raise PermissionError(13, "Permission denied", path)
            return real_open(path, *args, **kwargs)

        with mock.patch("builtins.open", fake_open):
            code, out = run(self.dir)
        self.assertEqual(code, 2)
        self.assertIn("Files checked: 1. No findings.\nINCOMPLETE", out)

    def test_very_deep_folders(self):
        # Regression: os.walk on Python 3.9 recursed and crashed past ~1000 levels.
        made = []

        def remove_bottom_up():  # shutil.rmtree is recursive on Python 3.9 too
            for path in reversed(made):
                if path.endswith(".py"):
                    os.remove(path)
                else:
                    os.rmdir(path)

        self.addCleanup(remove_bottom_up)
        folder = self.dir
        try:
            for _ in range(sys.getrecursionlimit() + 50):
                folder = os.path.join(folder, "a")
                os.mkdir(folder)
                made.append(folder)
            made.append(write(folder, "x.py", "key = " + STRIPE_LIVE + "\n"))
        except OSError:
            self.skipTest("this file system does not allow paths this long")
        findings, stats = mod.scan_path(self.dir)
        self.assertEqual((len(findings), stats["files_checked"]), (1, 1))

    def test_findings_sorted_most_severe_first(self):
        write(self.dir, "a.py", "token = '" + PASS_VALUE + "'\n")
        write(self.dir, "b.py", "key = '" + STRIPE_TEST + "'\nid = " + AWS_ID + "\n")
        write(self.dir, "c.py", "slack = '" + SLACK + "'\n")
        severities = [f["severity"] for f in mod.scan_path(self.dir)[0]]
        self.assertEqual(severities, ["critical", "high", "medium", "medium"])


class CliTests(TempFolder):
    def test_clean_folder(self):
        write(self.dir, "app.py", "print('hello')\n")
        code, out = run(self.dir)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "Files checked: 1. No findings.\nPASS: nothing is high or worse.")

    def test_missing_path_is_exit_2(self):
        code, out = run(os.path.join(self.dir, "nope"))
        self.assertEqual(code, 2)

    def test_bad_fail_on_value_is_exit_2(self):
        with self.assertRaises(SystemExit) as caught, contextlib.redirect_stderr(io.StringIO()):
            mod.main([self.dir, "--fail-on", "urgent"])
        self.assertEqual(caught.exception.code, 2)

    def test_human_output(self):
        path = write(self.dir, "app/config.php", "<?php\n$stripe = '" + STRIPE_LIVE + "';\n")
        code, out = run(path)
        self.assertEqual(code, 1)
        self.assertIn("CRITICAL  Stripe live secret key\n", out)
        self.assertIn("          where: " + path + ":2\n", out)
        self.assertIn("          found: sk_l****\n", out)
        self.assertIn("          why:   ", out)
        self.assertIn("          fix:   ", out)
        self.assertTrue(out.strip().endswith(
            "Files checked: 1. 1 finding: 1 critical.\nFAIL: at least one finding is high or worse."))
        self.assertNotIn(STRIPE_LIVE, out)

    def test_odd_file_name_does_not_crash_the_output(self):
        # Regression: a file name that is not valid UTF-8 crashed the human output.
        try:
            with open(os.path.join(os.fsencode(self.dir), b"caf\xe9.php"), "w") as handle:
                handle.write("<?php $password = '" + PASS_VALUE + "';\n")
        except (OSError, UnicodeError):
            self.skipTest("this file system only allows UTF-8 file names")
        code, out = run(self.dir, "--fail-on", "critical")
        self.assertEqual(code, 0)
        out.encode("utf-8")  # must not raise
        self.assertIn("caf\\udce9.php:1", out)
        json.loads(run(self.dir, "--json")[1])

    def test_json_output(self):
        write(self.dir, "a.py", "key = '" + STRIPE_LIVE + "'\npassword = '" + PASS_VALUE + "'\n")
        code, out = run(self.dir, "--json")
        data = json.loads(out)
        self.assertEqual(code, 1)
        for finding in data["findings"]:
            for key in ["severity", "title", "where", "why", "fix", "file", "line", "match"]:
                self.assertIn(key, finding)
        summary = data["summary"]
        self.assertEqual((summary["total"], summary["critical"], summary["medium"]), (2, 1, 1))
        self.assertEqual((summary["files_checked"], summary["files_skipped"]), (1, 0))
        self.assertEqual(summary["unreadable"], [])
        self.assertTrue(summary["failed"])
        self.assertNotIn(STRIPE_LIVE, out)
        self.assertNotIn(PASS_VALUE, out)

    def test_fail_on(self):
        medium = write(self.dir, "m.py", "password = '" + PASS_VALUE + "'\n")
        self.assertEqual(run(medium)[0], 0)  # default: high
        self.assertIn("PASS: nothing is high or worse.", run(medium)[1])
        self.assertEqual(run(medium, "--fail-on", "medium")[0], 1)
        self.assertEqual(run(medium, "--fail-on", "low")[0], 1)
        critical = write(self.dir, "c.py", "key = '" + STRIPE_LIVE + "'\n")
        self.assertEqual(run(critical, "--fail-on", "critical")[0], 1)
        high = write(self.dir, "h.py", "slack = '" + SLACK + "'\n")
        self.assertEqual(run(high, "--fail-on", "critical")[0], 0)
        self.assertEqual(run(high)[0], 1)


class ConventionTests(unittest.TestCase):
    def test_script_header_and_size(self):
        with open(mod.__file__) as handle:
            source = handle.read()
        self.assertTrue(source.startswith("#!/usr/bin/env python3\n"))
        self.assertLessEqual(len(source.splitlines()), 300)  # the spec's hard limit
        for word in ["Usage", "Exit codes", "forge:allow"]:
            self.assertIn(word, mod.__doc__)

    def test_this_test_file_and_the_script_have_no_secrets(self):
        for path in [__file__, mod.__file__]:
            self.assertEqual(mod.scan_path(path)[0], [], path)


if __name__ == "__main__":
    unittest.main()
