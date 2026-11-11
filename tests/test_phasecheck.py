"""Tests for forge/phasecheck.py: the exit checks of every phase, passing and failing, with the real
scripts of the other skills. A finished phase passes in every mode it runs in; a phase that left a
template half filled in, a section empty, a report or a spec out, or a verdict unearned fails, as the
dogfood run found (N1 to N43); lines hidden in comments or code blocks and decorated verdicts do not
fool the line checks; a script that prints nothing, crashes or hangs fails; a report older than --since
fails. Every test works in its own folder."""

import contextlib
import datetime
import glob
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402
from test_motioncount import sample_app  # noqa: E402  (an app at each look level, as motioncount.py counts it)

phasecheck = load("forge", "phasecheck")
gate = load("forge", "gate")
HAS_GIT = shutil.which("git") is not None
STATIC = os.path.join(ROOT, "forge-build", "templates", "static")
OLD = 1500000000  # 2017: a file time long before any go
FENCE = re.compile(r" {0,3}(`{3,}|~{3,})")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def write(root, name, text):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def png(rgb):
    """A 4 x 4 PNG of one colour, made at run time."""
    rows = b"".join(b"\0" + bytes(rgb) * 4 for _ in range(4))
    chunk = lambda kind, body: struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def shown(root, folder, after=(15, 123, 108), parts=("before", "after"), name="home-390-light.png"):
    """FOLDER/before and FOLDER/after (or the PARTS given) with a shot of one screen each, as Show the result leaves
    them: white before, AFTER's colour after (white too: no visible change)."""
    for part, rgb in zip(parts, ((255, 255, 255), after)):
        os.makedirs(os.path.join(root, folder, part), exist_ok=True)
        with open(os.path.join(root, folder, part, name), "wb") as handle:
            handle.write(png(rgb))


def frames(root, folder, name="home", kind="f", moving=True):
    """FOLDER/<NAME>-390-f1.png to -f4.png (KIND s: <NAME>-1440-s1.png to -s6.png), as shots.mjs --frames and
    --scene-frames take them: each frame a shade darker than the one before it (MOVING), or all the same."""
    os.makedirs(os.path.join(root, folder), exist_ok=True)
    for number in range(1, 5 if kind == "f" else 7):
        shade = 255 - 30 * number * moving
        with open(os.path.join(root, folder, "%s-%s-%s%d.png" % (name, "390" if kind == "f" else "1440", kind,
                                                                  number)), "wb") as handle:
            handle.write(png((shade, shade, shade)))


def template(folder, name):
    return read(os.path.join(ROOT, folder, name))


def example(phase):
    """The report in the Output section of PHASE's steps: the first markdown block of its steps file (a phase that
    is a skill of its own: of its SKILL.md)."""
    skill, _, part = gate_skill(phase).partition(" ")
    name = os.path.join("steps", part + ".md") if part else "SKILL.md"
    return template(skill, name).split("```markdown\n")[1].split("\n```\n")[0] + "\n"


def gate_skill(phase):
    """The skill of PHASE as forge/phases.json gives it: "forge-check secure", or "forge-improve"."""
    parts = json.loads(template("forge", "phases.json"))["parts"]
    return next(("forge-%s %s" % (skill, phase) for skill, names in parts.items() if phase in names), "forge-" + phase)


def filled(path, **lines):
    """The template at PATH (in the pack) as a writer fills it in: each {{...}}, and each <...> outside
    code, becomes its own words; each ## section gets a line of this app's own; LINES set `Label: value`."""
    text = re.sub(r"\{\{(.*?)\}\}", lambda match: " ".join(match.group(1).split()), read(os.path.join(ROOT, path)),
                  flags=re.S)
    out, fence = [], None
    for line in text.split("\n"):
        mark = FENCE.match(line)
        if fence:
            fence = None if mark and mark.group(1)[0] == fence[0] else fence
        elif mark:
            fence = mark.group(1)
        else:
            line = re.sub(r"<(?!!--)([^<>\n]+)>", r"\1", line)
        out.append(line)
        if not fence and line.startswith("## "):
            out.append("\nSlotwise: written for this app.")
    text = "\n".join(out)
    for label, value in lines.items():
        text = re.sub(r"(?m)^%s:.*$" % label, "%s: %s" % (label, value), text)
    return text


def outside_code(text):
    """TEXT with its one-line {{...}} outside code blocks filled in, and the rest left: how a writer who
    skips the code blocks and the long placeholders leaves a template."""
    out, fence = [], None
    for line in text.split("\n"):
        mark = FENCE.match(line)
        if fence:
            fence = None if mark and mark.group(1)[0] == fence[0] else fence
        elif mark:
            fence = mark.group(1)
        else:
            line = re.sub(r"\{\{[^{}\n]*\}\}", "x", line)
        out.append(line)
    return "\n".join(out)


FEATURES = "feature,area,priority,original,clone,notes\nBook a slot,booking,must,yes,yes,\nReminders,email,could,yes,no,\n"
NO_BUGS = "# Bugs\n\nNo bugs found.\n"
BUGS = "# Bugs\n\n## B001 [low] [open] Slot taken shows no message\ncase: F01-E1   screen: S08\nfixed in: -\n"
PLAN = filled("forge-plan/plan.md", Profile="static", PWA="no", Mode="clone")
CASES = "| case | flow | type | steps | expected | auto | result |\n| --- | --- | --- | --- | --- | --- | --- |\n" \
        "| F01-H1 | book a slot | happy | pick 10:00 | booked | e2e | pass |\n" \
        "| F01-E1 | | edge: slot taken | | message | e2e | fail B001 |\n"
TEST_PLAN = re.sub(r"(?m)^\| case \|.*\n(?:\|.*\n)*", CASES, filled("forge-check/test-plan.md")).replace("Level: 3 (Standard)", "Level: 2 (Basic)")
SPEC = "import { test } from '@playwright/test';\ntest('F01-H1 book a slot', async ({ page }) => {});\n"
TOKENS = json.dumps(dict(json.loads(template("forge-design", "tokens.json")),
                         font={"sans": "IBM Plex Sans, system-ui, sans-serif", "mono": "ui-monospace, monospace"}))
# components.md ends with ## Components: one block under it, as forge-design design Step 5 writes it.
COMPONENTS = filled("forge-design/components.md") + "\n```\nButton\n  variants  primary, secondary, ghost\n" \
             "  states    default, hover, active, focus-visible, disabled, loading\n  used on   S02, S07\n```\n"
CONCEPT = "<!doctype html><title>Slotwise: concept A</title><main><h1>Today: 12 bookings</h1></main>\n"
REVIEW = "# Look review: Slotwise\nServed: docker compose on http://localhost:8080\n\n" \
         "## Round 1 (2026-10-27, commit 3f2a1c9, judge: fresh eyes)\n| screen | score / 22 | no | weakest things | " \
         "fixes |\n| --- | --- | --- | --- | --- |\n| home | 19 | | the stat row is loud | stat row in text-muted |\n"
BUILD_LOG = "# Build log\nLevel: 2 (Polished)\n\n| ID | date | status | what | notes |\n| --- | --- | --- | --- | --- |\n" \
            "| S01 | 2026-10-27 | done | booking page | |\n"
SECURITY = "# Security check\nDate: 2026-10-27\nLevel: 3 (Standard)\nVerdict: PASS\nCounts: 0 critical, 0 high, 1 medium, 0 low\n\n" \
           "## What was checked\n- secretscan, codecheck, deps (npm), headers (http://localhost:8080), trackers\n\n" \
           "## Coverage\n| OWASP 2021 | result |\n| --- | --- |\n| A03 Injection | ok: codecheck, flowcheck |\n\n" \
           "## Findings\n### X001 [medium] Login has no rate limit\nwhere: app/login.ts:12\n\n" \
           "## Not checked\n- composer audit: composer is not installed.\n\n## Accepted risks\nNone.\n"
PARITY = "# Parity\n\nParity: 75.0 / 100\n- features: 75.0  (2 features scored, must-haves 1 of 1 done)\n\n" \
         "Every must-have feature is done.\n\n## By area, weakest first\n- email    0.0  (1 feature)\n" \
         "- booking  100.0  (1 feature)\n\n## Missing, in build order\n- [could] email: Reminders (not built)\n\n" \
         "## Behaviour differences\n| flow | original does | clone does | fix or keep |\n|---|---|---|---|\n" \
         "| F01 book a slot | 5 clicks | 3 clicks | keep |\n\n## Verdict\nDate: 2026-10-27\n" \
         "Shippable: 1 of 1 must-haves done, no open critical or high bug.\n\n## Next to build\n1. Reminders.\n"
BRAND = "# Brand\nDate: 2026-10-27\nName: Slotwise\n## Name checks (screening, not legal advice)\n" \
        "| check | Slotwise |\n|---|---|\n| EUIPO | nothing similar (2026-10-27) |\n" \
        "## Palette\naccent #0f7b6c, contrast.py exit 0.\n## Logo brief\nA slot in a week grid.\n" \
        "## Voice and the strings rewritten\nDirect, not blunt.\n## Sweep\nsweep.py exit 0 on 2026-10-27.\n"
BRAND_JSON = '{"name": "Slotwise", "avoid": ["Calendly"]}'
# The reports with no template, in the format of their skill's Output section.
COMPARE = "# Compare\nDate: 2026-10-27   Mode: clone   Apps: App A (the original), App B\n" \
          "Sample: 40 reviews from 3 sources (feedback.md). Pages read: 6, not reached: 0.\n\n" \
          "## Features\n| feature | App A | App B |\n|---|---|---|\n| book a slot | yes [1] | yes [2] |\n\n" \
          "## Pricing\n| app | plan | price | per | VAT | read | source |\n|---|---|---|---|---|---|---|\n" \
          "| App A | Standard | EUR 12 | user, month | excl. | 2026-10-27 | [1] |\n\n" \
          "## Positioning\nApp A: scheduling for sales teams. App B: for clinics.\n\n" \
          "## What they hate\n1. Reminders cost extra (App A, 12 reviews, 3 sources).\n\n" \
          "## What is missing\n1. SMS reminders (App A, App B, 9 reviews, 2 sources).\n\n" \
          "## What is unsolved\n1. Not built for hair salons (5 reviews, 2 sources: thin).\n\n" \
          "## Fix plan\n| id | fix | effort | evidence |\n|---|---|---|---|\n" \
          "| C001 | SMS reminders | M | 9 reviews |\n\n" \
          "## Angles\n1. For salons who hate paying for reminders, Slotwise sends them free. (recommended)\n\n" \
          "## Sources\n[1] https://app-a.example/features (read 2026-10-27)\n" \
          "[2] https://app-b.example/ (read 2026-10-27)\n"
AUDIT = "# Audit: Slotwise\nDate: 2026-10-27   Commit: 3f2a1c9\nProfile: laravel (detect.py)   Verdict: needs work " \
        "(0 critical, 1 high, 0 medium, 0 low)\n\n## Summary\nLaravel 11 with tests that pass. Any user can open " \
        "any invoice.\n\n## Top 5\n1. A001 [high] Any logged-in user can open any invoice (effort S)\n\n## Numbers\n" \
        "- Tests: 140 passed, 0 failed\n\n## Findings\n### A001 [high] Any logged-in user can open any invoice\n" \
        "where: app/Http/Controllers/InvoiceController.php:31\n\n## Not checked\n- composer audit: not installed\n"
INSPECT = "# Inspect: slotwise.example\nDate: 2026-10-27   Pages: 1   Mode: own app (active checks allowed)\n" \
          "Verdict: healthy (0 critical, 0 high, 1 medium, 0 low)\n\n## Summary\nThe pages load fast. One field " \
          "has no label.\n\n## What was checked\n- Pages: https://slotwise.example/. headers.py, pagecheck.py\n\n" \
          "## Findings\n### I001 [medium] The email field has no label\nwhere: https://slotwise.example/, line 40\n\n" \
          "## Not checked\n- Lighthouse: Chrome is not installed.\n"
