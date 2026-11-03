#!/usr/bin/env python3
"""Find secrets (API keys, passwords, private keys, tokens) in files before they leak.

Scans a file, or every text file under a folder, line by line, and says what, where, why it
matters and how to fix it. Secrets are masked (sk_l****).

Usage:
    python3 secretscan.py .                      scan the current folder
    python3 secretscan.py app/config.php --json  one file, machine-readable output
    python3 secretscan.py . --fail-on critical   fail only on critical findings

Finds keys of Stripe (also webhook secrets), AWS, GitHub, Slack (also webhooks), Google,
SendGrid, Mailgun, OpenAI and Anthropic, private keys, passwords in connection strings
(postgres://user:pass@host) and quoted passwords in code (password = "...",
define('DB_PASSWORD', '...')). A real .env file (.env, .env.local, ...) is high, its lines
are scanned. Two exceptions. One git ignores (so it stays on this machine) is low, and so are
its lines, but a Stripe live key stays critical (forge works in test mode only); no git: high.
One with only public build values (VITE_..., NEXT_PUBLIC_...) is fine, unless a name says
SECRET, PRIVATE or PASSWORD. Skipped: placeholders (changeme, ${DB_PASS}, App\\Rules\\Password),
lines with forge:allow, SKIP_FOLDERS (.git, node_modules, vendor, build and cache folders,
Laravel's generated bootstrap/cache), symlinks, binary files, files over 1 MB.
Not checked: unquoted values, values with spaces, git history.

Exit codes: 0 nothing at or above --fail-on (default: high); 1 at least one finding at or above
it; 2 bad usage, a missing path, or something under it could not be read (incomplete scan).
"""

import argparse
import collections
import errno
import json
import os
import re
import subprocess
import sys

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
MAX_BYTES = 1024 * 1024
SKIP_FOLDERS = {".git", "node_modules", "vendor", "venv", ".venv", "__pycache__", "dist", "build",
                ".next", ".nuxt", "out", "coverage", "storage/framework", ".cache", ".idea", ".vscode",
                "bootstrap/cache"}  # Laravel's generated caches: its own .gitignore keeps them out

Rule = collections.namedtuple("Rule", "severity title pattern why fix")

# Keys with a fixed, recognisable shape. The whole match is the secret.
MAIL = "anyone with it can send email in your name and read your contact lists"
AI_BILL = "anyone with it can run up your bill and read what you stored with the provider"
NEW_KEY = "delete it in %s, make a new one, load it from .env"
KEY_RULES = [
    Rule("critical", "Stripe live secret key", re.compile(r"\b[rs]k_live_[0-9A-Za-z]{10,}"),
         "anyone who reads the code can charge cards and issue refunds on your Stripe account",
         "make a new key in the Stripe dashboard, delete the old one, load the new one from .env"),
    Rule("critical", "AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
         "together with its secret it lets anyone use your Amazon account and run up the bill",
         "switch the key off in the AWS console, make a new one and load it from .env"),
    Rule("critical", "Private key",  # the shown part is the key type (RSA, OPENSSH, ...), masked
         re.compile(r"-----BEGIN (?P<secret>[A-Z0-9 ]*PRIVATE KEY)( BLOCK)?-----"),
         "anyone with it can log in to servers, sign things or decrypt traffic as you",
         "remove it from the code, make a new key pair, revoke the old key wherever it is trusted"),
    Rule("critical", "GitHub token", re.compile(r"\b(?:gh[posu]_\w{30,}|github_pat_\w{22,})"),
         "anyone with it can read and change your repositories, depending on its scopes",
         "revoke it at github.com/settings/tokens, make a new one, load it from .env"),
    Rule("high", "Slack token", re.compile(r"\bxox[abprs]-[0-9]+-[0-9A-Za-z-]{8,}"),
         "anyone with it can read or post messages in your Slack workspace",
         "revoke it in your Slack app settings, make a new one, load it from .env"),
    Rule("high", "Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}"),
         "anyone can use it on your Google Cloud bill unless it is locked to your sites and APIs",
         "lock it to your sites and APIs in the Google Cloud console (or replace it), keep it in .env"),
    Rule("critical", "SendGrid API key", re.compile(r"\bSG\.[\w-]{22}\.[\w-]{43}"), MAIL,
         NEW_KEY % "SendGrid (Settings > API Keys)"),
    Rule("critical", "Mailgun API key", re.compile(r"\bkey-[0-9a-f]{32}\b"), MAIL,
         NEW_KEY % "Mailgun (API Security)"),
    Rule("high", "Stripe webhook secret", re.compile(r"\bwhsec_[0-9A-Za-z]{24,}"),
         "anyone with it can send fake Stripe events, such as a payment, that your app trusts",
         "roll the endpoint's signing secret in Stripe (Webhooks), load the new one from .env"),
    Rule("high", "Slack webhook", re.compile(r"https://hooks\.slack\.com/services/T\w+/B\w+/\w+"),
         "anyone with it can post in your Slack channel", NEW_KEY % "your Slack app settings"),
    Rule("high", "Anthropic API key", re.compile(r"\bsk-ant-[\w-]{20,}"), AI_BILL,
         NEW_KEY % "the Anthropic Console (API keys)"),
    Rule("high", "OpenAI API key", re.compile(r"\bsk-(?:proj-|svcacct-|admin-)?(?=[\w-]{0,200}?\d)"
         r"(?=[\w-]{0,200}?[A-Z])[\w-]{32,}"), AI_BILL,  # random: it has digits and capitals
         NEW_KEY % "the OpenAI dashboard (API keys)"),
    Rule("medium", "Stripe test secret key", re.compile(r"\bsk_test_[0-9A-Za-z]{10,}"),
         "it moves no real money, but it opens your Stripe test data and settings to anyone",
         "load it from .env instead of the code"),
]

