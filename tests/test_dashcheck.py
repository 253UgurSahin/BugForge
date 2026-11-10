"""Tests for forge-design/dashcheck.py: each rule on the ## Numbers table fires and does not fire,
the exit codes 0, 1 and 2, the JSON shape, and that a table it cannot read is never a pass. The level
rules (--level N|auto): the count of numbers, a form that moves from level 3, the report's one
`Level: N` line, and no level on record is exit 2. And that steps/dashboard.md and dashboard.md say
what the script and ../forge/levels.json say."""

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

dashcheck = load("forge-design", "dashcheck")
SCRIPT = os.path.join(ROOT, "forge-design", "dashcheck.py")
STEPS = os.path.join(ROOT, "forge-design", "steps", "dashboard.md")
REFERENCE = os.path.join(ROOT, "forge-design", "dashboard.md")
LEVELS = os.path.join(ROOT, "forge", "levels.json")
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
                                             "level": None, "fail_on": "high", "failed": False})

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


MOVING = "line, draws in, morphs between periods; drill-down to the orders"


def numbers(count, form="tile"):
    return [row(number="N%d" % index, form=form) for index in range(count)]


class Levels(DashCase):
    def level(self, rows, level, said="Level: %d\n", *more):
        """(exit code, report) at --level LEVEL for a dashboard.md with these rows and line SAID."""
        text = said % level if "%d" in said else said
        code, out, err = run(self.write(text + page(rows)), "--json", "--level", str(level), *more)
        self.assertIn(code, (0, 1), err)
        return code, json.loads(out)

    def level_rules(self, rows, level, said="Level: %d\n"):
        return [(item["rule"], item["severity"]) for item in self.level(rows, level, said)[1]["findings"]]

    def test_the_count_of_numbers_fits_the_level(self):
        cases = {1: ([3, 4, 5], [1, 2, 6, 7]), 2: ([1, 5, 7], [8, 9]), 3: ([1, 9], [10, 12]),
                 4: ([9], [10]), 5: ([9], [10])}
        for level, (fine, wrong) in cases.items():
            for count in fine:
                with self.subTest(level=level, count=count):
                    self.assertEqual(self.level_rules(numbers(count, MOVING), level), [])
            for count in wrong:
                with self.subTest(level=level, count=count):
                    code, report = self.level(numbers(count, MOVING), level)
                    self.assertEqual([(item["rule"], item["severity"]) for item in report["findings"]],
                                     [("level-numbers", "high")], "and no too-many-numbers next to it")
                    self.assertEqual((code, report["summary"]["level"]), (1, level))
                    self.assertIn("%d numbers on a level %d dashboard" % (count, level), report["findings"][0]["what"])
        self.assertIn("3 to 5", self.level(numbers(2), 1)[1]["findings"][0]["what"])
        self.assertEqual(self.level(numbers(12, MOVING), 3)[1]["findings"][0]["line"], 12 + 9)

    def test_without_a_level_the_old_rule_holds(self):
        self.assertEqual(self.rules(numbers(2)), [])
        self.assertEqual(self.rules(numbers(10)), [("too-many-numbers", "medium")])

    def test_from_level_3_a_form_moves_or_drills_down(self):
        for level in (1, 2):
            self.assertEqual(self.level_rules(numbers(4), level), [], level)
        for level in (3, 4, 5):
            with self.subTest(level=level):
                code, report = self.level(numbers(4), level)
                self.assertEqual([item["rule"] for item in report["findings"]], ["level-form"])
                self.assertEqual(code, 1)
                self.assertIn("form column", report["findings"][0]["fix"])
        for form in ("line, draws in", "bars, drawn in", "line, draw-on", "area that morphs", "bars, morphing",
                     "animated line", "tile, drill-down to the rows", "tile, drills down to orders",
                     "table, click-through", "bars, clicks through to the region", "tile, drill through"):
            with self.subTest(form=form):
                self.assertEqual(self.level_rules(numbers(3) + [row(form=form)], 3), [])
        for form in ("line", "drawer with a table", "tile, live", "bars, drawing", "tile (click)"):
            with self.subTest(form=form):
                self.assertEqual(self.level_rules([row(form=form)], 3), [("level-form", "high")])
        allowed = [row(form=MOVING + " <!-- forge:allow -->"), row(form="tile")]
        self.assertEqual(self.level_rules(allowed, 3), [("level-form", "high")], "a skipped row does not count")

    def test_the_report_says_the_level_once(self):
        for said in ("Level: 3", "Level: 3 (Expressive)", "Level: 3 (Expressief)", "Level: 3 Expressive",
                     "Level:3", "Level: 3  "):
            with self.subTest(said=said):
                self.assertEqual(self.level_rules(numbers(3, MOVING), 3, said + "\n"), [])
        for said in ("", "Level: 4", "Level: 3 (Showpiece)", "Level: 3\nLevel: 3", "Level: 3 or 4",
                     "## Level: 3", "**Level:** 3", "level: 3", "<!-- Level: 3 -->", "```\nLevel: 3\n```"):
            with self.subTest(said=said):
                code, report = self.level(numbers(3, MOVING), 3, said + "\n")
                self.assertEqual([(item["rule"], item["severity"]) for item in report["findings"]],
                                 [("level-report", "high")])
                self.assertIn("Level: 3 (Expressive)", report["findings"][0]["what"])
        finding = self.level(numbers(3, MOVING), 3, "Level: 2\n")[1]["findings"][0]
        self.assertEqual(finding["line"], 1)
        self.assertIn("found: Level: 2", finding["what"])

    def test_from_level_4_a_3d_view_next_to_a_table_is_no_finding(self):
        depth = "bars with depth (3D, CSS) + table, draws in"
        self.assertEqual(self.level_rules([row(form=depth)], 4), [])
        self.assertEqual(self.level_rules([row(form="3D field (datascape) and a table, draws in")], 5), [])
        self.assertEqual(self.level_rules([row(form="3D bars, draws in")], 4), [("form-3d", "medium")])
        self.assertEqual(self.level_rules([row(form=depth)], 3), [("form-3d", "medium")])
        self.assertEqual(self.rules([row(form=depth)]), [("form-3d", "medium")])
        self.assertEqual(self.level_rules([row(form="gauge and a table, draws in")], 5), [("form-gauge", "medium")])

    def test_the_human_report_names_the_level(self):
        code, out, _ = run(self.write(page(numbers(4, MOVING), before="Level: 4 (Showpiece)\n\n")), "--level", "4")
        self.assertEqual(code, 0)
        self.assertIn("Level: 4 (Showpiece)", out)
        self.assertNotIn("Level:", run(self.write(page(GOOD)))[1])
        with self.assertRaises(SystemExit) as caught, contextlib.redirect_stderr(io.StringIO()):
            dashcheck.main(["a.md", "--level", "6"])
        self.assertEqual(caught.exception.code, 2)


