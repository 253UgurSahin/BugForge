"""Tests for forge/level.py and its data, forge/levels.json: the table as the spec has it, show in English
and Dutch, set by number, name and alias in any letter case, the record it writes whole, the floor of secure
inside a forge project, get, check (the report's Level line, the evidence files, the reason in the report),
every exit code, a damaged or linked record, a linked forge-work, a console that cannot show the words, and
that forge/levels.md names what levels.json holds. Every test works in its own temporary project folder."""

import contextlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252, symlink  # noqa: E402

level = load("forge", "level")
SCRIPT = os.path.join(ROOT, "forge", "level.py")
TABLE = level.load_table(level.TABLE)
RECORD = os.path.join("forge-work", "levels.json")
LOOK = [("Subtle", "Subtiel"), ("Polished", "Verzorgd"), ("Expressive", "Expressief"), ("Showpiece", "Showpiece"),
        ("Cinematic", "Cinematisch")]
DEPTH = [("Quick", "Snel"), ("Basic", "Basis"), ("Standard", "Standaard"), ("Thorough", "Grondig"),
         ("Exhaustive", "Uitputtend")]
NAMES = {"look": LOOK, "dashboard": LOOK, "test": DEPTH, "secure": DEPTH}  # the spec, section 2
MISSING = "level %d asks for a file that holds something (links and node_modules do not count): %s"


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class Project(unittest.TestCase):
    """A temporary project folder; level.py runs in it as if from the project root."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.work = os.path.join(self.root, "forge-work")

    def run_main(self, script, *args):
        """Run a script's main() in the project. Returns (exit code, stdout, stderr)."""
        out, err, before = io.StringIO(), io.StringIO(), os.getcwd()
        os.chdir(self.root)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = script.main(list(args))
        finally:
            os.chdir(before)
        return code, out.getvalue(), err.getvalue()

    def level(self, *args):
        return self.run_main(level, *args)

    def gate(self, *args):
        """Run gate.py in the project: the forge state as /forge starts it. Loaded here, so only the tests that
        need the gate depend on it."""
        return self.run_main(load("forge", "gate"), *args)

    def check(self, *args):
        """Run check with --json. Returns (exit code, what it printed as data)."""
        code, out, err = self.level("check", *args, "--json")
        self.assertIn(code, (0, 1), err)
        return code, json.loads(out)

    def choose(self, domain, number):
        code, _, err = self.level("set", domain, str(number), "--said", "niveau %d" % number)
        self.assertEqual(code, 0, err)

    def record(self):
        return json.loads(self.record_text())

    def record_text(self):
        return read(os.path.join(self.work, "levels.json"))

    def write(self, name, text="x\n"):
        path = os.path.join(self.root, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return path

    def forge(self):
        """Make this a forge project: the state that gate.py keeps is there."""
        self.write("forge-work/state.json", "{}\n")

    def outside(self, name, text):
        """A file NAME with TEXT in a folder outside the project. Returns the folder."""
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        with open(os.path.join(folder, name), "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return folder


class TableTests(Project):
    def test_the_domains_names_and_floor_of_the_spec(self):
        self.assertEqual(list(TABLE), ["look", "dashboard", "test", "secure"])
        for name, pairs in NAMES.items():
            rows = TABLE[name]["levels"]
            self.assertEqual([row["level"] for row in rows], [1, 2, 3, 4, 5])
            self.assertEqual([(row["name"], row["nl"]) for row in rows], pairs)
        self.assertEqual({name: domain.get("floor") for name, domain in TABLE.items()},
                         {"look": None, "dashboard": None, "test": None, "secure": 3})

    def test_every_level_says_what_it_is_in_one_plain_line(self):
        for name, domain in TABLE.items():
            self.assertTrue(domain["about"].strip() and domain["about_nl"].strip())
            for row in domain["levels"]:
                with self.subTest(domain=name, level=row["level"]):
                    for key in ("summary", "summary_nl"):
                        self.assertLessEqual(len(row[key]), 120, "one line, short enough for a question")
                        self.assertNotIn("\n", row[key])
                        self.assertEqual(row[key].startswith("+ "), row["level"] > 1, "a + from level 2 up")
                    self.assertTrue(row["includes"] and all(item.strip() for item in row["includes"]))

    def test_aliases_are_plain_lower_case_words(self):
        for name, domain in TABLE.items():
            for row in domain["levels"]:
                for alias in row["aliases"]:
                    with self.subTest(domain=name, alias=alias):
                        self.assertEqual(alias, " ".join(re.split(r"[\s_-]+", alias.casefold())).strip())
                        self.assertNotRegex(alias, r"^[1-5]$")

    def test_no_word_means_two_levels(self):
        """Not in one domain and not across them: it is one scale, so `set all WORD` never has to guess."""
        everywhere = {}
        for name, domain in TABLE.items():
            here = {}
            for row in domain["levels"]:
                for word in [row["name"], row["nl"]] + row["aliases"]:
                    word = word.casefold()
                    self.assertEqual(here.setdefault(word, row["level"]), row["level"], "%s in %s" % (word, name))
                    self.assertEqual(everywhere.setdefault(word, row["level"]), row["level"], word)

    def test_the_evidence_of_the_spec(self):
        evidence = {name: {row["level"]: row["evidence"] for row in domain["levels"] if row["evidence"]}
                    for name, domain in TABLE.items()}
        self.assertEqual(evidence, {
            "look": {}, "dashboard": {},
            "test": {3: ["forge-work/test/walk.json"],
                     4: ["e2e/**/edge*.spec.*", "forge-work/test/shots/r1/*.png", "forge-work/test/shots/r2/*.png"]},
            "secure": {3: ["forge-work/sbom.json"],
                       4: ["forge-work/security/probe.json", "forge-work/security/authz.json"]}})
        instead = {(name, row["level"]): row["evidence_or"] for name, domain in TABLE.items()
                   for row in domain["levels"] if "evidence_or" in row}
        self.assertEqual(instead, {("secure", 4): "no running app"})
        for domain in TABLE.values():
            for row in domain["levels"]:
                self.assertEqual(bool(row["evidence"]), "evidence_how" in row, "how the evidence comes about")
                for pattern in row["evidence"]:  # from the project root, never out of it
                    self.assertNotRegex(pattern, r"^/|\.\.|\\|^$")

    def test_level_py_holds_no_level_name_of_its_own(self):
        source = read(SCRIPT)
        for domain in TABLE.values():
            for row in domain["levels"]:
                for word in (row["name"], row["nl"]):
                    self.assertNotRegex(source, r"(?i)\b%s\b" % re.escape(word))

    def test_a_missing_or_broken_table_is_exit_2(self):
        good = json.loads(read(level.TABLE))

        def broken(change):
            data = json.loads(json.dumps(good))
            change(data["domains"])
            return json.dumps(data)

        cases = [None, "", "{not json", "[]", "{}", '{"domains": []}', '{"domains": {"look": {}}}',
                 broken(lambda domains: domains["look"]["levels"].pop()),
                 broken(lambda domains: domains["look"]["levels"].reverse()),
                 broken(lambda domains: domains["look"]["levels"][0].update(level="1")),
                 broken(lambda domains: domains["look"]["levels"][0].pop("nl")),
                 broken(lambda domains: domains["look"]["levels"][0].update(summary_nl="")),
                 broken(lambda domains: domains["look"]["levels"][0].update(aliases=[1])),
                 broken(lambda domains: domains["look"].pop("about_nl")),
                 broken(lambda domains: domains["test"]["levels"][2].update(evidence="forge-work/test/walk.json")),
                 broken(lambda domains: domains["secure"].update(floor=9)),
                 broken(lambda domains: domains["secure"].update(floor=3.0)),
                 broken(lambda domains: domains["secure"]["levels"][3].update(evidence_or={"words": "x"}))]
        path = os.path.join(self.root, "levels.json")
        for text in cases:
            with self.subTest(text=str(text)[:60]), mock.patch.object(level, "TABLE", path):
                if text is not None:
                    self.write("levels.json", text)
                for args in (["show"], ["get", "look"], ["set", "look", "3", "--said", "drie"]):
                    code, out, err = self.level(*args)
                    self.assertEqual((code, out), (2, ""))
                    self.assertIn("error: %s is missing or broken" % path, err)
                    self.assertNotIn("Traceback", err)
        self.assertFalse(os.path.exists(self.work))
        self.assertEqual(level.load_table(self.write("levels.json", json.dumps(good))), TABLE)


class ShowTests(Project):
    def test_show_every_domain(self):
        code, out, err = self.level("show")
        self.assertEqual((code, err), (0, ""))
        blocks = out.rstrip("\n").split("\n\n")
        self.assertEqual(len(blocks), len(TABLE))
        for name, block in zip(TABLE, blocks):
            lines = block.splitlines()
            self.assertEqual(lines[0], "%s: %s" % (name, TABLE[name]["about"]))
            self.assertEqual(len(lines), 6)
            for row, line in zip(TABLE[name]["levels"], lines[1:]):
                both = row["name"] if row["nl"] == row["name"] else "%s (%s)" % (row["name"], row["nl"])
                self.assertRegex(line, r"^  %d %s +%s$" % (row["level"], re.escape(both), re.escape(row["summary"])))
        self.assertTrue(out.isascii())
        self.assertLessEqual(max(len(line) for line in out.splitlines()), 150, "short enough to paste into a question")
        self.assertFalse(os.path.exists(self.work), "show reads the pack, it writes nothing in the project")

    def test_show_one_domain_in_dutch(self):
        code, out, err = self.level("show", "test", "--nl")
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        self.assertEqual(lines[0], "test: " + TABLE["test"]["about_nl"])
        self.assertEqual(len(lines), 6)
        for row, line in zip(TABLE["test"]["levels"], lines[1:]):
            both = "%d %s (%s)" % (row["level"], row["nl"], row["name"])
            self.assertRegex(line, r"^  %s +%s$" % (re.escape(both), re.escape(row["summary_nl"])))
        self.assertTrue(lines[4].startswith("  4 Grondig (Thorough)  "))
        self.assertTrue(self.level("show", "--nl")[1].isascii())

    def test_a_name_that_is_the_same_in_both_languages_is_shown_once(self):
        for extra in ([], ["--nl"]):
            out = self.level("show", "look", *extra)[1]
            self.assertRegex(out, r"(?m)^  4 Showpiece  +\+ ")
            self.assertNotIn("Showpiece (Showpiece)", out)

    def test_show_json(self):
        code, out, _ = self.level("show", "secure", "--json")
        self.assertEqual((code, json.loads(out)), (0, {"domains": {"secure": TABLE["secure"]}}))
        self.assertEqual(json.loads(self.level("show", "--json", "--nl")[1]), {"domains": TABLE})

    def test_show_works_whatever_the_project_holds(self):
        self.write("forge-work/levels.json", "{not json")
        self.assertEqual(self.level("show", "look")[0], 0)

    def test_bad_usage_is_exit_2(self):
        for args in ([], ["show", "speed"], ["show", "all"], ["get"], ["get", "all"], ["check", "all"], ["check"],
                     ["set", "speed", "3", "--said", "x"], ["set", "look"], ["set", "look", "3"], ["list"],
                     ["get", "look", "--report", "x.md"], ["check", "look", "--nl"]):
            with self.subTest(args=args), self.assertRaises(SystemExit) as stop:
                self.level(*args)
            self.assertEqual(stop.exception.code, 2)
        self.assertFalse(os.path.exists(self.work))


class SetTests(Project):
    def test_set_records_the_level_the_words_and_the_time(self):
        code, out, err = self.level("set", "look", "4", "--said", "  maak het uiterlijk niveau 4  ")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, "Recorded in %s: look 4 Showpiece. The user said: %s\n"
                         % (RECORD, '"maak het uiterlijk niveau 4"'))
        record = self.record()
        self.assertEqual(list(record), ["look"])
        self.assertEqual(sorted(record["look"]), ["at", "level", "said"])
        self.assertEqual((record["look"]["level"], record["look"]["said"]), (4, "maak het uiterlijk niveau 4"))
        self.assertRegex(record["look"]["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")
        self.assertTrue(self.record_text().endswith("}\n"))

    def test_set_makes_forge_work_with_the_gitignore_of_gate_init(self):
        self.choose("test", 2)
        self.assertEqual(sorted(os.listdir(self.work)), [".gitignore", "levels.json"])
        ignore = read(os.path.join(self.work, ".gitignore"))
        self.assertEqual(ignore.splitlines()[-1], "*")
        shutil.rmtree(self.work)
        self.assertEqual(self.gate("init", "--mode", "idea")[0], 0)
        self.assertEqual(read(os.path.join(self.work, ".gitignore")), ignore)

    def test_a_gitignore_that_is_there_is_kept(self):
        self.write("forge-work/.gitignore", "notes.md\n")
        self.choose("test", 2)
        self.assertEqual(read(os.path.join(self.work, ".gitignore")), "notes.md\n")

    def test_every_name_and_alias_in_any_letter_case(self):
        for name, domain in TABLE.items():
            for row in domain["levels"]:
                for word in [row["name"], row["nl"]] + row["aliases"]:
                    for text in (word, word.upper(), word.lower(), word.title(), "  %s\t" % word,
                                 word.replace(" ", "-"), word.replace(" ", "_")):
                        with self.subTest(domain=name, text=text):
                            self.assertEqual(level.resolve(TABLE, [name], text), row["level"])
                            self.assertEqual(level.resolve(TABLE, list(TABLE), text), row["level"])

    def test_names_in_english_and_dutch_on_the_command_line(self):
        cases = {"look": {"subtle": 1, "Subtiel": 1, "SHOWPIECE": 4, "cinematic": 5, "Cinematisch": 5, "4D": 5,
                          "show-piece": 4, "2": 2, " 3 ": 3},
                 "test": {"quick": 1, "Snel": 1, "standard": 3, "STANDAARD": 3, "grondig": 4, "Uitputtend": 5, "5": 5}}
        for name, words in cases.items():
            for word, number in words.items():
                with self.subTest(domain=name, word=word):
                    code, out, err = self.level("set", name, word, "--said", "ik wil " + word)
                    self.assertEqual((code, err), (0, ""))
                    self.assertEqual(self.record()[name]["level"], number)
                    self.assertIn(": %s %d %s. " % (name, number, NAMES[name][number - 1][0]), out)

    def test_a_name_of_another_domain_counts_as_its_number(self):
        code, out, _ = self.level("set", "test", "showpiece", "--said", "test op showpiece-niveau")
        self.assertEqual(code, 0)
        self.assertIn("test 4 Thorough", out)
        code, out, _ = self.level("set", "look", "Standaard", "--said", "standaard")
        self.assertEqual(code, 0)
        self.assertIn("look 3 Expressive", out)

    def test_a_word_with_two_meanings_is_refused(self):
        def domain(alias_at):
            return {"levels": [{"level": number, "name": "N%d" % number, "nl": "N%d" % number,
                                "aliases": ["plain"] if number == alias_at else []} for number in range(1, 6)]}

        table = {"a": domain(1), "b": domain(2), "c": domain(0)}
        self.assertEqual(level.resolve(table, ["a"], "plain"), 1)  # what it means in the domain itself comes first
        self.assertEqual(level.resolve(table, ["b"], "PLAIN"), 2)
        for names in (["a", "b"], ["c"], list(table)):
            with self.assertRaises(level.LevelError) as stop:
                level.resolve(table, names, "plain")
            self.assertIn('LEVEL "plain" is more than one level [1, 2]', str(stop.exception))

    def test_all_sets_every_domain(self):
        code, out, err = self.level("set", "all", "Grondig", "--said", "alles grondig")
        self.assertEqual((code, err), (0, ""))
        record = self.record()
        self.assertEqual(list(record), list(TABLE))
        self.assertEqual({entry["level"] for entry in record.values()}, {4})
        self.assertEqual({entry["said"] for entry in record.values()}, {"alles grondig"})
        self.assertEqual(len({entry["at"] for entry in record.values()}), 1)
        self.assertIn("look 4 Showpiece, dashboard 4 Showpiece, test 4 Thorough, secure 4 Thorough.", out)

    def test_set_keeps_the_other_domains_and_replaces_its_own(self):
        self.level("set", "secure", "4", "--said", "veiligheid grondig")
        self.level("set", "dashboard", "2", "--said", "dashboard verzorgd")
        before = self.record()
        self.assertEqual(list(before), ["dashboard", "secure"], "in the order of the table")
        code, out, _ = self.level("set", "look", "cinematic", "--said", "de look mag cinematic")
        self.assertEqual(code, 0)
        self.assertNotIn("secure", out)
        after = self.record()
        self.assertEqual(list(after), ["look", "dashboard", "secure"])
        self.assertEqual({name: after[name] for name in before}, before)
        self.level("set", "look", "1", "--said", "toch maar subtiel")
        self.assertEqual((self.record()["look"]["level"], self.record()["look"]["said"]), (1, "toch maar subtiel"))
        self.assertEqual({name: self.record()[name] for name in before}, before)

    def test_an_unknown_level_is_exit_2_and_writes_nothing(self):
        for text in ("0", "6", "10", "44", "4.5", "wow", "", "  ", "level 4", "niveau 4", "3d", "subtle polished",
                     "default", "auto"):  # the last two: there is never a silent default
            for domain in ("look", "all"):
                with self.subTest(text=text, domain=domain):
                    code, out, err = self.level("set", domain, text, "--said", "ik wil dit")
                    self.assertEqual((code, out), (2, ""))
                    self.assertIn("error: LEVEL %s is no level. Give a number from 1 to 5" % json.dumps(text), err)
                    self.assertIn("level.py show", err)
        self.assertFalse(os.path.exists(self.work))

    def test_set_refuses_words_that_say_nothing(self):
        for words in ("", "   ", "<the user's words>", "<their words>", "TEXT", "{{said}}", "\u200b", "\ufeff",
                      "\u200b \u2060\n", "\u00a0", "\u3000"):
            with self.subTest(words=repr(words)):
                code, out, err = self.level("set", "look", "4", "--said", words)
                self.assertEqual((code, err), (1, ""))
                self.assertIn("REFUSED: --said needs the user's own words", out)
        self.assertFalse(os.path.exists(self.work))
        self.assertEqual(self.level("set", "look", "wow", "--said", "")[0], 1, "no words: refused before the level")

    def test_the_words_are_kept_as_typed(self):
        words = "ja, cinematisch \u00e9n grondig \U0001f44d"
        code, out, err = self.level("set", "look", "5", "--said", words)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.record()["look"]["said"], words)
        self.assertIn(words, self.record_text())  # in the file as the user wrote it
        self.assertTrue(out.isascii())  # on the screen with escapes: every console can show it
        self.assertIn("The user said: " + json.dumps(words), out)

    def test_words_that_are_not_text_are_not_stored(self):
        code, out, err = self.level("set", "look", "4", "--said", "go \udcff")  # bytes that were not UTF-8
        self.assertEqual((code, out), (2, ""))
        self.assertIn("error:", err)
        self.assertFalse(os.path.exists(self.work))
        self.choose("look", 3)
        before = self.record_text()
        self.assertEqual(self.level("set", "all", "4", "--said", "go \udcff")[0], 2)
        self.assertEqual(self.record_text(), before)
        self.assertEqual(sorted(os.listdir(self.work)), [".gitignore", "levels.json"])

    def test_set_json(self):
        code, out, _ = self.level("set", "all", "5", "--said", "alles op max", "--json")
        data = json.loads(out)
        self.assertEqual((code, sorted(data), data["notes"]), (0, ["notes", "recorded"], []))
        self.assertEqual(list(data["recorded"]), list(TABLE))
        self.assertEqual(sorted(data["recorded"]["test"]), ["at", "level", "name", "said"])
        self.assertEqual([entry["name"] for entry in data["recorded"].values()],
                         ["Cinematic", "Cinematic", "Exhaustive", "Exhaustive"])
        for name, entry in self.record().items():
            self.assertEqual(dict(entry, name=data["recorded"][name]["name"]), data["recorded"][name])


class FloorTests(Project):
    def test_outside_a_forge_project_there_is_no_floor(self):
        code, out, _ = self.level("set", "secure", "snel", "--said", "even snel kijken")
        self.assertEqual((code, self.record()["secure"]["level"]), (0, 1))
        self.assertNotIn("Note", out)
        self.assertEqual(self.level("get", "secure"), (0, "1 Quick\n", ""))
        self.assertEqual(self.level("check", "secure")[0], 0)

    def test_set_raises_secure_to_the_floor_inside_a_forge_project(self):
        self.forge()
        for asked, number in (("1", 1), ("Snel", 1), ("2", 2), ("basis", 2)):
            with self.subTest(asked=asked):
                code, out, err = self.level("set", "secure", asked, "--said", "doe maar snel")
                self.assertEqual((code, err), (0, ""))
                self.assertEqual(self.record()["secure"]["level"], 3)
                self.assertEqual(out.splitlines(), [
                    'Recorded in %s: secure 3 Standard. The user said: "doe maar snel"' % RECORD,
                    "Note: secure was asked at level %d and is on record at 3: inside a forge project it never runs "
                    "below that. Tell the user." % number])
        for asked, number in (("3", 3), ("grondig", 4), ("5", 5)):
            with self.subTest(asked=asked):
                code, out, _ = self.level("set", "secure", asked, "--said", "zo dus")
                self.assertEqual((code, self.record()["secure"]["level"]), (0, number))
                self.assertNotIn("Note", out)

    def test_all_raises_only_the_domain_with_a_floor(self):
        self.forge()
        code, out, _ = self.level("set", "all", "1", "--said", "alles op 1", "--json")
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual({name: entry["level"] for name, entry in data["recorded"].items()},
                         {"look": 1, "dashboard": 1, "test": 1, "secure": 3})
        self.assertEqual(data["recorded"]["secure"]["name"], "Standard")
        self.assertEqual(len(data["notes"]), 1)
        self.assertIn("secure was asked at level 1 and is on record at 3", data["notes"][0])
        self.assertEqual(self.level("get", "test"), (0, "1 Quick\n", ""))

    def test_a_level_from_before_the_forge_project_started(self):
        """A check on its own at a low level, and then /forge in the same folder: gate.py init comes after the
        set, so a secure level below the floor is on record. get and check refuse it until it is recorded again."""
        self.level("set", "all", "2", "--said", "alles op 2")
        self.forge()
        code, out, err = self.level("get", "secure")
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, "secure is on record at level 2, and inside a forge project it never runs below 3. "
                              "Record it again, and tell the user: level.py set secure 3 --said "
                              "'<their words for it>'\n")
        code, out, _ = self.level("get", "secure", "--json")
        data = json.loads(out)
        self.assertEqual((code, data["level"], data["name"]), (1, 2, "Basic"))
        self.assertIn("never runs below 3", data["problem"])
        code, out, _ = self.level("check", "secure")
        self.assertEqual(code, 1)
        self.assertEqual(out.splitlines()[0][:38], "  FAIL  secure is on record at level 2")
        self.assertEqual(len(out.splitlines()), 2, "nothing else is checked at a level that will change")
        self.assertEqual(self.level("get", "test"), (0, "2 Basic\n", ""))
        self.assertEqual(self.level("set", "secure", "3", "--said", "alles op 2")[0], 0)
        self.assertEqual(self.level("get", "secure"), (0, "3 Standard\n", ""))

    def test_the_state_of_gate_init_makes_it_a_forge_project(self):
        self.assertEqual(self.gate("init", "--mode", "improve", "--about", "mijn app")[0], 0)
        ignore, state = read(os.path.join(self.work, ".gitignore")), read(os.path.join(self.work, "state.json"))
        code, out, _ = self.level("set", "all", "snel", "--said", "alles snel")
        self.assertEqual((code, self.record()["secure"]["level"], self.record()["test"]["level"]), (0, 3, 1))
        self.assertIn("Note: secure was asked at level 1", out)
        self.assertEqual(sorted(os.listdir(self.work)), [".gitignore", "levels.json", "state.json"])
        self.assertEqual((read(os.path.join(self.work, ".gitignore")), read(os.path.join(self.work, "state.json"))),
                         (ignore, state))
        self.assertEqual(self.gate("status")[0], 0)


