"""Tests for /forge-design motion's files: motion.css, motion.md, wireform.example.js and steps/motion.md.

motion.css holds no values of its own: every variable it reads is one theme.py writes from the
design tokens (forge-design design's template plus the keys motion.md section 2 adds), or one it sets
itself, or one a script sets and that has a fallback. It has the reduced-motion block, keeps the
rules motioncheck.py checks, and has every class the recipes in motion.md name. The hero example is
valid JavaScript with no imports, and in a fake browser it draws, pauses off-screen, draws one
still frame for reduced motion and cleans up. Those two tests need Node.

The level parts: the steps file reads the look level, asks the one question, has the table of what
each level adds as forge/levels.json has it, builds per level and proves the result as rule 9 of
forge/rules.md says; the reference has a part per level 3, 4 and 5 with patterns and a budget per
level. Its scripts parse, and the runtime (motion.js), the count-up, the spring, the live count and
the data feed run in Node with a make-believe browser."""

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


LEVELS = os.path.join(ROOT, "forge", "levels.json")
PATTERNS = {  # the section of motion.md, and the patterns it must hold
    "## 8. Level 3": ["Sticky scroll scene", "Spring", "Chart that morphs between periods", "Tilt card with depth.js"],
    "## 9. Level 4": ["Mounting a kit scene in a plain page", "Mounting a kit scene in React (and Next)"],
    "## 10. Level 5": ["Feeding setData from fetched data", "A count that follows live data",
                       "Screens that change in 3D space"],
}

# A make-believe browser for the scripts of the level parts: time and frames run by hand.
LEVEL_BROWSER = r"""
const { pathToFileURL } = require("url");
const [folder, mode] = process.argv.slice(2);
let now = 0, queue = [], fetched = [], timers = 0;
globalThis.window = { matchMedia: () => ({ matches: mode === "reduced" }) };
globalThis.document = { hidden: false, documentElement: { lang: "en" } };
globalThis.getComputedStyle = () => ({ getPropertyValue: (name) => (name === "--duration-slower" ? " 480ms " : "") });
globalThis.requestAnimationFrame = (callback) => { queue.push(callback); return queue.length; };
globalThis.cancelAnimationFrame = () => { queue = []; };
const tick = (ms) => { now += ms; const run = queue; queue = []; run.forEach((callback) => callback(now)); };
globalThis.CSS = { supports: () => true };
globalThis.setInterval = () => ++timers;
globalThis.clearInterval = () => { timers--; };
globalThis.fetch = async (url) => { fetched.push(url); return { ok: true, json: async () => [{ count: 2 }, { count: 8 }] }; };
const url = (name) => pathToFileURL(folder + "/" + name).href;
(async () => {
  const out = {};
  const { spring } = await import(url("spring.mjs"));
  for (const bounce of [0.2, 0.35, 0.6]) {
    const result = spring(320, bounce);
    const points = result.easing.slice(7, -1).split(", ").map(Number);
    out["spring " + bounce] = { duration: result.duration, first: points[0], last: points[points.length - 1],
                                most: Math.max(...points), count: points.length };
  }
  const { liveCount } = await import(url("livecount.mjs"));
  const el = { dataset: { value: "0" }, textContent: "0" }, label = { dataset: { unit: "catches" }, textContent: "" };
  const set = liveCount(el, label);
  set(1000);
  out.label = label.textContent;
  tick(0); tick(100);
  out["after 100ms"] = el.textContent;
  set(500);
  tick(0);
  out["new value mid-way starts at"] = el.textContent;
  for (let i = 0; i < 40; i++) tick(16);
  out.end = el.textContent;
  out["frames left"] = queue.length;
  const { feed, share } = await import(url("feed.mjs"));
  let used = null;
  const stop = feed("/api/week", (rows) => { used = share(rows.map((row) => row.count)); });
  await new Promise((resolve) => setTimeout(resolve, 20));
  out.fetched = fetched;
  out.used = used;
  out.timers = timers;
  stop();
  out["timers after stop"] = timers;
  document.hidden = true;
  feed("/api/hidden", () => {});
  await new Promise((resolve) => setTimeout(resolve, 20));
  out["fetched while hidden"] = fetched.length;
  console.log(JSON.stringify(out));
})();
"""


