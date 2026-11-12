#!/usr/bin/env python3
"""The level of a forge skill: how far it goes, from 1 to 5, as the user chose it.

levels.json, next to this script, holds the domains (look, dashboard, test, secure) and for each level
its names in English and Dutch, aliases, a one-line summary, what it includes and the evidence the gate
asks for; a level includes every level below it. This script shows that table, records the user's choice
in forge-work/levels.json with their own words and the time (only this script writes it: a temporary
file, then a rename) and checks the work against it. Run it from the project root. Inside a forge
project (forge-work/state.json is there) a domain never runs below its floor: set raises a lower level
to it and says so, get and check refuse a lower one on record.

Usage:
    python3 level.py show [DOMAIN] [--nl]            the table, to paste into a question (--nl: in Dutch)
    python3 level.py set DOMAIN LEVEL --said 'niveau 4 graag'       DOMAIN: one domain, or all
    python3 level.py get DOMAIN                      the chosen number and name      (each takes --json)
    python3 level.py check DOMAIN [--report FILE] [--since TIME]   is the work at the chosen level?

LEVEL: 1 to 5, or a name or alias from the table, English or Dutch, in any letter case; a name that only
another domain has counts as its number. --said: the user's own words, as typed. check passes when a
level is chosen, FILE has exactly one line `Level: N` for it (`Level: 2 (Name)` too) and each evidence
pattern up to that level fits a file that holds something: no link, none in node_modules, and with
--since (the last go) none in forge-work/ older than TIME; or FILE says why, where levels.json allows it.

Exit codes:
    0  shown, recorded, a level is chosen (get), every check passes (check)
    1  no level chosen yet or one below the floor (get, check: the output says what to ask or do),
       --said without the user's words (set), the report or the evidence is not at the level (check)
    2  bad usage, a LEVEL the table does not know, a damaged or linked forge-work/levels.json (a link is
       never read), a linked forge-work (nothing written), a FILE that is a link or cannot be read, or a
       broken levels.json next to this script
"""

import argparse
import datetime
import fnmatch
import json
import os
import re
import sys
import tempfile
import unicodedata

TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "levels.json")  # every name and requirement
RECORD = os.path.join("forge-work", "levels.json")  # the user's choice, in the project
STATE = os.path.join("forge-work", "state.json")  # gate.py's: where it is, this is a forge project
MAX_BYTES = 1000 * 1000  # a bigger record or report is refused, not read
LINKED = ("%s is a link. forge reads and writes only files of its own in the project, so it did nothing. "
          "Change nothing yourself: tell the user and ask them to look (ls -la forge-work).")
IGNORE = "# forge notes, reports and screenshots: git ignores this whole folder, from the start\n*\n"  # as gate.py
PLACEHOLDER = re.compile(r"^(<.*>|\{\{.*\}\}|TEXT)$", re.S)  # copied from the docs, not said by the user
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d\Z")  # as this script writes it
UNSEEN = re.compile(r"<!--.*?(?:-->|\Z)|^ {0,3}(`{3,}|~{3,}).*?(?:^ {0,3}\1|\Z)", re.S | re.M)  # comments, code
ABOUT = re.compile(r"(?im)^[ \t>#*_]*level[ \t*_]*:.*$")  # a report's line about the level, decorated or not
TEXTS, LISTS = ("name", "nl", "summary", "summary_nl"), ("aliases", "includes", "evidence")


class LevelError(Exception):
    """A broken table, an unknown LEVEL, a damaged or linked record, a linked forge-work or report (exit 2)."""


def spoken(text):
    """TEXT holds words of the user's own: a character a reader sees, and no placeholder copied from the docs."""
    return not PLACEHOLDER.match(text.strip()) and any(
        not char.isspace() and unicodedata.category(char) not in ("Cc", "Cf", "Cs", "Zl", "Zp") for char in text)


def load_table(path):
    """{domain: its entry} from the levels.json at PATH. LevelError when it is missing or broken."""
    try:
        with open(path, encoding="utf-8") as handle:
            table = json.load(handle)["domains"]
        for domain in table.values():
            rows = domain["levels"]
            texts = [domain["about"], domain["about_nl"]] + [row[key] for row in rows for key in TEXTS]
            texts += [item for row in rows for key in LISTS for item in row[key] + []]
            texts += [row["evidence_how"] for row in rows if row["evidence"]] + [words if set(files) <= set(row[
                "evidence"]) else None for row in rows for words, files in row.get("evidence_or", {}).items()]
            if ([row["level"] for row in rows] != [1, 2, 3, 4, 5] or str(domain.get("floor", 1)) not in list("12345")
                    or not all(isinstance(text, str) and text for text in texts)):
                raise ValueError("a domain needs about, about_nl and the levels 1 to 5 in order, each text a text")
    except (OSError, ValueError, LookupError, TypeError, AttributeError, RecursionError) as error:
        raise LevelError("%s is missing or broken (%s)" % (path, error))
    return table


