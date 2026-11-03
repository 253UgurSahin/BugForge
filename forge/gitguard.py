#!/usr/bin/env python3
"""Check that forge may commit here: a git work tree on a work branch, never on main.

forge builds and fixes on its own branch, so the main line stays as the user left it.
This passes when PATH (default: the current folder) is inside a git work tree on a local
branch that is not main, master, trunk or production (in any capitals) and not the default
branch of a remote (origin/HEAD). It fails when no branch is checked out, or when a rebase,
merge, cherry-pick, revert or bisect is not finished. With --clean nothing may be changed,
staged or untracked either (ignored files are fine), so forge's commits hold only forge's
work. A new repository without commits passes once its branch is not main.

It runs only read-only git commands (rev-parse, symbolic-ref, for-each-ref, status), with
core.fsmonitor off so the repository's config cannot start a monitor program. git status may
still run the filter programs that the repository's own config names, as any git status does.
A git that does not answer is stopped, on Windows with taskkill, with all the programs it started.
GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE and GIT_COMMON_DIR are ignored: PATH picks the repository.
A gate like scope.py, not a scanner: every finding blocks, so each one is high.

Usage:
    python3 gitguard.py                     check the current folder
    python3 gitguard.py ../my-app --clean   also require no uncommitted changes
    python3 gitguard.py . --json            machine-readable output

Exit codes (the output says what to do in each case):
    0  a work branch (with --clean: and nothing uncommitted), forge may commit here
    1  not safe to commit here: a protected branch, no branch (detached HEAD), an unfinished
       rebase or merge, or with --clean uncommitted changes. Follow the fix lines.
    2  the check could not be made: git is missing or did not answer, PATH is not a folder,
       there is no repository yet (git init; in an existing project only after the user's go),
       or git refuses the repository (another owner, damaged, bare): show the user git's reason.
"""

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys

GIT = "git"  # the git command; tests point it elsewhere to act as if git is missing
TIMEOUT = 60  # seconds per git command
TASKKILL = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "taskkill.exe")  # by full path
PROTECTED = ("main", "master", "trunk", "production")
REPO_VARIABLES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")
NEW_BRANCH = "git switch -c forge/<name>"
MAX_SHOWN = 20  # uncommitted changes listed in the plain output
UNFINISHED = (  # a file git keeps while an operation waits for someone; the operation; how to end it
    ("rebase-merge", "rebase", "git rebase --continue or git rebase --abort"),
    ("rebase-apply", "rebase (or git am)", "git rebase --abort (or git am --abort)"),
    ("MERGE_HEAD", "merge", "git merge --continue or git merge --abort"),
    ("CHERRY_PICK_HEAD", "cherry-pick", "git cherry-pick --continue or git cherry-pick --abort"),
    ("REVERT_HEAD", "revert", "git revert --continue or git revert --abort"),
    ("BISECT_LOG", "bisect", "git bisect reset"),
)
# git status codes: the first letter is the staged side, the second the files on disk.
STATUS_WORDS = {"M": "changed", "T": "changed", "A": "new file", "D": "deleted",
                "R": "renamed", "C": "copied"}
CONFLICTS = ("DD", "AU", "UD", "UA", "DU", "AA", "UU")


class GitError(Exception):
    """git could not answer, so the check cannot be made (exit 2)."""


def git(path, *args):
    """Run one read-only git command inside PATH. Returns (exit code, stdout, stderr)."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0",  # git status may not rewrite the index
               LC_ALL="C")  # git's messages in English, so explain() can read them
    for name in REPO_VARIABLES:  # these would point git at another repository than PATH
        env.pop(name, None)
    command = [GIT, "-C", path, "-c", "core.fsmonitor=false"] + list(args)
    try:
        with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=env, encoding="utf-8",
                              errors="replace") as process:
            try:
                out, err = process.communicate(timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                if os.name == "nt":  # git.exe is a launcher: kill() stops it, not the git that holds the pipes
                    with contextlib.suppress(OSError, subprocess.SubprocessError):  # kill() still follows
                        subprocess.run([TASKKILL, "/F", "/T", "/PID", str(process.pid)],
                                       capture_output=True, timeout=60)
                process.kill()
                raise
    except OSError as error:  # not installed, or cannot be started
        raise GitError("cannot run git (%s). Install git, then run gitguard.py again."
                       % (error.strerror or error))
    except subprocess.TimeoutExpired:
        raise GitError("git did not answer within %d seconds in %s" % (TIMEOUT, path))
    return process.returncode, out, err


def ask(path, *args):
    """Run a git command that must work and return what it printed. GitError if it fails."""
    code, out, err = git(path, *args)
    if code != 0:
        raise GitError("git %s failed in %s: %s" % (args[0], path, first_line(err)))
    return out


def first_line(text):
    """The first non-empty line of git's error output, or a plain stand-in."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0] if lines else "no message"


