"""Tests for forge-check/testdb.py: which database an app's own tests reach, per stack (Laravel's phpunit.xml with
and without force="true", <server>, .env.testing, the shell and a container; Django's test database; a node app's
.env.test and test set-up files), the exit codes, the JSON shape, and that no password is ever printed."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252, symlink  # noqa: E402

testdb = load("forge-check", "testdb")
SCRIPT = os.path.join(ROOT, "forge-check", "testdb.py")
SECRET = "s3cr" + "et-pw-" + "77x"  # built from pieces: the pack's own secret scan must not see a password here
PHPUNIT = '<?xml version="1.0" encoding="UTF-8"?>\n<phpunit>\n  <php>\n    <env name="APP_ENV" value="testing"/>\n%s' \
          '  </php>\n</phpunit>\n'
LARAVEL_10 = PHPUNIT % '    <!-- <env name="DB_CONNECTION" value="sqlite"/> -->\n' \
                       '    <!-- <env name="DB_DATABASE" value=":memory:"/> -->\n'
CLEAN = {key: "" for key in ("DB_CONNECTION", "DB_DATABASE", "DB_URL", "DATABASE_URL", "APP_ENV", "APP_CONFIG_CACHE")}
MEMORY = PHPUNIT % '    <env name="DB_CONNECTION" value="sqlite"/>\n    <env name="DB_DATABASE" value=":memory:"/>\n'


class Project(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        shell = mock.patch.dict(os.environ)  # the shell's DB_ variables count: none, unless a test sets them
        shell.start()
        self.addCleanup(shell.stop)
        for key in [key for key in os.environ if key in CLEAN or "TEST" in key.upper() and testdb.DB_NAME.match(key)]:
            os.environ.pop(key, None)

    def write(self, name, text=""):
        path = os.path.join(self.root, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return path

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = testdb.main([self.root] + list(args))
        return code, out.getvalue(), err.getvalue()

    def verdict(self):
        """(exit code, the verdict of each stack, the plain output)."""
        code, out, err = self.run_main("--json")
        self.assertEqual(err, "")
        data = json.loads(out)
        self.assertEqual(data["safe"], code == 0)
        plain = self.run_main()
        self.assertEqual(plain[0], code)
        self.assertNotIn(SECRET, plain[1] + out)
        return code, [item["verdict"] for item in data["stacks"]], plain[1]

    def laravel(self, phpunit, env="DB_CONNECTION=mysql\nDB_DATABASE=app\nDB_PASSWORD=%s\n" % SECRET):
        self.write("artisan", "#!/usr/bin/env php\n")
        self.write(".env", env)
        if phpunit is not None:
            self.write("phpunit.xml", phpunit)
        self.write("tests/Feature/BookingTest.php", "<?php\nclass BookingTest extends TestCase\n{\n"
                                                    "    use RefreshDatabase;\n}\n")


class LaravelTests(Project):
    def test_the_skeletons_commented_lines_reach_the_database_the_app_uses(self):
        """Laravel 10 and older ship phpunit.xml with the database lines commented out: RefreshDatabase then runs
        migrate:fresh on the database in .env."""
        self.laravel(LARAVEL_10)
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["same"]))
        self.assertIn('SAME DATABASE: the tests use mysql database "app"', out)
        self.assertIn("can delete every record in it. Do not run them. Ask the user, naming it", out)
        self.assertIn('<env name="DB_DATABASE" value="<name>_test" force="true"/>', out, "how to give them their own")
        self.assertIn("1 file(s) reset or empty the database: tests/Feature/BookingTest.php", out)

    def test_an_sqlite_database_in_memory_is_their_own(self):
        self.laravel(PHPUNIT % '    <env name="DB_CONNECTION" value="sqlite"/>\n'
                               '    <env name="DB_DATABASE" value=":memory:"/>\n')
        self.assertEqual(self.verdict()[:2], (0, ["own"]))

    def test_a_shell_variable_wins_over_an_env_line_without_force(self):
        self.laravel(PHPUNIT % '    <env name="DB_DATABASE" value="testing"/>\n')
        self.assertEqual(self.verdict()[:2], (0, ["own"]), "no DB_ in the shell: phpunit.xml's value")
        os.environ["DB_DATABASE"] = "app"
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["same"]))
        self.write("phpunit.xml", PHPUNIT % '    <env name="DB_DATABASE" value="testing" force="true"/>\n')
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (0, ["own"]))
        self.assertIn('with force="true"', out)
        self.write("phpunit.xml", PHPUNIT % '    <server name="DB_DATABASE" value="testing"/>\n')
        self.assertEqual(self.verdict()[:2], (0, ["own"]), "<server> is set whatever the shell holds")

    def test_env_testing_is_read_when_phpunit_sets_app_env_to_testing(self):
        self.laravel(LARAVEL_10)
        self.write(".env.testing", "DB_CONNECTION=mysql\nDB_DATABASE=app_testing\n")
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (0, ["own"]))
        self.assertIn("the rest comes from .env.testing", out)
        self.write("phpunit.xml", LARAVEL_10.replace('<env name="APP_ENV" value="testing"/>', ""))
        self.assertEqual(self.verdict()[:2], (1, ["same"]), "no APP_ENV testing: .env.testing is not read")

    def test_a_container_wins_over_phpunit_without_force(self):
        self.laravel(PHPUNIT % '    <env name="DB_DATABASE" value="testing"/>\n')
        self.write("docker-compose.yml", "services:\n  app:\n    env_file: .env\n")
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["unsure"]))
        self.assertIn("docker compose exec", out)
        self.assertIn("naming it: the tests can delete every record in it. Their go, or a test database of its own "
                      '(in phpunit.xml <env name="DB_DATABASE" value="<name>_test" force="true"/>', out,
                      "a NOT SURE line says how the tests get their own, as a SAME one does")
        self.write("phpunit.xml", PHPUNIT % '    <env name="DB_DATABASE" value="testing" force="true"/>\n')
        self.assertEqual(self.verdict()[:2], (0, ["own"]))

    def test_a_container_that_gets_the_apps_variables_wins_over_sqlite_in_memory(self):
        """Laravel 11's phpunit.xml, without force, in a container that compose gives the .env (forge's own template
        does): the container's DB_ variables win, so RefreshDatabase empties the app's database."""
        self.laravel(MEMORY, env="DB_CONNECTION=mysql\nDB_HOST=mysql\nDB_DATABASE=shop\n")
        self.write("compose.yaml", "services:\n  app:\n    build: .\n    env_file: .env\n  mysql:\n    image: mysql:8\n")
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["unsure"]))
        self.assertIn('there the tests use mysql database "shop"; on this machine sqlite database ":memory:"', out)
        self.write("phpunit.xml", MEMORY.replace('"/>', '" force="true"/>'))
        self.assertEqual(self.verdict()[:2], (0, ["own"]), "forced lines win in a container too")

    def test_a_container_without_the_apps_variables_keeps_the_lines_of_phpunit(self):
        """Sail mounts the folder and gives the container no DB_ variable, so phpunit.xml's lines win there too."""
        self.laravel(PHPUNIT % '    <env name="DB_DATABASE" value="testing"/>\n')
        self.write("docker-compose.yml", "services:\n  laravel.test:\n    environment:\n      LARAVEL_SAIL: 1\n"
                                         "    volumes:\n      - '.:/var/www/html'\n")
        self.assertEqual(self.verdict()[:2], (0, ["own"]))
        self.write("docker-compose.yml", "services:\n  app:\n    environment:\n      - DB_HOST=db\n"
                                         "      - DB_DATABASE=${DB_DATABASE:-shop}\n")
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["unsure"]), "the app's own database, through ${DB_DATABASE} of .env")
        self.assertIn('there the tests use mysql database "app"', out)
        self.write("docker-compose.yml", "services:\n  app:\n    environment:\n      DB_DATABASE: ${SOMEWHERE}\n")
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["unsure"]), "a value compose fills in from elsewhere: not sure")
        self.assertIn("some come from ${SOMEWHERE}, which this script cannot see", out)
        self.write("docker-compose.yml", "services:\n  app:\n    env_file:\n      - path: /etc/app.env\n      - ../x.env\n")
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["unsure"]), "a file outside the project is never read: not sure")
        self.assertIn("some come from ../x.env, which this script cannot see", out)
        self.write("phpunit.xml", PHPUNIT % "".join('    <env name="%s" value="%s" force="true"/>\n' % pair for pair in (
            ("DB_CONNECTION", "sqlite"), ("DB_DATABASE", ":memory:"), ("DB_URL", ""), ("DATABASE_URL", ""))))
        self.assertEqual(self.verdict()[:2], (0, ["own"]), "what that file sets cannot win over forced lines")

    def test_a_container_with_database_lines_of_its_own_is_compared_with_the_app_there(self):
        """The app's container gets DB_CONNECTION and DB_DATABASE from compose's environment, other values than the
        .env on this machine (Laravel 11's sqlite) or no .env at all: in the container the app and the tests both
        use mysql "shop", so RefreshDatabase empties it."""
        compose = ("services:\n  app:\n    build: .\n    volumes:\n      - .:/var/www/html\n    environment:\n"
                   "      DB_CONNECTION: mysql\n      DB_HOST: db\n      DB_DATABASE: shop\n  db:\n    image: mysql:8\n"
                   "    environment:\n      MYSQL_DATABASE: shop\n")
        self.laravel(MEMORY, env="APP_ENV=local\nDB_CONNECTION=sqlite\n")
        self.write("compose.yaml", compose)
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["unsure"]))
        self.assertIn('NOT SURE which database the tests reach (the app uses mysql database "shop")', out)
        self.assertIn('there the tests use mysql database "shop"; on this machine sqlite database ":memory:"', out)
        os.remove(os.path.join(self.root, ".env"))
        self.assertEqual(self.verdict()[:2], (1, ["unsure"]), "no .env: the container's lines still win")
        self.write(".env", "DB_CONNECTION=mysql\nDB_DATABASE=shop\n")
        self.write("phpunit.xml", PHPUNIT % '    <env name="DB_DATABASE" value="testing"/>\n')
        self.write("compose.yaml", "services:\n  app:\n    environment:\n      DB_CONNECTION: pgsql\n")
        self.assertEqual(self.verdict()[:2], (0, ["own"]), "there the app uses pgsql shop, the tests pgsql testing")

    def test_a_cached_config_wins_over_phpunit_and_env(self):
        """After `php artisan config:cache` (or optimize) the tests use the database in the cache, whatever
        phpunit.xml forces."""
        forced = '    <env name="DB_DATABASE" value="app_test" force="true"/>\n'
        self.laravel(PHPUNIT % forced)
        self.assertEqual(self.verdict()[:2], (0, ["own"]))
        self.write("bootstrap/cache/config.php", "<?php return ['database' => ['default' => 'mysql']];\n")
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["unsure"]))
        self.assertIn("`php artisan config:clear` first, with the user's go", out)
        self.write("phpunit.xml", PHPUNIT % ('    <env name="APP_CONFIG_CACHE" value="bootstrap/cache/tests.php"/>\n'
                                             + forced))
        self.assertEqual(self.verdict()[:2], (0, ["own"]), "a cache file of the tests' own, which is not there")

    def test_a_url_names_the_driver_and_the_database(self):
        """Laravel 11 puts 'url' => env('DB_URL') in every connection, and the URL's driver and database win over
        DB_CONNECTION and DB_DATABASE, also over sqlite in memory or a forced test database."""
        self.laravel(MEMORY, env="DB_URL=mysql://root@127.0.0.1:3306/myshop\n")
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["same"]))
        self.assertIn('mysql database "myshop"', out)
        self.assertIn('plus <env name="DB_URL" value="" force="true"/> when .env sets DB_URL', out, "the advice works")
        self.write("phpunit.xml", PHPUNIT % '    <env name="DB_DATABASE" value="myshop_test" force="true"/>\n')
        self.assertEqual(self.verdict()[:2], (1, ["same"]))
        self.write("phpunit.xml", PHPUNIT % ('    <env name="DB_URL" value="" force="true"/>\n'
                                             '    <env name="DB_DATABASE" value="myshop_test" force="true"/>\n'))
        self.assertEqual(self.verdict()[:2], (0, ["own"]), "an empty DB_URL: the connection's own settings")
        self.write(".env", "DB_CONNECTION=mariadb\nDB_DATABASE=shop\n")
        self.write("phpunit.xml", PHPUNIT % '    <env name="DB_CONNECTION" value="mysql"/>\n')
        self.assertEqual(self.verdict()[:2], (1, ["same"]), "mariadb and mysql: one server, two names")

    def test_a_url_is_compared_by_its_database_and_shown_without_its_password(self):
        self.laravel(LARAVEL_10, env="DB_URL=mysql://app:%s@127.0.0.1:3306/app\n" % SECRET)
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["same"]))
        self.assertIn('mysql database "app"', out)
        self.write("phpunit.xml", PHPUNIT % '    <env name="DB_URL" value="mysql://app:%s@127.0.0.1:3306/app_test" '
                                           'force="true"/>\n' % SECRET)
        self.assertEqual(self.verdict()[:2], (0, ["own"]))

    def test_no_phpunit_xml_a_broken_one_or_a_linked_one_cannot_be_read(self):
        self.laravel(None)
        self.assertEqual(self.verdict()[:2], (1, ["unsure"]))
        self.write("phpunit.xml", "<phpunit><php><env name=")
        self.assertEqual(self.verdict()[:2], (1, ["unsure"]))
        os.remove(os.path.join(self.root, "phpunit.xml"))
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        with open(os.path.join(outside, "phpunit.xml"), "w", encoding="utf-8") as handle:
            handle.write(PHPUNIT % '    <env name="DB_DATABASE" value=":memory:"/>\n')
        symlink(self, os.path.join(outside, "phpunit.xml"), os.path.join(self.root, "phpunit.xml"))
        self.assertEqual(self.verdict()[:2], (1, ["unsure"]), "a link is never read")


