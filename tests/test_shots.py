"""Tests for forge-design/shots.example.mjs, the capture script the skills copy into a project: it
parses as an ES module, its header explains every flag it reads, it refuses wrong use before it needs
Playwright, and it asks nothing of another host. BrowserTests run it for real on small pages served on
127.0.0.1, only where Playwright and its Chromium are installed (set FORGE_NO_BROWSER=1 to skip them)."""

import functools
import glob
import http.server
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT  # noqa: E402

SCRIPT = os.path.join(ROOT, "forge-design", "shots.example.mjs")
CHANGED = os.path.join(ROOT, "forge-design", "changed.py")
HEAD = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>%s</title><style>%s</style>'
        '</head><body>%s</body></html>')
SITE = {  # name: (style, body, script). Each page plants one thing the script must see, or must not.
    "index": ("body{margin:0;font:16px sans-serif}", "<h1>Home</h1>", ""),
    "login": ("", '<form><input name="user"><input type="pass' + 'word" name="secret"></form>', ""),
    "theme": (":root[data-theme=dark]{color-scheme:dark;background:#0b0d10;color:#eee}"
              ":root[data-theme=light]{color-scheme:light;background:#fff;color:#111}",
              "<h1>Remembered theme, dark by default</h1>", ""),
    "wide": ("body{margin:0}", '<form><input style="width:512px"></form>', ""),
    "frame": ("html,body{margin:0;height:100%;overflow:hidden}.app{display:flex;flex-direction:column;height:100vh}"
              "header{height:56px;background:#eee}main{flex:1;overflow:auto}.grid{display:grid;"
              "grid-template-columns:300px 300px;gap:12px;padding:12px}.card{height:300px;background:#ddd}"
              "nav{position:fixed;bottom:0;left:0;right:0;height:56px;background:#333;color:#fff}",
              '<div class="app"><header>Frame</header><main><div class="grid">%s</div></main></div><nav>Tabs</nav>'
              % "".join('<div class="card">%d</div>' % n for n in range(6)), ""),
    "maplist": ("html,body{margin:0;height:100%;overflow:hidden}.split{display:flex;height:100vh}"
                ".list{width:400px;overflow:auto}.list p{height:200px;margin:0}.map{flex:1;background:#cde}",
                '<div class="split"><div class="list">%s</div><div class="map"><canvas width="900" height="900">'
                '</canvas></div></div>' % "".join("<p>Water %d</p>" % n for n in range(12)), ""),
    "contrast": ("body{margin:0;font:16px/1.5 sans-serif;background:#fff;color:#111}.tabs{display:flex;gap:6px;"
                 "padding:16px}.tab{padding:10px 12px;border:1px solid #ccc;background:#fff;color:#111}"
                 '.tab[aria-selected="false"]{color:#d4d4d4}.shade{position:relative;isolation:isolate;'
                 'padding:40px 16px;color:#fff}.shade::before{content:"";position:absolute;inset:0;'
                 "background:#0b1020;z-index:-1}.layer{position:relative;padding:40px 16px;color:#fff}"
                 ".layer .bg{position:absolute;inset:0;background:#123}.layer p{position:relative;margin:0}",
                 '<div class="tabs" role="tablist"><button class="tab" role="tab" aria-selected="true">Catches'
                 '</button><button class="tab" role="tab" aria-selected="false">Waters</button></div>'
                 '<section class="shade"><h1>Dawn on the lake</h1></section>'
                 '<section class="layer"><div class="bg"></div><p>Text over a placed layer</p></section>', ""),
    "darkhero": ("body{margin:0;background:#fff;color:#111}.hero{height:100vh;background:#0b1020;color:#fff}"
                 "@media (prefers-color-scheme: dark){body{background:#111;color:#eee}}",
                 '<section class="hero"><h1>Dawn</h1></section><p>Below the hero</p>', ""),
    "same": ("body{background:#fafafa;color:#222}", "<p>One theme only</p>", ""),
    # Live after 7 s, past the 5 s that --scene-frames gives any scene to show up: only its poster child is seen.
    "scene": ("body{margin:0}.hero-scene{position:relative;height:60vh;overflow:hidden}.spin{width:200px;height:200px;"
              "margin:40px;background:linear-gradient(90deg,#0b6,#06b);animation:turn 1.3s linear infinite}"
              "@keyframes turn{to{transform:rotate(360deg)}}",
              '<div class="hero-scene"><div data-scene-poster></div><div class="spin"></div></div>',
              "setTimeout(function(){document.querySelector('.hero-scene').setAttribute('data-scene','live')},7000);"),
    # A full-screen hero whose colour is a placed layer: the text below it is on the white page.
    "hero": ("body{margin:0;font:16px/1.5 sans-serif;background:#fff;color:#111}.hero{position:relative;"
             "min-height:100vh;color:#fff;padding:40px 16px;box-sizing:border-box}.hero .shade{position:absolute;"
             "inset:0;background:#0b1020}.hero h1{position:relative;margin:0}.below{margin:0;padding:16px;color:#555}",
             '<section class="hero"><div class="shade"></div><h1>Morning on the river</h1></section>'
             '<p class="below">Below the hero, dark grey on white</p>', ""),
    # A backdrop fixed behind the whole page: white text reads on it, a planted dark text does not.
    "backdrop": ("body{margin:0;font:16px/1.5 sans-serif;color:#fff}.night{position:fixed;inset:0;background:#0b1020;"
                 "z-index:-1}.dim{color:#222}main{padding:16px}",
                 '<div class="night"></div><main><h1>Night water</h1><p class="dim">Planted dark text</p></main>', ""),
    # A fixed frame whose main area is a board of columns, built to scroll sideways: never "wide".
    "board": ("html,body{margin:0;height:100%;overflow:hidden}.app{display:flex;flex-direction:column;height:100vh}"
              "header{height:56px;background:#eee}.board{flex:1;display:flex;gap:12px;padding:12px;overflow-x:auto}"
              ".column{flex:0 0 280px;overflow-y:auto;background:#f4f4f4}"
              ".card{height:120px;margin:8px;background:#ddd}",
              '<div class="app"><header>Board</header><div class="board">%s</div></div>'
              % "".join('<div class="column"><div class="card">%s</div></div>' % name
                        for name in ("To do", "Doing", "Review", "Done", "Later", "Ideas")), ""),
    "private": ("", "<h1>Members only</h1>", ""),
}
SESSION = "session=ok"  # the cookie /private asks for; STATE_JSON holds it as a Playwright storage state
STATE_JSON = ('{"cookies": [{"name": "session", "value": "ok", "domain": "127.0.0.1", "path": "/", "expires": -1, '
              '"httpOnly": false, "secure": false, "sameSite": "Lax"}], "origins": []}')
