"""Tests for the examples gallery (examples/): it runs from its own folder with no request to another host,
the kit copy in examples/vendor/scenes is the kit of forge-design, and every level of the example app is
there with what that level asks for."""

import filecmp
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT  # noqa: E402

EXAMPLES = os.path.join(ROOT, "examples")
KIT = os.path.join(ROOT, "forge-design", "scenes")
COPY = os.path.join(EXAMPLES, "vendor", "scenes")
TEXT = (".html", ".css", ".js", ".mjs", ".json", ".md")
URL = re.compile(r"""(?:src|href)\s*=\s*["'](https?:)?//|url\(\s*["']?(https?:)?//|@import\s+["']?(https?:)?//|from\s+["']https?://""")


def pages():
    for folder, subfolders, names in os.walk(EXAMPLES):
        subfolders[:] = [name for name in subfolders if name != "vendor"]
        for name in names:
            if name.endswith(TEXT):
                yield os.path.join(folder, name)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class GalleryTests(unittest.TestCase):
    def test_the_kit_copy_is_the_kit(self):
        kit = sorted(name for name in os.listdir(KIT) if name.endswith((".js", ".css")))
        copy = sorted(name for name in os.listdir(COPY) if name.endswith((".js", ".css")))
        self.assertEqual(copy, kit, "copy forge-design/scenes/* to examples/vendor/scenes/")
        for name in kit:
            with self.subTest(file=name):
                self.assertTrue(filecmp.cmp(os.path.join(KIT, name), os.path.join(COPY, name), shallow=False),
                                "examples/vendor/scenes/%s differs from forge-design/scenes/%s: copy it again" % (name, name))

    def test_nothing_is_loaded_from_another_host(self):
        for path in pages():
            with self.subTest(file=os.path.relpath(path, ROOT)):
                self.assertIsNone(URL.search(read(path)))

    def test_three_is_the_local_copy_with_its_licence(self):
        folder = os.path.join(EXAMPLES, "vendor", "three")
        for name in ("three.module.js", "three.core.js", "LICENSE"):
            self.assertTrue(os.path.isfile(os.path.join(folder, name)), name)
        self.assertIn("MIT License", read(os.path.join(folder, "LICENSE")))
        for path in pages():
            text = read(path)
            for target in re.findall(r'"three"\s*:\s*"([^"]+)"', text):
                with self.subTest(file=os.path.relpath(path, ROOT)):
                    self.assertTrue(os.path.isfile(os.path.normpath(os.path.join(os.path.dirname(path), target))), target)

    def test_every_relative_file_a_page_names_is_there(self):
        for path in pages():
            if not path.endswith(".html"):
                continue
            for target in re.findall(r"""(?:src|href)\s*=\s*["']([^"'#?:]+)["']""", read(path)):
                with self.subTest(file=os.path.relpath(path, ROOT), target=target):
                    self.assertTrue(os.path.exists(os.path.normpath(os.path.join(os.path.dirname(path), target))))

    def test_the_levels_are_there(self):
        levels = os.path.join(EXAMPLES, "levels")
        found = sorted(name for name in os.listdir(levels) if name.isdigit())
        self.assertEqual(found, ["1", "2", "3", "4", "5"])
        for name in found:
            with self.subTest(level=name):
                self.assertTrue(os.path.isfile(os.path.join(levels, name, "index.html")))
        for name in [name for name in found if int(name) >= 4]:
            with self.subTest(level=name):
                page = "".join(read(os.path.join(levels, name, file)) for file in os.listdir(os.path.join(levels, name))
                               if file.endswith((".html", ".js")))
                self.assertIn("vendor/scenes/", page, "level %s mounts a scene of the kit" % name)
                self.assertIn("data-scene-poster", page, "level %s has a poster for no WebGL" % name)

    def test_the_start_page_shows_every_level_with_a_preview_and_a_still(self):
        start = read(os.path.join(EXAMPLES, "index.html"))
        for name in ("1", "2", "3", "4", "5"):
            with self.subTest(level=name):
                self.assertIn('href="levels/%s/index.html"' % name, start)
                self.assertIn('src="previews/level-%s.webp"' % name, start)
                self.assertIn('srcset="previews/level-%s-still.webp"' % name, start, "a still for less motion")
                for preview in ("level-%s.webp" % name, "level-%s-still.webp" % name):
                    self.assertTrue(os.path.isfile(os.path.join(EXAMPLES, "previews", preview)), preview)


if __name__ == "__main__":
    unittest.main()
