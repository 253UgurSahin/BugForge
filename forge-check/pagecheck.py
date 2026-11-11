#!/usr/bin/env python3
"""Check one web page for SEO, accessibility, speed, other hosts, PWA and mixed-content basics, passively.

A URL is loaded once by getpage.py: one passive GET, no redirect followed. No script runs, so a JavaScript
app (SPA) is checked as the HTML the server sends. Each finding's words are in rules.json. Tags are named
by line number with a masked address or plain id, never the page's text. forge:allow does not apply.

Usage:
    python3 pagecheck.py https://example.com/pricing [--json] [--fail-on medium] [--no-pwa]
    python3 pagecheck.py --file saved.html [--url https://example.com/pricing]   (no network)

Exit codes: 0 = nothing at or above --fail-on (default: high); 1 = a finding at or above it; 2 = nothing
checked: a bad address or file, no HTML in it, or getpage.py could not load the page.
"""

import argparse
import collections
import html.parser
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
GETPAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "forge-check", "getpage.py")
MAX_BYTES = 5 * 1024 * 1024  # read at most this much of a saved page
NOT_FIELDS = ("hidden", "submit", "button", "reset", "image")  # input types that need no label
NAMING = ("aria-label", "aria-labelledby", "title")  # attributes that give a tag a name
JS_TYPES = ("", "module", "text/javascript", "application/javascript")  # other types do not run
HEAD_TAGS = {"html", "head", "title", "meta", "link", "script", "style", "base", "template"}
NOSCRIPT = re.compile(r"<noscript\b(?:[^<]|<(?!/?noscript\b))*</noscript\s*>", re.I)
HOST = re.compile(r"\s*(?:https?:)?//(?:[^/?#@]*@)?(\[[0-9a-f:.]+\]|[a-z0-9.-]+)(?=[:/?#]|$)", re.I)
SCHEME = re.compile(r"\s*[a-z][a-z0-9+.-]*:", re.I)  # https:, data:; a relative address has none
PLAIN = re.compile(r"[^\s\"'<>`\\]{1,200}$")  # an id or address fit to print: no spaces or quotes
CSS_URL = re.compile(r"""(@import\s+(?:url\(\s*)?|url\(\s*)["']?\s*([^\s"')]*)""", re.I)  # (how, address)
URL_ATTRS = {"script": ["src"], "link": ["href"], "img": ["src", "srcset"], "source": ["src", "srcset"],
             "audio": ["src"], "video": ["src", "poster"], "track": ["src"], "iframe": ["src"],
             "embed": ["src"], "object": ["data"], "form": ["action"], "base": ["href"]}
BLOCKED = set("script iframe embed object track form base stylesheet preload modulepreload manifest".split())
LOADED = {"stylesheet", "preload", "modulepreload", "manifest", "icon", "apple-touch-icon"}  # rel words
FETCHED = LOADED | {"preconnect", "prefetch"}  # rel words that contact a host on every visit
TRACKS = re.compile(r"(^|\.)(fonts\.googleapis\.com|fonts\.gstatic\.com|typekit\.net|fontawesome\.com|"  # forge:allow
                    r"google-analytics\.com|googletagmanager\.com|doubleclick\.net|facebook\.net|"  # forge:allow
                    r"hotjar\.com|clarity\.ms)$")  # fonts, analytics and ads: names to find, nothing loaded. forge:allow
with open(os.path.join(os.path.dirname(GETPAGE), "rules.json"), encoding="utf-8") as rules_file:
    RULES = json.load(rules_file)  # rule: {"severity", "title", "why", "fix"}
Tag = collections.namedtuple("Tag", "name attrs line in_head in_label")

