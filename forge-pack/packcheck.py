#!/usr/bin/env python3
"""Check a project's container setup for settings that make it unsafe or fragile.

Reads the Dockerfile(s) and the ignore file each one uses (Dockerfile.dockerignore before
.dockerignore, as BuildKit does), checks that the files their COPY and ADD lines take from the
project are there and let in, looks for .env.example and runs composecheck.py, next to this script,
on the compose file. Plain line checks, no YAML library. Each finding says what, where, why and how
to fix it, in the words of rules.json next to this script. A real .env file is secretscan.py's job.

Usage:
    python3 packcheck.py .                     check the project in the current folder
    python3 packcheck.py . --json              machine-readable output
    python3 packcheck.py . --fail-on medium    also fail on medium findings

Opt-out: a `# forge:allow` line in a Dockerfile skips the findings of the instruction below it
(above FROM or USER: the root check of that stage); in a compose file, a forge:allow comment on the line.
Limits: only regular files of at most 1 MB in PATH itself are read; heredoc bodies (RUN <<EOF) are
skipped. COPY sources are looked up in PATH (build: .), but not the app's package files (forge-pack
checks they are committed) or those with a variable, a wildcard or a URL, and a file in a folder
only by its folder's ignore line. composecheck.py has its own limits.

Exit codes:
    0  nothing at or above --fail-on (default: high)
    1  at least one finding at or above --fail-on
    2  bad usage, PATH is not a folder, nothing to check, or a file could not be read or checked
"""

import argparse
import fnmatch
import json
import os
import posixpath
import re
import subprocess
import sys

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
MAX_BYTES = 1024 * 1024
COMPOSECHECK = os.path.dirname(os.path.abspath(__file__)) + "/../forge-pack/composecheck.py"
with open(os.path.join(os.path.dirname(COMPOSECHECK), "rules.json"), encoding="utf-8") as rules_file:
    RULES = json.load(rules_file)  # rule: {"severity", "title", "why", "fix"}; {0} {1} {2}: filled in per finding
TIMEOUT = 60  # seconds for composecheck.py
DOCKERFILE = re.compile(r"^(?:Dockerfile|Containerfile)(?:\.(?!dockerignore$)[\w-]+)?$"  # Dockerfile.prod
                        r"|^[\w.-]+\.[Dd]ockerfile$")  # app.Dockerfile
COMPOSE_FILE = re.compile(r"^(?:docker-)?compose(?:\.[\w.-]+)?\.ya?ml$")
# As in secretscan.py, a name that ENDS in a secret word holds a secret: DB_PASSWORD, SMTP_PASS, NPM_TOKEN,
# APP_KEY; TOKEN_URL and DB_PASSWORD_FILE do not. composecheck.py has the same rule (a test keeps them equal).
SECRET_NAME = re.compile(r"(?i)(?:passw(?:or)?d|^pass|[_.-]pass|[_.-]pwd|secret|token"
                         r"|(?:api|app|auth|access|private|secret|encryption|signing|master)[_-]?key)\d*$")
SWITCH_NAME = re.compile(r"(?i)RANDOM|ALLOW_EMPTY")  # MARIADB_RANDOM_ROOT_PASSWORD: a yes/no switch
SWITCH_VALUES = ("", "yes", "no", "true", "false", "on", "off", "null", "~", "0", "1")
FALLBACK = re.compile(r"\$\{\w+:?-([^$}][^}]*)\}")  # ${DB_PASSWORD:-hunter2}: hunter2 is written here
FILE_PATH = re.compile(r"^\.?/[\w.-]+(?:/[\w.-]+)+$")  # /run/secrets/db says where a secret is
HEREDOC = re.compile(r"""(?:^|\s)\d*<<-?(["']?)([A-Za-z_][\w-]*)\1""")  # RUN <<EOF, COPY <<'EOF' /x
KEEP_OUT = ((".env", ".env"), (".git", ".git"), ("forge-work", "forge-work/"))  # (name, as shown)
# Files of secrets: never let in, and kept out when they are in PATH. BY_PROFILE is the profile's call: next and
# static let in .env.production (public build values); only laravel's and django's images take all of PATH.
SECRET_FILE = re.compile(r"^(?:\.env(?:\..+(?<!\.example)(?<!\.sample)(?<!\.dist)(?<!\.template))?|auth\.json"
                         r"|\.npmrc|\.yarnrc\.yml|.*\.(?i:key|p12|pfx))$")  # env templates as in secretscan.py
