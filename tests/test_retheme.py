"""Tests for forge-design/retheme.py: the role a place gets from its property, the context flags (on a strong
fill, floating, in a field), the inventory, a map applied by name and by role, always from the committed
files, LEFT, SPLIT, LITERAL and KEPT, and the exit codes. The repository tests use real git in temporary
folders."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402

retheme = load("forge-design", "retheme")
theme = load("forge-design", "theme")  # its block marks, which a rerun must read past
SCRIPT = os.path.join(ROOT, "forge-design", "retheme.py")
HAS_GIT = shutil.which("git") is not None

CSS = """@import "tailwindcss";
:root { --ac: #0e7c86; --ink: #14181a; --line: #e4e9ea; }
.card { background: #fff; border: 1px solid var(--line); color: var(--ink); }
.menu { background: #fff; box-shadow: 0 8px 20px rgba(20, 24, 26, .2); }
.btn { background: var(--ac); color: #fff; }
.btn:hover, .btn:focus-visible { color: #fff; }
.btn svg { fill: #fff; }
.btn-ghost:hover { color: #fff; }
.field input { background: #fff; border-color: #c3cccd; }
.veil { background: rgba(255,255,255,.7); }
.row:hover { background: var(--line); }
/* not a dialog or a menu */
.note { background: #fff; }
.rule { border-color: var(--color-gray-200); }
.chip { @apply bg-gray-100 text-white; }
"""
TSX = """const W = "#fff";
const INK = "#14181a";
export function Landing({ active }: { active: boolean }) {
  return (
    <section style={{ background: W }}>
      <h2 style={{ color: W }}>Closing</h2>
      <p style={{ color: active ? "#fff" : INK }}>Text</p>
      <svg><path fill="#fff" d="M0 0" /></svg>
      <Icon c="#fff" />
      <a href="#fff">anchor</a>
      <button className="bg-blue-600 text-white">Go</button>
      <div className="bg-white text-gray-900 dark:bg-gray-900 border-gray-200 bg-[#fff]/50">x</div>
    </section>
  );
}
"""
LAYOUT = 'export const viewport = { themeColor: "#0E7C86" };\n'
MANIFEST = 'export default function manifest() { return { theme_color: "#0e7c86", background_color: "#ffffff" }; }\n'
PAGE = ('<meta name="theme-color" content="#0e7c86">\n<p style="color: #fff">x</p>\n'
        '<script>ctx.fillStyle = "#ffffff";</script>\n')
MAP = {
    "vars": {"--ac": "--color-accent", "--ink": "--color-text", "--line": {"border": "--color-border", "bg": "--tint-2"},
             "--color-gray-200": "--color-border"},
    "colours": {
        "#fff": {"bg": "--color-surface", "bg float": "--color-raised", "bg field": "--color-field",
                 "text": "--color-text", "text on-fill": "--color-on-accent", "icon": "currentColor",
                 "icon on-fill": "--color-on-accent"},
        "#14181a": {"text": "--color-text", "shadow": "--color-shadow"},
        "#C3CCCD": "--color-border-input",
        "gray-900": {"text": "--color-text", "bg": "--color-bg"},
        "gray-200": "--color-border",
        "gray-100": {"bg": "--color-surface"},
        "blue-600": "--color-accent",
    },
    "props": {"c": "icon"},  # the app's own Icon takes its colour as c=
}


class Helpers(unittest.TestCase):
    def test_colours_are_read_in_every_spelling(self):
        self.assertEqual(retheme.norm("#FFF"), ("#ffffff", 1.0, "#ffffff"))
        self.assertEqual(retheme.norm("white"), ("#ffffff", 1.0, "#ffffff"))
        self.assertEqual(retheme.norm("rgba(255, 255, 255, .7)"), ("#ffffff", 0.7, "#ffffff/0.7"))
        self.assertEqual(retheme.norm("rgb(20 24 26 / 50%)")[:2], ("#14181a", 0.5))
        self.assertEqual(retheme.norm("#ffffff80")[1], 0.5)
        self.assertEqual(retheme.norm("gray-100"), ("gray-100", 1.0, "gray-100"))
        self.assertEqual(retheme.norm("oklch(0.922  0 0 / 10%)")[2], "oklch(0.922 0 0/10%)")  # its own key, spaced
        self.assertEqual(retheme.norm("hsl(210, 40%, 98%)"), retheme.norm("hsl(210,40%,98%)"))

    def test_a_value_finds_its_property_past_ternaries_and_arrows(self):
        cases = [('style={{ color: active ? "#fff" : "#000" }}', '"#000"', ("color", "prop")),
                 ("background: ${(p) => (p.on ? '#fff' : '#000')};", "'#000'", ("background", "prop")),
                 ('<path fill="#fff" d="M0 0" />', "#fff", ("fill", "attr")),
                 ('{ "line-color": "#fff" }', "#fff", ("line-color", "quoted")),
                 (".a:hover { color: #fff }", "#fff", ("color", "prop")),
                 ("<path stroke={tone} />", "tone", ("stroke", "attr")),  # a JSX expression reads on to its name
                 ("#add-button { color: red }", "#add", (None, None))]  # a selector, not a value
        for text, value, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(retheme.prop_at(text, text.index(value)), expected)

    def test_roles(self):
        for name, role in [("background-color", "bg"), ("backgroundColor", "bg"), ("color", "text"),
                           ("borderTopColor", "border"), ("box-shadow", "shadow"), ("textShadow", "shadow"),
                           ("fill", "icon"), ("stopColor", "icon"), ("text", "text"), ("width", "other"),
                           ("fillStyle", "literal"), ("shadowColor", "literal"), ("theme_color", "literal")]:
            self.assertEqual(retheme.role_of(name), role, name)


@unittest.skipUnless(HAS_GIT, "needs git")
class Repository(unittest.TestCase):
    def setUp(self):
        self.fresh({"app/globals.css": CSS, "components/Landing.tsx": TSX, "app/layout.tsx": LAYOUT,
                    "app/manifest.ts": MANIFEST, "templates/page.html": PAGE})
        self.map(MAP)

    def fresh(self, files):
        """A repository of its own with FILES committed (and no map yet)."""
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "test")
        self.git("config", "core.autocrlf", "false")
        for path, text in files.items():
            self.write(path, text)
        self.git("add", "-A")
        self.git("commit", "-qm", "start")

    def git(self, *args):
        subprocess.run(["git", "-C", self.root] + list(args), check=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)

    def write(self, path, text, newline=None):
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline=newline) as handle:
            handle.write(text)

    def read(self, path):
        with open(os.path.join(self.root, path), encoding="utf-8", newline="") as handle:
            return handle.read()

    def map(self, data):
        self.write("forge-work/design/retheme.json", json.dumps(data))

    def run_it(self, *args):
        done = subprocess.run([sys.executable, SCRIPT] + list(args), cwd=self.root, timeout=120,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return done.returncode, done.stdout, done.stderr

    def apply(self, *extra):
        return self.run_it("--map", "forge-work/design/retheme.json", "--write", *extra)

    def test_inventory_lists_each_value_by_role_and_changes_nothing(self):
        code, out, err = self.run_it()
        self.assertEqual(code, 0, err)
        self.assertIn("(the inventory)", out)
        line = next(item for item in out.splitlines() if item.strip().startswith("#ffffff "))
        for part in ("bg float 1", "bg field 1", "icon 2"):  # no map: no fill is known yet, so no on-fill
            self.assertIn(part, line)
        self.assertIn("#ffffff/0.7", out)  # a colour with alpha is its own value
        self.assertIn("other(c) 1", line)  # an app's own property name, for the map's "props"
        self.assertIn("--line", out)
        self.assertIn("gray-900", out)
        self.assertIn("--color-gray-200", out)
        self.assertRegex(out, r"SPLIT 1\n  SPLIT components/Landing.tsx:1 .*W: #fff")
        self.assertEqual(self.read("app/globals.css"), CSS)
        self.assertEqual(self.read("components/Landing.tsx"), TSX)

    def test_a_dry_run_writes_only_the_log(self):
        code, out, _ = self.run_it("--map", "forge-work/design/retheme.json")
        self.assertEqual(code, 1, out)  # W is SPLIT
        self.assertIn("a dry run", out)
        self.assertEqual(self.read("app/globals.css"), CSS)
        log = self.read("forge-work/design/retheme.log")
        self.assertIn("app/globals.css:4 [.menu] background: #fff -> var(--color-raised)  (bg float)", log)
        self.assertFalse(os.path.exists(os.path.join(self.root, "forge-work", "design", "retheme.state.json")))

    def test_the_map_by_name_then_by_role_and_context(self):
        code, out, _ = self.apply()
        self.assertEqual(code, 1, out)
        css = self.read("app/globals.css")
        for expected in (".card { background: var(--color-surface); border: 1px solid var(--color-border); "
                         "color: var(--color-text); }",
                         ".menu { background: var(--color-raised); box-shadow: 0 8px 20px "
                         "color-mix(in srgb, var(--color-shadow) 20%, transparent); }",
                         ".btn { background: var(--color-accent); color: var(--color-on-accent); }",
                         ".btn:hover, .btn:focus-visible { color: var(--color-on-accent); }",  # its own rule has no fill
                         ".btn svg { fill: var(--color-on-accent); }",
                         ".btn-ghost:hover { color: var(--color-text); }",  # another component: no fill
                         ".field input { background: var(--color-field); border-color: var(--color-border-input); }",
                         ".veil { background: color-mix(in srgb, var(--color-surface) 70%, transparent); }",
                         ".row:hover { background: var(--tint-2); }",
                         ".note { background: var(--color-surface); }",  # a comment before it is not its context
                         ".rule { border-color: var(--color-border); }",  # Tailwind's own variable, gone in v4
                         ".chip { @apply bg-surface text-text; }",
                         ":root { --ac: #0e7c86;"):  # the old definitions stay for the hand pass
            self.assertIn(expected, css)
        tsx = self.read("components/Landing.tsx")
        for expected in ('const W = "#fff";',  # used in two roles: never re-pointed
                         'const INK = "var(--color-text)";',  # used as text only
                         'color: active ? "var(--color-text)" : INK',
                         '<path fill="currentColor"', '<Icon c="currentColor" />', '<a href="#fff">',
                         'className="bg-accent text-on-accent"',
                         'className="bg-surface text-text  border-border bg-surface/50"'):
            self.assertIn(expected, tsx)
        self.assertEqual(self.read("app/layout.tsx"), LAYOUT)  # LITERAL: a meta tag takes no var()
        self.assertEqual(self.read("app/manifest.ts"), MANIFEST)
        page = self.read("templates/page.html")
        self.assertIn('content="#0e7c86"', page)
        self.assertIn('ctx.fillStyle = "#ffffff"', page)  # a canvas takes no var()
        self.assertIn('<p style="color: var(--color-text)">', page)
        self.assertRegex(out, r"LITERAL 5")

    def test_a_new_run_starts_from_the_commit(self):
        self.apply()
        changed = json.loads(json.dumps(MAP))
        changed["colours"]["#fff"]["text"] = "--color-text-muted"
        self.map(changed)
        code, out, _ = self.apply()
        self.assertNotIn("KEPT 1", out)
        self.assertIn('color: active ? "var(--color-text-muted)" : INK', self.read("components/Landing.tsx"))
        del changed["colours"]["#fff"]  # a map without it: the committed text comes back, LEFT says where
        self.map(changed)
        code, out, _ = self.apply()
        self.assertEqual(code, 1)
        self.assertIn(".card { background: #fff;", self.read("app/globals.css"))
        self.assertIn("LEFT app/globals.css:3 [.card] background: #fff  (no token for #ffffff as bg)",
                      self.read("forge-work/design/retheme.log"))

    def test_a_file_changed_by_hand_is_kept_until_force(self):
        self.apply()
        css = self.read("app/globals.css") + ".mine { color: red; }\n"
        self.write("app/globals.css", css)
        code, out, _ = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("KEPT app/globals.css", out)
        self.assertEqual(self.read("app/globals.css"), css)
        code, out, _ = self.apply("--force")
        self.assertIn("KEPT 0", out)
        self.assertNotIn(".mine", self.read("app/globals.css"))

    def test_left_until_mapped_or_kept(self):
        partial = json.loads(json.dumps(MAP))
        del partial["colours"]["#C3CCCD"]
        self.map(partial)
        code, out, _ = self.run_it("--map", "forge-work/design/retheme.json")
        self.assertEqual(code, 1)
        self.assertIn("#c3cccd", out)
        partial["keep"] = ["#c3cccd"]
        self.map(partial)
        self.run_it("--map", "forge-work/design/retheme.json")
        self.assertNotIn("#c3cccd", self.read("forge-work/design/retheme.log"))

    def test_a_constant_with_no_known_role_is_not_split(self):
        self.write("components/Swatch.tsx", 'const TONE = "#fff";\nexport const Swatch = () => mix(TONE, 0.2);\n')
        self.git("add", "-A")
        self.git("commit", "-qm", "swatch")
        code, out, _ = self.run_it()
        self.assertIn("SPLIT 1", out)  # W only
        self.assertIn("other(TONE) 1", out)
        partial = json.loads(json.dumps(MAP))
        partial["keep"] = ["rgba(255,255,255,.7)"]
        self.map(partial)
        self.run_it("--map", "forge-work/design/retheme.json")
        self.assertNotIn("veil", self.read("forge-work/design/retheme.log"))  # kept with its alpha

    def test_nothing_left_is_exit_0(self):
        self.write("components/Landing.tsx", TSX.replace('const W = "#fff";', 'const W = "#fff";\nconst T = "#fff";')
                   .replace("color: W", "color: T"))
        self.git("commit", "-qam", "split W")
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out)
        self.assertIn('const W = "var(--color-surface)";', self.read("components/Landing.tsx"))

    def test_classes_only_in_a_tailwind_app(self):
        """Bootstrap has bg-white and text-white too: without Tailwind in the app's CSS they stay, and a
        selector .text-white of the app's own is never a class to map."""
        self.write("app/globals.css", CSS.replace('@import "tailwindcss";\n', "") + ".text-white { color: #fff; }\n")
        self.git("commit", "-qam", "no tailwind")
        self.apply()
        self.assertIn('className="bg-white text-gray-900', self.read("components/Landing.tsx"))
        self.assertIn(".text-white { color: var(--color-text); }", self.read("app/globals.css"))

    def test_line_ends_are_kept(self):
        self.write("app/crlf.css", ".card {\r\n  background: #fff;\r\n}\r\n", newline="")
        self.git("add", "-A")
        self.git("commit", "-qm", "crlf")
        self.apply()
        self.assertEqual(self.read("app/crlf.css"), ".card {\r\n  background: var(--color-surface);\r\n}\r\n")

    def test_could_not_run(self):
        self.write("forge-work/design/retheme.json", "{not json")
        self.assertEqual(self.run_it("--map", "forge-work/design/retheme.json")[0], 2)
        self.map({"colours": {"#fff": ["--color-surface"]}})
        code, _, err = self.run_it("--map", "forge-work/design/retheme.json")
        self.assertEqual(code, 2)
        self.assertIn("The map", err)
        self.map({"colours": {}, "palette": {}})
        self.assertEqual(self.run_it("--map", "forge-work/design/retheme.json")[0], 2)
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        done = subprocess.run([sys.executable, SCRIPT], cwd=outside, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=60)
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("not in a git repository", done.stderr)

    def test_output_survives_a_windows_pipe(self):
        self.write("app/accent.css", ".café { color: #fff; }\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "accent")
        code, out, err = run_cp1252(SCRIPT, cwd=self.root)
        self.assertEqual(code, 0, err)
        self.assertIn("#ffffff", out)

    def test_a_constant_s_roles_count_only_at_its_own_definition(self):
        """One `const color` in a chart once gave every color: of the app the constant's role."""
        self.fresh({"components/Chart.tsx": 'const color = "#8884d8";\n'
                                            "export const C = () => <path stroke={color} />;\n",
                    "app/globals.css": ".card { color: #333333; }\n",
                    "resources/views/a.blade.php": '<div style="color:#333333">x</div>\n'})
        self.map({"colours": {"#333333": {"text": "--color-text", "*": "--color-surface"},
                              "#8884d8": "--color-chart-1"}})
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("app/globals.css"), ".card { color: var(--color-text); }\n")
        self.assertIn('style="color:var(--color-text)"', self.read("resources/views/a.blade.php"))
        self.assertIn('const color = "var(--color-chart-1)";', self.read("components/Chart.tsx"))
        self.assertIn("color: #8884d8 -> var(--color-chart-1)  (icon)", self.read("forge-work/design/retheme.log"))

    def test_a_filled_rule_on_a_file_s_first_line(self):
        self.fresh({"components/Button.module.css": ".btn { background: #0e7c86; color: #fff; }\n"
                                                    ".btn:hover { color: #fff; }\n.btn svg { fill: #fff; }\n"})
        self.map({"colours": {"#0e7c86": "--color-accent", "#fff": {
            "text": "--color-text", "text on-fill": "--color-on-accent",
            "icon": "--color-text", "icon on-fill": "--color-on-accent"}}})
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("components/Button.module.css"),
                         ".btn { background: var(--color-accent); color: var(--color-on-accent); }\n"
                         ".btn:hover { color: var(--color-on-accent); }\n.btn svg { fill: var(--color-on-accent); }\n")
        self.assertIn(":2 [.btn:hover] color:", self.read("forge-work/design/retheme.log"))

    def test_next_s_theme_color_list_stays_literal(self):
        layout = ('export const viewport = {\n  themeColor: [\n'
                  '    { media: "(prefers-color-scheme: light)", color: "#ffffff" },\n'
                  '    { media: "(prefers-color-scheme: dark)", color: "#0b1214" },\n  ],\n};\n'
                  'export const Body = () => <body style={{ color: "#ffffff" }} />;\n')
        self.fresh({"app/layout.tsx": layout})
        self.map({"colours": {"#ffffff": {"text": "--color-text"}, "#0b1214": {"*": "--color-bg"}}})
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("app/layout.tsx"), layout.replace('style={{ color: "#ffffff" }}',
                                                                     'style={{ color: "var(--color-text)" }}'))
        self.assertIn("LITERAL 2", out)

    def test_an_exported_constant_counts_its_uses_in_other_files(self):
        self.fresh({"lib/colors.ts": 'export const WHITE = "#ffffff";\nexport const INK = "#111111";\n'
                                     'export const SPARE = "#eeeeee";\n',
                    "components/A.tsx": 'import { WHITE, INK } from "../lib/colors";\nexport const A = () => (\n'
                                        "  <div style={{ background: WHITE, color: INK }}>\n"
                                        "    <h1 style={{ color: WHITE }}>t</h1></div>);\n",
                    "components/B.tsx": 'import * as colors from "../lib/colors";\n'
                                        "export const B = () => <p style={{ color: colors.INK }} />;\n",
                    "components/Chart.tsx": 'export const color = "#8884d8";\n'
                                            "export const C = () => <path stroke={color} />;\n",
                    "components/Tag.tsx": 'export const Tag = () => <Box bg="gray.100" color="red" />;\n'})
        self.map({"colours": {"#ffffff": {"*": "--color-surface"}, "#111111": {"text": "--color-text"},
                              "#eeeeee": {"*": "--color-border"}, "#8884d8": {"icon": "--color-chart-1"}}})
        code, out, _ = self.apply()
        self.assertEqual(code, 1, out)
        colors = self.read("lib/colors.ts")
        self.assertIn('export const WHITE = "#ffffff";', colors)  # a background and a text elsewhere: never re-pointed
        self.assertIn('export const INK = "var(--color-text)";', colors)
        self.assertIn('export const SPARE = "#eeeeee";', colors)  # exported, its uses unseen: split it by hand
        self.assertIn("SPLIT 2\n", out)
        # Tag.tsx does not import `color`: its color="red" after bg= is no use of the chart's constant
        self.assertIn('export const color = "var(--color-chart-1)";', self.read("components/Chart.tsx"))

    def test_a_rerun_after_the_theme_commit_finds_nothing_old(self):
        css = (theme.START + "\n:root {\n  --color-surface: #f6f7f9;\n  --color-text: #14171c;\n"
               "  --color-tint: color-mix(in srgb, var(--color-text) 6%, transparent);\n}\n" + theme.END + "\n"
               ".card { background: var(--color-surface); color: var(--color-text); }\n")
        self.fresh({"app/globals.css": css})
        code, out, _ = self.run_it()
        self.assertIn("LEFT 0 places", out)
        self.map({"colours": {"#fff": {"bg": "--color-surface"}}})
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("app/globals.css"), css)

    def test_a_selector_is_no_colour_and_a_data_uri_keeps_its_own(self):
        css = ("#fab { position: fixed; }\n#feed, #add:hover { padding: 4px; }\n"
               ".icon { background: url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'>"
               "<path fill='#ffffff' d='M0 0'/></svg>\"); }\n.x { border-color: #ffffff; }\n")
        self.fresh({"app/globals.css": css})
        self.map({"colours": {"#ffffff": {"*": "--color-border", "icon": "currentColor"}}})
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("app/globals.css"), css.replace(".x { border-color: #ffffff;",
                                                                   ".x { border-color: var(--color-border);"))
        log = self.read("forge-work/design/retheme.log")
        for selector in ("#fab", "#feed", "#add"):
            self.assertNotIn(selector, log)
        self.assertIn("LITERAL app/globals.css:3 [] fill: #ffffff", log)

    def test_sass_less_and_js_themes_keep_literal_colours(self):
        """Sass and Less compute with their variables (tint-color, mix) and MUI's createTheme reads its
        values: var() breaks all of them. components.md says what goes there instead."""
        scss = ('$primary: #0d6efd;\n$theme-colors: (\n  "primary": #0d6efd,\n  "light": #f8f9fa\n);\n'
                ".card { background: #ffffff; border-color: mix(#ffffff, #000000, 90%); }\n")
        mui = ('import { createTheme } from "@mui/material/styles";\n'
               'export const theme = createTheme({ palette: { primary: { main: "#0d6efd" } } });\n')
        vue = ('<template><button class="b">x</button></template>\n<script setup>\nconst n = 1;\n</script>\n'
               '<style lang="scss">\n$primary: #0d6efd;\n.b { background: darken($primary, 10%); color: #ffffff; }\n'
               '</style>\n')  # Sass in a component: the same as in a .scss file
        mantine = ('import type { MantineThemeOverride } from "@mantine/core";\n'
                   'export const theme: MantineThemeOverride = { colors: { brand: ["#e6fcf5", "#0d6efd"] } };\n')
        provider = 'export const App = () => <MantineProvider theme={{ colors: { brand: ["#0d6efd"] } }} />;\n'
        self.fresh({"resources/sass/app.scss": scss, "src/theme.ts": mui, "app/site.less": "@brand: #0d6efd;\n",
                    "src/components/B.vue": vue, "src/mantine.ts": mantine, "src/App.tsx": provider})
        self.map({"colours": {"#0d6efd": "--color-accent", "#ffffff": {"*": "--color-surface"}, "#f8f9fa": "--color-bg",
                              "#000000": "--color-text"}})
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("resources/sass/app.scss"),
                         scss.replace(".card { background: #ffffff;", ".card { background: var(--color-surface);"))
        self.assertEqual(self.read("src/theme.ts"), mui)
        self.assertEqual(self.read("app/site.less"), "@brand: #0d6efd;\n")
        self.assertEqual(self.read("src/components/B.vue"),
                         vue.replace("color: #ffffff;", "color: var(--color-surface);"))
        self.assertEqual(self.read("src/mantine.ts"), mantine)
        self.assertEqual(self.read("src/App.tsx"), provider)
        self.assertIn("LITERAL 11", out)

    def test_a_token_that_tokens_json_lacks_is_left(self):
        self.fresh({"app/globals.css": ":root { --r: 8px; }\n.row { background: rgba(20,24,26,.06); "
                                       "color: #ffffff; border-radius: var(--r); }\n"})
        radius = {"--r": "--radius-md"}  # not a colour: tokens.json's colours do not name it, and need not
        white = {"text": "--color-text"}
        self.map({"vars": radius, "colours": {"rgba(20,24,26,.06)": "--tint-1", "#ffffff": white}})
        self.write("forge-work/design/tokens.json", json.dumps({"color": {"text": "#111111", "tint": "x"}}))
        code, out, _ = self.apply()
        self.assertEqual(code, 1, out)
        log = self.read("forge-work/design/retheme.log")
        self.assertIn("--tint-1 is no colour of tokens.json", log)
        self.assertNotIn("--radius-md is no colour", log)
        self.map({"vars": radius, "colours": {"rgba(20,24,26,.06)": "--color-tint", "#ffffff": white}})
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("app/globals.css"), ":root { --r: 8px; }\n.row { background: var(--color-tint); "
                         "color: var(--color-text); border-radius: var(--radius-md); }\n")
        self.write("forge-work/design/tokens.json", "{not json")
        code, _, err = self.run_it("--map", "forge-work/design/retheme.json")
        self.assertEqual(code, 2)
        self.assertIn("tokens.json", err)

    def test_the_map_s_words_its_skip_and_another_log(self):
        self.fresh({"app/globals.css": ".lade { background: #ffffff; }\n.veld input { background: #ffffff; }\n"
                                       ".plain { background: #ffffff; }\n",
                    "components/illustrations/Fish.tsx": 'export const Fish = () => <path fill="#ffffff" />;\n'})
        self.map({"colours": {"#ffffff": {"bg": "--color-surface", "bg float": "--color-raised",
                                          "bg field": "--color-field", "icon": "currentColor"}},
                  "words": {"float": ["lade"], "field": ["veld"]}, "skip": ["components/illustrations/"]})
        code, out, _ = self.apply("--log", "forge-work/other/run.log")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("app/globals.css"), ".lade { background: var(--color-raised); }\n"
                         ".veld input { background: var(--color-field); }\n"
                         ".plain { background: var(--color-surface); }\n")
        self.assertIn('fill="#ffffff"', self.read("components/illustrations/Fish.tsx"))  # skipped
        self.assertIn("(bg float)", self.read("forge-work/other/run.log"))
        self.assertFalse(os.path.exists(os.path.join(self.root, "forge-work", "design", "retheme.log")))

    def test_e_mails_keep_literal_colours_and_pages_about_e_mail_do_not(self):
        """Mail clients drop var(): the button of a sent e-mail would lose its white."""
        mail = ('export const html = (url: string) =>\n  `<a href="${url}" style="background:#0E7C86;color:#fff">Go</a>'
                '<div style="background:#ffffff">x</div>`;\n')
        page = '<p style="color:#ffffff">Check your e-mail</p>\n'
        mails = {"lib/server/mail.ts": mail, "lib/server/accountmails.ts": mail, "lib/mailer.js": mail,
                 "app/views/user_mailer/welcome.html.erb": page, "resources/views/emails/hi.blade.php": page}
        pages = {"resources/views/auth/verify-email.blade.php": page,  # Laravel Breeze's page: no e-mail
                 "components/EmailInput.tsx": 'export const E = () => <input style={{ color: "#ffffff" }} />;\n'}
        self.fresh(dict(mails, **pages))
        self.map({"colours": {"#0e7c86": "--color-accent", "#ffffff": {"*": "--color-text"}}})
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out)
        for path, text in mails.items():
            self.assertEqual(self.read(path), text, path)
        self.assertIn('style="color:var(--color-text)"', self.read("resources/views/auth/verify-email.blade.php"))
        self.assertIn('color: "var(--color-text)"', self.read("components/EmailInput.tsx"))
        self.assertIn("LITERAL 11", out)

    def test_a_rule_nested_in_a_filled_rule_is_on_the_fill(self):
        """CSS nesting and Sass: &:hover and a child of a filled .btn stay light on the accent."""
        css = ".btn { background: #0e7c86; color: #fff; &:hover { color: #fff; } svg { fill: #fff; } }\n"
        scss = (".card {\n  .btn { background: #0e7c86; }\n  p { color: #fff; }\n}\n"  # a sibling's fill is not p's
                "@media (hover: hover) {\n  .chip { background: #0e7c86;\n    &:hover { color: #fff; }\n  }\n}\n")
        self.fresh({"components/Button.module.css": css, "components/Card.module.scss": scss})
        self.map({"colours": {"#0e7c86": "--color-accent", "#fff": {
            "text": "--color-text", "text on-fill": "--color-on-accent",
            "icon": "--color-text", "icon on-fill": "--color-on-accent"}}})
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("components/Button.module.css"),
                         ".btn { background: var(--color-accent); color: var(--color-on-accent); &:hover { color: "
                         "var(--color-on-accent); } svg { fill: var(--color-on-accent); } }\n")
        card = self.read("components/Card.module.scss")
        self.assertIn("p { color: var(--color-text); }", card)
        self.assertIn("&:hover { color: var(--color-on-accent); }", card)

    def test_colours_a_canvas_draws_stay_literal(self):
        """A canvas cannot read var(): Chart.js drew its default grey. Its file's classes still follow the theme."""
        chart = ('import { Chart } from "chart.js/auto";\n'
                 'export const draw = (el) => new Chart(el, { data: { datasets: [{ backgroundColor: "#0e7c86" }] } });'
                 '\nexport const Frame = () => <div className="bg-white">x</div>;\n')
        dots = ('const DOT = "#0e7c86";\nconst BOTH = "#0e7c86";\n'
                "export function paint(ctx) { ctx.fillStyle = DOT; ctx.strokeStyle = BOTH; }\n"
                "export const Key = () => <i style={{ background: BOTH }} />;\n")
        self.fresh({"app/globals.css": '@import "tailwindcss";\n', "components/Chart.tsx": chart,
                    "components/Dots.tsx": dots})
        self.map({"colours": {"#0e7c86": "--color-accent", "white": {"bg": "--color-surface"}}})
        code, out, _ = self.apply()
        self.assertEqual(code, 1, out)  # BOTH: a canvas and a background, so split it by hand
        self.assertEqual(self.read("components/Chart.tsx"), chart.replace("bg-white", "bg-surface"))
        self.assertEqual(self.read("components/Dots.tsx"), dots)
        self.assertRegex(out, r"LITERAL 2\n.*Chart.tsx:2 .*backgroundColor: #0e7c86 .*\n"
                              r".*Dots.tsx:1 .*DOT: #0e7c86  \(literal\)")
        self.assertRegex(out, r"SPLIT 1\n  SPLIT components/Dots.tsx:2 ")

    def test_oklch_and_the_other_colour_functions_count(self):
        """shadcn/ui's Tailwind 4 theme writes the app's palette in oklch()."""
        css = ('@import "tailwindcss";\n:root {\n  --radius: 0.625rem;\n  --background: oklch(1 0 0);\n'
               '  --foreground: oklch(0.145 0 0);\n  --primary: oklch(0.205 0 0);\n  --border: oklch(0.922 0 0);\n}\n'
               '.dark {\n  --background: oklch(0.145 0 0);\n  --border: oklch(1 0 0 / 10%);\n}\n'
               'body { background: var(--background); color: var(--foreground); border-radius: var(--radius); }\n'
               '.btn { background: var(--primary); }\n'
               '.x { border-color: oklch(0.922  0 0); outline-color: color(display-p3 1 0 0);'
               ' fill: lab(50% 40 59); }\n')
        self.fresh({"app/globals.css": css})
        code, out, _ = self.run_it()
        self.assertEqual(code, 0, out)
        for value in ("--background", "--foreground", "--primary", "oklch(0.922 0 0)", "color(display-p3 1 0 0)",
                      "lab(50% 40 59)"):
            self.assertIn("\n  %s " % value, out)
        self.assertNotIn("--radius", out)
        self.map({"vars": {"--background": "--color-bg", "--foreground": "--color-text", "--primary": "--color-accent"},
                  "colours": {"oklch(0.922 0 0)": "--color-border", "color(display-p3 1 0 0)": "--color-danger",
                              "lab(50% 40 59)": "currentColor"}})
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out)
        self.assertIn("body { background: var(--color-bg); color: var(--color-text); border-radius: var(--radius); }\n"
                      ".btn { background: var(--color-accent); }\n.x { border-color: var(--color-border); "
                      "outline-color: var(--color-danger); fill: currentColor; }\n", self.read("app/globals.css"))


if __name__ == "__main__":
    unittest.main()
