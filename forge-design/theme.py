#!/usr/bin/env python3
"""Write the app's theme CSS from the design tokens, as components.md's ## Theme maps them.

Every value lives in forge-work/design/tokens.json: run it again after each change there (brand's too).

Usage:
    python3 theme.py forge-work/design/tokens.json --tailwind no              print the block
    python3 theme.py forge-work/design/tokens.json --tailwind 4 --write app/globals.css
    python3 theme.py forge-work/design/tokens.json --tailwind no --default dark --write app/globals.css
    python3 theme.py forge-work/design/tokens.json --write resources/sass/_tokens.scss

--tailwind is components.md's Tailwind line: 4 writes @theme static { } with only your colours
(--color-*: initial) and breakpoints and no --space-* (Tailwind's --spacing does that); 3 and no write
plain :root blocks. A dark group in color switches with data-theme on <html> (light, dark or system),
each theme with its color-scheme: --default is the theme while there is none (system when not given),
--dark-selector what an app's own switch sets for dark (.dark; it works out "system" itself). Without
--dark-selector, Tailwind's dark: follows it too: 4 gets @custom-variant dark, 3 a darkMode comment.
--format scss ($variables) and js (export const tokens) hold literal values, a var(--color-x) as that
colour, for a theme that computes with them (Bootstrap's Sass, MUI's createTheme): var() breaks it.
--write FILE (.scss, .js or .ts pick the format) puts it between the forge theme marks, in place of
the block there; the first time after the @charset, @import, @use, @source and other statements at
the top, never inside a rule (a new file is made). Numbers get px (not a weight; a type step's
stretch gets %, its tracking em), font names quotes where they need them ("Source Serif 4"), other
strings stay as they are. components.md (## Theme) has what each option writes.

Exit codes:
    0  printed or written
    2  bad input: no such file, not JSON, a group or value of the wrong shape, a name that is not
       letters, digits, - and _, a value with ; { } < > or a line break, a file with one mark only,
       a --dark-selector that is not one class or one attribute
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
STATEMENT = re.compile(r"""\s*(?:/\*.*?\*/|@[\w-]+(?:"[^"\n]*"|'[^'\n]*'|url\([^)"'{}]*\)"""
                       r"""|(?!url\([^)"'{}]*\))[^;{}"'])*;)""", re.S)  # a comment, or an @-rule without a
# block: a ; or a brace inside quotes or url() ends neither (Google Fonts URLs hold wght@400;700)
DECLARED = re.compile(r"(--[\w-]+)\s*:(?!\s*initial)")  # a custom property set (not one cleared)
IDENT = r"-?[A-Za-z_\x80-\U0010ffff][-\w\x80-\U0010ffff]*"  # a CSS identifier: Inter, -apple-system, Café
FAMILY = re.compile(r"%s(?:[ \t]+%s)*\Z" % (IDENT, IDENT))  # a font name of identifiers needs no quotes
NUMBER = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:%|[A-Za-z]+)?\Z")  # 125%, 1.2, -0.02em: a value, not a font name
SELECTOR = re.compile(r"""(?:\.[A-Za-z_][\w-]*|\[[A-Za-z_][\w-]*(?:=(?:"[\w -]*"|'[\w -]*'|[\w-]+))?\])\Z""")
NOT_LIGHT, DARK, SYSTEM = ':root:not([data-theme="light"])', ':root[data-theme="dark"]', ':root[data-theme="system"]'
WHEN = {"system": (NOT_LIGHT, DARK), "light": (SYSTEM, DARK),  # where the dark theme shows: while the device is dark,
        "dark": (SYSTEM, ':root:not([data-theme="light"], [data-theme="system"])')}  # and at any time, per --default
FORMATS = {".scss": "scss", ".js": "js", ".mjs": "js", ".ts": "js", ".mts": "js"}  # --write's extension
VAR = re.compile(r"var\(--color-([\w-]+)\)")  # a colour that names another: chart-1 is var(--color-accent)


