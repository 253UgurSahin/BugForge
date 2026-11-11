#!/usr/bin/env python3
"""Check a project's animations for what makes motion slow, unsafe or hard to bear.

Reads stylesheets (.css .scss .less .pcss), the <style> blocks and scripts of templates (.html, Blade, Django, Vue,
Twig, Svelte, Astro, EJS, Handlebars, Nunjucks, Liquid, Edge, Razor ...) and scripts (.js .ts .jsx .tsx). It reports:
  high    animations or transitions, and no prefers-reduced-motion rule anywhere in the project
  high    an animation library or a Lottie file loaded from a CDN or another host
  medium  a layout property animated (width, height, top, left, right, bottom, margin, padding)
  medium  an animation that never stops: not in a no-preference block, not stopped in a reduce block
  medium  a requestAnimationFrame loop that never ends (it asks for its next frame with no condition), no pause
  medium  GSAP, three.js or Lottie used while no script asks matchMedia for reduced motion
  medium  a video that plays by itself and has no controls
  low     transition: all; a transition over 1 s or under 80 ms; will-change on * or on 6+ rules
Not read: styles written in JavaScript, style="" attributes, indented .sass, minified files, and SKIP_FOLDERS,
symlinks and (with a warning) binary files and files over 1 MB. A file you name is read whatever its type.
Several PATHs are checked as one project (a monorepo's app and its packages). Opt out for one line: forge:allow

Usage:
    python3 motioncheck.py .                    check this folder
    python3 motioncheck.py src --json           machine-readable output
    python3 motioncheck.py . --fail-on medium   exit 1 on medium findings too

Exit codes: 0 nothing at or above --fail-on (default: high); 1 something is; 2 bad usage, no such path, the
rules (motioncheck.json) missing or broken, or not all checked (unreadable, or a named file binary or over 1 MB).
"""

import argparse
import json
import os
import re
import sys

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
MAX_BYTES, MAX_WILL_CHANGE = 1024 * 1024, 5
SKIP_FOLDERS = set(""".git node_modules vendor bower_components venv .venv .tox site-packages __pycache__ dist build
    out .next .nuxt .output .svelte-kit coverage .cache .idea .vscode staticfiles forge-work .claude""".split())
STYLES, SCRIPTS = {".css", ".scss", ".less", ".pcss"}, {".js", ".mjs", ".cjs", ".ts", ".mts", ".jsx", ".tsx"}
MARKUP = {".html", ".htm", ".php", ".djhtml", ".jinja", ".jinja2", ".j2", ".twig", ".vue", ".svelte", ".astro", ".erb",
          ".ejs", ".hbs", ".handlebars", ".mustache", ".njk", ".liquid", ".edge", ".eta", ".cshtml", ".razor",
          ".gohtml", ".tmpl", ".tpl", ".latte", ".heex", ".eex", ".pug", ".jade", ".haml", ".slim", ".nunjucks"}
try:  # rule: (severity, what, why, fix)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "motioncheck.json"), encoding="utf-8") as raw:
        RULES = {rule: tuple(item) for rule, item in json.load(raw)["rules"].items()}
except (OSError, ValueError, LookupError, TypeError, AttributeError) as error:
    RULES = error  # main() says so: exit 2
STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style\s*>", re.S | re.I)
COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?<![:\w])//[^\n]*")
STRING = re.compile(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'')
VENDOR = re.compile(r"^-(?:webkit|moz|ms|o)-")
REDUCE = re.compile(r"prefers-reduced-motion\s*(?::\s*reduce\s*)?\)")
NO_PREFERENCE = re.compile(r"prefers-reduced-motion\s*:\s*no-preference")
ASKS = re.compile(r"prefers-reduced-motion|motion-(?:reduce|safe):")  # the last two: Tailwind's variants
ASKS_IN_SCRIPT = re.compile(r"matchMedia[^\n]*prefers-reduced-motion|useReducedMotion|prefersReducedMotion", re.I)
LAYOUT = re.compile(r"(?<![\w-])(?:(?:(?:max|min)-)?(?:width|height)|(?:top|left|right|bottom|inset|margin|padding)"
                    r"(?:-(?:top|left|right|bottom|inline|block)(?:-(?:start|end))?)?)(?![\w-])")
