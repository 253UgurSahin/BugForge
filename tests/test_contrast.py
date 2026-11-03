"""Tests for forge-design/contrast.py (ported from the original test_contrast_listing.py, plus
the forge conventions: exit codes, JSON shape, findings with a fix that names a passing colour,
and a regression test for each defect a review found)."""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402

contrast = load("forge-design", "contrast")
TEMPLATE = os.path.join(ROOT, "forge-design", "tokens.json")


def run(*args):
    """Run main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = contrast.main(list(args))
    return code, out.getvalue(), err.getvalue()


def template():
    with open(TEMPLATE, encoding="utf-8") as handle:
        return json.load(handle)


class Ported(unittest.TestCase):
    """The original tests, on the forge paths."""

    def test_known_ratios(self):
        self.assertAlmostEqual(contrast.ratio("#000", "#fff"), 21.0, places=2)
        self.assertAlmostEqual(contrast.ratio("#ffffff", "#ffffff"), 1.0, places=2)
        # #767676 on white is the classic just-passes-AA grey
        self.assertGreaterEqual(contrast.ratio("#767676", "#ffffff"), 4.5)
        self.assertLess(contrast.ratio("#777777", "#ffffff"), 4.5)

    def test_nested_tokens_flatten(self):
        cols = contrast.colours({"color": {"text": {"default": "#111", "muted": {"value": "#999"}},
                                           "bg": "#fff", "$type": "color"}})
        self.assertEqual(cols, {"text-default": "#111", "text-muted": "#999", "bg": "#fff"})

    def test_large_text(self):
        cols = {"text-muted": "#949494", "faint": "#bbbbbb", "bg": "#ffffff"}
        rows = contrast.check(cols, [["text-muted", "bg"], ["text-muted", "bg", "large"],
                                     ["faint", "bg", "large"]])
        self.assertFalse(rows[0]["aa"])
        self.assertTrue(rows[1]["aa"])
        self.assertFalse(rows[2]["aa"])  # 1.92:1, under the 3:1 large text needs
        self.assertEqual(contrast.grade(rows[2]), "FAIL")

    def test_shipped_tokens_template_passes(self):
        code, out, _ = run(TEMPLATE)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS: every pair meets WCAG AA.", out)

    def test_cli_pair_failure_exit_code(self):
        self.assertEqual(run("#aaaaaa", "#ffffff")[0], 1)
        self.assertEqual(run("#222222", "#ffffff")[0], 0)

    def test_the_size_group_and_files_without_it(self):
        """The template has a size group (borders, rings, icons, controls); older token files do not."""
        tokens = template()
        self.assertIn("control", tokens["size"])
        del tokens["size"], tokens["_size"]
        with tempfile.TemporaryDirectory() as folder:
            older = os.path.join(folder, "tokens.json")
            with open(older, "w", encoding="utf-8") as handle:
                json.dump(tokens, handle)
            self.assertEqual(run(older)[1], run(TEMPLATE)[1].replace(TEMPLATE, older))
            self.assertEqual(run(older)[0], 0)


class CoreTests(unittest.TestCase):
    def test_parse_hex(self):
        self.assertEqual(contrast.parse_hex("#abc"), (170, 187, 204))
        self.assertEqual(contrast.parse_hex("#FF0000"), (255, 0, 0))
        for bad in ("#abcd", "red", "rgb(0,0,0)", "#ggg", "", "FF0000", 255, None):
            with self.assertRaises(ValueError):
                contrast.parse_hex(bad)

    def test_ratio_is_cut_not_rounded(self):
        # 4.4776...:1 would round up to 4.48; it is cut to 4.47 and fails
        row = contrast.check({"grey": "#777777", "bg": "#ffffff"}, [["grey", "bg"]])[0]
        self.assertEqual(row["ratio"], 4.47)
        self.assertFalse(row["aa"])

    def test_kinds_and_grades(self):
        cols = {"text": "#14171c", "muted": "#767676", "line": "#868e98", "faint": "#c0c0c0",
                "bg": "#ffffff"}
        rows = contrast.check(cols, [["text", "bg"], ["muted", "bg"], ["line", "bg", "ui"],
                                     ["faint", "bg", "ui"], ["muted", "bg", "large"]])
        self.assertEqual([contrast.grade(row) for row in rows], ["AAA", "AA", "PASS", "FAIL", "AAA"])
        self.assertEqual([row["needs"] for row in rows], [4.5, 4.5, 3.0, 3.0, 3.0])

    def test_dark_group_and_dollar_value(self):
        tokens = {"color": {"bg": {"$value": "#ffffff"}, "text": "#111111",
                            "dark": {"bg": "#0b0d10", "text": "#e6e8eb"}}}
        cols = contrast.colours(tokens)
        self.assertEqual(cols["dark-bg"], "#0b0d10")
        rows = contrast.check(cols, [["dark-text", "dark-bg"], ["text", "bg"]])
        self.assertTrue(all(row["aa"] for row in rows))

    def test_colour_group_aliases(self):
        self.assertEqual(contrast.colours({"colors": {"bg": "#fff"}}), {"bg": "#fff"})
        self.assertEqual(contrast.colours({"colour": {"bg": "#fff"}}), {"bg": "#fff"})
        self.assertEqual(contrast.colours({"font": {"sans": "Inter"}}), {})

    def test_bad_pairs_raise(self):
        cols = {"text": "#111111", "bg": "#ffffff", "overlay": "rgba(0,0,0,.5)"}
        for pair, words in [(["text"], "must look like"), ("text,bg", "must look like"),
                            (["text", "bg", "huge"], "normal, large or ui"),
                            (["text", "bgg"], "no colour named 'bgg'"),
                            (["text", "overlay"], "write it as #rgb or #rrggbb"),
                            (["text", 3], "must look like")]:
            with self.subTest(pair=pair):
                with self.assertRaises(ValueError) as caught:
                    contrast.check(cols, [["text", "bg"], pair])
                self.assertIn("pair 2", str(caught.exception))
                self.assertIn(words, str(caught.exception))

    def test_non_hex_colour_outside_the_pairs_is_fine(self):
        cols = {"text": "#111111", "bg": "#ffffff", "overlay": "rgba(0,0,0,.5)"}
        self.assertEqual(len(contrast.check(cols, [["text", "bg"]])), 1)
        self.assertEqual(contrast.unpaired(cols, [["text", "bg"]]), [])


class ValueShapeTests(unittest.TestCase):
    """Regression: names that clash, values that are not strings, and the # in token files."""

    def test_two_names_that_flatten_the_same_are_an_error(self):
        for group in ({"text-muted": "#eeeeee", "text": {"muted": "#111111"}},
                      {"text": {"muted": "#111111"}, "text-muted": "#eeeeee"}):
            with self.subTest(group=group):
                with self.assertRaises(ValueError) as caught:
                    contrast.colours({"color": group})
                self.assertIn("both called 'text-muted'", str(caught.exception))

    def test_dtcg_object_value_with_hex_works(self):
        cols = contrast.colours({"color": {
            "bg": {"$type": "color", "$value": {"colorSpace": "srgb", "components": [1, 1, 1],
                                                "hex": "#ffffff"}},
            "text": {"$type": "color", "$value": {"colorSpace": "srgb", "components": [0, 0, 0],
                                                  "hex": "#000000"}}}})
        self.assertEqual(cols, {"bg": "#ffffff", "text": "#000000"})

    def test_value_that_is_not_a_string_is_named(self):
        cases = [({"bg": "#fff", "text": 123}, "text is 123, write it as #rgb or #rrggbb"),
                 ({"bg": "#fff", "text": {"$value": {"colorSpace": "srgb", "components": [0, 0, 0]}}},
                  "text is {"),
                 ({"bg": "#fff", "text": None}, "text is null")]
        for group, words in cases:
            with self.subTest(group=group):
                with self.assertRaises(ValueError) as caught:
                    contrast.check(contrast.colours({"color": group}), [["text", "bg"]])
                self.assertIn(words, str(caught.exception))
                self.assertNotIn("no colour named", str(caught.exception))

    def test_hash_is_needed_in_a_token_file(self):
        with self.assertRaises(ValueError) as caught:
            contrast.check({"bg": "ffffff", "text": "#111111"}, [["text", "bg"]])
        self.assertIn('bg is "ffffff", write it as #rgb or #rrggbb', str(caught.exception))


