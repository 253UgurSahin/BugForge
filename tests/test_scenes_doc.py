"""Tests for forge-design/scenes.md: the one reference for using the scene kit in an app.

People copy its code samples into their app, so the samples must match the kit as it is: every
file of forge-design/scenes/ is named in the doc; every option and method a sample uses with a
scene is a name that scene's file (or stage.js and lazy.js, whose options and methods every scene
passes through) has; every data- attribute a markup sample uses is one the kit reads, and every
data-depth value is one depth.js knows; the JavaScript samples parse (with Node, skipped
without it); and the doc names no other host than this machine."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT  # noqa: E402

DOC = os.path.join(ROOT, "forge-design", "scenes.md")
SCENES = os.path.join(ROOT, "forge-design", "scenes")
RUNTIME = ["stage.js", "lazy.js"]  # their options and handle methods pass through every scene
BLOCK = re.compile(r"```(\w+)\n(.*?)```", re.S)
KEY = re.compile(r"[{,]\s*([A-Za-z_]\w*)\s*:(?!:)")        # `{ side: ...`, `, levels: ...`
METHOD = re.compile(r"\.([A-Za-z_]\w*)\s*\(")              # `hero.setProgress(`, `scene.current?.setData(`
ATTRIBUTE = re.compile(r"\b(data-[\w-]+)")
DEPTH_VALUE = re.compile(r'data-depth="([^"]*)"')
URL = re.compile(r"https?://(?!localhost\b|127\.0\.0\.1\b)[^\s)`'\"]+")
# What the samples call on the browser, the language or React, not on a scene.
PLATFORM = {"querySelector", "querySelectorAll", "addEventListener", "removeEventListener", "then",
            "json", "map", "max", "min", "all", "forEach", "toggleAttribute", "setAttribute",
            "split", "pop", "mkdirSync", "copyFileSync", "require"}
# Keys that are not scene options: dynamic()'s own, an npm script table, addEventListener's.
NOT_OPTIONS = {"ssr", "loading", "scripts", "recursive", "imports", "passive"}


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def kit_files():
    return sorted(name for name in os.listdir(SCENES) if name.endswith((".js", ".css")))


def scene_names():
    """The scenes an app mounts: every .js file of the kit but the runtime and the shader pieces."""
    return sorted(name for name in kit_files() if name.endswith(".js") and name not in RUNTIME + ["glsl.js"])


def blocks(text, languages):
    return [body for language, body in BLOCK.findall(text) if language in languages]


def scenes_in(block):
    return sorted({name for name in scene_names() if re.search(r"(?<![\w-])%s\b" % re.escape(name), block)})


def strip_strings(code):
    """The code with the text of its string literals blanked, so words inside a string are not keys."""
    return re.sub(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'', '""', code)


def unknown_names(block, sources):
    """Option keys and method names the block uses that no source file has."""
    code = strip_strings(re.sub(r"(?m)//[^\n]*$", "", block))
    names = {(name, "option") for name in KEY.findall(code) if name not in NOT_OPTIONS}
    names |= {(name, "method") for name in METHOD.findall(code) if name not in PLATFORM}
    return sorted((name, kind) for name, kind in names
                  if not re.search(r"\b%s\b" % re.escape(name), sources))


class ScenesDocTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = read(DOC)
        cls.kit = {name: read(os.path.join(SCENES, name)) for name in kit_files()}

    def test_names_every_file_of_the_kit(self):
        self.assertGreaterEqual(len(self.kit), 11)
        for name in self.kit:
            with self.subTest(file=name):
                self.assertIn("../forge-design/scenes/%s" % name, self.text)

    def test_every_option_and_method_of_a_sample_is_in_its_scene(self):
        checked = set()
        for block in blocks(self.text, {"js", "jsx"}):
            used = scenes_in(block)
            if not used:
                continue
            checked.update(used)
            sources = "\n".join(self.kit[name] for name in used + RUNTIME)
            with self.subTest(scenes=used, block=block[:60]):
                self.assertEqual(unknown_names(block, sources), [])
        self.assertTrue({"journey.js", "depth.js"} <= checked, checked)
        self.assertGreaterEqual(len(checked), 5)

    def test_markup_uses_only_attributes_the_kit_reads(self):
        kit = "\n".join(self.kit.values())
        depth = self.kit["depth.js"]
        for block in blocks(self.text, {"html", "jsx"}):
            for name in set(ATTRIBUTE.findall(block)):
                with self.subTest(attribute=name):
                    self.assertIn(name, kit)
            for value in DEPTH_VALUE.findall(block):
                with self.subTest(depth=value):
                    self.assertIn('data-depth="%s"' % value, depth)

    def test_the_samples_cover_every_stack(self):
        for part in ["importmap", "lazyScene", "motionToggle", "data-scene-poster", "useEffect",
                     "ssr: false", "{% static", "resources/js/app.js", "npm install three",
                     "node_modules/three/LICENSE", "data-journey-stage", "data-chapter",
                     "data-depth-layer", "prefers-reduced-motion"]:
            with self.subTest(part=part):
                self.assertIn(part, self.text)
        for value in ["tilt", "stack", "fold", "scene"]:
            self.assertIn('data-depth="%s"' % value, self.text)

    def test_no_other_host(self):
        self.assertEqual(URL.findall(self.text), [])
        self.assertNotRegex(self.text, r"//cdn|unpkg|jsdelivr")

    def test_the_checks_catch_a_wrong_name(self):
        sources = self.kit["form.js"] + self.kit["stage.js"] + self.kit["lazy.js"]
        good = 'const f = mount(el, { side: "right", quality: "low" });\nf.setProgress(0.5);'
        self.assertEqual(unknown_names(good, sources), [])
        bad = 'const f = mount(el, { wobbliness: 2, side: "right" });\nf.spinAround(2); // f.whirlAbout()'
        self.assertEqual(unknown_names(bad, sources), [("spinAround", "method"), ("wobbliness", "option")])
        self.assertEqual(unknown_names('x({ tooltipText: "a, b: c" })', sources), [("tooltipText", "option")])
        self.assertEqual(scenes_in('import("./scenes/form.js")'), ["form.js"])
        self.assertEqual(URL.findall("see http://localhost:3000 and https://example.org/x"),
                         ["https://example.org/x"])

    def test_the_javascript_samples_parse(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        with tempfile.TemporaryDirectory() as folder:
            for number, block in enumerate(blocks(self.text, {"js"})):
                path = os.path.join(folder, "sample%d.mjs" % number)
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(block)
                done = subprocess.run([node, "--check", path], timeout=60, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, universal_newlines=True)
                self.assertEqual(done.returncode, 0, block[:80] + done.stderr)


if __name__ == "__main__":
    unittest.main()
