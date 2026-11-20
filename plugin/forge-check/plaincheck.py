#!/usr/bin/env python3
"""Check pages for the plain rules a person sees without help: clear button words, an icon with a word,
a visible label on every field, no jargon or programming values on screen, short forms and menus.

The rules are those of ../forge-design/plain.md that a page's HTML shows by itself; the words to look for
are in plain.json next to this script (English and Dutch). A URL is loaded once by getpage.py: one
passive GET, no script runs, so a JavaScript app (SPA) is checked as the HTML the server sends; save the
rendered page (the walk's shots script, or the browser's "save as") and pass the file for what it shows.
Tags are named by line number; only the words from plain.json are quoted, never other page text.

Usage:
    python3 plaincheck.py PAGE [PAGE ...] [--json] [--fail-on medium]
    PAGE: a saved .html file, or an http:// or https:// address (http://localhost:3000/book)

Exit codes: 0 = nothing at or above --fail-on (default: high); 1 = a finding at or above it; 2 = a PAGE
could not be read or loaded, holds no HTML, or plain.json is broken. Exit 2 is never a pass.
"""

import argparse
import html.parser
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GETPAGE = os.path.join(HERE, "getpage.py")
SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
MAX_BYTES = 5 * 1024 * 1024  # read at most this much of a saved page
VOID = set("area base br col embed hr img input link meta source track wbr".split())  # tags that never close
UNSEEN_TAGS = {"script", "style", "template", "noscript", "head", "title"}
UNSEEN_CLASS = re.compile(r"(^|\s)(sr-only|visually-hidden|screen-reader-text|visuallyhidden)(\s|$)")
NOT_FIELDS = ("hidden", "submit", "button", "reset", "image", "search")  # inputs that need no label of their own
TRIM = " \t\r\n.:!?…→←>»«<-–—·•* "


def load_rules():
    with open(os.path.join(HERE, "plain.json"), encoding="utf-8") as handle:
        data = json.load(handle)
    for key in ("rules", "vague", "jargon", "leaks", "steps", "long_form", "long_menu"):
        if key not in data:
            raise ValueError("plain.json has no %r" % key)
    data["steps"] = re.compile(data["steps"], re.I)
    data["jargon_re"] = words_pattern(data["jargon"])
    data["leaks_re"] = words_pattern(data["leaks"], 0)  # exact case: "NaN" and "null", not "Nan" or "Null"
    return data


def words_pattern(words, flags=re.I):  # whole words or phrases; "[object Object]" too
    return re.compile(r"(?<![\w\[])(%s)(?![\w\]])" % "|".join(
        re.escape(word) for word in sorted(words, key=len, reverse=True)), flags)


