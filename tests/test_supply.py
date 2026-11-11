"""Tests for forge-check/supply.py: each supply-chain rule fires and stays quiet, the exit codes,
the JSON shape, the CycloneDX list, and that nothing is written through a symlink."""

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252, symlink  # noqa: E402

supply = load("forge-check", "supply")
SCRIPT = os.path.join(ROOT, "forge-check", "supply.py")
NPM = "https://registry.npmjs.org/%s/-/%s-%s.tgz"


def entry(name, version="1.0.0", **more):
    """One package of a package-lock.json, from the official registry, with a hash and a licence."""
    return dict({"version": version, "resolved": NPM % (name, name, version), "integrity": "sha512-abc",
                 "license": "MIT"}, **more)


def lock(**packages):
    return json.dumps({"name": "app", "lockfileVersion": 3,
                       "packages": dict({"": {"name": "app"}},
                                        **{"node_modules/" + name: item for name, item in packages.items()})})


class Project(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def write(self, name, text):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def npm(self, deps, **packages):
        self.write("package.json", json.dumps({"name": "app", "dependencies": deps}))
        self.write("package-lock.json", lock(**packages))

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = supply.main([self.root] + list(args))
        return code, out.getvalue(), err.getvalue()

    def report(self, *args):
        code, out, _ = self.run_main("--json", *args)
        return code, json.loads(out)

    def rules(self):
        return {finding["rule"]: finding for finding in self.report()[1]["findings"]}


class NpmTests(Project):
    def test_a_clean_project_passes(self):
        self.npm({"react": "^18.3.1"}, react=entry("react", "18.3.1"))
        code, data = self.report()
        self.assertEqual((code, data["findings"], data["unreadable"]), (0, [], []))
        self.assertEqual(data["summary"]["packages"], 1)
        self.assertFalse(data["summary"]["incomplete"])
        code, out, err = self.run_main()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("Packages in lockfiles: 1", out)

    def test_no_lockfile_is_high(self):
        self.write("package.json", json.dumps({"name": "app", "dependencies": {"express": "4.19.2"}}))
        found = self.rules()
        self.assertEqual(found["supply-no-lockfile"]["severity"], "high")
        self.assertEqual(found["supply-no-lockfile"]["where"], "package.json")
        self.assertEqual(self.run_main()[0], 1)

    def test_floating_versions(self):
        self.npm({"react": "*", "vue": "latest", "axios": ">=1.0.0", "express": "^4.19.2", "lodash": "4.17.21"},
                 **{name: entry(name) for name in ("react", "vue", "axios", "express", "lodash")})
        finding = self.rules()["supply-floating"]
        self.assertEqual(finding["severity"], "medium")
        self.assertEqual(sorted(finding["packages"]), ["axios", "react", "vue"])
        self.assertEqual(self.run_main()[0], 0)  # medium: under the default --fail-on high
        self.assertEqual(self.run_main("--fail-on", "medium")[0], 1)

    def test_code_from_outside_the_registry(self):
        self.npm({"a": "git+https://github.com/x/a.git", "b": "https://x.example/b.tgz", "c": "file:../c",
                  "d": "1.0.0"}, d=entry("d"))
        finding = self.rules()["supply-source"]
        self.assertEqual(finding["severity"], "high")
        self.assertEqual(sorted(finding["packages"]), ["a", "b", "c"])

    def test_a_locked_package_from_another_host(self):
        self.npm({"evil": "1.0.0", "fine": "1.0.0"}, fine=entry("fine"),
                 evil=entry("evil", resolved="https://evil.example/evil-1.0.0.tgz"))
        finding = self.rules()["supply-registry"]
        self.assertEqual(finding["severity"], "high")
        self.assertEqual(finding["packages"], ["evil (evil.example)"])

    def test_install_scripts_hashes_and_licences(self):
        self.npm({"a": "1.0.0", "b": "1.0.0", "c": "1.0.0", "d": "1.0.0"}, a=entry("a", hasInstallScript=True),
                 b={"version": "1.0.0", "resolved": NPM % ("b", "b", "1.0.0"), "license": "MIT"},
                 c=entry("c", license="AGPL-3.0-only"),
                 d={"version": "1.0.0", "resolved": NPM % ("d", "d", "1.0.0"), "integrity": "sha512-abc"})
        found = self.rules()
        self.assertEqual((found["supply-install-script"]["severity"], found["supply-install-script"]["packages"]),
                         ("low", ["a"]))
        self.assertEqual((found["supply-no-integrity"]["severity"], found["supply-no-integrity"]["packages"]),
                         ("medium", ["b"]))
        self.assertEqual((found["supply-licence"]["severity"], found["supply-licence"]["packages"]),
                         ("medium", ["c (AGPL-3.0-only)"]))
        self.assertEqual((found["supply-no-licence"]["severity"], found["supply-no-licence"]["packages"]),
                         ("low", ["d"]))

    def test_a_look_alike_name_but_not_the_real_one(self):
        self.npm({"lodahs": "^4.0.0", "lodash": "^4.17.21", "react": "^18.0.0"},
                 **{name: entry(name) for name in ("lodahs", "lodash", "react")})
        finding = self.rules()["supply-typosquat"]
        self.assertEqual(finding["severity"], "high")
        self.assertEqual(finding["packages"], ["lodahs (like lodash)"])

    def test_node_modules_and_forge_work_are_not_walked(self):
        self.npm({"react": "^18.3.1"}, react=entry("react", "18.3.1"))
        for folder in ("node_modules/dep", "forge-work/notes"):
            self.write(folder + "/package.json", json.dumps({"name": "dep", "dependencies": {"x": "*"}}))
        self.assertEqual(self.report()[1]["findings"], [])

    def test_test_fixtures_are_not_the_apps_packages(self):
        """A broken package.json in a test's fixtures is there on purpose: it never makes the check incomplete."""
        self.npm({"react": "^18.3.1"}, react=entry("react", "18.3.1"))
        for folder in ("tests/fixtures/broken", "src/__fixtures__/app", "pkg/testdata"):
            self.write(folder + "/package.json", '{"name": "broken", ')
        code, data = self.report("--sbom", os.path.join(self.root, "sbom.json"))
        self.assertEqual((code, data["unreadable"], data["sbom"]["written"]), (0, [], True))

    def test_a_lockfile_read_as_text_counts_and_says_what_it_lacks(self):
        self.write("package.json", json.dumps({"name": "app", "dependencies": {"react": "^18.3.1"}}))
        self.write("yarn.lock", "# yarn lockfile v1\n")
        code, data = self.report()
        self.assertNotIn("supply-no-lockfile", [finding["rule"] for finding in data["findings"]])
        self.assertEqual([item["file"] for item in data["not_read"]], ["yarn.lock"])
        self.assertIn("Not read in full: yarn.lock (names, versions and download addresses only: it holds no "
                      "licences or install scripts)", self.run_main()[1])


class TextLockTests(Project):
    """yarn, pnpm, bun and Pipenv: their packages go into the checks and the SBOM, as names and versions."""
    YARN_1 = ('# yarn lockfile v1\n\n\n"@babel/code-frame@^7.0.0", "@babel/code-frame@^7.10.4":\n  version "7.12.13"\n'
              '  resolved "https://registry.yarnpkg.com/@babel/code-frame/-/code-frame-7.12.13.tgz#dcfc826b"\n'
              '  integrity sha512-abc\n\nlodahs@^4.0.0:\n  version "4.0.1"\n'
              '  resolved "https://evil.example/lodahs-4.0.1.tgz"\n')
    YARN_BERRY = ('__metadata:\n  version: 8\n  cacheKey: 10\n\n"app@workspace:.":\n  version: 0.0.0-use.local\n'
                  '  resolution: "app@workspace:."\n\n"react@npm:^18.3.1":\n  version: 18.3.1\n'
                  '  resolution: "react@npm:18.3.1"\n  checksum: 10c0/abc\n')
    PNPM_9 = ("lockfileVersion: '9.0'\n\nimporters:\n\n  .:\n    dependencies:\n      next:\n        specifier: ^15.1.3\n"
              "        version: 15.1.3(react@19.0.0)\n\npackages:\n\n  '@next/env@15.1.3':\n"
              "    resolution: {integrity: sha512-abc}\n\n  next@15.1.3:\n    resolution: {integrity: sha512-def}\n"
              "    engines: {node: '>=18'}\n\n  tool@1.0.0:\n    resolution: {tarball: https://evil.example/tool.tgz}\n\n"
              "snapshots:\n\n  next@15.1.3(react@19.0.0):\n    dependencies:\n      react: 19.0.0\n")
    PNPM_6 = "lockfileVersion: '6.0'\n\npackages:\n\n  /react@18.2.0:\n    resolution: {integrity: sha512-abc}\n"
    BUN = ('{\n  "lockfileVersion": 1,\n  "workspaces": { "": { "name": "web", "dependencies": { "next": "15.1.3" } } },\n'
           '  "packages": {\n    "next": ["next@15.1.3", "", { "dependencies": {} }, "sha512-abc"],\n'
           '    "next/@swc/helpers": ["@swc/helpers@0.5.15", "", {}, "sha512-def"],\n'
           '    "ui": ["ui@workspace:packages/ui"],\n  }\n}\n')
    PIPFILE = json.dumps({"_meta": {"hash": {"sha256": "abc"}, "sources": [{"name": "pypi",
                                                                            "url": "https://pypi.org/simple"}]},
                          "default": {"django": {"hashes": ["sha256:abc"], "index": "pypi", "version": "==5.0.1"}},
                          "develop": {"pytest": {"version": "==8.3.4"}, "local": {"path": ".", "editable": True}}})

    def sbom(self, *args):
        target = os.path.join(self.root, "forge-work", "sbom.json")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        code, data = self.report("--sbom", target, *args)
        with open(target, encoding="utf-8") as handle:
            text = handle.read()
        return code, data, {part["purl"] for part in json.loads(text)["components"]} if text else None

    def test_yarn_1_and_berry(self):
        self.write("package.json", json.dumps({"name": "app", "dependencies": {"lodahs": "^4.0.0"}}))
        self.write("yarn.lock", self.YARN_1)
        code, data, parts = self.sbom()
        self.assertEqual(parts, {"pkg:npm/%40babel/code-frame@7.12.13", "pkg:npm/lodahs@4.0.1"})
        found = {finding["rule"]: finding["packages"] for finding in data["findings"]}
        self.assertEqual((code, found["supply-typosquat"], found["supply-registry"]),
                         (1, ["lodahs (like lodash)"], ["lodahs (evil.example)"]))
        self.write("yarn.lock", self.YARN_BERRY)
        self.assertEqual(self.sbom()[2], {"pkg:npm/react@18.3.1"}, "the workspace itself is no package")

    def test_pnpm_9_and_6(self):
        self.write("package.json", json.dumps({"name": "app", "dependencies": {"next": "^15.1.3"}}))
        self.write("pnpm-lock.yaml", self.PNPM_9)
        code, data, parts = self.sbom()
        self.assertEqual(parts, {"pkg:npm/%40next/env@15.1.3", "pkg:npm/next@15.1.3", "pkg:npm/tool@1.0.0"})
        self.assertIn("tool (evil.example)", [package for finding in data["findings"] for package in finding["packages"]])
        self.write("pnpm-lock.yaml", self.PNPM_6)
        self.assertEqual(self.sbom()[2], {"pkg:npm/react@18.2.0"})

    def test_bun_lock_and_a_binary_one(self):
        self.write("package.json", json.dumps({"name": "web", "dependencies": {"next": "15.1.3"}}))
        self.write("bun.lockb", "\x00\x01binary")
        code, data, parts = self.sbom()
        self.assertEqual((code, parts, data["summary"]["incomplete"]), (2, None, True), "an empty SBOM, exit 2")
        self.assertIn("bun.lockb", [item["path"] for item in data["unreadable"]])
        self.write("bun.lock", self.BUN)
        code, data, parts = self.sbom()
        self.assertEqual((code, parts), (0, {"pkg:npm/next@15.1.3", "pkg:npm/%40swc/helpers@0.5.15"}))
        self.assertEqual(data["unreadable"], [], "the text bun.lock is read, the old binary one left alone")

    def test_pipfile_lock_and_pdm_lock(self):
        self.write("Pipfile.lock", self.PIPFILE)
        self.write("pdm.lock", '[metadata]\ngroups = ["default"]\n\n[[package]]\nname = "Flask"\nversion = "3.1.0"\n')
        code, data, parts = self.sbom()
        self.assertEqual((code, parts), (0, {"pkg:pypi/django@5.0.1", "pkg:pypi/pytest@8.3.4", "pkg:pypi/flask@3.1.0"}))
        self.assertEqual([item["file"] for item in data["not_read"]], ["Pipfile.lock"])

    def test_package_lock_version_1_makes_the_check_incomplete(self):
        self.write("package.json", json.dumps({"name": "app", "dependencies": {"react": "^16.0.0"}}))
        self.write("package-lock.json", json.dumps({"name": "app", "lockfileVersion": 1, "dependencies": {}}))
        code, data, parts = self.sbom()
        self.assertEqual((code, parts), (2, None))
        self.assertEqual([item["path"] for item in data["unreadable"]], ["package-lock.json"])

    def test_the_data_file_names_each_lockfile_its_registry_and_what_it_lacks(self):
        self.assertEqual(sorted(supply.LOCKS), ["Pipfile.lock", "bun.lock", "bun.lockb", "pnpm-lock.yaml", "yarn.lock"])
        for name, (kind, pattern, note) in supply.LOCKS.items():
            with self.subTest(lock=name):
                self.assertIn(kind, ("npm", "pypi"))
                self.assertTrue(note.strip())
                self.assertEqual(re.compile(pattern).groups, 3) if pattern else self.assertEqual(name, "bun.lockb")


class OtherRegistryTests(Project):
    def test_requirements_pins_and_floats(self):
        self.write("requirements.txt", "requests>=2\ndjango==5.0.1\nflask\n# a comment\n")
        finding = self.rules()["supply-floating"]
        self.assertEqual(sorted(finding["packages"]), ["flask", "requests"])
        self.assertEqual(finding["where"], "requirements.txt")

    def test_requirements_from_a_git_url(self):
        self.write("requirements.txt", "git+https://github.com/x/y.git#egg=y\nz @ https://x.example/z.whl\n"
                                       "django==5.0.1\n")
        found = self.rules()
        self.assertEqual(len(found["supply-source"]["packages"]), 2)
        self.assertNotIn("supply-floating", found)  # "git" is no package name

    def test_composer_without_and_with_a_lockfile(self):
        self.write("composer.json", json.dumps({"require": {"laravel/framework": "^11.0"}}))
        self.assertIn("supply-no-lockfile", self.rules())
        self.write("composer.lock", json.dumps({"packages": [
            {"name": "laravel/framework", "version": "v11.0.0", "license": ["MIT"],
             "dist": {"url": "https://api.github.com/repos/laravel/framework/zipball/abc", "shasum": ""}}]}))
        code, data = self.report()
        self.assertNotIn("supply-no-lockfile", [finding["rule"] for finding in data["findings"]])
        self.assertEqual(data["summary"]["packages"], 1)

    def test_nothing_to_check_says_so(self):
        code, out, _ = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("Nothing was checked", out)


class SbomTests(Project):
    def test_the_sbom_is_cyclonedx_and_does_not_change_the_exit_code(self):
        self.npm({"react": "^18.3.1", "evil": "1.0.0"}, react=entry("react", "18.3.1"),
                 evil=entry("evil", resolved="https://evil.example/evil-1.0.0.tgz"))
        target = os.path.join(self.root, "forge-work", "sbom.json")
        os.makedirs(os.path.dirname(target))
        code, out, _ = self.run_main("--sbom", target)
        self.assertEqual(code, 1)  # the finding decides, not the list
        with open(target, encoding="utf-8") as handle:
            sbom = json.load(handle)
        self.assertEqual((sbom["bomFormat"], sbom["specVersion"]), ("CycloneDX", "1.5"))
        parts = {part["name"]: part for part in sbom["components"]}
        self.assertEqual(sorted(parts), ["evil", "react"])
        self.assertEqual(parts["react"]["type"], "library")
        self.assertEqual(parts["react"]["version"], "18.3.1")
        self.assertEqual(parts["react"]["purl"], "pkg:npm/react@18.3.1")
        self.assertEqual(parts["react"]["licenses"], [{"license": {"name": "MIT"}}])

    def test_the_sbom_is_never_written_through_a_symlink(self):
        self.npm({"react": "^18.3.1"}, react=entry("react", "18.3.1"))
        outside = os.path.join(self.root, "outside.txt")
        self.write("outside.txt", "keep me\n")
        link = os.path.join(self.root, "sbom.json")
        symlink(self, outside, link)
        self.run_main("--sbom", link)
        with open(outside, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "keep me\n")


class ExitCodeTests(Project):
    def test_a_path_that_is_no_folder_is_exit_2(self):
        self.write("file.txt", "x")
        for name in ("nope", "file.txt"):
            with self.subTest(path=name):
                done = subprocess.run([sys.executable, SCRIPT, os.path.join(self.root, name)], timeout=60,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                self.assertEqual(done.returncode, 2)
                self.assertIn("is not a folder", done.stderr)

    def test_a_broken_manifest_makes_the_check_incomplete(self):
        self.write("package.json", "{not json")
        code, data = self.report()
        self.assertEqual(code, 2)
        self.assertTrue(data["summary"]["incomplete"])
        self.assertEqual([item["path"] for item in data["unreadable"]], ["package.json"])
        code, out, _ = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn("INCOMPLETE, so not a pass", out)

    def test_json_shape(self):
        self.npm({"react": "*"}, react=entry("react", "18.3.1"))
        code, data = self.report()
        self.assertEqual(sorted(data), ["files", "findings", "not_read", "summary", "unreadable"])
        self.assertEqual(sorted(data["findings"][0]),
                         ["fix", "packages", "rule", "severity", "title", "where", "why"])
        for key in ("critical", "high", "medium", "low", "total", "packages", "incomplete"):
            self.assertIn(key, data["summary"])

    def test_every_rule_in_the_data_file_has_its_words(self):
        with open(os.path.join(ROOT, "forge-check", "supply.json"), encoding="utf-8") as handle:
            data = json.load(handle)
        for rule, words in data["rules"].items():
            with self.subTest(rule=rule):
                self.assertIn(words["severity"], ("critical", "high", "medium", "low"))
                for key in ("title", "why", "fix"):
                    self.assertTrue(words[key].strip())
        for kind, names in data["popular"].items():
            self.assertGreater(len(names), 40, kind)

    def test_help_and_a_windows_pipe(self):
        done = subprocess.run([sys.executable, SCRIPT, "--help"], timeout=60, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0)
        self.assertIn("Exit codes:", done.stdout)
        self.npm({"lodahs": "*"}, lodahs=entry("lodahs", license="GPL-3.0"))
        code, out, err = run_cp1252(SCRIPT, self.root)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("supply-typosquat", out)


if __name__ == "__main__":
    unittest.main()
