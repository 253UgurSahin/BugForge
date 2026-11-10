"""Tests for forge-design motion's reference files: motion.css, motion.md, wireform.example.js and SKILL.md.

motion.css holds no values of its own: every variable it reads is one theme.py writes from the
design tokens (forge-design design's template plus the keys motion.md section 2 adds), or one it sets
itself, or one a script sets and that has a fallback. It has the reduced-motion block, keeps the
rules motioncheck.py checks, and has every class the recipes in motion.md name. The hero example is
valid JavaScript with no imports, and in a fake browser it draws, pauses off-screen, draws one
still frame for reduced motion and cleans up. Those two tests need Node."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load  # noqa: E402

theme = load("forge-design", "theme")
motioncheck = load("forge-design", "motioncheck")
FOLDER = os.path.join(ROOT, "forge-design")
CSS = os.path.join(FOLDER, "motion.css")
REFERENCE = os.path.join(FOLDER, "motion.md")
SKILL = os.path.join(FOLDER, "steps", "motion.md")
WIREFORM = os.path.join(FOLDER, "wireform.example.js")
TOKENS = os.path.join(ROOT, "forge-design", "tokens.json")
MOTION_VARIABLES = {"--duration-fast", "--duration-base", "--duration-slow", "--duration-slower",
                    "--duration-stagger", "--duration-pulse", "--duration-loop", "--ease-standard", "--ease-exit",
                    "--ease-move", "--ease-spring", "--size-shift-sm", "--size-shift", "--size-shift-lg"}

# A fake browser for the hero: a canvas that counts stroke() calls, and frames, observers and
# listeners that only count. Prints JSON: what happened at each step.
BROWSER = r"""
const { pathToFileURL } = require("url");
const [file, mode] = process.argv.slice(2);
const calls = { stroke: 0, frames: 0, cancelled: 0, disconnected: 0, removed: 0 };
let frame = null, view = null;
const ctx = new Proxy({}, { get: (target, key) => (key === "stroke" ? () => { calls.stroke++; } : () => {}),
                            set: () => true });
const canvas = { width: 0, height: 0, getContext: () => ctx,
                 getBoundingClientRect: () => ({ width: 300, height: 200 }) };
