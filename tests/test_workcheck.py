"""Tests for forge/workcheck.py, run on its own: the feature list as recon, plan and build need it, tokens that
are still the template's, the component specs, the end-to-end specs, the screenshots forge-check diff compared
and the app's new name. The gate's use of each is tested in test_phasecheck.py; the look items of an improve
run are lookcheck.py's (test_lookcheck.py). Every test works in its own folder."""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402
from test_phasecheck import COMPONENTS, FEATURES, SPEC, TOKENS, read, write  # noqa: E402

workcheck = load("forge", "workcheck")
SCRIPT = os.path.join(ROOT, "forge", "workcheck.py")


class Work(unittest.TestCase):
    """A temporary project folder; workcheck.py runs in it as if from the project root."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def check(self, *args):
        """Run workcheck.main with --json in the project. Returns (exit code, the check, stderr)."""
        out, err, before = io.StringIO(), io.StringIO(), os.getcwd()
        os.chdir(self.root)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = workcheck.main(list(args) + ["--json"])
        finally:
            os.chdir(before)
        if code == 2:
            return code, None, err.getvalue()
        data = json.loads(out.getvalue())
        self.assertEqual(len(data["checks"]), 1)
        return code, data["checks"][0], err.getvalue()


class FeatureTests(Work):
    def test_the_contract_and_a_must_have(self):
        write(self.root, "features.csv", FEATURES)
        code, check, _ = self.check("features", "features.csv", "--theirs")
        self.assertEqual(code, 0, check)
        self.assertIn("1 row(s) with priority must, not skipped, that the original has", check["what"])
        write(self.root, "features.csv", FEATURES.replace("must,yes", "must,no"))
        self.assertEqual(self.check("features", "features.csv", "--theirs")[0], 1)
        self.assertEqual(self.check("features", "features.csv")[0], 0)  # idea mode: the user's own
        write(self.root, "features.csv", read(os.path.join(ROOT, "forge-research", "features.csv")))
        code, check, _ = self.check("features", "features.csv")
        self.assertIn("only example rows of ../forge-research/features.csv", check["what"])

    def test_built(self):
        write(self.root, "features.csv", FEATURES)
        self.assertEqual(self.check("built", "features.csv")[0], 0)
        write(self.root, "features.csv", FEATURES.replace("must,yes,yes", "must,yes,no"))
        code, check, _ = self.check("built", "features.csv")
        self.assertEqual(check["output"], ["line 2: Book a slot, clone no"])

    def test_a_file_it_cannot_read(self):
        code, check, err = self.check("features", "nowhere.csv")
        self.assertEqual(code, 2)
        self.assertIn("nowhere.csv", err)


class TokenTests(Work):
    def test_the_templates_values_are_not_the_apps(self):
        template = os.path.join(ROOT, "forge-design", "tokens.json")
        write(self.root, "tokens.json", read(template))
        code, check, _ = self.check("tokens", "tokens.json", template)
        self.assertEqual(code, 1)
        self.assertEqual(check["what"], "tokens.json still holds every value of ../forge-design/tokens.json")
        notes_only = dict(json.loads(read(template)), _notes="estimated: surface")
        write(self.root, "tokens.json", json.dumps(notes_only))
        self.assertEqual(self.check("tokens", "tokens.json", template)[0], 1)
        write(self.root, "tokens.json", TOKENS)
        self.assertEqual(self.check("tokens", "tokens.json", template)[0], 0)


class SpecTests(Work):
    def test_a_spec_outside_node_modules(self):
        code, check, _ = self.check("specs", "e2e/**/*.spec.*")
        self.assertEqual((code, check["what"]), (1, "no end-to-end spec: no file like e2e/**/*.spec.*"))
        write(self.root, "e2e/node_modules/@playwright/test/a.spec.ts", SPEC)
        self.assertEqual(self.check("specs", "e2e/**/*.spec.*")[0], 1)
        write(self.root, "e2e/f01-book.spec.ts", SPEC)
        code, check, _ = self.check("specs", "e2e/**/*.test.*", "e2e/**/*.spec.*")
        self.assertEqual((code, check["what"]), (0, "end-to-end specs: e2e/f01-book.spec.ts"))


class ComparedTests(Work):
    def test_reference_screenshots_have_a_comparison(self):
        code, check, _ = self.check("compared", "screens")  # recon took none
        self.assertEqual((code, check["what"]), (0, "screens holds no reference screenshot, so there is no layout "
                                                    "to compare"))
        write(self.root, "screens/S07.diff.png", "png")
        self.assertEqual(self.check("compared", "screens")[0], 0)  # a diff image is not a reference
        write(self.root, "screens/S07.png", "png")
        code, check, _ = self.check("compared", "screens")
        self.assertEqual((code, check["what"]), (1, "screens has 1 reference screenshot(s) and no .diff.json"))
        for broken in ("", "[]", "{"):
            with self.subTest(broken=broken):
                write(self.root, "screens/S07.diff.json", broken)
                self.assertEqual(self.check("compared", "screens")[0], 1)
        write(self.root, "screens/S07.diff.json", '{"score": 77.0, "regions": []}')
        code, check, _ = self.check("compared", "screens")
        self.assertEqual((code, check["what"]), (0, "screens: 1 comparison(s) of 1 reference screenshot(s)"))


class NamedTests(Work):
    def test_the_name_in_a_file_of_the_app(self):
        write(self.root, "brand.json", '{"name": "Druppeldag", "avoid": ["Groeiwijs"]}')
        for place in ("forge-work/brand.md", "node_modules/a/index.js", "e2e/a.spec.ts", "dist/index.html",
                      "build/app.js", ".env", ".env.local", ".git/HEAD"):
            write(self.root, place, "Druppeldag\n")
        code, check, _ = self.check("named", "brand.json")
        self.assertEqual(code, 1)
        self.assertIn("the name Druppeldag from brand.json is in no file of the app", check["what"])
        write(self.root, "src/partials/head.html", "<title>DRUPPELDAG</title>\n")
        code, check, _ = self.check("named", "brand.json")
        self.assertEqual((code, check["what"]), (0, "the app carries the name Druppeldag: src/partials/head.html "
                                                    "has it"))
        write(self.root, "brand.json", '{"name": " ", "avoid": ["Groeiwijs"]}')
        self.assertEqual(self.check("named", "brand.json")[0], 1)


class ComponentsTests(Work):
    """T33: a components.md whose ## Components held one line ('Button: see the app.') passed the design gate. The
    specs /forge-build builds from are a block per component (forge-design design Step 5), each with its states."""

    def test_a_block_per_component(self):
        write(self.root, "components.md", COMPONENTS)
        code, check, _ = self.check("components", "components.md")
        self.assertEqual((code, check["what"]), (0, "components.md: ## Components holds 1 component block(s), each "
                                                    "with its states"))
        for blocks in ("\n- **Card**: variants plain, raised\n  - **States:** default, hover\n",
                       "\nToast\n  states   enter, rest, leave\n\nDialog\n  states   open, closed\n"):
            write(self.root, "components.md", COMPONENTS + blocks)
            self.assertEqual(self.check("components", "components.md")[0], 0, blocks)
        self.assertIn("3 component block(s)", self.check("components", "components.md")[1]["what"])

    def test_a_line_about_them_a_comment_or_another_section_is_no_block(self):
        template = read(os.path.join(ROOT, "forge-design", "components.md"))
        for text in (template, template + "\nButton: see the app.\n", template + "\n<!-- Button\n  states  hover -->\n",
                     template + "\n  states:\n", template.replace("## Components", "## Theme notes\n  states  hover\n\n"
                                                                   "## Components")):
            with self.subTest(text=text[-60:]):
                write(self.root, "components.md", text)
                code, check, _ = self.check("components", "components.md")
                self.assertEqual((code, check["what"]), (1, "components.md: ## Components holds no component block "
                                                            "with a states line"))
                self.assertIn("forge-design design Step 5", check["output"][0])
        self.assertEqual(self.check("components", "nowhere.md")[0], 2)


class CommandLineTests(Work):
    def test_plain_output_on_a_cp1252_pipe(self):
        write(self.root, "brand.json", '{"name": "Café →", "avoid": ["x"]}')
        code, out, err = run_cp1252(SCRIPT, "named", "brand.json", cwd=self.root)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("FAIL  the name Café \\u2192 from brand.json is in no file of the app", out)

    def test_a_check_is_needed(self):
        with self.assertRaises(SystemExit) as stop, contextlib.redirect_stderr(io.StringIO()):
            workcheck.main([])
        self.assertEqual(stop.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
