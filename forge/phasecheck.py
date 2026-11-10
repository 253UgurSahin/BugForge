#!/usr/bin/env python3
"""Is the work of one forge phase there and finished? These are the exit checks the forge gate runs
before it records a phase as done: `gate.py check PHASE` and `gate.py done PHASE` run this script.
Run it from the project root. It reads files and runs the other skills' scripts; it changes nothing.
The checks of each phase are in phasecheck.json next to it, each with the skill line it rests on.
Two scripts next to it do part of the work: doccheck.py (the reports) and workcheck.py (the rest).

Usage:
    python3 phasecheck.py plan
    python3 phasecheck.py secure --since 2026-10-27T09:51:44+00:00 --mode improve --json

--since TIME: the phase's report must be newer than TIME, the last go before the phase, so a report from
before test's fixes, from the build or from an earlier round does not count: test-plan.md (test),
parity.md (diff; also newer than bugs.md and features.csv, which the fix loop and forge-build build change),
security.md (secure), audit.md, inspect.md and improve.md, all in forge-work/.
--until TIME: the phase's own go, once it is done: a bugs.md or features.csv changed later is a later phase's.
--mode MODE: clone, idea or improve, for the checks that differ by mode (where test's specs are).
Without it, the mode in forge-work/state.json; without that, only the checks every mode shares.

Exit codes:
    0  every exit check passes
    1  a check fails: the output says which and why
    2  bad usage: an unknown phase or mode, or a TIME that is not like 2026-10-27T09:51:44+00:00
"""

import argparse
import datetime
import json
import os
import re
import shlex
import subprocess
import sys

TIMEOUT = 600  # seconds per script: a secret scan of a big project takes a while
HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(HERE, "..")  # the forge skill pack
PYTHON = shlex.quote(sys.executable) if os.name == "nt" and sys.executable else "python3"  # no python3 on Windows
MODES, PROFILES = ("clone", "idea", "improve"), ("laravel", "django", "next", "static")
UNSEEN = re.compile(r"<!--.*?(?:-->|\Z)|^ {0,3}(`{3,}|~{3,}).*?(?:^ {0,3}\1|\Z)", re.S | re.M)  # comments, code
FRESH = {"test": "forge-work/test-plan.md", "diff": "forge-work/parity.md", "secure": "forge-work/security.md",
         "audit": "forge-work/audit.md", "inspect": "forge-work/inspect.md", "improve": "forge-work/improve.md"}
INPUTS = {"diff": ("forge-work/bugs.md", "forge-work/features.csv")}  # a fresh report is newer than these too


def read_text(*parts):
    """The text of the file at PARTS. A missing file raises FileNotFoundError: run_checks says so."""
    with open(os.path.join(*parts), encoding="utf-8-sig") as handle:
        return handle.read()


def check_file(root, *names):
    """One of NAMES exists and has text. A template's placeholders are a doc check (doccheck.py)."""
    found = [name for name in names if os.path.isfile(os.path.join(root, name))]
    if not found:
        return False, "%s is missing" % " or ".join(names)
    text = read_text(root, found[0])
    return bool(text.strip()), "%s %s" % (found[0], "exists" if text.strip() else "is empty")


def cut(lines):
    """At most 12 lines: the start says what is wrong; the rest is one command away."""
    return lines if len(lines) <= 12 else lines[:11] + ["... %d more lines: run it to see them" % (len(lines) - 11)]


def check_line(root, name, label, *allowed):
    """Exactly one line about LABEL outside comments and code blocks, and it is `LABEL: value` with a value
    from ALLOWED. `**Label:** x`, `## label: x` and `> Label : x` are lines about it too, so they count."""
    text = UNSEEN.sub("", read_text(root, name))
    found = [line.rstrip() for line in re.findall(r"(?im)^[ \t>#*_]*%s[ \t*_]*:.*$" % label, text)]
    if len(found) == 1 and found[0].startswith(label + ":") and found[0][len(label) + 1:].strip() in allowed:
        return True, "%s says %s" % (name, found[0])
    return False, "%s needs exactly one line `%s: %s`, outside comments and code blocks (found: %s)" % (
        name, label, "|".join(allowed), " / ".join(found)[:120] or "none")


