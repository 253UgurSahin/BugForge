"""Tests for forge-dashboard/dashcheck.py: each rule on the ## Numbers table fires and does not fire,
the exit codes 0, 1 and 2, the JSON shape, and that a table it cannot read is never a pass."""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402

dashcheck = load("forge-dashboard", "dashcheck")
SCRIPT = os.path.join(ROOT, "forge-dashboard", "dashcheck.py")
HEADER = "| number | definition | source | unit | period | compared with | form |\n| --- | --- | --- | --- | --- | --- | --- |\n"
GOOD = [
    "| Revenue | paid orders, refunds taken off | `orders` where status = paid | EUR | this month | last month | tile + line |",
    "| Orders | orders placed | `orders`, count | orders | this month | last month | tile |",
    "| Error rate | failed requests of all requests | `requests` where status >= 500 | % | 24 h | yesterday | tile + sparkline |",
]


def page(rows, before="", after="\n## Layout\n\nA 12 column grid.\n"):
    return "# Dashboard\n\n## Audience\n\nThe owner, daily.\n\n## Numbers\n\n%s%s%s\n%s" % (
        before, HEADER, "\n".join(rows), after)


def row(number="Visits", definition="page views by people", source="`visits`, count", unit="visits",
        period="this week", compared="last week", form="tile"):
    return "| %s | %s | %s | %s | %s | %s | %s |" % (number, definition, source, unit, period, compared, form)


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = dashcheck.main(list(args))
    return code, out.getvalue(), err.getvalue()


class DashCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)

    def write(self, text, name="dashboard.md", raw=None):
        path = os.path.join(self.folder, name)
        with open(path, "wb") as handle:
            handle.write(raw if raw is not None else text.encode("utf-8"))
        return path

    def check(self, rows, *more, **parts):
        """(exit code, report) for a dashboard.md with these rows."""
        code, out, err = run(self.write(page(rows, **parts)), "--json", *more)
        self.assertIn(code, (0, 1), err)
        return code, json.loads(out)

    def rules(self, rows, **parts):
        return [(item["rule"], item["severity"]) for item in self.check(rows, **parts)[1]["findings"]]


