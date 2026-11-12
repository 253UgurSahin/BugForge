"""Tests for examples/serve.py, the small local server that opens the gallery: its help, a port that is
not a port, a port that is taken, and that it only ever listens on 127.0.0.1. No test starts the server
for real: serve_forever would block."""

import contextlib
import io
import os
import socket
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import REPO, load  # noqa: E402

serve = load("examples", "serve", REPO)


def run(argv):
    """Call main(ARGV); returns (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = serve.main(argv)
        except SystemExit as stop:
            code = stop.code
    return code, out.getvalue(), err.getvalue()


class ServeTests(unittest.TestCase):
    def test_help_says_what_it_does(self):
        code, out, _ = run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("127.0.0.1", out)
        self.assertIn("--port", out)
        self.assertIn("--no-open", out)

    def test_a_port_that_is_not_a_port_exits_2(self):
        for port in ("0", "70000"):
            with self.subTest(port=port):
                code, _, err = run(["--port", port, "--no-open"])
                self.assertEqual(code, 2)
                self.assertIn("not a port", err)

    def test_a_taken_port_exits_2_and_names_the_next_one(self):
        taken = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            taken.bind(("127.0.0.1", 0))
            taken.listen(1)
            port = taken.getsockname()[1]
            code, _, err = run(["--port", str(port), "--no-open"])
        finally:
            taken.close()
        self.assertEqual(code, 2)
        self.assertIn("--port %d" % (port + 1), err)

    def test_it_listens_on_this_machine_only_and_serves_its_own_folder(self):
        with open(os.path.join(REPO, "examples", "serve.py"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn('("127.0.0.1", args.port)', text)
        self.assertNotIn("0.0.0.0", text)
        self.assertEqual(serve.HERE, os.path.join(REPO, "examples"))

    def test_the_gallery_has_a_start_page(self):
        self.assertTrue(os.path.isfile(os.path.join(serve.HERE, "index.html")),
                        "serve.py opens the folder's root: examples/index.html must be there")


if __name__ == "__main__":
    unittest.main()
