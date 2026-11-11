#!/usr/bin/env python3
"""Does the new look show on the screen? The forge gate's proof that a change of the look reached the app:
../forge-design/changed.py on the shots and frames that shots.mjs (../forge-design/shots.example.mjs) took.
phasecheck.py runs it for the exit checks of a phase. Run it from the project root. It reads files; it
changes nothing.

Usage:
    python3 lookcheck.py looked forge-work/improve.md forge-work/improve/shots
    python3 lookcheck.py moved forge-work/motion-shots/after --level auto
    python3 lookcheck.py moved forge-work/dashboard/motion --level auto --domain dashboard --json
    python3 lookcheck.py moved forge-work/launch/shots/after --level 4 --since 2026-10-27T09:51:44+00:00
    python3 lookcheck.py judged forge-work/design/review.md forge-work/design/shots/after

looked FILE FOLDER: each look item under ## Fixed of FILE (forge-improve's improve.md: a ### heading that
  starts with design, motion or dashboard, or holds [look]) starts with its part, as the gate runs each
  part's checks by that word, and names on its `report:` line its own look report, holding something:
  forge-work/design/redesign.md (design), forge-work/motion.md (motion), forge-work/dashboard.md or
  dashboard-<screen>.md (dashboard). And changed.py says VISIBLE CHANGE between the shots in FOLDER: before
  and after, for motion before-frames and after-frames (a still is the page at rest, so motion shows in
  frames only). Look items in comments, code or another section do not count.
moved FOLDER...: the frames the level asks for are in FOLDER (several: in any of them), and changed.py
  --moves says they move. From level 2 the entrance, <name>-390-f1.png to -f4.png of --frames (never f5 to
  f7: they differ by the scroll alone). With a scene, look level 4 and 5 or dashboard level 5, also
  <name>-1440-s1.png to -s6.png of --scene-frames, taken once the scene is live: a scene stuck on its
  poster does not move. One screen whose frames move is enough for each, as a form may stay still; the
  lines name each screen. Level 1 asks for no frames. --level auto reads forge-work/levels.json (level.py
  writes it); --domain: look (the default) or dashboard. The entrance proves motion only where f1 shows the
  page fully drawn: fonts, pictures or data that arrive after f1 change the frames with no motion at all.
judged REVIEW FOLDER: forge-build Step 7.4's look review ran on the screens as built: REVIEW (review.md)
  has a ## Round block and is newer than every shot in FOLDER, Step 7.3's after shots. Step 3.2's round of
  the slice alone is older than them.
--since TIME: the last go before the phase. A report, a pair of shots or a set of frames older than TIME is
  from an earlier round and does not count.

Exit codes:
    0  the check passes
    1  it fails: the output says what and how to fix it
    2  bad usage, a file it needs cannot be read, or no level on record for --level auto
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the forge skill pack
UNSEEN = re.compile(r"<!--.*?(?:-->|\Z)|^ {0,3}(`{3,}|~{3,}).*?(?:^ {0,3}\1|\Z)", re.S | re.M)  # comments, code
PART = re.compile(r"(?i)(design|motion|dashboard)\b")  # forge-improve Step 2: `### design [look] ...`
LOOK = re.compile(PART.pattern + r"|[^\n]*\[look\]")  # a look item: its part first, or [look] in its heading
REPORT = re.compile(r"(?im)^[ \t>*_-]*report[ \t*_]*:[ \t*_`]*([^\s`*]+)")  # `report: forge-work/motion.md`
REPORTS = {"design": ("design/redesign", "forge-work/design/redesign.md"), "motion": ("motion", "forge-work/motion.md"),
           "dashboard": (r"dashboard(?:-[\w-]+)?", "forge-work/dashboard.md or dashboard-<screen>.md")}
FRAME = re.compile(r"(.+)-(\d+)-([fs])(\d+)\.png")  # shots.mjs names: home-390-f1.png, home-1440-s1.png
KINDS = {"f": ("390", range(1, 5), "the entrance frames f1 to f4", "--frames", "f[1-4]", "the screen arrives in steps"),
         "s": ("1440", range(1, 7), "the scene frames s1 to s6", "--scene-frames", "s*",
               "the scene is live and moves (shots.mjs waits for it; one stuck on its poster stands still)")}
FROM = {"look": {"f": 2, "s": 4}, "dashboard": {"f": 2, "s": 5}}  # the level that asks for them (../forge/levels.md)
CAUSES = ("the work is on another branch or folder than the one the app serves, the app was not rebuilt or "
          "restarted, a cache serves the old files, or the change is too small (rules.md section 9)")
LOADING = ("A proof only where f1 shows the page fully drawn: fonts, pictures or data arriving later change frames "
           "too. Look at f1; still loading there: judge the entrance on --video (rules.md 9).")


def read(path):
    with open(path, encoding="utf-8-sig") as handle:
        return handle.read()


def cut(lines):
    """At most 12 lines: the start says what is wrong; the rest is one command away."""
    return lines if len(lines) <= 12 else lines[:11] + ["... %d more lines: run it to see them" % (len(lines) - 11)]


def changed(*args):
    """../forge-design/changed.py ARGS --json: (its exit code, None when it hung; its JSON, {} when none; its error)."""
    try:
        done = subprocess.run([sys.executable, os.path.join(PACK, "forge-design", "changed.py")] + list(args) + ["--json"],
                              stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8", errors="replace",
                              timeout=600, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    except subprocess.TimeoutExpired:
        return None, {}, "it did not finish within 600 seconds"
    try:
        data = json.loads(done.stdout)
    except ValueError:  # it stopped before it compared anything: its error line says why
        return done.returncode, {}, " ".join(done.stderr.split())[:300] or "it printed nothing"
    return done.returncode, data, "; ".join("%s: %s" % (pair["name"], pair["error"])
                                            for pair in data.get("pairs", []) if "error" in pair)[:300]


def newer(paths, since):
    """Every file of PATHS was written at or after SINCE (a timestamp; None: no limit)."""
    return not since or min(os.path.getmtime(path) for path in paths) >= since


def check_looked(name, shots, since=None):
    """forge-improve: a look item under ## Fixed was built and shown, not only written down (see the top)."""
    parts = re.split(r"(?im)^ {0,3}##[ \t]+fixed\b.*$", UNSEEN.sub("", read(name)), maxsplit=1)
    fixed = re.split(r"(?m)^ {0,3}##[ \t]", parts[1])[0] if len(parts) > 1 else ""
    looks = [item for item in re.split(r"(?m)^ {0,3}###[ \t]+", fixed)[1:] if LOOK.match(item)]
    problems, pairs = [], sorted({("before-frames", "after-frames") if item[:6].lower() == "motion" else
                                  ("before", "after") for item in looks})
    for item in looks:
        head, found = item.split("\n")[0].strip()[:80], REPORT.search(item)
        path = found.group(1).rstrip(".,;:") if found else ""
        own = [REPORTS[kind] for kind in REPORTS if item.lower().startswith(kind)] or list(REPORTS.values())
        if not PART.match(item):  # `### [look] The whole look`: the gate's part checks would never run for it
            problems.append("%s: name its part first: ### design [look], ### motion [look] or ### dashboard [look] "
                            "(forge-improve Step 2), one item per part" % head)
        if not path:
            problems.append("%s: no `report:` line that names its report" % head)
        elif os.path.islink(path) or not os.path.isfile(path) or not os.path.getsize(path):
            problems.append("%s: its report %s is not a file in the project that holds something" % (head, path))
        elif not any(re.fullmatch(r"forge-work/(?:%s)\.md" % pattern, path.replace("\\", "/")) for pattern, _ in own):
            problems.append("%s: its report %s is not its look report, %s" % (head, path, " or ".join(
                words for _, words in own)))
        elif not newer([path], since):
            problems.append("%s: its report %s is older than the last go: it is an earlier round's" % (head, path))
    for before, after in pairs:  # the stills for a new look, the frames for motion
        command = "changed.py %s/%s %s/%s" % (shots, before, shots, after)
        code, data, error = changed(os.path.join(shots, before), os.path.join(shots, after))
        fresh = [pair for pair in data.get("pairs", []) if newer([pair["before"], pair["after"]], since)]
        if code not in (0, 1):
            problems.append("%s exits %s: %s" % (command, code, error))
        elif not fresh:
            problems.append("%s: no pair of shots newer than the last go, so none of this round" % command)
        elif not any(pair.get("visible") for pair in fresh):
            problems.append("%s exits 1: NO VISIBLE CHANGE in any pair%s: none reaches %s%% of the pixels. Usually %s"
                            % (command, " of this round" if since else "", data["summary"]["min"], CAUSES))
    if problems:
        return False, "%s: %d look item(s) under ## Fixed, not built and shown as forge-improve says" % (
            name, len(looks)), cut(problems + [
                "Take Step 4's before shots (motion: --frames into before-frames) before the work and Step 7's after "
                "shots after it; name each report; or move the item to ## Skipped with why (forge-improve)."])
    return True, "%s: %d look item(s) under ## Fixed, each with its report%s" % (name, len(looks), "".join(
        "; changed.py %s/%s %s/%s: VISIBLE CHANGE" % (shots, before, shots, after) for before, after in pairs)), []


