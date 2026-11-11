"""Tests for forge-design/commit.py: the app's checks, gitguard and the secret scan come first; only the
files named are committed; a marked block can wait for a later commit; forge-work/, files staged before,
a protected branch and an unchanged file stop it; and the exit codes. Real git in temporary folders."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load  # noqa: E402

commit = load("forge-design", "commit")
SCRIPT = os.path.join(ROOT, "forge-design", "commit.py")
HAS_GIT = shutil.which("git") is not None
PASS = '"%s" -c "import sys; sys.exit(0)"' % sys.executable
FAIL = '"%s" -c "import sys; print(\'3 tests failed\'); sys.exit(3)"' % sys.executable
CSS = ".btn { color: red; }\n"
BLOCK = "/* forge: screen S11 Kaart */\n.kaart { background: blue; }\n/* forge: end screen S11 Kaart */\n"


@unittest.skipUnless(HAS_GIT, "needs git")
class Commit(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "test")
        self.git("config", "core.autocrlf", "false")
        self.git("checkout", "-q", "-b", "forge/redesign-20261111")
        self.write("app/globals.css", CSS)
        self.write("components/Button.tsx", "export const Button = 1;\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "start")

    def git(self, *args):
        done = subprocess.run(["git", "-C", self.root] + list(args), check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        return done.stdout

    def write(self, path, text):
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def committed(self, path):
        return self.git("show", "HEAD:" + path)

    def run_it(self, *args, **where):
        done = subprocess.run([sys.executable, SCRIPT] + list(args), cwd=where.get("cwd", self.root), timeout=300,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return done.returncode, done.stdout, done.stderr

    def test_only_the_named_files_are_committed(self):
        self.write("app/globals.css", ".btn { color: var(--color-accent); }\n")
        self.write("components/Button.tsx", "export const Button = 2;\n")
        code, out, err = self.run_it("-m", "style: theme", "-m", "The tokens.", "--check", PASS, "app/globals.css")
        self.assertEqual(code, 0, out + err)
        self.assertIn("check passed", out)
        self.assertIn("still uncommitted:\n M components/Button.tsx", out)
        self.assertEqual(self.committed("app/globals.css"), ".btn { color: var(--color-accent); }\n")
        self.assertEqual(self.committed("components/Button.tsx"), "export const Button = 1;\n")
        self.assertEqual(self.git("log", "-1", "--format=%B").strip(), "style: theme\n\nThe tokens.")

    def test_a_failing_check_commits_nothing(self):
        self.write("app/globals.css", ".btn { color: blue; }\n")
        code, out, _ = self.run_it("-m", "style: buttons", "--check", PASS, "--check", FAIL, "app/globals.css")
        self.assertEqual(code, 1)
        self.assertIn("failed (exit 3)", out)
        self.assertIn("3 tests failed", out)
        self.assertEqual(self.committed("app/globals.css"), CSS)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")

    def test_a_block_waits_for_its_own_commit(self):
        self.write("app/globals.css", ".btn { color: green; }\n" + BLOCK)
        code, out, err = self.run_it("-m", "style: buttons, the focus ring", "--no-check",
                                     "--without", "app/globals.css:screen S11", "app/globals.css")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.committed("app/globals.css"), ".btn { color: green; }\n")
        self.assertIn(" M app/globals.css", out)  # the block is still in the work tree, for the screen's commit
        code, out, err = self.run_it("-m", "style: S11 Kaart", "--no-check", "app/globals.css")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.committed("app/globals.css"), ".btn { color: green; }\n" + BLOCK)

    def test_a_block_runs_to_the_end_of_the_file_without_an_end_line(self):
        self.write("app/globals.css", CSS + "/* forge: screen S12 */\n.water { color: teal; }\n")
        self.write("components/Button.tsx", "export const Button = 3;\n")
        code, out, err = self.run_it("-m", "style: buttons", "--no-check", "--without", "app/globals.css:screen S12",
                                     "app/globals.css", "components/Button.tsx")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.committed("app/globals.css"), CSS)
        self.assertEqual(self.committed("components/Button.tsx"), "export const Button = 3;\n")

    def test_what_stops_it(self):
        self.write("forge-work/design/redesign.md", "# notes\n")
        self.assertEqual(self.run_it("-m", "x", "--no-check", "forge-work/design/redesign.md")[0], 1)
        self.assertEqual(self.run_it("-m", "x", "--no-check", "app/globals.css")[0], 1)  # nothing changed
        self.write("components/Button.tsx", "export const Button = 4;\n")
        self.git("add", "components/Button.tsx")
        self.write("app/globals.css", ".btn { color: blue; }\n")
        code, out, _ = self.run_it("-m", "x", "--no-check", "app/globals.css")
        self.assertEqual(code, 1)
        self.assertIn("already staged but not named: components/Button.tsx", out)

    def test_a_secret_stops_it(self):
        self.write("app/pay.ts", 'const key = "%s";\n' % ("sk_" + "live_" + "a1B2c3D4e5F6g7H8i9J0k1L2"))
        code, out, _ = self.run_it("-m", "style: pay", "--no-check", "app/pay.ts")
        self.assertEqual(code, 1)
        self.assertIn("secretscan.py said no", out)
        self.assertEqual(self.git("log", "--oneline").count("\n"), 1)

    def test_a_protected_branch_stops_it(self):
        self.git("checkout", "-q", "-b", "main")
        self.write("app/globals.css", ".btn { color: blue; }\n")
        code, out, _ = self.run_it("-m", "style: buttons", "--no-check", "app/globals.css")
        self.assertEqual(code, 1)
        self.assertIn("gitguard.py said no", out)

    def test_could_not_run(self):
        self.write("app/globals.css", ".btn { color: blue; }\n")
        self.assertEqual(self.run_it("-m", "x", "app/globals.css")[0], 2)  # neither --check nor --no-check
        self.assertEqual(self.run_it("-m", "x", "--no-check", "app/nothing.css")[0], 2)
        self.assertEqual(self.run_it("-m", "x", "--no-check", "--without", "app/globals.css:screen S9",
                                     "app/globals.css")[0], 2)  # no such block
        self.assertEqual(self.run_it("-m", "x", "--no-check", "--without", "other.css:S9", "app/globals.css")[0], 2)
        code, _, err = self.run_it("-m", "x", "--check", "no-such-command-anywhere", "app/globals.css")
        self.assertEqual(code, 2)
        self.assertIn("did not start", err)
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        done = subprocess.run([sys.executable, SCRIPT, "-m", "x", "--no-check", "a.css"], cwd=outside, timeout=60,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("not in a git repository", done.stderr)

    def test_from_a_folder_inside_the_repository(self):
        """A monorepo: the app in apps/web, the repository's top two folders up. The block left out once went
        to a new app/globals.css at the top, and the app's own file stayed as it was."""
        self.write("apps/web/app/globals.css", CSS)
        self.git("add", "-A")
        self.git("commit", "-qm", "the web app")
        self.write("apps/web/app/globals.css", ".btn { color: green; }\n" + BLOCK)
        code, out, err = self.run_it("-m", "style: buttons", "--no-check", "--without", "app/globals.css:screen S11",
                                     "app/globals.css", cwd=os.path.join(self.root, "apps", "web"))
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.committed("apps/web/app/globals.css"), ".btn { color: green; }\n")
        self.assertEqual(self.committed("app/globals.css"), CSS)  # the top's own file is not touched
        self.assertIn(" M app/globals.css", out)  # the block waits in the work tree (status names it from apps/web)

    def test_without_drops_only_its_own_block(self):
        path = os.path.join(self.root, "x.css")
        self.write("x.css", "a\n/* forge: S1 */\nb\n/* forge: end S1 */\n/* forge: S10 */\nc\n")
        self.assertEqual(commit.without(path, ["S1"]), b"a\n/* forge: S10 */\nc\n")
        self.assertEqual(commit.without(path, ["S10"]), b"a\n/* forge: S1 */\nb\n/* forge: end S1 */\n")


if __name__ == "__main__":
    unittest.main()
