"""Tests for forge-design/sweep.py: finding the original's name, domains and colours, what is
skipped, the brand file, the exit codes and the JSON shape. The first tests are ported from
replica-skill's tests/test_sweep.py; forge-work/ takes the place of the replica/ folder. The
Review* classes hold one regression test per defect found in review."""

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
from _load import ROOT, load, symlink  # noqa: E402

sweep = load("forge-design", "sweep")
SCRIPT = os.path.join(ROOT, "forge-design", "sweep.py")


def put(root, rel, text, binary=False):
    """Write a file under ROOT, making its folders. Returns its path."""
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8", "newline": ""})) as fh:
        fh.write(text)
    return path


def run(*args):
    """Run main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = sweep.main(list(args))
    return code, out.getvalue(), err.getvalue()


def matchers(**lists):
    """The usual lists for these tests, with any of them replaced."""
    base = {"avoid": ["Calendly", "Acuity Scheduling"], "domains": ["calendly.com"], "colors": ["#006bff"]}
    base.update(lists)
    return sweep.make_matchers(**base)


class Project(unittest.TestCase):
    """A small clone with leftovers in it (the fixture from the original tests)."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        r = self.root
        put(r, "src/app/page.tsx", "export default function Page() {\n  return <h1>Slotwise</h1>\n}\n")
        put(r, "src/components/CalendlyEmbed.tsx", "// left over\n")
        put(r, "src/lib/copy.ts", "export const hero = 'The calendly alternative'\n")
        put(r, "src/styles/tokens.css", ":root { --accent: #006BFF; --bg: #fff; }\n")
        put(r, "src/lib/links.ts", "const help = 'https://help.calendly.com/x'\n")
        put(r, "src/lib/team.ts", "export const AcuitySchedulingSync = 1\n")
        put(r, "forge-work/recon.md", "# Recon: Calendly\n")
        put(r, "node_modules/x/index.js", "calendly\n")
        put(r, "vendor/x/Calendly.php", "calendly\n")
        put(r, "storage/framework/views/x.php", "calendly\n")
        put(r, "public/logo.png", b"\x89PNG\0calendly", binary=True)
        put(r, "package-lock.json", '{"calendly": 1}\n')

    def tearDown(self):
        shutil.rmtree(self.root)

    def findings(self, **lists):
        return sweep.sweep(self.root, matchers(**lists))[0]


class Finds(Project):
    def test_finds_names_paths_domains_and_colours(self):
        kinds = {(f["kind"], os.path.basename(f["file"].rstrip("/"))) for f in self.findings()}
        self.assertIn(("path", "CalendlyEmbed.tsx"), kinds)
        self.assertIn(("name", "copy.ts"), kinds)
        self.assertIn(("domain", "links.ts"), kinds)
        self.assertIn(("color", "tokens.css"), kinds)
        self.assertIn(("name", "team.ts"), kinds)  # AcuitySchedulingSync

    def test_folder_names_are_checked(self):
        put(self.root, "src/calendly-widget/index.ts", "export {}\n")
        where = [f["where"] for f in self.findings() if f["kind"] == "path"]
        self.assertIn(os.path.join("src", "calendly-widget") + "/", where)

    def test_name_variants(self):
        for line in ["acuity_scheduling", "ACUITY SCHEDULING", "acuity-scheduling", "Acuity  Scheduling"]:
            with self.subTest(line=line):
                self.assertEqual([hit[0] for hit in sweep.scan_line(line, matchers())], ["name"])
        self.assertEqual(sweep.scan_line("Acuity alone is a normal word", matchers()), [])

    def test_short_hex_matches_long(self):
        put(self.root, "src/a.css", "a { color: #06f }\n")
        found = sweep.sweep(self.root, sweep.make_matchers(colors=["#0066FF"]))[0]
        self.assertTrue(any(f["file"].endswith("a.css") for f in found))

    def test_colour_forms(self):
        m = sweep.make_matchers(colors=["006bff"])  # the # may be left out in the brand file
        for line in ["#006BFF", "#006bffcc", "rgb(0, 107, 255)", "rgba(0,107,255,.5)", "rgb(0 107 255 / 50%)",
                     "bg-[#006bff]"]:
            with self.subTest(line=line):
                self.assertEqual(sweep.scan_line(line, m), [("color", "#006bff", "#006bff")])
        for line in ["#006bfe", "#006bff1", "rgb(300, 107, 255)", "#006bffzz"]:
            with self.subTest(line=line):
                self.assertEqual(sweep.scan_line(line, m), [])

    def test_domains_are_matched_bare(self):
        m = sweep.make_matchers(domains=["https://www.Calendly.com/pricing"])
        self.assertEqual(m["domains"][0][0], "calendly.com")
        self.assertEqual([h[0] for h in sweep.scan_line("see app.calendly.com", m)], ["domain"])
        self.assertEqual([h[0] for h in sweep.scan_line("mail help@calendly.com.", m)], ["domain"])

    def test_line_numbers_with_any_line_ending(self):
        put(self.root, "src/crlf.ts", "first\r\nsecond calendly\r\n")
        put(self.root, "src/cr.ts", "first\rsecond\rthird calendly")
        where = {f["where"] for f in self.findings()}
        self.assertIn(os.path.join("src", "crlf.ts") + ":2", where)
        self.assertIn(os.path.join("src", "cr.ts") + ":3", where)