class DjangoTests(Project):
    SETTINGS = 'DATABASES = {\n    "default": {\n        "ENGINE": "django.db.backends.postgresql",\n' \
               '        "NAME": "shop",\n%s    }\n}\n'

    def test_django_makes_a_test_database_of_its_own(self):
        self.write("manage.py", "")
        self.write("shop/settings.py", self.SETTINGS % "")
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (0, ["own"]))
        self.assertIn("test_<NAME>", out)

    def test_a_test_name_that_is_the_name_is_the_same_database(self):
        self.write("manage.py", "")
        self.write("shop/settings.py", self.SETTINGS % '        "TEST": {"NAME": "shop"},\n')
        self.assertEqual(self.verdict()[:2], (1, ["same"]))
        self.write("shop/settings.py", self.SETTINGS % '        "TEST": {"NAME": "shop_test"},\n')
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (0, ["own"]))
        self.assertIn('sets TEST NAME "shop_test"', out)


class NodeTests(Project):
    def node(self, deps):
        self.write("package.json", json.dumps({"scripts": {"test": "vitest run"}, "dependencies": deps,
                                               "devDependencies": {"vitest": "3.2.4"}}))
        self.write(".env", 'DATABASE_URL="postgresql://app:%s@localhost:5432/app?schema=public"\n' % SECRET)

    def test_no_database_package_has_no_database_to_empty(self):
        self.node({"react": "19.0.0"})
        self.assertEqual(self.verdict()[:2], (0, ["none"]))

    def test_a_database_and_no_test_settings_is_not_sure(self):
        self.node({"@prisma/client": "6.0.0"})
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["unsure"]))
        self.assertIn("the app uses @prisma/client", out)

    def test_env_test_with_a_database_of_its_own(self):
        self.node({"@prisma/client": "6.0.0"})
        self.write(".env.test", "DATABASE_URL=postgresql://app:%s@localhost:5432/app_test\n" % SECRET)
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (0, ["own"]))
        self.assertIn('DATABASE_URL="postgresql://localhost:5432/app_test"', out)
        self.write(".env.test", 'DATABASE_URL="postgresql://app:%s@localhost:5432/app?schema=public"\n' % SECRET)
        self.write("tests/global.ts", 'import { execSync } from "node:child_process";\n'
                                      'execSync("npx prisma migrate reset --force");\n')
        self.write("vitest.config.ts", "export default { test: { globalSetup: './tests/global.ts' } }\n")
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["same"]))
        self.assertIn("reset or empty the database: tests/global.ts", out)

    def test_a_set_up_file_with_a_database_in_memory(self):
        """As AnglerHub does: tests/setup.ts sets the app's own database variable to :memory: first."""
        self.node({"better-sqlite3": "12.0.0"})
        self.write(".env.local", "DATABASE_PATH=data/app.sqlite\n")
        self.write("vitest.config.mts", 'export default defineConfig({ test: { setupFiles: ["tests/setup.ts"] } });\n')
        self.write("tests/setup.ts", 'process.env.DATABASE_PATH = ":memory:";\nprocess.env.SESSION_SECRET = "%s";\n'
                   % SECRET)
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (0, ["own"]))
        self.assertIn('tests/setup.ts sets DATABASE_PATH to ":memory:"', out)

    def test_the_env_block_of_the_vitest_config_and_a_name_the_app_does_not_set(self):
        self.node({"pg": "8.0.0"})
        self.write("vitest.config.ts", "export default { test: { env: { POSTGRES_URL: 'postgres://localhost/app_test' "
                                       "} } }\n")
        self.assertEqual(self.verdict()[:2], (0, ["own"]), "a database named for the tests")
        self.write("vitest.config.ts", "export default { test: { env: { POSTGRES_URL: 'postgres://localhost/app' } } }\n")
        self.assertEqual(self.verdict()[:2], (1, ["unsure"]), "a name the app's .env files do not set")

    def test_a_variable_named_for_the_tests(self):
        """A forge-built next app: its tests read TEST_DATABASE_URL, a database whose name ends in _test."""
        self.node({"drizzle-orm": "0.44.0", "postgres": "3.4.0"})
        self.write("tests/setup.ts", "const url = process.env.TEST_DATABASE_URL;\n"
                                     "if (!/_test$/.test(url ?? '')) throw new Error('not a test database');\n")
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["unsure"]))
        self.assertIn("the test set-up reads TEST_DATABASE_URL, which is not set here", out)
        os.environ["TEST_DATABASE_URL"] = "postgres://app:%s@127.0.0.1:5433/app_test" % SECRET
        self.assertEqual(self.verdict()[:2], (0, ["own"]), "set in this shell")
        del os.environ["TEST_DATABASE_URL"]
        self.write(".env.local", "TEST_DATABASE_URL=postgresql://tester:%s@localhost:5432/app\n" % SECRET[::-1])
        self.assertEqual(self.verdict()[:2], (1, ["same"]), "the database of DATABASE_URL, another user and no query")
        self.write(".env.local", "TEST_DATABASE_URL=postgresql://localhost:5432/shop_test\n")
        self.assertEqual(self.verdict()[:2], (0, ["own"]))

    def test_a_test_that_empties_a_database_is_not_safe_without_a_database_package(self):
        """A database the package list does not show: node:sqlite, or a client this script does not know."""
        self.write("package.json", json.dumps({"scripts": {"test": "node --test"}}))
        self.write(".env", "DB_FILE=./data/app.db\n")
        self.write("tests/users.test.js", "import { DatabaseSync } from 'node:sqlite';\n"
                                          "new DatabaseSync(process.env.DB_FILE).exec('DELETE FROM users');\n")
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["unsure"]))
        self.assertIn("the app uses node:sqlite", out)
        self.assertIn('(the app uses DB_FILE="./data/app.db")', out, "the line names what the tests can empty")
        self.write("tests/users.test.js", "import { db } from './db.js';\nbeforeEach(() => db.query('truncate table x'));\n")
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["unsure"]), "no known package, but a test empties a database")
        self.assertIn("1 file(s) reset or empty the database: tests/users.test.js", out)
        self.write("tests/users.test.js", "test('adds', () => expect(1 + 1).toBe(2));\n")
        self.assertEqual(self.verdict()[:2], (0, ["none"]))

    def test_the_word_truncate_in_a_ui_test_is_no_reset(self):
        """lodash's truncate, Tailwind's class "truncate" and a test named for the cart: no database is emptied."""
        self.write("package.json", json.dumps({"scripts": {"test": "vitest run"}, "dependencies": {"lodash": "4"},
                                               "devDependencies": {"vitest": "3"}}))
        self.write("src/title.test.tsx", "import { truncate } from 'lodash';\n"
                                         "it('cuts', () => expect(truncate('abcdef', { length: 4 })).toBe('a...'));\n"
                                         "it('cuts too', () => expect(_.truncate(title, { length: 4 })).toBeTruthy());\n"
                                         "it('keeps one line', () => render(<p className=\"truncate\">x</p>));\n"
                                         "it('removes an item: delete from the cart', () => {});\n"
                                         "it('drag and drop table rows', () => {});\n")
        self.assertEqual(self.verdict()[:2], (0, ["none"]))
        for sql in ("TRUNCATE orders", "truncate table orders", "delete from orders where id > 0",
                    'drop table if exists "orders"', "DELETE FROM orders", "await User.truncate({ cascade: true })"):
            with self.subTest(sql=sql):
                self.write("src/db.test.ts", "beforeEach(() => run(`%s`));\n" % sql)
                self.assertEqual(self.verdict()[:2], (1, ["unsure"]))

    def test_the_common_clients_count_as_a_database(self):
        for name in ("@supabase/supabase-js", "firebase-admin", "ioredis", "redis", "mssql", "@mikro-orm/core"):
            with self.subTest(package=name):
                self.node({name: "1.0.0"})
                self.assertEqual(self.verdict()[:2], (1, ["unsure"]))

    def test_a_test_variable_counts_only_when_a_test_reads_it(self):
        """TEST_DATABASE_URL in .env that no test reads, while the tests load dotenv and use Prisma's DATABASE_URL."""
        self.node({"@prisma/client": "6.0.0"})
        self.write(".env", "DATABASE_URL=postgresql://localhost:5432/shop\n"
                           "TEST_DATABASE_URL=postgresql://localhost:5432/shop_test\n")
        self.write("tests/orders.test.ts", "import 'dotenv/config';\nbeforeEach(() => prisma.order.deleteMany());\n")
        self.assertEqual(self.verdict()[:2], (1, ["unsure"]))
        self.write("tests/orders.test.ts", "const url = process.env.TEST_DATABASE_URL;\n")
        self.assertEqual(self.verdict()[:2], (0, ["own"]), "read by a test file")

    def test_each_workspace_and_each_project_one_folder_down_is_read(self):
        """A monorepo root runs the tests of every workspace (turbo run test): each one is read on its own."""
        self.write("package.json", json.dumps({"private": True, "workspaces": ["apps/*"],
                                               "scripts": {"test": "turbo run test"}, "devDependencies": {"turbo": "2"}}))
        self.write("apps/web/package.json", json.dumps({"scripts": {"test": "vitest run"},
                                                        "dependencies": {"@prisma/client": "6.0.0"}}))
        self.write("apps/web/.env", "DATABASE_URL=postgresql://localhost:5432/shop\n")
        self.write("apps/web/tests/a.test.ts", "beforeEach(() => prisma.order.deleteMany());\n")
        self.write("apps/docs/package.json", json.dumps({"scripts": {"test": "vitest run"}}))
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["none", "unsure"]))
        self.assertIn("node in apps/web: NOT SURE", out)
        self.assertIn("reset or empty the database: tests/a.test.ts", out)
        self.assertNotIn("apps/docs", out, "a workspace with no database adds no line")
        os.remove(os.path.join(self.root, "package.json"))
        self.write("pnpm-workspace.yaml", "packages:\n  - 'apps/*'\n")
        self.assertEqual(self.verdict()[:2], (1, ["unsure"]), "pnpm's list, with no package.json at the top")
        shutil.rmtree(os.path.join(self.root, "apps"))
        os.remove(os.path.join(self.root, "pnpm-workspace.yaml"))
        self.write("backend/package.json", json.dumps({"scripts": {"test": "jest"}, "dependencies": {"pg": "8.0.0"}}))
        self.assertEqual(self.verdict()[:2], (1, ["unsure"]), "a project one folder down, with no list at all")
        shutil.rmtree(os.path.join(self.root, "backend"))
        # turborepo's with-prisma: the app's tests empty the database through another workspace, which lists prisma
        self.write("package.json", json.dumps({"private": True, "workspaces": ["apps/*", "packages/*"],
                                               "scripts": {"test": "turbo run test"}}))
        self.write("apps/web/package.json", json.dumps({"scripts": {"test": "vitest run"},
                                                        "dependencies": {"@acme/api": "workspace:*"}}))
        self.write("apps/web/tests/orders.test.ts", "import { resetDb } from '@acme/api';\nbeforeEach(() => resetDb());\n")
        self.write("packages/api/package.json", json.dumps({"name": "@acme/api", "dependencies": {"@acme/db": "*"}}))
        self.write("packages/db/package.json", json.dumps({"name": "@acme/db", "dependencies": {"@prisma/client": "6"}}))
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["none", "unsure"]), "a workspace that uses one that uses prisma")
        self.assertIn("node in apps/web: NOT SURE", out)
        self.assertIn("the app uses @acme/api", out)
        self.write("packages/db/package.json", json.dumps({"name": "@acme/db", "dependencies": {"zod": "3"}}))
        self.assertEqual(self.verdict()[:2], (0, ["none"]), "workspaces with no database package")

    def test_a_password_in_a_key_value_setting_is_never_shown(self):
        """libpq's keyword form and Prisma's SQL Server URL keep the user and the password in key=value parts."""
        self.node({"pg": "8.0.0"})
        self.write(".env", 'DATABASE_URL="host=localhost user=app password=%s dbname=shop"\n' % SECRET)
        self.write(".env.test", 'DATABASE_URL="host=localhost user=app password=%s dbname=shop_test"\n' % SECRET)
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (0, ["own"]))
        self.assertIn('"host=localhost dbname=shop_test"', out)
        server = 'DATABASE_URL="sqlserver://localhost:1433;database=shop;user=sa;password=%s;encrypt=true"\n'
        self.write(".env", server % SECRET)
        self.write(".env.test", server % SECRET[::-1])
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["same"]), "the same database, whatever the password")
        self.assertNotIn(SECRET[::-1], out)
        self.assertIn('"sqlserver://localhost:1433;database=shop;encrypt=true"', out)
        for value, kept in (("host=localhost user=app password='%s x' dbname=shop" % SECRET, "host=localhost dbname=shop"),
                            ("host=db password='it\\'s %s' dbname=shop" % SECRET, "host=db dbname=shop"),
                            ("Server=tcp:db,1433;Database=shop;User Id=sa;Password={a;%s x}};y};" % SECRET,
                             "Server=tcp:db,1433;Database=shop;"),
                            ('Server=db;Database=shop;Password="a;%s ""x""";' % SECRET, "Server=db;Database=shop;")):
            with self.subTest(value=value):
                self.assertEqual(json.loads(testdb.shown(value)), kept, "libpq quotes, SQL Server braces or quotes")

    def test_a_password_variable_is_never_read(self):
        self.node({"pg": "8.0.0"})
        self.write(".env.test", "DB_PASSWORD=%s\nDATABASE_AUTH_TOKEN=%s\n" % (SECRET, SECRET))
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (1, ["unsure"]), "no database variable set: a password does not count")