def check_judged(review, after, since=None):
    """forge-build Step 7.4: the look review ran after Step 7.3's after shots, on the screens as built (see the top)."""
    if not os.path.isfile(review):
        return False, "%s is missing" % review, []
    rounds = re.findall(r"(?im)^ {0,3}##[ \t]+(round\b.*?)[ \t]*$", UNSEEN.sub("", read(review)))
    shots = [entry.path for entry in os.scandir(after) if entry.name.lower().endswith(".png")
             and entry.is_file(follow_symlinks=False)] if os.path.isdir(after) else []
    if not rounds or not shots:
        return False, "%s: %s" % (review, "no ## Round block" if not rounds else "no after shots in %s yet" % after), [
            "Step 7.3: the after shots of every screen first; Step 7.4: then the look review on them, a round "
            "numbered on from the slice's (../forge-design/review.md section 4)."]
    if not newer([review], max([since or 0] + [os.path.getmtime(shot) for shot in shots])):
        return False, "%s is older than the after shots in %s: its last round (%s) is from before Step 7.3" % (
            review, after, rounds[-1][:60]), [
            "Step 7.4: the look review on every screen as built, after Step 7.3, as the next round numbered on "
            "from the slice's (../forge-design/review.md section 4). A change after it: one more round."]
    return True, "%s: its last round (%s) is newer than the after shots in %s" % (review, rounds[-1][:60], after), []


