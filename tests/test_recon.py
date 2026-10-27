"""Tests for forge-recon's template, recon-map.md.

The recon gate refuses a recon.md that still has a template placeholder, but it only finds the short
one-line kind (`{{...}}`, up to 80 characters). A longer placeholder, or one split over two lines, slips
past it: a recon.md with the terms check left blank once passed the gate. Tables must keep their
columns: a `|` inside a cell adds one."""

import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load  # noqa: E402

phasecheck = load("forge", "phasecheck")
TEMPLATE = os.path.join(ROOT, "forge-recon", "recon-map.md")
PLACEHOLDER = re.compile(r"\{\{.*?\}\}", re.S)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def visible(text):
    """The template without its comments and code blocks, the parts the gate reads."""
    return phasecheck.UNSEEN.sub("", text)


class ReconTemplateTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, "forge-work"))

    def gate(self, text):
        with open(os.path.join(self.root, "forge-work", "recon.md"), "w", encoding="utf-8") as handle:
            handle.write(text)
        return phasecheck.check_file(self.root, "forge-work/recon.md", phasecheck.TODO)

    def test_filled_in_it_passes(self):
        passed, message = self.gate(PLACEHOLDER.sub("x", visible(read(TEMPLATE))))
        self.assertTrue(passed, message)

    def test_each_placeholder_left_alone_fails(self):
        text = visible(read(TEMPLATE))
        found = PLACEHOLDER.findall(text)
        self.assertGreater(len(found), 10)
        for index, placeholder in enumerate(found):
            with self.subTest(placeholder=placeholder[:60]):
                count = iter(range(len(found)))
                left = PLACEHOLDER.sub(lambda match: match.group(0) if next(count) == index else "x", text)
                passed, message = self.gate(left)
                self.assertFalse(passed, "the gate misses %r: keep it on one line, at most 80 characters"
                                 % placeholder)
                self.assertIn("1 template placeholder(s)", message)

    def test_tables_keep_their_columns(self):
        table = []
        for number, line in enumerate(read(TEMPLATE).splitlines() + [""], 1):
            if line.startswith("|"):
                table.append((number, line.count("|")))
                continue
            for row, bars in table:
                with self.subTest(line=row):
                    self.assertEqual(bars, table[0][1], "a | inside a cell adds a column: write 'or'")
            table = []


if __name__ == "__main__":
    unittest.main()
