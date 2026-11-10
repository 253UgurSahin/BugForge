"""Tests for forge-test/shotcheck.py: two rounds of screenshots, compared pair by pair with
forge-diff/imgdiff.py. The PNGs are made here, at run time, with zlib and struct."""

import contextlib
import io
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zlib
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402

shotcheck = load("forge-test", "shotcheck")
SCRIPT = os.path.join(ROOT, "forge-test", "shotcheck.py")
WHITE, DARK, BLUE = (255, 255, 255), (30, 30, 30), (40, 110, 230)


def chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def png(path, boxes, width=120, height=160, background=WHITE):
    """Write an 8-bit RGB PNG: a plain background with filled boxes (x, y, w, h, colour) on it."""
    rows = [[background] * width for _ in range(height)]
    for x, y, w, h, colour in boxes:
        for yy in range(y, min(height, y + h)):
            for xx in range(x, min(width, x + w)):
                rows[yy][xx] = colour
    raw = b"".join(b"\x00" + bytes(value for pixel in row for value in pixel) for row in rows)
    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


PAGE = [(0, 0, 120, 20, DARK), (10, 40, 80, 6, DARK), (10, 56, 60, 6, DARK), (10, 100, 50, 20, BLUE)]
RECOLOURED = [(x, y, w, h, (120, 20, 20)) for x, y, w, h, _ in PAGE]  # the same layout, other colours
MOVED = [(0, 0, 120, 20, DARK), (60, 80, 50, 6, DARK), (30, 130, 80, 8, DARK), (70, 30, 40, 40, BLUE)]


class ShotcheckTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.before, self.after = os.path.join(self.folder, "r1"), os.path.join(self.folder, "r2")
        os.mkdir(self.before)
        os.mkdir(self.after)

    def shot(self, folder, name, boxes=PAGE, **options):
        png(os.path.join(folder, name), boxes, **options)

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = shotcheck.main([self.before, self.after] + list(args))
        return code, out.getvalue(), err.getvalue()

    def test_the_same_shots_pass(self):
        for name in ("S01-home-390-light.png", "S01-home-390-dark.png"):
            self.shot(self.before, name)
            self.shot(self.after, name)
        code, out, err = self.run_main()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("2 compared: 0 changed, 2 the same; 0 missing, 0 new.", out)

    def test_a_colour_change_alone_is_not_a_layout_change(self):
        self.shot(self.before, "a.png")
        self.shot(self.after, "a.png", RECOLOURED)
        code, out, _ = self.run_main("--json")
        report = json.loads(out)
        self.assertEqual((code, report["changed"], report["same"]), (0, [], ["a.png"]))

    def test_a_moved_layout_is_changed(self):
        self.shot(self.before, "same.png")
        self.shot(self.after, "same.png")
        self.shot(self.before, "S03-dashboard-768-light.png")
        self.shot(self.after, "S03-dashboard-768-light.png", MOVED)
        code, out, err = self.run_main()
        self.assertEqual((code, err), (1, ""))
        self.assertIn("CHANGED  S03-dashboard-768-light.png  layout score", out)
        self.assertIn("differs at", out)
        self.assertIn("2 compared: 1 changed, 1 the same", out)
        self.assertNotIn("CHANGED  same.png", out)

    def test_min_moves_the_line(self):
        self.shot(self.before, "a.png")
        self.shot(self.after, "a.png", MOVED)
        self.assertEqual(self.run_main("--min", "0")[0], 0)
        self.assertEqual(self.run_main("--min", "100")[0], 1)
        for bad in (["--min", "101"], ["--min", "-1"], ["--timeout", "0"], ["--min", "high"]):
            with self.subTest(bad=bad), self.assertRaises(SystemExit) as stopped:
                self.run_main(*bad)
            self.assertEqual(stopped.exception.code, 2)

    def test_missing_and_new_shots(self):
        for name in ("both.png", "gone.png"):
            self.shot(self.before, name)
        for name in ("both.png", "new.png"):
            self.shot(self.after, name)
        code, out, _ = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("MISSING  gone.png", out)
        self.assertIn("NEW      new.png", out)
        code, out, _ = self.run_main("--json")
        report = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual((report["only_before"], report["only_after"], report["same"]),
                         (["gone.png"], ["new.png"], ["both.png"]))

    def test_json_shape(self):
        self.shot(self.before, "a.png")
        self.shot(self.after, "a.png", MOVED)
        code, out, _ = self.run_main("--json")
        report = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(sorted(report), ["after", "before", "changed", "errors", "min", "only_after", "only_before",
                                          "same", "summary"])
        self.assertEqual(sorted(report["changed"][0]), ["height_delta_pct", "name", "regions", "score", "verdict"])
        self.assertLess(report["changed"][0]["score"], 90)
        self.assertEqual(sorted(report["changed"][0]["regions"][0]), ["h", "w", "where", "x", "y"])
        self.assertEqual(report["summary"], {"compared": 1, "changed": 1, "same": 0, "only_before": 0,
                                             "only_after": 0, "errors": 0, "differs": True})

    def test_folders_that_cannot_be_compared_exit_2(self):
        code, out, err = self.run_main()  # both empty
        self.assertEqual((code, out), (2, ""))
        self.assertIn("no PNG files", err)
        self.shot(self.before, "a.png")
        self.assertEqual(self.run_main()[0], 2)  # the first round only: a baseline, nothing to compare
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(shotcheck.main([self.before, os.path.join(self.folder, "r9")]), 2)
            self.assertEqual(shotcheck.main([os.path.join(self.before, "a.png"), self.before]), 2)
        self.assertIn("error: cannot compare", err.getvalue())

    def test_a_pair_imgdiff_cannot_read_exits_2(self):
        self.shot(self.before, "ok.png")
        self.shot(self.after, "ok.png")
        self.shot(self.before, "broken.png")
        with open(os.path.join(self.after, "broken.png"), "wb") as handle:
            handle.write(b"this is not a PNG")
        code, out, err = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn("error: broken.png could not be compared", err)
        self.assertIn("not a PNG", err)
        self.assertIn("1 compared", out)
        report = json.loads(self.run_main("--json")[1])
        self.assertEqual([pair["name"] for pair in report["errors"]], ["broken.png"])

    def test_a_pair_that_takes_too_long_exits_2(self):
        self.shot(self.before, "a.png")
        self.shot(self.after, "a.png", MOVED)
        slow = shotcheck.subprocess.TimeoutExpired("imgdiff", 1)
        with mock.patch.object(shotcheck.subprocess, "run", side_effect=slow) as run:
            code, _, err = self.run_main("--timeout", "1")
        self.assertEqual(code, 2)
        self.assertIn("took longer than 1 seconds", err)
        self.assertEqual(run.call_args[1]["timeout"], 1)
        self.assertNotIn("shell", run.call_args[1])

    def test_other_files_and_subfolders_do_not_count(self):
        self.shot(self.before, "a.png")
        self.shot(self.after, "a.png")
        os.mkdir(os.path.join(self.after, "old.png"))
        with open(os.path.join(self.after, "notes.txt"), "w") as handle:
            handle.write("not a shot")
        self.assertEqual(self.run_main()[0], 0)

    def test_help_and_a_cp1252_pipe(self):
        code, out, _ = run_cp1252(SCRIPT, "--help")
        self.assertEqual(code, 0)
        self.assertIn("Exit codes", out)
        self.shot(self.before, "a.png")
        self.shot(self.after, "a.png", MOVED)
        code, out, err = run_cp1252(SCRIPT, self.before, self.after)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("CHANGED  a.png", out)


if __name__ == "__main__":
    unittest.main()
