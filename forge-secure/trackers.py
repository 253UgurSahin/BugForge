#!/usr/bin/env python3
"""List the third-party services a project talks to, for the privacy policy (AVG/GDPR).

Finds analytics, ads, fonts, maps, payments, email, error tracking, chat, video and file hosts
by domain and package name in code and config (CODE_TYPES, .env*, requirements*.txt). Medium:
it needs the visitor's yes before it loads, or it gets every visitor's IP address before any yes
(fonts and files from a CDN: self-host them). Low: the rest. Never high: use --fail-on medium.
Skips SKIP_FOLDERS, lockfiles, symlinks, this script and (with a warning) binary files and files
over 1 MB. A file you name is read whatever its type. Opt out: # forge:allow

Usage:
    python3 trackers.py .                     list the services used in this folder
    python3 trackers.py src --json            machine-readable output
    python3 trackers.py . --fail-on medium    exit 1 when a service needs consent

Exit codes: 0 nothing at or above --fail-on (default: high); 1 something is; 2 bad usage, no
such path, or something not checked (unreadable, or a named file that is binary or over 1 MB).
"""

import argparse
import collections
import errno
import json
import os
import re
import sys

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
MAX_BYTES = 1024 * 1024
SKIP_FOLDERS = set(""".git node_modules vendor bower_components venv .venv .tox site-packages
    __pycache__ dist build out .next .nuxt .output .svelte-kit coverage .cache .idea .vscode
    forge-work .claude forge-secure""".split())  # the last three: forge's own notes and code
CODE_TYPES = set(""".html .htm .php .phtml .tpl .twig .erb .haml .slim .ejs .hbs .handlebars
    .mustache .njk .jinja .jinja2 .j2 .liquid .pug .astro .mdx .cshtml .razor .jsp .js .jsx .ts
    .tsx .mjs .cjs .vue .svelte .css .scss .sass .less .py .rb .go .java .kt .kts .swift .dart .cs
    .gradle .json .yml .yaml .toml .xml .conf .properties .env gemfile pipfile podfile""".split())
LOCKFILES = {"package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml"}  # every sub-dependency
FOOTER = "This finds services by name. Ones loaded another way are missed: check the network tab."

Category = collections.namedtuple("Category", "severity consent why fix")  # consent: needs a yes
IP_SENT = "each page view sends the visitor's IP address to the provider"
BEFORE_YES = IP_SENT + ", before any consent"
ASK_FIRST = "load it only after a yes in the cookie banner, and name it in your privacy policy"
SIGN_DPA = "name it in your privacy policy and sign its data processing agreement (DPA)"
SELF_HOST = "self-host the files (it takes minutes), so no visitor data goes to the provider"
NO_PII = "switch off sending personal data, then " + SIGN_DPA
CATEGORIES = {  # severity, needs a yes before it loads, why, fix
    "analytics": Category("medium", True, "it tracks visitors and often sets cookies", ASK_FIRST),
    "cookieless analytics": Category("low", False, "visit data goes to the provider", SIGN_DPA),
    "ads": Category("medium", True, "the ad network learns who visited, for its own ads too",
                    ASK_FIRST),
    "fonts": Category("medium", False, BEFORE_YES, SELF_HOST),
    "maps": Category("low", False, IP_SENT,
                     "show an image of the map; load the live map after a click"),
    "payments": Category("low", False, "names, emails and payment details go to the provider",
                         SIGN_DPA),
    "email": Category("low", False, "email addresses and messages go to the provider", SIGN_DPA),
    "error tracking": Category("low", False, "reports can hold emails, IPs and typed text", NO_PII),
    "chat": Category("medium", True, "the widget sets cookies on every page, even if unused",
                     ASK_FIRST),
    "video": Category("medium", True, "it sets cookies as the page loads",
                      "load the player after a click"),
    "file host": Category("medium", False, BEFORE_YES + "; a file changed there runs on your site",
                          SELF_HOST),
}


