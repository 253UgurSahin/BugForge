#!/usr/bin/env python3
"""Make one accessible, self-contained inline SVG chart from a small JSON data file.

No dependencies, no script and no external request in the output: paste the SVG into a page or template.
Every chart has role="img", a <title> and a <desc> with a plain-text summary (first, last, lowest and highest
per series). Every label is escaped and written as ASCII: data is untrusted, a label with <script> stays text.

Usage:
    python3 chart.py DATA.json --type line|area|bar|spark|donut [--tokens TOKENS.json] [--width W] [--height H]
                     [--title T] [--out FILE] [--json]
DATA.json: {"title": "Revenue per month", "unit": "EUR",
            "series": [{"name": "Revenue", "points": [["2026-01", 1200], ["2026-02", 1100]]}]}
Each point is [label, number]; at most 6 series. A value matrix (heat map) is an HTML table: dashboard.md.
    line   one line per series; the y axis fits the data (it need not start at zero)
    area   one filled series from zero, or several stacked (same length each, no negatives)
    bar    bars from a zero baseline; several series stand side by side (same length each)
    spark  one series, no axes: the small trend line inside a KPI tile
    donut  one series of up to 6 parts of a whole, the total in the middle
Colours: with --tokens (forge-work/design/tokens.json) the roles text, text-muted, border, bg and accent; series
use chart-1, chart-2, ... when the file has them, else hues derived from the accent (check those with contrast.py:
3:1 against bg). Without --tokens: the theme's CSS variables (--color-chart-1 ..., then --color-accent, then
currentColor), so it follows light and dark. Never colour alone: every series has a label, lines a dash pattern.
--json prints {"type", "width", "height", "title", "summary", "background", "colours", "out", "svg", "series":
[{"name", "points", "first", "last", "min", "max"}]}; "background" is null without --tokens, "svg" with --out.

Exit codes:
    0  the chart was written (to stdout, or to --out)
    2  bad input, nothing written: no points, a value that is not a number, a donut with negative values or over 6
       parts (use a bar chart), stacked series of different lengths, an unreadable file, a bad size, --out is a symlink
"""

import argparse
import colorsys
import html
import json
import math
import os
import re
import sys

SIZES = {"spark": (120, 32), "donut": (360, 200)}  # default width and height; the rest: 640 x 280
MAX_BYTES, MAX_SERIES, MAX_PARTS = 1000000, 6, 6
CHAR = 6.6  # rough width of one 12px character, to reserve room for labels
DASHES = ["", "6 3", "2 3", "9 3 2 3", "4 2", "1 3"]  # a second way to tell lines apart
UNSAFE = re.compile(u"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff]")  # not allowed in XML
HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class Bad(Exception):
    """Input this script refuses; the message is plain words for the user."""


def need(fine, message):
    if not fine:
        raise Bad(message)


def clean(value, limit=200):
    """Any label as one line of text without characters XML cannot hold, cut to LIMIT with dots."""
    line = " ".join(UNSAFE.sub("", str(value)).split())
    return line if len(line) <= limit else line[:limit - 3] + "..."


def esc(value, limit=200):
    """Text that is safe inside SVG: markup escaped, everything outside ASCII as a &#number;."""
    return html.escape(clean(value, limit), quote=True).encode("ascii", "xmlcharrefreplace").decode("ascii")


def fmt(value):
    """1200 -> 1,200 and 0.5 -> 0.5: at most two decimals, no trailing zeros."""
    shown = "{:,.2f}".format(value).rstrip("0").rstrip(".") if value != int(value) else "{:,}".format(int(value))
    return "0" if shown == "-0" else shown


def tag(name, inner="", **attrs):
    """One SVG element. INNER is already escaped; numbers get at most one decimal; fill_opacity is fill-opacity."""
    pairs = "".join(' %s="%s"' % (key.replace("_", "-"), ("%.1f" % value).rstrip("0").rstrip(".")
                                  if isinstance(value, float) else value) for key, value in attrs.items() if value != "")
    return "<%s%s>%s</%s>" % (name, pairs, inner, name) if inner else "<%s%s/>" % (name, pairs)


