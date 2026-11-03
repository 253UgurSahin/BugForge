#!/usr/bin/env python3
"""Check an app's dependencies for known security holes with npm audit, composer audit and
pip-audit (if installed; they look packages up online), each in an empty temp folder with copies
of only the files it needs, so a project's .npmrc or composer.json cannot redirect it or leak
tokens. pip-audit installs nothing. forge:allow does not apply: note accepted risks in security.md.

Usage:
    python3 deps.py .                     check every project under this folder
    python3 deps.py . --json --strict     JSON; also fail when something was not checked
    python3 deps.py . --fail-on critical  fail only on critical findings

Exit codes: 0 = nothing at or above --fail-on (default: high); 1 = a finding at or above it,
or with --strict anything not checked; 2 = PATH is not a folder that exists and can be read.
"""

import argparse
import errno
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from textwrap import shorten

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
SEVERITY_WORDS = {"critical": "critical", "high": "high", "moderate": "medium",
                  "medium": "medium", "low": "low", "info": "low"}  # npm's and Composer's words
TIMEOUT = 180  # seconds per auditor run
TASKKILL = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "taskkill.exe")  # by full path
BATCH_UNSAFE = re.compile(r'["%!^&|<>()\r\n]')  # what cmd.exe acts on in a .bat or .cmd file's arguments
SKIP_FOLDERS = set(".git node_modules vendor venv .venv __pycache__ dist build .next .nuxt out"
                   " coverage storage/framework .cache .idea .vscode".split())
NPM = ["npm", "audit", "--json", "--registry=https://registry.npmjs.org/"]
COMPOSER = ["composer", "audit", "--format=json", "--locked", "--no-plugins", "--no-scripts"]
PIP_AUDIT = ["pip-audit", "--no-deps", "--disable-pip", "-f", "json", "-r"]  # + the file
INSTALL = {"npm": "install Node.js (nodejs.org)", "composer": "install Composer (getcomposer.org)",
           "pip-audit": 'install it with "pipx install pip-audit"'}
NOTES = {"yarn.lock": 'Yarn is not run here: run "yarn npm audit" (or "yarn audit") in that folder',
         "pnpm-lock.yaml": 'pnpm is not run here: run "pnpm audit" in that folder'}
EXPORT = {"poetry.lock": "poetry export -f requirements.txt -o requirements.txt",
          "Pipfile.lock": "pipenv requirements > requirements.txt",
          "pyproject.toml": "pip-compile -o requirements.txt pyproject.toml"}  # first one found
WHY = 'this app uses a version of "%s" with publicly known security holes; attackers look for these'
UPGRADE = "upgrade %s to its latest version in the requirements file (fixes came out in %s)"
NO_LOCK = "A package.json or composer.json alone cannot be checked: create its lockfile first."
NO_FIX = "no fixed version of %s yet: read the advisory for a workaround, or replace it"
MAJOR = "update %s to %s in package.json; it is a new major version, so test the app well afterwards"
OLDER = ('npm\'s only fix is an older version of %s (%s, you have %s): do not run "npm audit fix'
         ' --force"; wait for a new release, or replace it')
DEV_ONLY = "; only dev tools use it, so it does not run in the production app"

def version_key(version):
    """'1.10.2' as [1, 10, 2], so versions sort as numbers."""
    return [int(number) for number in re.findall(r"\d+", str(version))]

def make_finding(kind, package, holes, fix, version=None):
    """One finding per package, as bad as its worst hole. HOLES: (severity, text, link) each."""
    unique = {hole[2] or hole[1]: hole for hole in holes}  # one per advisory link, else title
    holes = sorted(unique.values(), key=lambda hole: SEVERITIES.index(hole[0]))
    texts = [shorten(str(text).strip().rstrip("."), 100, placeholder="...") for _, text, _ in holes]
    texts = list(dict.fromkeys(texts))  # two advisories with the same title: shown once
    links = list(dict.fromkeys(link for _, _, link in holes if link))
    count = "Known vulnerability" if len(holes) == 1 else "%d known vulnerabilities" % len(holes)
    title = '%s in %s package "%s" %s' % (count, kind, package, version or "")
    return {"severity": holes[0][0], "title": title.strip(), "why": WHY % package, "fix": fix,
            "holes": "; ".join(texts[:3]), "more": links[0] if links else "",  # JSON has all
            "package": package, "version": version, "advisories": texts, "links": links}

