"""Tests for forge-secure/trackers.py.

The one fake key below is glued together at runtime, so this file never contains
a secret-looking literal: the repo itself is scanned with secretscan.py in CI.
"""

import contextlib
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

# Lets "python3 -m unittest tests.test_trackers" find _load too, not only "discover -s tests".
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _load import load  # noqa: E402

mod = load("forge-secure", "trackers")

FAKE_KEY = "sk_" + "test_" + "Q7w8E9r0T1y2U3i4O5p6"
GA = "Google Analytics / Tag Manager"

# One realistic line per service: each must find exactly that service and nothing else.
SNIPPETS = {
    GA: '<script async src="https://www.googletagmanager.com/gtag/js?id=G-XYZ"></script>',
    "Plausible": '<script defer data-domain="example.org" src="https://plausible.io/js/script.js"></script>',
    "Matomo": "_paq.push(['setTrackerUrl', u+'matomo.php']);",
    "Mixpanel": "import mixpanel from 'mixpanel-browser';",
    "Segment": '<script src="https://cdn.segment.com/analytics.js/v1/abc/analytics.min.js"></script>',
    "PostHog": "posthog.init('phc_abc', { api_host: 'https://eu.i.posthog.com' })",
    "Hotjar": "a.src='https://static.hotjar.com/c/hotjar-'+h._hjSettings.hjid+'.js'",
    "Microsoft Clarity": 't.src="https://www.clarity.ms/tag/"+i;',
    "Amplitude": "import * as amplitude from '@amplitude/analytics-browser';",
    "Meta Pixel": "fbq('init', '1234567890'); fbq('track', 'PageView');",
    "Google Ads": '<script src="https://securepubads.g.doubleclick.net/tag/js/gpt.js"></script>',
    "LinkedIn Insight": '_linkedin_partner_id = "123456";',
    "TikTok Pixel": "ttq.load('C4ABCDEFG'); ttq.page();",
    "Google Fonts": "@import url('https://fonts.googleapis.com/css2?family=Inter&display=swap');",
    "Adobe Fonts": '<link rel="stylesheet" href="https://use.typekit.net/abc1def.css">',
    "Google Maps": '<script src="https://maps.googleapis.com/maps/api/js?callback=initMap"></script>',
    "Mapbox": "import mapboxgl from 'mapbox-gl';",
    "Stripe": '"stripe/stripe-php": "^13.0",',
    "Mollie": '"mollie/laravel-mollie": "^3.0",',
    "SendGrid": "const sgMail = require('@sendgrid/mail');",
    "Mailgun": '"symfony/mailgun-mailer": "^7.0",',
    "Postmark": 'import { ServerClient } from "postmark";',
    "Resend": "import { Resend } from 'resend';",
    "Mailchimp": '<form action="https://example.us1.list-manage.com/subscribe/post?u=abc" method="post">',
    "Sentry": "sentry-sdk[django]==2.0.0",
    "Bugsnag": "import Bugsnag from '@bugsnag/js';",
    "LogRocket": "LogRocket.init('abc/my-app');",
    "Intercom": '<script src="https://widget.intercom.io/widget/abc123"></script>',
    "Crisp": 'window.$crisp=[];window.CRISP_WEBSITE_ID="abc";',
    "Tawk.to": "s1.src='https://embed.tawk.to/abc/default';",
    "Zendesk": '<script id="ze-snippet" src="https://static.zdassets.com/ekr/snippet.js?key=abc"></script>',
    "YouTube": '<iframe src="https://www.youtube-nocookie.com/embed/abc123"></iframe>',
    "Vimeo": '<iframe src="https://player.vimeo.com/video/123?dnt=1"></iframe>',
    "jsDelivr": '<script src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>',
    "unpkg": '<script src="https://unpkg.com/htmx.org@1.9.10"></script>',
    "cdnjs": '<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">',
}

