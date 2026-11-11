"""Tests for forge-design/dashbuilt.py: each item of the dashboard level is named under ## Built with a file and
line of the app's own, and the seven items that need certain code have it in a file named for them; what does not
count as a place (no such file, a line past the end, forge-work, node_modules, the scene kit's own files, outside
the project); leader lines that a screen leaves out with why; one report per screen of numbers; --level N|auto; the
exit codes and the JSON shape; and that steps/dashboard.md names every item."""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252, symlink  # noqa: E402

dashbuilt = load("forge-design", "dashbuilt")
SCRIPT = os.path.join(ROOT, "forge-design", "dashbuilt.py")
STEPS = os.path.join(ROOT, "forge-design", "steps", "dashboard.md")
APP = {  # a small app: each file holds the code its items need
    "app/stats/page.tsx": "export default function Stats() {\n  return <main>\n    <Tiles />\n    <Chart />\n"
                          "    <table><tbody></tbody></table>\n  </main>;\n}\n",
    "app/stats/Tiles.tsx": "export function Tiles() {\n  return <dl className=\"strip\">\n    <dt>Orders</dt>\n"
                           "    <dd>606</dd>\n  </dl>;\n}\n",
    "app/stats/stats.css": ".bar { transform: translateY(40%); }\n@keyframes rise { from { transform: translateY(100%); } }\n"
                           ".bar-top { transform: skewX(-59deg); }\n.plane { perspective: 1800px; }\n",
    "app/stats/useLive.ts": "export function useLive(load) {\n  const id = setInterval(load, 60000);\n"
                            "  document.addEventListener('visibilitychange', load);\n  return () => clearInterval(id);\n}\n",
    "app/stats/Scene.tsx": "import { mount } from './scenes/datascape.js';\nexport function Scene({ rows }) {\n"
                           "  const scene = mount(el, {});\n  scene.setData(rows);\n  scene.setProgress(0.5);\n"
                           "  return <button aria-keyshortcuts=\"t\">Show as table (T)</button>;\n}\n",
    "app/stats/scenes/datascape.js": "// the kit's own file, copied in\nexport function mount() {}\n",
}
ROWS = [  # item, where, how: every item of level 5 and below
    ("numbers", "app/stats/page.tsx:3", "tiles"), ("chart", "app/stats/page.tsx:4", "orders per day"),
    ("table", "app/stats/page.tsx:5", "the orders behind it"), ("sparkline", "app/stats/Tiles.tsx:4", "per tile"),
    ("period filter", "app/stats/page.tsx:2", "GET ?period="), ("states", "app/stats/page.tsx:6", "skeleton, empty"),
    ("draws in and morphs", "app/stats/stats.css:2", "translateY"), ("drill-down", "app/stats/page.tsx:4", "a link"),
    ("comparison", "app/stats/page.tsx:4", "last week"), ("value matrix", "app/stats/page.tsx:5", "5 tints"),
    ("live refresh", "app/stats/useLive.ts:2", "every 60 s"), ("readout strip", "app/stats/Tiles.tsx:2", "a dl"),
    ("leader lines", "app/stats/page.tsx:3", "an SVG"), ("crosshair", "app/stats/page.tsx:4", "one index"),
    ("3D-styled charts", "app/stats/stats.css:3", "faces with a side and a top"),
    ("sequence log", "app/stats/page.tsx:5", "newest first"), ("data scene", "app/stats/Scene.tsx:3", "the kit's"),
    ("camera", "app/stats/Scene.tsx:5", "eased"), ("table one key away", "app/stats/Scene.tsx:6", "T"),
]


def built(rows=ROWS, head="| item | where | how |\n| --- | --- | --- |\n"):
    return "## Built\n\n" + head + "".join("| %s | %s | %s |\n" % row for row in rows)


def report(section, level=5):
    return "Level: %d\n\n## Numbers\n\nSee the table.\n\n%s\n## Checks\n\nAll exit 0.\n" % (level, section)