TIME = re.compile(r"(?<![\w.-])(\d*\.?\d+)(ms|s)\b")
URL = re.compile(r"""(?:https?:|(?<=["'(=]))//([\w.-]+)(/[^\s"'<>)]*)?""")
LOAD = re.compile(r"""\bsrc\s*[=:]|\bimport\b|\bfrom\s*["']|require\(|importScripts|\bhref\s*=|\bpath\s*:""")
FILE = re.compile(r"\.(?:m?js|json|lottie|css)(?:[?#]|$)")
CDNS = ("jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com", "esm.sh", "esm.run", "skypack.dev", "jspm.io",
        "jspm.dev", "googleapis.com", "lottie.host", "lottiefiles.com", "cdn.rive.app")
LIBRARY = re.compile(r"(?<![a-z0-9])(?:gsap|greensock|scrolltrigger|three|lottie|dotlottie|lottiefiles|bodymovin"
                     r"|animejs|anime|framer-motion|motion|popmotion|velocity|aos|scrollreveal|scrollmagic|lenis"
                     r"|locomotive-scroll|barba|swiper|typed|pixi|p5|babylonjs|rive|vanta|tsparticles)(?![a-z0-9])")
USES = re.compile(r"""(?:\bfrom|\bimport|\brequire\s*\()\s*\(?\s*["'](gsap|three|lottie-web|lottie-react"""
                  r"""|react-lottie[\w-]*|@gsap/[\w-]+|@react-three/[\w-]+|@lottiefiles/[\w.-]+|@dotlottie/[\w.-]+)"""
                  r"""(?:/[^"']*)?["']|\b(gsap)\.(?:to|from|fromTo|set|timeline|registerPlugin)\("""
                  r"""|\bnew (THREE)\.|\b(lottie)\.loadAnimation\(""")
RAF = re.compile(r"requestAnimationFrame\(\s*(?:this\.)?([A-Za-z_$][\w$]*)\s*[),]")
DEFINED = r"function\s+%s\b|\b%s\s*=\s*(?:async\s*)?(?:function\b|\(|[A-Za-z_$][\w$]*\s*=>)|\b%s\s*\([^()]*\)\s*\{"
PAUSE = re.compile(r"visibilitychange|document\.hidden|visibilityState|IntersectionObserver")
OPENS = re.compile(r"=>\s*(\{?)|\)\s*(\{)")  # where a function's body starts: an arrow's (a block or not), or ) {
COND = re.compile(r"\b(?:if|while)\b|&&|\|\||\?")  # a condition on the call that asks for the next frame
VIDEO = re.compile(r"<video\b(?![^>]*\bcontrols\b)[^>]*\bautoplay\b[^>]*>", re.I)  # plays by itself, no controls
blank = lambda match: re.sub(r"[^\n]", " ", match.group(0))  # noqa: E731 (as spaces, line ends kept: lines stay right)


def endless(code, name):
    """The line where NAME, in its own body, asks for the next frame again with no condition on that call and no
    return before it: a loop that never ends. 0 when there is none (a tween ends; one frame is no loop)."""
    for found in re.finditer(DEFINED % (name, name, name), code):
        head = OPENS.search(code, found.start())
        start, depth = (head.end(), 1 if head.group(1) or head.group(2) else 0) if head else (len(code), 0)
        end = len(code) if depth else code.find("\n", start) % (len(code) + 1)  # an arrow's expression: its line
        for brace in re.finditer(r"[{}]", code[start:]) if depth else ():
            depth += 1 if brace.group() == "{" else -1
            if not depth:
                end = start + brace.start()
                break
        for call in re.finditer(r"requestAnimationFrame\(\s*(?:this\.)?%s\s*[),]" % name, code[start:end]):
            pre = code[start:start + call.start()]  # nested in a block of its own (an if, a callback): it can end
            if pre.count("{") <= pre.count("}") and not COND.search(re.split("[;{}]", pre)[-1]) and "return" not in pre:
                return code.count("\n", 0, start + call.start()) + 1
    return 0