class GetTests(Project):
    def test_get_prints_the_number_and_the_name(self):
        self.level("set", "look", "showpiece", "--said", "een showpiece")
        self.assertEqual(self.level("get", "look"), (0, "4 Showpiece\n", ""))
        code, out, _ = self.level("get", "look", "--json")
        data = json.loads(out)
        self.assertEqual(sorted(data), ["at", "domain", "level", "name", "problem", "said"])
        self.assertEqual((code, data["domain"], data["level"], data["name"], data["said"], data["problem"]),
                         (0, "look", 4, "Showpiece", "een showpiece", None))
        self.assertEqual(data["at"], self.record()["look"]["at"])

    def test_no_level_chosen_is_exit_1_with_what_to_ask(self):
        for domain in TABLE:
            with self.subTest(domain=domain):
                code, out, err = self.level("get", domain)
                self.assertEqual((code, err), (1, ""))
                self.assertEqual(out, "No level chosen for {0} yet: ask the user. python3 level.py show {0} shows the "
                                      "choices. Then record the answer: level.py set {0} LEVEL --said '<their words>'\n"
                                 .format(domain))
        self.assertFalse(os.path.exists(self.work), "get writes nothing")
        self.choose("look", 2)
        code, out, _ = self.level("get", "test", "--json")  # the level of one domain says nothing of another
        data = json.loads(out)
        self.assertEqual((code, data["domain"], data["level"], data["name"]), (1, "test", None, None))
        self.assertIn("ask the user", data["problem"])


