"""Tests for forge-pack/packcheck.py (the compose rules are in test_composecheck.py).

Fake secrets are glued together at runtime, so this file never contains a
secret-looking literal: the repo itself is scanned with secretscan.py in CI.
"""

import contextlib
import inspect
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load  # noqa: E402

mod = load("forge-pack", "packcheck")
compose = load("forge-pack", "composecheck")

TEMPLATES = os.path.join(ROOT, "forge-pack", "templates")
PROFILES = ("laravel", "django", "next", "static")
FAKE = "hunter" + "22-" + "Xy9"  # a password-looking value
GOOD_IGNORE = ".env\n.git\nforge-work/\n"
GOOD_DOCKERFILE = "FROM node:24-alpine\nWORKDIR /app\nCOPY . .\nUSER node\nCMD [\"node\", \"server.js\"]\n"
GOOD_COMPOSE = ("services:\n  app:\n    build: .\n    env_file: .env\n    healthcheck:\n"
                "      test: [\"CMD\", \"true\"]\n    restart: unless-stopped\n")


def write(folder, relative_path, content, encoding="utf-8"):
    path = os.path.join(folder, relative_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding=encoding) as handle:
        handle.write(content)
    return path


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def run(*args):
    """Run main() and return (exit code, stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = mod.main(list(args))
    return code, out.getvalue()


def rules(findings):
    return sorted(f["rule"] for f in findings)


def dockerfile_rules(text, targets=(), has_ignore=True):
    return rules(mod.check_dockerfile(text, "Dockerfile", targets, has_ignore)[0])


def in_final_stage(line):
    """A one-stage Dockerfile with LINE in it that is fine otherwise."""
    return "FROM node:24-alpine\n%s\nUSER node\n" % line


class Project(unittest.TestCase):
    """A temporary project folder with a clean container setup, which tests then break."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        write(self.dir, "Dockerfile", GOOD_DOCKERFILE)
        write(self.dir, "docker-compose.yml", GOOD_COMPOSE)
        write(self.dir, ".dockerignore", GOOD_IGNORE)
        write(self.dir, ".env.example", "DB_PASSWORD=change-me\n")

    def check(self):
        return mod.check_project(self.dir)


