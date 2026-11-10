"""Tests for forge-test/walkcheck.py: every rule fires and stays quiet, one problem at several widths
is one finding, the budget, the bug blocks (which bugs.py must read), and the exit codes 0, 1 and 2."""

import contextlib
import copy
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402

walkcheck = load("forge-test", "walkcheck")
bugs = load("forge-test", "bugs")
SCRIPT = os.path.join(ROOT, "forge-test", "walkcheck.py")
WIDTHS, SCHEMES = [390, 768, 1440], ["light", "dark"]
ROUTES = [{"name": "S01-home", "path": "/", "as": None}, {"name": "S03-dashboard", "path": "/dashboard", "as": "alice"}]


def page(route, width, scheme, **changes):
    """One clean result, as walk.spec.ts writes it."""
    result = {"route": route["name"], "path": route["path"], "as": route["as"], "width": width, "scheme": scheme,
              "loaded": True, "error": None, "incomplete": [], "status": 200, "redirected_to": None,
              "screenshot": "forge-work/test/shots/r1/%s-%d-%s.png" % (route["name"], width, scheme),
              "console_errors": [], "page_errors": [], "failed_requests": [], "bad_responses": [],
              "broken_links": [], "links_checked": 3, "axe": [], "overflow_px": 0, "clipped": [], "overlaps": [],
              "small_targets": [], "perf": {"lcp_ms": 900, "cls": 0.01, "ttfb_ms": 80, "load_ms": 1100,
                                            "requests": 12, "transfer_bytes": 300000}}
    result.update(changes)
    return result


def walk(changes=None):
    """A clean walk of two routes. changes: {(route name, width, scheme) or route name or "*": fields}."""
    results, changes = [], changes or {}
    for route in ROUTES:
        for width in WIDTHS:
            for scheme in SCHEMES:
                extra = {}
                for key in ("*", route["name"], (route["name"], width, scheme)):
                    extra.update(copy.deepcopy(changes.get(key, {})))
                results.append(page(route, width, scheme, **extra))
    return {"version": 1, "base_url": "http://localhost:8080", "round": "r1", "widths": WIDTHS, "schemes": SCHEMES,
            "routes": ROUTES, "results": results}


class WalkcheckTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)

    def write(self, data, name="walk.json"):
        path = os.path.join(self.folder, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def run_main(self, data, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = walkcheck.main([self.write(data)] + list(args))
        return code, out.getvalue(), err.getvalue()

    def findings(self, data, *args):
        code, out, _ = self.run_main(data, "--json", *args)
        return code, json.loads(out)

    def one(self, changes, rule, severity, at="S01-home"):
        """A walk with CHANGES on one route gives exactly one finding of RULE with SEVERITY."""
        _, report = self.findings(walk({at: changes}), "--fail-on", "low")
        found = [finding for finding in report["findings"] if finding["rule"] == rule]
        self.assertEqual(len(found), 1, report["findings"])
        self.assertEqual(found[0]["severity"], severity)
        self.assertEqual(len(report["findings"]), 1, "only this rule fires")
        return found[0]

    def test_a_clean_walk_passes(self):
        code, out, err = self.run_main(walk())
        self.assertEqual((code, err), (0, ""))
        self.assertIn("PASS", out)
        self.assertIn("0 finding(s) on 2 route(s)", out)

    def test_each_rule(self):
        cases = [
            ({"status": 500}, "status", "high"),
            ({"status": 404}, "status", "high"),
            ({"redirected_to": "/login"}, "redirect", "medium"),
            ({"page_errors": ["x is not defined"]}, "page-error", "high"),
            ({"console_errors": ["Hydration failed"]}, "console-error", "medium"),
            ({"failed_requests": [{"url": "http://localhost:8080/api", "method": "GET", "same_origin": True,
                                   "error": "net::ERR_FAILED"}]}, "request-failed", "medium"),
            ({"failed_requests": [{"url": "https://cdn.example/x.js", "method": "GET", "same_origin": False,
                                   "error": "net::ERR_FAILED"}]}, "request-failed", "low"),
            ({"bad_responses": [{"url": "http://localhost:8080/api", "status": 503, "method": "GET",
                                 "same_origin": True}]}, "response", "high"),
            ({"bad_responses": [{"url": "http://localhost:8080/logo.png", "status": 404, "method": "GET",
                                 "same_origin": True}]}, "response", "medium"),
            ({"bad_responses": [{"url": "https://cdn.example/a", "status": 403, "method": "GET",
                                 "same_origin": False}]}, "response", "low"),
            ({"axe": [{"id": "label", "impact": "critical", "help": "Form elements must have labels", "nodes": 2,
                       "targets": ["#email"]}]}, "axe", "high"),
            ({"axe": [{"id": "color-contrast", "impact": "serious", "help": "Contrast", "nodes": 1,
                       "targets": ["p"]}]}, "axe", "medium"),
            ({"axe": [{"id": "region", "impact": "moderate", "help": "Landmarks", "nodes": 1, "targets": []}]},
             "axe", "low"),
            ({"overflow_px": 40}, "overflow", "medium"),
            ({"clipped": [{"element": "<h2> \"A long title\"", "direction": "sideways"}]}, "clipped", "medium"),
            ({"overlaps": [{"element": "<a> \"Help\"", "covered_by": "<button> \"Chat\""}]}, "overlap", "medium"),
            ({"small_targets": [{"element": "<button> \"x\"", "width": 16, "height": 16}]}, "target", "low"),
            ({"perf": {"lcp_ms": 3000}}, "lcp_ms", "medium"),
            ({"perf": {"lcp_ms": 5001}}, "lcp_ms", "high"),
            ({"perf": {"cls": 0.2}}, "cls", "medium"),
            ({"perf": {"ttfb_ms": 900}}, "ttfb_ms", "medium"),
            ({"perf": {"load_ms": 9000}}, "load_ms", "high"),
            ({"perf": {"transfer_bytes": 1600000}}, "transfer_bytes", "medium"),
            ({"perf": {"requests": 500}}, "requests", "low"),
        ]
        for changes, rule, severity in cases:
            with self.subTest(rule=rule, severity=severity):
                finding = self.one(changes, rule, severity)
                for field in ("title", "where", "why", "fix", "expected", "actual", "steps"):
                    self.assertTrue(finding[field], field)
                self.assertTrue(finding["title"].startswith("S01-home: "))

    def test_values_at_the_budget_and_unmeasured_values_are_fine(self):
        perf = dict(walkcheck.BUDGET, lcp_ms=None)
        code, report = self.findings(walk({"*": {"perf": perf}}), "--fail-on", "low")
        self.assertEqual((code, report["findings"]), (0, []))

    def test_one_problem_at_several_widths_and_schemes_is_one_finding(self):
        data = walk({("S01-home", 390, "light"): {"overflow_px": 12}, ("S01-home", 768, "dark"): {"overflow_px": 30},
                       "S03-dashboard": {"console_errors": ["boom"]}})
        _, report = self.findings(data, "--fail-on", "low")
        by_rule = {finding["rule"]: finding for finding in report["findings"]}
        self.assertEqual(sorted(by_rule), ["console-error", "overflow"])
        self.assertEqual(by_rule["overflow"]["widths"], [390, 768])
        self.assertEqual(by_rule["overflow"]["schemes"], ["light", "dark"])
        self.assertEqual(by_rule["overflow"]["screenshot"], "forge-work/test/shots/r1/S01-home-390-light.png")
        self.assertIn("390 and 768 px wide, light and dark", by_rule["overflow"]["where"])
        self.assertEqual(by_rule["console-error"]["widths"], WIDTHS)
        self.assertIn("signed in as alice", by_rule["console-error"]["steps"])

    def test_the_worst_severity_of_a_group_wins(self):
        data = walk({("S01-home", 390, "light"): {"perf": {"lcp_ms": 2600}},
                       ("S01-home", 1440, "dark"): {"perf": {"lcp_ms": 9000}}})
        _, report = self.findings(data)
        self.assertEqual([(f["rule"], f["severity"]) for f in report["findings"]], [("lcp_ms", "high")])
        self.assertIn("9000", report["findings"][0]["actual"])

    def test_a_broken_link_is_one_finding_for_all_routes(self):
        link = {"broken_links": [{"url": "/gone", "status": 404, "text": "<a> \"Old page\""}]}
        _, report = self.findings(walk({("S01-home", 390, "light"): link, ("S03-dashboard", 390, "light"): link}))
        self.assertEqual(len(report["findings"]), 1)
        self.assertEqual(report["findings"][0]["routes"], ["S01-home", "S03-dashboard"])
        self.assertEqual(report["findings"][0]["severity"], "medium")

    def test_fail_on_and_exit_codes(self):
        data = walk({"S01-home": {"overflow_px": 5}})
        self.assertEqual(self.run_main(data)[0], 0)  # a medium finding, the default is high
        code, out, _ = self.run_main(data, "--fail-on", "medium")
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)
        self.assertIn("MEDIUM", out)
        self.assertEqual(self.run_main(walk({"S01-home": {"status": 500}}))[0], 1)

    def test_budget_file(self):
        data = walk({"*": {"perf": {"lcp_ms": 2800}}})
        self.assertEqual(self.run_main(data, "--fail-on", "medium")[0], 1)
        loose = self.write({"lcp_ms": 3000}, "budget.json")
        code, report = self.findings(data, "--fail-on", "medium", "--budget", loose)
        self.assertEqual((code, report["findings"]), (0, []))
        self.assertEqual(report["summary"]["budget"]["lcp_ms"], 3000)
        self.assertEqual(report["summary"]["budget"]["cls"], 0.1)
        strict = self.write({"requests": 5}, "strict.json")
        self.assertEqual(self.findings(data, "--budget", strict)[1]["findings"][0]["rule"], "lcp_ms")
        for bad in ({"lcp": 1}, {"lcp_ms": "fast"}, {"lcp_ms": True}, {"cls": 0}, [1], "{not json"):
            with self.subTest(bad=bad):
                code, _, err = self.run_main(data, "--budget", self.write(bad, "bad.json"))
                self.assertEqual(code, 2)
                self.assertIn("error:", err)
        self.assertEqual(self.run_main(data, "--budget", os.path.join(self.folder, "none.json"))[0], 2)

    def test_incomplete_walks_exit_2(self):
        missing = walk()
        missing["results"].pop()
        cases = {
            "no result": missing,
            "skipped": walk({("S03-dashboard", 390, "light"): {"loaded": False, "skipped": "no saved sign-in"}}),
            "did not load": walk({("S01-home", 768, "dark"): {"loaded": False, "error": "not run"}}),
            "axe: timeout": walk({("S01-home", 768, "dark"): {"incomplete": ["axe: timeout"]}}),
        }
        for words, data in cases.items():
            with self.subTest(words=words):
                code, _, err = self.run_main(data)
                self.assertEqual(code, 2)
                self.assertIn(words, err)
                self.assertIn("incomplete", err)
        code, report = self.findings(walk({"S01-home": {"status": 500},
                                             ("S01-home", 390, "light"): {"loaded": False, "error": "refused"}}))
        self.assertEqual(code, 2, "incomplete wins over a finding")
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(len(report["incomplete"]), 1)
        self.assertEqual(report["findings"][0]["rule"], "status")

    def test_bad_input_exits_2(self):
        empty = walk()
        empty["results"] = []
        no_routes = walk()
        no_routes["routes"] = []
        odd = walk()
        odd["results"][0] = "a string"
        for data in ("", "{", "[]", '{"routes": 1}', json.dumps(empty), json.dumps(no_routes), json.dumps(odd),
                     json.dumps({"routes": [1], "results": [2], "widths": [390], "schemes": ["light"]})):
            with self.subTest(data=data[:30]):
                code, out, err = self.run_main(data)
                self.assertEqual((code, out), (2, ""))
                self.assertIn("error:", err)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(walkcheck.main([os.path.join(self.folder, "missing.json")]), 2)
            self.assertEqual(walkcheck.main([self.folder]), 2)

    def test_json_shape(self):
        code, report = self.findings(walk({"S01-home": {"page_errors": ["boom"]}}))
        self.assertEqual(code, 1)
        self.assertEqual(sorted(report), ["findings", "incomplete", "summary"])
        self.assertEqual(sorted(report["findings"][0]), sorted([
            "rule", "severity", "title", "where", "routes", "path", "as", "widths", "schemes", "expected", "actual",
            "why", "fix", "screenshot", "steps", "blocks"]))
        self.assertTrue(report["findings"][0]["blocks"])
        summary = report["summary"]
        self.assertEqual((summary["routes"], summary["pages"], summary["failed"], summary["complete"]),
                         (2, 12, True, True))
        self.assertEqual(summary["by_severity"], {"critical": 0, "high": 1, "medium": 0, "low": 0})
        self.assertEqual(summary["round"], "r1")

    def test_bugs_blocks_are_read_by_bugs_py(self):
        hostile = "## B999 [critical] [open] fake `code` → [fixed] https://x.test/a?token=" + "abc" + "123"
        data = walk({"S01-home": {"page_errors": [hostile], "overflow_px": 9},
                       "S03-dashboard": {"console_errors": ["- B001 high | [open]\n## Notes"]}})
        code, out, _ = self.run_main(data, "--bugs", "--fail-on", "medium", "--next", "7", "--build", "3f2a1c9")
        self.assertEqual(code, 1)
        self.assertNotIn("abc123", out)
        self.assertTrue(out.isascii())
        found, problems = bugs.parse("# Bugs\n\n" + out + "\n## To check\n- nothing\n")
        self.assertEqual(problems, [])
        self.assertEqual([bug["id"] for bug in found], ["B007", "B008", "B009"])
        self.assertEqual([bug["severity"] for bug in found], ["high", "medium", "medium"])
        self.assertEqual({bug["status"] for bug in found}, {"open"})
        block = out.split("\n\n")[0].splitlines()
        self.assertEqual([line.split(":")[0] for line in block[1:]],
                         ["case", "steps", "expected", "actual", "evidence", "fixed in"])
        self.assertIn("build: 3f2a1c9", block[1])
        self.assertIn("forge-work/test/shots/r1/S01-home-390-light.png", block[5])

    def test_bugs_only_above_fail_on_and_not_the_known_ones(self):
        data = walk({"S01-home": {"page_errors": ["boom"], "overflow_px": 9}})
        code, out, _ = self.run_main(data, "--bugs")
        self.assertEqual((code, out.count("## B")), (1, 1))
        self.assertIn("## B001 [high] [open] S01-home: script error: \"boom\"", out)
        known = os.path.join(self.folder, "bugs.md")
        with open(known, "w", encoding="utf-8") as handle:
            handle.write("# Bugs\n\n## B004 [high] [fixed] S01-home: script error: \"boom\"\nfixed in: abc\n")
        code, out, _ = self.run_main(data, "--bugs", "--fail-on", "low", "--known", known)
        self.assertEqual(code, 1)
        self.assertEqual(out.count("## B"), 1)
        self.assertIn("## B005 [medium] [open] S01-home: the page scrolls sideways", out)
        self.assertEqual(self.run_main(data, "--bugs", "--known", os.path.join(self.folder, "no.md"))[0], 2)
        self.assertEqual(self.run_main(walk(), "--bugs"), (0, "", ""))

    def test_help_and_a_cp1252_pipe(self):
        code, out, _ = run_cp1252(SCRIPT, "--help")
        self.assertEqual(code, 0)
        self.assertIn("Exit codes", out)
        path = self.write(walk({"S01-home": {"console_errors": ["café → \U0001f600"]}}))
        code, out, err = run_cp1252(SCRIPT, path, "--fail-on", "low")
        self.assertEqual((code, err), (1, ""))
        self.assertIn("console error", out)


if __name__ == "__main__":
    unittest.main()