class CheckTests(Project):
    REPORT = "# Security check\nDate: 2026-11-10\nLevel: 4 (Thorough)\nVerdict: PASS\n\n## Not checked\n%s\n"

    def test_no_level_chosen_fails(self):
        code, out, err = self.level("check", "look")
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out.splitlines()[0][:54], "  FAIL  No level chosen for look yet: ask the user. py")
        self.assertEqual(out.splitlines()[1][:27], "FAIL: look does not pass. D")
        code, data = self.check("look", "--report", "forge-work/motion.md")
        self.assertEqual((code, data["ok"], data["level"], len(data["checks"])), (1, False, None, 1))

    def test_a_level_that_asks_for_no_file_passes_and_says_so(self):
        self.choose("look", 5)
        code, out, err = self.level("check", "look")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, '  ok    look is at level 5 Cinematic: the user said "niveau 5"\n'
                              "PASS: look is at the level the user chose.\n")

    def test_the_report_says_the_same_level(self):
        self.choose("look", 4)
        for line in ("Level: 4", "Level: 4 (Showpiece)", "Level: 4 showpiece", "Level:4", "Level: 4 (SHOWPIECE)",
                     "Level: 4   "):
            for text in ("# Motion\n%s\n\n## Direction\ntext\n", "\ufeff%s\n# Motion\n", "# Motion\r\n%s\r\n"):
                with self.subTest(line=line, text=text):
                    self.write("forge-work/motion.md", text % line)
                    code, data = self.check("look", "--report", "forge-work/motion.md")
                    self.assertEqual((code, len(data["checks"])), (0, 2), data)
                    self.assertEqual(data["checks"][1], {"ok": True, "output": [],
                                                         "what": "forge-work/motion.md says " + line.rstrip()})
        self.choose("test", 2)
        for line in ("Level: 2 (Basic)", "Level: 2 (Basis)", "Level: 2 basis"):  # the name in English or in Dutch
            self.write("forge-work/test-plan.md", "# Test plan\n%s\n" % line)
            code, data = self.check("test", "--report", "forge-work/test-plan.md")
            self.assertEqual((code, data["checks"][1]["what"]), (0, "forge-work/test-plan.md says " + line))

    def test_a_report_with_another_level_or_no_plain_level_line_fails(self):
        self.choose("look", 4)
        for line in ("Level: 3", "Level: 5 (Cinematic)", "Level: 4 (Cinematic)", "Level: 4 (Thorough)", "Level: 40",
                     "Level: 4 of 5", "Level: 4.", "Level: four", "level: 4", "**Level:** 4", "## Level: 4",
                     "> Level: 4", "  Level: 4", "Level: 4\nLevel: 4", "Level: 4\n\nLevel: 3", "Niveau: 4",
                     "The level: 4", ""):
            with self.subTest(line=line):
                self.write("forge-work/motion.md", "# Motion\n%s\n" % line)
                code, data = self.check("look", "--report", "forge-work/motion.md")
                self.assertEqual(code, 1)
                check = data["checks"][1]
                self.assertEqual((check["ok"], len(data["checks"])), (False, 2))
                self.assertIn("forge-work/motion.md needs exactly one line `Level: 4 (Showpiece)`, outside comments "
                              "and code blocks (found: ", check["what"])
                self.assertEqual(check["output"], ["The user chose level 4: do its work, then say so. Another level "
                                                   "is the user's call."])
        self.assertIn("(found: none)", check["what"])
        self.write("forge-work/motion.md", "Level: 3\nLevel: 4\n")
        code, data = self.check("look", "--report", "forge-work/motion.md")
        self.assertIn("(found: Level: 3 / Level: 4)", data["checks"][1]["what"])

    def test_a_level_line_in_a_comment_or_a_code_block_does_not_count(self):
        self.choose("look", 4)
        self.write("forge-work/motion.md", "# Motion\n<!-- Level: 4 -->\n```\nLevel: 4\n```\n~~~text\nLevel: 4\n~~~\n")
        code, data = self.check("look", "--report", "forge-work/motion.md")
        self.assertEqual(code, 1)
        self.assertIn("(found: none)", data["checks"][1]["what"])
        self.write("forge-work/motion.md", "# Motion\nLevel: 4 (Showpiece)\n<!--\nLevel: 2\n-->\n```\nLevel: 1\n```\n")
        self.assertEqual(self.check("look", "--report", "forge-work/motion.md")[0], 0)

    def test_a_missing_report_fails_and_one_that_cannot_be_read_is_exit_2(self):
        self.choose("look", 4)
        code, data = self.check("look", "--report", "forge-work/motion.md")
        self.assertEqual(code, 1)
        self.assertEqual(data["checks"][1], {"ok": False, "what": "forge-work/motion.md is missing",
                                             "output": ["Write the report, with one line `Level: 4 (Showpiece)`."]})
        os.makedirs(os.path.join(self.work, "motion.md"))
        self.write("forge-work/big.md", "Level: 4\n" + "x" * level.MAX_BYTES)
        for name in ("forge-work/motion.md", "forge-work/big.md"):
            code, out, err = self.level("check", "look", "--report", name)
            self.assertEqual((code, out), (2, ""))
            self.assertIn("error: %s is a link, not a file or over %d bytes" % (name, level.MAX_BYTES), err)
        self.write("forge-work/latin.md", "")
        with open(os.path.join(self.work, "latin.md"), "wb") as handle:
            handle.write(b"# Caf\xe9\nLevel: 4\n")  # not UTF-8: still read, the odd byte is replaced
        self.assertEqual(self.check("look", "--report", "forge-work/latin.md")[0], 0)
        absolute = self.write("forge-work/motion-2.md", "Level: 4\n")
        self.assertEqual(self.check("look", "--report", absolute)[0], 0)

    def test_the_evidence_of_every_level_up_to_the_chosen_one(self):
        self.choose("test", 4)
        code, data = self.check("test")
        self.assertEqual(code, 1)
        self.assertEqual([check["ok"] for check in data["checks"]], [True, False, False])
        self.assertEqual(data["checks"][1], {"ok": False, "what": MISSING % (3, "forge-work/test/walk.json"),
                                             "output": [TABLE["test"]["levels"][2]["evidence_how"]]})
        self.assertEqual(data["checks"][2], {"ok": False, "what": MISSING % (4, ", ".join(
            TABLE["test"]["levels"][3]["evidence"])), "output": [TABLE["test"]["levels"][3]["evidence_how"]]})
        self.write("forge-work/test/walk.json", "{}\n")
        self.write("e2e/edge.spec.ts", "test('F02-E1', async () => {});\n")
        self.write("forge-work/test/shots/r1/S01-home-390-light.png", "png")
        code, data = self.check("test")
        self.assertEqual(code, 1)
        self.assertEqual(data["checks"][1], {"ok": True, "what": "level 3 asks for forge-work/test/walk.json: there",
                                             "output": []})
        self.assertEqual(data["checks"][2]["what"], MISSING % (4, "forge-work/test/shots/r2/*.png"), "what is missing")
        self.write("forge-work/test/shots/r2/S01-home-390-light.png", "png")
        code, out, err = self.level("check", "test")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.splitlines()[1:], [
            "  ok    level 3 asks for forge-work/test/walk.json: there",
            "  ok    level 4 asks for %s: there" % ", ".join(TABLE["test"]["levels"][3]["evidence"]),
            "PASS: test is at the level the user chose."])

    def test_a_failing_check_in_plain_words(self):
        self.choose("test", 3)
        self.write("forge-work/test-plan.md", "# Test plan\nLevel: 2\n")
        code, out, err = self.level("check", "test", "--report", "forge-work/test-plan.md")
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out.splitlines(), [
            '  ok    test is at level 3 Standard: the user said "niveau 3"',
            "  FAIL  forge-work/test-plan.md needs exactly one line `Level: 3 (Standard)`, outside comments and code "
            "blocks (found: Level: 2)",
            "          The user chose level 3: do its work, then say so. Another level is the user's call.",
            "  FAIL  " + MISSING % (3, "forge-work/test/walk.json"),
            "          " + TABLE["test"]["levels"][2]["evidence_how"],
            "FAIL: test does not pass. Do what FAIL names: the work, never a file written only to pass. Another level "
            "is the user's call."])

    def test_no_line_of_a_failing_check_is_cut_by_the_gate(self):
        """phasecheck.py shows the first 200 characters of each line a failing script prints."""
        outputs = [self.level("check", "look")[1]]
        for domain in TABLE:
            self.choose(domain, 5)
            self.write("forge-work/report.md", "# Report\nLevel: 1\n")
            outputs.append(self.level("check", domain, "--report", "forge-work/report.md")[1])
        self.choose("secure", 1)
        self.forge()
        outputs.append(self.level("check", "secure")[1])
        self.assertEqual([text.splitlines()[-1][:5] for text in outputs], ["FAIL:"] * 6)
        for text in outputs:
            for line in text.splitlines():
                self.assertLessEqual(len(line), 200, line)

    def test_only_the_levels_up_to_the_chosen_one_are_asked(self):
        for number, asked in ((1, []), (2, []), (3, [3]), (4, [3, 4]), (5, [3, 4])):
            with self.subTest(level=number):
                self.choose("test", number)
                code, data = self.check("test")
                self.assertEqual(code, 1 if asked else 0)
                self.assertEqual([check["what"][:7] for check in data["checks"][1:]], ["level %d" % at for at in asked])

    def test_what_does_not_count_as_evidence(self):
        self.choose("test", 3)
        self.write("forge-work/test/walk.json", "")  # a file with nothing in it
        self.assertEqual(self.check("test")[0], 1)
        os.remove(os.path.join(self.work, "test", "walk.json"))
        os.makedirs(os.path.join(self.work, "test", "walk.json"))  # a folder with that name
        self.assertEqual(self.check("test")[0], 1)
        os.rmdir(os.path.join(self.work, "test", "walk.json"))
        self.write("forge-work/walk.json", "{}\n")  # in another folder
        self.write("forge-work/test/Walk.json.bak", "{}\n")
        self.assertEqual(self.check("test")[0], 1)
        self.write("forge-work/test/walk.json", " ")
        self.assertEqual(self.check("test")[0], 0)

    def test_the_edge_spec_sits_anywhere_in_e2e_but_not_in_node_modules(self):
        self.choose("test", 4)
        for name in ("forge-work/test/walk.json", "forge-work/test/shots/r1/a.png", "forge-work/test/shots/r2/a.png"):
            self.write(name)
        for name, counts in (("e2e/node_modules/pkg/edge.spec.js", False), ("e2e/edge.spec", False),
                             ("e2e/forms/login.spec.ts", False), ("tests/edge.spec.ts", False),
                             ("e2e/edge.spec.ts/readme.md", False), ("e2e/edge.spec.ts", True),
                             ("e2e/forms/deep/edge-login.spec.tsx", True), ("e2e/edge-cases.spec.mjs", True)):
            with self.subTest(name=name):
                self.write(name)
                code, data = self.check("test")
                self.assertEqual(code, 0 if counts else 1, data)
                shutil.rmtree(os.path.join(self.root, name.split("/")[0]))

    def test_secure_level_4_wants_the_probe_and_the_access_check_or_the_reason(self):
        self.choose("secure", 4)
        self.write("forge-work/sbom.json", "{}\n")
        self.write("forge-work/security.md", self.REPORT % "- composer audit: composer is not installed.")
        code, data = self.check("secure", "--report", "forge-work/security.md")
        self.assertEqual((code, [check["ok"] for check in data["checks"]]), (1, [True, True, True, False]))
        self.assertEqual(data["checks"][3], {
            "ok": False, "what": MISSING % (4, "forge-work/security/probe.json, forge-work/security/authz.json"),
            "output": [TABLE["secure"]["levels"][3]["evidence_how"],
                       "Or a line in the report (--report FILE) with the words 'no running app' and then why."]})
        reason = "- probe.py and authz.py: no running app, the user runs no containers here"
        for line, counts in ((reason, True), ("- probe and authz: No Running App (Docker is not installed)", True),
                             ("- probe.py and authz.py: no running app", False), ("- no running app.", False),
                             ("- no running app, see above", False), ("- the app was not running, so no probe", False),
                             ("<!-- %s -->" % reason, False), ("```\n%s\n```" % reason, False)):
            with self.subTest(line=line):
                self.write("forge-work/security.md", self.REPORT % line)
                code, data = self.check("secure", "--report", "forge-work/security.md")
                self.assertEqual(code, 0 if counts else 1, data)
        self.write("forge-work/security.md", self.REPORT % reason)
        code, data = self.check("secure", "--report", "forge-work/security.md")
        self.assertEqual(data["checks"][3], {"ok": True, "output": [], "what": "level 4 asks for forge-work/security/"
                                             "probe.json, forge-work/security/authz.json: not there, and the report "
                                             "says why: " + reason})
        self.assertEqual(self.check("secure")[0], 1, "the reason is in the report: without --report nobody reads it")
        self.write("forge-work/security/probe.json", "{}\n")
        self.write("forge-work/security/authz.json", "{}\n")
        self.assertEqual(self.check("secure")[0], 0)
        self.write("forge-work/security.md", self.REPORT % "- nothing")
        code, data = self.check("secure", "--report", "forge-work/security.md")
        self.assertEqual((code, data["checks"][3]["what"][-7:]), (0, ": there"))

    def test_the_reason_stands_only_for_its_own_level(self):
        self.choose("secure", 5)
        report = self.REPORT % "- probe.py: no running app, the build fails on this machine"
        self.write("forge-work/security.md", report.replace("Level: 4 (Thorough)", "Level: 5 (Uitputtend)"))
        code, data = self.check("secure", "--report", "forge-work/security.md")
        self.assertEqual((code, [check["ok"] for check in data["checks"]]), (1, [True, True, False, True]))
        self.assertEqual(data["checks"][2]["what"], MISSING % (3, "forge-work/sbom.json"))

    def test_check_json_shape(self):
        self.choose("test", 3)
        code, out, err = self.level("check", "test", "--json")
        data = json.loads(out)
        self.assertEqual((code, err, sorted(data)), (1, "", ["checks", "domain", "level", "ok"]))
        self.assertEqual((data["domain"], data["level"], data["ok"]), ("test", 3, False))
        for check in data["checks"]:
            self.assertEqual(sorted(check), ["ok", "output", "what"])
            self.assertIsInstance(check["output"], list)