class Rules(DashCase):
    def test_a_good_table_passes(self):
        code, report = self.check(GOOD)
        self.assertEqual((code, report["findings"]), (0, []))
        self.assertEqual(report["summary"], {"critical": 0, "high": 0, "medium": 0, "low": 0, "numbers": 3,
                                             "fail_on": "high", "failed": False})

    def test_no_definition_no_source_no_unit(self):
        for empty in ("", "-", "?", "TBD", "todo", "n/a", "<what is counted>", "--"):
            with self.subTest(empty=empty):
                self.assertEqual(self.rules([row(definition=empty)]), [("no-definition", "high")])
                self.assertEqual(self.rules([row(source=empty)]), [("no-source", "high")])
                self.assertEqual(self.rules([row(unit=empty)]), [("no-unit", "medium")])
        self.assertEqual(self.rules([row(period="-", compared="-")]), [], "only definition, source and unit are required")

    def test_a_missing_unit_alone_does_not_fail_by_default(self):
        self.assertEqual(self.check([row(unit="")])[0], 0)
        self.assertEqual(self.check([row(unit="")], "--fail-on", "medium")[0], 1)
        self.assertEqual(self.check([row(unit="")], "--fail-on", "low")[0], 1)
        self.assertEqual(self.check([row(definition="")], "--fail-on", "critical")[0], 0)
        self.assertEqual(self.check([row(definition="")])[0], 1)

    def test_invented_sources(self):
        for source in ("sample data", "fake numbers for the demo", "lorem", "Math.random()", "random values",
                       "dummy rows", "mocked", "mock API", "placeholder", "made up", "made-up", "hardcoded array",
                       "hard-coded", "SAMPLE"):
            with self.subTest(source=source):
                self.assertEqual(self.rules([row(source=source)]), [("invented-source", "high")])
                self.assertEqual(self.check([row(source=source)])[0], 1)

    def test_real_and_seed_sources_are_fine(self):
        for source in ("`orders`, sum(total_cents)", "seed data (labelled as seed on screen)", "`samples` table, count",
                       "`randomised_trials`", "`mockups` where published", "the `examples` table"):
            with self.subTest(source=source):
                self.assertEqual(self.rules([row(source=source)]), [])

    def test_more_than_nine_numbers(self):
        nine = [row(number="N%d" % index) for index in range(9)]
        self.assertEqual(self.rules(nine), [])
        code, report = self.check(nine + [row(number="N9")])
        self.assertEqual([(item["rule"], item["severity"]) for item in report["findings"]], [("too-many-numbers", "medium")])
        self.assertEqual(code, 0)
        self.assertIn("10 numbers", report["findings"][0]["what"])

    def test_pie_and_donut_over_five_parts(self):
        for form in ("pie (7 parts)", "donut, 6 slices", "Doughnut with 12 categories", "pie 6 segments"):
            with self.subTest(form=form):
                findings = self.check([row(form=form)])[1]["findings"]
                self.assertEqual([item["rule"] for item in findings], ["form-pie-parts"])
                self.assertIn("bar chart", findings[0]["fix"])
        for form in ("donut (4 parts)", "pie, 5 slices", "donut", "bar (12 categories)", "piece chart 9 parts"):
            with self.subTest(form=form):
                self.assertEqual(self.rules([row(form=form)]), [])

    def test_3d_gauge_and_dual_axis_name_the_better_form(self):
        cases = {"3D bar": ("form-3d", "flat bar"), "3-d pie (3 parts)": ("form-3d", "flat"),
                 "gauge": ("form-gauge", "target"), "speedometer": ("form-gauge", "bullet bar"),
                 "line, dual axis": ("form-dual-axis", "two small charts"), "dual-axis line": ("form-dual-axis", "indexed"),
                 "bars + line on a second axis": ("form-dual-axis", "two small charts"),
                 "line with two y axes": ("form-dual-axis", "two small charts")}
        for form, (rule, better) in cases.items():
            with self.subTest(form=form):
                findings = self.check([row(form=form)])[1]["findings"]
                self.assertEqual([(item["rule"], item["severity"]) for item in findings], [(rule, "medium")])
                self.assertIn(better, findings[0]["fix"])
        for form in ("tile", "line", "bar", "table", "tile + sparkline", "line on one axis", "d3 line", "gauged by hand"):
            self.assertEqual(self.rules([row(form=form)]), [], form)

    def test_each_finding_says_what_where_why_and_fix(self):
        path = self.write(page(GOOD + [row(number="Mystery", definition="", source="fake", unit="", form="3D gauge")]))
        code, out, _ = run(path, "--json")
        findings = json.loads(out)["findings"]
        self.assertEqual(sorted(item["rule"] for item in findings),
                         ["form-3d", "form-gauge", "invented-source", "no-definition", "no-unit"])
        for item in findings:
            self.assertEqual(sorted(item), ["fix", "line", "rule", "severity", "what", "where", "why"])
            self.assertEqual(item["where"], "%s:%d" % (path, item["line"]))
            self.assertEqual(item["line"], 14)
            self.assertIn("Mystery", item["what"])
            self.assertTrue(item["why"] and item["fix"])
        code, out, _ = run(path)
        self.assertEqual(code, 1)
        for part in ("HIGH", "MEDIUM", "where:", "why:", "fix:", "4 numbers, 2 high, 3 medium", "FAIL"):
            self.assertIn(part, out)

    def test_forge_allow_skips_a_row(self):
        self.assertEqual(self.rules([row(source="random sample of 1 in 10 rows of `visits` <!-- forge:allow -->")]), [])