# A make-believe page for motion.js and the count-up: observers and frames that only record, and a page
# whose elements a client-side router swaps out (as Livewire and Turbo swap <body>).
RUNTIME_BROWSER = r"""
const { pathToFileURL } = require("url");
const [folder] = process.argv.slice(2);
const frames = [], ios = [], observed = new Set(), disconnected = [];
let mutation = null, watched = null, reveals = [], scenes = [];
const element = (id, classes = []) => ({ id, dataset: {}, isConnected: true,
  classList: { set: new Set(classes), add(name) { this.set.add(name); }, contains(name) { return this.set.has(name); } } });
globalThis.Node = { TEXT_NODE: 3 };
globalThis.window = { matchMedia: () => ({ matches: false }) };
globalThis.getComputedStyle = () => ({ getPropertyValue: (name) => (name === "--duration-slower" ? " 480ms " : "") });
globalThis.document = { documentElement: { dataset: {}, lang: "en" },
  querySelectorAll(selector) {
    if (selector.includes(".m-reveal")) return reveals.filter((e) => e.isConnected && !e.classList.contains("is-visible"));
    return selector === ".scene" ? scenes.filter((e) => e.isConnected) : [];
  } };
globalThis.IntersectionObserver = class {
  constructor(callback) { this.callback = callback; ios.push(this); }
  observe(target) { observed.add(target.id); }
  unobserve() {}
  disconnect() { disconnected.push("io"); }
};
globalThis.MutationObserver = class {
  constructor(callback) { mutation = callback; }
  observe(target, options) { watched = target === document.documentElement && options.subtree === true; }
  disconnect() { disconnected.push("mo"); }
};
globalThis.requestAnimationFrame = (callback) => frames.push(callback);
globalThis.cancelAnimationFrame = () => {};
const run = (now) => frames.splice(0).forEach((callback) => callback(now));
const url = (name) => pathToFileURL(folder + "/" + name).href;
(async () => {
  const out = {};
  const { startMotion } = await import(url("motion.mjs"));
  reveals = [element("r1", ["m-reveal"])];
  scenes = [element("s1")];
  const started = [], stopped = [];
  const stop = startMotion({ ".scene": (e) => { started.push(e.id); return () => stopped.push(e.id); } });
  out.first = { observed: [...observed], started: [...started], motion: document.documentElement.dataset.motion, watched };
  const again = startMotion({ ".scene": (e) => { started.push("again " + e.id); return () => {}; } });
  again(); again();                                                 // a nested layout's cleanup, called twice
  out.again = { same: again === stop, started: [...started], observers: ios.length,   // Turbo runs it again
                disconnected: disconnected.length };                // the first call's runtime keeps running
  reveals[0].isConnected = scenes[0].isConnected = false;          // a page change without a reload
  reveals.push(element("tall", ["m-reveal"]));
  scenes.push(element("s2"));
  mutation([]);
  mutation([]);
  out.framesAsked = frames.length;                                  // two batches, one frame
  run(16);
  out.after = { observed: [...observed], started: [...started], stopped: [...stopped] };
  const tall = reveals[1], reveal = ios[0].callback;
  reveal([{ isIntersecting: true, intersectionRatio: 0.04, intersectionRect: { height: 50 }, target: tall }]);
  out.thinSlice = tall.classList.contains("is-visible");
  reveal([{ isIntersecting: true, intersectionRatio: 0.04, intersectionRect: { height: 200 }, target: tall }]);
  out.slice96 = tall.classList.contains("is-visible");             // 200px of a block taller than the screen
  stop();
  out.stop = { disconnected: disconnected.slice().sort(), stopped: [...stopped] };
  const fresh = startMotion();                                     // after a stop (React's second effect): a new one
  stop();                                                           // an old stop again: the new one keeps running
  out.fresh = fresh !== stop && ios.length === 4 && disconnected.length === 3;
  fresh();
  const { countUp } = await import(url("countup.mjs"));
  const text = { nodeType: 3, data: "1,280" }, seen = [];
  countUp({ firstChild: text, dataset: { value: "1280" } });
  ios[ios.length - 1].callback([{ isIntersecting: true }]);
  for (let now = 0; now <= 1000; now += 16) { seen.push(text.data); run(now); }
  out.count = { first: seen[0], last: text.data, values: new Set(seen).size, framesLeft: frames.length };
  const newer = { nodeType: 3, data: "49" };
  countUp({ firstChild: newer, dataset: { value: "49" } });
  ios[ios.length - 1].callback([{ isIntersecting: true }]);
  run(0);
  run(100);
  newer.data = "52";                                                // the framework drew a newer value
  for (let now = 116; now <= 1000; now += 16) run(now);
  out.newerValueStays = newer.data;
  console.log(JSON.stringify(out));
})();
"""


def code_blocks(text, language):
    return re.findall(r"```%s\n(.*?)```" % language, text, re.S)


def block_with(text, needle):
    found = [block for block in code_blocks(text, "js") if needle in block]
    assert len(found) == 1, needle
    return found[0]


