"""Tests for forge-check/craftcheck.py: the code-craft rules a scan can see, in Python and brace languages.

Every test writes a small project into its own temporary folder; nothing outside it is read.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `python3 -m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402

mod = load("forge-check", "craftcheck")
SCRIPT = os.path.join(ROOT, "forge-check", "craftcheck.py")
RULES = mod.load_rules()


def body(lines):
    return "".join("    x%d = %d\n" % (n, n) for n in range(lines))


class Project(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)

    def write(self, path, text):
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(textwrap.dedent(text))

    def found(self, tests=False):
        findings, summary = mod.check(self.root, RULES, tests)
        return {f["rule"]: f for f in findings}, summary


class PythonTests(Project):
    def test_a_clean_file_has_no_findings(self):
        self.write("app/price.py", '''
            def total(lines):
                """The sum of the lines' amounts, in cents."""
                return sum(line.amount for line in lines)
        ''')
        found, summary = self.found()
        self.assertEqual(found, {})
        self.assertEqual((summary["files"], summary["functions"]), (1, 1))

    def test_long_functions_by_their_limits(self):
        self.write("app/a.py", "def short():\n" + body(20) + "def longer():\n" + body(40) + "def longest():\n" + body(70))
        found, summary = self.found()
        where = found["long_function"]["where"]
        self.assertEqual(len(where), 2)
        self.assertTrue(where[0].startswith("app/a.py:") and "longest (71 lines)" in where[0], where)
        self.assertEqual(found["long_function"]["severity"], "medium")
        self.assertEqual(found["long_function"]["id"], "CR-F1")
        self.assertEqual(summary["functions_over_limit"], 2)

    def test_arguments_flags_and_self(self):
        self.write("app/b.py", '''
            class Shop:
                def book(self, a, b, c):
                    return a
                def book_more(self, a, b, c, d, e, f):
                    return a
            def send(to, html=False):
                return to
        ''')
        found, _ = self.found()
        self.assertEqual(found["many_params"]["where"], ["app/b.py:5 book_more (6 arguments)"])
        self.assertEqual(found["flag_param"]["where"], ["app/b.py:7 send"])

    def test_nesting_counts_an_elif_as_one_level(self):
        self.write("app/c.py", '''
            def flat(x):
                if x == 1:
                    return 1
                elif x == 2:
                    return 2
                elif x == 3:
                    return 3
                return 0
            def deep(rows):
                for row in rows:
                    if row:
                        for cell in row:
                            if cell:
                                while cell:
                                    cell -= 1
        ''')
        found, _ = self.found()
        self.assertEqual(found["deep_nesting"]["where"], ["app/c.py:10 deep (5 levels deep)"])

    def test_a_long_if_elif_chain(self):
        chain = "def kind(x):\n    if x == 0:\n        return 0\n" + "".join(
            "    elif x == %d:\n        return %d\n" % (n, n) for n in range(1, 7)) + "    else:\n        return -1\n"
        self.write("app/d.py", chain)
        found, _ = self.found()
        self.assertIn("kind (8 branches)", found["type_switch"]["where"][0])

    def test_a_class_with_many_methods_and_a_swallowed_error(self):
        methods = "".join("    def m%d(self):\n        return %d\n" % (n, n) for n in range(22))
        self.write("app/e.py", "class Everything:\n" + methods + "try:\n    x = 1\nexcept Exception:\n    pass\n")
        found, _ = self.found()
        self.assertEqual(found["large_class"]["where"], ["app/e.py:1 Everything (22 methods)"])
        self.assertEqual(found["swallowed_error"]["where"], ["app/e.py:48"])
        self.assertEqual(found["swallowed_error"]["severity"], "medium")

    def test_commented_out_code_but_not_prose(self):
        self.write("app/f.py", '''
            # This explains why we round half up:
            # the tax office does it this way.
            # see the 2024 rules
            x = 1
            # total = price * 2
            # if total > 10:
            #     send(total)
            y = 2
        ''')
        found, _ = self.found()
        self.assertEqual(found["commented_code"]["where"], ["app/f.py:6"])

    def test_a_file_that_does_not_parse_is_skipped_quietly(self):
        self.write("app/broken.py", "def (:\n")
        self.assertEqual(self.found()[0], {})


class BraceTests(Project):
    def test_javascript_functions_arrows_and_methods(self):
        self.write("src/a.js", "function big(a, b, c, d, e, f) {\n" + "  let x = 1;\n" * 40 + "}\n"
                   "const arrow = (a) => {\n  return a;\n};\n"
                   "class Cart {\n  add(item, quantity = false) {\n    return item;\n  }\n}\n"
                   "const config = { size: new Map(), parse(a) { return a; } };\n")
        found, summary = self.found()
        self.assertEqual(found["long_function"]["where"], ["src/a.js:1 big (42 lines)"])
        self.assertEqual(found["many_params"]["where"], ["src/a.js:1 big (6 arguments)"])
        self.assertEqual(found["flag_param"]["where"], ["src/a.js:47 add"])
        self.assertGreaterEqual(summary["functions"], 3)

    def test_php_nesting_switch_and_empty_catch(self):
        cases = "".join("      case %d: return %d;\n" % (n, n) for n in range(7))
        self.write("app/Http/Kind.php", "<?php\nclass Kind {\n  public function pick($x) {\n    switch ($x) {\n"
                   + cases + "    }\n  }\n  public function deep($rows) {\n    foreach ($rows as $r) {\n"
                   "      if ($r) {\n        foreach ($r as $c) {\n          if ($c) {\n            while ($c) { $c--; }\n"
                   "          }\n        }\n      }\n    }\n  }\n}\ntry { run(); } catch (Exception $e) {}\n")
        found, _ = self.found()
        self.assertIn("pick (7 branches)", found["type_switch"]["where"][0])
        self.assertIn("deep (5 levels deep)", found["deep_nesting"]["where"][0])
        self.assertEqual(len(found["swallowed_error"]["where"]), 1)

    def test_braces_in_strings_and_comments_do_not_count(self):
        self.write("src/b.ts", "function f(a: string): string {\n  const s = '{{{';\n  // }}}\n  /* { */\n"
                   "  return s + \"}\";\n}\nfunction g(flag: boolean) {\n  return flag;\n}\n")
        found, summary = self.found()
        self.assertEqual(summary["functions"], 2)
        self.assertEqual(found["flag_param"]["where"], ["src/b.ts:7 g"])

    def test_getter_chains(self):
        self.write("src/c.java", "class A {\n  String city() {\n    return order.getCustomer().getAddress().getCity();\n"
                   "  }\n  String fine() {\n    return query.where(1).orderBy(2).limit(3).get();\n  }\n}\n")
        found, _ = self.found()
        self.assertEqual(found["train_wreck"]["where"], ["src/c.java:3"])


class FolderTests(Project):
    def test_duplicates_across_files_once_per_block(self):
        block = "".join("total_%d = price_%d * rate + fee_%d\n" % (n, n, n) for n in range(10))
        self.write("app/one.py", "def a():\n" + textwrap.indent(block, "    "))
        self.write("app/two.py", "x = 1\n\ndef b():\n" + textwrap.indent(block, "    "))
        found, _ = self.found()
        self.assertEqual(found["duplicate"]["count"], 1)
        self.assertRegex(found["duplicate"]["where"][0], r"^app/one\.py:\d+ and app/two\.py:\d+$")

    def test_tests_libraries_generated_and_minified_are_left_out(self):
        long_one = "def slow():\n" + body(50)
        for path in ("tests/test_x.py", "node_modules/lib/x.py", "vendor/x.php", "app/migrations/0001.py"):
            self.write(path, long_one)
        self.write("app/gen.py", "# Generated by protoc. DO NOT EDIT.\n" + long_one)
        self.write("static/app.min.js", "function a(){" + "x();" * 50 + "}\n")
        self.write("static/bundle.js", "function a(){" + "x();" * 200 + "}\n")
        self.assertEqual(self.found()[0], {})
        found, _ = self.found(tests=True)
        self.assertEqual(found["long_function"]["where"], ["tests/test_x.py:1 slow (51 lines)"])

    def test_the_rules_file_and_craft_md_agree(self):
        with open(os.path.join(ROOT, "forge-check", "craft.md"), encoding="utf-8") as handle:
            doc = handle.read()
        for name, rule in RULES["rules"].items():
            with self.subTest(rule=name):
                self.assertRegex(doc, r"\| %s \*\*scan\*\* \|" % re.escape(rule["id"]))
        self.assertEqual(set(RULES["severity_for"]) - set(RULES["rules"]), set())


class CommandLineTests(Project):
    def test_exit_codes_json_and_no_file_contents(self):
        self.write("app/a.py", "SECRET_WORD = 'zebra'\ndef f(a, b, c, d, e, g):\n    return 'zebra'\n")
        code, out, err = run_cp1252(SCRIPT, self.root, "--json")
        self.assertEqual((code, err), (0, ""), "craft findings are medium or low: the default --fail-on high passes")
        data = json.loads(out)
        self.assertEqual([f["id"] for f in data["findings"]], ["CR-F2"])
        self.assertEqual(run_cp1252(SCRIPT, self.root, "--fail-on", "medium")[0], 1)
        code, out, _ = run_cp1252(SCRIPT, self.root)
        self.assertNotIn("zebra", out)
        self.assertIn("CR-F2", out)
        self.assertIn("craft.md", out)

    def test_a_missing_folder_is_exit_2(self):
        code, out, err = run_cp1252(SCRIPT, os.path.join(self.root, "nope"))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("is not a folder", err)


if __name__ == "__main__":
    unittest.main()
