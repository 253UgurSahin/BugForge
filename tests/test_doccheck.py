"""Tests for forge/doccheck.py: a report against the template it came from. Every placeholder of every
template the gate reads is found when it is left, in code blocks and over line breaks too, while user code
such as Blade's {{ $name }}, a comment or the Theme block's <role> never counts; a section with only the
template's lines or only a comment has no text of its own; the Cases tables (one per flow too), the specs, a
table's rows and a line that names a file are checked as the gate reads them; any console shows the output."""

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
from test_phasecheck import BUGS, CASES, SPEC, filled, read, write  # noqa: E402

doccheck = load("forge", "doccheck")
SCRIPT = os.path.join(ROOT, "forge", "doccheck.py")
TEMPLATES = [("forge-recon", "recon-map.md"), ("forge-plan", "plan.md"), ("forge-design", "components.md"),
             ("forge-test", "test-plan.md"), ("forge-launch", "launch.md"), ("forge-pack", "templates/static/RUN.md"),
             ("forge-pack", "templates/laravel/RUN.md"), ("forge-pack", "templates/django/RUN.md"),
             ("forge-pack", "templates/next/RUN.md")]


class Report(unittest.TestCase):
    """A temporary project folder; doccheck.py runs in it as if from the project root."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def check(self, text, *args, name="report.md"):
        """Write TEXT as NAME and run doccheck.main on it. Returns (exit code, {what: output}, stdout)."""
        write(self.root, name, text)
        out, err, before = io.StringIO(), io.StringIO(), os.getcwd()
        os.chdir(self.root)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = doccheck.main([name, "--json"] + list(args))
        finally:
            os.chdir(before)
        if code == 2:
            return code, {}, err.getvalue()
        data = json.loads(out.getvalue())
        return code, {item["what"]: item["output"] for item in data["checks"]}, out.getvalue()

    def template(self, folder, name):
        return os.path.join(ROOT, folder, name)


class PlaceholderTests(Report):
    def test_every_placeholder_of_every_template_is_found_when_left(self):
        for folder, name in TEMPLATES:
            path = self.template(folder, name)
            found = doccheck.placeholders(read(path))
            self.assertTrue(found, "%s/%s has no placeholder the gate can find" % (folder, name))
            done = filled(os.path.join(folder, name))
            with self.subTest(template=name):
                self.assertEqual(self.check(done, "--template", path, "--no-sections")[0], 0)
            for placeholder in found:
                with self.subTest(template=name, placeholder=placeholder[:50]):
                    left = done + "\n" + placeholder + "\n"
                    code, checks, out = self.check(left, "--template", path, "--no-sections")
                    self.assertEqual(code, 1, out)
                    self.assertIn("1 placeholder(s)", out)

    def test_a_template_copied_as_it_is_fails_with_every_placeholder(self):
        path = self.template("forge-recon", "recon-map.md")
        code, checks, out = self.check(read(path), "--template", path)
        self.assertEqual(code, 1)
        self.assertIn("report.md still has %d placeholder(s) of ../forge-recon/recon-map.md"
                      % len(doccheck.placeholders(read(path))), out)
        self.assertIn("line 1: {{app}}", out)

    def test_in_code_blocks_and_over_line_breaks_but_not_in_comments(self):
        tpl = "# T\n\n```\nF01 {{goal}}\n```\n\n{{Two or three lines: what the user said,\nwhy.}}\n<!-- {{note}} -->\n"
        write(self.root, "t.md", tpl)
        for text, left in (("# T\n\n```\nF01 {{goal}}\n```\n", "{{goal}}"),
                           ("{{Two or three lines: what the user said, why.}}\n", "{{Two or three lines"),
                           ("{{Two or three\n  lines: what the user said,\r\nwhy.}}\n", "{{Two or three lines"),
                           ("<!-- {{goal}} -->\n", None), ("{{note}}\n", None)):
            with self.subTest(text=text):
                code, checks, out = self.check(text, "--template", "t.md", "--no-sections")
                self.assertEqual(code, 1 if left else 0, out)
                if left:
                    self.assertIn(left, out)

    def test_user_code_is_not_a_placeholder(self):
        write(self.root, "t.md", "Name: {{app name}}\n")
        for text in ("Blade: `{{ $user->name }}`, Django: {{ user.first_name }}\n",
                     "```blade\n<h1>{{$title}}</h1>\n```\n", "~~~tsx\n<div style={{color: 'red'}} />\n~~~\n",
                     "{{ app name }}\n", "{{app}} name\n"):
            with self.subTest(text=text):
                self.assertEqual(self.check(text, "--template", "t.md", "--no-sections")[0], 0)

    def test_angle_placeholders_count_outside_code_only(self):
        """components.md's <...> choices must be filled in, but its ## Theme block maps every token by name
        (`--color-<role>`) and stays as it is (N21); a spec quotes <button> in code."""
        path = self.template("forge-design", "components.md")
        theme = read(path).split("## Theme")[1].split("## Fonts")[0]
        theme = theme.replace("<the theme file for the profile, from forge-design Step 3>", "app/globals.css")
        done = "Profile: next. Tailwind: 4.\nFont: Inter (SIL OFL).\n\n## Theme\n" + theme.replace(
            "<4|3|no>", "4").replace("<the file above>", "app/globals.css") + \
            "\nA `<name>` in code, and `--breakpoint-<name>: <value>px;`.\n```\nButton\n  a11y  real <button>\n```\n"
        code, checks, out = self.check(done, "--template", path, "--no-sections")
        self.assertEqual(code, 0, out)
        code, checks, out = self.check(done + "Font: <name>\n", "--template", path, "--no-sections")
        self.assertEqual(code, 1)
        self.assertIn("<name>", out)

    def test_the_seed_password_stays_a_placeholder_of_the_command(self):
        path = self.template("forge-test", "test-plan.md")
        self.assertNotIn("<the seed password>", doccheck.placeholders(read(path)))

    def test_templates_by_pattern(self):
        for profile in ("static", "next"):
            write(self.root, "templates/%s/RUN.md" % profile, "# Running {{App name}} on %s\n" % profile)
        code, checks, out = self.check("# Running {{App name}}\n", "--template", "templates/*/RUN.md", "--no-sections")
        self.assertEqual(code, 1)
        self.assertIn("1 placeholder(s) of templates/*/RUN.md", out)
        self.assertEqual(self.check("# Running Slotwise\n", "--template", "templates/*/RUN.md", "--no-sections")[0], 0)


class SectionTests(Report):
    TEMPLATE = "# Recon: {{app}}\n\n## Sources\n\n| # | source |\n| --- | --- |\n\n" \
               "## Out of scope (cannot be cloned)\n\n- {{licensed content}}\n\n" \
               "## Screens\n\n| ID | screen |\n| --- | --- |\n| S01 | {{...}} |\n"

    def run_sections(self, text, *args):
        write(self.root, "t.md", self.TEMPLATE)
        return self.check(text, "--template", "t.md", *args)

    def test_each_section_needs_a_line_of_its_own(self):
        own = "# Recon: Calendly\n\n## Sources\n| 1 | help center |\n## Out of scope\n- none seen\n" \
              "## Screens\n| S01 | x |\n"
        code, checks, out = self.run_sections(own)
        self.assertEqual(code, 0, out)
        self.assertIn("report.md has text of its own under ## Sources, ## Out of scope, ## Screens", out)
        only_the_header = own.replace("| 1 | help center |", "| # | source |\n| --- | --- |")
        for text, problem in (
                (only_the_header, "no text of its own under ## Sources"),
                (own.replace("| 1 | help center |", "<!-- later -->"), "no text of its own under ## Sources"),
                (own.replace("## Sources\n| 1 | help center |\n", ""), "has no ## Sources"),
                (own.replace("## Screens", "## Screenshots"), "has no ## Screens"),
                (own.replace("## Screens", "```\n## Screens\n```"), "has no ## Screens"),
                (own.replace("## Sources", "### Sources"), "has no ## Sources")):
            with self.subTest(problem=problem, text=text[-40:]):
                code, checks, out = self.run_sections(text)
                self.assertEqual(code, 1, out)
                self.assertIn(problem, out)

    def test_headings_match_by_their_start_in_any_case(self):
        own = "## sources (3)\n| 1 | help |\n## OUT OF SCOPE\nnone\n## Screens and states\n```\nS01 home\n```\n"
        self.assertEqual(self.run_sections(own)[0], 0)

    def test_named_sections_without_a_template(self):
        report = "# Brand\n## Name checks (screening)\n| check | x |\n## Palette\n\n## Sweep\nexit 0\n"
        code, checks, out = self.check(report, "--section", "Name checks", "--section", "Palette", "--section", "Sweep")
        self.assertEqual(code, 1)
        self.assertIn("report.md has no text of its own under ## Palette", out)
        self.assertIn("the headings of the report in its skill's Output section", out)


class CasesTests(Report):
    def cases(self, text, *args):
        write(self.root, "forge-work/bugs.md", BUGS)
        return self.check(text, "--cases", "forge-work/bugs.md", *args)

    def test_results_in_the_templates_words(self):
        self.assertEqual(self.cases(CASES)[0], 0)
        for row, problem in (("| F09 | | | | | e2e | fail B007 |", "F09: fail B007, but there is no ## B007"),
                             ("| F09 | | | | | e2e | fail |", "F09: fail names no bug"),
                             ("| F09 | | | | | e2e | skipped |", "F09: skipped, but not why"),
                             ("| F09 | | | | | e2e | ok |", "F09: ok"),
                             ("| F09 | | | | | e2e | |", "1 case row(s) without a result: F09")):
            with self.subTest(row=row):
                code, checks, out = self.cases(CASES + row + "\n")
                self.assertEqual(code, 1, out)
                self.assertIn(problem, out)
        for row in ("| F09 | | | | | manual | skipped: no account |", "| F09 | | | | | e2e | Failed B001, B001 |",
                    "| F09 | | | | | e2e | pass (failed first: B004, fixed in 3f2a1c9) |"):
            with self.subTest(row=row):
                self.assertEqual(self.cases(CASES + row + "\n")[0], 0)

    def test_a_table_in_a_code_block_or_only_the_examples_is_not_this_apps(self):
        code, checks, out = self.cases("```\n" + CASES + "```\n")
        self.assertIn("has no Cases table with rows", out)
        path = os.path.join(ROOT, "forge-test", "test-plan.md")
        code, checks, out = self.cases(read(path), "--template", path, "--no-sections")
        self.assertIn("has only the example rows of ../forge-test/test-plan.md", out)

    def test_specs_for_the_cases_marked_e2e(self):
        code, checks, out = self.cases(CASES, "--specs", "e2e/**/*.spec.*")
        self.assertEqual(code, 1)
        self.assertIn("report.md marks 2 case(s) e2e, but there is no file like e2e/**/*.spec.*", out)
        write(self.root, "node_modules/x/e2e/a.spec.ts", SPEC)
        write(self.root, "e2e/node_modules/a.spec.ts", SPEC)
        self.assertEqual(self.cases(CASES, "--specs", "e2e/**/*.spec.*")[0], 1)
        write(self.root, "tests/e2e/booking.spec.ts", SPEC)
        self.assertEqual(self.cases(CASES, "--specs", "e2e/**/*.spec.*", "--specs", "tests/**/*.spec.*")[0], 0)
        code, checks, out = self.cases(CASES.replace("| e2e |", "| unit |"), "--specs", "e2e/**/*.spec.*")
        self.assertEqual(code, 0)
        self.assertIn("marks no case e2e, so it needs no end-to-end spec", out)

    def test_every_cases_table_counts(self):
        """forge-test works per flow, so a plan may keep a Cases table per flow: the rows of each one count."""
        header, first = "".join(CASES.splitlines(True)[:2]), CASES.replace("| e2e |", "| unit |")
        second = "\n### F02 cancel a booking\n\n" + header + "| F02-H1 | cancel | happy | | gone | %s | %s |\n"
        code, checks, out = self.cases(first + second % ("unit", "pass"), "--specs", "e2e/**/*.spec.*")
        self.assertEqual(code, 0, out)
        self.assertIn("report.md has 3 case row(s), each with a result", out)
        for auto, result, problem in (("unit", "", "1 case row(s) without a result: F02-H1"),
                                      ("unit", "fail B099", "F02-H1: fail B099, but there is no ## B099"),
                                      ("e2e", "pass", "marks 1 case(s) e2e, but there is no file like e2e/")):
            with self.subTest(problem=problem):
                code, checks, out = self.cases(first + second % (auto, result), "--specs", "e2e/**/*.spec.*")
                self.assertEqual(code, 1, out)
                self.assertIn(problem, out)


class RowsAndNamesTests(Report):
    def test_a_table_with_rows(self):
        log = "| ID | date | status | what | notes |\n| --- | --- | --- | --- | --- |\n"
        self.assertEqual(self.check(log + "| S01 | 2026-10-27 | done | home | |\n", "--rows", "status,what")[0], 0)
        code, checks, out = self.check(log, "--rows", "status,what")
        self.assertIn("report.md has no table with the columns status and what and a row under them", out)

    def test_a_line_that_names_a_file(self):
        write(self.root, "public/og.png", "png")
        for line in ("- OG image: public/og.png (own)", "- OG image: `public/og.png`, 1200x630",
                     "**OG image:** own, see public/og.png"):
            with self.subTest(line=line):
                self.assertEqual(self.check(line + "\n", "--names", "OG image")[0], 0)
        for line, found in (("- OG image: og.png (own)", "og.png"), ("- OG image: x (own)", "no file name"),
                            ("<!-- OG image: public/og.png -->", "no file name"),
                            ("```\nOG image: public/og.png\n```", "no file name")):
            with self.subTest(line=line):
                code, checks, out = self.check(line + "\n", "--names", "OG image")
                self.assertEqual(code, 1, out)
                self.assertIn("(found: %s)" % found, out)


class CommandLineTests(Report):
    def test_unreadable_files_and_nothing_to_check(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(doccheck.main([os.path.join(self.root, "nowhere.md"), "--section", "x"]), 2)
            self.assertEqual(doccheck.main([SCRIPT, "--template", os.path.join(self.root, "none.md")]), 2)
        self.assertIn("cannot be read", err.getvalue())
        with self.assertRaises(SystemExit) as stop, contextlib.redirect_stderr(io.StringIO()):
            doccheck.main([SCRIPT])
        self.assertEqual(stop.exception.code, 2)
        with open(os.path.join(self.root, "latin.md"), "wb") as handle:
            handle.write(b"## Sources\ncaf\xe9\n")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(doccheck.main([os.path.join(self.root, "latin.md"), "--section", "Sources"]), 2)

    def test_plain_output_on_a_cp1252_pipe(self):
        write(self.root, "t.md", "# Recon: {{app → café}}\n\n## Bronnen ☕\n")
        write(self.root, "report.md", "# Recon: {{app → café}}\n\n## Bronnen ☕\n")
        code, out, err = run_cp1252(SCRIPT, "report.md", "--template", "t.md", cwd=self.root)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("{{app \\u2192 café}}", out)
        self.assertIn("no text of its own under ## Bronnen \\u2615", out)

    def test_plain_output(self):
        write(self.root, "report.md", "# R\n## A\nown\n")
        done = run_cp1252(SCRIPT, "report.md", "--section", "A", "--section", "B", cwd=self.root)
        self.assertEqual(done[0], 1)
        self.assertTrue(re.match(r"FAIL  report.md has no ## B\n      Fill in", done[1]), done[1])


if __name__ == "__main__":
    unittest.main()