BY_PROFILE = {".env.production", ".npmrc", ".yarnrc.yml"}
NOT_LOOKED_UP = re.compile(r"[$*?\[]|^<<|://|^git@")  # a variable, a wildcard, a heredoc or a URL
# The app's own package files, which a template on its own lacks: forge-pack checks they are committed.
APP_FILES = {"package.json", "package-lock.json", "composer.json", "composer.lock", "requirements.txt"}


def finding(rule, path, line, *words):
    """One finding: RULE's words with WORDS filled in. LINE 0: about a whole file or the project."""
    found = {key: text.format(*words) for key, text in RULES[rule].items()}  # severity, title, why, fix
    return dict(found, where="%s:%d" % (path, line) if line else path, rule=rule, file=path, line=line)


def unquote(text):
    return text.strip().strip("'\"").strip()


def is_written_secret(name, value):
    """True for a secret-looking NAME with its value written out. References (${DB_PASSWORD}),
    switches (yes, 1) and file paths are fine; the fallback in ${DB_PASSWORD:-hunter2} is not."""
    value = unquote(value)
    if not SECRET_NAME.search(name) or SWITCH_NAME.search(name):
        return False
    reference = (value.startswith("$") or "${" in value) and not FALLBACK.search(value)
    return not (reference or value.lower() in SWITCH_VALUES or FILE_PATH.match(value))


def is_pinned(image):
    """True for an image with a version tag or a digest, a variable, or scratch. node:24 yes;
    node, node:latest and localhost:5000/app no."""
    tag = image.rsplit("/", 1)[-1].partition(":")[2]  # localhost:5000/node:24 -> 24
    return tag not in ("", "latest") or "@" in image or "$" in image or image in ("", "scratch")


def instructions(text):
    """[(line number, INSTRUCTION, arguments, allowed)] of a Dockerfile. Lines ending in \\ are
    joined and heredoc bodies are skipped. ALLOWED: a comment line above it says forge:allow."""
    found, parts, heredoc_ends = [], [], []
    start, allowed = None, False  # the first line of the instruction being read, and its opt-out
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if heredoc_ends:  # inside RUN <<EOF: skip lines up to the one that is just EOF
            if line == heredoc_ends[0]:
                heredoc_ends.pop(0)
            continue
        if not line or line.startswith("#"):
            allowed = allowed or "forge:allow" in line
            continue
        start = start or number
        parts.append(line.rstrip("\\"))
        if line.endswith("\\"):
            continue
        words = " ".join(parts).split(None, 1) + [""]
        keyword, args = words[0].upper(), words[1].strip()
        found.append((start, keyword, args, allowed))
        if keyword in ("RUN", "COPY", "ADD") and not args.startswith("["):  # the exec form has none
            heredoc_ends = [match.group(2) for match in HEREDOC.finditer(args)]
        parts, start, allowed = [], None, False
    return found


def env_pairs(args):
    """(name, value) pairs of ENV A=1 B="two c", ARG A=1, ARG A and the old form ENV A 1."""
    words = args.split(None, 1) + ["", ""]
    if "=" not in words[0]:
        return [(words[0], words[1])] if words[0] else []
    return re.findall(r"([\w.-]+)=(\"[^\"]*\"|'[^']*'|\S*)", args)


def copy_sources(args):
    """The sources of COPY or ADD ARGS: each word but the options and the destination (the last)."""
    args = re.sub(r"^(?:--\S+\s+)+", "", args)  # --chown=node --link
    words = re.findall(r'"([^"]*)"', args) if args.startswith("[") else args.split()
    return words[:-1]


def copies_everything(args):
    """True when the sources of COPY or ADD ARGS are the whole build folder: . ./ / * ./* .*"""
    bare = [re.sub(r"^(?:\.?/)+", "", source).rstrip("/") for source in copy_sources(args)]  # ./* -> *
    return any(name in ("", ".") or ("*" in name and fnmatch.fnmatchcase(".env", name)) for name in bare)


