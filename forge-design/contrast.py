#!/usr/bin/env python3
"""Check the colour contrast of design tokens against WCAG 2 level AA.

Works out the contrast ratio of every text and background pair in a token file and says which
are too faint to read. Run it after every palette change, the rebrand included.

Usage:
    python3 contrast.py forge-work/design/tokens.json          check every pair in the file
    python3 contrast.py forge-work/design/tokens.json --json   machine-readable output
    python3 contrast.py "#6b7280" "#ffffff"                     one pair: text, then background

The file's "pairs" list names colours from its "color" group (there is no guessing):
    [["text", "bg"], ["text-muted", "surface", "large"], ["border-input", "bg", "ui"]]
The third item is optional. normal (the default): body text, needs 4.5:1. large: text from
24px, or from 18.66px bold, needs 3:1. ui: input borders, icons and focus rings, needs 3:1.
Every text colour (text, fg or on as a part of its name: text-muted, on-accent, dark-text)
must be in a pair, or it was never checked; names with "disabled" are left out (WCAG asks
nothing of disabled controls). Nested groups get dashed names ({"dark": {"bg": ..}} is
"dark-bg"); {"value": ..}, {"$value": ..} and {"$value": {"hex": ..}} work too. Colours in the
file are #rgb or #rrggbb; on the command line the # may be left out. Each failing pair comes
with the nearest colour that passes, so the fix is one edit in the tokens.

Exit codes:
    0  every pair passes AA and every text colour is in a pair
    1  a pair fails AA, or a text colour is in no pair
    2  bad input: a missing or invalid file, no "pairs" list, a malformed pair, an unknown or
       doubled colour name, or a colour that is not #rgb or #rrggbb
"""

import argparse
import json
import math
import os
import re
import sys

HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
TEXT_NAME = re.compile(r"(^|-)(text|fg|on)(-|$)")  # text, text-muted, on-accent, dark-text, fg
DISABLED = re.compile(r"(^|-)disabled(-|$)")  # WCAG asks no contrast of disabled controls
NEEDS = {"normal": (4.5, 7.0), "large": (3.0, 4.5), "ui": (3.0, 3.0)}  # kind: (AA, AAA)
BLACK, WHITE = (0, 0, 0), (255, 255, 255)
WHY = {"normal": "text this faint is hard to read with low vision, older eyes or a phone in the sun",
       "large": "even large text this faint is hard to read with low vision or a phone in the sun",
       "ui": "people with low vision cannot see where the input, icon or focus ring is"}


def parse_hex(value):
    """'#abc' or '#aabbcc' -> (r, g, b) from 0 to 255."""
    match = HEX.match(value.strip()) if isinstance(value, str) else None
    if not match:
        raise ValueError("not a hex colour: %r" % (value,))
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))


