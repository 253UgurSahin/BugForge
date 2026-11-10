"""Tests for forge-design/changed.py: reading every kind of PNG it says it reads, what counts as a
changed pixel, where the change is in plain words, folders, sizes that differ, --moves, the exit
codes and the JSON shape. The test PNG encoder has its own filters and its own Paeth predictor, and
the pixel count is checked against a plain loop, so a mistake in changed.py cannot hide."""

import contextlib
import io
import json
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zlib
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252, symlink  # noqa: E402

changed = load("forge-design", "changed")
SCRIPT = os.path.join(ROOT, "forge-design", "changed.py")
SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}  # PNG colour type -> bytes per pixel
WHITE, INK, SEA = (255, 255, 255), (20, 24, 31), (45, 212, 191)
NOT_SEEN = "NO VISIBLE CHANGE: a person would not see a difference"
ARROW = chr(0x2192)  # a character that cp1252, the encoding of a Windows pipe, does not have


def chunk(name, body):
    return struct.pack(">I", len(body)) + name + body + struct.pack(">I", zlib.crc32(name + body) & 0xFFFFFFFF)


def write_raw(path, width, height, colour, image_data, depth=8, interlace=0, extra=b""):
    """A PNG file with these header values and this compressed image data, as it is. Returns the path."""
    header = struct.pack(">IIBBBBB", width, height, depth, colour, 0, 0, interlace)
    with open(path, "wb") as handle:
        handle.write(SIGNATURE + chunk(b"IHDR", header) + extra + chunk(b"IDAT", image_data) + chunk(b"IEND", b""))
    return path


def content(path):
    with open(path, "rb") as handle:
        return handle.read()


def reference_paeth(a, b, c):
    """The Paeth predictor written out as in the PNG spec, for the test encoder."""
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def filtered(rows, bpp, kinds):
    """The rows as a PNG stores them: each with its filter type byte (kinds, repeated) and filtered so."""
    raw, prev = bytearray(), bytearray(len(rows[0]))
    for y, row in enumerate(rows):
        kind, line = kinds[y % len(kinds)], bytearray(row)
        raw.append(kind)
        for i, value in enumerate(line):
            left, corner = (line[i - bpp], prev[i - bpp]) if i >= bpp else (0, 0)
            guess = (0, left, prev[i], (left + prev[i]) >> 1, reference_paeth(left, prev[i], corner))[kind]
            raw.append((value - guess) & 255)
        prev = line
    return bytes(raw)