def resolve(table, names, text):
    """The number TEXT means for the domains NAMES: 1 to 5, or a name or alias in English or Dutch, in any letter
    case. A name that only another domain has counts as its number there: it is one scale. LevelError: none, two."""
    word = " ".join(re.split(r"[\s_-]+", text.casefold())).strip()
    levels = {name: {row["level"] for row in table[name]["levels"] if word in [
        item.casefold() for item in [row["name"], row["nl"]] + row["aliases"]]} for name in table}
    found = {int(word)} if re.fullmatch("[1-5]", word) else (
        set().union(*(levels[name] for name in names)) or set().union(*levels.values()))
    if len(found) != 1:
        raise LevelError("LEVEL %s is %s. Give a number from 1 to 5, or a name the table shows (level.py show)." % (
            json.dumps(text), "more than one level %s" % sorted(found) if found else "no level"))
    return found.pop()


def load_record(root, table):
    """{domain: {"level", "said", "at"}} from forge-work/levels.json in ROOT; {} when there is none. LevelError
    when it is a link (never read) or damaged: only what this script writes passes."""
    path = os.path.join(root, RECORD)
    if os.path.islink(path):  # it could point anywhere: a pipe would hang this, /dev/zero fill the memory
        raise LevelError(LINKED % RECORD)
    if not os.path.lexists(path):
        return {}
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > MAX_BYTES:
            raise ValueError("not a file, or over %d bytes" % MAX_BYTES)
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
        for name, entry in record.items():
            if (name not in table or type(entry["level"]) is not int or not 1 <= entry["level"] <= 5
                    or not spoken(entry["said"]) or not TIME.match(entry["at"])
                    or not datetime.datetime.fromisoformat(entry["at"])):
                raise ValueError("%r is not a domain with a level from 1 to 5, the user's words and a time" % name)
    except (OSError, ValueError, LookupError, TypeError, AttributeError, RecursionError) as error:
        raise LevelError("%s is damaged: not what level.py writes (%s: %s). Do not guess a level: tell the user. "
                         "With their go, delete that file and record each level again."
                         % (RECORD, type(error).__name__, error))
    return record


def save(root, record):
    """Write ROOT's forge-work/levels.json whole: a temporary file next to it, then a rename over the old one.
    Makes forge-work when it is missing, and gate.py init's .gitignore in it when it has none. Never into a
    linked forge-work (LevelError); words that are not text stop it before anything is written (UnicodeError)."""
    folder, text = os.path.join(root, "forge-work"), json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    if os.path.islink(folder):
        raise LevelError(LINKED % "forge-work")
    text.encode("utf-8")
    os.makedirs(folder, exist_ok=True)
    ignore = [] if os.path.lexists(os.path.join(folder, ".gitignore")) else [(".gitignore", IGNORE)]
    for name, body in ignore + [("levels.json", text)]:
        handle, temp = tempfile.mkstemp(prefix=".forge-", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
                out.write(body)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, os.path.join(folder, name))
        finally:
            if os.path.exists(temp):
                os.unlink(temp)


def find(folder, parts, since=None, shown=""):
    """The first file below FOLDER that the pattern PARTS fits (** is any folders, also none, never a .hidden one),
    holding something and, in forge-work/, not older than SINCE: its path, or None. No link, node_modules, 30+ deep."""
    found = find(folder, parts[1:], since, shown) if parts[0] == "**" and len(parts) > 1 else None  # ** as none
    for name in [] if found or not os.path.isdir(folder) else sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if os.path.islink(path) or name == "node_modules" or not fnmatch.fnmatch(name, parts[0].replace("**", "[!.]*")):
            continue
        if os.path.isdir(path) and (parts[0] == "**" or len(parts) > 1) and shown.count("/") < 30:
            found = find(path, parts if parts[0] == "**" else parts[1:], since, shown + name + "/")
        elif len(parts) == 1 and os.path.isfile(path) and os.path.getsize(path):  # a run's record: of this run
            found = shown + name if shown[:11] != "forge-work/" or os.path.getmtime(path) >= (since or 0) else None
        if found:
            break
    return found


