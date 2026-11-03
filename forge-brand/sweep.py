#!/usr/bin/env python3
"""Find names, domains and brand colours that must not ship: the original's, a rival's or an old name.

Every leftover ships: a page title, a link, a CSS colour, a file such as CalendlyEmbed.tsx.
forge-brand runs this after the rebrand; the forge gate runs it again. There is no --fail-on:
every leftover is high and counts. The output never shows a line itself (it could hold a secret).

Usage:
    python3 sweep.py .                        reads forge-work/brand.json in the current folder
    python3 sweep.py . --config forge-work/brand.json --json
    python3 sweep.py . --avoid "Calendly,Calendly LLC" --domains calendly.com --colors "#006bff"

Brand file: {"name": "Slotwise", "avoid": ["Calendly"], "domains": ["calendly.com"], "colors":
["#006bff"], "allow": []}; other keys start with "_"; command-line lists are added to it. Names
match in any case, inside words and file names, with or without spaces, dashes, dots or
underscores; domains as the host or a subdomain; colours as #rgb up to #rrggbbaa and rgb(), not
hsl(). "allow": single words that hold a whole name and are fine (linear-gradient for Linear),
never a domain. A line with forge:allow is listed, not a finding: each needs the user's OK.
Not read: SKIP_ANYWHERE, SKIP_AT_TOP, TOOL_FILES, the brand file, binary files, symlink targets.

Exit codes:
    0  nothing on the lists found
    1  at least one leftover
    2  bad usage (a missing path or brand file, invalid JSON, an unknown key, a bad entry) or an
       INCOMPLETE sweep (no text file checked, or a file or folder that could not be read)
"""

import argparse
import json
import os
import re
import sys

DEFAULT_CONFIG = os.path.join("forge-work", "brand.json")
LIST_KEYS = ["avoid", "domains", "colors", "allow"]
SKIP_ANYWHERE = {".git", "node_modules", "venv", ".venv", "__pycache__", ".next", ".nuxt", ".cache",
                 ".idea", ".vscode"}  # dependencies and tool folders: never your own pages
SKIP_AT_TOP = {"forge-work", "vendor", "dist", "build", "out", "coverage", os.path.join("storage", "framework")}
TOOL_FILES = {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock", "composer.lock",
              "poetry.lock", "Pipfile.lock", "uv.lock", "next-env.d.ts", ".eslintcache", ".phpunit.result.cache"}
HEX = re.compile(r"(?<!&)#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![\w-])")  # not &#169; or #add-to
DOMAIN = r"(?<![\w-])%s(?![\w-])"  # a whole host: help.calendly.com counts, mycalendly.com does not
RGB = re.compile(r"rgba?\(\s*(\d{1,3})[\s,_]+(\d{1,3})[\s,_]+(\d{1,3})(?!\d)", re.IGNORECASE)

KINDS = {  # kind: (title, why, fix), in the order of the report
    "name": ("A name to avoid: %s",
             "an old name looks unfinished; another app's name confuses people and can break its trademark",
             "replace it with your app's name, or a plain word in code (BookingWidget, not TheirNameWidget)"),
    "path": ("A name to avoid in a file or folder name: %s",
             "file names end up in URLs, imports, bundles and error messages",
             "rename the file or folder and update everything that points to it"),
    "domain": ("A domain to avoid: %s",
               "a link or request to another site sends your users, and maybe their data, there",
               "point it at your own domain or remove it"),
    "color": ("A brand colour to avoid: %s",
              "another app's signature colour on a similar layout makes yours look like theirs (trade dress)",
              "use the matching role from your own palette in forge-work/design/tokens.json"),
}


def norm_hex(digits):
    """'06f', '06fc', '0066ff' or '0066ffcc' -> '#0066ff' (lowercase, alpha dropped)."""
    if len(digits) in (3, 4):
        digits = "".join(c * 2 for c in digits[:3])
    return "#" + digits[:6].lower()


