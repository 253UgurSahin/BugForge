#!/usr/bin/env python3
"""Rank what users of competing apps hate and ask for, from real reviews you collected.

Sorts the rows of forge-work/reviews.csv (source,url,date,rating,text) into the themes in
themes.json next to this script and writes a plain report. It never writes or rewords a review:
each quote is a piece of a row you supplied, with its link. load_reviews and analyse say how.

Usage:
    python3 reviews.py forge-work/reviews.csv --out forge-work/feedback.md
    python3 reviews.py forge-work/reviews.csv --json --today 2026-10-27 --themes /tmp/themes.json

Exit codes: 0 report made; 2 bad input (a missing, unreadable or broken file, no url or text
column, no usable rows, a themes file that is not valid, a bad --today or --months).
"""

import argparse
import csv
import datetime
import io
import json
import os
import re
import sys
import unicodedata

THEMES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes.json")
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")
SMALL_SAMPLE = 30  # under this many reviews, a ranking is a direction at best
PRAISE = 5  # a review with this many stars is praise: it counts toward no theme
STRAIGHT = str.maketrans("\U00002018\U00002019\U000002bc", "'''")  # curly apostrophes, one for one
# Hidden besides categories Cc and Cf: blanks, and variation selectors but one U+FE0E or U+FE0F.
HIDDEN = re.compile("[\U0000034f\U0000115f\U00001160\U00002800\U00003164\U0000ffa0]|[\U0000fe00-"
                    "\U0000fe0f\U000e0100-\U000e01ef]{2,}|[\U0000fe00-\U0000fe0d\U000e0100-\U000e01ef]")
MARKUP = str.maketrans({"\\": "\\\\", "&": "&amp;", "<": "&lt;", "[": "\\[", "]": "\\]"})
URL_MARKUP = re.compile(r'[<>\[\]"`\\]|&(?=#?\w+;)')  # percent-encoded in a link
LEGEND = ("score: a review adds 1.0 at 1 star down to 0.4 at 4 (0.6 without stars), half when older "
          "than %d months; 5 stars is praise, not counted. thin: under 3 reviews or one site only.")

class ReviewsError(Exception):
    """The reviews or the themes file cannot be used as they are."""

def read_text(path):
    """The text of a UTF-8 file (a byte order mark is fine), or an error that names the file."""
    if not os.path.isfile(path):
        raise ReviewsError("%s is not a file that exists" % path)
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            return handle.read()
    except UnicodeDecodeError:
        raise ReviewsError("%s is not UTF-8 text: save it as UTF-8 (Excel: CSV UTF-8)" % path)

def compile_all(patterns, where):
    """Compiled, case-insensitive patterns from a list of strings."""
    if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
        raise ReviewsError("%s must be a list of strings" % where)
    try:
        return [re.compile(p, re.IGNORECASE) for p in patterns]
    except re.error as error:
        raise ReviewsError("%s: %r is not a valid pattern: %s" % (where, error.pattern, error))

def load_themes(path=THEMES_FILE):
    """(themes, request patterns) from a themes file. Each theme: id, label, kind, patterns."""
    try:
        data = json.loads(read_text(path))
    except ValueError as error:
        raise ReviewsError("%s is not valid JSON: %s" % (path, error))
    if not isinstance(data, dict) or not isinstance(data.get("themes"), list):
        raise ReviewsError('%s needs a "themes" list' % path)
    themes = []
    for number, theme in enumerate(data["themes"], 1):
        theme = theme if isinstance(theme, dict) else {}
        name, kind, label = theme.get("id"), theme.get("kind", "complaint"), theme.get("label")
        if (not isinstance(name, str) or not name or name in [t["id"] for t in themes]
                or kind not in ("complaint", "request") or not isinstance(label or "", str)):
            raise ReviewsError("%s: theme %d needs its own id, kind complaint or request, and a "
                               "label, each as text" % (path, number))
        patterns = compile_all(theme.get("patterns"), "%s: theme %s: patterns" % (path, name))
        themes.append({"id": name, "label": label or name, "kind": kind, "patterns": patterns})
    return themes, compile_all(data.get("request_patterns", []), "%s: request_patterns" % path)

