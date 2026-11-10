#!/usr/bin/env python3
"""Would a person see the change? Counts the pixels that differ between screenshots of one screen.

A skill that changes an app must show the result on the user's own screen. This is the proof:
screenshots from before and after the work must differ where a person can see it, and frames taken
a moment apart must differ when something is meant to move.

Usage:
    python3 changed.py BEFORE AFTER [--min PERCENT] [--json]
    python3 changed.py --moves FRAME FRAME [FRAME ...] [--min PERCENT] [--json]

BEFORE and AFTER are two PNG files, or two folders: then each PNG directly in BEFORE is compared with
the PNG of the same name in AFTER, and names only one folder has are listed. Links and hidden files
in a folder are left out. --moves takes frames of one screen in the order they were taken and
compares each with the next.

A pixel counts as changed when its red, green or blue differs by more than 8 on the scale of 0 to
255: smaller steps are what font smoothing and image compression give, and a person does not see
them. See-through pixels are laid over white. Where the sizes differ (the page got longer), the part
both have is compared and the rest counts as changed. Each pair gets the share of its pixels that
changed, where on the screen they are (the box around them, in plain words), and a verdict: VISIBLE
CHANGE when the share reaches --min (default: 2 percent, with --moves 0.2), else NO VISIBLE CHANGE.
Reads 8-bit PNGs without interlacing (what browsers and Playwright save), up to 64 MB and 30 million
pixels. Every pixel is compared: a 1440 x 900 pair takes about a second. --json adds the box in pixels.

Exit codes:
    0  at least one pair changed visibly; with --moves: something moves
    1  no pair did; with --moves: nothing moves on this screen in the frames taken. For before and
       after that usually means: the work is on another branch or folder than the one the local app
       serves, the app was not rebuilt or restarted, a service worker or a cache serves the old
       files, or the change is too small to see
    2  could not compare: bad usage, no pair to compare, or a file that is missing or cannot be
       read (the output names it and says what to do). Never a pass
"""

import argparse
import json
import os
import struct
import sys
import zlib
from itertools import accumulate

CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}  # PNG colour type -> bytes per pixel at 8 bits
MAX_FILE, MAX_PIXELS = 64 * 1024 * 1024, 30 * 1000 * 1000  # a bigger file or picture is refused, not read
TOLERANCE = 8  # a channel (0-255) must differ by more than this for its pixel to count as changed
FAR = bytes(int(step > TOLERANCE) for step in range(256))  # a 1 for every step between two channels that counts
RESAVE = ": save it as an 8-bit PNG without interlacing (a fresh screenshot from a browser is one)"
RETAKE = ": take the screenshot again"
PARTS = [(0, 2, "{0} third"), (2, 4, "{1} third"), (4, 6, "{2} third"), (0, 3, "{0} half"), (3, 6, "{2} half"),
         (0, 4, "{0} two thirds"), (2, 6, "{2} two thirds")]  # from, to (in sixths of the screen), name
CAUSES = ("the work is on another branch or folder than the one the local app serves; the app was not rebuilt or "
          "restarted; a service worker or a cache still serves the old files; the change is too small to see")


def masks(size):
    """Two whole numbers of SIZE bytes: every byte 127, and every byte 128. Python does sums on numbers
    of any length at once, far quicker than a loop over bytes; these keep each byte's sum in its byte."""
    return int.from_bytes(b"\x7f" * size, "big"), int.from_bytes(b"\x80" * size, "big")


def unfilter(kind, line, prev, bpp):
    """Undo PNG filter type 1 to 4 on one row (the PNG spec, section 9). line and prev, the finished
    row above it, both start with bpp zero bytes: the pixel left of the first one."""
    if kind == 1:  # add the byte one pixel to the left: a running total per channel
        for channel in range(bpp):
            line[channel::bpp] = bytes(map((255).__and__, accumulate(line[channel::bpp])))
    elif kind == 2:  # add the byte above: all bytes at once
        (low, high), one, two = masks(len(line)), int.from_bytes(line, "big"), int.from_bytes(prev, "big")
        line = bytearray((((one & low) + (two & low)) ^ ((one ^ two) & high)).to_bytes(len(line), "big"))
    elif kind in (3, 4):  # these need the finished byte to the left: byte by byte, one channel at a time
        for first in range(bpp, 2 * bpp):
            left, corner, out = 0, 0, bytearray()
            for value, up in zip(line[first::bpp], prev[first::bpp]):
                if kind == 3:  # add the average of left and above
                    left = (value + ((left + up) >> 1)) & 255
                elif up == corner:  # Paeth: add whichever of left, above and upper left (the corner) is
                    left = (value + left) & 255  # closest to left + above - corner; on a tie left, then above
                elif left == corner:
                    left = (value + up) & 255
                else:  # the PNG spec's pa, pb and pc: how far each of the three is from that sum
                    pa, pb, pc = abs(up - corner), abs(left - corner), abs(left + up - 2 * corner)
                    left = (value + (left if pa <= pb and pa <= pc else up if pb <= pc else corner)) & 255
                out.append(left)
                corner = up
            line[first::bpp] = out
    return line


