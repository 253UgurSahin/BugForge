"""Tests for forge/phasecheck.py: the exit checks of every phase, passing and failing, with the real
scripts of the other skills. Templates copied without filling them in fail; lines hidden in comments
or code blocks and decorated verdicts do not fool the line checks; a script that prints nothing,
crashes or hangs fails; a report older than --since fails. Every test works in its own folder."""

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402

phasecheck = load("forge", "phasecheck")
HAS_GIT = shutil.which("git") is not None
FEATURES = "feature,area,priority,original,clone,notes\nBook a slot,booking,must,yes,yes,\nReminders,email,could,yes,no,\n"
NO_BUGS = "# Bugs\n\nNo bugs found.\n"
SECTIONS = "".join("\n## %s\n\n%s\n" % pair for pair in (
    ("Entities and schema", "```sql\nCREATE TABLE bookings (id bigint PRIMARY KEY);\n```"),
    ("Routes and API", "| GET | /bookings | my bookings |"), ("Build order", "1. Vertical slice: book a slot"),
    ("Decisions log", "| 2026-10-27 | profile next | the user knows React |")))
PLAN = "# Plan: Slotwise\n\nProfile: next\nPWA: no\n" + SECTIONS
CASES = "| case | flow | type | steps | expected | auto | result |\n| --- | --- | --- | --- | --- | --- | --- |\n" \
        "| F01-H1 | book a slot | happy | pick 10:00 | booked | e2e | pass |\n" \
        "| F01-E1 | | edge: slot taken | | message | e2e | fail B001 |\n"
STATIC = os.path.join(ROOT, "forge-pack", "templates", "static")
COMPONENTS = "# Design\n\nProfile: next. Tailwind: 4.\nFont: Inter (SIL OFL, next/font).\n\n```css\n" \
             ":root { --color-<role>: <color.role>; }\n```\n\nButton\n  a11y  real <button>, visible focus\n"
