#!/usr/bin/env python3
"""Read exact colours off a screenshot, as an eyedropper does, and the grey of the same lightness.

A hex value read off a screenshot by eye is a guess. In a screenshot at 100% zoom (deviceScaleFactor
1, as forge-research recon takes them) a flat area holds the very colour the page uses, so read the pixels.

Usage:
    python3 eyedropper.py forge-work/screens/S05.png                     the colours used most
    python3 eyedropper.py forge-work/screens/S05.png 60,500 176,121      the colour at each point
    python3 eyedropper.py forge-work/screens/S05.png --box 176,121,339,51 --json   in one area
    python3 eyedropper.py --grey "#1e4d3b" "#faf6ec"                     the grey of each colour

Points and boxes count from the top left: x,y and x,y,width,height in pixels. Each colour comes
with its share of the pixels, where one of them is, and its grey: the neutral grey with the same
lightness, so the same contrast with every other colour. In a box over text the background comes
first and the text colour next; the edges of letters are blends, each one rare. Reads 8-bit PNGs
without interlacing (what browsers save). A colour profile other than sRGB (a Mac's Display P3)
means other values: the output warns.

Exit codes:
    0  read
    2  bad input: no such file, a PNG it cannot read, a point or box outside the image, a colour
       that is not #rgb or #rrggbb
"""

import argparse
import bisect
import collections
import json
import os
import re
import struct
import sys
import zlib
from itertools import accumulate
from operator import add

CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}  # PNG colour type -> bytes per pixel at 8 bits
MAX_PIXELS = 30 * 1000 * 1000  # about 1170 x 25000: bigger images are refused, not read
RESAVE = ": save it as an 8-bit PNG without interlacing (a fresh screenshot is one)"
HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
MOD256 = list(range(256)) * 2  # MOD256[n] is n % 256 for n up to 511


def linear(channel):
    channel /= 255.0
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


GREYS = [linear(value) for value in range(256)]  # the luminance of #000000 up to #ffffff, rising


def full_hex(colour):
    """'1E4' or '#11ee44' -> '#11ee44'."""
    digits = HEX.match(colour.strip()).group(1).lower()
    return "#" + ("".join(c * 2 for c in digits) if len(digits) == 3 else digits)


def grey(colour):
    """'#1e4d3b' -> the neutral grey with the same WCAG luminance, so the same contrast everywhere."""
    digits = full_hex(colour)[1:]
    red, green, blue = (linear(int(digits[i:i + 2], 16) * 1.0) for i in (0, 2, 4))
    target = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    above = min(bisect.bisect_left(GREYS, target), 255)
    best = min((above - 1, above), key=lambda value: abs(GREYS[max(value, 0)] - target))
    return "#%02x%02x%02x" % ((max(best, 0),) * 3)


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
            line[i] = (line[i] + ((left + prev[i]) >> 1 if kind == 3 else paeth(left, prev[i], upleft))) & 255
    return line


def rgb(line, colour, palette):
    """One decoded row as 3 bytes (red, green, blue) per pixel; alpha is left out."""
    if colour == 2:
        return bytes(line)
    if colour == 3:
        return b"".join(palette[index * 3:index * 3 + 3].ljust(3, b"\0") for index in line)
    if colour == 6:
        return bytes(b for pixel in zip(line[0::4], line[1::4], line[2::4]) for b in pixel)
    return bytes(value for value in line[0::CHANNELS[colour]] for _ in range(3))  # grey, maybe with alpha


def read_png(path):
    """(width, height, rows, warning): rows of RGB bytes, and a warning about the colour profile."""
    if not os.path.isfile(path):
        raise ValueError("%s is not a file that exists" % path)
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("%s is not a PNG file: save the screenshot as PNG" % path)
    chunks, pos = {}, 8
    while pos + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunks.setdefault(kind, []).append(data[pos + 8:pos + 8 + length])
        pos += 12 + length  # length, type, body, checksum
    header = chunks.get(b"IHDR", [b""])[0]
    if len(header) != 13:
        raise ValueError("%s has no valid PNG header: take the screenshot again" % path)
    width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", header)
    for failed, problem in [(not width * height, "it has no pixels"),
                            (width * height > MAX_PIXELS, "it is too big (%d x %d): crop it" % (width, height)),
                            (interlace != 0, "it is interlaced" + RESAVE),
                            (depth != 8, "only 8-bit PNGs are read here, it has %d bits%s" % (depth, RESAVE)),
                            (colour not in CHANNELS, "colour type %d is not a PNG colour type" % colour)]:
        if failed:
            raise ValueError("%s: %s" % (path, problem))
    bpp, stride = CHANNELS[colour], width * CHANNELS[colour] + 1  # each row: a filter byte, then pixels
    try:  # capped at the size the header promises: no zip bomb
        raw = zlib.decompressobj().decompress(b"".join(chunks.get(b"IDAT", [])), height * stride)
    except zlib.error:
        raw = b""
    if len(raw) < height * stride or any(raw[start] > 4 for start in range(0, height * stride, stride)):
        raise ValueError("%s: the image data is broken or cut short: take the screenshot again" % path)
    rows, line, palette = [], bytearray(stride - 1), chunks.get(b"PLTE", [b""])[0]
    for start in range(0, height * stride, stride):
        line = unfilter(raw[start], bytearray(raw[start + 1:start + stride]), line, bpp)
        rows.append(rgb(line, colour, palette))
    profile = chunks.get(b"iCCP", [b""])[0].split(b"\0", 1)[0][:79].decode("latin-1")
    profile = "".join(c if c.isprintable() else "?" for c in profile)  # the file's own text: shown safely
    warning = None
    if profile and "srgb" not in profile.lower() and b"sRGB" not in chunks:
        warning = ("this screenshot has the colour profile %s, not sRGB, so its values differ from the page's: "
                   "take it with Playwright, or with the screenshot tool set to sRGB" % profile)
    return width, height, rows, warning


