#!/usr/bin/env python3
"""Does the app really move? Counts the motion that is wired into an app's own code.

forge-design motion must change the app, not only write a plan. This counts the places where something on a
screen will move: a rule in a stylesheet or <style> block with a transition or an animation, on a selector of
the app's own (.btn, .card:hover); a motion class on an element (an m- class that a stylesheet of the app has
a moving rule for, as in motion.css, or Tailwind's transition and animate- classes); a script that animates
(element.animate(), startViewTransition, an IntersectionObserver, a requestAnimationFrame loop). A rule for an
.m- class is only on offer until an element carries the class; classes no element uses are listed. Skips
node_modules, vendor, build, forge-work and other such folders, symlinks, files over 1 MB.

--level N (the look level, 1 to 5) also asks for the features of that level and all below it. Comments and
strings never count (GLSL lives in strings, so there it does), nor a rule for an m- class no element carries,
nor the kit's own files (stage.js, form.js ... in a *scene* folder). Patterns: motioncount.json. What counts:
1 reduced motion: @media (prefers-reduced-motion), matchMedia('(prefers-reduced-motion'), Tailwind
  motion-reduce: or motion-safe: in a class attribute or @apply.
2 entrance: a rule with an animation (not on :hover, :focus, :active, view-transition), a Tailwind animate-
  class on a tag (not spin, pulse, ping, bounce), @starting-style, el.animate([.
2 page transition or counted number: @view-transition, view-transition-name, startViewTransition(; a script
  with requestAnimationFrame or setInterval that writes Math.round( toFixed( toLocaleString( format( Number(
  or String( into textContent; a moving rule for .m-count, on an element.
3 scroll: new IntersectionObserver(, animation-timeline, view( or scroll( in a rule, new ScrollTimeline( or
  ViewTimeline(, a scroll listener in a file that sets a progress (progress =, setProgress().
3 CSS 3D: perspective, preserve-3d, rotateX( rotateY( rotate3d( translateZ( perspective( translate3d( with a
  z not 0, in a rule, style attribute or el.style.transform; depth.js mounted (import, <script src>, data-depth).
4 WebGL scene: import of three (or three.module.js), getContext('webgl'|'webgl2'), import of a scenes/*.js
  file, lazyScene(, <script src=".../three.js">.
4 pointer: a pointermove, mousemove or touchmove listener (onPointerMove=) in a file with the scene,
  setPointer(, or the kit mounted (a scenes/*.js import, lazyScene(): its stage reads the pointer.
4 fallback: data-scene-poster on a tag, a [data-scene="fallback"] selector, poster= on a tag but <video>,
  if (!gl), !ctx, !context or gl === null in a file with getContext('webgl'), !window.WebGLRenderingContext.
5 scroll drives the scene: .setProgress(, an import of journey.js, a scroll listener in a file with it.
5 shader: (Raw)ShaderMaterial, gl_FragColor, gl_Position, GLSL void main(), an import of a kit scene (scenes/
  form, field, aurora, contour, datascape or glsl: all are shaders).
5 data hook: .setData( with an argument; uniforms.x.value = data/values/stats/state/rows/... (motioncount.json).
--level sets the minimum (1: 5 places, 2: 12, 3 to 5: 20; always in 2 files or more) unless --min is given
too. --level auto reads the look level from PATH/forge-work/levels.json (forge/level.py writes it).

Usage: python3 motioncount.py PATH [--min N] [--level N|auto] [--json]   (e.g. . --min 8, or . --level auto)
Exit codes: 0 enough places move (--min, default 5, in 2 files or more) and, with --level, every feature up
to it is there; 1 too few places, or a feature MISSING; 2 PATH is not a folder, a file could not be read (the
count is not complete), motioncount.json is missing or broken, or --level auto found no look level on record.
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
RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "motioncount.json")  # the feature patterns
COMMENT = re.compile(r"/\*.*?(?:\*/|\Z)|<!--.*?(?:-->|\Z)", re.S)
SCRIPT_COMMENT = re.compile(r"/\*.*?(?:\*/|\Z)|(?<![:\w])//[^\n]*", re.S)  # not the // of https://
STYLE_BLOCK = re.compile(r"<style\b[^<>]*>(.*?)(?:</style\s*>|\Z)", re.S | re.I)
SCRIPT_BLOCK = re.compile(r"<script\b[^<>]*>(.*?)(?:</script\s*>|\Z)", re.S | re.I)
TOKENS = re.compile(r"/\*.*?(?:\*/|\Z)|<!--.*?(?:-->|\Z)|(?<![:\w(])//[^\n]*|(\"(?:\\.|[^\"\\\n])*(?:\"|$)|'"
                    r"(?:\\.|[^'\\\n])*(?:'|$)|`(?:\\.|[^`\\])*(?:`|\Z))", re.S | re.M)  # a comment; a string (group 1)
BLANK = re.compile(r"[^\n]")  # what blanking a comment or a block replaces: all but the line ends
RULE = re.compile(r"(?<![^{}])([^{}]+)\{([^{}]*)\}")  # one innermost rule: its selector and its declarations
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


def load_rules(path):
    """The features per level from motioncount.json, patterns compiled. ValueError when missing or broken."""
    try:
        data = json.loads(read(path))
        features = [dict(item, signals=[dict(sig, re=re.compile(sig["re"]), also=sig.get("also") and re.compile(
            sig["also"]), rule=re.compile(sig["rule"]) if "rule" in sig else None) for sig in item["signals"]])
            for item in data["features"]]
        signals = [((i, n), sig) for i, item in enumerate(features) for n, sig in enumerate(item["signals"])]
        if set(data["min"]) != set("12345") or {s["view"] for _, s in signals} - {"style", "script", "markup"}:
            raise ValueError("each level 1 to 5 needs a minimum and features, each with signals of a known view")
        return {"min": {int(key): int(value) for key, value in data["min"].items()}, "kit": set(data["kit_files"]),
                "features": features, "signals": signals, "ask": data["ask"]}
    except (OSError, ValueError, LookupError, TypeError, AttributeError, RecursionError, re.error) as error:
        raise ValueError("%s is missing or broken (%s: %s)" % (path, type(error).__name__, error))


def level_on_record(root, ask):
    """The look level in ROOT/forge-work/levels.json. ValueError, saying to ask the user, when there is none."""
    path = os.path.join(root, "forge-work", "levels.json")
    linked = os.path.islink(os.path.dirname(path)) or os.path.islink(path)
    try:
        if linked or not os.path.isfile(path) or os.path.getsize(path) > MAX_BYTES:
            raise ValueError("it is a link, so it was not read: tell the user" if linked else "not there, or over 1 MB")
        level = json.loads(read(path))["look"]["level"]
        if type(level) is int and 1 <= level <= 5:
            return level
        raise ValueError("its look level is %r, not 1 to 5" % (level,))
    except (OSError, ValueError, LookupError, TypeError, RecursionError) as error:
        raise ValueError("No look level on record in forge-work/levels.json (%s). %s" % (error, ask))


def scrub(text):
    """(full, mask) of TEXT: comments blanked in both; in mask the inside of every string is NUL as well."""
    full, mask, last = [], [], 0
    for match in TOKENS.finditer(text):
        piece, string = match.group(0), match.group(1) is not None
        inside = piece[0] + BLANK.sub("\0", piece[1:-1]) + piece[-1] if string else BLANK.sub(" ", piece)
        full += [text[last:match.start()], piece if string else inside]
        mask += [text[last:match.start()], inside]
        last = match.end()
    return "".join(full + [text[last:]]), "".join(mask + [text[last:]])


def keep(text, pattern):
    """TEXT with all but the insides of PATTERN's blocks blanked, so the line numbers stay."""
    out = list(BLANK.sub(" ", text))
    for match in pattern.finditer(text):
        out[match.start(1):match.end(1)] = match.group(1)
    return "".join(out)