def value(where, item, px=True, font=False):
    """A token value as CSS: a number gets px, a string stays, and in a font stack (font) the names that
    need them get quotes. Raises ValueError on anything else."""
    if isinstance(item, dict) and ("$value" in item or "value" in item):  # {"$value": ...}, {"value": ...}
        item = item.get("$value", item.get("value"))
        item = item.get("hex", item) if isinstance(item, dict) else item
    if isinstance(item, bool) or not isinstance(item, (str, int, float)):
        raise ValueError("%s must be a value (a number or a string), not %s" % (where, json.dumps(item)))
    if isinstance(item, str) and (UNSAFE.search(item) or not item.strip()):
        raise ValueError("%s is %s: write a plain CSS value, no ; { } < > or line break" % (where, json.dumps(item)))
    if not isinstance(item, str):
        return "%gpx" % item if px else "%g" % item
    return font_names(item.strip()) if font else item.strip()


def literal(item, names, links=5):
    """ITEM with each var(--color-x) of a colour in NAMES as that colour's value, to the end of a chain (link:
    var(--color-chart-1), chart-1: var(--color-accent)): Sass and JS themes compute with it, var() breaks them."""
    out = VAR.sub(lambda found: names.get(found.group(1), found.group(0)), item) if isinstance(item, str) else item
    return literal(out, names, links - 1) if links and out != item else out


def font_names(stack):
    """A font stack with double quotes around each name that needs them: "Source Serif 4", Georgia, serif.
    Names of identifiers (Inter Variable, -apple-system, Café Sans), generic families, and names with a
    quote or a bracket in them (quoted, var()) stay as they are."""
    names = []
    for part in stack.split(","):
        if names and names[-1].count("(") > names[-1].count(")"):  # a comma inside var( ): not between names
            names[-1] += "," + part
        else:
            names.append(part)
    quoted = []
    for name in map(str.strip, names):
        if name and not FAMILY.match(name) and not NUMBER.match(name) and not re.search("[\"'()]", name):
            name = '"%s"' % re.sub(r"[ \t]+", " ", name)  # one space between words, as CSS reads them unquoted
        quoted.append(name)
    return ", ".join(quoted)


def group(tokens, name):
    """The named group as {key: item}, {} when it is not there. Notes (_ or $) are left out."""
    found = tokens.get(name, {})
    if not isinstance(found, dict):
        raise ValueError("%s must be a group, such as {\"sm\": ...}, not %s" % (name, json.dumps(found)[:60]))
    for key in [key for key in found if not key.startswith(("_", "$")) and not NAME.match(key)][:1]:
        raise ValueError("%s.%s: a name may hold only letters, digits, - and _" % (name, key))
    return {key: item for key, item in found.items() if not key.startswith(("_", "$"))}


def colours(found, prefix="color", path=""):
    """[(--color-name, value)] from a colour group; nested groups get dashed names (text.muted)."""
    lines = []
    for key, item in [(key, item) for key, item in found.items() if not key.startswith(("_", "$"))]:
        if not NAME.match(key):
            raise ValueError("%s.%s: a name may hold only letters, digits, - and _" % (prefix, path + key))
        if isinstance(item, dict) and "$value" not in item and "value" not in item:
            lines += colours(item, prefix, path + key + "-")
        else:
            lines.append(("--color-" + path + key, value("%s.%s" % (prefix, path + key), item)))
    return lines