def encode(path, rows, colour=2, kinds=(0,), palette=None, alphas=None, cut=0):
    """Write rows (the bytes of each row, as the colour type stores them) as an 8-bit PNG. cut drops
    bytes from the end of the compressed image data. Returns the path."""
    extra = chunk(b"PLTE", bytes(value for entry in palette for value in entry)) if palette else b""
    extra += chunk(b"tRNS", bytes(alphas)) if alphas else b""
    data = zlib.compress(filtered(rows, CHANNELS[colour], kinds))
    return write_raw(path, len(rows[0]) // CHANNELS[colour], len(rows), colour, data[:len(data) - cut], extra=extra)


def canvas(width, height, colour=WHITE):
    return [[colour] * width for _ in range(height)]


def paint(pixels, x, y, width, height, colour):
    """Fill a box of a canvas with one colour. Returns the canvas."""
    for row in pixels[y:y + height]:
        row[x:x + width] = [colour] * len(row[x:x + width])
    return pixels


def flat(pixels):
    """A canvas (rows of (r, g, b)) as the bytes of each row."""
    return [bytes(value for pixel in row for value in pixel) for row in pixels]


def picture(pixels):
    """A canvas as read_png() would give it, with nothing on disk."""
    rows = flat(pixels)
    return len(pixels[0]), len(pixels), lambda: rows, object()


def plain_count(one, two):
    """Which pixels of two rows changed, by the plainest loop there is."""
    return bytes(int(any(abs(one[i + c] - two[i + c]) > changed.TOLERANCE for c in range(3)))
                 for i in range(0, len(one), 3))


def over_white(value, alpha):
    return (value * alpha + 255 * (255 - alpha)) // 255


def as_rgb(rows, colour, palette=(), alphas=()):
    """What a viewer shows for rows of any colour type: red, green, blue, laid over white."""
    out = []
    for row in rows:
        pixels = []
        for i in range(0, len(row), CHANNELS[colour]):
            if colour == 3:
                rgb = palette[row[i]] if row[i] < len(palette) else (0, 0, 0)
                alpha = alphas[row[i]] if row[i] < len(alphas) else 255
            elif colour in (0, 4):
                rgb, alpha = (row[i],) * 3, (row[i + 1] if colour == 4 else 255)
            else:
                rgb, alpha = tuple(row[i:i + 3]), (row[i + 3] if colour == 6 else 255)
            pixels += [over_white(value, alpha) for value in rgb]
        out.append(bytes(pixels))
    return out


class TempFolder(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)

    def path(self, *names):
        """A path in the temp folder; the folders above it are made."""
        path = os.path.join(self.folder, *names)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def save(self, name, pixels, kinds=(0,)):
        """Write a canvas as an RGB PNG. Returns its path."""
        return encode(self.path(*name.split("/")), flat(pixels), 2, kinds)

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = changed.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def report(self, *args):
        code, out, err = self.run_main("--json", *args)
        self.assertEqual(err, "")
        return code, json.loads(out)

    def assert_refused(self, path, *words):
        with self.assertRaises(ValueError) as caught:
            changed.read_png(path)[2]()
        for word in words + (path,):  # the message always names the file
            self.assertIn(word, str(caught.exception))


class ReadTests(TempFolder):
    def test_every_colour_type_with_every_filter_type(self):
        dice = random.Random(7)
        palette = [tuple(dice.randrange(256) for _ in range(3)) for _ in range(256)]
        alphas = [dice.choice((0, 90, 255)) for _ in range(200)]  # the last 56 colours have no alpha: solid
        for colour, bpp in sorted(CHANNELS.items()):
            rows = [bytes(dice.randrange(256) for _ in range(11 * bpp)) for _ in range(6)]
            rows.insert(3, rows[2])  # a row equal to the one above it
            rows.append(bytes(rows[0][:bpp]) * 11)  # a row of one colour
            if colour in (4, 6):  # a row of solid pixels, so not every row is see-through
                rows.append(bytes(value | (255 if i % bpp == bpp - 1 else 0) for i, value in enumerate(rows[1])))
            expected = as_rgb(rows, colour, palette, alphas)
            for kinds in [(0,), (1,), (2,), (3,), (4,), (4, 1, 3, 2, 0, 4, 4)]:
                with self.subTest(colour=colour, kinds=kinds):
                    path = encode(self.path("x.png"), rows, colour, kinds, palette if colour == 3 else None,
                                  alphas if colour == 3 else None)
                    width, height, decode, data = changed.read_png(path)
                    self.assertEqual((width, height), (11, len(rows)))
                    self.assertEqual(decode(), expected)
                    self.assertEqual(data, content(path))

    def test_unfilter_gives_back_what_the_encoder_took_out(self):
        """Paeth has short cuts for flat areas: rows with few values meet every one of them."""
        dice = random.Random(11)
        for values in (range(256), (0, 255), (7, 8, 9), (200,)):
            for bpp in (1, 2, 3, 4):
                rows = [bytes(dice.choice(values) for _ in range(40 * bpp)) for _ in range(5)]
                for kind in range(5):
                    raw, prev = filtered(rows, bpp, (kind,)), bytearray(len(rows[0]) + bpp)
                    for y, row in enumerate(rows):
                        start = y * (len(row) + 1) + 1
                        prev = changed.unfilter(kind, bytearray(bpp) + raw[start:start + len(row)], prev, bpp)
                        self.assertEqual(bytes(prev[bpp:]), row, (values, bpp, kind, y))
                        self.assertEqual(bytes(prev[:bpp]), bytes(bpp))

    def test_see_through_pixels_are_laid_over_white(self):
        rgba = encode(self.path("rgba.png"), [bytes([0, 0, 0, 0, 0, 0, 0, 255, 0, 0, 0, 128, 200, 100, 0, 51])], 6)
        self.assertEqual(changed.read_png(rgba)[2](), [bytes([255, 255, 255, 0, 0, 0, 127, 127, 127, 244, 224, 204])])
        grey = encode(self.path("grey.png"), [bytes([0, 128, 255])], 0)
        self.assertEqual(changed.read_png(grey)[2](), [bytes([0, 0, 0, 128, 128, 128, 255, 255, 255])])
        grey_alpha = encode(self.path("ga.png"), [bytes([0, 128, 90, 255])], 4)  # half-strength black, a solid grey
        self.assertEqual(changed.read_png(grey_alpha)[2](), [bytes([127, 127, 127, 90, 90, 90])])

    def test_palette_with_alpha_and_a_colour_it_lacks(self):
        colours = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (9, 9, 9)]
        path = encode(self.path("p.png"), [bytes([0, 1, 2, 3, 9])], 3, palette=colours, alphas=[255, 255, 0, 128])
        self.assertEqual(changed.read_png(path)[2](),
                         [bytes([255, 0, 0, 0, 255, 0, 255, 255, 255, 131, 131, 131, 0, 0, 0])])
        bare = encode(self.path("bare.png"), [bytes([0, 1])], 3)  # no palette at all: black, not a crash
        self.assertEqual(changed.read_png(bare)[2](), [bytes(6)])

    def test_the_same_picture_in_any_colour_type_is_no_change(self):
        pixels = paint(paint(canvas(12, 8, (200, 200, 200)), 2, 2, 5, 3, (40, 40, 40)), 8, 1, 3, 6, WHITE)
        greys = [bytes(pixel[0] for pixel in row) for row in pixels]
        index = {200: 0, 40: 1, 255: 2}
        others = [encode(self.path("grey.png"), greys, 0, (1,)),
                  encode(self.path("ga.png"), [bytes(v for value in row for v in (value, 255)) for row in greys], 4, (3,)),
                  encode(self.path("rgba.png"), [bytes(v for pixel in row for v in pixel + (255,)) for row in pixels], 6),
                  encode(self.path("p.png"), [bytes(index[value] for value in row) for row in greys], 3, (2,),
                         palette=[(200, 200, 200), (40, 40, 40), WHITE])]
        for other in others:
            with self.subTest(other=os.path.basename(other)):
                result = changed.compare(changed.read_png(self.save("rgb.png", pixels, (4,))), changed.read_png(other))
                self.assertEqual((result["changed"], result["pixels"]), (0, 96))

    def test_the_rows_are_decoded_once_and_only_when_asked(self):
        path = self.save("a.png", canvas(4, 3, SEA))
        with mock.patch.object(changed, "unfilter", wraps=changed.unfilter) as unfilter:
            _, _, decode, _ = changed.read_png(path)
            self.assertEqual(unfilter.call_count, 0)
            self.assertIs(decode(), decode())
            self.assertEqual(unfilter.call_count, 3)

    def test_other_kinds_of_png_are_refused_with_what_to_do(self):
        sixteen = write_raw(self.path("s.png"), 1, 1, 2, zlib.compress(b"\0" + bytes(6)), depth=16)
        self.assert_refused(sixteen, "16 bits per channel", "save it as an 8-bit PNG")
        two_bit = write_raw(self.path("p.png"), 4, 1, 3, zlib.compress(b"\0\x1b"), depth=2,
                            extra=chunk(b"PLTE", bytes(12)))
        self.assert_refused(two_bit, "2 bits per channel", "save it as an 8-bit PNG")
        laced = write_raw(self.path("i.png"), 1, 1, 2, zlib.compress(b"\0\1\2\3"), interlace=1)
        self.assert_refused(laced, "interlaced", "without interlacing")
        self.assert_refused(write_raw(self.path("t.png"), 1, 1, 5, b""), "colour type 5", "save it as an 8-bit PNG")

    def test_broken_files_are_refused_with_what_to_do(self):
        for name, start in (("x.png", b"GIF89a"), ("j.png", b"\xff\xd8\xff\xe0 a JPEG"), ("e.png", b"")):
            with open(self.path(name), "wb") as handle:
                handle.write(start)
            self.assert_refused(self.path(name), "is not a PNG file", "save the screenshot as PNG")
        with open(self.path("h.png"), "wb") as handle:
            handle.write(SIGNATURE + b"\0\0\0\0IEND")
        self.assert_refused(self.path("h.png"), "no valid PNG header", "take the screenshot again")
        cut = encode(self.path("c.png"), flat(canvas(30, 30, SEA)), cut=12)
        self.assert_refused(cut, "broken or cut short", "take the screenshot again")
        odd_filter = write_raw(self.path("f.png"), 1, 1, 2, zlib.compress(b"\x09\1\2\3"))
        self.assert_refused(odd_filter, "broken or cut short", "take the screenshot again")
        self.assert_refused(write_raw(self.path("z.png"), 1, 1, 2, b"not zlib data"), "broken or cut short")
        self.assert_refused(write_raw(self.path("n.png"), 1, 1, 2, b""), "broken or cut short")

    def test_huge_and_empty_pictures_are_refused_before_any_decoding(self):
        path = self.save("a.png", canvas(40, 40, SEA))
        with mock.patch.object(zlib, "decompressobj", side_effect=AssertionError("must not decode")):
            self.assert_refused(write_raw(self.path("big.png"), 100000, 100000, 2, b""),
                                "too big (100000 x 100000)", "crop it")
            self.assert_refused(write_raw(self.path("zero.png"), 0, 10, 2, b""), "no pixels")
            with mock.patch.object(changed, "MAX_FILE", os.path.getsize(path) - 1):
                self.assert_refused(path, "is bigger than", "crop it")
        with mock.patch.object(changed, "MAX_FILE", os.path.getsize(path)):
            self.assertEqual(len(changed.read_png(path)[2]()), 40)

    def test_a_zip_bomb_is_not_unpacked_past_the_size_in_the_header(self):
        bomb = write_raw(self.path("bomb.png"), 2, 2, 2, zlib.compress(bytes(50 * 1000 * 1000)))
        unpack, asked = zlib.decompressobj, []

        class Counting:
            def decompress(self, data, max_length=0):
                asked.append(max_length)
                return unpack().decompress(data, max_length)

        with mock.patch.object(zlib, "decompressobj", Counting):
            self.assertEqual(changed.read_png(bomb)[2](), [bytes(6), bytes(6)])
        self.assertEqual(asked, [14])  # two rows of a filter byte and six bytes of pixels, not one byte more

    def test_damaged_files_never_crash_it(self):
        """Whatever is in the file, the answer is a picture or a ValueError that names the file."""
        dice = random.Random(13)
        data = content(self.save("good.png", paint(canvas(9, 7, SEA), 2, 2, 4, 3, INK), kinds=(4, 3, 2, 1, 0)))
        path = self.path("damaged.png")
        for _ in range(300):
            damaged = bytearray(data)
            for _ in range(dice.randint(1, 3)):
                damaged[dice.randrange(len(damaged))] = dice.randrange(256)
            with open(path, "wb") as handle:
                handle.write(damaged[:dice.choice((len(damaged), len(damaged), dice.randrange(len(damaged))))])
            try:
                width, height, decode, _ = changed.read_png(path)
                self.assertEqual([len(row) for row in decode()], [3 * width] * height)
            except ValueError as error:
                self.assertIn(path, str(error))


