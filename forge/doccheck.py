#!/usr/bin/env python3
"""Is a forge report finished? Checks one markdown file: the placeholders of the template it was
copied from that are still in it, the sections with no text of their own, and the tables the forge
gate reads. phasecheck.py runs it for the exit checks of a phase. Run it from the project root. It
reads files (UTF-8; UTF-16 and UTF-32 with a byte order mark too, like bugs.py) and changes nothing.

Usage:
    python3 doccheck.py forge-work/recon.md --template ../forge-recon/recon-map.md
    python3 doccheck.py RUN.md --template '../forge-pack/templates/*/RUN.md' --no-sections
    python3 doccheck.py forge-work/brand.md --section 'Name checks' --section Palette --json
    python3 doccheck.py forge-work/test-plan.md --cases forge-work/bugs.md --specs 'e2e/**/*.spec.*'

--template FILE: the template the report was copied from (a * stands for any folder name). Its
  placeholders are each {{...}}, and each <...> outside its code; HTML comments do not count. The
  report still has one when the same words are in it outside comments: a {{...}} in code blocks
  too, a <...> only outside code (fenced blocks and `inline code`). So Blade's {{ $user->name }}
  and a spec's <button> never count. Its ## headings are the sections, unless --section names them.
--section TITLE: a heading that starts with TITLE needs a line of its own under it: a line that the
  template's section does not have, such as "none seen". Code blocks are text, comments are not.
--cases BUGS: the tables with the columns case and result (one per flow too) hold this app's rows,
  not only the template's; each result is pass, fail B003 (a ## B003 heading in BUGS) or skipped: why.
--specs PATTERN: when a case is marked e2e (the auto column), a file like PATTERN is in the project
  (** is any folders; node_modules does not count). Give it more than once for more patterns.
--rows 'A,B': a table with the columns A and B has at least one row.
--names LABEL: the line `LABEL: ...` names a file that is in the project, such as public/og.png.

Exit codes:
    0  every check passes
    1  a check fails: the output says which and how to fix it
    2  the report, a template or BUGS cannot be read: missing, a folder, or not text
"""

import argparse
import codecs
import errno
import glob
import json
import os
import re
import sys

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the forge skill pack
UNSEEN = re.compile(r"<!--.*?(?:-->|\Z)|^ {0,3}(`{3,}|~{3,}).*?(?:^ {0,3}\1|\Z)", re.S | re.M)  # comments, code
INLINE = re.compile(r"(`+).+?\1")  # `inline code`, on one line
BRACES = re.compile(r"\{\{.+?\}\}", re.S)  # a template's {{...}}, also over a line break
ANGLES = re.compile(r"<[^<>\n]+>")  # a template's <...>, as in forge-design/components.md
FENCE = re.compile(r" {0,3}(`{3,}|~{3,})")
HEADING = re.compile(r" {0,3}(#{1,2})[ \t]+(.*?)[ \t#]*$")
FILE_NAME = re.compile(r"[\w@-]+(?:[./][\w@-]+)*\.(?:png|jpe?g|webp|gif|svg|avif|tsx|jsx|ts|js)\b")
BOMS = ((codecs.BOM_UTF32_LE, "utf-32"), (codecs.BOM_UTF32_BE, "utf-32"), (codecs.BOM_UTF16_LE, "utf-16"),
        (codecs.BOM_UTF16_BE, "utf-16"))  # UTF-32 first: its little-endian mark starts like UTF-16's


def read(path):
    """The text of the file at PATH: UTF-8, or UTF-16 or UTF-32 with a byte order mark (PowerShell's >
    writes that, and bugs.py reads it). A file that is not text raises an OSError that names PATH."""
    with open(path, "rb") as handle:
        data = handle.read()
    codec = next((codec for mark, codec in BOMS if data.startswith(mark)), "utf-8-sig")  # -sig: Notepad's BOM
    try:
        text = data.decode(codec)
    except UnicodeDecodeError as error:  # it names no file, so the error would blame the report
        raise OSError(errno.EILSEQ, "not UTF-8 text (%s): save it as UTF-8" % error, path) from None
    return text.replace("\r\n", "\n").replace("\r", "\n")  # line ends as text mode reads them


def blank(match):
    """The matched text as spaces, its line breaks kept, so every line keeps its number."""
    return re.sub(r"[^\n]", " ", match.group(0))


def visible(text, fences=True, inline=True):
    """TEXT without its HTML comments and, unless FENCES or INLINE says no, without its fenced code
    blocks and its `inline code`: spaces stand in their place, so every line keeps its number."""
    text = UNSEEN.sub(lambda match: blank(match) if fences or match.group(0).startswith("<!--")
                      else match.group(0), text)
    return INLINE.sub(blank, text) if inline else text


def shown(path):
    """A path the way the skills write it: ../forge-recon/recon-map.md for a file of the pack."""
    try:
        inside = os.path.relpath(os.path.abspath(path), PACK)
    except ValueError:  # Windows: on another drive than the pack
        return path
    return path if inside.startswith("..") else "../" + inside.replace(os.sep, "/")