def name_pattern(name):
    """'Acuity Scheduling' -> a pattern that also finds AcuityScheduling and acuity-scheduling."""
    words = []
    for word in re.split(r"[\s_-]+", name):
        pieces = [re.escape(piece) for piece in word.split(".") if piece]
        if pieces:
            words.append(r"[._-]?".join(pieces))  # Cal.com also finds calcom and cal-com
    return re.compile(r"[\s_-]*".join(words), re.IGNORECASE)


def clean_domain(entry):
    """'https://user@www.Calendly.com:443/x', '*.calendly.com' or 'calendly.com.' -> 'calendly.com'.
    Raises ValueError when what is left is not a host name with a dot in it."""
    host = entry.strip().lower().split("://")[-1].lstrip("/")  # no scheme
    host = re.split(r"[/?#]", host)[0].rpartition("@")[2].split(":")[0]  # no path, user@ or :port
    host = re.sub(r"^(\*\.)?(www\.)?", "", host.strip("."))  # no dot at either end, no *. or www.
    if not re.match(r"[\w-]+(\.[\w-]+)+$", host):
        raise ValueError("domains entry %r is not a domain: write it as calendly.com" % entry)
    return host


def make_matchers(avoid=(), domains=(), colors=(), allow=()):
    """Check the lists and turn them into patterns, without blanks or repeats. Raises ValueError."""
    names, hosts, colours, words = [], [], set(), []
    for entry in [entry.strip() for entry in avoid if entry.strip()]:
        if sum(c.isalnum() for c in entry) < 3:
            raise ValueError("avoid entry %r is too short: it would match inside ordinary words" % entry)
        if entry.lower() not in [known.lower() for known, _ in names]:
            names.append((entry, name_pattern(entry)))
    for host in sorted({clean_domain(entry) for entry in domains if entry.strip()}):
        hosts.append((host, re.compile(DOMAIN % re.escape(host), re.IGNORECASE)))
    for entry in colors:
        match = HEX.fullmatch("#" + entry.strip().lstrip("#"))
        if not match:
            raise ValueError("%r is not a colour: write it as #rrggbb" % entry)
        colours.add(norm_hex(match.group(1)))
    for word in sorted({entry.strip() for entry in allow if entry.strip()}, key=len, reverse=True):
        rests = [pattern.sub("", word) for _, pattern in names if pattern.search(word)]  # word minus name
        more_than_a_name = rests and all(any(c.isalnum() for c in rest) for rest in rests)
        if not (re.match(r"[\w.-]+$", word) and more_than_a_name):
            raise ValueError("allow entry %r must be one word that holds a whole name from avoid and "
                             "more, such as linear-gradient for Linear, or it hides leftovers" % word)
        words.append((word, re.compile(re.escape(word), re.IGNORECASE)))
    if not (names or hosts or colours):
        raise ValueError("nothing to look for: fill avoid, domains or colors in the brand file, "
                         "or pass --avoid with the original app's name")
    looked_for = [name for name, _ in names] + [host for host, _ in hosts] + sorted(colours)
    return {"names": names, "domains": hosts, "colors": colours, "allow": words, "looked_for": looked_for}


def scan_line(line, matchers):
    """(kind, label, the text found) for each leftover in a line. Allow words hide names, not domains."""
    text, hits = line, []
    for _, pattern in matchers["allow"]:
        text = pattern.sub(" ", text)
    for name, pattern in matchers["names"]:
        match = pattern.search(text)
        if match:
            hits.append(("name", name, match.group(0)))
    for host, pattern in matchers["domains"]:
        match = pattern.search(line)
        if match:
            hits.append(("domain", host, match.group(0)))
    colours = {norm_hex(match.group(1)) for match in HEX.finditer(line)}
    for match in RGB.finditer(line):  # a value over 255 gives a longer string: never a brand colour
        colours.add("#%02x%02x%02x" % tuple(int(value) for value in match.groups()))
    for colour in sorted(colours & matchers["colors"]):
        hits.append(("color", colour, colour))
    return hits