class OtherTests(Project):
    def test_no_test_set_up_is_safe_and_another_stack_is_not_sure(self):
        code, out, err = self.run_main()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("No test set-up found", out)
        self.write("Gemfile", "source 'https://rubygems.org'\n")
        self.assertEqual(self.verdict()[:2], (1, ["unsure"]))

    def test_two_stacks_each_get_a_line(self):
        self.laravel(PHPUNIT % '    <env name="DB_DATABASE" value=":memory:"/>\n')
        self.write("package.json", json.dumps({"scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "3"}}))
        code, kinds, out = self.verdict()
        self.assertEqual((code, kinds), (0, ["own", "none"]))
        self.assertEqual([line.split(":")[0] for line in out.splitlines()], ["laravel", "node"])

    def test_a_path_that_is_no_folder_is_exit_2(self):
        self.write("file.txt", "x")
        for name in ("nope", "file.txt"):
            with self.subTest(path=name), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(testdb.main([os.path.join(self.root, name)]), 2)
                self.assertIn("is not a folder", err.getvalue())

    def test_json_shape(self):
        self.laravel(LARAVEL_10)
        data = json.loads(self.run_main("--json")[1])
        self.assertEqual(sorted(data), ["safe", "stacks"])
        self.assertEqual(sorted(data["stacks"][0]), ["app", "resets", "stack", "tests", "verdict", "where"])

    def test_help_and_a_windows_pipe(self):
        done = subprocess.run([sys.executable, SCRIPT, "--help"], timeout=60, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0)
        self.assertIn("Exit codes:", done.stdout)
        self.laravel(LARAVEL_10, env="DB_CONNECTION=mysql\nDB_DATABASE=café→\n")
        code, out, err = run_cp1252(SCRIPT, self.root)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("SAME DATABASE", out)


if __name__ == "__main__":
    unittest.main()