class Skips(Project):
    def test_skips_planning_folder_deps_locks_and_binaries(self):
        files = {f["file"] for f in self.findings()}
        self.assertFalse(any(f.startswith("forge-work") for f in files))
        self.assertFalse(any("node_modules" in f or "vendor" in f or "storage" in f for f in files))
        self.assertNotIn("package-lock.json", files)
        self.assertNotIn(os.path.join("public", "logo.png"), files)
        self.assertNotIn(os.path.join("src", "app", "page.tsx"), files)

    def test_forge_work_is_only_skipped_at_the_top(self):
        put(self.root, "public/forge-work/notes.md", "Calendly\n")  # it would ship from public/
        files = {f["file"] for f in self.findings()}
        self.assertIn(os.path.join("public", "forge-work", "notes.md"), files)

    def test_binary_files_are_skipped_and_counted(self):
        findings, summary = sweep.sweep(self.root, matchers())
        self.assertEqual(summary["files_skipped"], 1)  # logo.png
        self.assertNotIn(os.path.join("public", "logo.png"), {f["file"] for f in findings})

    def test_symlinks_are_not_followed_but_their_names_are_checked(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)
        put(outside, "secret.txt", "calendly\n")
        symlink(self, os.path.join(outside, "secret.txt"), os.path.join(self.root, "src", "plain-link"))
        symlink(self, outside, os.path.join(self.root, "src", "folder-link"))
        symlink(self, outside, os.path.join(self.root, "src", "calendly-link"))
        files = {f["file"] for f in self.findings()}
        self.assertNotIn(os.path.join("src", "plain-link"), files)
        self.assertFalse(any("folder-link" in f or "secret.txt" in f for f in files))
        self.assertIn(os.path.join("src", "calendly-link"), files)

    def test_forge_allow_line_is_listed_not_a_finding(self):
        put(self.root, "src/import.ts", "const label = 'Import from Calendly' // forge:allow\n")
        findings, summary = sweep.sweep(self.root, matchers())
        self.assertNotIn(os.path.join("src", "import.ts"), {f["file"] for f in findings})
        self.assertEqual(summary["allowed"], [os.path.join("src", "import.ts") + ":1"])
        out = run(self.root, "--avoid", "Calendly")[1]  # the user sees each one
        self.assertIn("Let through by forge:allow, each needs the user's OK: " + os.path.join("src", "import.ts"), out)

    def test_allow_words(self):
        m = sweep.make_matchers(avoid=["Linear"], domains=["linear.app"], allow=["linear-gradient"])
        self.assertEqual(sweep.scan_line("background: linear-gradient(red, blue)", m), [])
        self.assertEqual(sweep.scan_line("LINEAR-GRADIENT", m), [])
        self.assertEqual([h[0] for h in sweep.scan_line("linear-gradient and Linear", m)], ["name"])
        self.assertEqual([h[0] for h in sweep.scan_line("see linear-gradient.linear.app", m)],
                         ["name", "domain"])
        m = sweep.make_matchers(avoid=["Linear"], domains=["linear.app"], allow=["linear.app"])
        self.assertEqual(sweep.scan_line("https://linear.app/x", m),
                         [("domain", "linear.app", "linear.app")])  # the allow list never hides a domain

    def test_allow_entry_that_is_the_name_itself_is_refused(self):
        for word in ["Linear", "linear.", "LINEAR!", "Acuity-Scheduling"]:
            with self.subTest(word=word):
                with self.assertRaises(ValueError):
                    sweep.make_matchers(avoid=["Linear", "Acuity Scheduling"], allow=[word])