def placeholders(template):
    """The template's placeholders, each once, with each run of spaces and line breaks as one space."""
    found = BRACES.findall(visible(template, fences=False, inline=False)) + ANGLES.findall(visible(template))
    return list(dict.fromkeys(" ".join(text.split()) for text in found))


def sections(text):
    """[(level, title, lines)]: each # and ## heading outside code blocks, with the lines under it,
    each with its spaces as one. The lines before the first heading come first, at level 0."""
    found, fence = [(0, "", [])], None
    for line in visible(text, fences=False, inline=False).split("\n"):
        mark = FENCE.match(line)
        if fence:
            closes = mark and mark.group(1)[0] == fence[0] and len(mark.group(1)) >= len(fence)
            fence = None if closes else fence
        elif mark:
            fence = mark.group(1)
        elif HEADING.match(line):
            found.append((len(HEADING.match(line).group(1)), HEADING.match(line).group(2), []))
            continue
        found[-1][2].append(" ".join(line.split()))
    return found


def key(title):
    """What a template's heading is known by: its start, before a ( or a colon. `## Out of scope (cannot
    or should not be cloned)` is Out of scope, so a report may write `## Out of scope` only."""
    return re.split(r"[(:]", title)[0].strip()


def under(found, title):
    """The lines of each section in FOUND whose heading starts with TITLE, as a whole word."""
    return [lines for _, head, lines in found if re.match(re.escape(title) + r"(?!\w)", head, re.I)]


def check_placeholders(name, text, templates, label):
    seen = {"{": visible(text, fences=False, inline=False), "<": visible(text)}  # where each kind counts
    left = {}
    for template in templates:
        for placeholder in placeholders(template):
            match = re.search(r"\s+".join(map(re.escape, placeholder.split())), seen[placeholder[0]])
            if match and placeholder not in left:
                left[placeholder] = text.count("\n", 0, match.start()) + 1
    if not left:
        return True, "%s has no placeholder of %s left" % (name, label), []
    lines = ["line %d: %s" % (line, item if len(item) <= 70 else item[:66] + " ...")
             for item, line in sorted(left.items(), key=lambda pair: pair[1])]
    return False, "%s still has %d placeholder(s) of %s" % (name, len(left), label), lines + [
        "Write this app's own facts in their place (or none, and why); delete a line that does not apply."]


def check_sections(name, text, titles, template, label):
    found, theirs, missing, empty = sections(text), sections(template or ""), [], []
    for title in titles:
        mine, known = under(found, title), set(sum(under(theirs, title), []))
        if not mine:
            missing.append(title)
        elif not any(line and line not in known for lines in mine for line in lines):
            empty.append(title)
    if not missing and not empty:
        return True, "%s has text of its own under ## %s" % (name, ", ## ".join(titles)), []
    words = (["no ## %s" % ", ## ".join(missing)] if missing else []) + (
        ["no text of its own under ## %s" % ", ## ".join(empty)] if empty else [])
    where = ("the headings of %s, and a line that the template has already is not enough" % label if template
             else "the headings of the report in its skill's Output section")
    return False, "%s has %s" % (name, " and ".join(words)), [
        "Fill in each section with this app's facts, as its skill says (or write none, and why): %s." % where]