class PixelTests(unittest.TestCase):
    def test_a_channel_must_differ_by_more_than_the_tolerance(self):
        self.assertEqual(changed.TOLERANCE, 8)
        self.assertIn("differs by more than 8 on the scale of 0 to 255", " ".join(changed.__doc__.split()))
        base = bytes([100, 150, 200])
        for channel in range(3):
            for step, counts in ((0, 0), (1, 0), (8, 0), (9, 1), (10, 1), (55, 1)):
                for sign in (1, -1):
                    other = bytearray(base)
                    other[channel] += sign * step
                    with self.subTest(channel=channel, step=sign * step):
                        self.assertEqual(changed.changed_pixels(base, bytes(other)), bytes([counts]))
                        self.assertEqual(changed.changed_pixels(bytes(other), base), bytes([counts]))

    def test_the_ends_of_the_scale(self):
        cases = [((0, 0, 0), (255, 255, 255), 1), ((0, 0, 0), (8, 8, 8), 0), ((255, 255, 255), (247, 247, 247), 0),
                 ((255, 0, 128), (246, 9, 127), 1), ((127, 128, 129), (128, 127, 128), 0), ((0, 255, 0), (0, 255, 0), 0),
                 ((128, 128, 128), (119, 128, 128), 1), ((127, 127, 127), (136, 127, 127), 1), ((0, 0, 9), (0, 0, 0), 1)]
        for one, two, counts in cases:
            with self.subTest(one=one, two=two):
                self.assertEqual(changed.changed_pixels(bytes(one), bytes(two)), bytes([counts]))
        one, two = bytes(v for case in cases for v in case[0]), bytes(v for case in cases for v in case[1])
        self.assertEqual(changed.changed_pixels(one, two), bytes(case[2] for case in cases))  # no pixel leaks over

    def test_it_counts_what_a_plain_loop_counts(self):
        dice = random.Random(3)
        for trial in range(60):
            one = bytes(dice.randrange(256) for _ in range(3 * 97))
            spread = dice.choice((1, 9, 12, 300))
            two = bytes(min(255, max(0, value + dice.randint(-spread, spread))) for value in one)
            self.assertEqual(changed.changed_pixels(one, two), plain_count(one, two), trial)


