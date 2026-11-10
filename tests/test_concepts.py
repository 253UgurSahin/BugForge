"""Tests for forge-design's concept board: concepts.example.html and concepts.md. The board must open
from a folder with no server and no request to another host, and hold three concepts with every field
the page reads."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT  # noqa: E402

BOARD = os.path.join(ROOT, "forge-design", "concepts.example.html")
REFERENCE = os.path.join(ROOT, "forge-design", "concepts.md")
FIELDS = ("id", "name", "idea", "first", "colors", "display", "text", "src")
LABELS = ("title", "intro", "first", "open", "desktop", "phone", "replay", "light", "dark", "level")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.page = read(BOARD)
        self.board = json.loads(re.search(r'<script type="application/json" id="board">(.*?)</script>',
                                          self.page, re.S).group(1))

    def test_three_concepts_with_every_field_the_page_reads(self):
        self.assertEqual([concept["id"] for concept in self.board["concepts"]], ["a", "b", "c"])
        for concept in self.board["concepts"]:
            with self.subTest(concept=concept["id"]):
                for field in FIELDS:
                    self.assertTrue(concept[field], field)
                self.assertEqual(concept["src"], concept["id"] + "/index.html")
                self.assertTrue(4 <= len(concept["colors"]) <= 6)
                for colour in concept["colors"]:
                    self.assertRegex(colour, r"^#[0-9a-fA-F]{6}$")
        self.assertIn(self.board["level"], (1, 2, 3, 4, 5))
        self.assertTrue(self.board["app"] and self.board["levelName"])

    def test_every_label_is_there_and_used(self):
        for label in LABELS:
            with self.subTest(label=label):
                self.assertTrue(self.board["labels"][label])
                self.assertRegex(self.page, r"label\.%s\b|label\[id\]" % label)

    def test_it_asks_nothing_of_another_host(self):
        """It is opened from forge-work by double click: no CDN, no font host, no tracker."""
        self.assertEqual(re.findall(r"https?://[^\s\"'<>)]+", self.page), [])
        self.assertNotRegex(self.page, r"<link\b|@import\b|<script[^>]*\bsrc=")

    def test_the_text_of_a_concept_is_never_run_as_html(self):
        """The skill fills in the JSON from the app's own words: they are set as text, not as markup."""
        script = self.page.split("<script>")[1]
        for field in ("name", "idea", "first", "display"):
            self.assertNotRegex(script, r"innerHTML[^;]*concept\.%s" % field)
        self.assertIn("textContent", script)

    def test_keys_and_themes_are_documented_and_handled(self):
        for key in ("'escape'", "'d'", "'p'", "'r'"):
            self.assertIn(key, self.page)
        self.assertIn("?theme=", self.page)
        self.assertIn("prefers-color-scheme: dark", self.page)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_the_script_parses(self):
        script = self.page.split("<script>")[1].split("</script>")[0]
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "board.js")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(script)
            done = subprocess.run(["node", "--check", path], timeout=60, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class ReferenceTests(unittest.TestCase):
    def test_the_reference_names_what_the_board_needs(self):
        text = read(REFERENCE)
        for words in ("forge-work/design/concepts/a/index.html", "concepts.example.html", "A, B or C, or a mix",
                      "holds in auto mode", "world.md", "board.png", "brief.md", "No font CDN", "never from a CDN"):
            with self.subTest(words=words):
                self.assertIn(words, text)


if __name__ == "__main__":
    unittest.main()