def parts(tokens, tailwind):
    """(first, second, dark, points): the (name, value) pairs of the two blocks, the dark ones, the breakpoints."""
    color = group(tokens, "color")
    dark = colours(group(color, "dark"), "color.dark") if "dark" in color else []
    first = [("--color-*", "initial")] if tailwind == "4" else []
    first += colours({key: item for key, item in color.items() if key != "dark"})
    first += [("--font-" + key, value("font." + key, item, font=True)) for key, item in group(tokens, "font").items()]
    for step, item in group(tokens, "type").items():
        if not (isinstance(item, dict) and {"size", "line", "weight"} <= set(item)):
            raise ValueError('type.%s needs size, line and weight, such as {"size": 16, "line": 24, '
                             '"weight": 400}' % step)
        first += [("--text-" + step, value("type.%s.size" % step, item["size"])),
                  ("--text-%s--line-height" % step, value("type.%s.line" % step, item["line"])),
                  ("--text-%s--font-weight" % step, value("type.%s.weight" % step, item["weight"], px=False))]
        for key, prop, unit in (("stretch", "font-stretch", "%"), ("tracking", "letter-spacing", "em")):
            found = value("type.%s.%s" % (step, key), item[key], px=False) if key in item else ""
            if found:  # a bare number gets the unit: 125 is 125%, -0.02 is -0.02em
                first.append(("--text-%s--%s" % (step, prop), found + unit if found[-1].isdigit() else found))
    space = tokens.get("space", [])
    if not isinstance(space, list) or not all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in space):
        raise ValueError("space must be a list of numbers in px, such as [0, 4, 8, 16]")
    first += [] if tailwind == "4" else [("--space-" + ("%g" % (n / 4.0)).replace(".", "_"), value("space", n))
                                         for n in space]  # the step on a 4px grid: 16 is --space-4, 6 --space-1_5
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
    return first, second, dark, points


def switch(dark, default, selector, tailwind):
    """CSS lines that put the dark colours over the light ones (where WHEN says, or on the app's own selector) and,
    with Tailwind, its dark: on the same switch, so the app's own dark: classes (a logo swap) follow the choice."""
    rule = [" {", "  color-scheme: dark;"] + ["  %s: %s;" % pair for pair in dark] + ["}"]
    if selector:  # the app's own switch sets it on <html>, works out "system" itself and has its own dark: variant
        return [":root" + selector + rule[0]] + rule[1:]
    media, always = WHEN[default]
    lines = ["@media (prefers-color-scheme: dark) {", "  " + media + rule[0]] + ["  " + x for x in rule[1:]] + ["}"]
    lines += [always + rule[0]] + rule[1:]
    on = ["&:where(%s, %s *)" % (where, where) for where in (media, always)]
    if tailwind == "3":  # it goes in tailwind.config.js (Tailwind 3.4.1 and later)
        lines.append("/* tailwind.config.js, for dark: on this switch: darkMode: ['variant', ['@media "
                     "(prefers-color-scheme: dark) { %s }', '%s']] */" % tuple(on))
    return lines + (["@custom-variant dark {", "  @media (prefers-color-scheme: dark) { %s { @slot; } }" % on[0],
                     "  %s { @slot; }" % on[1], "}"] if tailwind == "4" else [])


def plain(item, names, font=False):
    """A token group as literal values, for a JS theme: notes left out, each {"$value": x} as x, font names
    quoted as CSS needs them, a var(--color-x) as the colour NAMES gives."""
    if isinstance(item, dict) and ("$value" in item or "value" in item):
        item = item.get("$value", item.get("value"))
        item = item.get("hex", item) if isinstance(item, dict) else item
    if isinstance(item, dict):
        return {key: plain(found, names, font) for key, found in item.items() if not key.startswith(("_", "$"))}
    return font_names(item.strip()) if font and isinstance(item, str) else literal(item, names)