def luminance(rgb):
    """Relative luminance from WCAG 2: 0 for black, 1 for white."""
    def channel(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def rgb_ratio(one, two):
    light, dark = sorted((luminance(one), luminance(two)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def ratio(fg, bg):
    """The WCAG contrast ratio of two hex colours, from 1 (same) to 21 (black on white)."""
    return rgb_ratio(parse_hex(fg), parse_hex(bg))


def flatten(group, prefix="", found=None):
    """{"text": {"muted": "#999"}} -> {"text-muted": "#999"}. Keys starting with $ or _ are notes.
    A value that is not a string is kept as it is, so the error can name it. Two names that end
    up the same ({"text-muted": ..} next to {"text": {"muted": ..}}) are a ValueError."""
    found = {} if found is None else found
    if isinstance(group, dict) and "value" not in group and "$value" not in group:
        for key, value in group.items():
            if not key.startswith(("$", "_")):
                flatten(value, prefix + "-" + key if prefix else key, found)
        return found
    if isinstance(group, dict):  # a token: {"$value": "#fff"} or {"$value": {"hex": "#fff"}}
        group = group.get("$value", group.get("value"))
        if isinstance(group, dict) and isinstance(group.get("hex"), str):
            group = group["hex"]
    if prefix in found:
        raise ValueError("two colours are both called %r: rename one of them" % prefix)
    found[prefix] = group.strip() if isinstance(group, str) else group
    return found


def colours(tokens):
    """Every value in the token file's colour group, by dashed name. {} when there is none."""
    for key in ("color", "colors", "colour"):
        if key in tokens:
            if not isinstance(tokens[key], dict):
                raise ValueError('"%s" must be a group of named colours, such as {"bg": "#ffffff"}' % key)
            return flatten(tokens[key])
    return {}


def check_pair(number, pair, cols):
    """(fg, bg, kind) of one pair, or a ValueError that says what is wrong with it."""
    shape = isinstance(pair, (list, tuple)) and len(pair) in (2, 3)
    if not shape or not all(isinstance(item, str) for item in pair):
        raise ValueError('pair %d must look like ["text", "bg"] or ["text", "bg", "large"], not %s'
                         % (number, json.dumps(pair)))
    kind = pair[2] if len(pair) == 3 else "normal"
    if kind not in NEEDS:
        raise ValueError("pair %d: the third item must be normal, large or ui, not %r" % (number, kind))
    for name in pair[:2]:
        if name not in cols:
            raise ValueError("pair %d: there is no colour named %r" % (number, name))
        if not isinstance(cols[name], str) or not HEX.match(cols[name]):
            raise ValueError("pair %d: %s is %s, write it as #rgb or #rrggbb"
                             % (number, name, json.dumps(cols[name])))
    return pair[0], pair[1], kind


def check(cols, pairs):
    """One row per pair with its ratio and grades. Pure, so tests can call it directly.
    The ratio is cut (not rounded) to 2 decimals, so 4.499 shows as 4.49 and fails."""
    rows = []
    for number, pair in enumerate(pairs, start=1):
        fg, bg, kind = check_pair(number, pair, cols)
        value = ratio(cols[fg], cols[bg])
        aa, aaa = NEEDS[kind]
        rows.append({"fg": fg, "bg": bg, "kind": kind, "fg_hex": cols[fg], "bg_hex": cols[bg],
                     "ratio": math.floor(value * 100) / 100, "needs": aa,
                     "aa": value >= aa, "aaa": value >= aaa})
    return rows


def unpaired(cols, pairs):
    """Text colours that no pair uses, so their contrast was never checked. Disabled ones are fine."""
    used = {name for pair in pairs for name in pair[:2]}
    return [name for name in cols
            if TEXT_NAME.search(name) and not DISABLED.search(name) and name not in used]


def nearest_passing(colour, other, need, both_ways=True):
    """The colour closest to COLOUR (fewest 1% steps toward black or white) that reaches NEED:1
    on OTHER, or None. With both_ways=False it only moves away from OTHER: right for a
    background, where flipping a light page to dark is no small fix."""
    start, against = parse_hex(colour), parse_hex(other)
    away = BLACK if luminance(start) <= luminance(against) else WHITE
    best = None
    for target in ((BLACK, WHITE) if both_ways else (away,)):
        for step in range(1, 101):
            mixed = tuple(int(round(c + (t - c) * step / 100.0)) for c, t in zip(start, target))
            if rgb_ratio(mixed, against) >= need:
                if best is None or step < best[0]:
                    best = (step, "#%02x%02x%02x" % mixed)
                break
    return best[1] if best else None


def finding(row, source):
    """A failing row as a finding in the forge format, with a fix that names real colours.
    The text colour comes first: changing a background changes every pair on it."""
    better_fg = nearest_passing(row["fg_hex"], row["bg_hex"], row["needs"])
    better_bg = nearest_passing(row["bg_hex"], row["fg_hex"], row["needs"], both_ways=False)
    if source == "command line":  # two colours, no names and no token file
        fg_text, bg_text, tail = " as the text colour", " as the background", ""
    else:
        fg_text = " for " + row["fg"]
        bg_text = " for %s (changing %s changes every pair that uses it)" % (row["bg"], row["bg"])
        tail = ". Change it in the tokens (not per component) and run contrast.py again"
    options = [colour + text for colour, text in ((better_fg, fg_text), (better_bg, bg_text)) if colour]
    fix = ("use " + ", or ".join(options) if options else "pick a much lighter or darker colour") + tail
    return {"severity": "high",
            "title": "Too little contrast: %s on %s (%.2f:1, needs %g:1)"
                     % (row["fg"], row["bg"], row["ratio"], row["needs"]),
            "where": "%s: %s on %s" % (source, row["fg"], row["bg"]),
            "why": "%s; WCAG AA asks for %g:1" % (WHY[row["kind"]], row["needs"]), "fix": fix}


def unpaired_finding(name, source, cols):
    """A text colour that is in no pair, as a finding with an example pair to add."""
    match = TEXT_NAME.search(name)
    rest = name[match.end():] if match.group(2) == "on" else ""
    guess = name[:match.start(2)] + (rest or "bg")  # on-accent -> accent, dark-text -> dark-bg
    example = '["%s", "%s"]' % (name, guess if guess in cols else "<its background>")
    return {"severity": "high", "title": "Not checked: the text colour %s is in no pair" % name,
            "where": "%s: color %s" % (source, name),
            "why": "a text colour that is in no pair was never checked, so it may be unreadable",
            "fix": "add a pair for each background it is used on, such as %s, to \"pairs\" "
                   "and run contrast.py again" % example}


def grade(row):
    if row["kind"] == "ui":
        return "PASS" if row["aa"] else "FAIL"
    return "AAA" if row["aaa"] else ("AA" if row["aa"] else "FAIL")


def format_human(rows, findings, missing):
    """One line per pair, then a block per finding, then the verdict."""
    lines = []
    for row in rows:
        kind = "" if row["kind"] == "normal" else "  (%s)" % row["kind"]
        lines.append("%-5s %6.2f:1  %s on %s%s" % (grade(row), row["ratio"], row["fg"], row["bg"], kind))
    lines.append("")
    for f in findings:
        lines += ["%-8s  %s" % (f["severity"].upper(), f["title"]), "          where: " + f["where"],
                  "          why:   " + f["why"], "          fix:   " + f["fix"], ""]
    noun = "pair" if len(rows) == 1 else "pairs"
    summary = "%d %s checked, %d failing WCAG AA" % (len(rows), noun, len(findings) - len(missing))
    lines.append(summary + (", %d text colour(s) in no pair." % len(missing) if missing else "."))
    lines.append("FAIL: fix the findings above." if findings else "PASS: every pair meets WCAG AA.")
    return "\n".join(lines)


def read_tokens(path):
    """The parsed token file, or a ValueError in plain words."""
    if os.path.isdir(path):
        raise ValueError("%s is a folder: give the tokens.json file inside it" % path)
    if not os.path.isfile(path):
        hint = ""
        if HEX.match("#" + path.strip().lstrip("#")):  # one colour instead of two
            hint = ': give two colours, text then background, such as "#6b7280" "#ffffff"'
        raise ValueError("%s is not a file that exists%s" % (path, hint))
    try:
        with open(path, encoding="utf-8-sig") as handle:  # -sig: a byte order mark is fine too
            return json.load(handle)
    except UnicodeDecodeError:
        raise ValueError("%s is not UTF-8 text: save it as UTF-8 and run contrast.py again" % path)
    except json.JSONDecodeError as error:
        raise ValueError("%s is not valid JSON (line %d, column %d): look for a missing or extra "
                         "comma, quote or bracket" % (path, error.lineno, error.colno))


def read_input(inputs):
    """(source, colours, pairs) from the command line: one token file, or two colours."""
    if len(inputs) == 2:
        pair = ["#" + value.strip().lstrip("#") for value in inputs]  # the # is optional here
        if not all(HEX.match(value) for value in pair):
            raise ValueError('two arguments must be two colours, such as "#6b7280" "#ffffff"')
        return "command line", {pair[0]: pair[0], pair[1]: pair[1]}, [pair]
    if len(inputs) != 1:
        raise ValueError("give one token file, or two colours")
    path = inputs[0]
    tokens = read_tokens(path)
    if not isinstance(tokens, dict):
        raise ValueError("%s must hold a JSON object" % path)
    cols = colours(tokens)
    if not cols:
        raise ValueError('%s has no colours: put them in a "color" group' % path)
    pairs = tokens.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError('%s needs a "pairs" list with every text and background combination the '
                         'app uses, such as [["text", "bg"], ["text-muted", "bg"]]' % path)
    return path, cols, pairs


def main(argv=None):
    """Run the check from the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: escapes, no crash
    parser = argparse.ArgumentParser(description="Check the WCAG AA colour contrast of design tokens.")
    parser.add_argument("inputs", nargs="+", metavar="TOKENS_OR_COLOURS",
                        help="a tokens.json file, or two colours: text and background")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        source, cols, pairs = read_input(args.inputs)
        rows = check(cols, pairs)
    except RecursionError:
        print("error: the token file is nested too deeply to read", file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    missing = unpaired(cols, pairs)
    findings = [finding(row, source) for row in rows if not row["aa"]]
    findings += [unpaired_finding(name, source, cols) for name in missing]
    summary = {"pairs": len(rows), "failing": len(findings) - len(missing), "unchecked": len(missing),
               "high": len(findings), "verdict": "FAIL" if findings else "PASS"}
    print(json.dumps({"pairs": rows, "findings": findings, "summary": summary}, indent=2) if args.json
          else format_human(rows, findings, missing))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
