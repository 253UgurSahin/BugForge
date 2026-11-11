#!/usr/bin/env python3
"""Commit one step of the build of a look: the app's own checks, gitguard and the secret scan first, then
only the files you name, with a marked block left out of a file when it belongs to a later commit.

The theme, the fonts, each component, a shell and each screen are commits of their own (restyle.md).
The styles of several screens often live in one file (app/globals.css), so each screen's rules sit in a
block of their own at the end of it: from a line with "forge: NAME" up to and with a line with "forge: end
NAME" (or the end of the file). --without FILE:NAME stages FILE without that block, so a component fix
found during a screen gets its own commit first while the screen's block waits in the work tree.

Usage:
    python3 commit.py -m "style: buttons" --check "npm test" app/globals.css components/Button.tsx
    python3 commit.py -m "style: S10 Overzicht" -m "The hero and the season strip." \\
        --check "npm run -s typecheck" --check "npm test" app/page.tsx app/globals.css
    python3 commit.py -m "style: focus ring" --check "npm test" --without "app/globals.css:screen S11" \\
        app/globals.css
    python3 commit.py -m "style: theme" --no-check app/globals.css         an app with no tests at all

Exit codes:
    0  committed: the commit and what is still uncommitted are printed
    1  not committed: a check failed (its last lines are printed), gitguard or the secret scan said no, a
       path is in forge-work/, a file not named was already staged, or the named files did not change
    2  could not run: not in a git repository, a named file that is not there, a block that is not in its
       file, a check that does not start, or neither --check nor --no-check
"""

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GUARDS = (os.path.join(HERE, os.pardir, "forge", "gitguard.py"),  # a work branch, never main
          os.path.join(HERE, os.pardir, "forge-check", "secretscan.py"))  # no key or password goes in


class Stop(Exception):
    """The commit cannot be tried (exit 2)."""


def run(command, data=None, timeout=900):
    """(exit code, output) of COMMAND, a list, without a shell; DATA goes to its input."""
    try:
        done = subprocess.run([shutil.which(command[0]) or command[0]] + command[1:], input=data, timeout=timeout,
                              stdin=None if data is not None else subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
    except OSError as error:
        raise Stop("%s did not start: %s" % (command[0], error))
    except subprocess.TimeoutExpired:
        return 1, "it took longer than %d seconds" % timeout
    return done.returncode, done.stdout.decode("utf-8", "replace")


def git(*args, **kwargs):
    return run(["git", "-c", "core.fsmonitor=false"] + list(args), timeout=120, **kwargs)


def without(path, names):
    """The bytes of PATH with each block in NAMES left out."""
    with open(path, "rb") as handle:
        lines = handle.read().splitlines(True)
    for name in names:
        opens = re.compile(r"forge: %s(?![\w-])" % re.escape(name)).search
        closes = re.compile(r"forge: end %s(?![\w-])" % re.escape(name)).search
        text = [line.decode("utf-8", "replace") for line in lines]
        start = next((i for i, line in enumerate(text) if opens(line)), None)
        if start is None:
            raise Stop('%s has no line with "forge: %s": mark the block first' % (path, name))
        end = next((i for i in range(start + 1, len(text)) if closes(text[i])), len(text) - 1)
        lines = lines[:start] + lines[end + 1:]
    return b"".join(lines)


def tail(text, count=30):
    return "\n".join("  " + line for line in text.strip().splitlines()[-count:])


def commit(args):
    if not args.check and not args.no_check:
        raise Stop("say what must pass first: --check COMMAND (the app's tests, its typecheck), or --no-check "
                   "for an app with no tests (and write that under ## Changed)")
    code, top = git("rev-parse", "--show-toplevel")
    if code:
        raise Stop("not in a git repository: run it from the app's root")
    top, paths, blocks = top.strip(), [p.replace("\\", "/") for p in args.paths], {}
    for item in args.without:
        path, _, name = item.replace("\\", "/").rpartition(":")
        if not name or path not in paths:
            raise Stop("--without takes FILE:NAME, with FILE one of the files named: %s" % item)
        blocks.setdefault(path, []).append(name)
    for path in paths:
        if "forge-work" in path.split("/"):
            print("commit: %s is in forge-work/, which never goes into git" % path)
            return 1
        if not os.path.exists(path) and git("ls-files", "--error-unmatch", "--", path)[0]:
            raise Stop("%s is not there and not in git" % path)
    named = {os.path.normcase(os.path.realpath(p)) for p in paths}
    staged = [n for n in git("diff", "--cached", "--name-only", "-z")[1].split("\0") if n and os.path.normcase(
        os.path.realpath(os.path.join(top, n))) not in named]
    if staged:
        print("commit: already staged but not named: %s. Name them, or unstage them (git restore --staged FILE)."
              % ", ".join(staged))
        return 1
    for command in args.check:  # Windows keeps the quotes of "C:\Program Files\..." in a word: take them off
        words = shlex.split(command, posix=os.name != "nt")
        code, out = run([w[1:-1] if len(w) > 1 and w[0] == w[-1] == '"' else w for w in words])
        if code:
            print("commit: the check %s failed (exit %d), nothing is committed:\n%s" % (command, code, tail(out)))
            return 1
        print("check passed: %s" % command)
    for guard in GUARDS:
        if not os.path.isfile(guard):
            raise Stop("%s is missing: run commit.py from the forge pack" % guard)
        code, out = run([sys.executable, guard, "."], timeout=300)
        if code:
            print("commit: %s said no, nothing is committed:\n%s" % (os.path.basename(guard), tail(out, 20)))
            return 1
    for path in paths:
        if path not in blocks:
            code, out = git("add", "--", path)
        else:
            code, sha = git("hash-object", "-w", "--stdin", "--path", path, data=without(path, blocks[path]))
            mode = "100755" if os.name != "nt" and os.access(path, os.X_OK) else "100644"
            where = os.path.relpath(os.path.realpath(path), os.path.realpath(top)).replace(os.sep, "/")
            code, out = (code, sha) if code else git("update-index", "--add", "--cacheinfo", "%s,%s,%s" % (
                mode, sha.strip(), where))  # --cacheinfo reads its path from the top, wherever this runs (apps/web)
        if code:
            raise Stop("git could not stage %s: %s" % (path, out.strip()))
    if git("diff", "--cached", "--quiet")[0] == 0:
        print("commit: the files named have no change to commit")
        return 1
    code, out = git("commit", "-q", "-F", "-", data="\n\n".join(args.message).encode("utf-8"))
    if code:
        print("commit: git commit failed:\n%s" % tail(out))
        return 1
    left = git("status", "--short")[1].rstrip()
    print("committed %s\n%s" % (git("log", "--oneline", "-1")[1].strip(), "still uncommitted:\n" + left if left
                                else "nothing else is uncommitted"))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("paths", nargs="+", metavar="FILE", help="the files this commit holds")
    parser.add_argument("-m", dest="message", action="append", required=True,
                        help="the subject, then each paragraph of the message (as git commit -m)")
    parser.add_argument("--check", action="append", default=[], metavar="COMMAND",
                        help="a command that must exit 0 first, such as the app's tests (again for more)")
    parser.add_argument("--no-check", action="store_true", help="the app has no tests or typecheck to run")
    parser.add_argument("--without", action="append", default=[], metavar="FILE:NAME",
                        help="stage FILE without its block NAME (again for more)")
    args = parser.parse_args(argv)
    for stream in [s for s in (sys.stdout, sys.stderr) if hasattr(s, "reconfigure")]:
        stream.reconfigure(errors="backslashreplace")
    try:
        return commit(args)
    except Stop as error:
        print("commit: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
