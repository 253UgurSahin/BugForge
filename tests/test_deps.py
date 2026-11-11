"""Tests for forge-check/deps.py.

The real auditors (npm, composer, pip-audit) are never run here. The parsers get canned JSON,
the CLI tests swap deps.run_tool for a fake, and the run_tool tests put small fake auditors
(Python scripts) first on PATH, so nothing touches the network. On Windows each fake is reached
through a .cmd file, as npm.cmd is there: shutil.which() finds that, and cmd.exe runs it.
"""

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import signal
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import load, run_cp1252, symlink  # noqa: E402

mod = load("forge-check", "deps")

NPM_REPORT = json.dumps({
    "auditReportVersion": 2,
    "vulnerabilities": {
        "lodash": {
            "name": "lodash", "severity": "high", "fixAvailable": True,
            "via": [{"title": "Prototype Pollution in lodash", "severity": "high",
                     "url": "https://github.com/advisories/GHSA-aaaa-bbbb-cccc"},
                    {"title": "Prototype Pollution in lodash", "severity": "high",
                     "url": "https://github.com/advisories/GHSA-aaaa-bbbb-cccc"},
                    {"title": "Command Injection in lodash.", "severity": "high",
                     "url": "https://github.com/advisories/GHSA-dddd-eeee-ffff"}]},
        "minimist": {  # two advisories with one title, as npm really reports minimist 0.0.8
            "name": "minimist", "severity": "critical",
            "fixAvailable": {"name": "minimist", "version": "1.2.8", "isSemVerMajor": False},
            "via": [{"title": "Prototype Pollution in minimist", "severity": "moderate",
                     "url": "https://github.com/advisories/GHSA-vh95-rmgr-6w4m"},
                    {"title": "Prototype Pollution in minimist", "severity": "critical",
                     "url": "https://github.com/advisories/GHSA-xvch-5gv4-984h"}]},
        "react-scripts": {  # only listed because it uses nth-check and postcss
            "name": "react-scripts", "severity": "moderate", "via": ["nth-check", "postcss"],
            "fixAvailable": {"name": "react-scripts", "version": "5.0.1", "isSemVerMajor": True}},
        "nth-check": {
            "name": "nth-check", "severity": "moderate", "via": [
                {"title": "Inefficient Regular Expression in nth-check", "url": None}],
            "fixAvailable": {"name": "react-scripts", "version": "5.0.1", "isSemVerMajor": True}},
        "left-pad": {"name": "left-pad", "severity": "low", "fixAvailable": False,
                     "via": [{"title": "Slow left-pad", "severity": "low"}]},
        "debug": {"name": "debug", "severity": "info", "fixAvailable": True,
                  "via": [{"title": "Slow debug output"}]},
    },
})

# Dogfood (idea-next-pwa): npm's semver-major "fix" for esbuild was drizzle-kit 0.18.1, two years
# older than the 0.31.11 in use, and drizzle-kit is a dev tool only.
DRIZZLE_REPORT = json.dumps({"vulnerabilities": {
    "esbuild": {"name": "esbuild", "severity": "moderate", "isDirect": False,
                "via": [{"title": "esbuild lets any website read the dev server", "severity": "moderate",
                         "url": "https://github.com/advisories/GHSA-67mh-4wv8-2f99"}],
                "nodes": ["node_modules/esbuild", "node_modules/@esbuild-kit/core-utils/node_modules/esbuild"],
                "fixAvailable": {"name": "drizzle-kit", "version": "0.18.1", "isSemVerMajor": True}},
    "next": {"name": "next", "severity": "high", "isDirect": True, "nodes": ["node_modules/next"],
             "via": [{"title": "Next.js cache poisoning", "severity": "high", "url": "https://x.test/1"}],
             "fixAvailable": {"name": "next", "version": "16.0.1", "isSemVerMajor": True}},
}})
DRIZZLE_LOCK = {"lockfileVersion": 3, "packages": {
    "": {"dependencies": {"next": "^15.5.0"}, "devDependencies": {"drizzle-kit": "^0.31.11"}},
    "node_modules/drizzle-kit": {"version": "0.31.11", "dev": True},
    "node_modules/esbuild": {"version": "0.25.4", "dev": True},
    "node_modules/@esbuild-kit/core-utils/node_modules/esbuild": {"version": "0.18.20", "dev": True},
    "node_modules/next": {"version": "15.5.0"},
}}

COMPOSER_REPORT = json.dumps({
    "advisories": {
        "guzzlehttp/psr7": [
            {"title": "CRLF injection in headers", "cve": "CVE-2026-0001", "severity": "medium",
             "link": "https://github.com/advisories/GHSA-1111-2222-3333"},
            {"title": "Host confusion", "cve": "CVE-2026-0002", "severity": "high",
             "link": "https://github.com/advisories/GHSA-4444-5555-6666"}],
        "symfony/http-kernel": {  # PHP prints a list with gaps as an object, as Composer 2.8 does
            "1": {"title": None, "cve": "CVE-2022-24894", "severity": None,
                  "link": "https://symfony.com/cve-2022-24894"}},
    },
    "abandoned": [],
})

PIP_REPORT = json.dumps({
    "dependencies": [
        {"name": "flask", "version": "0.5", "vulns": [
            {"id": "PYSEC-2019-179", "aliases": ["CVE-2019-1010083"], "fix_versions": ["1.0"],
             "description": "Flask before 1.0 is affected by unexpected memory usage."},
            {"id": "PYSEC-2018-66", "aliases": [], "fix_versions": ["0.12.3", "1.0"],
             "description": "Flask before 0.12.3 has a denial of service via crafted JSON."}]},
        {"name": "click", "version": "8.1.7", "vulns": []},
        {"name": "oldlib", "version": "1.0", "vulns": [{"id": "GHSA-zzzz-yyyy-xxxx"}]},
        {"name": "private-pkg", "skip_reason": "Dependency not found on PyPI"},
    ],
    "fixes": [],
})