class TemplateTests(unittest.TestCase):
    """Every profile's templates, and the promises SKILL.md makes about them."""

    def test_each_profile_is_clean_once_installed(self):
        for profile in PROFILES:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as folder:
                source = os.path.join(TEMPLATES, profile)
                names = {"dockerignore": ".dockerignore", "env.example": ".env.example"}
                for name in os.listdir(source):
                    shutil.copy(os.path.join(source, name), os.path.join(folder, names.get(name, name)))
                code, out = run(folder, "--fail-on", "low")
                self.assertEqual(code, 0, out)
                self.assertIn("No findings.", out)

    def test_each_profile_has_its_files(self):
        expected = {"Dockerfile", "docker-compose.yml", "dockerignore", "env.example", "RUN.md"}
        for profile in PROFILES:
            with self.subTest(profile=profile):
                names = set(os.listdir(os.path.join(TEMPLATES, profile)))
                self.assertEqual(names, expected | ({"nginx.conf"} if profile in ("laravel", "static") else set()))
        self.assertEqual(sorted(os.listdir(TEMPLATES)), sorted(PROFILES))

    def test_compose_promises(self):
        """The app on 127.0.0.1 only, on APP_PORT (default 8080), every service restarts, the app's
        settings from .env."""
        for profile in PROFILES:
            with self.subTest(profile=profile):
                services = compose.compose_services(read(os.path.join(TEMPLATES, profile, "docker-compose.yml")))
                published = [line for lines in services.values() for _, keys, line in lines if keys == ("ports",)]
                self.assertIn('- "127.0.0.1:${APP_PORT:-8080}:', " ".join(published))
                # this machine only, and every host port a variable: two stacks on one machine
                self.assertTrue(all(line.startswith('- "127.0.0.1:${') for line in published), published)
                for name, lines in services.items():
                    texts = [line for _, keys, line in lines if keys == ()]
                    self.assertIn("restart: unless-stopped", texts, name)
                    if name in ("app", "worker"):
                        self.assertIn("env_file: .env", texts, name)

    def test_dockerignore_promises(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                lines = read(os.path.join(TEMPLATES, profile, "dockerignore")).splitlines()
                for name in (".env", ".git", "forge-work", "node_modules", "coverage", "test-results"):
                    self.assertTrue(mod.is_ignored(lines, name), name)
                self.assertFalse(mod.is_ignored(lines, ".env.example"))

    def test_e2e_and_backups_stay_out_of_the_image(self):
        """forge-test keeps the whole e2e/ folder out; a database dump or an uploads backup too."""
        for profile in PROFILES:
            with self.subTest(profile=profile):
                lines = read(os.path.join(TEMPLATES, profile, "dockerignore")).splitlines()
                self.assertTrue(mod.is_ignored(lines, "e2e"))
                if profile != "static":  # no database
                    for name in ("db-2026-01-31.sql.gz", "dump.sql", "uploads-2026-01-31.tgz"):
                        self.assertTrue(mod.is_ignored(lines, name), name)

    def test_env_example_promises(self):
        """The port, the seed password forge-build and forge-test use, and Stripe lines that say
        they can go."""
        for profile in PROFILES:
            with self.subTest(profile=profile):
                text = read(os.path.join(TEMPLATES, profile, "env.example"))
                if profile == "static":  # needs no .env to run
                    self.assertIn("\n# APP_PORT=8080\n", text)
                    continue
                for line in ("APP_PORT=8080", "SEED_PASSWORD=change-me", "# MAILPIT_PORT=8025",
                             "# Delete these lines if the app takes no payments."):
                    self.assertIn("\n" + line + "\n", text)

    def test_run_md_promises(self):
        """One RUN.md per profile with only its own commands, its placeholders, and backups that
        are written outside the project."""
        allowed = {"{{App name}}", "{{app}}", "{{First account}}", "{{Stripe webhook events}}"}
        others = {"laravel": ("Django", "Next", "PostgreSQL", "pg_dump", "BETTER_AUTH"),
                  "django": ("Laravel", "artisan", "Next", "BETTER_AUTH"),
                  "next": ("Laravel", "artisan", "Django", "manage.py", "MariaDB"),
                  "static": ("Laravel", "Django", "Next", "db-data", "change-me", "{{app}}")}
        for profile in PROFILES:
            with self.subTest(profile=profile):
                text = read(os.path.join(TEMPLATES, profile, "RUN.md"))
                self.assertLessEqual(set(re.findall(r"\{\{[^}]*\}\}", text)), allowed)
                self.assertIn("APP_PORT", text)
                for word in others[profile]:
                    self.assertNotIn(word, text)
                for line in text.splitlines():
                    if re.search(r"\bgzip > |\btar czf .* > ", line):
                        self.assertIn("> ~/backups/{{app}}/", line)

    def test_laravel_keeps_its_local_secrets_out(self):
        """Composer logins, Passport keys, the cached config (every .env value), uploads and sessions."""
        lines = read(os.path.join(TEMPLATES, "laravel", "dockerignore")).splitlines()
        self.assertTrue(mod.is_ignored(lines, "vendor"))
        for line in ("auth.json", "storage/*.key", "storage/app/**", "storage/framework/**", "storage/logs/**",
                     "bootstrap/cache/**", "!storage/**/.gitignore", "!bootstrap/cache/.gitignore"):
            self.assertIn(line, lines)
        dockerfile = read(os.path.join(TEMPLATES, "laravel", "Dockerfile"))
        self.assertIn("mkdir -p storage/app/public storage/framework/cache/data", dockerfile)


class ProjectTests(Project):
    def test_clean_project(self):
        findings, checked = self.check()
        self.assertEqual(findings, [])
        self.assertEqual(checked, ["docker-compose.yml", "Dockerfile", ".dockerignore", ".env.example"])

    def test_the_dev_override_file_is_no_finding(self):
        """The git-ignored docker-compose.override.yml forge-build and forge-test ask for."""
        override = "services:\n  app:\n    ports:\n      - \"127.0.0.1:3000:3000\"\n"
        write(self.dir, "docker-compose.override.yml", override)
        findings, checked = self.check()
        self.assertEqual(findings, [])
        self.assertIn("docker-compose.override.yml", checked)

    def test_no_env_example(self):
        os.remove(os.path.join(self.dir, ".env.example"))
        findings = self.check()[0]
        self.assertEqual(rules(findings), ["no_example"])
        self.assertEqual(findings[0]["where"], "the project folder")

    def test_no_healthcheck_anywhere(self):
        no_check = GOOD_COMPOSE.replace("    healthcheck:\n      test: [\"CMD\", \"true\"]\n", "")
        write(self.dir, "docker-compose.yml", no_check)
        self.assertEqual(rules(self.check()[0]), ["no_health"])
        write(self.dir, "Dockerfile", GOOD_DOCKERFILE + "HEALTHCHECK CMD wget -q --spider http://127.0.0.1:3000/\n")
        self.assertEqual(self.check()[0], [])

    def test_compose_findings_are_included(self):
        write(self.dir, "docker-compose.yml", GOOD_COMPOSE + "    privileged: true\n")
        self.assertEqual(rules(self.check()[0]), ["privileged"])

    def test_copy_everything_without_dockerignore(self):
        os.remove(os.path.join(self.dir, ".dockerignore"))
        self.assertEqual(rules(self.check()[0]), ["copy_all"])
        write(self.dir, "Dockerfile.dockerignore", GOOD_IGNORE)  # BuildKit's per-Dockerfile ignore file
        self.assertEqual(self.check()[0], [])

    def test_the_per_dockerfile_ignore_file_is_the_one_checked(self):
        write(self.dir, "Dockerfile.dockerignore", "node_modules\n")  # BuildKit uses it, not .dockerignore
        findings, checked = self.check()
        self.assertEqual(sorted(f["title"] for f in findings), [
            "Dockerfile.dockerignore does not keep out .env", "Dockerfile.dockerignore does not keep out .git",
            "Dockerfile.dockerignore does not keep out forge-work/"])
        self.assertNotIn(".dockerignore", checked)

    def test_dockerignore_must_keep_out_env_git_and_forge_work(self):
        write(self.dir, ".dockerignore", "node_modules\n")
        findings = self.check()[0]
        self.assertEqual(rules(findings), ["ignore", "ignore", "ignore"])
        self.assertEqual(sorted(f["title"] for f in findings), [".dockerignore does not keep out .env",
                         ".dockerignore does not keep out .git", ".dockerignore does not keep out forge-work/"])

    def test_other_dockerfile_names_are_checked(self):
        write(self.dir, "Dockerfile.worker", "FROM python\n")
        write(self.dir, "api.Dockerfile", "FROM python:3.14-slim\nUSER app\n")
        findings, checked = self.check()
        self.assertIn("Dockerfile.worker", checked)
        self.assertIn("api.Dockerfile", checked)
        self.assertEqual(rules(findings), ["root", "tag"])

    def test_compose_targets_are_final_stages(self):
        write(self.dir, "Dockerfile", "FROM php:8.5-fpm-alpine AS app\nCOPY . .\n"
                                      "FROM nginx:1.30-alpine AS web\nUSER nginx\n")
        build = ("    ports:\n      - published: 9000\n        target: 9000\n"  # a target: that is not the build's
                 "    build:\n      context: .\n      target: app\n")
        write(self.dir, "docker-compose.yml", GOOD_COMPOSE.replace("    build: .\n", build))
        findings = self.check()[0]
        self.assertEqual(rules(findings), ["root"])
        self.assertEqual(findings[0]["where"], "Dockerfile:1")

    def test_findings_are_sorted_most_severe_first(self):
        os.remove(os.path.join(self.dir, ".env.example"))
        write(self.dir, "Dockerfile", "FROM node\nENV API_KEY=" + FAKE + "\nUSER node\n")
        self.assertEqual([f["severity"] for f in self.check()[0]], ["critical", "medium", "medium"])

    def test_files_that_start_with_a_bom(self):
        """Windows editors write one; Docker and compose read such files normally."""
        write(self.dir, "Dockerfile", "﻿FROM node:24-alpine\nCOPY . .\n")
        write(self.dir, ".dockerignore", "﻿" + GOOD_IGNORE)
        write(self.dir, "docker-compose.yml", "﻿" + GOOD_COMPOSE + "    privileged: true\n")
        self.assertEqual(rules(self.check()[0]), ["privileged", "root"])


class DockerfileTests(unittest.TestCase):
    def test_base_image_tags(self):
        self.assertEqual(dockerfile_rules("FROM node\nUSER node\n"), ["tag"])
        self.assertEqual(dockerfile_rules("FROM node:latest\nUSER node\n"), ["tag"])
        self.assertEqual(dockerfile_rules("FROM localhost:5000/app\nUSER app\n"), ["tag"])
        for fine in ("node:24-alpine", "localhost:5000/app:1.2", "node@sha256:" + "a" * 64,
                     "scratch", "${BASE_IMAGE}", "--platform=linux/amd64 node:24-alpine"):
            with self.subTest(image=fine):
                self.assertEqual(dockerfile_rules("FROM %s\nUSER app\n" % fine), [])

    def test_tag_finding_names_the_image(self):
        findings = mod.check_dockerfile("FROM node:latest AS build\nFROM node\nUSER node\n", "Dockerfile")[0]
        self.assertEqual(sorted(f["title"] for f in findings), ["Base image node is not pinned to a version",
                                                                "Base image node:latest is not pinned to a version"])

    def test_root_user(self):
        self.assertEqual(dockerfile_rules("FROM node:24-alpine\n"), ["root"])
        for user in ("root", "0", "0:0", "root:root", '"root"', "'0'"):
            with self.subTest(user=user):
                self.assertEqual(dockerfile_rules("FROM node:24-alpine\nUSER %s\n" % user), ["root"])
        self.assertEqual(dockerfile_rules("FROM node:24-alpine\nUSER node\n"), [])
        self.assertEqual(dockerfile_rules("FROM node:24-alpine\nUSER node\nUSER root\n"), ["root"])

    def test_only_the_last_stage_and_targets_must_drop_root(self):
        text = "FROM node:24-alpine AS build\nRUN npm ci\nFROM node:24-alpine\nUSER node\n"
        self.assertEqual(dockerfile_rules(text), [])
        self.assertEqual(dockerfile_rules(text, targets={"build"}), ["root"])

    def test_user_is_inherited_from_an_earlier_stage(self):
        text = "FROM php:8.5-fpm-alpine AS base\nUSER www-data\nFROM base AS app\nCOPY . .\n"
        self.assertEqual(dockerfile_rules(text), [])

    def test_heredoc_bodies_are_not_instructions(self):
        python = 'RUN python3 <<PY\nfrom pathlib import Path\nPath("/tmp/ready").write_text("ok")\nPY\n'
        self.assertEqual(dockerfile_rules("FROM python:3.14-slim\nUSER app\n" + python + "CMD [\"app\"]\n"), [])
        self.assertEqual(dockerfile_rules("FROM node:24-alpine\nRUN <<EOF\nset -e\nUSER node\nenv\nEOF\n"), ["root"])
        text = "FROM node:24-alpine\nRUN <<-'ONE' cat - <<TWO\n\techo 1\n\tONE\nENV X=1\nTWO\nUSER node\n"
        self.assertEqual([i[1] for i in mod.instructions(text)], ["FROM", "RUN", "USER"])
        for run in ("RUN cat <<< 'x'", 'RUN ["sh", "-c", "cat <<EOF"]'):  # a here-string; the exec form
            with self.subTest(run=run):
                found = mod.instructions("FROM a:1\n%s\nUSER a\n" % run)
                self.assertEqual([i[1] for i in found], ["FROM", "RUN", "USER"])

    def test_bare_env_and_arg(self):
        for line in ("ARG", "ENV", "ENV A", "ARG  "):
            with self.subTest(line=line):
                self.assertEqual(dockerfile_rules(in_final_stage(line)), [])
        self.assertEqual(mod.env_pairs(""), [])

    def test_secret_in_env_or_arg(self):
        for line in ("ENV DB_PASSWORD=" + FAKE, "ENV API_KEY " + FAKE, "ARG NPM_TOKEN=" + FAKE,
                     'ENV A=1 STRIPE_SECRET="' + FAKE + '"', "ENV APP_KEY=base64:" + FAKE,
                     "ENV SESSION_SECRET=${SESSION_SECRET:-" + FAKE + "}", "ENV DB_PASSWORD=12345678",
                     "ENV DB_PASS=" + FAKE, "ENV SMTP_PASS " + FAKE, "ENV MAIL_PWD=" + FAKE):
            with self.subTest(line=line):
                self.assertEqual(dockerfile_rules(in_final_stage(line)), ["env_secret"])

    def test_no_secret_in_references_settings_and_paths(self):
        for line in ("ENV DB_PASSWORD=${DB_PASSWORD}", "ARG NPM_TOKEN", "ENV DB_PASSWORD=", "ENV DB_PASSWORD=${A:-}",
                     "ENV POSTGRES_PASSWORD_FILE=/run/secrets/db", "ENV NEXT_TELEMETRY_DISABLED=1",
                     'ENV PATH="/opt/venv/bin:$PATH" PIP_NO_CACHE_DIR=1', "ARG TOKEN_TTL=3600",
                     "ENV TOKEN_URL=https://auth.example.com/token", "ENV PASSWORD_HASHER=argon2",
                     "ENV AUTH_TOKEN_TTL=1h", "ENV CREDENTIALS_PROVIDER=google", "ENV CACHE_BYPASS=1h",
                     "ENV GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcp-key.json", "ENV PWD=/app"):
            with self.subTest(line=line):
                self.assertEqual(dockerfile_rules(in_final_stage(line)), [])

    def test_copy_of_the_whole_folder(self):
        for line in ("COPY . .", "COPY ./ /app/", "ADD . /app", 'COPY [".", "/app"]', "COPY --chown=app . .",
                     "COPY * ./", "COPY ./* /app/", "COPY ./. /app", "COPY / /app", "COPY .* /app/"):
            with self.subTest(line=line):
                self.assertEqual(dockerfile_rules(in_final_stage(line), has_ignore=False), ["copy_all"])
                self.assertEqual(dockerfile_rules(in_final_stage(line), has_ignore=True), [])
        for line in ("COPY package.json .", "COPY --from=build /app/dist .", "COPY src/* ./src/", "COPY *.json ./"):
            with self.subTest(line=line):
                self.assertEqual(dockerfile_rules(in_final_stage(line), has_ignore=False), [])

    def test_forge_allow_on_the_line_above(self):
        self.assertEqual(dockerfile_rules(in_final_stage("# forge:allow test key, not real\nENV API_KEY=" + FAKE)), [])
        self.assertEqual(dockerfile_rules("# forge:allow\nFROM node\n"), [])  # the tag and root checks
        self.assertEqual(dockerfile_rules("FROM node:24-alpine\n# forge:allow\nUSER root\n"), [])
        self.assertEqual(dockerfile_rules(in_final_stage("# forge:allow\nRUN true\nENV API_KEY=" + FAKE)),
                         ["env_secret"])  # only the instruction right below it

    def test_continuations_and_comments(self):
        text = "# FROM node\nFROM node:24-alpine\nRUN apk add \\\n    # a comment inside\n    curl\nUSER \\\n  node\n"
        self.assertEqual([i[:2] for i in mod.instructions(text)], [(2, "FROM"), (3, "RUN"), (6, "USER")])
        self.assertEqual(dockerfile_rules(text), [])

    def test_healthcheck(self):
        self.assertTrue(mod.check_dockerfile("FROM a:1\nHEALTHCHECK CMD true\n", "D")[1])
        self.assertFalse(mod.check_dockerfile("FROM a:1\nHEALTHCHECK NONE\n", "D")[1])

    def test_secret_rule_is_the_same_as_composecheck(self):
        for name in ("SECRET_NAME", "SWITCH_NAME", "SWITCH_VALUES", "FALLBACK", "FILE_PATH"):
            with self.subTest(name=name):
                self.assertEqual(getattr(mod, name), getattr(compose, name))
        for function in ("is_written_secret", "unquote"):
            with self.subTest(function=function):
                self.assertEqual(inspect.getsource(getattr(mod, function)),
                                 inspect.getsource(getattr(compose, function)))


class DockerignoreTests(unittest.TestCase):
    def test_patterns(self):
        for patterns in ([".env"], [".env*"], ["**/.env"], ["/.env"], ["./.env"], ["*", "!src"]):
            with self.subTest(patterns=patterns):
                self.assertTrue(mod.is_ignored(patterns, ".env"))
        for patterns in ([".env.local"], [".env", "!.env"], ["env"], []):
            with self.subTest(patterns=patterns):
                self.assertFalse(mod.is_ignored(patterns, ".env"))
        for pattern in ("forge-work", "forge-work/", "/forge-work/", "forge-work/**", "forge-*"):
            with self.subTest(pattern=pattern):
                self.assertTrue(mod.is_ignored([pattern], "forge-work"))
        self.assertTrue(mod.is_ignored([".env", ".env.*", "!.env.example"], ".env"))

    def test_bringing_back_a_part_counts_as_not_kept_out(self):
        self.assertFalse(mod.is_ignored(["forge-work/", "!forge-work/recon.md"], "forge-work"))
        self.assertFalse(mod.is_ignored(["forge-work/drafts/"], "forge-work"))  # only a part is kept out


class CommandLineTests(Project):
    def test_exit_codes_and_fail_on(self):
        self.assertEqual(run(self.dir)[0], 0)
        os.remove(os.path.join(self.dir, ".env.example"))  # a medium finding
        self.assertEqual(run(self.dir)[0], 0)
        self.assertEqual(run(self.dir, "--fail-on", "medium")[0], 1)
        write(self.dir, "Dockerfile", GOOD_DOCKERFILE.replace("USER node\n", ""))  # a high one
        self.assertEqual(run(self.dir)[0], 1)
        self.assertEqual(run(self.dir, "--fail-on", "critical")[0], 0)

    def test_human_output(self):
        write(self.dir, "Dockerfile", "FROM node\nUSER node\n")
        code, out = run(self.dir)
        self.assertEqual(code, 0)
        self.assertIn("MEDIUM    Base image node is not pinned to a version", out)
        self.assertIn("where: Dockerfile:1", out)
        self.assertIn("Checked: docker-compose.yml, Dockerfile, .dockerignore, .env.example.", out)
        self.assertIn("1 finding: 1 medium.", out)
        self.assertIn("PASS: nothing is high or worse.", out)

    def test_json_output(self):
        write(self.dir, "Dockerfile", "FROM node\n")
        code, out = run(self.dir, "--json")
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual((data["summary"]["high"], data["summary"]["medium"], data["summary"]["total"]), (1, 1, 2))
        self.assertTrue(data["summary"]["failed"])
        for f in data["findings"]:
            self.assertTrue({"severity", "title", "where", "why", "fix"} <= set(f))

    def test_bad_input(self):
        self.assertEqual(run(os.path.join(self.dir, "missing"))[0], 2)
        self.assertEqual(run(os.path.join(self.dir, "Dockerfile"))[0], 2)  # a file, not a folder
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(run(empty)[0], 2)  # nothing to check
        with self.assertRaises(SystemExit) as raised:
            run(self.dir, "--fail-on", "nope")
        self.assertEqual(raised.exception.code, 2)

    def test_a_dockerfile_that_is_not_a_plain_file(self):
        os.remove(os.path.join(self.dir, "Dockerfile"))
        os.mkdir(os.path.join(self.dir, "Dockerfile"))  # a folder
        self.assertEqual(run(self.dir)[0], 2)
        os.rmdir(os.path.join(self.dir, "Dockerfile"))
        write(self.dir, "Dockerfile", "# x\n" * 300000)  # over 1 MB
        self.assertEqual(run(self.dir)[0], 2)
        if hasattr(os, "mkfifo"):  # a FIFO would make a read wait forever
            os.remove(os.path.join(self.dir, "Dockerfile"))
            os.mkfifo(os.path.join(self.dir, "Dockerfile"))
            self.assertEqual(run(self.dir)[0], 2)

    def test_a_link_to_a_file_outside_the_folder(self):
        with tempfile.TemporaryDirectory() as outside:
            os.remove(os.path.join(self.dir, "Dockerfile"))
            os.symlink(write(outside, "Dockerfile", GOOD_DOCKERFILE), os.path.join(self.dir, "Dockerfile"))
            self.assertEqual(run(self.dir)[0], 2)
        os.remove(os.path.join(self.dir, "Dockerfile"))
        write(self.dir, "docker/Dockerfile", GOOD_DOCKERFILE)
        os.symlink(os.path.join("docker", "Dockerfile"), os.path.join(self.dir, "Dockerfile"))
        self.assertEqual(run(self.dir)[0], 0)  # a link inside the folder is fine

    def test_a_compose_file_it_cannot_read_is_an_error_not_a_pass(self):
        write(self.dir, "docker-compose.yml", '{"services": {"db": {"image": "postgres:18", "privileged": true}}}')
        self.assertEqual(run(self.dir)[0], 2)

    def test_composecheck_that_gives_no_report_is_an_error(self):
        broken = write(self.dir, "broken.py", "import sys\nsys.exit(1)\n")  # exit 1 and no JSON
        original, mod.COMPOSECHECK = mod.COMPOSECHECK, broken
        self.addCleanup(setattr, mod, "COMPOSECHECK", original)
        self.assertEqual(run(self.dir)[0], 2)

    def test_a_bare_arg_gives_no_traceback(self):
        write(self.dir, "Dockerfile", "FROM node:24-alpine\nARG\nUSER node\n")
        self.assertEqual(run(self.dir, "--json")[0], 0)


if __name__ == "__main__":
    unittest.main()
