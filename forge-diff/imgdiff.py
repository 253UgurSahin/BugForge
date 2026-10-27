#!/usr/bin/env python3
"""Compare the layout of a screenshot of the original app with the same screen in your clone.

Both are shrunk to one shared width (at most 480 pixels), so a 2x and a 1x screenshot of one
viewport compare fine. In each cell of a 12-column grid it measures the outlines (where the
brightness jumps: boxes, text, buttons, light grey borders), letting a cell line up a few
pixels away. Colour does not count (forge-brand changes every colour), nor do cells blank in
both; rows only one of them has count as different. Score, rounded down: matches 90+, close
75+, partly 50+, different below. Reads 8-bit PNGs without interlacing (what browsers save);
anything else is refused with what to do. A long full-page screenshot takes up to a minute.

Usage:
    python3 imgdiff.py forge-work/screens/S07.png forge-work/clone-screens/S07.png
    python3 imgdiff.py ORIGINAL.png CLONE.png --out S07.diff.png --json > S07.diff.json

Exit codes:
    0  compared
    2  bad input: a missing or unreadable file, a PNG it cannot read, two blank screenshots
"""

import argparse
import json
import math
import os
import struct
import sys
import zlib
from array import array
from itertools import accumulate
from operator import add, sub

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}  # PNG colour type -> bytes per pixel at 8 bits
MAX_PIXELS = 30 * 1000 * 1000  # about 1170 x 25000; bigger images are refused, not read
RESAVE = ": save it as an 8-bit RGB or RGBA PNG without interlacing (a fresh screenshot is one)"
RETAKE = ": take the screenshot again"
WIDTH, COLUMNS = 480, 12  # compare at most this wide, in a grid this many cells wide
MAX_COMPARED = 3 * 1000 * 1000  # compare at most this many pixels, so memory stays small
EDGE_STEP = 10  # a brightness jump (0-255) bigger than this is an outline
SHIFT = 3  # a cell may line up with the clone's this many compared pixels away, each way
DEVICE_RATIOS = (1, 1.25, 1.5, 1.75, 2, 2.5, 3, 4)  # 2x, 3x ... copies of one viewport
VERDICTS = [(90, "matches"), (75, "close"), (50, "partly"), (0, "different")]  # lowest score, word
MOD256 = list(range(256)) * 2  # MOD256[n] is n % 256 for n up to 511


class PngError(Exception):
    """A file, or a pair of files, this script cannot use, with what to do about it."""