def ticks(low, high, want=5):
    """Axis values in steps of 1, 2 or 5 times a power of ten that cover low to high."""
    high = high if high > low else low + (abs(low) or 1)
    raw = (high - low) / float(want)
    size = 10 ** math.floor(math.log10(raw))
    step = next(mult for mult in (1, 2, 5, 10) if mult * size >= raw) * size
    first, last = int(math.floor(low / step + 1e-9)), int(math.ceil(high / step - 1e-9))
    return [round(index * step, 10) for index in range(first, last + 1)]


def read_json(path, what):
    try:
        need(os.path.getsize(path) <= MAX_BYTES, "%s %s is over %d bytes: aggregate first" % (what, path, MAX_BYTES))
        with open(path, encoding="utf-8-sig", errors="replace") as handle:
            data = json.load(handle)
    except OSError as error:
        raise Bad("cannot read %s %s: %s" % (what, path, error.strerror or error))
    except (ValueError, RecursionError):
        raise Bad("%s %s is not valid JSON" % (what, path))
    need(isinstance(data, dict), "%s %s must be a JSON object: {...}" % (what, path))
    return data


def read_series(data, kind):
    """The series as [{"name", "labels", "values"}], or Bad when the data makes no sense for KIND."""
    raw, series = data.get("series"), []
    need(isinstance(raw, list) and raw, 'no data: "series" must be a list of {"name": ..., "points": [...]}')
    need(len(raw) <= MAX_SERIES, "%d series: over %d cannot be told apart; add the smallest up as Other" % (len(raw), MAX_SERIES))
    for number, item in enumerate(raw, 1):
        points = item.get("points") if isinstance(item, dict) else None
        need(isinstance(points, list) and points, "series %d has no points: show an empty state, not a chart" % number)
        for point in points:  # a number is finite: no true, null, text, NaN or Infinity
            fine = isinstance(point, list) and len(point) == 2 and isinstance(point[0], (str, int, float))
            need(fine and isinstance(point[1], (int, float)) and not isinstance(point[1], bool) and abs(point[1]) < 1e300,
                 "series %d: %s is not [label, number]; leave a missing value out" % (number, clean(json.dumps(point), 60)))
        series.append({"name": clean(item.get("name") or "Series %d" % number),
                       "labels": [clean(point[0]) for point in points], "values": [point[1] for point in points]})
    values = [value for one in series for value in one["values"]]
    need(kind not in ("spark", "donut") or len(series) == 1, "a %s shows one series, this file has %d" % (kind, len(series)))
    need(kind not in ("area", "bar") or len({len(one["values"]) for one in series}) == 1, "the series have different "
         "lengths, so they cannot be stacked or put side by side: give each a point for every label (0 for none)")
    need(kind != "area" or len(series) == 1 or min(values) >= 0, "a stacked area cannot hold negative values: use a line chart")
    if kind == "donut":
        need(min(values) >= 0, "a donut cannot show negative values: use a bar chart")
        need(len(values) <= MAX_PARTS, "a donut with %d parts cannot be read (at most %d): use a bar chart" % (len(values), MAX_PARTS))
        need(sum(values) > 0, "a donut needs a total above zero: show the empty state instead")
    return series


