#!/usr/bin/env python3
"""Write the app's theme CSS from the design tokens, as components.md's ## Theme maps them.

Every value lives in forge-work/design/tokens.json. This turns it into the CSS custom properties
the components use, so nobody writes some 70 variables out by hand, and writes them again after
every change to the tokens (forge-brand's palette included).

Usage:
    python3 theme.py forge-work/design/tokens.json --tailwind no              print the block
    python3 theme.py forge-work/design/tokens.json --tailwind 4 --write app/globals.css

--tailwind is the Tailwind line of components.md. 4: the first block is @theme static { } with
only your colours (--color-*: initial) and breakpoints, and no --space-* (Tailwind's --spacing
does that); 3 and no: plain :root blocks (Tailwind 3 maps them in tailwind.config.js). A dark
group in color becomes a prefers-color-scheme: dark block. --write puts the block in that file
between the forge theme marks, in place of the one there; the first time right after the
@charset, @import, @source and other statements at its top, or at the very top when there are
none, never inside a rule (a new file is made). Numbers get px (not a weight), font names get
quotes where they need them ("Source Serif 4"), other strings stay as they are: contrast.py
checks the colours.

Exit codes:
    0  printed or written
    2  bad input: no such file, not JSON, a group or value of the wrong shape, a name that is not
       letters, digits, - and _, a value with ; { } < > or a line break, a file with one mark only
"""

import argparse
import json
import os
import re
import sys

START = "/* forge theme start: theme.py writes this from forge-work/design/tokens.json. Change the tokens. */"
END = "/* forge theme end */"
NAME = re.compile(r"^[A-Za-z0-9_-]+$")
UNSAFE = re.compile(r"[;{}<>\r\n]")  # a value that could end the declaration or the block
KNOWN = {"color", "font", "type", "space", "radius", "shadow", "motion", "layout", "size", "breakpoint", "pairs"}
STATEMENT = re.compile(r"\s*(?:/\*.*?\*/|@[\w-]+[^;{}]*;)", re.S)  # a comment, or an @-rule without a block
DECLARED = re.compile(r"(--[\w-]+)\s*:(?!\s*initial)")  # a custom property set (not one cleared)
IDENT = r"-?[A-Za-z_\x80-\U0010ffff][-\w\x80-\U0010ffff]*"  # a CSS identifier: Inter, -apple-system, Café
FAMILY = re.compile(r"%s(?:[ \t]+%s)*\Z" % (IDENT, IDENT))  # a font name of identifiers needs no quotes


def value(where, item, px=True, font=False):
    """A token value as CSS: a number gets px, a string stays, and in a font stack (font) the names that
    need them get quotes. Raises ValueError on anything else."""
    if isinstance(item, dict) and ("$value" in item or "value" in item):  # {"$value": ...}, {"value": ...}
        item = item.get("$value", item.get("value"))
        item = item.get("hex", item) if isinstance(item, dict) else item
    if isinstance(item, bool) or not isinstance(item, (str, int, float)):
        raise ValueError("%s must be a value (a number or a string), not %s" % (where, json.dumps(item)))
    if isinstance(item, str) and (UNSAFE.search(item) or not item.strip()):
        raise ValueError("%s is %s: write a plain CSS value, without ; { } < > or a line break"
                         % (where, json.dumps(item)))
    if not isinstance(item, str):
        return "%gpx" % item if px else "%g" % item
    return font_names(item.strip()) if font else item.strip()


def font_names(stack):
    """A font stack with double quotes around each name that needs them: "Source Serif 4", Georgia,
    serif. A name made of identifiers needs none (Inter Variable, -apple-system, Café Sans), a generic
    family must have none, and a name with a quote or a bracket in it (quoted, var()) stays as it is."""
    names = []
    for part in stack.split(","):
        if names and names[-1].count("(") > names[-1].count(")"):  # a comma inside var( ): not between names
            names[-1] += "," + part
        else:
            names.append(part)
    quoted = []
    for name in map(str.strip, names):
        if name and not FAMILY.match(name) and not re.search("[\"'()]", name):
            name = '"%s"' % re.sub(r"[ \t]+", " ", name)  # one space between words, as CSS reads them unquoted
        quoted.append(name)
    return ", ".join(quoted)