DASHBOARD = "Level: 2 (Polished)\n# Dashboard: Slotwise\nDate: 2026-10-27\n\n## Audience\nThe salon owner, each morning.\n\n" \
            "## Numbers\n| number | definition | source | unit | period | compared with | form |\n" \
            "|---|---|---|---|---|---|---|\n| Bookings | confirmed bookings | bookings.status | count | this week | " \
            "last week | number with a sparkline |\n\n## Layout\nStandard density, 12 columns, one column at 390px.\n\n" \
            "## Charts\nBookings per day: a line, drawn by chart.py.\n\n## States\nEmpty: how to add a booking.\n\n" \
            "## Built\n| item | where | how |\n|---|---|---|\n| numbers | src/dashboard.html:2 | the tiles |\n" \
            "| chart | src/dashboard.html:4 | bookings per day |\n| table | src/dashboard.html:5 | the bookings |\n" \
            "| sparkline | src/dashboard.html:3 | in the tile |\n| period filter | src/dashboard.html:1 | GET ?week= |\n" \
            "| states | src/dashboard.html:6 | skeleton, empty, error |\n\n" \
            "## Checks\ndashcheck.py exit 0. A second user sees none of the first user's numbers.\n"
DASHBOARD_HTML = "<form method=get><select name=week></select></form>\n<dl><dt>Bookings</dt><dd>12</dd></dl>\n" \
                 "<svg role=img><title>Bookings this week</title></svg>\n<svg role=img><title>Per day</title></svg>\n" \
                 "<table><caption>Bookings</caption></table>\n<p class=empty>No bookings yet.</p>\n"
MOTION ="Level: 2 (Polished)\n# Motion: Slotwise\nDate: 2026-10-27\n\n## Direction\nCalm: motion only where a state changes.\n\n" \
         "## Inventory\n| screen | moment | motion | why |\n|---|---|---|---|\n| S03 | booking saved | toast slides " \
         "in | feedback |\n\n## Tokens\nduration fast 120ms, base 200ms; ease out.\n\n## Libraries\nNone: CSS " \
         "only.\n\n## Checks\nmotioncheck.py exit 0. Reduced motion checked at 390px and 1440px.\n"
LEVELS = json.dumps({part: {"level": level, "said": "niveau %d" % level, "at": "2026-10-27T09:00:00+00:00"}
                     for part, level in (("look", 2), ("dashboard", 2), ("test", 2), ("secure", 3))})


def levels(**chosen):
    """LEVELS with the levels CHOSEN (look=4) in place of its own."""
    return json.dumps(dict(json.loads(LEVELS), **{part: {"level": level, "said": "niveau %d" % level,
                                                         "at": "2026-10-27T09:00:00+00:00"}
                                                  for part, level in chosen.items()}))
MOTION_CSS = "@keyframes rise { from { opacity: 0; transform: translateY(8px); } }\n" \
             "@media (prefers-reduced-motion: no-preference) {\n" + "".join(
                 "  .%s { transition: opacity 200ms; }\n" % name for name in
                 ("btn", "card", "toast", "dialog", "tab", "nav", "chip", "row", "m-enter", "m-stagger", "m-lift")) + \
             "  .hero { animation: rise 400ms both; }\n  @view-transition { navigation: auto; }\n}\n"
MOTION_HTML = "<title>Slotwise</title>\n<main class=\"m-enter\"><ul class=\"m-stagger\"><li class=\"m-lift\">10:00</li></ul></main>\n"
IMPROVE = "# Improve: Slotwise\nDate: 2026-10-27   Branch: forge/improve-20261027   Started from: main at 3f2a1c9\n" \
          "Picked: A001. The user said: \"fix A001\"\n\n## To do\n## Fixed\n### A001 [high] Any logged-in user can " \
          "open any invoice\ncommit: 9b1e2f4 fix(A001): check the owner first\n\n## Skipped\n## For you\n" \
          "## Found on the way\n"  # To do ends empty; the last three may stay empty


