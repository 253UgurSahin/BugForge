"""Tests for forge-diff/imgdiff.py (ported from the original test_imgdiff.py, plus the forge
limits: 8-bit PNGs only with a clear message for anything else, big images read small, and
--out never overwrites a screenshot). The original's pixel mode is gone, so its tests are too.
The test PNG encoder has its own Paeth predictor, so a wrong one in imgdiff.py cannot hide."""

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
from _load import load  # noqa: E402

imgdiff = load("forge-diff", "imgdiff")
WHITE = (255, 255, 255)


def canvas(width, height, colour=WHITE):
    return [[colour for _ in range(width)] for _ in range(height)]


def rect(rows, x, y, width, height, colour):
    for yy in range(y, min(len(rows), y + height)):
        for xx in range(x, min(len(rows[0]), x + width)):
            rows[yy][xx] = colour


def page(width=240, height=360, header=(20, 20, 60), accent=(40, 110, 230), text=(30, 30, 30), button_y=250,
         button_x=20, top=0):
    """A fake app screen: a header bar, lines of 'text' and a button. top moves it all down."""
    rows = canvas(width, height)
    rect(rows, 0, top, width, 40, header)
    for i in range(6):
        rect(rows, 20, top + 70 + i * 22, width - 60 - (i % 3) * 30, 8, text)
    rect(rows, button_x, top + button_y, 120, 36, accent)
    return (width, height, rows)


def cards(border, fill=(249, 250, 251), width=240, height=200):
    """Boxes with a thin border, the way most web apps draw cards."""
    rows = canvas(width, height)
    for y in (20, 110):
        for x in (10, 125):
            rect(rows, x, y, 105, 70, border)
            rect(rows, x + 1, y + 1, 103, 68, fill)
            rect(rows, x + 10, y + 45, 40, 12, (37, 99, 235))
    return (width, height, rows)