class BrandFile(Project):
    def test_cli_exit_codes_and_config(self):
        cfg = put(self.root, "brand.json", "\ufeff" + json.dumps({"avoid": ["Calendly"]}))  # a BOM is fine
        self.assertEqual(run(self.root, "--config", cfg)[0], 1)
        clean = tempfile.mkdtemp(dir=self.root)
        put(clean, "index.html", "<h1>Slotwise</h1>")
        code, out, _ = run(clean, "--avoid", "Calendly")
        self.assertEqual(code, 0)
        self.assertIn("PASS", out)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            cwd = os.getcwd()
            os.chdir(clean)  # no forge-work/brand.json here: nothing to look for
            try:
                code, _, err = run(clean)
            finally:
                os.chdir(cwd)
        self.assertEqual(code, 2)
        self.assertIn("there is no %s in " % os.path.join("forge-work", "brand.json"), err)
        self.assertIn("project root", err)

    def test_brand_file_itself_is_not_swept(self):
        cfg = put(self.root, "brand.json", json.dumps({"name": "Slotwise", "avoid": ["Slotwise"]}))
        code, out, _ = run(self.root, "--config", cfg, "--json")
        files = {f["file"] for f in json.loads(out)["findings"]}
        self.assertEqual(files, {os.path.join("src", "app", "page.tsx")})
        self.assertEqual(code, 1)

    def test_brand_file_is_not_swept_under_another_name(self):
        """macOS disks ignore case: --config BRAND.json opens brand.json, yet the two paths differ as text.
        A hard link is one file under two names on any disk, so it stands in for that here."""
        cfg = put(self.root, "brand.json", json.dumps({"name": "Slotwise", "avoid": ["Slotwise"]}))
        try:
            os.link(cfg, os.path.join(self.root, "brand-link.json"))
        except (OSError, AttributeError):
            self.skipTest("this file system has no hard links")
        code, out, _ = run(self.root, "--config", cfg, "--json")
        self.assertEqual({f["file"] for f in json.loads(out)["findings"]}, {os.path.join("src", "app", "page.tsx")})
        self.assertEqual(code, 1)

    def test_brand_file_spelled_in_other_case(self):
        """The real case, on the disks that ignore case (macOS and Windows; skipped elsewhere)."""
        put(self.root, "brand.json", json.dumps({"name": "Slotwise", "avoid": ["Slotwise"]}))
        if not os.path.exists(os.path.join(self.root, "BRAND.JSON")):
            self.skipTest("this disk tells BRAND.JSON from brand.json")
        code, out, _ = run(self.root, "--config", os.path.join(self.root, "BRAND.JSON"), "--json")
        self.assertEqual({f["file"] for f in json.loads(out)["findings"]}, {os.path.join("src", "app", "page.tsx")})
        self.assertEqual(code, 1)

    def test_old_palette_values_are_found_without_a_brand_file(self):
        """forge-design brand Step 3 looks for copies of the old token values before brand.json exists."""
        clean = tempfile.mkdtemp(dir=self.root)
        put(clean, "public/offline.css", ":root { --color-accent: #3F4856; }\n")
        put(clean, "public/icons/favicon.svg", '<svg><rect fill="#3f4856"/></svg>\n')
        put(clean, "public/manifest.webmanifest", '{"theme_color": "#3f4856", "background_color": "#f5f8fb"}\n')
        put(clean, "forge-work/design/tokens.json", '{"color": {"accent": "#3f4856"}}\n')
        code, out, _ = run(clean, "--colors", "#3f4856", "--json")
        found = {f["file"] for f in json.loads(out)["findings"]}
        self.assertEqual(found, {os.path.join("public", name) for name in
                                 ("offline.css", os.path.join("icons", "favicon.svg"), "manifest.webmanifest")})
        self.assertEqual(code, 1)

    def test_default_config_is_read_from_the_current_folder(self):
        put(self.root, "forge-work/brand.json", json.dumps(
            {"_about": "notes are fine", "name": "Slotwise", "avoid": ["Calendly"], "domains": [], "colors": []}))
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            code, out, _ = run(".")
            code_json, out_json, _ = run("--json", "--avoid", "Slotwise")
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 1)
        self.assertIn("(from %s)" % os.path.join("forge-work", "brand.json"), out)
        self.assertEqual(code_json, 1)
        self.assertEqual(json.loads(out_json)["summary"]["looked_for"], ["Calendly", "Slotwise"])

    def test_bad_input_exits_2(self):
        bad = {
            "invalid JSON": "{not json",
            "not an object": json.dumps(["Calendly"]),
            "a typo in a key": json.dumps({"avoid": ["Calendly"], "colours": ["#006bff"]}),
            "avoid is not a list": json.dumps({"avoid": "Calendly"}),
            "a number in a list": json.dumps({"avoid": ["Calendly", 3]}),
            "not a colour": json.dumps({"avoid": ["Calendly"], "colors": ["blue"]}),
            "nothing to look for": json.dumps({"name": "Slotwise", "avoid": [], "domains": [" "]}),
            "allow is the name": json.dumps({"avoid": ["Calendly"], "allow": ["calendly"]}),
            "allow is part of the name": json.dumps({"avoid": ["Acuity Scheduling"], "allow": ["acuity"]}),
            "allow is two words": json.dumps({"avoid": ["Calendly"], "allow": ["the Calendly"]}),
            "not a domain": json.dumps({"avoid": ["Calendly"], "domains": ["calendly"]}),
            "a name too short": json.dumps({"avoid": ["Cal", "a"]}),
            "nested too deep": '{"avoid": ' + "[" * 100000 + "]" * 100000 + "}",
        }
        for problem, text in bad.items():
            with self.subTest(problem=problem):
                cfg = put(self.root, "forge-work/bad.json", text)
                code, out, err = run(self.root, "--config", cfg)
                self.assertEqual(code, 2)
                self.assertIn("error:", err)
                self.assertEqual(out, "")
        self.assertEqual(run(self.root, "--config", os.path.join(self.root, "missing.json"))[0], 2)
        self.assertEqual(run(os.path.join(self.root, "missing"), "--avoid", "Calendly")[0], 2)
        self.assertEqual(run(self.root, "--colors", "#12345")[0], 2)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                sweep.main([self.root, "--fail-on", "low"])  # not an option: every leftover counts
        self.assertEqual(raised.exception.code, 2)