def parse_npm(text, lock=None):
    """Pure: `npm audit --json` text (and the parsed package-lock.json) in, (findings, skipped) out.
    The lockfile tells the installed version and whether only dev tools use a package."""
    packages = lock.get("packages") if isinstance(lock, dict) else None
    packages = packages if isinstance(packages, dict) else {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("no vulnerability list")
    if not isinstance(data.get("vulnerabilities"), dict):  # npm says why in error or message
        error = data["error"] if isinstance(data.get("error"), dict) else {}
        raise ValueError(str(error.get("summary") or data.get("message") or "needs npm 7 or newer"))
    findings = []
    for package, vuln in sorted(data["vulnerabilities"].items()):
        advisories = [item for item in vuln.get("via") or [] if isinstance(item, dict)]
        if vuln.get("via") and not advisories:
            continue  # only listed because it uses a vulnerable package, which gets the finding
        holes = [(SEVERITY_WORDS.get(a.get("severity") or vuln.get("severity"), "high"),
                  a.get("title") or "unnamed advisory", a.get("url")) for a in advisories or [{}]]
        fix = vuln.get("fixAvailable")  # true, false, or {name, version, isSemVerMajor}
        advice = 'run "npm audit fix" in that folder and test the app' if fix else NO_FIX % package
        if isinstance(fix, dict) and fix.get("isSemVerMajor"):  # "npm audit fix" leaves these
            name, new = fix.get("name"), fix.get("version")
            have = (packages.get("node_modules/%s" % name) or {}).get("version")
            older = have and new and version_key(new) < version_key(have)  # npm can offer a downgrade
            advice = OLDER % (name, new, have) if older else MAJOR % (name, new)
        finding = make_finding("npm", package, holes, advice)
        nodes = [packages.get(node) or {} for node in vuln.get("nodes") or []]
        if nodes and all(node.get("dev") for node in nodes):  # every copy is for dev tools only
            finding["why"] += DEV_ONLY
        findings.append(finding)
    return findings, []

def parse_composer(text):
    """Pure: `composer audit --format=json` text in, (findings, skipped) out."""
    data = json.loads(text)
    if not isinstance(data, dict) or "advisories" not in data:
        raise ValueError("no advisory list")
    findings = []
    for package, advisories in sorted((data["advisories"] or {}).items()):  # PHP: [] for none
        if isinstance(advisories, dict):  # PHP prints a list with gaps as {"1": .., "3": ..}
            advisories = list(advisories.values())
        holes = [(SEVERITY_WORDS.get(a.get("severity"), "high"), a.get("title") or a.get("cve")
                  or "unnamed advisory", a.get("link")) for a in advisories]
        fix = 'run "composer update %s" in that folder, then test the app' % package
        findings.append(make_finding("Composer", package, holes, fix))
    return findings, []

def parse_pip_audit(text):
    """Pure: `pip-audit -f json` text in, (findings, skipped) out. No severity given: high."""
    data = json.loads(text)
    dependencies = data.get("dependencies") if isinstance(data, dict) else data  # old: a list
    if not isinstance(dependencies, list):
        raise ValueError("no dependency list")
    findings, skipped = [], []
    for dep in dependencies:
        name, vulns = dep.get("name"), dep.get("vulns") or []
        if dep.get("skip_reason"):
            skipped.append("pip-audit could not check %s: %s" % (name, dep["skip_reason"]))
        if not vulns:
            continue
        holes = [("high", "%s: %s" % (v["id"], v.get("description") or "no description"),
                  "https://osv.dev/vulnerability/" + v["id"]) for v in vulns]
        versions = {version for v in vulns for version in v.get("fix_versions") or []}
        versions = sorted(versions, key=version_key)
        fix = UPGRADE % (name, ", ".join(versions)) if versions else NO_FIX % name
        findings.append(make_finding("pip", name, holes, fix, dep.get("version")))
    return findings, skipped

def plan_checks(folder, names):
    """Pure: jobs for the files NAMES in FOLDER: {file, cmd, parse, copy} or {file, note}."""
    jobs = []
    npm_lock = "npm-shrinkwrap.json" if "npm-shrinkwrap.json" in names else "package-lock.json"
    if npm_lock in names:  # npm uses the shrinkwrap first. A missing package.json is reported.
        jobs.append({"file": npm_lock, "cmd": NPM, "parse": parse_npm,
                     "copy": [npm_lock, "package.json"], "lock": npm_lock})
    if "composer.lock" in names:
        jobs.append({"file": "composer.lock", "cmd": COMPOSER, "parse": parse_composer,
                     "copy": ["composer.lock"]})
    pattern = "*.txt" if os.path.basename(folder) == "requirements" else "requirements*.txt"
    requirements = fnmatch.filter(names, pattern)
    for name in requirements:  # the full path, as pip-audit runs in a temp folder
        cmd = PIP_AUDIT + [os.path.abspath(os.path.join(folder, name))]
        jobs.append({"file": name, "cmd": cmd, "parse": parse_pip_audit, "copy": []})
    jobs += [{"file": name, "note": NOTES[name]} for name in names if name in NOTES]
    python = [name for name in EXPORT if name in names]
    if python and not requirements:
        note = 'pip-audit needs a requirements.txt: run "%s" in that folder, then run deps.py again'
        jobs.append({"file": python[0], "note": note % EXPORT[python[0]]})
    return jobs

def run_tool(cmd, folder, copy):
    """Run an auditor in an empty temp folder with copies of only the COPY files from FOLDER,
    so the project's own settings stay out. Returns (stdout, stderr), or None if not installed."""
    program = shutil.which(cmd[0])
    if program is None or os.path.dirname(os.path.abspath(program)) == os.getcwd():
        return None  # never a program in the current folder (Windows looks there first)
    if program.lower().endswith((".bat", ".cmd")) and any(BATCH_UNSAFE.search(arg) for arg in cmd[1:]):
        raise ValueError("it is a batch file, and cmd.exe would act on characters in the path: run it there by hand")
    with tempfile.TemporaryDirectory(prefix="forge-deps-") as sandbox:
        for name in copy:
            shutil.copyfile(os.path.join(folder, name), os.path.join(sandbox, name))
        if cmd[0] == "composer":
            with open(os.path.join(sandbox, "composer.json"), "w", encoding="utf-8") as handle:
                handle.write("{}\n")
        with subprocess.Popen([os.path.abspath(program)] + cmd[1:], cwd=sandbox, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
                              env=dict(os.environ, PYTHONIOENCODING="utf-8")) as process:  # pip-audit: UTF-8
            try:
                return process.communicate(timeout=TIMEOUT)  # the exit code is ignored: npm exits 1 on findings
            except subprocess.TimeoutExpired:
                if os.name == "nt":  # kill() stops npm.cmd's cmd.exe only, and its node.exe holds the sandbox
                    subprocess.run([TASKKILL, "/F", "/T", "/PID", str(process.pid)], capture_output=True, timeout=60)
                process.kill()
                raise

def read_lock(path):
    """The parsed lockfile, or {} when it cannot be read: then the advice is just less precise."""
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}