FAKE_AUDITOR = """#!%s
# A stand-in for npm, composer or pip-audit: it logs what it saw and prints a canned report.
import json, os, subprocess, sys, time
files = sorted(os.listdir("."))
composer_json = open("composer.json", encoding="utf-8").read() if "composer.json" in files else None
child = None
if os.environ.get("FORGE_FAKE_HANG"):  # hangs, with a child of its own (as npm.cmd runs node.exe)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"]).pid
with open(os.environ["FORGE_FAKE_LOG"], "a") as log:
    log.write(json.dumps({"tool": os.path.splitext(os.path.basename(sys.argv[0]))[0], "cwd": os.getcwd(),
                          "files": files, "args": sys.argv[1:], "composer_json": composer_json,
                          "child": child}) + "\\n")
if child:
    time.sleep(60)
sys.stdout.write(os.environ.get("FORGE_FAKE_OUT", ""))
sys.stderr.write(os.environ.get("FORGE_FAKE_ERR", ""))
sys.exit(1)  # npm audit exits 1 when it finds something: never an error for deps.py
"""
# On Windows a fake runs through a .cmd file, the way npm.cmd runs npm; %~dp0 is the .cmd file's folder.
# Python's path comes from the environment: cmd.exe reads a .cmd file in another code page than Python writes.
FAKE_CMD = '@echo off\n"%%FORGE_FAKE_PYTHON%%" "%%~dp0..\\fakes\\%s.py" %%*\n'  # text mode: CRLF there