def parse_date(text):
    """A date from YYYY-MM-DD (a time after it is fine) or YYYY-MM (the 1st), else None."""
    match = re.match(r"(\d{4})-(\d\d)(?:-(\d\d))?(?:[T ]\S*)?$", (text or "").strip())
    try:
        return datetime.date(*(int(part or 1) for part in match.groups())) if match else None
    except ValueError:  # a day that does not exist, such as 2026-02-30
        return None

def parse_rating(text):
    """Stars 1 to 5 ("4,5", "4/5", "★★★★☆"); a score out of 10 is halved. Else None."""
    text = (text or "").strip()
    match = re.match(r"(\d+(?:[.,]\d+)?)\s*(?:(?:/|out of)\s*(\d+))?", text, re.IGNORECASE)
    value = float(match.group(1).replace(",", ".")) if match else float(text.count("★"))
    scale = match.group(2) if match else None
    if scale not in (None, "5"):  # a score out of 10 is halved; another scale is not read
        value = max(1.0, value / 2) if scale == "10" and value <= 10 else 0
    return value if 1 <= value <= 5 else None

def site(url):
    """The site of a link, to count sources by: nl.trustpilot.com is trustpilot.com."""
    host = re.match(r"(?:https?://)?(?:[^/?#@]*@)?([\w.-]*)", url, re.IGNORECASE).group(1)
    parts = host.lower().strip(".").split(".")
    country = len(parts) > 2 and len(parts[-1]) == 2 and parts[-2] in ("co", "com", "org", "ac")
    return ".".join(parts[-3:] if country else parts[-2:]) or "unknown"  # trustpilot.co.uk

def load_reviews(path):
    """(reviews, notes) from a UTF-8 CSV with commas, a header with url and text, text last (so a
    comma in unquoted text shows as an extra field). Rows without a link or text, or with too many
    fields, are not counted; an unreadable date or rating counts as blank; a repeated text counts
    once. Notes read "line N: what", N the row's first line. An unclosed quote stops the run."""
    reader = csv.reader(io.StringIO(read_text(path), newline=""), strict=True)
    rows, line = [], 0
    try:
        for cells in reader:
            if any(cell.strip() for cell in cells):
                rows.append((line + 1, [cell.strip() for cell in cells]))
            line = reader.line_num
    except csv.Error as error:  # strict: else the rows below an unclosed quote are glued to it
        raise ReviewsError('%s line %d: %s. Text in double quotes must end with one, and a double '
                           'quote inside it is written twice ("")' % (path, line + 1, error))
    header = [name.lower() for name in rows[0][1]] if rows else []
    if "url" not in header or header[-1:] != ["text"]:
        raise ReviewsError("%s needs the header source,url,date,rating,text (commas, text last)" % path)
    kept, notes, seen = [], [], {}
    for line, cells in rows[1:]:
        row = dict(zip(header, cells))
        url, text = row.get("url", ""), row.get("text", "")
        words = re.findall(r"\w+", text.translate(STRAIGHT).lower())
        key = (url if len(words) < 5 else "", " ".join(words))  # a short text: once per link
        if len(cells) > len(header):
            notes.append("line %d: too many fields (quote a text with commas), not counted" % line)
        elif not re.match(r"https?://\S+$", url, re.IGNORECASE):
            notes.append("line %d: no http or https link, not counted" % line)
        elif not text:
            notes.append("line %d: no text, not counted" % line)
        elif key in seen:
            notes.append("line %d: same text as line %d, counted once" % (line, seen[key]))
        else:
            seen[key] = line
            label = re.sub(r"[\s_]+", "-", row.get("source", "").lower())
            kept.append({"source": label or site(url), "url": url, "text": text,
                         "date": parse_date(row.get("date")), "rating": parse_rating(row.get("rating"))})
            if row.get("date") and kept[-1]["date"] is None:
                notes.append("line %d: date is not YYYY-MM-DD, counted as undated" % line)
            if row.get("rating") and kept[-1]["rating"] is None:
                notes.append("line %d: rating is not 1 to 5 stars or out of 10, counted as none" % line)
    return kept, notes