SECURITY = "# Security check\nDate: 2026-10-27\nVerdict: PASS\nCounts: 0 critical, 0 high, 1 medium, 0 low\n"
OLD = 1500000000  # 2017: a file time long before any go


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def write(root, name, text):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def git(root, *args):
    subprocess.run(["git", "-C", root] + list(args), check=True, timeout=60,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def work_branch(root, branch="forge/improve-20261027"):
    """Make ROOT a git repository on BRANCH (no commits needed)."""
    git(root, "init", "-q")
    git(root, "symbolic-ref", "HEAD", "refs/heads/" + branch)


def copy_static_pack(root):
    """The static profile's container files from forge-pack, as forge-pack copies them."""
    for source, target in (("Dockerfile", "Dockerfile"), ("docker-compose.yml", "docker-compose.yml"),
                           ("nginx.conf", "nginx.conf"), ("dockerignore", ".dockerignore"),
                           ("env.example", ".env.example")):
        shutil.copy(os.path.join(STATIC, source), os.path.join(root, target))


def template(folder, name):
    return read(os.path.join(ROOT, folder, name))


# What each phase leaves behind when it is finished: enough for its exit checks to pass.
PASSING = {
    "recon": lambda root: (write(root, "forge-work/recon.md", "# Recon\n"),
                           write(root, "forge-work/features.csv", FEATURES)),
    "compare": lambda root: write(root, "forge-work/compare.md", "# Compare\n"),
    "plan": lambda root: (write(root, "forge-work/plan.md", PLAN),
                          write(root, "forge-work/features.csv", FEATURES)),
    "design": lambda root: (write(root, "forge-work/design/tokens.json", template("forge-design", "tokens.json")),
                            write(root, "forge-work/design/components.md", COMPONENTS)),
    "build": lambda root: (write(root, "forge-work/build-log.md", "| S01 | 2026-10-27 | done | booking page | |\n"),
                           write(root, "forge-work/features.csv", FEATURES), copy_static_pack(root)),
    "test": lambda root: (write(root, "forge-work/test-plan.md", "# Test plan\n\n## Cases\n\n" + CASES),
                          write(root, "forge-work/bugs.md", NO_BUGS)),
    "diff": lambda root: write(root, "forge-work/features.csv", FEATURES),
    "brand": lambda root: (write(root, "forge-work/brand.json", '{"name": "Slotwise", "avoid": ["Calendly"]}'),
                           write(root, "index.html", "<title>Slotwise</title>\n")),
    "launch": lambda root: write(root, "forge-work/launch.md", "# Launch\n"),
    "secure": lambda root: (write(root, "forge-work/security.md", SECURITY),
                            write(root, "index.html", "<title>Slotwise</title>\n")),
    "pack": copy_static_pack,
    "audit": lambda root: write(root, "forge-work/audit.md", "# Audit\n"),
    "inspect": lambda root: write(root, "forge-work/inspect.md", "# Inspect\n"),
    "improve": lambda root: (write(root, "forge-work/improve.md", "# Improve\n"), work_branch(root)),
}


class Checks(unittest.TestCase):
    """A temporary project folder; phasecheck.py runs in it as if from the project root."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def run_main(self, *args):
        out, err, before = io.StringIO(), io.StringIO(), os.getcwd()
        os.chdir(self.root)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = phasecheck.main(list(args))
        finally:
            os.chdir(before)
        return code, out.getvalue(), err.getvalue()

    def finish(self, *phases):
        for phase in phases:
            PASSING[phase](self.root)

    def assert_passes(self, phase, *args):
        code, out, err = self.run_main(phase, *args)
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("PASS: every exit check of %s passes." % phase, out)
        self.assertNotIn("FAIL", out)
        return out

    def assert_fails(self, phase, *expected, args=()):
        code, out, err = self.run_main(phase, *args)
        self.assertEqual((code, err), (1, ""), out)
        self.assertIn("FAIL: %s is not finished" % phase, out)
        for text in expected:
            self.assertIn(text, out)
        return out


class TableTests(unittest.TestCase):
    def test_every_script_the_checks_run_exists(self):
        for phase, checks in phasecheck.CHECKS.items():
            for check, *args in checks:
                if check is phasecheck.check_run:
                    self.assertTrue(os.path.isfile(os.path.join(ROOT, args[0])), "%s: %s" % (phase, args[0]))

    def test_the_plan_sections_are_headings_of_the_plan_template(self):
        headings = [line[3:] for line in template("forge-plan", "plan.md").splitlines() if line.startswith("## ")]
        for title in phasecheck.PLAN_SECTIONS:
            self.assertIn(title, headings)

    def test_every_fresh_report_is_a_file_its_phase_checks(self):
        for phase, name in phasecheck.FRESH.items():
            self.assertIn(name, [args[0] for _, *args in phasecheck.CHECKS[phase]])


class PhaseTests(Checks):
    def test_every_phase_passes_when_its_work_is_there(self):
        for phase in phasecheck.CHECKS:
            if phase == "improve" and not HAS_GIT:
                continue  # its check runs gitguard.py, which needs git
            with self.subTest(phase=phase):
                self.finish(phase)
                self.assert_passes(phase)

    def test_every_phase_fails_in_an_empty_project(self):
        for phase in phasecheck.CHECKS:
            with self.subTest(phase=phase):
                self.assert_fails(phase)

    def test_a_missing_file_is_named_once(self):
        out = self.assert_fails("plan", "forge-work/plan.md is missing", "forge-work/features.csv is missing")
        self.assertEqual(out.count("forge-work/plan.md is missing"), 1)

    def test_an_empty_file_is_not_enough(self):
        write(self.root, "forge-work/compare.md", " \n\n")
        self.assert_fails("compare", "FAIL  forge-work/compare.md is empty")
        write(self.root, "forge-work/build-log.md", "")
        self.assert_fails("build")

    def test_a_folder_where_a_file_should_be(self):
        os.makedirs(os.path.join(self.root, "forge-work", "plan.md"))
        self.assert_fails("plan", "forge-work/plan.md cannot be read")

    def test_recon_features(self):
        write(self.root, "forge-work/recon.md", "# Recon\n")
        write(self.root, "forge-work/features.csv", FEATURES.replace(",must,", ",should,"))
        self.assert_fails("recon", "0 row(s) with priority must")
        write(self.root, "forge-work/features.csv", "feature;area;priority;original;clone;notes\nA;b;must;yes;no;\n")
        self.assert_fails("recon", "is not exactly feature,area,priority,original,clone,notes")
        write(self.root, "forge-work/features.csv", "")
        self.assert_fails("recon", "is not exactly")
        write(self.root, "forge-work/features.csv", "﻿" + FEATURES.replace("\n", "\r\n"))  # Excel's way
        self.assert_passes("recon")
        write(self.root, "forge-work/features.csv", 'feature,area,priority,original,clone,notes\n"Book, pay",x,must,yes,no,\n')
        self.assert_passes("recon")
        write(self.root, "forge-work/features.csv", FEATURES + '"%s",x,must,yes,no,\n' % ("a" * 200000))
        self.assert_fails("recon", "forge-work/features.csv cannot be read")  # too big for the csv module
        os.remove(os.path.join(self.root, "forge-work", "recon.md"))
        self.assert_fails("recon", "forge-work/recon.md is missing")

    def test_every_feature_row_follows_the_contract(self):
        """Values parity.py refuses (exit 2) fail at recon and plan already, not six phases later."""
        write(self.root, "forge-work/recon.md", "# Recon\n")
        header = "feature,area,priority,original,clone,notes\n"
        for rows, expected in (
                ("Create poll,create,MUST!,maybe,done,\n", [
                    "line 2: priority 'MUST!' is not one of must, should, could",
                    "line 2: original 'maybe' is not one of yes, no",
                    "line 2: clone 'done' is not one of yes, partial, no, skip"]),
                ("Grid,s2,must,yes,yes please,\n", ["line 2: clone 'yes please'"]),
                ("Grid,must,yes\n", ["line 2 has 3 cells, not 6"]),
                ("Book, pay,x,must,yes,no,\n", ["line 2 has 7 cells, not 6: put text with a comma in double quotes"]),
                (",x,must,yes,no,\n", ["line 2: the feature name is empty"]),
                ("Book,x,must,yes,no,\nPay,x,should,yes,skip,\n", ["line 3: Pay is skipped without a reason"])):
            with self.subTest(rows=rows):
                write(self.root, "forge-work/features.csv", header + rows)
                for phase in ("recon", "plan"):
                    self.assert_fails(phase, "forge-work/features.csv breaks the contract in", *expected)
        write(self.root, "forge-work/features.csv", header + "Book,x,Must,YES,No,\nPay,x,should,,,\n")
        self.assert_passes("recon")  # case and empty cells as parity.py reads them

    def test_a_skipped_or_own_must_have_is_not_one_to_build_from_the_original(self):
        write(self.root, "forge-work/recon.md", "# Recon\n")
        write(self.root, "forge-work/features.csv",
              "feature,area,priority,original,clone,notes\nExisting polls,data,must,yes,skip,their data\n")
        self.assert_fails("recon", "0 row(s) with priority must, not skipped")
        write(self.root, "forge-work/features.csv",
              "feature,area,priority,original,clone,notes\nSMS reminders,booking,must,no,no,C003: 23 reviews\n")
        self.assert_fails("recon", "0 row(s) with priority must, not skipped, that the original has")
        write(self.root, "forge-work/plan.md", PLAN)
        self.assert_passes("plan")  # idea mode: every row is the user's own (original no)

    def test_build_needs_the_must_haves_built(self):
        """Idea mode has no diff phase: the build gate is the only one that reads the clone column."""
        self.finish("build")
        header = "feature,area,priority,original,clone,notes\n"
        for rows, expected in (
                ("Book,x,must,no,no,\nPay,x,must,no,yes,\n", "line 2: Book, clone no"),
                ("Book,x,must,yes,,\nPay,x,must,no,yes,\n", "line 2: Book, clone empty"),
                ("Book,x,must,no,partial,\nPay,x,must,no,yes,\n", "line 2: Book, clone partial, no note"),
                ("Book,x,must,no,skip,their data\nPay,x,should,no,yes,\n", "0 of 1 must-have(s) built"),
                ("Book,x,must,no,maybe,\n", "line 2: clone 'maybe'")):
            with self.subTest(rows=rows):
                write(self.root, "forge-work/features.csv", header + rows)
                self.assert_fails("build", expected)
        write(self.root, "forge-work/features.csv", header + "Book,x,must,no,yes,\n"
              "Pay,x,must,no,partial,no refunds yet\nOld data,x,must,yes,skip,their data\nTeams,x,could,no,no,\n")
        out = self.assert_passes("build")
        self.assertIn("1 of 3 must-have(s) built, the rest partial or skipped with a note", out)
        os.remove(os.path.join(self.root, "docker-compose.yml"))
        self.assert_fails("build", "compose.yaml or compose.yml or docker-compose.yaml or docker-compose.yml "
                                   "is missing")

    def test_plan_needs_its_sections(self):
        self.finish("plan")
        write(self.root, "forge-work/plan.md", "Profile: laravel\nPWA: no\n")
        self.assert_fails("plan", "forge-work/plan.md needs text under ## Entities and schema, ## Routes and API, "
                                  "## Build order, ## Decisions log, as in ../forge-plan/plan.md")
        write(self.root, "forge-work/plan.md", PLAN.replace("1. Vertical slice: book a slot", "<!-- later -->"))
        self.assert_fails("plan", "needs text under ## Build order,")
        write(self.root, "forge-work/plan.md", PLAN.replace("## Entities and schema", "## Entities and schema (SQL)"))
        out = self.assert_passes("plan")  # the schema section is only SQL in a code block: that is text
        self.assertIn("has text under ## Entities and schema, ## Routes and API", out)

    def test_test_plan_needs_its_cases_run(self):
        self.finish("test")
        example = re.sub(r"\{\{[^}]*\}\}", "x", template("forge-test", "test-plan.md"))
        write(self.root, "forge-work/test-plan.md", example)
        self.assert_fails("test", "has only the example rows of ../forge-test/test-plan.md")
        write(self.root, "forge-work/test-plan.md", "# Test plan\n\nAll good.\n\n```\n" + CASES + "```\n")
        self.assert_fails("test", "has no Cases table with rows")  # a table in a code block is not one
        write(self.root, "forge-work/test-plan.md", CASES.replace("fail B001", " ") + "| F01-N1 | | negative | | x |\n")
        self.assert_fails("test", "forge-work/test-plan.md has 2 case row(s) without a result: F01-E1, F01-N1")
        write(self.root, "forge-work/test-plan.md", "| Case | result |\n|:--|--:|\n| F01-H1 | skipped: no account |\n")
        self.assert_passes("test")

    def test_the_example_rows_of_the_template_are_not_a_feature_list(self):
        write(self.root, "forge-work/recon.md", "# Recon\n")
        example = template("forge-recon", "features.csv")
        for text in (example, example.replace("\n", "\r\n"), "\n".join(example.splitlines()[:4]) + "\n"):
            with self.subTest(text=text[:60]):
                write(self.root, "forge-work/features.csv", text)
                self.assert_fails("recon", "has only example rows of ../forge-recon/features.csv")
        write(self.root, "forge-work/features.csv", example + "Pay a deposit with iDEAL,payments,must,no,no,\n")
        self.assert_passes("recon")

    def test_templates_copied_without_filling_them_in_fail(self):
        for phase, name, source in (("recon", "recon.md", ("forge-recon", "recon-map.md")),
                                    ("plan", "plan.md", ("forge-plan", "plan.md")),
                                    ("test", "test-plan.md", ("forge-test", "test-plan.md")),
                                    ("launch", "launch.md", ("forge-launch", "launch.md"))):
            with self.subTest(phase=phase):
                self.finish(phase)
                write(self.root, "forge-work/" + name, template(*source))
                self.assert_fails(phase, "forge-work/%s still has" % name, "template placeholder(s), such as {{")
        self.finish("design")
        write(self.root, "forge-work/design/components.md", template("forge-design", "components.md"))
        self.assert_fails("design", "forge-work/design/components.md still has", "such as <laravel|django|next|static>")

    def test_only_the_last_placeholder_left_still_fails(self):
        self.finish("launch")
        write(self.root, "forge-work/launch.md", "# Launch: Slotwise\n\nDomain: {{TO-FILL until the user gives it}}\n")
        self.assert_fails("launch", "1 template placeholder(s), such as {{TO-FILL")

    def test_braces_in_code_comments_and_templating_are_not_placeholders(self):
        self.finish("plan")
        write(self.root, "forge-work/plan.md",
              "# Plan\n<!-- Replace every {{...}}, then delete this comment. -->\nProfile: laravel\nPWA: no\n\n"
              "Greeting in Blade: `{{ $user->name }}`, in Django {{ user.first_name }}.\n\n"
              "```blade\n<h1>{{$title}}</h1>\n```\n\n~~~tsx\n<div style={{color: 'red'}} />\n~~~\n" + SECTIONS)
        self.assert_passes("plan")

    def test_plan_lines(self):
        write(self.root, "forge-work/features.csv", FEATURES)
        write(self.root, "forge-work/plan.md", template("forge-plan", "plan.md"))
        self.assert_fails("plan", "needs exactly one line `Profile: laravel|django|next|static`",
                          "needs exactly one line `PWA: yes|no`")
        for text in ("Profile: Next\nPWA: no\n", "Profile: next\nPWA: maybe\n", "**Profile:** next\nPWA: no\n",
                     "Profile: next\nProfile: django\nPWA: no\n", "Profile: next (Next.js)\nPWA: no\n", "PWA: no\n",
                     "```\nProfile: laravel\nPWA: no\n```\n", "<!--\nProfile: next\n-->\nPWA: no\n",
                     "**Profile:** wordpress\nProfile: next\nPWA: no\n", "## profile: wordpress\nProfile: next\nPWA: no\n"):
            with self.subTest(text=text):
                write(self.root, "forge-work/plan.md", text)
                self.assert_fails("plan")
        for profile in ("laravel", "django", "next", "static"):
            write(self.root, "forge-work/plan.md", "# Plan\nProfile:  %s \r\nPWA: yes\r\n%s" % (profile, SECTIONS))
            self.assert_passes("plan")
        write(self.root, "forge-work/plan.md", "# Plan\nProfile: next\nPWA: no\n- Profile page: the user edits a name\n"
              + SECTIONS)
        self.assert_passes("plan")  # a list item about a profile page is not a Profile line

    def test_idea_mode_plan_needs_the_feature_list(self):
        self.finish("plan")
        os.remove(os.path.join(self.root, "forge-work", "features.csv"))
        self.assert_fails("plan", "forge-work/features.csv is missing")

    def test_design_contrast_and_components(self):
        self.finish("design")
        write(self.root, "forge-work/design/tokens.json",
              '{"color": {"bg": "#ffffff", "text": "#bbbbbb"}, "pairs": [["text", "bg"]]}')
        shown = phasecheck.PYTHON + " ../forge-design/contrast.py forge-work/design/tokens.json"  # python3, or this Python on Windows
        out = self.assert_fails("design", "forge-work/design/tokens.json parses", shown + " exits 1")
        self.assertIn("text", out.split("exits 1")[1])  # contrast.py's own words are shown
        write(self.root, "forge-work/design/tokens.json", '{"color": ')
        self.assert_fails("design", "forge-work/design/tokens.json cannot be read", "exits 2: it could not check")
        write(self.root, "forge-work/design/tokens.json", "[]")
        self.assert_fails("design", "is not a JSON object")
        write(self.root, "forge-work/design/tokens.json", "[" * 100000 + "]" * 100000)
        self.assert_fails("design", "forge-work/design/tokens.json cannot be read")  # too deep, not a traceback
        self.finish("design")
        os.remove(os.path.join(self.root, "forge-work", "design", "components.md"))
        self.assert_fails("design", "forge-work/design/components.md is missing")

    def test_test_needs_no_open_serious_bug(self):
        self.finish("test")
        write(self.root, "forge-work/bugs.md", "# Bugs\n\n## B001 [high] [open] Booking fails\nsteps: x\n")
        self.assert_fails("test", "bugs.py forge-work/bugs.md exits 1: it found problems", "B001")
        write(self.root, "forge-work/bugs.md", "# Bugs\n\n## B001 [high] [fixed] Booking fails\n"
                                               "## B002 [low] [open] Footer overlaps\n")
        self.assert_passes("test")
        os.remove(os.path.join(self.root, "forge-work", "bugs.md"))
        self.assert_fails("test", "exits 2: it could not check")

    def test_long_script_output_is_cut_short(self):
        self.finish("test")
        bugs = "".join("## B%03d [critical] [open] Bug number %d\n" % (n, n) for n in range(1, 31))
        write(self.root, "forge-work/bugs.md", "# Bugs\n\n" + bugs)
        out = self.assert_fails("test", "more lines: run it to see them")
        self.assertLess(len(out.splitlines()), 20)

    def test_diff_needs_every_must_have(self):
        write(self.root, "forge-work/features.csv", FEATURES.replace("must,yes,yes", "must,yes,partial"))
        self.assert_fails("diff", "parity.py forge-work/features.csv exits 1")

    def test_brand(self):
        self.finish("brand")
        write(self.root, "src/footer.html", "<p>Powered by Calendly</p>\n")
        self.assert_fails("brand", "sweep.py . --config forge-work/brand.json exits 1")
        os.remove(os.path.join(self.root, "src", "footer.html"))
        for text, wrong in (('{"name": "Slotwise", "avoid": []}', '"avoid"'), ('{"avoid": ["Calendly"]}', '"name"'),
                            ('{"name": " ", "avoid": ["Calendly"]}', '"name"'),
                            ('{"name": ["Slotwise"], "avoid": ["Calendly"]}', '"name" is missing, empty or not a text'),
                            ('{"name": 5, "avoid": ["Calendly"]}', '"name"'),
                            ('{"name": true, "avoid": ["Calendly"]}', '"name"'),
                            ('{"name": "Slotwise", "avoid": "Calendly"}', '"avoid" is missing, empty or not a list')):
            with self.subTest(text=text):
                write(self.root, "forge-work/brand.json", text)
                self.assert_fails("brand", wrong)

    def test_secure(self):
        self.finish("secure")
        for text in ("Verdict: FAIL\n", "# Security\n", "Verdict: PASS\nVerdict: FAIL\n", "verdict: pass\n",
                     "> Verdict: PASS\n", "**Verdict:** PASS\n"):
            with self.subTest(text=text):
                write(self.root, "forge-work/security.md", text)
                self.assert_fails("secure", "Verdict: PASS")
        write(self.root, "forge-work/security.md", "Verdict: PASS\n")
        write(self.root, "app/config.php", "$key = '%s';\n" % ("sk_" + "live_" + "a" * 24))  # built at runtime
        out = self.assert_fails("secure", "secretscan.py . exits 1")
        self.assertNotIn("a" * 24, out)  # secretscan masks it, and so the gate never shows it

    def test_a_pass_in_a_comment_or_code_block_or_next_to_a_fail_does_not_count(self):
        self.finish("secure")
        for text in ("# Security check\n<!--\nVerdict: PASS\n-->\nCounts: 1 critical\n",
                     "<!-- Verdict: PASS\n", "```\nVerdict: PASS\n```\nCounts: 2 critical\n", "```\nVerdict: PASS\n",
                     "   ````\nVerdict: PASS\n```\n", "~~~\nVerdict: PASS\n~~~\nVerdict - FAIL\n",
                     "**Verdict:** FAIL\nVerdict: PASS\n", "verdict: FAIL\nVerdict: PASS\n",
                     "## Verdict: FAIL\nVerdict: PASS\n", "> Verdict: FAIL\nVerdict: PASS\n",
                     "Verdict : FAIL\nVerdict: PASS\n", "__Verdict__: FAIL\nVerdict: PASS\n"):
            with self.subTest(text=text):
                write(self.root, "forge-work/security.md", text)
                self.assert_fails("secure", "needs exactly one line `Verdict: PASS`")
        report = template("forge-secure", "SKILL.md").split("```markdown\n")[1].split("```\n")[0]
        write(self.root, "forge-work/security.md", report.replace("Verdict: FAIL", "Verdict: PASS"))
        self.assert_passes("secure")  # forge-secure's own report format passes

    def test_pack(self):
        self.finish("pack")
        os.rename(os.path.join(self.root, "docker-compose.yml"), os.path.join(self.root, "compose.yaml"))
        self.assert_passes("pack")
        os.remove(os.path.join(self.root, "compose.yaml"))
        self.assert_fails("pack", "compose.yaml or compose.yml or docker-compose.yaml or docker-compose.yml is missing")
        self.finish("pack")
        os.remove(os.path.join(self.root, ".dockerignore"))
        self.assert_fails("pack", ".dockerignore is missing", "packcheck.py . exits 1")

    def test_pack_scans_for_secrets_again(self):
        self.finish("secure", "pack")
        self.assert_passes("pack")
        write(self.root, "app.js", 'const STRIPE_KEY = "%s";\n' % ("sk_" + "live_" + "51HxYzAbCdEfGhIjKlMnOp" * 2))
        self.assert_fails("pack", "secretscan.py . exits 1")

    @unittest.skipUnless(HAS_GIT, "git is not installed")
    def test_improve_needs_a_work_branch(self):
        self.finish("improve")
        git(self.root, "symbolic-ref", "HEAD", "refs/heads/main")
        self.assert_fails("improve", "gitguard.py . exits 1", "On the main branch")

    def test_json_output(self):
        write(self.root, "forge-work/plan.md", "Profile: next\n")
        code, out, _ = self.run_main("plan", "--json")
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual((data["phase"], data["ok"]), ("plan", False))
        self.assertEqual([item["ok"] for item in data["checks"]], [True, False, True, False, False])
        self.assertEqual(set(data["checks"][0]), {"ok", "what", "output"})

    def test_unknown_phase_or_time(self):
        for args in (["deploy"], ["secure", "--since", "yesterday"], ["secure", "--since", "2026-13-01T00:00:00"]):
            with self.subTest(args=args), self.assertRaises(SystemExit) as stop, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.run_main(*args)
            self.assertEqual(stop.exception.code, 2)


class SinceTests(Checks):
    def test_a_report_from_before_the_last_go_does_not_count(self):
        self.finish("secure")
        os.utime(os.path.join(self.root, "forge-work", "security.md"), (OLD, OLD))
        self.assert_fails("secure", "forge-work/security.md is older than the last go (2026-10-27T09:51:44+00:00)",
                          "Run the phase's skill again in full", args=("--since", "2026-10-27T09:51:44+00:00"))
        self.assert_passes("secure", "--since", "2017-01-01T00:00:00+00:00")
        self.assert_passes("secure")  # without --since, its age is not checked

    def test_since_applies_only_to_a_phase_with_a_report(self):
        self.finish("plan")
        os.utime(os.path.join(self.root, "forge-work", "plan.md"), (OLD, OLD))
        self.assert_passes("plan", "--since", "2026-10-27T09:51:44+00:00")

    def test_a_missing_report_is_named_once(self):
        out = self.assert_fails("secure", args=("--since", "2026-10-27T09:51:44+00:00"))
        self.assertEqual(out.count("forge-work/security.md is missing"), 1)


class ScriptTests(Checks):
    def fake_pack(self, source):
        """A copy of the pack's forge and forge-secure folders with secretscan.py replaced by SOURCE."""
        pack = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pack, ignore_errors=True)
        for folder in ("forge", "forge-secure"):
            shutil.copytree(os.path.join(ROOT, folder), os.path.join(pack, folder),
                            ignore=shutil.ignore_patterns("__pycache__"))
        with open(os.path.join(pack, "forge-secure", "secretscan.py"), "w", encoding="utf-8") as handle:
            handle.write(source)
        return pack

    def test_a_script_that_prints_nothing_checked_nothing(self):
        self.finish("secure")
        for source in ("", "import sys\nsys.exit(None)\n", "def main():\n    return 0\n"):
            with self.subTest(source=source), mock.patch.object(phasecheck, "PACK", self.fake_pack(source)):
                self.assert_fails("secure", "secretscan.py . exits 0: it printed nothing, so it checked nothing")

    def test_a_script_that_crashes_is_not_said_to_find_problems(self):
        self.finish("secure")
        with mock.patch.object(phasecheck, "PACK", self.fake_pack('raise RuntimeError("boom")\n')):
            out = self.assert_fails("secure", "secretscan.py . exits 1: it crashed: this is a bug in that script")
        self.assertNotIn("it found problems", out)

    def test_a_missing_script_fails_the_check(self):
        self.finish("diff")
        with mock.patch.object(phasecheck, "PACK", os.path.join(self.root, "nowhere")):
            self.assert_fails("diff", "exits 2: it could not check")

    def test_a_script_that_hangs_fails_the_check(self):
        self.finish("diff")
        hung = subprocess.TimeoutExpired(cmd="parity.py", timeout=phasecheck.TIMEOUT)
        with mock.patch.object(phasecheck.subprocess, "run", side_effect=hung):
            self.assert_fails("diff", "did not finish within %d seconds" % phasecheck.TIMEOUT)


class ConsoleTests(Checks):
    def test_the_scripts_it_runs_are_read_as_utf8_on_a_cp1252_pipe(self):
        """phasecheck.py asks the scripts it runs for UTF-8 and reads them as UTF-8. Windows pipes are cp1252
        otherwise, and the e of Caf\u00e9 came out as the Unicode replacement character."""
        write(self.root, "forge-work/brand.json", '{"name": "Slotwise", "avoid": ["Caf\u00e9 Noir \u2192"]}')
        write(self.root, "index.html", "<title>Caf\u00e9 Noir \u2192 booking</title>\n")
        code, out, err = run_cp1252(os.path.join(ROOT, "forge", "phasecheck.py"), "brand", cwd=self.root)
        self.assertEqual(code, 1, err)
        self.assertIn("A name to avoid: Caf\u00e9 Noir \\u2192 (1 place)", out)
        self.assertNotIn("\\ufffd", out)


if __name__ == "__main__":
    unittest.main()