def colours(tokens, count):
    """The paints: text, muted, grid, bg (None without tokens) and one per series."""
    if tokens is None:
        series = ["var(--color-chart-%d, var(--color-accent, currentColor))" % (index + 1) for index in range(count)]
        return {"text": "var(--color-text, currentColor)", "muted": "var(--color-text-muted, currentColor)",
                "grid": "currentColor", "bg": None, "series": series}
    roles = tokens.get("color") if isinstance(tokens.get("color"), dict) else {}

    def role(name, fallback=None):
        value = roles.get(name, roles.get(fallback))
        need(isinstance(value, str) and HEX.match(value.strip()), 'the tokens file needs color.%s as "#rgb" or "#rrggbb"' % name)
        return value.strip()

    def rgb(code):  # "#abc" or "#aabbcc" as three numbers from 0 to 1
        code = code[1:] if len(code) == 7 else "".join(char * 2 for char in code[1:])
        return [int(code[index:index + 2], 16) / 255.0 for index in (0, 2, 4)]

    def lum(parts):  # WCAG relative luminance, 0 (black) to 1 (white)
        return sum(w * (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4) for w, c in zip((0.2126, 0.7152, 0.0722), parts))
    (hue, _, sat), bg, series = colorsys.rgb_to_hls(*rgb(role("accent"))), lum(rgb(role("bg"))), []
    for index in range(count):  # chart-N from the file, else the accent's hue turned and dimmed to 3:1 on a light bg
        turned = colorsys.hls_to_rgb((hue + 0.382 * index) % 1, 0.65 if bg < 0.18 else 0.4, max(sat, 0.5))
        dim = 1 if bg < 0.18 else min(1, ((bg + 0.05) / 3.3 - 0.05) / lum(turned)) ** (1 / 2.4)
        series.append(role("chart-%d" % (index + 1), "accent") if not index or "chart-%d" % (index + 1) in roles else
                      "#%02x%02x%02x" % tuple(int(round(part * dim * 255)) for part in turned))
    return {"text": role("text"), "muted": role("text-muted", "text"), "grid": role("border", "text"), "bg": role("bg"), "series": series}


def summary(kind, title, unit, series):
    """The plain-text summary for <desc>: what a sighted reader takes from the chart."""
    parts = ["%s chart%s%s." % (kind.capitalize(), ": " + title if title else "", " in " + unit if unit else "")]
    for one in series:
        values, labels, total = one["values"], one["labels"], float(sum(one["values"]))
        low, high = values.index(min(values)), values.index(max(values))
        shares = ", ".join("%s %s (%d%%)" % (label, fmt(value), round(value / (total or 1) * 100)) for label, value in zip(labels, values))
        parts.append("Total %s. %s." % (fmt(total), shares) if kind == "donut" else "%s: %d points, first %s (%s), last %s (%s), "
                     "lowest %s (%s), highest %s (%s)." % (one["name"], len(values), fmt(values[0]), labels[0], fmt(values[-1]),
                                                             labels[-1], fmt(values[low]), labels[low], fmt(values[high]), labels[high]))
    return " ".join(parts)


