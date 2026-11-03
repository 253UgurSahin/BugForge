#!/usr/bin/env python3
"""The forge gate: which phase comes next, and may this phase be marked done?

forge-work/state.json records the mode and each phase that is done (with the user's words of go and
the time) or skipped (with the reason). A phase is done only when its exit checks pass (phasecheck.py,
next to this script), the user's words are given and every earlier phase (MODES) is done or skipped.
Only this script writes state.json: a temporary file first, then a rename. Run it from the project root.
init also writes forge-work/.gitignore (`*`), so git never picks up the notes and screenshots in there.

Usage:
    python3 gate.py init --mode idea --about 'a booking app for my salon'   (clone, idea or improve)
    python3 gate.py status                  every phase and the next step (status and check: --json)
    python3 gate.py check plan              the exit checks of one phase
    python3 gate.py done plan --approved 'ja, ga door'
    python3 gate.py skip compare --reason 'no rivals worth reading'     (compare and inspect only)

Exit codes:
    0  state started, checks passed, phase recorded, or status shown
    1  refused: a check fails, no words of go or no reason, an earlier phase is still open, the
       phase may not be skipped, or a state exists already (init without --force)
    2  a phase that is not in this mode, or a damaged state.json; for status, done and skip also no
       state.json in this folder (check then only looks at the files, so run status first)
"""

import argparse
import datetime
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unicodedata

STATE = os.path.join("forge-work", "state.json")
VERSION = 1  # of the state.json format
TIMEOUT = 1800  # seconds for one phase's exit checks: up to two scripts of 600 seconds each, and more
MODES = {
    "clone": ["recon", "compare", "plan", "design", "build", "test", "diff", "brand", "launch", "secure", "pack"],
    "idea": ["compare", "plan", "design", "build", "test", "brand", "launch", "secure", "pack"],
    "improve": ["audit", "inspect", "improve", "test", "secure"],
}
PHASES = list(dict.fromkeys(phase for phases in MODES.values() for phase in phases))
OPTIONAL = ("compare", "inspect")  # may be skipped with the user's reason; secure never
PYTHON = shlex.quote(sys.executable) if os.name == "nt" and sys.executable else "python3"  # no python3 on Windows
PLACEHOLDER = re.compile(r"^(<.*>|\{\{.*\}\}|TEXT)$", re.S)  # copied from the docs, not said by the user
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:[+-]\d\d:\d\d)?\Z")  # as this script writes it
# What a terminal hides or acts on (control and format characters such as a zero-width space, line
# separators): never counted as words, and shown as \u escapes so the user sees what was stored.
ESCAPE = {code: "\\u%04x" % code for code in [*range(0x10000), *range(0xE0000, 0xE0080)]
          if unicodedata.category(chr(code)) in ("Cc", "Cf", "Cs", "Zl", "Zp")}


class StateError(Exception):
    """No state.json, a damaged one, or a phase that is not in its mode (exit 2)."""


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def shows(text):
    """TEXT has a character a reader sees: more than spaces, line breaks, control and format characters."""
    return any(ord(char) not in ESCAPE and not char.isspace() for char in text)


def quote(text):
    """TEXT in double quotes as JSON writes it, with hidden and control characters as \\u escapes."""
    return json.dumps(text, ensure_ascii=False).translate(ESCAPE)


def state_problem(state):
    """What is wrong with a loaded state.json, in plain words, or None. Only what gate.py writes passes:
    the gate keeps the phases in order, so a gap, a missing time or a placeholder means a hand edit."""
    if not (isinstance(state, dict) and type(state.get("version")) is int and state["version"] == VERSION
            and str(state.get("mode")) in MODES and isinstance(state.get("phases"), dict)
            and TIME.match(str(state.get("started")))):
        return "it is not a forge state: version %d, a mode (clone, idea or improve), phases, a start time" % VERSION
    for phase, entry in state["phases"].items():
        entry = entry if isinstance(entry, dict) else {}
        words = entry.get({"done": "approved", "skipped": "reason"}.get(str(entry.get("status"))))
        if (phase not in MODES[state["mode"]] or not isinstance(words, str) or not shows(words)
                or PLACEHOLDER.match(words.strip()) or not TIME.match(str(entry.get("at")))
                or (entry["status"] == "skipped" and phase not in OPTIONAL)):
            return "%r is not a %s phase done with the user's words or skipped with a reason, at a time" % (
                phase, state["mode"])
    recorded = [phase for phase in MODES[state["mode"]] if phase in state["phases"]]
    if recorded and still_open(state, recorded[-1]):
        return "%s is recorded while %s before it is not" % (recorded[-1], ", ".join(still_open(state, recorded[-1])))
    return None