class UnpairedTests(unittest.TestCase):
    """Regression: a text colour in no pair was never checked, and the gate passed anyway."""

    def test_unpaired_text_colours(self):
        cols = {"bg": "#ffffff", "text": "#111111", "on-danger": "#ffffff", "danger": "#c62f2f",
                "text-disabled": "#bbbbbb", "border": "#e3e6ea", "dark-bg": "#0b0d10",
                "dark-text": "#30343a", "icon": "#555555", "fg": "#222222"}
        self.assertEqual(contrast.unpaired(cols, [["text", "bg"]]), ["on-danger", "dark-text", "fg"])
        self.assertEqual(contrast.unpaired(cols, [["text", "bg"], ["on-danger", "danger"],
                                                  ["dark-text", "dark-bg"], ["fg", "bg"]]), [])

    def test_unpaired_finding_suggests_a_pair(self):
        cols = {"bg": "#fff", "danger": "#c00", "dark-bg": "#000"}
        for name, example in [("dark-text", '["dark-text", "dark-bg"]'),
                              ("on-danger", '["on-danger", "danger"]'),
                              ("text-link", '["text-link", "bg"]'),
                              ("on-brand", '["on-brand", "<its background>"]')]:
            with self.subTest(name=name):
                found = contrast.unpaired_finding(name, "tokens.json", cols)
                self.assertEqual(found["severity"], "high")
                self.assertIn(name + " is in no pair", found["title"])
                self.assertIn(example, found["fix"])

    def test_dark_theme_without_dark_pairs_fails(self):
        path = os.path.join(tempfile.mkdtemp(), "tokens.json")
        self.addCleanup(shutil.rmtree, os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"color": {"bg": "#ffffff", "text": "#111111",
                                 "dark": {"bg": "#0b0d10", "text": "#30343a"}},
                       "pairs": [["text", "bg"]]}, handle)
        code, out, _ = run(path)
        self.assertEqual(code, 1)
        self.assertIn("Not checked: the text colour dark-text is in no pair", out)
        self.assertIn("1 pair checked, 0 failing WCAG AA, 1 text colour(s) in no pair.", out)
        code, out, _ = run(path, "--json")
        self.assertEqual(json.loads(out)["summary"],
                         {"pairs": 1, "failing": 0, "unchecked": 1, "high": 1, "verdict": "FAIL"})