def check_dockerfile(text, path, targets=(), has_ignore=True):
    """(findings, has a HEALTHCHECK, [(line, COPY or ADD, source)]) for one Dockerfile. TARGETS: the
    stages compose builds. The last stage and each target must end with a USER that is not root."""
    findings, stages, healthcheck, sources = [], [], False, []
    for line, instruction, args, allowed in instructions(text):
        if instruction == "FROM":
            words = [word for word in args.split() if not word.startswith("--")] + ["", "", ""]
            image = words[0]
            name = words[2].lower() if words[1].lower() == "as" else None  # FROM node:24 AS build
            parent = [stage for stage in stages if stage["name"] == image.lower()]
            if not (parent or allowed or is_pinned(image)):
                findings.append(finding("tag", path, line, image))
            user = parent[-1]["user"] if parent else ""  # FROM base: the user of stage base
            stages.append({"name": name, "line": line, "user": user, "allowed": allowed})
        elif instruction == "USER" and stages:
            stages[-1]["user"] = unquote((args.split() or [""])[0])  # USER "root" is root too
            stages[-1]["allowed"] = stages[-1]["allowed"] or allowed
        elif instruction in ("ENV", "ARG") and not allowed:
            findings += [finding("env_secret", path, line, instruction, name)
                         for name, value in env_pairs(args) if is_written_secret(name, value)]
        elif instruction in ("COPY", "ADD") and not (allowed or "--from" in args):
            sources += [(line, instruction, source) for source in copy_sources(args)]
            if not has_ignore and copies_everything(args):
                findings.append(finding("copy_all", path, line, instruction))
        elif instruction == "HEALTHCHECK" and not args.upper().startswith("NONE"):
            healthcheck = True
    for index, stage in enumerate(stages):
        final = index == len(stages) - 1 or stage["name"] in targets
        if final and not stage["allowed"] and stage["user"].split(":")[0] in ("", "root", "0"):
            findings.append(finding("root", path, stage["line"]))
    return findings, healthcheck, sources


def is_ignored(patterns, name):
    """True when .dockerignore PATTERNS keep the top-level NAME out of the build. As in Docker, the
    last matching line wins, and a line with ! brings it back, or a part of it (!forge-work/a.md)."""
    ignored = False
    for pattern in patterns:
        path = re.sub(r"^(?:\./|/|\*\*/)+", "", pattern.lstrip("!"))  # /.env ./.env **/.env -> .env
        path = re.sub(r"(?:/\*\*|/\*|/)+$", "", path)  # forge-work/ forge-work/** -> forge-work
        if not path:
            continue
        if pattern.startswith("!") and fnmatch.fnmatchcase(name, path.split("/")[0]):
            ignored = False
        elif not pattern.startswith("!") and fnmatch.fnmatchcase(name, path):
            ignored = True
    return ignored


def read(root, name):
    """The text of ROOT/NAME: a regular file of at most 1 MB inside ROOT. A BOM is dropped."""
    path, real_root = os.path.join(root, name), os.path.realpath(root)
    real = os.path.realpath(path)
    elsewhere = os.path.splitdrive(real)[0] != os.path.splitdrive(real_root)[0]  # on another drive (Windows)
    if elsewhere or os.path.commonpath([real, real_root]) != real_root:  # commonpath() fails across drives
        raise ValueError("%s is a link to a file outside %s" % (name, root))
    if not os.path.isfile(path) or os.path.getsize(path) > MAX_BYTES:
        raise ValueError("%s is not a regular file of at most 1 MB" % name)
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        return handle.read()


def check_compose(root):
    """composecheck.py's JSON report on ROOT. Raises ValueError when it could not check the files."""
    done = subprocess.run([sys.executable, COMPOSECHECK, root, "--json", "--fail-on", "critical"], timeout=TIMEOUT,
                          capture_output=True, encoding="utf-8", errors="replace",  # asked for UTF-8, read as
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))  # such: Windows pipes are cp1252
    if done.returncode not in (0, 1) or not done.stdout.startswith("{"):
        lines = done.stderr.strip().splitlines() or ["composecheck.py gave no report"]
        raise ValueError(lines[-1].replace("error: ", "", 1))
    return json.loads(done.stdout)