def report_says(root, name, row):
    """The report NAME in ROOT: its text outside comments and code blocks ("": it is missing), and the check of
    its one `Level: N` line against ROW, the chosen level, as (ok, what, what to do)."""
    path, want = os.path.join(root, name), "Level: %d (%s)" % (row["level"], row["name"])
    if not os.path.lexists(path):
        return "", (False, "%s is missing" % name, ["Write the report, with one line `%s`." % want])
    if os.path.islink(path) or not os.path.isfile(path) or os.path.getsize(path) > MAX_BYTES:
        raise LevelError("%s is a link, not a file or over %d bytes: no report this script reads" % (name, MAX_BYTES))
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        text = UNSEEN.sub("", handle.read())
    found, names = [line.rstrip() for line in ABOUT.findall(text)], "|".join(map(re.escape, (row["name"], row["nl"])))
    if len(found) == 1 and re.match(r"Level: *%d(?: *\(?(?i:%s)\)?)?\Z" % (row["level"], names), found[0]):
        return text, (True, "%s says %s" % (name, found[0]), [])
    return text, (False, "%s needs exactly one line `%s`, outside comments and code blocks (found: %s)" % (
        name, want, " / ".join(found)[:120] or "none"), [
            "The user chose level %d: do its work, then say so. Another level is the user's call." % row["level"]])


def chosen(table, root, name):
    """(NAME's record in ROOT or None, its row in the table, why it cannot be worked at and what to do or None)."""
    entry = load_record(root, table).get(name)
    low = table[name].get("floor", 1) if os.path.lexists(os.path.join(root, STATE)) else 1
    if not entry:
        return None, None, ("No level chosen for {0} yet: ask the user. python3 level.py show {0} shows the choices. "
                            "Then record the answer: level.py set {0} LEVEL --said '<their words>'".format(name))
    return entry, table[name]["levels"][entry["level"] - 1], None if entry["level"] >= low else (
        "{0} is on record at level {1}, and inside a forge project it never runs below {2}. Record it again, and "
        "tell the user: level.py set {0} {2} --said '<their words for it>'".format(name, entry["level"], low))


def cmd_show(table, root, args):
    """show: the table of one domain, or of every domain, in English or Dutch."""
    names, blocks, nl = [args.domain] if args.domain else list(table), [], "_nl" if args.nl else ""
    for name in names:
        rows = [("%d %s" % (row["level"], row["nl" if nl else "name"]) + ("" if row["nl"] == row["name"] else
                 " (%s)" % row["name" if nl else "nl"]), row["summary" + nl]) for row in table[name]["levels"]]
        blocks.append("\n".join(["%s: %s" % (name, table[name]["about" + nl])] + [
            "  %-*s  %s" % (max(len(first) for first, _ in rows), first, second) for first, second in rows]))
    print(json.dumps({"domains": {name: table[name] for name in names}}, indent=2) if args.json
          else "\n\n".join(blocks))
    return 0


def cmd_set(table, root, args):
    """set: record the level of one domain, or of all, with the user's words and the time."""
    words, names = args.said.strip(), list(table) if args.domain == "all" else [args.domain]
    if not spoken(words):
        print("REFUSED: --said needs the user's own words for this level, as they typed them in this chat. "
              "No level given yet: ask them, with the table of level.py show.")
        return 1
    level, record, notes = resolve(table, names, args.level), load_record(root, table), []
    at, inside = datetime.datetime.now().astimezone().isoformat(timespec="seconds"), os.path.lexists(
        os.path.join(root, STATE))
    for name in names:
        record[name] = {"level": max(level, table[name].get("floor", 1) if inside else 1), "said": words, "at": at}
        if record[name]["level"] != level:
            notes.append("Note: %s was asked at level %d and is on record at %d: inside a forge project it never "
                         "runs below that. Tell the user." % (name, level, record[name]["level"]))
    save(root, {name: record[name] for name in table if name in record})
    done = {name: dict(record[name], name=table[name]["levels"][record[name]["level"] - 1]["name"]) for name in names}
    print(json.dumps({"recorded": done, "notes": notes}, indent=2) if args.json else "\n".join([
        "Recorded in %s: %s. The user said: %s" % (RECORD, ", ".join(
            "%s %d %s" % (name, entry["level"], entry["name"]) for name, entry in done.items()), json.dumps(words))]
        + notes))
    return 0


