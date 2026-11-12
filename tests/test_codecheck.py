"""Tests for forge-check/codecheck.py (quick first-pass check for risky code)."""

import ast
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # also lets "-m unittest tests.test_codecheck" work
from _load import load, run_cp1252, symlink  # noqa: E402

codecheck = load("forge-check", "codecheck")
SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugin", "forge-check", "codecheck.py")
SPEC_SKIP_DIRS = {".git", "node_modules", "vendor", "venv", ".venv", "__pycache__", "dist", "build", ".next",
                  ".nuxt", "out", "coverage", "storage/framework", ".cache", ".idea", ".vscode"}

# One or more risky lines per rule: (language, rule id, severity the spec asks for, line).
RISKY = [
    ("php", "php-eval", "critical", "<?php eval($code); ?>"),
    ("php", "php-unserialize", "critical", "$cart = unserialize($_COOKIE['cart']);"),
    ("php", "php-sql", "critical", "$rows = mysqli_query($db, \"SELECT * FROM users WHERE id = \" . $_GET['id']);"),
    ("php", "php-sql", "critical", "$sql = \"DELETE FROM posts WHERE id = {$request->input('id')}\";"),
    ("php", "php-sql", "critical", "$q = \"SELECT * FROM users WHERE id = $_GET[id]\";"),
    ("php", "php-sql", "critical", "$q = sprintf(\"SELECT * FROM users WHERE id = %s\", $_GET['id']);"),
    ("php", "php-sql", "critical", "$db->query(\"UPDATE posts SET title = '\" . $request->post('title') . \"'\");"),
    ("php", "php-shell", "critical", "system(\"ping -c 1 \" . $_GET['host']);"),
    ("php", "php-shell", "critical", "$out = shell_exec('whois ' . $_REQUEST['domain']);"),
    ("php", "php-shell", "critical", "passthru($_GET['cmd']);"),
    ("php", "php-shell", "critical", "$out = `ls {$_GET['dir']}`;"),
    ("php", "php-shell", "critical", "exec('a ' . escapeshellarg($_GET['f']) . ' ' . $_GET['g']);"),
    ("php", "php-echo-input", "high", "echo \"Hello \" . $_GET['name'];"),
    ("php", "php-echo-input", "high", "<p><?= $_POST['comment'] ?></p>"),
    ("php", "php-echo-input", "high", "if ($ok) print $_GET['msg'];"),
    ("php", "php-blade-raw", "medium", "<div>{!! $post->body !!}</div>"),
    ("php", "php-raw-sql", "high", "$users = DB::table('users')->whereRaw(\"age > $age\")->get();"),
    ("php", "php-raw-sql", "high", "$total = DB::raw('SUM(price) * ' . $rate);"),
    ("php", "php-raw-sql", "high", "$posts = Post::orderByRaw($sort)->get();"),
    ("php", "php-weak-hash", "medium", "$hash = md5($password);"),
    ("php", "php-weak-hash", "medium", "$user->passwd = sha1($input);"),
    ("php", "php-weak-hash", "medium", "$check = md5($db_pass);"),
    ("python", "py-eval", "high", "result = eval(user_input)"),
    ("python", "py-eval", "high", "exec(code, {})"),
    ("python", "py-pickle", "high", "obj = pickle.loads(request.body)"),
    ("python", "py-pickle", "high", "obj = cPickle.loads(blob)"),
    ("python", "py-yaml-load", "medium", "config = yaml.load(text)"),
    ("python", "py-yaml-load", "medium", "data = yaml.unsafe_load(request.body)"),
    ("python", "py-shell-true", "high", "subprocess.run(cmd, shell=True)"),
    ("python", "py-os-system", "medium", "os.system('convert ' + name)"),
    ("python", "py-sql", "critical", 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")'),
    ("python", "py-sql", "critical", 'cursor.execute("SELECT * FROM users WHERE name = \'%s\'" % name)'),
    ("python", "py-sql", "critical", 'cursor.execute("SELECT * FROM users WHERE id = " + user_id)'),
    ("python", "py-sql", "critical", 'cursor.execute("DELETE FROM t WHERE id = {}".format(item_id))'),
    ("python", "py-sql", "critical", "cursor.execute(query % params)"),
    ("python", "py-sql", "critical", "User.objects.raw(f\"SELECT * FROM auth_user WHERE email = '{email}'\")"),
    ("python", "py-sql", "critical", "qs.extra(where=[\"name = '%s'\" % name])"),
    ("python", "py-sql", "critical", 'cursor.executescript(f"DROP TABLE {name}")'),
    ("python", "py-sql", "critical", "sql = f\"SELECT * FROM events_event WHERE title LIKE '%%{term}%%'\""),
    ("python", "py-sql", "critical", 'query = "DELETE FROM t WHERE id = %s" % item_id'),
    ("python", "py-sql", "critical", "q = \"SELECT * FROM t WHERE name = '\" + name + \"'\""),
    ("python", "py-sql", "critical", 'q = "select * from t where id = {}".format(x)'),
    ("python", "py-sql", "critical", 'stmt = rf"UPDATE shop_order SET note = {note!r} WHERE id = 1"'),
    ("python", "py-naive-now", "low", "from django.db import models; today = datetime.datetime.now()"),
    ("python", "py-naive-now", "low", "from django.db import models; stamp = datetime.utcnow()"),
    ("python", "py-verify-false", "high", "requests.get(url, verify=False)"),
    ("python", "py-debug", "medium", "DEBUG = True"),
    ("python", "py-allowed-hosts", "medium", "ALLOWED_HOSTS = ['*']"),
    ("python", "py-allowed-hosts", "medium", "ALLOWED_HOSTS += ['*']"),
    ("python", "py-mark-safe", "medium", "return mark_safe(comment.text)"),
    ("python", "py-csrf-exempt", "medium", "@csrf_exempt"),
    ("python", "py-csrf-exempt", "medium", 'path("hook/", csrf_exempt(views.stripe_webhook)),'),
    ("python", "py-csrf-exempt", "medium", '@method_decorator(csrf_exempt, name="dispatch")'),
    ("js", "js-eval", "high", "const result = eval(input);"),
    ("js", "js-eval", "high", "const fn = new Function('a', body);"),
    ("js", "js-raw-html", "medium", "<div dangerouslySetInnerHTML={{ __html: post.body }} />"),
    ("js", "js-raw-html", "medium", '<div v-html="post.body"></div>'),
    ("js", "js-raw-html", "medium", "{@html post.body}"),
    ("js", "js-raw-html", "medium", "el.innerHTML = message;"),
    ("js", "js-raw-html", "medium", "list.innerHTML += '<li>' + item + '</li>';"),
    ("js", "js-raw-html", "medium", 'el.innerHTML = "" + location.hash;'),
    ("js", "js-shell", "high", "exec(`convert ${file} out.png`);"),
    ("js", "js-shell", "high", "child_process.execSync('ls ' + dir);"),
    ("js", "js-shell", "high", "exec(baseCmd + req.query.file);"),
    ("js", "js-sql", "critical", "const rows = await db.query(`SELECT * FROM users WHERE id = ${id}`);"),
    ("js", "js-sql", "critical", "knex.raw('SELECT * FROM users WHERE name = ' + name);"),
    ("js", "js-sql", "critical", "await prisma.$queryRawUnsafe(`SELECT * FROM users WHERE id = ${id}`);"),
    ("js", "js-tls-off", "high", "https.request({ host, rejectUnauthorized: false });"),
    ("js", "js-tls-off", "high", "new https.Agent({ 'rejectUnauthorized': false })"),
    ("js", "js-tls-off", "high", "options.rejectUnauthorized = false;"),
    ("js", "js-tls-off", "high", "process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';"),
    ("js", "js-tls-off", "high", 'process.env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0";'),
    ("js", "js-cors-any", "medium", "res.setHeader('Access-Control-Allow-Origin', '*');"),
    ("js", "js-cors-any", "medium", "app.use(cors({ origin: '*' }));"),
    ("js", "js-cors-any", "medium", "app.use(cors());"),
    ("js", "js-next-public", "high", "const key = process.env.NEXT_PUBLIC_STRIPE_SECRET_KEY;"),
]

# Lines that look a bit like the rules but are fine: no finding expected. Many are the fix a rule recommends.
SAFE = [
    ("php", "echo htmlspecialchars($_GET['name'], ENT_QUOTES, 'UTF-8');"),
    ("php", "echo e($request->input('name'));"),
    ("php", "$page = $request->query('page', 1);"),
    ("php", "$sort = $request->query('sort', 'name');"),
    ("php", "$next = '/posts?page=' . $request->query('page');"),
    ("php", "$users = DB::select('select * from users where id = ?', [$request->input('id')]);"),
    ("php", "DB::update('update users set votes = 100 where name = ?', [$_POST['name']]);"),
    ("php", "$stmt = $pdo->prepare('SELECT * FROM t WHERE id = ?'); $stmt->execute([$_GET['id']]);"),
    ("php", "$stmt = $pdo->prepare(\"SELECT * FROM t WHERE id = ?\"); $stmt->execute([$_GET[\"id\"]]);"),
    ("php", "exec('convert ' . escapeshellarg($_GET['file']) . ' out.png');"),
    ("php", "if (isset($_GET['saved'])) echo '<p>Saved!</p>';"),
    ("php", "if (isset($_POST['submit'])) { echo 'Saved'; }"),
    ("php", "$mode = $_GET['print'] ?? 'screen';"),
    ("php", "$users = DB::table('users')->whereRaw('age > ?', [$age])->get();"),
    ("php", "$total = DB::raw('count(*) as total');"),
    ("php", "$raw = $response->getRaw($key);"),
    ("php", "$result = $db->exec('VACUUM');"),
    ("php", "$value = $cache->eval($script);"),
    ("php", "$etag = md5($content);"),
    ("php", "$etag = md5($content); // bypass the cache"),
    ("php", "$id = md5($passport_number);"),
    ("php", "<p>{{ $post->body }}</p>"),
    ("php", "echo 'Please select a file from the list';"),
    ("python", 'cursor.execute("SELECT * FROM users WHERE id = %s", [user_id])'),
    ("python", 'cursor.execute("SELECT * FROM products WHERE name LIKE %s", ["%" + term + "%"])'),
    ("python", 'cursor.execute("SELECT * FROM products WHERE name LIKE %s", (f"%{term}%",))'),
    ("python", 'cursor.execute("SELECT * FROM t WHERE id = %s", (uid,)); log.info(f"looked up {uid}")'),
    ("python", "cursor.execute(sql, params)"),
    ("python", "config = yaml.load(text, Loader=yaml.SafeLoader)"),
    ("python", "config = yaml.safe_load(text)"),
    ("python", "model.eval()"),
    ("python", "data = ast.literal_eval(text)"),
    ("python", "subprocess.run(['ls', path], check=True)"),
    ("python", "DEBUG = False"),
    ("python", "ALLOWED_HOSTS = ['example.com', 'www.example.com']"),
    ("python", "from django.views.decorators.csrf import csrf_exempt"),
    ("python", "from django.views.decorators.csrf import (csrf_exempt, csrf_protect)"),
    ("python", "from django.utils.safestring import mark_safe"),
    ("python", 'print(f"Select a seat from the {n} free seats")'),  # a sentence, not SQL
    ("python", 'log.info(f"Deleted {n} rows from the cart")'),
    ("python", 'msg = "Select one from the list: %s" % name'),
    ("python", 'sql = "SELECT * FROM t WHERE id = %s"'),
    ("python", 'sql = "SELECT * FROM t " "WHERE id = %s"'),
    ("python", "now = datetime.now()"),  # not Django code
    ("python", "from django.utils import timezone; now = timezone.now()"),
    ("python", "from django.db import models; now = datetime.now(tz=timezone.utc)"),
    ("php", "{{-- Never use {!! !!} with user input here --}}"),
    ("js", "el.innerHTML = '';"),
    ("js", "el.innerHTML = ''; // start empty"),
    ("js", "if (el.innerHTML === '') { show(); }"),
    ("js", "el.textContent = message;"),
    ("js", "el.innerHTML = DOMPurify.sanitize(html);"),
    ("js", "<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(post.body) }} />"),
    ("js", "db.query('SELECT * FROM users WHERE id = $1', [id]);"),
    ("js", "const rows = await prisma.$queryRaw`SELECT * FROM users WHERE id = ${id}`;"),
    ("js", "const res = await query(`/api/users/${id}`);"),
    ("js", "const { data } = useQuery(`user-${id}`);"),
    ("js", "execFile('convert', [file, 'out.png']);"),
    ("js", "const match = pattern.exec(text);"),
    ("js", "const m = pattern.exec('prefix' + text);"),
    ("js", "const m = re.exec(`${a}-b`);"),
    ("js", "const value = obj.eval(x);"),
    ("js", "app.use(cors({ origin: 'https://example.com' }));"),
    ("js", "const key = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;"),
    ("js", "if (process.env.NODE_TLS_REJECT_UNAUTHORIZED === '0') warn();"),
    ("js", "if (options.rejectUnauthorized === false) warn();"),
]


def rule_ids(language, text):
    return [f["rule"] for f in codecheck.scan_text(text, language, "sample")]


def make_tree(root, files):
    """Write {relative path: text or bytes} under root."""
    for rel, content in files.items():
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(content if isinstance(content, bytes) else content.encode("utf-8"))


def run_main(*args):
    """Run main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = codecheck.main(list(args))
        except SystemExit as exit_error:  # argparse errors
            code = exit_error.code
    return code, out.getvalue(), err.getvalue()


def run_script(*args, **kwargs):
    """Run codecheck.py as a separate process and return the CompletedProcess."""
    return subprocess.run([sys.executable, SCRIPT] + list(args), capture_output=True, timeout=120, **kwargs)


class RuleTests(unittest.TestCase):
    def test_each_risky_line_hits_exactly_its_rule(self):
        for language, rule_id, _, line in RISKY:
            with self.subTest(line=line):
                self.assertEqual(rule_ids(language, line), [rule_id])

    def test_severities_match_the_spec(self):
        for language, rule_id, severity, line in RISKY:
            with self.subTest(line=line):
                self.assertEqual(codecheck.scan_text(line, language, "x")[0]["severity"], severity)

    def test_every_rule_has_a_sample(self):
        all_ids = {rule["info"]["rule"] for rules in codecheck.RULES.values() for rule in rules}
        self.assertEqual({rule_id for _, rule_id, _, _ in RISKY}, all_ids)
        self.assertEqual(len(all_ids), sum(len(rules) for rules in codecheck.RULES.values()), "ids must be unique")

    def test_every_rule_explains_itself(self):
        for rules in codecheck.RULES.values():
            for rule in rules:
                info = rule["info"]
                self.assertIn(info["severity"], codecheck.SEVERITIES)
                for key in ("title", "why", "fix"):
                    self.assertTrue(info[key].strip(), "%s has no %s" % (info["rule"], key))

    def test_safe_lines_are_not_flagged(self):
        for language, line in SAFE:
            with self.subTest(line=line):
                self.assertEqual(rule_ids(language, line), [])

    def test_rules_only_apply_to_their_own_language(self):
        self.assertEqual(rule_ids("js", "DEBUG = True"), [])
        self.assertEqual(rule_ids("python", "<div>{!! $html !!}</div>"), [])

    def test_opt_out_comment_skips_the_line(self):
        self.assertEqual(rule_ids("js", "const fn = eval(input); // forge:allow reviewed"), [])
        self.assertEqual(rule_ids("python", "DEBUG = True  # forge:allow"), [])

    def test_line_numbers_and_where(self):
        findings = codecheck.scan_text("a = 1\n\nresult = eval(x)\n", "python", "app/views.py")
        places = [(f["where"], f["file"], f["line"]) for f in findings]
        self.assertEqual(places, [("app/views.py:3", "app/views.py", 3)])

    def test_two_rules_on_one_line_give_two_findings(self):
        self.assertEqual(sorted(rule_ids("php", "echo shell_exec($_GET['cmd']);")), ["php-echo-input", "php-shell"])

    def test_old_mac_line_ends_count_as_lines(self):
        findings = codecheck.scan_text("a = 1\r" * 500 + "eval(user)\r", "python", "x")
        self.assertEqual([f["line"] for f in findings], [501])

    def test_very_long_lines_are_checked_to_the_end(self):
        shell = "<?php $p = '" + "QUJD" * 600 + "'; eval(base64_decode($p)); system($_GET['c']);"
        self.assertEqual(sorted(rule_ids("php", shell)), ["php-eval", "php-shell"])
        self.assertEqual(rule_ids("js", "var a=" + "1+" * 1100 + "1;eval(location.hash.slice(1));"), ["js-eval"])


class MultilineTests(unittest.TestCase):
    def test_sql_template_over_several_lines(self):
        code = "const rows = await pool.query(`\n  SELECT * FROM users\n  WHERE id = ${req.params.id}\n`);\nnext();\n"
        findings = codecheck.scan_text(code, "js", "x")
        self.assertEqual([(f["rule"], f["line"]) for f in findings], [("js-sql", 1)])

    def test_python_f_string_on_the_next_line(self):
        code = 'cursor.execute(\n    f"SELECT * FROM users WHERE id = {user_id}"\n)\n'
        self.assertEqual([(f["rule"], f["line"]) for f in codecheck.scan_text(code, "python", "x")], [("py-sql", 1)])

    def test_sql_pieces_glued_together_then_an_f_string(self):
        # Regression (dogfood): the critical injection in events/search.py was not reported.
        code = ('def search(term):\n    return Event.objects.raw(\n        "SELECT * FROM events_event "\n'
                '        "WHERE status = \'published\' "\n        f"AND (title LIKE \'%%{term}%%\')"\n    )\n')
        self.assertEqual([(f["rule"], f["line"]) for f in codecheck.scan_text(code, "python", "x")], [("py-sql", 2)])

    def test_sql_f_string_in_a_variable_first(self):
        # Regression (dogfood): sql = f"SELECT ... {term}" and then .raw(sql) was not reported.
        code = 'def search(term):\n    sql = f"SELECT * FROM events_event WHERE title LIKE \'%%{term}%%\'"\n    return Event.objects.raw(sql)\n'
        self.assertEqual([(f["rule"], f["line"]) for f in codecheck.scan_text(code, "python", "x")], [("py-sql", 2)])
        code = 'sql = f"""\n    SELECT *\n    FROM events_event\n    WHERE title = \'{term}\'\n"""\nrows = Event.objects.raw(sql)\n'
        self.assertEqual([(f["rule"], f["line"]) for f in codecheck.scan_text(code, "python", "x")], [("py-sql", 1)])

    def test_naive_time_only_in_django_code(self):
        code = "from django.db import models\n\nclass Event(models.Model):\n    def upcoming(self):\n" \
               "        return self.filter(starts_at__gte=datetime.now())\n"
        self.assertEqual([(f["rule"], f["line"]) for f in codecheck.scan_text(code, "python", "x")], [("py-naive-now", 5)])
        self.assertEqual(rule_ids("python", code.replace("django", "peewee")), [])

    def test_blade_comments_are_not_checked(self):
        # Regression (dogfood): {!! !!} inside {{-- --}} was reported, once per comment line.
        code = "{{-- Plain-text mail:\n     never {!! $name !!} here\n--}}\n<p>{{ $name }}</p>\n<div>{!! $html !!}</div>\n"
        self.assertEqual([(f["rule"], f["line"]) for f in codecheck.scan_text(code, "php", "a.blade.php")],
                         [("php-blade-raw", 5)])
        code = "{{-- a --}}\r{!! $a !!}\r\n{{-- b\r--}} {!! $b !!}\n{{-- not closed {!! $c !!}\n"
        self.assertEqual([f["line"] for f in codecheck.scan_text(code, "php", "x")], [2, 4, 5])

    def test_safe_multiline_calls_are_not_flagged(self):
        self.assertEqual(rule_ids("js", "db.query(\n  'SELECT * FROM users WHERE id = $1',\n  [id]\n);"), [])
        self.assertEqual(rule_ids("python", 'cursor.execute(\n    "SELECT 1 WHERE a = %s",\n    [a],\n)'), [])

    def test_a_match_is_reported_on_the_line_where_it_starts(self):
        findings = codecheck.scan_text("run(\n  exec(`rm ${x}`)\n);\n", "js", "x")
        self.assertEqual([(f["rule"], f["line"]) for f in findings], [("js-shell", 2)])


class SpeedAndSelfTests(unittest.TestCase):
    def test_pathological_input_stays_fast(self):
        tokens = ["select from ", ".execute(", "pass md5( ", "aRaw( '", "echo ", "{!! ", "`", "query(", "exec(",
                  "ALLOWED_HOSTS = ", ".innerHTML = '' //", "sprintf(", "update x set ", "(\n", "query(`\n",
                  "{{--", "{{-- {!! --}}", 'f"SELECT a ', '"select a ', '"""\n', ".raw('a' ", "datetime.now() django "]
        for token in tokens:
            text = (token * (200000 // len(token)))[:200000]
            for language in ("php", "python", "js"):
                with self.subTest(token=token, language=language):
                    start = time.time()
                    codecheck.scan_text(text, language, "x")
                    self.assertLess(time.time() - start, 5)

    def test_long_words_stay_fast(self):
        start = time.time()  # one regex used to backtrack on long runs of letters: 1 MB of PHP took 6 seconds
        codecheck.scan_text(("a" * 1999 + "\n") * 520, "php", "x")
        self.assertLess(time.time() - start, 2)

    def test_the_script_does_not_flag_itself(self):
        # A copy of the skill in a project's .claude/skills/ must not fail that project's security gate.
        code, out, _ = run_main(SCRIPT, "--json")
        self.assertEqual((code, json.loads(out)["findings"]), (0, []))


class FolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def wheres(self, path):
        code, out, _ = run_main(path, "--json")
        return sorted(f["where"] for f in json.loads(out)["findings"])

    def test_skip_list_matches_the_spec(self):
        self.assertEqual(codecheck.SKIP_DIRS, SPEC_SKIP_DIRS)

    def test_every_skipped_folder_and_unknown_file_type(self):
        files = {name + "/lib/x.py": "eval(x)\n" for name in SPEC_SKIP_DIRS}
        files.update({"src/app.js": "const x = eval(input);\n", "storage/app/upload.php": "<?php eval($x);\n",
                      "notes.txt": "eval(x)\n", "src/framework/ok.py": "eval(x)\n"})
        make_tree(self.root, files)
        self.assertEqual(self.wheres(self.root), ["src/app.js:1", "src/framework/ok.py:1", "storage/app/upload.php:1"])

    def test_storage_framework_is_skipped_however_the_path_is_written(self):
        make_tree(self.root, {"storage/framework/views/c.php": "<?php echo $_GET['q']; ?>\n",
                              "storage/app/a.php": "<?php eval($x);\n"})
        storage = os.path.join(self.root, "storage")
        self.assertEqual(self.wheres(storage), ["app/a.php:1"])
        self.assertEqual(self.wheres(storage + os.sep), ["app/a.php:1"])
        result = run_script(".", "--json", cwd=storage)
        self.assertEqual([f["where"] for f in json.loads(result.stdout)["findings"]], ["app/a.php:1"])

    def test_binary_and_big_files_are_listed_as_skipped(self):
        make_tree(self.root, {
            "image.js": b"\x89PNG\0\0" + b"eval(x)\n",
            "big.py": "x = 1\n" * 200000 + "eval(x)\n",
            "ok.py": "eval(x)\n",
        })
        code, out, err = run_main(self.root, "--json")
        data = json.loads(out)
        self.assertEqual([f["where"] for f in data["findings"]], ["ok.py:1"])
        self.assertEqual(data["summary"]["files_skipped"], ["big.py", "image.js"])
        self.assertEqual((code, data["summary"]["unreadable"], data["summary"]["incomplete"]), (1, [], False))
        code, out, err = run_main(self.root)
        self.assertIn("Skipped (binary or over 1 MB): big.py, image.js", out)
        self.assertNotIn("INCOMPLETE", out)

    def test_symlinks_are_not_followed(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        make_tree(outside.name, {"evil.js": "eval(a)\n", "dir/inner.js": "eval(a)\n"})
        symlink(self, os.path.join(outside.name, "evil.js"), os.path.join(self.root, "link.js"))
        symlink(self, os.path.join(outside.name, "dir"), os.path.join(self.root, "linkdir"))
        self.assertEqual(self.wheres(self.root), [])

    def test_blade_vue_and_svelte_files_are_checked(self):
        make_tree(self.root, {"views/post.blade.php": "<div>{!! $body !!}</div>\n",
                              "src/App.vue": "<div v-html=\"html\"></div>\n", "src/Post.svelte": "{@html body}\n"})
        self.assertEqual(self.wheres(self.root), ["src/App.vue:1", "src/Post.svelte:1", "views/post.blade.php:1"])

    def test_unreadable_file_in_folder_makes_the_scan_incomplete(self):
        make_tree(self.root, {"a.py": "eval(x)\n", "b.py": "print(y)\n"})
        real_open = open

        def flaky_open(path, *args, **kwargs):
            if str(path).endswith("a.py"):
                raise PermissionError(13, "Permission denied")
            return real_open(path, *args, **kwargs)

        with mock.patch.object(codecheck, "open", flaky_open, create=True):
            code, out, err = run_main(self.root, "--json")
            human = run_main(self.root, "--fail-on", "critical")
        data = json.loads(out)
        self.assertEqual((code, data["findings"]), (2, []), "an incomplete scan never looks clean")
        self.assertEqual(data["summary"]["unreadable"], [{"path": "a.py", "reason": "Permission denied"}])
        self.assertTrue(data["summary"]["incomplete"])
        self.assertEqual(human[0], 2)
        self.assertIn("INCOMPLETE, so not a pass. Could not read: a.py (Permission denied)", human[1])

    def test_unreadable_subfolder_is_listed_and_exit_2(self):
        make_tree(self.root, {"locked/a.php": "<?php eval($_GET['x']);\n", "open/b.py": "eval(x)\n"})
        locked, real_scandir = os.path.join(self.root, "locked"), os.scandir

        def scandir(path="."):
            if os.path.abspath(path) == os.path.abspath(locked):
                raise PermissionError(13, "Permission denied", path)
            return real_scandir(path)

        with mock.patch("os.scandir", scandir):
            code, out, err = run_main(self.root, "--json")
            human = run_main(self.root)[1]
        data = json.loads(out)
        self.assertEqual(code, 2)
        self.assertEqual([f["where"] for f in data["findings"]], ["open/b.py:1"])
        self.assertEqual(data["summary"]["unreadable"], [{"path": "locked", "reason": "Permission denied"}])
        self.assertIn("Could not read: locked (Permission denied)", human)

    def test_unreadable_root_folder_is_exit_2(self):
        make_tree(self.root, {"a.php": "<?php eval($_GET['x']);\n"})
        real_scandir = os.scandir

        def scandir(path="."):
            if os.path.abspath(path) == os.path.abspath(self.root):
                raise PermissionError(13, "Permission denied", path)
            return real_scandir(path)

        with mock.patch("os.scandir", scandir):
            code, out, err = run_main(self.root)
        self.assertEqual(code, 2)
        self.assertIn("Nothing was checked", out)
        self.assertIn("INCOMPLETE, so not a pass. Could not read: %s (Permission denied)" % self.root, out)

    @unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() != 0,
                         "needs POSIX permissions and a non-root user: chmod 0 locks no folder on Windows or for root")
    def test_unreadable_folder_for_real(self):
        make_tree(self.root, {"locked/a.php": "<?php eval($_GET['x']);\n", "b.py": "eval(x)\n"})
        locked = os.path.join(self.root, "locked")
        os.chmod(locked, 0)
        try:
            self.assertEqual(run_main(locked)[0], 2)
            code, out, _ = run_main(self.root)
        finally:
            os.chmod(locked, 0o755)
        self.assertEqual(code, 2)
        self.assertIn("Could not read: locked (Permission denied)", out)

    def test_file_name_that_is_not_utf8_does_not_crash(self):
        try:
            with open(os.path.join(os.fsencode(self.root), b"caf\xe9.php"), "wb") as handle:
                handle.write(b"<?php eval($x);\n")
        except (OSError, ValueError):
            self.skipTest("this file system needs UTF-8 file names")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")  # strict, like a normal desktop terminal
        result = run_script(self.root, env=env)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b"caf\\xe9.php:1", result.stdout)


class MainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        make_tree(self.root, {
            "app.php": "<div>{!! $body !!}</div>\n<?php eval($code);\n",  # medium on line 1, critical on line 2
            "only_medium.py": "DEBUG = True\n",
            "only_high.js": "el.x = eval(input);\n",
            "clean.py": "print('hello')\n",
        })

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.root, name)

    def test_human_output(self):
        code, out, _ = run_main(self.path("app.php"))
        self.assertEqual(code, 1)
        self.assertLess(out.index("CRITICAL  Text run as PHP"), out.index("MEDIUM  HTML printed"), "worst first")
        self.assertIn("          where: " + self.path("app.php") + ":2", out)
        self.assertIn("        why:   ", out)
        self.assertIn("        fix:   ", out)
        self.assertIn("2 findings: 1 critical, 1 medium.", out)
        self.assertIn("Files checked: 1", out)
        self.assertIn("not a full scanner", out)
        self.assertIn("run semgrep if it is installed", out)

    def test_clean_file(self):
        code, out, _ = run_main(self.path("clean.py"))
        self.assertEqual(code, 0)
        self.assertIn("No findings.", out)
        self.assertIn("semgrep", out)

    def test_one_finding_is_singular(self):
        _, out, _ = run_main(self.path("only_high.js"))
        self.assertIn("1 finding: 1 high.", out)

    def test_json_output_shape(self):
        code, out, _ = run_main(self.root, "--json")
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual([f["severity"] for f in data["findings"]], ["critical", "high", "medium", "medium"])
        for finding in data["findings"]:
            for key in ("severity", "title", "where", "why", "fix", "rule", "file", "line"):
                self.assertIn(key, finding)
        summary = data["summary"]
        self.assertEqual((summary["total"], summary["critical"], summary["high"], summary["medium"], summary["low"]),
                         (4, 1, 1, 2, 0))
        self.assertEqual(summary["files_checked"], 4)
        self.assertIn("semgrep", data["note"])

    def test_fail_on(self):
        self.assertEqual(run_main(self.path("only_medium.py"))[0], 0)
        self.assertEqual(run_main(self.path("only_medium.py"), "--fail-on", "medium")[0], 1)
        self.assertEqual(run_main(self.path("only_medium.py"), "--fail-on", "low")[0], 1)
        self.assertEqual(run_main(self.path("only_high.js"))[0], 1)
        self.assertEqual(run_main(self.path("only_high.js"), "--fail-on", "critical")[0], 0)
        self.assertEqual(run_main(self.path("app.php"), "--fail-on", "critical")[0], 1)
        self.assertEqual(run_main(self.path("clean.py"), "--fail-on", "low")[0], 0)

    def test_missing_path_is_exit_2(self):
        code, out, err = run_main(self.path("nope"))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("does not exist", err)

    def test_device_is_exit_2(self):
        self.assertEqual(run_main(os.devnull)[0], 2)  # /dev/null, or nul on Windows

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs named pipes")
    def test_named_pipe_is_exit_2_and_does_not_hang(self):
        fifo = self.path("pipe.py")
        os.mkfifo(fifo)
        self.assertEqual(run_main(fifo)[0], 2)

    def test_unreadable_file_is_exit_2(self):
        with mock.patch.object(codecheck, "open", side_effect=PermissionError(13, "Permission denied"), create=True):
            code, out, _ = run_main(self.path("clean.py"))
        self.assertEqual(code, 2)
        self.assertIn("INCOMPLETE, so not a pass. Could not read: %s (Permission denied)" % self.path("clean.py"), out)
        self.assertNotIn("No findings", out)

    def test_named_file_that_cannot_be_checked_is_exit_2(self):
        make_tree(self.root, {"readme.txt": "eval(x)\n", "big.py": "x = 1\n" * 200000 + "eval(x)\n",
                              "image.js": b"\0\0eval(x)\n"})
        for name in ("readme.txt", "big.py", "image.js"):
            with self.subTest(name=name):
                code, out, err = run_main(self.path(name))
                self.assertEqual((code, out), (2, ""))
                self.assertIn("error: ", err)
        self.assertIn("not a PHP, Python or JS/TS file", run_main(self.path("readme.txt"))[2])
        self.assertIn("over 1 MB", run_main(self.path("big.py"))[2])

    def test_folder_with_nothing_to_check_says_so(self):
        make_tree(self.root, {"go/main.go": "package main\n", "go/index.html": "<script>eval(x)</script>\n"})
        code, out, _ = run_main(self.path("go"))
        self.assertEqual(code, 0)
        self.assertIn("Nothing was checked", out)
        self.assertNotIn("No findings", out)
        self.assertIn("Files checked: 0", out)

    def test_bad_arguments_are_exit_2(self):
        self.assertEqual(run_main(self.root, "--fail-on", "urgent")[0], 2)
        self.assertEqual(run_main()[0], 2)

    def test_output_into_a_closed_pipe_ends_quietly(self):
        # Regression (dogfood): `codecheck.py . | head` printed a BrokenPipeError traceback.
        with open(self.path("many.py"), "w") as handle:
            handle.write("x = eval(y)\n" * 5000)
        done = subprocess.Popen([sys.executable, SCRIPT, self.root], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        done.stdout.close()  # the reader is gone before anything is printed
        error = done.stderr.read().decode()
        done.stderr.close()
        self.assertEqual(done.wait(timeout=60), 1)
        self.assertNotIn("Traceback", error)

    def test_runs_as_a_script(self):
        result = run_script(self.path("only_high.js"), "--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["summary"]["high"], 1)


class ConventionTests(unittest.TestCase):
    def setUp(self):
        with open(SCRIPT, encoding="utf-8") as handle:
            self.source = handle.read()

    def test_docstring_and_length(self):
        for words in ("Usage", "Exit codes", "forge:allow", "semgrep if it is installed", "first pass"):
            self.assertIn(words, codecheck.__doc__)
        self.assertLessEqual(len(self.source.splitlines()), 300)  # the spec's hard limit
        self.assertTrue(self.source.startswith("#!/usr/bin/env python3\n"))
        imports = sorted(line for line in self.source.splitlines() if line.startswith(("import ", "from ")))
        self.assertEqual(imports, ["import argparse", "import errno", "import json", "import os", "import re",
                                   "import sys"])

    def test_runs_on_python_3_9(self):
        ast.parse(self.source, feature_version=(3, 9))

    def test_every_function_has_a_docstring(self):
        for node in ast.walk(ast.parse(self.source)):
            if isinstance(node, ast.FunctionDef):
                self.assertTrue(ast.get_docstring(node), node.name)


class ConsoleTests(unittest.TestCase):
    def test_a_cp1252_pipe_gets_escapes_not_a_crash(self):
        """Windows pipes are cp1252 (no arrow): the arrow prints as \\u2192, no crash."""
        with tempfile.TemporaryDirectory() as root:
            make_tree(root, {"caf\u00e9 \u2192.py": "eval(x)\n"})
            code, out, err = run_cp1252(SCRIPT, root)
        self.assertEqual(code, 1, err)
        self.assertIn("where: caf\u00e9 \\u2192.py:1", out)


if __name__ == "__main__":
    unittest.main()