def check_project(root):
    """(findings sorted most severe first, files checked). Raises OSError or ValueError when a file
    cannot be read or checked, or when there is nothing to check."""
    names = sorted(os.listdir(root))
    findings, checked, ignores = [], [], {}  # ignores: {ignore file: its patterns}
    targets, healthcheck = set(), False
    if any(COMPOSE_FILE.match(name) for name in names):
        report = check_compose(root)
        findings += report["findings"]
        checked += report["summary"]["checked"]
        healthcheck = report["summary"]["healthcheck"]
        targets = set(report["summary"]["targets"])
    for name in [name for name in names if DOCKERFILE.match(name)]:
        ignore = next((n for n in (name + ".dockerignore", ".dockerignore") if n in names), None)  # BuildKit's order
        if ignore and ignore not in ignores:
            ignores[ignore] = [line.strip() for line in read(root, ignore).splitlines()
                               if line.strip() and not line.strip().startswith("#")]
        found, has_check, sources = check_dockerfile(read(root, name), name, targets, ignore is not None)
        findings += found
        for line, word, source in sources:  # word: COPY or ADD. Must reach the build, or it stops there.
            path = posixpath.normpath(source).lstrip("/")  # ./a -> a, /a -> a, a/../../b -> ../b
            if NOT_LOOKED_UP.search(source) or path in ("", ".") or path in APP_FILES:
                continue
            if path.split("/")[0] == ".." or not os.path.exists(os.path.join(root, path)):  # .. is outside
                findings.append(finding("missing", name, line, word, source, ignore))
            elif is_ignored(ignores.get(ignore, []), path.split("/")[0]):  # a folder by the folder's line
                secret = SECRET_FILE.match(posixpath.basename(path))  # kept_secret never says to let it in
                findings.append(finding("kept_secret" if secret else "kept_out", name, line, word, source, ignore))
        healthcheck = healthcheck or has_check
        checked.append(name)
    if not checked:
        raise ValueError("nothing to check: no Dockerfile or compose file in " + root)
    keep_out = dict(KEEP_OUT + tuple((n, n) for n in names if SECRET_FILE.match(n) and n not in BY_PROFILE))
    for ignore in sorted(ignores):  # KEEP_OUT and each file of secrets in ROOT (a dict: .env only once)
        findings += [finding("ignore", ignore, 0, shown, ignore) for name, shown in keep_out.items()
                     if not is_ignored(ignores[ignore], name)]
        checked.append(ignore)
    if not healthcheck:
        findings.append(finding("no_health", "the Dockerfile and the compose file", 0))
    if ".env.example" in names:
        checked.append(".env.example")
    else:
        findings.append(finding("no_example", "the project folder", 0))
    findings.sort(key=lambda f: SEVERITIES.index(f["severity"]))
    return findings, checked


def format_human(findings, summary):
    lines = []
    for f in findings:
        lines += ["%-8s  %s" % (f["severity"].upper(), f["title"]), "          where: " + f["where"],
                  "          why:   " + f["why"], "          fix:   " + f["fix"], ""]
    counts = ", ".join("%d %s" % (summary[sev], sev) for sev in SEVERITIES if summary[sev])
    noun = "finding" if len(findings) == 1 else "findings"
    lines.append("Checked: %s." % ", ".join(summary["checked"]))
    lines.append("%d %s: %s." % (len(findings), noun, counts) if findings else "No findings.")
    lines.append(("FAIL: at least one finding is %s or worse." if summary["failed"]
                  else "PASS: nothing is %s or worse.") % summary["fail_on"])
    return "\n".join(lines)


def main(argv=None):
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: escapes, no crash
    parser = argparse.ArgumentParser(description="Check a project's container setup for unsafe settings.")
    parser.add_argument("path", help="the project folder")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high",
                        help="exit 1 when a finding is this bad or worse (default: high)")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.path):
        print("error: %s is not a folder that exists" % args.path, file=sys.stderr)
        return 2
    try:
        findings, checked = check_project(args.path)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    too_bad = any(SEVERITIES.index(f["severity"]) <= SEVERITIES.index(args.fail_on) for f in findings)
    summary = {sev: len([f for f in findings if f["severity"] == sev]) for sev in SEVERITIES}
    summary.update(total=len(findings), checked=checked, fail_on=args.fail_on, failed=too_bad)
    print(json.dumps({"findings": findings, "summary": summary}, indent=2) if args.json
          else format_human(findings, summary))
    return 1 if too_bad else 0


if __name__ == "__main__":
    sys.exit(main())
