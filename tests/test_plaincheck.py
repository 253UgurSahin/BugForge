"""Tests for forge-check/plaincheck.py: the plain rules a page's HTML shows by itself.

Pages are checked from strings and saved files; the URL mode (which runs getpage.py) is tested against
a small web server on 127.0.0.1 that runs in a thread. No other network.
"""

import contextlib
import http.server
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `python3 -m unittest tests.x` works too
from _load import ROOT, load, run_cp1252  # noqa: E402

mod = load("forge-check", "plaincheck")
SCRIPT = os.path.join(ROOT, "forge-check", "plaincheck.py")
RULES = mod.load_rules()

CLEAR = """<!doctype html><html lang="nl"><head><title>Afspraken</title></head><body>
<nav><a href="/">Home</a><a href="/afspraken">Afspraken</a><a href="/klanten">Klanten</a></nav>
<h1>Je afspraken</h1>
<p>Nog geen afspraken. Maak je eerste afspraak.</p>
<button>Afspraak maken</button>
<button><svg aria-hidden="true"></svg> Verwijderen</button>
<form><label for="naam">Naam</label><input id="naam" placeholder="bijv. Anna">
<label>Telefoonnummer <input type="tel"></label>
<input type="search" aria-label="Zoeken"><input type="hidden" name="x"><input type="submit" value="Afspraak opslaan"></form>
</body></html>"""


def rules_of(html):
    return sorted({finding["rule"] for finding in mod.check(mod.Page(html), RULES)})


def found(html, rule):
    return [finding for finding in mod.check(mod.Page(html), RULES) if finding["rule"] == rule]