def group(tokens, name):
    """The named group as {key: item}, {} when it is not there. Notes (_ or $) are left out."""
    found = tokens.get(name, {})
    if not isinstance(found, dict):
        raise ValueError("%s must be a group, such as {\"sm\": ...}, not %s" % (name, json.dumps(found)[:60]))
    for key in found:
        if not key.startswith(("_", "$")) and not NAME.match(key):
            raise ValueError("%s.%s: a name may hold only letters, digits, - and _" % (name, key))
    return {key: item for key, item in found.items() if not key.startswith(("_", "$"))}


def colours(found, prefix="color", path=""):
    """[(--color-name, value)] from a colour group; nested groups get dashed names (text.muted)."""
    lines = []
    for key, item in found.items():
        if key.startswith(("_", "$")):
            continue
        if not NAME.match(key):
            raise ValueError("%s.%s: a name may hold only letters, digits, - and _" % (prefix, path + key))
        if isinstance(item, dict) and "$value" not in item and "value" not in item:
            lines += colours(item, prefix, path + key + "-")
        else:
            lines.append(("--color-" + path + key, value("%s.%s" % (prefix, path + key), item)))
    return lines


def space_name(item):
    """16 -> '4' and 6 -> '1_5': the step on a 4px grid, as a name."""
    return ("%g" % (item / 4.0)).replace(".", "_")


def blocks(tokens, tailwind):
    """The theme CSS from parsed tokens, as one string."""
    color = group(tokens, "color")
    dark = colours(group(color, "dark"), "color.dark") if "dark" in color else []
    first = [("--color-*", "initial")] if tailwind == "4" else []
    first += colours({key: item for key, item in color.items() if key != "dark"})
    first += [("--font-" + key, value("font." + key, item, font=True))
              for key, item in group(tokens, "font").items()]
    for step, item in group(tokens, "type").items():
        if not (isinstance(item, dict) and {"size", "line", "weight"} <= set(item)):
            raise ValueError('type.%s needs size, line and weight, such as {"size": 16, "line": 24, '
                             '"weight": 400}' % step)
        first += [("--text-" + step, value("type.%s.size" % step, item["size"])),
                  ("--text-%s--line-height" % step, value("type.%s.line" % step, item["line"])),
                  ("--text-%s--font-weight" % step, value("type.%s.weight" % step, item["weight"], px=False))]
    space = tokens.get("space", [])
    numbers = isinstance(space, list) and all(isinstance(n, (int, float)) for n in space)
    if not numbers or any(isinstance(n, bool) for n in space):
        raise ValueError("space must be a list of numbers in px, such as [0, 4, 8, 16]")
    first += [] if tailwind == "4" else [("--space-" + space_name(n), value("space", n)) for n in space]
    first += [("--radius-" + key, value("radius." + key, item)) for key, item in group(tokens, "radius").items()]
    first += [("--shadow-" + key, value("shadow." + key, item)) for key, item in group(tokens, "shadow").items()]
    motion = group(tokens, "motion")
    first += [("--ease-standard" if key == "ease" else "--" + key, value("motion." + key, item))
              for key, item in motion.items() if key == "ease" or key.startswith("ease-")]
    points = [(key, value("breakpoint." + key, item)) for key, item in group(tokens, "breakpoint").items()]
    if tailwind == "4":
        first += [("--breakpoint-*", "initial")] + [("--breakpoint-" + key, item) for key, item in points]
    second = [("--duration-" + key, value("motion." + key, item))
              for key, item in motion.items() if key != "ease" and not key.startswith("ease-")]
    second += [("--layout-" + key, value("layout." + key, item)) for key, item in group(tokens, "layout").items()]
    second += [("--size-" + key, value("size." + key, item)) for key, item in group(tokens, "size").items()]
    out = [START, "@theme static {" if tailwind == "4" else ":root {"]
    out += ["  %s: %s;" % pair for pair in first] + ["}"]
    out += [":root {"] + ["  %s: %s;" % pair for pair in second] + ["}"] if second else []
    if dark:
        out += ["@media (prefers-color-scheme: dark) {", "  :root {"] + ["    %s: %s;" % pair for pair in dark]
        out += ["  }", "}"]
    if points and tailwind != "4":
        out.append("/* Breakpoints go into media queries as numbers (var() fails there): %s. */"
                   % ", ".join("%s %s" % pair for pair in points))
    return "\n".join(out + [END]) + "\n"