class StepsLevelTests(unittest.TestCase):
    def setUp(self):
        self.steps = read(SKILL)

    def test_says_which_skill_it_is_part_of_and_where_the_rules_are(self):
        top = "\n".join(self.steps.splitlines()[:6])
        for part in ["`/forge-design`", "`SKILL.md`", "`../forge/rules.md`", "section 9", "section 10"]:
            self.assertIn(part, top)
        self.assertLessEqual(len(self.steps.splitlines()), 260)  # about 250: detail goes to motion.md

    def test_reads_records_and_asks_for_the_level(self):
        for part in ["python3 ../forge/level.py get look", "python3 ../forge/level.py show look",
                     "python3 ../forge/level.py set look", "--said '", "ONE question", "auto mode too",
                     "python3 ../forge/level.py check look --report forge-work/motion.md", "`Level: N"]:
            self.assertIn(part, self.steps)

    def test_the_level_table_says_what_levels_json_says(self):
        with open(LEVELS, encoding="utf-8") as handle:
            look = json.load(handle)["domains"]["look"]["levels"]
        rows = {int(match.group(1)): match.group(0) for match in re.finditer(r"(?m)^\| (\d) \|.*$", self.steps)}
        self.assertEqual(sorted(rows), [1, 2, 3, 4, 5])
        for level in look:
            with self.subTest(level=level["level"]):
                row = rows[level["level"]]
                self.assertTrue(row.startswith("| %d | %s | %s |" % (level["level"], level["name"], level["nl"])), row)
                for item in level["includes"]:
                    self.assertIn(item, row)

    def test_builds_per_level_and_proves_the_result(self):
        for part in ["../forge-design/concepts.md", "`Concept:`", "../forge-design/motion.css",
                     "../forge-design/scenes/depth.js", "../forge-design/scenes.md", "npm install three",
                     "lazyScene", "data-scene-poster", "motionToggle", "journey.js", "setData",
                     "../forge-design/shots.example.mjs", "--frames", "--video", "--reduced",
                     "python3 ../forge-design/changed.py forge-work/motion-shots/before forge-work/motion-shots/after",
                     "python3 ../forge-design/changed.py --moves", "python3 ../forge-design/motioncount.py . --level auto",
                     "the gate's own run from the root", "python3 ../forge-design/motioncheck.py . --fail-on medium",
                     "--scene-frames", "../forge-check/testdb.py", "Auto mode:", "yes or no",
                     "Agent or Task", "git branch --show-current", "git worktree list", "service worker",
                     "git switch", ".webm"]:
            self.assertIn(part, self.steps)
        order = ["## Step 1", "## Step 2: the level", "## Step 3: the concept", "## Step 4: the inventory",
                 "## Step 5", "## Step 6: build", "## Step 7: accessibility", "## Step 8", "## Step 9", "## Output",
                 "## Next"]
        self.assertEqual([self.steps.index(name) for name in order], sorted(self.steps.index(name) for name in order))
        header = "| screen | moment | job | what is built | the file to change | what reduced motion shows |"
        self.assertIn(header, self.steps)


