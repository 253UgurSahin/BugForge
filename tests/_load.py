"""Helpers for the tests: load a script from a skill folder (the folder names have hyphens), run one
the way Windows does, and make a symlink where the system lets the tests make one."""

import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(folder, name):
    path = os.path.join(ROOT, folder, name + ".py")
    spec = importlib.util.spec_from_file_location("forge_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def symlink(test, target, link):
    """os.symlink(TARGET, LINK), or skip TEST where Windows refuses it: there only an admin or Developer
    Mode may make symlinks. Any other error fails the test."""
    try:
        os.symlink(target, link)
    except OSError as error:
        if getattr(error, "winerror", None) != 1314:  # ERROR_PRIVILEGE_NOT_HELD
            raise
        test.skipTest("Windows lets only an admin or Developer Mode make symlinks")


def run_cp1252(script, *args, cwd=None):
    """Run SCRIPT as Windows does before Python 3.15 when Claude Code reads it: its output goes into a
    pipe in cp1252, which has no arrow (U+2192) or emoji. Returns (exit code, stdout, stderr) as text,
    with Windows' \\r\\n line ends read as \\n, the way text mode reads them."""
    done = subprocess.run([sys.executable, script] + list(args), cwd=cwd, timeout=120, stdin=subprocess.DEVNULL,
                          capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
    text = [stream.decode("cp1252").replace("\r\n", "\n") for stream in (done.stdout, done.stderr)]
    return done.returncode, text[0], text[1]