def draw_xy(kind, series, width, height, col):
    """Line, area and bar: grid lines with 1-2-5 ticks, x labels, the marks, then a label per series."""
    stacked, many = kind == "area" and len(series) > 1, len(series) > 1
    direct = many and kind != "bar" and len(series) <= 4  # labels at the line ends; otherwise a list top right
    values = [sum(column) for column in zip(*(one["values"] for one in series))] if stacked else [
        value for one in series for value in one["values"]]
    marks = ticks(min(values), max(values)) if kind == "line" else ticks(min(values + [0]), max(values + [0]))
    labels = max(series, key=lambda one: len(one["labels"]))["labels"]
    left = 24 + CHAR * max(len(fmt(mark)) for mark in marks)  # room for the ticks and half an x label
    right = width - (26 + CHAR * max(len(clean(one["name"], 14)) for one in series) if many else 34.0)
    top, bottom, out = 12.0, height - 24.0, []
    band = (right - left) / float(len(labels) if kind == "bar" else max(len(labels) - 1, 1))
    xs = [left + band * (spot + 0.5 if kind == "bar" else spot) for spot in range(len(labels))]

    def y(value):
        return bottom - (value - marks[0]) / float(marks[-1] - marks[0]) * (bottom - top)
    for mark in marks:
        zero = mark == 0 and kind != "line"  # the baseline that bars and areas stand on
        out.append(tag("line", x1=left, x2=right, y1=y(mark), y2=y(mark), stroke=col["text"] if zero else col["grid"],
                       stroke_opacity="" if zero or col["bg"] else "0.25"))
        out.append(tag("text", fmt(mark), x=left - 6, y=y(mark) + 4, fill=col["muted"], text_anchor="end"))
    out += [tag("text", esc(labels[spot], 10), x=xs[spot], y=height - 7.0, fill=col["muted"], text_anchor="middle")
            for spot in range(0, len(labels), max(1, int(math.ceil(len(labels) * 72.0 / max(right - left, 1)))))]  # no overlap
    base, ends = [0.0] * len(labels), []
    for index, one in enumerate(series):
        paint, vals, wide = col["series"][index], one["values"], min(band * 0.8 / len(series), 48)
        for spot, value in enumerate(vals if kind == "bar" else []):
            hint = tag("title", esc("%s, %s: %s" % (one["labels"][spot], one["name"], fmt(value))))
            out.append(tag("rect", hint, x=xs[spot] - wide * len(series) / 2.0 + wide * index, y=min(y(value), y(0)),
                           width=max(wide - 1, 1.0), height=abs(y(value) - y(0)), fill=paint))
        tops = [under + value for under, value in zip(base, vals)] if stacked else vals
        line = " ".join("%.1f,%.1f" % (xs[spot], y(value)) for spot, value in enumerate(tops))
        if kind == "area":
            floor = " ".join("%.1f,%.1f" % (xs[spot], y(base[spot])) for spot in reversed(range(len(vals))))
            out.append(tag("polygon", points=line + " " + floor, fill=paint, fill_opacity="0.55" if stacked else "0.2"))
        dash = DASHES[index] if kind == "line" else ""
        if kind != "bar":
            out.append(tag("polyline", points=line, fill="none", stroke=paint, stroke_width=2, stroke_dasharray=dash))
            out.append(tag("circle", cx=xs[len(vals) - 1], cy=y(tops[-1]), r=3, fill=paint))
        end = y((base[len(vals) - 1] + tops[-1]) / 2.0) if stacked else y(tops[-1])
        ends.append([end if direct else top + 6 + 16 * index, one["name"], paint, dash])
        base = tops if stacked else base
    ends.sort(key=lambda end: end[0])
    for index, end in enumerate(ends if many else []):  # the series labels, pushed apart so they never overlap
        end[0] = max(end[0], ends[index - 1][0] + 13) if index else end[0]
        out.append(tag("line", x1=right + 6, x2=right + 18, y1=end[0], y2=end[0], stroke=end[2], stroke_width=3,
                       stroke_dasharray=end[3]))
        out.append(tag("text", esc(end[1], 14), x=right + 22, y=end[0] + 4, fill=col["text"]))
    return out


def draw_spark(series, width, height, col):
    values = series[0]["values"]  # a flat series runs through the middle
    low, span, step = min(values), float(max(values) - min(values)), (width - 8) / float(max(len(values) - 1, 1))
    points = [(4 + step * spot, height - 4 - ((value - low) / span if span else 0.5) * (height - 8))
              for spot, value in enumerate(values)]
    return [tag("polyline", points=" ".join("%.1f,%.1f" % point for point in points), fill="none",
                stroke=col["series"][0], stroke_width="1.5", stroke_linejoin="round"),
            tag("circle", cx=points[-1][0], cy=points[-1][1], r="2.5", fill=col["series"][0])]


def draw_donut(series, width, height, col, unit):
    """Parts as arcs of one circle with a 2px gap, the total in the middle and a labelled list beside it."""
    values, labels, total = series[0]["values"], series[0]["labels"], float(sum(series[0]["values"]))
    radius = min(height, width / 2.0) / 2.0 - 16
    centre, around, start, out = radius + 16, 2 * math.pi * radius, 0.0, []
    for index, (label, value) in enumerate(zip(labels, values)):
        length, paint = value / total * around, col["series"][index]
        line = esc("%s: %s (%d%%)" % (clean(label, 16), fmt(value), round(value / total * 100)))
        if value:
            out.append(tag("circle", tag("title", line), cx=centre, cy=centre, r=radius, fill="none", stroke=paint,
                           stroke_width=radius * 0.36, stroke_dasharray="%.1f %.1f" % (max(length - 2, 0.5), around),
                           stroke_dashoffset=-start, transform="rotate(-90 %.1f %.1f)" % (centre, centre)))
        start += length
        out.append(tag("rect", x=centre * 2 + 8, y=14 + 20 * index, width=10, height=10, fill=paint))
        out.append(tag("text", line, x=centre * 2 + 24, y=23 + 20 * index, fill=col["text"]))
    out.append(tag("text", fmt(total), x=centre, y=centre + 2, fill=col["text"], text_anchor="middle", font_size=16))
    return out + ([tag("text", esc(unit), x=centre, y=centre + 17, fill=col["muted"], text_anchor="middle")] if unit else [])