class WhereTests(unittest.TestCase):
    def test_the_box_in_plain_words(self):
        cases = [((0, 0, 1440, 300), "the top third"), ((0, 310, 1440, 590), "the middle third"),
                 ((0, 600, 1440, 900), "the bottom third"), ((0, 0, 1440, 450), "the top half"),
                 ((0, 460, 1440, 900), "the bottom half"), ((0, 40, 1440, 600), "the top two thirds"),
                 ((0, 300, 1440, 900), "the bottom two thirds"), ((0, 0, 480, 900), "the left third"),
                 ((500, 0, 940, 900), "the centre third"), ((960, 0, 1440, 900), "the right third"),
                 ((0, 0, 700, 900), "the left half"), ((720, 0, 1440, 900), "the right half"),
                 ((0, 0, 900, 900), "the left two thirds"), ((500, 0, 1440, 900), "the right two thirds"),
                 ((10, 10, 300, 200), "the top left"), ((1000, 700, 1440, 900), "the bottom right"),
                 ((600, 400, 800, 500), "the centre"), ((0, 500, 600, 900), "the bottom left"),
                 ((500, 20, 900, 200), "the top centre"), ((1100, 320, 1400, 560), "the middle right"),
                 ((300, 200, 1100, 700), "the middle")]
        for box, words in cases:
            with self.subTest(box=box):
                self.assertEqual(changed.where(box, 1440, 900), words + " of the screen")

    def test_a_box_that_spans_the_screen(self):
        self.assertEqual(changed.where((0, 0, 1440, 900), 1440, 900), "the whole screen")
        self.assertEqual(changed.where((20, 20, 1420, 880), 1440, 900), "almost the whole screen")
        self.assertEqual(changed.where((0, 100, 1440, 800), 1440, 900), "most of the screen")
        self.assertEqual(changed.where((0, 0, 1, 1), 1, 1), "the whole screen")

    def test_a_few_pixels_over_the_line_do_not_change_the_words(self):
        self.assertEqual(changed.where((0, 0, 1440, 318), 1440, 900), "the top third of the screen")  # 35 percent
        self.assertEqual(changed.where((0, 0, 1440, 330), 1440, 900), "the top half of the screen")