def load_state(root, phase=None):
    """The state in ROOT. StateError when it is missing or damaged, or PHASE is not in its mode."""
    path = os.path.join(root, STATE)
    if not os.path.lexists(path):
        raise StateError("no forge state in %s. Run gate.py in the project root, or start: gate.py init" % path)
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
        problem = state_problem(state)
    except (OSError, ValueError, RecursionError) as error:
        state, problem = None, "it cannot be read as JSON (%s)" % error
    if problem:
        raise StateError("%s is damaged: %s. Do not guess what it said: tell the user. Only with their go: gate.py "
                         "init --mode <mode> --force (work files stay, approvals go)." % (path, problem))
    if phase and phase not in MODES[state["mode"]]:
        raise StateError("%s is not a phase of %s mode: %s" % (phase, state["mode"], ", ".join(MODES[state["mode"]])))
    return state


def save_state(root, state):
    """Write state.json whole: a temporary file next to it, then a rename over the old one."""
    handle, temp = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=os.path.join(root, "forge-work"))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, os.path.join(root, STATE))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def still_open(state, phase=None):
    """The phases before PHASE (or all phases) that are not done or skipped yet."""
    order = MODES[state["mode"]]
    return [name for name in order[:order.index(phase) if phase else None] if name not in state["phases"]]


def last_go(state, phase):
    """The time of the last go before PHASE: the start, or the latest phase before it that was recorded."""
    order, stamp = MODES[state["mode"]], lambda at: datetime.datetime.fromisoformat(at).timestamp()
    return max([state["started"]] + [entry["at"] for name, entry in state["phases"].items()
                                     if order.index(name) < order.index(phase)], key=stamp)


def exit_checks(root, phase, state=None, as_json=False):
    """Run phasecheck.py for PHASE in ROOT and show what it says. With a STATE, the checks are those of its
    mode, and the phase's report must be newer than the last go before it. Returns 0 when every check
    passes, else 1."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phasecheck.py")
    command = [sys.executable, script, phase] + (
        ["--mode", state["mode"], "--since", last_go(state, phase)] if state else [])
    try:
        done = subprocess.run(command + (["--json"] if as_json else []), cwd=root, stdin=subprocess.DEVNULL,
                              capture_output=True, encoding="utf-8", errors="replace", timeout=TIMEOUT,
                              env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    except subprocess.TimeoutExpired:
        print("FAIL: the exit checks of %s did not finish within %d seconds." % (phase, TIMEOUT))
        return 1
    print(done.stdout, end="")
    print(done.stderr, end="", file=sys.stderr)
    return 0 if done.returncode == 0 else 1


def next_step(state):
    """The next step in plain words, with the commands to run."""
    waiting, gate = still_open(state), PYTHON + " " + shlex.quote(os.path.abspath(__file__))
    if not waiting:
        return "All phases are done. Tell the user what they have now, what is left, and that shipping is their step."
    text = ("Next: {0}. Run /forge-{0}, then {1} check {0}. Show the user a checkpoint (5 plain lines) and "
            "wait for their go. Then: {1} done {0} --approved '<their exact words>'").format(waiting[0], gate)
    skip = ". Or, when the user says so: {1} skip {0} --reason '<their reason>'".format(waiting[0], gate)
    return text + (skip if waiting[0] in OPTIONAL else "")


def refuse(text):
    print("REFUSED: " + text)
    return 1


def cmd_init(root, args):
    if os.path.lexists(os.path.join(root, STATE)) and not args.force:
        return refuse("%s exists already. Resume with: gate.py status. Start over only when the user asks for "
                      "it: gate.py init --mode %s --force (forgets every approval)." % (STATE, args.mode))
    os.makedirs(os.path.join(root, "forge-work"), exist_ok=True)
    with open(os.path.join(root, "forge-work", ".gitignore"), "w", encoding="utf-8") as handle:
        handle.write("# forge notes, reports and screenshots: git ignores this whole folder, from the start\n*\n")
    state = {"version": VERSION, "mode": args.mode, "phases": {}, "started": now()}
    if shows(args.about or ""):  # what the user asked for, in their words, so a later session knows it too
        state["about"] = args.about.strip()
    save_state(root, state)
    print("Started forge in %s mode in %s.\nPhases: %s.\n%s"
          % (args.mode, root, ", ".join(MODES[args.mode]), next_step(state)))
    return 0


def cmd_status(root, args):
    state, rows = load_state(root), []
    for phase in MODES[state["mode"]]:
        entry = state["phases"].get(phase, {})
        status = entry.get("status") or ("next" if phase == still_open(state)[0] else "waiting")
        rows.append(dict(entry, phase=phase, status=status, skill="forge-" + phase, optional=phase in OPTIONAL))
    if args.json:
        print(json.dumps({"mode": state["mode"], "about": state.get("about"), "started": state["started"],
                          "phases": rows, "next_step": next_step(state)}, indent=2))
        return 0
    print("forge, %s mode, started %s" % (state["mode"], state["started"]))
    print("About: %s\n" % quote(state["about"]) if "about" in state else "")
    for row in rows:
        detail = "/" + row["skill"] + ("  (may be skipped)" if row["optional"] else "")
        if row["status"] in ("done", "skipped"):  # quote() shows line breaks and hidden characters as escapes
            label = "approved" if row["status"] == "done" else "reason"
            detail = "%s  %s: %s" % (row["at"], label, quote(row[label]))
        print("%-8s %-8s %s" % (row["status"], row["phase"], detail))
    print("\n" + next_step(state))
    return 0


def cmd_check(root, args):
    """The exit checks. With a state.json here, a phase of another mode is refused (exit 2) and the
    phase's report must be newer than the last go. Without one, it only looks at the files."""
    state = load_state(root, args.phase) if os.path.lexists(os.path.join(root, STATE)) else None
    return exit_checks(root, args.phase, state, args.json)


