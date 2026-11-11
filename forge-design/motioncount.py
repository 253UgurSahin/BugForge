#!/usr/bin/env python3
"""Does the app really move? Counts the motion that is wired into an app's own code.

forge-design motion must change the app, not only write a plan. A place that moves: a moving rule on a selector of
the app's own (.btn:hover); a motion class on an element (an m- class a stylesheet of the app moves, as motion.css
does, or Tailwind's transition and animate- classes); a script that animates or a style that moves set in a script
(motioncount.json's "places": element.animate(), gsap, <motion.div animate>, styled or css templates, sx and style
objects). An m- class no element carries is only on offer, and listed. Templates count (Blade, Twig, ERB, Pug ...).
Several PATHs are one app (a monorepo's app and its packages). Skips node_modules, build and such, symlinks, 1 MB+.

--level N (the look level, 1 to 5) also asks for the features of that level and those below it (motioncount.json):
1 reduced motion; 2 an entrance, a page transition or a count-up; 3 scroll-driven motion, CSS 3D or depth.js; 4 a
WebGL scene (not depth.js), the pointer reaching it, a fallback (a data-scene-poster in the scene's container, up to
six elements down or in a partial placed there; a branch for no WebGL); 5 journey.js, a shader of its own, a data
hook. Comments, strings (but GLSL) and the kit's own files (in a *scene* folder) never count. --level sets --min (1:
5, 2: 12, 3 to 5: 20); auto reads forge-work/levels.json in the first PATH or above it in its repo. MISSING first.

Usage: python3 motioncount.py PATH [PATH ...] [--min N] [--level N|auto] [--json]   (. or apps/web packages/ui)
Exit codes: 0 enough places move (--min, in 2 files or more) and every feature up to --level is there; 1 too few
places or a feature MISSING; 2 a PATH is no folder, a file unreadable, motioncount.json broken, or no level for auto.
"""

import argparse
import json
import os
import pathlib
import re
import sys

SKIP = {".git", "node_modules", "vendor", "venv", ".venv", "__pycache__", "dist", "build", ".next", ".nuxt", "out",
        "coverage", "forge-work", "staticfiles", "e2e", "tests", "test", ".claude"}
STYLES, SHORT = {".css", ".scss", ".less", ".pcss"}, {".pug", ".jade", ".haml", ".slim"}  # SHORT: tag.class
MARKUP = {".html", ".htm", ".php", ".djhtml", ".jinja", ".jinja2", ".j2", ".twig", ".vue", ".svelte", ".astro",
          ".jsx", ".tsx", ".erb", ".ejs", ".hbs", ".handlebars", ".mustache", ".njk", ".nunjucks", ".liquid",
          ".edge", ".eta", ".cshtml", ".razor", ".gohtml", ".tmpl", ".tpl", ".latte", ".heex", ".eex"} | SHORT
SCRIPTS = {".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx", ".vue", ".svelte", ".astro"}
MAX_BYTES, RULES = 1024 * 1024, os.path.join(os.path.dirname(os.path.abspath(__file__)), "motioncount.json")
COMMENT = re.compile(r"/\*.*?(?:\*/|\Z)|<!--.*?(?:-->|\Z)", re.S)
SCRIPT_COMMENT = re.compile(r"/\*.*?(?:\*/|\Z)|(?<![:\w])//[^\n]*", re.S)  # not the // of https://
STYLE_BLOCK, SCRIPT_BLOCK = (re.compile(r"<%s\b[^<>]*>(.*?)(?:</%s\s*>|\Z)" % (tag, tag), re.S | re.I)
                             for tag in ("style", "script"))
TOKENS = re.compile(r"/\*.*?(?:\*/|\Z)|<!--.*?(?:-->|\Z)|(?<![:\w(])//[^\n]*|(\"(?:\\.|[^\"\\\n])*(?:\"|$)|'"
                    r"(?:\\.|[^'\\\n])*(?:'|$)|`(?:\\.|[^`\\])*(?:`|\Z))", re.S | re.M)  # a comment; a string (group 1)
BLANK = re.compile(r"[^\n]")  # what blanking a comment or a block replaces: all but the line ends
RULE = re.compile(r"(?<![^{}])([^{}]+)\{([^{}]*)\}")  # one innermost rule: its selector and its declarations
MOVES = re.compile(r"(?<![\w-])(?:transition|animation)(?:-name|-duration)?\s*:(?!\s*(?:none|0s|initial|unset)\b)")
OFFERED = re.compile(r"\.(m-[a-z][\w-]*)")
CLASSES = re.compile(r"""\bclass(?:Name)?\s*=\s*(?:\{\s*)?(?:"([^"]*)"|'([^']*)'|`([^`]*)`)""")
SHORT_CLASSES = re.compile(r"(?m)^[ \t]*%?[\w-]*(?:#[\w-]+)?((?:\.[A-Za-z_][\w-]*)+)")  # button.m-press, %a.m-lift
MOTION_CLASS = re.compile(r"(?<![\w:-])(?:[a-z-]+:)*(m-[a-z][\w-]*|transition(?:-[a-z]+)?|animate-(?!none\b)[\w-]+)"
                          r"(?![\w-])")