class CompareTests(unittest.TestCase):
    def test_the_same_picture_has_no_changed_pixel(self):
        result = changed.compare(picture(canvas(40, 30)), picture(canvas(40, 30)))
        self.assertEqual(result, {"percent": 0.0, "changed": 0, "pixels": 1200, "where": "", "box": None,
                                  "before_size": [40, 30], "after_size": [40, 30]})

    def test_two_files_with_the_same_bytes_are_not_decoded(self):
        def never():
            raise AssertionError("decoded")
        result = changed.compare((40, 30, never, b"the same bytes"), (40, 30, never, b"the same bytes"))
        self.assertEqual((result["changed"], result["pixels"], result["box"]), (0, 1200, None))

    def test_a_changed_box_is_counted_and_found(self):
        result = changed.compare(picture(canvas(60, 30)), picture(paint(canvas(60, 30), 0, 2, 60, 5, SEA)))
        self.assertEqual((result["changed"], result["pixels"], result["percent"]), (300, 1800, 16.66))
        self.assertEqual(result["box"], {"x": 0, "y": 2, "w": 60, "h": 5})
        self.assertEqual(result["where"], "the top third of the screen")
        result = changed.compare(picture(canvas(60, 30)), picture(paint(canvas(60, 30), 41, 21, 7, 8, SEA)))
        self.assertEqual((result["changed"], result["box"]), (56, {"x": 41, "y": 21, "w": 7, "h": 8}))
        self.assertEqual(result["where"], "the bottom right of the screen")

    def test_the_box_goes_around_every_change(self):
        after = paint(paint(canvas(60, 30), 0, 0, 1, 1, INK), 59, 29, 1, 1, INK)
        result = changed.compare(picture(canvas(60, 30)), picture(after))
        self.assertEqual((result["changed"], result["percent"]), (2, 0.11))
        self.assertEqual((result["box"], result["where"]), ({"x": 0, "y": 0, "w": 60, "h": 30}, "the whole screen"))

    def test_a_change_within_the_tolerance_is_no_change(self):
        result = changed.compare(picture(canvas(20, 10, (100, 100, 100))), picture(canvas(20, 10, (108, 92, 104))))
        self.assertEqual((result["changed"], result["box"]), (0, None))
        result = changed.compare(picture(canvas(20, 10, (100, 100, 100))), picture(canvas(20, 10, (100, 109, 100))))
        self.assertEqual((result["changed"], result["percent"]), (200, 100.0))

    def test_a_longer_page_counts_what_only_it_has_as_changed(self):
        result = changed.compare(picture(canvas(40, 30)), picture(canvas(40, 45)))
        self.assertEqual((result["changed"], result["pixels"], result["percent"]), (600, 1800, 33.33))
        self.assertEqual(result["box"], {"x": 0, "y": 30, "w": 40, "h": 15})
        self.assertEqual(result["where"], "the bottom third of the screen")
        self.assertEqual((result["before_size"], result["after_size"]), ([40, 30], [40, 45]))
        shorter = changed.compare(picture(canvas(40, 45)), picture(paint(canvas(40, 30), 0, 0, 40, 1, INK)))
        self.assertEqual((shorter["changed"], shorter["box"]), (640, {"x": 0, "y": 0, "w": 40, "h": 45}))

    def test_a_wider_picture_and_one_that_is_bigger_both_ways(self):
        wider = changed.compare(picture(canvas(40, 30)), picture(paint(canvas(50, 30), 45, 0, 5, 30, INK)))
        self.assertEqual((wider["changed"], wider["pixels"]), (300, 1500))  # the part both have is the same
        self.assertEqual(wider["box"], {"x": 40, "y": 0, "w": 10, "h": 30})
        self.assertEqual(wider["where"], "the right third of the screen")
        narrower = changed.compare(picture(paint(canvas(40, 30), 3, 3, 2, 2, INK)), picture(canvas(50, 30)))
        self.assertEqual((narrower["changed"], narrower["box"]), (304, {"x": 3, "y": 0, "w": 47, "h": 30}))
        both = changed.compare(picture(canvas(40, 30)), picture(canvas(50, 45)))
        self.assertEqual((both["changed"], both["pixels"], both["box"]), (1050, 2250, {"x": 0, "y": 0, "w": 50, "h": 45}))
        crossed = changed.compare(picture(canvas(50, 30)), picture(canvas(40, 45)))  # neither holds the other
        self.assertEqual((crossed["changed"], crossed["pixels"]), (50 * 45 - 40 * 30, 50 * 45))

    def test_the_percentage_is_rounded_down(self):
        after = paint(paint(canvas(100, 100), 0, 0, 100, 1, INK), 0, 1, 99, 1, INK)
        self.assertEqual(changed.compare(picture(canvas(100, 100)), picture(after))["percent"], 1.99)
        result = changed.compare(picture(canvas(300, 100)), picture(paint(canvas(300, 100), 5, 5, 2, 1, INK)))
        self.assertEqual((result["percent"], result["changed"]), (0.0, 2))

    def test_a_full_screenshot_is_compared_in_well_under_a_few_seconds(self):
        rows = [bytes(INK) * 1440] * 450 + [bytes(SEA) * 1440] * 450
        noisy = bytes(random.Random(5).randrange(256) for _ in range(3 * 1440))
        start = time.time()
        result = changed.compare((1440, 900, lambda: rows, 1), (1440, 900, lambda: [noisy] * 900, 2))
        self.assertLess(time.time() - start, 3)
        self.assertGreater(result["percent"], 90)