class FindTests(Project):
    def test_patterns(self):
        for name in ("a/b.txt", "a/x/b2.txt", "a/x/y/c.txt", "a/node_modules/n.txt", "a/x/node_modules/c.txt"):
            self.write(name)
        self.write("d/empty.txt", "")
        cases = {"a/b.txt": "a/b.txt", "a/*.txt": "a/b.txt", "a/?.txt": "a/b.txt", "a/[bc].txt": "a/b.txt",
                 "a/**/b*.txt": "a/b.txt", "a/*/b*.txt": "a/x/b2.txt", "a/**/c.txt": "a/x/y/c.txt",
                 "**/c.txt": "a/x/y/c.txt", "a/x/**": "a/x/b2.txt", "**": "a/b.txt", "a/**/y/*": "a/x/y/c.txt",
                 "a/*/c.txt": None, "d/*.txt": None, "a/node_modules/*.txt": None, "a/**/n.txt": None, "a": None,
                 "a/x": None, "b.txt": None, "../a/b.txt": None, "a/../a/b.txt": None, "/a/b.txt": None,
                 os.path.join(self.root, "a", "b.txt").replace(os.sep, "/"): None, "nowhere/**/x": None}
        for pattern, found in cases.items():
            with self.subTest(pattern=pattern):
                self.assertEqual(level.find(self.root, pattern.split("/")), found)

    def test_a_tree_made_to_be_endless_is_not_followed_to_the_end(self):
        """30 folders deep is far more than any project has; below that nothing counts, so nothing can hang."""
        self.write("near/" + "d/" * 29 + "x.txt")
        self.write("far/" + "d/" * 30 + "x.txt")
        self.assertEqual(level.find(self.root, ["near", "**", "x.txt"]), "near/" + "d/" * 29 + "x.txt")
        self.assertIsNone(level.find(self.root, ["far", "**", "x.txt"]))
        self.assertIsNone(level.find(self.root, ("far/" + "d/" * 30 + "x.txt").split("/")))