def run_check(job, folder):
    """Do one job. Returns (checked, findings, reasons); a reason is something not checked."""
    if "note" in job:
        return False, [], [job["note"]]
    tool = job["cmd"][0]
    try:
        output = run_tool(job["cmd"], folder, job["copy"])
        if output is None:
            reason = "%s is not installed: %s, then run deps.py again" % (tool, INSTALL[tool])
            return False, [], [reason]
        lock = [read_lock(os.path.join(folder, job["lock"]))] if "lock" in job else []
        findings, skipped = job["parse"](output[0], *lock)  # npm: also its lockfile
        return True, findings, skipped
    except subprocess.TimeoutExpired:
        reason = "it took over %d seconds: try again later" % TIMEOUT
    except json.JSONDecodeError:  # no JSON report: the last line of its error output says why
        reason = (output[1].strip().splitlines() or ["it printed nothing"])[-1]
    except (OSError, ValueError) as error:  # could not run it, or npm's error / not a report
        reason = str(error)
    except (TypeError, AttributeError, KeyError):  # JSON of a shape this script does not know
        reason = "its report has a shape this script does not know"
    reason = shorten(re.sub(r"//[^/@\s]+@", "//****@", reason), 120, placeholder="...")
    return False, [], ["%s could not check it (%s)" % (tool, reason)]

