#!/usr/bin/env python3
"""Turn the walk of the app (forge-work/test/walk.json) into findings, and into bugs for bugs.md.

e2e/walk.spec.ts opens every route at three widths, light and dark, and writes down what it saw.
This script judges it. One problem seen at several widths or schemes is one finding. Severities:
high: the page answers 4xx or 5xx, a script error, a 5xx answer or link, an axe violation with the
impact critical, a speed or size value over twice its budget. medium: a console error, a failed
request, a 4xx from the app itself, a 404 link, an axe violation with the impact serious, sideways
scrolling, cut-off text, covered buttons, a redirect, a value over its budget. low: the rest.
The budget (--budget FILE, JSON with any of these keys) is per page on a first load:
lcp_ms 2500, cls 0.1, ttfb_ms 800, load_ms 4000, transfer_bytes 1500000, requests 60.
The check is incomplete (exit 2) when a route, width or scheme has no result, a page was skipped
or did not load, or one of its checks could not run. ../forge-check/walk.md has the details.

Usage:
    python3 walkcheck.py forge-work/test/walk.json [--fail-on medium] [--budget FILE] [--json]
    python3 walkcheck.py forge-work/test/walk.json --bugs --known forge-work/bugs.md --build 3f2a1c9
    python3 walkcheck.py forge-work/test/walk.json --bugs --next 7

--bugs prints each finding at or above --fail-on as a block in the form bugs.py reads, ready to
paste into forge-work/bugs.md above "## To check". --known FILE leaves out findings whose title
is in that file already and numbers after its last bug; --next N sets the first number yourself.

Exit codes:
    0  no finding at or above --fail-on (default: high)
    1  at least one finding at or above --fail-on
    2  bad usage, walk.json or the budget is missing, unreadable or not in the right shape, or
       the walk is incomplete (the output names each page)
"""

import argparse
import json
import re
import sys

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
BUDGET = {"lcp_ms": 2500, "cls": 0.1, "ttfb_ms": 800, "load_ms": 4000, "transfer_bytes": 1500000,
          "requests": 60}
MAX_BYTES = 20 * 1000 * 1000  # a bigger walk.json is refused, not read
AXE = {"critical": "high", "serious": "medium"}  # axe's impact -> severity; the rest is low
SCRIPT = "open the browser's console on this page, find the line it names and fix the cause"
SERVER = "read `docker compose logs app` for this request and fix the cause"
LAYOUT = "fix the CSS at this width: let it wrap or shrink (min-width: 0, flex-wrap, max-width: 100%)"
RULES = {  # rule: (title, what the user should get, why it matters, fix)
    "status": ("the page answers %s", "the page, with status 200",
               "the user gets an error page in place of this screen", SERVER),
    "redirect": ("the page sends the user to %s", "the page that was asked for",
                 "this screen was not walked: the browser landed somewhere else",
                 "sign-in page: run the setup project again; otherwise put the final path in routes.json"),
    "page-error": ("script error: %s", "no uncaught script error",
                   "a script stopped half-way, so part of the page may not work", SCRIPT),
    "console-error": ("console error: %s", "an empty browser console",
                      "the page reports a fault of its own; often a feature that quietly fails", SCRIPT),
    "request-failed": ("a request fails: %s", "every request the page makes gets an answer",
                       "something the page needs never arrives", "check the address and that the app serves it"),
    "response": ("%s", "an answer below 400", "the page asks for something and gets an error back", SERVER),
    "link": ("broken link to %s", "every link opens a page", "a user who clicks it lands on an error page",
             "fix the address, or remove the link"),
    "axe": ("accessibility: %s", "no WCAG 2.2 AA violation",
            "people who use a screen reader, a keyboard or need more contrast cannot use this part",
            "follow the rule's help page (in walk.json: help_url)"),
    "overflow": ("the page scrolls sideways", "the page fits the width of the screen",
                 "content is wider than the screen: users must scroll sideways and may miss it", LAYOUT),
    "clipped": ("text is cut off", "all text readable, or cut with an ellipsis",
                "words are hidden with no sign that there is more", LAYOUT + ", or text-overflow: ellipsis"),
    "overlap": ("a button or link lies under another one", "every control can be clicked",
                "a click on it hits the control on top", LAYOUT + ", or move one of the two"),
    "target": ("tap targets smaller than 24 px", "targets of at least 24 by 24 px (WCAG 2.5.8)",
               "small targets are hard to hit with a finger", "add padding or a min-width and min-height of 24px"),
    "lcp_ms": ("slow to show its main content (LCP)", "the biggest part of the screen drawn within %s ms",
               "users look at an unfinished page", "shrink or preload the main picture, send less blocking CSS and JS"),
    "cls": ("the layout jumps while loading (CLS)", "a layout shift score of at most %s",
            "things move under the user's finger while they read or tap",
            "give pictures and embeds a width and height, keep space for late content"),
    "ttfb_ms": ("the server answers slowly (TTFB)", "the first byte within %s ms",
                "every visit starts with a wait", "look for slow queries or work done on every request; cache it"),
    "load_ms": ("slow to finish loading", "fully loaded within %s ms", "the page stays busy for a long time",
                "load less up front: smaller pictures, fewer scripts, lazy loading"),
    "transfer_bytes": ("the page is heavy", "at most %s bytes sent on a first load",
                       "slow and costly on a phone connection", "compress pictures, drop unused scripts and fonts"),
    "requests": ("the page makes many requests", "at most %s requests on a first load",
                 "each request adds waiting time", "bundle files and drop what the page does not use"),
}