class CliTests(TempFolder):
    def setUp(self):
        TempFolder.setUp(self)
        self.before = self.save("before.png", canvas(60, 40))
        self.after = self.save("after.png", paint(canvas(60, 40), 0, 0, 60, 10, SEA))
        self.same = self.save("same.png", canvas(60, 40), kinds=(1,))  # the same picture as before, other bytes

    def test_a_visible_change_is_exit_0(self):
        code, out, err = self.run_main(self.before, self.after)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.splitlines(), [
            "before.png -> after.png: 25.00% of the pixels changed (600 of 2400), spread over the top third of the "
            "screen. VISIBLE CHANGE", "VISIBLE CHANGE: 1 of 1 pair(s) changed 2% of the pixels or more."])

    def test_files_with_the_same_name_are_shown_as_typed(self):
        before, after = self.save("b/home.png", canvas(20, 20)), self.save("a/home.png", canvas(20, 20, SEA))
        code, out, _ = self.run_main(before, after)
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("%s -> %s: 100.00%% of the pixels changed" % (before, after)), out)
        self.assertEqual(self.report(before, after)[1]["pairs"][0]["name"], "%s -> %s" % (before, after))

    def test_no_change_is_exit_1_and_says_what_that_usually_means(self):
        self.assertNotEqual(content(self.before), content(self.same))
        for other, name in ((self.same, "before.png -> same.png"),  # the same picture in other bytes,
                            (self.before, "%s -> %s" % (self.before, self.before))):  # and the very same file
            code, out, err = self.run_main(self.before, other)
            self.assertEqual((code, err), (1, ""))
            self.assertEqual(out.splitlines(), [
                "%s: 0.00%% of the pixels changed (0 of 2400). %s" % (name, NOT_SEEN),
                "NO VISIBLE CHANGE in any pair: none reaches 2% of the pixels. This usually means one of:",
                "- the work is on another branch or folder than the one the local app serves",
                "- the app was not rebuilt or restarted",
                "- a service worker or a cache still serves the old files",
                "- the change is too small to see"])

    def test_files_with_the_same_bytes_are_not_decoded(self):
        with mock.patch.object(changed, "unfilter", side_effect=AssertionError("decoded")):
            self.assertEqual(self.run_main(self.before, self.before)[0], 1)
            copy = shutil.copy(self.after, self.path("copy.png"))
            self.assertEqual(self.report(self.after, copy)[1]["pairs"][0]["changed"], 0)

    def test_min_sets_how_much_must_change(self):
        small = self.save("small.png", paint(canvas(60, 40), 3, 3, 6, 6, INK))  # 36 of 2400 pixels: 1.5 percent
        code, out, _ = self.run_main(self.before, small)
        self.assertEqual(code, 1)
        self.assertIn("1.50% of the pixels changed (36 of 2400), spread over the top left of the screen. " + NOT_SEEN, out)
        self.assertEqual(self.run_main(self.before, small, "--min", "1.5")[0], 0)
        self.assertEqual(self.run_main(self.before, small, "--min", "1.51")[0], 1)
        self.assertEqual(self.run_main(self.before, self.after, "--min", "25")[0], 0)
        self.assertEqual(self.run_main(self.before, self.after, "--min", "25.5")[0], 1)
        self.assertIn("changed 0.05% of the pixels or more.", self.run_main(self.before, small, "--min", "0.05")[1])

    def test_a_step_within_the_tolerance_is_not_a_change(self):
        grey = self.save("grey.png", canvas(30, 20, (120, 120, 120)))
        close = self.save("close.png", canvas(30, 20, (128, 112, 120)))
        far = self.save("far.png", canvas(30, 20, (120, 129, 120)))
        code, out, _ = self.run_main(grey, close)
        self.assertEqual(code, 1)
        self.assertIn("0.00% of the pixels changed (0 of 600). " + NOT_SEEN, out)
        code, out, _ = self.run_main(grey, far)
        self.assertEqual(code, 0)
        self.assertIn("100.00% of the pixels changed (600 of 600), spread over the whole screen. VISIBLE CHANGE", out)

    def test_every_filter_type_gives_the_same_answer(self):
        expected = self.report(self.before, self.after)[1]["pairs"][0]
        for kind in range(5):
            after = self.save("k%d.png" % kind, paint(canvas(60, 40), 0, 0, 60, 10, SEA), kinds=(kind,))
            code, data = self.report(self.save("b%d.png" % kind, canvas(60, 40), kinds=(4 - kind,)), after)
            self.assertEqual(code, 0)
            for key in ("percent", "changed", "pixels", "box", "where", "visible"):
                self.assertEqual(data["pairs"][0][key], expected[key], (kind, key))

    def test_sizes_that_differ(self):
        longer = self.save("longer.png", canvas(60, 60))
        code, out, _ = self.run_main(self.before, longer)
        self.assertEqual(code, 0)
        self.assertIn("33.33% of the pixels changed (1200 of 3600), spread over the bottom third of the screen. The "
                      "sizes differ (60 x 40 and 60 x 60): what only one has counts as changed, so take both the same "
                      "way. VISIBLE CHANGE", out)

    def test_two_folders_pair_the_pngs_by_name(self):
        before, after = os.path.join(self.folder, "b"), os.path.join(self.folder, "a")
        self.save("b/home.png", canvas(60, 40))
        self.save("a/home.png", paint(canvas(60, 40), 0, 20, 60, 20, SEA))
        self.save("b/login.png", canvas(30, 40))
        self.save("a/login.png", canvas(30, 40), kinds=(2,))
        self.save("b/gone.png", canvas(5, 5))
        self.save("a/new.PNG", canvas(5, 5))
        self.save("a/deeper/home.png", canvas(5, 5))  # not directly in the folder
        self.save("a/home.jpg", canvas(5, 5))  # not named .png
        os.mkdir(os.path.join(after, "folder.png"))
        for hidden in ("b/._home.png", "a/._home.png", "a/.cache.png"):  # what a Mac leaves on some disks
            with open(self.path(*hidden.split("/")), "wb") as handle:
                handle.write(b"not a picture")
        code, out, err = self.run_main(before, after)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.splitlines(), [
            "home.png: 50.00% of the pixels changed (1200 of 2400), spread over the bottom half of the screen. "
            "VISIBLE CHANGE", "login.png: 0.00% of the pixels changed (0 of 1200). " + NOT_SEEN,
            "Only in %s, so not compared: gone.png" % before, "Only in %s, so not compared: new.PNG" % after,
            "VISIBLE CHANGE: 1 of 2 pair(s) changed 2% of the pixels or more."])
        code, data = self.report(before, after)
        self.assertEqual((data["only_before"], data["only_after"]), (["gone.png"], ["new.PNG"]))
        self.assertEqual([pair["name"] for pair in data["pairs"]], ["home.png", "login.png"])
        self.assertEqual((data["pairs"][0]["before"], data["pairs"][0]["after"]),
                         (os.path.join(before, "home.png"), os.path.join(after, "home.png")))
        self.assertEqual((data["summary"]["pairs"], data["summary"]["visible"]), (2, 1))
        self.assertEqual(self.run_main(before, before)[0], 1)

    def test_links_in_a_folder_are_not_followed(self):
        self.save("b/home.png", canvas(20, 20))
        self.save("a/home.png", canvas(20, 20, SEA))
        self.save("a/linked.png", canvas(20, 20))
        symlink(self, self.save("elsewhere/other.png", canvas(20, 20, INK)), self.path("b", "linked.png"))
        code, data = self.report(os.path.join(self.folder, "b"), os.path.join(self.folder, "a"))
        self.assertEqual(code, 0)
        self.assertEqual([pair["name"] for pair in data["pairs"]], ["home.png"])
        self.assertEqual((data["only_before"], data["only_after"]), ([], ["linked.png"]))

    def test_bad_usage_is_exit_2(self):
        empty = os.path.join(self.folder, "empty")
        os.mkdir(empty)
        cases = [([self.before], "give BEFORE and AFTER"), ([self.before, self.after, self.same], "or --moves"),
                 ([self.before, "--moves"], "two or more frames"),
                 ([self.before, self.path("nope.png")], "nope.png is not a file that exists"),
                 ([self.before, self.folder], "is not a file that exists: give PNG files, or two folders"),
                 ([self.folder, self.after], "is not a file that exists"),
                 ([self.folder, empty, "--moves"], "is not a file that exists"),
                 ([empty, self.folder], "no PNG has the same name in"),
                 ([self.before, self.after, "--min", "0"], "--min is a percentage"),
                 ([self.before, self.after, "--min", "-1"], "more than 0"),
                 ([self.before, self.after, "--min", "100.5"], "at most 100"),
                 ([self.before, self.after, "--min", "nan"], "--min is a percentage")]
        for args, words in cases:
            for extra in ([], ["--json"]):
                with self.subTest(args=args + extra):
                    code, out, err = self.run_main(*(args + extra))
                    self.assertEqual((code, out), (2, ""))
                    self.assertTrue(err.startswith("error: "), err)
                    self.assertIn(words, err)
        for args in ([], [self.before, self.after, "--min", "lots"], [self.before, self.after, "--fast"]):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    changed.main(args)
                self.assertEqual(caught.exception.code, 2)

    def test_a_file_it_cannot_read_is_exit_2_never_a_pass(self):
        before, after = os.path.join(self.folder, "b"), os.path.join(self.folder, "a")
        with open(self.path("b", "broken.png"), "wb") as handle:
            handle.write(b"GIF89a")
        self.save("a/broken.png", canvas(60, 40))
        self.save("b/home.png", canvas(60, 40))
        self.save("a/home.png", canvas(60, 40, SEA))
        code, out, err = self.run_main(before, after)
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out.splitlines(), [
            "broken.png: could not compare: %s is not a PNG file: save the screenshot as PNG"
            % os.path.join(before, "broken.png"),
            "home.png: 100.00% of the pixels changed (2400 of 2400), spread over the whole screen. VISIBLE CHANGE",
            "INCOMPLETE, so not a pass: 1 of 2 pair(s) could not be compared."])
        code, data = self.report(before, after)
        self.assertEqual(code, 2)
        self.assertEqual(sorted(data["pairs"][0]), ["after", "before", "error", "name"])
        self.assertEqual(data["summary"], {"pairs": 2, "visible": 1, "enough": True, "complete": False,
                                           "largest": 100.0, "verdict": "INCOMPLETE", "min": 2.0})
        cut = encode(self.path("cut.png"), flat(canvas(60, 40, SEA)), cut=9)
        code, out, _ = self.run_main(self.before, cut)
        self.assertEqual(code, 2)
        self.assertIn("could not compare: %s: the image data is broken or cut short: take the screenshot again" % cut, out)

    def test_a_file_that_cannot_be_opened_is_exit_2(self):
        with mock.patch.object(changed, "read_png", side_effect=OSError(13, "Permission denied", self.before)):
            code, out, _ = self.run_main(self.before, self.after)
        self.assertEqual(code, 2)
        self.assertIn("could not compare: cannot read %s (Permission denied)" % self.before, out)

    def test_json_shape(self):
        code, data = self.report(self.before, self.after)
        self.assertEqual(code, 0)
        self.assertEqual(sorted(data), ["mode", "only_after", "only_before", "pairs", "summary", "tolerance"])
        self.assertEqual((data["mode"], data["tolerance"], data["only_before"], data["only_after"]), ("change", 8, [], []))
        self.assertEqual(data["pairs"], [{
            "name": "before.png -> after.png", "before": self.before, "after": self.after,
            "percent": 25.0, "changed": 600, "pixels": 2400, "where": "the top third of the screen",
            "box": {"x": 0, "y": 0, "w": 60, "h": 10}, "before_size": [60, 40], "after_size": [60, 40], "visible": True}])
        self.assertEqual(data["summary"], {"pairs": 1, "visible": 1, "enough": True, "complete": True, "largest": 25.0,
                                           "verdict": "VISIBLE CHANGE", "min": 2.0})
        code, data = self.report(self.before, self.same, "--min", "0.5")
        self.assertEqual(code, 1)
        pair = data["pairs"][0]
        self.assertEqual((pair["percent"], pair["box"], pair["where"], pair["visible"]), (0.0, None, "", False))
        self.assertEqual(data["summary"], {"pairs": 1, "visible": 0, "enough": False, "complete": True, "largest": 0.0,
                                           "verdict": "NO VISIBLE CHANGE", "min": 0.5})

    def test_help_and_running_as_a_script(self):
        done = subprocess.run([sys.executable, SCRIPT, "--help"], timeout=60, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        for words in ("Usage:", "Exit codes:", "--moves", "--min PERCENT", "default: 2 percent, with --moves 0.2"):
            self.assertIn(words, done.stdout)
        done = subprocess.run([sys.executable, SCRIPT, self.before, self.same], timeout=60, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual((done.returncode, done.stderr), (1, ""))
        self.assertIn(NOT_SEEN, done.stdout)

    def test_a_cp1252_pipe_gets_escapes_not_a_crash(self):
        """Windows pipes are cp1252, which has no arrow: it prints as \\u2192, no crash."""
        before = self.save("caf%s %s before.png" % (chr(0xE9), ARROW), canvas(20, 20))
        after = self.save("caf%s %s after.png" % (chr(0xE9), ARROW), canvas(20, 20, SEA))
        code, out, err = run_cp1252(SCRIPT, before, after)
        self.assertEqual((code, err), (0, ""))
        shown = "%s -> %s: 100.00%% of the pixels changed" % (os.path.basename(before), os.path.basename(after))
        self.assertIn(shown.replace(ARROW, "\\u2192"), out)


class MovesTests(TempFolder):
    def frames(self, *positions):
        """Frames of one screen with a small dot at each position: 16 of 2400 pixels, so 32 change per move."""
        return [self.save("f%d.png" % number, paint(canvas(60, 40), x, 20, 4, 4, INK))
                for number, x in enumerate(positions, start=1)]

    def test_frames_that_differ_are_exit_0_with_each_step_listed(self):
        one, two, three, four = self.frames(0, 10, 10, 30)
        code, out, err = self.run_main("--moves", one, two, three, four)
        self.assertEqual((code, err), (0, ""))
        moved = ": 1.33% of the pixels changed (32 of 2400), spread over the middle left of the screen. VISIBLE CHANGE"
        self.assertEqual(out.splitlines(), [
            "f1.png -> f2.png" + moved, "f2.png -> f3.png: 0.00% of the pixels changed (0 of 2400). " + NOT_SEEN,
            "f3.png -> f4.png" + moved, "SOMETHING MOVES: 2 of 3 pair(s) changed 0.2% of the pixels or more."])

    def test_frames_that_are_the_same_are_exit_1(self):
        frames = self.frames(5, 5) + [self.save("f3.png", paint(canvas(60, 40), 5, 20, 4, 4, INK), kinds=(4,))]
        code, out, err = self.run_main(*(frames + ["--moves"]))
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out.count("0.00% of the pixels changed (0 of 2400). " + NOT_SEEN), 2)
        self.assertEqual(out.splitlines()[2], "NOTHING MOVES: nothing moves on this screen in the frames taken (no "
                         "frame differs from the next by 0.2% of the pixels). Take the frames while the motion runs, "
                         "with reduced motion off, and check that the app shows the new code.")

    def test_the_default_bar_is_lower_for_frames_and_min_moves_it(self):
        frames = self.frames(0, 10)  # 1.33 percent: it moves, but it is under the 2 percent of before and after
        self.assertEqual(self.run_main(*frames)[0], 1)
        self.assertEqual(self.run_main("--moves", *frames)[0], 0)
        self.assertEqual(self.run_main("--moves", "--min", "1.4", *frames)[0], 1)
        code, data = self.report("--moves", *frames)
        summary = data["summary"]
        self.assertEqual((data["mode"], summary["min"], summary["verdict"]), ("moves", 0.2, "SOMETHING MOVES"))
        self.assertEqual((data["pairs"][0]["name"], data["pairs"][0]["before"]), ("f1.png -> f2.png", frames[0]))
        self.assertEqual(self.report("--moves", frames[0], frames[0])[1]["summary"]["verdict"], "NOTHING MOVES")

    def test_each_frame_is_read_once(self):
        frames = self.frames(0, 10, 20, 30)
        with mock.patch.object(changed, "read_png", wraps=changed.read_png) as read, \
                mock.patch.object(changed, "unfilter", wraps=changed.unfilter) as unfilter:
            self.assertEqual(self.run_main("--moves", *frames)[0], 0)
        self.assertEqual([call[0][0] for call in read.call_args_list], frames)
        self.assertEqual(unfilter.call_count, 4 * 40)  # every row of every frame, once

    def test_frames_of_other_sizes_and_broken_frames(self):
        frames = self.frames(0, 0) + [self.save("tall.png", paint(canvas(60, 50), 0, 20, 4, 4, INK))]
        code, out, _ = self.run_main("--moves", *frames)
        self.assertEqual(code, 0)
        self.assertIn("f2.png -> tall.png: 20.00% of the pixels changed (600 of 3000)", out)
        with open(self.path("bad.png"), "wb") as handle:
            handle.write(b"not a picture")
        code, out, _ = self.run_main("--moves", frames[0], self.path("bad.png"), frames[1])
        self.assertEqual(code, 2)
        self.assertEqual(out.count("bad.png is not a PNG file"), 2)  # both steps that need it
        self.assertIn("INCOMPLETE, so not a pass: 2 of 2 pair(s) could not be compared.", out)
        cut = encode(self.path("cut.png"), flat(canvas(60, 40, SEA)), cut=9)
        code, out, _ = self.run_main("--moves", frames[0], cut, frames[1], frames[2])
        self.assertEqual(code, 2)
        self.assertEqual(out.count("cut.png: the image data is broken or cut short"), 2)
        self.assertIn("INCOMPLETE, so not a pass: 2 of 3 pair(s) could not be compared.", out)


if __name__ == "__main__":
    unittest.main()