# A name that ENDS in one of these words holds a secret: DB_PASSWORD, client_secret, apiKey,
# AUTH_KEY, aws_secret_access_key. Names that only start with one (TOKEN_URL, tokenizer) do not.
SECRET_NAME = (r"(?i:password|passwd|secret|secret[_-]?key|secret[_-]?access[_-]?key"
               r"|api[_-]?key|token|auth[_-]?key)\d*")

# Passwords that can look like anything. Only the (?P<secret>...) part is the secret.
LOOSE_RULES = [
    Rule("high", "Password inside a connection string",  # scheme://user:password@host, but
         re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]{0,30}://[^\s:/@'\"]*:(?P<secret>[^\s:/@'\"]+)"
                    r"@(?!sha\d+:)[^\s/'\"]+"),  # not docker://image:tag@sha256:... (a digest)
         "anyone who reads the code can log in to that database or service",
         "put the whole URL in .env (for example DATABASE_URL) and change the password"),
    Rule("medium", "Password or secret written in the code",
         re.compile(r"(?:\bdefine\(\s*['\"]\w*?" + SECRET_NAME + r"['\"]\s*,"  # define('DB_PASSWORD',
                    r"|" + SECRET_NAME + r"['\"]?\s*"  # or a name, maybe quoted: 'password'
                    r"(?::\s*\w{1,40}\s*)?(?:=>|:=|=|:))"  # then = : => or :=  (password: str = ok)
                    r"""\s*['"](?P<secret>[^'"\s]{8,})['"]"""),  # a quoted value, 8+ chars, no spaces
         "anyone who reads the code learns it, and it stays in git history after you change it",
         "load it from .env or your framework's config, and change it if it was ever committed"),
]

ENV_FILE = Rule("high", "Real .env file in the project", None,
                "it holds real passwords and keys: they leak if git commits it (even once) or if it "
                "is copied into a container image or a zip", "list .env in .gitignore and "
                ".dockerignore; if `git ls-files` lists it, `git rm --cached` it and change its secrets")
LOCAL_ENV_FILE = Rule("low", "Local .env file, ignored by git", None,
                      "fine on this machine; it must never be committed, shared or put in an image",
                      "keep .env in .gitignore and .dockerignore; never paste what is in it")
PUBLIC_SECRET = Rule("high", "Secret-looking name in public build settings",
                     re.compile(r"^\s*(?:export\s+)?(?:VITE|NEXT_PUBLIC)_\w*(?i:secret|private|passw)"),
                     "VITE_ and NEXT_PUBLIC_ values go into the JavaScript every visitor downloads",
                     "keep secrets out of the browser: use them in server code, without that prefix")
PUBLIC_NAME = re.compile(r"^\s*(?:export\s+)?(?:VITE|NEXT_PUBLIC)_\w*\s*=")

