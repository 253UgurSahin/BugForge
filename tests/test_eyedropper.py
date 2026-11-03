"""Tests for forge-design/eyedropper.py: exact colours off a PNG (every PNG filter and colour type it
reads), the most used colours of an image or an area, single pixels, the grey of the same lightness,
the colour profile warning and the files it refuses."""

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402

eyedropper = load("forge-design", "eyedropper")
contrast = load("forge-design", "contrast")


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = eyedropper.main(list(args))
    return code, out.getvalue(), err.getvalue()


def chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def png(path, pixels, colour=2, filters=(0,), extra=b"", depth=8, interlace=0, palette=None):
    """Write PIXELS (rows of tuples) as a PNG, row y filtered with filters[y % len(filters)]."""
    size = len(pixels[0][0])
    raw, prev = b"", bytes(len(pixels[0]) * size)
    for y, row in enumerate(pixels):
        line, kind = bytes(value for pixel in row for value in pixel), filters[y % len(filters)]
        out = bytearray()
        for i, value in enumerate(line):
            left, up = (line[i - size] if i >= size else 0), prev[i]
            upleft = prev[i - size] if i >= size else 0
            guess = [0, left, up, (left + up) >> 1, eyedropper.paeth(left, up, upleft)][kind]
            out.append((value - guess) & 255)
        raw, prev = raw + bytes([kind]) + bytes(out), line
    header = struct.pack(">IIBBBBB", len(pixels[0]), len(pixels), depth, colour, 0, 0, interlace)
    body = chunk(b"IHDR", header) + extra + (chunk(b"PLTE", palette) if palette else b"")
    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n" + body + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return path


class Images(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def path(self, name):
        return os.path.join(self.dir, name)

    def page(self, name="page.png", **options):
        """A 10x6 page: cream background, a green 4x2 button at (2,1), one red pixel at (9,5)."""
        cream, green, red = (0xfa, 0xf6, 0xec), (0x1e, 0x4d, 0x3b), (0xa9, 0x4b, 0x26)
        rows = [[green if 2 <= x < 6 and 1 <= y < 3 else cream for x in range(10)] for y in range(6)]
        rows[5][9] = red
        return png(self.path(name), rows, **options)


class Reading(Images):
    def test_every_filter_type_reads_back_the_same_pixels(self):
        for filters in [(0,), (1,), (2,), (3,), (4,), (0, 1, 2, 3, 4)]:
            with self.subTest(filters=filters):
                width, height, rows, warning = eyedropper.read_png(self.page(filters=filters))
                self.assertEqual((width, height, warning), (10, 6, None))
                self.assertEqual(rows[1][6:9], bytes([0x1e, 0x4d, 0x3b]))
                self.assertEqual(rows[5][27:30], bytes([0xa9, 0x4b, 0x26]))

    def test_rgba_grey_and_palette_images(self):
        rgba = png(self.path("a.png"), [[(1, 2, 3, 255), (4, 5, 6, 128)]], colour=6, filters=(4,))
        self.assertEqual(eyedropper.read_png(rgba)[2], [bytes([1, 2, 3, 4, 5, 6])])
        grey = png(self.path("g.png"), [[(7,), (200,)]], colour=0)
        self.assertEqual(eyedropper.read_png(grey)[2], [bytes([7, 7, 7, 200, 200, 200])])
        grey_alpha = png(self.path("ga.png"), [[(9, 255)]], colour=4)
        self.assertEqual(eyedropper.read_png(grey_alpha)[2], [bytes([9, 9, 9])])
        indexed = png(self.path("p.png"), [[(1,), (0,)]], colour=3, palette=bytes([10, 20, 30, 40, 50, 60]))
        self.assertEqual(eyedropper.read_png(indexed)[2], [bytes([40, 50, 60, 10, 20, 30])])

    def test_most_used_colours_with_where_and_grey(self):
        code, out, err = run(self.page())
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("#faf6ec  85.0%  at 0,0"), lines[0])
        self.assertTrue(lines[1].startswith("#1e4d3b  13.3%  at 2,1"), lines[1])
        self.assertTrue(lines[2].startswith("#a94b26   1.7%  at 9,5"), lines[2])
        data = json.loads(run(self.page(), "--json")[1])
        self.assertEqual(data["colours"][1], {"hex": "#1e4d3b", "share": 13.3, "at": [2, 1],
                                              "grey": eyedropper.grey("#1e4d3b")})
        self.assertEqual((data["width"], data["height"], data["warning"]), (10, 6, None))
        self.assertEqual(len(json.loads(run(self.page(), "--json", "--top", "1")[1])["colours"]), 1)

    def test_points_and_a_box(self):
        code, out, _ = run(self.page(), "3,2", "9,5")
        self.assertEqual(code, 0)
        self.assertEqual([line.split()[:2] for line in out.splitlines()], [["3,2", "#1e4d3b"], ["9,5", "#a94b26"]])
        code, out, _ = run(self.page(), "--box", "1,1,3,2")  # 2 cream, 4 green pixels
        self.assertEqual(code, 0)
        self.assertEqual([line.split()[:2] for line in out.splitlines()], [["#1e4d3b", "66.7%"], ["#faf6ec", "33.3%"]])
        self.assertIn("at 2,1", out)  # positions stay those of the whole image

    def test_a_colour_profile_that_is_not_srgb_is_named(self):
        profile = chunk(b"iCCP", b"Display P3\0\0" + zlib.compress(b"profile"))
        code, out, _ = run(self.page(extra=profile))
        self.assertEqual(code, 0)
        self.assertIn("warning: this screenshot has the colour profile Display P3", out)
        srgb = chunk(b"iCCP", b"sRGB IEC61966-2.1\0\0" + zlib.compress(b"profile"))
        self.assertNotIn("warning", run(self.page(extra=srgb))[1])