def main(argv=None):
    """Run from the command line. Returns the exit code: 0 or 2 (see the top)."""
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("data", metavar="DATA.json", help="the data file (see above)")
    parser.add_argument("--type", required=True, choices=["line", "area", "bar", "spark", "donut"], help="the form of the chart")
    parser.add_argument("--tokens", metavar="TOKENS.json", help="forge's design tokens, for fixed colours")
    parser.add_argument("--width", type=int, help="width in px (default 640; spark 120, donut 360)")
    parser.add_argument("--height", type=int, help="height in px (default 280; spark 32, donut 200)")
    parser.add_argument("--title", help="the chart's accessible name (default: the data's title)")
    parser.add_argument("--out", metavar="FILE", help="write the SVG here instead of to stdout")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    kind, size = args.type, SIZES.get(args.type, (640, 280))
    width, height = size[0] if args.width is None else args.width, size[1] if args.height is None else args.height
    try:
        need((16 if kind == "spark" else 100) <= min(width, height) and max(width, height) <= 4000,
             "--width and --height: from 100 to 4000 px (a spark: from 16 px)")
        data = read_json(args.data, "the data file")
        series = read_series(data, kind)
        col = colours(read_json(args.tokens, "the tokens file") if args.tokens else None,
                      len(series[0]["values"]) if kind == "donut" else len(series))
        title, unit = clean(args.title or data.get("title") or "%s chart" % kind.capitalize()), clean(data.get("unit") or "", 20)
        desc = summary(kind, title, unit, series)
        body = (draw_spark(series, width, height, col) if kind == "spark" else
                draw_donut(series, width, height, col, unit) if kind == "donut" else draw_xy(kind, series, width, height, col))
        name = "c%x" % (sum((spot + 1) * ord(char) for spot, char in enumerate(kind + desc)) % 2 ** 32)  # ids differ per chart
        head = tag("svg", " ", xmlns="http://www.w3.org/2000/svg", viewBox="0 0 %d %d" % (width, height), width=width,
                   height=height, role="img", aria_labelledby="%s-t %s-d" % (name, name), font_family="inherit", font_size=12)
        svg = "\n".join([head[:-len(" </svg>")], tag("title", esc(title), id=name + "-t"), tag("desc", esc(desc, 4000), id=name + "-d")]
                        + body + ["</svg>"])
        if args.out:  # never through a symlink: it could point at any file
            need(not os.path.islink(args.out), "--out %s is a symlink: give the path of a real file" % args.out)
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(args.out, flags, 0o644), "w", encoding="ascii", newline="\n") as handle:
                handle.write(svg + "\n")
    except (Bad, OSError) as error:
        message = error if isinstance(error, Bad) else "cannot write %s: %s" % (args.out, error.strerror or error)
        print("error: %s" % clean(message, 400).encode("ascii", "backslashreplace").decode("ascii"), file=sys.stderr)
        return 2
    report = {"type": kind, "width": width, "height": height, "title": title, "summary": desc, "background": col["bg"],
              "colours": col["series"], "out": args.out, "svg": None if args.out else svg,
              "series": [{"name": one["name"], "points": len(one["values"]), "first": one["values"][0],
                          "last": one["values"][-1], "min": min(one["values"]), "max": max(one["values"])} for one in series]}
    print(json.dumps(report, indent=2) if args.json else svg if not args.out else
          "wrote %s (%s chart, %d x %d px)" % (args.out, kind, width, height))
    return 0


if __name__ == "__main__":
    sys.exit(main())