def check_path(path):
    """Check every folder under PATH: (findings most severe first, checked, not_checked)."""
    findings, checked, not_checked, unreadable = [], [], [], []
    for folder, subfolders, names in os.walk(path, onerror=lambda e: unreadable.append(e.filename)):
        parent = os.path.basename(os.path.normpath(folder))  # for 'storage/framework'
        subfolders[:] = sorted(name for name in subfolders if name not in SKIP_FOLDERS
                               and parent + "/" + name not in SKIP_FOLDERS)
        names = sorted(n for n in names if not os.path.islink(os.path.join(folder, n)))
        for job in plan_checks(folder, names):
            ok, found, reasons = run_check(job, folder)
            where = os.path.normpath(os.path.join(folder, job["file"]))
            findings += [dict(finding, where=where) for finding in found]
            if ok:
                checked.append({"file": where, "tool": job["cmd"][0]})
            not_checked += [{"file": where, "reason": reason} for reason in reasons]
    not_checked += [{"file": name, "reason": "could not open this folder"} for name in unreadable]
    findings.sort(key=lambda f: (SEVERITIES.index(f["severity"]), f["where"], str(f["package"])))
    return findings, checked, not_checked

def format_human(findings, not_checked, summary):
    """Plain-text report. A file name that is not UTF-8 prints as \\udcff instead of crashing."""
    lines = []
    for f in findings:
        lines.append("%-8s  %s" % (f["severity"].upper(), f["title"]))
        for key in ("where", "why", "fix", "holes", "more"):
            if f[key]:
                lines.append("          %-6s %s" % (key + ":", f[key]))
        lines.append("")
    if not_checked:
        lines.append("Not checked (the result below does not cover these):")
        lines += ["  - %(file)s: %(reason)s" % item for item in not_checked] + [""]
    counts = ", ".join("%d %s" % (summary[sev], sev) for sev in SEVERITIES if summary[sev])
    result = "Findings: %d (%s)." % (len(findings), counts) if findings else "No findings."
    if not summary["checked"]:
        result = "Nothing could be checked, so this is NOT a clean result."
    elif not_checked and not findings:
        result = 'No findings in what was checked; the rest is listed under "Not checked".'
    lines.append("Dependency files checked: %d. %s" % (summary["checked"], result))
    if not summary["checked"] and not not_checked:
        lines[-1] = "No lockfiles or requirements files found, so nothing was checked. " + NO_LOCK
    return "\n".join(lines).encode("utf-8", "backslashreplace").decode("utf-8")

def main(argv=None):
    """Read the arguments, check PATH, print the report and return the exit code."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: escapes, no crash
    parser = argparse.ArgumentParser(description="Check dependencies for known security holes.")
    parser.add_argument("path", help="folder to check")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high",
                        help="exit 1 when a finding is this bad or worse (default: high)")
    parser.add_argument("--strict", action="store_true", help="exit 1 if anything was not checked")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.path) or not os.access(args.path, os.R_OK):
        print("error: %s is not a folder that exists and can be read" % args.path, file=sys.stderr)
        return 2
    findings, checked, not_checked = check_path(args.path)
    limit = SEVERITIES.index(args.fail_on)
    failed = any(SEVERITIES.index(f["severity"]) <= limit for f in findings)
    failed = failed or (args.strict and (bool(not_checked) or not checked))
    summary = {sev: sum(f["severity"] == sev for f in findings) for sev in SEVERITIES}
    summary.update(total=len(findings), checked=len(checked), not_checked=len(not_checked),
                   fail_on=args.fail_on, strict=args.strict, failed=failed)
    report = {"findings": findings, "checked": checked, "not_checked": not_checked,
              "summary": summary}
    try:
        print(json.dumps(report, indent=2) if args.json
              else format_human(findings, not_checked, summary), flush=True)
    except OSError as error:  # the reader stopped early (| head): end quietly, no traceback
        if error.errno not in (errno.EPIPE, errno.EINVAL):  # EINVAL: what Windows says there
            raise
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