def split(text, kind):
    """(the CSS, the rest) of one file's text, each with the file's own line numbers. Comments and
    quoted text in the CSS are blanked, so a brace or a word in them is not read as code."""
    if kind in SCRIPTS:
        return "", text
    css, rest = text, ""
    if kind not in STYLES:  # a template: the CSS is what sits inside <style> blocks
        rest = STYLE_BLOCK.sub(blank, text)
        css = "".join(" " if here == there and here != "\n" else here for here, there in zip(text, rest))
        css = re.sub(r"</?style\b[^>]*>", blank, css, flags=re.I)
    css = STRING.sub(blank, COMMENT.sub(blank, css))
    return (LINE_COMMENT.sub(blank, css) if kind in (".scss", ".less") else css), rest


def css_blocks(css):
    """Yield (preludes, declarations, line) for every { } block: what stands before each brace from the outermost
    block to its own (@media ..., then the selector), and its own (property, value, line). All lowercased."""
    stack, line, start = [("", [], 1)], 1, 0
    for mark in re.finditer(r"[{};]", css):
        piece = css[start:mark.start()]
        at = line + piece[:len(piece) - len(piece.lstrip())].count("\n")
        line, start = line + piece.count("\n"), mark.end()
        words = " ".join(piece.split()).lower()
        if mark.group() == "{":
            stack.append((words, [], at))
            continue
        name, colon, value = words.partition(":")
        if colon and re.match(r"[\w-]+$", name.strip()):
            stack[-1][1].append((VENDOR.sub("", name.strip()), value.strip(), at))
        if mark.group() == "}" and len(stack) > 1:
            prelude, declarations, where = stack.pop()
            yield [block[0] for block in stack[1:]] + [prelude], declarations, where


def finding(rule, path, line, detail=""):
    severity, what, why, fix = RULES[rule]
    return {"severity": severity, "rule": rule, "title": what + (": " + detail if detail else ""),
            "where": "%s:%d" % (path, line), "file": path, "line": line, "why": why, "fix": fix}


def check_css(path, css, state, found):
    """Add the findings of one file's CSS to found, and what only the whole project can judge to state."""
    for preludes, declarations, line in css_blocks(css):
        chain = " ".join(preludes)
        selectors = [" ".join(part.split()) for part in preludes[-1].split(",")]
        frames = [prelude for prelude in preludes if prelude.startswith(("@keyframes", "@-webkit-keyframes"))]
        if REDUCE.search(chain):  # what a reduce block stops; nothing inside it is a finding
            if any(name.startswith(("animation", "transition")) for name, _, _ in declarations):
                state["stopped"].update(selectors)
            continue
        if frames:
            state["motion"].append((path, line))
            moved = sorted({name for name, _, _ in declarations if LAYOUT.fullmatch(name)})
            if moved and (path, frames[0]) not in state["frames"]:
                state["frames"].add((path, frames[0]))
                found.append(finding("layout", path, line, "%s changes %s" % (frames[0], ", ".join(moved))))
            continue
        for name, value, at in declarations:
            if name == "will-change" and value != "auto":
                state["will"].append((path, at))
                if any(part.startswith("*") for part in selectors):
                    found.append(finding("will-change", path, at, "on the * selector"))
            if not name.startswith(("animation", "transition")) or value.split()[:1] in ([], ["none"]):
                continue
            state["motion"].append((path, at))
            flat = re.sub(r"\([^()]*\)", "", value)  # without cubic-bezier( ) and var( ) and their commas
            if name in ("transition", "transition-property"):
                if re.search(r"(?<![\w-])all(?![\w-])", flat):
                    found.append(finding("transition-all", path, at))
                moved = sorted({match.group(0) for match in LAYOUT.finditer(flat)})
                if moved:
                    found.append(finding("layout", path, at, "a transition on " + ", ".join(moved)))
            if name in ("transition", "transition-duration"):
                for times in map(TIME.findall, flat.split(",")):  # per property: the first time is the duration
                    ms = float(times[0][0]) * (1000 if times[0][1] == "s" else 1) if times else 0
                    if ms > 1000 or 0 < ms < 80:
                        found.append(finding("duration", path, at, "%g ms" % ms))
            endless = name in ("animation", "animation-iteration-count") and "infinite" in re.split(r"[\s,]+", flat)
            if endless and not NO_PREFERENCE.search(chain):  # finish() looks for a reduce block that stops it
                state["endless"].append((path, at, selectors))