TAG = re.compile(r"<(/?)([A-Za-z][\w.:-]*)([^<>]*?)(/?)>")  # the tags before a poster: what it is inside of
HOLDS = re.compile(r"""\b(?:class(?:Name)?|id)\s*=\s*\{?\s*["'`]([^"'`]*)|\s(data-[\w-]+)""")
VOID = set("area base br col embed hr img input link meta source track wbr".split())
NAMES = re.compile(r"""(?<![\w$)\]])[.#\[]([A-Za-z_][\w-]*)|getElementById\(\s*["'`]([\w-]+)|\b(?:function|class)"""
                   r"""\s+([A-Z]\w*)|\b([A-Z]\w*)\s*=(?!=)""")  # what a scene's file selects, or defines (Scene)
MOUNT = re.compile(r"(?m)^.*?\blazyScene\s*\(\s*[^,;]{0,300}")  # a lazyScene( call's line, to its first argument's end
REFS = re.compile(r"""(?<=["'`/.:<])[A-Za-z_][\w-]*""")  # what a template names: @include('x.hero-poster'), <x-hero>
line_of = lambda text, index: text.count("\n", 0, index) + 1  # noqa: E731 (the line number of INDEX in TEXT)
read = lambda path: pathlib.Path(path).read_text(encoding="utf-8", errors="replace")  # noqa: E731
blanked = lambda found: BLANK.sub(" ", found.group(0))  # noqa: E731 (a comment or a block as spaces: lines stay)
pascal = lambda word: "".join(part[:1].upper() + part[1:] for part in re.split(r"[-_\s]+", word))  # noqa: E731
stem = lambda path: pascal(path.rsplit("/", 1)[-1].split(".")[0])  # noqa: E731 (hero.blade.php: Hero)


def load_rules(path):
    """The features per level and the places from motioncount.json, patterns compiled. ValueError: missing, broken."""
    try:
        data = json.loads(read(path))
        features = [dict(item, signals=[dict(sig, re=re.compile(sig["re"]), also=sig.get("also") and re.compile(
            sig["also"]), rule=re.compile(sig["rule"]) if "rule" in sig else None) for sig in item["signals"]])
            for item in data["features"]]
        signals = [((i, n), sig) for i, item in enumerate(features) for n, sig in enumerate(item["signals"])]
        if set(data["min"]) != set("12345") or {s["view"] for _, s in signals} - {"style", "script", "markup"}:
            raise ValueError("each level 1 to 5 needs a minimum and features, each with signals of a known view")
        return {"min": {int(key): int(value) for key, value in data["min"].items()}, "kit": set(data["kit_files"]),
                "features": features, "signals": signals, "ask": data["ask"],
                "places": re.compile("|".join("(?:%s)" % item for item in data["places"] if item) or "(?!)", re.M)}
    except (OSError, ValueError, LookupError, TypeError, AttributeError, RecursionError, re.error) as error:
        raise ValueError("%s is missing or broken (%s: %s)" % (path, type(error).__name__, error))


def level_on_record(root, ask):
    """The look level in forge-work/levels.json of ROOT, or of the nearest folder above it in its git repository."""
    up = [os.path.abspath(root)]
    while not os.path.lexists(os.path.join(up[-1], ".git")) and os.path.dirname(up[-1]) != up[-1]:
        up.append(os.path.dirname(up[-1]))
    if os.path.lexists(os.path.join(up[-1], ".git")):
        root = next((folder for folder in up if os.path.lexists(os.path.join(folder, "forge-work"))), root)
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
        out["markup"] = (out["script"][0] if ext in SCRIPTS else scrub(text)[0],) * 2
    return out


def rule_at(mask, at):
    """The selector of the rule whose declarations hold AT, looked for within 4000 characters; None outside one."""
    opened, closed = (mask.rfind(char, max(0, at - 4000), at) for char in "{}")
    if opened <= closed:
        return None
    start = max(0, opened - 4000)
    selector = " ".join(mask[max([start - 1] + [mask.rfind(char, start, opened) for char in "{};"]) + 1:opened].split())
    return None if selector.startswith("@") else selector


