"""Tests for forge-design/motioncount.py: what counts as a place that moves, that motion on offer
but on no element does not count, the exit codes and the JSON shape; and with --level, each feature
found and missing, each level passing and failing, --level auto, and that comments and strings do not count."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252, symlink  # noqa: E402

motioncount = load("forge-design", "motioncount")
SCRIPT = os.path.join(ROOT, "forge-design", "motioncount.py")
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
        shutil.copy(os.path.join(ROOT, "forge-design", "motion.css"), os.path.join(self.root, "motion.css"))


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
        self.assertEqual(sorted(data), ["features", "files_moving", "files_read", "level", "places", "summary",
                                        "unread", "unused"])
        self.assertEqual(sorted(data["places"][0]), ["file", "kind", "line", "what"])
        self.assertEqual(data["summary"], {"places": 5, "files_moving": 2, "min": 5, "enough": True,
                                           "complete": True})
        self.assertEqual((data["level"], data["features"]), (None, []))  # without --level: no features asked

    def test_help_and_a_windows_pipe(self):
        done = subprocess.run([sys.executable, SCRIPT, "--help"], timeout=60, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0)
        self.assertIn("Exit codes:", done.stdout)
        self.write("index.html", '<p class="m-enter">café →</p>\n')
        code, out, err = run_cp1252(SCRIPT, self.root)
        self.assertEqual((code, err), (1, ""))


# --level: the features. FEATURES are the names in motioncount.json, in level order.
FEATURES = [feature["name"] for feature in motioncount.load_rules(motioncount.RULES)["features"]]
CONTROLS = ["btn", "link", "tab", "chip", "toggle", "menu", "toast", "badge", "row", "field", "nav", "avatar",
            "tooltip", "pager", "panel", "tile", "pill", "step", "crumb", "sheet", "drawer", "card"]
REDUCED = "@media (prefers-reduced-motion: reduce) {\n  * { transition-duration: 1ms !important; }\n}\n"
SCENE = ("import * as THREE from 'three';\nexport function mount(el) {\n  const renderer = new THREE.WebGLRenderer();\n"
         "  el.addEventListener('pointermove', (e) => { renderer.domElement.style.opacity = 1; });\n"
         "  return renderer;\n}\n")


def sample_app(level, places):
    """A small app of a lake-fishing log at the look LEVEL: its features and PLACES places that move (one is
    the motion class in index.html, so they are always in two files)."""
    css = "".join(".%s { transition: transform 150ms; }\n" % name for name in CONTROLS[:places - 1]) + REDUCED
    html = '<main><h1 class="hero">Lake log</h1><button class="btn transition">Log a catch</button>\n'
    js, scene = "", ""
    if level >= 2:
        css += "@keyframes rise { from { opacity: 0; } }\n.hero { animation: rise 300ms both; }\n@view-transition { navigation: auto; }\n"
    if level >= 3:
        css += ".shelf { perspective: 800px; }\n.shelf > .card:hover { transform: rotateY(-6deg); }\n"
        js += "const seen = new IntersectionObserver(reveal);\n"
    if level >= 4:
        scene = SCENE
        html += '<section id="hero"><img data-scene-poster src="poster.png" alt=""></section>\n'
        js += "import('./scene.js').then((m) => m.mount(document.getElementById('hero')));\n"
    if level >= 5:
        scene = scene.replace("  return renderer;", "  const material = new THREE.ShaderMaterial({ fragmentShader: "
                              "'void main() { gl_FragColor = vec4(1.0); }' });\n  return { setProgress(p) {}, "
                              "setData(values) {} };")
        js += ("addEventListener('scroll', () => hero.setProgress(scrollY / innerHeight));\n"
               "fetch('/api/catches').then((r) => r.json()).then((stats) => hero.setData(stats));\n")
    files = {"css/app.css": css, "index.html": html + "</main>\n", "app.js": js, "scene.js": scene}
    return {name: text for name, text in files.items() if text}


class LevelProject(Project):
    def build(self, files):
        for name, text in files.items():
            self.write(name, text)

    def features(self, *args):
        """{feature name: where it was found, or None} at level 5 with --min 1, so only the features matter."""
        code, data = self.report("--level", "5", "--min", "1", *args)
        return {item["name"]: item["where"] for item in data["features"]}

    def found(self, files, *names):
        self.build(files)
        where = self.features()
        self.assertEqual(sorted(name for name, at in where.items() if at), sorted(names), files)
        return where


class FeatureTests(LevelProject):
    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def check(self, cases):
        """Each case: (files, the feature names found), each in a fresh folder."""
        for files, names in cases:
            with self.subTest(files=files):
                shutil.rmtree(self.root, ignore_errors=True)
                os.makedirs(self.root)
                self.found(files, *names)

    def test_reduced_motion(self):
        name = FEATURES[0]
        self.check([({"a.css": REDUCED}, [name]),
                    ({"a.css": "@media (prefers-reduced-motion: no-preference) { .a { color: red; } }\n"}, [name]),
                    ({"A.tsx": 'export const A = () => <p className="motion-reduce:transition-none">x</p>;\n'}, [name]),
                    ({"a.js": "if (matchMedia('(prefers-reduced-motion: reduce)').matches) stop();\n"}, [name]),
                    ({"a.css": ".a { transition: color 1s; }\n"}, [])])

    def test_entrance(self):
        name = FEATURES[1]
        motion = open(os.path.join(ROOT, "forge-design", "motion.css"), encoding="utf-8").read()
        found = [f for f in FEATURES[:3] if f != FEATURES[2]]  # motion.css brings its reduced-motion rule
        self.check([({"a.css": ".hero { animation: rise 300ms both; }\n"}, [name]),
                    ({"a.css": "@starting-style { dialog[open] { opacity: 0; } }\n"}, [name]),
                    ({"a.js": "el.animate([{ opacity: 0 }, { opacity: 1 }], 300);\n"}, [name]),
                    ({"a.html": '<p class="md:animate-fade-in">x</p>\n'}, [name]),
                    ({"a.css": ".btn:hover { animation: wiggle 1s; }\n"}, []),
                    ({"a.html": '<p class="animate-spin">x</p>\n'}, []),
                    ({"motion.css": motion, "a.html": '<main class="m-enter">x</main>\n'},
                     found + [FEATURES[2]]),  # motion.css also has @view-transition, which needs no class
                    ({"motion.css": motion, "a.html": "<main>x</main>\n"}, [FEATURES[0], FEATURES[2]])])

    def test_page_transition_or_counted_number(self):
        name = FEATURES[2]
        count = "out.textContent = Math.round(value).toLocaleString();\n"
        self.check([({"a.css": "@view-transition { navigation: auto; }\n"}, [name]),
                    ({"a.css": ".photo { view-transition-name: photo; }\n"}, [name]),
                    ({"a.js": "document.startViewTransition(() => swap());\n"}, [name]),
                    ({"a.js": "function tick() { %s requestAnimationFrame(tick); }\n" % count}, [name]),
                    ({"a.js": "setInterval(() => { %s }, 50);\n" % count}, [name]),
                    ({"a.js": count, "b.js": "requestAnimationFrame(tick);\n"}, []),  # not in one file
                    ({"a.css": ".m-count { transition: color 1s; }\n", "a.html": '<b class="m-count">9</b>\n'}, [name]),
                    ({"a.css": ".m-count { transition: color 1s; }\n", "a.html": "<b>9</b>\n"}, []),
                    ({"a.css": ".photo { view-transition-name: none; }\n"}, [])])

    def test_scroll_driven_motion(self):
        name = FEATURES[3]
        self.check([({"a.js": "const seen = new IntersectionObserver(show);\n"}, [name]),
                    ({"a.css": ".r { animation: rise linear both; animation-timeline: view(); }\n"},
                     [name, FEATURES[1]]),
                    ({"a.css": ".bar { animation-timeline: scroll(root); }\n"}, [name]),
                    ({"a.js": "addEventListener('scroll', () => { progress = scrollY / max; });\n"}, [name]),
                    ({"a.js": "addEventListener('scroll', () => log(scrollY));\n"}, []),
                    ({"a.css": "@supports (animation-timeline: view()) { .r { color: red; } }\n"}, [])])

    def test_css_3d_or_depth(self):
        name = FEATURES[4]
        self.check([({"a.css": ".shelf { perspective: 900px; }\n"}, [name]),
                    ({"a.css": ".card { transform-style: preserve-3d; }\n"}, [name]),
                    ({"a.css": ".card:hover { transform: rotateX(4deg); }\n"}, [name]),
                    ({"a.css": ".layer { transform: translate3d(0, 0, 12px); }\n"}, [name]),
                    ({"a.css": ".layer { transform: translate3d(4px, 2px, 0); }\n"}, []),
                    ({"a.js": "card.style.transform = `rotateY(${x}deg)`;\n"}, [name]),
                    ({"a.js": "import { tilt } from './scenes/depth.js';\n"}, [name, FEATURES[5], FEATURES[6]]),
                    ({"a.html": '<article class="card" data-depth="2">x</article>\n'}, [name]),
                    ({"a.css": ".a { transform: rotate(4deg) translate(2px, 3px); }\n"}, [])])

    def test_webgl_scene(self):
        name = FEATURES[5]
        self.check([({"a.js": "import * as THREE from 'three';\n"}, [name]),
                    ({"a.js": "const gl = canvas.getContext('webgl2');\n"}, [name]),
                    ({"a.js": "const two = canvas.getContext('2d');\n"}, []),
                    ({"a.html": "<script type=\"module\">\nimport { Scene } from 'three';\n</script>\n"}, [name])])

    def test_pointer_reaching_the_scene(self):
        name = FEATURES[6]
        self.check([({"scene.js": SCENE}, [FEATURES[5], name]),
                    ({"scene.js": SCENE.replace("pointermove", "click"),
                      "other.js": "addEventListener('pointermove', move);\n"}, [FEATURES[5]]),  # not in the scene's file
                    ({"a.js": "import * as THREE from 'three';\nhero.setPointer(x, y);\n"}, [FEATURES[5], name]),
                    ({"a.js": "lazyScene(el, () => import('./form.js'));\n"}, [FEATURES[5], name])])

    def test_fallback(self):
        name = FEATURES[7]
        self.check([({"a.html": '<div id="hero"><img data-scene-poster src="p.png" alt=""></div>\n'}, [name]),
                    ({"a.css": '[data-scene="fallback"] .poster { display: block; }\n'}, [name]),
                    ({"a.html": '<div class="scene" poster="p.png"></div>\n'}, [name]),
                    ({"a.html": '<video poster="p.png"></video>\n'}, []),
                    ({"a.js": "const gl = canvas.getContext('webgl');\nif (!gl) showPoster();\n"}, [FEATURES[5], name]),
                    ({"a.js": "const gl = canvas.getContext('webgl');\ndraw(gl);\n"}, [FEATURES[5]])])

    def test_scroll_driving_the_scene(self):
        name = FEATURES[8]
        self.check([({"a.js": "hero.setProgress(0.4);\n"}, [name]),
                    ({"a.js": "import { journey } from './scenes/journey.js';\n"}, [name, FEATURES[5], FEATURES[6]]),
                    ({"scene.js": SCENE + "addEventListener('scroll', () => tilt(scrollY));\n"},
                     [FEATURES[5], FEATURES[6], name]),
                    ({"scene.js": SCENE, "other.js": "addEventListener('scroll', () => tilt(scrollY));\n"},
                     [FEATURES[5], FEATURES[6]])])

    def test_custom_shader(self):
        name = FEATURES[9]
        self.check([({"a.js": "const m = new THREE.ShaderMaterial({});\n"}, [name]),
                    ({"a.js": "const frag = `void main() { gl_FragColor = vec4(1.0); }`;\n"}, [name]),  # GLSL: strings
                    ({"a.js": "import { mount } from './scenes/aurora.js';\n"}, [FEATURES[5], FEATURES[6], name]),
                    ({"a.js": "const m = new THREE.MeshStandardMaterial({});\n"}, [])])

    def test_data_hook(self):
        name = FEATURES[10]
        self.check([({"a.js": "hero.setData(stats.catches);\n"}, [name]),
                    ({"a.js": "material.uniforms.uLevel.value = data.level;\n"}, [name]),
                    ({"a.js": "material.uniforms.uTime.value = clock.elapsed;\n"}, []),
                    ({"a.js": "hero.setData();\n"}, [])])


class HonestyTests(LevelProject):
    def test_words_only_in_comments_or_strings_do_not_count(self):
        self.found({
            "a.css": "/* @media (prefers-reduced-motion: reduce) {} .x { perspective: 10px; } @view-transition {} */\n"
                     '.note::after { content: "perspective: 10px; animation-timeline: view()"; }\n',
            "a.js": "// import * as THREE from 'three'; hero.setProgress(1); hero.setData(stats);\n"
                    "/* new IntersectionObserver(show); el.animate([{}]); gl_FragColor */\n"
                    'const doc = "new IntersectionObserver(x); el.setData(values); new THREE.ShaderMaterial()";\n'
                    "const tip = 'startViewTransition( and matchMedia(prefers-reduced-motion)';\n",
            "a.html": '<!-- <img data-scene-poster src="p.png"> <div data-depth> -->\n'
                      "<p>Add data-depth and poster= and class=\"motion-reduce:x\" later.</p>\n"})

    def test_the_scene_kits_own_files_count_only_once_used(self):
        kit = "import * as THREE from 'three';\nconst m = new THREE.ShaderMaterial({});\nm.setData(values);\n"
        self.found({"src/scenes/form.js": kit, "src/scenes/stage.js": kit})
        self.found({"src/main.js": "import { mount } from './scenes/form.js';\n"}, *FEATURES[5:7] + [FEATURES[9]])

    def test_dependencies_and_build_output_never_count(self):
        self.found({folder + "/x.js": SCENE for folder in ("node_modules/three", "dist", "build", "vendor", "forge-work")})

    def test_a_rule_for_an_m_class_counts_once_an_element_carries_it(self):
        css = ".m-tilt { transition: transform 1s; perspective: 600px; }\n"
        self.found({"a.css": css, "a.html": "<p>x</p>\n"})
        self.found({"a.html": '<p class="m-tilt">x</p>\n'}, FEATURES[4])


class LevelTests(LevelProject):
    MINIMUM = {1: 5, 2: 12, 3: 20, 4: 20, 5: 20}

    def test_each_level_passes_with_its_app_and_fails_without(self):
        for level in range(1, 6):
            with self.subTest(level=level):
                shutil.rmtree(self.root, ignore_errors=True)
                self.build(sample_app(level, self.MINIMUM[level]))
                code, data = self.report("--level", str(level))
                self.assertEqual((code, data["level"], data["summary"]["min"]), (0, level, self.MINIMUM[level]))
                self.assertEqual([item["level"] for item in data["features"]],
                                 [item for item in (1, 2, 2, 3, 3, 4, 4, 4, 5, 5, 5) if item <= level])
                self.assertTrue(all(item["found"] and item["where"] for item in data["features"]))
                if level < 5:  # the next level asks for more
                    code, data = self.report("--level", str(level + 1))
                    self.assertEqual(code, 1)
                    self.assertTrue([item for item in data["features"] if not item["found"]])

    def test_too_few_places_fail_even_with_every_feature(self):
        self.build(sample_app(3, 12))
        code, data = self.report("--level", "3")
        self.assertEqual((code, data["summary"]["enough"]), (1, False))
        self.assertEqual(self.report("--level", "3", "--min", "12")[0], 0)  # --min wins over the level's
        self.assertEqual(self.report("--level", "3", "--min", "25")[0], 1)

    def test_the_text_output(self):
        self.build(sample_app(1, 5))
        code, out, err = self.run_main("--level", "2")
        self.assertEqual((code, err), (1, ""))
        self.assertIn("Level 2 needs:\nfound  %s  (css/app.css:5)\n" % FEATURES[0], out)
        self.assertIn("MISSING  %s: " % FEATURES[1], out)
        self.assertIn("FAIL: not level 2 yet: 2 feature(s) MISSING above.", out)
        self.assertNotIn("Level", self.run_main()[1])

    def test_json_shape(self):
        self.build(sample_app(4, 20))
        code, data = self.report("--level", "4")
        self.assertEqual(code, 0)
        self.assertEqual(sorted(data["features"][0]), ["found", "level", "name", "needs", "where"])
        self.assertEqual(data["features"][7]["where"], "index.html:2")


class AutoTests(LevelProject):
    def record(self, text):
        self.write("forge-work/levels.json", text)

    def test_auto_reads_the_look_level(self):
        self.build(sample_app(2, 12))
        self.record(json.dumps({"look": {"level": 2, "said": "niveau 2", "at": "2026-11-10T10:00:00+01:00"},
                                "test": {"level": 5, "said": "alles", "at": "2026-11-10T10:00:00+01:00"}}))
        code, data = self.report("--level", "auto")
        self.assertEqual((code, data["level"], data["summary"]["min"]), (0, 2, 12))

    def test_auto_without_a_look_level_is_exit_2_and_says_to_ask(self):
        self.build(sample_app(2, 12))
        for text in (None, '{"test": {"level": 3}}', '{"look": {"level": 7}}', '{"look": {"level": "4"}}',
                     "not json", "[]"):
            with self.subTest(text=text):
                if text is not None:
                    self.record(text)
                code, out, err = self.run_main("--level", "auto")
                self.assertEqual((code, out), (2, ""))
                self.assertIn("python3 ../forge/level.py set look N --said '<their words>'", err)
                self.assertIn("Ask the user", err)

    def test_a_linked_record_is_never_read(self):
        self.build(sample_app(2, 12))
        real = os.path.join(self.root, "real.json")
        with open(real, "w", encoding="utf-8") as handle:
            handle.write('{"look": {"level": 2, "said": "2", "at": "2026-11-10T10:00:00+01:00"}}')
        os.makedirs(os.path.join(self.root, "forge-work"))
        symlink(self, real, os.path.join(self.root, "forge-work", "levels.json"))
        code, out, err = self.run_main("--level", "auto")
        self.assertEqual(code, 2)
        self.assertIn("is a link, so it was not read", err)
        os.remove(os.path.join(self.root, "forge-work", "levels.json"))
        os.rmdir(os.path.join(self.root, "forge-work"))
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other, ignore_errors=True)
        shutil.copy(real, os.path.join(other, "levels.json"))
        symlink(self, other, os.path.join(self.root, "forge-work"))  # a linked forge-work folder: not read either
        self.assertIn("is a link", self.run_main("--level", "auto")[2])


class BadInputTests(LevelProject):
    def test_a_level_out_of_range_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            motioncount.main([self.root, "--level", "6"])
        self.assertEqual(raised.exception.code, 2)

    def test_a_missing_or_broken_motioncount_json_is_exit_2(self):
        broken = os.path.join(self.root, "rules.json")
        good = json.loads(open(motioncount.RULES, encoding="utf-8").read())
        bad_view = dict(good, features=[dict(good["features"][0], signals=[{"view": "x", "re": "a"}])] + good["features"])
        for text in (None, "{", '{"min": {}}', json.dumps(dict(good, min={"1": 5})), json.dumps(bad_view),
                     json.dumps(dict(good, features=[dict(good["features"][0], signals=[{"view": "style", "re": "("}])]))):
            with self.subTest(text=text and text[:40]):
                if text is not None:
                    with open(broken, "w", encoding="utf-8") as handle:
                        handle.write(text)
                with mock.patch.object(motioncount, "RULES", broken):
                    code, out, err = self.run_main()
                self.assertEqual(code, 2)
                self.assertIn("is missing or broken", err)

    def test_hostile_input_stays_fast(self):
        self.write("a.js", "<" * 200000 + "`" + "a = getContext('webgl') " * 2000)
        self.write("b.html", "<div " + "class=' " * 50000)
        self.write("c.css", "/*" + "{" * 100000)
        start = time.time()
        self.assertIn(self.run_main("--level", "5")[0], (1, 2))
        self.assertLess(time.time() - start, 20)


if __name__ == "__main__":
    unittest.main()