def grey(image):
    """An (r, g, b) image as the brightness rows imgdiff compares."""
    width, height, rows = image
    return width, height, [[(299 * r + 587 * g + 114 * b) // 1000 for r, g, b in row] for row in rows]


def upscale(image, factor):
    """Every pixel as a factor x factor block: an exact 2x or 3x screenshot of the same screen."""
    width, height, rows = image
    big = [[pixel for pixel in row for _ in range(factor)] for row in rows for _ in range(factor)]
    return width * factor, height * factor, big


def compare(image_a, image_b, **options):
    return imgdiff.compare(grey(image_a), grey(image_b), **options)


def lines(count, width=480, height=80):
    """count dark lines across the top grid row: each grid cell there holds count lines of outline."""
    rows = canvas(width, height)
    for i in range(count):
        rect(rows, 0, 6 + 3 * i, width, 1, (0, 0, 0))
    return (width, height, rows)


def reference_paeth(a, b, c):
    """The Paeth predictor written out as in the PNG spec, for the test encoder."""
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def chunk(name, body):
    return struct.pack(">I", len(body)) + name + body + struct.pack(">I", zlib.crc32(name + body) & 0xFFFFFFFF)


def write_raw(path, width, height, colour_type, image_data, depth=8, interlace=0, extra=b""):
    """A PNG file with the given header values and compressed image data, as is."""
    header = struct.pack(">IIBBBBB", width, height, depth, colour_type, 0, 0, interlace)
    with open(path, "wb") as handle:
        handle.write(imgdiff.PNG_SIGNATURE + chunk(b"IHDR", header) + extra + chunk(b"IDAT", image_data)
                     + chunk(b"IEND", b""))


def encode(path, width, height, sample_rows, colour_type, depth=8, kind=0, palette=None, alphas=None,
           interlace=0, cut=0):
    """A tiny PNG encoder for the tests, with the chosen filter on every row. cut drops bytes
    from the end of the compressed image data."""
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colour_type]
    bpp = max(1, depth * channels // 8)
    raw, prev = bytearray(), bytearray(len(sample_rows[0]))
    for samples in sample_rows:
        line = bytearray(samples)
        out = bytearray()
        for i, value in enumerate(line):
            left = line[i - bpp] if i >= bpp else 0
            up, upleft = prev[i], (prev[i - bpp] if i >= bpp else 0)
            guess = [0, left, up, (left + up) >> 1, reference_paeth(left, up, upleft)][kind]
            out.append((value - guess) & 0xFF)
        raw.append(kind)
        raw.extend(out)
        prev = line
    extra = chunk(b"PLTE", bytes(c for rgb in palette for c in rgb)) if palette else b""
    extra += chunk(b"tRNS", bytes(alphas)) if alphas else b""
    compressed = zlib.compress(bytes(raw))
    write_raw(path, width, height, colour_type, compressed[:len(compressed) - cut], depth, interlace, extra)


def pixels(path):
    """The brightness rows of a PNG file as read by imgdiff."""
    return [list(row) for row in imgdiff.read_png(path)[2]]


class TempFolder(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.folder)

    def path(self, name):
        return os.path.join(self.folder, name)

    def assert_refused(self, name, *words):
        with self.assertRaises(imgdiff.PngError) as caught:
            pixels(self.path(name))
        for word in words + (self.path(name),):  # the message always names the file
            self.assertIn(word, str(caught.exception))


class ReadWrite(TempFolder):
    def test_paeth_known_answers(self):
        self.assertEqual(imgdiff.paeth(10, 20, 15), 15)  # upleft is the closest guess
        self.assertEqual(imgdiff.paeth(5, 5, 5), 5)
        self.assertEqual(imgdiff.paeth(100, 50, 0), 100)
        self.assertEqual(imgdiff.paeth(50, 100, 0), 100)
        self.assertEqual(imgdiff.paeth(1, 4, 3), 1)  # a tie between left and upleft: left
        self.assertEqual(imgdiff.paeth(0, 3, 1), 3)  # a tie between up and upleft: up
        for a, b, c in [(0, 0, 255), (255, 0, 128), (7, 200, 90), (128, 128, 0), (3, 9, 6)]:
            self.assertEqual(imgdiff.paeth(a, b, c), reference_paeth(a, b, c), (a, b, c))

    def test_roundtrip_rgb(self):
        image = page(40, 30)
        imgdiff.write_png(self.path("a.png"), *image)
        width, height, _ = imgdiff.read_png(self.path("a.png"))
        self.assertEqual((width, height), (40, 30))
        self.assertTrue(pixels(self.path("a.png")) == grey(image)[2])

    def test_every_filter_type_rgba(self):
        width, height = 7, 5
        source = [[(x * 30 % 256, y * 50 % 256, (x * y * 17) % 256, 255) for x in range(width)]
                  for y in range(height)]
        flat = [[c for px in row for c in px] for row in source]
        expected = [[(299 * r + 587 * g + 114 * b) // 1000 for r, g, b, _ in row] for row in source]
        for kind in range(5):
            encode(self.path("f.png"), width, height, flat, 6, kind=kind)
            self.assertEqual(pixels(self.path("f.png")), expected, "filter %d" % kind)

    def test_every_filter_type_on_a_real_looking_screen(self):
        _, _, rows = page(60, 50)
        flat = [[c for px in row for c in px] for row in rows]
        for kind in range(5):
            encode(self.path("s.png"), 60, 50, flat, 2, kind=kind)
            same = pixels(self.path("s.png")) == grey(page(60, 50))[2]  # no assertEqual: its diff is slow
            self.assertTrue(same, "filter %d gives other pixels" % kind)

    def test_alpha_is_laid_over_white(self):
        encode(self.path("a.png"), 2, 1, [[0, 0, 0, 0, 0, 0, 0, 255]], 6)
        self.assertEqual(pixels(self.path("a.png"))[0], [255, 0])
        encode(self.path("ga.png"), 1, 1, [[0, 128]], 4)  # grey with alpha: black at half strength
        self.assertEqual(pixels(self.path("ga.png"))[0], [127])

    def test_grey_and_palette(self):
        encode(self.path("g.png"), 3, 1, [[0, 128, 255]], 0)
        self.assertEqual(pixels(self.path("g.png"))[0], [0, 128, 255])
        colours = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (9, 9, 9)]
        encode(self.path("p.png"), 5, 1, [[0, 1, 2, 3, 9]], 3, palette=colours, alphas=[255, 255, 255, 0])
        self.assertEqual(pixels(self.path("p.png"))[0], [76, 149, 29, 255, 0])  # 9: not in the palette

    def test_16_bit_and_small_palettes_are_refused_with_advice(self):
        encode(self.path("s.png"), 1, 1, [[0x12, 0x34, 0xAB, 0xCD, 0xEF, 0x01]], 2, depth=16)
        self.assert_refused("s.png", "bit depth is 16", "save it as an 8-bit RGB or RGBA PNG")
        encode(self.path("p.png"), 4, 1, [[0b00011011]], 3, depth=2, palette=[(1, 2, 3)] * 4)
        self.assert_refused("p.png", "bit depth is 2")

    def test_interlaced_is_refused_with_advice(self):
        encode(self.path("i.png"), 1, 1, [[1, 2, 3]], 2, interlace=1)
        self.assert_refused("i.png", "interlaced", "without interlacing")

    def test_broken_files_are_refused_with_the_file_and_what_to_do(self):
        for name, start in (("x.png", b"GIF89a"), ("j.png", b"\xff\xd8\xff\xe0 a JPEG")):
            with open(self.path(name), "wb") as handle:
                handle.write(start)
            self.assert_refused(name, "is not a PNG file", "convert it")
        with open(self.path("h.png"), "wb") as handle:
            handle.write(imgdiff.PNG_SIGNATURE + b"\0\0\0\0IEND")
        self.assert_refused("h.png", "no valid PNG header", "take the screenshot again")
        encode(self.path("c.png"), 30, 30, [[7, 8, 9] * 30] * 30, 2, cut=30)
        self.assert_refused("c.png", "cut short", "take the screenshot again")
        write_raw(self.path("t.png"), 1, 1, 2, zlib.compress(b"\x09\x01\x02\x03"))  # filter type 9
        self.assert_refused("t.png", "image data is broken", "take the screenshot again")
        write_raw(self.path("z.png"), 1, 1, 2, b"not zlib data")  # also what an Apple CgBI PNG gives
        self.assert_refused("z.png", "image data is broken", "take the screenshot again")

    def test_huge_or_empty_images_are_refused_before_reading(self):
        write_raw(self.path("big.png"), 100000, 100000, 2, b"")
        self.assert_refused("big.png", "too big (100000 x 100000)", "crop it")
        write_raw(self.path("zero.png"), 0, 10, 2, b"")
        self.assert_refused("zero.png", "no pixels")
        write_raw(self.path("type5.png"), 1, 1, 5, b"")
        self.assert_refused("type5.png", "colour type 5", "save it as an 8-bit RGB or RGBA PNG")

    def test_rows_are_read_one_at_a_time(self):
        imgdiff.write_png(self.path("w.png"), *page(240, 120))
        width, height, rows = imgdiff.read_png(self.path("w.png"))
        self.assertEqual((width, height), (240, 120))
        self.assertIs(iter(rows), rows)  # a generator, not a list of every pixel
        self.assertEqual(len(next(rows)), 240)


class Compare(unittest.TestCase):
    def test_identical_is_100_with_no_regions(self):
        report, _ = compare(page(), page())
        self.assertEqual(report["score"], 100.0)
        self.assertEqual(report["regions"], [])
        self.assertEqual(report["verdict"], "matches")
        self.assertEqual(report["warnings"], [])

    def test_rebrand_keeps_the_layout_score(self):
        rebranded = page(header=(120, 20, 40), accent=(20, 160, 90), text=(60, 50, 40))
        self.assertGreaterEqual(compare(page(), rebranded)[0]["score"], 90.0)

    def test_light_grey_borders_count_so_a_darker_border_is_not_a_layout_change(self):
        report, _ = compare(cards(border=(229, 231, 235)), cards(border=(156, 163, 175)))
        self.assertGreaterEqual(report["score"], 95.0)

    def test_one_or_two_pixels_off_still_matches(self):
        for top in (1, 2):
            with self.subTest(top=top):
                self.assertGreaterEqual(compare(page(), page(top=top))[0]["score"], 90.0)
                self.assertGreaterEqual(compare(cards((200, 200, 200)), cards((200, 200, 200), height=200 + top),
                                                width=240)[0]["score"], 90.0)

    def test_retina_and_odd_widths_compare_at_one_scale(self):
        small = page(250, 180)
        for big in (upscale(small, 2), upscale(small, 3)):
            for width in (96, 125, 240):  # whole and broken scale steps (250 / 96 is 2.6)
                with self.subTest(width=width, big=big[0]):
                    report, _ = compare(small, big, width=width)
                    self.assertGreaterEqual(report["score"], 97.0)
                    self.assertEqual(report["warnings"], [])
        report, _ = compare(small, (251, 180, [row + [WHITE] for row in small[2]]), width=96)
        self.assertGreaterEqual(report["score"], 95.0)  # the same screen on a canvas 1 pixel wider

    def test_moved_button_is_found_where_it_is(self):
        report, _ = compare(page(), page(button_y=310))
        self.assertLess(report["score"], 100.0)
        self.assertTrue(report["regions"])
        self.assertTrue(all(region["y"] >= 200 for region in report["regions"]), report["regions"])
        self.assertTrue(all(region["x"] < 160 for region in report["regions"]))
        self.assertTrue(all(region["where"].startswith("bottom") for region in report["regions"]))
        report, _ = compare(page(480), page(480, button_x=340))  # the button moved to the right
        self.assertEqual(sorted((region["x"] > 240, region["where"]) for region in report["regions"]),
                         [(False, "bottom left"), (True, "bottom right")])

    def test_a_cell_is_flagged_below_60_percent(self):
        report, _ = compare(lines(10), lines(5))
        self.assertEqual((report["score"], report["verdict"]), (50.0, "partly"))
        self.assertEqual([(r["where"], r["cells"]) for r in report["regions"]], [("top centre", 12)])
        report, _ = compare(lines(10), lines(7))
        self.assertEqual((report["score"], report["regions"]), (70.0, []))

    def test_the_verdict_goes_with_the_score_as_shown(self):
        with mock.patch.object(imgdiff, "similarity", return_value=0.89996):
            report, _ = compare(page(), page())
        self.assertEqual((report["score"], report["verdict"]), (89.9, "close"))  # never rounded up to 90.0

    def test_blank_clone_is_different(self):
        width, height, _ = page()
        report, _ = compare(page(), (width, height, canvas(width, height)))
        self.assertLess(report["score"], 50.0)
        self.assertEqual(report["verdict"], "different")

    def test_two_blank_screenshots_are_refused(self):
        with self.assertRaises(imgdiff.PngError) as caught:
            compare((40, 30, canvas(40, 30)), (1, 1, [[(0, 0, 0)]]))
        self.assertIn("nothing to compare", str(caught.exception))

    def test_a_clone_with_only_the_top_of_the_page_scores_low(self):
        width, height, rows = page(240, 720)
        for y in range(360, 720, 60):
            rect(rows, 20, y, 200, 30, (30, 30, 30))
        report, _ = compare((width, height, rows), (width, 180, rows[:180]))
        self.assertLess(report["score"], 50.0)
        self.assertEqual(report["height_delta_pct"], -75.0)
        self.assertTrue(any(region["where"].startswith("bottom") for region in report["regions"]))

    def test_regions_are_in_the_original_s_pixels(self):
        report, _ = compare(upscale(page(), 3), page(button_y=310))
        self.assertEqual(report["original"], {"width": 720, "height": 1080})
        self.assertTrue(all(region["y"] >= 600 for region in report["regions"]), report["regions"])

    def test_height_difference_is_reported(self):
        width, height, rows = page()
        report, _ = compare((width, height, rows), (width, height + 90, rows + canvas(width, 90)))
        self.assertEqual(report["height_delta_pct"], 25.0)
        self.assertIn("taller", imgdiff.render_text(report, "a", "b"))

    def test_different_viewports_get_a_warning(self):
        report, _ = compare(page(240), page(100))
        self.assertIn("same viewport", report["warnings"][0])
        self.assertIn("warning: the screenshots have different widths (240 and 100 pixels)",
                      imgdiff.render_text(report, "a", "b"))

    def test_a_very_long_page_is_compared_smaller(self):
        tall = (100, 10000, ([(y // 50) % 2 * 255] * 100 for y in range(10000)))
        with mock.patch.object(imgdiff, "MAX_COMPARED", 20000):
            report, _ = imgdiff.compare(tall, (100, 10000, ([(y // 50) % 2 * 255] * 100 for y in range(10000))))
        size = report["compared_at"]
        self.assertLessEqual(size["width"] * size["height"], 20000)
        self.assertEqual(report["score"], 100.0)

    def test_diff_picture_marks_the_regions_red(self):
        report, picture = compare(page(), page(button_y=310))
        picture = list(picture)
        self.assertEqual((len(picture[0]), len(picture)), (240, 360))
        region = report["regions"][0]
        red, green, _ = picture[region["y"] + 1][region["x"] + 1]
        self.assertGreater(red, green)
        self.assertEqual(len(set(picture[5][5])), 1)  # the header is faded grey, not red


class Cli(TempFolder):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = imgdiff.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_json_and_diff_image(self):
        original, clone, diff = self.path("a.png"), self.path("b.png"), self.path("diff.png")
        imgdiff.write_png(original, *page())
        imgdiff.write_png(clone, *page(button_y=310))
        code, out, _ = self.run_main(original, clone, "--json", "--out", diff)
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertEqual(report["files"], {"original": original, "clone": clone})
        self.assertEqual(report["diff_image"], diff)
        self.assertEqual(imgdiff.read_png(diff)[:2], (report["compared_at"]["width"], report["compared_at"]["height"]))

    def test_text_output(self):
        imgdiff.write_png(self.path("a.png"), *page())
        code, out, _ = self.run_main(self.path("a.png"), self.path("a.png"))
        self.assertEqual(code, 0)
        self.assertIn("layout score 100.0 / 100: MATCHES", out)
        self.assertIn("sizes: original 240 x 360, clone 240 x 360, compared at 240 x 360", out)
        self.assertIn("no differing regions", out)

    def test_out_never_overwrites_a_screenshot(self):
        imgdiff.write_png(self.path("a.png"), *page())
        before = pixels(self.path("a.png"))
        os.link(self.path("a.png"), self.path("hard.png"))
        os.symlink(self.path("a.png"), self.path("soft.png"))
        for out in ("a.png", "hard.png", "soft.png", os.path.join(self.folder, ".", "a.png")):
            with self.subTest(out=out), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    imgdiff.main([self.path("a.png"), self.path("a.png"), "--out", self.path(out)])
                self.assertEqual(caught.exception.code, 2)
        self.assertTrue(pixels(self.path("a.png")) == before, "a.png was overwritten")

    def test_bad_files_exit_2_with_a_plain_message(self):
        code, out, err = self.run_main("/nope/a.png", "/nope/b.png")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("cannot read or write /nope/a.png (No such file or directory)", err)
        with open(self.path("x.png"), "wb") as handle:
            handle.write(b"GIF89a")
        code, out, err = self.run_main(self.path("x.png"), self.path("x.png"))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("is not a PNG file", err)
        write_raw(self.path("z.png"), 1, 1, 2, b"not zlib data")
        code, _, err = self.run_main(self.path("z.png"), self.path("z.png"))
        self.assertEqual(code, 2)
        self.assertIn(self.path("z.png") + ": the image data is broken", err)

    def test_two_blank_screenshots_exit_2(self):
        imgdiff.write_png(self.path("w.png"), *(40, 30, canvas(40, 30)))
        code, out, err = self.run_main(self.path("w.png"), self.path("w.png"))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("nothing to compare", err)


if __name__ == "__main__":
    unittest.main()