def views(text, ext):
    """{view: (full, mask)}: the file's stylesheet, script and markup parts, comments blanked, lines kept."""
    out = {"style": scrub(text if ext in STYLES else keep(text, STYLE_BLOCK))} if ext in STYLES | MARKUP else {}
    if ext in SCRIPTS | MARKUP:
        out["script"] = scrub(text if ext in SCRIPTS else keep(text, SCRIPT_BLOCK))
    if ext in MARKUP:  # tags and attributes: the patterns start at a tag or an attribute, so no string check
        markup = out["script"][0] if ext in SCRIPTS else scrub(text)[0]
        out["markup"] = (markup, markup)
    return out


def rule_at(mask, at):
    """The selector of the rule whose declarations hold AT, looked for within 4000 characters; None outside one."""
    opened, closed = (mask.rfind(char, max(0, at - 4000), at) for char in "{}")
    if opened <= closed:
        return None
    start = max(0, opened - 4000)
    selector = " ".join(mask[max([start - 1] + [mask.rfind(char, start, opened) for char in "{};"]) + 1:opened].split())
    return None if selector.startswith("@") else selector


def look_for(rules, text, ext, name, hits):
    """Add to HITS {(feature, signal): [(file, line, the m- classes of its rule)]} what matches in this file."""
    for view, (full, mask) in views(text, ext).items():
        for key, sig in rules["signals"]:
            if sig["view"] != view or sig["also"] and all(mask[m.start()] == "\0" for m in sig["also"].finditer(full)):
                continue
            for count, match in enumerate(sig["re"].finditer(full)):
                at = match.start()
                rule = rule_at(mask, at) if view == "style" and (sig.get("strings") or mask[at] != "\0") else None
                if (sig.get("strings") or mask[at] != "\0") and (not sig["rule"] or rule and sig["rule"].search(rule)):
                    classes = OFFERED.findall(match.group(0) if rule is None else rule) if view == "style" else []
                    hits.setdefault(key, []).append((name, line_of(full, at), classes))
                    if not classes or count > 100:
                        break  # the first is enough; one for an m- class waits for an element with the class