def marker_regex(markers):
    """One regex for a service's markers: lowercase text, found in any case; ' also matches ".
    A marker that starts or ends with a letter or digit must not touch another one there ('gtag'
    finds nuxt-gtag, not gtags). Plain words (stripe) only count in a domain, package or setting."""
    alternatives = []
    for marker in markers:
        start = "(?<![a-z0-9])" if marker[0].isalnum() else ""
        end = "(?![a-z0-9])" if marker[-1].isalnum() else ""
        alternatives.append(start + re.escape(marker) + end)
    return re.compile("|".join(alternatives))


Service = collections.namedtuple("Service", "name category markers note", defaults=[""])
SERVICES = [
    Service("Google Analytics / Tag Manager", "analytics", ["google-analytics", "googleanalytics",
            "googletagmanager", "gtag", "gtm-", "react-ga", "ga4"],
            "data goes to Google in the US; Tag Manager can load more tags this scan cannot see"),
    Service("Plausible", "cookieless analytics", ["plausible.io", "plausible-tracker",
            "next-plausible"], "no cookie banner needed; self-host it to keep the data"),
    Service("Matomo", "analytics", ["matomo", "piwik"], "unless self-hosted without cookies"),
    Service("Mixpanel", "analytics", ["mixpanel", "mxpnl.com"]),
    Service("Segment", "analytics", ["segment.com", "segment.io", "@segment/"]),
    Service("PostHog", "analytics", ["posthog"], "pick the EU cloud; mask form fields"),
    Service("Hotjar", "analytics", ["hotjar"], "it records sessions: mask form fields"),
    Service("Microsoft Clarity", "analytics", ["clarity.ms", "@microsoft/clarity"]),
    Service("Amplitude", "analytics", ["amplitude.com", "@amplitude/", "amplitude-js"]),
    Service("Meta Pixel", "ads", ["connect.facebook.net", "fbq(", "facebook-pixel"]),
    Service("Google Ads", "ads", ["doubleclick.net", "googleadservices.com", "googlesyndication"]),
    Service("LinkedIn Insight", "ads", ["snap.licdn.com", "ads.linkedin.com", "linkedin_partner"]),
    Service("TikTok Pixel", "ads", ["analytics.tiktok.com", "ttq.load"]),
    Service("Google Fonts", "fonts", ["fonts.googleapis.com", "fonts.gstatic.com"],
            "in 2022 a German court made a site pay damages for sending visitor IPs to Google"),
    Service("Adobe Fonts", "fonts", ["typekit"], "it cannot be self-hosted: use an open font"),
    Service("Google Maps", "maps", ["maps.googleapis.com", "google.com/maps/embed", "googlemaps",
            "google-maps", "google_maps", "googlemapsembed"]),
    Service("Mapbox", "maps", ["mapbox", "mapboxgl"]),
    Service("Stripe", "payments", ["stripe.com", "stripe/", "stripe\\", "stripe_", "'stripe'",
            "stripe==", "import stripe"]),
    Service("Mollie", "payments", ["mollie.com", "mollie/", "mollie-api", "mollie_"]),
    Service("SendGrid", "email", ["sendgrid.com", "sendgrid.net", "@sendgrid/", "sendgrid/sendgrid",
            "sendgrid==", "sendgrid>=", "import sendgrid", "from sendgrid", "'sendgrid'",
            "sendgrid_"]),
    Service("Mailgun", "email", ["mailgun.net/v3", "mailgun-mailer", "mailgun/mailgun-php",
            "mailgun.js", "mailgun-js"], "choose its EU region to keep the data in the EU"),
    Service("Postmark", "email", ["postmarkapp.com", "postmark-mailer", "wildbit/postmark",
            "postmarker", "require('postmark')", "from 'postmark'", "'postmark': '^"]),
    Service("Resend", "email", ["resend.com", "resend/resend-", "resend.emails", "resend==",
            "require('resend')", "from 'resend'", "'resend': '^"]),
    Service("Mailchimp", "email", ["mailchimp", "list-manage.com", "chimpstatic.com"]),
    Service("Sentry", "error tracking", ["sentry"]),
    Service("Bugsnag", "error tracking", ["bugsnag"]),
    Service("LogRocket", "error tracking", ["logrocket"], "it records sessions: mask form fields"),
    Service("Intercom", "chat", ["intercom.io", "intercomcdn.com", "@intercom/", "intercom('",
            "intercomsettings", "intercom_app_id", "react-use-intercom", "intercom-client"]),
    Service("Crisp", "chat", ["crisp.chat", "$crisp", "crisp-sdk-web", "crisp_website_id"]),
    Service("Tawk.to", "chat", ["tawk"]),
    Service("Zendesk", "chat", ["zendesk", "zdassets.com", "zopim"]),
    Service("YouTube", "video", ["youtube.com/embed", "youtube-nocookie.com", "react-youtube",
            "youtube.com/iframe_api", "youtubeembed", "lite-youtube", "youtube-player"],
            "youtube-nocookie.com still contacts Google as the page loads: it needs a yes too"),
    Service("Vimeo", "video", ["player.vimeo.com", "@vimeo/player", "vimeo-player", "react-vimeo"]),
    Service("jsDelivr", "file host", ["cdn.jsdelivr.net"]),
    Service("unpkg", "file host", ["unpkg.com"]),
    Service("cdnjs", "file host", ["cdnjs.cloudflare.com"]),
]
PATTERNS = [(service, marker_regex(service.markers)) for service in SERVICES]


