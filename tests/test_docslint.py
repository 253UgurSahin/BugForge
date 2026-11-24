"""Tests for forge-docs/docslint.py: the checks on the documentation forge-docs writes.

Every test writes a small project into its own temporary folder; nothing outside it is read.
"""

import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `python3 -m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402

mod = load("forge-docs", "docslint")
SCRIPT = os.path.join(ROOT, "forge-docs", "docslint.py")
RULES = mod.load_rules()
FENCE = "`" * 3

ARCHITECTURE = """# Architecture

How this was made: from the code at abc1234.

## Context
{f}mermaid
flowchart TB
  user([Customer]) --> app[Shop]
{f}

## Logical view: layers and parts
The controllers in `app/Http` call the services.

## Domain model
{f}mermaid
classDiagram
  Customer "1" --> "*" Booking : makes
{f}

## Main flows
{f}mermaid
sequenceDiagram
  Customer->>BookingController: POST /bookings
{f}

## Deployment view
See [the compose file](../docker-compose.yml).

## Decisions
- [0001 Laravel](decisions/0001-laravel.md)
""".format(f=FENCE)


class Project(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.write("app/Http/BookingController.php", "<?php\n")
        self.write("docker-compose.yml", "services: {}\n")

    def write(self, path, text):
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(textwrap.dedent(text) if not text.startswith("#") else text)

    def complete(self):
        self.write("README.md", "# Shop\n\nRead [the architecture](docs/architecture.md). Code in `app/Http/BookingController.php`.\n")
        self.write("docs/architecture.md", ARCHITECTURE)
        self.write("docs/api.md", "# API\n\n| method | path |\n| --- | --- |\n| POST | /bookings |\n")
        self.write("docs/glossary.md", "# Glossary\n\n| word | meaning |\n| --- | --- |\n| Booking | a reservation |\n")
        self.write("docs/decisions/0001-laravel.md", "# 0001. Laravel\n\n## Context\nx\n\n## Decision\ny\n\n## Consequences\nz\n")
        self.write("docs/handleiding.md", "# Shop: zo gebruik je het\n\n## Een afspraak maken\n1. Druk op **Afspraak maken**.\n")

    def found(self, parts=None):
        findings, summary = mod.check(self.root, parts or RULES["default_parts"], RULES)
        return {f["rule"]: f for f in findings}, summary


class LintTests(Project):
    def test_a_complete_set_passes(self):
        self.complete()
        found, summary = self.found()
        self.assertEqual(found, {})
        self.assertEqual(summary["diagrams"], 3)
        self.assertEqual(summary["kinds"], ["classDiagram", "flowchart", "sequenceDiagram"])
        self.assertEqual(summary["docs"], 6)

    def test_missing_parts_headings_and_diagrams(self):
        self.write("README.md", "# Shop\n")
        self.write("docs/architecture.md", "# Architecture\n\n## Context\n\n## Domain model\n")
        found, _ = self.found(["readme", "architecture", "guide"])
        self.assertEqual(found["missing_part"]["where"], ["guide: docs/user-guide.md or docs/handleiding.md"])
        self.assertEqual(found["missing_part"]["severity"], "high")
        self.assertIn("docs/architecture.md: ## Main flows", found["missing_heading"]["where"])
        self.assertNotIn("docs/architecture.md: ## Context", found["missing_heading"]["where"])
        self.assertEqual(found["missing_diagram"]["count"], 3)

    def test_mermaid_blocks(self):
        self.write("README.md", "# X\n\n{f}mermaid\nclasDiagram\n  A --> B\n{f}\n\n{f}mermaid\n%% only a comment\n{f}\n\n"
                   "{f}mermaid\ngraph LR\n  A --> B\n{f}\n\n{f}mermaid\nflowchart\n".format(f=FENCE))
        found, summary = self.found(["readme"])
        self.assertEqual(found["unknown_diagram"]["where"], ["README.md:3"])
        self.assertEqual(found["empty_diagram"]["where"], ["README.md:8"])
        self.assertEqual(found["open_fence"]["where"], ["README.md:17"])
        self.assertEqual(summary["kinds"], ["flowchart"], "graph counts as a flowchart")

    def test_links_and_file_names(self):
        self.write("docs/api.md", "# API\n\n[up](../README.md) [gone](gone.md) [site](https://example.com) "
                   "[anchor](#api) [mail](mailto:a@example.test)\n"
                   "`app/Http/BookingController.php` `app/Models/Ghost.php` `/bookings/42` `forge-work/audit.md` "
                   "`npm run dev` `docker-compose.yml`\n\n{f}\n[in code](nowhere.md) `also/not/checked.py`\n{f}\n".format(f=FENCE))
        self.write("README.md", "# X\n")
        found, _ = self.found(["readme", "api"])
        self.assertEqual(found["broken_link"]["where"], ["docs/api.md:3"])
        self.assertEqual(found["missing_file"]["where"], ["docs/api.md:4"])
        self.assertEqual(found["missing_file"]["count"], 1)

    def test_placeholders_to_fill_and_secrets(self):
        self.write("README.md", "# X\n\n<your app name here>\nTBD\nTO-FILL: who uses the app?\n"
                   "The key is `STRIPE_SECRET`, set it in .env.\n"
                   "{f}\nSTRIPE_" "SECRET=sk_" "live_0123456789abcdefghij\nAPP_PASSWORD=change-me\n# TODO in code is fine\n{f}\n".format(f=FENCE))
        found, _ = self.found(["readme"])
        self.assertEqual(found["placeholder"]["where"], ["README.md:3", "README.md:4"])
        self.assertEqual(found["to_fill"]["where"], ["README.md:5"])
        self.assertEqual(found["to_fill"]["severity"], "low")
        self.assertEqual(found["secret"]["where"], ["README.md:8"])

    def test_the_parts_match_views_md(self):
        with open(os.path.join(ROOT, "forge-docs", "views.md"), encoding="utf-8") as handle:
            views = handle.read()
        for name, part in RULES["parts"].items():
            with self.subTest(part=name):
                self.assertIn("## %s:" % name, views)
                for heading in part["headings"]:
                    self.assertIn("## " + heading, views)


class CommandLineTests(Project):
    def test_exit_codes_and_json(self):
        self.complete()
        self.assertEqual(run_cp1252(SCRIPT, self.root)[0], 0)
        self.write("docs/glossary.md", "# Glossary\n\nTO-FILL: the word for a cancelled booking\n")
        code, out, err = run_cp1252(SCRIPT, self.root, "--json")
        self.assertEqual((code, err), (0, ""), "TO-FILL is low: it passes the default --fail-on medium")
        self.assertEqual(json.loads(out)["summary"]["to_fill"], 1)
        self.assertEqual(run_cp1252(SCRIPT, self.root, "--fail-on", "low")[0], 1)
        os.remove(os.path.join(self.root, "docs", "api.md"))
        self.assertEqual(run_cp1252(SCRIPT, self.root)[0], 1)
        self.assertEqual(run_cp1252(SCRIPT, self.root, "--parts", "readme,glossary")[0], 0)

    def test_bad_usage_is_exit_2_and_no_secret_is_printed(self):
        self.assertEqual(run_cp1252(SCRIPT, self.root, "--parts", "readme,poems")[0], 2)
        self.assertEqual(run_cp1252(SCRIPT, os.path.join(self.root, "nope"))[0], 2)
        self.write("README.md", "# X\nAPI_" "TOKEN=ghp_" "abcdefghijklmnopqrstuvwxyz0123\n")
        code, out, _ = run_cp1252(SCRIPT, self.root, "--parts", "readme")
        self.assertEqual(code, 1)
        self.assertNotIn("ghp_", out)
        self.assertIn("README.md:2", out)


if __name__ == "__main__":
    unittest.main()