class Page(html.parser.HTMLParser):
    """Reads a page once. The CSS in a <style> block is kept as that tag's style attribute."""
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags = []  # every start tag, in page order
        self.by_name = collections.defaultdict(list)  # tag name: those tags
        self.meta = {}  # meta name or property: the content of the first one
        self.rels = collections.defaultdict(list)  # rel word, such as canonical: those <link> tags
        self.named = []  # [tag, text pieces] for each link and button
        self.open = []  # the links and buttons we are inside now
        self.title, self.in_head, self.labels = None, True, 0  # labels: how many <label> tags we are inside
        self.collect = None  # "title" or "style" while we read the text of one
        self.feed(NOSCRIPT.sub(lambda block: "\n" * block.group(0).count("\n"), text))  # <noscript>: skip
        self.close()
    def handle_starttag(self, name, attrs):
        attrs = {key: value or "" for key, value in reversed(attrs)}  # like browsers: the first copy counts
        self.in_head = self.in_head and name in HEAD_TAGS  # any other tag ends <head>
        self.tags.append(Tag(name, attrs, self.getpos()[0], self.in_head, self.labels > 0))
        self.by_name[name].append(self.tags[-1])
        for _, pieces in self.open:  # an aria-label, or an image's alt text, names a link
            pieces.append(attrs.get("aria-label", "") + (attrs.get("alt", "") if name == "img" else ""))
        if name == "meta":
            for key in (attrs.get("name", "").lower(), attrs.get("property", "").lower()):
                self.meta.setdefault(key, " ".join(attrs.get("content", "").split()))
        elif name == "link":
            for word in attrs.get("rel", "").lower().split():
                self.rels[word].append(self.tags[-1])
        elif name == "label":
            self.labels += 1
        elif name == "style":
            self.collect = "style"
        elif name == "title" and self.in_head and self.title is None:
            self.collect, self.title = "title", ""
        elif name == "input" and attrs.get("type", "").strip().lower() in ("image", "button"):
            self.named.append([self.tags[-1], [attrs.get(key, "") for key in NAMING + ("alt", "value")]])
        elif name == "button" or (name == "a" and "href" in attrs):
            self.open = [item for item in self.open if item[0].name != name]  # a new <a> ends an <a>
            self.named.append([self.tags[-1], [attrs.get(key, "") for key in NAMING]])
            self.open.append(self.named[-1])
    handle_startendtag = handle_starttag  # like browsers: the slash in <a href="/x" /> means nothing
    def handle_endtag(self, name):
        self.in_head = self.in_head and name != "head"
        self.collect = None if name == self.collect else self.collect
        if name == "label" and self.labels:
            self.labels -= 1
        if self.open and self.open[-1][0].name == name:  # the innermost link or button ends
            self.open.pop()
    def handle_data(self, data):
        if self.collect == "title":
            self.title += data
        elif self.collect == "style":  # no tag starts inside <style>, so the last tag is the <style>
            self.tags[-1].attrs["style"] = self.tags[-1].attrs.get("style", "") + data
        for _, pieces in self.open:
            pieces.append(data)

def hit(rule, where, severity=None):  # one finding for a rule in rules.json
    return dict(RULES[rule], severity=severity or RULES[rule]["severity"], where=where)

def show(text, limit=80):  # outside text made safe to print: no control characters, not too long
    text = "".join(ch if ch.isprintable() else "?" for ch in str(text))
    return text if len(text) <= limit else text[:limit] + "..."

def safe_url(url):  # an address fit to print: user:password, ;jsessionid=, ?query and #part become ****
    url = re.sub(r"//[^/?#]*@", "//****@", url, count=1)
    return show(re.sub(r"([;?#]).*", r"\1****", url, count=1, flags=re.S))

def describe(tag):  # 'line 12 <img src="/logo.png">': a value with spaces or quotes is page text, left out
    for key in ("src", "href", "action", "data", "id", "name"):
        value = tag.attrs.get(key, "").strip()
        if PLAIN.match(value):
            return 'line %d <%s %s="%s">' % (tag.line, tag.name, key, show(safe_url(value), 60))
    return "line %d <%s>" % (tag.line, tag.name)

def examples(tags, first=3):  # how many tags break a rule, and the first few
    more = " and %d more" % (len(tags) - first) if len(tags) > first else ""
    return "%d found: %s%s" % (len(tags), "; ".join(describe(tag) for tag in tags[:first]), more)

