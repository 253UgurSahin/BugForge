"""Tests for forge-build/composecheck.py.

Fake secrets are glued together at runtime, so this file never contains a
secret-looking literal: the repo itself is scanned with secretscan.py in CI.
"""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, run_cp1252, symlink  # noqa: E402

mod = load("forge-build", "composecheck")

FAKE = "hunter" + "22-" + "Xy9"  # a password-looking value
GOOD_COMPOSE = ("services:\n  app:\n    build: .\n    env_file: .env\n    healthcheck:\n"
                "      test: [\"CMD\", \"true\"]\n    restart: unless-stopped\n")


def run(*args):
    """Run main() and return (exit code, stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = mod.main(list(args))
    return code, out.getvalue()


def rules(findings):
    return sorted(f["rule"] for f in findings)


def check(text):
    """(findings, has a healthcheck, build targets) of compose TEXT."""
    return mod.check_compose(text, "docker-compose.yml")


def service(body, name="app"):
    """A compose file with one service that has a restart policy, plus BODY."""
    return "services:\n  %s:\n    restart: unless-stopped\n%s" % (name, body)


class ParserTests(unittest.TestCase):
    def test_reads_services_and_the_keys_each_line_is_under(self):
        text = ("version: '3'\nservices:\n  web:\n    image: nginx:1.30\n    ports:\n      - \"8080:80\"\n"
                "    build:\n      context: .\n      args:\n        A: b\n"
                "  db:  # the database\n    image: postgres:18\nvolumes:\n  data:\n")
        services = mod.compose_services(text)
        self.assertEqual(list(services), ["web", "db"])
        self.assertEqual(services["web"][1:], [
            (4, (), "image: nginx:1.30"), (5, (), "ports:"), (6, ("ports",), "- \"8080:80\""), (7, (), "build:"),
            (8, ("build",), "context: ."), (9, ("build",), "args:"), (10, ("build", "args"), "A: b")])
        self.assertEqual(services["db"][0], (11, (), "db:"))

    def test_list_items_with_keys(self):
        text = service("    ports:\n      - published: 9000\n        target: 9000\n    build:\n      target: app\n")
        lines = mod.compose_services(text)["app"]
        self.assertEqual([keys for _, keys, _ in lines[2:]], [(), ("ports",), ("ports",), (), ("build",)])

    def test_flow_items(self):
        self.assertEqual(mod.flow_items(' ["a", b, ]'), ['"a"', "b"])
        self.assertEqual(mod.flow_items("{A: b, 'C': d}"), ["A: b", "'C': d"])
        self.assertEqual(mod.flow_items("[]"), [])

    def test_a_file_without_a_services_block_cannot_be_checked(self):
        for text in ('{"services": {"db": {"image": "postgres:18", "privileged": true}}}', "services: {}\n",
                     "volumes:\n  data:\n", "", "services:\n  db: {image: postgres, privileged: true}\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                check(text)


class RuleTests(unittest.TestCase):
    def test_privileged_host_network_and_docker_socket(self):
        findings = check(service("    privileged: true\n    network_mode: host\n    volumes:\n"
                                 "      - /var/run/docker.sock:/var/run/docker.sock\n"))[0]
        self.assertEqual(rules(findings), ["host_net", "privileged", "sock"])
        self.assertEqual([f["severity"] for f in findings if f["rule"] != "host_net"], ["critical", "critical"])
        self.assertEqual(check(service("    # privileged: true\n    privileged: false\n"))[0], [])

    def test_every_way_to_write_true(self):
        for value in ("true", "True", "yes", "on", "ON", "y", "'true'", '"yes"'):  # docker compose reads all as true
            with self.subTest(value=value):
                self.assertEqual(rules(check(service("    privileged: %s\n" % value))[0]), ["privileged"])
        for value in ("false", "no", "off", "n"):
            with self.subTest(value=value):
                self.assertEqual(check(service("    privileged: %s\n" % value))[0], [])

    def test_service_user_root(self):
        for user in ("root", '"0"', "0:0", "'root:root'"):
            with self.subTest(user=user):
                self.assertEqual(rules(check(service("    user: %s\n" % user))[0]), ["root"])
        for user in ('"1000"', "node", "rootless", '"${UID}:${GID}"'):
            with self.subTest(user=user):
                self.assertEqual(check(service("    user: %s\n" % user))[0], [])

    def test_database_ports(self):
        for ports in ('      - "5432:5432"\n', "      - 5432\n", '      - "0.0.0.0:5432:5432"\n',
                      "      - target: 5432\n        published: 5432\n", "    - 5432:5432\n"):
            with self.subTest(ports=ports):
                text = service("    image: postgres:18-alpine\n    ports:\n" + ports, name="db")
                self.assertEqual(rules(check(text)[0]), ["db_port"])
        self.assertEqual(rules(check(service('    ports: ["3306:3306"]\n', name="mariadb"))[0]), ["db_port"])
        for ports in ('      - "127.0.0.1:5432:5432"\n', "      - target: 5432\n        host_ip: 127.0.0.1\n",
                      '      - "[::1]:5432:5432"\n', "      - host_ip: 127.0.0.1\n        target: 5432\n"):
            with self.subTest(ports=ports):
                text = service("    image: postgres:18-alpine\n    ports:\n" + ports, name="db")
                self.assertEqual(check(text)[0], [])
        self.assertEqual(check(service("    image: postgres:18-alpine\n    ports: []\n", name="db"))[0], [])

    def test_database_images(self):
        for image in ("pgvector/pgvector:pg17", "timescale/timescaledb:2.17.2-pg17", "bitnami/postgresql:17",
                      "valkey/valkey:8", "localhost:5000/mariadb:11.8", "mcr.microsoft.com/mssql/server:2022-latest"):
            with self.subTest(image=image):
                text = service('    image: %s\n    ports:\n      - "5432:5432"\n' % image, name="store")
                self.assertEqual(rules(check(text)[0]), ["db_port"])
        for image in ("postgrest/postgrest:v12.2.3", "nginx:1.30-alpine", "mongo-express:1.0",
                      "rediscommander/redis-commander:0.9"):
            with self.subTest(image=image):
                text = service('    image: %s\n    ports:\n      - "3001:3000"\n' % image, name="api")
                self.assertEqual(check(text)[0], [])

    def test_ports_of_other_services_are_fine_but_a_service_named_db_is_a_database(self):
        text = service('    image: nginx:1.30-alpine\n    ports:\n      - "80:8080"\n', name="web")
        self.assertEqual(check(text)[0], [])
        for name in ("db", "app-db", "app_database", "postgres"):
            with self.subTest(name=name):
                text = service('    build: .\n    ports:\n      - "5432:5432"\n', name=name)
                self.assertEqual(rules(check(text)[0]), ["db_port"])

    def test_secrets_written_in_environment_or_build_args(self):
        fallback = "${STRIPE_SECRET_KEY:-" + FAKE + "}"
        for env in ("    environment:\n      DB_PASSWORD: " + FAKE + "\n",
                    "    environment:\n      - API_KEY=" + FAKE + "\n",
                    '    environment:\n      "STRIPE_SECRET": "' + FAKE + '"\n',
                    "    build:\n      args:\n        NPM_TOKEN: " + FAKE + "\n",
                    "    environment:\n      STRIPE_SECRET_KEY: " + fallback + "\n",  # the fallback is used
                    '    environment:\n      MARIADB_ROOT_PASSWORD: "123456"\n',  # digits are a password too
                    "    environment:\n      SMTP_PASS: " + FAKE + "\n",
                    '    environment: ["DB_PASSWORD=' + FAKE + '", "DEBUG=0"]\n',
                    "    environment: {DB_PASSWORD: " + FAKE + "}\n",
                    "    build:\n      context: .\n      args: [NPM_TOKEN=" + FAKE + "]\n"):
            with self.subTest(env=env):
                findings = check(service(env))[0]
                self.assertEqual(rules(findings), ["secret"])
                self.assertNotIn(FAKE, json.dumps(findings))  # the value is never repeated

    def test_references_settings_and_docker_secrets_are_fine(self):
        env = ("    environment:\n      MARIADB_PASSWORD: ${DB_PASSWORD:?set it in .env}\n"
               "      MARIADB_RANDOM_ROOT_PASSWORD: \"yes\"\n      - SECRET_KEY=$SECRET_KEY\n"
               "      DB_PASSWORD:\n      DATABASE_URL: postgres://app:${DB_PASSWORD}@db/app\n"
               "      POSTGRES_PASSWORD_FILE: /run/secrets/db\n      DB_PASSWORD: ${DB_PASSWORD:-}\n"
               "      OAUTH_TOKEN_URL: https://oauth2.googleapis.com/token\n      JWT_ACCESS_TOKEN_EXPIRES_IN: 15m\n"
               "      PASSWORD_RESET_URL: http://localhost:8080/reset\n      PASSWORD_HASHER: argon2\n"
               "      GOOGLE_APPLICATION_CREDENTIALS: /run/secrets/gcp-key.json\n"
               "      JWT_PRIVATE_KEY: /run/secrets/jwt.pem\n    env_file: .env\n"
               "    secrets: [db_password, stripe_secret_key]\n    build:\n      context: .\n"
               "      secrets:\n        - npm_token\nsecrets:\n  db_password:\n    file: ./db_password.txt\n")
        self.assertEqual(check(service(env))[0], [])

    def test_forge_allow_comment(self):
        text = service("    privileged: true  # forge:allow the user accepted this\n"
                       "    environment:\n      DB_PASSWORD: " + FAKE + "  # forge:allow\n")
        self.assertEqual(check(text)[0], [])

    def test_restart_policy(self):
        text = "services:\n  app:\n    image: a:1\n  job:\n    image: a:1\n    deploy:\n      restart_policy:\n"
        findings = check(text)[0]
        self.assertEqual([f["title"] for f in findings], ["Service app has no restart policy"])
        self.assertEqual(findings[0]["where"], "docker-compose.yml:2")
        self.assertEqual(check('services:\n  migrate:\n    image: a:1\n    restart: "no"\n')[0], [])

    def test_unpinned_images(self):
        for image in ("postgres", "redis:latest", "localhost:5000/app"):
            with self.subTest(image=image):
                findings = check(service("    image: %s\n" % image, name="cache"))[0]
                self.assertEqual(rules(findings), ["tag"])
                self.assertEqual(findings[0]["title"], "Image %s of service cache is not pinned to a version" % image)
        for image in ("postgres:18-alpine", "nginx@sha256:" + "a" * 64, "${IMAGE}"):
            with self.subTest(image=image):
                self.assertEqual(check(service("    image: %s\n" % image))[0], [])
        self.assertEqual(check(service("    build: .\n    image: myapp\n"))[0], [])  # names the built image


class HealthcheckAndTargetTests(unittest.TestCase):
    def test_target_and_healthcheck(self):
        findings, healthcheck, targets = check("services:\n  web:\n    build:\n      context: .\n      target: Web\n"
                                               "    healthcheck:\n      test: [\"CMD\", \"true\"]\n")
        self.assertEqual((healthcheck, targets), (True, {"web"}))

    def test_only_build_target_counts(self):
        text = service("    ports:\n      - published: 9000\n        target: 9000\n        host_ip: 127.0.0.1\n"
                       "    secrets:\n      - source: db\n        target: db_password\n"
                       "    build:\n      context: .\n      target: app\n")
        self.assertEqual(check(text)[2], {"app"})

    def test_a_disabled_healthcheck_is_no_healthcheck(self):
        for body in ("      disable: true\n", '      test: ["NONE"]\n', "      test: NONE\n"):
            with self.subTest(body=body):
                self.assertFalse(check(service("    healthcheck:\n" + body))[1])
        self.assertTrue(check(GOOD_COMPOSE)[1])


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, name, content, encoding="utf-8"):
        with open(os.path.join(self.dir, name), "w", encoding=encoding) as handle:
            handle.write(content)

    def test_a_link_to_a_file_outside_the_folder(self):
        """Also one on another drive (Windows: the runners have the checkout on D: and the temp folder on C:)."""
        template = os.path.join(ROOT, "forge-build", "templates", "static", "docker-compose.yml")
        symlink(self, template, os.path.join(self.dir, "docker-compose.yml"))
        with self.assertRaisesRegex(ValueError, "^docker-compose.yml is a link to a file outside "):
            mod.check_folder(self.dir)
        self.assertEqual(run(self.dir)[0], 2)

    def test_exit_codes_json_and_summary(self):
        build = "build:\n      context: .\n      target: app"
        self.write("docker-compose.yml", GOOD_COMPOSE.replace("build: .", build))
        code, out = run(self.dir, "--json")
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(data["summary"]["checked"], ["docker-compose.yml"])
        self.assertEqual((data["summary"]["healthcheck"], data["summary"]["targets"]), (True, ["app"]))
        self.write("compose.override.yaml", service("    network_mode: host\n"))
        self.assertEqual(run(self.dir)[0], 0)
        self.assertEqual(run(self.dir, "--fail-on", "medium")[0], 1)
        code, out = run(self.dir, "--fail-on", "medium")
        self.assertIn("MEDIUM    Service app uses the host network", out)
        self.assertIn("where: compose.override.yaml:4", out)
        self.assertIn("Checked: compose.override.yaml, docker-compose.yml.", out)
        for f in json.loads(run(self.dir, "--json")[1])["findings"]:
            self.assertTrue({"severity", "title", "where", "why", "fix"} <= set(f))

    def test_an_override_file_adds_to_the_main_file(self):
        """forge-build build's dev override publishes the db port for the tests: it keeps the restart policy,
        the build and the image of the main file, and every safety rule still applies to it."""
        self.write("docker-compose.yml", "services:\n  app:\n    build: .\n    restart: unless-stopped\n"
                                         "  store:\n    image: postgres:18\n    restart: unless-stopped\n")
        self.write("docker-compose.override.yml", "services:\n  store:\n    ports:\n"
                                                  "      - \"127.0.0.1:5433:5432\"\n  app:\n    image: myapp\n")
        code, out = run(self.dir, "--fail-on", "low")
        self.assertEqual(code, 0, out)
        self.assertIn("No findings.", out)
        self.write("docker-compose.override.yml", "services:\n  store:\n    ports:\n      - \"5433:5432\"\n"
                                                  "  app:\n    privileged: true\n  adminer:\n    image: adminer:5\n")
        found = json.loads(run(self.dir, "--json")[1])["findings"]
        self.assertEqual([(f["rule"], f["where"]) for f in found], [
            ("privileged", "docker-compose.override.yml:6"), ("db_port", "docker-compose.override.yml:4"),
            ("no_restart", "docker-compose.override.yml:7")])  # adminer is new: it needs its own
        os.remove(os.path.join(self.dir, "docker-compose.yml"))  # no main file: checked on its own
        self.write("docker-compose.override.yml", "services:\n  app:\n    image: myapp\n")
        self.assertEqual(rules(json.loads(run(self.dir, "--json")[1])["findings"]), ["no_restart", "tag"])

    def test_a_file_that_starts_with_a_bom(self):
        self.write("docker-compose.yml", "\ufeff" + service("    privileged: true\n"), encoding="utf-8")
        code, out = run(self.dir)
        self.assertEqual(code, 1)
        self.assertIn("Service app runs privileged", out)

    def test_bad_input(self):
        self.assertEqual(run(os.path.join(self.dir, "missing"))[0], 2)
        self.assertEqual(run(self.dir)[0], 2)  # no compose file
        self.write("docker-compose.yml", '{"services": {"app": {"privileged": true}}}')
        self.assertEqual(run(self.dir)[0], 2)  # JSON: cannot be checked, so no false PASS
        with self.assertRaises(SystemExit) as raised:
            run(self.dir, "--fail-on", "nope")
        self.assertEqual(raised.exception.code, 2)


class ConsoleTests(unittest.TestCase):
    def test_a_cp1252_pipe_gets_escapes_not_a_crash(self):
        """Windows pipes are cp1252 (no arrow): the arrow prints as \\u2192, no crash."""
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, "docker-compose.yml"), "w", encoding="utf-8") as handle:
                handle.write(service("    privileged: true\n", name="caf\u00e9-\u2192"))
            code, out, err = run_cp1252(mod.__file__, folder)
        self.assertEqual(code, 1, err)
        self.assertIn("Service caf\u00e9-\\u2192 runs privileged", out)


if __name__ == "__main__":
    unittest.main()
