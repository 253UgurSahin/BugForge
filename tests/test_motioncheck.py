"""Tests for forge-motion/motioncheck.py: each rule fires and stays quiet, in stylesheets, templates
and scripts, plus the walking rules, the exit codes and the output."""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252, symlink  # noqa: E402

mod = load("forge-motion", "motioncheck")
SCRIPT = os.path.join(ROOT, "forge-motion", "motioncheck.py")
CALM = "@media (prefers-reduced-motion: reduce) { .other { transition: none; } }\n"  # the project asks
ASKS = 'const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;\n'
CDN = "https://cdn.jsdelivr.net/npm/"


class Case(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def write(self, name, text, mode="w"):
        path = os.path.join(self.root, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8", "newline": ""})) as handle:
            handle.write(text)
        return path

    def fresh(self):
        shutil.rmtree(self.root)
        os.mkdir(self.root)

    def scan(self, files=None, fail_on="high"):
        for name, text in (files or {}).items():
            self.write(name, text)
        return mod.scan_path(self.root, fail_on)

    def rules(self, files=None):
        return sorted(item["rule"] for item in self.scan(files)["findings"])

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = mod.main(list(args))
        return code, out.getvalue(), err.getvalue()


class ReducedMotionTests(Case):
    def test_animation_and_nobody_asks_is_high(self):
        report = self.scan({"app.css": ".a { transition: opacity .2s; }\n.b { animation: pop .3s; }\n"})
        self.assertEqual([(f["rule"], f["severity"], f["line"]) for f in report["findings"]],
                         [("no-reduced-motion", "high", 1)])
        self.assertIn("2 rule(s)", report["findings"][0]["title"])

    def test_keyframes_alone_count_as_motion(self):
        self.assertEqual(self.rules({"a.css": "@keyframes pop { from { opacity: 0; } }\n"}), ["no-reduced-motion"])

    def test_a_rule_anywhere_in_the_project_is_enough(self):
        for name, text in [("calm.css", CALM), ("calm.js", ASKS), ("page.html", '<div class="motion-reduce:hidden">'),
                           ("b.scss", "@media (prefers-reduced-motion: no-preference) { .x { color: red; } }")]:
            with self.subTest(asks_in=name):
                self.assertEqual(self.rules({"app.css": ".a { transition: opacity .2s; }", name: text}), [])
                os.remove(os.path.join(self.root, name))

    def test_no_motion_means_no_finding(self):
        self.assertEqual(self.rules({"app.css": ".a { color: red; transition: none; }\n"}), [])


class CssRuleTests(Case):
    def css(self, text):
        return self.rules({"calm.css": CALM, "app.css": text})

    def test_transition_all(self):
        self.assertEqual(self.css(".a { transition: all .2s ease; }"), ["transition-all"])
        self.assertEqual(self.css(".a { -webkit-transition: all .2s; }"), ["transition-all"])
        self.assertEqual(self.css(".a { transition-property: all; }"), ["transition-all"])
        self.assertEqual(self.css(".a { transition: opacity .2s, overlay .2s allow-discrete; }"), [])

    def test_layout_properties_in_transitions(self):
        for value in ["width .3s", "max-height .3s ease", "transform .2s, left .2s", "margin-top .2s", "padding .2s"]:
            with self.subTest(value=value):
                self.assertEqual(self.css(".a { transition: %s; }" % value), ["layout"])
        self.assertEqual(self.css(".a { transition-property: top, bottom; }"), ["layout"])
        for value in ["transform .2s ease-in-out", "border-left-color .2s", "grid-template-rows .2s", "opacity .2s",
                      "line-height .2s", "stroke-dashoffset .4s"]:
            with self.subTest(value=value):
                self.assertEqual(self.css(".a { transition: %s; }" % value), [])

    def test_layout_properties_in_keyframes_once_per_animation(self):
        report = self.scan({"calm.css": CALM, "app.css": "@keyframes grow {\n  from { height: 0; }\n"
                                                         "  to { height: 100px; width: 5px; }\n}\n"})
        self.assertEqual([f["rule"] for f in report["findings"]], ["layout"])
        self.assertIn("@keyframes grow changes height", report["findings"][0]["title"])
        self.assertEqual(self.css("@keyframes in { from { opacity: 0; transform: translateY(8px); } }"), [])

    def test_infinite_outside_a_guard(self):
        self.assertEqual(self.css(".spin { animation: spin 1s linear infinite; }"), ["infinite"])
        self.assertEqual(self.css(".spin { animation-iteration-count: infinite; }"), ["infinite"])
        self.assertEqual(self.css(".a { animation: infinite-scroll 1s 3; }"), [])  # a name, not the keyword

    def test_infinite_inside_a_guard(self):
        guarded = "@media (prefers-reduced-motion: no-preference) { .spin { animation: spin 1s linear infinite; } }"
        self.assertEqual(self.css(guarded), [])
        stopped = (".spin, .other { animation: spin 1s infinite; }\n"
                   "@media (prefers-reduced-motion: reduce) { .spin { animation: none; } }")
        self.assertEqual(self.css(stopped), [])
        reset = (".spin { animation: spin 1s infinite; }\n@media (prefers-reduced-motion: reduce) {\n"
                 "  *, *::before { animation-iteration-count: 1 !important; animation-duration: .01ms !important; }\n}")
        self.assertEqual(self.css(reset), [])
        other = ".spin { animation: spin 1s infinite; }\n@media (prefers-reduced-motion: reduce) { .x { animation: none; } }"
        self.assertEqual(self.css(other), ["infinite"])

    def test_a_reduce_block_in_another_file_stops_it(self):
        files = {"a.css": ".spin { animation: spin 1s infinite; }",
                 "b.css": "@media (prefers-reduced-motion: reduce) { .spin { animation: none; } }"}
        self.assertEqual(self.rules(files), [])

    def test_durations(self):
        for value, found in [("opacity 2s", True), ("opacity 1200ms", True), ("opacity 50ms", True),
                             ("opacity .2s", False), ("opacity 1s", False), ("opacity 80ms", False),
                             ("opacity .2s 3s", False),  # the second time is the delay
                             ("opacity var(--duration-base) cubic-bezier(.2,.8,.2,1)", False),
                             ("visibility 0s linear .2s", False), ("opacity .2s, transform 1.5s", True)]:
            with self.subTest(value=value):
                self.assertEqual(self.css(".a { transition: %s; }" % value), ["duration"] if found else [])
        self.assertEqual(self.css(".a { transition-duration: 3s; }"), ["duration"])
        self.assertEqual(self.css(".a { animation: fade 3s; }"), [])  # only interface transitions

    def test_nothing_in_a_reduce_block_is_a_finding(self):
        block = "@media (prefers-reduced-motion: reduce) { * { transition: all .01ms !important; width: 0; } }"
        self.assertEqual(self.rules({"app.css": block}), [])

    def test_will_change(self):
        many = "".join(".a%d { will-change: transform; }\n" % n for n in range(6))
        report = self.scan({"app.css": many})
        self.assertEqual([(f["rule"], f["line"]) for f in report["findings"]], [("will-change", 1)])
        self.assertIn("6 rules", report["findings"][0]["title"])
        self.fresh()
        self.assertEqual(self.rules({"app.css": many.replace(".a5 { will-change: transform; }", "")}), [])
        self.fresh()
        self.assertEqual(self.rules({"b.css": "*, .x { will-change: transform; }\n.y { will-change: auto; }"}),
                         ["will-change"])

    def test_comments_and_strings_are_not_code(self):
        text = ('/* .a { transition: all 5s; } */\n.b::after { content: "} .c { transition: all 5s; }"; }\n'
                ".d { background: url(data:image/png;base64,AAAA); }\n")
        self.assertEqual(self.css(text), [])

    def test_scss_nesting_and_line_comments(self):
        text = (".card {\n  // transition: all 9s;\n  &:hover { transition: width .2s; }\n"
                "  @media (prefers-reduced-motion: no-preference) { .dot { animation: pulse 2s infinite; } }\n}\n")
        report = self.scan({"calm.css": CALM, "app.scss": text})
        self.assertEqual([(f["rule"], f["line"]) for f in report["findings"]], [("layout", 3)])

    def test_style_blocks_in_templates_with_the_right_line(self):
        page = "<html>\n<head>\n<style>\n.a { color: red; }\n.b { transition: all .2s; }\n</style>\n</head>\n"
        for name in ["page.html", "resources/views/home.blade.php", "templates/base.djhtml", "src/App.vue",
                     "src/Card.svelte"]:
            with self.subTest(template=name):
                report = self.scan({"calm.css": CALM, name: page})
                self.assertEqual([(f["rule"], f["line"], f["file"].replace(os.sep, "/").endswith(name))
                                  for f in report["findings"]], [("transition-all", 5, True)])
                os.remove(os.path.join(self.root, *name.split("/")))

    def test_css_in_a_script_is_not_read(self):
        self.assertEqual(self.rules({"a.js": "const css = `.a { transition: all 5s; }`;\n"}), [])

    def test_forge_allow_skips_the_line(self):
        self.assertEqual(self.css(".a { transition: all .2s; } /* forge:allow */"), [])


class ScriptRuleTests(Case):
    def test_library_from_a_cdn_is_high(self):
        lines = ['<script src="%sgsap@3.13/dist/gsap.min.js"></script>' % CDN,
                 '<script src="//unpkg.com/three@0.160.0/build/three.module.js" type="module"></script>',
                 'import * as THREE from "https://esm.sh/three@0.160.0";',
                 'const lottie = await import("%slottie-web@5/+esm");' % CDN,
                 '{ "imports": { "three": "https://unpkg.com/three@0.160.0/build/three.module.js" } }',
                 '<lottie-player src="https://files.example.com/loader.json" autoplay loop></lottie-player>',
                 '<script src="https://static.example.com/js/gsap.min.js"></script>',
                 "lottie.loadAnimation({ container, path: 'https://lottie.host/abc/def.json' });"]
        for line in lines:
            with self.subTest(line=line):
                report = self.scan({"page.html": "<p>hello</p>\n" + line + "\n"})
                self.assertEqual([(f["rule"], f["severity"], f["line"]) for f in report["findings"]
                                  if f["rule"] == "cdn"], [("cdn", "high", 2)])

    def test_local_and_unrelated_urls_are_not(self):
        lines = ['<script src="/build/assets/gsap-4f2a.js"></script>', 'import gsap from "gsap";',
                 '<script type="module" src="http://localhost:5173/src/three-scene.js"></script>',
                 '<a href="https://gsap.com/docs/v3/">the GSAP docs</a>',
                 '<script src="%sbootstrap@5/dist/js/bootstrap.min.js"></script>' % CDN,  # trackers.py's job
                 '<img src="https://images.example.com/three.png">']
        for line in lines:
            with self.subTest(line=line):
                found = [f["rule"] for f in self.scan({"page.html": line + "\n", "calm.js": ASKS})["findings"]]
                self.assertNotIn("cdn", found)

    def test_animation_loop_without_a_pause(self):
        loop = "function tick(now) {\n  draw(now);\n  requestAnimationFrame(tick);\n}\nrequestAnimationFrame(tick);\n"
        report = self.scan({"hero.js": loop})
        self.assertEqual([(f["rule"], f["severity"], f["line"]) for f in report["findings"]], [("raf", "medium", 3)])
        arrow = "const loop = () => {\n  draw();\n  frame = requestAnimationFrame(loop);\n};\nloop();\n"
        self.assertEqual(self.rules({"hero.js": arrow}), ["raf"])
        method = "class Scene {\n  render(now) {\n    requestAnimationFrame(this.render);\n  }\n}\n"
        self.assertEqual(self.rules({"hero.js": method}), ["raf"])

    def test_animation_loop_with_a_pause_or_one_shot(self):
        loop = "function tick() { draw(); requestAnimationFrame(tick); }\n"
        for pause in ["new IntersectionObserver(update).observe(canvas);",
                      'document.addEventListener("visibilitychange", update);', "if (document.hidden) return;"]:
            with self.subTest(pause=pause):
                self.assertEqual(self.rules({"hero.ts": loop + pause + "\n"}), [])
        self.assertEqual(self.rules({"a.js": "requestAnimationFrame(() => el.classList.add('in'));\n"}), [])
        self.assertEqual(self.rules({"a.js": "requestAnimationFrame(callbackFromElsewhere);\n"}), [])

    def test_library_and_no_script_asks_for_reduced_motion(self):
        uses = {"gsap": 'import { gsap } from "gsap";', "three": "import * as THREE from 'three';",
                "lottie-web": 'const lottie = require("lottie-web");',
                "@lottiefiles/dotlottie-web": 'import { DotLottie } from "@lottiefiles/dotlottie-web";',
                "lottie": "lottie.loadAnimation({ container });", "THREE": "const scene = new THREE.Scene();"}
        for name, line in uses.items():
            with self.subTest(library=name):
                files = {"calm.css": CALM, "src/hero.tsx": "// hero\n" + line + "\ngsap.to(box, { x: 100 });\n"}
                report = self.scan(files)
                self.assertEqual([(f["rule"], f["severity"], f["line"]) for f in report["findings"]],
                                 [("library", "medium", 2)])  # once per file, and CSS asking is not enough
                self.assertIn(name, report["findings"][0]["title"])
                self.assertEqual(self.rules({"src/motion.ts": ASKS}), [])
                os.remove(os.path.join(self.root, "src", "motion.ts"))

    def test_other_imports_are_not_libraries(self):
        self.assertEqual(self.rules({"a.js": 'import three from "./three-columns.js";\nimport x from "threads";\n'}), [])

    def test_autoplay_video(self):
        report = self.scan({"a.html": "<main>\n<video\n  src='/a.mp4'\n  autoplay muted loop></video>"})
        self.assertEqual([(f["rule"], f["severity"], f["line"]) for f in report["findings"]], [("video", "medium", 2)])
        self.fresh()
        self.assertEqual(self.rules({"a.jsx": "<video src={clip} autoPlay muted loop playsInline />"}), ["video"])
        self.fresh()
        self.assertEqual(self.rules({"a.html": "<video src='/a.mp4' autoplay muted controls></video>",
                                     "b.html": "<video src='/a.mp4' muted></video>"}), [])


class WalkTests(Case):
    BAD = ".a { transition: all .2s; }\n"

    def test_skipped_folders_minified_and_other_files(self):
        for name in ["node_modules/x/x.css", "vendor/x.css", "dist/app.css", "build/app.css", ".next/a.css",
                     "forge-work/notes.css", ".git/x.css", "public/app.min.css", "notes.md", "data.json"]:
            self.write(name, self.BAD)
        report = self.scan()
        self.assertEqual((report["findings"], report["summary"]["files_checked"]), ([], 0))

    def test_symlinks_are_not_followed(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        with open(os.path.join(outside, "x.css"), "w", encoding="utf-8") as handle:
            handle.write(self.BAD)
        symlink(self, os.path.join(outside, "x.css"), os.path.join(self.root, "link.css"))
        symlink(self, outside, os.path.join(self.root, "linked"))
        self.assertEqual(self.scan()["summary"]["files_checked"], 0)

    def test_a_named_file_is_read_whatever_its_type(self):
        path = self.write("styles.txt", "<style>" + self.BAD + "</style>")
        self.assertEqual([f["rule"] for f in mod.scan_path(path)["findings"]], ["no-reduced-motion", "transition-all"])

    def test_windows_line_ends_and_bad_bytes(self):
        self.write("a.css", b".a {\r\n  color: red;\r\n  transition: all .2s;\r\n}\r\n\xff\xfe", "wb")
        report = self.scan()
        self.assertEqual([(f["rule"], f["line"]) for f in report["findings"]],
                         [("no-reduced-motion", 3), ("transition-all", 3)])


class OutputTests(Case):
    def test_exit_codes(self):
        self.write("calm.css", CALM)
        self.assertEqual(self.run_main(self.root)[0], 0)
        self.write("app.css", ".a { transition: all .2s; }\n.b { transition: width .2s; }\n")
        self.assertEqual(self.run_main(self.root)[0], 0)  # low and medium: under the default, high
        self.assertEqual(self.run_main(self.root, "--fail-on", "medium")[0], 1)
        self.assertEqual(self.run_main(self.root, "--fail-on", "low")[0], 1)
        os.remove(os.path.join(self.root, "calm.css"))
        self.assertEqual(self.run_main(self.root)[0], 1)  # high now

    def test_bad_input_is_exit_2(self):
        code, _, err = self.run_main(os.path.join(self.root, "missing"))
        self.assertEqual(code, 2)
        self.assertIn("does not exist", err)
        binary = self.write("blob.css", b"\0\0\0\0", "wb")
        self.assertEqual(self.run_main(binary)[0], 2)
        big = self.write("big.css", "a" * (mod.MAX_BYTES + 1))
        self.assertEqual(self.run_main(big)[0], 2)
        self.assertEqual(self.run_main(self.root)[0], 0)  # in a folder they are skipped, with a warning
        with self.assertRaises(SystemExit) as stop, contextlib.redirect_stderr(io.StringIO()):
            mod.main([self.root, "--fail-on", "worst"])
        self.assertEqual(stop.exception.code, 2)

    def test_json_shape(self):
        self.write("app.css", ".a { transition: all .2s; }\n")
        code, out, _ = self.run_main(self.root, "--json")
        report = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(sorted(report), ["findings", "summary"])
        self.assertEqual([f["severity"] for f in report["findings"]], ["high", "low"])  # worst first
        for item in report["findings"]:
            self.assertEqual(sorted(item), ["file", "fix", "line", "rule", "severity", "title", "where", "why"])
            self.assertEqual(item["where"], "%s:%d" % (item["file"], item["line"]))
        self.assertEqual(report["summary"], {"critical": 0, "high": 1, "medium": 0, "low": 1, "total": 2,
                                             "files_checked": 1, "not_checked": [], "fail_on": "high", "failed": True})

    def test_human_output_says_what_where_why_and_fix(self):
        self.write("app.css", ".a { transition: all .2s; }\n")
        code, out, _ = self.run_main(self.root)
        for part in ["HIGH  animations, and no prefers-reduced-motion", "LOW  transition: all", "where: ", "app.css:1",
                     "why:   ", "fix:   ", "2 findings: 1 high, 1 low.", "Files checked: 1."]:
            self.assertIn(part, out)
        os.remove(os.path.join(self.root, "app.css"))
        self.assertIn("No findings", self.run_main(self.root)[1])

    def test_help_and_a_cp1252_pipe(self):
        with self.assertRaises(SystemExit) as stop, contextlib.redirect_stdout(io.StringIO()) as out:
            mod.main(["--help"])
        self.assertEqual(stop.exception.code, 0)
        self.assertIn("Exit codes", out.getvalue())
        self.write("app.css", CALM + ".spin→x { animation: spin 1s infinite; }\n")
        code, out, err = run_cp1252(SCRIPT, self.root, "--fail-on", "medium")
        self.assertEqual((code, err), (1, ""))
        self.assertIn("\\u2192", out)

    def test_the_pack_own_motion_files_are_clean(self):
        report = mod.scan_path(os.path.join(ROOT, "forge-motion"), "low")
        self.assertEqual(report["findings"], [])
        self.assertGreaterEqual(report["summary"]["files_checked"], 2)


if __name__ == "__main__":
    unittest.main()