class LevelOnRecord(DashCase):
    def project(self, record, rows=None, said="Level: 4\n\n"):
        """forge-work/dashboard.md and, unless RECORD is None, forge-work/levels.json holding RECORD."""
        work = os.path.join(self.folder, "forge-work")
        os.makedirs(work, exist_ok=True)
        if record is not None:
            with open(os.path.join(work, "levels.json"), "w", encoding="utf-8") as handle:
                handle.write(record if isinstance(record, str) else json.dumps(record))
        path = os.path.join(work, "dashboard.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(page(rows or numbers(4, MOVING), before=said))
        return path

    def test_auto_reads_the_dashboard_level(self):
        record = {"look": {"level": 2, "said": "2", "at": "x"}, "dashboard": {"level": 4, "said": "4", "at": "x"}}
        code, out, err = run(self.project(record), "--level", "auto", "--json")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out)["summary"]["level"], 4)
        code, out, _ = run(self.project(record, rows=numbers(4)), "--level", "auto", "--json")
        self.assertEqual([item["rule"] for item in json.loads(out)["findings"]], ["level-form"])

    def test_auto_reads_forge_work_under_the_current_folder_for_a_file_elsewhere(self):
        self.project({"dashboard": {"level": 1, "said": "1", "at": "x"}})
        other = self.write(page(numbers(4), before="Level: 1 (Subtiel)\n\n"), name="elsewhere.md")
        here = os.getcwd()
        os.chdir(self.folder)
        self.addCleanup(os.chdir, here)
        code, out, err = run(other, "--level", "auto", "--json")
        self.assertEqual((code, json.loads(out)["summary"]["level"]), (0, 1), err)

    def test_no_level_on_record_is_exit_2_and_ask_the_user(self):
        here = os.getcwd()
        os.chdir(self.folder)
        self.addCleanup(os.chdir, here)
        for record in (None, {"look": {"level": 4}}, {"dashboard": {"level": 9}}, {"dashboard": {"level": "4"}},
                       {"dashboard": {"level": True}}, "{not json", "[]", "\"x\"", "x" * (dashcheck.MAX_BYTES + 1)):
            with self.subTest(record=str(record)[:40]):
                if record is None and os.path.exists(os.path.join(self.folder, "forge-work", "levels.json")):
                    os.remove(os.path.join(self.folder, "forge-work", "levels.json"))
                code, out, err = run(self.project(record), "--level", "auto")
                self.assertEqual((code, out), (2, ""))
                for part in ("no dashboard level on record", "Ask the user", "level.py set dashboard", "not a pass"):
                    self.assertIn(part, err)

    def test_a_linked_record_is_not_read(self):
        target = os.path.join(self.folder, "real.json")
        with open(target, "w", encoding="utf-8") as handle:
            json.dump({"dashboard": {"level": 4}}, handle)
        path = self.project(None)
        try:
            os.symlink(target, os.path.join(self.folder, "forge-work", "levels.json"))
        except (OSError, NotImplementedError):
            self.skipTest("this system cannot make links")
        code, _, err = run(path, "--level", "auto")
        self.assertEqual(code, 2)
        self.assertIn("link", err)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class SkillAgrees(unittest.TestCase):
    """The table the skill tells Claude to write is the table this script reads, and the steps file and
    the reference say what the levels say."""

    def setUp(self):
        self.steps = read(STEPS)

    def test_the_skill_shows_the_same_columns(self):
        skill = self.steps
        self.assertIn("| " + " | ".join(dashcheck.COLUMNS) + " |", skill)
        example = skill[skill.index("```markdown"):].split("```")[1].replace("markdown\n", "", 1)
        rows, problem = dashcheck.read_numbers("## Numbers\n\n" + example)
        self.assertEqual((problem, len(rows)), ("", 1))
        self.assertEqual(dashcheck.check(rows, "SKILL.md"), [])
        self.assertEqual(dashcheck.check(rows, "SKILL.md", 3, "Level: 3\n"), [], "the example moves")

    def test_says_which_skill_it_is_part_of_and_where_the_rules_are(self):
        top = "\n".join(self.steps.splitlines()[:6])
        for part in ["`/forge-design`", "`SKILL.md`", "`../forge/rules.md`", "section 9", "section 10"]:
            self.assertIn(part, top)
        self.assertLessEqual(len(self.steps.splitlines()), 240)
        for clumsy in ("forge-design design", "forge-design dashboard's", "forge-check test's"):
            self.assertNotIn(clumsy, self.steps)

    def test_reads_records_and_asks_for_the_level(self):
        for part in ["python3 ../forge/level.py get dashboard", "python3 ../forge/level.py show dashboard",
                     "python3 ../forge/level.py set dashboard", "--said '", "ONE question", "auto mode too",
                     "python3 ../forge/level.py check dashboard --report forge-work/dashboard.md", "`Level: N",
                     "python3 ../forge-design/dashcheck.py forge-work/dashboard.md --level auto"]:
            self.assertTrue(part in self.steps, part)

    def test_the_level_table_says_what_levels_json_says(self):
        with open(LEVELS, encoding="utf-8") as handle:
            levels = json.load(handle)["domains"]["dashboard"]["levels"]
        rows = {int(match.group(1)): match.group(0) for match in re.finditer(r"(?m)^\| (\d) \|.*$", self.steps)}
        self.assertEqual(sorted(rows), [1, 2, 3, 4, 5])
        for level in levels:
            with self.subTest(level=level["level"]):
                row = rows[level["level"]]
                self.assertTrue(row.startswith("| %d | %s | %s |" % (level["level"], level["name"], level["nl"])), row)
                for item in level["includes"]:
                    self.assertIn(item, row)
                low, high = dashcheck.COUNTS[level["level"]]
                self.assertIn("%d to %d" % (low, high) if low > 1 else "up to %d" % high, row)

    def test_shows_the_result_and_proves_it(self):
        for part in ["git branch --show-current", "git worktree list", "service worker", "`Served:`",
                     "../forge-design/shots.example.mjs", "--frames", "--video",
                     "python3 ../forge-design/changed.py forge-work/dashboard/before forge-work/dashboard/after",
                     "python3 ../forge-design/changed.py --moves", "VISIBLE CHANGE", "git switch",
                     "../forge-design/scenes/datascape.js", "npm install three", "lazyScene", "setData",
                     "second user", "show as table"]:
            self.assertTrue(part in self.steps, part)
        order = ["## Step 1", "## Step 2: the level", "## Step 3", "## Step 4", "## Step 5", "## Step 6",
                 "## Step 7", "## Step 8", "## Step 9", "## Step 10", "## Output", "## Next"]
        self.assertEqual([self.steps.index(name) for name in order], sorted(self.steps.index(name) for name in order))
        for section in ("Audience", "Numbers", "Layout", "Charts", "States", "Checks"):
            self.assertIn("`## %s`" % section, self.steps[self.steps.index("## Output"):])

    def test_the_reference_shows_each_level_the_hud_and_the_data_scene(self):
        reference = read(REFERENCE)
        for part in ["## 12. What each level looks like", "## 13. The HUD composition (level 4)",
                     "## 14. The data scene (level 5)", "datascape.js", "setData", "onHover", "aria-keyshortcuts",
                     "prefers-reduced-motion", "data-scene"]:
            self.assertTrue(part in reference, part)


if __name__ == "__main__":
    unittest.main()