class Page(html.parser.HTMLParser):
    """Reads a page once: its controls, fields, forms, menus and visible text."""
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.stack = []  # [name, hidden] of the open tags
        self.controls, self.open = [], []  # each control: {"tag", "line", "text", "content"}
        self.fields, self.labelled, self.labels = [], set(), 0  # labelled: ids named by <label for>
        self.forms, self.navs = [], []  # each: {"line", "fields"} / {"line", "links"}
        self.text, self.has_steps, self.tags = [], False, 0
        self.feed(text)
        self.close()

    def hidden(self):
        return bool(self.stack) and self.stack[-1][1]

    def handle_starttag(self, name, attrs):
        attrs = {key: value or "" for key, value in reversed(attrs)}
        self.tags += 1
        line, hidden = self.getpos()[0], self.hidden()
        hidden = hidden or name in UNSEEN_TAGS or "hidden" in attrs or attrs.get("aria-hidden") == "true" \
            or bool(UNSEEN_CLASS.search(attrs.get("class", ""))) \
            or bool(re.search(r"display\s*:\s*none", attrs.get("style", ""), re.I))
        for control in self.open:
            control["content"] = True  # an icon, an image or a span inside
        if name == "label":
            self.labels += 1
            self.labelled.add(attrs.get("for", ""))
        elif name in ("button", "a") and (name == "button" or "href" in attrs) and not hidden:
            self.open = [item for item in self.open if item["tag"] != name]  # a new <a> ends an <a>
            self.controls.append({"tag": name, "line": line, "text": [], "content": False})
            self.open.append(self.controls[-1])
        elif name in ("input", "select", "textarea") and not hidden:
            kind = attrs.get("type", "").strip().lower() if name == "input" else name
            if kind in ("submit", "button", "reset"):
                self.controls.append({"tag": "input", "line": line, "text": [attrs.get("value", "")], "content": False})
            elif kind == "image":
                self.controls.append({"tag": "input", "line": line, "text": [], "content": True})
            elif kind not in NOT_FIELDS:
                self.fields.append({"line": line, "id": attrs.get("id", ""), "inside": self.labels > 0,
                                    "box": kind not in ("checkbox", "radio")})
                for form in self.forms[-1:]:
                    form["fields"] += 1
        elif name == "form":
            self.forms.append({"line": line, "fields": 0})
        elif name == "nav" and not hidden:
            self.navs.append({"line": line, "links": 0})
        elif name in ("progress",) or attrs.get("aria-current") == "step":
            self.has_steps = True
        if name == "a" and "href" in attrs and not hidden:
            for nav in self.navs:
                if nav.get("open", True):
                    nav["links"] += 1
        if name not in VOID:
            self.stack.append([name, hidden])

    def handle_startendtag(self, name, attrs):  # <br/>, <img/>: never opened
        self.handle_starttag(name, attrs)
        if name not in VOID and self.stack and self.stack[-1][0] == name:
            self.stack.pop()

    def handle_endtag(self, name):
        if name == "label" and self.labels:
            self.labels -= 1
        if name == "nav":
            for nav in reversed(self.navs):
                if nav.get("open", True):
                    nav["open"] = False
                    break
        self.open = [item for item in self.open if item["tag"] != name]
        for index in range(len(self.stack) - 1, -1, -1):  # close up to the matching tag, if it is open
            if self.stack[index][0] == name:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.hidden():
            return
        self.text.append(data)
        for control in self.open:
            control["text"].append(data)


def plain(text):  # a label as people read it: one space, no trailing arrows or dots, lower case
    return " ".join(text.split()).strip(TRIM).lower()


def where(lines, tag):
    shown = ", ".join("line %d" % line for line in lines[:3])
    more = " and %d more" % (len(lines) - 3) if len(lines) > 3 else ""
    return "%d %s: %s%s" % (len(lines), tag, shown, more)


def check(page, rules):
    """The findings for one parsed page, most severe first."""
    found = []

    def add(rule, text):
        found.append(dict(rules["rules"][rule], rule=rule, where=text))

    vague = {}  # the word: the lines it is on
    icons = []
    for control in page.controls:
        label = plain("".join(control["text"]))
        if label and label in rules["vague"]:
            vague.setdefault(label, []).append(control["line"])
        elif not label and control["content"]:
            icons.append(control["line"])
    if vague:
        add("vague_label", "; ".join('"%s" on %s' % (word, ", ".join("line %d" % line for line in lines[:3]))
                                     for word, lines in sorted(vague.items())))
    if icons:
        add("icon_only", where(icons, "control(s) with an icon and no word"))
    unlabelled = [field["line"] for field in page.fields if not field["inside"]
                  and not (field["id"] and field["id"] in page.labelled)]
    if unlabelled:
        add("placeholder_label", where(unlabelled, "field(s) with no <label>"))
    text = " ".join(" ".join(page.text).split())
    jargon = sorted({hit.lower() for hit in rules["jargon_re"].findall(text)})
    if jargon:
        add("jargon", "words: " + ", ".join('"%s"' % word for word in jargon[:8]))
    leaks = sorted(set(rules["leaks_re"].findall(text)))
    if leaks:
        add("leak", "on screen: " + ", ".join('"%s"' % word for word in leaks))
    steps = page.has_steps or bool(rules["steps"].search(text))
    for form in page.forms:
        if form["fields"] > rules["long_form"] and not steps:
            add("long_form", "the form on line %d has %d fields and no \"Stap 1 van 3\"" % (form["line"], form["fields"]))
    for nav in page.navs:
        if nav["links"] > rules["long_menu"]:
            add("long_menu", "the menu on line %d has %d links" % (nav["line"], nav["links"]))
    return sorted(found, key=lambda finding: SEVERITIES.index(finding["severity"]))