def plain(value, limit=160):
    """Text from the page, safe to print and to paste into bugs.md: one line, ASCII, no [tags] or
    backticks that bugs.py would read as markup, and no query string (it can hold a token)."""
    text = re.sub(r"\?[\w.%-]+=[^\s\"')]*", "?...", " ".join(str(value).split()))
    text = text.replace("[", "(").replace("]", ")").replace("`", "'").lstrip("#>|-*+ ")
    text = text.encode("ascii", "backslashreplace").decode("ascii")
    return text if len(text) <= limit else text[:limit - 3] + "..."


def listed(words):
    """'390, 768 and 1440' from [390, 768, 1440]."""
    words = [str(word) for word in words]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def page_problems(result, budget):
    """(rule, key, severity, the title's word, what was seen) for each problem on one walked page."""
    found = []
    status = result.get("status")
    if isinstance(status, int) and status >= 400:
        found.append(("status", status, "high", status, "status %d" % status))
    if result.get("redirected_to"):
        to = plain(result["redirected_to"], 80)
        found.append(("redirect", to, "medium", to, "asked for %s, landed on %s" % (plain(result["path"], 80), to)))
    for rule, field, severity in (("page-error", "page_errors", "high"), ("console-error", "console_errors", "medium")):
        for text in result.get(field) or []:
            found.append((rule, plain(text, 70), severity, '"%s"' % plain(text, 70), plain(text)))
    for item in result.get("failed_requests") or []:
        url = plain(item.get("url"), 90)
        found.append(("request-failed", url, "medium" if item.get("same_origin") else "low", url,
                      "%s %s: %s" % (plain(item.get("method"), 8), url, plain(item.get("error"), 60))))
    for item in result.get("bad_responses") or []:
        url, code = plain(item.get("url"), 90), int(item.get("status") or 0)
        severity = "high" if code >= 500 else "medium" if item.get("same_origin") else "low"
        found.append(("response", (url, code), severity, "%d on %s" % (code, url),
                      "%s %s answers %d" % (plain(item.get("method"), 8), url, code)))
    for item in result.get("broken_links") or []:
        url, code = plain(item.get("url"), 90), int(item.get("status") or 0)
        found.append(("link", url, "high" if code >= 500 else "medium", url,
                      "the link %s answers %d" % (plain(item.get("text"), 60), code)))
    for item in result.get("axe") or []:
        found.append(("axe", plain(item.get("id"), 40), AXE.get(item.get("impact"), "low"),
                      "%s (%s)" % (plain(item.get("help"), 70), plain(item.get("id"), 40)),
                      "%s element(s), such as %s" % (item.get("nodes"), plain(listed(item.get("targets") or ["?"]), 120))))
    if (result.get("overflow_px") or 0) > 0:
        found.append(("overflow", "", "medium", None, "the page is %d px wider than the screen" % result["overflow_px"]))
    for rule, field, severity in (("clipped", "clipped", "medium"), ("overlap", "overlaps", "medium"),
                                  ("target", "small_targets", "low")):
        items = result.get(field) or []
        if items:
            shown = ["%s under %s" % (plain(item.get("element"), 50), plain(item.get("covered_by"), 50))
                     if rule == "overlap" else plain(item.get("element"), 60) for item in items[:3]]
            found.append((rule, "", severity, None, "%d element(s), such as %s" % (len(items), "; ".join(shown))))
    perf = result.get("perf") or {}
    for name, limit in budget.items():
        value = perf.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > limit:
            high = value > 2 * limit and name != "requests"
            severity = "high" if high else "low" if name == "requests" else "medium"
            found.append((name, "", severity, None, "%s is %s, the budget is %s" % (name, value, limit)))
    return found