def write(folder, relative_path, content="{}"):
    path = os.path.join(folder, relative_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(content)
    return path


def run(*args):
    """Run main() and return (exit code, stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = mod.main(list(args))
    return code, out.getvalue()


def by_package(parsed):
    findings, skipped = parsed
    return {f["package"]: f for f in findings}


class ParseNpmTests(unittest.TestCase):
    def setUp(self):
        self.found = by_package(mod.parse_npm(NPM_REPORT))

    def test_one_finding_per_vulnerable_package(self):
        self.assertEqual(sorted(self.found), ["debug", "left-pad", "lodash", "minimist", "nth-check"])

    def test_package_that_only_uses_a_vulnerable_one_gets_no_finding(self):
        self.assertNotIn("react-scripts", self.found)  # no false "known vulnerability in ..."
        report = json.dumps({"vulnerabilities": {"foo": {
            "severity": "high", "via": [{"title": "ReDoS in foo"}, "bar"]}}})
        self.assertEqual(mod.parse_npm(report)[0][0]["title"],
                         'Known vulnerability in npm package "foo"')  # "bar" is not counted

    def test_severity_mapping(self):
        severities = {name: f["severity"] for name, f in self.found.items()}
        self.assertEqual(severities, {"lodash": "high", "minimist": "critical",
                                      "nth-check": "medium", "left-pad": "low", "debug": "low"})

    def test_unknown_severity_counts_as_high_and_empty_via_reads_well(self):
        report = json.dumps({"vulnerabilities": {"x": {"severity": "weird", "via": []}}})
        finding = mod.parse_npm(report)[0][0]
        self.assertEqual(finding["severity"], "high")
        self.assertEqual(finding["title"], 'Known vulnerability in npm package "x"')
        self.assertEqual(finding["holes"], "unnamed advisory")

    def test_advisories_with_one_title_count_separately(self):
        minimist = self.found["minimist"]
        self.assertEqual(minimist["title"], '2 known vulnerabilities in npm package "minimist"')
        self.assertEqual(minimist["holes"], "Prototype Pollution in minimist")  # shown once
        self.assertEqual(minimist["links"], ["https://github.com/advisories/GHSA-xvch-5gv4-984h",
                                             "https://github.com/advisories/GHSA-vh95-rmgr-6w4m"])

    def test_repeated_advisory_is_listed_once(self):
        lodash = self.found["lodash"]
        self.assertEqual(lodash["title"], '2 known vulnerabilities in npm package "lodash"')
        self.assertEqual(lodash["holes"], "Prototype Pollution in lodash; Command Injection in lodash")

    def test_why_is_plain_and_punctuation_does_not_double(self):
        why = self.found["lodash"]["why"]
        self.assertEqual(why, 'this app uses a version of "lodash" with publicly known security '
                              "holes; attackers look for these")
        self.assertNotIn("..", self.found["lodash"]["holes"])

    def test_fix_advice(self):
        self.assertIn('"npm audit fix"', self.found["lodash"]["fix"])
        self.assertIn('"npm audit fix"', self.found["minimist"]["fix"])  # not a major update
        nth = self.found["nth-check"]["fix"]
        self.assertIn("update react-scripts to 5.0.1 in package.json", nth)
        self.assertIn("new major version", nth)
        self.assertNotIn("--force", nth)
        self.assertIn("no fixed version of left-pad", self.found["left-pad"]["fix"])

    def test_a_major_fix_that_is_a_downgrade_says_so(self):
        found = by_package(mod.parse_npm(DRIZZLE_REPORT, DRIZZLE_LOCK))
        fix = found["esbuild"]["fix"]
        self.assertIn("older version of drizzle-kit (0.18.1, you have 0.31.11)", fix)
        self.assertIn('do not run "npm audit fix --force"', fix)
        self.assertNotIn("update drizzle-kit", fix)
        self.assertIn("update next to 16.0.1 in package.json", found["next"]["fix"])  # a real upgrade

    def test_a_package_only_dev_tools_use_says_so(self):
        found = by_package(mod.parse_npm(DRIZZLE_REPORT, DRIZZLE_LOCK))
        self.assertTrue(found["esbuild"]["why"].endswith("so it does not run in the production app"))
        self.assertNotIn("dev tools", found["next"]["why"])
        self.assertEqual(found["esbuild"]["severity"], "medium")  # the note never lowers a severity

    def test_without_a_lockfile_the_advice_is_the_plain_one(self):
        for lock in [None, {}, [], {"packages": "odd"}]:
            found = by_package(mod.parse_npm(DRIZZLE_REPORT, lock))
            self.assertIn("update drizzle-kit to 0.18.1", found["esbuild"]["fix"])
            self.assertNotIn("dev tools", found["esbuild"]["why"])

    def test_version_key(self):
        self.assertLess(mod.version_key("0.18.1"), mod.version_key("0.31.11"))
        self.assertLess(mod.version_key("1.9.0"), mod.version_key("1.10.0"))

    def test_holes_line_shows_three_and_json_keeps_all(self):
        via = [{"title": "Problem %d." % n, "url": "https://x.test/%d" % n} for n in range(5)]
        report = json.dumps({"vulnerabilities": {"pkg": {"severity": "high", "via": via}}})
        finding = mod.parse_npm(report)[0][0]
        self.assertEqual(finding["title"], '5 known vulnerabilities in npm package "pkg"')
        self.assertEqual(finding["holes"], "Problem 0; Problem 1; Problem 2")
        self.assertEqual(len(finding["advisories"]), 5)
        self.assertEqual(len(finding["links"]), 5)

    def test_long_titles_are_shortened(self):
        report = json.dumps({"vulnerabilities": {"pkg": {"severity": "high", "via": [
            {"title": "word " * 50 + "end."}]}}})
        self.assertLessEqual(len(mod.parse_npm(report)[0][0]["advisories"][0]), 100)

    def test_clean_report(self):
        self.assertEqual(mod.parse_npm('{"auditReportVersion": 2, "vulnerabilities": {}}'), ([], []))

    def test_npm_error_says_why(self):
        old = json.dumps({"error": {"code": "ENOLOCK", "summary": "This command needs a lockfile"}})
        with self.assertRaisesRegex(ValueError, "needs a lockfile"):
            mod.parse_npm(old)
        npm10 = json.dumps({"message": "request to https://x failed, reason: ECONNREFUSED",
                            "error": {"summary": "", "detail": ""}})
        with self.assertRaisesRegex(ValueError, "ECONNREFUSED"):
            mod.parse_npm(npm10)
        with self.assertRaisesRegex(ValueError, "npm 7 or newer"):
            mod.parse_npm('{"auditReportVersion": 1, "advisories": {}}')  # npm 6

    def test_bad_output_is_always_a_value_error(self):
        for text in ["", "npm WARN something", "[1, 2]", '{"error": "boom"}', '"text"']:
            with self.assertRaises(ValueError, msg=text):
                mod.parse_npm(text)


class ParseComposerTests(unittest.TestCase):
    def setUp(self):
        self.found = by_package(mod.parse_composer(COMPOSER_REPORT))

    def test_worst_severity_per_package(self):
        guzzle = self.found["guzzlehttp/psr7"]
        self.assertEqual(guzzle["severity"], "high")
        self.assertEqual(guzzle["title"],
                         '2 known vulnerabilities in Composer package "guzzlehttp/psr7"')
        self.assertIn('"composer update guzzlehttp/psr7"', guzzle["fix"])
        self.assertEqual(guzzle["links"][0], "https://github.com/advisories/GHSA-4444-5555-6666")

    def test_advisories_printed_as_an_object(self):
        report = json.dumps({"advisories": {"symfony/http-kernel": {
            "1": {"title": "Prevent RCE", "severity": "high"},
            "3": {"title": "Cookie issue", "severity": "medium"}}}})
        [finding], skipped = mod.parse_composer(report)
        self.assertEqual((finding["severity"], finding["advisories"], skipped),
                         ("high", ["Prevent RCE", "Cookie issue"], []))

    def test_missing_severity_is_high_and_cve_stands_in_for_title(self):
        kernel = self.found["symfony/http-kernel"]
        self.assertEqual(kernel["severity"], "high")
        self.assertEqual(kernel["advisories"], ["CVE-2022-24894"])

    def test_severity_words(self):
        for word, expected in [("critical", "critical"), ("high", "high"), ("medium", "medium"),
                               ("moderate", "medium"), ("low", "low"), ("odd", "high")]:
            report = json.dumps({"advisories": {"a/b": [{"title": "t", "severity": word}]}})
            self.assertEqual(mod.parse_composer(report)[0][0]["severity"], expected, word)

    def test_nothing_found_is_an_empty_list_in_php(self):
        self.assertEqual(mod.parse_composer('{"advisories": [], "abandoned": []}'), ([], []))

    def test_bad_output(self):
        for text in ["", "No packages - skipping audit.", '{"other": 1}', "[]"]:
            with self.assertRaises(ValueError, msg=text):
                mod.parse_composer(text)


class ParsePipAuditTests(unittest.TestCase):
    def setUp(self):
        self.findings, self.skipped = mod.parse_pip_audit(PIP_REPORT)
        self.found = {f["package"]: f for f in self.findings}

    def test_only_vulnerable_packages_all_high(self):
        self.assertEqual(sorted(self.found), ["flask", "oldlib"])
        self.assertEqual({f["severity"] for f in self.findings}, {"high"})

    def test_flask_finding(self):
        flask = self.found["flask"]
        self.assertEqual(flask["title"], '2 known vulnerabilities in pip package "flask" 0.5')
        self.assertTrue(flask["holes"].startswith("PYSEC-2019-179: Flask before 1.0 is affected"))
        self.assertEqual(flask["links"][0], "https://osv.dev/vulnerability/PYSEC-2019-179")

    def test_fix_says_latest_version_and_lists_fixes_in_order(self):
        fix = self.found["flask"]["fix"]
        self.assertIn("upgrade flask to its latest version", fix)
        self.assertIn("fixes came out in 0.12.3, 1.0)", fix)  # sorted, each once
        vulns = [{"id": "A", "fix_versions": ["10.0", "2.3.2"]}, {"id": "B", "fix_versions":
                 ["9.1", "0.12.3", "2.2.5", "2.3.2"]}]
        report = json.dumps({"dependencies": [{"name": "x", "version": "0", "vulns": vulns}]})
        self.assertIn("fixes came out in 0.12.3, 2.2.5, 2.3.2, 9.1, 10.0)",  # as numbers
                      mod.parse_pip_audit(report)[0][0]["fix"])

    def test_no_fix_version(self):
        oldlib = self.found["oldlib"]
        self.assertIn("no fixed version of oldlib", oldlib["fix"])
        self.assertEqual(oldlib["advisories"], ["GHSA-zzzz-yyyy-xxxx: no description"])

    def test_one_advisory_listed_twice_counts_once(self):
        vulns = [{"id": "PYSEC-1", "description": "Text from one source."},
                 {"id": "PYSEC-1", "description": "Text from another source."},
                 {"id": "PYSEC-2", "description": "Other hole."}]
        report = json.dumps({"dependencies": [{"name": "x", "version": "1", "vulns": vulns}]})
        finding = mod.parse_pip_audit(report)[0][0]
        self.assertEqual(finding["title"], '2 known vulnerabilities in pip package "x" 1')
        self.assertEqual(finding["links"], ["https://osv.dev/vulnerability/PYSEC-1",
                                            "https://osv.dev/vulnerability/PYSEC-2"])

    def test_skipped_packages_are_reported(self):
        self.assertEqual(self.skipped,
                         ["pip-audit could not check private-pkg: Dependency not found on PyPI"])

    def test_old_list_format_and_long_description(self):
        report = json.dumps([{"name": "a", "version": "1", "vulns": [
            {"id": "PYSEC-1", "description": "word " * 100}]}])  # old pip-audit: a plain list
        problem = mod.parse_pip_audit(report)[0][0]["advisories"][0]
        self.assertLessEqual(len(problem), 100)
        self.assertTrue(problem.endswith("..."))

    def test_clean_report(self):
        self.assertEqual(mod.parse_pip_audit('{"dependencies": [], "fixes": []}'), ([], []))

    def test_bad_output(self):
        for text in ["", "ERROR: no such file", '{"fixes": []}', '"text"']:
            with self.assertRaises(ValueError, msg=text):
                mod.parse_pip_audit(text)


class PlanTests(unittest.TestCase):
    def plan(self, *names, folder="app"):
        return [(job["file"], job.get("cmd"), job.get("copy"), job.get("note"))
                for job in mod.plan_checks(folder, list(names))]

    def test_npm_runs_once_on_copies_and_uses_the_public_registry(self):
        [(name, cmd, copy, _)] = self.plan("npm-shrinkwrap.json", "package-lock.json",
                                           "package.json", ".npmrc")
        self.assertEqual(name, "npm-shrinkwrap.json")
        self.assertEqual(cmd, ["npm", "audit", "--json", "--registry=https://registry.npmjs.org/"])
        self.assertEqual(copy, ["npm-shrinkwrap.json", "package.json"])  # never .npmrc
        self.assertEqual(mod.plan_checks(".", ["package-lock.json"])[0]["parse"], mod.parse_npm)

    def test_composer_never_runs_project_code_or_settings(self):
        [(name, cmd, copy, _)] = self.plan("composer.json", "composer.lock", "auth.json")
        self.assertEqual((name, copy), ("composer.lock", ["composer.lock"]))
        self.assertEqual(cmd[:4], ["composer", "audit", "--format=json", "--locked"])
        self.assertIn("--no-plugins", cmd)
        self.assertIn("--no-scripts", cmd)

    def test_pip_audit_installs_nothing(self):
        plan = self.plan("pyproject.toml", "requirements-dev.txt", "requirements.txt", "setup.py")
        self.assertEqual([name for name, _, _, _ in plan],
                         ["requirements-dev.txt", "requirements.txt"])  # and no export note
        cmd, copy = plan[1][1], plan[1][2]
        self.assertEqual(cmd[:6], ["pip-audit", "--no-deps", "--disable-pip", "-f", "json", "-r"])
        self.assertEqual(cmd[6], os.path.abspath(os.path.join("app", "requirements.txt")))
        self.assertEqual(copy, [])

    def test_requirements_folder(self):
        plan = self.plan("base.txt", "prod.txt", "README.md", folder=os.path.join("x", "requirements"))
        self.assertEqual([name for name, _, _, _ in plan], ["base.txt", "prod.txt"])
        self.assertEqual(self.plan("base.txt", folder="docs"), [])

    def test_python_without_requirements_gets_one_export_note(self):
        [(name, cmd, _, note)] = self.plan("poetry.lock", "pyproject.toml")
        self.assertEqual((name, cmd), ("poetry.lock", None))
        self.assertIn("poetry export -f requirements.txt", note)
        self.assertIn("pipenv requirements", self.plan("Pipfile", "Pipfile.lock")[0][3])
        self.assertIn("pip-compile", self.plan("pyproject.toml")[0][3])

    def test_yarn_pnpm_and_bun_only_get_a_note(self):
        plan = self.plan("pnpm-lock.yaml", "yarn.lock", "bun.lock")
        self.assertEqual([(name, cmd) for name, cmd, _, _ in plan],
                         [("pnpm-lock.yaml", None), ("yarn.lock", None), ("bun.lock", None)])
        self.assertIn('"pnpm audit"', plan[0][3])
        self.assertIn('"yarn npm audit"', plan[1][3])
        self.assertIn('"bun audit"', plan[2][3])
        self.assertIn('"bun audit"', self.plan("bun.lockb")[0][3])  # a lockfile: never "create its lockfile first"

    def test_other_files_are_ignored(self):
        self.assertEqual(self.plan("index.php", "package.json", "composer.json", "README.md"), [])


class RunToolTests(unittest.TestCase):
    def test_missing_tool_gives_none(self):
        self.assertIsNone(mod.run_tool(["forge-no-such-auditor-xyz", "--json"], ".", []))

    def test_a_program_in_the_current_folder_is_never_run(self):
        planted = os.path.join(os.getcwd(), "npm")
        with mock.patch.object(mod.shutil, "which", return_value=planted), \
                mock.patch.object(mod.subprocess, "run") as fake_run:
            self.assertIsNone(mod.run_tool(["npm", "audit"], ".", []))
        fake_run.assert_not_called()

    def test_timeout_and_no_input(self):
        with mock.patch.object(mod.subprocess, "Popen") as fake_popen:
            process = fake_popen.return_value.__enter__.return_value
            process.communicate.return_value = ("out", "err")
            self.assertEqual(mod.run_tool([sys.executable, "-V"], ".", []), ("out", "err"))
        kwargs = fake_popen.call_args[1]
        self.assertEqual(process.communicate.call_args[1]["timeout"], mod.TIMEOUT)
        self.assertEqual(mod.TIMEOUT, 180)
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertNotIn("shell", kwargs)
        self.assertEqual(kwargs["env"]["PYTHONIOENCODING"], "utf-8")  # pip-audit writes UTF-8 on Windows too

    def test_a_batch_file_never_gets_characters_cmd_exe_acts_on(self):
        """On Windows a .bat or .cmd file runs in cmd.exe: a folder named a&calc&b would start calc."""
        tools = os.path.join(os.path.abspath(os.sep), "tools")  # C:\tools on Windows
        for name, path, runs in [("pip-audit.BAT", "C:\\work\\a&calc&b\\requirements.txt", False),
                                 ("pip-audit.cmd", "C:\\work\\shop (1)\\requirements.txt", False),
                                 ("pip-audit.cmd", "C:\\Users\\RUNNER~1\\shop\\requirements.txt", True),
                                 ("pip-audit.exe", "C:\\work\\a&b\\requirements.txt", True)]:
            program = os.path.join(tools, name)
            with self.subTest(program=program, path=path), \
                    mock.patch.object(mod.shutil, "which", return_value=program), \
                    mock.patch.object(mod.subprocess, "Popen") as fake_popen:
                fake_popen.return_value.__enter__.return_value.communicate.return_value = ("{}", "")
                if runs:
                    self.assertEqual(mod.run_tool(mod.PIP_AUDIT + [path], ".", []), ("{}", ""))
                else:
                    with self.assertRaisesRegex(ValueError, "batch file"):
                        mod.run_tool(mod.PIP_AUDIT + [path], ".", [])
                    fake_popen.assert_not_called()
        self.assertTrue(all(not mod.BATCH_UNSAFE.search(arg) for arg in mod.NPM + mod.COMPOSER))  # npm.cmd runs


class SandboxTests(unittest.TestCase):
    """deps.main with the real run_tool and fake auditors first on PATH: Python scripts with a
    shebang, and on Windows a .cmd file for each (the way npm is npm.cmd there)."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.bin = os.path.join(self.dir, "bin")
        self.log = os.path.join(self.dir, "log.jsonl")
        for tool in ("npm", "composer", "pip-audit"):
            if os.name == "nt":
                write(os.path.join(self.dir, "fakes"), tool + ".py", FAKE_AUDITOR % sys.executable)
                write(self.bin, tool + ".cmd", FAKE_CMD % tool)
            else:
                os.chmod(write(self.bin, tool, FAKE_AUDITOR % sys.executable), 0o755)
        env = {"PATH": self.bin + os.pathsep + os.environ.get("PATH", ""),
               "FORGE_FAKE_LOG": self.log, "FORGE_FAKE_OUT": "", "FORGE_FAKE_ERR": "",
               "FORGE_FAKE_PYTHON": sys.executable}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.project = os.path.join(self.dir, "project")

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as handle:
            return [json.loads(line) for line in handle]

    def test_npm_sees_only_copies_never_the_npmrc(self):
        write(self.project, "package.json", '{"name": "shop"}')
        write(self.project, "package-lock.json", '{"lockfileVersion": 3}')
        write(self.project, ".npmrc", "registry=http://127.0.0.1:9/\n")
        os.environ["FORGE_FAKE_OUT"] = '{"auditReportVersion": 2, "vulnerabilities": {}}'
        code, out = run(self.project, "--strict")
        [call] = self.calls()
        self.assertEqual(call["files"], ["package-lock.json", "package.json"])
        self.assertIn("--registry=https://registry.npmjs.org/", call["args"])
        self.assertFalse(os.path.realpath(call["cwd"]).startswith(os.path.realpath(self.project)))
        self.assertFalse(os.path.exists(call["cwd"]))  # the temp folder is gone afterwards
        self.assertEqual(code, 0)  # the fake exits 1: that is not an error
        self.assertIn("Dependency files checked: 1. No findings.", out)

    def test_composer_gets_an_empty_composer_json(self):
        write(self.project, "composer.json", '{"repositories": [{"packagist.org": false}]}')
        write(self.project, "composer.lock", '{"packages": []}')
        write(self.project, "auth.json", "{}")
        os.environ["FORGE_FAKE_OUT"] = '{"advisories": []}'
        run(self.project)
        [call] = self.calls()
        self.assertEqual(call["files"], ["composer.json", "composer.lock"])
        self.assertEqual(json.loads(call["composer_json"]), {})

    def test_pip_audit_gets_the_full_path_and_its_error_is_shown(self):
        path = write(self.project, "requirements.txt", "flask>=2\n")
        os.environ["FORGE_FAKE_ERR"] = ("WARNING: hashes are better\n"
                                        "ERROR: requirement flask is not pinned: flask>=2\n")
        code, out = run(self.project, "--json")
        [call] = self.calls()
        self.assertEqual(call["args"], ["--no-deps", "--disable-pip", "-f", "json", "-r",
                                        os.path.abspath(path)])
        [item] = json.loads(out)["not_checked"]
        self.assertEqual(item["reason"], "pip-audit could not check it (ERROR: requirement flask "
                                         "is not pinned: flask>=2)")

    def test_npm_advice_reads_the_project_lockfile(self):
        write(self.project, "package.json", '{"name": "shop"}')
        write(self.project, "package-lock.json", json.dumps(DRIZZLE_LOCK))
        os.environ["FORGE_FAKE_OUT"] = DRIZZLE_REPORT
        code, out = run(self.project)
        self.assertIn("older version of drizzle-kit (0.18.1, you have 0.31.11)", out)
        write(self.project, "package-lock.json", "{not json")  # unreadable: the plain advice
        self.assertIn("update drizzle-kit to 0.18.1", run(self.project)[1])

    def test_output_into_a_closed_pipe_ends_quietly(self):
        # Regression (dogfood): the scripts printed a BrokenPipeError traceback into `| head`.
        write(self.project, "package.json", '{"name": "shop"}')
        write(self.project, "package-lock.json", json.dumps(DRIZZLE_LOCK))
        os.environ["FORGE_FAKE_OUT"] = DRIZZLE_REPORT
        done = subprocess.Popen([sys.executable, mod.__file__, self.project], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        done.stdout.close()  # the reader is gone before anything is printed
        error = done.stderr.read().decode()
        done.stderr.close()
        self.assertEqual(done.wait(timeout=60), 1)
        self.assertNotIn("Traceback", error)

    def test_a_hung_auditor_is_stopped_with_what_it_started(self):
        """On Windows npm.cmd's cmd.exe runs node.exe: a timeout stops both, so nothing keeps the pipes or
        the sandbox open, and deps.py goes on at the time limit."""
        write(self.project, "package.json", '{"name": "shop"}')
        write(self.project, "package-lock.json", '{"lockfileVersion": 3}')
        os.environ["FORGE_FAKE_HANG"] = "1"
        started = time.monotonic()
        with mock.patch.object(mod, "TIMEOUT", 3):
            code, out = run(self.project, "--json")
        took = time.monotonic() - started
        [call] = self.calls()
        with contextlib.suppress(OSError):  # stopped already, unless the fix is missing
            os.kill(call["child"], signal.SIGTERM)
        self.assertLess(took, 30)
        [item] = json.loads(out)["not_checked"]
        self.assertEqual(item["reason"], "npm could not check it (it took over 3 seconds: try again later)")
        self.assertFalse(os.path.exists(call["cwd"]))  # the sandbox is gone: nothing runs in it any more

    def test_lockfile_without_package_json_is_not_checked(self):
        write(self.project, "package-lock.json", '{"lockfileVersion": 3}')
        code, out = run(self.project, "--json")
        self.assertEqual(self.calls(), [])  # npm never ran, so it cannot audit a parent project
        [item] = json.loads(out)["not_checked"]
        self.assertIn("package.json", item["reason"])
        self.assertEqual(json.loads(out)["summary"]["checked"], 0)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.calls = []
        self.answers = {"npm": (NPM_REPORT, ""), "composer": (COMPOSER_REPORT, ""),
                        "pip-audit": None}
        patcher = mock.patch.object(mod, "run_tool", self.fake_run_tool)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_run_tool(self, cmd, folder, copy):
        if cmd[0] not in self.answers:
            raise AssertionError("unexpected tool %r" % cmd[0])  # a test mistake must fail
        self.calls.append((cmd[0], os.path.relpath(folder, self.dir), list(copy)))
        answer = self.answers[cmd[0]]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def make_project(self):
        write(self.dir, "shop/package-lock.json")
        write(self.dir, "shop/package.json")
        write(self.dir, "blog/composer.lock")
        write(self.dir, "api/requirements.txt", "flask==0.5\n")
        write(self.dir, "web/pnpm-lock.yaml", "lockfileVersion: 9.0\n")

    def test_runs_each_auditor_for_its_folder(self):
        self.make_project()
        run(self.dir)
        self.assertEqual(sorted(self.calls), [
            ("composer", "blog", ["composer.lock"]), ("npm", "shop", ["package-lock.json",
                                                                     "package.json"]),
            ("pip-audit", "api", [])])

    def test_every_skipped_folder_is_skipped(self):
        for skipped in sorted(mod.SKIP_FOLDERS):
            write(self.dir, os.path.join(skipped, "deep", "composer.lock"))
        write(self.dir, "framework/composer.lock")  # only storage/framework is skipped
        write(self.dir, "storage/app/composer.lock")
        write(self.dir, "lib/build-tools/composer.lock")
        run(self.dir)
        self.assertEqual(sorted(folder for _, folder, _ in self.calls),
                         ["framework", os.path.join("lib", "build-tools"),
                          os.path.join("storage", "app")])

    def test_human_output(self):
        self.make_project()
        code, out = run(self.dir)
        self.assertEqual(code, 1)  # critical and high findings, --fail-on high
        self.assertLess(out.index("CRITICAL"), out.index("HIGH"))
        self.assertLess(out.index("HIGH"), out.index("MEDIUM"))
        self.assertLess(out.index("MEDIUM"), out.index("LOW"))
        self.assertIn('CRITICAL  2 known vulnerabilities in npm package "minimist"', out)
        self.assertIn("where: " + os.path.join(self.dir, "shop", "package-lock.json"), out)
        self.assertIn('why:   this app uses a version of "minimist" with publicly known', out)
        self.assertIn("holes: Prototype Pollution in minimist\n", out)
        self.assertIn("more:  https://github.com/advisories/GHSA-xvch-5gv4-984h", out)
        self.assertIn('fix:   update react-scripts to 5.0.1 in package.json', out)
        self.assertIn("Not checked (the result below does not cover these):", out)
        self.assertIn('pip-audit is not installed: install it with "pipx install pip-audit",'
                      ' then run deps.py again', out)
        self.assertIn('pnpm-lock.yaml: pnpm is not run here: run "pnpm audit" in that folder', out)
        self.assertTrue(out.rstrip().endswith(
            "Dependency files checked: 2. Findings: 7 (1 critical, 3 high, 1 medium, 2 low)."))

    def test_json_output(self):
        self.make_project()
        code, out = run(self.dir, "--json")
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(len(data["findings"]), 7)
        for finding in data["findings"]:
            for key in ("severity", "title", "where", "why", "fix", "holes", "package", "links"):
                self.assertIn(key, finding)
        self.assertEqual(data["findings"][0]["severity"], "critical")
        self.assertEqual([item["tool"] for item in data["checked"]], ["composer", "npm"])
        self.assertEqual(sorted(os.path.basename(item["file"]) for item in data["not_checked"]),
                         ["pnpm-lock.yaml", "requirements.txt"])
        summary = data["summary"]
        self.assertEqual((summary["critical"], summary["high"], summary["total"]), (1, 3, 7))
        self.assertEqual((summary["checked"], summary["not_checked"]), (2, 2))
        self.assertTrue(summary["failed"])

    def test_fail_on(self):
        write(self.dir, "blog/composer.lock")  # worst finding here: high
        self.assertEqual(run(self.dir)[0], 1)
        self.assertEqual(run(self.dir, "--fail-on", "critical")[0], 0)
        low = {"advisories": {"a/b": [{"title": "t", "severity": "low"}]}}
        self.answers["composer"] = (json.dumps(low), "")
        self.assertEqual(run(self.dir)[0], 0)
        self.assertEqual(run(self.dir, "--fail-on", "low")[0], 1)

    def test_nothing_checked_is_never_called_clean(self):
        write(self.dir, "api/requirements.txt")
        code, out = run(self.dir)
        self.assertEqual(code, 0)
        self.assertNotIn("No findings", out)
        self.assertIn("Nothing could be checked, so this is NOT a clean result.", out)
        self.assertEqual(run(self.dir, "--strict")[0], 1)

    def test_partly_checked_says_so(self):
        write(self.dir, "shop/package-lock.json")
        write(self.dir, "api/requirements.txt")
        self.answers["npm"] = ('{"vulnerabilities": {}}', "")
        code, out = run(self.dir)
        self.assertIn('Dependency files checked: 1. No findings in what was checked; the rest is '
                      'listed under "Not checked".', out)
        self.assertEqual((code, run(self.dir, "--strict")[0]), (0, 1))

    def test_clean_project(self):
        write(self.dir, "shop/package-lock.json")
        self.answers["npm"] = ('{"auditReportVersion": 2, "vulnerabilities": {}}', "")
        code, out = run(self.dir, "--strict")
        self.assertEqual(code, 0)
        self.assertIn("Dependency files checked: 1. No findings.", out)

    def test_nothing_to_check_explains_lockfiles(self):
        write(self.dir, "src/index.php", "<?php echo 1;")
        write(self.dir, "package.json", "{}")
        write(self.dir, "composer.json", "{}")
        code, out = run(self.dir)
        self.assertEqual(code, 0)
        self.assertIn("No lockfiles or requirements files found, so nothing was checked.", out)
        self.assertIn("package.json or composer.json alone cannot be checked", out)
        self.assertEqual(run(self.dir, "--strict")[0], 1)
        self.assertEqual(self.calls, [])

    def test_install_hints(self):
        write(self.dir, "shop/package-lock.json")
        write(self.dir, "blog/composer.lock")
        self.answers.update(npm=None, composer=None)
        reasons = [item["reason"] for item in json.loads(run(self.dir, "--json")[1])["not_checked"]]
        self.assertEqual(reasons, [
            "composer is not installed: install Composer (getcomposer.org), then run deps.py again",
            "npm is not installed: install Node.js (nodejs.org), then run deps.py again"])

    def test_timeout_is_a_note(self):
        write(self.dir, "shop/package-lock.json")
        self.answers["npm"] = subprocess.TimeoutExpired(["npm"], mod.TIMEOUT)
        code, out = run(self.dir)
        self.assertEqual(code, 0)
        self.assertIn("npm could not check it (it took over 180 seconds: try again later)", out)
        self.assertEqual(run(self.dir, "--strict")[0], 1)

    def test_tool_that_will_not_start_is_a_note(self):
        write(self.dir, "shop/package-lock.json")
        self.answers["npm"] = PermissionError(13, "Permission denied")
        self.assertIn("npm could not check it ([Errno 13] Permission denied)", run(self.dir)[1])

    def test_unreadable_output_says_why(self):
        write(self.dir, "shop/package-lock.json")
        write(self.dir, "blog/composer.lock")
        write(self.dir, "api/requirements.txt")
        self.answers["npm"] = (json.dumps({"error": {"summary": "registry unreachable"}}), "")
        login = "user:" + "hunter2" + "-secret@"  # built at runtime: the repo holds no secret
        self.answers["composer"] = ("Command audit is not defined.",
                                    "Do not run Composer as root\nIn Application.php: "
                                    "https://" + login + "repo.example.com/ failed\n")
        self.answers["pip-audit"] = ('{"dependencies": [{"vulns": [{"no-id": 1}]}]}', "")
        code, out = run(self.dir, "--json")
        reasons = [item["reason"] for item in json.loads(out)["not_checked"]]
        self.assertEqual(code, 0)
        self.assertEqual(reasons, [
            "pip-audit could not check it (its report has a shape this script does not know)",
            "composer could not check it (In Application.php: https://****@repo.example.com/ "
            "failed)",
            "npm could not check it (registry unreachable)"])
        self.assertNotIn("hunter2", out)

    def test_packages_pip_audit_skipped_are_not_checked(self):
        write(self.dir, "api/requirements.txt")
        self.answers["pip-audit"] = (PIP_REPORT, "")
        data = json.loads(run(self.dir, "--json")[1])
        self.assertEqual(data["summary"]["checked"], 1)
        self.assertEqual([item["reason"] for item in data["not_checked"]],
                         ["pip-audit could not check private-pkg: Dependency not found on PyPI"])

    def test_unreadable_folder_is_not_checked(self):
        def fake_walk(path, onerror):
            onerror(PermissionError(13, "Permission denied", os.path.join(path, "locked")))
            yield path, [], ["README.md"]
        with mock.patch.object(mod.os, "walk", fake_walk):
            code, out = run(self.dir, "--json")
        data = json.loads(out)
        self.assertEqual(data["not_checked"], [{"file": os.path.join(self.dir, "locked"),
                                                "reason": "could not open this folder"}])
        with mock.patch.object(mod.os, "walk", fake_walk):
            self.assertEqual(run(self.dir, "--strict")[0], 1)

    def test_python_notes_end_to_end(self):
        write(self.dir, "a/poetry.lock")
        write(self.dir, "a/pyproject.toml")
        write(self.dir, "b/Pipfile.lock")
        write(self.dir, "c/pyproject.toml")
        reasons = [item["reason"] for item in json.loads(run(self.dir, "--json")[1])["not_checked"]]
        self.assertEqual(len(reasons), 3)
        for word, reason in zip(["poetry export", "pipenv requirements", "pip-compile"], reasons):
            self.assertIn(word, reason)

    def test_file_name_that_is_not_utf8_does_not_crash(self):
        try:
            folder = os.path.join(self.dir, os.fsdecode(b"app\xff"))
            write(folder, "yarn.lock", "")
        except (OSError, UnicodeError):
            self.skipTest("this file system needs UTF-8 names")
        raw = io.BytesIO()
        strict_stdout = io.TextIOWrapper(raw, encoding="utf-8", errors="strict")
        with contextlib.redirect_stdout(strict_stdout):
            code = mod.main([self.dir])
        strict_stdout.flush()
        self.assertEqual(code, 0)
        self.assertIn(b"app\\udcff", raw.getvalue())

    def test_symlinks_are_not_followed(self):
        target = write(self.dir, "elsewhere/package-lock.json")
        write(self.dir, "app/README.md", "hi")
        symlink(self, target, os.path.join(self.dir, "app", "package-lock.json"))
        symlink(self, os.path.join(self.dir, "elsewhere"), os.path.join(self.dir, "app", "linked"))
        run(os.path.join(self.dir, "app"))
        self.assertEqual(self.calls, [])

    def test_missing_path_or_a_file_is_exit_2(self):
        self.assertEqual(run(os.path.join(self.dir, "nope"))[0], 2)
        self.assertEqual(run(write(self.dir, "package-lock.json"))[0], 2)

    def test_bad_flag_is_exit_2(self):
        with self.assertRaises(SystemExit) as caught:
            run(self.dir, "--fail-on", "urgent")
        self.assertEqual(caught.exception.code, 2)


class ScriptTests(unittest.TestCase):
    def test_conventions(self):
        with open(mod.__file__) as handle:
            source = handle.read()
        self.assertTrue(source.startswith("#!/usr/bin/env python3\n"))
        self.assertLessEqual(len(source.splitlines()), 300)  # the spec's hard limit
        for words in ("Usage", "Exit codes", "forge:allow"):
            self.assertIn(words, mod.__doc__)
        self.assertIn("\ndef main(argv=None):", source)
        self.assertIn("timeout=TIMEOUT", source)
        self.assertNotRegex(source, r"\bshell\s*=")
        self.assertNotRegex(source, r"\b(eval|exec)\s*\(|\bpickle\b")
        imports = sorted(line.split()[1] for line in source.splitlines()
                         if line.startswith(("import ", "from ")))
        self.assertEqual(imports, ["argparse", "errno", "fnmatch", "json", "os", "re", "shutil",
                                   "subprocess", "sys", "tempfile", "textwrap"])


class ConsoleTests(unittest.TestCase):
    def test_a_cp1252_pipe_gets_escapes_not_a_crash(self):
        """Windows pipes are cp1252 (no arrow): the arrow prints as \\u2192, no crash."""
        with tempfile.TemporaryDirectory() as folder:
            lock = write(folder, os.path.join("caf\u00e9 \u2192", "yarn.lock"), "")
            code, out, err = run_cp1252(mod.__file__, folder)
        self.assertEqual(code, 0, err)
        self.assertIn("  - %s: Yarn is not run here" % lock.replace("\u2192", "\\u2192"), out)


if __name__ == "__main__":
    unittest.main()