def printable(text):
    """TEXT with invisible characters (newlines, escape codes) shown as <U+XXXX>, so a file
    name cannot fake a line of this report."""
    return "".join(ch if ch.isprintable() else "<U+%04X>" % ord(ch) for ch in text)


def find_dot_git(path):
    """The nearest .git at or above PATH, or None."""
    folder = os.path.abspath(path)
    while not os.path.exists(os.path.join(folder, ".git")):
        if os.path.dirname(folder) == folder:
            return None
        folder = os.path.dirname(folder)
    return os.path.join(folder, ".git")


def explain(path, message):
    """Why git refused PATH and what to do, from git's own MESSAGE (exit 2)."""
    said = "(git says: %s)" % message
    if "dubious ownership" in message or "unsafe repository" in message:
        quoted = re.search(r"'(.*)'", message)
        where = quoted.group(1) if quoted else os.path.abspath(path)
        return ("git refuses the repository at %s %s: the folder belongs to another user account "
                "than the one running git. Trusting it is the user's call: "
                "git config --global --add safe.directory %s" % (where, said, where))
    if "must be run in a work tree" in message:
        return ("%s is a bare repository or inside a .git folder, not a project folder %s. "
                "Run gitguard.py in the project folder." % (path, said))
    dot_git = find_dot_git(path)
    if "not a git repository" in message and dot_git is None:
        return ("%s is not inside a git repository %s. Start one: git init (in an existing "
                "project only after the user's go), then %s" % (path, said, NEW_BRANCH))
    return ("git cannot use the repository at %s %s. Show this to the user and do not run git "
            "init over it: the repository may be damaged." % (dot_git or path, said))


def describe(code, path=""):
    """Plain words for git's two-letter status code: '??' new file, ' M' changed,
    'D ' deleted, staged (staged means marked for the next commit)."""
    if code == "??":
        return "new folder" if path.endswith("/") else "new file"
    if code in CONFLICTS:
        return "conflict, not resolved yet"
    staged, on_disk = STATUS_WORDS.get(code[0]), STATUS_WORDS.get(code[1])
    if staged and on_disk:
        return "%s, staged, then %s" % (staged, on_disk)
    if staged:
        return staged + ", staged"
    return on_disk or code


def parse_status(out):
    """Read `git status --porcelain -z`: a list of {"code", "path", "from", "what"}.
    "from" is the old name of a renamed or copied file, else None."""
    changes, fields = [], iter(out.split("\0"))
    for entry in fields:
        if len(entry) < 4:  # the empty piece after the last NUL
            continue
        code, path = entry[:2], entry[3:]
        moved_from = next(fields, None) if "R" in code or "C" in code else None
        changes.append({"code": code, "path": path, "from": moved_from, "what": describe(code, path)})
    return changes


def remote_defaults(path):
    """{branch name in lower case: remote} for each remote's default branch (origin/HEAD)."""
    found = {}
    out = ask(path, "for-each-ref", "--format=%(refname) %(symref)", "refs/remotes/*/HEAD")
    for line in out.splitlines():
        refname, _, target = line.partition(" ")  # refs/remotes/origin/HEAD refs/remotes/origin/main
        prefix = refname[:-len("HEAD")]
        if target.startswith(prefix):
            found[target[len(prefix):].lower()] = prefix[len("refs/remotes/"):-1]
    return found


def finding(kind, title, why, fix):
    """One reason not to commit. kind: unfinished, detached, protected or uncommitted."""
    return {"severity": "high", "title": title, "where": "", "why": why, "fix": fix, "kind": kind}