class Case(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        for name, text in APP.items():
            self.write(name, text)

    def write(self, name, text):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return path

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = dashbuilt.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def check(self, section, level=5, name="forge-work/dashboard.md"):
        """(exit code, JSON report) for a report holding SECTION, at LEVEL."""
        code, out, err = self.run_main(self.write(name, report(section, level)), "--level", str(level), "--json")
        self.assertIn(code, (0, 1), err)
        return code, json.loads(out)

    def rules(self, section, level=5):
        return [(item["rule"], item["what"]) for item in self.check(section, level)[1]["findings"]]

    def without(self, item):
        return [row for row in ROWS if row[0] != item]

    def replaced(self, item, place, how=None):
        return [(name, place if name == item else where, how if name == item and how is not None else what)
                for name, where, what in ROWS]


class Items(Case):
    def test_every_item_built_where_the_report_says_passes(self):
        code, data = self.check(built())
        self.assertEqual((code, data["findings"]), (0, []))
        self.assertEqual(data["summary"], {"reports": 1, "items": 19, "built": 19, "high": 0, "failed": False})
        self.assertEqual(data["level"], 5)
        items = data["reports"][0]["items"]
        self.assertEqual([item["item"] for item in items], [item for _, item, _, _, _ in dashbuilt.ITEMS])
        self.assertEqual(sorted(items[0]), ["built", "item", "level", "places"])
        self.assertIn("app/stats/page.tsx:3", items[0]["places"])

    def test_only_the_items_up_to_the_level_count(self):
        for level, count in ((1, 3), (2, 6), (3, 11), (4, 16), (5, 19)):
            with self.subTest(level=level):
                code, data = self.check(built([row for row in ROWS if row[0] in [
                    item for number, item, _, _, _ in dashbuilt.ITEMS if number <= level]]), level)
                self.assertEqual((code, data["summary"]["items"], data["summary"]["built"]), (0, count, count))

    def test_an_item_no_entry_names(self):
        for item in ("crosshair", "data scene", "sparkline", "sequence log", "3D-styled charts", "drill-down"):
            with self.subTest(item=item):
                found = self.rules(built(self.without(item)))
                self.assertEqual([rule for rule, _ in found], ["no-item"])
                self.assertIn("names the %s" % item, found[0][1])
        self.assertEqual(self.rules(built(self.without("data scene")), 4), [], "level 5's items are not asked at 4")

    def test_a_report_without_built_is_a_finding(self):
        code, data = self.check("## Charts\n\nA line.\n")
        self.assertEqual((code, [item["rule"] for item in data["findings"]]), (1, ["no-built"]))
        self.assertIn("one row per item", data["findings"][0]["fix"])

    def test_three_numbers_that_draw_in_are_not_level_5(self):
        """The review's case: Level 5, three numbers whose forms draw in, nothing else: dashcheck passes it, this does not."""
        numbers = "## Numbers\n\n| number | definition | source | unit | form |\n| --- | --- | --- | --- | --- |\n" + \
                  "".join("| N%d | rows | `t` | rows | line, draws in |\n" % index for index in range(3))
        code, out, _ = self.run_main(self.write("forge-work/dashboard.md", "Level: 5 (Cinematic)\n\n" + numbers),
                                     "--level", "5")
        self.assertEqual(code, 1)
        self.assertIn("no ## Built section", out)


class Places(Case):
    def test_what_is_not_a_place_of_the_app(self):
        self.write("forge-work/design/build/peek.js", "one\ntwo\n")
        self.write("node_modules/chart/index.js", "one\ntwo\n")
        self.write("e2e/stats.spec.ts", "one\ntwo\n")
        self.write("docs/stats.md", "one\ntwo\n")
        cases = {"page.tsx:3": "no such file from the project root", "app/stats/page.tsx:40": "it has 7 lines",
                 "app/stats/page.tsx:0": "it has 7 lines", "forge-work/design/build/peek.js:1": "not the app's own code",
                 "node_modules/chart/index.js:1": "not the app's own code",
                 "e2e/stats.spec.ts:1": "in e2e, not the app's own code", "docs/stats.md:1": "a note, not the app's",
                 "app/stats/scenes/datascape.js:1": "scene kit itself", "../outside.tsx:1": "no such file",
                 "app/stats/page.tsx": "no path:line"}
        with open(os.path.join(os.path.dirname(self.root), "outside.tsx"), "w", encoding="utf-8") as handle:
            handle.write("one\n")
        self.addCleanup(os.remove, os.path.join(os.path.dirname(self.root), "outside.tsx"))
        cases["../outside.tsx:1"] = "outside the project"
        for place, why in cases.items():
            with self.subTest(place=place):
                found = self.rules(built(self.replaced("crosshair", place)))
                self.assertEqual([rule for rule, _ in found], ["no-place"], found)
                self.assertIn(why, found[0][1])

    def test_one_good_place_is_enough_and_the_forms_of_writing_it(self):
        for place in ("page.tsx:3, app/stats/page.tsx:4", "`app/stats/page.tsx:4`", "(app/stats/page.tsx:4)",
                      "./app/stats/page.tsx:4", "app\\stats\\page.tsx:4", "app/stats/page.tsx:4-6",
                      "app/stats/page.tsx:4:12"):
            with self.subTest(place=place):
                self.assertEqual(self.rules(built(self.replaced("crosshair", place))), [])

    def test_a_link_out_of_the_project_is_not_a_place(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside, True)
        with open(os.path.join(outside, "Chart.tsx"), "w", encoding="utf-8") as handle:
            handle.write("one\ntwo\n")
        symlink(self, os.path.join(outside, "Chart.tsx"), os.path.join(self.root, "app", "Chart.tsx"))
        found = self.rules(built(self.replaced("crosshair", "app/Chart.tsx:1")))
        self.assertEqual([rule for rule, _ in found], ["no-place"])
        self.assertIn("outside the project", found[0][1])

    def test_the_code_an_item_needs_is_in_a_file_named_for_it(self):
        cases = {"3D-styled charts": "app/stats/page.tsx:2", "data scene": "app/stats/page.tsx:2",
                 "readout strip": "app/stats/page.tsx:2", "live refresh": "app/stats/stats.css:1",
                 "draws in and morphs": "app/stats/page.tsx:1", "camera": "app/stats/Tiles.tsx:1",
                 "table one key away": "app/stats/page.tsx:1"}
        for item, place in cases.items():
            with self.subTest(item=item):
                found = self.rules(built(self.replaced(item, place)))
                self.assertEqual([rule for rule, _ in found], ["no-code"], found)
                self.assertIn("for the %s" % item, found[0][1])
        both = "app/stats/page.tsx:2, app/stats/stats.css:3"
        self.assertEqual(self.rules(built(self.replaced("3D-styled charts", both))), [], "any file named will do")
        self.write("app/stats/Bars.tsx", "export const Bars = () => <canvas ref={(c) => c && c.getContext('2d')} />;\n")
        self.assertEqual(self.rules(built(self.replaced("3D-styled charts", "app/stats/Bars.tsx:1"))), [], "a canvas")

    def test_leader_lines_a_screen_leaves_out_with_why(self):
        for place in ("none: the side panels are not parts of the main chart", "none, P-02 to P-04 are not its splits"):
            with self.subTest(place=place):
                self.assertEqual(self.rules(built(self.replaced("leader lines", place)), 4), [])
        for place in ("none", "none here", "not on this screen"):
            with self.subTest(place=place):
                found = self.rules(built(self.replaced("leader lines", place, how="")), 4)
                self.assertEqual([rule for rule, _ in found], ["no-place"])
        found = self.rules(built(self.replaced("crosshair", "none: there is no time axis on this screen")), 4)
        self.assertEqual([rule for rule, _ in found], ["no-place"], "only leader lines may be left out")


class Writing(Case):
    def test_lists_paragraphs_and_one_entry_for_many_items(self):
        prose = ("## Built\n\n- Level 1: the readout strip app/stats/Tiles.tsx:2 (numbers), the chart\n"
                 "  app/stats/page.tsx:4 and the table app/stats/page.tsx:5.\n"
                 "* Level 2: sparkline, period filter and states: app/stats/page.tsx:2\n\n"
                 "Level 3: draws in app/stats/stats.css:2; drill-down, comparison and the value matrix\n"
                 "app/stats/page.tsx:4; live refresh app/stats/useLive.ts:2.\n\n"
                 "1. Level 4: leader lines, the crosshair and the sequence log app/stats/page.tsx:3; charts in 3D\n"
                 "   app/stats/stats.css:3.\n")
        self.assertEqual(self.rules(prose, 4), [])

    def test_a_table_row_names_its_item_by_its_first_cell_only(self):
        """The verifier's case: the period filter's and the states' own rows point nowhere, while the table row's how
        cell mentions both. Each item's own row decides it; the other cells of another row never stand in for it."""
        moved = {"period filter": "app/Filter.tsx:4", "states": "app/States.tsx:7"}
        rows = [(name, moved.get(name, where), "with the states and the period" if name == "table" else how)
                for name, where, how in ROWS]
        found = self.rules(built(rows), 2)
        self.assertEqual([rule for rule, _ in found], ["no-place", "no-place"], found)
        self.assertIn("the period filter (level 2) has no file and line of the app: app/Filter.tsx:4 (no such file",
                      found[0][1])
        self.assertIn("the states (level 2)", found[1][1])
        found = self.rules(built(self.replaced("chart", "app/stats/Nowhere.tsx:1")))
        self.assertEqual([rule for rule, _ in found], ["no-place"], "the row of the 3D-styled charts does not stand in")
        loose = [("the crosshair (P-01)" if name == "crosshair" else name, where, how) for name, where, how in ROWS]
        self.assertEqual(self.rules(built(loose)), [], "a first cell that holds the item's words names it")
        other = [("P-01" if name == "crosshair" else name, where, "the crosshair" if name == "crosshair" else how)
                 for name, where, how in ROWS]
        found = self.rules(built(other))
        self.assertEqual([rule for rule, _ in found], ["no-item"], "only the first cell of a row names its item")
        self.assertIn("a table row names its item in its first cell", self.check(built(other))[1]["findings"][0]["why"])

    def test_a_row_of_another_items_name_never_stands_in(self):
        """The verifier's near misses: the chart's row is "main chart", the numbers' "tiles", the table's "data table",
        each pointing nowhere. The rows of the 3D-styled charts, the readout strip and the table one key away hold
        their words, but are named for their own item: each near miss gives no-place, never a pass."""
        for item, cell, level in (("chart", "main chart", 4), ("numbers", "tiles", 4), ("table", "data table", 5)):
            with self.subTest(item=item):
                rows = [(cell, "app/stats/Nowhere.tsx:1", how) if name == item else (name, where, how)
                        for name, where, how in ROWS]
                found = self.rules(built(rows), level)
                self.assertEqual([rule for rule, _ in found], ["no-place"], found)
                self.assertIn("the %s (level 1) has no file and line of the app: app/stats/Nowhere.tsx:1" % item,
                              found[0][1])
        near = [("main chart" if name == "chart" else "tiles" if name == "numbers" else name, where, how)
                for name, where, how in ROWS]
        self.assertEqual(self.rules(built(near), 4), [], "a near miss that points to the app still names its item")
        alone = [row for row in ROWS if row[0] != "numbers"]
        self.assertEqual([rule for rule, _ in self.rules(built(alone), 4)], ["no-item"], "the readout strip's row is "
                         "its own, so the numbers need a row of theirs")

    def test_comments_code_blocks_and_other_sections_do_not_count(self):
        hidden = "## Built\n\n<!--\n%s-->\n```\n%s```\n" % (built()[10:], built()[10:])
        self.assertEqual({rule for rule, _ in self.rules(hidden)}, {"no-item"})
        elsewhere = "## Notes\n\n" + built()[10:] + "\n## Built\n\nNothing yet.\n"
        self.assertEqual({rule for rule, _ in self.rules(elsewhere)}, {"no-item"})
        self.assertEqual(self.rules(built() + "\n### Left\n\nThe camera: later.\n"), [])

    def test_the_human_report(self):
        path = self.write("forge-work/dashboard.md", report(built(self.without("crosshair")), 4))
        code, out, err = self.run_main(path, "--level", "4")
        self.assertEqual((code, err), (1, ""))
        for part in ("HIGH", "where: %s:" % path, "why:", "fix:", "names the crosshair (level 4)",
                     "15 of 16 items of dashboard level 4", "FAIL: 1 finding"):
            self.assertIn(part, out)
        self.write("forge-work/dashboard.md", report(built(), 4))
        code, out, _ = self.run_main(path, "--level", "4")
        self.assertEqual(code, 0)
        self.assertIn("PASS: every item of level 4 and below is built", out)


class Reports(Case):
    def test_each_screen_of_numbers_has_its_own_report_and_each_is_checked(self):
        main = self.write("forge-work/dashboard.md", report(built(), 4))
        self.write("forge-work/dashboard-admin.md", report(built(self.without("sequence log")), 4))
        self.write("forge-work/dashboard-old.txt", "not a report")
        code, out, _ = self.run_main(main, "--level", "4", "--json")
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual([os.path.basename(item["file"]) for item in data["reports"]], ["dashboard.md", "dashboard-admin.md"])
        self.assertEqual([os.path.basename(item["where"]).split(":")[0] for item in data["findings"]], ["dashboard-admin.md"])
        self.assertEqual(data["summary"]["reports"], 2)
        other = self.run_main(os.path.join(self.root, "forge-work", "dashboard-admin.md"), "--level", "4", "--json")[1]
        self.assertEqual(len(json.loads(other)["reports"]), 1, "only dashboard.md brings the others")

    def test_a_report_elsewhere_is_read_from_the_current_folder(self):
        path = self.write("notes/dashboard.md", report(built(), 5))
        here = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, here)
        self.assertEqual(self.run_main(path, "--level", "5")[0], 0)


