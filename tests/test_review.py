"""Tests for forge-design/review.md (the look review) and the shots part of forge-design/steps/brand.md:
how the shots script is copied and Playwright installed, what the fresh-eyes judge is given and asked,
how the after shots keep both themes, and the redesign rule that steps/design.md and restyle.md share."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT  # noqa: E402

REVIEW = os.path.join(ROOT, "forge-design", "review.md")
BRAND = os.path.join(ROOT, "forge-design", "steps", "brand.md")


def flat(path, heading=None):
    """The file as one line of words (line breaks do not matter), or only its part under HEADING."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if heading:
        start = text.index(heading)
        end = text.find("\n## ", start + len(heading))
        text = text[start:end if end > 0 else len(text)]
    return " ".join(text.split())


class ReviewTests(unittest.TestCase):
    def test_playwright_never_goes_into_the_project_itself(self):
        """In a new app the shots come before /forge-build's scaffold, which a package.json in the root blocks."""
        shots = flat(REVIEW, "## 1. Take the shots")
        self.assertIn("npm install --prefix forge-work/design @playwright/test", shots)
        self.assertNotIn("npm i -D", shots)

    def test_the_script_is_copied_again_at_each_run(self):
        """An older copy reads the new flags wrongly: the last --state for every path, with no error."""
        shots = flat(REVIEW, "## 1. Take the shots")
        self.assertNotIn("Once: `mkdir", shots)
        self.assertIn("At the start of each run", shots)

    def test_after_shots_keep_both_themes_of_an_app_that_now_keeps_one(self):
        shots = flat(REVIEW, "## 1. Take the shots")
        self.assertIn("give the after command `--init-script forge-work/design/theme.js` all the same", shots)
        self.assertIn("kept profile of section 5, item 2 now, with the before shots", shots)

    def test_the_judge_gets_the_level_row_the_opening_theme_and_the_keep_rule(self):
        judge = flat(REVIEW, "## 2. Fresh eyes")
        for words in ('"What each look level shows"', "The theme it opens in:", "- Big enough:",
                      "under ## Keep is the app's own taste, not a fault", "the five answers"):
            with self.subTest(words=words):
                self.assertIn(words, judge)

    def test_the_judge_sees_depth_with_motion_on(self):
        """A plain run is the reduced-motion version: depth.js lays cards flat and a scene shows its poster,
        so At rest and Big enough at level 3 and up are judged on the movement run's stills."""
        judge = flat(REVIEW, "## 2. Fresh eyes")
        for words in ("from level 3 also those of the stills its movement run took", "These are the reduced-motion "
                      "version", "The same screens with motion on:", "those with motion on where given",
                      "with `--dark-selector`, the brief's `Dark theme:` line"):
            with self.subTest(words=words):
                self.assertIn(words, judge)
        self.assertIn("From level 3 judge at rest and big enough on the movement run's stills", flat(REVIEW, "## 3."))

    def test_the_example_commands_carry_the_checks_and_the_theme(self):
        with open(REVIEW, encoding="utf-8") as handle:
            lines = [line for line in handle if line.startswith("node forge-work/design/shots.mjs")]
        self.assertEqual(len(lines), 3, lines)
        for line in lines:
            with self.subTest(line=line[:80]):
                self.assertIn("--init-script forge-work/design/theme.js", line)
                self.assertLess(line.index("--state"), line.index("/dashboard"))  # a signed-in path after its state
        self.assertIn("round-1 --overflow --contrast", lines[1])  # each round's checks come before the judge

    def test_a_board_built_to_scroll_sideways_is_no_fault(self):
        shots = flat(REVIEW, "## 1. Take the shots")
        self.assertIn("A panel built to scroll sideways (a board of columns, a timeline) is no fault", shots)
        self.assertIn("names as not measured (up to five, with their place)", shots)

    def test_a_redesign_may_change_the_markup_but_never_what_the_app_does(self):
        redesign = flat(REVIEW, "## Redesign: an app that exists")
        self.assertNotIn("No markup or logic change", redesign)
        self.assertIn("The markup may change as far as the picked concept and the level need", redesign)
        self.assertIn("never what the app does", redesign)
        self.assertIn("../forge-design/restyle.md", redesign)
        self.assertIn("../forge-check/testdb.py", redesign)  # tests can empty the database they reach

    def test_the_hand_over_says_who_picked_and_how_laravel_shows_it(self):
        show = flat(REVIEW, "## 5. Show")
        for words in ("`Picked by:`", "public/hot", "sail npm run build", "rules.md section 9's commands"):
            with self.subTest(words=words):
                self.assertIn(words, show)


class BrandTests(unittest.TestCase):
    def test_brand_copies_the_script_and_tests_the_old_worker(self):
        text = flat(BRAND)
        self.assertNotIn("copy it once", text)
        self.assertIn("kept profile of review.md section 5, item 2 now", text)
        self.assertNotIn("reload twice", text)  # a fresh profile shows the new look either way

    def test_brand_moves_the_branch_and_names_every_gate_check(self):
        text = flat(BRAND)
        self.assertNotIn("the one command that switches", text)  # a plain git switch fails in their folder
        self.assertIn("rules.md section 9's commands", text)
        self.assertIn("changed.py finds a visible change between forge-work/brand/shots/before and after", text)
        self.assertIn("the scene posters", text)  # they keep the old colours wherever the scene does not run


if __name__ == "__main__":
    unittest.main()
