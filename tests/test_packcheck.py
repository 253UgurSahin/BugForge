"""Tests for forge-build/packcheck.py (the compose rules are in test_composecheck.py).

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
from _load import ROOT, load, run_cp1252, symlink  # noqa: E402

mod = load("forge-build", "packcheck")
compose = load("forge-build", "composecheck")

TEMPLATES = os.path.join(ROOT, "forge-build", "templates")
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


def install(profile, folder):
    """PROFILE's templates in FOLDER as forge-build pack installs them: the dotfiles get their dot."""
    source = os.path.join(TEMPLATES, profile)
    names = {"dockerignore": ".dockerignore", "env.example": ".env.example"}
    for name in os.listdir(source):
        shutil.copy(os.path.join(source, name), os.path.join(folder, names.get(name, name)))


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
        """Without the app, as the CI templates job checks them: each file the Dockerfile copies is
        there, but for the app's package files (forge-build pack Step 3 checks those are committed)."""
        for profile in PROFILES:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as folder:
                install(profile, folder)
                code, out = run(folder, "--fail-on", "low")
                self.assertEqual(code, 0, out)
                self.assertIn("No findings.", out)

    def test_a_missing_nginx_conf_fails(self):
        """Dogfood: the pack gate passed with nginx.conf deleted, so the image could not be built."""
        for profile in ("laravel", "static"):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as folder:
                install(profile, folder)
                os.remove(os.path.join(folder, "nginx.conf"))
                code, out = run(folder)
                self.assertEqual(code, 1, out)
                self.assertIn("HIGH      The image build needs nginx.conf, which is not in the project folder", out)
                self.assertRegex(out, r"where: Dockerfile:\d+\n")

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

    def test_nginx_promises(self):
        """Dogfood: behind the user's HTTPS proxy, nginx's redirect from /planner to /planner/ named its
        own address (http://<host>:8080/planner/), and the PWA manifest went out as octet-stream."""
        for profile in ("laravel", "static"):
            with self.subTest(profile=profile):
                text = read(os.path.join(TEMPLATES, profile, "nginx.conf"))
                server_level = text[:text.index("    location ")]  # before the first location block
                self.assertIn("\n    absolute_redirect off;\n", server_level)
                manifest = re.search(r"\n    location = /manifest\.webmanifest \{\n(.*?)\n    \}", text, re.S)
                self.assertIsNotNone(manifest)
                self.assertIn("default_type application/manifest+json;", manifest.group(1))
                self.assertIn("expires -1;", manifest.group(1))  # checked for a new version, like sw.js
                self.assertNotIn("types {", text)  # a types block would replace all of mime.types

    def test_static_nginx_names_the_multi_page_variants(self):
        """forge-launch Step 2 points at the multi-page try_files line here (/pricing gets pricing.html,
        an unknown path a 404, its own 404 page if it has one) and at the /app/ location for a
        single-page app in app.html. The default stays the single-page app's fallback."""
        text = read(os.path.join(TEMPLATES, "static", "nginx.conf"))
        self.assertIn("\n        try_files $uri $uri/ /index.html;\n", text)
        for variant in ("`try_files $uri $uri/ $uri.html =404;`", "`error_page 404 /404.html;`",
                        "`location /app/ { expires -1; try_files $uri /app.html; }`"):
            self.assertIn(variant, text)

    def test_dockerignore_promises(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                lines = read(os.path.join(TEMPLATES, profile, "dockerignore")).splitlines()
                # every file of secrets packcheck asks to keep out, so an honest project passes as it is
                for name in (".env", ".git", "forge-work", "node_modules", "coverage", "test-results", "auth.json",
                             "local.key", "cert.p12", "cert.pfx"):
                    self.assertTrue(mod.is_ignored(lines, name), name)
                self.assertFalse(mod.is_ignored(lines, ".env.example"))
                # npm's and Yarn's logins: the laravel and django images take the whole folder, while
                # next and static ship only their build output (review: a token reached the image).
                for name in (".npmrc", ".yarnrc.yml"):
                    self.assertEqual(mod.is_ignored(lines, name), profile in ("laravel", "django"), name)

    def test_the_in_image_check_looks_for_each_login(self):
        """forge-build pack Step 5 looks in the running app image for the .env, npm's and Composer's logins
        and forge's notes, which the laravel and django images would take from the folder."""
        text = read(os.path.join(ROOT, "forge-build", "steps", "pack.md"))
        check = re.search(r"docker compose exec app sh -c '([^']*)'", text).group(1)
        self.assertEqual(re.findall(r"test ! -e (\S+) &&", check), [".env", ".npmrc", "auth.json", "forge-work"])
        self.assertTrue(check.endswith("&& echo clean"), check)

    def test_e2e_and_backups_stay_out_of_the_image(self):
        """forge-check test keeps the whole e2e/ folder out; a database dump or an uploads backup too."""
        for profile in PROFILES:
            with self.subTest(profile=profile):
                lines = read(os.path.join(TEMPLATES, profile, "dockerignore")).splitlines()
                self.assertTrue(mod.is_ignored(lines, "e2e"))
                if profile != "static":  # no database
                    for name in ("db-2026-01-31.sql.gz", "dump.sql", "uploads-2026-01-31.tgz"):
                        self.assertTrue(mod.is_ignored(lines, name), name)

    def test_env_example_promises(self):
        """The port, the seed password forge-build build and forge-check test use, and Stripe lines that say
        they can go. No build values (VITE_, NEXT_PUBLIC_): .dockerignore keeps .env out of the image
        build, so they go in .env.production (dogfood: the static one had VITE_APP_NAME)."""
        for profile in PROFILES:
            with self.subTest(profile=profile):
                text = read(os.path.join(TEMPLATES, profile, "env.example"))
                settings = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
                self.assertEqual([line for line in settings if re.match(r"(?:VITE|NEXT_PUBLIC)_", line)], [])
                if profile == "static":  # needs no .env to run
                    self.assertIn("\n# APP_PORT=8080\n", text)
                    self.assertEqual(settings, [])
                    self.assertIn(".env.production", text)
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
        """Composer, npm and Yarn logins, Passport keys, the cached config (every .env value), uploads
        and sessions."""
        lines = read(os.path.join(TEMPLATES, "laravel", "dockerignore")).splitlines()
        self.assertTrue(mod.is_ignored(lines, "vendor"))
        for line in ("auth.json", ".npmrc", ".yarnrc.yml", "storage/*.key", "storage/app/**", "storage/framework/**",
                     "storage/logs/**", "bootstrap/cache/**", "!storage/**/.gitignore", "!bootstrap/cache/.gitignore"):
            self.assertIn(line, lines)
        dockerfile = read(os.path.join(TEMPLATES, "laravel", "Dockerfile"))
        self.assertIn("mkdir -p storage/app/public storage/framework/cache/data", dockerfile)

    def test_laravel_builds_the_app_name_into_its_javascript(self):
        """No .env reaches the image build, so `npm run build` had no VITE_APP_NAME and the Inertia
        kits' page titles said Laravel, also after a rename. compose passes APP_NAME as a build arg,
        the same to each service that builds (web serves the Vite files app's pages name). No
        .env.production either: in the image, Laravel would load it at run time (APP_ENV is set)."""
        stage, steps = None, []  # (stage, INSTRUCTION, arguments)
        for _, keyword, args, _ in mod.instructions(read(os.path.join(TEMPLATES, "laravel", "Dockerfile"))):
            stage = args.split()[-1] if keyword == "FROM" else stage
            steps.append((stage, keyword, args))
        assets = [(keyword, args) for name, keyword, args in steps if name == "assets"]
        self.assertLess(assets.index(("ARG", "VITE_APP_NAME")), assets.index(("RUN", "npm run build")))
        self.assertEqual([step for step in steps if "VITE_" in step[2] and step[0] != "assets"], [])
        services = compose.compose_services(read(os.path.join(TEMPLATES, "laravel", "docker-compose.yml")))
        args = {name: [line for _, keys, line in lines if keys == ("build", "args")]
                for name, lines in services.items() if any(line.startswith("build:") for _, _, line in lines)}
        self.assertEqual(args, {name: ["VITE_APP_NAME: ${APP_NAME:-Laravel}"] for name in ("web", "app", "worker")})
        ignore = read(os.path.join(TEMPLATES, "laravel", "dockerignore")).splitlines()
        self.assertTrue(mod.is_ignored(ignore, ".env.production"))


class ProjectTests(Project):
    def test_clean_project(self):
        findings, checked = self.check()
        self.assertEqual(findings, [])
        self.assertEqual(checked, ["docker-compose.yml", "Dockerfile", ".dockerignore", ".env.example"])

    def test_the_dev_override_file_is_no_finding(self):
        """The git-ignored docker-compose.override.yml forge-build build and forge-check test ask for."""
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

    def test_a_file_of_secrets_in_the_folder_must_be_kept_out(self):
        """Review: a line !.env.local let the file back in, and nothing said so. Not for the files a
        profile decides on: .env.production (next and static let in its public build values) and
        npm's and Yarn's logins (only the laravel and django images take the whole folder)."""
        for name in (".env.local", ".env.production.local", "auth.json", "oauth-private.key", "app.p12", "app.pfx",
                     ".env.example", ".env.production", ".npmrc", ".yarnrc.yml", "ca.pem", "monkey", ".env.sample"):
            write(self.dir, name, "x")
        static = ".env\n.env.*\n!.env.example\n!.env.production\n.git\nforge-work/\n"  # as in the templates
        write(self.dir, ".dockerignore", static + "!.env.local\n!.env.sample\n")  # .env.sample: fake values
        self.assertEqual([f["title"] for f in self.check()[0]], [
            ".dockerignore does not keep out .env.local", ".dockerignore does not keep out app.p12",
            ".dockerignore does not keep out app.pfx", ".dockerignore does not keep out auth.json",
            ".dockerignore does not keep out oauth-private.key"])
        write(self.dir, ".dockerignore", static + "auth.json\n*.key\n*.p12\n*.pfx\n")
        self.assertEqual(self.check()[0], [])
        write(self.dir, ".env", "x")  # .env is checked once, also when it is in the folder
        write(self.dir, ".dockerignore", static.replace(".env\n", "", 1) + "auth.json\n*.key\n*.p12\n*.pfx\n")
        self.assertEqual([f["title"] for f in self.check()[0]], [".dockerignore does not keep out .env"])

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


class CopySourceTests(Project):
    """Each COPY and ADD source must reach the image build: in the project folder, let in by the
    ignore file. Otherwise docker compose build stops at that line."""

    def found(self):
        return [(f["rule"], f["title"], f["where"]) for f in self.check()[0]]

    def test_a_missing_file(self):
        write(self.dir, "Dockerfile", in_final_stage("COPY nginx.conf /etc/nginx/conf.d/default.conf"))
        self.assertEqual(self.found(), [("missing", "The image build needs nginx.conf, which is not in the "
                                                    "project folder", "Dockerfile:2")])
        write(self.dir, "nginx.conf", "server {}\n")
        self.assertEqual(self.found(), [])

    def test_each_source_of_each_form(self):
        write(self.dir, "Dockerfile", in_final_stage("COPY app.ini app.conf ./"))
        write(self.dir, "app.ini", "x")
        self.assertEqual([title for _, title, _ in self.found()],
                         ["The image build needs app.conf, which is not in the project folder"])
        for line in ('COPY ["conf/app.ini", "/etc/app/"]', 'COPY --chown=node ["conf/app.ini", "/etc/app/"]',
                     "COPY --chown=node --chmod=644 conf/app.ini /etc/app/", "COPY ./conf/app.ini /etc/",
                     "COPY /conf/app.ini /etc/", "ADD conf /etc/app", "COPY conf/ /etc/app/",
                     "COPY --link conf/app.ini \\\n    /etc/app/"):
            with self.subTest(line=line):
                write(self.dir, "Dockerfile", in_final_stage(line))
                self.assertEqual(rules(self.check()[0]), ["missing"])
                write(self.dir, "conf/app.ini", "x")
                self.assertEqual(self.check()[0], [])
                shutil.rmtree(os.path.join(self.dir, "conf"))

    def test_a_source_the_ignore_file_keeps_out(self):
        write(self.dir, "nginx.conf", "server {}\n")
        write(self.dir, "Dockerfile", in_final_stage("COPY nginx.conf /etc/nginx/conf.d/default.conf"))
        write(self.dir, ".dockerignore", GOOD_IGNORE + "*.conf\n")
        self.assertEqual(self.found(), [("kept_out", "The image build needs nginx.conf, which .dockerignore "
                                                     "keeps out", "Dockerfile:2")])
        write(self.dir, ".dockerignore", GOOD_IGNORE + "*.conf\n!nginx.conf\n")
        self.assertEqual(self.found(), [])
        write(self.dir, "Dockerfile.dockerignore", GOOD_IGNORE + "nginx.conf\n")  # BuildKit uses this one
        self.assertEqual(self.found()[0][1], "The image build needs nginx.conf, which Dockerfile.dockerignore keeps out")

    def test_a_file_of_secrets_is_never_let_in(self):
        """Review: for auth.json or .env.local too, the fix said to let it in with a ! line, and then
        packcheck passed with the secrets in the image. The app reads its secrets at run time, and a
        build gets one through RUN --mount=type=secret."""
        write(self.dir, ".dockerignore", GOOD_IGNORE + ".env.*\n!.env.example\nauth.json\n.npmrc\n.yarnrc.yml\n"
                                                       "*.key\n*.p12\n*.pfx\ndocker/\n")
        for source in (".env", ".env.local", ".env.production", "./auth.json", ".npmrc", ".yarnrc.yml",
                       "oauth-private.key", "app.p12", "app.pfx", "docker/.env.prod"):
            with self.subTest(source=source):
                write(self.dir, source, "x")
                write(self.dir, "Dockerfile", in_final_stage("COPY %s /app/" % source))
                findings = self.check()[0]
                self.assertEqual(self.found(), [("kept_secret", "The image build copies %s, a file of secrets that "
                                                 ".dockerignore keeps out" % source, "Dockerfile:2")])
                self.assertNotIn("!", findings[0]["fix"])
                self.assertIn("RUN --mount=type=secret", findings[0]["fix"])

    def test_a_kept_out_file_that_holds_no_secret_may_be_let_in(self):
        """A CA certificate (.pem) is public; env templates (.env.example, .sample, .dist, .template: as
        secretscan.py reads them) hold fake values only."""
        write(self.dir, ".dockerignore", GOOD_IGNORE + ".env*\n*.pem\n")
        for source in (".env.example", ".env.sample", ".env.dist", ".env.template", ".env.local.example", "ca.pem"):
            with self.subTest(source=source):
                write(self.dir, source, "x")
                write(self.dir, "Dockerfile", in_final_stage("COPY %s /app/" % source))
                findings = self.check()[0]
                self.assertEqual(rules(findings), ["kept_out"])
                self.assertIn("let it in with a line !%s at the end of .dockerignore" % source, findings[0]["fix"])

    def test_a_file_in_a_folder_the_ignore_file_keeps_out(self):
        write(self.dir, "docker/app.ini", "x")
        write(self.dir, "Dockerfile", in_final_stage("COPY docker/app.ini /etc/"))
        write(self.dir, ".dockerignore", GOOD_IGNORE + "docker/\n")
        self.assertEqual(rules(self.check()[0]), ["kept_out"])
        write(self.dir, ".dockerignore", GOOD_IGNORE + "docker/\n!docker/app.ini\n")
        self.assertEqual(self.check()[0], [])
        write(self.dir, ".dockerignore", GOOD_IGNORE + "*.ini\n")  # in Docker, * stays in one folder
        self.assertEqual(self.check()[0], [])

    def test_a_source_outside_the_project_folder(self):
        """It is on disk, but docker builds only from the project folder."""
        write(self.dir, "Dockerfile", in_final_stage("COPY ../%s/Dockerfile /etc/" % os.path.basename(self.dir)))
        self.assertEqual(rules(self.check()[0]), ["missing"])

    def test_the_app_package_files_are_left_to_forge_pack(self):
        """A template on its own has none; forge-build pack Step 3 checks they are committed. Any other file
        is the app's or the container setup's, and is looked up."""
        write(self.dir, "Dockerfile", in_final_stage("COPY package.json package-lock.json composer.json "
                                                     "composer.lock requirements.txt ./"))
        self.assertEqual(self.check()[0], [])
        for line in ("COPY yarn.lock ./", "COPY web/package.json web/", "COPY src ./src"):
            with self.subTest(line=line):
                write(self.dir, "Dockerfile", in_final_stage(line))
                self.assertEqual(rules(self.check()[0]), ["missing"])

    def test_what_cannot_be_looked_up_is_left_alone(self):
        for line in ("COPY --from=build /app/dist /usr/share/nginx/html", "COPY --from=composer:2.10 /usr/bin/composer /bin/",
                     "ADD https://example.com/app.tar.gz /tmp/", "ADD git@example.com:me/app.git /src",
                     "COPY $CONF /etc/", "COPY ${CONF:-app.ini} /etc/", "COPY *.ini /etc/", "COPY conf/?.ini /etc/",
                     "COPY . .", "COPY ./ /app/", "COPY <<EOF /etc/app.ini\nkey=1\nEOF", "ONBUILD COPY app.ini /etc/",
                     "# forge:allow the CI job builds dist/ first\nCOPY dist/ /usr/share/nginx/html/"):
            with self.subTest(line=line):
                write(self.dir, "Dockerfile", in_final_stage(line))
                self.assertEqual(self.check()[0], [])


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
            symlink(self, write(outside, "Dockerfile", GOOD_DOCKERFILE), os.path.join(self.dir, "Dockerfile"))
            self.assertEqual(run(self.dir)[0], 2)
        os.remove(os.path.join(self.dir, "Dockerfile"))  # the pack's own template: on the Windows runners on D:,
        template = os.path.join(ROOT, "forge-build", "templates", "static", "Dockerfile")  # the temp folder on C:
        symlink(self, template, os.path.join(self.dir, "Dockerfile"))
        with self.assertRaisesRegex(ValueError, "^Dockerfile is a link to a file outside "):
            mod.check_project(self.dir)
        os.remove(os.path.join(self.dir, "Dockerfile"))
        write(self.dir, "docker/Dockerfile", GOOD_DOCKERFILE)
        symlink(self, os.path.join("docker", "Dockerfile"), os.path.join(self.dir, "Dockerfile"))
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


class ConsoleTests(Project):
    def test_a_cp1252_pipe_gets_escapes_not_a_crash(self):
        """Windows pipes are cp1252 (no arrow): the arrow prints as \\u2192, no crash."""
        write(self.dir, "docker-compose.yml", GOOD_COMPOSE + "  caf\u00e9-\u2192:\n    image: busybox:1.37\n"
              "    privileged: true\n    restart: unless-stopped\n")
        code, out, err = run_cp1252(mod.__file__, self.dir)
        self.assertEqual(code, 1, err)
        self.assertIn("Service caf\u00e9-\\u2192 runs privileged", out)  # composecheck's words, through packcheck

    def test_composecheck_is_read_in_the_encoding_it_writes(self):
        """packcheck.py asks composecheck.py for UTF-8 and reads it so: before, it read the pipe in its own
        encoding, and composecheck's message in another one crashed it."""
        write(self.dir, "docker-compose.yml", "services:\n  caf\u00e9: {image: busybox:1.37}\n")
        code, out, err = run_cp1252(mod.__file__, self.dir)
        self.assertEqual((code, out), (2, ""), err)
        self.assertIn("error: could not read service caf\u00e9 in docker-compose.yml", err)
        self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