# A real key is random, so only clear fakes are skipped: AKIAIOSFODNN7EXAMPLE, sk_live_yourkey...
KEY_PLACEHOLDER_WORDS = ("example", "placeholder", "xxxxxx", "yours", "your_", "your-")
PLACEHOLDER_VALUES = {"password", "passwd", "pass", "secret", "token", "null", "none"}
# A password-like value that matches this is a placeholder or a reference, not a secret.
PLACEHOLDER = re.compile(r"""
      ^<.*>$ | ^\{.*\}$ | ^\$\{.*\}$ | ^\$[A-Z_][A-Z0-9_]*$   # <pw>  {pw}  ${DB_PASS}  $DB_PASS
    | ^%s$ | ^%\(\w+\)s$ | ://                     # format strings; URLs (checked by the rule above)
    | env\( | getenv | process\.env | os\.environ    # code that reads the environment
    | ^(?:bail|required|nullable|sometimes|string|confirmed)\|   # Laravel rules: required|min:8
    | ^\\{0,2}(?:[A-Za-z_]\w*\\{1,2})+[A-Za-z_]\w*$     # a PHP class name: App\\Rules\\Password
    | (?i: your[-_] | changeme | change[-_]me | example | placeholder | xxx )
""", re.VERBOSE)

def is_placeholder(rule, value):
    """True for values that are clearly not real: 'changeme', '${DB_PASS}', '<password>', '****'."""
    low = value.lower()
    if rule in KEY_RULES:
        return any(word in low for word in KEY_PLACEHOLDER_WORDS)
    return low in PLACEHOLDER_VALUES or len(set(low)) == 1 or PLACEHOLDER.search(value) is not None

def scan_line(line):
    """Return (rule, secret) pairs for one line. Every rule runs; text already reported by one
    rule (a Stripe key assigned to api_key) is not reported again by another."""
    if "forge:allow" in line:  # the user's opt-out for this line
        return []
    hits, taken = [], []  # taken: (start, end) of each secret already reported
    for rule in KEY_RULES + LOOSE_RULES:
        part = "secret" if "secret" in rule.pattern.groupindex else 0  # 0 = the whole match
        for match in rule.pattern.finditer(line):
            start, end = match.span(part)
            seen = any(start < old_end and old_start < end for old_start, old_end in taken)
            if not seen and not is_placeholder(rule, match.group(part)):
                hits.append((rule, match.group(part)))
                taken.append((start, end))
    return hits