# Services added through an SDK, framework plugin or dependency list (reviewer findings).
SDK_LINES = [
    (GA, "import { GoogleAnalytics } from '@next/third-parties/google';"),
    (GA, "<GoogleAnalytics gaId={process.env.NEXT_PUBLIC_GA_ID} />"),
    (GA, '"gatsby-plugin-google-gtag": "^5.0.0",'),
    (GA, "modules: ['@nuxtjs/google-analytics'],"),
    (GA, "modules: ['nuxt-gtag'], gtag: { id: 'G-ABC123' }"),
    (GA, '<link rel="preconnect" href="https://www.googletagmanager.com">'),
    (GA, "add_header Content-Security-Policy \"script-src 'self' https://www.googletagmanager.com\";"),
    (GA, "})(window,document,'script','dataLayer','GTM-AB12CD');"),
    ("Meta Pixel", "import ReactPixel from 'react-facebook-pixel';"),
    ("Google Maps", "import { APIProvider, Map } from '@vis.gl/react-google-maps';"),
    ("Google Maps", "import { GoogleMap, useJsApiLoader } from '@react-google-maps/api';"),
    ("Google Maps", "import 'package:google_maps_flutter/google_maps_flutter.dart';"),
    ("Vimeo", "import Player from '@vimeo/player';"),
    ("YouTube", "import YouTube from 'react-youtube';"),
    ("YouTube", '<YouTubeEmbed videoid="ogfYd705cRs" />'),
    ("Postmark", '"postmark": "^4.0.2",'),
    ("Resend", '"resend": "^3.2.0",'),
    ("Resend", "resend==2.0.0"),
    ("Resend", "resend.Emails.send(params)"),
    ("Mailgun", '"mailgun-js": "^0.22.0",'),
    ("SendGrid", "sendgrid==6.11.0"),
    ("SendGrid", "from sendgrid import SendGridAPIClient"),
    ("SendGrid", '"sendgrid/sendgrid": "^8.1",'),
    ("SendGrid", "SENDGRID_API_KEY=SG.xxx"),
    ("SendGrid", 'SENDGRID_ENDPOINT = "https://api.sendgrid.com/v3/mail/send"'),
    ("SendGrid", 'EMAIL_BACKEND = "sendgrid_backend.SendgridBackend"'),
    ("Stripe", "gem 'stripe'"),
    ("Stripe", "stripe==7.0.0"),
    ("Stripe", "import stripe"),
    ("Stripe", "import { loadStripe } from '@stripe/stripe-js';"),
    ("Stripe", '<script src="https://js.stripe.com/v3/"></script>'),
    ("Stripe", "$stripe = new \\Stripe\\StripeClient($key);"),
    ("Mollie", '"@mollie/api-client": "^3.7.0",'),
    ("Mollie", "mollie-api-python==3.6.0"),
    ("Sentry", "implementation 'io.sentry:sentry-android:7.0.0'"),
    ("Sentry", "import 'package:sentry_flutter/sentry_flutter.dart';"),
    ("Sentry", "sentry.dsn=https://abc@o1.ingest.sentry.io/1"),
    ("Intercom", 'window.Intercom("boot", {app_id: "abc"});'),
    ("Intercom", '"react-use-intercom": "^5.0.0",'),
]

# Lines that look close but are not a third-party service.
NOT_SERVICES = [
    '<table class="table table-striped">',
    '<table id="orders" class="display stripe hover"></table>',  # DataTables zebra stripes
    ".table .stripe { background: #eee; } /* zebra stripe */",
    ":root { --stripe-color: #f5f5f5; }",
    '[{"first_name": "Mollie", "last_name": "Jansen"}]',
    "'name' => 'Mollie Smith',",
    '"""Smart-home intercom panel."""',
    "class DoorIntercom:",
    "public function resendVerificationEmail() { return back(); }",
    "Route::post('/email/resend', [VerifyController::class, 'resend']);",
    "import resend from './actions/resend';",
    "import resend_utils",
    '{"resend": "Resend the code"}',  # a translation key
    "image-rendering: crisp-edges;",
    "const amplitude = Math.sin(t) * 0.5;",
    "$part = $request->segment(2);",
    "For clarity, the steps are split up.",
    "That is a plausible explanation.",
    "The intercompany transfer is booked monthly.",
    "import { Inter } from 'next/font/google';",  # next/font downloads the font at build time
    '<a href="https://www.facebook.com/ourpage">Facebook</a>',  # a link, not the pixel
    '<a href="https://www.youtube.com/watch?v=abc">our video</a>',  # a link, not an embed
    # Laravel's default config names these mail services even when the app does not use them.
    "'postmark' => ['token' => env('POSTMARK_TOKEN')],",
    "'resend' => ['key' => env('RESEND_KEY')],",
    "'endpoint' => env('MAILGUN_ENDPOINT', 'api.mailgun.net'),",
    "'mailers' => ['smtp', 'ses', 'postmark', 'resend', 'mailgun', 'log'],",
    'Rule("critical", "SendGrid API key", pattern, MAIL, fix)',  # forge's own secret scanner
]


