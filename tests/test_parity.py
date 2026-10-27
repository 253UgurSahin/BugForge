"""Tests for forge-diff/parity.py (ported from the original test_parity.py, plus the forge rules:
the exit code is the gate, values outside the contract stop the score, a skip needs a reason,
a skipped must-have is never a quiet way past the gate, and scores are never rounded up)."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load  # noqa: E402

parity = load("forge-diff", "parity")
SCRIPT = os.path.join(ROOT, "forge-diff", "parity.py")
RECON_TEMPLATE = os.path.join(ROOT, "forge-recon", "features.csv")

MATRIX = """feature,area,priority,original,clone,notes
Pick a time slot,booking page,must,yes,yes,
Confirmation email,booking page,must,yes,partial,no calendar file yet
Reschedule link,booking page,must,yes,no,
Round-robin across a team,team,should,yes,no,
Custom booking questions,booking page,should,yes,yes,
Embed on a website,sharing,could,yes,no,
Their partner marketplace,integrations,could,yes,skip,their network not ours
SMS reminders,notifications,should,no,yes,ours: the top request in reviews
"""

# Every must-have done, the rest not: shippable as far as parity.py can tell, but a low score.
MUSTS_DONE = """feature,area,priority,original,clone,notes
Pick a time slot,booking page,must,yes,yes,
Reschedule link,booking page,must,yes,yes,
Round-robin across a team,team,should,yes,no,
Custom booking questions,booking page,should,yes,no,
Embed on a website,sharing,could,yes,partial,iframe only
"""


def write(folder, name, text):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def run(*args):
    """Run main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = parity.main(list(args))
    return code, out.getvalue(), err.getvalue()