class Output(Project):
    def test_json_shape(self):
        code, out, _ = run(self.root, "--avoid", "Calendly", "--colors", "#006bff", "--json")
        data = json.loads(out)
        self.assertEqual(code, 1)
        for finding in data["findings"]:
            for key in ("severity", "title", "where", "why", "fix", "kind", "label", "match", "file", "line"):
                self.assertIn(key, finding)
            self.assertEqual(finding["severity"], "high")
        summary = data["summary"]
        self.assertEqual(summary["total"], len(data["findings"]))
        self.assertTrue(summary["failed"])
        self.assertEqual(summary["unreadable"], [])
        self.assertEqual(summary["incomplete"], [])
        self.assertEqual(summary["allowed"], [])
        self.assertEqual(summary["allow_words"], [])
        self.assertEqual(summary["looked_for"], ["Calendly", "#006bff"])

    def test_human_output_groups_the_places(self):
        code, out, _ = run(self.root, "--avoid", "Calendly")
        self.assertEqual(code, 1)
        self.assertIn("HIGH      A name to avoid: Calendly (2 places)", out)
        self.assertIn("where: " + os.path.join("src", "lib", "copy.ts") + ":1", out)
        self.assertIn("FAIL:", out)

    def test_the_line_itself_is_never_printed(self):
        key = "sk_" + "live_" + "a" * 24  # built at runtime: the repo holds no secret-looking text
        put(self.root, ".env", "CALENDLY_SECRET=%s\n" % key)
        for extra in ([], ["--json"]):
            code, out, err = run(self.root, "--avoid", "Calendly", *extra)
            self.assertEqual(code, 1)
            self.assertIn(".env:1", out)
            self.assertNotIn(key, out + err)
            self.assertNotIn("aaaaaaaa", out + err)

    def test_unreadable_file_is_an_incomplete_sweep(self):
        def fail_on_copy(path, *args, **kwargs):
            if str(path).endswith("copy.ts"):
                raise PermissionError(13, "Permission denied", path)
            return open(path, *args, **kwargs)

        sweep.open = fail_on_copy  # the module's own open() now; the built-in one stays as it is
        try:
            code, out, _ = run(self.root, "--avoid", "Calendly")
        finally:
            del sweep.open
        self.assertEqual(code, 2)
        self.assertIn("INCOMPLETE", out)
        self.assertIn(os.path.join("src", "lib", "copy.ts"), out)

    def test_one_file(self):
        path = os.path.join(self.root, "src", "lib", "copy.ts")
        self.assertEqual(run(path, "--avoid", "Calendly")[0], 1)
        self.assertEqual(run(os.path.join(self.root, "src", "app", "page.tsx"), "--avoid", "Calendly")[0], 0)

    def test_command_line(self):
        done = subprocess.run([sys.executable, SCRIPT, ".", "--avoid", "Calendly", "--json"], cwd=self.root,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertTrue(json.loads(done.stdout)["findings"])

    def test_a_reader_that_stops_early_is_no_crash(self):
        """`sweep.py . | head`: a report bigger than the pipe holds meets a closed pipe. No traceback, same exit."""
        for number in range(400):
            put(self.root, "src/pages/page%d.ts" % number, "// calendly\n" * 5)
        done = subprocess.Popen([sys.executable, SCRIPT, ".", "--avoid", "Calendly"], cwd=self.root,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        done.stdout.read(200)
        done.stdout.close()  # what head does once it has its lines
        err = done.stderr.read().decode("utf-8", "replace")
        done.stderr.close()
        self.assertEqual(done.wait(timeout=120), 1, err)
        self.assertNotIn("Traceback", err)


class ReviewMatching(unittest.TestCase):
    """Regression tests for what was matched, or not, before the review fixes."""

    def hits(self, line, **lists):
        return [hit[:2] for hit in sweep.scan_line(line, sweep.make_matchers(**lists))]

    def test_a_domain_matches_only_as_a_whole_host(self):
        for line in ["local.commit();", "typical.compute()", "historical.compare(a, b)", "x.cal.coma"]:
            with self.subTest(line=line):
                self.assertEqual(self.hits(line, domains=["cal.com"]), [])
        self.assertEqual(self.hits('import Box from "./index.component";', domains=["x.com"]), [])
        self.assertEqual(self.hits("see mycalendly.com", domains=["calendly.com"]), [])
        for line in ["https://help.calendly.com/x", "CALENDLY.COM", "mail@calendly.com", "(calendly.com)"]:
            with self.subTest(line=line):
                self.assertEqual(self.hits(line, domains=["calendly.com"]), [("domain", "calendly.com")])

    def test_domain_entries_are_cleaned(self):
        for entry in ["*.calendly.com", "calendly.com.", ".calendly.com", "calendly.com:443", "//calendly.com",
                      "https://calendly.com:443/", "https://user@www.Calendly.com:8443/x?y#z", " CALENDLY.com "]:
            with self.subTest(entry=entry):
                self.assertEqual(sweep.clean_domain(entry), "calendly.com")
                self.assertEqual(self.hits('fetch("https://api.calendly.com/v2")', domains=[entry]),
                                 [("domain", "calendly.com")])

    def test_entries_that_are_not_domains_are_refused(self):
        for entry in ["calendly", "localhost", "https://", "*", "cal endly.com", "[::1]"]:
            with self.subTest(entry=entry):
                with self.assertRaises(ValueError):
                    sweep.make_matchers(avoid=["Slotwise"], domains=[entry])

    def test_allow_words_that_would_hide_leftovers_are_refused(self):
        cases = [("Acuity Scheduling", "acuity"), ("Linear", "linea"), ("Calendly", "the Calendly"),
                 ("Calendly", "Calendly's"), ("Calendly", "Calendly app"), ("Calendly", "Calendly!")]
        for name, word in cases:
            with self.subTest(word=word):
                with self.assertRaises(ValueError):
                    sweep.make_matchers(avoid=[name], allow=[word])
        m = sweep.make_matchers(avoid=["Cal.com"], allow=["local.commit"])
        self.assertEqual(sweep.scan_line("local.commit()", m), [])
        self.assertEqual([h[0] for h in sweep.scan_line("local.commit() on Cal.com", m)], ["name"])

    def test_allow_words_are_shown(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        put(root, "a.css", "background: linear-gradient(red, blue)\n")
        code, out, _ = run(root, "--config", put(root, "b.json", json.dumps({"avoid": ["Linear"],
                                                                          "allow": ["linear-gradient"]})))
        self.assertEqual(code, 0)
        self.assertIn("Allowed words, check each is fine: linear-gradient", out)

    def test_a_dotted_name_also_matches_joined(self):
        for line in ['import Cal from "@calcom/embed-react";', "export function CalComEmbed() {}", "cal-com",
                     "Book on Cal.com"]:
            with self.subTest(line=line):
                self.assertEqual(self.hits(line, avoid=["Cal.com"]), [("name", "Cal.com")])
        self.assertEqual(self.hits("Calendly Inc", avoid=["Calendly Inc."]), [("name", "Calendly Inc.")])

    def test_names_shorter_than_three_letters_are_refused(self):
        for name in ["a", "X", "a-b", "1."]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    sweep.make_matchers(avoid=[name])

    def test_repeats_are_dropped(self):
        m = sweep.make_matchers(avoid=["Calendly", "calendly", " Calendly "],
                                domains=["calendly.com", "https://www.calendly.com", "CALENDLY.COM/x"])
        self.assertEqual(m["looked_for"], ["Calendly", "calendly.com"])
        self.assertEqual(len(sweep.scan_line('"https://calendly.com/help"', m)), 2)  # one name, one domain

    def test_entities_and_ids_are_not_colours(self):
        line = "<footer>&#169; 2026 &middot; it&#039;s yours</footer> #add-to-cart { margin: 0 }"
        self.assertEqual(self.hits(line, colors=["#116699", "#003399", "#aadddd"]), [])
        self.assertEqual(self.hits("a{border:1px solid#006bff}", colors=["#006bff"]), [("color", "#006bff")])

    def test_tailwind_rgb_with_underscores(self):
        line = '<button className="bg-[rgb(0_107_255)] text-white">'
        self.assertEqual(self.hits(line, colors=["#006bff"]), [("color", "#006bff")])


class ReviewSweep(Project):
    """Regression tests for what was skipped or passed before the review fixes."""

    def test_vendor_and_build_folders_are_only_skipped_at_the_top(self):
        shipped = ["resources/views/vendor/mail/html/header.blade.php", "lang/vendor/x/en.php",
                   "app/build/page.tsx", "app/coverage/page.tsx", "app/out/page.tsx", "src/dist/x.ts",
                   "app/storage/framework/x.php"]
        tooling = ["dist/x.js", "build/x.js", "out/x.js", "coverage/x.html", ".next/x.js", "src/.next/x.js",
                   ".venv/x.py", "src/node_modules/x.js", "src/__pycache__/x.py", "src/.git/x"]
        for rel in shipped + tooling:
            put(self.root, rel, "<a href='https://calendly.com'>Calendly</a>\n")
        files = {f["file"] for f in self.findings()}
        for rel in shipped:
            self.assertIn(os.path.join(*rel.split("/")), files)
        for rel in tooling:
            self.assertNotIn(os.path.join(*rel.split("/")), files)

    def test_nothing_checked_is_not_a_pass(self):
        empty = tempfile.mkdtemp(dir=self.root)
        code, out, _ = run(empty, "--avoid", "Calendly")
        self.assertEqual(code, 2)
        self.assertIn("INCOMPLETE", out)
        self.assertNotIn("PASS", out)
        put(empty, "logo.png", b"\x89PNG\0", binary=True)  # only a binary file: still nothing read
        self.assertEqual(run(empty, "--avoid", "Calendly")[0], 2)

    def test_big_text_files_are_read(self):
        put(self.root, "database/seed.json", "x" * (2 * 1024 * 1024) + "\n{\"vendor\": \"Calendly\"}\n")
        where = {f["where"] for f in self.findings()}
        self.assertIn(os.path.join("database", "seed.json") + ":2", where)

    def test_unreadable_folder_is_an_incomplete_sweep(self):
        real = os.scandir

        def fail_on_lib(path):
            if str(path).endswith("lib"):
                raise PermissionError(13, "Permission denied", path)
            return real(path)

        sweep.os.scandir = fail_on_lib
        try:
            code, out, _ = run(self.root, "--avoid", "Calendly", "--json")
        finally:
            sweep.os.scandir = real
        summary = json.loads(out)["summary"]
        self.assertEqual(code, 2)
        self.assertEqual(summary["unreadable"], [os.path.join("src", "lib")])
        self.assertTrue(summary["failed"])

    def test_output_survives_an_ascii_pipe_and_odd_file_names(self):
        put(self.root, "docs/日本-calendly.md", "Calendly\n")
        try:  # a file name that is not UTF-8, where the file system allows it
            put(os.fsencode(self.root).decode("utf-8", "surrogateescape"), "docs/caf\udce9.txt", "Calendly\n")
        except (OSError, UnicodeError):
            pass
        env = dict(os.environ, PYTHONIOENCODING="ascii")
        for extra in ([], ["--json"]):
            done = subprocess.run([sys.executable, SCRIPT, ".", "--avoid", "Calendly"] + extra, cwd=self.root,
                                  env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            self.assertEqual(done.returncode, 1, done.stderr)
            self.assertNotIn(b"Traceback", done.stderr)
            self.assertIn(b"\\u65e5\\u672c-calendly.md", done.stdout)


class ReviewDogfood(Project):
    """Regression tests for what real runs of the pack hit."""

    def test_tool_written_caches_are_not_read(self):
        cache = '{"program":{"fileNames":["./node_modules/next/dist/vercel/x.d.ts"]}}'  # from tsc --noEmit
        for rel in ["tsconfig.tsbuildinfo", "packages/web/app.tsbuildinfo", "next-env.d.ts", ".eslintcache",
                    ".phpunit.result.cache"]:
            put(self.root, rel, cache + "\n")
        put(self.root, "src/vercel.tsbuildinfo", "{}\n")  # its name is still checked
        put(self.root, "src/deploy.ts", "// deploy to Vercel\n")
        findings = sweep.sweep(self.root, sweep.make_matchers(avoid=["Vercel"]))[0]
        expected = {("name", os.path.join("src", "deploy.ts")), ("path", os.path.join("src", "vercel.tsbuildinfo"))}
        self.assertEqual({(f["kind"], f["file"]) for f in findings}, expected)

    def test_the_report_does_not_assume_an_original(self):
        clean = tempfile.mkdtemp(dir=self.root)  # idea mode: an old working name, no original app
        put(clean, "index.html", "<title>Kapsalon</title><a href='https://kapsalon.example'>x</a> #006bff\n")
        code, out, _ = run(clean, "--avoid", "Kapsalon", "--domains", "kapsalon.example", "--colors", "#006bff")
        self.assertEqual(code, 1)
        self.assertIn("A name to avoid: Kapsalon", out)
        self.assertIn("A domain to avoid: kapsalon.example", out)
        self.assertIn("A brand colour to avoid: #006bff", out)
        self.assertNotIn("original", out.lower())
        put(clean, "index.html", "<title>Knipkamer</title>\n")
        code, out, _ = run(clean, "--avoid", "Kapsalon")
        self.assertEqual(code, 0)
        self.assertNotIn("original", out.lower())


if __name__ == "__main__":
    unittest.main()