class LinkTests(Project):
    GOOD = '{"look": {"level": 5, "said": "vijf", "at": "2026-11-10T14:03:11+01:00"}}\n'

    def test_a_linked_record_is_never_read(self):
        """It could point to a pipe (get would hang) or to any file the user can read."""
        folder = self.outside("levels.json", self.GOOD)
        os.makedirs(self.work)
        symlink(self, os.path.join(folder, "levels.json"), os.path.join(self.work, "levels.json"))
        for args in (["get", "look"], ["get", "look", "--json"], ["check", "look"],
                     ["set", "look", "3", "--said", "drie"], ["set", "all", "3", "--said", "drie"]):
            with self.subTest(args=args):
                code, out, err = self.level(*args)
                self.assertEqual((code, out), (2, ""))
                self.assertIn("error: %s is a link" % RECORD, err)
                self.assertIn("ls -la forge-work", err)
        self.assertEqual(read(os.path.join(folder, "levels.json")), self.GOOD)
        self.assertTrue(os.path.islink(os.path.join(self.work, "levels.json")))
        self.assertEqual(os.listdir(self.work), ["levels.json"])
        self.assertEqual(self.level("show", "look")[0], 0)

    def test_a_link_to_nowhere_is_a_link_too(self):
        os.makedirs(self.work)
        symlink(self, os.path.join(self.root, "nowhere.json"), os.path.join(self.work, "levels.json"))
        for args in (["get", "look"], ["set", "look", "3", "--said", "drie"]):
            code, out, err = self.level(*args)
            self.assertEqual((code, out), (2, ""))
            self.assertIn("error: %s is a link" % RECORD, err)
        self.assertFalse(os.path.exists(os.path.join(self.root, "nowhere.json")))

    def test_set_never_writes_into_a_linked_forge_work(self):
        folder = self.outside("notes.txt", "the user's own notes\n")
        symlink(self, folder, self.work)
        for args in (["set", "look", "4", "--said", "vier"], ["set", "all", "2", "--said", "twee"]):
            with self.subTest(args=args):
                code, out, err = self.level(*args)
                self.assertEqual((code, out), (2, ""))
                self.assertIn("error: forge-work is a link", err)
                self.assertIn("ls -la forge-work", err)
                self.assertEqual(os.listdir(folder), ["notes.txt"])
        self.assertEqual(read(os.path.join(folder, "notes.txt")), "the user's own notes\n")

    def test_a_record_behind_a_linked_forge_work_is_read_but_never_replaced(self):
        """As gate.py: forge-work made a link after the first set. get still answers; set writes nothing there."""
        self.choose("look", 4)
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        moved = os.path.join(folder, "work")
        shutil.move(self.work, moved)
        symlink(self, moved, self.work)
        self.assertEqual(self.level("get", "look"), (0, "4 Showpiece\n", ""))
        before = read(os.path.join(moved, "levels.json"))
        code, out, err = self.level("set", "look", "5", "--said", "vijf")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("error: forge-work is a link", err)
        self.assertEqual(read(os.path.join(moved, "levels.json")), before)
        self.assertEqual(sorted(os.listdir(moved)), [".gitignore", "levels.json"])

    def test_a_linked_gitignore_is_left_alone(self):
        folder = self.outside("notes.txt", "important user data\n")
        os.makedirs(self.work)
        symlink(self, os.path.join(folder, "notes.txt"), os.path.join(self.work, ".gitignore"))
        code, _, err = self.level("set", "look", "4", "--said", "vier")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(read(os.path.join(folder, "notes.txt")), "important user data\n")
        self.assertTrue(os.path.islink(os.path.join(self.work, ".gitignore")))
        self.assertEqual(self.level("get", "look")[1], "4 Showpiece\n")

    def test_linked_evidence_does_not_count_and_a_linked_report_is_not_read(self):
        self.choose("test", 3)
        folder = self.outside("walk.json", "{}\n")
        os.makedirs(os.path.join(self.work, "test"))
        symlink(self, os.path.join(folder, "walk.json"), os.path.join(self.work, "test", "walk.json"))
        self.assertEqual(self.check("test")[0], 1)
        shutil.rmtree(os.path.join(self.work, "test"))
        symlink(self, folder, os.path.join(self.work, "test"))  # the folder is the link: what is in it does not count
        self.assertEqual(self.check("test")[0], 1)
        os.remove(os.path.join(self.work, "test"))
        self.write("forge-work/test/walk.json", "{}\n")
        self.assertEqual(self.check("test")[0], 0)
        plan = os.path.join(self.outside("plan.md", "Level: 3\n"), "plan.md")
        symlink(self, plan, os.path.join(self.work, "plan.md"))
        code, out, err = self.level("check", "test", "--report", "forge-work/plan.md")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("error: forge-work/plan.md is a link", err)