def check_script(path, text, state, found):
    """Add the findings of one file's scripts and markup (TEXT: the file without its CSS) to found."""
    for number, row in enumerate(text.split("\n"), start=1):
        for url in URL.finditer(row):
            host, rest = url.group(1).lower(), (url.group(2) or "").lower()
            known = host not in ("localhost", "127.0.0.1") and (LIBRARY.search(host + rest) or "lottie" in row.lower())
            if known and (host.endswith(CDNS) or (LOAD.search(row) and FILE.search(rest))):
                found.append(finding("cdn", path, number, host))
                break
        for used in USES.finditer(row):
            state["libraries"].append((path, number, next(name for name in used.groups() if name)))
    state["asks_in_script"] = state["asks_in_script"] or bool(ASKS_IN_SCRIPT.search(text))
    code = STRING.sub(blank, LINE_COMMENT.sub(blank, COMMENT.sub(blank, text))) if RAF.search(text) else ""
    for name in [] if PAUSE.search(text) else dict.fromkeys(RAF.findall(code)):
        line = endless(code, re.escape(name))
        if line:
            found.append(finding("raf", path, line, name + "()"))
            break
    for tag in VIDEO.finditer(text):
        found.append(finding("video", path, text.count("\n", 0, tag.start()) + 1))


def finish(state, found):
    """The findings that need the whole project: is reduced motion asked for anywhere, and by a script?"""
    if state["motion"] and not state["asks"]:
        path, line = state["motion"][0]
        found.append(finding("no-reduced-motion", path, line, "%d rule(s) that animate" % len(state["motion"])))
    everything = any(part.startswith("*") for part in state["stopped"])  # * { animation: none } stops all
    for path, line, selectors in state["endless"]:
        if not everything and not state["stopped"] & set(selectors):
            found.append(finding("infinite", path, line, selectors[0]))
    if len(state["will"]) > MAX_WILL_CHANGE:
        path, line = state["will"][0]
        found.append(finding("will-change", path, line, "on %d rules, this is the first" % len(state["will"])))
    for path, line, name in [] if state["asks_in_script"] else state["libraries"]:
        if not any(f["rule"] == "library" and f["file"] == path for f in found):  # once per file
            found.append(finding("library", path, line, name))


def files_under(folder, not_checked):
    """Yield the style, template and script files under folder. Folders it cannot open go in not_checked."""
    for parent, folders, names in os.walk(folder, onerror=lambda e: not_checked.append(e.filename)):
        folders[:] = sorted(name for name in folders if name not in SKIP_FOLDERS)
        for name in sorted(names):  # os.walk does not enter symlinked folders; skip symlinked files
            full = os.path.normpath(os.path.join(parent, name))
            known = os.path.splitext(name)[1].lower() in STYLES | SCRIPTS | MARKUP
            minified = re.search(r"[.-]min\.\w+$", name.lower())
            if known and not minified and os.path.isfile(full) and not os.path.islink(full):
                yield full


