"""Tests for forge-build/pagetext.py: what it keeps of the original's saved pages (the visible text
only, in blocks), where, what it refuses, and that the secret, tracker and code scans find nothing
in what it keeps."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402

pagetext = load("forge-build", "pagetext")
copycheck = load("forge-build", "copycheck")
KEPT = os.path.join("forge-work", "original-text")

PAGE = """<!doctype html>
<html lang="nl"><head>
  <title>Groeiwijs - waterplanner voor je kamerplanten</title>
  <meta name="description" content="Groeiwijs onthoudt wanneer elke kamerplant water nodig heeft.">
  <style>.hero { color: #1e4d3b }</style>
  <script>window.secret = "never kept"; trackEverything();</script>
</head><body>
  <nav><ul><li><a href="/prijzen/">Prijzen</a></li><li><a href="/contact/">Contact</a></li></ul></nav>
  <h1>Elke plant <span class="markeer">op tijd</span> water.</h1>
  <p class="lead">Zo zie je elke dag in een oogopslag
     wat er moet gebeuren met je planten.</p>
  <div class="knoppen"><a class="btn" href="/app/">Open de planner</a> <a href="/prijzen/">Bekijk de prijzen</a></div>
  <img src="/assets/hero.png" alt="Een monstera in een terracotta pot op de vensterbank">
  <input name="naam" placeholder="Bijvoorbeeld Monstera woonkamer" data-key="ignored-attribute">
  <svg viewBox="0 0 10 10"><title>logo drawing</title><text>Groeiwijs</text></svg><svg/>
  <p>Na de tekening<br>gaat het verder</p>
</body></html>
"""


def run(*args):
    """main() in the current folder: (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = pagetext.main(list(args))
    return code, out.getvalue(), err.getvalue()


class Blocks(unittest.TestCase):
    def test_words_are_lower_case_letters_and_digits(self):
        self.assertEqual(pagetext.words("Elke plant, op TIJD! 1 tot 30 e-mail sk_live_X"),
                         ["elke", "plant", "op", "tijd", "1", "tot", "30", "e", "mail", "sk", "live", "x"])
        self.assertEqual(pagetext.words("ﬁets één"), ["fiets", "één"])  # NFKC: the fi ligature

    def test_the_same_words_and_inline_tags_as_copycheck(self):
        """The kept text and the clone are cut into words the same way, or runs would never match."""
        self.assertEqual(pagetext.WORD.pattern, copycheck.WORD.pattern)
        self.assertEqual(pagetext.INLINE, copycheck.INLINE)

    def test_blocks_keep_what_a_visitor_reads(self):
        texts = [" ".join(found) for found in pagetext.page_blocks(PAGE)]
        for block in ("groeiwijs waterplanner voor je kamerplanten",
                      "groeiwijs onthoudt wanneer elke kamerplant water nodig heeft",
                      "elke plant op tijd water",  # the span stays inside the sentence
                      "zo zie je elke dag in een oogopslag wat er moet gebeuren met je planten",
                      "open de planner", "bekijk de prijzen",  # two buttons side by side are two blocks
                      "een monstera in een terracotta pot op de vensterbank", "bijvoorbeeld monstera woonkamer",
                      "prijzen", "contact", "na de tekening", "gaat het verder"):  # <br> ends a block
            self.assertIn(block, texts)
        kept = " ".join(texts).split()
        for never in ("secret", "trackeverything", "color", "1e4d3b", "logo", "drawing", "assets", "png",
                      "ignored", "markeer", "btn", "prijzen/"):
            self.assertNotIn(never, kept)

    def test_only_a_link_next_to_an_inline_element_ends_a_block(self):
        """Labels side by side are not one sentence: a link next to a link or a label ends the block, as in
        a footer. Other inline elements side by side stay in it, as in a headline with a span per word, and
        two that touch are two words."""
        blocks = pagetext.page_blocks(
            '<h1><span class="w">Elke</span> <span class="w">kamerplant</span><span class="w">krijgt</span> '
            '<span class="w">precies</span><span class="w">op</span> <span class="w">tijd</span> water</h1>'
            '<p>Groeiwijs is <strong>gratis</strong> <em>voor altijd</em> en houdt je planten bij.</p>'
            '<footer><a href="/privacy">Privacy</a><span>&middot;</span><a href="/voorwaarden">Voorwaarden</a>'
            ' <a href="/contact">Contact</a> <strong>Groeiwijs</strong> <a href="/app/">Open de planner</a></footer>')
        self.assertEqual([" ".join(found) for found in blocks],
                         ["elke kamerplant krijgt precies op tijd water",
                          "groeiwijs is gratis voor altijd en houdt je planten bij",
                          "privacy", "voorwaarden", "contact", "groeiwijs", "open de planner"])

    def test_submit_values_and_share_tags(self):
        blocks = pagetext.page_blocks('<input type="submit" value="Stuur het bericht">'
                                      '<input type="text" value="not a label">'
                                      '<meta property="og:description" content="Elke plant op tijd">'
                                      '<meta name="viewport" content="width=device-width">')
        self.assertEqual(blocks, [["stuur", "het", "bericht"], ["elke", "plant", "op", "tijd"]])


class Project(unittest.TestCase):
    """A project folder (with forge-work/) and a folder outside it for the saved pages."""

    def setUp(self):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base)
        self.project, self.outside = os.path.join(base, "project"), os.path.join(base, "pages")
        os.makedirs(os.path.join(self.project, "forge-work"))
        os.makedirs(self.outside)
        old = os.getcwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, old)

    def save(self, name, text, folder=None):
        path = os.path.join(folder or self.outside, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path


class KeepTests(Project):
    def test_one_text_file_per_page(self):
        code, out, err = run(self.save("source-1.html", PAGE))
        self.assertEqual(code, 0, err)
        path = os.path.join(KEPT, "source-1.txt")
        self.assertIn("Kept 59 words of", out)
        self.assertIn(path, out)
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        self.assertTrue(lines[0].startswith("# "))
        self.assertIn("elke plant op tijd water", lines)
        self.assertTrue(all(line == " ".join(pagetext.words(line)) for line in lines[1:]))
        self.assertEqual(run(self.save("source-1.html", PAGE.replace("Contact", "Hulp")))[0], 0)
        with open(path, encoding="utf-8") as handle:  # keeping a page again replaces its text
            self.assertIn("hulp", handle.read().split())

    def test_a_folder_gives_its_html_files(self):
        self.save(os.path.join("a", "source-2.htm"), "<p>Een tweede pagina met tekst</p>")
        self.save("notes.txt", "not a page")
        self.save("source-1.html", PAGE)
        code, out, err = run(self.outside)
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(os.listdir(KEPT)), ["source-1.txt", "source-2.txt"])
        self.assertIn('only 5 words: drawn by JavaScript? Save it from a browser, "Webpage, Complete"', out)

    def test_a_complete_save_and_an_old_encoding(self):
        """A browser's "Webpage, Complete" puts the page's files in source-1_files/, embedded pages too:
        those are not the original's pages. A page saved in cp1252 keeps its accents."""
        self.save(os.path.join("source-1_files", "embed.html"), "<p>Someone else's widget text</p>")
        with open(os.path.join(self.outside, "source-1.html"), "wb") as handle:
            handle.write("<p>Café één keer per week water geven</p>".encode("cp1252"))
        code, out, err = run(self.outside)
        self.assertEqual(code, 0, err)
        self.assertEqual(os.listdir(KEPT), ["source-1.txt"])
        with open(os.path.join(KEPT, "source-1.txt"), encoding="utf-8") as handle:
            self.assertIn("café één keer per week water geven", handle.read())

    def test_bad_input_keeps_nothing(self):
        inside = self.save("source-1.html", PAGE, folder=os.path.join(self.project, "saved"))
        shell = self.save("source-3.html", "<div id='app'></div><script>start()</script>")
        good = self.save("source-1.html", PAGE)
        twin = self.save(os.path.join("b", "source-1.html"), PAGE)
        image = self.save("source-4.html", "\x89PNG\r\n\x1a\n\0\0")
        for args, words in [((inside,), "is inside this project"), ((good, shell), "has no visible text"),
                            ((good, image), "has no visible text"), ((good, twin), "would both be source-1.txt"),
                            ((os.path.join(self.outside, "nothing.html"),), "does not exist"),
                            ((os.path.join(self.outside, "b", "x"),), "does not exist")]:
            with self.subTest(args=args):
                code, out, err = run(*args)
                self.assertEqual((code, out), (2, ""))
                self.assertIn(words, err)
                self.assertFalse(os.path.exists(KEPT))
        os.makedirs(os.path.join(self.outside, "empty"))
        code, _, err = run(os.path.join(self.outside, "empty"))
        self.assertEqual((code, "no saved page in" in err), (2, True))
        shutil.rmtree("forge-work")
        code, _, err = run(good)
        self.assertEqual((code, "run pagetext.py from the project root" in err), (2, True))
        with self.assertRaises(SystemExit):
            run()  # no page at all is a usage error

    def test_a_cp1252_pipe_gets_escapes_not_a_crash(self):
        page = self.save("source-łódź.html", "<p>Een pagina uit łódź met tekst</p>")
        code, out, err = run_cp1252(os.path.join(ROOT, "forge-build", "pagetext.py"), page, cwd=self.project)
        self.assertEqual(code, 0, err)
        self.assertIn("source-\\u0142ód\\u017a.txt", out)