def make_finding(kind, label, text, path, line=None):
    title, why, fix = KINDS[kind]
    where = path if line is None else "%s:%d" % (path, line)
    return {"severity": "high", "title": title % label, "where": where, "why": why, "fix": fix,
            "kind": kind, "label": label, "match": text, "file": path, "line": line}


def walk(root):
    """Yield (path, kind) under ROOT but the skipped folders: folder, file, other or unreadable."""
    to_visit = [root]
    while to_visit:  # a to-do list instead of recursion, so very deep trees work too
        folder = to_visit.pop()
        try:
            entries = sorted(os.scandir(folder), key=lambda entry: entry.name)
        except OSError:
            yield folder, "unreadable"
            continue
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False):
                yield entry.path, "file" if entry.is_file(follow_symlinks=False) else "other"
            elif entry.name not in SKIP_ANYWHERE and os.path.relpath(entry.path, root) not in SKIP_AT_TOP:
                to_visit.append(entry.path)
                yield entry.path, "folder"


def sweep_file(path, shown, matchers, skip=None):
    """(checked, binary, unreadable or brand; findings; places on a forge:allow line) for one file,
    read line by line whatever its size. A NUL byte in the first 8 KB makes it binary."""
    findings, allowed = [], []
    try:
        if skip and os.path.samestat(os.stat(path), skip):  # by inode: on macOS BRAND.json is brand.json
            return "brand", [], []
        with open(path, "rb") as handle:
            if b"\0" in handle.read(8192):
                return "binary", [], []  # an image, a font, an archive
        with open(path, encoding="utf-8", errors="replace") as handle:  # lines end in \n, \r\n or \r
            for number, line in enumerate(handle, 1):
                hits = scan_line(line, matchers)
                if hits and "forge:allow" in line:  # the user's OK for this line
                    allowed.append("%s:%d" % (shown, number))
                elif hits:
                    findings += [make_finding(kind, label, text, shown, number) for kind, label, text in hits]
    except OSError:
        return "unreadable", [], []
    return "checked", findings, allowed


def sweep(root, matchers, skip=None):
    """Sweep a folder or one file, but never the brand file (skip: its os.stat()). Returns (findings, summary)."""
    findings, allowed, places = [], [], {"checked": [], "binary": [], "unreadable": [], "brand": []}
    is_folder = os.path.isdir(root)
    for path, kind in (walk(root) if is_folder else [(root, "file")]):
        shown = os.path.relpath(path, root) if is_folder else path
        if kind == "unreadable":
            places["unreadable"].append(shown)
            continue
        name = os.path.basename(path)
        for what, label, text in scan_line(name, matchers):
            if what == "name":
                findings.append(make_finding("path", label, text, shown + ("/" if kind == "folder" else "")))
        tool_file = name in TOOL_FILES or name.endswith(".tsbuildinfo")  # lock files, caches: not by people
        if kind == "file" and not tool_file:
            status, found, allowed_here = sweep_file(path, shown, matchers, skip)
            places[status].append(shown)
            findings += found
            allowed += allowed_here
    findings.sort(key=lambda f: (list(KINDS).index(f["kind"]), f["label"], f["file"], f["line"] or 0))
    incomplete = []
    if places["unreadable"]:
        incomplete.append("Could not read: %s." % ", ".join(sorted(places["unreadable"])))
    if not places["checked"]:
        incomplete.append("No text file was checked: is the path right?")
    return findings, {"total": len(findings), "failed": bool(findings or incomplete), "incomplete": incomplete,
                      "files_checked": len(places["checked"]), "files_skipped": len(places["binary"]),
                      "unreadable": sorted(places["unreadable"]), "allowed": allowed,
                      "allow_words": [word for word, _ in matchers["allow"]], "looked_for": matchers["looked_for"]}