def is_script_file(tag):  # a <script src> that browsers run, not JSON data or a script held for consent
    return (tag.name == "script" and bool(tag.attrs.get("src", "").strip())
            and tag.attrs.get("type", "").strip().lower() in JS_TYPES)

def addresses(tag, rels=LOADED):  # what a tag loads; a <link> only with one of these rel words
    loads = tag.name != "link" or set(tag.attrs.get("rel", "").lower().split()) & rels  # not rel="canonical"
    image_input = tag.name == "input" and tag.attrs.get("type", "").strip().lower() == "image"
    keys = ["src"] if image_input else URL_ATTRS.get(tag.name, []) if loads else []
    found = [tag.attrs.get(key, "").strip() for key in keys if key != "srcset"]
    if "srcset" in keys:  # several: "a.png 1x, b.png 2x"
        found += [part.split()[0] for part in tag.attrs.get("srcset", "").split(",") if part.strip()]
    return [address for address in found if address]

def other_hosts(page, url):  # hosts files load from that are not the page's own, its www. twin or subdomains
    own = re.sub(r"^www\.", "", (urllib.parse.urlsplit(url or "").hostname or "").lower())
    loaded = [tag for tag in page.tags if tag.name not in ("form", "base", "script") or is_script_file(tag)]
    found = [address for tag in loaded for address in addresses(tag, FETCHED)]
    found += [address for tag in page.tags for _, address in CSS_URL.findall(tag.attrs.get("style", ""))]
    hosts = {start.group(1).lower() for start in map(HOST.match, found) if start}  # none: relative, or no real host
    return sorted(host for host in hosts if not (own and (host.strip("[]") == own or host.endswith("." + own))))