class KeptTextPassesTheOtherScans(Project):
    def test_secretscan_trackers_and_codecheck_find_nothing_in_the_kept_text(self):
        keys = ["sk_" + "live_" + "a1B2c3D4e5F6g7H8i9J0k1L2", "AKIA" + "Z7QW4RT2YP8MXN3K",
                "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8", "AIza" + "SyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q",
                "xoxb-" + "123456789012-abcdefghijkl", "whsec_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3",
                "sk_" + "test_" + "m1N2b3V4c5X6z7L8k9J0h1G2", "key-" + "0123456789abcdef0123456789abcdef",
                "sk-ant-" + "api03-a1B2c3D4e5F6g7H8i9J0", "SG." + "a1B2c3D4e5F6g7H8i9J0k1" + "." + "x" * 43]
        page = PAGE.replace("</body>", "".join(
            "<pre>api_key = '%s'</pre><p title='%s'>%s</p>" % (key, key, key) for key in keys) +
            "<pre>-----BEGIN RSA " + "PRIVATE KEY-----</pre><p>postgres://admin:" + "s3cretpass@db.example.com/app</p>"
            "<pre>password = \"hunter2hunter2\"</pre><p>We use https://www.googletagmanager.com/gtag/js, "
            "connect.facebook.net with fbq('init'), fonts.googleapis.com and eval(location.hash)</p>"
            "<script src='https://www.google-analytics.com/analytics.js'></script>"
            "<a href='https://hooks.slack.com/services/" + "T000/B000/XXXX'>hook</a></body>")
        self.assertEqual(run(self.save("source-1.html", page))[0], 0)
        with open(os.path.join(self.project, "index.html"), "w", encoding="utf-8") as handle:
            handle.write("<!doctype html><title>Mijn eigen planner</title><p>Eigen woorden.</p>\n")
        for script in ("secretscan.py", "trackers.py", "codecheck.py"):
            with self.subTest(script=script):
                done = subprocess.run([sys.executable, os.path.join(ROOT, "forge-secure", script), ".", "--json",
                                       "--fail-on", "low"], cwd=self.project, timeout=120, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                self.assertEqual(json.loads(done.stdout)["findings"], [])
        done = subprocess.run([sys.executable, os.path.join(ROOT, "forge-secure", "secretscan.py"),
                               self.save("same-page.html", page), "--fail-on", "low"], timeout=120,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(done.returncode, 1, "the saved page itself must trip the scan, or this test proves nothing")


if __name__ == "__main__":
    unittest.main()