def table(text, *columns):
    """The rows of every table in TEXT whose header has COLUMNS, as dicts (a table's line 2 is ---)."""
    found = []
    for block in re.findall(r"(?m)(?:^[ \t]*\|.*\n?)+", text):
        rows = [[cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
                for line in block.splitlines()]
        header = [cell.lower() for cell in rows[0]]
        if set(columns) <= set(header):
            found += [dict(zip(header, row + [""] * len(header))) for row in rows[2:] if any(row)]
    return found


def check_cases(name, text, bugs, template, label):
    """This app's cases, not only the template's examples, each with a result in the template's words."""
    rows, examples = table(visible(text, inline=False), "case", "result"), table(template or "", "case", "result")
    if not rows:
        return False, "%s has no Cases table with rows: | case | ... | result |" % name, []
    if all(row in examples for row in rows):
        return False, "%s has only the example rows of %s, not this app's cases" % (name, label), []
    left = [row.get("case") or "(no case ID)" for row in rows if not row.get("result")]
    if left:
        return False, "%s has %d case row(s) without a result: %s" % (name, len(left), ", ".join(left)[:120]), []
    known = re.findall(r"(?m)^##[ \t]+(B\d+)\b", read(bugs)) if os.path.isfile(bugs) else []
    wrong = []
    for row in rows:
        case, result = row.get("case") or "(no case ID)", row["result"]
        bug_ids = re.findall(r"\bB\d+\b", result)
        if re.match(r"(?i)fail(ed)?\b", result):
            if not bug_ids:
                wrong.append("%s: %s names no bug" % (case, result))
            wrong += ["%s: %s, but there is no ## %s in %s" % (case, result, ref, bugs)
                      for ref in bug_ids if ref not in known]
        elif re.match(r"(?i)skip(ped)?\W*$", result):
            wrong.append("%s: skipped, but not why" % case)
        elif not re.match(r"(?i)(pass|skip)", result):
            wrong.append("%s: %s" % (case, result[:60]))
    if wrong:
        return False, "%s has %d result(s) that are not pass, fail B003 (a ## B003 in %s) or skipped: why" % (
            name, len(wrong), bugs), wrong
    return True, "%s has %d case row(s), each with a result" % (name, len(rows)), []


def check_specs(name, text, patterns):
    """The cases marked e2e have specs: a file like one of PATTERNS. No case marked e2e: none needed."""
    marked = [row.get("case") for row in table(visible(text, inline=False), "case", "auto")
              if re.match(r"(?i)e2e\b", row.get("auto", ""))]
    for pattern in patterns if marked else ():
        found = sorted(path for path in glob.glob(pattern, recursive=True) if os.path.isfile(path)
                       and "node_modules" not in os.path.normpath(path).split(os.sep))
        if found:
            return True, "%s marks %d case(s) e2e; a spec: %s" % (name, len(marked), found[0].replace(os.sep, "/")), []
    if not marked:
        return True, "%s marks no case e2e, so it needs no end-to-end spec" % name, []
    return False, "%s marks %d case(s) e2e, but there is no file like %s" % (
        name, len(marked), " or ".join(patterns)), [
        "Write the specs (forge-test Step 3), or mark a case unit or manual when that is how it was tested."]


def check_rows(name, text, columns):
    names = [column.strip().lower() for column in columns.split(",")]
    rows = table(visible(text, inline=False), *names)
    if rows:
        return True, "%s has %d row(s) in its table of %s" % (name, len(rows), " and ".join(names)), []
    return False, "%s has no table with the columns %s and a row under them" % (name, " and ".join(names)), []


def check_names(name, text, label):
    """The line `LABEL: ...` names a file of the project, as launch.md's `OG image: public/og.png`."""
    lines = re.findall(r"(?im)^[ \t>*_-]*%s[ \t*_]*:(.*)$" % re.escape(label), visible(text, inline=False))
    named = [path for line in lines for path in FILE_NAME.findall(line.replace("`", " "))]
    there = [path for path in named if os.path.isfile(path)]
    if there:
        return True, "%s names %s, which is in the project" % (name, there[0]), []
    return False, "%s needs a line `%s: <file>` naming a file in the project, such as public/og.png " \
                  "(found: %s)" % (name, label, ", ".join(named) or "no file name"), []


def run(args):
    """Every check ARGS asks for, as [(ok, what, output lines)]. OSError when a file cannot be read."""
    text = read(args.file)
    paths = [found for pattern in args.template for found in sorted(glob.glob(pattern)) or [pattern]]
    templates, label = [read(path) for path in paths], " and ".join(shown(path) for path in args.template)
    first = templates[0] if templates else None
    checks = [check_placeholders(args.file, text, templates, label)] if templates else []
    titles = args.section or [key(title) for level, title, _ in sections(first or "") if level == 2]
    if titles and not args.no_sections:
        checks.append(check_sections(args.file, text, titles, first, label))
    if args.cases:
        checks.append(check_cases(args.file, text, args.cases, first, label))
    checks += [check_specs(args.file, text, args.specs)] if args.specs else []
    checks += [check_rows(args.file, text, columns) for columns in args.rows]
    return checks + [check_names(args.file, text, line) for line in args.names]


def main(argv=None):
    """Check one report. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):  # what the console cannot show comes out as \u escapes, not a crash
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", help="the report, such as forge-work/recon.md")
    parser.add_argument("--template", action="append", default=[], metavar="FILE", help="the template it came from")
    parser.add_argument("--section", action="append", default=[], metavar="TITLE", help="a section to check")
    parser.add_argument("--no-sections", action="store_true", help="check the placeholders only")
    parser.add_argument("--cases", metavar="BUGS", help="check the Cases tables, with this bug list")
    parser.add_argument("--specs", action="append", default=[], metavar="PATTERN", help="where the e2e specs are")
    parser.add_argument("--rows", action="append", default=[], metavar="'A,B'", help="a table that needs rows")
    parser.add_argument("--names", action="append", default=[], metavar="LABEL", help="a line naming a file")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    if not (args.template or args.section or args.cases or args.specs or args.rows or args.names):
        parser.error("nothing to check: give --template, --section, --cases, --specs, --rows or --names")
    try:
        checks = run(args)
    except (OSError, ValueError) as error:  # missing, a folder, or not text
        name = getattr(error, "filename", None)  # the file that failed: the report, a template or BUGS
        why = error.strerror if name and error.strerror else error  # an OSError's text names the file again
        print("error: %s cannot be read: %s" % (name or args.file, why), file=sys.stderr)
        return 2
    ok = all(check[0] for check in checks)
    if args.json:
        print(json.dumps({"file": args.file, "ok": ok, "checks": [
            {"ok": good, "what": what, "output": output} for good, what, output in checks]}, indent=2))
    else:
        for good, what, output in checks:
            print("\n".join(["%-4s  %s" % ("ok" if good else "FAIL", what)] + ["      " + line for line in output]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