def page_rules(page, url, size, pwa):  # findings about the page as a whole: head tags, weight, other hosts
    title, description = " ".join((page.title or "").split()), page.meta.get("description", "")
    h1s = page.by_name["h1"]
    noindex = [tag for tag in page.by_name["meta"] if tag.attrs.get("name", "").lower() in ("robots", "googlebot")
               and {"noindex", "none"} & set(re.split(r"[\s,]+", tag.attrs.get("content", "").lower()))]
    icons = page.rels["apple-touch-icon"] + page.rels["apple-touch-icon-precomposed"]
    no_share = [name for name, there in [("canonical link", page.rels["canonical"]),
                ("og:title", page.meta.get("og:title")), ("og:image", page.meta.get("og:image"))] if not there]
    no_app = [name for name, there in [("manifest link", page.rels["manifest"]),
              ("theme-color", page.meta.get("theme-color")), ("apple-touch-icon", icons)] if not there]
    scripts, styles, images = list(filter(is_script_file, page.tags)), page.rels["stylesheet"], page.by_name["img"]
    weight = "HTML: %d KB, script files: %d, stylesheets: %d" % (size // 1024, len(scripts), len(styles))
    lazy = any(tag.attrs.get("loading", "").lower() == "lazy" for tag in images)
    hosts = other_hosts(page, url)
    rows = [  # (rule, broken: True or False, where, severity: None for the rule's own)
        ("title", not 10 <= len(title) <= 60, "title length: %d" % len(title) if title else "no <title>",
         None if title else "medium"),
        ("description", not 50 <= len(description) <= 160, "description length: %d" % len(description), None),
        ("one_h1", len(h1s) != 1, examples(h1s) if h1s else "no <h1>", None if h1s else "medium"),
        ("no_lang", not any(tag.attrs.get("lang", "").strip() for tag in page.by_name["html"][:1]), "<html>", None),
        ("no_viewport", not page.meta.get("viewport"), "<head>", None),
        ("noindex", bool(noindex), describe(noindex[0]) if noindex else "", None),
        ("share_tags", bool(no_share), "missing: " + ", ".join(no_share), None),
        ("pwa", pwa and bool(no_app), "missing: " + ", ".join(no_app), None),
        ("heavy", size > 500 * 1024 or len(scripts) > 20 or len(styles) > 8, weight, None),
        ("no_lazy", len(images) > 10 and not lazy, "images: %d, none with loading=lazy" % len(images), None),
        ("other_hosts", bool(hosts), show("hosts: " + ", ".join(hosts), 300),
         "medium" if any(map(TRACKS.search, hosts)) else None),  # fonts and analytics: medium
    ]
    return [hit(rule, where, severity) for rule, broken, where, severity in rows if broken]

def mixed_rule(tag, base_http):  # the mixed-content rule a tag breaks: http://, or relative under an http <base>
    blocked = tag.name in BLOCKED or set(tag.attrs.get("rel", "").lower().split()) & BLOCKED
    for address in addresses(tag):
        if address.lower().startswith("http://") or (base_http and not SCHEME.match(address)):
            return "mixed_blocked" if blocked else "mixed_media"
    for how, address in CSS_URL.findall(tag.attrs.get("style", "")):  # @import: a stylesheet; url(): image, font
        if address.lower().startswith("http://"):
            return "mixed_blocked" if how.startswith("@") else "mixed_media"

def tag_rules(tag, label_for, https, base_http):  # the rules one tag breaks, judged on its own
    attrs = tag.attrs
    type_attr = attrs.get("type", "").strip().lower()
    decoration = attrs.get("aria-hidden") == "true" or attrs.get("role", "").lower() in ("presentation", "none")
    if tag.name == "img" and "alt" not in attrs and not decoration:
        yield "img_alt"
    if tag.name == "img" and not (attrs.get("width", "").strip() and attrs.get("height", "").strip()):
        yield "no_size"
    if (tag.name in ("input", "select", "textarea") and type_attr not in NOT_FIELDS and not tag.in_label
            and attrs.get("id") not in label_for and not any(attrs.get(key, "").strip() for key in NAMING)):
        yield "no_label"  # a placeholder is not a label
    if re.match(r"\s*\+?0*[1-9]", attrs.get("tabindex", "")):  # 1 or more
        yield "tabindex"
    held_back = {"defer", "async", "nomodule"} & set(attrs)  # browsers that run modules skip nomodule
    if is_script_file(tag) and tag.in_head and type_attr != "module" and not held_back:
        yield "blocking"
    if https and mixed_rule(tag, base_http):
        yield mixed_rule(tag, base_http)

def check(page, url=None, size=0, pwa=True):
    """All findings for a parsed page, most severe first. Without a url, https is assumed."""
    https = urllib.parse.urlsplit(url or "").scheme != "http"
    label_for = {tag.attrs.get("for", "") for tag in page.by_name["label"]} - {""}  # worked out once
    bases = [tag.attrs["href"] for tag in page.by_name["base"] if tag.attrs.get("href", "").strip()]
    base_http = bool(bases) and bases[0].strip().lower().startswith("http://")  # the first one counts
    broken = collections.defaultdict(list)  # rule: the tags that break it
    for tag in page.tags:
        for rule in tag_rules(tag, label_for, https, base_http):
            broken[rule].append(tag)
    broken["no_name"] = [tag for tag, pieces in page.named if not "".join(pieces).strip()]
    levels = [(int(tag.name[1]), tag) for tag in page.tags if re.match(r"h[1-6]$", tag.name)]
    broken["heading_skip"] = [tag for (before, _), (level, tag) in zip(levels, levels[1:]) if level > before + 1]
    found = page_rules(page, url, size, pwa) + [hit(rule, examples(tags)) for rule, tags in broken.items() if tags]
    return sorted(found, key=lambda finding: SEVERITIES.index(finding["severity"]))

def read_page(data):  # the parsed page; ValueError when the bytes hold no HTML (empty, plain text, binary)
    utf16 = data.startswith((b"\xff\xfe", b"\xfe\xff"))  # a byte order mark: saved as UTF-16 (Windows)
    if b"\0" in data[:8192] and not utf16:
        raise ValueError("it is not a text file (an image or other binary file?)")
    page = Page(data.decode("utf-16" if utf16 else "utf-8-sig", errors="replace"))  # Latin-1 tags read too
    if not page.tags:
        raise ValueError("there is no HTML in it (empty, or plain text?)")
    return page

def load(url, path=None):
    """(status, bytes, cut) of a saved file, or of url loaded once by getpage.py into a temporary folder."""
    if path:
        with open(path, "rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        return None, data[:MAX_BYTES], len(data) > MAX_BYTES
    with tempfile.TemporaryDirectory() as folder:
        saved = os.path.join(folder, "page.html")
        done = subprocess.run([sys.executable, GETPAGE, url, saved, "--json"], capture_output=True,
                              text=True, errors="replace", timeout=60)
        answer = json.loads(done.stdout) if done.stdout.startswith("{") else {}
        if not answer.get("saved"):
            raise ValueError(answer.get("error") or "getpage.py failed: " + show(done.stderr[-200:], 200))
        with open(saved, "rb") as handle:
            return answer["status"], handle.read(), answer["cut"]

def format_human(findings, summary, intro):  # the intro, one block per finding, then a one-line summary
    lines = [intro, ""]
    for f in findings:
        lines.append("%-8s  %s\n          where: %s\n          why:   %s\n          fix:   %s\n"
                     % (f["severity"].upper(), f["title"], f["where"], f["why"], f["fix"]))
    counts = ", ".join("%d %s" % (summary[sev], sev) for sev in SEVERITIES if summary[sev])
    noun = "finding" if len(findings) == 1 else "findings"
    lines.append("%d %s: %s." % (len(findings), noun, counts) if findings else "No findings.")
    return "\n".join(lines)

def main(argv=None):
    """Read the command line, read or load the page, print the report and return the exit code."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: escapes, no crash
    parser = argparse.ArgumentParser(description="Passive check of one web page (SEO, accessibility, speed).")
    parser.add_argument("url", nargs="?", help="http:// or https:// address of the page to load once")
    parser.add_argument("--file", help="check a saved HTML file instead (no network)")
    parser.add_argument("--url", dest="file_url", metavar="URL", help="with --file: the page's address")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high", help="exit 1 at this or a worse one")
    parser.add_argument("--no-pwa", action="store_true", help="skip the PWA tags (plan.md says PWA: no)")
    args = parser.parse_args(argv)
    if bool(args.url) == bool(args.file) or (args.url and args.file_url):  # one or the other
        parser.error("give one URL to load, or --file SAVED_HTML with an optional --url")
    url = args.url or args.file_url  # None for --file without --url
    source = show(args.file) if args.file else safe_url(url)
    try:
        if args.file and url and (urllib.parse.urlsplit(url).scheme not in ("http", "https") or "@" in url):
            raise ValueError("--url takes a plain http:// or https:// address, like https://example.com")
        status, data, cut = load(url, args.file)
        page = read_page(data)
    except (OSError, ValueError, AssertionError, NotImplementedError, subprocess.SubprocessError) as error:
        reason = error.strerror if isinstance(error, OSError) and error.strerror else error
        if isinstance(error, (AssertionError, NotImplementedError)):  # how older 3.9 parsers give up
            reason = "its HTML is too broken to read"
        elif isinstance(error, subprocess.SubprocessError):  # its text holds the command, with the URL
            reason = "getpage.py did not finish in time"
        print("error: could not check %s: %s" % (source, show(reason, 300)), file=sys.stderr)
        return 2
    findings = check(page, url, len(data), pwa=not args.no_pwa)
    failed = any(SEVERITIES.index(f["severity"]) <= SEVERITIES.index(args.fail_on) for f in findings)
    summary = {sev: sum(f["severity"] == sev for f in findings) for sev in SEVERITIES}
    summary.update(total=len(findings), url=url and safe_url(url), status=status, bytes=len(data), cut=cut,
                   fail_on=args.fail_on, failed=failed)
    where = "%s (%s)" % (source, summary["url"] or "https assumed") if args.file else source
    intro = "Checked %s: %.1f KB%s." % (where, len(data) / 1024.0, ", only the first 5 MB read" if cut else "")
    print(json.dumps({"findings": findings, "summary": summary}, indent=2) if args.json
          else format_human(findings, summary, intro))
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