def read_tokens(path):
    if not os.path.isfile(path):
        raise ValueError("%s is not a file that exists" % path)
    try:
        with open(path, encoding="utf-8-sig") as handle:
            tokens = json.load(handle)
    except UnicodeDecodeError:
        raise ValueError("%s is not UTF-8 text: save it as UTF-8" % path)
    except json.JSONDecodeError as error:
        raise ValueError("%s is not valid JSON (line %d, column %d)" % (path, error.lineno, error.colno))
    if not isinstance(tokens, dict):
        raise ValueError("%s must hold a JSON object of token groups" % path)
    return tokens


def write(path, css):
    """Put CSS in the file at PATH between the marks, or the first time after its top statements (at
    the very top when it has none). Returns the names of our variables the file also sets outside the
    block (the scaffold's)."""
    text = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig", newline="") as handle:
            text = handle.read()
    newline = "\r\n" if "\r\n" in text else "\n"
    css = css.replace("\n", newline)
    if (START in text) != (END in text) or text.find(START) > text.find(END):
        raise ValueError("%s has only one of the theme marks, or they are in the wrong order: put back the "
                         "block between them, or remove what is left of it" % path)
    if START in text:
        end = text.index(END) + len(END)
        text = text[:text.index(START)] + css.rstrip(newline) + text[end:]
    else:
        top = 0  # no statement at the top: the block goes first, before the first rule, not inside it
        while STATEMENT.match(text, top):
            top = STATEMENT.match(text, top).end()
        next_line = text.find("\n", top) + 1 or len(text)  # where the next line starts, or the end of the file
        if top and not text[top:next_line].strip():  # nothing else on the last statement's line: go below it
            top = next_line
        before = newline if text[:top].strip() else ""
        after = newline if text[top:].strip() and not text[top:].startswith(newline) else ""
        text = text[:top] + before + css + after + text[top:]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    outside = text[:text.index(START)] + text[text.index(END):]
    return sorted(set(DECLARED.findall(css)) & set(DECLARED.findall(outside)))


def main(argv=None):
    """Print or write the theme. Returns the exit code: 0 or 2 (see the top)."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: escapes, no crash
    parser = argparse.ArgumentParser(description="Write the theme CSS from tokens.json.")
    parser.add_argument("tokens", help="forge-work/design/tokens.json")
    parser.add_argument("--tailwind", required=True, choices=["4", "3", "no"],
                        help="the Tailwind line of components.md")
    parser.add_argument("--write", metavar="FILE", help="put the block in this theme file instead of printing it")
    args = parser.parse_args(argv)
    try:
        tokens = read_tokens(args.tokens)
        css = blocks(tokens, args.tailwind)
        twice = write(args.write, css) if args.write else []
    except (OSError, ValueError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    for name in sorted(set(tokens) - KNOWN):
        if not name.startswith(("_", "$")):
            print("note: the group %s is not in the theme: map it in components.md first" % name, file=sys.stderr)
    if twice:
        print("note: %s also sets %s outside the forge theme block (the scaffold's own theme?): remove those "
              "lines, or they win over the tokens" % (args.write, ", ".join(twice)), file=sys.stderr)
    if args.write:
        print("Wrote the theme from %s into %s (%d variables)."
              % (args.tokens, args.write, len(DECLARED.findall(css))))
    else:
        print(css, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
