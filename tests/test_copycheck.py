"""Tests for forge-build/copycheck.py: the runs of words it finds in the clone, where it says they
are, what it lets through (short runs, labels side by side, the allow list) and what it skips."""

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

copycheck = load("forge-build", "copycheck")
pagetext = load("forge-build", "pagetext")

ORIGINAL = """<html><head><title>Groeiwijs - waterplanner voor je kamerplanten</title></head><body>
  <h1>Elke plant <span>op tijd</span> water.</h1>
  <p>Zo zie je elke dag in een oogopslag wat er moet gebeuren met je planten.</p>
  <div><a href="/app/">Open de planner</a> <a href="/prijzen/">Bekijk de prijzen</a></div>
  <p>Bijvoorbeeld Monstera woonkamer</p>
</body></html>
"""


def run(*args):
    """main() in the current folder: (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = copycheck.main(list(args))
    return code, out.getvalue(), err.getvalue()


class TagBlocks(unittest.TestCase):
    def test_inline_tags_stay_in_a_block_and_others_end_it(self):
        text = ('<main>\n  <p>Bij ons <a href="/x" title="a > b">zie je</a> elke\n  dag.</p>'
                '<Button onClick="go()">Open</Button><br/>Verder</main>')
        self.assertEqual(copycheck.tag_blocks(text), [(2, ["bij", "ons", "zie", "je", "elke", "dag"]),
                                                      (3, ["open"]), (3, ["verder"])])

    def test_file_blocks_add_lines_and_html_blocks(self):
        self.assertEqual(copycheck.file_blocks("a.ts", "x = 'Een zin';\n\n"), [(1, ["x", "een", "zin"])])
        self.assertEqual(copycheck.file_blocks("a.vue", "<p>Een\nzin</p>"),
                         [(1, ["p", "een"]), (2, ["zin", "p"]), (1, ["een", "zin"])])


class Project(unittest.TestCase):
    """A project folder whose forge-work/original-text/ holds the original's kept text."""

    def setUp(self):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base)
        self.project = os.path.join(base, "project")
        os.makedirs(os.path.join(self.project, "forge-work", "original-text"))
        old = os.getcwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, old)
        self.keep("source-1", ORIGINAL)

    def keep(self, name, page):
        """Keep PAGE's text in forge-work/original-text/NAME.txt, the way pagetext.py does."""
        self.write(os.path.join("forge-work", "original-text", name + ".txt"),
                   "# kept\n" + "".join(" ".join(found) + "\n" for found in pagetext.page_blocks(page)))

    def write(self, path, text):
        os.makedirs(os.path.dirname(os.path.join(self.project, path)), exist_ok=True)
        with open(os.path.join(self.project, path), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)