class Greys(unittest.TestCase):
    def test_the_grey_has_the_same_contrast_with_everything(self):
        for colour in ("#1e4d3b", "#faf6ec", "#f2c14e", "#a94b26", "#416958", "#0000ff"):
            with self.subTest(colour=colour):
                found = eyedropper.grey(colour)
                self.assertEqual(found[1:3] * 3, found[1:])  # a neutral grey: #vvvvvv
                for other in ("#ffffff", "#000000", "#777777"):
                    self.assertAlmostEqual(contrast.ratio(found, other), contrast.ratio(colour, other), delta=0.1)
        self.assertEqual(eyedropper.grey("#777777"), "#777777")
        self.assertEqual((eyedropper.grey("#000"), eyedropper.grey("#fff")), ("#000000", "#ffffff"))

    def test_grey_on_the_command_line(self):
        code, out, _ = run("--grey", "#1e4d3b", "faf6ec")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["#1e4d3b  grey %s" % eyedropper.grey("#1e4d3b"),
                                            "#faf6ec  grey %s" % eyedropper.grey("#faf6ec")])
        self.assertEqual(json.loads(run("--grey", "#000", "--json")[1]), {"colours": [{"hex": "#000000",
                                                                                       "grey": "#000000"}]})


class BadInput(Images):
    def test_files_and_arguments_it_refuses(self):
        text = self.path("notes.png")
        with open(text, "w", encoding="utf-8") as handle:
            handle.write("not a png")
        cases = [((self.path("missing.png"),), "not a file that exists"), ((text,), "is not a PNG file"),
                 ((self.page("deep.png", depth=16),), "only 8-bit PNGs"),
                 ((self.page("lace.png", interlace=1),), "interlaced"),
                 ((self.page(), "10,0"), "outside the image (10 x 6)"), ((self.page(), "1;2"), "not a point"),
                 ((self.page(), "--box", "8,4,3,3"), "outside the image"), ((self.page(), "--box", "1,1,0,2"), "a box"),
                 (("--grey", "green"), "not a colour"), ((), "give a screenshot"),
                 ((self.page(), "--grey", "#fff"), "either a screenshot or --grey")]
        for args, words in cases:
            with self.subTest(args=args):
                code, out, err = run(*args)
                self.assertEqual((code, out), (2, ""))
                self.assertIn(words, err)

    def test_broken_image_data(self):
        good = self.page()
        with open(good, "rb") as handle:
            data = handle.read()
        cut = self.path("cut.png")
        with open(cut, "wb") as handle:
            handle.write(data[:-30])
        code, _, err = run(cut)
        self.assertEqual(code, 2)
        self.assertIn("broken or cut short", err)

    def test_a_cp1252_pipe_and_odd_profile_names_do_not_crash(self):
        profile = chunk(b"iCCP", b"Caf\xe9 P3\x81\n\x9d\0\0" + zlib.compress(b"profile"))
        path = self.page("café-→.png", extra=profile)
        code, out, err = run_cp1252(os.path.join(ROOT, "forge-design", "eyedropper.py"), path, "--box", "0,0,1,1")
        self.assertEqual(code, 0, err)
        self.assertIn("the colour profile Café P3???, not sRGB", out)  # control bytes shown as ?
        self.assertIn("#faf6ec 100.0%", out)


if __name__ == "__main__":
    unittest.main()
