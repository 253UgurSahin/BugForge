"""Tests for forge/gitguard.py: a work branch passes; main, master, trunk, production, a remote's
default branch, a detached HEAD and an unfinished rebase or merge fail; with --clean uncommitted
changes fail too; no git, no repository or a repository git refuses is exit 2.
The repository tests use real git in temporary folders."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load  # noqa: E402

gitguard = load("forge", "gitguard")
SCRIPT = os.path.join(ROOT, "forge", "gitguard.py")
HAS_GIT = shutil.which("git") is not None
REAL_RUN = subprocess.run
REAL_GIT = gitguard.git
IS_ROOT = getattr(os, "geteuid", lambda: -1)() == 0
REBASE = ("rebase", "git rebase --continue or git rebase --abort")


def run(*args):
    """Run main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = gitguard.main(list(args))
    return code, out.getvalue(), err.getvalue()


def kinds(findings):
    return [item["kind"] for item in findings]


def failing(subcommand, message="fatal: something broke"):
    """A stand-in for gitguard.git where one git subcommand fails with exit 128."""
    def fake(path, *args):
        return (128, "", message + "\n") if args[0] == subcommand else REAL_GIT(path, *args)
    return mock.patch.object(gitguard, "git", side_effect=fake)


class Judge(unittest.TestCase):
    """The pure decision, without git."""

    def test_a_work_branch_passes(self):
        self.assertEqual(gitguard.judge("forge/build", None), [])
        self.assertEqual(gitguard.judge("forge/improve-20261027", []), [])

    def test_protected_branches_fail_in_any_capitals(self):
        for name in ["main", "master", "trunk", "production", "Main", "MASTER", "Production"]:
            with self.subTest(branch=name):
                found = gitguard.judge(name, None)
                self.assertEqual(kinds(found), ["protected"])
                self.assertIn(name, found[0]["title"])
                self.assertIn("git switch -c forge/<name>", found[0]["fix"])

    def test_names_that_only_contain_a_protected_word_pass(self):
        for name in ["forge/main", "main-fix", "maintenance", "feature/master-plan", "pre-production"]:
            with self.subTest(branch=name):
                self.assertEqual(gitguard.judge(name, None), [])

    def test_the_default_branch_of_a_remote_is_protected(self):
        defaults = {"develop": "origin"}
        found = gitguard.judge("Develop", None, None, defaults)
        self.assertEqual(kinds(found), ["protected"])
        self.assertIn("(the default branch of origin)", found[0]["title"])
        self.assertEqual(gitguard.judge("forge/x", None, None, defaults), [])
        self.assertNotIn("default branch", gitguard.judge("main", None, None, {"main": "origin"})[0]["title"])

    def test_a_detached_head_fails(self):
        found = gitguard.judge(None, None)
        self.assertEqual(kinds(found), ["detached"])
        self.assertIn("git switch -c forge/<name>", found[0]["fix"])

    def test_an_unfinished_operation_replaces_the_detached_advice(self):
        found = gitguard.judge(None, None, REBASE)  # git refuses git switch -c during a rebase
        self.assertEqual(kinds(found), ["unfinished"])
        self.assertEqual(found[0]["title"], "A rebase is not finished")
        self.assertIn("git rebase --abort", found[0]["fix"])
        self.assertNotIn("switch -c", found[0]["fix"])
        merge = ("merge", "git merge --continue or git merge --abort")
        self.assertEqual(kinds(gitguard.judge("forge/x", None, merge)), ["unfinished"])

    def test_changes_count_only_when_listed(self):
        self.assertEqual(gitguard.judge("forge/x", None), [])  # --clean not asked
        self.assertEqual(gitguard.judge("forge/x", []), [])  # asked, nothing found
        found = gitguard.judge("forge/x", gitguard.parse_status("?? notes.txt\0"))
        self.assertEqual(kinds(found), ["uncommitted"])
        self.assertEqual(found[0]["title"], "1 uncommitted change")
        self.assertIn("never discard", found[0]["fix"])

    def test_every_finding_is_listed_in_the_house_shape(self):
        found = gitguard.judge("main", gitguard.parse_status(" M app.py\0?? notes.txt\0"), REBASE)
        self.assertEqual(kinds(found), ["unfinished", "protected", "uncommitted"])
        self.assertEqual(found[2]["title"], "2 uncommitted changes")
        for item in found:
            self.assertEqual(set(item), {"severity", "title", "where", "why", "fix", "kind"})
            self.assertEqual(item["severity"], "high")
            self.assertTrue(item["why"] and item["fix"])