def git(root, *args):
    subprocess.run(["git", "-C", root] + list(args), check=True, timeout=60,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def work_branch(root, branch="forge/improve-20261027"):
    """Make ROOT a git repository on BRANCH (no commits needed)."""
    git(root, "init", "-q")
    git(root, "symbolic-ref", "HEAD", "refs/heads/" + branch)


def copy_static_pack(root):
    """The static profile's container files from forge-build pack, as forge-build pack copies them, RUN.md filled in,
    in a project with the files its Dockerfile copies in."""
    for source, target in (("Dockerfile", "Dockerfile"), ("docker-compose.yml", "docker-compose.yml"),
                           ("nginx.conf", "nginx.conf"), ("dockerignore", ".dockerignore"),
                           ("env.example", ".env.example")):
        shutil.copy(os.path.join(STATIC, source), os.path.join(root, target))
    write(root, "RUN.md", filled("forge-build/templates/static/RUN.md"))
    write(root, "package.json", '{"name": "slotwise", "private": true}\n')
    write(root, "package-lock.json", '{"name": "slotwise", "lockfileVersion": 3, "packages": {}}\n')


# What each phase leaves behind when it is finished, in every mode it runs in: enough for its exit checks.
PASSING = {
    "recon": lambda root: (write(root, "forge-work/recon.md", filled("forge-research/recon-map.md")),
                           write(root, "forge-work/features.csv", FEATURES)),
    "compare": lambda root: write(root, "forge-work/compare.md", COMPARE),
    "plan": lambda root: (write(root, "forge-work/plan.md", PLAN),
                          write(root, "forge-work/features.csv", FEATURES)),
    "design": lambda root: (write(root, "forge-work/design/tokens.json", TOKENS),
                            write(root, "forge-work/design/brief.md", filled("forge-design/brief.md", Level="2 (Polished)")),
                            write(root, "forge-work/levels.json", LEVELS),
                            write(root, "forge-work/design/components.md", COMPONENTS),
                            write(root, "forge-work/design/world.md", "# The world of Slotwise\nA salon's week.\n"),
                            [write(root, "forge-work/design/concepts/%s" % name, CONCEPT)  # the board and the three
                             for name in ("index.html", "a/index.html", "b/index.html", "c/index.html")]),
    "build": lambda root: (write(root, "forge-work/build-log.md", BUILD_LOG), copy_static_pack(root),
                           write(root, "forge-work/features.csv", FEATURES), write(root, "forge-work/levels.json", LEVELS),
                           write(root, "forge-work/security.md", SECURITY),  # forge-build build Step 7 runs forge-check secure
                           shown(root, "forge-work/design/shots"),  # Steps 1 and 7: the shots before and after
                           write(root, "forge-work/design/review.md", REVIEW)),  # Step 7.4: the look review
    "dashboard": lambda root: (write(root, "forge-work/dashboard.md", DASHBOARD), write(root, "forge-work/levels.json", LEVELS),
                               write(root, "src/dashboard.html", DASHBOARD_HTML),  # Step 11: ## Built names its lines
                               shown(root, "forge-work/dashboard"), frames(root, "forge-work/dashboard/motion")),
    "motion": lambda root: (write(root, "forge-work/motion.md", MOTION), write(root, "forge-work/levels.json", LEVELS),
                            write(root, "index.html", MOTION_HTML), write(root, "src/style.css", MOTION_CSS),
                            shown(root, "forge-work/motion-shots"), frames(root, "forge-work/motion-shots/after")),
    "test": lambda root: (write(root, "forge-work/test-plan.md", TEST_PLAN), write(root, "forge-work/bugs.md", BUGS),
                          write(root, "e2e/f01-book.spec.ts", SPEC), write(root, "forge-work/levels.json", LEVELS)),
    "diff": lambda root: (write(root, "forge-work/features.csv", FEATURES), write(root, "forge-work/bugs.md", BUGS),
                          write(root, "forge-work/parity.md", PARITY)),  # Step 4 writes parity.md last
    "brand": lambda root: (write(root, "forge-work/brand.json", BRAND_JSON), write(root, "forge-work/brand.md", BRAND),
                           write(root, "forge-work/design/tokens.json", TOKENS),
                           write(root, "index.html", "<title>Slotwise</title>\n"), shown(root, "forge-work/brand/shots")),
    "launch": lambda root: (write(root, "forge-work/launch.md", filled("forge-launch/launch.md", Level="2 (Polished)")),
                            write(root, "public/og.png", "not really a PNG\n"),
                            write(root, "forge-work/brand.json", BRAND_JSON),  # forge-design brand's, for the sweep
                            write(root, "forge-work/levels.json", LEVELS),  # the look level, and the app at that level
                            write(root, "index.html", MOTION_HTML), write(root, "src/style.css", MOTION_CSS),
                            shown(root, "forge-work/launch/shots"), frames(root, "forge-work/launch/shots/motion")),
    "secure": lambda root: (write(root, "forge-work/security.md", SECURITY),
                            write(root, "forge-work/levels.json", LEVELS),
                            write(root, "forge-work/sbom.json", '{"bomFormat": "CycloneDX", "components": []}\n'),
                            write(root, "index.html", "<title>Slotwise</title>\n")),
    "pack": copy_static_pack,
    "audit": lambda root: write(root, "forge-work/audit.md", AUDIT),
    "inspect": lambda root: write(root, "forge-work/inspect.md", INSPECT),
    "improve": lambda root: (write(root, "forge-work/improve.md", IMPROVE), work_branch(root)),
}


class Checks(unittest.TestCase):
    """A temporary project folder; phasecheck.py runs in it as if from the project root."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def run_main(self, *args):
        out, err, before = io.StringIO(), io.StringIO(), os.getcwd()
        os.chdir(self.root)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = phasecheck.main(list(args))
        finally:
            os.chdir(before)
        return code, out.getvalue(), err.getvalue()

    def finish(self, *phases):
        for phase in phases:
            PASSING[phase](self.root)

    def remove(self, *names):
        for name in names:
            os.remove(os.path.join(self.root, name))

    def assert_passes(self, phase, *args):
        code, out, err = self.run_main(phase, *args)
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("PASS: every exit check of %s passes." % phase, out)
        self.assertNotIn("FAIL", out)
        return out

    def assert_fails(self, phase, *expected, args=()):
        code, out, err = self.run_main(phase, *args)
        self.assertEqual((code, err), (1, ""), out)
        self.assertIn("FAIL: %s is not finished" % phase, out)
        for text in expected:
            self.assertIn(text, out)
        return out


class TableTests(unittest.TestCase):
    def test_every_check_runs_something_that_exists(self):
        for phase, checks in phasecheck.CHECKS.items():
            for entry in checks:
                with self.subTest(phase=phase, check=entry["check"]):
                    self.assertTrue(callable(entry["run"]))
                    self.assertTrue(entry.get("why", "").startswith("forge-"), "name the skill line it rests on")
                    if entry["run"] in (phasecheck.check_run, phasecheck.check_scan):
                        script = entry["args"][0 if entry["run"] is phasecheck.check_run else 1]
                        self.assertTrue(os.path.isfile(os.path.join(ROOT, script)), script)
                    for arg in entry["args"]:  # a ../ path is a file of the pack (* for any folder)
                        if isinstance(arg, str) and arg.startswith("../"):
                            self.assertTrue(glob.glob(os.path.join(ROOT, arg[3:])), arg)

    def test_modes_and_profiles_are_known(self):
        for phase, checks in phasecheck.CHECKS.items():
            for entry in checks:
                runs_in = [mode for mode, phases in gate.MODES.items() if phase in phases] + [None]
                for mode in entry.get("modes", []):
                    self.assertIn(mode, runs_in, "%s: %s does not run in %s mode" % (phase, entry["check"], mode))
                for profile in entry.get("profiles", []):
                    self.assertIn(profile, phasecheck.PROFILES)

    def test_when_is_a_path_in_the_project(self):
        """A path, or [FILE, SECTION, START]: a file of the project, a ## heading of it and the start of a line."""
        for phase, checks in phasecheck.CHECKS.items():
            for entry in [entry for entry in checks if "when" in entry]:
                with self.subTest(phase=phase, check=entry["check"]):
                    when = entry["when"]
                    path = when if isinstance(when, str) else when[0]
                    self.assertFalse(os.path.isabs(path) or ".." in path.split("/"), when)
                    if not isinstance(when, str):
                        self.assertEqual((len(when), all(isinstance(part, str) and part.strip() for part in when)),
                                         (3, True), when)

    def test_every_fresh_report_is_a_file_its_phase_checks(self):
        for phase, name in phasecheck.FRESH.items():
            self.assertIn(name, [entry["args"][0] for entry in phasecheck.CHECKS[phase]])

    def test_the_modes_are_the_gates(self):
        self.assertEqual(set(phasecheck.MODES), set(gate.MODES))


class PhaseTests(Checks):
    def test_every_phase_passes_in_every_mode_it_runs_in(self):
        for phase in phasecheck.CHECKS:
            if phase == "improve" and not HAS_GIT:
                continue  # its check runs gitguard.py, which needs git
            for mode in [mode for mode, phases in gate.MODES.items() if phase in phases] + [None]:
                with self.subTest(phase=phase, mode=mode):
                    shutil.rmtree(self.root, ignore_errors=True)
                    os.makedirs(self.root)
                    self.finish(phase)
                    self.assert_passes(phase, *(["--mode", mode] if mode else []))

    def test_every_phase_fails_in_an_empty_project(self):
        for phase in phasecheck.CHECKS:
            with self.subTest(phase=phase):
                self.assert_fails(phase)

    def test_a_missing_file_is_named_once(self):
        out = self.assert_fails("plan", "forge-work/plan.md is missing", "forge-work/features.csv is missing")
        self.assertEqual(out.count("forge-work/plan.md is missing"), 1)
        out = self.assert_fails("recon")
        self.assertEqual(out.count("forge-work/recon.md is missing"), 1)

    def test_a_failure_says_which_skill_line_it_rests_on(self):
        out = self.assert_fails("diff", "forge-work/parity.md is missing")
        self.assertIn("why: forge-check diff, Step 4", out)
        self.finish("compare")
        self.assertNotIn("why:", self.assert_passes("compare"))

    def test_an_empty_file_is_not_enough(self):
        write(self.root, "forge-work/compare.md", " \n\n")
        self.assert_fails("compare", "FAIL  forge-work/compare.md is empty")
        write(self.root, "forge-work/build-log.md", "")
        self.assert_fails("build")

    def test_a_folder_where_a_file_should_be(self):
        os.makedirs(os.path.join(self.root, "forge-work", "plan.md"))
        self.assert_fails("plan")

    def test_recon_features(self):
        self.finish("recon")
        write(self.root, "forge-work/features.csv", FEATURES.replace(",must,", ",should,"))
        self.assert_fails("recon", "0 row(s) with priority must")
        write(self.root, "forge-work/features.csv", "feature;area;priority;original;clone;notes\nA;b;must;yes;no;\n")
        self.assert_fails("recon", "is not exactly feature,area,priority,original,clone,notes")
        write(self.root, "forge-work/features.csv", "")
        self.assert_fails("recon", "is not exactly")
        write(self.root, "forge-work/features.csv", "﻿" + FEATURES.replace("\n", "\r\n"))  # Excel's way
        self.assert_passes("recon")
        write(self.root, "forge-work/features.csv", 'feature,area,priority,original,clone,notes\n"Book, pay",x,must,yes,no,\n')
        self.assert_passes("recon")
        write(self.root, "forge-work/features.csv", FEATURES + '"%s",x,must,yes,no,\n' % ("a" * 200000))
        self.assert_fails("recon", "workcheck.py features forge-work/features.csv --theirs --json exits 2: it could "
                                   "not check", "field larger than field limit")  # too big for the csv module
        self.remove("forge-work/recon.md")
        self.assert_fails("recon", "forge-work/recon.md is missing")

    def test_every_feature_row_follows_the_contract(self):
        """Values parity.py refuses (exit 2) fail at recon and plan already, not six phases later."""
        self.finish("recon", "plan")
        header = "feature,area,priority,original,clone,notes\n"
        for rows, expected in (
                ("Create poll,create,MUST!,maybe,done,\n", [
                    "line 2: priority 'MUST!' is not one of must, should, could",
                    "line 2: original 'maybe' is not one of yes, no",
                    "line 2: clone 'done' is not one of yes, partial, no, skip"]),
                ("Grid,s2,must,yes,yes please,\n", ["line 2: clone 'yes please'"]),
                ("Grid,must,yes\n", ["line 2 has 3 cells, not 6"]),
                ("Book, pay,x,must,yes,no,\n", ["line 2 has 7 cells, not 6: put text with a comma in double quotes"]),
                (",x,must,yes,no,\n", ["line 2: the feature name is empty"]),
                ("Book,x,must,yes,no,\nPay,x,should,yes,skip,\n", ["line 3: Pay is skipped without a reason"])):
            with self.subTest(rows=rows):
                write(self.root, "forge-work/features.csv", header + rows)
                for phase in ("recon", "plan"):
                    self.assert_fails(phase, "forge-work/features.csv breaks the contract in", *expected)
        write(self.root, "forge-work/features.csv", header + "Book,x,Must,YES,No,\nPay,x,should,,,\n")
        self.assert_passes("recon")  # case and empty cells as parity.py reads them

    def test_a_skipped_or_own_must_have_is_not_one_to_build_from_the_original(self):
        self.finish("recon", "plan")
        write(self.root, "forge-work/features.csv",
              "feature,area,priority,original,clone,notes\nExisting polls,data,must,yes,skip,their data\n")
        self.assert_fails("recon", "0 row(s) with priority must, not skipped")
        write(self.root, "forge-work/features.csv",
              "feature,area,priority,original,clone,notes\nSMS reminders,booking,must,no,no,C003: 23 reviews\n")
        self.assert_fails("recon", "0 row(s) with priority must, not skipped, that the original has")
        self.assert_passes("plan")  # idea mode: every row is the user's own (original no)

    def test_build_needs_the_must_haves_built(self):
        """Idea mode has no diff phase: the build gate is the only one that reads the clone column."""
        self.finish("build")
        header = "feature,area,priority,original,clone,notes\n"
        for rows, expected in (
                ("Book,x,must,no,no,\nPay,x,must,no,yes,\n", "line 2: Book, clone no"),
                ("Book,x,must,yes,,\nPay,x,must,no,yes,\n", "line 2: Book, clone empty"),
                ("Book,x,must,no,partial,\nPay,x,must,no,yes,\n", "line 2: Book, clone partial, no note"),
                ("Book,x,must,no,skip,their data\nPay,x,should,no,yes,\n", "0 of 1 must-have(s) built"),
                ("Book,x,must,no,maybe,\n", "line 2: clone 'maybe'")):
            with self.subTest(rows=rows):
                write(self.root, "forge-work/features.csv", header + rows)
                self.assert_fails("build", expected)
        write(self.root, "forge-work/features.csv", header + "Book,x,must,no,yes,\n"
              "Pay,x,must,no,partial,no refunds yet\nOld data,x,must,yes,skip,their data\nTeams,x,could,no,no,\n")
        out = self.assert_passes("build")
        self.assertIn("1 of 3 must-have(s) built, the rest partial or skipped with a note", out)
        self.remove("docker-compose.yml")
        self.assert_fails("build", "compose.yaml or compose.yml or docker-compose.yaml or docker-compose.yml "
                                   "is missing")

    def test_plan_lines(self):
        self.finish("plan")
        write(self.root, "forge-work/plan.md", template("forge-plan", "plan.md"))
        self.assert_fails("plan", "needs exactly one line `Profile: laravel|django|next|static`",
                          "needs exactly one line `PWA: yes|no`")
        body = PLAN.split("\n## ", 1)[1]
        for head in ("Profile: Next\nPWA: no\n", "Profile: next\nPWA: maybe\n", "**Profile:** next\nPWA: no\n",
                     "Profile: next\nProfile: django\nPWA: no\n", "Profile: next (Next.js)\nPWA: no\n", "PWA: no\n",
                     "```\nProfile: laravel\nPWA: no\n```\n", "<!--\nProfile: next\n-->\nPWA: no\n",
                     "**Profile:** wordpress\nProfile: next\nPWA: no\n", "## profile: wordpress\nProfile: next\nPWA: no\n"):
            with self.subTest(head=head):
                write(self.root, "forge-work/plan.md", "# Plan\n" + head + "\n## " + body)
                self.assert_fails("plan")
        for profile in ("laravel", "django", "next", "static"):
            write(self.root, "forge-work/plan.md", "# Plan\nProfile:  %s \r\nPWA: yes\r\n\n## %s" % (profile, body))
            self.assert_passes("plan")
        profile_page = PLAN.replace("PWA: no", "PWA: no\n- Profile page: the user edits a name")
        write(self.root, "forge-work/plan.md", profile_page)
        self.assert_passes("plan")  # a list item about a profile page is not a Profile line

    def test_idea_mode_plan_needs_the_feature_list(self):
        self.finish("plan")
        self.remove("forge-work/features.csv")
        self.assert_fails("plan", "forge-work/features.csv is missing", args=("--mode", "idea"))

    def test_design_contrast_and_components(self):
        self.finish("design")
        write(self.root, "forge-work/design/tokens.json",
              '{"color": {"bg": "#ffffff", "text": "#bbbbbb"}, "pairs": [["text", "bg"]]}')
        shown = phasecheck.PYTHON + " ../forge-design/contrast.py forge-work/design/tokens.json"
        out = self.assert_fails("design", "forge-work/design/tokens.json parses", shown + " exits 1")
        self.assertIn("text", out.split("exits 1")[1])  # contrast.py's own words are shown
        write(self.root, "forge-work/design/tokens.json", '{"color": ')
        self.assert_fails("design", "forge-work/design/tokens.json cannot be read", "exits 2: it could not check")
        write(self.root, "forge-work/design/tokens.json", "[]")
        self.assert_fails("design", "is not a JSON object")
        write(self.root, "forge-work/design/tokens.json", "[" * 100000 + "]" * 100000)
        self.assert_fails("design", "forge-work/design/tokens.json cannot be read")  # too deep, not a traceback
        self.finish("design")
        self.remove("forge-work/design/components.md")
        self.assert_fails("design", "forge-work/design/components.md is missing")

    def test_test_needs_no_open_serious_bug(self):
        self.finish("test")
        write(self.root, "forge-work/bugs.md", BUGS + "\n## B002 [high] [open] Booking fails\nsteps: x\n")
        self.assert_fails("test", "bugs.py forge-work/bugs.md exits 1: it found problems", "B002")
        write(self.root, "forge-work/bugs.md", BUGS.replace("[low]", "[high]").replace("[open]", "[fixed]"))
        self.assert_passes("test")
        self.remove("forge-work/bugs.md")
        self.assert_fails("test", "exits 2: it could not check")

    def test_long_script_output_is_cut_short(self):
        self.finish("test")
        bugs = "".join("## B%03d [critical] [open] Bug number %d\n" % (n, n) for n in range(1, 31))
        write(self.root, "forge-work/bugs.md", "# Bugs\n\n" + bugs)
        out = self.assert_fails("test", "more lines: run it to see them")
        self.assertLess(len(out.splitlines()), 26)

    def test_diff_needs_every_must_have(self):
        self.finish("diff")
        write(self.root, "forge-work/features.csv", FEATURES.replace("must,yes,yes", "must,yes,partial"))
        self.assert_fails("diff", "parity.py forge-work/features.csv exits 1")

    def test_launch_sweeps_its_pages_for_the_names_to_avoid(self):
        """Launch writes the public pages after brand ran its sweep: the original's or a rival's name on one
        of them fails launch too. brand.json is forge-design brand's, which comes before launch in both its modes."""
        self.finish("launch")
        write(self.root, "pricing.html", "<p>Switching from Calendly? Bring your slots along.</p>\n")
        out = self.assert_fails("launch", "sweep.py . --config forge-work/brand.json exits 1: it found problems",
                                "A name to avoid: Calendly")
        self.assertIn("why: forge-launch, Also for this skill: no names, logos or screenshots of competitors", out)
        self.remove("pricing.html")
        self.assertIn("sweep.py . --config forge-work/brand.json exits 0", self.assert_passes("launch"))
        self.remove("forge-work/brand.json")
        self.assert_fails("launch", "sweep.py . --config forge-work/brand.json exits 2: it could not check")

    def test_compare_audit_inspect_and_improve_have_their_sections(self):
        """These reports have no template: the gate checks the sections their skill's Output names. One line
        fails, and so do the headings alone. improve.md needs Fixed only (To do ends empty; Skipped, For you
        and Found on the way are often empty), and a ### finding there is that section's text."""
        sections = {"compare": "Features, ## Pricing, ## Positioning, ## What they hate, ## What is missing, "
                               "## What is unsolved, ## Fix plan, ## Angles, ## Sources",
                    "audit": "Summary, ## Top 5, ## Numbers, ## Findings, ## Not checked",
                    "inspect": "Summary, ## What was checked, ## Findings, ## Not checked", "improve": "Fixed"}
        for phase, titles in sections.items():
            if phase == "improve" and not HAS_GIT:
                continue  # its check runs gitguard.py, which needs git
            with self.subTest(phase=phase):
                shutil.rmtree(self.root, ignore_errors=True)
                os.makedirs(self.root)
                self.finish(phase)
                name = "forge-work/%s.md" % phase
                write(self.root, name, "# %s: Slotwise\nDate: 2026-10-27\n" % phase.title())
                out = self.assert_fails(phase, "%s has no ## %s" % (name, titles))
                self.assertIn("why: %s, Output" % gate_skill(phase), out)
                write(self.root, name, "# %s\n\n" % phase.title() + "".join("## %s\n" % title
                                                                            for title in titles.split(", ## ")))
                self.assert_fails(phase, "%s has no text of its own under ## %s" % (name, titles))
        if HAS_GIT:
            write(self.root, "forge-work/improve.md", "# Improve\n## To do\n## Fixed\n### A001 [high] Any user "
                                                      "can open any invoice\n## Skipped\n## For you\n")
            self.assert_passes("improve")
            write(self.root, "forge-work/improve.md", IMPROVE.replace("## To do\n", "## To do\n### A003 [high] "
                                                                       "Passwords stored with MD5\n"))
            self.assert_fails("improve", "forge-work/improve.md has 1 item(s) left under ## To do",
                              "why: forge-improve, Output")

    def test_the_report_in_each_skills_output_passes(self):
        """The example in forge-check audit's, forge-check inspect's and forge-improve's Output passes as it is: its
        findings are ### headings under ## Findings or ## Fixed (forge-improve's look item once the report it names,
        at the level it says, and Step 4's shots are there). forge-research compare's shows only the parts with a
        fixed shape; with its other sections, in the order its Output gives, it passes too."""
        for phase in ("audit", "inspect", "improve"):
            if phase == "improve" and not HAS_GIT:
                continue  # its check runs gitguard.py, which needs git
            with self.subTest(phase=phase):
                self.finish(phase)
                write(self.root, "forge-work/%s.md" % phase, example(phase))
                if phase == "improve":
                    write(self.root, "forge-work/levels.json", levels(look=4))
                    write(self.root, "forge-work/design/redesign.md", "# Redesign: Slotwise\nLevel: 4 (Showpiece)\n")
                    shown(self.root, "forge-work/improve/shots")
                    # design at level 4 builds motion and 3D too (forge-improve Step 2): its report and the app
                    write(self.root, "forge-work/motion.md", MOTION.replace("Level: 2 (Polished)", "Level: 4 (Showpiece)"))
                    for name, text in sample_app(4, 20).items():
                        write(self.root, name, text)
                    shown(self.root, "forge-work/improve/shots", parts=("before-frames", "after-frames"),
                          name="home-390-f2.png")
                    for kind in "fs":  # its proof: "--moves on home: something moves", the scene's frames too
                        frames(self.root, "forge-work/improve/shots/after-frames", kind=kind)
                self.assert_passes(phase)
                if phase == "improve":  # with that motion as its own item, as Step 2 asks, the example passes too
                    text = example(phase)
                    write(self.root, "forge-work/improve.md", text if "### motion" in text else text.replace(
                        "## Skipped\n", "### motion [look] Motion at level 4, with the redesign\nreport: "
                                        "forge-work/motion.md\n## Skipped\n"))
                    out = self.assert_passes(phase)
                    self.assertIn("forge-design/motioncount.py . --level auto exits 0", out)
        others = ("Positioning", "What they hate", "What is missing", "What is unsolved", "Fix plan", "Angles")
        write(self.root, "forge-work/compare.md", example("compare").replace(
            "## Sources", "".join("## %s\n1. Written for this app.\n\n" % title for title in others) + "## Sources"))
        self.assert_passes("compare")

    def test_dashboard_names_where_each_item_of_its_level_is_built(self):
        """A Level line and a numbers table are not a level 4 or 5 dashboard: ## Built must tie each item of the
        level to a file and line of the app, in dashboard.md and in each dashboard-<screen>.md next to it."""
        self.finish("dashboard")
        self.assert_passes("dashboard")
        built = DASHBOARD[DASHBOARD.index("## Built"):DASHBOARD.index("## Checks")]
        write(self.root, "forge-work/dashboard.md", DASHBOARD.replace(built, ""))
        self.assert_fails("dashboard", "forge-work/dashboard.md has no ## Built", "why: forge-design dashboard, Output")
        write(self.root, "forge-work/dashboard.md", DASHBOARD.replace("src/dashboard.html:4", "Chart.tsx:4"))
        self.assert_fails("dashboard", "dashbuilt.py forge-work/dashboard.md --level auto exits 1",
                          "why: forge-design dashboard, Step 11: dashbuilt.py")
        write(self.root, "forge-work/dashboard.md", DASHBOARD)
        write(self.root, "forge-work/dashboard-admin.md", DASHBOARD.replace("| sparkline |", "| tiles |"))
        self.assert_fails("dashboard", "dashbuilt.py forge-work/dashboard.md --level auto exits 1")
        write(self.root, "forge-work/dashboard-admin.md", DASHBOARD)
        self.assert_passes("dashboard")
        write(self.root, "forge-work/levels.json", levels(dashboard=4))
        self.assert_fails("dashboard", "dashbuilt.py forge-work/dashboard.md --level auto exits 1")

    def test_brand(self):
        self.finish("brand")
        write(self.root, "src/footer.html", "<p>Powered by Calendly</p>\n")
        self.assert_fails("brand", "sweep.py . --config forge-work/brand.json exits 1")
        self.remove("src/footer.html")
        for text, wrong in (('{"name": "Slotwise", "avoid": []}', '"avoid"'), ('{"avoid": ["Calendly"]}', '"name"'),
                            ('{"name": " ", "avoid": ["Calendly"]}', '"name"'),
                            ('{"name": ["Slotwise"], "avoid": ["Calendly"]}', '"name" is missing, empty or not a text'),
                            ('{"name": 5, "avoid": ["Calendly"]}', '"name"'),
                            ('{"name": true, "avoid": ["Calendly"]}', '"name"'),
                            ('{"name": "Slotwise", "avoid": "Calendly"}', '"avoid" is missing, empty or not a list')):
            with self.subTest(text=text):
                write(self.root, "forge-work/brand.json", text)
                self.assert_fails("brand", wrong)

    def test_secure(self):
        self.finish("secure")
        for text in ("Verdict: FAIL\n", "# Security\n", "Verdict: PASS\nVerdict: FAIL\n", "verdict: pass\n",
                     "> Verdict: PASS\n", "**Verdict:** PASS\n"):
            with self.subTest(text=text):
                write(self.root, "forge-work/security.md", SECURITY.replace("Verdict: PASS\n", text))
                self.assert_fails("secure", "Verdict: PASS")
        write(self.root, "forge-work/security.md", SECURITY)
        write(self.root, "app/config.php", "$key = '%s';\n" % ("sk_" + "live_" + "a" * 24))  # built at runtime
        out = self.assert_fails("secure", "secretscan.py . exits 1")
        self.assertNotIn("a" * 24, out)  # secretscan masks it, and so the gate never shows it

    def test_a_pass_in_a_comment_or_code_block_or_next_to_a_fail_does_not_count(self):
        self.finish("secure")
        for text in ("<!--\nVerdict: PASS\n-->\n", "<!-- Verdict: PASS\n", "```\nVerdict: PASS\n```\n",
                     "   ````\nVerdict: PASS\n```\n", "~~~\nVerdict: PASS\n~~~\nVerdict - FAIL\n",
                     "**Verdict:** FAIL\nVerdict: PASS\n", "verdict: FAIL\nVerdict: PASS\n",
                     "## Verdict: FAIL\nVerdict: PASS\n", "> Verdict: FAIL\nVerdict: PASS\n",
                     "Verdict : FAIL\nVerdict: PASS\n", "__Verdict__: FAIL\nVerdict: PASS\n"):
            with self.subTest(text=text):
                write(self.root, "forge-work/security.md", SECURITY.replace("Verdict: PASS\n", text))
                self.assert_fails("secure", "needs exactly one line `Verdict: PASS`")
        report = template("forge-check", "steps/secure.md").split("```markdown\n")[1].split("```\n")[0]
        report = re.sub(r"\d+ high", "0 high", report.replace("Verdict: FAIL", "Verdict: PASS"))
        report = re.sub(r"(?m)^Level: .*$", "Level: 3 (Standard)", report)  # the level on record in LEVELS
        write(self.root, "forge-work/security.md", report)
        self.assert_passes("secure")  # forge-check secure's own report format passes

    def test_pack(self):
        self.finish("pack")
        os.rename(os.path.join(self.root, "docker-compose.yml"), os.path.join(self.root, "compose.yaml"))
        self.assert_passes("pack")
        self.remove("compose.yaml")
        self.assert_fails("pack", "compose.yaml or compose.yml or docker-compose.yaml or docker-compose.yml is missing")
        self.finish("pack")
        self.remove(".dockerignore")
        self.assert_fails("pack", ".dockerignore is missing", "packcheck.py . exits 1")

    def test_pack_scans_for_secrets_again(self):
        self.finish("secure", "pack")
        self.assert_passes("pack")
        write(self.root, "app.js", 'const STRIPE_KEY = "%s";\n' % ("sk_" + "live_" + "51HxYzAbCdEfGhIjKlMnOp" * 2))
        self.assert_fails("pack", "secretscan.py . exits 1")

    @unittest.skipUnless(HAS_GIT, "git is not installed")
    def test_improve_needs_a_work_branch(self):
        self.finish("improve")
        git(self.root, "symbolic-ref", "HEAD", "refs/heads/main")
        self.assert_fails("improve", "gitguard.py . exits 1", "On the main branch")

    def test_json_output(self):
        self.finish("plan")
        write(self.root, "forge-work/plan.md", PLAN.replace("PWA: no", "PWA: maybe"))
        code, out, _ = self.run_main("plan", "--json", "--mode", "idea")
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual((data["phase"], data["mode"], data["ok"]), ("plan", "idea", False))
        self.assertEqual([item["ok"] for item in data["checks"]], [True, True, True, True, True, False])
        self.assertEqual(set(data["checks"][0]), {"ok", "what", "output"})
        self.assertEqual(data["checks"][-1]["output"][-1][:20], "why: forge-plan, Ste")

    def test_unknown_phase_mode_or_time(self):
        for args in (["deploy"], ["secure", "--since", "yesterday"], ["secure", "--since", "2026-13-01T00:00:00"],
                     ["test", "--mode", "fast"]):
            with self.subTest(args=args), self.assertRaises(SystemExit) as stop, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.run_main(*args)
            self.assertEqual(stop.exception.code, 2)


class FindingTests(Checks):
    """Each finding of the dogfood run: what the gate let through, and now fails, with a message that
    says what is missing and how to fix it."""

    def test_n1_placeholders_in_code_blocks_and_over_two_lines(self):
        """recon.md with only the placeholders outside code filled in, and plan.md with only the one-line
        ones outside code: both passed. A template's placeholders count everywhere but in comments now."""
        self.finish("recon", "plan")
        write(self.root, "forge-work/recon.md", outside_code(template("forge-research", "recon-map.md")))
        out = self.assert_fails("recon", "forge-work/recon.md still has",
                                "placeholder(s) of ../forge-research/recon-map.md", "{{goal}}", "{{Entity}}",
                                "{{high | medium | guess}}")
        self.assertIn("Write this app's own facts in their place", out)
        plan = re.sub(r"(?m)^Profile: x$", "Profile: static", outside_code(template("forge-plan", "plan.md")))
        write(self.root, "forge-work/plan.md", plan.replace("PWA: x", "PWA: no"))
        out = self.assert_fails("plan", "forge-work/plan.md still has 4 placeholder(s) of ../forge-plan/plan.md",
                                "{{Two or three lines", "{{Clone mode:", "{{F01 book an appointment",
                                "{{the first migration")
        self.assertIn("plan.md says Profile: static", out)

    def test_n1_a_rewrapped_or_windows_placeholder_still_counts(self):
        self.finish("plan")
        why = re.search(r"\{\{Two.*?\}\}", template("forge-plan", "plan.md"), re.S).group(0)
        write(self.root, "forge-work/plan.md", PLAN.replace("## Why\n", "## Why\n" + " ".join(why.split()) + "\n"))
        self.assert_fails("plan", "1 placeholder(s)", "{{Two or three lines")
        write(self.root, "forge-work/plan.md", (PLAN + "\n" + why + "\n").replace("\n", "\r\n"))
        self.assert_fails("plan", "1 placeholder(s)")

    def test_n1_braces_in_code_comments_and_templating_are_not_placeholders(self):
        self.finish("plan")
        write(self.root, "forge-work/plan.md", PLAN + "\n<!-- Replace every {{...}} and {{app name}}. -->\n"
              "Greeting in Blade: `{{ $user->name }}`, in Django {{ user.first_name }}.\n\n"
              "```blade\n<h1>{{$title}}</h1>\n```\n\n~~~tsx\n<div style={{color: 'red'}} />\n~~~\n")
        self.assert_passes("plan")

    def test_n2_a_recon_with_no_sections(self):
        self.finish("recon")
        write(self.root, "forge-work/recon.md", "# Recon: x (web)\n")
        out = self.assert_fails("recon", "forge-work/recon.md has no ## Sources, ## Core loop, ## Screens, "
                                         "## Reference screenshots, ## Flows")
        self.assertIn("why: forge-research recon, Output: recon.md from the template, every section filled in", out)
        recon = filled("forge-research/recon-map.md")
        only_the_example = recon.replace("## Components\n\nSlotwise: written for this app.", "## Components")
        write(self.root, "forge-work/recon.md", only_the_example)  # the template's Button row and nothing else
        self.assert_fails("recon", "no text of its own under ## Components")
        write(self.root, "forge-work/recon.md", recon.replace(
            "## Components\n\nSlotwise: written for this app.", "## Components\n<!-- later -->"))
        self.assert_fails("recon", "no text of its own under ## Components")
        write(self.root, "forge-work/recon.md", recon.replace(
            "## Components\n\nSlotwise: written for this app.", "## Components\n\nnone seen"))
        self.assert_passes("recon")

    def test_n12_a_design_from_the_untouched_templates(self):
        """Only the <a|b> choices of components.md replaced, tokens.json as the template: it passed."""
        self.finish("design")
        components = template("forge-design", "components.md")
        for choice in re.findall(r"<[^<>\n]*\|[^<>\n]*>", components):
            components = components.replace(choice, choice[1:-1].split("|")[0].strip())
        write(self.root, "forge-work/design/components.md", components)
        out = self.assert_fails("design", "<name>", "<licence>", "<the theme file for the profile", "<the file above>",
                                "<path>", "<#hex>", "no text of its own under ## Fonts and icons, ## Original brand "
                                "colours, ## Components", args=("--mode", "clone"))
        self.assertNotIn("<role>", out)  # the Theme block maps tokens by name: its <role> stays (N21)
        self.finish("design")
        write(self.root, "forge-work/design/tokens.json", template("forge-design", "tokens.json"))
        self.assert_fails("design", "forge-work/design/tokens.json still holds every value of "
                                    "../forge-design/tokens.json")
        notes = dict(json.loads(TOKENS), _notes="estimated: surface, border")
        write(self.root, "forge-work/design/tokens.json", json.dumps(notes))
        self.assert_passes("design")

    def test_n12_clone_mode_lists_the_original_brand_colours(self):
        self.finish("design")
        components = COMPONENTS.replace(
            "## Original brand colours\n\nSlotwise: written for this app.", "## Original brand colours")
        components = re.sub(r"(?m)^- #hex \(their accent\)$", "", components)
        write(self.root, "forge-work/design/components.md", components)
        self.assert_fails("design", "no text of its own under ## Original brand colours", args=("--mode", "clone"))
        self.assert_passes("design", "--mode", "idea")  # idea mode has no original

    def test_n12_the_theme_command_is_filled_in(self):
        """forge-design design Step 3 fills in the theme.py command that forge-build build and forge-design brand run."""
        self.finish("design")
        command = next(line for line in template("forge-design", "components.md").split("\n")
                       if line.startswith("Command:"))
        components = re.sub(r"(?m)^Command:.*$", lambda _: command, COMPONENTS)
        write(self.root, "forge-work/design/components.md", components)
        self.assert_fails("design", "<the file above>", "<4|3|no>")

    def test_n16_a_build_with_no_app(self):
        self.finish("build")
        write(self.root, "forge-work/build-log.md", "# Build log\n")
        write(self.root, "docker-compose.yml", "services: {}\n")
        self.remove("forge-work/security.md")
        self.assert_fails("build", "forge-work/build-log.md has no table with the columns status and what",
                          "composecheck.py . exits 2: it could not check", "forge-work/security.md is missing",
                          "why: forge-build build, Step 7: /forge-check secure has run")
        write(self.root, "forge-work/build-log.md", BUILD_LOG.split("| S01")[0])
        self.assert_fails("build", "build-log.md has no table with the columns status and what and a row")

    def test_n18_a_clone_that_shares_a_sentence_with_the_original(self):
        """The clone shared runs of words with the original and every gate passed. In clone mode build, brand
        and launch run copycheck.py when forge-research recon kept the original's text in forge-work/original-text/: a
        shared run of 6+ words fails until it is rewritten or, with the user's OK, in copy-allow.txt. Without
        the kept text the line says it skipped; idea mode, which has no original, never runs it."""
        sentence = "<main>\n<p>Zo zie je elke dag wat er moet gebeuren.</p>\n</main>\n"
        for phase, why in (("build", "why: forge-build build, Step 7"), ("brand", "why: forge-design brand, Step 6"),
                           ("launch", "why: forge-launch, Also for this skill")):
            with self.subTest(phase=phase):
                shutil.rmtree(self.root, ignore_errors=True)
                os.makedirs(self.root)
                self.finish(phase)
                write(self.root, "src/home.html", sentence)
                out = self.assert_passes(phase, "--mode", "clone")
                self.assertIn("ok    forge-build/copycheck.py skipped: no forge-work/original-text/", out)
                write(self.root, "forge-work/original-text/source-1.txt",
                      "# kept by pagetext.py\nzo zie je elke dag wat er moet gebeuren met je planten\n")
                self.assert_fails(phase, "copycheck.py exits 1: it found problems",
                                  '9 words in a row from the original: "zo zie je elke dag wat er moet gebeuren"',
                                  "where: %s:2" % os.path.join("src", "home.html"), why, args=("--mode", "clone"))
                for mode in ("idea", None):
                    self.assertNotIn("copycheck", self.assert_passes(phase, *(["--mode", mode] if mode else [])))
                write(self.root, "forge-work/copy-allow.txt", "# OK from the user\nZo zie je elke dag wat er moet gebeuren\n")
                self.assertIn("copycheck.py exits 0", self.assert_passes(phase, "--mode", "clone"))
        write(self.root, "forge-work/original-text/source-1.txt", "# kept by pagetext.py: nothing\n")
        self.assert_fails("launch", "copycheck.py exits 2: it could not check", "holds no text of the original",
                          args=("--mode", "clone"))

    def test_n25_a_test_phase_with_no_tests(self):
        self.finish("test")
        shutil.rmtree(os.path.join(self.root, "e2e"))
        for mode in ("clone", "idea"):
            self.assert_fails("test", "no end-to-end spec: no file like e2e/**/*.spec.* or e2e/**/*.test.*",
                              "why: forge-check test, Step 3: from level 2, one spec per flow in e2e/", args=("--mode", mode))
        write(self.root, "e2e/node_modules/pkg/x.spec.ts", SPEC)
        self.assert_fails("test", "no end-to-end spec", args=("--mode", "clone"))
        write(self.root, "e2e/flows/f01.test.js", SPEC)
        self.assert_passes("test", "--mode", "clone")

    def test_n25_results_name_a_bug_that_is_there(self):
        self.finish("test")
        for result, expected in (("fail B009", "F01-E1: fail B009, but there is no ## B009 in forge-work/bugs.md"),
                                 ("fail", "F01-E1: fail names no bug"), ("skipped", "F01-E1: skipped, but not why"),
                                 ("done", "F01-E1: done")):
            with self.subTest(result=result):
                write(self.root, "forge-work/test-plan.md", TEST_PLAN.replace("fail B001", result))
                self.assert_fails("test", "result(s) that are not pass, fail B003", expected)
        write(self.root, "forge-work/test-plan.md", TEST_PLAN.replace("fail B001", "failed B001 (open, low)"))
        self.assert_passes("test")

    def test_n25_improve_mode_tests_the_users_app_its_own_way(self):
        """Improve mode: no e2e/ folder is needed. The app's own Playwright setup counts, and a plan that
        marks no case e2e needs no spec at all (an API tested with its unit tests)."""
        self.finish("test")
        shutil.rmtree(os.path.join(self.root, "e2e"))
        self.assert_fails("test", "marks 2 case(s) e2e, but there is no file like e2e/**/*.spec.*",
                          args=("--mode", "improve"))
        write(self.root, "playwright.config.ts", "export default {};\n")
        self.assert_passes("test", "--mode", "improve")
        self.remove("playwright.config.ts")
        write(self.root, "forge-work/test-plan.md", TEST_PLAN.replace("| e2e |", "| unit |"))
        self.assert_passes("test", "--mode", "improve")
        self.assert_passes("test")  # no mode known: as lenient as improve mode
        self.assert_fails("test", "no end-to-end spec", args=("--mode", "idea"))

    def test_improve_mode_finds_the_apps_playwright_setup_in_any_folder(self):
        """A monorepo keeps its Playwright setup next to the app it tests (apps/web/playwright.config.ts, the
        specs beside it), and forge-check test adds the specs there. One inside node_modules is not the app's."""
        self.finish("test")
        shutil.rmtree(os.path.join(self.root, "e2e"))
        write(self.root, "node_modules/some-kit/playwright.config.ts", "export default {};\n")
        self.assert_fails("test", "marks 2 case(s) e2e, but there is no file like", args=("--mode", "improve"))
        write(self.root, "apps/web/playwright.config.ts", "export default { testDir: 'tests' };\n")
        write(self.root, "apps/web/tests/invoice-owner.spec.ts", SPEC)
        out = self.assert_passes("test", "--mode", "improve")
        self.assertIn("marks 2 case(s) e2e; a spec: apps/web/playwright.config.ts", out)

    def test_n26_a_diff_with_only_the_feature_list(self):
        self.finish("diff")
        self.remove("forge-work/parity.md", "forge-work/bugs.md")
        self.assert_fails("diff", "forge-work/parity.md is missing", "bugs.py forge-work/bugs.md exits 2")
        self.finish("diff")
        write(self.root, "forge-work/parity.md", PARITY.split("## Behaviour")[0])
        self.assert_fails("diff", "has no ## Behaviour differences, ## Verdict, ## Next to build")
        write(self.root, "forge-work/parity.md", "# Parity\n\n## Behaviour" + PARITY.split("## Behaviour")[1])
        self.assert_fails("diff", "forge-work/parity.md has no ## By area, ## Missing")  # parity.py's part, by hand

    def test_n26_a_bug_from_the_behaviour_walk_keeps_diff_open(self):
        self.finish("diff")
        walk = "\n## B014 [high] [open] Reschedule link opens a not-found page\n"  # found in the behaviour walk
        write(self.root, "forge-work/bugs.md", BUGS + walk)
        self.assert_fails("diff", "bugs.py forge-work/bugs.md exits 1: it found problems", "B014")

    def test_n26_reference_screenshots_are_compared(self):
        self.finish("diff")
        write(self.root, "forge-work/screens/S07.png", "png")
        write(self.root, "forge-work/screens/S07-mobile.png", "png")
        self.assert_fails("diff", "forge-work/screens has 2 reference screenshot(s) and no .diff.json")
        write(self.root, "forge-work/screens/S07.diff.json", "")
        self.assert_fails("diff", "S07.diff.json is not the JSON imgdiff.py writes")
        write(self.root, "forge-work/screens/S07.diff.json", '{"score": 91.2}')
        self.assert_passes("diff")

    def test_n32_a_brand_before_any_brand_work(self):
        self.finish("brand")
        self.remove("forge-work/brand.md", "forge-work/design/tokens.json")
        write(self.root, "index.html", "<title>Waterplanner</title>\n")
        self.assert_fails("brand", "forge-work/brand.md is missing",
                          "contrast.py forge-work/design/tokens.json exits 2",
                          "the name Slotwise from forge-work/brand.json is in no file of the app")
        write(self.root, "forge-work/brand.md", BRAND.split("## Logo brief")[0])
        self.assert_fails("brand", "has no ## Logo brief, ## Voice, ## Sweep")

    def test_n32_the_name_counts_only_in_the_app(self):
        self.finish("brand")
        write(self.root, "index.html", "<title>Waterplanner</title>\n")
        for place in ("forge-work/notes.md", "node_modules/x/index.js", "e2e/home.spec.ts", "dist/index.html", ".env"):
            write(self.root, place, "Slotwise\n")
        self.assert_fails("brand", "is in no file of the app")
        write(self.root, "README.md", "# SLOTWISE\n")
        self.assertIn("the app carries the name Slotwise: README.md has it", self.assert_passes("brand"))

    def test_n37_a_launch_file_of_one_line(self):
        self.finish("launch")
        write(self.root, "forge-work/launch.md", "launch: later\n")
        self.assert_fails("launch", "has no ## Pricing, ## Privacy, cookies and SEO, ## Legal pages",
                          "needs a line `OG image: <file>`")
        write(self.root, "forge-work/launch.md", re.sub(r"\{\{.*?\}\}", "x", template("forge-launch", "launch.md"),
                                                         flags=re.S))
        self.assert_fails("launch", "no text of its own under ## Legal pages", "(found: no file name)")
        self.finish("launch")
        self.remove("public/og.png")
        self.assert_fails("launch", "needs a line `OG image: <file>` naming a file in the project, such as "
                                    "public/og.png (found: public/og.png)")

    def test_n42_a_pass_the_scan_did_not_earn(self):
        self.finish("secure")
        write(self.root, "src/bad.ts", "const q = location.search;\n\neval(q);\n")
        out = self.assert_fails("secure", "codecheck.py . exits 1: it found problems", "src/bad.ts:3")
        self.assertIn("why: forge-check secure, Step 3 and The gate", out)
        write(self.root, "forge-work/security.md", SECURITY.replace(
            "## Accepted risks\nNone.\n", "## Accepted risks\n- X002 [high] eval in src/bad.ts:3. The user said: "
                                          "\"ik accepteer dit\" (2026-10-27)\n"))
        self.assertIn("has accepted risks: each finding must be one of them", self.assert_passes("secure"))

    def test_n42_a_one_line_report(self):
        self.finish("secure")
        write(self.root, "forge-work/security.md", "Verdict: PASS\n")
        self.assert_fails("secure", "has no ## What was checked, ## Coverage, ## Findings, ## Not checked, ## Accepted risks",
                          "needs one line `Counts: 0 critical, 0 high, 1 medium, 0 low`")
        write(self.root, "forge-work/security.md", SECURITY.replace("0 high", "2 high"))
        self.assert_fails("secure", "says Verdict: PASS but counts 2 critical or high finding(s), and no risk "
                                    "is accepted")
        write(self.root, "forge-work/security.md", SECURITY.replace("0 high", "1 high").replace(
            "## Accepted risks\nNone.", "## Accepted risks\n- X001: \"fine for the beta\", the user, 2026-10-27"))
        self.assert_passes("secure")

    def test_n43_run_md_and_nginx_conf(self):
        self.finish("plan", "pack")
        shutil.copy(os.path.join(STATIC, "RUN.md"), os.path.join(self.root, "RUN.md"))
        self.assert_fails("pack", "RUN.md still has 1 placeholder(s) of ../forge-build/templates/*/RUN.md",
                          "line 1: {{App name}}")
        self.remove("RUN.md", "nginx.conf")
        self.assert_fails("pack", "RUN.md is missing", "nginx.conf is missing", "why: forge-build pack, Output: nginx.conf "
                                                                               "for laravel and static")
        write(self.root, "forge-work/plan.md", PLAN.replace("Profile: static", "Profile: next"))
        write(self.root, "RUN.md", filled("forge-build/templates/next/RUN.md"))
        self.assertNotIn("nginx.conf is missing", self.run_main("pack")[1])  # next serves its pages itself


class ShownTests(Checks):
    """rules.md section 9: a change the user cannot see has not happened. Each phase that changes the app runs
    changed.py on its before and after shots (R28): no visible change, or no after shots (exit 2), fails."""

    def test_a_change_that_does_not_show_fails(self):
        for phase, folder in (("build", "forge-work/design/shots"), ("dashboard", "forge-work/dashboard"),
                              ("motion", "forge-work/motion-shots"), ("brand", "forge-work/brand/shots"),
                              ("launch", "forge-work/launch/shots")):
            with self.subTest(phase=phase):
                shutil.rmtree(self.root, ignore_errors=True)
                os.makedirs(self.root)
                self.finish(phase)
                self.assertIn("changed.py %s/before %s/after exits 0" % (folder, folder), self.assert_passes(phase))
                shown(self.root, folder, after=(255, 255, 255))
                self.assert_fails(phase, "NO VISIBLE CHANGE", "why: %s, " % gate_skill(phase))
                shutil.rmtree(os.path.join(self.root, folder, "after"))
                self.assert_fails(phase, "changed.py %s/before %s/after exits 2: it could not check" % (folder, folder))


class MovedTests(Checks):
    """W-forge-2: stills never proved that anything moves, or that a scene went live: a plain landing page passed the
    motion, dashboard and launch gates. From level 2 a screen's entrance frames must move (lookcheck.py moved); from
    look level 4, and at dashboard level 5, a scene's frames too."""

    def test_entrance_frames_that_are_missing_or_still_fail(self):
        for phase, folder in (("dashboard", "forge-work/dashboard/motion"), ("motion", "forge-work/motion-shots/after"),
                              ("launch", "forge-work/launch/shots/motion")):
            with self.subTest(phase=phase):
                shutil.rmtree(self.root, ignore_errors=True)
                os.makedirs(self.root)
                self.finish(phase)
                self.assertIn("level 2 asks for the entrance frames f1 to f4 at 390, from level 2: 1 of 1 screen(s) "
                              "move in %s" % folder, self.assert_passes(phase))
                frames(self.root, folder, moving=False)
                self.assert_fails(phase, "from level 2: nothing moves in them", "home-390: nothing moves",
                                  "why: %s, Step" % gate_skill(phase))
                for path in glob.glob(os.path.join(self.root, folder, "*-f*.png")):
                    os.remove(path)
                self.assert_fails(phase, "from level 2: none in %s" % folder, "--frames <paths>")

    def test_a_scene_must_go_live_and_move_from_look_level_4(self):
        self.finish("motion")
        write(self.root, "forge-work/levels.json", levels(look=4))
        write(self.root, "forge-work/motion.md", MOTION.replace("Level: 2 (Polished)", "Level: 4 (Showpiece)"))
        self.assert_fails("motion", "look level 4 asks for the scene frames s1 to s6 at 1440, from level 4: none in "
                                    "forge-work/motion-shots/after", "--scene-frames <paths>")
        frames(self.root, "forge-work/motion-shots/after", kind="s", moving=False)  # a scene stuck on its poster
        self.assert_fails("motion", "from level 4: nothing moves in them", "home-1440: nothing moves")
        frames(self.root, "forge-work/motion-shots/after", kind="s")
        self.assertIn("ok    look level 4 asks for the scene frames s1 to s6 at 1440, from level 4: 1 of 1 screen(s) "
                      "move", self.run_main("motion")[1])  # motioncount still fails: this app has no WebGL scene

    def test_the_dashboard_asks_for_a_scene_at_level_5_only(self):
        self.finish("dashboard")
        write(self.root, "forge-work/levels.json", levels(dashboard=4))
        self.assertNotIn("scene frames", self.run_main("dashboard")[1])
        write(self.root, "forge-work/levels.json", levels(dashboard=5))
        self.assertIn("FAIL  dashboard level 5 asks for the scene frames s1 to s6 at 1440, from level 5: none in "
                      "forge-work/dashboard/motion", self.run_main("dashboard")[1])
        frames(self.root, "forge-work/dashboard/motion", kind="s")
        self.assertIn("ok    dashboard level 5 asks for the scene frames", self.run_main("dashboard")[1])


class DesignWorkTests(Checks):
    """W-forge-10: the design gate passed with only the brief, the tokens and components.md, so auto mode could skip the
    world, the board and the three concepts. T33: a components.md whose ## Components held one line passed. W-forge-12:
    the build gate never asked for the look review, the pack's guard against a generic look."""

    def test_the_world_the_board_and_the_three_concepts(self):
        for name in ("world.md", "concepts/index.html", "concepts/a/index.html", "concepts/b/index.html",
                     "concepts/c/index.html"):
            with self.subTest(name=name):
                self.finish("design")
                self.remove("forge-work/design/" + name)
                self.assert_fails("design", "forge-work/design/%s is missing" % name, "why: forge-design design, ")

    def test_a_block_per_component(self):
        self.finish("design")
        self.assertIn("## Components holds 1 component block(s), each with its states", self.assert_passes("design"))
        write(self.root, "forge-work/design/components.md", filled("forge-design/components.md").replace(
            "## Components\n\nSlotwise: written for this app.", "## Components\n\nButton: see the app."))
        self.assert_fails("design", "## Components holds no component block with a states line",
                          "why: forge-design design, Step 5: for every component one block")

    def test_the_build_holds_the_look_review_in_rounds(self):
        self.finish("build")
        self.remove("forge-work/design/review.md")
        self.assert_fails("build", "forge-work/design/review.md is missing", "why: forge-build build, Step 7.4",
                          args=("--mode", "idea"))
        write(self.root, "forge-work/design/review.md", "# Look review: Slotwise\nServed: docker compose\n")
        self.assert_fails("build", "forge-work/design/review.md has no ## Round", args=("--mode", "clone"))
        self.assert_passes("build")  # no mode known: a build outside /forge, where the gate does not ask for it
        write(self.root, "forge-work/design/review.md", REVIEW)  # Step 3.2's round of the slice, then no Step 7.4
        os.utime(os.path.join(self.root, "forge-work", "design", "review.md"), (OLD, OLD))
        self.assert_fails("build", "forge-work/design/review.md is older than the after shots in "
                                   "forge-work/design/shots/after: its last round (Round 1", "why: forge-build build, "
                                   "Step 7.3: after shots", args=("--mode", "idea"))
        write(self.root, "forge-work/design/review.md", REVIEW + "\n## Round 2 (2026-10-28, commit 9c0d1e2, judge: "
                                                        "fresh eyes)\n| home | 20 | | none | none |\n")
        self.assertIn("its last round (Round 2 (2026-10-28", self.assert_passes("build", "--mode", "idea"))


class LookLevelTests(Checks):
    """The look level is a promise in both directions (rules.md section 10), and the gate checks it in each report of
    the look (R09): the brief in every mode, build-log.md, motion.md and launch.md. Launch also counts the motion of
    that level in the app, so motion skipped at level 4 cannot end in an app without its 3D (R64)."""

    def test_design_needs_the_brief_in_every_mode_at_the_level_on_record(self):
        self.finish("design")
        for mode in ("clone", "idea"):
            self.assert_passes("design", "--mode", mode)
        write(self.root, "forge-work/design/brief.md", filled("forge-design/brief.md", Level="4 (Showpiece)"))
        self.assert_fails("design", "forge-work/design/brief.md needs exactly one line `Level: 2 (Polished)`",
                          "why: forge-design design, Output: level.py check look", args=("--mode", "clone"))
        self.remove("forge-work/design/brief.md")
        out = self.assert_fails("design", "forge-work/design/brief.md is missing", args=("--mode", "clone"))
        self.assertEqual(out.count("forge-work/design/brief.md is missing"), 1)

    def test_each_report_of_the_look_says_the_level_on_record(self):
        for phase, name in (("build", "forge-work/build-log.md"), ("motion", "forge-work/motion.md"),
                            ("launch", "forge-work/launch.md")):
            with self.subTest(phase=phase):
                shutil.rmtree(self.root, ignore_errors=True)
                os.makedirs(self.root)
                self.finish(phase)
                write(self.root, name, read(os.path.join(self.root, name)).replace("Level: 2 (Polished)", "Level: 3"))
                self.assert_fails(phase, "%s needs exactly one line `Level: 2 (Polished)`" % name, args=("--mode", "idea"))

    def test_a_build_on_the_users_own_app_in_its_own_look_has_no_look_level(self):
        """forge-build build, The level: a feature added to the user's own app in its own look logs `Level: none`.
        That build runs outside the gate's modes, so with no mode known the gate does not ask for the level."""
        self.finish("build")
        write(self.root, "forge-work/build-log.md", BUILD_LOG.replace("Level: 2 (Polished)", "Level: none, the app's "
                                                                       "own look"))
        self.assert_passes("build")
        self.assert_fails("build", "needs exactly one line `Level: 2 (Polished)`", args=("--mode", "clone"))

    def test_launch_counts_the_motion_and_3d_of_the_look_level(self):
        self.finish("launch")
        write(self.root, "forge-work/levels.json", levels(look=4))
        write(self.root, "forge-work/launch.md", filled("forge-launch/launch.md", Level="4 (Showpiece)"))
        self.assert_fails("launch", "motioncount.py . --level auto exits 1: it found problems",
                          "why: forge-launch, Step 2: build exactly what that level asks")  # no WebGL scene


@unittest.skipUnless(HAS_GIT, "the improve phase runs gitguard.py, which needs git")
class ImproveLookTests(Checks):
    """Improve mode has no design, motion or dashboard phase: forge-improve builds the look the user picked, and the
    gate checks what each look item under ## Fixed names (R37, R63). R63: a redesign at level 4 listed there, with no
    report, no shots and the app unchanged, passed."""
    DESIGN = ("### design [look] A redesign at level 4 (Showpiece)\nreport: forge-work/design/redesign.md   commits: "
              "4c1d2e0..a7f3b19\nproof:  changed.py: VISIBLE CHANGE on 1 of 1 pairs\n")
    MOTION_ITEM = "### motion [look] Motion and 3D at level 4 (Showpiece)\nreport: forge-work/motion.md\n"

    def setUp(self):
        super().setUp()
        self.finish("improve")
        write(self.root, "forge-work/levels.json", levels(look=4))

    def pick(self, *items):
        write(self.root, "forge-work/improve.md", IMPROVE.replace("## Skipped\n", "".join(items) + "## Skipped\n"))

    def test_a_look_item_that_was_not_built_and_shown_fails(self):
        self.pick(self.DESIGN)
        self.assert_fails("improve", "forge-work/improve.md: 1 look item(s) under ## Fixed, not built and shown",
                          "its report forge-work/design/redesign.md is not a file in the project that holds something",
                          "changed.py forge-work/improve/shots/before forge-work/improve/shots/after exits 2",
                          "why: forge-improve, Step 6")

    def test_a_design_pick_with_its_report_shots_and_frames_passes(self):
        """Design at level 2 to 5 builds motion too (forge-improve Step 4: also --frames): its entrance frames move and
        from level 4 its scene's frames too (W-forge-2). The motion count runs for a motion item only."""
        self.pick(self.DESIGN)
        write(self.root, "forge-work/design/redesign.md", "# Redesign: Slotwise\nLevel: 4 (Showpiece)\n")
        shown(self.root, "forge-work/improve/shots")
        self.assert_fails("improve", "look level 4 asks for the entrance frames f1 to f4 at 390, from level 2: none in "
                                     "forge-work/improve/shots/after-frames", "why: forge-improve, Step 7: --moves")
        frames(self.root, "forge-work/improve/shots/after-frames")
        frames(self.root, "forge-work/improve/shots/after-frames", kind="s")
        out = self.assert_passes("improve")
        self.assertIn("forge-design/motioncount.py . --level auto skipped: no ### motion under ## Fixed of "
                      "forge-work/improve.md", out)
        write(self.root, "forge-work/design/redesign.md", "# Redesign: Slotwise\nLevel: 2 (Polished)\n")
        self.assert_fails("improve", "forge-work/design/redesign.md needs exactly one line `Level: 4 (Showpiece)`")

    def test_only_the_parts_this_run_picked_are_checked(self):
        """VG5-N1: an older dashboard.md or motion.md, from a run before, is not this run's pick. Their checks wait for
        a look item of that part under ## Fixed; one under ## Skipped does not count."""
        write(self.root, "forge-work/dashboard.md", DASHBOARD.replace("src/dashboard.html:4", "Chart.tsx:4"))
        write(self.root, "forge-work/motion.md", MOTION.replace("Level: 2 (Polished)", "Level: 5"))
        write(self.root, "forge-work/improve.md", IMPROVE.replace("## For you\n", self.MOTION_ITEM + "why: the user "
                                                                  "chose the findings only\n## For you\n"))
        out = self.assert_passes("improve")
        self.assertIn("forge-design/dashbuilt.py forge-work/dashboard.md --level auto skipped: no ### dashboard under "
                      "## Fixed of forge-work/improve.md", out)
        self.assertIn("forge-design/motioncheck.py . --fail-on high skipped: no ### motion under ## Fixed", out)
        self.pick("### dashboard [look] The statistics screen at level 2\nreport: forge-work/dashboard.md\n")
        self.assert_fails("improve", "dashbuilt.py forge-work/dashboard.md --level auto exits 1")

    def test_a_look_item_names_its_own_report_of_this_round(self):
        """VG1-N5: `report: package.json` passed, as any file that holds something did. R63: the shots, frames and report
        of an earlier round passed with nothing of this round; the gate gives --since, the last go."""
        write(self.root, "package.json", '{"name": "slotwise", "private": true}\n')
        self.pick(self.DESIGN.replace("forge-work/design/redesign.md", "package.json"))
        shown(self.root, "forge-work/improve/shots")
        frames(self.root, "forge-work/improve/shots/after-frames")
        frames(self.root, "forge-work/improve/shots/after-frames", kind="s")
        self.assert_fails("improve", "its report package.json is not its look report, forge-work/design/redesign.md")
        self.pick(self.DESIGN)
        write(self.root, "forge-work/design/redesign.md", "# Redesign: Slotwise\nLevel: 4 (Showpiece)\n")
        self.assert_passes("improve")
        old = glob.glob(os.path.join(self.root, "forge-work", "improve", "shots", "*", "*.png"))
        for path in old + [os.path.join(self.root, "forge-work", "design", "redesign.md")]:
            os.utime(path, (OLD, OLD))  # an earlier round's, before the last go
        since = ("--since", "2020-01-01T00:00:00+00:00")
        self.assert_fails("improve", "its report forge-work/design/redesign.md is older than the last go",
                          "forge-work/improve/shots/after: no pair of shots newer than the last go",
                          "home-390: from before the last go", args=since)
        write(self.root, "forge-work/design/redesign.md", "# Redesign: Slotwise\nLevel: 4 (Showpiece)\n")
        shown(self.root, "forge-work/improve/shots")
        frames(self.root, "forge-work/improve/shots/after-frames")
        frames(self.root, "forge-work/improve/shots/after-frames", kind="s")
        self.assert_passes("improve", *since)

    def test_older_motion_findings_in_the_apps_own_code_may_stay(self):
        """VG1-N1: forge-design motion Step 9.2 leaves a finding in the app's older code under ## Checks when it is
        not small and safe to fix, so on the user's own app the gate stops at a high one only. /forge's motion
        phase, on an app forge built, keeps --fail-on medium."""
        self.pick(self.MOTION_ITEM.replace("level 4 (Showpiece)", "level 2 (Polished)"))
        write(self.root, "forge-work/levels.json", LEVELS)
        for name, text in (("forge-work/motion.md", MOTION), ("index.html", MOTION_HTML), ("src/style.css", MOTION_CSS),
                           ("src/old/bar.css", ".bar { transition: width 200ms; }\n")):  # the last: from before
            write(self.root, name, text)
        shown(self.root, "forge-work/improve/shots", parts=("before-frames", "after-frames"), name="home-390-f2.png")
        frames(self.root, "forge-work/improve/shots/after-frames")
        self.assertIn("motioncheck.py . --fail-on high exits 0", self.assert_passes("improve"))
        self.finish("motion")
        self.assert_fails("motion", "motioncheck.py . --fail-on medium exits 1", "why: forge-design motion, Step 9.2")

    def test_a_look_item_names_its_part_first(self):
        """V3G1-N1: `### [look] The whole look` counted as a look item, but the part checks run only for a heading
        that starts with design, motion or dashboard: a redesign.md at level 2, with look 4 on record and no frames,
        passed. Two spaces after ### read as one, in lookcheck.py and in the part checks alike."""
        write(self.root, "forge-work/design/redesign.md", "# Redesign: Slotwise\nLevel: 2 (Polished)\n")
        shown(self.root, "forge-work/improve/shots")
        self.pick(self.DESIGN.replace("### design [look] A redesign", "### [look] The whole look"))
        self.assert_fails("improve", "[look] The whole look at level 4 (Showpiece): name its part first: ### design "
                                     "[look], ### motion [look] or ### dashboard [look] (forge-improve Step 2)")
        self.pick(self.DESIGN.replace("### design", "###  design"))
        self.assert_fails("improve", "forge-work/design/redesign.md needs exactly one line `Level: 4 (Showpiece)`",
                          "the entrance frames f1 to f4 at 390, from level 2: none in")

    def test_a_high_motion_finding_stops_improve(self):
        """V3G1-N5: at --fail-on high an older medium finding may stay (Step 9.2), but an animation with no
        prefers-reduced-motion rule anywhere in the app still stops the run."""
        self.pick(self.MOTION_ITEM.replace("level 4 (Showpiece)", "level 2 (Polished)"))
        write(self.root, "forge-work/levels.json", LEVELS)
        write(self.root, "forge-work/motion.md", MOTION)
        write(self.root, "index.html", MOTION_HTML)
        write(self.root, "src/style.css", ".hero { animation: rise 400ms both; }\n@keyframes rise { from { opacity: 0; } }\n")
        self.assert_fails("improve", "forge-design/motioncheck.py . --fail-on high exits 1: it found problems",
                          "why: forge-improve, Step 6: each look item moves to Fixed with its checks passing")

    def test_a_look_item_in_a_comment_or_code_block_picks_no_part(self):
        """V3G1-N5: a look item in a comment or a code block under ## Fixed is not a pick, so its part's checks are
        skipped: no report, shots or frames are asked for."""
        for hidden in ("<!--\n%s-->\n", "```\n%s```\n"):
            with self.subTest(hidden=hidden[:4]):
                self.pick(hidden % self.DESIGN)
                out = self.assert_passes("improve")
                for check in ("forge/level.py check look --report forge-work/design/redesign.md skipped: no ### design "
                              "under ## Fixed of forge-work/improve.md", "forge/lookcheck.py moved forge-work/improve/"
                              "shots/after-frames --level auto skipped: no ### design under ## Fixed"):
                    self.assertIn(check, out)
                self.assertIn("forge-work/improve.md: 0 look item(s) under ## Fixed", out)

    def test_after_shots_that_are_missing_or_show_no_change_fail(self):
        self.pick(self.DESIGN)
        write(self.root, "forge-work/design/redesign.md", "# Redesign: Slotwise\nLevel: 4 (Showpiece)\n")
        shown(self.root, "forge-work/improve/shots", after=(255, 255, 255))
        self.assert_fails("improve", "forge-work/improve/shots/after exits 1: NO VISIBLE CHANGE in any pair",
                          "the app was not rebuilt or restarted", "why: forge-improve, Step 6")
        shutil.rmtree(os.path.join(self.root, "forge-work", "improve", "shots", "after"))
        self.assert_fails("improve", "changed.py forge-work/improve/shots/before forge-work/improve/shots/after exits 2")

    def test_findings_alone_run_no_changed_py_at_the_gate(self):
        """A small fix can stay under changed.py's bar; its proof is its test or its own shots (forge-improve Step 5)."""
        shown(self.root, "forge-work/improve/shots", after=(255, 255, 255))
        self.assert_passes("improve")

    def test_a_motion_pick_is_counted_at_the_look_level(self):
        self.pick(self.MOTION_ITEM)
        write(self.root, "forge-work/motion.md", MOTION.replace("Level: 2 (Polished)", "Level: 4 (Showpiece)"))
        write(self.root, "index.html", MOTION_HTML)
        write(self.root, "src/style.css", MOTION_CSS)
        shown(self.root, "forge-work/improve/shots", after=(255, 255, 255))  # the stills: the page at rest
        shown(self.root, "forge-work/improve/shots", parts=("before-frames", "after-frames"), name="home-390-f2.png")
        frames(self.root, "forge-work/improve/shots/after-frames")  # the entrance moves; there is no scene
        self.assert_fails("improve", "motioncount.py . --level auto exits 1: it found problems",
                          "why: forge-improve, Step 6: each look item moves to Fixed with its checks passing",
                          "the scene frames s1 to s6 at 1440, from level 4: none in forge-work/improve/shots/after-frames")
        write(self.root, "forge-work/levels.json", LEVELS)  # the same app at look level 2 passes
        write(self.root, "forge-work/motion.md", MOTION)
        self.assertIn("motioncheck.py . --fail-on high exits 0", self.assert_passes("improve"))


class ModeTests(Checks):
    def test_the_mode_comes_from_the_state_unless_given(self):
        self.finish("test")
        shutil.rmtree(os.path.join(self.root, "e2e"))
        write(self.root, "forge-work/test-plan.md", TEST_PLAN.replace("| e2e |", "| unit |"))
        self.assertIn("Exit checks for test (no mode known: only the checks every mode has):",
                      self.assert_passes("test"))
        write(self.root, "forge-work/state.json", json.dumps({"version": 1, "mode": "clone", "phases": {}}))
        self.assert_fails("test", "Exit checks for test (clone mode):", "no end-to-end spec")
        self.assert_passes("test", "--mode", "improve")
        for state in ("{not json", "[]", '{"mode": ["clone"]}', '{"mode": "deploy"}'):
            with self.subTest(state=state):
                write(self.root, "forge-work/state.json", state)
                self.assert_passes("test")


class SinceTests(Checks):
    def test_a_report_from_before_the_last_go_does_not_count(self):
        self.finish("secure")
        os.utime(os.path.join(self.root, "forge-work", "security.md"), (OLD, OLD))
        self.assert_fails("secure", "forge-work/security.md is older than the last go (2026-10-27T09:51:44+00:00)",
                          "Run the phase's skill again in full", args=("--since", "2026-10-27T09:51:44+00:00"))
        self.assert_passes("secure", "--since", "2017-01-01T00:00:00+00:00")
        self.assert_passes("secure")  # without --since, its age is not checked

    def test_a_parity_report_from_before_tests_go_does_not_count(self):
        """N26, N27: test's fix loop changes the clone after build, so diff's parity.md must be newer than
        the go before diff (test's), or it scores the clone as it was before those fixes."""
        self.finish("diff")
        go = "2026-10-27T09:51:44+00:00"
        at = datetime.datetime.fromisoformat(go).timestamp()
        os.utime(os.path.join(self.root, "forge-work", "parity.md"), (at - 1, at - 1))
        self.assert_fails("diff", "forge-work/parity.md is older than the last go (%s)" % go,
                          "Run the phase's skill again in full", args=("--since", go))
        self.assert_passes("diff")  # without --since, its age is not checked
        for name in ("bugs.md", "features.csv"):  # written before parity.md, as in forge-check diff
            os.utime(os.path.join(self.root, "forge-work", name), (at, at))
        os.utime(os.path.join(self.root, "forge-work", "parity.md"), (at + 1, at + 1))
        self.assertIn("forge-work/parity.md is newer than the last go (%s)" % go,
                      self.assert_passes("diff", "--since", go))

    def test_a_parity_report_older_than_the_bugs_or_the_features_does_not_count(self):
        """gate-6: a bug from diff's behaviour walk goes through forge-check test's fix loop, which changes bugs.md,
        and a missing must-have through forge-build build, which changes features.csv. diff then runs again from
        Step 1 and its Step 4 rewrites parity.md: an older parity.md holds the verdict from before."""
        self.finish("diff")
        go = "2026-10-27T09:51:44+00:00"
        parity = os.path.join(self.root, "forge-work", "parity.md")
        for name in ("bugs.md", "features.csv"):
            with self.subTest(name=name):
                at = os.path.getmtime(parity)
                os.utime(os.path.join(self.root, "forge-work", name), (at + 5, at + 5))
                self.assert_fails("diff", "forge-work/parity.md is older than forge-work/%s, which" % name,
                                  "Run the phase's skill again from its first step", args=("--since", go))
                os.utime(parity, (at + 5, at + 5))  # the same time passes: some file systems keep whole seconds
                self.assertIn("forge-work/parity.md is newer than the last go (%s)" % go,
                              self.assert_passes("diff", "--since", go))

    def test_an_input_changed_after_the_phases_own_go_is_a_later_phases(self):
        """--until is the phase's own go, once it is done: a bugs.md changed after it comes from a later
        phase's fix (brand, launch, secure or pack sent a bug through test's loop), not from diff's own."""
        self.finish("diff")
        go, own = "2026-10-27T09:51:44+00:00", "2026-10-27T10:30:00+00:00"
        at = datetime.datetime.fromisoformat(own).timestamp()
        os.utime(os.path.join(self.root, "forge-work", "parity.md"), (at - 60, at - 60))  # Step 4, during diff
        bugs = os.path.join(self.root, "forge-work", "bugs.md")
        os.utime(bugs, (at + 60, at + 60))  # after diff's go
        os.utime(os.path.join(self.root, "forge-work", "features.csv"), (at - 120, at - 120))
        self.assert_passes("diff", "--since", go, "--until", own)
        os.utime(bugs, (at - 30, at - 30))  # still during diff, after parity.md: the report is stale
        self.assert_fails("diff", "forge-work/parity.md is older than forge-work/bugs.md",
                          args=("--since", go, "--until", own))

    def test_a_report_from_an_earlier_round_does_not_count(self):
        """gate-2: later changes to a finished app run improve mode in its root (forge/SKILL.md, Next), and
        init --force keeps the files of the earlier round. Its test-plan.md, audit.md, inspect.md and
        improve.md must not pass this round's test, audit, inspect and improve."""
        go = "2026-10-27T09:51:44+00:00"
        for phase in ("test", "audit", "inspect", "improve"):
            if phase == "improve" and not HAS_GIT:
                continue  # its check runs gitguard.py, which needs git
            with self.subTest(phase=phase):
                self.finish(phase)
                name = phasecheck.FRESH[phase]
                self.assert_passes(phase, "--since", go)
                os.utime(os.path.join(self.root, name), (OLD, OLD))
                self.assert_fails(phase, "%s is older than the last go (%s)" % (name, go), args=("--since", go))

    def test_the_levels_evidence_from_before_the_last_go_does_not_count(self):
        """R13: the build's own /forge-check secure leaves sbom.json behind (from level 4 also the probe). The secure
        phase runs the check again in full (forge/SKILL.md): a new security.md next to the build's SBOM fails."""
        self.finish("secure")
        go = "2026-10-27T09:51:44+00:00"
        self.assert_passes("secure", "--since", go)
        os.utime(os.path.join(self.root, "forge-work", "sbom.json"), (OLD, OLD))
        self.assert_fails("secure", "nor in forge-work/ one older than --since): forge-work/sbom.json",
                          args=("--since", go))
        self.assert_passes("secure")  # without --since, its age is not checked

    def test_since_applies_only_to_a_phase_with_a_report(self):
        self.finish("plan")
        os.utime(os.path.join(self.root, "forge-work", "plan.md"), (OLD, OLD))
        self.assert_passes("plan", "--since", "2026-10-27T09:51:44+00:00")

    def test_a_missing_report_is_named_once(self):
        for phase, name in phasecheck.FRESH.items():
            with self.subTest(phase=phase):
                out = self.assert_fails(phase, args=("--since", "2026-10-27T09:51:44+00:00"))
                self.assertEqual(out.count("%s is missing" % name), 1)


class ScriptTests(Checks):
    def fake_pack(self, source, script="forge-check/secretscan.py"):
        """A copy of the pack's forge and forge-check secure folders with SCRIPT replaced by SOURCE."""
        pack = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pack, ignore_errors=True)
        for folder in ("forge", "forge-check"):
            shutil.copytree(os.path.join(ROOT, folder), os.path.join(pack, folder),
                            ignore=shutil.ignore_patterns("__pycache__"))
        with open(os.path.join(pack, script), "w", encoding="utf-8") as handle:
            handle.write(source)
        return pack

    def test_a_script_that_prints_nothing_checked_nothing(self):
        self.finish("secure")
        for source in ("", "import sys\nsys.exit(None)\n", "def main():\n    return 0\n"):
            with self.subTest(source=source), mock.patch.object(phasecheck, "PACK", self.fake_pack(source)):
                self.assert_fails("secure", "secretscan.py . exits 0: it printed nothing, so it checked nothing")

    def test_a_script_that_crashes_is_not_said_to_find_problems(self):
        self.finish("secure")
        with mock.patch.object(phasecheck, "PACK", self.fake_pack('raise RuntimeError("boom")\n')):
            out = self.assert_fails("secure", "secretscan.py . exits 1: it crashed: this is a bug in that script")
        self.assertNotIn("it found problems", out)

    def test_a_report_checker_that_crashes_fails_the_check(self):
        self.finish("secure")
        with mock.patch.object(phasecheck, "PACK", self.fake_pack('raise RuntimeError("boom")\n', "forge/doccheck.py")):
            self.assert_fails("secure", "doccheck.py forge-work/security.md", "it crashed")

    def test_a_missing_script_fails_the_check(self):
        self.finish("diff")
        with mock.patch.object(phasecheck, "PACK", os.path.join(self.root, "nowhere")):
            self.assert_fails("diff", "exits 2: it could not check")

    def test_a_script_that_hangs_fails_the_check(self):
        self.finish("diff")
        hung = subprocess.TimeoutExpired(cmd="parity.py", timeout=phasecheck.TIMEOUT)
        with mock.patch.object(phasecheck.subprocess, "run", side_effect=hung):
            self.assert_fails("diff", "did not finish within %d seconds" % phasecheck.TIMEOUT)


