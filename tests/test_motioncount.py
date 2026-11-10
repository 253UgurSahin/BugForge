"""Tests for forge-motion/motioncount.py: what counts as a place that moves, that motion on offer
but on no element does not count, the exit codes and the JSON shape."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402

motioncount = load("forge-motion", "motioncount")
SCRIPT = os.path.join(ROOT, "forge-motion", "motioncount.py")
APP_CSS = (".btn { transition: transform 120ms; }\n.card:hover { transition: box-shadow 200ms; }\n"
           "@media (prefers-reduced-motion: no-preference) {\n  .toast { animation: rise 200ms; }\n}\n"
           ".plain { color: red; transition: none; }\n/* .old { transition: all 1s; } */\n")


class Project(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def write(self, name, text):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = motioncount.main([self.root] + list(args))
        return code, out.getvalue(), err.getvalue()

    def report(self, *args):
        code, out, _ = self.run_main("--json", *args)
        return code, json.loads(out)

    def copy_motion_css(self):
        shutil.copy(os.path.join(ROOT, "forge-motion", "motion.css"), os.path.join(self.root, "motion.css"))


class CountTests(Project):
    def test_a_plan_and_a_copied_motion_css_move_nothing(self):
        """What went wrong in practice: motion.css in the project, no element using it."""
        self.copy_motion_css()
        self.write("index.html", '<main><button class="btn">Go</button></main>\n')
        self.write("forge-work/motion.md", "# Motion\n.x { transition: all 1s; }\n")
        code, data = self.report()
        self.assertEqual(code, 1)
        self.assertEqual(data["places"], [])
        self.assertIn("m-enter", data["unused"])
        self.assertIn("m-stagger", data["unused"])
        code, out, _ = self.run_main()
        self.assertIn("FAIL: the app barely moves", out)
        self.assertIn("On offer but on no element", out)

    def test_the_apps_own_rules_count_and_none_or_comments_do_not(self):
        self.write("css/app.css", APP_CSS)
        code, data = self.report("--min", "1")
        self.assertEqual([(place["what"], place["line"]) for place in data["places"]],
                         [(".btn", 1), (".card:hover", 2), (".toast", 4)])
        self.assertEqual({place["kind"] for place in data["places"]}, {"style rule"})

    def test_a_motion_class_counts_once_an_element_carries_it(self):
        self.copy_motion_css()
        self.write("index.html", '<main class="m-enter"><ul class="list m-stagger"><li>a</li></ul></main>\n')
        self.write("src/Card.tsx", 'export const Card = () => <div className="card md:transition-colors">x</div>;\n')
        self.write("src/App.vue", "<template><p :class=\"x\" class='animate-pulse'>x</p></template>\n")
        code, data = self.report("--min", "4")
        self.assertEqual(code, 0)
        self.assertEqual(sorted(place["what"] for place in data["places"]),
                         ["animate-pulse", "m-enter", "m-stagger", "transition-colors"])
        self.assertNotIn("m-enter", data["unused"])
        self.assertIn("m-lift", data["unused"])

    def test_words_that_only_look_like_motion_classes_do_not_count(self):
        self.copy_motion_css()
        self.write("index.html", '<p class="am-enter team-stagger animate-none no-transition-x">x</p>\n'
                                 '<p>class="m-enter" in the text is no attribute of this tag</p>\n')
        self.assertEqual(len(self.report()[1]["places"]), 1)  # only the quoted attribute in the second line

    def test_an_m_class_with_no_moving_rule_in_the_app_does_not_count(self):
        self.write("index.html", '<main class="m-enter m-made-up"><p class="m-foo transition">x</p></main>\n')
        places = self.report()[1]["places"]
        self.assertEqual([place["what"] for place in places], ["transition"])  # no stylesheet has .m-enter here
        self.copy_motion_css()
        self.assertEqual([place["what"] for place in self.report()[1]["places"]], ["m-enter", "transition"])

    def test_scripts_that_animate(self):
        self.write("src/main.js", "el.animate([{ opacity: 0 }, { opacity: 1 }], 200);\n"
                                  "document.startViewTransition(() => swap());\n"
                                  "const seen = new IntersectionObserver(show);\n"
                                  "// el.animate([{ opacity: 0 }], 1);\nrequestAnimationFrame(tick);\n")
        code, data = self.report("--min", "1")
        self.assertEqual([place["line"] for place in data["places"]], [1, 2, 3, 5])

    def test_a_style_block_in_a_template(self):
        self.write("page.html", "<h1>x</h1>\n<style>\n.hero { animation: drift 20s infinite; }\n</style>\n")
        place = self.report()[1]["places"][0]
        self.assertEqual((place["what"], place["line"], place["kind"]), (".hero", 3, "style rule"))

    def test_dependencies_build_output_tests_and_notes_are_not_counted(self):
        for folder in ("node_modules/x", "dist", "forge-work", "e2e", "vendor/y"):
            self.write(folder + "/a.css", APP_CSS)
        self.write("app.min.css", APP_CSS)
        self.assertEqual(self.report()[1]["places"], [])


class ExitCodeTests(Project):
    def wire(self):
        self.write("css/app.css", APP_CSS)
        self.write("index.html", '<main class="transition"><p class="animate-in">x</p></main>\n')

    def test_enough_in_two_files_passes(self):
        self.wire()
        code, out, err = self.run_main()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("5 place(s) move, in 2 file(s)", out)
        self.assertNotIn("FAIL", out)

    def test_too_few_or_all_in_one_file_fails(self):
        self.wire()
        self.assertEqual(self.run_main("--min", "6")[0], 1)
        os.remove(os.path.join(self.root, "index.html"))
        self.write("css/app.css", APP_CSS + ".a { transition: color 1s; }\n.b { transition: color 1s; }\n")
        code, data = self.report()
        self.assertEqual((code, data["summary"]["places"], data["summary"]["files_moving"]), (1, 5, 1))

    def test_bad_input_is_exit_2(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(motioncount.main([os.path.join(self.root, "nope")]), 2)
            self.assertEqual(motioncount.main([self.root, "--min", "0"]), 2)
        self.assertIn("is not a folder", err.getvalue())

    def test_json_shape(self):
        self.wire()
        code, data = self.report()
        self.assertEqual(sorted(data), ["files_moving", "files_read", "places", "summary", "unread", "unused"])
        self.assertEqual(sorted(data["places"][0]), ["file", "kind", "line", "what"])
        self.assertEqual(data["summary"], {"places": 5, "files_moving": 2, "min": 5, "enough": True,
                                           "complete": True})

    def test_help_and_a_windows_pipe(self):
        done = subprocess.run([sys.executable, SCRIPT, "--help"], timeout=60, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0)
        self.assertIn("Exit codes:", done.stdout)
        self.write("index.html", '<p class="m-enter">café →</p>\n')
        code, out, err = run_cp1252(SCRIPT, self.root)
        self.assertEqual((code, err), (1, ""))


if __name__ == "__main__":
    unittest.main()
