#!/usr/bin/env python3
"""Check a project's container setup for settings that make it unsafe or fragile.

Reads the Dockerfile(s) and the ignore file each one uses (Dockerfile.dockerignore before
.dockerignore, as BuildKit does), looks for .env.example and runs composecheck.py, next to this
script, on the compose file. Plain line checks, no YAML library. Each finding says what, where, why
and how to fix it: see RULES below. A real .env file in the project is secretscan.py's job.

Usage:
    python3 packcheck.py .                     check the project in the current folder
    python3 packcheck.py . --json              machine-readable output
    python3 packcheck.py . --fail-on medium    also fail on medium findings

Opt-out: a `# forge:allow` line in a Dockerfile skips the findings of the instruction below it
(above FROM or USER: the root check of that stage); in a compose file, a forge:allow comment on the line.
Limits: only regular files of at most 1 MB in PATH itself are read; heredoc bodies (RUN <<EOF) are
skipped. composecheck.py lists its own limits.

Exit codes:
    0  nothing at or above --fail-on (default: high)
    1  at least one finding at or above --fail-on
    2  bad usage, PATH is not a folder, nothing to check, or a file could not be read or checked
"""

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
MAX_BYTES = 1024 * 1024
COMPOSECHECK = os.path.dirname(os.path.abspath(__file__)) + "/../forge-pack/composecheck.py"
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

# rule: (severity, title, why, fix). {0} and {1} are filled in per finding.
RULES = {
    "env_secret": ("critical", "{0} {1} has a secret written in the Dockerfile", "it is stored in the image, "
                   "for anyone who can pull it", "remove the value: the app gets it at run time from env_file: "
                   ".env; a secret the build needs goes in with RUN --mount=type=secret"),
    "root": ("high", "The image runs as root", "if someone breaks into the app, they are root in the container",
             "end this stage with a USER line for an unprivileged user, for example USER www-data"),
    "copy_all": ("high", "{0} copies the whole folder and there is no .dockerignore",
                 "the image gets .env, .git and forge-work/ too",
                 "add a .dockerignore that lists .env, .git and forge-work/"),
    "ignore": ("high", "{1} does not keep out {0}",
               "a COPY of the folder puts it in the image, for anyone who has the image to read",
               "add a line {0} to {1}"),
    "tag": ("medium", "Base image {0} is not pinned to a version",
            "the image can change under you and break a build that worked",
            "pin a version, at least major.minor, for example node:24-alpine"),
    "no_example": ("medium", "No .env.example", "whoever runs the app cannot tell which settings it needs",
                   "add .env.example with every name from .env and fake values"),
    "no_health": ("low", "No healthcheck",
                  "nobody sees that the app is stuck, and depends_on cannot wait until it is ready",
                  "add a healthcheck: to the app service that requests its health URL"),
}


def finding(rule, path, line, *words):
    """One finding. LINE is 0 when it is about a whole file or the project."""
    severity, title, why, fix = RULES[rule]
    where = "%s:%d" % (path, line) if line else path
    return {"severity": severity, "title": title.format(*words), "where": where, "why": why,
            "fix": fix.format(*words), "rule": rule, "file": path, "line": line}


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


def copies_everything(args):
    """True when the sources of COPY or ADD ARGS are the whole build folder: . ./ / * ./* .*"""
    sources = re.findall(r'"([^"]*)"', args) if args.startswith("[") else args.split()
    for source in sources[:-1]:  # the last one is the destination
        bare = re.sub(r"^(?:\.?/)+", "", source).rstrip("/")  # ./. -> .   ./* -> *   / -> ''
        if bare in ("", ".") or ("*" in bare and fnmatch.fnmatchcase(".env", bare)):
            return True
    return False


def check_dockerfile(text, path, targets=(), has_ignore=True):
    """(findings, has a HEALTHCHECK) for one Dockerfile. TARGETS: the stages compose builds.
    The last stage and each target must end with a USER that is not root."""
    findings, stages, healthcheck = [], [], False
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
        elif instruction in ("COPY", "ADD") and not (allowed or has_ignore or "--from" in args):
            if copies_everything(args):
                findings.append(finding("copy_all", path, line, instruction))
        elif instruction == "HEALTHCHECK" and not args.upper().startswith("NONE"):
            healthcheck = True
    for index, stage in enumerate(stages):
        final = index == len(stages) - 1 or stage["name"] in targets
        if final and not stage["allowed"] and stage["user"].split(":")[0] in ("", "root", "0"):
            findings.append(finding("root", path, stage["line"]))
    return findings, healthcheck


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
    findings, checked, ignore_files = [], [], set()
    targets, healthcheck = set(), False
    if any(COMPOSE_FILE.match(name) for name in names):
        report = check_compose(root)
        findings += report["findings"]
        checked += report["summary"]["checked"]
        healthcheck = report["summary"]["healthcheck"]
        targets = set(report["summary"]["targets"])
    for name in [name for name in names if DOCKERFILE.match(name)]:
        ignore = name + ".dockerignore"  # BuildKit uses this one instead of .dockerignore
        if ignore not in names:
            ignore = ".dockerignore" if ".dockerignore" in names else None
        found, has_check = check_dockerfile(read(root, name), name, targets, ignore is not None)
        findings += found
        healthcheck = healthcheck or has_check
        ignore_files |= {ignore} if ignore else set()
        checked.append(name)
    if not checked:
        raise ValueError("nothing to check: no Dockerfile or compose file in " + root)
    for ignore in sorted(ignore_files):
        patterns = [line.strip() for line in read(root, ignore).splitlines()
                    if line.strip() and not line.strip().startswith("#")]
        findings += [finding("ignore", ignore, 0, shown, ignore) for name, shown in KEEP_OUT
                     if not is_ignored(patterns, name)]
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