def scan_path(path, fail_on="high"):
    """Check a file or folder, or a list of them as one project. Returns {"findings": [...], "summary": {...}}."""
    found, checked, not_checked, paths = [], 0, [], [path] if isinstance(path, str) else path
    state = dict(motion=[], stopped=set(), endless=[], will=[], frames=set(), libraries=[], asks=False,
                 asks_in_script=False)
    for file_path in (f for p in paths for f in (files_under(p, not_checked) if os.path.isdir(p) else [p])):
        try:
            with open(file_path, "rb") as handle:
                data = handle.read(MAX_BYTES + 1)
        except OSError:
            not_checked.append(file_path)
            continue
        if len(data) > MAX_BYTES or b"\0" in data[:8192]:  # too big, or binary (a NUL byte)
            print("skipped: %s (binary, or over 1 MB)" % file_path, file=sys.stderr)
            not_checked += [file_path + " (binary, or over 1 MB)"] if file_path in paths else []  # a named file
            continue
        checked += 1
        rows = data.decode("utf-8", errors="replace").replace("\r\n", "\n").split("\n")
        text = "\n".join("" if "forge:allow" in row else row for row in rows)  # the user's opt-out
        state["asks"] = state["asks"] or bool(ASKS.search(text))
        css, rest = split(text, os.path.splitext(file_path)[1].lower())
        check_css(file_path, css, state, found)
        check_script(file_path, rest, state, found)
    finish(state, found)
    found.sort(key=lambda f: (SEVERITIES.index(f["severity"]), f["file"], f["line"]))
    summary = {severity: sum(f["severity"] == severity for f in found) for severity in SEVERITIES}
    too_bad = any(SEVERITIES.index(f["severity"]) <= SEVERITIES.index(fail_on) for f in found)
    return {"findings": found, "summary": dict(summary, total=len(found), files_checked=checked, fail_on=fail_on,
                                               not_checked=not_checked, failed=too_bad or bool(not_checked))}


def format_human(report):
    """One block per finding and a summary. A file name that is not valid UTF-8 prints as an escape."""
    findings, summary, lines = report["findings"], report["summary"], []
    for item in findings:
        pad = " " * (len(item["severity"]) + 2)
        lines += [item["severity"].upper() + "  " + item["title"], pad + "where: " + item["where"],
                  pad + "why:   " + item["why"], pad + "fix:   " + item["fix"], ""]
    counts = ", ".join("%d %s" % (summary[s], s) for s in SEVERITIES if summary[s])
    lines.append("%d finding%s: %s." % (len(findings), "" if len(findings) == 1 else "s", counts) if findings
                 else "No findings: the motion rules this script knows are kept.")
    missed = ", ".join(summary["not_checked"]) or "nothing"  # anything here: exit code 2
    lines += ["Files checked: %d. Could not check: %s." % (summary["files_checked"], missed),
              "This reads the code. Frame rate, flashing and lost focus need a browser (forge-design motion Step 9.4)."]
    return "\n".join(lines).encode("utf-8", "backslashreplace").decode("utf-8")


def main(argv=None):
    """Run the check from the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: no crash
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("path", nargs="+", help="file or folder to check (several: one project)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high",
                        help="exit 1 when a finding is this bad or worse (default: high)")
    args = parser.parse_args(argv)
    for problem in [p + " does not exist, or is not a file or folder" for p in args.path if not os.path.exists(p)] + (
            [] if isinstance(RULES, dict) else ["motioncheck.json is missing or broken (%s)" % RULES]):
        print("error: %s" % problem, file=sys.stderr)
        return 2
    report = scan_path(args.path, args.fail_on)
    try:
        print(json.dumps(report, indent=2) if args.json else format_human(report), flush=True)
    except BrokenPipeError:  # the reader stopped early (| head): end quietly, no traceback
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    return 2 if report["summary"]["not_checked"] else int(report["summary"]["failed"])  # 2: not all was checked


if __name__ == "__main__":
    sys.exit(main())