class SuggestionTests(unittest.TestCase):
    def test_suggested_colour_passes_and_keeps_its_direction(self):
        better = contrast.nearest_passing("#999999", "#f6f7f9", 4.5)
        self.assertGreaterEqual(contrast.ratio(better, "#f6f7f9"), 4.5)
        self.assertLess(contrast.luminance(contrast.parse_hex(better)),
                        contrast.luminance(contrast.parse_hex("#999999")))  # darker, not flipped
        # one step lighter would no longer pass, so it is the nearest
        self.assertLess(contrast.ratio("#727272", "#f6f7f9"), 4.5)

    def test_no_suggestion_when_neither_black_nor_white_is_enough(self):
        self.assertIsNone(contrast.nearest_passing("#ffffff", "#767676", 7.0))
        self.assertIsNone(contrast.nearest_passing("#ffffff", "#5b8cff", 4.5, both_ways=False))

    def test_text_may_flip_but_a_background_does_not(self):
        # dark grey on a slightly lighter dark grey: only light text works
        better = contrast.nearest_passing("#2a2a2a", "#303030", 4.5)
        self.assertGreaterEqual(contrast.ratio(better, "#303030"), 4.5)
        self.assertGreater(contrast.luminance(contrast.parse_hex(better)),
                           contrast.luminance(contrast.parse_hex("#303030")))
        # a white page is never turned dark to fit grey text
        self.assertIsNone(contrast.nearest_passing("#ffffff", "#777777", 4.5, both_ways=False))

    def test_finding_names_the_passing_colours(self):
        row = contrast.check({"on-accent": "#ffffff", "accent": "#5b8cff"}, [["on-accent", "accent"]])[0]
        found = contrast.finding(row, "tokens.json")
        self.assertEqual(found["severity"], "high")
        self.assertIn("on-accent on accent", found["title"])
        self.assertIn("needs 4.5:1", found["title"])
        text = contrast.nearest_passing("#ffffff", "#5b8cff", 4.5)  # white text can only darken
        page = contrast.nearest_passing("#5b8cff", "#ffffff", 4.5, both_ways=False)
        self.assertGreaterEqual(contrast.ratio(text, "#5b8cff"), 4.5)
        self.assertGreaterEqual(contrast.ratio("#ffffff", page), 4.5)
        self.assertIn("use %s for on-accent, or %s for accent (changing accent changes every pair "
                      "that uses it). Change it in the tokens" % (text, page), found["fix"])

    def test_command_line_fix_talks_about_colours_not_tokens(self):
        code, out, _ = run("#777777", "#ffffff")
        self.assertEqual(code, 1)
        self.assertIn("fix:   use #767676 as the text colour\n", out)
        self.assertNotIn("tokens", out)
        data = json.loads(run("#fff", "#fff", "--json")[1])
        self.assertEqual(data["findings"][0]["fix"],
                         "use #757575 as the text colour, or #757575 as the background")
        fix = json.loads(run("#2a2a2a", "#303030", "--json")[1])["findings"][0]["fix"]
        self.assertTrue(fix.startswith("use #"), fix)
        self.assertIn("as the text colour, or #", fix)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, data, name="tokens.json"):
        path = os.path.join(self.dir, name)
        if not isinstance(data, (str, bytes)):
            data = json.dumps(data)
        with open(path, "wb") as handle:
            handle.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        return path

    def test_failing_file_shows_the_finding_block(self):
        path = self.write({"color": {"text": "#999999", "bg": "#ffffff"}, "pairs": [["text", "bg"]]})
        code, out, _ = run(path)
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)
        self.assertIn("HIGH", out)
        for label in ("where: " + path + ": text on bg", "why:", "fix:   use #"):
            self.assertIn(label, out)
        self.assertIn("1 pair checked, 1 failing WCAG AA.", out)

    def test_human_output_labels_and_grades(self):
        path = self.write({"color": {"text": "#111111", "muted": "#767676", "line": "#868e98",
                                     "faint": "#bbbbbb", "bg": "#ffffff"},
                           "pairs": [["text", "bg"], ["muted", "bg"], ["line", "bg", "ui"],
                                     ["faint", "bg", "large"]]})
        code, out, _ = run(path)
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("AAA ") and lines[0].endswith("text on bg"), lines[0])
        self.assertTrue(lines[1].startswith("AA ") and lines[1].endswith("muted on bg"), lines[1])
        self.assertTrue(lines[2].startswith("PASS") and lines[2].endswith("line on bg  (ui)"), lines[2])
        self.assertTrue(lines[3].startswith("FAIL") and lines[3].endswith("faint on bg  (large)"), lines[3])
        self.assertIn("needs 3:1", out)

    def test_json_shape(self):
        path = self.write({"color": {"text": "#999999", "ok": "#111111", "bg": "#ffffff"},
                           "pairs": [["text", "bg"], ["ok", "bg"]]})
        code, out, _ = run(path, "--json")
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(set(data), {"pairs", "findings", "summary"})
        self.assertEqual(len(data["pairs"]), 2)
        self.assertEqual(set(data["findings"][0]), {"severity", "title", "where", "why", "fix"})
        self.assertEqual(data["summary"],
                         {"pairs": 2, "failing": 1, "unchecked": 0, "high": 1, "verdict": "FAIL"})

    def test_json_pass(self):
        code, out, _ = run(TEMPLATE, "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["summary"]["verdict"], "PASS")

    def test_no_pairs_list_is_bad_input_never_a_guess(self):
        """Regression: without pairs the old guess put on-accent on bg and dark text on light."""
        no_key = template()
        del no_key["pairs"]
        cases = [no_key] + [dict(template(), pairs=value) for value in ([], None, {}, 0, "", False)]
        for number, tokens in enumerate(cases):
            with self.subTest(pairs=tokens.get("pairs", "missing")):
                code, out, err = run(self.write(tokens, "t%d.json" % number))
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn('needs a "pairs" list', err)

    def test_byte_order_mark_is_fine(self):
        data = json.dumps({"color": {"text": "#111111", "bg": "#ffffff"}, "pairs": [["text", "bg"]]})
        self.assertEqual(run(self.write(b"\xef\xbb\xbf" + data.encode("utf-8")))[0], 0)

    def test_very_deep_nesting_is_bad_input_not_a_crash(self):
        deep = '{"color": ' + '{"a": ' * 5000 + '"#fff"' + "}" * 5000 + "}"
        code, _, err = run(self.write(deep))
        self.assertEqual(code, 2)
        self.assertIn("nested too deeply", err)

    def test_hash_is_optional_on_the_command_line(self):
        self.assertEqual(run("222222", "ffffff")[0], 0)
        code, out, _ = run("777777", "fff")
        self.assertEqual(code, 1)
        self.assertIn("#777777 on #fff", out)

    def test_bad_input_exits_2(self):
        cases = [
            ([os.path.join(self.dir, "missing.json")], "not a file that exists"),
            ([self.dir], "is a folder: give the tokens.json file"),
            ([self.write('{"color": {"bg": "#fff"\n  "text": "#000"}}', "broken.json")],
             "broken.json is not valid JSON (line 2, column 3): look for a missing or extra comma"),
            ([self.write([1, 2], "list.json")], "JSON object"),
            ([self.write({"color": {"bg": "#fff"}, "pairs": "text,bg"}, "p.json")], 'needs a "pairs" list'),
            ([self.write({"color": {"accent": "#2f5bea"}}, "none.json")], 'needs a "pairs" list'),
            ([self.write({"pairs": [["text", "bg"]]}, "nogroup.json")], 'has no colours: put them in'),
            ([self.write({"color": "#fff", "pairs": [["text", "bg"]]}, "flat.json")], "group of named"),
            ([self.write({"color": {"bg": "#fff"}, "pairs": [["text", "bg"]]}, "u.json")], "no colour named"),
            ([self.write({"color": {"bg": 255, "text": "#000"}, "pairs": [["text", "bg"]]}, "n.json")],
             "bg is 255, write it as #rgb or #rrggbb"),
            ([self.write({"color": {"bg": "ffffff", "text": "111111"}, "pairs": [["text", "bg"]]},
                         "h.json")], "write it as #rgb or #rrggbb"),
            ([self.write({"color": {"text-muted": "#eee", "text": {"muted": "#111"}, "bg": "#fff"},
                          "pairs": [["text-muted", "bg"]]}, "d.json")], "both called 'text-muted'"),
            ([self.write({"color": {"bg": "#fff", "text": "#000"}, "pairs": [["text", "bg", "big"]]},
                         "k.json")], "normal, large or ui"),
            ([self.write(b"\xff\xfe{}", "latin.json")], "is not UTF-8 text"),
            (["#fff"], "give two colours, text then background"),
            (["#fff", "white"], "two colours"),
            (["a.json", "#fff", "#000"], "one token file, or two colours"),
        ]
        for args, words in cases:
            for extra in ([], ["--json"]):
                with self.subTest(args=args, extra=extra):
                    code, out, err = run(*(args + extra))
                    self.assertEqual(code, 2)
                    self.assertEqual(out, "")
                    self.assertIn(words, err)

    def test_no_arguments_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as caught:
            run()
        self.assertEqual(caught.exception.code, 2)


class ConsoleTests(unittest.TestCase):
    def test_a_cp1252_pipe_gets_escapes_not_a_crash(self):
        """Windows pipes are cp1252 (no arrow): the arrow prints as \\u2192, no crash."""
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "tokens.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"color": {"bg": "#ffffff", "text-caf\u00e9-\u2192": "#000000"},
                           "pairs": [["text-caf\u00e9-\u2192", "bg"]]}, handle)
            code, out, err = run_cp1252(contrast.__file__, path)
        self.assertEqual(code, 0, err)
        self.assertIn("text-caf\u00e9-\\u2192 on bg", out)


if __name__ == "__main__":
    unittest.main()
