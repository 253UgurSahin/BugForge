#!/usr/bin/env python3
"""Find text the clone shares with the original: runs of 6 or more words in a row.

Clean-room proof for forge-build: every word of the clone is written fresh, so 6+ words in a row
that it shares with the original's pages are their copy, or written from memory of it. Labels
that match by what they do ("Add a plant") are shorter. The original's text is what pagetext.py
kept in forge-work/original-text/. Run it from the project root.

Usage:
    python3 copycheck.py                    check the whole project (.)
    python3 copycheck.py dist src           check these folders or files
    python3 copycheck.py --json --words 4   machine-readable output, shorter runs too

It reads every text file under the paths line by line, and HTML-like files (templates,
components) also by block, so a sentence wrapped over lines or with a link in it is still one
run. Skipped: forge-work, dependencies, build output (unless you name it), lock files, binary
files, symlinks. A run in forge-work/copy-allow.txt (one per line, # for notes) is let through,
such as the user's own words or a legal phrase: each needs the user's OK.

Exit codes:
    0  nothing shared
    1  at least one run of --words (default 6) or more words is in both
    2  bad input or an incomplete check: a missing path, no kept text (run pagetext.py), no
       file read, or a file or folder it could not read
"""

import argparse
import json
import os
import re
import sys
import unicodedata

TEXT_DIR = os.path.join("forge-work", "original-text")
ALLOW_FILE = os.path.join("forge-work", "copy-allow.txt")
WORD = re.compile(r"[^\W_]+")  # letters and digits only, the same as in pagetext.py
TAG = re.compile(r"</?([A-Za-z][\w:.-]*)(?:[^>\"']|\"[^\"]*\"|'[^']*')*>")  # a '>' in quotes is no end
INLINE = set("a abbr b bdi bdo cite code data del dfn em font i ins kbd mark q s samp small span strong "
             "sub sup time tt u var wbr".split())  # tags inside a sentence: they do not end a block
HTML_LIKE = (".html", ".htm", ".xhtml", ".php", ".twig", ".jinja", ".jinja2", ".j2", ".njk", ".liquid",
             ".hbs", ".handlebars", ".mustache", ".ejs", ".erb", ".vue", ".svelte", ".astro", ".jsx",
             ".tsx", ".mdx", ".svg", ".xml")
SKIP_ANYWHERE = {".git", "node_modules", "venv", ".venv", "__pycache__", ".next", ".nuxt",
                 ".svelte-kit", ".output", ".turbo", ".cache", ".idea", ".vscode"}
SKIP_AT_TOP = {"forge-work", "vendor", "dist", "build", "out", "coverage", "storage", "staticfiles"}
TOOL_FILES = {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock",
              "composer.lock", "poetry.lock", "Pipfile.lock", "uv.lock", ".phpunit.result.cache"}
FIX = ("write it again in your own words. Must it match (the user's own words, a legal phrase)? "
       "Then put it on its own line in %s, with the user's OK" % ALLOW_FILE)


def words(text):
    """'Elke plant, op tijd!' -> ['elke', 'plant', 'op', 'tijd']."""
    return WORD.findall(unicodedata.normalize("NFKC", text).lower())


def tag_blocks(text):
    """(line, words) of each block in an HTML-like file: inline tags stay inside a block, every
    other tag ends one. Code in it gives odd blocks, which match nothing the original says."""
    blocks, start, line = [], 0, 1
    for match in list(TAG.finditer(text)) + [None]:
        if match is not None and match.group(1).lower() in INLINE:
            continue
        end = match.start() if match else len(text)
        chunk = TAG.sub("", text[start:end])  # only inline tags are left in it
        first = len(chunk) - len(chunk.lstrip())
        if words(chunk):
            blocks.append((line + chunk.count("\n", 0, first), words(chunk)))
        line += text.count("\n", start, match.end() if match else end)
        start = match.end() if match else end
    return blocks


def file_blocks(path, text):
    """(line, words) blocks of one file: each line, and the blocks of an HTML-like file."""
    lines = [(number, words(line)) for number, line in enumerate(text.splitlines(), 1)]
    return [block for block in lines if block[1]] + (tag_blocks(text) if path.lower().endswith(HTML_LIKE) else [])


def load_original(size):
    """{SIZE words in a row: the names of the original's pages that have them}, from TEXT_DIR."""
    runs = {}
    for name in sorted(os.listdir(TEXT_DIR)) if os.path.isdir(TEXT_DIR) else []:
        if name.endswith(".txt"):
            with open(os.path.join(TEXT_DIR, name), encoding="utf-8", errors="replace") as handle:
                for found in [words(line) for line in handle if not line.startswith("#")]:
                    for i in range(len(found) - size + 1):
                        runs.setdefault(tuple(found[i:i + size]), set()).add(name[:-4])
    if not runs:
        raise ValueError("%s holds no text of the original: in clone mode forge-recon keeps it there with "
                         "pagetext.py, and without it there is nothing to compare" % TEXT_DIR)
    return runs


def read_allow():
    """The phrases in ALLOW_FILE as lists of words, longest first. Lines starting with # are notes."""
    if not os.path.isfile(ALLOW_FILE):
        return []
    with open(ALLOW_FILE, encoding="utf-8-sig") as handle:
        phrases = [words(line) for line in handle if not line.lstrip().startswith("#")]
    return sorted([phrase for phrase in phrases if phrase], key=len, reverse=True)


def segments(found, allow, used):
    """FOUND split around each allowed phrase in it (noted in USED): the rest is still checked."""
    parts, part, i = [], [], 0
    while i < len(found):
        phrase = next((p for p in allow if found[i:i + len(p)] == p), None)
        if phrase:
            used.add(" ".join(phrase))
            parts, part, i = parts + [part], [], i + len(phrase)
        else:
            part, i = part + [found[i]], i + 1
    return parts + [part]