def read_png(path):
    """(width, height, rows) of a PNG file. rows yields the brightness (0-255) of each pixel, row
    by row; it decodes a row only when it is needed, so a big screenshot never sits in memory."""
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:8] != PNG_SIGNATURE:
        raise PngError("%s is not a PNG file: save the screenshot as PNG, or convert it "
                       "(on a Mac: sips -s format png IN --out OUT.png)" % path)
    chunks, pos = {}, 8
    while pos + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunks.setdefault(kind, []).append(data[pos + 8:pos + 8 + length])
        pos += 12 + length  # length, type, body, checksum
    header = chunks.get(b"IHDR", [b""])[0]
    if len(header) != 13:
        raise PngError("%s has no valid PNG header%s" % (path, RETAKE))
    width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", header)
    for failed, problem in [
            (width * height == 0, "it has no pixels" + RETAKE),
            (width * height > MAX_PIXELS, "it is too big (%d x %d): crop it first" % (width, height)),
            (interlace != 0, "it is interlaced" + RESAVE),
            (depth != 8, "its bit depth is %d and only 8-bit PNGs are read here%s" % (depth, RESAVE)),
            (colour not in CHANNELS, "colour type %d is not a PNG colour type%s" % (colour, RESAVE))]:
        if failed:
            raise PngError("%s: %s" % (path, problem))
    plte, alphas = chunks.get(b"PLTE", [b""])[0], chunks.get(b"tRNS", [b""])[0]
    palette = b"".join(plte[i * 3:i * 3 + 3] + bytes([alphas[i] if i < len(alphas) else 255])
                       for i in range(len(plte) // 3))  # as RGBA; a colour the palette lacks is black
    bpp, table = CHANNELS[colour], bytes(brightness(palette, 6))[:256].ljust(256, b"\0")
    stride = width * bpp + 1  # each row is one filter byte, then the pixels
    try:  # capped at the size the header promises: no zip bomb
        data = zlib.decompressobj().decompress(b"".join(chunks.get(b"IDAT", [])), height * stride)
    except zlib.error:
        raise PngError("%s: the image data is broken%s" % (path, RETAKE)) from None
    if len(data) < height * stride:
        raise PngError("%s: the image data is missing or cut short%s" % (path, RETAKE))

    def rows():  # decodes one row at a time, as they are used
        line = bytearray(stride - 1)
        for start in range(0, height * stride, stride):
            if data[start] > 4:
                raise PngError("%s: the image data is broken%s" % (path, RETAKE))
            line = unfilter(data[start], bytearray(data[start + 1:start + stride]), line, bpp)
            yield brightness(line, colour, table)
    return width, height, rows()


def paeth(left, up, upleft):
    """The PNG Paeth predictor: whichever neighbour is closest to left + up - upleft."""
    guess = left + up - upleft
    distances = [abs(guess - left), abs(guess - up), abs(guess - upleft)]
    return (left, up, upleft)[distances.index(min(distances))]  # on a tie: left, then up


def unfilter(kind, line, prev, bpp):
    """Undo filter type 0 to 4 on one row of PNG image data (the PNG spec, section 9)."""
    if kind == 1:  # add the byte one pixel to the left: a running total per channel
        for channel in range(bpp):
            line[channel::bpp] = bytearray(map((255).__and__, accumulate(line[channel::bpp])))
    elif kind == 2:  # add the byte above
        line = bytearray(map(MOD256.__getitem__, map(add, line, prev)))
    elif kind in (3, 4):  # add the average of left and above, or the Paeth guess: byte by byte
        for i in range(len(line)):
            left, upleft = (line[i - bpp], prev[i - bpp]) if i >= bpp else (0, 0)
            guess = (left + prev[i]) >> 1 if kind == 3 else paeth(left, prev[i], upleft)
            line[i] = (line[i] + guess) & 255
    return line


def brightness(line, colour, table=None):
    """The brightness (0-255) of each pixel in a decoded row (table: of each palette colour)."""
    if colour == 3:
        return line.translate(table)
    size = CHANNELS[colour]
    values = line[0::size] if colour in (0, 4) else [
        (299 * red + 587 * green + 114 * blue) // 1000
        for red, green, blue in zip(line[0::size], line[1::size], line[2::size])]
    if colour in (4, 6):  # the last byte of each pixel is its alpha
        values = [(v * alpha + 255 * (255 - alpha)) // 255 for v, alpha in zip(values, line[size - 1::size])]
    return values


def write_png(path, width, height, rows):
    """Write rows of (r, g, b) tuples as an 8-bit RGB PNG."""
    raw = b"".join(b"\0" + bytes(value for colour in row for value in colour) for row in rows)
    chunks = [(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),  # 8-bit RGB, not interlaced
              (b"IDAT", zlib.compress(raw, 6)), (b"IEND", b"")]
    with open(path, "wb") as handle:  # each chunk: length, type, body, checksum
        handle.write(PNG_SIGNATURE + b"".join(struct.pack(">I", len(body)) + kind + body
                                              + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
                                              for kind, body in chunks))


def shrink(image, target):
    """Shrink an image (width, height, brightness rows) to the target width. Returns (outline,
    faded): outline[y][x] is the length of outline in that small pixel and faded is the image,
    small. Outline pixels jump in brightness from the pixel left of or above them; a 2x
    screenshot has twice as many, each counting half, so the length is the same at any density."""
    width, _, rows = image
    starts = [(x * width + target - 1) // target for x in range(target + 1)]  # columns per small pixel
    patches, length = list(zip(starts, starts[1:])), target / float(width)
    outline, faded, above = [], [], None
    for y, row in enumerate(rows):
        above = row if above is None else above  # the first row has nothing above it
        across = map(abs, map(sub, row, row[:1] + row[:-1]))  # the jump from the pixel to the left
        down = map(abs, map(sub, row, above))  # the jump from the pixel above
        found = bytes(map(EDGE_STEP.__lt__, map(add, across, down)))  # 1 where they add up to an outline
        above, lengths = row, array("d", (sum(found[start:end]) * length for start, end in patches))
        if y * target // width < len(outline):  # another full-size row of the same small row
            outline[-1] = array("d", map(add, outline[-1], lengths))
        else:
            outline.append(lengths)
            faded.append(bytearray(row[start] for start, _ in patches))
    return outline, faded


def amount(outline, box):
    """The amount of outline in a box (left, top, right, bottom)."""
    left, top, right, bottom = box
    return sum(sum(row[left:right]) for row in outline[top:bottom])


def similarity(outline_a, outline_b, box):
    """How alike the outlines in one grid cell are, 0.0 to 1.0, at the best fit with the clone's
    cell moved up to SHIFT pixels each way. None when both are blank there: no layout."""
    left, top, right, bottom = box
    in_a = amount(outline_a, box)
    if max(in_a, amount(outline_b, box)) < 0.01 * (right - left) * (bottom - top):
        return None
    fits = [amount(outline_b, (left + across, top + down, right + across, bottom + down))  # within the image
            for down in range(max(-SHIFT, -top), min(SHIFT, len(outline_b) - bottom) + 1)
            for across in range(max(-SHIFT, -left), min(SHIFT, len(outline_b[0]) - right) + 1)]
    return max(1.0 - abs(in_a - in_b) / max(in_a, in_b, 1.0) for in_b in fits)


def group(flagged, n_rows, n_cols):
    """Touching flagged cells as (top row, left column, bottom row, right column, cells, where),
    biggest first. where is 'top left', 'middle centre', 'bottom right' and so on."""
    left_over, found = set(flagged), []
    while left_over:
        todo, cells = [left_over.pop()], []
        while todo:
            row, col = todo.pop()
            cells.append((row, col))
            near = {(row + 1, col), (row - 1, col), (row, col + 1), (row, col - 1)} & left_over
            left_over -= near
            todo += near
        (top, bottom), (left, right) = [(min(values), max(values)) for values in zip(*cells)]
        down = (top + bottom) / 2.0 / (n_rows - 1) if n_rows > 1 else 0.5
        across = (left + right) / 2.0 / (n_cols - 1) if n_cols > 1 else 0.5
        vertical = ("top", "middle", "bottom")[min(2, int(down * 3))]
        where = vertical + " " + ("left", "centre", "right")[min(2, int(across * 3))]
        found.append((top, left, bottom, right, len(cells), where))
    return sorted(found, key=lambda region: (-region[4], region[0], region[1]))


def compare(image_a, image_b, width=WIDTH, cols=COLUMNS):
    """Compare two images, each (width, height, brightness rows). Returns the report and the diff
    picture (rows of (r, g, b)). Raises PngError when both are blank: there is nothing to compare."""
    (width_a, height_a), (width_b, height_b) = image_a[:2], image_b[:2]
    longest = max(height_a / float(width_a), height_b / float(width_b))  # a long page: compared smaller
    target = max(1, min(width, width_a, width_b, int(math.sqrt(MAX_COMPARED / longest))))
    (outline_a, faded), (outline_b, _) = shrink(image_a, target), shrink(image_b, target)
    small_a, small_b = len(outline_a), len(outline_b)
    height = max(small_a, small_b)  # rows that only one of them has count too: blank in the other
    outline_a += [array("d", [0.0]) * target] * (height - small_a)
    outline_b += [array("d", [0.0]) * target] * (height - small_b)
    cell = max(1, target // cols)
    lefts, tops = range(0, min(target, cols * cell), cell), range(0, height, cell)
    scores, flagged = [], set()
    for top in tops:
        for left in lefts:
            box = (left, top, min(target, left + cell), min(height, top + cell))
            score = similarity(outline_a, outline_b, box)
            if score is not None:
                scores.append(score)
                if score < 0.6:
                    flagged.add((top // cell, left // cell))
    if not scores:
        raise PngError("both screenshots are blank, so there is nothing to compare: take them again "
                       "once the page has loaded")
    score = math.floor(1000.0 * sum(scores) / len(scores) + 1e-6) / 10.0  # rounded down: 89.96 is 89.9
    regions, scale = [], width_a / float(target)  # compared pixels -> the original's pixels
    for top, left, bottom, right, cells, where in group(flagged, len(tops), len(lefts)):
        box = (left * cell, top * cell, min(target, (right + 1) * cell), min(height, (bottom + 1) * cell))
        x, y, x_end, y_end = (int(value * scale) for value in box)
        regions.append({"x": x, "y": y, "w": x_end - x, "h": y_end - y, "cells": cells, "where": where})
    ratio = max(width_a, width_b) / float(min(width_a, width_b))
    warnings = [] if any(abs(ratio - usual) <= 0.02 * usual for usual in DEVICE_RATIOS) else [
        "the screenshots have different widths (%d and %d pixels): take both at the same viewport "
        "(a 2x or 3x copy of one viewport is fine)" % (width_a, width_b)]
    report = {"score": score, "verdict": next(word for lowest, word in VERDICTS if score >= lowest),
              "regions": regions, "original": {"width": width_a, "height": height_a},
              "clone": {"width": width_b, "height": height_b},
              "compared_at": {"width": target, "height": height}, "warnings": warnings,
              "height_delta_pct": round((small_b - small_a) * 100.0 / small_a, 1)}
    faded += [bytearray(b"\xff" * target)] * (height - small_a)
    picture = ([(min(255, v + 30), v // 3, v // 3) if (y // cell, x // cell) in flagged else (v, v, v)
                for x, v in enumerate(200 + value // 5 for value in row)] for y, row in enumerate(faded))
    return report, picture  # the picture is made row by row, only when it is written


def render_text(report, name_a, name_b):
    """The plain-text report."""
    regions, delta, small = report["regions"], report["height_delta_pct"], report["compared_at"]
    lines = ["%s vs %s" % (name_a, name_b),
             "layout score %.1f / 100: %s" % (report["score"], report["verdict"].upper()),
             "sizes: original {0[width]} x {0[height]}, clone {1[width]} x {1[height]}, compared at "
             "{2[width]} x {2[height]}".format(report["original"], report["clone"], small)]
    lines += ["warning: %s" % warning for warning in report["warnings"]]
    lines.append("where they differ (original's pixels, biggest first):" if regions else "no differing regions")
    lines += ["  {where:14} x={x} y={y} w={w} h={h}".format(**region) for region in regions[:8]]
    if len(regions) > 8:
        lines.append("  and %d smaller ones (see --json or the diff image)" % (len(regions) - 8))
    if abs(delta) >= 5:
        lines.append("height: the clone is %.0f%% %s than the original (a missing or extra section?)"
                     % (abs(delta), "taller" if delta > 0 else "shorter"))
    if report.get("diff_image"):
        lines.append("diff image: %s (a %d x %d copy of the original, differences tinted red)"
                     % (report["diff_image"], small["width"], small["height"]))
    return "\n".join(lines)


def main(argv=None):
    """Compare from the command line. Returns the exit code: 0 or 2 (see the top)."""
    parser = argparse.ArgumentParser(description="Compare the layout of two screenshots of one screen.")
    parser.add_argument("original", help="screenshot of the original app (PNG)")
    parser.add_argument("clone", help="the same screen in your clone, same viewport and state (PNG)")
    parser.add_argument("--out", help="write a diff image here (PNG)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    if args.out and os.path.exists(args.out) and any(  # samefile also sees symlinks and hard links
            os.path.exists(path) and os.path.samefile(args.out, path) for path in (args.original, args.clone)):
        parser.error("--out would overwrite one of the screenshots: pick another file name")
    try:
        report, picture = compare(read_png(args.original), read_png(args.clone))
        report["files"] = {"original": args.original, "clone": args.clone}
        if args.out:
            write_png(args.out, report["compared_at"]["width"], report["compared_at"]["height"], picture)
            report["diff_image"] = args.out
    except (PngError, OSError) as error:
        print("error: %s" % (error if isinstance(error, PngError) else "cannot read or write %s (%s)"
                             % (error.filename, error.strerror)), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.json else render_text(report, args.original, args.clone))
    return 0


if __name__ == "__main__":
    sys.exit(main())