class DamagedRecordTests(Project):
    GOOD = {"level": 4, "said": "vier", "at": "2026-11-10T14:03:11+01:00"}
    DAMAGED = [
        "{not json", "", "[]", "null", "42", '"look"', "[" * 200000 + "]" * 200000,
        {"speed": GOOD}, {"all": GOOD}, {"look": 4}, {"look": "4"}, {"look": [GOOD]}, {"look": None}, {"look": {}},
        {"look": dict(GOOD, level=0)}, {"look": dict(GOOD, level=6)}, {"look": dict(GOOD, level="4")},
        {"look": dict(GOOD, level=4.0)}, {"look": dict(GOOD, level=True)}, {"look": dict(GOOD, level=None)},
        {"look": {"said": "vier", "at": GOOD["at"]}}, {"look": {"level": 4, "at": GOOD["at"]}},
        {"look": {"level": 4, "said": "vier"}},
        {"look": dict(GOOD, said="")}, {"look": dict(GOOD, said=" ")}, {"look": dict(GOOD, said="\u200b")},
        {"look": dict(GOOD, said="<the user's words>")}, {"look": dict(GOOD, said=["vier"])},
        {"look": dict(GOOD, said=None)}, {"look": dict(GOOD, said=4)},
        {"look": dict(GOOD, at="yesterday")}, {"look": dict(GOOD, at="2026-11-10T14:03:11")},  # no offset
        {"look": dict(GOOD, at="2026-11-31T09:00:00+00:00")},  # no such day
        {"look": dict(GOOD, at="2026-11-10T25:03:11+01:00")},  # hour 25
        {"look": dict(GOOD, at="2026-11-10T14:03:11+99:99")},  # no such zone
        {"look": dict(GOOD, at="2026-11-10T14:03:11+01:00 ")}, {"look": dict(GOOD, at=5)},
        {"look": dict(GOOD, at=None)},
        {"look": GOOD, "test": dict(GOOD, level=9)},  # one good entry does not save the file
    ]

    def test_every_command_that_reads_it_stops_with_a_plain_message(self):
        for record in self.DAMAGED:
            text = record if isinstance(record, str) else json.dumps(record)
            self.write("forge-work/levels.json", text)
            for args in (["get", "look"], ["get", "test", "--json"], ["check", "look"],
                         ["check", "test", "--report", "forge-work/test-plan.md"],
                         ["set", "look", "3", "--said", "drie"], ["set", "all", "3", "--said", "drie"]):
                with self.subTest(record=text[:70], args=args):
                    code, out, err = self.level(*args)
                    self.assertEqual((code, out), (2, ""))
                    self.assertIn("error: %s is damaged: not what level.py writes (" % RECORD, err)
                    self.assertIn("Do not guess a level: tell the user.", err)
                    self.assertNotIn("Traceback", err)
            self.assertEqual(self.record_text(), text, "set left the file as it was")
        self.assertEqual(os.listdir(self.work), ["levels.json"])

    def test_a_record_as_level_py_writes_it_is_fine(self):
        self.write("forge-work/levels.json", json.dumps({
            "look": self.GOOD, "secure": dict(self.GOOD, level=3, said="\u00e9\u00e9n \U0001f44d", note="kept")}))
        self.assertEqual(self.level("get", "look"), (0, "4 Showpiece\n", ""))
        self.assertEqual(self.level("get", "secure"), (0, "3 Standard\n", ""))
        self.choose("test", 2)
        self.assertEqual(self.record()["secure"]["note"], "kept")
        self.write("forge-work/levels.json", "{}")  # a record with no level yet
        self.assertEqual(self.level("get", "look")[0], 1)

    def test_a_record_that_is_no_file_not_text_or_too_big(self):
        os.makedirs(os.path.join(self.work, "levels.json"))
        code, out, err = self.level("get", "look")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("is damaged", err)
        os.rmdir(os.path.join(self.work, "levels.json"))
        with open(os.path.join(self.work, "levels.json"), "wb") as handle:
            handle.write(b'{"look": "\xff"}')
        self.assertEqual(self.level("get", "look")[0], 2)
        self.write("forge-work/levels.json", json.dumps({"look": dict(self.GOOD, said="x" * level.MAX_BYTES)}))
        code, _, err = self.level("set", "look", "3", "--said", "drie")
        self.assertEqual(code, 2)
        self.assertIn("over %d bytes" % level.MAX_BYTES, err)