def judge(walk, budget):
    """(findings, incomplete): the grouped findings, worst first, and what could not be judged."""
    routes = {route["name"]: route for route in walk["routes"]}
    results = {(r["route"], r["width"], r["scheme"]): r for r in walk["results"]}
    groups, incomplete = {}, []
    for name in routes:
        for width in walk["widths"]:
            for scheme in walk["schemes"]:
                result, at = results.get((name, width, scheme)), "%s at %s px, %s" % (plain(name), width, scheme)
                reasons = (["no result: the walk did not get to this page"] if result is None else
                           ["skipped: %s" % plain(result["skipped"])] if result.get("skipped") else
                           ["did not load: %s" % plain(result.get("error"))] if result.get("loaded") is not True else
                           [plain(reason) for reason in ([result["error"]] if result.get("error") else [])
                            + list(result.get("incomplete") or [])])
                incomplete += ["%s: %s" % (at, reason) for reason in reasons]
                if result is None or result.get("skipped") or result.get("loaded") is not True:
                    continue
                for rule, key, severity, word, seen in page_problems(result, budget):
                    group = groups.setdefault((rule, "" if rule == "link" else name, key), {
                        "rule": rule, "severity": severity, "word": word, "seen": seen, "pages": []})
                    if SEVERITIES.index(severity) < SEVERITIES.index(group["severity"]):
                        group.update(severity=severity, seen=seen)
                    group["pages"].append(result)
    findings = []
    for group in groups.values():
        title, expected, why, fix = RULES[group["rule"]]
        first, pages = group["pages"][0], group["pages"]
        names = sorted({page["route"] for page in pages})
        widths = sorted({page["width"] for page in pages})
        schemes = [scheme for scheme in walk["schemes"] if any(page["scheme"] == scheme for page in pages)]
        user = " (signed in as %s)" % plain(first["as"], 30) if first.get("as") else ""
        limit = budget.get(group["rule"])
        findings.append({
            "rule": group["rule"], "severity": group["severity"],
            "title": "%s: %s" % (plain(listed(names), 60), title % group["word"] if "%s" in title else title),
            "where": "%s (%s)%s at %s px wide, %s" % (plain(listed(names), 60), plain(first["path"], 80), user,
                                                    listed(widths), listed(schemes)),
            "routes": names, "path": first["path"], "as": first.get("as"), "widths": widths, "schemes": schemes,
            "expected": expected % limit if "%s" in expected else expected, "actual": group["seen"], "why": why,
            "fix": fix, "screenshot": next((page.get("screenshot") for page in pages if page.get("screenshot")), None),
            "steps": "open %s%s at %s px wide, %s colour scheme" % (plain(first["path"], 80), user, first["width"],
                                                                 first["scheme"])})
    findings.sort(key=lambda finding: (SEVERITIES.index(finding["severity"]), finding["title"]))
    return findings, incomplete


def bug_block(finding, number, build, source):
    """One bug for bugs.md, in the form bugs.py reads and forge-check test Step 5 shows."""
    evidence = "%s; %s (rule %s)" % (plain(finding["screenshot"] or "no screenshot", 200), source, finding["rule"])
    return "\n".join([
        "## B%03d [%s] [open] %s" % (number, finding["severity"], finding["title"]),
        "case: walk   screen: %s   build: %s   browser: Chromium, %s px wide, %s" % (
            plain(listed(finding["routes"]), 60), plain(build, 40), listed(finding["widths"]),
            listed(finding["schemes"])),
        "steps: " + finding["steps"], "expected: " + finding["expected"],
        "actual: %s (%s)" % (finding["actual"], finding["why"]), "evidence: " + evidence, "fixed in: -", ""])


def known_bugs(path):
    """(titles, next number) from the bug headings of an existing bugs.md."""
    with open(path, "rb") as handle:
        text = handle.read(MAX_BYTES).decode("utf-8-sig", errors="replace")
    heads = re.findall(r"(?m)^## B(\d{3,}) \[\w+\] \[\w+\] (.*?)\s*$", text)
    return {title for _, title in heads}, max([int(number) for number, _ in heads] or [0]) + 1