class PlainWords(unittest.TestCase):
    def test_status_codes(self):
        for code, words in [("??", "new file"), (" M", "changed"), ("M ", "changed, staged"),
                            ("MM", "changed, staged, then changed"), ("A ", "new file, staged"),
                            (" D", "deleted"), ("D ", "deleted, staged"), ("R ", "renamed, staged"),
                            (" T", "changed"), ("UU", "conflict, not resolved yet"),
                            ("AA", "conflict, not resolved yet")]:
            with self.subTest(code=code):
                self.assertEqual(gitguard.describe(code), words)
        self.assertEqual(gitguard.describe("??", "notes/"), "new folder")

    def test_status_output_with_renames_and_odd_names(self):
        changes = gitguard.parse_status(" M app.py\0R  new name.txt\0old.txt\0 R b2\0b\0"
                                        "?? café menu.txt\0")
        self.assertEqual([(c["code"], c["path"], c["from"]) for c in changes],
                         [(" M", "app.py", None), ("R ", "new name.txt", "old.txt"),
                          (" R", "b2", "b"), ("??", "café menu.txt", None)])
        self.assertEqual(gitguard.change_line(changes[1]), "old.txt -> new name.txt (renamed, staged)")
        self.assertEqual(gitguard.parse_status(""), [])

    def test_invisible_characters_are_shown(self):
        self.assertEqual(gitguard.printable("a\nPASS\x1b[0m café"), "a<U+000A>PASS<U+001B>[0m café")


class Folder(unittest.TestCase):
    """A temporary folder. Git never looks above it for a repository."""

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base)
        patcher = mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": self.base})
        patcher.start()
        self.addCleanup(patcher.stop)

    def make(self, *parts):
        path = os.path.join(self.base, *parts)
        os.makedirs(path, exist_ok=True)
        return path