class SaveTests(Project):
    def test_no_temporary_file_is_left(self):
        for number in (1, 2, 3):
            self.choose("all", number)
            self.choose("look", number + 1)
        self.assertEqual(sorted(os.listdir(self.work)), [".gitignore", "levels.json"])

    def test_a_failed_write_keeps_the_old_record(self):
        self.choose("look", 3)
        before = self.record_text()
        with mock.patch.object(level.os, "replace", side_effect=OSError("disk full")):
            code, out, err = self.level("set", "look", "5", "--said", "vijf")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("error: disk full", err)
        self.assertEqual(self.record_text(), before)
        self.assertEqual(sorted(os.listdir(self.work)), [".gitignore", "levels.json"])

    def test_forge_work_that_is_a_file(self):
        self.write("forge-work", "not a folder")
        code, out, err = self.level("set", "look", "3", "--said", "drie")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("error:", err)
        self.assertNotIn("Traceback", err)
        self.assertEqual(self.level("get", "look")[0], 1)
        self.assertEqual(read(self.work), "not a folder")


class ConsoleTests(Project):
    def run_script(self, *args):
        return subprocess.run([sys.executable, SCRIPT] + list(args), cwd=self.root, timeout=120,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    def test_help_shows_the_usage_and_the_exit_codes(self):
        done = self.run_script("--help")
        self.assertEqual(done.returncode, 0, done.stderr)
        for text in ("Usage:", "Exit codes:", "python3 level.py show [DOMAIN] [--nl]",
                     "python3 level.py set DOMAIN LEVEL --said", "python3 level.py get DOMAIN",
                     "python3 level.py check DOMAIN [--report FILE]", "--json"):
            self.assertIn(text, done.stdout)
        self.assertTrue(done.stdout.isascii())
        done = self.run_script("set", "--help")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("--said TEXT", done.stdout)
        self.assertIn("{look,dashboard,test,secure,all}", done.stdout)

    def test_the_exit_codes_on_the_command_line(self):
        self.assertEqual(self.run_script("get", "look").returncode, 1)
        self.assertEqual(self.run_script("check", "look").returncode, 1)
        self.assertEqual(self.run_script("set", "look", "4", "--said", "TEXT").returncode, 1)
        done = self.run_script("set", "look", "Showpiece", "--said", "een showpiece")
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        done = self.run_script("get", "look")
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "4 Showpiece\n", ""))
        self.assertEqual(self.run_script("check", "look").returncode, 0)
        self.assertEqual(self.run_script("show", "look").returncode, 0)
        self.assertEqual(self.run_script("set", "look", "wow", "--said", "wow").returncode, 2)
        self.assertEqual(self.run_script("get", "speed").returncode, 2)
        self.write("forge-work/levels.json", "{not json")
        for args in (["get", "look"], ["check", "look"], ["set", "look", "3", "--said", "drie"]):
            done = self.run_script(*args)
            self.assertEqual((done.returncode, done.stdout), (2, ""))
            self.assertTrue(done.stderr.startswith("error: "), done.stderr)
            self.assertNotIn("Traceback", done.stderr)

    def test_from_another_folder_there_is_no_level(self):
        self.choose("look", 4)
        os.makedirs(os.path.join(self.root, "src"))
        done = subprocess.run([sys.executable, SCRIPT, "get", "look"], cwd=os.path.join(self.root, "src"), timeout=120,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 1)
        self.assertIn("No level chosen for look yet", done.stdout)

    def test_a_console_that_cannot_show_the_words_never_crashes(self):
        """Windows before Python 3.15 with a pipe: cp1252, which has no arrow and no emoji."""
        for extra in ([], ["--nl"]):
            code, out, err = run_cp1252(SCRIPT, "show", *extra, cwd=self.root)
            self.assertEqual((code, err), (0, ""))
            self.assertEqual(out, self.level("show", *extra)[1])
        words = "ja \u2192 cinematisch \U0001f44d"
        code, out, err = run_cp1252(SCRIPT, "set", "look", "cinematisch", "--said", words, cwd=self.root)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("look 5 Cinematic. The user said: " + json.dumps(words), out)
        self.assertEqual(self.record()["look"]["said"], words)
        code, out, err = run_cp1252(SCRIPT, "get", "look", "--json", cwd=self.root)
        self.assertEqual((code, err, json.loads(out)["said"]), (0, "", words))
        self.write("forge-work/motion.md", "# Motion\nLevel: 5 \u2192 film\n")
        code, out, err = run_cp1252(SCRIPT, "check", "look", "--report", "forge-work/motion.md", cwd=self.root)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("the user said " + json.dumps(words), out)
        self.assertIn("(found: Level: 5 \\u2192 film)", out)
        code, out, err = run_cp1252(SCRIPT, "set", "look", "\u2192", "--said", words, cwd=self.root)
        self.assertEqual((code, out), (2, ""))
        self.assertIn('error: LEVEL "\\u2192" is no level', err)