def holders(text, at, levels=6):
    """The names of the LEVELS elements AT is inside (within 100 KB). {""}: in none (a partial, a component's own)."""
    depth, words, around = 0, set(), 0
    for close, name, attrs, alone in reversed(TAG.findall(text, max(0, at - 100000), at)):
        depth += 0 if alone or name.lower() in VOID else 1 if close else -1
        if depth < 0 and around < levels:  # an element AT is inside; a Vue or Svelte <template> is none
            words |= {word for two in HOLDS.findall(attrs) for word in " ".join(two).split()} | (  # class, id, data-;
                {pascal(re.split(r"[.:]", re.sub(r"^x-", "", name))[-1])} if re.search(r"[A-Z.:-]", name) else set())
            depth, around = 0, around + (name.lower() != "template")
    return words if around else {""}


def look_for(rules, text, ext, name, hits):
    """Add the matches to HITS {(feature, signal): [(file, line, m- classes, holders())]}, "names" and "files"."""
    inside = {sig.get("inside") for _, sig in rules["signals"]}
    for view, (full, mask) in views(text, ext).items():
        if view == "markup":  # its elements' names, and the partials and components it names
            hits.setdefault("files", {})[name] = ({w for two in HOLDS.findall(full) for w in " ".join(two).split()},
                                                  {pascal(re.sub(r"^x-", "", w)) for w in REFS.findall(full)})
        for key, sig in rules["signals"]:
            if sig["view"] != view or sig["also"] and all(mask[m.start()] == "\0" for m in sig["also"].finditer(full)):
                continue
            for count, match in enumerate(sig["re"].finditer(full)):
                at = match.start()
                rule = rule_at(mask, at) if view == "style" and (sig.get("strings") or mask[at] != "\0") else None
                if (sig.get("strings") or mask[at] != "\0") and (not sig["rule"] or rule and sig["rule"].search(rule)):
                    classes = OFFERED.findall(match.group(0) if rule is None else rule) if view == "style" else []
                    around = holders(full, at) if sig.get("inside") else set()
                    hits.setdefault(key, []).append((name, line_of(full, at), classes, around))
                    if rules["features"][key[0]]["id"] in inside:  # what its lazyScene( mounts on (none: what the
                        mounts, every = (NAMES.findall(part) for part in ("\n".join(MOUNT.findall(full)), full))
                        hits.setdefault("names", set()).update([stem(name)] + [w for f in every for w in f[2:] if w] + (
                            [w for f in mounts for w in f[:2] if w] or [w for f in every for w in f[:2] if w]))
                    if not (classes or sig.get("inside")) or count > 100:  # file selects), Scene, Scene.tsx
                        break  # the first is enough; one for an m- class waits for an element with the class


def judge(rules, level, hits, used):
    """The features up to LEVEL, each {level, name, found, where, needs}, from the HITS of look_for()."""
    out, files_of, names, held = [], {}, set(hits.get("names", ())) - {""}, set()
    for file, (words, refs) in hits.get("files", {}).items():  # a template holding the scene's container: its own
        names, held = (names | {stem(file)}, held | refs) if words & names else (names, held)  # component, partials
    for index, feature in enumerate(rules["features"]):
        seen = [hit for number, sig in enumerate(feature["signals"]) for hit in hits.get((index, number), [])
                if (not hit[2] or set(hit[2]) & used) and hit[0] in files_of.get(sig.get("same_file_as"), [hit[0]])
                and files_of.get(sig.get("with"), True) and (not sig.get("inside") or hit[0] in files_of[sig["inside"]]
                or files_of[sig["inside"]] and (hit[3] & names or "" in hit[3] and stem(hit[0]) in held))]
        files_of[feature["id"]] = {hit[0] for hit in seen}
        if feature["level"] <= level:
            out.append({"level": feature["level"], "name": feature["name"], "found": bool(seen),
                        "where": "%s:%d" % seen[0][:2] if seen else None, "needs": feature["needs"]})
    return out


def count_styles(css, name, places, offered, offset=0):
    """The moving rules of one stylesheet. A rule for an .m- class is on offer, not a place yet."""
    for match in RULE.finditer(COMMENT.sub(blanked, css)):  # lines stay
        selector, body = " ".join(match.group(1).split()), match.group(2)
        if selector.startswith("@") or "view-transition" in selector or not MOVES.search(body):
            continue  # a view-transition rule sets how a page change looks: the browser or a script starts it
        offered.update(OFFERED.findall(selector))  # a rule for an m- class: on offer until an element carries it
        if not OFFERED.search(selector):
            start = match.start(1) + len(match.group(1)) - len(match.group(1).lstrip())
            places.append({"file": name, "line": offset + line_of(css, start), "kind": "style rule",
                           "what": selector[-80:]})