def frame_sets(folders, kind):
    """{screen: [its frames of KIND, in order]} in FOLDERS, at KIND's width. A file of a later folder wins."""
    width, numbers = KINDS[kind][:2]
    found = {}
    for folder in folders:
        for entry in sorted(os.scandir(folder), key=lambda entry: entry.name) if os.path.isdir(folder) else []:
            match = FRAME.fullmatch(entry.name)
            if (match and match.group(2) == width and match.group(3) == kind and int(match.group(4)) in numbers
                    and entry.is_file(follow_symlinks=False)):
                found.setdefault("%s-%s" % (match.group(1), width), {})[int(match.group(4))] = entry.path
    return {screen: [frames[number] for number in sorted(frames)] for screen, frames in sorted(found.items())}


def check_moved(folders, level, domain, since=None):
    """The frames LEVEL asks for are in FOLDERS and move (see the top): one check for each kind it asks for."""
    checks, where = [], " or ".join(folders)
    for kind, (width, _, words, flag, names, shows) in KINDS.items():
        if level < FROM[domain][kind]:
            continue
        lines, moving, sets = [], [], frame_sets(folders, kind)
        for screen, frames in sets.items():
            if not newer(frames, since):
                lines.append("%s: from before the last go, so of an earlier round: not counted" % screen)
                continue
            code, data, error = changed("--moves", *frames) if len(frames) > 1 else (2, {}, "one frame only")
            moving += [screen] if code == 0 else []
            lines.append("%s: %s" % (screen, {0: "something moves", 1: "nothing moves"}.get(code, "not compared: "
                                                                                             + error)))
        about = "%s level %d asks for %s at %s, from level %d" % (domain, level, words, width, FROM[domain][kind])
        if moving:
            checks.append((True, "%s: %d of %d screen(s) move in %s" % (about, len(moving), len(sets), where), lines + [
                LOADING] * (kind == "f")))
            continue
        checks.append((False, "%s: %s" % (about, "nothing moves in them" if sets else "none in " + where), cut(lines + [
            "Proof that %s: after the work, with reduced motion off, node forge-work/design/shots.mjs <URL> <FOLDER> "
            "%s <paths>, then changed.py --moves on its <name>-%s-%s.png. Nothing moves: the app does not show the "
            "new work (rules.md section 9), or it was never built." % (shows, flag, width, names)])))
    return checks or [(True, "%s level %d asks for no frames: they start at level %d" % (
        domain, level, FROM[domain]["f"]), [])]


