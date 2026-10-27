"""Tests for forge-plan's two reference files: the plan.md template and profiles.md.

A template filled in the natural way, each sentence of a placeholder on its own line, must still pass
the plan gate: no placeholder may invite a second line that starts with `Profile:` or `PWA:`.
profiles.md stays within the spec's 300 lines."""

import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load  # noqa: E402

phasecheck = load("forge", "phasecheck")
TEMPLATE = os.path.join(ROOT, "forge-plan", "plan.md")
PROFILES = os.path.join(ROOT, "forge-plan", "profiles.md")
MAX_PROFILES_LINES = 300


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def fill_in(template):
    """The template as a writer fills it in: the two gate lines get a value, and every other
    placeholder becomes its own words with each sentence on a new line."""
    text = re.sub(r"(?m)^Profile: \{\{.*?\}\}$", "Profile: laravel", template)
    text = re.sub(r"(?m)^PWA: \{\{.*?\}\}$", "PWA: no", text)
    return re.sub(r"\{\{(.*?)\}\}", lambda match: re.sub(r"\.\s+", ".\n", match.group(1)), text, flags=re.S)


class PlanTemplateTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, "forge-work"))

    def check(self, text, label, *allowed):
        with open(os.path.join(self.root, "forge-work", "plan.md"), "w", encoding="utf-8") as handle:
            handle.write(text)
        return phasecheck.check_line(self.root, "forge-work/plan.md", label, *allowed)

    def test_a_natural_fill_in_passes_the_gate_lines(self):
        filled = fill_in(read(TEMPLATE))
        self.assertNotIn("{{", filled)
        for label, allowed in (("Profile", ("laravel", "django", "next", "static")), ("PWA", ("yes", "no"))):
            with self.subTest(label=label):
                passed, message = self.check(filled, label, *allowed)
                self.assertTrue(passed, message)

    def test_the_old_trap_is_caught(self):
        """The Why placeholder once ended with `PWA: why or why not.`: filled in, a second PWA line."""
        trap = "Profile: {{laravel | next}}\nPWA: {{yes | no}}\n\n## Why\n\n{{What was not chosen. PWA: why or why not.}}\n"
        passed, message = self.check(fill_in(trap), "PWA", "yes", "no")
        self.assertFalse(passed)
        self.assertIn("needs exactly one line", message)


class ProfilesTests(unittest.TestCase):
    def test_profiles_md_stays_short(self):
        lines = len(read(PROFILES).splitlines())
        self.assertLessEqual(lines, MAX_PROFILES_LINES, "profiles.md is %d lines: trim it" % lines)


if __name__ == "__main__":
    unittest.main()