class ReferenceLevelTests(unittest.TestCase):
    def setUp(self):
        self.text = read(REFERENCE)

    def test_has_a_part_per_level_with_its_patterns(self):
        heads = ["## 7. ", "## 8. Level 3", "## 9. Level 4", "## 10. Level 5", "## 11. The budget per level"]
        self.assertEqual([self.text.index(head) for head in heads], sorted(self.text.index(head) for head in heads))
        for head, names in PATTERNS.items():
            part = self.text[self.text.index(head):]
            part = part[:part.index("\n## ", 4)] if "\n## " in part[4:] else part
            for name in names:
                with self.subTest(pattern=name):
                    piece = part[part.index("**%s.**" % name):]
                    piece = piece[:piece.index("\n**", 4)] if "\n**" in piece[4:] else piece
                    self.assertIn("Reduced", piece)
                    self.assertIn("Mistake", piece)

    def test_the_budget_has_a_row_per_level(self):
        budget = self.text[self.text.index("## 11. The budget per level"):]
        for level, name in enumerate(["Subtle", "Polished", "Expressive", "Showpiece", "Cinematic"], 1):
            self.assertRegex(budget, r"(?m)^\| %d %s \|" % (level, name))

    def test_no_code_reaches_another_host(self):
        for language in ["js", "jsx", "html", "css"]:
            for block in code_blocks(self.text, language):
                self.assertNotRegex(block, r"https?://|//cdn|unpkg|jsdelivr")

    def node(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        return node

    def test_every_script_parses(self):
        node = self.node()
        with tempfile.TemporaryDirectory() as folder:
            for number, block in enumerate(code_blocks(self.text, "js")):
                path = os.path.join(folder, "block%d.mjs" % number)
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(block)
                done = subprocess.run([node, "--check", path], timeout=60, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, universal_newlines=True)
                self.assertEqual(done.returncode, 0, block[:80] + done.stderr)

    def run_scripts(self, mode):
        node = self.node()
        with tempfile.TemporaryDirectory() as folder:
            files = {"tokens.js": block_with(self.text, "// tokens.js"),
                     "spring.mjs": block_with(self.text, "export function spring("),
                     "livecount.mjs": block_with(self.text, "export function liveCount("),
                     "feed.mjs": block_with(self.text, "export function feed(")}
            files["livecount.mjs"] = files["livecount.mjs"].replace('"./tokens.js"', '"./tokens.mjs"')
            files["tokens.mjs"] = files.pop("tokens.js")
            files["browser.cjs"] = LEVEL_BROWSER
            for name, code in files.items():
                with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
                    handle.write(code)
            done = subprocess.run([node, os.path.join(folder, "browser.cjs"), folder, mode], timeout=60,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            return json.loads(done.stdout)

    def test_the_spring_live_count_and_feed_work(self):
        out = self.run_scripts("moving")
        for bounce, most in [("0.2", (1.005, 1.03)), ("0.35", (1.04, 1.1)), ("0.6", (1.15, 1.35))]:
            spring = out["spring " + bounce]
            self.assertEqual((spring["first"], spring["last"], spring["count"]), (0, 1, 41))
            self.assertGreater(spring["duration"], 320)  # it settles after one swing
            self.assertTrue(most[0] < spring["most"] < most[1], spring)
        self.assertEqual(out["label"], "1,000 catches")  # the screen reader gets the value once
        self.assertTrue(0 < int(out["after 100ms"].replace(",", "")) < 1000)
        self.assertEqual(out["new value mid-way starts at"], out["after 100ms"])  # from where it stands
        self.assertEqual((out["end"], out["frames left"]), ("500", 0))
        self.assertEqual((out["fetched"], out["used"], out["timers"], out["timers after stop"]),
                         (["/api/week"], [0.25, 1], 1, 0))
        self.assertEqual(out["fetched while hidden"], 1)  # nobody looks: no request

    def test_reduced_motion_gives_the_number_at_once(self):
        out = self.run_scripts("reduced")
        self.assertEqual((out["after 100ms"], out["end"], out["frames left"]), ("1,000", "500", 0))

    def test_the_runtime_follows_page_changes_and_the_count_writes_its_own_text_node(self):
        """motion.js for every stack: content and scenes a client-side page change brings are picked up
        (the critic's Inertia, Livewire and SPA case), a block taller than the screen reveals at 96px, and
        the count-up writes the page's own text node and leaves a newer value of the app alone."""
        node = self.node()
        with tempfile.TemporaryDirectory() as folder:
            files = {"motion.mjs": block_with(self.text, "export function startMotion("),
                     "tokens.mjs": block_with(self.text, "// tokens.js"),
                     "countup.mjs": 'import { ms, reduce } from "./tokens.mjs";\n'
                                    + block_with(self.text, "export function countUp("),
                     "browser.cjs": RUNTIME_BROWSER}
            for name, code in files.items():
                with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
                    handle.write(code)
            done = subprocess.run([node, os.path.join(folder, "browser.cjs"), folder], timeout=60,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertEqual(out["first"], {"observed": ["r1"], "started": ["s1"], "motion": "on", "watched": True})
        self.assertEqual(out["again"], {"same": False, "started": ["s1"], "observers": 2,  # no second scene or observer
                                        "disconnected": 0})  # and its own stop leaves the first caller's runtime alone
        self.assertTrue(out["fresh"])
        self.assertEqual(out["framesAsked"], 1)
        self.assertEqual(out["after"], {"observed": ["r1", "tall"], "started": ["s1", "s2"], "stopped": ["s1"]})
        self.assertEqual((out["thinSlice"], out["slice96"]), (False, True))
        self.assertEqual(out["stop"], {"disconnected": ["io", "io", "mo"], "stopped": ["s1", "s2"]})
        self.assertEqual((out["count"]["first"], out["count"]["last"], out["count"]["framesLeft"]), ("0", "1,280", 0))
        self.assertGreater(out["count"]["values"], 10)  # it counts, in the node that was there
        self.assertEqual(out["newerValueStays"], "52")


if __name__ == "__main__":
    unittest.main()