THEME_JS = ("localStorage.setItem('theme', matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');")
REMEMBER = ('try{var t=localStorage.getItem("theme");document.documentElement.dataset.theme='
            '(t==="light"||t==="dark")?t:"dark"}catch(e){}')


def build_site(folder):
    """The pages above as NAME.html in FOLDER; /theme reads its remembered theme before the first paint."""
    for name, (style, body, script) in SITE.items():
        head_script = REMEMBER if name == "theme" else ""
        page = HEAD % (name, style, body + ("<script>%s</script>" % script if script else ""))
        if head_script:
            page = page.replace("<style>", "<script>%s</script><style>" % head_script, 1)
        with open(os.path.join(folder, name + ".html"), "w", encoding="utf-8") as handle:
            handle.write(page)


class Site(http.server.SimpleHTTPRequestHandler):
    """/app sends the visitor to /login, as an expired session does, and so does /private without the
    SESSION cookie; /x serves x.html. Each request's path and cookies go into the server's `seen` list."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        cookies = self.headers.get("Cookie") or ""
        getattr(self.server, "seen", []).append((path, cookies))
        if path == "/app" or (path == "/private" and SESSION not in cookies):
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return
        self.path = "/index.html" if path == "/" else path + ".html"
        super().do_GET()


def playwright_here(folder):
    """True when node finds Playwright (or @playwright/test) from FOLDER and its Chromium is on disk."""
    if os.environ.get("FORGE_NO_BROWSER") or not shutil.which("node"):
        return False
    probe = ("let p; try { p = require('playwright'); } catch (e) { p = require('@playwright/test'); }"
             "process.exit(require('fs').existsSync(p.chromium.executablePath()) ? 0 : 1);")
    try:
        done = subprocess.run(["node", "-e", probe], cwd=folder, timeout=60, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0
FLAGS = {"--no-dark", "--state", "--viewport-only", "--wait", "--reduced", "--frames", "--video", "--scene-frames",
         "--storage", "--init-script", "--overflow", "--contrast", "--width"}


def read():
    with open(SCRIPT, encoding="utf-8") as handle:
        return handle.read()


class ShotsTests(unittest.TestCase):
    def test_every_flag_it_reads_is_explained_in_the_header(self):
        text = read()
        header = "\n".join(line for line in text.split("\n") if line.startswith("//"))
        flags = set(re.findall(r"'(--[a-z][a-z-]+)'", text))
        self.assertTrue(FLAGS <= flags, FLAGS - flags)
        for flag in flags:
            with self.subTest(flag=flag):
                self.assertIn(flag, header)

    def test_it_names_the_files_changed_py_reads(self):
        header = read().split("import ")[0]
        for words in ("-f1.png", "-reduced.png", ".webm", "changed.py --moves", "-s1.png", "-s6.png",
                      "--moves OUT/<name>-390-f[1-4].png", "--moves\n//                    OUT/<name>-1440-s*.png"):
            with self.subTest(words=words):
                self.assertIn(words, header)
        self.assertNotIn("-f*.png", header)  # f5 to f7 differ by the scroll alone: never a proof that it moves

    def test_scene_frames_wait_for_a_live_scene_with_a_limit(self):
        text = read()
        self.assertRegex(text, r"const SCENE_LIMIT = 120000;")
        self.assertIn("data-scene-poster", text)
        self.assertIn("now === 'live'", text)

    def test_a_sign_in_page_in_place_of_the_screen_is_never_a_still(self):
        text = read()
        self.assertIn("a sign-in page, in place of", text)
        self.assertIn("input[type=\"password\"]:visible", text)
        sign_in = re.search(r"const SIGN_IN = /(.*)/i;", text).group(1)
        for path in ("/login", "/users/sign_in", "/auth/login", "/inloggen", "/signin"):
            with self.subTest(path=path):
                self.assertRegex(path, re.compile(sign_in.replace("\\/", "/"), re.I))
        for path in ("/dashboard", "/blogin-tips", "/authors"):
            with self.subTest(path=path):
                self.assertNotRegex(path, re.compile(sign_in.replace("\\/", "/"), re.I))

    def test_only_the_base_site_and_no_other_host(self):
        text = read()
        urls = re.findall(r"https?://[^\s'\"`)]+", text)
        hosts = [url for url in urls if not re.match(r"https?://(localhost|127\.0\.0\.1)\b|https?://\.\.\.", url)]
        self.assertEqual(hosts, [])
        self.assertIn("is not ${site.origin}", text)  # a page that led away is never shot

    def test_without_playwright_it_says_to_install_it_next_to_the_copy(self):
        """Before /forge-build scaffolds a new app, a package.json in the project root would push its own aside."""
        text = read()
        self.assertIn("npm install --prefix forge-work/design @playwright/test", text)
        self.assertNotIn("npm i -D -E", text)

    def test_it_never_waits_forever(self):
        text = read()
        self.assertRegex(text, r"const LOAD_LIMIT = \d+")
        self.assertRegex(text, r"const QUIET_LIMIT = \d+")

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_it_parses_as_an_es_module(self):
        with tempfile.TemporaryDirectory() as folder:
            copy = os.path.join(folder, "shots.mjs")
            shutil.copy(SCRIPT, copy)
            done = subprocess.run(["node", "--check", copy], timeout=60, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_wrong_use_is_exit_2_before_it_looks_for_playwright(self):
        """A folder with no node_modules: these must stop on the flags, never get as far as Playwright."""
        with tempfile.TemporaryDirectory() as folder:
            copy = os.path.join(folder, "shots.mjs")
            shutil.copy(SCRIPT, copy)
            with open(os.path.join(folder, "state.json"), "w", encoding="utf-8") as handle:
                handle.write('{"cookies": [], "origins": []}')
            base = ["node", copy, "http://127.0.0.1:9", os.path.join(folder, "out")]
            cases = [(["--width", "12"], "--width takes whole pixels"), (["--storage", "theme"], "--storage takes KEY=VALUE"),
                     (["/", "--state", "nope.json", "/app"], "nope.json is not a storage state file"),
                     (["--init-script", "nope.js"], "nope.js is not a file that can be read"),
                     (["--wait", "-5"], "--wait takes milliseconds"), (["--fast"], "unknown option --fast"),
                     (["--state"], "--state needs a value")]
            for args, words in cases:
                with self.subTest(args=args):
                    done = subprocess.run(base + args, cwd=folder, timeout=60, stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE, universal_newlines=True)
                    self.assertEqual(done.returncode, 2, done.stderr)
                    self.assertIn(words, done.stderr)
                    self.assertNotIn("Playwright is not installed", done.stderr)
            done = subprocess.run(["node", copy, "--help"], cwd=folder, timeout=60, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertTrue(done.stdout.startswith("Pictures of your own app"), done.stdout[:80])
            self.assertIn("--scene-frames", done.stdout)


class PackTests(unittest.TestCase):
    def test_no_doc_proves_motion_with_the_scroll_frames(self):
        """--frames' f5 to f7 are taken after scrolling, so any page taller than the window 'moves' between
        f4 and f5: `--moves <name>-390-f*.png` passes with no motion at all. Use f[1-4], or the scene frames."""
        found = []
        for path in glob.glob(os.path.join(ROOT, "forge*", "**", "*.*"), recursive=True):
            if path.endswith((".md", ".mjs", ".js", ".json", ".html", ".py")) and os.path.isfile(path):
                with open(path, encoding="utf-8") as handle:
                    for number, line in enumerate(handle, start=1):
                        if re.search(r"\d+-f\*\.png", line):
                            found.append("%s:%d" % (os.path.relpath(path, ROOT), number))
        self.assertEqual(found, [], "pass the entrance frames f[1-4] to --moves, never f*")


class BrowserTests(unittest.TestCase):
    """The script itself in one Chromium at a time, on the pages of SITE served on 127.0.0.1: the names of
    the files, the lines it prints and its exit code. About a minute."""

    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp()
        if not playwright_here(cls.folder):
            shutil.rmtree(cls.folder, ignore_errors=True)
            raise unittest.SkipTest("Playwright and its Chromium are not installed here")
        cls.site = os.path.join(cls.folder, "site")
        os.mkdir(cls.site)
        build_site(cls.site)
        cls.copy = os.path.join(cls.folder, "shots.mjs")
        shutil.copy(SCRIPT, cls.copy)
        with open(os.path.join(cls.folder, "theme.js"), "w", encoding="utf-8") as handle:
            handle.write(THEME_JS)
        with open(os.path.join(cls.folder, "member.json"), "w", encoding="utf-8") as handle:
            handle.write(STATE_JSON)
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Site, directory=cls.site))
        cls.server.seen = []
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.folder, ignore_errors=True)

    def shoot(self, out, *args):
        """Runs the copy into OUT: its exit code, all it printed, and the files it wrote."""
        done = subprocess.run(["node", self.copy, self.base, os.path.join(self.folder, out)] + list(args),
                              cwd=self.folder, timeout=300, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, encoding="utf-8", errors="backslashreplace")
        return done.returncode, done.stdout + done.stderr, sorted(os.listdir(os.path.join(self.folder, out)))

    def test_names_checks_and_a_sign_in_page(self):
        code, said, files = self.shoot("checks", "--width", "390", "--viewport-only", "--overflow", "--contrast",
                                       "--init-script", "theme.js", "/app", "/theme", "/wide", "/frame", "/contrast",
                                       "/darkhero", "/same", "/hero", "/backdrop", "/board")
        self.assertEqual(code, 1, said)
        self.assertIn("it led to /login, a sign-in page, in place of /app", said)
        self.assertFalse([name for name in files if name.startswith("app-")], files)
        for name in ("theme-390-light.png", "theme-390-dark.png", "darkhero-390-light.png", "darkhero-390-dark.png",
                     "same-390-light.png"):
            with self.subTest(name=name):
                self.assertIn(name, files)  # a light page with a dark hero is named light, its dark theme dark
        self.assertNotIn("same-390-dark.png", files)
        self.assertRegex(said, r"same \S*same-390-light\.png: with the system set to dark the page names no theme")
        self.assertRegex(said, r"wide  /wide at 390px light: the page is 5\d\dpx wide in a window of 390px")
        self.assertRegex(said, r"wide  /frame at 390px light: its scroll panel main is 6\d\dpx wide inside 390px")
        self.assertNotIn("wide  /board", said)  # its columns scroll sideways by design, and it never scrolls down
        self.assertRegex(said, r'low contrast  /contrast at 390px light: "Waters" 1\.\d\d:1')
        self.assertNotIn('"Dawn on the lake"', said)  # white on its ::before shade, not on the white page
        self.assertIn('not measured: look at "Text over a placed layer" (section.layer > p, ', said)
        # A hero's layer fills the first screen only: the text over it is named, the text below it reads on white.
        self.assertIn('"Morning on the river" (section.hero > h1, ', said)
        self.assertNotIn('"Below the hero', said)
        # A backdrop fixed behind the whole page is what its text is measured on.
        self.assertNotIn('"Night water"', said)
        self.assertRegex(said, r'low contrast  /backdrop at 390px light: "Planted dark text" 1\.\d\d:1')

    def test_a_state_counts_for_the_paths_after_it(self):
        """/ before the --state is shot signed out, /private after it signed in (it sends a visitor without
        the cookie to /login, which would fail the run)."""
        self.server.seen.clear()
        code, said, files = self.shoot("state", "--width", "390", "--viewport-only", "--no-dark",
                                       "/", "--state", "member.json", "/private")
        self.assertEqual(code, 0, said)
        stills = [name for name in files if name.endswith(".png")]
        self.assertEqual(stills, ["home-390-light.png", "private-390-light.png"], said)
        home = [cookies for path, cookies in self.server.seen if path == "/"]
        private = [cookies for path, cookies in self.server.seen if path == "/private"]
        self.assertTrue(home and private, self.server.seen)
        self.assertFalse([cookies for cookies in home if SESSION in cookies], home)
        self.assertTrue(all(SESSION in cookies for cookies in private), private)

    def test_scene_frames_wait_for_the_poster_and_give_the_size(self):
        """The scene goes live after 7 s: the still waits for it only by its poster child (a still waits for
        no scene it does not see), and the scene frames would give up on an unseen scene after 5 s."""
        code, said, files = self.shoot("scene", "--width", "390", "--viewport-only", "--no-dark", "--scene-frames",
                                       "/scene")
        self.assertEqual(code, 0, said)
        frames = [os.path.join(self.folder, "scene", "scene-390-s%d.png" % number) for number in range(1, 7)]
        self.assertEqual([os.path.basename(frame) for frame in frames if not os.path.isfile(frame)], [], said)
        self.assertRegex(said, r"scene-390-light\.png  \(1 scene\(s\) live after \d+ s")
        self.assertRegex(said, r"scene-390-s1\.png  \(1 scene\(s\) live after \d+ s, the first 390 x 506 px in the "
                               r"window \(100% of its width, 60% of its height\)")
        moved = subprocess.run([sys.executable, CHANGED, "--moves"] + frames, timeout=120, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(moved.returncode, 0, moved.stdout + moved.stderr)
        self.assertIn("SOMETHING MOVES", moved.stdout)

    def test_a_fixed_frame_is_opened_up_but_a_list_beside_a_map_is_not(self):
        code, said, _ = self.shoot("pages", "--width", "1440", "/frame", "/maplist")
        self.assertEqual(code, 0, said)
        saved = [line for line in said.splitlines() if line.startswith("200 ")]  # a file's own line: its status
        frame = [line for line in saved if "frame-1440-light.png" in line]
        self.assertTrue(frame and "its scroll panel opened up" in frame[0], said)
        self.assertIn("bar(s) fixed to the bottom", frame[0])
        listed = [line for line in saved if "maplist-1440-light.png" in line]
        self.assertTrue(listed and "opened up" not in listed[0], said)


if __name__ == "__main__":
    unittest.main()
