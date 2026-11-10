"""Tests for forge-design/shots.example.mjs, the capture script the skills copy into a project: it
parses as an ES module, its header explains every flag it reads, and it asks nothing of another host."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT  # noqa: E402

SCRIPT = os.path.join(ROOT, "forge-design", "shots.example.mjs")


def read():
    with open(SCRIPT, encoding="utf-8") as handle:
        return handle.read()


class ShotsTests(unittest.TestCase):
    def test_every_flag_it_reads_is_explained_in_the_header(self):
        text = read()
        header = "\n".join(line for line in text.split("\n") if line.startswith("//"))
        flags = set(re.findall(r"'(--[a-z][a-z-]+)'", text))
        self.assertTrue({"--no-dark", "--state", "--viewport-only", "--wait", "--reduced", "--frames", "--video"} <= flags)
        for flag in flags:
            with self.subTest(flag=flag):
                self.assertIn(flag, header)

    def test_it_names_the_files_changed_py_reads(self):
        header = read().split("import ")[0]
        for words in ("-f1.png", "-reduced.png", ".webm", "changed.py --moves"):
            self.assertIn(words, header)

    def test_only_the_base_site_and_no_other_host(self):
        text = read()
        urls = re.findall(r"https?://[^\s'\"`)]+", text)
        hosts = [url for url in urls if not re.match(r"https?://(localhost|127\.0\.0\.1)\b|https?://\.\.\.", url)]
        self.assertEqual(hosts, [])
        self.assertIn("is not ${site.origin}", text)  # a page that led away is never shot

    def test_it_never_waits_forever(self):
        text = read()
        self.assertRegex(text, r"const LOAD_LIMIT = \d+")
        self.assertRegex(text, r"const QUIET_LIMIT = \d+")

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_it_parses_as_an_es_module(self):
        with tempfile.TemporaryDirectory() as folder:
            copy = os.path.join(folder, "shots.mjs")
            shutil.copy(SCRIPT, copy)
            done = subprocess.run(["node", "--check", copy], timeout=60, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