def cmd_check(table, root, args):
    """get: the chosen level. check: also that the report says the same one and the evidence up to it is there."""
    name, text, fits = args.domain, "", lambda item: find(root, item.split("/"), args.since and args.since.timestamp())
    entry, top, problem = chosen(table, root, name)
    if args.command == "get":
        print(json.dumps(dict(entry or {"level": None}, domain=name, name=top and top["name"], problem=problem),
                         indent=2) if args.json else problem or "%d %s" % (entry["level"], top["name"]))
        return 1 if problem else 0
    checks = [(False, problem, [])] if problem else [(True, "%s is at level %d %s: the user said %s" % (
        name, entry["level"], top["name"], json.dumps(entry["said"])), [])]
    if args.report and not problem:
        text, check = report_says(root, args.report, top)
        checks.append(check)
    for row in table[name]["levels"][:0 if problem else entry["level"]]:
        missing, ways = [item for item in row["evidence"] if not fits(item)], row.get("evidence_or", {})
        why = {item: [line.strip() for words in ways if item in ways[words] for line in text.splitlines()
                      if re.search(re.escape(words) + r"(\W+\w+){3}", line, re.I)] for item in missing}
        if left := [item for item in missing if not why[item]]:  # its words, then why: three words or more
            checks.append((False, "level %d asks for a file that holds something (links and node_modules do not "
                           "count%s): %s" % (row["level"], args.since and ", nor in forge-work/ one older than "
                           "--since" or "", ", ".join(left)), [row["evidence_how"]] + ["Or a line in the report with "
                           "the words '%s' and then why, for %s." % (way, " and ".join(ways[way])) for way in ways]))
        elif row["evidence"]:
            said = missing and "%s not there, the report says why: %s" % (", ".join(missing), why[missing[0]][0][:120])
            checks.append((True, "level %d asks for %s: %s" % (row["level"], ", ".join(row["evidence"]), said or
                           "there"), []))
    passed = all(ok for ok, _, _ in checks)
    if args.json:
        print(json.dumps({"domain": name, "level": entry["level"] if entry else None, "ok": passed, "checks": [
            {"ok": ok, "what": what, "output": more} for ok, what, more in checks]}, indent=2))
    else:
        for ok, what, more in checks:
            print("\n".join(["  %-4s  %s" % ("ok" if ok else "FAIL", what)] + ["          " + line for line in more]))
        print("PASS: %s is at the level the user chose." % name if passed else "FAIL: %s does not pass. Do what "
              "FAIL names: the work, never a file written only to pass. Another level is the user's call." % name)
    return 0 if passed else 1


def main(argv=None):
    """Run one level command. Returns the exit code: 0, 1 or 2 (see the top)."""
    for stream in (sys.stdout, sys.stderr):  # what the console cannot show comes out as \u escapes, not a crash
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    try:
        table = load_table(TABLE)
        parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
        commands = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)
        for name, run, words in (("show", cmd_show, "the levels as a short table, to paste into a question"),
                                 ("set", cmd_set, "record the level the user chose, with their own words"),
                                 ("get", cmd_check, "the chosen number and name"),
                                 ("check", cmd_check, "is the work at the chosen level?")):
            command = commands.add_parser(name, help=words)
            command.set_defaults(run=run)
            command.add_argument("domain", choices=list(table) + ["all"] * (name == "set"), help="what has the level",
                                 nargs="?" if name == "show" else None)
            command.add_argument("--json", action="store_true", help="print machine-readable JSON")
        commands.choices["show"].add_argument("--nl", action="store_true", help="in Dutch")
        commands.choices["set"].add_argument("level", metavar="LEVEL", help="1 to 5, or a name in English or Dutch")
        commands.choices["set"].add_argument("--said", required=True, metavar="TEXT", help="the user's own words")
        commands.choices["check"].add_argument("--report", metavar="FILE", help="the report, with one line `Level: N`")
        commands.choices["check"].add_argument("--since", metavar="TIME", type=datetime.datetime.fromisoformat)
        args = parser.parse_args(argv)
        return args.run(table, os.getcwd(), args)
    except (LevelError, OSError, UnicodeError, RecursionError) as error:  # OSError: forge-work cannot be written
        print("error: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