def weight(review, today, months):
    """How much one review counts: low stars more, old reviews half."""
    stars, date = review["rating"], review["date"]
    value = 0.6 if stars is None else (6.0 - stars) / 5.0
    return value / 2 if date and today and (today - date).days > months * 30.4 else value

def snippet(text, pattern=None, limit=220):
    """The first sentence that matches pattern, verbatim, cut around the match; else the start."""
    for sentence in SENTENCE_BREAK.split(text) if pattern else []:
        part = sentence.strip()
        match = pattern.search(part.translate(STRAIGHT))
        if match and len(part) > limit:
            start = max(0, match.start() - limit // 2)
            return ("..." if start > 0 else "") + part[start:start + limit].strip() + "..."
        if match:
            return part
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "..."

def quote(review, text):
    """One quote with where it came from."""
    return {"quote": text, "url": review["url"], "source": review["source"], "rating": review["rating"]}

def summarise(theme, items, total, today, months):
    """One ranked theme from its (review, quote) pairs; quotes with the fewest stars first."""
    stars = [review["rating"] for review, _ in items if review["rating"] is not None]
    sites = sorted({site(review["url"]) for review, _ in items})
    items.sort(key=lambda item: (3 if item[0]["rating"] is None else item[0]["rating"], len(item[1])))
    return {"id": theme["id"], "label": theme["label"], "kind": theme["kind"],
            "score": round(sum(weight(review, today, months) for review, _ in items), 2),
            "count": len(items), "share_pct": round(100.0 * len(items) / max(total, 1), 1),
            "avg_rating": round(sum(stars) / len(stars), 2) if stars else None,
            "sources": sites, "thin": len(items) < 3 or len(sites) < 2,
            "quotes": [quote(review, text) for review, text in items[:3]]}

def analyse(reviews, themes, request_patterns, today=None, months=18):
    """Score each theme (5-star praise counts toward none), collect wishes and unthemed lows."""
    today = today or datetime.date.today()
    found, requests, unthemed = {theme["id"]: [] for theme in themes}, [], []
    for review in reviews:
        text, stars, matched = review["text"], review["rating"], False
        folded = text.translate(STRAIGHT)
        for theme in themes if stars is None or stars < PRAISE else []:
            pattern = next((p for p in theme["patterns"] if p.search(folded)), None)
            if pattern is not None:
                matched = True
                found[theme["id"]].append((review, snippet(text, pattern)))
        wish = next((p for p in request_patterns if p.search(folded)), None)
        if wish is not None:
            requests.append(quote(review, snippet(text, wish)))
        if not matched and stars is not None and stars <= 2:
            unthemed.append(quote(review, snippet(text)))
    ranked = [summarise(theme, found[theme["id"]], len(reviews), today, months)
              for theme in themes if found[theme["id"]]]
    ranked.sort(key=lambda theme: (-theme["score"], -theme["count"], theme["id"]))
    return {"reviews": len(reviews), "sources": sorted({site(r["url"]) for r in reviews}),
            "rated": sum(1 for r in reviews if r["rating"] is not None), "today": today.isoformat(),
            "months": months, "themes": ranked, "requests": requests, "unthemed_negative": unthemed}

def one_line(text, markup=MARKUP):
    """Text for the report: one line, markup shown as text, hidden characters as <U+XXXX>."""
    text = " ".join(text.split()).translate(markup)
    text = HIDDEN.sub(lambda match: "".join("<U+%04X>" % ord(c) for c in match.group()), text)
    return "".join("<U+%04X>" % ord(c) if unicodedata.category(c) in ("Cc", "Cf")
                   and c != "\N{ZERO WIDTH JOINER}" else c for c in text)

def plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")

def quotes(items):
    """Markdown quote blocks: the words, where from, and the link with markup percent-encoded."""
    lines = []
    for item in items:
        rating, url = item["rating"], URL_MARKUP.sub(lambda m: "%%%02X" % ord(m.group()), item["url"])
        stars = "no stars" if rating is None else "%g star%s" % (rating, "" if rating == 1 else "s")
        lines += ["", '> "%s" (%s, %s) %s' % (one_line(item["quote"]), one_line(item["source"]),
                                              stars, one_line(url, {}))]
    return lines

def theme_table(rows, months):
    """The ranking table of one kind of theme, and what score and thin mean."""
    lines = ["| rank | theme | score | reviews | share | avg stars | sources |", "|---" * 7 + "|"]
    for rank, t in enumerate(rows, 1):
        stars = "-" if t["avg_rating"] is None else "%.1f" % t["avg_rating"]
        label = t["label"] + (" (thin)" if t["thin"] else "")
        lines.append("| %d | %s | %.1f | %d | %.0f%% | %s | %d |" % (
            rank, label, t["score"], t["count"], t["share_pct"], stars, len(t["sources"])))
    return lines + ["", LEGEND % months] if rows else ["No theme matched."]

def render(result):
    """The markdown report for forge-work/feedback.md."""
    sources = ", ".join(one_line(s) for s in result["sources"])
    out = ["# What users hate and ask for", "", "Sample: %s from %s (%s), %d with stars. Made on %s."
           % (plural(result["reviews"], "review"), plural(len(result["sources"]), "source"), sources,
              result["rated"], result["today"])]
    notes = result.get("notes", [])
    out += ["%s on reviews.csv, listed at the end." % plural(len(notes), "note")] if notes else []
    if result["reviews"] < SMALL_SAMPLE:
        out += ["", "Small sample: under %d reviews shows a direction, not a ranking. "
                    "Collect more before you bet the roadmap on it." % SMALL_SAMPLE]
    for kind, title in (("complaint", "What they hate"), ("request", "What they ask for")):
        rows = [theme for theme in result["themes"] if theme["kind"] == kind]
        out += ["", "## " + title, ""] + theme_table(rows, result["months"])
        for theme in rows[:6]:
            out += ["", "**%s**%s" % (theme["label"], " (thin)" if theme["thin"] else "")]
            out += quotes(theme["quotes"])
    if result["requests"]:
        out += ["", "## Asked for in their own words"] + quotes(result["requests"][:25])
    if result["unthemed_negative"]:
        out += ["", "## Read these by hand", "", "Low ratings that matched no theme: noise, or a "
                "theme themes.json does not have yet. Often the most useful part."]
        out += quotes(result["unthemed_negative"][:15])
    if notes:
        out += ["", "## Notes on reviews.csv", ""] + ["- " + note for note in notes]
    return "\n".join(out) + "\n"

def main(argv=None):
    """Run the ranking from the command line. Returns the exit code: 0 or 2 (see the top)."""
    parser = argparse.ArgumentParser(description="Rank what users hate and ask for, from reviews.")
    parser.add_argument("reviews", help="the reviews, normally forge-work/reviews.csv")
    parser.add_argument("--themes", default=THEMES_FILE, help="themes file (default: the one here)")
    parser.add_argument("--months", type=int, default=18, help="older reviews count half (18)")
    parser.add_argument("--today", help="YYYY-MM-DD to count ages from, for a repeatable report")
    parser.add_argument("--out", help="write the report here, normally forge-work/feedback.md")
    parser.add_argument("--json", action="store_true", help="machine-readable JSON output")
    args = parser.parse_args(argv)
    try:
        today = parse_date(args.today) if args.today else None
        if (args.today and not (today and re.match(r"\d{4}-\d\d-\d\d$", args.today))) or args.months < 1:
            raise ReviewsError("--today must be a date that exists, as YYYY-MM-DD; --months 1 or more")
        themes, request_patterns = load_themes(args.themes)
        reviews, notes = load_reviews(args.reviews)
        if not reviews:
            raise ReviewsError("%s has no usable rows: each row needs a link (http or https) and "
                               "the review text. %s" % (args.reviews, "; ".join(notes[:10])))
        result = analyse(reviews, themes, request_patterns, today=today, months=args.months)
        result["notes"] = notes
        report = json.dumps(result, indent=2) + "\n" if args.json else render(result)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(report)
            report = "wrote %s (%s)\n" % (args.out, plural(result["reviews"], "review"))
    except (ReviewsError, OSError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    encoding = sys.stdout.encoding or "utf-8"  # a terminal that cannot show a character: escape
    sys.stdout.write(report.encode(encoding, "backslashreplace").decode(encoding))
    return 0

if __name__ == "__main__":
    sys.exit(main())