const listeners = { addEventListener() {}, removeEventListener() { calls.removed++; } };
globalThis.window = { devicePixelRatio: 3, matchMedia: () => ({ matches: mode === "reduced", ...listeners }) };
globalThis.document = { hidden: false, ...listeners };
globalThis.getComputedStyle = () => ({ getPropertyValue: () => " #5fd4ff ", color: "rgb(0, 0, 0)" });
globalThis.requestAnimationFrame = (callback) => { calls.frames++; frame = callback; return calls.frames; };
globalThis.cancelAnimationFrame = () => { calls.cancelled++; };
globalThis.ResizeObserver = class { observe() {} disconnect() { calls.disconnected++; } };
globalThis.IntersectionObserver = class {
  constructor(callback) { view = callback; }
  observe() {}
  disconnect() { calls.disconnected++; }
};
import(pathToFileURL(file).href).then(({ createWireform }) => {
  const wireform = createWireform(canvas);
  const out = { width: canvas.width, height: canvas.height, "frames at start": calls.frames,
                "strokes at start": calls.stroke };
  if (frame) frame(performance.now() + 16);
  out["frames after one"] = calls.frames;
  out["strokes after one"] = calls.stroke;
  view([{ isIntersecting: false }]);
  out["cancelled off-screen"] = calls.cancelled;
  out["frames off-screen"] = calls.frames;
  view([{ isIntersecting: true }]);
  out["frames back on screen"] = calls.frames;
  wireform.destroy();
  out.disconnected = calls.disconnected;
  out.removed = calls.removed;
  console.log(JSON.stringify(out));
});
"""


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def added_tokens():
    """The token keys motion.md section 2 tells Claude to add: its first json block."""
    return json.loads(re.search(r"```json\n(.*?)```", read(REFERENCE), re.S).group(1))


def theme_variables():
    """Every variable theme.py writes from forge-design design's tokens with motion.md's keys added."""
    tokens = json.loads(read(TOKENS))
    for group, keys in added_tokens().items():
        tokens[group] = dict(tokens[group], **keys)
    return set(theme.DECLARED.findall(theme.blocks(tokens, "no")))


class MotionCssTests(unittest.TestCase):
    def setUp(self):
        self.css = read(CSS)
        self.code = re.sub(r"/\*.*?\*/", "", self.css, flags=re.S)

    def test_has_the_reduced_motion_block_and_keeps_movement_out_of_it(self):
        self.assertEqual(len(re.findall(r"@media \(prefers-reduced-motion: reduce\) \{", self.code)), 1)
        self.assertEqual(len(re.findall(r"@media \(prefers-reduced-motion: no-preference\) \{", self.code)), 1)
        moving = self.code[self.code.index("@media (prefers-reduced-motion: no-preference)"):
                           self.code.index("@media (prefers-reduced-motion: reduce)")]
        before = self.code[:self.code.index("@media (prefers-reduced-motion: no-preference)")]
        for name in ["m-rise-in", "m-sheen", "m-marquee", "m-drift"]:  # the keyframes that travel
            self.assertIn("@keyframes %s " % name, moving)
            self.assertNotIn("@keyframes %s " % name, before)
        self.assertNotIn("infinite", before)
        self.assertIn("@view-transition", moving)

    def test_only_uses_variables_that_exist(self):
        from_theme = theme_variables()
        self.assertEqual(MOTION_VARIABLES - from_theme, set(), "theme.py does not write these")
        set_here = set(re.findall(r"(--[\w-]+)\s*:", self.code))
        for name, fallback in re.findall(r"var\(\s*(--[\w-]+)\s*(,)?", self.code):
            with self.subTest(variable=name):
                if name.startswith("--m-"):  # the file's own: set in it, or set by a script with a fallback here
                    self.assertTrue(name in set_here or fallback, "%s is never set and has no fallback" % name)
                else:
                    self.assertIn(name, from_theme, "%s is not a variable theme.py writes" % name)

    def test_uses_every_motion_variable_family(self):
        used = set(re.findall(r"var\(\s*(--[\w-]+)", self.code))
        self.assertEqual(MOTION_VARIABLES - used, {"--ease-spring"})  # the spring is for scripts (motion.md)

    def test_holds_no_values_of_its_own(self):
        self.assertEqual(re.findall(r"(?<![\w.-])\d*\.?\d+m?s\b", self.code.replace(" 0s", " ")), [], "a raw time")
        self.assertNotIn("cubic-bezier", self.code)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", self.code), [], "a raw colour")
        self.assertEqual(re.findall(r"(?<![\w.-])\d*\.?\d+(?:px|rem|em)\b", self.code), [], "a raw length")

    def test_is_well_formed_and_keeps_its_own_rules(self):
        self.assertEqual(self.code.count("{"), self.code.count("}"))
        self.assertNotIn("will-change", self.code)
        report = motioncheck.scan_path(CSS, "low")
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["summary"]["files_checked"], 1)

    def test_has_every_class_the_recipes_name(self):
        defined = set(re.findall(r"\.(m-[\w-]+)", self.code))
        named = set(re.findall(r"\b(m-[a-z][\w-]*)\b", read(REFERENCE) + read(SKILL))) - {"m-index"}
        named = {name for name in named if "--" + name not in self.css and not name.endswith("-")}
        self.assertTrue({"m-press", "m-lift", "m-ring", "m-skeleton", "m-stagger", "m-accordion", "m-enter", "m-leave",
                         "m-modal", "m-sheet", "m-tabs__line", "m-reveal", "m-reveal-scroll", "m-count", "m-draw",
                         "m-grow", "m-parallax", "m-marquee", "m-glow"} <= defined)
        self.assertEqual(named - defined, set(), "motion.md names classes motion.css does not have")


class ReferenceTests(unittest.TestCase):
    def test_the_added_tokens_fit_the_theme(self):
        added = added_tokens()
        self.assertEqual(sorted(added), ["motion", "size"])
        template = json.loads(read(TOKENS))
        for group, keys in added.items():
            self.assertEqual(set(keys) & set(template[group]), set(), "a key forge-design design already has")
        for key, item in added["motion"].items():  # theme.py: ease-* is a curve, the rest is a time
            self.assertRegex(item, r"^cubic-bezier\(" if key.startswith("ease-") else r"^\d+m?s$")
        self.assertTrue(all(isinstance(item, int) for item in added["size"].values()))

    def test_the_reference_has_every_recipe_and_the_skill_its_sections(self):
        text = read(REFERENCE)
        for recipe in ["Button press", "Hover lift", "Focus ring", "Skeleton to content", "List stagger", "Accordion",
                       "Toast", "Modal and sheet", "Tab underline", "Page transition",
                       "Scroll reveal, IntersectionObserver", "Scroll reveal, animation-timeline", "Number count-up",
                       "Chart draw-on", "Parallax, done safely", "Marquee that pauses", "Cursor glow"]:
            part = text[text.index("**%s.**" % recipe):]
            part = part[:part.index("\n**", 4)] if "\n**" in part[4:] else part
            self.assertIn("Reduced", part, recipe)
            self.assertIn("Mistake", part, recipe)
        for name in ["GSAP", "Three.js", "lottie-web", "laravel", "django", "next", "static"]:
            self.assertIn(name, text[text.index("## 5. Libraries"):text.index("## 6.")])
        skill = read(SKILL)
        for section in ["## Direction", "## Inventory", "## Tokens", "## Libraries", "## Checks"]:
            self.assertIn("`%s`" % section, skill)
        self.assertIn("/forge-check test", skill[skill.index("## Next"):])


class WireformTests(unittest.TestCase):
    def setUp(self):
        self.source = read(WIREFORM)

    def test_is_a_small_module_with_no_dependencies(self):
        self.assertLessEqual(len(self.source.splitlines()), 220)
        self.assertNotRegex(self.source, r"(?m)^\s*import\b|\brequire\(|https?://")
        self.assertIn("export function createWireform(", self.source)
        self.assertIn("Three.js", self.source[:self.source.index("const TAU")])  # the top says when to move on
        for part in ["prefers-reduced-motion", "IntersectionObserver", "visibilitychange", "ResizeObserver",
                     "devicePixelRatio", "getPropertyValue", "cancelAnimationFrame", "destroy()"]:
            self.assertIn(part, self.source)
        self.assertNotRegex(self.source, r"#[0-9a-fA-F]{3,8}\b|rgba?\(")  # colours come from the CSS

    def run_node(self, *args):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        with tempfile.TemporaryDirectory() as folder:
            module = os.path.join(folder, "wireform.mjs")  # .mjs: a module for every Node version
            shutil.copyfile(WIREFORM, module)
            browser = os.path.join(folder, "browser.cjs")
            with open(browser, "w", encoding="utf-8") as handle:
                handle.write(BROWSER)
            command = [node, "--check", module] if not args else [node, browser, module] + list(args)
            return subprocess.run(command, timeout=60, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True)

    def test_node_check(self):
        done = self.run_node()
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_draws_pauses_and_cleans_up(self):
        done = self.run_node("moving")
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertEqual((out["width"], out["height"]), (600, 400))  # 300 by 200, at 2 of the screen's 3 pixels
        self.assertGreater(out["strokes at start"], 0)
        self.assertEqual(out["frames at start"], 1)
        self.assertEqual(out["frames after one"], 2)  # the loop goes on
        self.assertGreater(out["strokes after one"], out["strokes at start"])
        self.assertEqual((out["cancelled off-screen"], out["frames off-screen"]), (1, 2))  # stopped
        self.assertEqual(out["frames back on screen"], 3)
        self.assertEqual((out["disconnected"], out["removed"]), (2, 2))

    def test_reduced_motion_draws_one_still_frame_and_never_loops(self):
        done = self.run_node("reduced")
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertGreater(out["strokes at start"], 0)
        self.assertEqual((out["frames at start"], out["frames back on screen"], out["cancelled off-screen"]), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
