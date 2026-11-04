"""Tests for forge/gate.py: init per mode, check through phasecheck.py (with and without a state, and with
the checks of the state's mode), done and skip with all their refusals, words made only of invisible
characters, a report older than the last go, status in plain words and JSON on any console, a damaged or
hand-edited state.json, resuming in a new process, and the atomic write. The exit checks themselves are
tested in test_phasecheck.py. Every test works in its own temporary project folder."""

import contextlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load  # noqa: E402
from test_phasecheck import HAS_GIT, OLD, PASSING, read, write  # noqa: E402

gate = load("forge", "gate")
phasecheck = load("forge", "phasecheck")
SCRIPT = os.path.join(ROOT, "forge", "gate.py")
SECRET = "const STRIPE_KEY = \"%s\";\n" % ("sk_" + "live_" + "51HxYzAbCdEfGhIjKlMnOp" * 2)  # built at runtime


class Project(unittest.TestCase):
    """A temporary project folder; gate.py runs in it as if from the project root."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def gate(self, *args):
        """Run gate.main() in the project. Returns (exit code, stdout, stderr)."""
        out, err, before = io.StringIO(), io.StringIO(), os.getcwd()
        os.chdir(self.root)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = gate.main(list(args))
        finally:
            os.chdir(before)
        return code, out.getvalue(), err.getvalue()

    def run_script(self, *args, cwd=None, env=None):
        return subprocess.run([sys.executable, SCRIPT] + list(args), cwd=cwd or self.root, timeout=120, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    def state(self):
        with open(os.path.join(self.root, "forge-work", "state.json"), encoding="utf-8") as handle:
            return json.load(handle)

    def state_text(self):
        return read(os.path.join(self.root, "forge-work", "state.json"))

    def write_state(self, text):
        write(self.root, "forge-work/state.json", text if isinstance(text, str) else json.dumps(text))

    def finish(self, *phases):
        """Leave the files of PHASES behind, as if each phase did its work."""
        for phase in phases:
            PASSING[phase](self.root)

    def approve(self, *phases):
        """Finish and mark done each of PHASES, in order."""
        for phase in phases:
            self.finish(phase)
            code, out, err = self.gate("done", phase, "--approved", "go")
            self.assertEqual(code, 0, out + err)

    def age(self, name):
        """Make NAME look written long before any go."""
        os.utime(os.path.join(self.root, name), (OLD, OLD))


class TableTests(unittest.TestCase):
    def test_modes_and_phases_follow_the_spec(self):
        self.assertEqual(gate.MODES["clone"], ["recon", "compare", "plan", "design", "build", "test", "diff",
                                               "brand", "launch", "secure", "pack"])
        self.assertEqual(gate.MODES["idea"], ["compare", "plan", "design", "build", "test", "brand", "launch",
                                              "secure", "pack"])
        self.assertEqual(gate.MODES["improve"], ["audit", "inspect", "improve", "test", "secure"])
        self.assertEqual(set(gate.OPTIONAL), {"compare", "inspect"})

    def test_every_phase_has_checks_a_skill_and_secure_is_everywhere(self):
        for mode, phases in gate.MODES.items():
            self.assertIn("secure", phases)
            for phase in phases:
                self.assertTrue(phasecheck.CHECKS[phase], phase)
                self.assertTrue(os.path.isfile(os.path.join(ROOT, "forge-" + phase, "SKILL.md")), phase)
        self.assertEqual(set(phasecheck.CHECKS), set(gate.PHASES))

    def test_hidden_characters_are_escaped_and_never_count_as_words(self):
        for char in ("\u200b", "\ufeff", "\u2060", "\u202e", "\u2028", "\x85", "\x7f", "\U000e0067"):
            with self.subTest(char=repr(char)):
                self.assertFalse(gate.shows(char + " " + char))
                self.assertNotIn(char, gate.quote("go" + char))
        for words in ("go", "\U0001f44d", "ja \U0001f44d", "\u00e9\u00e9n", "\u597d"):
            with self.subTest(words=words):
                self.assertTrue(gate.shows(words))
                self.assertEqual(gate.quote(words), '"%s"' % words)


class InitTests(Project):
    def test_init_each_mode(self):
        for mode, phases in gate.MODES.items():
            with self.subTest(mode=mode):
                shutil.rmtree(os.path.join(self.root, "forge-work"), ignore_errors=True)
                code, out, err = self.gate("init", "--mode", mode)
                self.assertEqual(code, 0, err)
                state = self.state()
                self.assertEqual((state["version"], state["mode"], state["phases"]), (1, mode, {}))
                self.assertRegex(state["started"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")
                self.assertNotIn("about", state)
                self.assertIn("Next: %s. Run /forge-%s" % (phases[0], phases[0]), out)
                self.assertIn(", ".join(phases), out)

    def test_init_keeps_what_the_user_asked_for(self):
        code, _, _ = self.gate("init", "--mode", "idea", "--about", " boekingsapp voor mijn kapsalon met iDEAL ")
        self.assertEqual(code, 0)
        self.assertEqual(self.state()["about"], "boekingsapp voor mijn kapsalon met iDEAL")
        _, out, _ = self.gate("status")
        self.assertEqual(out.splitlines()[1], 'About: "boekingsapp voor mijn kapsalon met iDEAL"')
        self.assertEqual(out.splitlines()[3].split()[:2], ["next", "compare"])
        _, out, _ = self.gate("status", "--json")
        self.assertEqual(json.loads(out)["about"], "boekingsapp voor mijn kapsalon met iDEAL")
        self.gate("init", "--mode", "idea", "--about", "\u200b", "--force")
        self.assertNotIn("about", self.state())

    def test_init_refuses_an_existing_state_unless_forced(self):
        self.gate("init", "--mode", "idea")
        self.approve("compare")
        before = self.state_text()
        code, out, _ = self.gate("init", "--mode", "clone")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", out)
        self.assertIn("--force", out)
        self.assertEqual(self.state_text(), before)
        code, _, _ = self.gate("init", "--mode", "clone", "--force")
        self.assertEqual(code, 0)
        self.assertEqual((self.state()["mode"], self.state()["phases"]), ("clone", {}))

    def test_init_keeps_forge_work_out_of_git(self):
        self.gate("init", "--mode", "clone")
        self.assertEqual(read(os.path.join(self.root, "forge-work", ".gitignore")).splitlines()[-1], "*")
        if HAS_GIT:  # screenshots and quotes of the original are never addable, not even before forge-build
            subprocess.run(["git", "init", "-q", self.root], check=True, timeout=60)
            self.finish("recon", "plan")
            status = subprocess.run(["git", "-C", self.root, "status", "--porcelain", "--untracked-files=all"],
                                    check=True, timeout=60, stdout=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(status.stdout, "")

    def test_init_needs_a_known_mode(self):
        for args in (["init"], ["init", "--mode", "deploy"]):
            with self.subTest(args=args), self.assertRaises(SystemExit) as stop:
                self.gate(*args)
            self.assertEqual(stop.exception.code, 2)
        self.assertFalse(os.path.exists(os.path.join(self.root, "forge-work")))

    def test_init_when_forge_work_is_a_file(self):
        write(self.root, "forge-work", "not a folder")
        code, out, err = self.gate("init", "--mode", "idea")
        self.assertEqual(code, 2)
        self.assertIn("error:", err)
        self.assertNotIn("Traceback", err)


class CheckTests(Project):
    def test_check_runs_the_exit_checks_without_a_state(self):
        code, out, err = self.gate("check", "plan")
        self.assertEqual((code, err), (1, ""))
        self.assertIn("FAIL: plan is not finished", out)
        self.assertEqual(out.count("forge-work/plan.md is missing"), 1)
        self.finish("plan")
        code, out, err = self.gate("check", "plan")
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("PASS: every exit check of plan passes.", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "forge-work", "state.json")))

    def test_check_json(self):
        write(self.root, "forge-work/plan.md", "Profile: next\n")
        code, out, _ = self.gate("check", "plan", "--json")
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual((data["phase"], data["ok"]), ("plan", False))

    def test_with_a_state_check_knows_the_mode(self):
        self.gate("init", "--mode", "idea")
        self.finish("recon")
        code, out, err = self.gate("check", "recon")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("recon is not a phase of idea mode", err)

    def test_the_checks_are_those_of_the_mode(self):
        """Idea mode tests the app forge built, with specs in e2e/. Improve mode tests the user's own app
        its own way: a plan that marks no case e2e (an API tested with its unit tests) needs no spec."""
        self.finish("test")
        shutil.rmtree(os.path.join(self.root, "e2e"))
        write(self.root, "forge-work/test-plan.md", read(os.path.join(self.root, "forge-work", "test-plan.md"))
              .replace("| e2e |", "| unit |"))
        self.gate("init", "--mode", "idea")
        code, out, _ = self.gate("check", "test")
        self.assertEqual(code, 1, out)
        self.assertIn("Exit checks for test (idea mode):", out)
        self.assertIn("no end-to-end spec: no file like e2e/", out)
        self.gate("init", "--mode", "improve", "--force")
        code, out, _ = self.gate("check", "test")
        self.assertEqual(code, 0, out)
        self.assertIn("Exit checks for test (improve mode):", out)

    def test_only_clone_mode_runs_the_copy_check(self):
        """copycheck.py compares the clone with the original's text that forge-recon kept (N18). Without a
        state the mode is not known, so check runs no copy check; with a clone state it does."""
        self.finish("build")
        write(self.root, "forge-work/original-text/source-1.txt", "zo zie je elke dag wat er moet gebeuren\n")
        write(self.root, "index.html", "<p>Zo zie je elke dag wat er moet gebeuren.</p>\n")
        code, out, _ = self.gate("check", "build")
        self.assertEqual(code, 0, out)
        self.assertNotIn("copycheck", out)
        self.gate("init", "--mode", "clone")
        code, out, _ = self.gate("check", "build")
        self.assertEqual(code, 1, out)
        self.assertIn("copycheck.py exits 1: it found problems", out)

    def test_with_a_state_an_old_security_report_fails(self):
        self.gate("init", "--mode", "idea")
        self.approve("compare")
        self.finish("secure")
        self.age("forge-work/security.md")
        code, out, _ = self.gate("check", "secure")
        self.assertEqual(code, 1)
        self.assertIn("forge-work/security.md is older than the last go (%s)" % self.state()["phases"]["compare"]["at"],
                      out)
        self.finish("secure")
        self.assertEqual(self.gate("check", "secure")[0], 0)

    def test_a_check_that_hangs_or_cannot_run_fails(self):
        hung = subprocess.TimeoutExpired(cmd="phasecheck.py", timeout=gate.TIMEOUT)
        with mock.patch.object(gate.subprocess, "run", side_effect=hung):
            code, out, _ = self.gate("check", "plan")
        self.assertEqual(code, 1)
        self.assertIn("FAIL: the exit checks of plan did not finish within %d seconds." % gate.TIMEOUT, out)
        self.finish("plan")
        with mock.patch.object(gate, "__file__", os.path.join(self.root, "nowhere", "forge", "gate.py")):
            code, _, err = self.gate("check", "plan")
        self.assertEqual(code, 1)
        self.assertIn("phasecheck.py", err)

    def test_unknown_phase(self):
        with self.assertRaises(SystemExit) as stop, contextlib.redirect_stderr(io.StringIO()):
            self.gate("check", "deploy")
        self.assertEqual(stop.exception.code, 2)


class DoneTests(Project):
    def setUp(self):
        super().setUp()
        self.gate("init", "--mode", "clone")

    def test_done_records_the_words_and_the_time(self):
        self.finish("recon")
        code, out, _ = self.gate("done", "recon", "--approved", "  ja, ga door \u00e9n snel  ")
        self.assertEqual(code, 0, out)
        entry = self.state()["phases"]["recon"]
        self.assertEqual((entry["status"], entry["approved"]), ("done", "ja, ga door \u00e9n snel"))
        self.assertRegex(entry["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")
        self.assertIn('Recorded: recon done. The user said: "ja, ga door \u00e9n snel"', out)
        self.assertIn("Next: compare.", out)
        self.assertIn("\u00e9n", self.state_text())  # stored as the user wrote it

    def test_done_refuses_without_words(self):
        self.finish("recon")
        for words in ("", "   ", "<their exact words>", "<the user's exact words>", "TEXT", "{{go}}",
                      "\u200b", "\ufeff", "\u2060", "\u200b \u2060\n", "\u00a0", "\u3000"):
            with self.subTest(words=repr(words)):
                code, out, _ = self.gate("done", "recon", "--approved", words)
                self.assertEqual(code, 1)
                self.assertIn("REFUSED: --approved needs the user's own words of go", out)
        self.assertEqual(self.state()["phases"], {})
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.gate("done", "recon")

    def test_an_emoji_is_a_go(self):
        self.finish("recon")
        code, out, _ = self.gate("done", "recon", "--approved", "\U0001f44d")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state()["phases"]["recon"]["approved"], "\U0001f44d")

    def test_words_that_are_not_text_are_not_stored(self):
        self.finish("recon")
        before = self.state_text()
        code, out, err = self.gate("done", "recon", "--approved", "go \udcff")  # bytes that were not UTF-8
        self.assertEqual(code, 2)
        self.assertIn("error:", err)
        self.assertEqual(self.state_text(), before)
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "forge-work"))),
                         [".gitignore", "features.csv", "recon.md", "state.json"])

    def test_done_refuses_while_a_check_fails(self):
        write(self.root, "forge-work/recon.md", "# Recon\n")
        code, out, _ = self.gate("done", "recon", "--approved", "go")
        self.assertEqual(code, 1)
        self.assertIn("FAIL  forge-work/features.csv is missing", out)
        self.assertIn("REFUSED: recon stays open until every check passes.", out)
        self.assertEqual(self.state()["phases"], {})

    def test_done_refuses_out_of_order(self):
        self.finish("recon", "plan")
        code, out, _ = self.gate("done", "plan", "--approved", "go")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED: plan comes after recon, compare", out)
        self.approve("recon")
        code, out, _ = self.gate("done", "plan", "--approved", "go")
        self.assertEqual(code, 1)
        self.assertIn("plan comes after compare:", out)
        self.assertNotIn("Exit checks", out)  # the order is refused before any check runs
        self.approve("compare", "plan")
        self.assertEqual(list(self.state()["phases"]), ["recon", "compare", "plan"])

    def test_done_refuses_a_phase_of_another_mode(self):
        self.finish("audit")
        code, out, err = self.gate("done", "audit", "--approved", "go")
        self.assertEqual(code, 2)
        self.assertIn("audit is not a phase of clone mode", err)

    def test_done_again_and_done_after_a_skip(self):
        self.approve("recon")
        self.gate("skip", "compare", "--reason", "no time")
        self.approve("compare", "recon")
        self.assertEqual(self.state()["phases"]["compare"]["status"], "done")
        self.assertEqual(self.state()["phases"]["recon"]["status"], "done")

    def test_a_whole_mode_end_to_end(self):
        shutil.rmtree(os.path.join(self.root, "forge-work"))
        self.gate("init", "--mode", "idea")
        self.approve(*gate.MODES["idea"])
        code, out, _ = self.gate("status")
        self.assertEqual(code, 0)
        self.assertIn("All phases are done.", out)
        self.assertEqual(out.count("\ndone "), len(gate.MODES["idea"]))
        self.assertNotIn("\nnext ", out)


class FreshReportTests(Project):
    """A security.md from the build or from an earlier round, or a parity.md from before test's fixes,
    says nothing about the app as it is now."""

    def test_the_build_report_is_not_the_secure_phase(self):
        self.gate("init", "--mode", "idea")
        self.approve("compare", "plan", "design", "build")  # forge-build runs forge-secure at its end
        self.age("forge-work/security.md")  # so this report is from then, before test, brand and launch
        self.approve("test", "brand", "launch")
        code, out, _ = self.gate("done", "secure", "--approved", "go")
        self.assertEqual(code, 1)
        self.assertIn("forge-work/security.md is older than the last go (%s)" % self.state()["phases"]["launch"]["at"],
                      out)
        self.assertNotIn("secure", self.state()["phases"])
        self.approve("secure")  # forge-secure ran again: a new report

    def test_a_report_from_an_earlier_round_does_not_count(self):
        self.finish("audit", "test", "secure")
        self.age("forge-work/security.md")
        self.gate("init", "--mode", "improve", "--force")
        self.approve("audit")
        self.gate("skip", "inspect", "--reason", "no live url")
        if HAS_GIT:
            self.approve("improve")
        else:
            self.skipTest("the improve phase runs gitguard.py, which needs git")
        self.approve("test")
        code, out, _ = self.gate("done", "secure", "--approved", "go")
        self.assertEqual(code, 1)
        self.assertIn("is older than the last go", out)

    def test_a_parity_report_from_before_tests_go_does_not_count(self):
        """test's fix loop changes the clone, so diff must score it after test's go (N26, N27)."""
        self.gate("init", "--mode", "clone")
        self.approve("recon", "compare", "plan", "design", "build", "test")
        self.finish("diff")
        self.age("forge-work/parity.md")  # written before test's fixes
        code, out, _ = self.gate("done", "diff", "--approved", "go")
        self.assertEqual(code, 1)
        self.assertIn("forge-work/parity.md is older than the last go (%s)" % self.state()["phases"]["test"]["at"], out)
        self.assertNotIn("diff", self.state()["phases"])
        self.approve("diff")  # forge-diff ran again from its Step 1: a new report

    def test_a_secret_added_after_secure_stops_pack(self):
        self.gate("init", "--mode", "idea")
        self.approve(*gate.MODES["idea"][:-1])
        self.finish("pack")
        write(self.root, "app.js", SECRET)
        code, out, _ = self.gate("done", "pack", "--approved", "go pack")
        self.assertEqual(code, 1)
        self.assertIn("secretscan.py . exits 1: it found problems", out)
        self.assertNotIn("pack", self.state()["phases"])


class SkipTests(Project):
    def test_skip_an_optional_phase(self):
        self.gate("init", "--mode", "clone")
        self.approve("recon")
        code, out, _ = self.gate("skip", "compare", "--reason", "geen concurrenten de moeite waard")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state()["phases"]["compare"]["reason"], "geen concurrenten de moeite waard")
        self.assertIn("Next: plan.", out)

    def test_skip_inspect_in_improve_mode(self):
        self.gate("init", "--mode", "improve")
        self.approve("audit")
        code, out, _ = self.gate("skip", "inspect", "--reason", "no UI")
        self.assertEqual(code, 0, out)
        self.assertIn("Next: improve.", out)

    def test_secure_is_never_skipped(self):
        for mode in gate.MODES:
            with self.subTest(mode=mode):
                self.gate("init", "--mode", mode, "--force")
                code, out, _ = self.gate("skip", "secure", "--reason", "the user is in a hurry")
                self.assertEqual(code, 1)
                self.assertIn("REFUSED: secure can never be skipped", out)
                self.assertEqual(self.state()["phases"], {})

    def test_required_phases_are_never_skipped(self):
        self.gate("init", "--mode", "clone")
        for phase in ("recon", "plan", "design", "build", "test", "diff", "brand", "launch", "pack"):
            with self.subTest(phase=phase):
                code, out, _ = self.gate("skip", phase, "--reason", "not needed")
                self.assertEqual(code, 1)
                self.assertIn("REFUSED: %s cannot be skipped. Only compare and inspect may be." % phase, out)
        self.assertEqual(self.state()["phases"], {})

    def test_skip_refuses_no_reason_out_of_order_and_other_modes(self):
        self.gate("init", "--mode", "clone")
        code, out, _ = self.gate("skip", "compare", "--reason", "go")
        self.assertEqual(code, 1)
        self.assertIn("compare comes after recon", out)
        self.approve("recon")
        for reason in ("", "  ", "<their reason>", "\u2060", "\u200b\ufeff"):
            code, out, _ = self.gate("skip", "compare", "--reason", reason)
            self.assertEqual(code, 1)
            self.assertIn("--reason needs the user's reason", out)
        code, _, err = self.gate("skip", "inspect", "--reason", "no UI")
        self.assertEqual(code, 2)
        self.assertIn("inspect is not a phase of clone mode", err)
        self.assertEqual(list(self.state()["phases"]), ["recon"])


class StatusTests(Project):
    def test_status_in_plain_words(self):
        self.gate("init", "--mode", "clone")
        self.approve("recon")
        self.gate("skip", "compare", "--reason", "nothing to compare")
        code, out, err = self.gate("status")
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("forge, clone mode, started "))
        table = [line.split()[:2] for line in lines[2:13]]
        self.assertEqual(table, [["done", "recon"], ["skipped", "compare"], ["next", "plan"]]
                         + [["waiting", phase] for phase in gate.MODES["clone"][3:]])
        self.assertIn('approved: "go"', lines[2])
        self.assertIn('reason: "nothing to compare"', lines[3])
        self.assertIn("/forge-plan", lines[4])
        self.assertIn("Next: plan. Run /forge-plan, then %s " % gate.PYTHON, out)
        self.assertIn("done plan --approved '<their exact words>'", out)
        # One stop per phase (N10): the skill's own checkpoint, and one line more for the gate.
        self.assertIn("Show the user the skill's checkpoint plus one line with the gate result, and wait", out)

    def test_the_printed_commands_run_on_this_machine(self):
        """python3 on macOS and Linux. Windows has no python3 (only python and py): there the commands
        start with this Python's own path, quoted for Git Bash, the shell Claude Code uses there."""
        self.gate("init", "--mode", "improve")
        _, out, _ = self.gate("status")
        command = shlex.split(re.search(r"then (.+?) check audit\.", out).group(1))
        self.assertEqual(command, [sys.executable if os.name == "nt" else "python3", SCRIPT])
        done = subprocess.run(command + ["status"], cwd=self.root, timeout=120, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("forge, improve mode", done.stdout)

    def test_status_offers_skip_only_for_optional_phases(self):
        self.gate("init", "--mode", "improve")
        _, out, _ = self.gate("status")
        self.assertIn("audit --approved", out)
        self.assertNotIn("skip audit", out)
        self.approve("audit")
        _, out, _ = self.gate("status")
        self.assertIn("skip inspect --reason '<their reason>'", out)

    def test_hidden_characters_in_the_words_cannot_fake_a_line(self):
        self.gate("init", "--mode", "idea")
        self.finish("compare")
        self.gate("done", "compare", "--approved", "go\ndone     plan  \x1b[2J\u200b\u202e\u2028!")
        _, out, _ = self.gate("status")
        self.assertIn('"go\\ndone     plan  \\u001b[2J\\u200b\\u202e\\u2028!"', out)
        for char in ("\x1b", "\u200b", "\u202e", "\u2028"):
            self.assertNotIn(char, out)
        self.assertIn("\nnext     plan", out)

    def test_status_json(self):
        self.gate("init", "--mode", "improve")
        self.approve("audit")
        code, out, _ = self.gate("status", "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["mode"], "improve")
        self.assertEqual([(row["phase"], row["status"]) for row in data["phases"]],
                         [("audit", "done"), ("inspect", "next"), ("improve", "waiting"), ("test", "waiting"),
                          ("secure", "waiting")])
        self.assertEqual(data["phases"][0]["approved"], "go")
        self.assertTrue(data["phases"][1]["optional"])
        self.assertEqual(data["phases"][1]["skill"], "forge-inspect")
        self.assertIn("Next: inspect.", data["next_step"])

    def test_no_state_yet(self):
        code, out, err = self.gate("status")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("no forge state in", err)
        self.assertIn("gate.py init", err)


class ConsoleTests(Project):
    def test_a_console_that_cannot_show_the_words_never_crashes(self):
        cp1252 = dict(os.environ, PYTHONIOENCODING="cp1252")  # Windows before Python 3.15, with a pipe
        self.assertEqual(self.run_script("init", "--mode", "improve", "--about", "mijn app \u2615",
                                         env=cp1252).returncode, 0)
        self.finish("audit")
        done = self.run_script("done", "audit", "--approved", "ja \U0001f44d", env=cp1252)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('Recorded: audit done. The user said: "ja \\U0001f44d"', done.stdout)
        self.assertEqual(self.state()["phases"]["audit"]["approved"], "ja \U0001f44d")
        status = self.run_script("status", env=cp1252)
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertIn('approved: "ja \\U0001f44d"', status.stdout)
        status = self.run_script("status", "--json", env=cp1252)
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["phases"][0]["approved"], "ja \U0001f44d")
        self.assertEqual(json.loads(status.stdout)["about"], "mijn app \u2615")

    def test_help_shows_the_exit_codes(self):
        done = self.run_script("--help")
        self.assertEqual(done.returncode, 0)
        self.assertIn("Exit codes:", done.stdout)
        self.assertIn("gate.py done plan --approved", done.stdout)


class DamagedStateTests(Project):
    GO = {"status": "done", "approved": "go", "at": "2026-10-27T09:51:44+00:00"}
    START = "2026-10-27T09:00:00+00:00"
    DAMAGED = [
        "{not json",
        "",
        "[]",
        "[" * 200000 + "]" * 200000,
        {"mode": "clone", "phases": {}, "started": START},
        {"version": 2, "mode": "clone", "phases": {}, "started": START},
        {"version": True, "mode": "clone", "phases": {}, "started": START},
        {"version": 1.0, "mode": "clone", "phases": {}, "started": START},
        {"version": 1, "mode": "deploy", "phases": {}, "started": START},
        {"version": 1, "mode": ["clone"], "phases": {}, "started": START},
        {"version": 1, "mode": {"clone": 1}, "phases": {}, "started": START},
        {"version": 1, "mode": "clone", "phases": [], "started": START},
        {"version": 1, "mode": "clone", "started": START},
        {"version": 1, "mode": "clone", "phases": {}},
        {"version": 1, "mode": "clone", "phases": {}, "started": "yesterday"},
        {"version": 1, "mode": "clone", "phases": {}, "started": "2026-11-31T09:00:00+00:00"},  # no such day
        {"version": 1, "mode": "clone", "phases": {"audit": GO}, "started": START},
        {"version": 1, "mode": "clone", "phases": {"recon": dict(GO, status="maybe")}, "started": START},
        {"version": 1, "mode": "clone", "phases": {"recon": dict(GO, status=["done"])}, "started": START},
        {"version": 1, "mode": "clone", "phases": {"recon": {"status": "done", "at": GO["at"]}}, "started": START},
        {"version": 1, "mode": "clone", "phases": {"recon": dict(GO, approved=" ")}, "started": START},
        {"version": 1, "mode": "clone", "phases": {"recon": dict(GO, approved=["go"])}, "started": START},
        {"version": 1, "mode": "clone", "phases": {"recon": dict(GO, approved="\u200b")}, "started": START},
        {"version": 1, "mode": "clone", "phases": {"recon": dict(GO, approved="<their exact words>")},
         "started": START},
        {"version": 1, "mode": "clone", "phases": {"recon": {"status": "done", "approved": "go"}}, "started": START},
        {"version": 1, "mode": "clone", "phases": {"recon": dict(GO, at=5)}, "started": START},
        {"version": 1, "mode": "clone", "phases": {"recon": dict(GO, at="2026-10-27T25:51:44+00:00")},  # hour 25
         "started": START},
        {"version": 1, "mode": "clone", "phases": {"recon": dict(GO, at="2026-10-27T09:51:44+99:99")},  # no such zone
         "started": START},
        {"version": 1, "mode": "clone", "phases": {"recon": "done"}, "started": START},
        {"version": 1, "mode": "clone", "phases": {"compare": {"status": "skipped", "reason": "", "at": GO["at"]}},
         "started": START},
        {"version": 1, "mode": "clone", "phases": {"recon": GO, "secure": {"status": "skipped", "reason": "hurry",
                                                                          "at": GO["at"]}}, "started": START},
        {"version": 1, "mode": "improve", "phases": {"secure": GO}, "started": START},  # a gap: the gate never
        {"version": 1, "mode": "clone", "phases": {"recon": GO, "plan": GO}, "started": START},  # writes one
    ]

    def test_every_command_stops_with_a_plain_message(self):
        for state in self.DAMAGED:
            self.write_state(state)
            for args in (["status"], ["status", "--json"], ["done", "recon", "--approved", "go"],
                         ["skip", "compare", "--reason", "x"], ["check", "recon"]):
                with self.subTest(state=str(state)[:120], args=args):
                    code, out, err = self.gate(*args)
                    self.assertEqual((code, out), (2, ""))
                    self.assertIn(os.path.join("forge-work", "state.json") + " is damaged", err)
                    self.assertIn("Do not guess", err)
                    self.assertIn("--force", err)

    def test_a_state_as_the_gate_writes_it_is_fine(self):
        self.write_state({"version": 1, "mode": "improve", "phases": {"audit": self.GO}, "started": self.START})
        code, out, err = self.gate("status")
        self.assertEqual((code, err), (0, ""))
        self.assertIn("Next: inspect.", out)

    def test_unreadable_states(self):
        os.makedirs(os.path.join(self.root, "forge-work", "state.json"))
        code, _, err = self.gate("status")
        self.assertEqual(code, 2)
        self.assertIn("is damaged", err)
        os.rmdir(os.path.join(self.root, "forge-work", "state.json"))
        with open(os.path.join(self.root, "forge-work", "state.json"), "wb") as handle:
            handle.write(b'{"version": 1, "mode": "\xff"}')
        code, _, err = self.gate("status")
        self.assertEqual(code, 2)
        self.assertIn("is damaged", err)

    def test_the_command_line_shows_no_traceback(self):
        for state in ("{not json", {"version": 1, "mode": ["clone"], "phases": {}}, "[" * 200000 + "]" * 200000):
            with self.subTest(state=str(state)[:40]):
                self.write_state(state)
                done = self.run_script("status")
                self.assertEqual(done.returncode, 2)
                self.assertNotIn("Traceback", done.stderr)
                self.assertTrue(done.stderr.startswith("error: "))

    def test_init_keeps_a_damaged_state_until_forced(self):
        self.write_state("{not json")
        code, _, _ = self.gate("init", "--mode", "idea")
        self.assertEqual(code, 1)
        self.assertEqual(self.state_text(), "{not json")
        code, _, _ = self.gate("init", "--mode", "idea", "--force")
        self.assertEqual(code, 0)
        self.assertEqual(self.state()["phases"], {})


class ResumeTests(Project):
    def test_a_new_session_picks_up_where_the_last_one_stopped(self):
        self.assertEqual(self.run_script("init", "--mode", "clone").returncode, 0)
        self.finish("recon")
        self.assertEqual(self.run_script("done", "recon", "--approved", "ga door").returncode, 0)
        self.assertEqual(self.run_script("skip", "compare", "--reason", "no rivals").returncode, 0)
        status = self.run_script("status")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertIn("next     plan", status.stdout)
        self.assertIn("Next: plan. Run /forge-plan", status.stdout)
        self.assertIn(SCRIPT, status.stdout)  # the commands name this script by its full path
        self.finish("plan")
        self.assertEqual(self.run_script("done", "plan", "--approved", "prima").returncode, 0)
        self.assertEqual(json.loads(self.run_script("status", "--json").stdout)["phases"][3]["status"], "next")

    def test_from_another_folder_there_is_no_state(self):
        self.run_script("init", "--mode", "idea")
        os.makedirs(os.path.join(self.root, "src"))
        done = self.run_script("status", cwd=os.path.join(self.root, "src"))
        self.assertEqual(done.returncode, 2)
        self.assertIn("Run gate.py in the project root", done.stderr)


class SaveTests(Project):
    def test_no_temporary_files_are_left(self):
        self.gate("init", "--mode", "idea")
        self.approve("compare")
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "forge-work"))),
                         [".gitignore", "compare.md", "state.json"])

    def test_a_failed_write_keeps_the_old_state(self):
        self.gate("init", "--mode", "idea")
        before = self.state_text()
        self.finish("compare")
        with mock.patch.object(gate.os, "replace", side_effect=OSError("disk full")):
            code, out, err = self.gate("done", "compare", "--approved", "go")
        self.assertEqual(code, 2)
        self.assertIn("disk full", err)
        self.assertEqual(self.state_text(), before)
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "forge-work"))),
                         [".gitignore", "compare.md", "state.json"])


if __name__ == "__main__":
    unittest.main()
