#!/usr/bin/env python3
"""Does the app really move? Counts the motion that is wired into an app's own code.

forge-motion must change the app, not only write a plan. This counts each place where something
on a screen will move, and fails when there are too few. A place counts when it is one of:

- a rule in a stylesheet (or a <style> block) with a transition or an animation, on a selector of
  the app's own (.btn, .card:hover, dialog[open]);
- a motion class put on an element in a template or component: an m- class that a stylesheet of
  the app has a moving rule for (forge-motion's motion.css: m-enter, m-stagger, m-lift ...), or
  Tailwind's transition and animate- classes;
- a script that animates: element.animate(), startViewTransition, an IntersectionObserver, or a
  requestAnimationFrame loop.

A rule for a .m- class is only on offer: it counts once an element carries the class. Classes
on offer that no element uses are listed, since that is the usual reason nothing moves: motion.css
was copied in and never put to work. Skips node_modules, vendor, build and forge-work folders,
symlinks and files over 1 MB.

Usage: python3 motioncount.py PATH [--min N] [--json], for example
    python3 motioncount.py . --min 8
Exit codes: 0 at least --min places move (default: 5), in at least two files; 1 fewer than that;
2 PATH is not a folder, or a file under it could not be read (the count is then not complete).
"""

import argparse
import json
import os
import re
import sys

SKIP = {".git", "node_modules", "vendor", "venv", ".venv", "__pycache__", "dist", "build", ".next", ".nuxt", "out",
        "coverage", "forge-work", "staticfiles", "e2e", "tests", "test", ".claude"}
STYLES = {".css", ".scss", ".less", ".pcss"}
MARKUP = {".html", ".htm", ".php", ".djhtml", ".jinja", ".jinja2", ".j2", ".twig", ".vue", ".svelte", ".astro",
          ".jsx", ".tsx", ".erb"}
SCRIPTS = {".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx", ".vue", ".svelte", ".astro"}
MAX_BYTES = 1024 * 1024
COMMENT = re.compile(r"/\*.*?\*/|<!--.*?-->", re.S)
SCRIPT_COMMENT = re.compile(r"/\*.*?\*/|(?<![:\w])//[^\n]*", re.S)  # not the // of https://
STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style\s*>", re.S | re.I)
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")  # one innermost rule: its selector and its declarations
MOVES = re.compile(r"(?<![\w-])(?:transition|animation)(?:-name|-duration)?\s*:(?!\s*(?:none|0s|initial|unset)\b)")
OFFERED = re.compile(r"\.(m-[a-z][\w-]*)")
CLASSES = re.compile(r"""\bclass(?:Name)?\s*=\s*(?:\{\s*)?(?:"([^"]*)"|'([^']*)'|`([^`]*)`)""")
MOTION_CLASS = re.compile(r"(?<![\w:-])(?:[a-z-]+:)*(m-[a-z][\w-]*|transition(?:-[a-z]+)?|animate-(?!none\b)[\w-]+)"
                          r"(?![\w-])")
SCRIPTED = re.compile(r"\.animate\(\s*[\[{]|startViewTransition\s*\(|new\s+IntersectionObserver\s*\("
                      r"|requestAnimationFrame\s*\(")


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def count_styles(css, name, places, offered, offset=0):
    """The moving rules of one stylesheet. A rule for an .m- class is on offer, not a place yet."""
    css = COMMENT.sub(lambda match: re.sub(r"[^\n]", " ", match.group(0)), css)
    for match in RULE.finditer(css):
        selector, body = " ".join(match.group(1).split()), match.group(2)
        if selector.startswith("@") or not MOVES.search(body):
            continue
        names = OFFERED.findall(selector)
        if names:
            offered.update(names)  # a rule for an m- class: on offer until an element carries the class
        elif "view-transition" not in selector:  # those set how a page change looks: the script starts it
            start = match.start(1) + len(match.group(1)) - len(match.group(1).lstrip())
            places.append({"file": name, "line": offset + line_of(css, start), "kind": "style rule",
                           "what": selector[-80:]})