def shared_runs(found, original, size):
    """Each longest run in FOUND whose every SIZE words in a row are in ORIGINAL."""
    start = None
    for i in range(len(found) - size + 2):  # one step past the last window ends an open run
        hit = i <= len(found) - size and tuple(found[i:i + size]) in original
        if hit and start is None:
            start = i
        elif not hit and start is not None:
            yield found[start:i - 1 + size]
            start = None


def files_under(root, unreadable):
    """ROOT itself, or every file under it but the skipped folders, tool files and symlinks."""
    if not os.path.isdir(root):
        return [root]
    found = []
    for folder, subfolders, names in os.walk(root, onerror=lambda error: unreadable.append(error.filename)):
        at_top = os.path.relpath(folder, root) == "."
        subfolders[:] = sorted(name for name in subfolders if name not in SKIP_ANYWHERE
                               and not (at_top and name in SKIP_AT_TOP)
                               and not os.path.islink(os.path.join(folder, name)))
        found += [os.path.join(folder, name) for name in sorted(names) if name not in TOOL_FILES
                  and not name.endswith((".map", ".tsbuildinfo")) and not os.path.islink(os.path.join(folder, name))]
    return found


def finding(text, files, runs, original, size):
    """The finding for one shared run, or None when a longer run in the same files says it all."""
    longer = [other for other in runs if len(other) > len(text) and " %s " % text in " %s " % other]
    places = ["%s:%d" % (path, line) for path, lines in files.items()
              if not any(path in runs[other] for other in longer) for line in sorted(lines)]
    if not places:
        return None
    run = text.split()
    pages = sorted(set().union(*(original[tuple(run[i:i + size])] for i in range(len(run) - size + 1))))
    has = ("pages %s have" if pages[1:] else "page %s has") % " and ".join(pages)
    return {"severity": "high", "title": '%d words in a row from the original: "%s"' % (len(run), text),
            "where": ", ".join(places[:10]) + (" and %d more" % (len(places) - 10) if places[10:] else ""),
            "why": "the original's %s the same words: copied, or written from memory of it" % has,
            "fix": FIX, "run": text, "words": len(run), "places": places, "original": pages}


def check(paths, original, size, allow):
    """(findings, summary) for the files under PATHS."""
    unreadable, runs, used, counts = [], {}, set(), {"checked": 0, "binary": 0}
    for root in paths:
        for path in files_under(root, unreadable):
            shown = path if os.path.isabs(root) else os.path.relpath(path)
            try:
                with open(path, "rb") as handle:
                    data = handle.read()
            except OSError:
                unreadable.append(shown)
                continue
            binary = b"\0" in data[:8192]  # an image, a font, an archive
            counts["binary" if binary else "checked"] += 1
            for line, found in [] if binary else file_blocks(path, data.decode("utf-8", errors="replace")):
                for part in segments(found, allow, used) if allow else [found]:
                    for run in shared_runs(part, original, size):
                        runs.setdefault(" ".join(run), {}).setdefault(shown, set()).add(line)
    found = [finding(text, files, runs, original, size)
             for text, files in sorted(runs.items(), key=lambda item: (-len(item[0]), item[0]))]
    findings = [one for one in found if one]
    verdict = "INCOMPLETE" if unreadable or not counts["checked"] else "FAIL" if findings else "PASS"
    return findings, {"runs": len(findings), "files_checked": counts["checked"], "files_skipped": counts["binary"],
                      "words": size, "unreadable": sorted(unreadable), "allowed": sorted(used), "verdict": verdict}


def format_human(findings, summary):
    lines = []
    for f in findings:
        lines += ["HIGH      " + f["title"], "          where: " + f["where"], "          why:   " + f["why"],
                  "          fix:   " + f["fix"], ""]
    lines.append("Files checked: %d, skipped: %d (binary). Compared with %s, runs of %d words or more."
                 % (summary["files_checked"], summary["files_skipped"], TEXT_DIR, summary["words"]))
    if summary["allowed"]:
        lines.append("Let through by %s, each needs the user's OK: %s" % (ALLOW_FILE, "; ".join(summary["allowed"])))
    if summary["verdict"] == "INCOMPLETE":
        missed = "Could not read: " + ", ".join(summary["unreadable"]) if summary["unreadable"] else "No file read."
        lines.append("INCOMPLETE, so not a pass. " + missed)
    elif findings:
        lines.append("FAIL: %d run(s) shared with the original. Rewrite each, then run copycheck.py again."
                     % len(findings))
    else:
        lines.append("PASS: no run of %d or more words is shared with the original." % summary["words"])
    return "\n".join(lines)


def main(argv=None):
    """Check the paths on the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: escapes, no crash
    parser = argparse.ArgumentParser(description="Find runs of words the clone shares with the original.")
    parser.add_argument("paths", nargs="*", default=["."], help="folders or files to check (default: .)")
    parser.add_argument("--words", type=int, default=6, help="the shortest run that counts (default: 6)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        missing = [path for path in args.paths if not os.path.exists(path)]
        if missing:
            raise ValueError("%s does not exist" % ", ".join(missing))
        if not 3 <= args.words <= 50:
            raise ValueError("--words must be a number from 3 to 50")
        findings, summary = check(args.paths, load_original(args.words), args.words, read_allow())
    except (OSError, ValueError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    except RecursionError:
        print("error: the folders are nested too deeply to read", file=sys.stderr)
        return 2
    print(json.dumps({"findings": findings, "summary": summary}, indent=2) if args.json
          else format_human(findings, summary))
    return 2 if summary["verdict"] == "INCOMPLETE" else 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