class Levels(Case):
    def test_auto_reads_the_dashboard_level_on_record(self):
        self.write("forge-work/levels.json", json.dumps({"look": {"level": 5}, "dashboard": {"level": 2}}))
        code, out, err = self.run_main(self.write("forge-work/dashboard.md", report(built(), 2)), "--level", "auto",
                                       "--json")
        self.assertEqual((code, json.loads(out)["level"]), (0, 2), err)

    def test_no_level_is_exit_2(self):
        path = self.write("forge-work/dashboard.md", report(built()))
        for record in (None, {"look": {"level": 4}}, {"dashboard": {"level": 7}}, "{broken"):
            with self.subTest(record=record):
                if record is not None:
                    self.write("forge-work/levels.json", record if isinstance(record, str) else json.dumps(record))
                code, out, err = self.run_main(path, "--level", "auto")
                self.assertEqual((code, out), (2, ""))
                for part in ("no dashboard level on record", "Ask the user", "level.py set dashboard", "not a pass"):
                    self.assertIn(part, err)
        with self.assertRaises(SystemExit) as caught, contextlib.redirect_stderr(io.StringIO()):
            dashbuilt.main([path])
        self.assertEqual(caught.exception.code, 2, "--level is required")


class Exits(Case):
    def test_what_cannot_be_read_is_exit_2(self):
        missing = os.path.join(self.root, "forge-work", "dashboard.md")
        os.makedirs(os.path.dirname(missing))
        code, out, err = self.run_main(missing, "--level", "3")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("cannot read", err)
        for raw in (b"## Built\n\x00", b"x" * (dashbuilt.MAX_BYTES + 1)):
            path = os.path.join(self.root, "forge-work", "dashboard.md")
            with open(path, "wb") as handle:
                handle.write(raw)
            self.assertEqual(self.run_main(path, "--level", "3")[0], 2)
        self.assertEqual(self.run_main(self.root, "--level", "3")[0], 2, "a folder")

    def test_help_and_a_cp1252_pipe(self):
        code, out, _ = run_cp1252(SCRIPT, "--help")
        self.assertEqual(code, 0)
        for part in ("Usage:", "Exit codes:", "## Built", "dashboard-<screen>.md", "leader lines"):
            self.assertIn(part, out)
        path = self.write("forge-work/dashboard.md", report(built(self.replaced("crosshair", "app/café数.tsx:1"))))
        code, out, err = run_cp1252(SCRIPT, path, "--level", "5")
        self.assertEqual((code, err), (1, ""))
        self.assertIn("app/café\\u6570.tsx:1 (no such file", out)


class SkillAgrees(unittest.TestCase):
    def test_the_steps_name_every_item_and_the_command(self):
        with open(STEPS, encoding="utf-8") as handle:
            steps = " ".join(handle.read().split())
        step11 = steps[steps.index("## Step 11"):steps.index("## Output")]
        self.assertIn("python3 ../forge-design/dashbuilt.py forge-work/dashboard.md --level auto", step11)
        for _, item, _, _, _ in dashbuilt.ITEMS:
            self.assertIn(item, step11)
        for number, item, words, _, _ in dashbuilt.ITEMS:  # each item's own name is among its words
            self.assertTrue(dashbuilt.WORDS[[name for _, name, _, _, _ in dashbuilt.ITEMS].index(item)].search(item), item)


if __name__ == "__main__":
    unittest.main()
