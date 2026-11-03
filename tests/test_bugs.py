"""Tests for forge-test/bugs.py: reading forge-work/bugs.md, the exit codes, the JSON shape,
and that anything that looks like a bug heading but is not in the right form is an error,
never skipped."""

import codecs
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load  # noqa: E402

bugs = load("forge-test", "bugs")
SCRIPT = os.path.join(ROOT, "forge-test", "bugs.py")
BOM, ZERO_WIDTH_SPACE, WORD_JOINER = chr(0xFEFF), chr(0x200B), chr(0x2060)

SAMPLE = """# Bugs

## B001 [low] [open] The footer overlaps the button at 390px
case: F02-E5
## B002 [high] [open] Booking fails when the name has an accent
steps: pick 10:00, type the name "Zoe", confirm
## B003 [critical] [fixed] A second user can see someone else's booking
fixed in: 3f2a1c9
## B004 [medium] [wontfix] The date picker starts on Sunday
the user said: "fine, leave it"
## B005 [critical] [open] Paying twice charges the card twice

## To check
- the calendar feels slow with 200 events
"""


def run(*args):
    """Run main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = bugs.main(list(args))
    return code, out.getvalue(), err.getvalue()


def one_problem(test, line):
    """Parse a bugs.md with this line on line 3 and return the single problem it must cause."""
    found, problems = bugs.parse("# Bugs\n\n" + line + "\nsome text\n")
    test.assertEqual(found, [], "a line that is not in the exact form must not count as a bug")
    test.assertEqual(len(problems), 1, "it must be reported, never skipped")
    test.assertEqual(problems[0][0], 3)
    return problems[0][2]


class TempFiles(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.folder)

    def write(self, text, name="bugs.md", encoding="utf-8"):
        path = os.path.join(self.folder, name)
        with open(path, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
        return path

    def write_bytes(self, data, name="bugs.md"):
        path = os.path.join(self.folder, name)
        with open(path, "wb") as handle:
            handle.write(data)
        return path


class Parse(unittest.TestCase):
    def test_reads_every_bug(self):
        found, problems = bugs.parse(SAMPLE)
        self.assertEqual(problems, [])
        self.assertEqual([bug["id"] for bug in found], ["B001", "B002", "B003", "B004", "B005"])
        self.assertEqual(found[1], {"id": "B002", "severity": "high", "status": "open",
                                    "title": "Booking fails when the name has an accent", "line": 5})
        self.assertEqual(found[2]["status"], "fixed")
        self.assertEqual(found[3]["status"], "wontfix")

    def test_other_text_is_fine(self):
        text = ("# Bugs\n## To check\n## to check: later\n### Steps\nBug B001 was found on Monday.\n"
                "No bugs found.\nB2B checkout is slow on low-end phones.\n")
        self.assertEqual(bugs.parse(text), ([], []))

    def test_free_text_under_a_bug_is_fine(self):
        text = ("# Bugs\n\n## B001 [high] [fixed] Booking fails with accents\nevidence:\n"
                "B001 [screenshot](../forge-work/clone-screens/s03.png)\n"
                "see the [open](https://example.test/issues) issues\n"
                "```\n# B001 repro script\n## install the packages\n```\n\n"
                "## To check\n- B002 [maybe a duplicate of B001] the calendar is slow\n"
                "- B003 slow on low-end phones\n")
        found, problems = bugs.parse(text)
        self.assertEqual(problems, [])
        self.assertEqual([bug["id"] for bug in found], ["B001"])

    def test_the_title_is_required(self):
        for text in ["", "\n\n", "## B001 [high] [open] No title above me\n", "# Test plan: demo\n"]:
            with self.subTest(text=text):
                problems = bugs.parse(text)[1]
                self.assertEqual(len(problems), 1)
                self.assertEqual(problems[0][0], 1)
                self.assertIn("'# Bugs'", problems[0][2])

    def test_extra_spaces_and_line_endings(self):
        found, problems = bugs.parse("# Bugs\r\n## B001  [high]   [open]  Title  \r\n## B002 [low] [open] Next\r")
        self.assertEqual(problems, [])
        self.assertEqual([(bug["title"], bug["line"]) for bug in found], [("Title", 2), ("Next", 3)])

    def test_malformed_headings_are_never_skipped(self):
        cases = {
            "### B001 [high] [open] Title": "two # signs",
            "# B001 [high] [open] Title": "two # signs",
            "- B001 [high] [open] Title": "two # signs",
            "**B001** [high] [open] Title": "two # signs",
            "##B001 [high] [open] Title": "one space after the ##",
            "##\tB001 [high] [open] Title": "not a tab",
            "  ## B001 [high] [open] Title": "very start of the line",
            "## B1 [high] [open] Title": "like B001",
            "## b001 [high] [open] Title": "like B001",
            "## BUG-001 [high] [open] Title": "like B001",
            "## Bug 1: login is broken": "like B001",
            "## [high] [open] Title": "like B001",
            "## B001 [High] [open] Title": "the severity",
            "## B001 [S1] [open] Title": "the severity",
            "## B001 high open Title": "the severity",
            "## B001 [high] Title": "the status",
            "## B001 [high] [won't fix] Title": "the status",
            "## B001 [high] [open]": "title is missing",
            "## B001": "the severity",
            "## Login broken [high] [open]": "like B001",
        }
        for line, expected in cases.items():
            with self.subTest(line=line):
                self.assertIn(expected, one_problem(self, line))

    def test_every_other_level_2_heading_is_an_error(self):
        for line in ["## Background", "## B2B checkout notes", "## Notes", "## Bug: paying twice",
                     "## Critical: paying twice charges the card twice",
                     "## Paying twice charges the card twice (critical, open)"]:
            with self.subTest(line=line):
                self.assertIn("or ## To check", one_problem(self, line))

    def test_markdown_prefixes_do_not_hide_a_bug(self):
        """Lists, quotes, tables, task boxes, indents: a bug written like this is reported."""
        for line in ["+ B001 [critical] [open] Payment charged twice",
                     "* B001 [critical] [open] Payment charged twice",
                     "1. B001 [critical] [open] Payment charged twice",
                     "1) B001 high Payment charged twice",
                     "> ## B001 [critical] [open] Payment charged twice",
                     "- [ ] B001 [critical] [open] Payment charged twice",
                     "- [x] B001 [critical] [open] Payment charged twice",
                     "| B001 | critical | open | Payment charged twice |",
                     "    ## B001 [critical] [open] Payment charged twice",
                     "\t## B001 [critical] [open] Payment charged twice",
                     "B001 [high] [open] Payment charged twice",
                     "B001: [critical] [open] Payment charged twice",
                     "- B001 critical: payment charged twice",
                     "- Bug #1: payment charged twice (critical, open)",
                     "## Bug #1: payment charged twice (critical, open)",
                     "## #B001 critical open Payment charged twice",
                     "### Bug 2 login broken",
                     "Payment charged twice [critical] [open]"]:
            with self.subTest(line=line):
                one_problem(self, line)

    def test_invisible_characters_do_not_hide_a_bug(self):
        text = ("# Bugs\n\n## B001 [low] [open] Footer overlaps\n"
                + BOM + "## B002 [critical] [open] Payment charged twice\n"
                + ZERO_WIDTH_SPACE + "## B003 [high] [open] Login broken\n"
                + "## B004 [medium] [open] Slow" + WORD_JOINER + "\n")
        found, problems = bugs.parse(text)
        self.assertEqual(problems, [])
        self.assertEqual([(bug["id"], bug["severity"]) for bug in found],
                         [("B001", "low"), ("B002", "critical"), ("B003", "high"), ("B004", "medium")])
        self.assertEqual(found[3]["title"], "Slow")

    def test_bug_headings_in_a_code_block_count(self):
        found, problems = bugs.parse("# Bugs\n```\n## B001 [critical] [open] In a code block\n```\n")
        self.assertEqual((problems, [bug["id"] for bug in found]), ([], ["B001"]))
        problem = bugs.parse("# Bugs\n~~~\n- B002 [critical] [open] Bad form\n~~~\n")[1]
        self.assertEqual([number for number, _, _ in problem], [3])

    def test_an_unclosed_code_block_is_an_error(self):
        problems = bugs.parse("# Bugs\n\n## B001 [high] [open] Crash\n```\nlog\n## Notes\n")[1]
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][:2], (4, "```"))
        self.assertIn("never closed", problems[0][2])

    def test_every_problem_is_reported(self):
        text = "# Bugs\n## B001 [High] [open] A\n## B002 [high] [open] Fine\n- B003 [low] [open] C\n## Notes\n"
        found, problems = bugs.parse(text)
        self.assertEqual([bug["id"] for bug in found], ["B002"])
        self.assertEqual([number for number, _, _ in problems], [2, 4, 5])

    def test_duplicate_id_is_an_error(self):
        found, problems = bugs.parse("# Bugs\n## B001 [high] [open] One\n\n## B001 [low] [open] Two\n")
        self.assertEqual(len(found), 1)
        self.assertEqual(problems[0][0], 4)
        self.assertIn("already used on line 2", problems[0][2])

    def test_long_odd_lines_are_quick(self):
        """A garbage line must not make the check hang (no slow regex backtracking)."""
        start = time.time()
        bugs.parse("# Bugs\nB" + " " * 100000 + "x\n- b" + " \t" * 50000 + "1 high\n")
        self.assertLess(time.time() - start, 5)

    def test_ids_can_grow_past_999(self):
        found, problems = bugs.parse("# Bugs\n## B1000 [low] [open] The thousandth bug\n")
        self.assertEqual((found[0]["id"], problems), ("B1000", []))


class Summary(unittest.TestCase):
    def test_open_bugs_sorted_most_severe_first(self):
        found, _ = bugs.parse(SAMPLE)
        findings, summary = bugs.summarize(found, "forge-work/bugs.md", "high")
        self.assertEqual([bug["id"] for bug in findings], ["B005", "B002", "B001"])
        self.assertEqual(findings[0]["where"], "forge-work/bugs.md:11")
        self.assertEqual((summary["open"], summary["fixed"], summary["wontfix"], summary["total"]), (3, 1, 1, 5))
        self.assertEqual(summary["open_by_severity"], {"critical": 1, "high": 1, "medium": 0, "low": 1})
        self.assertEqual(summary["all_by_severity"], {"critical": 2, "high": 1, "medium": 1, "low": 1})
        self.assertTrue(summary["failed"])

    def test_findings_say_why_and_how_to_fix(self):
        found, _ = bugs.parse(SAMPLE)
        findings, _ = bugs.summarize(found, "bugs.md", "high")
        for finding in findings:
            self.assertTrue(finding["why"] and finding["fix"])
        self.assertIn("blocks the test phase", findings[0]["why"])
        self.assertNotIn("blocks", findings[2]["why"])  # a low bug does not block at --fail-on high
        self.assertNotIn("why", found[0])  # the plain bug list stays plain

    def test_only_open_bugs_count_for_the_verdict(self):
        found, _ = bugs.parse("# Bugs\n## B001 [critical] [fixed] A\n## B002 [critical] [wontfix] B\n")
        findings, summary = bugs.summarize(found, "bugs.md", "low")
        self.assertEqual((findings, summary["failed"]), ([], False))


class Cli(TempFiles):
    def test_open_high_bug_fails(self):
        code, out, err = run(self.write(SAMPLE))
        self.assertEqual(code, 1, err)
        self.assertLess(out.index("CRITICAL  B005"), out.index("HIGH      B002"))
        self.assertLess(out.index("HIGH      B002"), out.index("LOW       B001"))
        self.assertNotIn("B003", out)  # fixed bugs are not listed
        self.assertIn("details: " + os.path.join(self.folder, "bugs.md") + ", line 5", out)
        self.assertIn("5 bugs listed: 2 critical, 1 high, 1 medium, 1 low.", out)
        self.assertIn("3 open (1 critical, 1 high, 1 low), 1 fixed, 1 wontfix.", out)
        self.assertIn("FAIL: at least one open bug is high or worse.", out)

    def test_only_low_and_medium_open_passes_by_default(self):
        path = self.write("# Bugs\n## B001 [medium] [open] A\n## B002 [low] [open] B\n## B003 [high] [fixed] C\n")
        code, out, _ = run(path)
        self.assertEqual(code, 0)
        self.assertIn("PASS: no open bug is high or worse.", out)

    def test_fail_on(self):
        path = self.write("# Bugs\n## B001 [medium] [open] A\n## B002 [high] [open] B\n")
        self.assertEqual(run(path, "--fail-on", "low")[0], 1)
        self.assertEqual(run(path, "--fail-on", "medium")[0], 1)
        self.assertEqual(run(path, "--fail-on", "high")[0], 1)
        self.assertEqual(run(path, "--fail-on", "critical")[0], 0)

    def test_no_open_bugs(self):
        code, out, _ = run(self.write("# Bugs\n## B001 [critical] [fixed] A\n"))
        self.assertEqual(code, 0)
        self.assertIn("1 bug listed: 1 critical.", out)
        self.assertIn("No open bugs, 1 fixed, 0 wontfix.", out)

    def test_serious_wontfix_bugs_are_shown_not_only_counted(self):
        path = self.write("# Bugs\n## B001 [critical] [wontfix] Old browsers break\n## B002 [low] [wontfix] Typo\n")
        code, out, _ = run(path)
        self.assertEqual(code, 0)
        self.assertIn("Accepted by the user as wontfix", out)
        self.assertIn("CRITICAL  B001  Old browsers break", out)
        self.assertNotIn("Typo", out)

    def test_empty_bug_list_passes(self):
        code, out, _ = run(self.write("# Bugs\n\nNo bugs found.\n"))
        self.assertEqual(code, 0)
        self.assertIn("No bugs listed.", out)

    def test_empty_or_wrong_file_exits_2(self):
        for text in ["", "# Test plan: demo\n\n| case | flow |\n"]:
            with self.subTest(text=text):
                code, out, err = run(self.write(text))
                self.assertEqual((code, out), (2, ""))
                self.assertIn("'# Bugs'", err)

    def test_json_shape(self):
        code, out, _ = run(self.write(SAMPLE), "--json")
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(sorted(data), ["bugs", "findings", "summary"])
        self.assertEqual([bug["id"] for bug in data["findings"]], ["B005", "B002", "B001"])
        self.assertEqual(len(data["bugs"]), 5)
        for key in ("severity", "title", "where", "why", "fix", "id", "status", "line"):
            self.assertIn(key, data["findings"][0])
        self.assertEqual(data["summary"]["fail_on"], "high")
        self.assertEqual(data["summary"]["open_by_severity"]["critical"], 1)
        self.assertTrue(data["summary"]["failed"])

    def test_json_on_a_passing_file(self):
        code, out, _ = run(self.write("# Bugs\n## B001 [low] [open] A\n## B002 [high] [fixed] B\n"), "--json")
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual([bug["id"] for bug in data["findings"]], ["B001"])
        self.assertFalse(data["summary"]["failed"])

    def test_malformed_heading_exits_2_and_names_the_line(self):
        path = self.write("# Bugs\n## B001 [high] [open] Fine\n### B002 [critical] [open] Wrong level\n")
        code, out, err = run(path)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("line 3: ### B002 [critical] [open] Wrong level", err)
        self.assertIn("two # signs", err)
        self.assertIn("The form is: ## B001 [high] [open]", err)

    def test_malformed_heading_exits_2_with_json_too(self):
        code, out, err = run(self.write("# Bugs\n## B001 [High] [open] A\n"), "--json")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("line 2:", err)

    def test_long_line_is_cut_in_the_error(self):
        code, _, err = run(self.write("# Bugs\n## B001 [urgent] [open] " + "x" * 300 + "\n"))
        self.assertEqual(code, 2)
        self.assertIn("...", err)
        self.assertFalse(any(len(line) > 140 for line in err.splitlines()))

    def test_missing_file_and_folder_exit_2(self):
        code, _, err = run(os.path.join(self.folder, "nope.md"))
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)
        self.assertEqual(run(self.folder)[0], 2)

    def test_byte_order_mark_and_latin1_bytes(self):
        path = self.write(BOM + "# Bugs\n## B001 [high] [open] Starts with a BOM\n", encoding="utf-8")
        self.assertEqual(run(path)[0], 1)  # the title is read, not hidden by the BOM
        path = self.write("# Bugs\n## B001 [low] [open] Caf" + chr(0xE9) + "\n", name="latin.md", encoding="latin-1")
        self.assertEqual(run(path)[0], 0)  # not UTF-8: still read, the odd byte is replaced

    def test_utf16_and_utf32_with_a_byte_order_mark_are_read(self):
        text = "# Bugs\r\n\r\n## B001 [critical] [open] Payment charged twice\r\n"
        for codec, mark in (("utf-16-le", codecs.BOM_UTF16_LE), ("utf-16-be", codecs.BOM_UTF16_BE),
                            ("utf-32-le", codecs.BOM_UTF32_LE), ("utf-32-be", codecs.BOM_UTF32_BE)):
            with self.subTest(codec=codec):
                code, out, err = run(self.write_bytes(mark + text.encode(codec)))
                self.assertEqual(code, 1, err)  # PowerShell's `echo ... > bugs.md` must not hide B001
                self.assertIn("CRITICAL  B001  Payment charged twice", out)

    def test_nul_bytes_without_a_byte_order_mark_exit_2(self):
        code, out, err = run(self.write_bytes("# Bugs\n## B001 [critical] [open] X\n".encode("utf-16-le")))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("NUL bytes", err)

    def test_bad_usage_exits_2(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                bugs.main([self.write(SAMPLE), "--fail-on", "urgent"])
        self.assertEqual(caught.exception.code, 2)

    def test_runs_as_a_script(self):
        path = self.write(SAMPLE)
        done = subprocess.run([sys.executable, SCRIPT, path], timeout=60, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn("B005", done.stdout)

    def test_a_reader_that_stops_early_is_not_a_crash(self):
        """`bugs.py ... | head -1`: no traceback, and the exit code is still the verdict (0 here)."""
        lines = ["# Bugs"] + ["## B%05d [low] [open] Bug number %d" % (n, n) for n in range(1, 20001)]
        path = self.write("\n".join(lines) + "\n")
        for extra in ([], ["--json"]):
            with self.subTest(extra=extra):
                process = subprocess.Popen([sys.executable, SCRIPT, path] + extra,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                first = process.stdout.readline()
                process.stdout.close()  # the reader goes away, like head does
                err = process.stderr.read()
                process.stderr.close()
                self.assertEqual(process.wait(timeout=60), 0, err)
                self.assertTrue(first.strip())
                self.assertNotIn(b"Traceback", err)


class Output(unittest.TestCase):
    def test_say_survives_a_terminal_without_emoji(self):
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="ascii", newline="\n")  # \n, also on Windows: the escape counts here
        bugs.say("B001 Emoji " + chr(0x1F600) + " in the name", stream)
        stream.flush()
        self.assertEqual(raw.getvalue(), b"B001 Emoji " + b"\\" + b"U0001f600 in the name\n")

    def test_example_in_skill_md_is_valid(self):
        """The bug format shown in SKILL.md must be one bugs.py reads without problems."""
        with open(os.path.join(ROOT, "forge-test", "SKILL.md"), encoding="utf-8") as handle:
            text = handle.read()
        block = re.search(r"```markdown\n(# Bugs\n.*?)```", text, re.DOTALL)
        self.assertIsNotNone(block, "SKILL.md shows an example bugs.md in a ```markdown block")
        found, problems = bugs.parse(block.group(1))
        self.assertEqual(problems, [])
        self.assertEqual(len(found), 1)


if __name__ == "__main__":
    unittest.main()