def judge(rules, level, hits, used):
    """The features up to LEVEL, each {level, name, found, where, needs}, from the HITS of look_for()."""
    out, files_of = [], {}
    for index, feature in enumerate(rules["features"]):
        seen = [hit for number, sig in enumerate(feature["signals"]) for hit in hits.get((index, number), [])
                if (not hit[2] or set(hit[2]) & used) and hit[0] in files_of.get(sig.get("same_file_as"), [hit[0]])]
        files_of[feature["id"]] = {hit[0] for hit in seen}
        if feature["level"] <= level:
            out.append({"level": feature["level"], "name": feature["name"], "found": bool(seen),
                        "where": "%s:%d" % seen[0][:2] if seen else None, "needs": feature["needs"]})
    return out


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


def count_path(root, rules=None, level=0):
    """Walk ROOT. The report: places, the m- classes on offer and unused, what was not read, the features."""
    places, offered, used, unread, files, hits = [], set(), set(), [], 0, {}
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
            if level and not (item in rules["kit"] and "scene" in os.path.basename(folder).lower()):
                look_for(rules, text, ext, name, hits)  # the kit's own files are on offer: only their use counts
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
            "files_moving": len({place["file"] for place in places}), "level": level or None,
            "features": judge(rules, level, hits, used) if level else []}


def main(argv=None):
    """Count the motion under PATH. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="the app's folder")
    parser.add_argument("--min", type=int, metavar="N", help="places that must move (default: 5, or the level's)")
    parser.add_argument("--level", choices=list("12345") + ["auto"], metavar="N|auto", help="the look level, or auto")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        if not os.path.isdir(args.path) or (args.min is not None and args.min < 1):
            raise ValueError("%s is not a folder, or --min is under 1" % args.path)
        rules = load_rules(RULES)
        level = level_on_record(args.path, rules["ask"]) if args.level == "auto" else int(args.level or 0)
    except ValueError as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    minimum, report = args.min or (rules["min"][level] if level else 5), count_path(args.path, rules, level)
    total = len(report["places"])
    enough = total >= minimum and report["files_moving"] >= min(2, minimum)
    missing = [item for item in report["features"] if not item["found"]]
    report["summary"] = {"places": total, "files_moving": report["files_moving"], "min": minimum,
                         "enough": enough, "complete": not report["unread"]}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for place in report["places"]:
            print("%-12s %s:%d  %s" % (place["kind"], place["file"], place["line"], place["what"]))
        if report["unused"]:
            print("\nOn offer but on no element (put the class on one, or delete the rule): %s"
                  % ", ".join(report["unused"]))
        print("\n%d place(s) move, in %d file(s); %d file(s) read. Needed: %d, in 2 files or more.%s" % (total, report[
            "files_moving"], report["files_read"], minimum, "\n\nLevel %d needs:" % level if level else ""))
        for item in report["features"]:
            print("found  %s  (%s)" % (item["name"], item["where"]) if item["found"]
                  else "MISSING  %s: %s" % (item["name"], item["needs"]))
        for item in report["unread"]:
            print("INCOMPLETE, so not a pass. Could not read %s" % item)
        if not enough:
            print("FAIL: the app barely moves. Motion counts only once it is in the app's own stylesheets, "
                  "templates or scripts: a plan, or a copied motion.css that no element uses, changes nothing.")
        if missing:
            print("FAIL: not level %d yet: %d feature(s) MISSING above." % (level, len(missing)))
    return 2 if report["unread"] else int(not enough or bool(missing))


if __name__ == "__main__":
    sys.exit(main())
