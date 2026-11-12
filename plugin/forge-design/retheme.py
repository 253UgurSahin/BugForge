#!/usr/bin/env python3
"""Re-theme an app that exists: its old colour variables, raw colours and Tailwind colour classes become design
tokens by name, then by each place's role and context, with a log you read (../forge-design/restyle.md, section 2).

Usage:
    python3 retheme.py                                                  the inventory of the project
    python3 retheme.py --map forge-work/design/retheme.json [--write]   a dry run (the log); --write: the files too

Exit codes:
    0  the inventory; or every place mapped (the LITERAL ones, which var() cannot reach, are for the hand pass)
    1  places LEFT (no entry, or a colour the tokens.json next to the map lacks), constants SPLIT, files KEPT
    2  could not run: not in a git repository with a commit, a map or a tokens.json that is not valid
"""

import argparse
import bisect
import collections
import hashlib
import json
import os
import re
import subprocess
import sys

SKIP = set(".git node_modules vendor venv .venv __pycache__ dist build .next coverage forge-work".split())
SCRIPT = tuple(".js .jsx .ts .tsx .mjs .cjs .vue .svelte .astro".split())  # where an exported constant is used
EXTS = tuple(".css .scss .sass .less .html .htm .php .twig .njk .erb .hbs .liquid .jinja .j2".split()) + SCRIPT
HEX = r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])"  # FUNC: rgb() to oklch(), not hsl(var(--x))
FUNC = r"(?<![\w.$-])(?:(?:rgba?|hsla?|hwb|(?:ok)?l(?:ab|ch))\(\s*[\d.]+|color\(\s*[a-z][\w-]*\s+[\d.])[^()]*\)"
COLOUR = re.compile(r"(?:%s|%s)(?!(?:[^{};\"'`#$]|[#$](?!\{))*\{)" % (HEX, FUNC))  # not a selector's #fab {
TW = re.compile(r"(?<![\w/:\[.-])((?:[\w-]+:)*)!?(bg|text|border(?:-[trblxyse])?|ring(?:-offset)?|outline|divide|fill"
                r"|stroke|from|via|to|shadow|accent|caret|decoration|placeholder)-(white|black|[a-z]+-\d{2,3}"
                r"|\[(?:%s|%s)\])(/\d{1,3})?(?![\w-])" % (HEX, FUNC))
ROLES = (("literal", ("themecolor", "fillstyle", "strokestyle", "shadowcolor")), ("shadow", ("boxshadow", "textshadow",
         "filter", "shadow")), ("text", ("color", "caretcolor", "text", "caret", "decoration", "placeholder",
         "webkittextfill")), ("bg", ("background", "bg", "accent", "from", "via", "to")), ("border", ("border",
         "outline", "columnrule", "ring", "divide")), ("icon", ("fill", "stroke", "stop")))  # literal: takes no var()
VAR, DEF = re.compile(r"var\(\s*(--[\w-]+)"), re.compile(r"(?<![\w-])(--[\w-]+)\s*:\s*([^;{}]*)")  # a use, a definition
CONST = re.compile(r"\b(export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::\s*[\w.]+\s*)?=\s*([\"'`])(%s|%s)\3"
                   % (HEX, FUNC))  # a colour constant in code; a Sass or Less variable stays LITERAL
NAME_BEFORE = re.compile(r"([\"']?)(-{0,2}[A-Za-z_$@][\w$-]*)\1\s*$")
ZONE = re.compile(r"\btheme_?color[\"']?\s*[:=]\s*\[[^\]]*\]", re.I)  # Next's themeColor list of { media, color }
WHOLE = re.compile(r"[\"'](?:(?:next|@vercel)/og|nodemailer|@react-email/[\w-]+|(chart\.js(?:/auto)?|echarts[\w/-]*"
                   r"|react-chartjs-2))[\"']|\b(?:create(?:Theme|System|Vuetify)|extendTheme|define\w*Config)\("
                   r"|\bMantineThemeOverride\b|<MantineProvider\b[^>]*\btheme=\{\{")  # group 1: a chart on a canvas