def read_png(path):
    """(width, height, rows, data) of a PNG file. rows() decodes it, once: each row as bytes, 3 per
    pixel (red, green, blue), see-through pixels laid over white. data is the file as it is: two files
    with the same bytes need no decoding. Raises ValueError, with what to do, for a file it cannot read."""
    with open(path, "rb") as handle:
        data = handle.read(MAX_FILE + 1)
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("%s is not a PNG file: save the screenshot as PNG" % path)
    chunks, pos, done = {}, 8, []
    while pos + 8 <= len(data):
        length, name = struct.unpack(">I4s", data[pos:pos + 8])
        chunks.setdefault(name, []).append(data[pos + 8:pos + 8 + length])
        pos += 12 + length  # length, type, body, checksum
    header = chunks.get(b"IHDR", [b""])[0]
    if len(header) != 13:
        raise ValueError("%s has no valid PNG header%s" % (path, RETAKE))
    width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", header)
    for failed, problem in [
            (len(data) > MAX_FILE, "it is bigger than %d MB: crop it, or save it smaller" % (MAX_FILE >> 20)),
            (width * height == 0, "it has no pixels" + RETAKE),
            (width * height > MAX_PIXELS, "it is too big (%d x %d): crop it first" % (width, height)),
            (interlace != 0, "it is interlaced" + RESAVE),
            (depth != 8, "it has %d bits per channel and only 8-bit PNGs are read here%s" % (depth, RESAVE)),
            (colour not in CHANNELS, "colour type %d is not a PNG colour type%s" % (colour, RESAVE))]:
        if failed:
            raise ValueError("%s: %s" % (path, problem))
    bpp, stride = CHANNELS[colour], width * CHANNELS[colour] + 1  # each row: one filter byte, then the pixels
    plte, alphas = chunks.get(b"PLTE", [b""])[0], chunks.get(b"tRNS", [b""])[0].ljust(256, b"\xff")
    palette = [bytes((plte[i * 3 + channel] * alpha + 255 * (255 - alpha)) // 255  # laid over white
                     for i, alpha in zip(range(len(plte) // 3), alphas)).ljust(256, b"\0") for channel in range(3)]

    def rows():
        if done:  # decoded before
            return done
        try:  # capped at the size the header promises: no zip bomb
            raw = zlib.decompressobj().decompress(b"".join(chunks.get(b"IDAT", [])), height * stride)
        except zlib.error:
            raw = b""
        if len(raw) < height * stride or max(raw[::stride]) > 4:
            raise ValueError("%s: the image data is broken or cut short%s" % (path, RETAKE))
        line = bytearray(stride - 1 + bpp)
        for start in range(0, height * stride, stride):
            line = unfilter(raw[start], bytearray(bpp) + raw[start + 1:start + stride], line, bpp)
            pixels = out = line[bpp:]
            if colour != 2:  # make it red, green, blue; a colour the palette lacks is black
                out = bytearray(3 * width)
                for channel in range(3):
                    out[channel::3] = (pixels.translate(palette[channel]) if colour == 3
                                       else pixels[(channel if colour == 6 else 0)::bpp])
                alpha = pixels[bpp - 1::bpp] if colour in (4, 6) else b""
                if alpha.count(255) < len(alpha):  # see-through pixels in this row: lay them over white
                    out = ((v * alpha[i // 3] + 255 * (255 - alpha[i // 3])) // 255 for i, v in enumerate(out))
            done.append(bytes(out))
        return done
    return width, height, rows, data


def changed_pixels(one, two):
    """A byte per pixel: 1 where red, green or blue differs by more than TOLERANCE between two rows of
    3 bytes per pixel. Each row is one big number, so this never loops over the pixels."""
    (low, high), x, y = masks(len(one)), int.from_bytes(one, "big"), int.from_bytes(two, "big")
    x_wins = ((x & ~y) | (~(x ^ y) & ((x | high) - (y & low)))) & high  # the top bit of each byte: is x >= y there
    swap = (x ^ y) & ((x_wins >> 7) * 255)
    steps = ((y ^ swap) - (x ^ swap)).to_bytes(len(one), "big")  # per byte: the bigger one minus the smaller one
    far = int.from_bytes(steps.translate(FAR), "big")
    return (far | far >> 8 | far >> 16).to_bytes(len(one), "big")[2::3]


def where(box, width, height):
    """The box (left, top, right, bottom) in plain words, such as 'the top third of the screen'."""
    words = []
    for start, end, size, names in ((box[0], box[2], width, ("left", "centre", "right")),
                                    (box[1], box[3], height, ("top", "middle", "bottom"))):
        fits = [name.format(*names) for low, high, name in PARTS  # the named parts that hold it, with 2% of slack
                if start * 6 >= (low - 0.12) * size and end * 6 <= (high + 0.12) * size]
        words.append(fits[0] if fits else "")  # the smallest of them
    across, down = words
    if across and down:
        return ("the %s %s of the screen" % (down.split()[0], across.split()[0])).replace("middle centre", "centre")
    if across or down:
        return "the %s of the screen" % (across or down)
    share = (box[2] - box[0]) * (box[3] - box[1]) / float(width * height)
    return ("the whole screen" if share == 1 else "almost the whole screen" if share >= 0.9
            else "most of the screen" if share >= 0.5 else "the middle of the screen")


def compare(before, after):
    """Compare two pictures, each as read_png() gives it. Returns how many pixels changed and of how
    many, that as a percentage (rounded down), and the box around them."""
    (width_a, height_a, rows_a, file_a), (width_b, height_b, rows_b, file_b) = before, after
    width, height = min(width_a, width_b), min(height_a, height_b)  # the part both have
    full_width, full_height = max(width_a, width_b), max(height_a, height_b)
    changed, across, down = 0, [], []
    both = () if file_a == file_b else zip(rows_a(), rows_b())  # the same bytes are the same picture: no decoding
    for y, (row_a, row_b) in enumerate(both):
        row_a, row_b = row_a[:3 * width], row_b[:3 * width]
        if row_a != row_b:  # most rows of most pairs are the same: no need to look inside
            marks = changed_pixels(row_a, row_b)
            if 1 in marks:
                changed += marks.count(1)
                across += [marks.find(1), marks.rfind(1) + 1]
                down += [y, y + 1]
    if (full_width, full_height) != (width, height):  # what only one of them has counts as changed
        changed += full_width * full_height - width * height
        across += [width if full_height == height else 0, full_width]
        down += [height if full_width == width else 0, full_height]
    box = [min(across), min(down), max(across), max(down)] if across else None
    return {"percent": (10000 * changed // (full_width * full_height)) / 100.0, "changed": changed,
            "pixels": full_width * full_height, "where": where(box, full_width, full_height) if box else "",
            "box": box and dict(zip("xywh", (box[0], box[1], box[2] - box[0], box[3] - box[1]))),
            "before_size": [width_a, height_a], "after_size": [width_b, height_b]}


def shots(folder):
    """{file name: path} of the PNG files directly in FOLDER. Links and hidden files are left out."""
    with os.scandir(folder) as entries:
        return {entry.name: entry.path for entry in entries if entry.is_file(follow_symlinks=False)
                and entry.name.lower().endswith(".png") and not entry.name.startswith(".")}


def sentence(item):
    """One line for one pair: how much changed, where, and the verdict."""
    if "error" in item:
        return "%s: could not compare: %s" % (item["name"], item["error"])
    text = "{name}: {percent:.2f}% of the pixels changed ({changed} of {pixels})".format(**item)
    text += ", spread over " + item["where"] if item["where"] else ""
    if item["before_size"] != item["after_size"]:
        text += (". The sizes differ ({before_size[0]} x {before_size[1]} and {after_size[0]} x {after_size[1]}): "
                 "what only one has counts as changed, so take both the same way").format(**item)
    verdict = "VISIBLE CHANGE" if item["visible"] else "NO VISIBLE CHANGE: a person would not see a difference"
    return "%s. %s" % (text, verdict)


def main(argv=None):
    """Compare from the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: no crash
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("images", nargs="+", metavar="PNG", help="BEFORE and AFTER, or with --moves the frames")
    parser.add_argument("--moves", action="store_true", help="the PNGs are frames of one screen: does anything move?")
    parser.add_argument("--min", type=float, metavar="PERCENT",
                        help="the share of the pixels that must change (default: 2 percent, with --moves 0.2)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    minimum, only = args.min if args.min is not None else 0.2 if args.moves else 2.0, [[], []]
    try:
        if not 0 < minimum <= 100:
            raise ValueError("--min is a percentage: more than 0, at most 100")
        if len(args.images) < 2 or (len(args.images) > 2 and not args.moves):
            raise ValueError("give BEFORE and AFTER (two PNGs or two folders), or --moves and two or more frames")
        if not args.moves and all(map(os.path.isdir, args.images)):
            old, new = shots(args.images[0]), shots(args.images[1])
            pairs = [(name, old[name], new[name]) for name in sorted(set(old) & set(new))]
            only = [sorted(set(old) - set(new)), sorted(set(new) - set(old))]
            if not pairs:
                raise ValueError("no PNG has the same name in %s and in %s: nothing to compare" % tuple(args.images))
        else:
            missing = [path for path in args.images if not os.path.isfile(path)]
            if missing:
                raise ValueError("%s is not a file that exists: give PNG files, or two folders of them" % missing[0])
            short = [os.path.basename(path) for path in args.images]  # file names, when they tell the files apart
            shown = short if len(set(short)) == len(short) else args.images
            pairs = [(" -> ".join(shown[i:i + 2]), args.images[i], args.images[i + 1]) for i in range(len(shown) - 1)]
    except (OSError, ValueError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    results, kept = [], (None, None)
    for name, before, after in pairs:
        result = {"name": name, "before": before, "after": after}
        try:
            images = [kept[1] if path == kept[0] else read_png(path) for path in (before, after)]
            kept = (after, images[1])  # a frame is the before of the next pair: read it once
            result.update(compare(*images))
            result["visible"] = result["percent"] >= minimum
        except (OSError, ValueError) as error:
            result["error"] = str(error) if isinstance(error, ValueError) else "cannot read %s (%s)" % (
                error.filename or before, error.strerror or error)
        results.append(result)
    visible = [item for item in results if item.get("visible")]
    failed = [item for item in results if "error" in item]
    verdict = ("INCOMPLETE" if failed else ("SOMETHING MOVES" if visible else "NOTHING MOVES") if args.moves
               else "VISIBLE CHANGE" if visible else "NO VISIBLE CHANGE")
    if args.json:
        summary = {"pairs": len(results), "visible": len(visible), "enough": bool(visible), "complete": not failed,
                   "largest": max(item.get("percent", 0.0) for item in results), "verdict": verdict, "min": minimum}
        print(json.dumps({"mode": "moves" if args.moves else "change", "tolerance": TOLERANCE, "pairs": results,
                          "only_before": only[0], "only_after": only[1], "summary": summary}, indent=2))
        return 2 if failed else int(not visible)
    print("\n".join(sentence(item) for item in results))
    for names, folder in zip(only, args.images):
        if names:
            print("Only in %s, so not compared: %s" % (folder, ", ".join(names)))
    if failed:
        print("INCOMPLETE, so not a pass: %d of %d pair(s) could not be compared." % (len(failed), len(results)))
    elif visible:
        print("%s: %d of %d pair(s) changed %g%% of the pixels or more."
              % (verdict, len(visible), len(results), minimum))
    elif args.moves:
        print("NOTHING MOVES: nothing moves on this screen in the frames taken (no frame differs from the next by "
              "%g%% of the pixels). Take the frames while the motion runs, with reduced motion off, and check "
              "that the app shows the new code." % minimum)
    else:
        print("NO VISIBLE CHANGE in any pair: none reaches %g%% of the pixels. This usually means one of:\n- %s"
              % (minimum, CAUSES.replace("; ", "\n- ")))
    return 2 if failed else int(not visible)


if __name__ == "__main__":
    sys.exit(main())