def write(folder, relative_path, content):
    path = os.path.join(folder, relative_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(content, bytes) else "w") as handle:
        handle.write(content)
    return path


def run(*args):
    """Run main() and return (exit code, stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = mod.main(list(args))
    return code, out.getvalue()


def services_in(text):
    return set(mod.find_services(text))


class TempFolder(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def scan(self, *extra):
        code, out = run(self.dir, "--json", *extra)
        return code, json.loads(out)

    def found(self):
        return {f["service"] for f in self.scan()[1]["findings"]}


class MatchTests(unittest.TestCase):
    def test_every_service_has_a_snippet(self):
        self.assertEqual(set(SNIPPETS), {service.name for service in mod.SERVICES})

    def test_each_snippet_finds_exactly_its_service(self):
        for name, line in SNIPPETS.items():
            with self.subTest(service=name):
                self.assertEqual(services_in(line), {name})

    def test_every_marker_finds_only_its_own_service(self):
        for service in mod.SERVICES:
            for marker in service.markers:
                with self.subTest(marker=marker):
                    self.assertEqual(services_in("x = (" + marker + ");"), {service.name})

    def test_sdk_plugin_and_dependency_lines(self):
        for name, line in SDK_LINES:
            with self.subTest(line=line):
                self.assertEqual(services_in(line), {name})

    def test_lookalikes_are_not_services(self):
        for line in NOT_SERVICES:
            with self.subTest(line=line):
                self.assertEqual(services_in(line), set())

    def test_any_case_and_either_quote(self):
        self.assertEqual(services_in("STRIPE_SECRET_KEY=" + FAKE_KEY), {"Stripe"})
        self.assertEqual(services_in("const { Resend } = require(\"resend\");"), {"Resend"})
        self.assertEqual(services_in("'gtm-ab12cd'"), {GA})

    def test_reports_the_first_line(self):
        text = "a\nb\n<script src='https://unpkg.com/a'></script>\n<script src='https://unpkg.com/b'></script>"
        self.assertEqual(mod.find_services(text), {"unpkg": 3})

    def test_several_services_on_one_line(self):
        line = "script-src 'self' https://www.googletagmanager.com https://api.mapbox.com https://js.stripe.com"
        self.assertEqual(services_in(line), {GA, "Mapbox", "Stripe"})

    def test_forge_allow_skips_the_line(self):
        self.assertEqual(services_in(SNIPPETS["Hotjar"] + "  // forge:allow"), set())
        self.assertEqual(services_in(SNIPPETS["Hotjar"] + "\n" + SNIPPETS["Vimeo"] + " forge:allow"), {"Hotjar"})
        self.assertEqual(mod.find_services(SNIPPETS["Vimeo"] + " forge:allow\n" + SNIPPETS["Vimeo"]), {"Vimeo": 2})

    def test_every_category_is_known(self):
        for service in mod.SERVICES:
            self.assertIn(service.category, mod.CATEGORIES, service.name)


class ConsentTests(unittest.TestCase):
    def findings_for(self, *names):
        report = mod.make_report({name: ["x.html:1"] for name in names}, 1, [], "high")
        return {f["service"]: f for f in report["findings"]}

    def test_consent_needing_services_are_medium(self):
        names = [GA, "Matomo", "Meta Pixel", "TikTok Pixel", "Intercom", "YouTube", "Vimeo", "Hotjar"]
        for name, finding in self.findings_for(*names).items():
            with self.subTest(service=name):
                self.assertEqual((finding["severity"], finding["needs_consent"]), ("medium", True))
                self.assertIn("needs consent", finding["title"])

    def test_fonts_and_files_from_a_cdn_are_medium_without_consent(self):
        # Dogfood: fonts were low here, high in the audit table and banned in forge-design. Every
        # page view sends the visitor's IP before any yes: medium, fixed by self-hosting.
        for name, finding in self.findings_for("Google Fonts", "Adobe Fonts", "jsDelivr", "unpkg").items():
            with self.subTest(service=name):
                self.assertEqual((finding["severity"], finding["needs_consent"]), ("medium", False))
                self.assertTrue(finding["title"].endswith(": self-host it"), finding["title"])
                self.assertIn("before any consent", finding["why"])

    def test_other_services_are_low(self):
        names = ["Plausible", "Google Maps", "Stripe", "Mollie", "SendGrid", "Sentry"]
        for name, finding in self.findings_for(*names).items():
            with self.subTest(service=name):
                self.assertEqual((finding["severity"], finding["needs_consent"]), ("low", False))

    def test_plausible_and_matomo_notes(self):
        found = self.findings_for("Plausible", "Matomo")
        self.assertIn("no cookie banner", found["Plausible"]["note"])
        self.assertIn("self-hosted", found["Matomo"]["note"])

    def test_google_fonts_fix_and_note_agree(self):
        finding = self.findings_for("Google Fonts")["Google Fonts"]
        self.assertIn("self-host", finding["fix"])
        self.assertNotIn("privacy policy", finding["fix"])  # naming Google was not enough in court
        self.assertIn("German court", finding["note"])
        self.assertIn("IP address", finding["why"])

    def test_file_host_fix_stops_the_ip_transfer(self):
        finding = self.findings_for("unpkg")["unpkg"]
        self.assertIn("IP address", finding["why"])
        self.assertIn("self-host", finding["fix"])
        self.assertNotIn("integrity", finding["fix"])

    def test_medium_first_then_table_order(self):
        places = {name: ["x.html:1"] for name in ["cdnjs", "YouTube", "Stripe", "Hotjar"]}
        report = mod.make_report(places, 1, [], "high")
        self.assertEqual([f["service"] for f in report["findings"]], ["Hotjar", "YouTube", "cdnjs", "Stripe"])


class WalkTests(TempFolder):
    def test_code_and_config_files_are_checked(self):
        write(self.dir, "resources/views/layout.blade.php", SNIPPETS[GA])
        write(self.dir, "package.json", '{"dependencies": {"@sendgrid/mail": "^8.0.0"}}')
        write(self.dir, "composer.json", SNIPPETS["Mollie"])
        write(self.dir, "requirements-prod.txt", SNIPPETS["Sentry"])
        write(self.dir, "assets/app.scss", SNIPPETS["Google Fonts"])
        write(self.dir, ".env.example", "STRIPE_KEY=\nSTRIPE_SECRET=\n")
        self.assertEqual(self.found(), {GA, "SendGrid", "Mollie", "Sentry", "Google Fonts", "Stripe"})

    def test_templates_mobile_code_and_manifests_are_checked(self):
        files = ["layout.handlebars", "header.tpl", "view.phtml", "_Layout.cshtml", "Page.razor",
                 "index.pug", "page.jsp", "base.jinja", "base.j2", "post.mdx", "app.mustache",
                 "App.swift", "Main.kt", "main.dart", "Program.cs", "app/build.gradle",
                 "application.properties", "nginx.conf", "Gemfile", "Pipfile", "Podfile",
                 "requirements/base.txt", "requirements.in"]
        for name in files:
            with self.subTest(file=name):
                folder = tempfile.mkdtemp()
                self.addCleanup(shutil.rmtree, folder)
                write(folder, name, SNIPPETS["Hotjar"])
                report = json.loads(run(folder, "--json")[1])
                self.assertEqual([f["service"] for f in report["findings"]], ["Hotjar"])

    def test_docs_text_and_lockfiles_are_skipped(self):
        write(self.dir, "README.md", "We take payments with js.stripe.com and use Hotjar.")
        write(self.dir, "requirements.md", "Users pay with js.stripe.com. Errors go to Sentry.")
        write(self.dir, "docs/requirements.rst", SNIPPETS["Hotjar"])
        write(self.dir, "notes.txt", SNIPPETS["Hotjar"])
        write(self.dir, "package-lock.json", '"node_modules/@sentry/browser": {}')
        write(self.dir, "npm-shrinkwrap.json", '"node_modules/@sentry/browser": {}')
        write(self.dir, "pnpm-lock.yaml", "'@sentry/browser': 1.0.0")
        self.assertEqual(self.found(), set())

    def test_a_named_file_is_checked_whatever_its_type(self):
        path = write(self.dir, "README.md", SNIPPETS["Hotjar"])
        code, out = run(path, "--json")
        self.assertEqual([f["service"] for f in json.loads(out)["findings"]], ["Hotjar"])

    def test_skipped_folders(self):
        for folder in sorted(mod.SKIP_FOLDERS) + ["storage/framework/views"]:
            write(self.dir, folder + "/x/page.html", SNIPPETS["Hotjar"])
        write(self.dir, "env/lib/python3.12/site-packages/stripe/api.py", "import sentry_sdk")
        write(self.dir, "env/pyvenv.cfg", "home = /usr/bin\n")
        write(self.dir, "storage/app/page.html", SNIPPETS["Vimeo"])  # only storage/framework is skipped
        write(self.dir, "framework/page.html", SNIPPETS["Vimeo"])
        self.assertEqual(self.found(), {"Vimeo"})

    def test_binary_and_big_files_in_a_folder_are_skipped(self):
        write(self.dir, "logo.svg.js", b"\0\x01" + SNIPPETS["Hotjar"].encode())
        write(self.dir, "huge.js", SNIPPETS["Vimeo"] + "\n" + "x" * (mod.MAX_BYTES + 10))
        code, report = self.scan()
        self.assertEqual((code, report["findings"]), (0, []))
        self.assertEqual((report["summary"]["files_checked"], report["summary"]["not_checked"]), (0, []))

    def test_a_named_binary_or_big_file_is_exit_2(self):
        big = write(self.dir, "vendor-chunk.js", SNIPPETS["Meta Pixel"] + "\n" + "x" * (mod.MAX_BYTES + 10))
        binary = write(self.dir, "logo.js", b"\0\x01" + SNIPPETS["Hotjar"].encode())
        for path in [big, binary]:
            with self.subTest(path=path):
                code, out = run(path, "--fail-on", "medium")
                self.assertEqual(code, 2)
                self.assertIn("Could not check: " + path + " (binary, or over 1 MB)", out)

    def test_a_named_pipe_is_exit_2_and_skipped_in_a_folder(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("no named pipes here")
        pipe = os.path.join(self.dir, "pipe.js")
        os.mkfifo(pipe)
        write(self.dir, "b.html", SNIPPETS["unpkg"])
        for path, code in [(pipe, 2), (self.dir, 0)]:  # a subprocess, so a hang fails the test
            result = subprocess.run([sys.executable, mod.__file__, path], capture_output=True,
                                    text=True, timeout=30)
            self.assertEqual(result.returncode, code, path)

    def test_unreadable_file_is_reported_and_exit_2(self):
        locked = write(self.dir, "open/locked.html", SNIPPETS["Hotjar"])
        write(self.dir, "b.html", SNIPPETS["unpkg"])
        real_open = open

        def fake_open(path, *args, **kwargs):
            if path == locked:
                raise PermissionError(13, "Permission denied", path)
            return real_open(path, *args, **kwargs)

        with mock.patch("builtins.open", fake_open):
            code, report = self.scan()
        self.assertEqual(code, 2)
        self.assertEqual(report["summary"]["not_checked"], [locked])
        self.assertTrue(report["summary"]["failed"])
        self.assertEqual([f["service"] for f in report["findings"]], ["unpkg"])

    def test_unreadable_folder_is_reported_and_exit_2(self):
        locked = os.path.join(self.dir, "locked")
        write(self.dir, "locked/index.html", SNIPPETS["Hotjar"])
        write(self.dir, "b.html", SNIPPETS["unpkg"])
        real_scandir = os.scandir

        def fake_scandir(path="."):
            if os.path.normpath(path) == locked:
                raise PermissionError(13, "Permission denied", path)
            return real_scandir(path)

        with mock.patch("os.scandir", fake_scandir):
            code, out = run(self.dir)
        self.assertEqual(code, 2)
        self.assertIn("Could not check: " + locked, out)

    def test_symlinks_are_not_followed(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)
        write(outside, "tracker.js", SNIPPETS["Hotjar"])
        try:
            os.symlink(os.path.join(outside, "tracker.js"), os.path.join(self.dir, "link.js"))
            os.symlink(outside, os.path.join(self.dir, "linked-folder"))
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not supported here")
        self.assertEqual(self.found(), set())

    def test_this_script_does_not_list_itself(self):
        files = list(mod.files_under(os.path.dirname(mod.__file__), []))
        self.assertNotIn(os.path.realpath(mod.__file__), [os.path.realpath(f) for f in files])

    def test_forge_scripts_name_no_service(self):
        for path in glob.glob(os.path.join(os.path.dirname(mod.__file__), "*.py")):
            if os.path.basename(path) != "trackers.py":
                with self.subTest(script=os.path.basename(path)), open(path, encoding="utf-8") as handle:
                    self.assertEqual(services_in(handle.read()), set())

    def test_a_copy_of_forge_in_the_project_lists_nothing(self):
        tools = os.path.join(self.dir, "tools")  # copied under another name than forge-secure
        os.makedirs(tools)
        for path in glob.glob(os.path.join(os.path.dirname(mod.__file__), "*.py")):
            shutil.copy(path, tools)
        result = subprocess.run([sys.executable, os.path.join(tools, "trackers.py"), self.dir, "--json"],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(json.loads(result.stdout)["findings"], [])

    def test_one_finding_per_service_with_every_file(self):
        for number in range(7):
            write(self.dir, "src/pay%d.js" % number, "\n" * number + "import Stripe from 'stripe';")
        findings = self.scan()[1]["findings"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(len(findings[0]["files"]), 7)
        self.assertIn(os.path.join(self.dir, "src", "pay3.js") + ":4", findings[0]["files"])
        self.assertTrue(findings[0]["where"].endswith(" and 4 more"))

    def test_env_values_are_never_printed(self):
        write(self.dir, ".env", "STRIPE_SECRET=" + FAKE_KEY + "\n")
        for args in [(self.dir,), (self.dir, "--json")]:
            code, out = run(*args)
            self.assertIn("Stripe", out)
            self.assertNotIn(FAKE_KEY, out)
            self.assertNotIn(FAKE_KEY[:12], out)


class OutputTests(TempFolder):
    def test_human_output(self):
        page = write(self.dir, "index.html", "<html>\n" + SNIPPETS[GA] + "\n")
        pay = write(self.dir, "pay.js", SNIPPETS["Stripe"])
        code, out = run(self.dir)
        self.assertEqual(code, 0)
        self.assertIn("MEDIUM  " + GA + " (analytics): needs consent before it loads\n"
                      "        where: " + page + ":2\n        why:   ", out)
        self.assertIn("        note:  data goes to Google in the US", out)
        stripe_block = out[out.index("LOW  Stripe (payments)\n"):]
        self.assertIn("LOW  Stripe (payments)\n     where: " + pay + ":1\n     why:   ", stripe_block)
        self.assertNotIn("note:", stripe_block)  # an empty note prints no note line
        self.assertLess(out.index("MEDIUM"), out.index("LOW"))
        self.assertIn("Name these in your privacy policy (AVG/GDPR), with the data they get: "
                      + GA + ", Stripe.", out)
        self.assertIn("2 findings: 1 medium, 1 low.", out)
        self.assertIn("Files checked: 2. Could not check: nothing.", out)
        self.assertIn("network tab", out)

    def test_no_findings(self):
        write(self.dir, "index.html", "<h1>Hello</h1>")
        code, out = run(self.dir)
        self.assertEqual(code, 0)
        self.assertIn("No findings", out)
        self.assertNotIn("privacy policy", out)

    def test_json_shape(self):
        write(self.dir, "index.html", SNIPPETS["YouTube"] + "\n" + SNIPPETS["cdnjs"])
        code, report = self.scan()
        self.assertEqual(code, 0)
        for finding in report["findings"]:
            for key in ["severity", "title", "where", "why", "fix", "note", "service", "category",
                        "needs_consent", "files"]:
                self.assertIn(key, finding)
        summary = report["summary"]
        self.assertEqual((summary["medium"], summary["low"], summary["total"]), (2, 0, 2))  # cdnjs: medium
        self.assertEqual((summary["critical"], summary["high"], summary["needs_consent"]), (0, 0, 1))
        self.assertEqual((summary["files_checked"], summary["fail_on"], summary["failed"]), (1, "high", False))
        self.assertEqual(summary["not_checked"], [])

    def test_a_file_name_that_is_not_utf8_does_not_crash(self):
        try:
            name = os.path.join(os.fsencode(self.dir), b"caf\xe9.js")
            with open(name, "wb") as handle:
                handle.write(b"import Stripe from 'stripe';\n")
        except (OSError, UnicodeError):
            self.skipTest("this file system does not allow such names")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        for extra in [[], ["--fail-on", "medium"], ["--json"]]:
            with self.subTest(args=extra):
                result = subprocess.run([sys.executable, mod.__file__, self.dir] + extra, env=env,
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("caf\\udce9.js", result.stdout)


class ExitCodeTests(TempFolder):
    def test_fail_on(self):
        write(self.dir, "index.html", SNIPPETS["YouTube"])  # medium
        self.assertEqual(run(self.dir)[0], 0)  # default: high, which this script never reports
        self.assertEqual(run(self.dir, "--fail-on", "high")[0], 0)
        self.assertEqual(run(self.dir, "--fail-on", "medium")[0], 1)
        self.assertTrue(self.scan("--fail-on", "low")[1]["summary"]["failed"])

    def test_fail_on_with_only_low(self):
        write(self.dir, "index.html", SNIPPETS["Stripe"])  # low
        self.assertEqual(run(self.dir, "--fail-on", "medium")[0], 0)
        self.assertEqual(run(self.dir, "--fail-on", "low")[0], 1)

    def test_missing_path_is_exit_2(self):
        self.assertEqual(run(os.path.join(self.dir, "nope"))[0], 2)

    def test_output_into_a_closed_pipe_ends_quietly(self):
        # Regression (dogfood): `trackers.py . | head` printed a BrokenPipeError traceback.
        write(self.dir, "index.html", "\n".join(SNIPPETS.values()))
        done = subprocess.Popen([sys.executable, mod.__file__, self.dir], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        done.stdout.close()  # the reader is gone before anything is printed
        error = done.stderr.read().decode()
        done.stderr.close()
        self.assertEqual(done.wait(timeout=60), 0)
        self.assertNotIn("Traceback", error)

    def test_bad_arguments_are_exit_2(self):
        for args in [[], [self.dir, "--fail-on", "urgent"]]:
            with self.assertRaises(SystemExit) as caught, contextlib.redirect_stderr(io.StringIO()):
                mod.main(args)
            self.assertEqual(caught.exception.code, 2)

    def test_runs_as_a_script(self):
        write(self.dir, "index.html", SNIPPETS["Intercom"])
        result = subprocess.run([sys.executable, mod.__file__, self.dir, "--fail-on", "medium"],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Intercom (chat): needs consent before it loads", result.stdout)


class ConventionTests(unittest.TestCase):
    def test_script_conventions(self):
        with open(mod.__file__, encoding="utf-8") as handle:
            source = handle.read()
        self.assertTrue(source.startswith("#!/usr/bin/env python3\n"))
        self.assertLessEqual(source.count("\n"), 300)  # the spec's hard limit
        self.assertIn("Usage", mod.__doc__)
        self.assertIn("Exit codes", mod.__doc__)
        self.assertIn("forge:allow", mod.__doc__)

    def test_lines_are_at_most_100_characters(self):
        with open(mod.__file__, encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                self.assertLessEqual(len(line.rstrip("\n")), 100, "line %d" % number)


if __name__ == "__main__":
    unittest.main()