class Reading(DashCase):
    def test_pipes_in_code_and_escaped_pipes_stay_in_their_cell(self):
        rows = [row(source="`select a || b from t where x | y`"), row(number="B", definition="a \\| b")]
        code, report = self.check(rows)
        self.assertEqual((code, report["findings"]), (0, []))
        self.assertEqual(report["numbers"][0]["source"], "`select a || b from t where x | y`")
        self.assertEqual(report["numbers"][0]["form"], "tile")
        self.assertEqual(report["numbers"][1]["definition"], "a \\| b")

    def test_numbers_json_has_every_column_and_the_line(self):
        report = self.check(GOOD)[1]
        self.assertEqual(sorted(report["numbers"][0]),
                         ["compared with", "definition", "form", "line", "number", "period", "source", "unit"])
        self.assertEqual((report["numbers"][0]["number"], report["numbers"][0]["line"]), ("Revenue", 11))
        self.assertEqual(report["numbers"][2]["compared with"], "yesterday")

    def test_columns_in_another_order_with_bold_headers_and_no_outer_pipes(self):
        text = ("## Numbers\n\nform | **Number** | Unit | Source | Definition\n--- | --- | --- | --- | ---\n"
                "gauge | Speed | | fake | \n")
        code, out, _ = run(self.write(text), "--json")
        self.assertEqual(code, 2, "a row that does not start with | is not read as a table")
        text = text.replace("form |", "| form |").replace("--- | ---", "| --- | ---", 1).replace("gauge |", "| gauge |")
        code, out, _ = run(self.write(text), "--json")
        self.assertEqual(code, 1)
        self.assertEqual(sorted(item["rule"] for item in json.loads(out)["findings"]),
                         ["form-gauge", "invented-source", "no-definition", "no-unit"])

    def test_a_table_in_a_code_block_is_not_the_numbers(self):
        example = "```markdown\n%s%s\n```\n\n" % (HEADER, row(source="fake"))
        self.assertEqual(self.rules(GOOD, before=example), [])
        code, _, err = run(self.write("## Numbers\n\n" + example))
        self.assertEqual(code, 2)
        self.assertIn("no table", err)

    def test_only_the_numbers_section_is_read(self):
        other = "\n## Charts\n\n%s%s\n" % (HEADER, row(source="fake"))
        self.assertEqual(self.rules(GOOD, after=other), [])
        self.assertEqual(self.check(GOOD, after="\nSome notes.\n\n| a | b |\n| --- | --- |\n| fake | 3D |\n")[0], 0)

    def test_what_cannot_be_checked_is_exit_2(self):
        cases = {
            "no section": "# Dashboard\n\n## Audience\n\nThe owner.\n",
            "no table": "## Numbers\n\nRevenue and orders.\n\n## Layout\n",
            "table in the next section": "## Numbers\n\n## Layout\n\n" + HEADER + GOOD[0] + "\n",
            "no rows": "## Numbers\n\n" + HEADER,
            "missing columns": "## Numbers\n\n| number | form |\n| --- | --- |\n| Revenue | tile |\n",
            "empty": "",
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                code, out, err = run(self.write(text))
                self.assertEqual((code, out), (2, ""))
                self.assertIn("not a pass", err)
        self.assertIn("definition, source, unit", run(self.write(cases["missing columns"]))[2])
        code, _, err = run(os.path.join(self.folder, "missing.md"))
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)
        self.assertEqual(run(self.folder)[0], 2)  # a folder
        self.assertEqual(run(self.write("", raw=b"## Numbers\n\x00\x00"))[0], 2)
        self.assertEqual(run(self.write("", raw=b"## Numbers\n" + b"x" * (dashcheck.MAX_BYTES + 1)))[0], 2)

    def test_windows_line_ends_a_byte_order_mark_and_odd_bytes(self):
        text = page(GOOD + [row(number="Café €", source="fake")]).replace("\n", "\r\n")
        code, out, _ = run(self.write("", raw=b"\xef\xbb\xbf" + text.encode("utf-8") + b"\xff\xfe"), "--json")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["summary"]["numbers"], 4)

    def test_usage_and_help(self):
        for args in ([], ["a.md", "--fail-on", "severe"]):
            with self.assertRaises(SystemExit) as caught, contextlib.redirect_stderr(io.StringIO()):
                dashcheck.main(args)
            self.assertEqual(caught.exception.code, 2)
        code, out, _ = run_cp1252(SCRIPT, "--help")
        self.assertEqual(code, 0)
        for word in ("Usage:", "Exit codes:", "--fail-on", "## Numbers"):
            self.assertIn(word, out)

    def test_output_survives_a_cp1252_pipe(self):
        path = self.write(page([row(number="→ \U0001f600 Omzet", source="fake")]))
        code, out, err = run_cp1252(SCRIPT, path)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("Omzet", out)
        code, out, _ = run_cp1252(SCRIPT, path, "--json")
        self.assertEqual(json.loads(out)["numbers"][0]["number"], "→ \U0001f600 Omzet")


class SkillAgrees(unittest.TestCase):
    """The table the skill tells Claude to write is the table this script reads."""

    def test_the_skill_shows_the_same_columns(self):
        with open(os.path.join(ROOT, "forge-dashboard", "SKILL.md"), encoding="utf-8") as handle:
            skill = handle.read()
        self.assertIn("| " + " | ".join(dashcheck.COLUMNS) + " |", skill)
        example = skill[skill.index("```markdown"):].split("```")[1].replace("markdown\n", "", 1)
        rows, problem = dashcheck.read_numbers("## Numbers\n\n" + example)
        self.assertEqual((problem, len(rows)), ("", 1))
        self.assertEqual(dashcheck.check(rows, "SKILL.md"), [])


if __name__ == "__main__":
    unittest.main()
