"""Tests for forge-design/theme.py: the theme CSS it writes from tokens.json for plain CSS and for
Tailwind 4, that it follows the mapping in components.md, where --write puts the block, and the
token files it refuses."""

import contextlib
import io
import json
import os
import re
import shutil
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

    def test_dark_theme_nested_names_and_token_objects(self):
        tokens = {"color": {"bg": {"$value": "#ffffff"}, "text": {"muted": {"value": "#5b6470"}},
                            "dark": {"bg": "#0b0d10", "text": {"muted": "#9aa3ad"}}},
                  "space": [2, 6, 8], "pairs": [["text-muted", "bg"]], "_notes": "x", "$schema": "y"}
        code, out, err = run(self.file(tokens), "--tailwind", "no")
        self.assertEqual(code, 0, err)
        self.assertIn("  --color-bg: #ffffff;\n  --color-text-muted: #5b6470;\n", out)
        self.assertIn("@media (prefers-color-scheme: dark) {\n  :root {\n    --color-bg: #0b0d10;\n"
                      "    --color-text-muted: #9aa3ad;\n  }\n}\n", out)
        self.assertNotIn("--color-dark", out)
        self.assertIn("  --space-0_5: 2px;\n  --space-1_5: 6px;\n  --space-2: 8px;\n", out)
        self.assertEqual(out.count(":root {"), 2)  # no second plain block: no motion, layout or size
        self.assertEqual(err, "")

    def file(self, tokens):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        path = os.path.join(folder, "tokens.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(tokens, handle)
        return path

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