class CheckTests(Project):
    def test_a_copied_sentence_is_found_with_where_it_is(self):
        self.write("src/home.html", "<main>\n  <p>Bij ons zie je elke dag in een oogopslag wat er moet\n"
                                    "  gebeuren.</p>\n  <p>Elke plant <em>op tijd</em> water</p>\n</main>\n")
        self.write("src/planner.ts", 'const lead = "Zo zie je elke dag in een oogopslag";\n')
        code, out, err = run()
        self.assertEqual(code, 1, err)
        # the sentence goes on over a line break: as a block it is one run, longer than either line
        self.assertIn('11 words in a row from the original: "zie je elke dag in een oogopslag wat er moet gebeuren"',
                      out)
        self.assertIn("where: " + os.path.join("src", "home.html") + ":2\n", out)
        self.assertIn("why:   the original's page source-1 has the same words", out)
        self.assertIn("FAIL: 2 run(s) shared with the original.", out)
        data = json.loads(run("--json")[1])
        self.assertEqual(data["summary"]["verdict"], "FAIL")
        self.assertEqual([f["words"] for f in data["findings"]], [11, 8])
        self.assertEqual(data["findings"][1]["places"], [os.path.join("src", "planner.ts") + ":1"])
        self.assertEqual(set(data["findings"][0]), {"severity", "title", "where", "why", "fix", "run", "words",
                                                    "places", "original"})

    def test_short_runs_and_labels_side_by_side_are_not_copy(self):
        self.write("index.html", "<p>Zo zie je elke dag</p><div><a>Open de planner</a> <a>Bekijk de prijzen</a>"
                                 "</div>\n<p>Bijvoorbeeld Monstera woonkamer</p>\n<p>Open de planner bekijk de prijzen</p>")
        code, out, _ = run()
        self.assertEqual(code, 0, out)
        self.assertIn("PASS: no run of 6 or more words", out)
        code, out, _ = run("--words", "4")
        self.assertEqual(code, 1)
        self.assertIn('"zo zie je elke dag"', out)

    def test_a_longer_run_hides_the_runs_inside_it(self):
        self.write("a.html", "<p>Zo zie je elke dag in een oogopslag wat er moet\ngebeuren</p>\n")
        data = json.loads(run("--json")[1])
        self.assertEqual([(f["words"], f["places"]) for f in data["findings"]], [(12, ["a.html:1"])])

    def test_entities_and_escapes_count_as_the_characters_they_stand_for(self):
        """pagetext.py reads the original's entities as the characters a visitor sees. copycheck.py reads the
        clone's files the same way, so a copy that keeps them (JSX wants &apos;) is still one run. So is one
        in a JSON file, where json.dump writes the curly quote as \\u2019."""
        self.keep("source-2", "<p>Foto&rsquo;s &amp; notities van je planten, zo&rsquo;n beetje elke&nbsp;dag: "
                              "dat&rsquo;s alles.</p>")
        self.write("index.html", "<p>Foto&rsquo;s &amp; notities van je planten, zo&rsquo;n beetje elke&nbsp;dag: "
                                 "dat&rsquo;s alles.</p>\n")
        self.write("app/page.tsx", "export const Lead = () => <p>Foto&apos;s &amp; notities van je planten, zo&#39;n "
                                   "beetje elke dag: dat&apos;s alles.</p>;\n")
        self.write("messages.json", '{"lead": "Foto\\u2019s & notities van je planten, zo\\u2019n beetje elke dag: '
                                    'dat\\u2019s alles."}\n')
        code, out, _ = run("--json")
        self.assertEqual(code, 1, out)
        self.assertEqual([(f["run"], f["places"]) for f in json.loads(out)["findings"]],
                         [("foto s notities van je planten zo n beetje elke dag dat s alles",
                           ["index.html:1", "messages.json:1", os.path.join("app", "page.tsx") + ":1"])])

    def test_a_headline_with_a_span_per_word(self):
        """A page builder puts each word of a headline in a span of its own, with space between or touching.
        pagetext.py keeps the headline whole, so a copy of it is found, written plainly or in the same markup.
        So is a sentence with <strong> and <em> side by side."""
        self.keep("source-2", '<h1><span class="w">Elke</span> <span class="w">kamerplant</span><span class="w">'
                              'krijgt</span> <span class="w">precies</span><span class="w">op</span> <span>tijd</span>'
                              ' water</h1><p>Groeiwijs is <strong>gratis</strong> <em>voor altijd</em> en houdt je '
                              'planten bij.</p>')
        self.write("index.html", "<h1>Elke kamerplant krijgt precies op tijd water</h1>\n"
                                 "<p>Groeiwijs is gratis voor altijd en houdt je planten bij.</p>\n")
        self.write("copied.vue", "<h1><span>Elke</span><span>kamerplant</span><span>krijgt</span><span>precies"
                                 "</span><span>op</span><span>tijd</span> water</h1>\n")
        code, out, _ = run("--json")
        self.assertEqual(code, 1, out)
        self.assertEqual([(f["run"], f["places"]) for f in json.loads(out)["findings"]],
                         [("groeiwijs is gratis voor altijd en houdt je planten bij", ["index.html:2"]),
                          ("elke kamerplant krijgt precies op tijd water", ["copied.vue:1", "index.html:1"])])

    def test_two_pages_of_the_original(self):
        self.write(os.path.join("forge-work", "original-text", "source-2.txt"),
                   "zo zie je elke dag in een oogopslag\n")
        self.write("a.txt", "zo zie je elke dag in een oogopslag\n")
        data = json.loads(run("--json")[1])
        self.assertEqual(data["findings"][0]["original"], ["source-1", "source-2"])
        self.assertIn("pages source-1 and source-2 have", data["findings"][0]["why"])

    def test_the_allow_list_lets_a_phrase_through(self):
        self.write("terms.html", "<p>Zo zie je elke dag in een oogopslag. Dat is alles.</p>\n")
        self.write(copycheck.ALLOW_FILE, "# legal phrase, OK from the user on 2026-11-03\n"
                                         "Zo zie je elke dag in een oogopslag.\n")
        code, out, _ = run()
        self.assertEqual(code, 0, out)
        self.assertIn("each needs the user's OK: zo zie je elke dag in een oogopslag", out)
        self.write("more.html", "<p>Ja: zo zie je elke dag in een oogopslag wat er moet gebeuren met je planten</p>")
        code, out, _ = run()
        self.assertEqual(code, 1)  # what is left after the phrase is still checked
        self.assertIn('7 words in a row from the original: "wat er moet gebeuren met je planten"', out)

    def test_what_is_skipped(self):
        sentence = "<p>zo zie je elke dag in een oogopslag</p>\n"
        for path in ("node_modules/x/index.html", "dist/index.html", "forge-work/notes.html", "package-lock.json",
                     "src/.next/page.html", "vendor/lib/view.php", "app.js.map"):
            self.write(path, sentence)
        with open(os.path.join(self.project, "logo.png"), "wb") as handle:
            handle.write(b"\x89PNG\r\n\x1a\n\0\0" + sentence.encode("utf-8"))
        self.write("index.html", "<p>Eigen woorden</p>\n")
        code, out, _ = run()
        self.assertEqual(code, 0, out)
        self.assertIn("Files checked: 1, skipped: 1 (binary)", out)
        self.assertEqual(run("dist")[0], 1)  # a folder you name is checked, build output too
        self.assertEqual(run(os.path.join("src", ".next", "page.html"))[0], 1)

    def test_bad_input_and_incomplete_checks_exit_2(self):
        os.makedirs("empty")
        for args, words, stream in [(("empty",), "INCOMPLETE, so not a pass. No file read.", 1),
                                    (("--words", "2"), "from 3 to 50", 2), (("missing",), "does not exist", 2)]:
            with self.subTest(args=args):
                code, out, err = run(*args)
                self.assertEqual(code, 2)
                self.assertIn(words, out if stream == 1 else err)
        self.write(os.path.join("forge-work", "original-text", "source-1.txt"), "# kept by pagetext.py\n\n")
        code, out, err = run()  # pagetext kept no word: save the pages again
        self.assertEqual((code, out), (2, ""))
        self.assertIn("holds no text of the original: save its pages again as forge-recon Step 2 says", err)
        self.assertIn("run pagetext.py on them, or ask the user", err)
        self.assertLessEqual(len(err.rstrip()), 200, "the gate shows 200 characters of a line")
        shutil.rmtree(os.path.join("forge-work", "original-text"))
        code, out, err = run()  # no folder: a secondhand recon kept no page (the gate skips the check then)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("With no page saved (a secondhand recon) there is nothing to compare: say so at the checkpoint",
                      err)

    def test_kept_text_with_no_run_that_long_passes_with_a_note(self):
        """An original of short labels, or in a language written without spaces, has no 6 words in a row.
        Nothing can be shared at that length, so that is a pass, with a note to pass on at the checkpoint.
        A shorter --words still finds what the clone shares with it."""
        self.keep("source-1", "<nav><a href='/'>Planten</a> <a href='/p'>Prijzen</a></nav><p>Gemaakt in Utrecht</p>")
        self.write("index.html", "<footer>Gemaakt in Utrecht</footer>\n")
        code, out, err = run()
        self.assertEqual(code, 0, err)
        self.assertIn("Note: the original's kept text has no 6 words in a row (a language written without spaces, "
                      "or only short labels), so nothing can be shared at that length: say so at the checkpoint.\n"
                      "PASS: no run of 6 or more words", out)
        summary = json.loads(run("--json")[1])["summary"]
        self.assertEqual(summary["verdict"], "PASS")
        self.assertIn("no 6 words in a row", summary["note"])
        code, out, _ = run("--json", "--words", "3")
        self.assertEqual((code, json.loads(out)["summary"]["note"]), (1, ""))

    def test_a_cp1252_pipe_gets_escapes_not_a_crash(self):
        self.write(os.path.join("forge-work", "original-text", "source-2.txt"),
                   "zo werkt het in \u0142\u00f3d\u017a en elders voor iedereen\n")
        self.write("index.html", "<p>zo werkt het in \u0142\u00f3d\u017a en elders</p>\n")
        code, out, err = run_cp1252(os.path.join(ROOT, "forge-build", "copycheck.py"), cwd=self.project)
        self.assertEqual(code, 1, err)
        self.assertIn("in \\u0142\u00f3d\\u017a en", out)