def check_json(root, name, *keys):
    """A JSON object (json.loads says where it breaks) with each of KEYS filled in: name a text, others a list."""
    data = json.loads(read_text(root, name))
    if not isinstance(data, dict):
        return False, "%s is not a JSON object" % name
    wrong = [key for key in keys if not isinstance(data.get(key), str if key == "name" else list)
             or not (data[key].strip() if key == "name" else data[key])]
    return not wrong, "%s parses" % name + "".join(', but "%s" is missing, empty or not a %s'
                                                   % (key, "text" if key == "name" else "list") for key in wrong)


def run_script(root, script, *args):
    """Run another forge script in ROOT: (exit code, None when it hung and -1 when it crashed; its output;
    its errors; the command as the skills write it). An argument that starts with ../ is a file of the
    pack. The script writes UTF-8 and is read as such, also where pipes are cp1252 (Windows)."""
    args = [os.path.join(PACK, arg[3:]) if arg.startswith("../") else arg for arg in args]
    shown = " ".join([PYTHON, "../" + script] + [arg.replace(PACK + os.sep, "../") for arg in args])
    try:
        done = subprocess.run([sys.executable, os.path.join(PACK, script)] + args, cwd=root, timeout=TIMEOUT,
                              stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8", errors="replace",
                              env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    except subprocess.TimeoutExpired:
        return None, "", "", shown
    crashed = "Traceback (most recent call last)" in done.stderr
    return -1 if crashed else done.returncode, done.stdout, done.stderr, shown


def ran(code, out, err, shown):
    """The answer for one run of a script: it passes when it exits 0 and printed its report. Every forge
    script prints what it checked, so no output means it checked nothing."""
    if code is None:
        return False, "%s did not finish within %d seconds" % (shown, TIMEOUT)
    if code == 0 and out.strip():
        return True, "%s exits 0" % shown
    meaning = ("it crashed: this is a bug in that script" if code == -1
               else "it printed nothing, so it checked nothing" if code == 0
               else {1: "it found problems", 2: "it could not check"}.get(code, "it stopped"))
    lines = [line.rstrip()[:200] for line in (err + out).splitlines() if line.strip()]
    return False, "%s exits %d: %s" % (shown, 1 if code == -1 else code, meaning), cut(lines)


def check_run(root, script, *args):
    """Run another forge skill's script in ROOT; on a failure, show what it printed."""
    return ran(*run_script(root, script, *args))


def check_tool(root, script, *args):
    """Run doccheck.py or workcheck.py, next to this script, with --json: each of its checks comes out as
    a line of this phase. When it cannot check (exit 2, a crash), it fails as check_run does."""
    code, out, err, shown = run_script(root, script, *(args + ("--json",)))
    try:
        if code in (0, 1):
            return [(item["ok"], item["what"], item["output"]) for item in json.loads(out)["checks"]]
    except (ValueError, KeyError, TypeError):
        pass
    return ran(code, out, err, shown)


def check_doc(root, name, *args):
    """NAME, a report, as doccheck.py checks it with ARGS. A missing NAME is named once, like any file."""
    if not os.path.isfile(os.path.join(root, name)):
        return False, "%s is missing" % name
    return check_tool(root, "forge/doccheck.py", name, *args)


def check_work(root, command, *args):
    """workcheck.py COMMAND ARGS: the feature list, the tokens, the specs, the screenshots, the name."""
    if command in ("features", "built", "tokens", "named") and not os.path.isfile(os.path.join(root, args[0])):
        return False, "%s is missing" % args[0]
    return check_tool(root, "forge/workcheck.py", command, *args)


def accepted(root, name):
    """The lines under ## Accepted risks in NAME that are not 'None': risks the user accepted in writing."""
    parts = re.split(r"(?im)^ {0,3}##[ \t]+accepted risks.*$", UNSEEN.sub("", read_text(root, name)), maxsplit=1)
    body = re.split(r"(?m)^ {0,3}#{1,2}[ \t]", parts[1])[0] if len(parts) > 1 else ""
    return [line for line in body.splitlines() if line.strip() and not re.match(r"(?i)[\W_]*none\b", line.strip())]


def check_scan(root, report, script, *args):
    """A scanner, as check_run runs it. Its exit 1 passes too when REPORT names risks the user accepted:
    forge-check secure lets the user accept one specific risk (The gate). Secrets never: they use check_run."""
    result = run_script(root, script, *args)
    answer = ran(*result)
    if result[0] != 1 or not accepted(root, report):
        return answer
    return True, "%s; %s has accepted risks: each finding must be one of them" % (answer[1], report), answer[2]


def check_counts(root, name):
    """The Counts line of forge-check secure's report. With Verdict: PASS, a critical or high finding counted
    there needs the user's acceptance under ## Accepted risks (forge-check secure, The gate)."""
    text = UNSEEN.sub("", read_text(root, name))
    lines = re.findall(r"(?im)^[ \t>*_]*counts[ \t*_]*:(.*)$", text)
    numbers = [re.search(r"(\d+)\s*%s" % word, lines[0]) if len(lines) == 1 else None
               for word in ("critical", "high")]
    if not all(numbers):
        return False, "%s needs one line `Counts: 0 critical, 0 high, 1 medium, 0 low`, as in forge-check secure's " \
                      "report (found: %s)" % (name, " / ".join(line.strip() for line in lines)[:80] or "none")
    serious = sum(int(number.group(1)) for number in numbers)
    if serious and re.search(r"(?m)^Verdict: PASS[ \t]*$", text) and not accepted(root, name):
        return False, "%s says Verdict: PASS but counts %d critical or high finding(s), and no risk is accepted: " \
                      "fix them, or write the user's own words for each under ## Accepted risks" % (name, serious)
    return True, "%s counts %d critical or high finding(s)%s" % (name, serious, ", accepted" if serious else "")


def check_fresh(root, name, since, until, *inputs):
    """NAME was written after SINCE, the last go before this phase, and after each of INPUTS that changed
    before UNTIL (the phase's own go, or None): an older report says nothing of now. The same time passes."""
    written = os.path.getmtime(os.path.join(root, name))
    if written < datetime.datetime.fromisoformat(since).timestamp():
        return False, "%s is older than the last go (%s): the app may have changed, or an earlier phase was " \
                      "recorded again. Run the phase's skill again in full, so it writes a new one" % (name, since)
    end = datetime.datetime.fromisoformat(until).timestamp() if until else float("inf")
    later = [other for other in inputs if os.path.isfile(os.path.join(root, other))
             and written < os.path.getmtime(os.path.join(root, other)) <= end]
    if later:
        return False, "%s is older than %s, which the fix loop or forge-build build changed after it. Run the " \
                      "phase's skill again from its first step, so it writes a new one" % (name, " and ".join(later))
    also = " and than " + " and ".join(inputs) + (" at its go (%s)" % until if until else "") if inputs else ""
    return True, "%s is newer than the last go (%s)%s" % (name, since, also)


def load_table(path):
    """{phase: [entry]} from phasecheck.json. An entry's check names a function here (check_ + the name)
    and its arguments; 'modes', 'profiles' and 'when' limit where it runs; 'why' is the skill line it rests on."""
    with open(path, encoding="utf-8") as handle:
        table = json.load(handle)
    return {phase: [dict(entry, run=globals()["check_" + entry["check"][0]], args=entry["check"][1:])
                    for entry in entries] for phase, entries in table.items() if not phase.startswith("_")}


def mode_of(root):
    """The mode in forge-work/state.json (gate.py writes it there), or None."""
    try:
        mode = json.loads(read_text(root, "forge-work", "state.json")).get("mode")
    except (OSError, ValueError, AttributeError, RecursionError):
        return None
    return mode if mode in MODES else None


def profile_of(root):
    """The profile on plan.md's one Profile: line, or None: no plan.md (forge-build pack on its own), no line."""
    try:
        found = re.findall(r"(?im)^[ \t>#*_]*profile[ \t*_]*:(.*)$",
                           UNSEEN.sub("", read_text(root, "forge-work", "plan.md")))
    except (OSError, ValueError):
        return None
    return found[0].strip() if len(found) == 1 and found[0].strip() in PROFILES else None


def run_checks(root, phase, since=None, mode=None, until=None):
    """Every exit check of PHASE in ROOT for MODE (None: not known) and plan.md's profile, plus the age of
    its report when SINCE is given: a list of {"ok", "what", "output"}. A missing file is named once. A
    check with 'when' runs only when that path is there; else its line says it was skipped."""
    profile = profile_of(root)
    entries = [entry for entry in CHECKS[phase] if mode in entry.get("modes", [mode])
               and profile in entry.get("profiles", [profile])]
    fresh = [{"run": check_fresh, "args": [FRESH[phase], since, until, *INPUTS.get(phase, ())]}] \
        if since and phase in FRESH else []
    results = []
    for entry in entries + fresh:
        try:
            if "when" in entry and not os.path.exists(os.path.join(root, entry["when"])):
                answers = True, "%s skipped: no %s" % (" ".join(entry["args"]), entry["when"])
            else:
                answers = entry["run"](root, *entry["args"])
        except FileNotFoundError:
            answers = False, "%s is missing" % entry["args"][0]
        except (OSError, ValueError, RecursionError) as error:  # a folder, or not UTF-8 or JSON
            answers = False, "%s cannot be read: %s" % (entry["args"][0], error)
        for answer in answers if isinstance(answers, list) else [answers]:
            if answer[1] not in [item["what"] for item in results]:
                output = list(answer[2]) if len(answer) > 2 else []
                why = ["why: " + entry["why"]] if not answer[0] and entry.get("why") else []
                results.append({"ok": answer[0], "what": answer[1], "output": output + why})
    return results


def show_checks(phase, results, as_json=False, mode=None):
    """Print the results, in plain words or as JSON. Returns 0 when every check passed, else 1."""
    ok = all(item["ok"] for item in results)
    if as_json:
        print(json.dumps({"phase": phase, "mode": mode, "ok": ok, "checks": results}, indent=2))
        return 0 if ok else 1
    print("Exit checks for %s (%s):" % (phase, mode + " mode" if mode else "no mode known: only the checks "
                                        "every mode has"))
    for item in results:
        print("\n".join(["  %-4s  %s" % ("ok" if item["ok"] else "FAIL", item["what"])]
                        + ["          " + line for line in item["output"]]))
    print("PASS: every exit check of %s passes." % phase if ok else "FAIL: %s is not finished. Fix what "
          "FAIL names within the phase, or ask the user. Never work around the gate." % phase)
    return 0 if ok else 1


def a_time(text):
    """argparse type for --since: an ISO 8601 time, as gate.py writes it."""
    try:
        datetime.datetime.fromisoformat(text).timestamp()
    except ValueError:
        raise argparse.ArgumentTypeError("not a time like 2026-10-27T09:51:44+00:00: %r" % text)
    return text


CHECKS = load_table(os.path.join(HERE, "phasecheck.json"))


def main(argv=None):
    """Run the exit checks of one phase. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):  # what the console cannot show comes out as \u escapes, not a crash
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("phase", choices=list(CHECKS))
    parser.add_argument("--since", type=a_time, metavar="TIME", help="the report must be newer than this time")
    parser.add_argument("--until", type=a_time, metavar="TIME", help="the phase's own go, once it is done")
    parser.add_argument("--mode", choices=MODES, help="the forge mode (default: the one in forge-work/state.json)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    mode = args.mode or mode_of(os.getcwd())
    return show_checks(args.phase, run_checks(os.getcwd(), args.phase, args.since, mode, args.until), args.json, mode)


if __name__ == "__main__":
    sys.exit(main())