def blocks(tokens, tailwind, default="system", selector=None, fmt="css"):
    """The theme from parsed tokens, as one string: CSS, or with fmt scss $variables and js an ES module."""
    first, second, dark, points = parts(tokens, tailwind if fmt == "css" else "no")
    light = [pair for pair in first if pair[0].startswith("--color-") and pair[1] != "initial"]
    names = {name[8:]: item for name, item in light}  # accent: #3f4856, what var(--color-accent) is
    both = dict(names, **{name[8:]: item for name, item in dark})  # in the dark group, its own first
    if fmt == "js":
        groups = {name: found for name, found in tokens.items() if name in KNOWN - {"pairs"}}
        data = {name: plain(found, names, name == "font") for name, found in groups.items()}
        if isinstance(data.get("color", {}).get("dark"), dict):
            data["color"]["dark"] = plain(groups["color"]["dark"], both)
        body = ["export const tokens = %s;" % json.dumps(data, indent=2, ensure_ascii=False)]
    elif fmt == "scss":  # Sass computes with these (tint-color, mix): literal values, the dark ones as $color-dark-*
        pairs = [(name, literal(item, names)) for name, item in first + second]
        pairs += [("--color-dark-" + name[8:], literal(item, both)) for name, item in dark]
        body = ["$%s: %s;" % (name[2:], item) for name, item in pairs + [("--breakpoint-" + k, v) for k, v in points]]
    else:
        second = ([("color-scheme", "light")] if dark else []) + second
        body = ["@theme static {" if tailwind == "4" else ":root {"] + ["  %s: %s;" % pair for pair in first] + ["}"]
        body += [":root {"] + ["  %s: %s;" % pair for pair in second] + ["}"] if second else []
        body += switch(dark, default, selector, tailwind) if dark else []
        if points and tailwind != "4":
            body.append("/* Breakpoints go into media queries as numbers (var() fails there): %s. */"
                        % ", ".join("%s %s" % pair for pair in points))
    return "\n".join([START] + body + [END]) + "\n"


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
    """Put CSS in the file at PATH between the marks, or the first time after its top statements (at the very
    top when it has none). Returns the names of our variables the file also sets outside it (the scaffold's)."""
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
        text = text[:text.index(START)] + css.rstrip(newline) + text[text.index(END) + len(END):]
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
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("tokens", help="forge-work/design/tokens.json")
    parser.add_argument("--tailwind", choices=["4", "3", "no"], help="the Tailwind line of components.md (CSS)")
    parser.add_argument("--format", choices=["css", "scss", "js"], help="css, or what --write's .scss, .js or .ts says")
    how = parser.add_mutually_exclusive_group()
    how.add_argument("--default", choices=["system", "light", "dark"], help="the theme while <html> has no data-theme")
    how.add_argument("--dark-selector", metavar="SELECTOR", help="what the app's own switch sets on <html> for dark")
    parser.add_argument("--write", metavar="FILE", help="put the block in this theme file instead of printing it")
    args = parser.parse_args(argv)
    fmt = args.format or FORMATS.get(os.path.splitext(args.write or "")[1].lower(), "css")
    if fmt == "css" and not args.tailwind:
        parser.error("--tailwind 4|3|no is needed for CSS: the Tailwind line of components.md")
    if args.dark_selector is not None and not SELECTOR.match(args.dark_selector):
        parser.error('--dark-selector takes one class (.dark) or one attribute ([data-mode="dark"])')
    try:
        tokens = read_tokens(args.tokens)
        css = blocks(tokens, args.tailwind, args.default or "system", args.dark_selector, fmt)
        twice = write(args.write, css) if args.write else []
    except (OSError, ValueError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    for name in sorted(name for name in set(tokens) - KNOWN if not name.startswith(("_", "$"))):
        print("note: the group %s is not in the theme: map it in components.md first" % name, file=sys.stderr)
    if (args.default not in (None, "system") or args.dark_selector) and "dark" not in group(tokens, "color"):
        print("note: --default and --dark-selector switch the dark group in color, and it has none", file=sys.stderr)
    if twice and fmt == "css":
        print("note: %s also sets %s outside the forge theme block (the scaffold's own theme?): remove those "
              "lines, or they win over the tokens" % (args.write, ", ".join(twice)), file=sys.stderr)
    count = " (%d variables)" % len(DECLARED.findall(css)) if fmt == "css" else " (%s)" % fmt
    print("Wrote the theme from %s into %s%s.\n" % (args.tokens, args.write, count) if args.write else css, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
