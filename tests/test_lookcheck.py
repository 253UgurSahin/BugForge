"""Tests for forge/lookcheck.py, run on its own: the look items of an improve run (looked) and the frames a look or
dashboard level asks for (moved), with the real ../forge-design/changed.py. The gate's use of both is tested in
test_phasecheck.py. Every test works in its own folder; the pictures are made at run time."""

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
from test_phasecheck import OLD, frames, levels, png, write  # noqa: E402

lookcheck = load("forge", "lookcheck")
SCRIPT = os.path.join(ROOT, "forge", "lookcheck.py")
SINCE = "2020-01-01T00:00:00+00:00"  # a last go after OLD (2017) and before now


class Look(unittest.TestCase):
    """A temporary project folder; lookcheck.py runs in it as if from the project root."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def check(self, *args):
        """Run lookcheck.main with --json in the project: (exit code, its checks or None on exit 2, stderr)."""
        out, err, before = io.StringIO(), io.StringIO(), os.getcwd()
        os.chdir(self.root)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = lookcheck.main(list(args) + ["--json"])
        finally:
            os.chdir(before)
        return code, None if code == 2 else json.loads(out.getvalue())["checks"], err.getvalue()

    def age(self, *names):
        """Make each file below NAMES (files or folders in the project) look written long before the last go."""
        for name in names:
            path = os.path.join(self.root, name)
            for target in [path] if os.path.isfile(path) else [os.path.join(folder, file) for folder, _, files
                                                               in os.walk(path) for file in files]:
                os.utime(target, (OLD, OLD))


class LookedTests(Look):
    """forge-improve: a look item under ## Fixed of improve.md was built and shown (R63: a redesign at level 4 listed
    there, with no report, no shots and the app unchanged, passed the gate). A design or dashboard pick shows in the
    stills; a motion pick in the frames, as a still is the page at rest (R19). Its report is its own look report
    (VG1-N5: `report: package.json` passed), and with --since nothing of an earlier round counts (R63)."""
    SHOTS = "forge-work/improve/shots"
    IMPROVE = ("# Improve: Slotwise\n## To do\n## Fixed\n### A001 [high] Any user can open any invoice\ncommit: 9b1e2f4\n"
               "### design [look] A redesign at level 4 (Showpiece)\nreport: forge-work/design/redesign.md   commits: "
               "4c1d2e0..a7f3b19\nproof:  changed.py: VISIBLE CHANGE on 8 of 8 pairs\n%s## Skipped\n"
               "### motion [look] Motion and 3D at level 4\nwhy: the user chose design only\n## For you\n")

    def looked(self, *more):
        code, checks, err = self.check("looked", "forge-work/improve.md", self.SHOTS, *more)
        return code, checks and checks[0], err

    def shots(self, before, after, colour=(15, 123, 108)):
        """The shot of one screen in SHOTS/BEFORE (white) and SHOTS/AFTER (COLOUR; white: no visible change)."""
        for folder, rgb in ((before, (255, 255, 255)), (after, colour)):
            os.makedirs(os.path.join(self.root, self.SHOTS, folder), exist_ok=True)
            with open(os.path.join(self.root, self.SHOTS, folder, "home-390-light.png"), "wb") as handle:
                handle.write(png(rgb))

    def test_a_look_item_needs_its_report_and_a_change_that_shows(self):
        write(self.root, "forge-work/improve.md", self.IMPROVE % "")
        code, check, _ = self.looked()
        self.assertEqual((code, check["what"]), (1, "forge-work/improve.md: 1 look item(s) under ## Fixed, not built "
                                                    "and shown as forge-improve says"))
        self.assertEqual(check["output"][0], "design [look] A redesign at level 4 (Showpiece): its report "
                                             "forge-work/design/redesign.md is not a file in the project that holds "
                                             "something")
        self.assertRegex(check["output"][1], r"^changed\.py forge-work/improve/shots/before forge-work/improve/shots/"
                                             r"after exits 2: error: .*shots/before")  # changed.py names what is missing
        write(self.root, "forge-work/design/redesign.md", "")
        self.shots("before", "after", colour=(255, 255, 255))
        code, check, _ = self.looked()
        self.assertEqual(code, 1)
        self.assertTrue(check["output"][0].endswith("is not a file in the project that holds something"), check)
        self.assertRegex(check["output"][1], r"exits 1: NO VISIBLE CHANGE in any pair: none reaches 2(\.0)?% of the "
                                             r"pixels\. Usually .*the app was not rebuilt or restarted")
        write(self.root, "forge-work/design/redesign.md", "# Redesign\nLevel: 4 (Showpiece)\n")
        self.shots("before", "after")
        code, check, _ = self.looked()
        self.assertEqual((code, check["what"]), (0, "forge-work/improve.md: 1 look item(s) under ## Fixed, each with its "
                                                    "report; changed.py %s/before %s/after: VISIBLE CHANGE"
                                                    % (self.SHOTS, self.SHOTS)))

    def test_a_motion_pick_shows_in_the_frames(self):
        write(self.root, "forge-work/motion.md", "Level: 2 (Polished)\n")
        write(self.root, "forge-work/improve.md", "## Fixed\n### motion [look] Motion at level 2\n- **report:** "
                                                  "`forge-work/motion.md`.\n")
        self.shots("before", "after", colour=(255, 255, 255))  # the stills: the page at rest, as it was
        code, check, _ = self.looked()
        self.assertEqual(code, 1)
        self.assertIn("changed.py forge-work/improve/shots/before-frames forge-work/improve/shots/after-frames exits 2",
                      check["output"][0])
        self.shots("before-frames", "after-frames")
        self.assertEqual(self.looked()[0], 0)

    def test_a_look_item_with_no_report_line_or_one_outside_the_project(self):
        self.shots("before", "after")
        write(self.root, "forge-work/improve.md", "## Fixed\n### Dashboard: the statistics screen at level 3\nsee: /stats\n")
        code, check, _ = self.looked()
        self.assertEqual((code, check["output"][0]), (1, "Dashboard: the statistics screen at level 3: no `report:` line "
                                                         "that names its report"))
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        write(outside, "report.md", "Level: 3\n")
        write(self.root, "forge-work/dashboard.md", "Level: 3\n")
        for path in (os.path.join(outside, "report.md"), "../report.md", "forge-work/../../report.md",
                     "forge-work/../forge-work/dashboard.md"):
            with self.subTest(path=path):
                write(self.root, "forge-work/improve.md", "## Fixed\n### dashboard [look] x\n- **report:** `%s`\n" % path)
                self.assertEqual(self.looked()[0], 1)
        write(self.root, "forge-work/improve.md", "## Fixed\n### dashboard [look] x\n- **report:** `forge-work/dashboard.md`.\n")
        self.assertEqual(self.looked()[0], 0)

    def test_the_report_is_the_look_report_of_its_part(self):
        """VG1-N5: any file that held something passed as a report, so the level check of the look reports, which runs
        by their fixed names, was never asked. A dashboard has one report per screen of numbers."""
        self.shots("before", "after")
        for name in ("package.json", "forge-work/motion.md", "forge-work/design/redesign.md", "forge-work/dashboard.md",
                     "forge-work/dashboard-admin.md", "forge-work/dashboard-old.md.bak"):
            write(self.root, name, "Level: 3\n")
        for heading, report, ok in (("design [look] x", "package.json", False), ("design [look] x", "forge-work/motion.md",
                                    False), ("design [look] x", "forge-work/design/redesign.md", True),
                                    ("dashboard [look] x", "forge-work/dashboard-admin.md", True),
                                    ("dashboard [look] x", "forge-work/dashboard-old.md.bak", False),
                                    ("Dashboard: the statistics [look]", "forge-work/dashboard.md", True)):
            with self.subTest(heading=heading, report=report):
                write(self.root, "forge-work/improve.md", "## Fixed\n### %s\nreport: %s\n" % (heading, report))
                code, check, _ = self.looked()
                self.assertEqual(code, 0 if ok else 1, check)
                if not ok:
                    self.assertIn("its report %s is not its look report, " % report, check["output"][0])
        write(self.root, "forge-work/improve.md", "## Fixed\n### design [look] x\nreport: package.json\n")
        self.assertTrue(self.looked()[1]["output"][0].endswith("is not its look report, forge-work/design/redesign.md"))

    def test_a_look_item_names_its_part_first(self):
        """V3G1-N1: the gate runs each part's checks only for a heading that starts with design, motion or dashboard
        (picked() in phasecheck.py), so `### [look] The whole look` skipped every level and motion check."""
        self.shots("before", "after")
        write(self.root, "forge-work/motion.md", "Level: 4 (Showpiece)\n")
        for heading in ("[look] The whole look at level 4", "3D and motion [look]", "The look [look]", "Designs [look]"):
            with self.subTest(heading=heading):
                write(self.root, "forge-work/improve.md", "## Fixed\n### %s\nreport: forge-work/motion.md\n" % heading)
                code, check, _ = self.looked()
                self.assertEqual((code, check["output"][0]), (1, "%s: name its part first: ### design [look], ### "
                                                                 "motion [look] or ### dashboard [look] (forge-improve "
                                                                 "Step 2), one item per part" % heading))
        write(self.root, "forge-work/improve.md", "## Fixed\n###  motion  [look] x\nreport: forge-work/motion.md\n")
        self.shots("before-frames", "after-frames")
        self.assertEqual(self.looked()[0], 0)

    def test_since_leaves_out_what_an_earlier_round_left(self):
        """R63: improve/shots and a redesign.md of an earlier round, with a visible change, passed a round that built
        nothing. With --since (the gate's last go) the report and both shots of a pair must be newer."""
        write(self.root, "forge-work/improve.md", self.IMPROVE % "")
        write(self.root, "forge-work/design/redesign.md", "# Redesign\nLevel: 4 (Showpiece)\n")
        self.shots("before", "after")
        self.assertEqual(self.looked("--since", SINCE)[0], 0)
        self.age("forge-work/design/redesign.md", self.SHOTS)
        self.assertEqual(self.looked()[0], 0)  # without --since: no round is known
        code, check, _ = self.looked("--since", SINCE)
        self.assertEqual((code, check["output"][:2]), (1, [
            "design [look] A redesign at level 4 (Showpiece): its report forge-work/design/redesign.md is older than "
            "the last go: it is an earlier round's",
            "changed.py %s/before %s/after: no pair of shots newer than the last go, so none of this round"
            % (self.SHOTS, self.SHOTS)]))
        write(self.root, "forge-work/design/redesign.md", "# Redesign\nLevel: 4 (Showpiece)\n")
        self.shots("before", "after", colour=(255, 255, 255))  # this round: the before again, and no change
        self.age(os.path.join(self.SHOTS, "after"))
        self.assertIn("no pair of shots newer than the last go", self.looked("--since", SINCE)[1]["output"][0])
        self.shots("before", "after", colour=(255, 255, 255))
        self.assertIn("NO VISIBLE CHANGE in any pair of this round", self.looked("--since", SINCE)[1]["output"][0])
        self.shots("before", "after")
        self.assertEqual(self.looked("--since", SINCE)[0], 0)

    def test_findings_alone_and_look_items_in_comments_or_skipped_need_nothing(self):
        """A fix of a finding has its own proof (its test, or its shots under improve/shots/<ID>): a small one can stay
        under changed.py's bar, so a run of findings alone runs no changed.py here."""
        write(self.root, "forge-work/improve.md", self.IMPROVE.replace("### design [look]", "<!-- ### design [look]")
              .replace("pairs\n%s", "pairs\n-->\n%s") % "")
        code, check, _ = self.looked()
        self.assertEqual((code, check["what"]), (0, "forge-work/improve.md: 0 look item(s) under ## Fixed, each with its "
                                                    "report"))
        write(self.root, "forge-work/improve.md", "# Improve\n## To do\n## Fixed\n### A001 [high] x\n## Skipped\n")
        self.shots("before", "after", colour=(255, 255, 255))
        self.assertEqual(self.looked()[0], 0)
        self.assertEqual(self.check("looked", "forge-work/nowhere.md", self.SHOTS)[0], 2)


class MovedTests(Look):
    """W-forge-2: no check proved that anything moves or that a scene went live. From level 2 the entrance frames of a
    screen (f1 to f4 at 390) must move; from look level 4, and at dashboard level 5, a scene's frames (s1 to s6 at
    1440) too. One screen that moves is enough for each: a form may stay still."""

    def moved(self, *args):
        return self.check("moved", *args)

    def test_entrance_frames_from_level_2(self):
        frames(self.root, "after")
        frames(self.root, "after", name="settings", moving=False)
        for level in "234":  # at dashboard level 5 a scene too
            code, checks, _ = self.moved("after", "--level", level, "--domain", "dashboard")
            self.assertEqual((code, checks[0]["ok"]), (0, True), checks)
            self.assertEqual(checks[0]["what"], "dashboard level %s asks for the entrance frames f1 to f4 at 390, from "
                                                "level 2: 1 of 2 screen(s) move in after" % level)
            self.assertEqual(checks[0]["output"], ["home-390: something moves", "settings-390: nothing moves",
                                                   lookcheck.LOADING])  # V3G1-N2: loading alone moves them too
        self.assertIn("Look at f1", lookcheck.LOADING)
        self.assertEqual(self.moved("after", "--level", "1")[1], [{
            "ok": True, "what": "look level 1 asks for no frames: they start at level 2", "output": []}])

    def test_frames_that_are_missing_or_still_fail(self):
        frames(self.root, "after", moving=False)
        code, checks, _ = self.moved("after", "--level", "3")
        self.assertEqual((code, checks[0]["what"]), (1, "look level 3 asks for the entrance frames f1 to f4 at 390, from "
                                                        "level 2: nothing moves in them"))
        self.assertIn("--frames <paths>, then changed.py --moves on its <name>-390-f[1-4].png", checks[0]["output"][-1])
        shutil.rmtree(os.path.join(self.root, "after"))
        code, checks, _ = self.moved("after", "elsewhere", "--level", "2")
        self.assertEqual((code, checks[0]["what"]), (1, "look level 2 asks for the entrance frames f1 to f4 at 390, from "
                                                        "level 2: none in after or elsewhere"))

    def test_only_the_entrance_counts_never_the_scroll_frames(self):
        """f5 to f7 differ by the scroll alone, even where nothing moves (shots.example.mjs)."""
        frames(self.root, "after", moving=False)
        for number, shade in ((5, 10), (6, 90), (7, 170)):  # scrolled down: other parts of the page
            with open(os.path.join(self.root, "after", "home-390-f%d.png" % number), "wb") as handle:
                handle.write(png((shade, shade, shade)))
        self.assertEqual(self.moved("after", "--level", "2")[0], 1)
        for number in range(1, 5):  # the entrance at 1440 moves: --moves on it is a run of its own, not this check's
            with open(os.path.join(self.root, "after", "home-1440-f%d.png" % number), "wb") as handle:
                handle.write(png((30 * number, 0, 0)))
        self.assertEqual(self.moved("after", "--level", "2")[0], 1)

    def test_a_live_scene_that_moves_from_look_level_4(self):
        frames(self.root, "after")
        self.assertEqual([check["ok"] for check in self.moved("after", "--level", "3")[1]], [True])
        code, checks, _ = self.moved("after", "--level", "4")
        self.assertEqual((code, [check["ok"] for check in checks]), (1, [True, False]))
        self.assertEqual(checks[1]["what"], "look level 4 asks for the scene frames s1 to s6 at 1440, from level 4: none "
                                            "in after")
        self.assertIn("--scene-frames <paths>, then changed.py --moves on its <name>-1440-s*.png", checks[1]["output"][-1])
        frames(self.root, "after", kind="s", moving=False)  # a scene stuck on its poster stands still
        self.assertEqual(self.moved("after", "--level", "5")[1][1]["output"][0], "home-1440: nothing moves")
        frames(self.root, "after", name="map", kind="s")
        code, checks, _ = self.moved("after", "--level", "5")
        self.assertEqual((code, checks[1]["what"]), (0, "look level 5 asks for the scene frames s1 to s6 at 1440, from "
                                                        "level 4: 1 of 2 screen(s) move in after"))
        self.assertEqual(len(self.moved("after", "--level", "4", "--domain", "dashboard")[1]), 1)  # a scene at 5 only

    def test_frames_of_an_earlier_round_do_not_count(self):
        frames(self.root, "after")
        self.age("after")
        code, checks, _ = self.moved("after", "--level", "2", "--since", SINCE)
        self.assertEqual((code, checks[0]["output"][0]), (1, "home-390: from before the last go, so of an earlier round: "
                                                             "not counted"))
        self.assertEqual(self.moved("after", "--level", "2")[0], 0)
        frames(self.root, "after")
        self.assertEqual(self.moved("after", "--level", "2", "--since", SINCE)[0], 0)

    def test_the_level_on_record(self):
        frames(self.root, "after", moving=False)
        code, _, err = self.moved("after", "--level", "auto")
        self.assertEqual(code, 2)
        self.assertIn("no look level on record in %s" % os.path.join("forge-work", "levels.json"), err)
        write(self.root, "forge-work/levels.json", levels(look=1))
        self.assertEqual(self.moved("after", "--level", "auto")[0], 0)  # level 1 asks for no frames
        write(self.root, "forge-work/levels.json", levels(look=3, dashboard=1))
        self.assertEqual(self.moved("after", "--level", "auto")[0], 1)
        self.assertEqual(self.moved("after", "--level", "auto", "--domain", "dashboard")[0], 0)
        write(self.root, "forge-work/levels.json", '{"look": {"level": 9}}')
        self.assertEqual(self.moved("after", "--level", "auto")[0], 2)

    def test_a_linked_record_is_never_read(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        write(outside, "levels.json", levels(look=1))
        os.makedirs(os.path.join(self.root, "forge-work"))
        symlink(self, os.path.join(outside, "levels.json"), os.path.join(self.root, "forge-work", "levels.json"))
        code, _, err = self.moved("after", "--level", "auto")
        self.assertEqual(code, 2)
        self.assertIn("is a link, so it was not read", err)


class JudgedTests(Look):
    """W-forge-12: forge-build Step 3.2 writes the slice's ## Round 1 into review.md, so a build that skipped Step 7.4
    (the look review of every screen, after Step 7.3's after shots) still had a filled Round block."""
    REVIEW = "# Look review\n## Round 1 (2026-10-27, commit 3f2a1c9, judge: fresh eyes)\n| screen | score / 22 |\n"

    def judged(self, *more):
        code, checks, err = self.check("judged", "forge-work/design/review.md", "after", *more)
        return code, checks and checks[0], err

    def test_the_review_is_newer_than_the_after_shots(self):
        frames(self.root, "after")  # any shots: the after shots of Step 7.3
        write(self.root, "forge-work/design/review.md", self.REVIEW)
        code, check, _ = self.judged()
        self.assertEqual((code, check["what"]), (0, "forge-work/design/review.md: its last round (Round 1 (2026-10-27, "
                                                    "commit 3f2a1c9, judge: fresh eyes)) is newer than the after shots "
                                                    "in after"))
        self.age("forge-work/design/review.md")  # the slice's round, from before the after shots
        code, check, _ = self.judged()
        self.assertEqual((code, check["what"]), (1, "forge-work/design/review.md is older than the after shots in after: "
                                                    "its last round (Round 1 (2026-10-27, commit 3f2a1c9, judge: fresh "
                                                    "eyes)) is from before Step 7.3"))
        self.assertIn("Step 7.4: the look review on every screen as built", check["output"][0])
        write(self.root, "forge-work/design/review.md", self.REVIEW + "## Round 2 (2026-10-28)\n| home | 19 |\n")
        self.assertEqual(self.judged("--since", SINCE)[0], 0)
        self.age("after")
        self.assertEqual(self.judged("--since", "2999-01-01T00:00:00+00:00")[0], 1)  # older than the last go

    def test_no_round_no_shots_or_no_review(self):
        write(self.root, "forge-work/design/review.md", "# Look review\n<!-- ## Round 1 -->\n")
        frames(self.root, "after")
        self.assertEqual(self.judged()[1]["what"], "forge-work/design/review.md: no ## Round block")
        write(self.root, "forge-work/design/review.md", self.REVIEW)
        shutil.rmtree(os.path.join(self.root, "after"))
        code, check, _ = self.judged()
        self.assertEqual((code, check["what"]), (1, "forge-work/design/review.md: no after shots in after yet"))
        self.assertIn("Step 7.3: the after shots of every screen first", check["output"][0])
        os.remove(os.path.join(self.root, "forge-work", "design", "review.md"))
        self.assertEqual(self.judged()[1]["what"], "forge-work/design/review.md is missing")


class CommandLineTests(Look):
    def test_plain_output_on_a_cp1252_pipe(self):
        frames(self.root, "after", name="café-→")  # cp1252 has the e with its accent, not the arrow
        code, out, err = run_cp1252(SCRIPT, "moved", "after", "--level", "2", cwd=self.root)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("ok    look level 2 asks for the entrance frames", out)
        self.assertIn("café-\\u2192-390: something moves", out)

    def test_usage(self):
        for argv in ([], ["moved", "after"], ["moved", "after", "--level", "6"], ["looked", "x"], ["judged", "x"],
                     ["moved", "after", "--level", "2", "--since", "yesterday"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as stop, \
                    contextlib.redirect_stderr(io.StringIO()):
                lookcheck.main(argv)
            self.assertEqual(stop.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