def judge(branch, changes, unfinished=None, defaults=None):
    """What stops forge from committing here. Pure, so tests can call it directly.
    branch: the local branch name, or None when HEAD is not on a branch (detached).
    changes: from parse_status, or None when --clean was not asked.
    unfinished: (operation, how to end it) when a rebase, merge... waits, else None.
    defaults: {branch name in lower case: remote} for the remotes' default branches."""
    findings, defaults = [], defaults or {}
    if unfinished:  # a rebase or bisect also detaches HEAD: this finding explains that too
        findings.append(finding(
            "unfinished", "A %s is not finished" % unfinished[0],
            "git is waiting for it; a commit made now would mix forge's work into it",
            "ask the user to finish or stop it first: " + unfinished[1]))
    elif branch is None:
        findings.append(finding(
            "detached", "No branch checked out (detached HEAD)",
            "commits made now belong to no branch and are easy to lose",
            "switch to the work branch (git switch <name>) or create one: " + NEW_BRANCH))
    if branch is not None and (branch.lower() in PROTECTED or branch.lower() in defaults):
        title = "On the %s branch" % branch
        if branch.lower() not in PROTECTED:
            title += " (the default branch of %s)" % defaults[branch.lower()]
        findings.append(finding(
            "protected", title,
            "the main line stays as it is; forge works on its own branch, to review and then "
            "merge or drop", "create a branch first: " + NEW_BRANCH))
    if changes:
        findings.append(finding(
            "uncommitted", "%d uncommitted change%s" % (len(changes), "" if len(changes) == 1 else "s"),
            "forge's commits must hold only forge's work; earlier changes could get mixed in or lost",
            "commit or stash them first; never discard them. git status lists them"))
    return findings


def check(path, clean):
    """Ask git about PATH and judge it. Returns the result dict; raises GitError (exit 2)."""
    code, out, err = git(path, "rev-parse", "--show-toplevel")
    if code != 0:
        raise GitError(explain(path, first_line(err)))
    repo = os.path.normpath(out.strip())  # git writes C:/x on Windows: shown as C:\x, as the other paths are
    git_dir = ask(path, "rev-parse", "--absolute-git-dir").strip()
    # The full name (refs/heads/main), never --short: a tag called main makes that heads/main.
    code, out, err = git(path, "symbolic-ref", "--quiet", "HEAD")
    if code not in (0, 1):  # 1 means HEAD is detached
        raise GitError("git symbolic-ref failed in %s: %s" % (path, first_line(err)))
    ref = out.strip() if code == 0 else ""
    branch = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else None
    waiting = [entry[1:] for entry in UNFINISHED if os.path.exists(os.path.join(git_dir, entry[0]))]
    defaults = remote_defaults(path)
    changes = None
    if clean:
        changes = parse_status(ask(path, "status", "--porcelain", "-z", "--untracked-files=normal"))
    findings = judge(branch, changes, waiting[0] if waiting else None, defaults)
    for item in findings:
        item["where"] = repo
    return {"ok": not findings, "path": os.path.abspath(path), "repo": repo, "branch": branch,
            "clean_required": clean, "changes": changes or [], "findings": findings}


def change_line(change):
    """One uncommitted change in plain words: `app/models.py (changed)`."""
    name = change["path"] if change["from"] is None else change["from"] + " -> " + change["path"]
    return "%s (%s)" % (name, change["what"])


def format_human(result):
    """The plain-text report: PASS in one line, or one block per finding and FAIL."""
    if result["ok"]:
        clean = " Nothing uncommitted." if result["clean_required"] else ""
        return printable("PASS: work branch %s in %s.%s" % (result["branch"], result["repo"], clean))
    lines = []
    for item in result["findings"]:
        lines += ["%-8s  %s" % (item["severity"].upper(), item["title"]),
                  "          where: " + item["where"]]
        if item["kind"] == "uncommitted":
            shown = [change_line(change) for change in result["changes"][:MAX_SHOWN]]
            hidden = len(result["changes"]) - len(shown)
            if hidden:
                shown.append("... and %d more" % hidden)
            lines.append("          found: " + shown[0])
            lines += ["                 " + line for line in shown[1:]]
        lines += ["          why:   " + item["why"], "          fix:   " + item["fix"], ""]
    lines.append("FAIL: forge may not commit here yet. Fix the above, then run gitguard.py again.")
    return "\n".join(printable(line) for line in lines)


def main(argv=None):
    """Run the check from the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: escapes, no crash
    parser = argparse.ArgumentParser(description="Check that forge may commit here: a git work "
                                                 "tree on a work branch, never on main.")
    parser.add_argument("path", nargs="?", default=".",
                        help="a folder inside the git work tree (default: the current folder)")
    parser.add_argument("--clean", action="store_true",
                        help="also require no uncommitted changes (untracked files count)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.path):
        print(printable("error: %s is not a folder that exists" % args.path), file=sys.stderr)
        return 2
    try:
        result = check(args.path, args.clean)
    except GitError as error:
        print(printable("error: %s" % error), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2) if args.json else format_human(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