class RuleTests(unittest.TestCase):
    def test_a_clear_page_has_no_findings(self):
        self.assertEqual(rules_of(CLEAR), [])

    def test_vague_labels_in_english_and_dutch(self):
        for label in ("Verzenden", "OK", "Klik hier →", "Lees meer...", "Submit", "click here", "Doorgaan"):
            with self.subTest(label=label):
                self.assertEqual(rules_of("<button>%s</button>" % label), ["vague_label"])
        page = '<a href="/a">Meer</a><input type="submit" value="Versturen"><button>Opslaan</button>'
        finding = found(page, "vague_label")
        self.assertEqual(len(finding), 1, "one finding for all the vague words")
        self.assertIn('"meer" on line 1', finding[0]["where"])
        self.assertIn('"versturen"', finding[0]["where"])

    def test_a_label_with_the_action_and_the_thing_is_fine(self):
        for label in ("Afspraak maken", "Bekijk de prijzen", "Meer opties", "Volgende pagina", "Opslaan"):
            with self.subTest(label=label):
                self.assertEqual(rules_of("<button>%s</button>" % label), [])

    def test_an_icon_alone_is_found_and_a_screen_reader_word_does_not_help(self):
        for page in ('<button><svg></svg></button>', '<a href="/x" aria-label="Menu"><i class="icon"></i></a>',
                     '<button><svg></svg><span class="sr-only">Verwijderen</span></button>',
                     '<button><img src="bin.svg" alt="Verwijderen"></button>', '<input type="image" src="go.png" alt="Zoek">'):
            with self.subTest(page=page):
                self.assertEqual(rules_of(page), ["icon_only"])
        self.assertEqual(rules_of('<button><svg></svg> Menu</button>'), [])
        self.assertEqual(rules_of('<button hidden><svg></svg></button><div aria-hidden="true"><a href="/"><i></i></a></div>'), [])

    def test_a_field_needs_a_visible_label(self):
        for page in ('<input placeholder="Telefoon">', '<input aria-label="Naam">', '<select></select>',
                     '<textarea></textarea>', '<label for="other">X</label><input id="naam">'):
            with self.subTest(page=page):
                self.assertEqual(rules_of(page), ["placeholder_label"])
        for page in ('<label for="a">Naam</label><input id="a">', '<label>Naam <input></label>',
                     '<input type="checkbox" id="c"><label for="c">Ja graag</label>', '<input type="hidden">',
                     '<input type="search" placeholder="Zoeken">'):
            with self.subTest(page=page):
                self.assertEqual(rules_of(page), [])

    def test_jargon_in_visible_text_only(self):
        finding = found("<p>Authenticatie mislukt: Invalid input</p>", "jargon")
        self.assertEqual(len(finding), 1)
        self.assertIn('"authenticatie"', finding[0]["where"])
        self.assertIn('"invalid input"', finding[0]["where"])
        hidden = ("<script>var authenticatie = 1</script><style>.payload{}</style>"
                  "<div hidden>sessie verlopen</div><p class='sr-only'>timeout</p>")
        self.assertEqual(rules_of(hidden), [])

    def test_programming_values_in_their_exact_case(self):
        for text in ("Prijs: NaN", "Naam: undefined", "[object Object]", "Datum: null", "TypeError: x"):
            with self.subTest(text=text):
                self.assertEqual(rules_of("<p>%s</p>" % text), ["leak"])
        for text in ("Nan komt langs", "Null tolerance policy", "Het is undefinedness", "nanny"):
            with self.subTest(text=text):
                self.assertEqual(rules_of("<p>%s</p>" % text), [])

    def test_a_long_form_needs_steps(self):
        fields = "".join('<label for="f%d">Veld</label><input id="f%d">' % (n, n) for n in range(8))
        self.assertEqual(rules_of("<form>%s</form>" % fields), ["long_form"])
        self.assertIn("8 fields", found("<form>%s</form>" % fields, "long_form")[0]["where"])
        self.assertEqual(rules_of("<p>Stap 1 van 3</p><form>%s</form>" % fields), [])
        self.assertEqual(rules_of("<form><progress value=1 max=3></progress>%s</form>" % fields), [])
        self.assertEqual(rules_of("<form>%s</form>" % fields[:len(fields) // 2]), [])

    def test_a_long_menu(self):
        links = "".join('<a href="/%d">Item %d</a>' % (n, n) for n in range(9))
        self.assertEqual(rules_of("<nav>%s</nav>" % links), ["long_menu"])
        five = "".join('<a href="/%d">Item %d</a>' % (n, n) for n in range(5))
        self.assertEqual(rules_of("<nav>%s</nav><a href='/x'>Ander</a><a href='/y'>Nog een</a>" % five), [],
                         "links after the menu do not count for it")

    def test_most_severe_first_and_every_finding_has_words(self):
        findings = mod.check(mod.Page('<button>OK</button><input><p>NaN</p>'), RULES)
        self.assertEqual([finding["severity"] for finding in findings], ["high", "high", "medium"])
        for finding in findings:
            self.assertEqual(set(finding) >= {"rule", "severity", "title", "why", "fix", "where"}, True)

    def test_the_rules_file_matches_plain_md(self):
        with open(os.path.join(ROOT, "forge-design", "plain.md"), encoding="utf-8") as handle:
            doc = handle.read()
        for rule in RULES["rules"]:
            with self.subTest(rule=rule):
                self.assertIn("`%s`" % rule, doc, "plain.md names each rule plaincheck.py reports")


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)

    def write(self, name, text, raw=None):
        path = os.path.join(self.folder, name)
        with open(path, "wb") as handle:
            handle.write(raw if raw is not None else text.encode("utf-8"))
        return path

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = mod.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_exit_codes_and_fail_on(self):
        clear, vague = self.write("clear.html", CLEAR), self.write("vague.html", "<button>OK</button>")
        self.assertEqual(self.run_main(clear)[0], 0)
        self.assertEqual(self.run_main(vague)[0], 0, "a medium finding passes the default --fail-on high")
        self.assertEqual(self.run_main(vague, "--fail-on", "medium")[0], 1)
        self.assertEqual(self.run_main(clear, vague, "--fail-on", "medium")[0], 1)

    def test_a_page_that_cannot_be_read_is_exit_2(self):
        clear = self.write("clear.html", CLEAR)
        for bad in (os.path.join(self.folder, "missing.html"), self.write("empty.html", ""),
                    self.write("pic.png", "", raw=b"\x89PNG\r\n\x1a\n\0\0\0"), "http://user:" + "pw@127.0.0.1/"):
            with self.subTest(bad=bad):
                code, _, err = self.run_main(clear, bad)
                self.assertEqual(code, 2)
                self.assertTrue(err.startswith("error: could not check"))

    def test_json(self):
        code, out, _ = self.run_main(self.write("a.html", "<button>OK</button><input>"), "--json")
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(data["summary"]["pages"], 1)
        self.assertEqual(data["summary"]["high"], 1)
        self.assertEqual([f["rule"] for f in data["pages"][0]["findings"]], ["placeholder_label", "vague_label"])

    def test_page_text_is_never_printed(self):
        secret_words = "Mevrouw Jansen woont op de Dorpsstraat 12"
        code, out, _ = self.run_main(self.write("a.html", "<p>%s</p><button>OK</button>" % secret_words))
        self.assertNotIn("Jansen", out)
        self.assertIn('"ok"', out)

    def test_help_and_a_cp1252_pipe(self):
        code, out, _ = run_cp1252(SCRIPT, "--help")
        self.assertEqual(code, 0)
        self.assertIn("PAGE", out)
        page = self.write("arrow.html", "<a href='/x'>Lees meer →</a><p>Prijs: NaN €</p>")
        code, out, err = run_cp1252(SCRIPT, page)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("clear for everyone" if code == 0 else "finding(s)", out)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = (CLEAR if self.path == "/clear" else "<button>Verzenden</button><input>").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class UrlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_a_local_url_is_loaded_once_and_checked(self):
        code, out, err = run_cp1252(SCRIPT, self.base + "/clear", self.base + "/form", "--json")
        self.assertEqual((code, err), (1, ""))
        pages = json.loads(out)["pages"]
        self.assertEqual(pages[0]["findings"], [])
        self.assertEqual({f["rule"] for f in pages[1]["findings"]}, {"vague_label", "placeholder_label"})


if __name__ == "__main__":
    unittest.main()