class EndToEnd(Project):
    def test_kept_pages_against_a_clone(self):
        """pagetext.py keeps a saved page, copycheck.py finds the sentence the clone took from it."""
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)
        page = os.path.join(outside, "source-7.html")
        with open(page, "w", encoding="utf-8") as handle:
            handle.write("<p>Je planten blijven in je eigen browser, niet op onze servers.</p>")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pagetext.main([page]), 0)
        self.write("privacy.html", '<meta name="description" content="Druppeldag: je planten blijven in je eigen '
                                   'browser.">\n')
        code, out, _ = run()
        self.assertEqual(code, 1)
        self.assertIn('"je planten blijven in je eigen browser"', out)
        self.assertIn("page source-7 has", out)

    def test_vowel_signs_stay_inside_a_word(self):
        """Thai and Hindi write vowel signs (combining marks) inside a word: they are no word break, so a
        Thai clause stays one word, as Japanese does, and a Hindi line splits at its spaces only."""
        self.write(os.path.join("forge-work", "original-text", "source-9.txt"),
                   "ข้อมูลของคุณจะถูกเก็บไว้ในเบราว์เซอร์ของคุณเท่านั้น ไม่ต้องสมัครสมาชิก\n"
                   "आपका डेटा केवल आपके ब्राउज़र में रहता है\n")
        self.write("privacy.html", "<p>ข้อมูลของคุณจะถูกเก็บไว้บนอุปกรณ์นี้</p>\n<p>आपका डेटा केवल आपके ब्राउज़र में रहता</p>\n")
        code, out, _ = run()
        self.assertEqual(code, 1, out)
        self.assertIn("7 words in a row from the original", out)  # the Hindi line, word by word
        self.assertIn("where: privacy.html:2", out)
        self.assertNotIn("privacy.html:1", out)  # the Thai clause differs: no run of 6 fragments

    def test_a_language_written_without_spaces(self):
        """Japanese has no spaces between words, so a clause counts as one word and no block of the page has
        6. pagetext.py says so while the saved pages still exist. copycheck.py passes with a note, and a
        shorter --words still finds a paragraph the clone took from it."""
        os.remove(os.path.join("forge-work", "original-text", "source-1.txt"))
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)
        page = os.path.join(outside, "source-8.html")
        paragraph = "データはお使いのブラウザにだけ保存され、外部に送信されることはありません。アカウントも不要です。登録は無料です。"
        with open(page, "w", encoding="utf-8") as handle:
            handle.write("<h1>植物の水やりを、もう忘れない。</h1><p>%s</p>" % paragraph)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(pagetext.main([page]), 0)
        self.assertIn("no 6 words in a row", out.getvalue())
        self.write("privacy.html", "<p>%s</p>\n" % paragraph)
        code, out, _ = run()
        self.assertEqual(code, 0, out)
        self.assertIn("Note: the original's kept text has no 6 words in a row", out)
        code, out, _ = run("--words", "3")
        self.assertEqual(code, 1, out)
        self.assertIn("4 words in a row from the original", out)


if __name__ == "__main__":
    unittest.main()