def find_services(text):
    """Return {service name: first line number} for one file's text. Pure: no file access."""
    text = text.lower().replace('"', "'")  # markers are lowercase and written with ' quotes
    found = {}
    for service, pattern in PATTERNS:
        if any(marker in text for marker in service.markers):  # a quick plain-text look first
            for number, line in enumerate(text.split("\n"), start=1):
                if pattern.search(line) and "forge:allow" not in line:  # the user's opt-out
                    found[service.name] = number
                    break
    return found


def is_code_or_config(path):
    """True for code, templates, styles and config: not docs, lockfiles or text files."""
    name = os.path.basename(path).lower()
    if name.endswith((".txt", ".in")):  # requirements.txt, requirements/base.txt, requirements.in
        return "requirements" in path.lower()
    return name not in LOCKFILES and (name.startswith(".env") or name in CODE_TYPES  # Gemfile
                                      or os.path.splitext(name)[1] in CODE_TYPES)


def files_under(folder, not_checked):
    """Yield the code and config files under folder. Folders it cannot open go in not_checked."""
    for parent, folders, names in os.walk(folder, onerror=lambda e: not_checked.append(e.filename)):
        in_storage = os.path.basename(os.path.normpath(parent)) == "storage"
        folders[:] = sorted(name for name in folders if name not in SKIP_FOLDERS
                            and not (in_storage and name == "framework"))  # Laravel's cache
        for name in sorted(names):  # os.walk does not enter symlinked folders; skip symlinked files
            full = os.path.normpath(os.path.join(parent, name))
            if (is_code_or_config(full) and os.path.isfile(full) and not os.path.islink(full)
                    and os.path.realpath(full) != os.path.realpath(__file__)):  # not this script
                yield full


def scan_path(path):
    """Return ({service name: ["file:line", ...]}, files checked, [what could not be checked])."""
    places, checked, not_checked = {}, 0, []
    for file_path in files_under(path, not_checked) if os.path.isdir(path) else [path]:
        try:
            with open(file_path, "rb") as handle:
                data = handle.read(MAX_BYTES + 1)
        except OSError:
            not_checked.append(file_path)
            continue
        if len(data) > MAX_BYTES or b"\0" in data[:8192]:  # too big, or binary (a NUL byte)
            print("skipped: %s (binary, or over 1 MB)" % file_path, file=sys.stderr)
            if file_path == path:  # the user named this file, so skipping it is an error
                not_checked.append(file_path + " (binary, or over 1 MB)")
            continue
        checked += 1
        for name, line in find_services(data.decode("utf-8", errors="replace")).items():
            places.setdefault(name, []).append("%s:%d" % (file_path, line))
    return places, checked, not_checked