def load(path, shape):
    """The JSON file at PATH, or a ValueError that says in plain words what is wrong with it."""
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_BYTES + 1)
    except OSError as error:
        raise ValueError("cannot read %s: %s" % (path, error.strerror or error))
    if len(data) > MAX_BYTES:
        raise ValueError("%s is bigger than %d MB: not read" % (path, MAX_BYTES // 1000000))
    try:
        value = json.loads(data.decode("utf-8-sig", errors="replace"))
    except ValueError as error:
        raise ValueError("%s is not valid JSON (%s)" % (path, error))
    if not isinstance(value, shape):
        raise ValueError("%s does not have the right shape (see ../forge-check/walk.md)" % path)
    return value


def main(argv=None):
    """Run the check from the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):  # a cp1252 pipe gets escapes, not a crash
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("file", help="the walk's record, normally forge-work/test/walk.json")
    parser.add_argument("--budget", metavar="FILE", help="JSON with your own limits, such as {\"lcp_ms\": 3000}")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high",
                        help="exit 1 when a finding is this bad or worse (default: high)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--bugs", action="store_true", help="print the findings as blocks for bugs.md")
    parser.add_argument("--next", type=int, metavar="N", help="with --bugs: the number of the first bug")
    parser.add_argument("--known", metavar="BUGS.md", help="with --bugs: skip what this file lists already")
    parser.add_argument("--build", default="-", help="with --bugs: the commit that was walked")
    args = parser.parse_args(argv)
    budget, known, number = dict(BUDGET), set(), args.next or 1
    try:
        walk = load(args.file, dict)
        for name, value in (load(args.budget, dict) if args.budget else {}).items():
            if name not in BUDGET or isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError("%s: %r must be one of %s, with a number above 0" % (args.budget, name, listed(BUDGET)))
            budget[name] = value
        if args.known:
            known, number = known_bugs(args.known)
            number = args.next or number
        try:
            if not (walk["routes"] and walk["results"] and walk["widths"] and walk["schemes"]):
                raise KeyError("empty")
            findings, incomplete = judge(walk, budget)
        except (KeyError, TypeError, ValueError, AttributeError, IndexError) as error:
            raise ValueError("%s does not have the shape walk.spec.ts writes (%s: %s). Run the walk again."
                             % (args.file, type(error).__name__, error))
    except (ValueError, OSError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    for finding in findings:
        finding["blocks"] = SEVERITIES.index(finding["severity"]) <= SEVERITIES.index(args.fail_on)
    failed = any(finding["blocks"] for finding in findings)
    summary = {"routes": len(walk["routes"]), "pages": len(walk["results"]), "fail_on": args.fail_on,
               "failed": failed, "complete": not incomplete, "budget": budget, "round": walk.get("round"),
               "by_severity": {sev: len([f for f in findings if f["severity"] == sev]) for sev in SEVERITIES}}
    if args.bugs:
        for finding in [f for f in findings if f["blocks"] and f["title"] not in known]:
            print(bug_block(finding, number, args.build, plain(args.file, 120)))
            number += 1
    elif args.json:
        print(json.dumps({"findings": findings, "incomplete": incomplete, "summary": summary}, indent=2))
    else:
        for finding in findings:
            print("%-8s  %s" % (finding["severity"].upper(), finding["title"]))
            for name, field in (("where", "where"), ("found", "actual"), ("why", "why"), ("fix", "fix"),
                                ("shot", "screenshot")):
                print("          %-6s %s" % (name + ":", finding[field] or "none"))
        print("%d finding(s) on %d route(s): %s." % (len(findings), summary["routes"], ", ".join(
            "%d %s" % (count, sev) for sev, count in summary["by_severity"].items())))
    if incomplete:
        print("\n".join("incomplete: %s" % line for line in incomplete), file=sys.stderr)
        print("error: the walk is incomplete (%d page(s) or checks): fix the cause and run it again, or take "
              "the route out of routes.json and write it under Not tested." % len(incomplete), file=sys.stderr)
        return 2
    if not args.bugs and not args.json:
        print("FAIL: at least one finding is %s or worse." % args.fail_on if failed
              else "PASS: no finding is %s or worse." % args.fail_on)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