def cmd_mark(root, args):
    """done and skip: record a phase, after every check the gate asks for."""
    state, phase, skipping = load_state(root, args.phase), args.phase, args.command == "skip"
    words = (args.reason if skipping else args.approved).strip()
    if skipping and phase not in OPTIONAL:
        return refuse("secure can never be skipped: nothing ships without Verdict: PASS." if phase == "secure"
                      else "%s cannot be skipped. Only %s may be." % (phase, " and ".join(OPTIONAL)))
    if not shows(words) or PLACEHOLDER.match(words):
        return refuse("--reason needs the user's reason for skipping it." if skipping else "--approved needs "
                      "the user's own words of go, as they typed them in this chat. No go yet: wait for it.")
    if still_open(state, phase):
        return refuse("%s comes after %s: not done or skipped yet. See gate.py status."
                      % (phase, ", ".join(still_open(state, phase))))
    if not skipping and exit_checks(root, phase, state):
        return refuse("%s stays open until every check passes." % phase)
    entry = {"status": "skipped", "reason": words} if skipping else {"status": "done", "approved": words}
    state["phases"][phase] = dict(entry, at=now())
    save_state(root, state)
    print("Recorded: %s %s. %s: %s\n%s" % (phase, entry["status"], "Reason" if skipping else "The user said",
                                           quote(words), next_step(state)))
    return 0


def main(argv=None):
    """Run one gate command. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):  # what the console cannot show comes out as \u escapes, not a crash
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)
    init = commands.add_parser("init", help="start forge-work/state.json for a mode")
    init.add_argument("--mode", required=True, choices=list(MODES))
    init.add_argument("--about", metavar="TEXT", help="what the user asked for, in their words: idea, URL or repo")
    init.add_argument("--force", action="store_true", help="replace an existing state: every approval is forgotten")
    status = commands.add_parser("status", help="show every phase and the next step")
    check = commands.add_parser("check", help="run the exit checks of a phase")
    done = commands.add_parser("done", help="mark a phase done after the user's go (runs its checks first)")
    done.add_argument("--approved", required=True, metavar="TEXT", help="the user's exact words of go")
    skip = commands.add_parser("skip", help="skip an optional phase: %s" % ", ".join(OPTIONAL))
    skip.add_argument("--reason", required=True, metavar="TEXT", help="the user's reason")
    for command in (check, done, skip):
        command.add_argument("phase", choices=PHASES)
    for command in (status, check):
        command.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    run = {"init": cmd_init, "status": cmd_status, "check": cmd_check, "done": cmd_mark, "skip": cmd_mark}
    try:
        return run[args.command](os.getcwd(), args)
    except (StateError, OSError, UnicodeError) as error:  # OSError: state.json could not be written, for one
        print("error: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