def read_page(source):
    """The page's text from a saved file, or from a URL loaded once by getpage.py. ValueError: none."""
    if re.match(r"https?://", source, re.I):
        if "@" in source.split("/")[2]:
            raise ValueError("remove the username and password from the address")
        with tempfile.TemporaryDirectory() as folder:
            saved = os.path.join(folder, "page.html")
            done = subprocess.run([sys.executable, GETPAGE, source, saved, "--json"], capture_output=True,
                                  text=True, errors="replace", timeout=60)
            answer = json.loads(done.stdout) if done.stdout.startswith("{") else {}
            if not answer.get("saved"):
                raise ValueError(answer.get("error") or "getpage.py could not load it")
            with open(saved, "rb") as handle:
                data = handle.read(MAX_BYTES)
    else:
        with open(source, "rb") as handle:
            data = handle.read(MAX_BYTES)
    utf16 = data.startswith((b"\xff\xfe", b"\xfe\xff"))
    if b"\0" in data[:8192] and not utf16:
        raise ValueError("it is not a text file")
    page = Page(data.decode("utf-16" if utf16 else "utf-8-sig", errors="replace"))
    if not page.tags:
        raise ValueError("there is no HTML in it")
    return page


def show(text, limit=120):  # outside text made safe to print
    text = "".join(ch if ch.isprintable() else "?" for ch in str(text))
    return text if len(text) <= limit else text[:limit] + "..."


def main(argv=None):
    """Read the command line, check each page, print the report and return the exit code."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: no crash
    parser = argparse.ArgumentParser(description="Check pages for the plain rules of forge-design/plain.md.")
    parser.add_argument("pages", nargs="+", metavar="PAGE", help="a saved .html file or an http(s):// address")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high", help="exit 1 at this or a worse one")
    args = parser.parse_args(argv)
    try:
        rules = load_rules()
    except (OSError, ValueError, re.error) as error:
        print("error: plain.json: %s" % show(error), file=sys.stderr)
        return 2
    results, broken = [], False
    for source in args.pages:
        try:
            findings = check(read_page(source), rules)
        except (OSError, ValueError, AssertionError, NotImplementedError, subprocess.SubprocessError) as error:
            reason = error.strerror if isinstance(error, OSError) and error.strerror else error
            print("error: could not check %s: %s" % (show(source), show(reason, 300)), file=sys.stderr)
            broken = True
            continue
        results.append({"page": show(source, 300), "findings": findings})
    every = [finding for result in results for finding in result["findings"]]
    limit = SEVERITIES.index(args.fail_on)
    failed = any(SEVERITIES.index(finding["severity"]) <= limit for finding in every)
    summary = {sev: sum(finding["severity"] == sev for finding in every) for sev in SEVERITIES}
    summary.update(pages=len(results), unreadable=len(args.pages) - len(results), fail_on=args.fail_on,
                   failed=failed)
    if args.json:
        print(json.dumps({"pages": results, "summary": summary}, indent=2))
    else:
        for result in results:
            print("%s: %s" % (result["page"], "%d finding(s)" % len(result["findings"])
                              if result["findings"] else "clear for everyone"))
            for f in result["findings"]:
                print("  %-7s %s\n          where: %s\n          why:   %s\n          fix:   %s"
                      % (f["severity"].upper(), f["title"], show(f["where"], 200), f["why"], f["fix"]))
        print("%d page(s) checked, %d finding(s)." % (len(results), len(every)))
    return 2 if broken else 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
