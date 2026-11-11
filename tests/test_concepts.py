"""Tests for forge-design's concept board: concepts.example.html and concepts.md. The board opens from
a folder by double click at levels 1 to 3 and through a server on 127.0.0.1 from level 4, never asks
another host for anything, and holds three concepts with every field the page reads."""

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
                self.assertIn(concept["theme"], ("light", "dark"))  # a dark-first concept opens dark
        self.assertIn(self.board["level"], (1, 2, 3, 4, 5))
        self.assertTrue(self.board["app"] and self.board["levelName"] and self.board["lang"])

    def test_the_board_shows_the_previews_as_the_shots_do(self):
        """1440 wide as the shots and the review, every preview loaded (a lazy frame below the fold stays
        empty in a narrow picture), the labels' language, and a theme switch that keeps the scenes running."""
        self.assertIn("desktop: [1440, 900]", self.page)
        self.assertNotIn('loading="lazy"', self.page)
        self.assertIn("document.documentElement.lang = board.lang", self.page)
        self.assertIn("root.setAttribute('data-theme'", self.page)
        self.assertRegex(self.page, r"label\.note\b")
        # a small preview lets no pointer through, so the board says how to see a scene follow it
        self.assertIn("open it large and move your pointer", self.board["labels"]["intro"])

    def test_every_label_is_there_and_used(self):
        for label in LABELS:
            with self.subTest(label=label):
                self.assertTrue(self.board["labels"][label])
                self.assertRegex(self.page, r"label\.%s\b|label\[id\]" % label)

    def test_it_asks_nothing_of_another_host(self):
        """It is opened from forge-work by double click (levels 1 to 3) or served on 127.0.0.1: no CDN, no
        font host, no tracker."""
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
                      "holds in auto mode", "world.md", "board.png", "brief.md", "No font CDN", "never from a CDN",
                      "--bind 127.0.0.1 0", "concepts-server.pid", "kill", "never the file path",
                      "--scene-frames /a/ /b/ /c/", "a-1440-s*.png", "a-390-f[1-4].png", "1440px", "a/scene.js"):
            with self.subTest(words=words):
                self.assertIn(words, text)
        self.assertNotIn("1280", text)  # one desktop width: the shots' and the review's

    def test_the_kit_copy_has_every_file_a_level_loads(self):
        """design.md points here for the board's server: a file missing from kit/ is a 404 and a blank 3D."""
        flat = " ".join(read(REFERENCE).split())
        server = flat[flat.index("**The server.**"):flat.index("```bash")]
        for name in ("depth.js", "depth.css", "stage.js", "glsl.js", "lazy.js", "journey.js"):
            with self.subTest(name=name):
                self.assertIn("`%s`" % name, server)

    def test_each_level_imports_and_proves_only_what_it_loads(self):
        """lazy.js is copied from level 4 only, and level 1 asks for no motion, so no --moves there."""
        flat = " ".join(read(REFERENCE).split())
        self.assertIn('From level 4 give each preview the import map', flat)
        self.assertIn('at level 3 `import ... from "../kit/depth.js"` and a link to `../kit/depth.css`', flat)
        self.assertIn("level 1, which asks for no motion: neither", flat)
        self.assertIn("level 1: no `--moves`", flat)
        self.assertNotIn("levels 1 to 3: `--frames`", flat)

    def test_a_preview_scene_can_be_waited_for(self):
        """The kit marks a scene only once it is live: an empty poster child is what shots.mjs waits on."""
        text = read(REFERENCE)
        self.assertIn("`<div data-scene-poster></div>`", text)
        self.assertIn("@fontsource/<name>", text)  # a font with no variable version


if __name__ == "__main__":
    unittest.main()