class DocsTests(Project):
    """forge/levels.md is the same table for people: it names what levels.json holds."""

    def setUp(self):
        super().setUp()
        self.text = read(os.path.join(ROOT, "forge", "levels.md"))

    def section(self, title):
        """The text under the ## heading that starts with TITLE, up to the next ## heading."""
        found = re.search(r"(?ms)^## %s\b[^\n]*\n(.*?)(?=^## |\Z)" % re.escape(title), self.text)
        self.assertIsNotNone(found, "levels.md has no section ## %s" % title)
        return found.group(1)

    def test_it_names_every_level_number_name_and_alias(self):
        for name, domain in TABLE.items():
            section = self.section(name)
            for row in domain["levels"]:
                with self.subTest(domain=name, level=row["level"]):
                    self.assertRegex(section, r"(?m)^\| %d \| %s \| %s \| " % (row["level"], row["name"], row["nl"]))
                    for alias in row["aliases"]:
                        self.assertRegex(section, r"\b%s\b[^;.]*\(%d\)" % (re.escape(alias), row["level"]), alias)
            self.assertEqual(len(re.findall(r"(?m)^\| \d \| ", section)), 5)

    def test_it_names_the_evidence_and_the_floor(self):
        for name, domain in TABLE.items():
            section = self.section(name)
            for row in domain["levels"]:
                line = re.search(r"(?m)^\| %d \| .*$" % row["level"], section).group(0)
                for text in row["evidence"] + [row[key] for key in ("evidence_or",) if key in row]:
                    self.assertIn("`%s`" % text, line)
                self.assertEqual("forge-work/" in line or "e2e/" in line, bool(row["evidence"]), line)
            self.assertEqual("floor" in section, "floor" in domain, name)
        self.assertRegex(self.section("secure"), r"never runs below\s+level %d\b" % TABLE["secure"]["floor"])

    def test_the_question_holds_the_table_that_show_prints(self):
        blocks = re.findall(r"(?ms)^```text\n(.*?)^```", self.text)
        english, dutch = self.level("show", "look")[1], self.level("show", "look", "--nl")[1]
        self.assertTrue(any(block.startswith("How far should I go with the look?") and english in block
                            for block in blocks), "the English question, with `level.py show look` as it prints it")
        self.assertTrue(any(block.startswith("Hoe ver moet ik gaan met het uiterlijk?") and dutch in block
                            for block in blocks), "the Dutch question, with `level.py show look --nl` as it prints it")
        both = ("How far should I go, from 1 to 5?", "Hoe ver moet ik gaan, van 1 tot 5?")
        self.assertTrue(any(all(line in block for line in both) for block in blocks),
                        "the question /forge asks for all four, in both languages")

    def test_its_commands_run_and_its_record_is_one_level_py_reads(self):
        commands = re.findall(r"(?m)^python3 \.\./forge/level\.py (set .*)$", self.text)
        self.assertGreaterEqual(len(commands), 3)
        for command in commands:
            with self.subTest(command=command):
                code, _, err = self.level(*shlex.split(command))
                self.assertEqual((code, err), (0, ""))
        for command in re.findall(r"`python3 \.\./forge/level\.py ((?:get|check|show)[^`]*)`", self.text):
            with self.subTest(command=command):
                self.assertIn(self.level(*command.split())[0], (0, 1))
        self.assertEqual({name: entry["level"] for name, entry in self.record().items()}, dict.fromkeys(TABLE, 3))
        record = re.search(r"(?ms)^```json\n(.*?)^```", self.text).group(1)
        self.write("forge-work/levels.json", record)
        self.assertEqual(self.level("get", "look"), (0, "4 Showpiece\n", ""))
        self.assertEqual(self.level("get", "secure"), (0, "3 Standard\n", ""))


if __name__ == "__main__":
    unittest.main()