def level_on_record(domain):
    """DOMAIN's level in forge-work/levels.json, which level.py writes. ValueError: none, a link or not 1 to 5."""
    path = os.path.join("forge-work", "levels.json")
    if os.path.islink("forge-work") or os.path.islink(path):
        raise ValueError("%s is a link, so it was not read: tell the user and change nothing" % path)
    try:
        if not os.path.isfile(path):
            raise ValueError("there is no such file")
        level = json.loads(read(path))[domain]["level"]
    except (OSError, ValueError, LookupError, TypeError, RecursionError) as error:
        raise ValueError("no %s level on record in %s (%s): ask the user, and record their answer with "
                         "level.py set" % (domain, path, error))
    if type(level) is not int or not 1 <= level <= 5:
        raise ValueError("the %s level in %s is %r, not 1 to 5: show the user level.py get %s" % (
            domain, path, level, domain))
    return level


def a_time(text):
    """argparse type for --since: an ISO 8601 time, as gate.py writes it, as a timestamp."""
    try:
        return datetime.datetime.fromisoformat(text).timestamp()
    except (ValueError, OverflowError, OSError):
        raise argparse.ArgumentTypeError("not a time like 2026-10-27T09:51:44+00:00: %r" % text)


def main(argv=None):
    """Run one check. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):  # what the console cannot show comes out as \u escapes, not a crash
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", metavar="CHECK", required=True)
    looked = commands.add_parser("looked", help="each look item of improve.md: its report, and a change that shows")
    looked.add_argument("file")
    looked.add_argument("folder")
    moved = commands.add_parser("moved", help="the frames the level asks for are there, and they move")
    moved.add_argument("folder", nargs="+")
    moved.add_argument("--level", required=True, choices=list("12345") + ["auto"], metavar="N|auto",
                       help="the level, or auto: the one on record")
    moved.add_argument("--domain", choices=sorted(FROM), default="look", help="whose level: look or dashboard")
    judged = commands.add_parser("judged", help="forge-build's look review is newer than its after shots")
    judged.add_argument("file")
    judged.add_argument("folder")
    for command in (looked, moved, judged):
        command.add_argument("--since", type=a_time, metavar="TIME", help="the last go: older files do not count")
        command.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        if args.command in ("looked", "judged"):
            checks = [(check_looked if args.command == "looked" else check_judged)(args.file, args.folder, args.since)]
        else:
            level = level_on_record(args.domain) if args.level == "auto" else int(args.level)
            checks = check_moved(args.folder, level, args.domain, args.since)
    except (OSError, ValueError, RecursionError) as error:  # missing, a folder, not UTF-8, no level on record
        print("error: %s" % error, file=sys.stderr)
        return 2
    passed = all(ok for ok, _, _ in checks)
    if args.json:
        print(json.dumps({"check": args.command, "ok": passed, "checks": [
            {"ok": ok, "what": what, "output": output} for ok, what, output in checks]}, indent=2))
    else:
        for ok, what, output in checks:
            print("\n".join(["%-4s  %s" % ("ok" if ok else "FAIL", what)] + ["      " + line for line in output]))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