class ConsoleTests(Checks):
    def test_the_scripts_it_runs_are_read_as_utf8_on_a_cp1252_pipe(self):
        """phasecheck.py asks the scripts it runs for UTF-8 and reads them as UTF-8. Windows pipes are cp1252
        otherwise, and the e of Café came out as the Unicode replacement character."""
        self.finish("brand")
        write(self.root, "forge-work/brand.json", '{"name": "Slotwise", "avoid": ["Café Noir →"]}')
        write(self.root, "index.html", "<title>Slotwise: Café Noir → booking</title>\n")
        code, out, err = run_cp1252(os.path.join(ROOT, "forge", "phasecheck.py"), "brand", cwd=self.root)
        self.assertEqual(code, 1, err)
        self.assertIn("A name to avoid: Café Noir \\u2192 (1 place)", out)
        self.assertNotIn("\\ufffd", out)

    def test_a_report_with_any_text_on_a_cp1252_pipe(self):
        self.finish("recon")
        write(self.root, "forge-work/recon.md", "# Recon: Café → (web)\n\n## Sources ☕\n")
        code, out, err = run_cp1252(os.path.join(ROOT, "forge", "phasecheck.py"), "recon", cwd=self.root)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("no ## Core loop", out)


if __name__ == "__main__":
    unittest.main()