IMPORT = r"\bimport\b[^;{]*\{[^}]*\b%s\b[^}]*\}\s*from\b|\bimport\s*\*\s*as\s+(\w+)[\s\S]*?\b\1\.%s\b"  # imports NAME
SASS = re.compile(r"<style\b[^>]*\blang=[\"']?(s[ac]ss|less)\b[^>]*>(.*?)</style>", re.S | re.I)  # in a .vue, .svelte
CALL = re.compile(r"([\w.$-]+)\((?:[^(){}\[\]]|\([^()]*\))*$")  # the call a value is an argument of: mix(#fff,
CSS_CALL = re.compile(r"(var|calc|color-mix|light-dark|drop-shadow|[\w-]*gradient)$", re.I)  # these take var()
FORGE = re.compile(r"/\* forge theme start.*?/\* forge theme end \*/", re.S)  # theme.py's block: the tokens
BG = re.compile(r"(?:background(?:-color)?|backgroundColor|\bbg)\s*[:=]\s*([^;\n}]+)")
TW_BG = re.compile(r"(?<![\w-])bg-([a-z]+(?:-\d{2,3})?)(?![\w-])")
IGNORE = {"href", "src", "id", "key", "d", "viewbox", "path", "url", "to", "xlinkhref", "name", "value", "class"}
LITERAL_FILE = re.compile(r"(^|/)(manifest\.\w+|[^/]*\.webmanifest|(opengraph|twitter)-image\.\w+|global-error\.\w+)$"
                          r"|(^|/)([^/]*_)?e?-?mails?(ers?)?/|(^|/)(?![^/]*\.(blade\.php|[jt]sx|vue|svelte|astro)$)"
                          r"[^/]*mail[^/]*\.\w+$", re.I)  # a manifest, an OG image, global-error, e-mails (mail.ts)
FILL = re.compile(r"--color-(accent|danger|success|warning|brand|primary|error|info)(-strong)?$")
WORDS = {"float": ["menu", "modal", "dialog", "popover", "toast", "tooltip", "dropdown", "drawer", "sheet", "overlay",
                   "popup", "listbox"], "field": ["input", "textarea", "select", "field", "search", "combobox"]}
FLOATING = re.compile(r"position\s*:\s*[\"']?fixed|(?<![\w-])fixed(?![\w-])|absolute.{0,300}?(z-?index|\bz-\d)", re.S)
PSEUDO, PROPS = re.compile(r"::?[\w-]+(\([^)]*\))?"), {}  # :hover and the like; the map's "props"
PALETTE = re.compile(r"--color-(white|black|[a-z]+-\d{2,3})$")  # Tailwind's own, gone after the theme commit
Stop = type("Stop", (Exception,), {"__doc__": "The run cannot go on (exit 2)."})