def make_report(places, checked, not_checked, fail_on):
    """The findings (one per service, consent-needing ones first) and a summary with counts."""
    findings = []
    for service in SERVICES:
        files = places.get(service.name)
        if files:
            category = CATEGORIES[service.category]
            more = " and %d more" % (len(files) - 3) if len(files) > 3 else ""
            where = ", ".join(files[:3]) + more  # the first three files, then "and N more"
            label = (": needs consent before it loads" if category.consent
                     else ": self-host it" if category.severity == "medium" else "")
            findings.append({"severity": category.severity,
                             "title": "%s (%s)%s" % (service.name, service.category, label),
                             "where": where, "why": category.why, "fix": category.fix,
                             "note": service.note, "service": service.name, "files": files,
                             "category": service.category, "needs_consent": category.consent})
    findings.sort(key=lambda finding: SEVERITIES.index(finding["severity"]))  # keeps table order
    counts = collections.Counter(finding["severity"] for finding in findings)
    summary = {severity: counts[severity] for severity in SEVERITIES}
    too_bad = any(SEVERITIES.index(f["severity"]) <= SEVERITIES.index(fail_on) for f in findings)
    summary.update(total=len(findings), files_checked=checked,
                   needs_consent=sum(finding["needs_consent"] for finding in findings),
                   not_checked=not_checked, fail_on=fail_on, failed=too_bad or bool(not_checked))
    return {"findings": findings, "summary": summary}


def format_human(report):
    """One block per service, the services for the privacy policy, and a one-line summary.
    A file name that is not valid UTF-8 prints as \\udce9 instead of crashing the output."""
    findings, summary, lines = report["findings"], report["summary"], []
    for finding in findings:
        pad = " " * (len(finding["severity"]) + 2)
        lines += [finding["severity"].upper() + "  " + finding["title"],
                  pad + "where: " + finding["where"], pad + "why:   " + finding["why"],
                  pad + "fix:   " + finding["fix"]]
        if finding["note"]:
            lines.append(pad + "note:  " + finding["note"])
        lines.append("")
    if findings:
        names = ", ".join(finding["service"] for finding in findings)
        counts = ", ".join("%d %s" % (summary[s], s) for s in SEVERITIES if summary[s])
        noun = "finding" if len(findings) == 1 else "findings"
        lines += ["Name these in your privacy policy (AVG/GDPR), with the data they get: "
                  + names + ".", "", "%d %s: %s." % (len(findings), noun, counts)]
    else:
        lines.append("No findings: no known third-party services in the code.")
    missed = ", ".join(summary["not_checked"]) or "nothing"  # anything here: exit code 2
    lines.append("Files checked: %d. Could not check: %s." % (summary["files_checked"], missed))
    return "\n".join(lines + [FOOTER]).encode("utf-8", "backslashreplace").decode("utf-8")


def main(argv=None):
    """Run the scan from the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    # What a cp1252 pipe (Windows) cannot show comes out as an escape, not a crash.
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(description="List the third-party services in the code.")
    parser.add_argument("path", help="file or folder to check")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high",
                        help="exit 1 when a finding is this bad or worse (default: high)")
    args = parser.parse_args(argv)
    if not (os.path.isfile(args.path) or os.path.isdir(args.path)):
        print("error: %s does not exist, or is not a file or folder" % args.path, file=sys.stderr)
        return 2
    places, checked, not_checked = scan_path(args.path)
    report = make_report(places, checked, not_checked, args.fail_on)
    try:
        print(json.dumps(report, indent=2) if args.json else format_human(report), flush=True)
    except OSError as error:  # the reader stopped early (| head): end quietly, no traceback
        if error.errno not in (errno.EPIPE, errno.EINVAL):  # EINVAL: what Windows says there
            raise
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    if not_checked:
        return 2  # part of the project was not checked, so the list may be incomplete
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