def count_markup(text, name, places, used):
    for match in CLASSES.finditer(text):
        found = sorted(set(MOTION_CLASS.findall(next(group for group in match.groups() if group is not None))))
        used.update(item for item in found if item.startswith("m-"))
        if found:
            places.append({"file": name, "line": line_of(text, match.start()), "kind": "motion class",
                           "what": " ".join(found)[:80], "names": found})


def count_path(root):
    """Walk ROOT. Returns the report: places, the m- classes on offer and unused, what was not read."""
    places, offered, used, unread, files = [], set(), set(), [], 0
    for folder, subfolders, names in os.walk(root, onerror=lambda error: unread.append(str(error))):
        subfolders[:] = sorted(name for name in subfolders
                               if name not in SKIP and not os.path.islink(os.path.join(folder, name)))
        for item in sorted(names):
            path, ext = os.path.join(folder, item), os.path.splitext(item)[1].lower()
            if ext not in STYLES | MARKUP | SCRIPTS or os.path.islink(path) or ".min." in item:
                continue
            name = os.path.relpath(path, root).replace(os.sep, "/")
            try:
                if os.path.getsize(path) > MAX_BYTES:
                    continue
                text = read(path)
            except OSError as error:
                unread.append("%s (%s)" % (name, error.strerror or error))
                continue
            files += 1
            if ext in STYLES:
                count_styles(text, name, places, offered)
            if ext in MARKUP:
                for block in STYLE_BLOCK.finditer(text):
                    count_styles(block.group(1), name, places, offered, line_of(text, block.start(1)) - 1)
                count_markup(text, name, places, used)
            if ext in SCRIPTS:
                code = SCRIPT_COMMENT.sub(lambda match: re.sub(r"[^\n]", " ", match.group(0)), text)
                for match in SCRIPTED.finditer(code):
                    places.append({"file": name, "line": line_of(text, match.start()), "kind": "script",
                                   "what": match.group(0).strip(" ([{")[:80]})
    for place in places:  # an m- class counts only when a stylesheet of the app has a moving rule for it
        names = [item for item in place.pop("names", [place["what"]]) if not item.startswith("m-") or item in offered]
        place["what"] = " ".join(names)[:80]
    places = [place for place in places if place["what"]]
    return {"places": places, "unused": sorted(offered - used), "unread": unread, "files_read": files,
            "files_moving": len({place["file"] for place in places})}


def main(argv=None):
    """Count the motion under PATH. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="the app's folder")
    parser.add_argument("--min", type=int, default=5, metavar="N", help="places that must move (default: 5)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.path) or args.min < 1:
        print("error: %s is not a folder, or --min is under 1" % args.path, file=sys.stderr)
        return 2
    report = count_path(args.path)
    total = len(report["places"])
    enough = total >= args.min and report["files_moving"] >= min(2, args.min)
    report["summary"] = {"places": total, "files_moving": report["files_moving"], "min": args.min,
                         "enough": enough, "complete": not report["unread"]}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for place in report["places"]:
            print("%-12s %s:%d  %s" % (place["kind"], place["file"], place["line"], place["what"]))
        if report["unused"]:
            print("\nOn offer but on no element (put the class on one, or delete the rule): %s"
                  % ", ".join(report["unused"]))
        print("\n%d place(s) move, in %d file(s); %d file(s) read. Needed: %d, in 2 files or more."
              % (total, report["files_moving"], report["files_read"], args.min))
        for item in report["unread"]:
            print("INCOMPLETE, so not a pass. Could not read %s" % item)
        if not enough:
            print("FAIL: the app barely moves. Motion counts only once it is in the app's own stylesheets, "
                  "templates or scripts: a plan, or a copied motion.css that no element uses, changes nothing.")
    return 2 if report["unread"] else int(not enough)


if __name__ == "__main__":
    sys.exit(main())