def make_finding(rule, path, line=None, secret=None):
    """One finding. The secret is masked: first 4 characters (fewer if it is short), then ****."""
    where = path if line is None else "%s:%d" % (path, line)
    masked = secret[:min(4, len(secret) // 3)] + "****" if secret else None
    return {"severity": rule.severity, "title": rule.title, "where": where, "why": rule.why,
            "fix": rule.fix, "file": path, "line": line, "match": masked}

def scan_text(text, path):
    """Scan the text of one file. Pure: no file access, so tests can call it directly."""
    return [make_finding(rule, path, number, secret)  # any line ending: \r\n, \r or \n
            for number, line in enumerate(re.split(r"\r\n|\r|\n", text), start=1)
            for rule, secret in scan_line(line)]

def is_real_env_file(name):
    """'.env' and '.env.local' are real; '.env.example', '.env.sample' etc. are templates."""
    is_env = name == ".env" or name.startswith(".env.")
    return is_env and name.rsplit(".", 1)[-1] not in ("example", "sample", "dist", "template")

def only_public_values(lines):
    """True when every setting in an env file is a VITE_ or NEXT_PUBLIC_ build value."""
    settings = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
    return bool(settings) and all(PUBLIC_NAME.match(line) for line in settings)

def git_ignores(file_path):
    """True when git ignores this file and does not track it (git check-ignore says so).
    False when git is missing, the folder is not a repository, or git says no."""
    folder, name = os.path.split(os.path.abspath(file_path))
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    try:  # no GIT_DIR and the like from outside, and no fsmonitor program from the repo's config
        done = subprocess.run(["git", "-c", "core.fsmonitor=false", "check-ignore", "-q", "--", name],
                              cwd=folder, env=env, timeout=20, stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0

def env_file_findings(text, path):
    """Findings for a real .env file and its lines (see the top of this file)."""
    lines = re.split(r"\r\n|\r|\n", text)
    if only_public_values(lines):
        return scan_text(text, path) + [
            make_finding(PUBLIC_SECRET, path, number) for number, line in enumerate(lines, start=1)
            if PUBLIC_SECRET.pattern.match(line) and "forge:allow" not in line]
    if not git_ignores(path):
        return [make_finding(ENV_FILE, path)] + scan_text(text, path)
    found = [make_finding(LOCAL_ENV_FILE, path)]
    for finding in scan_text(text, path):
        if finding["title"] != "Stripe live secret key":  # forge never runs with live keys
            finding.update(severity="low", title=finding["title"] + ", in the git-ignored .env",
                           fix="nothing while .env stays git-ignored; change it if it was ever shared")
        found.append(finding)
    return found

def files_under(folder, unreadable):
    """Yield every regular file under FOLDER, minus skipped folders and symlinks.
    Folders that cannot be opened are added to the unreadable list."""
    to_visit = [folder]
    while to_visit:  # a to-do list instead of recursion, so very deep trees work on Python 3.9
        folder = to_visit.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError:
            unreadable.append(folder)
            continue
        parent = os.path.basename(os.path.normpath(folder))  # for 'storage/framework'
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                if entry.name not in SKIP_FOLDERS and parent + "/" + entry.name not in SKIP_FOLDERS:
                    to_visit.append(entry.path)
            elif entry.is_file(follow_symlinks=False):
                yield entry.path

def scan_path(path):
    """Scan a file or folder. Returns (findings sorted most severe first, stats): how many files
    were checked, how many were skipped (binary or over 1 MB) and which could not be read."""
    findings, unreadable, checked, skipped = [], [], 0, 0
    for file_path in files_under(path, unreadable) if os.path.isdir(path) else [path]:
        real_env = is_real_env_file(os.path.basename(file_path))
        try:
            with open(file_path, "rb") as handle:
                data = handle.read(MAX_BYTES + 1)
        except OSError:
            unreadable.append(file_path)
            continue
        if len(data) > MAX_BYTES or b"\0" in data[:8192]:  # too big, or binary (a NUL byte)
            skipped += 1
            findings += [make_finding(ENV_FILE, file_path)] if real_env else []
            continue
        checked += 1
        text = data.decode("utf-8", errors="replace")
        findings.extend(env_file_findings(text, file_path) if real_env else scan_text(text, file_path))
    findings.sort(key=lambda f: (SEVERITIES.index(f["severity"]), f["file"], f["line"] or 0))
    return findings, {"files_checked": checked, "files_skipped": skipped,
                      "unreadable": sorted(unreadable)}

def format_human(findings, summary):
    """The plain-text report: one block per finding, then what was checked and the verdict."""
    lines = []
    for f in findings:
        found = ["          found: " + f["match"]] if f["match"] else []
        lines += ["%-8s  %s" % (f["severity"].upper(), f["title"]), "          where: " + f["where"]]
        lines += found + ["          why:   " + f["why"], "          fix:   " + f["fix"], ""]
    counts = ", ".join("%d %s" % (summary[sev], sev) for sev in SEVERITIES if summary[sev])
    noun = "finding" if len(findings) == 1 else "findings"
    result = "%d %s: %s." % (len(findings), noun, counts) if findings else "No findings."
    skipped = ", skipped: %d (binary or over 1 MB)" % summary["files_skipped"] if summary["files_skipped"] else ""
    lines.append("Files checked: %d%s. %s" % (summary["files_checked"], skipped, result))
    if summary["unreadable"]:
        lines.append("INCOMPLETE, so not a pass. Could not read: " + ", ".join(summary["unreadable"]))
    elif summary["failed"]:
        lines.append("FAIL: at least one finding is %s or worse." % summary["fail_on"])
    else:
        lines.append("PASS: nothing is %s or worse." % summary["fail_on"])
    # A file name with bytes that are not UTF-8 prints as \udce9 instead of crashing the output.
    return "\n".join(lines).encode("utf-8", "backslashreplace").decode("utf-8")

def main(argv=None):
    """Run the scan from the command line. Returns the exit code: 0, 1 or 2 (see the top)."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: escapes, no crash
    parser = argparse.ArgumentParser(description="Find secrets (keys, passwords, tokens) in files.")
    parser.add_argument("path", help="file or folder to scan")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high",
                        help="exit 1 when a finding is this bad or worse (default: high)")
    args = parser.parse_args(argv)
    if not (os.path.isfile(args.path) or os.path.isdir(args.path)):
        print("error: %s is not a file or folder that exists" % args.path, file=sys.stderr)
        return 2
    findings, stats = scan_path(args.path)
    too_bad = any(SEVERITIES.index(f["severity"]) <= SEVERITIES.index(args.fail_on) for f in findings)
    summary = {sev: len([f for f in findings if f["severity"] == sev]) for sev in SEVERITIES}
    summary.update(stats, total=len(findings), fail_on=args.fail_on, failed=too_bad or bool(stats["unreadable"]))
    try:
        print(json.dumps({"findings": findings, "summary": summary}, indent=2) if args.json
              else format_human(findings, summary), flush=True)
    except OSError as error:  # the reader stopped early (| head): end quietly, no traceback
        if error.errno not in (errno.EPIPE, errno.EINVAL):  # EINVAL: what Windows says there
            raise
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    return 2 if stats["unreadable"] else 1 if too_bad else 0  # 2: some files were never read

if __name__ == "__main__":
    sys.exit(main())