def count_markup(text, name, places, used, short=False):  # class="..." and, in Pug, Haml or Slim, tag.class
    lists = [(m.start(), next(group for group in m.groups() if group is not None)) for m in CLASSES.finditer(text)]
    lists += [(m.start(1), m.group(1).replace(".", " ")) for m in SHORT_CLASSES.finditer(text)] if short else []
    for at, value in lists:
        found = sorted(set(MOTION_CLASS.findall(value)))
        used.update(item for item in found if item.startswith("m-"))
        if found:
            places.append({"file": name, "line": line_of(text, at), "kind": "motion class",
                           "what": " ".join(found)[:80], "names": found})


def count_path(roots, rules, level=0):
    """Walk ROOTS as one app (names relative to the one folder, else as given): places, m- classes, unread, features."""
    places, offered, used, unread, files, hits, done = [], set(), set(), [], 0, {}, set()
    for root, (folder, subfolders, names) in ((root, step) for root in roots for step in os.walk(
            os.path.normpath(root), onerror=lambda error: unread.append(str(error)))):
        subfolders[:] = sorted(n for n in subfolders if n not in SKIP and not os.path.islink(os.path.join(folder, n)))
        for item in sorted(names):
            path, ext = os.path.join(folder, item), os.path.splitext(item)[1].lower()
            if ext not in STYLES | MARKUP | SCRIPTS or os.path.islink(path) or ".min." in item or path in done:
                continue
            done.add(path)  # a folder named twice, or one inside another, is read once
            name = os.path.normpath(os.path.relpath(path, root) if len(roots) == 1 else path).replace(os.sep, "/")
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
                count_markup(text, name, places, used, ext in SHORT)
            code = STYLE_BLOCK.sub(blanked, SCRIPT_COMMENT.sub(blanked, text)) if ext in SCRIPTS else ""  # counted
            places += [{"file": name, "line": line_of(code, m.start()), "kind": "script", "what": " ".join(  # above
                re.findall(r"[\w.:-]+", m.group(0)))[:80]} for m in rules["places"].finditer(code)]
    for p in places:  # an m- class counts only when a stylesheet of the app has a moving rule for it
        p["what"] = " ".join(n for n in p.pop("names", [p["what"]]) if not n.startswith("m-") or n in offered)[:80]
    places = [place for place in places if place["what"]]
    return {"places": places, "unused": sorted(offered - used), "unread": unread, "files_read": files,
            "files_moving": len({place["file"] for place in places}), "level": level or None,
            "features": judge(rules, level, hits, used) if level else []}


def main(argv=None):
    """Count the motion under each PATH. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="+", help="the app's folder (in a monorepo: also its workspace packages)")
    parser.add_argument("--min", type=int, metavar="N", help="places that must move (default: 5, or the level's)")
    parser.add_argument("--level", choices=list("12345") + ["auto"], metavar="N|auto", help="the look level, or auto")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        if not all(os.path.isdir(path) for path in args.path) or (args.min is not None and args.min < 1):
            raise ValueError("%s: a PATH is not a folder, or --min is under 1" % " ".join(args.path))
        rules = load_rules(RULES)
        level = level_on_record(args.path[0], rules["ask"]) if args.level == "auto" else int(args.level or 0)
    except ValueError as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    minimum, report = args.min or (rules["min"][level] if level else 5), count_path(args.path, rules, level)
    total, missing = len(report["places"]), [item for item in report["features"] if not item["found"]]
    enough = total >= minimum and report["files_moving"] >= min(2, minimum)
    report["summary"] = {"places": total, "files_moving": report["files_moving"], "min": minimum,
                         "enough": enough, "complete": not report["unread"]}
    lines = ["INCOMPLETE, so not a pass. Could not read %s" % item for item in report["unread"]] + ([] if enough else [
        "FAIL: the app barely moves. Motion counts only once it is in the app's own stylesheets, templates or "
        "scripts: a plan, or a copied motion.css that no element uses, changes nothing."])
    lines += ["FAIL: not level %d yet: %d feature(s) MISSING below." % (level, len(missing))] if missing else []
    lines += ["%d place(s) move, in %d file(s); %d file(s) read. Needed: %d, in 2 files or more." % (total, report[
        "files_moving"], report["files_read"], minimum)] + (["", "Level %d needs:" % level] if level else [])
    lines += ["MISSING  %s: %s" % (item["name"], item["needs"]) for item in missing] + [
        "found  %s  (%s)" % (item["name"], item["where"]) for item in report["features"] if item["found"]]
    if report["unused"]:
        lines += ["", "On offer but on no element (put it to work, or delete its rule): " + ", ".join(report["unused"])]
    lines += ["", "What moves:"] + ["%-12s %s:%d  %s" % (place["kind"], place["file"], place["line"], place["what"])
                                    for place in report["places"]] if report["places"] else []
    print(json.dumps(report, indent=2) if args.json else "\n".join(lines))
    return 2 if report["unread"] else int(not enough or bool(missing))


if __name__ == "__main__":
    sys.exit(main())