def read_config(path):
    """The four lists from a brand file. Raises ValueError with a plain message."""
    try:
        with open(path, encoding="utf-8-sig") as handle:  # -sig: a BOM at the start is fine
            config = json.load(handle)
    except OSError as error:
        raise ValueError("cannot read %s (%s)" % (path, error.strerror or error))
    except (ValueError, RecursionError) as error:  # RecursionError: nested far too deep
        raise ValueError("%s is not valid JSON: %s" % (path, error))
    if not isinstance(config, dict):
        raise ValueError('%s must be a JSON object: {"name": ..., "avoid": [...], ...}' % path)
    for key, value in config.items():
        if key not in LIST_KEYS + ["name"] and not key.startswith("_"):  # a typo must not pass
            raise ValueError("%s has an unknown key %r: use name, %s" % (path, key, ", ".join(LIST_KEYS)))
        if key in LIST_KEYS and not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
            raise ValueError('%s: "%s" must be a list of strings' % (path, key))
    return {key: list(config.get(key, [])) for key in LIST_KEYS}


def format_human(findings, summary):
    """The plain-text report: one block per name, domain or colour, with every place it was found."""
    lines, groups = [], {}
    for finding in findings:
        groups.setdefault((finding["kind"], finding["label"]), []).append(finding)
    for group in groups.values():
        lines.append("HIGH      %s (%d %s)" % (group[0]["title"], len(group), "places" if group[1:] else "place"))
        lines.append("          where: " + group[0]["where"])
        lines += ["                 " + finding["where"] for finding in group[1:]]
        lines += ["          why:   " + group[0]["why"], "          fix:   " + group[0]["fix"], ""]
    source = " (from %s)" % summary["config"] if summary["config"] else ""
    lines.append("Looked for: %s%s. Files checked: %d, skipped: %d (binary)." % (
        ", ".join(summary["looked_for"]), source, summary["files_checked"], summary["files_skipped"]))
    if summary["allow_words"]:
        lines.append("Allowed words, check each is fine: " + ", ".join(summary["allow_words"]))
    if summary["allowed"]:
        lines.append("Let through by forge:allow, each needs the user's OK: " + ", ".join(summary["allowed"]))
    if summary["incomplete"]:
        lines.append("INCOMPLETE, so not a pass. " + " ".join(summary["incomplete"]))
    elif findings:
        lines.append("FAIL: %d leftover(s) in %d file(s). Replace every one, then run sweep.py again."
                     % (len(findings), len({finding["file"] for finding in findings})))
    else:
        lines.append("PASS: clean, none of the names, domains or colours to avoid found.")
    return "\n".join(lines)


def main(argv=None):
    """Run the sweep from the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    parser = argparse.ArgumentParser(description="Find names, domains and colours to avoid. No --fail-on.")
    parser.add_argument("path", nargs="?", default=".", help="project folder or one file (default: .)")
    parser.add_argument("--config", help="brand file (default: %s if it exists)" % DEFAULT_CONFIG)
    parser.add_argument("--avoid", default="", help="names to avoid, comma-separated")
    parser.add_argument("--domains", default="", help="domains to avoid, comma-separated")
    parser.add_argument("--colors", default="", help="brand colours to avoid, comma-separated")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    config = args.config or (DEFAULT_CONFIG if os.path.isfile(DEFAULT_CONFIG) else None)
    try:
        if not (os.path.isfile(args.path) or os.path.isdir(args.path)):
            raise ValueError("%s is not a file or folder that exists" % args.path)
        if not (config or args.avoid or args.domains or args.colors):
            raise ValueError("there is no %s in %s: run this from the project root, or pass --config "
                             "or --avoid" % (DEFAULT_CONFIG, os.getcwd()))
        lists = read_config(config) if config else {key: [] for key in LIST_KEYS}
        for key in ("avoid", "domains", "colors"):
            lists[key] += [item for item in getattr(args, key).split(",") if item.strip()]
        matchers = make_matchers(**lists)
    except ValueError as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    findings, summary = sweep(args.path, matchers, os.stat(config) if config else None)
    summary["config"] = config
    text = (json.dumps({"findings": findings, "summary": summary}, indent=2) if args.json
            else format_human(findings, summary))
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"  # an ASCII pipe, or a file name that
    print(text.encode(encoding, "backslashreplace").decode(encoding))  # is not UTF-8: escape, no crash
    if summary["incomplete"]:
        return 2  # part of the project was never read, so the result cannot be trusted
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