def numbers(text, count, what):
    """'176,121' -> (176, 121), or a ValueError that names WHAT."""
    parts = text.split(",")
    if len(parts) != count or not all(part.strip().isdigit() for part in parts):
        raise ValueError("%r is not %s" % (text, what))
    return tuple(int(part) for part in parts)


def most_used(rows, box, top):
    """[(hex, share, (x, y))] of the TOP colours inside BOX (x, y, width, height), most used first."""
    x, y, width, height = box
    counts = collections.Counter()
    for row in rows[y:y + height]:
        part = row[x * 3:(x + width) * 3]
        counts.update(part[i:i + 3] for i in range(0, len(part), 3))
    found = []
    for pixel, count in counts.most_common(top):
        for row_number in range(y, y + height):  # where the first one is, top left first
            part, i = rows[row_number][x * 3:(x + width) * 3], -1
            while True:
                i = part.find(pixel, i + 1)
                if i < 0 or i % 3 == 0:
                    break
            if i >= 0:
                share = round(100.0 * count / (width * height), 1)
                found.append(("#" + pixel.hex(), share, (x + i // 3, row_number)))
                break
    return found


def main(argv=None):
    """Read the colours the command line asks for. Returns the exit code: 0 or 2 (see the top)."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: escapes, no crash
    parser = argparse.ArgumentParser(description="Read exact colours off a screenshot.")
    parser.add_argument("image", nargs="?", help="a PNG screenshot at 100%% zoom")
    parser.add_argument("points", nargs="*", metavar="X,Y", help="read the colour at these points")
    parser.add_argument("--box", metavar="X,Y,W,H", help="the colours used most in this area")
    parser.add_argument("--top", type=int, default=12, help="how many colours to list (default: 12)")
    parser.add_argument("--grey", nargs="+", metavar="COLOUR", help="the grey of the same lightness, no image")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        if args.grey and (args.image or args.box):
            raise ValueError("give either a screenshot or --grey with colours, not both")
        if args.grey:
            bad = [colour for colour in args.grey if not HEX.match(colour.strip())]
            if bad:
                raise ValueError("%s is not a colour: write it as #rgb or #rrggbb" % bad[0])
            colours = [{"hex": full_hex(colour), "grey": grey(colour)} for colour in args.grey]
            print(json.dumps({"colours": colours}, indent=2) if args.json
                  else "\n".join("%s  grey %s" % (item["hex"], item["grey"]) for item in colours))
            return 0
        if not args.image:
            raise ValueError("give a screenshot (a PNG), or --grey with colours")
        width, height, rows, warning = read_png(args.image)
        points = [numbers(text, 2, "a point: write it as x,y") for text in args.points]
        box = numbers(args.box, 4, "a box: write it as x,y,width,height") if args.box else (0, 0, width, height)
        if box[2] < 1 or box[3] < 1:
            raise ValueError("%s is not a box: its width and height must be 1 or more" % args.box)
        for x, y in points + [(box[0] + box[2] - 1, box[1] + box[3] - 1)]:
            if x >= width or y >= height:
                raise ValueError("%d,%d is outside the image (%d x %d)" % (x, y, width, height))
    except ValueError as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    if points:
        colours = [{"at": [x, y], "hex": "#" + rows[y][x * 3:x * 3 + 3].hex()} for x, y in points]
    else:
        colours = [{"hex": found, "share": share, "at": list(at)}
                   for found, share, at in most_used(rows, box, args.top)]
    for item in colours:
        item["grey"] = grey(item["hex"])
    if args.json:
        print(json.dumps({"image": args.image, "width": width, "height": height, "warning": warning,
                          "colours": colours}, indent=2))
        return 0
    if warning:
        print("warning: " + warning)
    for item in colours:
        at = "%d,%d" % tuple(item["at"])
        if points:
            print("%-9s %s  grey %s" % (at, item["hex"], item["grey"]))
        else:
            print("%s %5.1f%%  at %-9s grey %s" % (item["hex"], item["share"], at, item["grey"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