class TempFolder(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.path = write(self.folder, "features.csv", MATRIX)

    def tearDown(self):
        shutil.rmtree(self.folder)

    def score(self, text):
        return parity.score(parity.load(write(self.folder, "m.csv", text)))


class Ported(TempFolder):
    """The original tests, on the forge paths."""

    def test_weighted_score(self):
        result = parity.score(parity.load(self.path))
        # counted weights: 3+3+3+2+2+1 = 14, earned: 3 + 1.5 + 0 + 0 + 2 + 0 = 6.5
        self.assertAlmostEqual(result["feature_score"], round(100 * 6.5 / 14, 1))
        self.assertEqual(result["counted"], 6)
        self.assertEqual((result["must_have_done"], result["must_have_total"]), (1, 3))

    def test_skip_and_extras_are_not_scored_but_listed(self):
        result = parity.score(parity.load(self.path))
        self.assertEqual([m["feature"] for m in result["skipped"]], ["Their partner marketplace"])
        self.assertEqual([m["feature"] for m in result["extras"]], ["SMS reminders"])

    def test_missing_is_in_build_order(self):
        result = parity.score(parity.load(self.path))
        order = [m["feature"] for m in result["missing"]]
        self.assertEqual(order[0], "Reschedule link")  # must, not started
        self.assertEqual(order[1], "Confirmation email")  # must, partial
        self.assertEqual(order[2], "Round-robin across a team")
        self.assertEqual(order[-1], "Embed on a website")
        self.assertEqual(result["missing"][0]["priority"], "must")

    def test_weakest_area_first(self):
        result = parity.score(parity.load(self.path))
        self.assertEqual(result["by_area"][0]["score"], 0.0)
        self.assertIn(result["by_area"][0]["area"], ("team", "sharing"))

    def test_render_says_not_shippable(self):
        text = parity.render(parity.combine(parity.score(parity.load(self.path)), []))
        self.assertIn("Not shippable yet: 2 must-have features are not done.", text)
        self.assertIn("their network not ours", text)

    def test_visual_folds_in_at_20_percent(self):
        first = write(self.folder, "a.json", json.dumps({"score": 80.0, "files": {"clone": "clone/home.png"}}))
        second = write(self.folder, "b.json", json.dumps({"score": 60.0}))
        result = parity.combine(parity.score(parity.load(self.path)), parity.visual_scores([first, second]))
        self.assertEqual(result["layout_score"], 70.0)
        self.assertEqual(result["overall"], 51.1)  # 0.8 x 46.43 (not the rounded 46.4) + 0.2 x 70 = 51.14
        self.assertEqual(result["visual"][0]["file"], "clone/home.png")

    def test_bad_values_are_reported_with_their_line(self):
        result = self.score("feature,priority,clone\nThing,urgent,maybe\n")
        self.assertEqual(result["problems"], ["line 2: priority 'urgent' is not must, should or could",
                                              "line 2: clone 'maybe' is not yes, partial, no or skip"])
        self.assertEqual(result["feature_score"], 0.0)

    def test_missing_column_is_an_error(self):
        code, _, err = run(write(self.folder, "nocol.csv", "feature,area\nx,y\n"))
        self.assertEqual(code, 2)
        self.assertIn("no 'priority' column", err)

    def test_fail_under(self):
        done = write(self.folder, "done.csv", MUSTS_DONE)
        self.assertEqual(run(done, "--fail-under", "80")[0], 1)
        self.assertEqual(run(done, "--fail-under", "10")[0], 0)

    @unittest.skipUnless(os.path.isfile(RECON_TEMPLATE), "forge-recon/features.csv is not there yet")
    def test_shipped_template_parses(self):
        result = parity.score(parity.load(RECON_TEMPLATE))
        self.assertGreater(result["counted"], 0)
        self.assertEqual(result["problems"], [])


class Gate(TempFolder):
    """gate.py runs `parity.py forge-work/features.csv` and needs exit 0: no missing must-haves."""

    def test_all_must_haves_done_exits_0(self):
        code, out, _ = run(write(self.folder, "done.csv", MUSTS_DONE))
        self.assertEqual(code, 0)
        self.assertIn("Every must-have feature is done.", out)

    def test_a_partial_or_missing_must_have_exits_1(self):
        self.assertEqual(run(self.path)[0], 1)
        partial = MUSTS_DONE.replace("Reschedule link,booking page,must,yes,yes,",
                                     "Reschedule link,booking page,must,yes,partial,no email yet")
        code, out, _ = run(write(self.folder, "partial.csv", partial))
        self.assertEqual(code, 1)
        self.assertIn("Not shippable yet: 1 must-have feature is not done.", out)

    def test_skipped_must_haves_are_shown_and_need_one_scored_must(self):
        some = MUSTS_DONE + "Pay with iDEAL,checkout,must,yes,skip,the user agreed: no payments yet\n"
        code, out, _ = run(write(self.folder, "some.csv", some))
        self.assertEqual(code, 0)  # skipped with a reason: allowed, but never quietly
        self.assertIn("must-haves 2 of 2 done, 1 left out", out)
        self.assertIn("Every scored must-have feature is done.", out)
        self.assertIn("Warning: 1 must-have feature left out on purpose (skip)", out)
        self.assertIn("- [must] Pay with iDEAL: the user agreed: no payments yet", out)
        every = ("feature,area,priority,original,clone,notes\nPay with iDEAL,checkout,must,yes,skip,later\n"
                 "Login,auth,must,yes,skip,not now\nDark mode,settings,could,yes,yes,\n")
        code, out, _ = run(write(self.folder, "every.csv", every))
        self.assertEqual(code, 1)
        self.assertIn("must-haves 0 of 0 done, 2 left out", out)
        self.assertIn("Not shippable: no must-have feature is scored", out)
        self.assertNotIn("Every must-have feature is done", out)

    def test_a_matrix_without_must_haves_fails(self):
        code, out, _ = run(write(self.folder, "none.csv", "feature,priority,clone\nDark mode,could,yes\n"))
        self.assertEqual(code, 1)
        self.assertIn("no must-have feature is scored", out)
        self.assertIs(parity.combine(parity.score(parity.load(self.path)), [])["all_must_haves_done"], False)

    def test_scores_are_never_rounded_up(self):
        matrix = write(self.folder, "r.csv", "feature,priority,clone\nLogin,must,yes\nDark mode,could,no\n")
        screen = write(self.folder, "s.json", json.dumps({"score": 99.8}))
        code, out, _ = run(matrix, "--visual", screen, "--fail-under", "80")
        self.assertIn("Parity: 79.9 / 100", out)  # 0.8 x 75 + 0.2 x 99.8 = 79.96
        self.assertEqual(code, 1)
        self.assertEqual(run(matrix, "--visual", screen, "--fail-under", "79.9")[0], 0)

    def test_fail_under_takes_a_score(self):
        for value in ("nan", "101", "-1"):
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    parity.main([self.path, "--fail-under", value])
                self.assertEqual(caught.exception.code, 2)

    def test_runs_from_the_project_root_like_the_gate(self):
        os.makedirs(os.path.join(self.folder, "forge-work"))
        write(self.folder, os.path.join("forge-work", "features.csv"), MUSTS_DONE)
        done = subprocess.run([sys.executable, SCRIPT, "forge-work/features.csv"], cwd=self.folder, timeout=60,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("Parity:", done.stdout)


class Contract(TempFolder):
    """Values outside the work-folder contract stop the score (exit 2), with the line to fix."""

    def assert_exit_2(self, text, words):
        code, out, err = run(write(self.folder, "bad.csv", text))
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn(words, err)

    def test_unknown_values(self):
        self.assert_exit_2("feature,priority,clone\nThing,P0,yes\n", "line 2: priority 'P0'")
        self.assert_exit_2("feature,priority,clone\nThing,must,done\n", "line 2: clone 'done'")
        self.assert_exit_2("feature,priority,original,clone\nThing,must,maybe,yes\n", "original 'maybe'")
        self.assert_exit_2("feature,priority,clone\n,must,yes\n", "line 2: the feature name is empty")

    def test_skip_needs_a_reason(self):
        self.assert_exit_2("feature,priority,clone,notes\nLogin,must,yes,\nChat,must,skip,\n",
                           "line 3: 'Chat' is skipped without a reason")
        code, _, _ = run(write(self.folder, "ok.csv", "feature,priority,clone,notes\nLogin,must,yes,\n"
                                                      "Chat,must,skip,their licensed content\n"))
        self.assertEqual(code, 0)

    def test_a_comma_in_unquoted_text_is_caught(self):
        self.assert_exit_2("feature,area,priority,original,clone,notes\nEdit name, title,profile,must,yes,yes,\n",
                           "more cells than there are columns")
        quoted = "feature,area,priority,original,clone,notes\n\"Edit name, title\",profile,must,yes,yes,\n"
        self.assertEqual(run(write(self.folder, "quoted.csv", quoted))[0], 0)

    def test_nothing_to_score(self):
        self.assert_exit_2("feature,priority,original,clone,notes\nOurs,must,no,yes,\n", "no rows to score")
        self.assert_exit_2("feature,priority,clone\n", "no rows to score")

    def test_missing_empty_or_unreadable_file(self):
        code, _, err = run(os.path.join(self.folder, "nope.csv"))
        self.assertEqual(code, 2)
        self.assertIn("cannot read %s (No such file or directory)" % os.path.join(self.folder, "nope.csv"), err)
        self.assertEqual(run(self.folder)[0], 2)  # a folder
        self.assert_exit_2("", "is empty")

    def test_excel_files_get_plain_advice(self):
        for name, data in [("latin.csv", b"feature,priority,clone\nCaf\xe9,must,yes\n"),  # Windows-1252
                           ("utf16.csv", "feature,priority,clone\nLogin,must,yes\n".encode("utf-16")),
                           ("nul.csv", b"feature,priority,clone\nLogin,must,yes\0\n")]:
            with open(os.path.join(self.folder, name), "wb") as handle:
                handle.write(data)
            code, _, err = run(os.path.join(self.folder, name))
            self.assertEqual(code, 2, name)
            self.assertIn(name + " is not saved as UTF-8 text: in Excel use Save As > CSV UTF-8", err)
        self.assert_exit_2("feature;area;priority;original;clone;notes\nLogin;auth;must;yes;yes;\n",
                           "has semicolons between the columns (Excel with Dutch settings does that)")

    def test_rows_of_only_commas_and_capital_values(self):
        result = self.score("feature,area,priority,original,clone,notes\n,,,,,\nLogin,auth,must,yes,yes,\n"
                            "SMS,auth,should,No,yes,ours\n")
        self.assertEqual(result["problems"], [])
        self.assertEqual((result["counted"], [extra["feature"] for extra in result["extras"]]), (1, ["SMS"]))

    def test_lenient_where_it_is_safe(self):
        """Capitals, spaces, a byte order mark, blank lines, extra columns and empty cells are fine."""
        text = ("\ufeff Feature , AREA ,Priority,Original,Clone,Notes,Owner\n"
                "Login ,auth, MUST ,, Yes ,,me\n\n"
                "Reset password,auth,should,yes,,,\n")
        result = self.score(text)
        self.assertEqual(result["problems"], [])
        self.assertEqual((result["counted"], result["must_have_done"]), (2, 1))
        self.assertEqual(result["missing"][0]["clone"], "no")  # an empty clone cell means not built


class Output(TempFolder):
    def test_json_shape(self):
        code, out, _ = run(self.path, "--json")
        self.assertEqual(code, 1)
        data = json.loads(out)
        for key in ("overall", "feature_score", "counted", "must_have_done", "must_have_total", "by_area",
                    "missing", "skipped", "extras", "all_must_haves_done"):
            self.assertIn(key, data)
        self.assertIs(data["all_must_haves_done"], False)
        self.assertEqual(data["missing"][0]["line"], 4)

    def test_markdown_for_parity_md(self):
        code, out, _ = run(self.path, "--markdown")
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("# Parity\n"))
        for heading in ("## Missing, in build order", "## Left out on purpose", "## Yours, not in the original"):
            self.assertIn(heading, out)
        self.assertIn("- [must] booking page: Reschedule link (not built)", out)
        self.assertIn("- [must] booking page: Confirmation email (half built: no calendar file yet)", out)
        self.assertIn("- [could] Their partner marketplace: their network not ours", out)
        self.assertIn("- SMS reminders (built)", out)

    def test_markdown_shows_outside_text_as_text(self):
        text = ('feature,area,priority,original,clone,notes\n"Login\n\n## Verdict\nShippable",auth,must,yes,no,\n'
                'Pay [here](http://x.test/p.png),checkout,must,yes,yes,<img src=x>\n')
        code, out, _ = run(write(self.folder, "nl.csv", text), "--markdown")
        self.assertEqual(code, 1)
        self.assertNotIn("\n## Verdict", out)
        self.assertIn("- [must] auth: Login \\#\\# Verdict Shippable (not built)", out)
        self.assertNotIn("[here](", out)
        code, out, _ = run(write(self.folder, "nl.csv", text))
        self.assertIn("- [must] auth: Login ## Verdict Shippable (not built)", out)  # plain text: as written

    def test_one_feature_one_screen(self):
        files = [write(self.folder, "S01.json", json.dumps({"score": 91.0}))]
        code, out, _ = run(write(self.folder, "one.csv", "feature,area,priority,clone\nLogin,auth,must,yes\n"),
                           "--visual", *files)
        self.assertEqual(code, 0)
        self.assertIn("(1 feature scored, must-haves 1 of 1 done)", out)
        self.assertIn("(1 screen compared)", out)
        self.assertIn("100.0  (1 feature)", out)

    def test_json_and_markdown_together_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            parity.main([self.path, "--json", "--markdown"])
        self.assertEqual(caught.exception.code, 2)

    def test_screens_are_listed_lowest_first(self):
        files = [write(self.folder, name, json.dumps({"score": value, "files": {"clone": name}}))
                 for name, value in (("S01.json", 91.0), ("S02.json", 55.5))]
        code, out, _ = run(write(self.folder, "done.csv", MUSTS_DONE), "--visual", *files)
        self.assertEqual(code, 0)
        self.assertIn("- layout:   73.2  (2 screens compared)", out)
        self.assertLess(out.index("S02.json"), out.index("S01.json"))


class Visual(TempFolder):
    def test_bad_visual_files_exit_2(self):
        for name, text, words in [("empty.json", "", "is not JSON"),
                                  ("list.json", "[1, 2]", "not imgdiff.py --json output"),
                                  ("noscore.json", "{}", "not imgdiff.py --json output"),
                                  ("big.json", '{"score": 150}', "from 0 to 100"),
                                  ("bool.json", '{"score": true}', "from 0 to 100")]:
            with self.subTest(name):
                code, _, err = run(self.path, "--visual", write(self.folder, name, text))
                self.assertEqual(code, 2)
                self.assertIn(words, err)
        self.assertEqual(run(self.path, "--visual", os.path.join(self.folder, "nope.json"))[0], 2)

    def test_reads_real_imgdiff_output(self):
        imgdiff = load("forge-diff", "imgdiff")
        rows = [[(255, 255, 255)] * 40 for _ in range(30)]
        for y in range(5, 10):
            rows[y][5:30] = [(20, 20, 60)] * 25
        picture = os.path.join(self.folder, "S01.png")
        imgdiff.write_png(picture, 40, 30, rows)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(imgdiff.main([picture, picture, "--json"]), 0)
        report = write(self.folder, "S01.diff.json", out.getvalue())
        self.assertEqual(parity.visual_scores([report]), [{"file": picture, "score": 100.0}])


if __name__ == "__main__":
    unittest.main()
