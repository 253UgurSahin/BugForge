"""Tests for forge-design/theme.py: the theme CSS it writes from tokens.json for plain CSS and for
Tailwind 4, that it follows the mapping in components.md, where --write puts the block, and the
token files it refuses."""

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402

theme = load("forge-design", "theme")
TEMPLATE = os.path.join(ROOT, "forge-design", "tokens.json")
COMPONENTS = os.path.join(ROOT, "forge-design", "components.md")


def run(*args):
    """main() with these arguments: (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = theme.main(list(args))
    return code, out.getvalue(), err.getvalue()


def template():
    with open(TEMPLATE, encoding="utf-8") as handle:
        return json.load(handle)


class Folder(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def path(self, name):
        return os.path.join(self.dir, name)

    def write(self, name, data):
        with open(self.path(name), "w", encoding="utf-8", newline="") as handle:
            handle.write(data if isinstance(data, str) else json.dumps(data))
        return self.path(name)

    def read(self, name):
        with open(self.path(name), encoding="utf-8", newline="") as handle:
            return handle.read()


class PlainCss(unittest.TestCase):
    def test_the_template_as_plain_css(self):
        code, out, err = run(TEMPLATE, "--tailwind", "no")
        self.assertEqual(code, 0, err)
        for line in ("  --color-bg: #ffffff;", "  --color-border-input: #868e98;", "  --font-sans: Inter Variable, "
                     "system-ui, -apple-system, Segoe UI, Roboto, sans-serif;", "  --text-base: 16px;",
                     "  --text-base--line-height: 24px;", "  --text-base--font-weight: 400;", "  --space-0: 0px;",
                     "  --space-4: 16px;", "  --space-16: 64px;", "  --radius-pill: 999px;",
                     "  --shadow-pop: 0 12px 32px rgba(16,24,40,.16);", "  --ease-standard: cubic-bezier(.2,.8,.2,1);",
                     "  --duration-fast: 120ms;", "  --layout-content: 1200px;", "  --size-control: 40px;",
                     "/* Breakpoints go into media queries as numbers (var() fails there): sm 640px, md 768px, "
                     "lg 1024px, xl 1280px. */"):
            self.assertIn(line + "\n", out)
        self.assertTrue(out.startswith(theme.START))
        self.assertTrue(out.rstrip().endswith(theme.END))
        self.assertEqual(out.count(":root {"), 2)
        self.assertNotIn("@theme", out)
        self.assertNotIn("prefers-color-scheme", out)  # the template has no dark theme
        self.assertEqual(run(TEMPLATE, "--tailwind", "3")[1], out)  # Tailwind 3 maps these in its config

    def test_it_follows_the_mapping_in_components_md(self):
        """The variable kinds components.md's ## Theme names (--color-, --size-, ...) are the ones
        theme.py writes for the template, with the same parts of a type step."""
        with open(COMPONENTS, encoding="utf-8") as handle:
            mapping = handle.read().split("## Theme", 1)[1].split("```css", 1)[1].split("```", 1)[0]
        out = run(TEMPLATE, "--tailwind", "no")[1]
        kinds = [set(re.findall(r"^\s*--([a-z]+)-", text, re.M)) for text in (mapping, out)]
        self.assertEqual(kinds[0], kinds[1])
        self.assertIn("size", kinds[1])
        for part in ("--line-height:", "--font-weight:", "--ease-standard:", "--duration-fast:"):
            self.assertIn(part, mapping)
            self.assertIn(part, out)

    def test_the_switch_in_components_md_is_the_one_theme_py_writes(self):
        """The rules of components.md's ## Theme block are those theme.py writes for a dark group (--default
        system), and the selector its comment names for --default light or dark is theirs: no drift."""
        with open(COMPONENTS, encoding="utf-8") as handle:
            mapping = handle.read().split("## Theme", 1)[1].split("```css", 1)[1].split("```", 1)[0]
        def selectors(css):
            return re.findall(r"^\s*([:@][^{]*?)\s*\{", re.sub(r"/\*.*?\*/", "", css, flags=re.S), re.M)
        tokens = self.file(SWITCHED)
        self.assertEqual(selectors(mapping), selectors(run(tokens, "--tailwind", "no")[1]))
        named = re.search(r"--default light or dark: (:root\S+) \*/", mapping).group(1)
        for default in ("light", "dark"):
            out = run(tokens, "--tailwind", "no", "--default", default)[1]
            self.assertIn("@media (prefers-color-scheme: dark) {\n  %s {\n" % named, out)

    def test_dark_theme_nested_names_and_token_objects(self):
        tokens = {"color": {"bg": {"$value": "#ffffff"}, "text": {"muted": {"value": "#5b6470"}},
                            "dark": {"bg": "#0b0d10", "text": {"muted": "#9aa3ad"}}},
                  "space": [2, 6, 8], "pairs": [["text-muted", "bg"]], "_notes": "x", "$schema": "y"}
        code, out, err = run(self.file(tokens), "--tailwind", "no")
        self.assertEqual(code, 0, err)
        self.assertIn("  --color-bg: #ffffff;\n  --color-text-muted: #5b6470;\n", out)
        self.assertIn('@media (prefers-color-scheme: dark) {\n  :root:not([data-theme="light"]) {\n'
                      "    color-scheme: dark;\n    --color-bg: #0b0d10;\n    --color-text-muted: #9aa3ad;\n  }\n}\n", out)
        self.assertNotIn("--color-dark", out)
        self.assertIn("  --space-0_5: 2px;\n  --space-1_5: 6px;\n  --space-2: 8px;\n", out)
        self.assertEqual(out.count(":root {"), 2)  # the colours, then color-scheme: light (no motion, layout, size)
        self.assertIn(":root {\n  color-scheme: light;\n}\n", out)
        self.assertEqual(run(self.file(tokens), "--tailwind", "no", "--default", "system")[1], out)  # the default
        self.assertEqual(err, "")

    def file(self, tokens):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        path = os.path.join(folder, "tokens.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(tokens, handle)
        return path

    def test_font_names_get_quotes_where_they_need_them(self):
        """Unquoted, a name with a word that starts with a digit (Source Serif 4) makes the browser drop the
        whole stack. Names of identifiers, generic families, quoted names and var() stay as they are."""
        tokens = template()
        tokens["font"] = {"serif": "Source Serif 4, Georgia, serif", "display": "Exo  2,M PLUS 1p , cursive",
                          "sans": "Inter Variable, system-ui, -apple-system, Segoe UI, Café Sans, sans-serif",
                          "next": "var(--font-inter), system-ui, sans-serif", "size": 16,
                          "brand": "'Baloo 2', \"Noto Sans JP\", var(--font-brand, Fira Sans), monospace"}
        code, out, err = run(self.file(tokens), "--tailwind", "no")
        self.assertEqual(code, 0, err)
        for line in ('--font-serif: "Source Serif 4", Georgia, serif;',
                     '--font-display: "Exo 2", "M PLUS 1p", cursive;',
                     "--font-sans: Inter Variable, system-ui, -apple-system, Segoe UI, Café Sans, sans-serif;",
                     "--font-next: var(--font-inter), system-ui, sans-serif;", "--font-size: 16px;",
                     "--font-brand: 'Baloo 2', \"Noto Sans JP\", var(--font-brand, Fira Sans), monospace;"):
            self.assertIn("\n  %s\n" % line, out)

    def test_older_files_and_unknown_groups(self):
        tokens = template()
        for group in ("size", "motion", "layout", "breakpoint", "shadow"):
            del tokens[group]
        tokens["opacity"] = {"muted": 0.6}
        code, out, err = run(self.file(tokens), "--tailwind", "no")
        self.assertEqual(code, 0, err)
        self.assertEqual(out.count(":root {"), 1)
        self.assertIn("opacity", err)
        self.assertIn("not in the theme", err)


class Tailwind4(unittest.TestCase):
    def test_theme_static_with_only_our_colours_and_breakpoints(self):
        code, out, err = run(TEMPLATE, "--tailwind", "4")
        self.assertEqual(code, 0, err)
        first = out.split("@theme static {\n", 1)[1].split("}\n", 1)[0]
        self.assertTrue(first.startswith("  --color-*: initial;\n  --color-bg: #ffffff;\n"))
        self.assertIn("  --breakpoint-*: initial;\n  --breakpoint-sm: 640px;\n  --breakpoint-md: 768px;\n", first)
        self.assertIn("  --text-xl: 28px;\n", first)
        self.assertNotIn("--space-", out)  # Tailwind's own --spacing does that
        self.assertNotIn("Breakpoints go into media queries", out)
        plain = out.split("@theme static {", 1)[1].split(":root {\n", 1)[1]
        self.assertIn("  --duration-base: 200ms;\n  --layout-content: 1200px;\n", plain)
        self.assertIn("  --size-ring: 2px;\n", plain)


SWITCHED = {"color": {"bg": "#ffffff", "text": "#111111", "accent": "#0e7c86",
                      "tint": "color-mix(in srgb, var(--color-text) 5%, transparent)",
                      "dark": {"bg": "#040b0d", "text": "#e6eef0"}},
            "space": [4, 16], "motion": {"fast": "120ms"}}


def matches(rule, theme, marks):
    """Does the selector RULE (as theme.py writes them) match <html data-theme=THEME class=MARKS>? A :not() with a
    list matches when none of its parts do: :root:not([data-theme="light"], [data-theme="system"])."""
    if rule == "@theme static":
        return True
    def hit(part):  # [data-theme="dark"] or .dark
        attribute = re.match(r'\[[\w-]+="([^"]*)"\]\Z', part)
        return theme == attribute.group(1) if attribute else part[1:] in marks
    simple = r'(?:\[[\w-]+="[^"]*"\]|\.[\w-]+)'
    for negated, group in re.findall(r"(:not\(|)(%s(?:, %s)*)\)?" % (simple, simple), rule[len(":root"):]):
        if (any if negated else lambda hits: not all(hits))([hit(part) for part in group.split(", ")]):
            return False
    return rule.startswith((":root", "@theme"))


def cascade(css, theme=None, device="light", marks=()):
    """What <html> gets from CSS with this data-theme (None: none) and classes on a device that prefers DEVICE:
    the rule outside a layer beats @theme (Tailwind's layer), then the higher specificity, then the later rule."""
    found, stack = {}, []
    for order, line in enumerate(line.strip() for line in css.split("\n")):
        if line.endswith("{"):
            stack.append(line[:-1].strip())
        elif line == "}":
            stack.pop()
        elif stack and re.match(r"(--[\w-]+|color-scheme):", line):
            name, item = line.rstrip(";").split(":", 1)
            rule = stack[-1]
            if any("prefers-color-scheme: %s)" % device not in outer for outer in stack[:-1]):
                continue
            weight = (rule != "@theme static", 1 + len(re.findall(r"\[|\.", rule)), order)
            if matches(rule, theme, marks) and weight >= found.get(name, ((), ""))[0]:
                found[name] = (weight, item.strip())
    return {name: item for name, (_, item) in found.items()}


class ThemeSwitch(unittest.TestCase):
    """design Step 3: the app's switch (data-theme light, dark or system on <html>) or its own selector decides,
    the device only where the user left it to the device, and the concept's default while nothing is set."""

    def css(self, *args):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        path = os.path.join(folder, "tokens.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(SWITCHED, handle)
        code, out, err = run(path, *args)
        self.assertEqual((code, err), (0, ""))
        return out

    def assert_shows(self, css, table, marks=()):
        """TABLE: {data-theme: (theme on a light device, theme on a dark device)}."""
        for theme, shown in table.items():
            for device, want in zip(("light", "dark"), shown):
                with self.subTest(theme=theme, device=device, marks=marks):
                    got = cascade(css, theme, device, marks)
                    self.assertEqual(got["color-scheme"], want)
                    self.assertEqual(got["--color-bg"], "#040b0d" if want == "dark" else "#ffffff")
                    self.assertEqual(got["--color-text"], "#e6eef0" if want == "dark" else "#111111")
                    self.assertEqual(got["--color-accent"], "#0e7c86")  # no dark value: the same in both
                    self.assertEqual(got["--color-tint"], SWITCHED["color"]["tint"])  # mixes the shown text

    def test_each_default_with_tailwind_4_and_without(self):
        light, dark, device = ("light", "light"), ("dark", "dark"), ("light", "dark")
        for tailwind in ("no", "4"):
            css = self.css("--tailwind", tailwind)
            self.assertEqual(css, self.css("--tailwind", tailwind, "--default", "system"))
            self.assert_shows(css, {None: device, "system": device, "light": light, "dark": dark})
            self.assert_shows(self.css("--tailwind", tailwind, "--default", "light"),
                              {None: light, "system": device, "light": light, "dark": dark})
            self.assert_shows(self.css("--tailwind", tailwind, "--default", "dark"),
                              {None: dark, "system": device, "light": light, "dark": dark})

    def test_the_apps_own_selector_decides_alone(self):
        for selector in (".dark", '[data-mode="dark"]'):
            css = self.css("--tailwind", "4", "--dark-selector", selector)
            self.assertIn(":root%s {\n  color-scheme: dark;\n  --color-bg: #040b0d;\n" % selector, css)
            self.assertNotIn("prefers-color-scheme", css)
            self.assertNotIn("data-theme", css)
        css = self.css("--tailwind", "no", "--dark-selector", ".dark")
        self.assert_shows(css, {None: ("light", "light"), "dark": ("light", "light")})  # data-theme means nothing
        self.assert_shows(css, {None: ("dark", "dark")}, marks=("dark",))

    def test_the_dark_default_writes_only_dark_values(self):
        """--default dark: the dark colours where data-theme is neither light nor system, and for system while
        the device is dark; the light ones are never written twice."""
        css = self.css("--tailwind", "no", "--default", "dark")
        self.assertIn('\n:root:not([data-theme="light"], [data-theme="system"]) {\n  color-scheme: dark;\n'
                      "  --color-bg: #040b0d;\n  --color-text: #e6eef0;\n}\n", css)
        self.assertIn('@media (prefers-color-scheme: dark) {\n  :root[data-theme="system"] {\n', css)
        self.assertNotIn("prefers-color-scheme: light", css)
        self.assertEqual(css.count("--color-bg: #ffffff;"), 1)

    def variant(self, css):
        """The two selectors of Tailwind 4's @custom-variant dark that theme.py wrote: (while the device is dark, always)."""
        found = re.search(r"\n@custom-variant dark \{\n  @media \(prefers-color-scheme: dark\) \{ &:where\((.+), \1 \*\) "
                          r"\{ @slot; \} \}\n  &:where\((.+), \2 \*\) \{ @slot; \}\n\}\n", css)
        self.assertTrue(found, css)
        return found.groups()

    def test_tailwinds_dark_variant_follows_the_same_switch(self):
        """With Tailwind, the app's own dark: classes (a logo swap, dark:invert) show exactly where the dark colours
        do; Tailwind 3 gets the same two selectors as its darkMode line for tailwind.config.js."""
        for default in ("system", "light", "dark"):
            css = self.css("--tailwind", "4", "--default", default)
            media, always = self.variant(css)
            for theme in (None, "system", "light", "dark"):
                for device in ("light", "dark"):
                    with self.subTest(default=default, theme=theme, device=device):
                        dark = (device == "dark" and matches(media, theme, ())) or matches(always, theme, ())
                        self.assertEqual(dark, cascade(css, theme, device)["color-scheme"] == "dark")
            three = self.css("--tailwind", "3", "--default", default)
            self.assertIn("darkMode: ['variant', ['@media (prefers-color-scheme: dark) { &:where(%s, %s *) }', "
                          "'&:where(%s, %s *)']] */\n" % (media, media, always, always), three)
            self.assertNotIn("@custom-variant", three)
        self.assertNotIn("darkMode", self.css("--tailwind", "4"))
        for args in (("--tailwind", "no"), ("--tailwind", "4", "--dark-selector", ".dark")):  # no dark: classes,
            css = self.css(*args)  # or the app's own switch, which has its own variant
            self.assertNotIn("@custom-variant", css)
            self.assertNotIn("darkMode", css)

    def test_bad_or_clashing_switch_options_and_no_dark_group(self):
        for args in (("--dark-selector", ".dark { x"), ("--dark-selector", "html.dark"),
                     ("--default", "dark", "--dark-selector", ".dark"), ("--default", "dim")):
            with self.subTest(args=args), self.assertRaises(SystemExit) as stop:
                run(TEMPLATE, "--tailwind", "no", *args)
            self.assertEqual(stop.exception.code, 2)
        code, out, err = run(TEMPLATE, "--tailwind", "no", "--default", "dark")
        self.assertEqual(code, 0)
        self.assertIn("it has none", err)
        self.assertNotIn("color-scheme", out)  # no dark group: nothing to switch
        # components.md's command line carries --default system: with no dark group it does nothing, quietly
        self.assertEqual(run(TEMPLATE, "--tailwind", "4", "--default", "system"), (0, run(TEMPLATE, "--tailwind", "4")[1], ""))


class TypeAndFonts(unittest.TestCase):
    def test_stretch_tracking_and_a_number_in_the_font_group(self):
        tokens = template()
        tokens["type"]["num"] = {"size": 44, "line": 44, "weight": 840, "stretch": 125, "tracking": "-0.02em"}
        tokens["type"]["label"] = {"size": 12, "line": 16, "weight": 640, "stretch": "condensed", "tracking": 0.07}
        tokens["font"]["stretch-wide"] = "125%"
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        path = os.path.join(folder, "tokens.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(tokens, handle)
        code, out, err = run(path, "--tailwind", "4")
        self.assertEqual(code, 0, err)
        for line in ("--text-num--font-stretch: 125%;", "--text-num--letter-spacing: -0.02em;",
                     "--text-label--font-stretch: condensed;", "--text-label--letter-spacing: 0.07em;",
                     "--font-stretch-wide: 125%;"):
            self.assertIn("\n  %s\n" % line, out)
        self.assertNotIn("--text-base--font-stretch", out)  # only the steps that have one


class Formats(Folder):
    def test_scss_holds_the_same_values_as_sass_variables(self):
        tokens = dict(SWITCHED, breakpoint={"md": 768}, type={"base": {"size": 16, "line": 24, "weight": 400}},
                      font={"sans": "Source Serif 4, serif"})
        code, out, err = run(self.write("tokens.json", tokens), "--format", "scss")
        self.assertEqual(code, 0, err)
        for line in ("$color-bg: #ffffff;", "$color-dark-bg: #040b0d;", "$space-4: 16px;", "$duration-fast: 120ms;",
                     "$text-base--line-height: 24px;", '$font-sans: "Source Serif 4", serif;', "$breakpoint-md: 768px;"):
            self.assertIn("\n%s\n" % line, out)
        self.assertNotIn("{", out.replace(theme.START, "").replace(theme.END, ""))  # no rules: values only
        target = self.path("_tokens.scss")
        self.assertEqual(run(self.write("tokens.json", tokens), "--tailwind", "4", "--write", target)[0], 0)
        self.assertEqual(self.read("_tokens.scss"), out)  # the extension picks scss; --tailwind changes nothing

    def test_js_is_a_module_of_the_tokens_with_literal_values(self):
        tokens = dict(template(), font={"sans": "Source Serif 4, serif", "_note": "x"})
        target = self.path(os.path.join("src", "theme", "tokens.ts"))
        code, out, err = run(self.write("tokens.json", tokens), "--write", target)
        self.assertEqual(code, 0, err)
        self.assertIn("(js)", out)
        text = self.read(os.path.join("src", "theme", "tokens.ts"))
        self.assertTrue(text.startswith(theme.START + "\nexport const tokens = {"))
        data = json.loads(text.split("export const tokens = ", 1)[1].rsplit(";", 1)[0])
        self.assertEqual(data["color"]["accent"], "#3f4856")
        self.assertEqual(data["radius"]["md"], 10)  # a number stays a number: MUI's shape.borderRadius
        self.assertEqual(data["font"], {"sans": '"Source Serif 4", serif'})
        self.assertNotIn("pairs", data)
        self.assertFalse([key for key in data if key.startswith("_")])
        if shutil.which("node"):
            module = self.write("check.mjs", text)
            done = subprocess.run(["node", "--check", module], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True, timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_colour_that_names_another_is_its_value_in_sass_and_js(self):
        """The template's chart-1 is var(--color-accent): Sass's mix() and MUI's alpha() cannot compute with a var(),
        so scss and js write the accent's value, the dark group's own in the dark group (components.md's
        tokens.color.dark.bg). A chain is followed to its end (link names chart-1, which names the accent); one
        that names no token, or a loop, stays a var() and the run still ends."""
        color = dict(SWITCHED["color"], **{"chart-1": "var(--color-accent)", "chart-9": "var(--color-brand)",
                                           "link": "var(--color-chart-1)", "loop-a": "var(--color-loop-b)",
                                           "loop-b": "var(--color-loop-a)"})
        color["dark"] = dict(color["dark"], **{"accent": "#5fd0da", "chart-1": "var(--color-accent)",
                                               "link": "var(--color-chart-1)"})
        tokens = self.write("tokens.json", dict(SWITCHED, color=color))
        code, out, err = run(tokens, "--format", "scss")
        self.assertEqual(code, 0, err)
        for line in ("$color-chart-1: #0e7c86;", "$color-dark-chart-1: #5fd0da;", "$color-chart-9: var(--color-brand);",
                     "$color-tint: color-mix(in srgb, #111111 5%, transparent);", "$color-link: #0e7c86;",
                     "$color-dark-link: #5fd0da;"):
            self.assertIn("\n%s\n" % line, out)
        self.assertRegex(out, r"\n\$color-loop-a: var\(--color-loop-[ab]\);\n")
        code, out, err = run(tokens, "--format", "js")
        self.assertEqual(code, 0, err)
        data = json.loads(out.split("export const tokens = ", 1)[1].rsplit(";", 1)[0])
        self.assertEqual((data["color"]["chart-1"], data["color"]["dark"]["chart-1"]), ("#0e7c86", "#5fd0da"))
        self.assertEqual((data["color"]["link"], data["color"]["dark"]["link"]), ("#0e7c86", "#5fd0da"))
        self.assertEqual(data["color"]["dark"]["bg"], "#040b0d")
        self.assertEqual(data["color"]["chart-9"], "var(--color-brand)")
        self.assertEqual(data["space"], [4, 16])
        self.assertNotIn("var(--color-accent)", out)

    def test_scss_goes_below_the_use_and_import_lines(self):
        """A Sass partial starts with @use (it must come first) and @import: the block goes below them."""
        target = self.write("_tokens.scss", '@use "sass:math";\n@import "bootstrap/scss/functions";\n\n'
                                            "$spacer: 1rem;\n")
        self.assertEqual(run(self.write("tokens.json", SWITCHED), "--write", target)[0], 0)
        text = self.read("_tokens.scss")
        self.assertTrue(text.startswith('@use "sass:math";\n@import "bootstrap/scss/functions";\n\n' + theme.START), text)
        self.assertTrue(text.endswith(theme.END + "\n\n$spacer: 1rem;\n"), text)
        self.assertIn("\n$color-dark-bg: #040b0d;\n", text)
        self.assertEqual(run(self.write("tokens.json", SWITCHED), "--write", target)[0], 0)
        self.assertEqual(self.read("_tokens.scss"), text)  # written again in its place, not twice

    def test_css_still_needs_the_tailwind_line(self):
        with self.assertRaises(SystemExit):
            run(TEMPLATE, "--write", self.path("app.css"))


class WriteTests(Folder):
    def test_a_new_file_and_writing_again(self):
        target = os.path.join(self.dir, "static", "css", "tokens.css")
        code, out, err = run(TEMPLATE, "--tailwind", "no", "--write", target)
        self.assertEqual(code, 0, err)
        self.assertIn("Wrote", out)
        first = self.read(os.path.join("static", "css", "tokens.css"))
        self.assertTrue(first.startswith(theme.START))
        self.assertEqual(run(TEMPLATE, "--tailwind", "no", "--write", target)[0], 0)
        self.assertEqual(self.read(os.path.join("static", "css", "tokens.css")), first)  # the same, not twice

    def test_the_block_goes_after_the_imports_and_replaces_itself(self):
        css = ('@charset "utf-8";\n/* the app */\n@import "tailwindcss";\n@source "../views";\n'
               '@custom-variant dark (&:where(.dark, .dark *));\n\nbody { margin: 0; }\n')
        target = self.write("app.css", css)
        self.assertEqual(run(TEMPLATE, "--tailwind", "4", "--write", target)[0], 0)
        text = self.read("app.css")
        self.assertLess(text.index("@custom-variant"), text.index(theme.START))
        self.assertLess(text.index(theme.END), text.index("body { margin: 0; }"))
        tokens = template()
        tokens["color"]["accent"] = "#1b5c96"
        self.assertEqual(run(self.write("tokens.json", tokens), "--tailwind", "4", "--write", target)[0], 0)
        again = self.read("app.css")
        self.assertEqual(again.count(theme.START), 1)
        self.assertIn("--color-accent: #1b5c96;", again)
        self.assertNotIn("#3f4856", again)
        self.assertTrue(again.endswith("body { margin: 0; }\n"))

    def test_a_rule_at_the_top_stays_outside_the_block(self):
        """create-vite's CSS starts with :root {. The block goes before that rule, never inside it (there
        it is :root :root, which matches nothing), and after a statement only when its line holds no more."""
        vite = ":root {\n  --text: #6b6375;\n}\n"
        for top in ("", '@import "x.css"; ', "/* the app */ "):
            with self.subTest(top=top):
                target = self.write("style.css", top + vite)
                self.assertEqual(run(TEMPLATE, "--tailwind", "no", "--write", target)[0], 0)
                text = self.read("style.css")
                self.assertEqual(text.index(theme.START), len(top.rstrip()) + 1 if top else 0)
                self.assertLess(text.index(theme.END), text.index(vite))
                self.assertTrue(text.endswith(vite))  # the scaffold's rule is whole
                self.assertEqual(run(TEMPLATE, "--tailwind", "no", "--write", target)[0], 0)
                self.assertEqual(self.read("style.css"), text)  # the block is replaced where it is

    def test_a_semicolon_or_a_brace_in_an_imports_url_is_no_end(self):
        """Google Fonts URLs hold a ; (wght@400;700), quoted or not, and a file name may hold a brace: the
        @import ends at its own ;, so the block goes below the whole line, never inside the URL."""
        vite = ":root {\n  --text: #6b6375;\n}\n"
        for line in ("@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');",
                     "@import url(https://fonts.googleapis.com/css2?family=Inter:wght@400;700);",
                     '@import "theme-{v1}.css";'):
            with self.subTest(line=line):
                target = self.write("style.css", line + "\n" + vite)
                self.assertEqual(run(TEMPLATE, "--tailwind", "no", "--write", target)[0], 0)
                text = self.read("style.css")
                self.assertTrue(text.startswith(line + "\n\n" + theme.START), text[:200])
                self.assertTrue(text.endswith(vite))

    def test_the_scaffolds_own_theme_values_are_named(self):
        """Laravel's app.css sets --font-sans in its own @theme after the imports: it would win."""
        target = self.write("app.css", "@import 'tailwindcss';\n@source '../**/*.blade.php';\n\n@theme {\n"
                                       "    --font-sans: 'Instrument Sans', ui-sans-serif, sans-serif;\n}\n")
        code, out, err = run(TEMPLATE, "--tailwind", "4", "--write", target)
        self.assertEqual(code, 0, err)
        self.assertIn("also sets --font-sans outside the forge theme block", err)
        text = self.read("app.css")
        self.assertIn("@source '../**/*.blade.php';\n\n" + theme.START, text)
        self.assertIn(theme.END + "\n\n@theme {", text)  # one blank line around the block, not two

    def test_windows_line_endings_stay(self):
        target = self.write("style.css", "@import 'x.css';\r\nbody { margin: 0; }\r\n")
        self.assertEqual(run(TEMPLATE, "--tailwind", "no", "--write", target)[0], 0)
        text = self.read("style.css")
        self.assertNotIn("\n", text.replace("\r\n", ""))

    def test_one_mark_without_the_other_is_refused(self):
        target = self.write("style.css", theme.START + "\n:root { --color-bg: red; }\n")
        code, _, err = run(TEMPLATE, "--tailwind", "no", "--write", target)
        self.assertEqual(code, 2)
        self.assertIn("only one of the theme marks", err)
        self.assertEqual(self.read("style.css"), theme.START + "\n:root { --color-bg: red; }\n")


class BadInput(Folder):
    def test_bad_token_files_exit_2(self):
        def changed(**groups):
            tokens = template()
            tokens.update(groups)
            return tokens
        cases = [
            (os.path.join(self.dir, "missing.json"), "not a file that exists"),
            (self.write("broken.json", '{"color": {"bg": "#fff"\n "x": 1}}'), "not valid JSON (line 2"),
            (self.write("list.json", [1, 2]), "JSON object"),
            (self.write("a.json", changed(type={"sm": {"size": 14, "line": 20}})), "type.sm needs size, line and weight"),
            (self.write("b.json", changed(shadow={"card": "0 1px red; } body { display: none"})), "shadow.card"),
            (self.write("c.json", changed(radius={"big round": 8})), "radius.big round: a name"),
            (self.write("d.json", changed(color={"bg": ["#fff"]})), "color.bg must be a value"),
            (self.write("e.json", changed(space={"sm": 4})), "space must be a list of numbers"),
            (self.write("f.json", changed(radius={"sm": True})), "radius.sm must be a value"),
            (self.write("g.json", changed(font="Inter")), "font must be a group"),
        ]
        for path, words in cases:
            with self.subTest(path=os.path.basename(path)):
                code, out, err = run(path, "--tailwind", "no")
                self.assertEqual((code, out), (2, ""))
                self.assertIn(words, err)

    def test_tailwind_is_needed(self):
        with self.assertRaises(SystemExit):
            run(TEMPLATE)

    def test_a_cp1252_pipe_gets_escapes_not_a_crash(self):
        tokens = template()
        tokens["font"]["sans"] = "Café → Sans, sans-serif"
        code, out, err = run_cp1252(os.path.join(ROOT, "forge-design", "theme.py"), self.write("t.json", tokens),
                                    "--tailwind", "no")
        self.assertEqual(code, 0, err)
        self.assertIn("--font-sans: Café \\u2192 Sans, sans-serif;", out)


if __name__ == "__main__":
    unittest.main()