def git(*args):
    try:
        done = subprocess.run(["git", "-c", "core.fsmonitor=false"] + list(args), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Stop("git did not run: %s" % error)
    return done.returncode, done.stdout.decode("utf-8", "surrogateescape")


def norm(text):  # ('#rrggbb', alpha, key: '#rrggbb' or '#rrggbb/0.5'); a Tailwind name or oklch() is its own key
    c = {"white": "#fff", "black": "#000"}.get(text.strip().lower(), text.strip().lower())
    m = re.match(r"rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)\s*(?:[,/]\s*([\d.]+)(%?))?\s*\)$", c)
    base, alpha = re.sub(r"\s*([(),/])\s*", r"\1", re.sub(r"\s+", " ", c)), 1.0  # oklch(0.9 0 0/10%), hsl(1,2%,3%)
    if c.startswith("#"):
        h = c[1:] if len(c) > 5 else "".join(ch * 2 for ch in c[1:])
        base, alpha = "#" + h[:6], (round(int(h[6:8], 16) / 255, 2) if len(h) == 8 else 1.0)
    elif m:
        base = "#%02x%02x%02x" % tuple(min(255, int(float(x))) for x in m.groups()[:3])
        alpha = round(float(m.group(4)) / (100 if m.group(5) else 1), 2) if m.group(4) else 1.0
    return base, alpha, base if alpha == 1 else "%s/%g" % (base, alpha)


def role_of(name):  # the map's "props" first: the app's own names, such as an icon's c= or a Dutch "kleur"
    n = (name or "").lower().replace("-", "").replace("_", "")
    return PROPS.get(name) or next((role for role, starts in ROLES if n.startswith(starts)), "other")


def prop_at(text, pos):  # (name, prop|attr|quoted): the nearest name: or name= before POS, past ternaries, arrows
    depth, lo = 0, max(0, pos - 600)
    for i, c in zip(range(pos - 1, lo - 1, -1), reversed(text[lo:pos])):
        if c in ")]}" or c in "([{" and depth:
            depth += 1 if c in ")]}" else -1
        elif c == "{" and text[i - 1:i] not in "$=" or c == ";" and depth == 0:
            return None, None  # the start of the rule or object: no property (fill={tone} reads on to fill)
        elif depth == 0 and c in ":=" and text[i + 1:i + 2] not in ("=", ">") and text[i - 1:i] not in "=!<>:":
            m = NAME_BEFORE.search(text, max(lo, i - 80), i)
            if m and text[lo:m.start()].rstrip()[-1:] not in ("?", ":"):  # `a ? b : "#000"`: b is no property
                return m.group(2), "quoted" if m.group(1) else ("attr" if c == "=" else "prop")
    return None, None


def scan(path, text, cfg):  # every place in TEXT with an old colour variable, a raw colour or a Tailwind class
    low, found, opens, closes, chain, stack = path.lower(), [], [], [], [], []
    cssy, pre = low.endswith((".css", ".scss", ".sass", ".less")), low.endswith((".scss", ".sass", ".less"))
    sheets = [(0, len(text), low)] if pre else [(z.start(2), z.end(2), z.group(1)) for z in SASS.finditer(text)]
    for m in re.finditer(r"[{}]", text):  # every {...} pair; its chain: the pair, then each pair it sits in
        if m.group(0) == "{":
            chain.append([len(opens)] + (chain[stack[-1]] if stack else []))
            stack.append(len(opens))
            opens.append(m.start())
            closes.append(len(text))
        elif stack:
            closes[stack.pop()] = m.start()
    zones, skips = [z.span() for z in ZONE.finditer(text)], [b.span() for b in FORGE.finditer(text)]
    whole = WHOLE.search(text)  # an OG image, a JS theme, an e-mail: every colour stays; a chart: its raw ones
    after = lambda marks, o: max([0] + [p + len(c) for c in marks for p in [text.rfind(c, 0, o)] if p >= 0])  # noqa
    head_of = lambda o: max(after(("{", "}", ";", "*/"), o) if cssy else text.rfind("\n", 0, o - 1) + 1, o - 300)
    filled = {PSEUDO.sub("", " ".join(s.split())) for o, c in zip(opens, closes) if cssy and cfg["on_fill"](
        text[o:c]) for s in text[head_of(o):o].split(",")}  # rules that fill with a strong colour (.btn)

    def add(start, end, what, key, alpha, role, prop, kind, **extra):
        k = bisect.bisect_left(opens, start) - 1  # the innermost {...} around START
        k = next((j for j in (chain[k] if k >= 0 else ()) if closes[j] >= start), -1)
        if what == "class" or kind == "attr" or k < 0:  # a class or an attribute: its line, and the one before
            s, e = text.rfind("\n", 0, start) + 1, text.find("\n", start) % (len(text) + 1)
            ctx, label, fill = text[text.rfind("\n", 0, max(0, s - 1)) + 1:e], "", cfg["on_fill"](text[s:e])
        else:  # a declaration: its rule or object, with the selector or the line that opens it
            o, head = opens[k], head_of(opens[k])
            ctx = text[head:o] + text[max(o, start - 800):min(closes[k] + 1, start + 800)]
            label = " ".join(text[head:o].split())[-40:]  # a state or a child of a filled rule: .btn:hover, .btn svg
            sels = {PSEUDO.sub("", " ".join(s.split())) for s in text[head:o].split(",")}  # nested: &:hover, svg
            fill = cfg["on_fill"](ctx) or any(b == f or b.startswith(f + " ") for f in filled for b in sels) or any(
                cssy and cfg["on_fill"](text[opens[j]:min([closes[j] + 1] + opens[j + 1:j + 2])]) for j in chain[k][1:])
        plain = re.sub(r"([a-z])([A-Z])", r"\1 \2", ctx).lower()
        flags = [f for f, hit in (("on-fill", fill), ("float", FLOATING.search(plain) or cfg["float"].search(plain)),
                                  ("field", cfg["field"].search(plain))) if hit]
        call = what == "colour" and CALL.search(text, max(0, start - 999), start)  # mix(#fff, 5%), THREE.Color()
        sass = any(a <= start < b and re.match(r"\s*[$@][\w-]+\s*:", text[max(a, after(";{}" + "\n" * x.endswith(
            "sass"), start)):start]) for a, b, x in sheets)  # $x: #fff, in a .scss file or a <style lang="scss">
        literal = bool(LITERAL_FILE.search(path) or whole and (what == "colour" or not whole.group(1)) or sass
                       or role == "literal" or any(a <= start < b for a, b in zones)  # theme-color, a canvas
                       or kind == "quoted" and (prop or "").endswith("-color") and not cssy
                       or prop == "content" and "theme-color" in ctx or call and not CSS_CALL.match(call.group(1)))
        found.append(dict(extra, start=start, end=end, what=what, key=key, alpha=alpha, role=role, flags=flags,
                          prop=prop, kind=kind, label=label, literal=literal, line=text.count("\n", 0, start) + 1))

    for m in TW.finditer(text) if cfg["tailwind"] else ():  # Tailwind's own classes: Bootstrap has a bg-white too
        add(m.start(), m.end(), "class", *norm(m.group(3).strip("[]"))[:2], role_of(m.group(2)), m.group(2), "class",
            variants=m.group(1), suffix=m.group(4) or "", dark="dark:" in m.group(1))
    for m in (v for v in VAR.finditer(text) if v.group(1) in cfg["old"] or PALETTE.match(v.group(1))):  # the app's,
        prop, kind = prop_at(text, m.start())  # the map's and Tailwind's own colour variables (--color-gray-200)
        add(m.start(1), m.end(1), "var", m.group(1), 1.0, role_of(prop), prop, kind)
    for m in COLOUR.finditer(TW.sub(lambda tw: " " * len(tw.group(0)), text) if cfg["tailwind"] else text):
        prop, kind = prop_at(text, m.start())
        if not prop or prop.startswith("--") or prop.lower().replace("-", "") in IGNORE:
            continue  # not a value, or the definition of a custom property (the hand pass removes those)
        const = cfg["constants"].get((path, m.start()))  # the definition of a constant: the roles of its uses
        role = role_of(prop) if const is None else (sorted(const) + ["other"])[0] if len(const) < 2 else "split"
        add(m.start(), m.end(), "colour", *norm(m.group(0))[:2], role, prop, kind)
    return [p for p in found if not any(a <= p["start"] < b for a, b in skips)]  # not theme.py's own block


def load_map(path):  # the map, and the colours of the tokens.json next to it: one the map writes must be there
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
        groups = [raw.get(g) or {} for g in ("vars", "colours")]
        PROPS.update(raw.get("props") or {})
        if set(raw) - {"vars", "colours", "keep", "skip", "words", "props", "_notes"} or not all(all(
                isinstance(v, str) or all(isinstance(x, str) for x in v.values()) for v in g.values()) for g in groups):
            raise ValueError("a key or a value of the wrong kind")
        tokens = os.path.join(os.path.dirname(path), "tokens.json")
        with open(tokens if os.path.isfile(tokens) else os.devnull, encoding="utf-8") as handle:
            named = dict(json.loads(handle.read() or "{}")).get("color")  # none (yet): nothing to check against
        return dict(vars=groups[0], colours={norm(k)[2]: v for k, v in groups[1].items()}, skip=raw.get("skip", []),
                    keep={norm(k)[2] for k in raw.get("keep", [])}, words=raw.get("words", {}), named=named, targets={
                        v for g in groups for e in g.values() for v in ([e] if isinstance(e, str) else e.values())})
    except (OSError, ValueError, AttributeError, TypeError) as error:
        raise Stop('the map %s, or the tokens.json next to it: %s (see restyle.md, "The map")' % (path, error))


def prepare(cfg, files):  # the app's colour variables, its colour constants with their roles, the on-fill test
    cfg.update(colour_vars=set(), constants={}, tailwind=any("tailwind" in files[p] for p in files if ".css" in p))
    for path, text in files.items():  # (theme.py's block holds the tokens, not old values)
        cfg["colour_vars"].update(m.group(1) for m in DEF.finditer(FORGE.sub("", text)) if COLOUR.search(m.group(2)))
        for m in CONST.finditer(text):  # its roles: its uses after it and, exported, in the scripts that import it
            use = re.compile(r"{0}(?<![\w$]{0})(?<![tr] {0})(?![\w$-])".format(re.escape(m.group(2))))  # not const W
            homes = [(text, m.end())] + [(t, 0) for p, t in files.items() if m.group(1) and p != path and p.endswith(
                SCRIPT) and re.search(IMPORT % ((re.escape(m.group(2)),) * 2), t)]  # not a prop of the same name
            roles = {role_of(prop_at(t, u.start())[0]) for t, at in homes for u in use.finditer(t, at)} - {"other"}
            cfg["constants"][path, m.start(4)] = roles or ({"split"} if m.group(1) else roles)  # exported, unseen
    fill_vars, fill_keys = [{k for k, e in cfg[g].items() if FILL.match(e if isinstance(e, str) else e.get(
        "bg", e.get("*", "")))} for g in ("vars", "colours")]  # the old variables and colours of a strong fill
    def on_fill(ctx):
        return any(any(v in fill_vars or FILL.match(v) for v in VAR.findall(value)) or any(
            norm(c.group(0))[2] in fill_keys for c in COLOUR.finditer(value)) for value in BG.findall(ctx)) or any(
            n in fill_keys or FILL.match("--color-" + n) for n in TW_BG.findall(ctx))
    words = {k: re.compile(r"(?<![a-z])(%s)(?:s|es|er)?(?![a-z])" % "|".join(
        re.escape(w.lower()) for w in v + list(cfg["words"].get(k, [])))) for k, v in WORDS.items()}
    cfg.update(on_fill=on_fill, old=set(cfg["vars"]) | set(cfg["colour_vars"]) - cfg["targets"], **words)  # no token


def replacement(place, cfg):  # (the new text, None), or (None, why the place is LEFT)
    group = cfg["vars" if place["what"] == "var" else "colours"]
    exact = group.get(place["key"] if place["alpha"] == 1 else "%s/%g" % (place["key"], place["alpha"]))
    entry = exact if exact is not None else group.get(place["key"])
    value = entry if isinstance(entry, str) or entry is None else next((entry[k] for k in [
        "%s %s" % (place["role"], f) for f in place["flags"]] + [place["role"], "*"] if k in entry), None)
    token = (value or "").startswith("--")
    if value is None or place["what"] == "var" and not token:
        return None, "no token for %s as %s" % (place["key"], " ".join([place["role"]] + place["flags"]))
    named = cfg.get("named") if place["what"] != "var" or value.startswith("--color-") or place["key"] in cfg[
        "colour_vars"] or PALETTE.match(place["key"]) else None  # a colour: in tokens.json (an old radius --r is not)
    if token and named is not None and not (value.startswith("--color-") and value[8:] in named):
        return None, "%s is no colour of tokens.json, so nothing sets it: add it there, or map to one" % value
    if place["what"] == "class":
        name = value[8:] if value.startswith("--color-") else ("[var(%s)]" if token else "[%s]") % value
        return ("" if place["dark"] else place["variants"] + place["prop"] + "-" + name + place["suffix"]), None
    new = value if place["what"] == "var" or not token else "var(%s)" % value
    return (new if place["alpha"] >= 1 or exact is not None else "color-mix(in srgb, %s %g%%, transparent)" % (
        new, round(place["alpha"] * 100))), None


def run(args):
    sha = lambda text: hashlib.sha1(text.replace("\r\n", "\n").encode("utf-8", "surrogateescape")).hexdigest()  # noqa
    cfg = load_map(args.map) if args.map else dict(vars={}, colours={}, keep=set(), skip=[], words={}, targets=set())
    code, listed = git("ls-files", "-z")
    if code or git("rev-parse", "--verify", "-q", "HEAD")[0]:
        raise Stop("not in a git repository with a commit: run it from the app's root, after its last commit")
    wanted = [p for p in listed.split("\0") if p.lower().endswith(EXTS) and not SKIP & set(p.split("/")[:-1])
              and ".min." not in p and not any(p.startswith(s) for s in cfg["skip"])]
    files = {p: t.replace("\r\n", "\n") for p, (c, t) in ((p, git("show", "HEAD:./" + p)) for p in wanted) if c == 0}
    prepare(cfg, files)
    state_file = os.path.join(os.path.dirname(args.log) or ".", "retheme.state.json")
    with open(state_file if args.map and os.path.isfile(state_file) else os.devnull, encoding="utf-8") as handle:
        state = json.loads(handle.read() or "{}")
    left, log, notes = collections.OrderedDict(), [], collections.defaultdict(list)
    for path, text in sorted(files.items()):
        pieces, last = [], 0
        for p in sorted(scan(path, text, cfg), key=lambda place: place["start"]):
            role = " ".join([p["role"] + ("(%s)" % p["prop"]) * (p["role"] == "other")] + p["flags"])
            where = "%s:%d [%s] %s: %s" % (path, p["line"], p["label"], p["prop"], text[p["start"]:p["end"]])
            kind = "LITERAL" if p["literal"] else "SPLIT" if p["role"] == "split" else None
            name = p["key"] + ("" if p["alpha"] == 1 else "/%g" % p["alpha"])  # with its alpha: its own value
            new, why = (None, None) if kind or {p["key"], name} & cfg["keep"] else replacement(p, cfg)
            if why:  # grouped by value: with no map, this is the inventory
                left.setdefault(name, [collections.Counter(), where])[0][role] += 1
            if kind or why:
                notes[kind or "LEFT"].append("%s %s  (%s)" % (kind or "LEFT", where, why or role))
            elif new is not None:
                pieces, last = pieces + [text[last:p["start"]], new], p["end"]
                log.append("%s -> %s  (%s)" % (where, new or "(removed: the tokens switch by themselves)", role))
        out = "".join(pieces) + text[last:]
        if args.map and (out != text or path in state) and os.path.isfile(path):
            with open(path, encoding="utf-8", errors="surrogateescape", newline="") as handle:
                now = handle.read()
            if sha(now) not in (sha(text), state.get(path)) and not args.force:
                notes["KEPT"].append("KEPT %s: changed since the last run (by hand, or theme.py): see --force" % path)
            elif args.write and sha(now) != sha(out):
                with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as handle:
                    handle.write(out.replace("\n", "\r\n") if "\r\n" in now else out)
                state[path] = sha(out)
    os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
    body = "\n".join(log + [n for k in ("KEPT", "SPLIT", "LEFT", "LITERAL") for n in notes[k]]) + "\n"
    for name, body in [(args.log, body)] + ([(state_file, json.dumps(state, sort_keys=True))] if args.write else []):
        with open(name, "w", encoding="utf-8", errors="surrogateescape") as handle:
            handle.write(body)
    print("retheme: %d committed files, %d changes in %d files (%s); log: %s" % (len(files), len(log), len({
        x.split(":")[0] for x in log}), args.map and ("a dry run", "written")[args.write] or "the inventory", args.log))
    print("LEFT %d places, %d values: how often, as which role, the first place" % (len(notes["LEFT"]), len(left)))
    for name, (roles, where) in sorted(left.items(), key=lambda item: -sum(item[1][0].values())):
        print("  %-22s %5d  %s\n      %s" % (name, sum(roles.values()), ", ".join(
            "%s %d" % r for r in roles.most_common()), where))
    for kind in ("SPLIT", "LITERAL", "KEPT"):
        print("%s %d%s" % (kind, len(notes[kind]), "".join("\n  " + n for n in notes[kind][:25])))
    return 1 if args.map and (notes["LEFT"] or notes["SPLIT"] or notes["KEPT"]) else 0


def main(argv=None):
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("--map", metavar="MAP", help="the map to apply (JSON); without it: the inventory")
    parser.add_argument("--write", action="store_true", help="with --map: write the files (else a dry run)")
    parser.add_argument("--force", action="store_true", help="also rewrite files changed since the last run")
    parser.add_argument("--log", default=os.path.join("forge-work", "design", "retheme.log"), help="the log file")
    for stream in [s for s in (sys.stdout, sys.stderr) if hasattr(s, "reconfigure")]:
        stream.reconfigure(errors="backslashreplace")
    try:
        return run(parser.parse_args(argv))
    except Stop as error:
        print("retheme: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
