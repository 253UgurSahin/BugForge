"""Tests for forge-recon's template, recon-map.md.

The recon gate checks forge-work/recon.md with forge/doccheck.py against this template: a recon.md
fails while it still has one of the template's own placeholders, of any length and also when it is
wrapped over two lines, each {{...}} in code blocks too; only HTML comments do not count. A recon.md
with the terms check left blank once passed the gate, when it found only short one-line placeholders.
So the template filled in must pass, and each placeholder left alone must fail. Tables must keep
their columns: a `|` inside a cell adds one."""

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
from _load import ROOT, load  # noqa: E402

doccheck = load("forge", "doccheck")
TEMPLATE = os.path.join(ROOT, "forge-recon", "recon-map.md")
GATE = os.path.join(ROOT, "forge", "phasecheck.json")
PLACEHOLDER = re.compile(r"\{\{.*?\}\}", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def counted(text):
    """The template without its HTML comments: the part where the gate looks for placeholders."""
    return COMMENT.sub("", text)


class ReconTemplateTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)

    def gate(self, text):
        """doccheck.py on TEXT as recon.md with the template, as the recon gate runs it, its sections
        aside (test_phasecheck checks those). Returns (passed, what it printed)."""
        path = os.path.join(self.root, "recon.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = doccheck.main([path, "--template", TEMPLATE, "--no-sections", "--json"])
        self.assertIn(code, (0, 1), err.getvalue())
        lines = [line for check in json.loads(out.getvalue())["checks"] for line in [check["what"]] + check["output"]]
        return code == 0, "\n".join(lines)

    def test_the_recon_gate_checks_recon_md_against_this_template(self):
        checks = [entry["check"] for entry in json.loads(read(GATE))["recon"]]
        self.assertTrue(any(check[:2] == ["doc", "forge-work/recon.md"] and "../forge-recon/recon-map.md" in check
                            for check in checks), checks)

    def test_filled_in_it_passes(self):
        passed, message = self.gate(PLACEHOLDER.sub("x", read(TEMPLATE)))
        self.assertTrue(passed, message)

    def test_each_placeholder_left_alone_fails(self):
        text = counted(read(TEMPLATE))
        found = PLACEHOLDER.findall(text)
        self.assertGreater(len(found), 10)
        for index, placeholder in enumerate(found):
            for left_as in (placeholder, placeholder.replace(" ", "\n  ", 1)):  # as it is, and wrapped
                with self.subTest(placeholder=left_as[:60]):
                    count = iter(range(len(found)))
                    left = PLACEHOLDER.sub(lambda match: left_as if next(count) == index else "x", text)
                    passed, message = self.gate(left)
                    self.assertFalse(passed, "the gate misses %r" % left_as)
                    self.assertIn("1 placeholder(s)", message)

    def test_the_placeholders_in_code_blocks_count_too(self):
        """Flows and the data model are code blocks: their {{...}} need this app's own facts as well."""
        found = doccheck.placeholders(read(TEMPLATE))
        for placeholder in ("{{goal}}", "{{n}}", "{{Entity}}", "{{high | medium | guess}}"):
            self.assertIn(placeholder, found)

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