@unittest.skipUnless(HAS_GIT, "git is not installed")
class Repo(Folder):
    """Real repositories. Each one starts on an unborn main branch."""

    def setUp(self):
        super().setUp()
        self.repo = self.new_repo("app")

    def git(self, repo, *args, check=True):
        config = ["-c", "commit.gpgsign=false", "-c", "user.name=forge test",
                  "-c", "user.email=test@example.invalid"]
        return REAL_RUN(["git", "-C", repo] + config + list(args), check=check, timeout=60,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def new_repo(self, name):
        repo = self.make(name)
        self.git(repo, "init", "-q")
        self.git(repo, "symbolic-ref", "HEAD", "refs/heads/main")  # whatever init.defaultBranch says
        return repo

    def write(self, name, text="hello\n"):
        path = os.path.join(self.repo, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def commit(self, name="README.md", text="hello\n"):
        self.write(name, text)
        self.git(self.repo, "add", name)
        self.git(self.repo, "commit", "-q", "--no-verify", "-m", "add " + name)

    def branch(self, name):
        self.git(self.repo, "checkout", "-q", "-b", name)

    def conflict(self):
        """main and forge/x both change README.md; forge/x is checked out."""
        self.commit()
        self.branch("forge/x")
        self.commit(text="from forge\n")
        self.git(self.repo, "checkout", "-q", "main")
        self.commit(text="from main\n")
        self.git(self.repo, "checkout", "-q", "forge/x")


class Branches(Repo):
    def test_a_work_branch_passes(self):
        self.commit()
        self.branch("forge/build")
        code, out, err = run(self.repo)
        self.assertEqual(code, 0, out + err)
        self.assertIn("PASS: work branch forge/build", out)

    def test_main_fails_with_plain_advice(self):
        self.commit()
        code, out, _ = run(self.repo)
        self.assertEqual(code, 1)
        for text in ["HIGH      On the main branch", "where: " + self.repo, "why:",
                     "fix:   create a branch first: git switch -c forge/<name>", "FAIL"]:
            self.assertIn(text, out)

    def test_each_protected_branch_fails(self):
        self.commit()
        for name in ["master", "trunk", "production"]:
            with self.subTest(branch=name):
                self.branch(name)
                code, out, _ = run(self.repo)
                self.assertEqual(code, 1)
                self.assertIn("On the %s branch" % name, out)

    def test_a_tag_with_the_branch_name_does_not_hide_it(self):
        """git symbolic-ref --short says heads/main when a tag is called main too."""
        self.commit()
        for name in ["main", "production"]:
            with self.subTest(branch=name):
                if name != "main":
                    self.branch(name)
                self.git(self.repo, "tag", name)
                code, out, _ = run(self.repo, "--json")
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(out)["branch"], name)
                self.assertIn("On the %s branch" % name, run(self.repo)[1])

    def test_head_pointing_outside_the_branches_is_no_branch(self):
        self.commit()
        self.git(self.repo, "update-ref", "refs/remotes/origin/forge/x", "HEAD")
        self.git(self.repo, "symbolic-ref", "HEAD", "refs/remotes/origin/forge/x")
        code, out, _ = run(self.repo, "--json")
        self.assertEqual(code, 1)
        self.assertEqual((json.loads(out)["branch"], kinds(json.loads(out)["findings"])),
                         (None, ["detached"]))

    def test_the_default_branch_of_a_remote_is_protected(self):
        self.commit()
        self.branch("develop")
        self.git(self.repo, "update-ref", "refs/remotes/origin/develop", "HEAD")
        self.git(self.repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop")
        code, out, _ = run(self.repo)
        self.assertEqual(code, 1)
        self.assertIn("On the develop branch (the default branch of origin)", out)
        self.branch("forge/build")
        self.assertEqual(run(self.repo)[0], 0)

    def test_a_new_repository_without_commits(self):
        self.assertEqual(run(self.repo)[0], 1)  # unborn main
        self.git(self.repo, "symbolic-ref", "HEAD", "refs/heads/forge/build")
        self.assertEqual(run(self.repo)[0], 0)  # unborn work branch

    def test_a_detached_head_fails(self):
        self.commit()
        self.git(self.repo, "checkout", "-q", "--detach")
        code, out, _ = run(self.repo)
        self.assertEqual(code, 1)
        self.assertIn("detached HEAD", out)

    def test_an_unfinished_rebase_fails_with_the_right_advice(self):
        self.conflict()
        self.assertNotEqual(self.git(self.repo, "rebase", "main", check=False).returncode, 0)
        code, out, _ = run(self.repo)
        self.assertEqual(code, 1)
        self.assertIn("A rebase is not finished", out)
        self.assertIn("git rebase --abort", out)
        self.assertNotIn("switch -c", out)  # git refuses to switch branches during a rebase

    def test_an_unfinished_merge_on_a_work_branch_fails(self):
        self.conflict()
        self.assertNotEqual(self.git(self.repo, "merge", "main", check=False).returncode, 0)
        code, out, _ = run(self.repo)  # without --clean too: a commit now would end the merge
        self.assertEqual(code, 1)
        self.assertIn("A merge is not finished", out)
        self.git(self.repo, "merge", "--abort")
        self.assertEqual(run(self.repo)[0], 0)

    def test_a_subfolder_finds_its_repository(self):
        self.commit()
        self.branch("forge/build")
        code, out, _ = run(self.make("app", "src", "deep"), "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["repo"], self.repo)

    def test_the_default_path_is_the_current_folder(self):
        self.commit()
        done = REAL_RUN([sys.executable, SCRIPT], cwd=self.repo, timeout=60, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.branch("forge/build")
        done = REAL_RUN([sys.executable, SCRIPT, "--clean"], cwd=self.repo, timeout=60,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_git_dir_in_the_environment_is_ignored(self):
        other = self.new_repo("other")
        self.git(other, "symbolic-ref", "HEAD", "refs/heads/forge/other")
        self.commit()
        with mock.patch.dict(os.environ, {"GIT_DIR": os.path.join(other, ".git")}):
            code, out, _ = run(self.repo)
        self.assertEqual(code, 1)
        self.assertIn("On the main branch", out)

    def test_the_other_repository_variables_are_ignored(self):
        """Each would make plain git see deleted, untracked or missing files here."""
        other, empty = self.new_repo("other"), self.make("empty")
        self.commit()
        self.branch("forge/build")
        for name, value in [("GIT_WORK_TREE", empty), ("GIT_INDEX_FILE", os.path.join(empty, "index")),
                            ("GIT_COMMON_DIR", os.path.join(other, ".git"))]:
            with self.subTest(variable=name), mock.patch.dict(os.environ, {name: value}):
                code, out, err = run(self.repo, "--clean")
                self.assertEqual(code, 0, out + err)


class Clean(Repo):
    def setUp(self):
        super().setUp()
        self.write(".gitignore", "forge-work/\n.env\n")
        self.commit("README.md")
        self.git(self.repo, "add", ".gitignore")
        self.git(self.repo, "commit", "-q", "--no-verify", "-m", "ignore")
        self.branch("forge/improve-20261027")

    def test_a_clean_tree_passes(self):
        code, out, _ = run(self.repo, "--clean")
        self.assertEqual(code, 0, out)
        self.assertIn("Nothing uncommitted.", out)

    def test_ignored_files_do_not_count(self):
        self.write("forge-work/state.json", "{}\n")
        self.write(".env", "APP_ENV=local\n")
        self.assertEqual(run(self.repo, "--clean")[0], 0)

    def test_each_kind_of_change_fails_only_with_clean(self):
        changes = {
            "README.md (changed)": lambda: self.write("README.md", "changed\n"),
            "new.txt (new file, staged)": lambda: (self.write("new.txt"), self.git(self.repo, "add", "new.txt")),
            "notes/ (new folder)": lambda: self.write("notes/todo.txt"),
            "README.md (deleted)": lambda: os.remove(os.path.join(self.repo, "README.md")),
        }
        for words, make_change in changes.items():
            with self.subTest(change=words):
                make_change()
                self.assertEqual(run(self.repo)[0], 0)  # without --clean: fine
                code, out, _ = run(self.repo, "--clean")
                self.assertEqual(code, 1)
                self.assertIn("1 uncommitted change", out)
                self.assertIn("found: " + words, out)
                self.assertIn("never discard them", out)
                self.git(self.repo, "reset", "-q", "--hard")
                self.git(self.repo, "clean", "-q", "-f", "-d")

    def test_main_with_changes_lists_both_findings(self):
        self.git(self.repo, "checkout", "-q", "main")
        self.write("notes.txt")
        code, out, _ = run(self.repo, "--clean")
        self.assertEqual(code, 1)
        self.assertIn("On the main branch", out)
        self.assertIn("found: notes.txt (new file)", out)

    def test_file_names_in_plain_words(self):
        self.write("café menu.txt")
        self.git(self.repo, "mv", "README.md", "LEESMIJ.md")
        out = run(self.repo, "--clean")[1]
        self.assertIn("README.md -> LEESMIJ.md (renamed, staged)", out)
        self.assertIn("café menu.txt (new file)", out)  # not "caf\303\251 menu.txt"
        self.assertNotIn("??", out)

    @unittest.skipIf(os.name == "nt", "file names cannot hold a newline on Windows")
    def test_a_file_name_cannot_fake_a_report_line(self):
        self.write("x\nPASS: all good")
        code, out, _ = run(self.repo, "--clean")
        self.assertEqual(code, 1)
        self.assertIn("x<U+000A>PASS: all good (new file)", out)
        self.assertNotIn("\nPASS", out)

    @unittest.skipIf(os.name == "nt", "the monitor command below needs a Unix shell")
    def test_the_repository_config_cannot_start_a_monitor_program(self):
        marker = os.path.join(self.base, "marker")
        self.git(self.repo, "config", "core.fsmonitor", "touch '%s'; false" % marker)
        self.assertEqual(run(self.repo, "--clean")[0], 0)
        self.assertFalse(os.path.exists(marker), "gitguard let git start core.fsmonitor")
        self.git(self.repo, "status", "--porcelain")  # proof that plain git status starts it
        if not os.path.exists(marker):
            self.skipTest("this git version does not run core.fsmonitor commands")

    def test_a_long_list_is_cut_in_plain_output_only(self):
        for number in range(25):
            self.write("file%02d.txt" % number)
        code, out, _ = run(self.repo, "--clean")
        self.assertEqual(code, 1)
        self.assertIn("25 uncommitted changes", out)
        self.assertIn("file19.txt (new file)", out)
        self.assertNotIn("file20.txt", out)
        self.assertIn("... and 5 more", out)
        self.assertEqual(len(json.loads(run(self.repo, "--clean", "--json")[1])["changes"]), 25)

    def test_json_shape(self):
        self.write("notes.txt")
        code, out, _ = run(self.repo, "--clean", "--json")
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(set(data), {"ok", "path", "repo", "branch", "clean_required", "changes",
                                     "findings"})
        self.assertEqual((data["ok"], data["branch"], data["clean_required"]),
                         (False, "forge/improve-20261027", True))
        self.assertEqual(data["changes"], [{"code": "??", "path": "notes.txt", "from": None,
                                            "what": "new file"}])
        self.assertEqual(data["findings"][0]["where"], self.repo)
        self.assertEqual(data["findings"][0]["severity"], "high")
        passed = json.loads(run(self.repo, "--json")[1])
        self.assertEqual((passed["ok"], passed["findings"], passed["changes"]), (True, [], []))

    def test_git_status_failing_is_exit_2(self):
        with open(os.path.join(self.repo, ".git", "index"), "wb") as handle:
            handle.write(b"xx")  # a damaged index
        self.assertEqual(run(self.repo)[0], 0)  # without --clean the index is not read
        code, out, err = run(self.repo, "--clean")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("git status failed", err)

    def test_it_only_runs_read_only_git_commands(self):
        calls = []

        def spy(cmd, **kwargs):
            calls.append((cmd, kwargs["env"]))
            return REAL_RUN(cmd, **kwargs)

        self.write("notes.txt")
        with mock.patch.object(gitguard.subprocess, "run", side_effect=spy):
            self.assertEqual(run(self.repo, "--clean")[0], 1)
        self.assertEqual([cmd[5] for cmd, _ in calls],
                         ["rev-parse", "rev-parse", "symbolic-ref", "for-each-ref", "status"])
        for cmd, env in calls:
            self.assertEqual(cmd[:5], [gitguard.GIT, "-C", self.repo, "-c", "core.fsmonitor=false"])
            self.assertEqual((env.get("GIT_OPTIONAL_LOCKS"), env.get("LC_ALL")), ("0", "C"))
            if cmd[5] == "symbolic-ref":
                self.assertEqual(cmd[6:], ["--quiet", "HEAD"])  # one name only reads; never --short


class BadInput(Folder):
    def test_a_missing_path(self):
        code, out, err = run(os.path.join(self.base, "missing"))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("not a folder that exists", err)

    def test_a_file_is_not_a_folder(self):
        path = os.path.join(self.base, "file.txt")
        open(path, "w").close()
        self.assertEqual(run(path)[0], 2)

    def test_git_is_missing(self):
        with mock.patch.object(gitguard, "GIT", os.path.join(self.base, "no-git-here")):
            code, out, err = run(self.base)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("Install git", err)

    def test_git_is_missing_from_the_command_line(self):
        empty = self.make("empty-bin")
        done = REAL_RUN([sys.executable, SCRIPT, self.base], env=dict(os.environ, PATH=empty),
                        timeout=60, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        universal_newlines=True)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("cannot run git", done.stderr)

    def test_git_does_not_answer(self):
        timeout = subprocess.TimeoutExpired(cmd="git", timeout=gitguard.TIMEOUT)
        with mock.patch.object(gitguard.subprocess, "run", side_effect=timeout):
            code, _, err = run(self.base)
        self.assertEqual(code, 2)
        self.assertIn("did not answer", err)

    @unittest.skipUnless(HAS_GIT, "git is not installed")
    def test_a_folder_without_a_repository(self):
        code, out, err = run(self.make("plain"))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("not inside a git repository (git says: fatal: not a git repository", err)
        self.assertIn("Start one: git init", err)

    @unittest.skipUnless(HAS_GIT, "git is not installed")
    def test_a_bare_repository_and_the_git_folder(self):
        bare = self.make("bare.git")
        REAL_RUN(["git", "init", "-q", "--bare", bare], check=True, timeout=60)
        work = self.make("work")
        REAL_RUN(["git", "init", "-q", work], check=True, timeout=60)
        for path in [bare, os.path.join(work, ".git")]:
            with self.subTest(path=path):
                code, _, err = run(path)
                self.assertEqual(code, 2)
                self.assertIn("a bare repository or inside a .git folder", err)
                self.assertNotIn("Start one", err)

    @unittest.skipUnless(HAS_GIT, "git is not installed")
    def test_a_damaged_repository_gets_no_git_init_advice(self):
        work = self.make("work")
        REAL_RUN(["git", "init", "-q", work], check=True, timeout=60)
        with open(os.path.join(work, ".git", "HEAD"), "w") as handle:
            handle.write("garbage\n")  # git now says "not a git repository"
        code, _, err = run(self.make("work", "src"))
        self.assertEqual(code, 2)
        self.assertIn("git cannot use the repository at " + os.path.join(work, ".git"), err)
        self.assertIn("do not run git init", err)
        self.assertNotIn("Start one", err)

    def test_dubious_ownership_names_the_cause(self):
        message = ("fatal: detected dubious ownership in repository at '/srv/my app'\n"
                   "To add an exception for this directory, call:")
        with mock.patch.object(gitguard, "git", return_value=(128, "", message)):
            code, out, err = run(self.base)
        self.assertEqual((code, out), (2, ""))
        for text in ["git refuses the repository at /srv/my app", "another user account",
                     "the user's call: git config --global --add safe.directory /srv/my app"]:
            self.assertIn(text, err)
        self.assertNotIn("Start one", err)

    @unittest.skipUnless(HAS_GIT and IS_ROOT, "needs git and root, to give the folder away")
    def test_dubious_ownership_for_real(self):
        trusted = REAL_RUN(["git", "-C", self.base, "config", "--get-all", "safe.directory"],
                           timeout=60, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if trusted.stdout.strip():
            self.skipTest("git trusts some folders here (safe.directory is set)")
        work = self.make("work")
        REAL_RUN(["git", "init", "-q", work], check=True, timeout=60)
        for folder, _, files in os.walk(work):
            for name in [folder] + [os.path.join(folder, file) for file in files]:
                os.chown(name, 65534, 65534)  # nobody
        code, _, err = run(work)
        self.assertEqual(code, 2)
        self.assertIn("safe.directory " + work, err)

    @unittest.skipUnless(HAS_GIT, "git is not installed")
    def test_other_git_failures_are_exit_2(self):
        work = self.make("work")
        REAL_RUN(["git", "init", "-q", work], check=True, timeout=60)
        for subcommand in ["symbolic-ref", "for-each-ref"]:
            with self.subTest(subcommand=subcommand), failing(subcommand, "fatal: boom"):
                code, out, err = run(work)
                self.assertEqual((code, out), (2, ""))
                self.assertIn("git %s failed in %s: fatal: boom" % (subcommand, work), err)


if __name__ == "__main__":
    unittest.main()
