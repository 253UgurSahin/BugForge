#!/usr/bin/env python3
"""Check where an app's packages come from (its supply chain). Offline: it reads package.json with
package-lock.json (version 2 or 3), composer.json with composer.lock, requirements*.txt and, with line
patterns, pyproject.toml, poetry.lock, uv.lock, pdm.lock, and for names, versions and sources only ("Not
read in full") yarn.lock, pnpm-lock.yaml, bun.lock and Pipfile.lock. Per file, with the package names: no
lockfile, or one git ignores; versions with no upper limit; code from a git URL, a link or a local path;
locked packages from another host than the official registry, with no integrity hash (npm), that run code
on install, or with a GPL, AGPL, SSPL or no licence (not legal advice); a name one letter away from a
well-known package (a possible typosquat). bun.lockb or package-lock version 1 makes the check incomplete.
forge:allow does not apply: note an accepted risk in security.md. Skips symlinks and node_modules, vendor,
build, cache, test fixture (fixtures, testdata) and forge-work folders. --sbom FILE also writes the locked
packages as CycloneDX 1.5 JSON (never through a symlink), empty when the check is incomplete; same exit code.

Usage: python3 supply.py PATH [--sbom FILE] [--json] [--fail-on critical|high|medium|low], for example
    python3 supply.py . --sbom forge-work/sbom.json
Exit codes: 0 nothing at or above --fail-on (default: high); 1 at least one finding at or above it;
2 PATH is not a folder, something could not be read (an incomplete check), or supply.json is broken.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from urllib.parse import quote

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
SKIP_DIRS = {".git", "node_modules", "vendor", "venv", ".venv", "__pycache__", "dist", "build", ".next", ".nuxt",
             "out", "coverage", "storage/framework", ".cache", ".idea", ".vscode", "forge-work", "fixtures",
             "__fixtures__", "testdata"}  # test fixtures: a broken package.json there is on purpose, not the app's
MAX_BYTES = 20 * 1024 * 1024  # a bigger manifest or lockfile is not read
OFFICIAL = {"registry.npmjs.org", "registry.yarnpkg.com", "packagist.org", "pypi.org", "files.pythonhosted.org"}
OUTSIDE = re.compile(r"(?:git[+:@]|(?:git|https?|ssh|file)://|github:|gitlab:|bitbucket:|file:|link:|\.{0,2}/|~/"
                     r"|[\w.-]+/[\w.-]+(?:#\S*)?$)")  # a git URL, a link, a local path, npm's user/repo
COPYLEFT = re.compile(r"(?i)(?<![a-z])(?:AGPL|GPL|SSPL)")  # not LGPL
NPM_LOCKS = ["package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock", "bun.lockb"]
PY_LOCKS = ["uv.lock", "poetry.lock", "pdm.lock", "Pipfile.lock"]  # the first three: [[package]] blocks
REQUIREMENT = re.compile(r"([A-Za-z0-9][\w.-]*)(?:\[[^\]]*\])?\s*(?!@)([^;@]*)(?:;.*)?$")  # name[extra] range; marker

try:  # supply.json, next to this script: the words of each finding, and well-known package names per registry
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "supply.json"), encoding="utf-8") as data_file:
        RULES, POPULAR, LOCKS = map(json.load(data_file).__getitem__, ("rules", "popular", "locks"))
except (OSError, ValueError, LookupError, TypeError, AttributeError) as data_error:
    print("error: supply.json is missing or broken (%s)" % data_error, file=sys.stderr)
    sys.exit(2)

def host_of(url):
    """The host name in a URL, without any user:password@ part; "" when there is none."""
    return (re.search(r"://(?:[^/@]*@)?([^/:?#]+)", str(url)) or ["", ""])[1].lower()

def floats(spec):
    """True for a version range with no upper limit: empty, *, latest, dev-main, >=1.2."""
    return (spec.strip() in ("", "*", "x", "latest", "next") or spec.startswith("dev-") or spec.endswith("@dev")
            or (">" in spec and not re.search(r"<|==|~=", spec)))

def look_alike(name, kind):
    """The well-known package (5 letters or more) that NAME is one letter added, dropped, changed or swapped from."""
    for known in POPULAR[kind] if name not in POPULAR[kind] else ():
        same = next((i for i, (a, b) in enumerate(zip(name, known)) if a != b), min(len(name), len(known)))
        a, b = name[same:], known[same:]  # what is left after the letters they share
        if len(known) >= 5 and (a[1:] == b[1:] or a[1:] == b or a == b[1:] or (a[:2] == b[1::-1] and a[2:] == b[2:])):
            return known
    return None

def licence_of(value):
    """A lockfile's licence field as one string: "MIT", "MIT OR GPL-3.0"; "" when none is stated."""
    names = [str(item or "").strip("() ") for item in (value if isinstance(value, list) else [value])]
    return " OR ".join(name for name in names if name and name.upper() not in ("UNLICENSED", "NONE"))

def shown(report, folder, name=""):
    """A path as the report shows it: relative to the checked folder, with forward slashes."""
    return os.path.relpath(os.path.join(folder, name), report["root"]).replace(os.sep, "/")

def read(report, folder, name, as_json=False):
    """A file's text, or its JSON object. Raises ValueError(name, why) when it cannot be read."""
    try:
        with open(os.path.join(folder, name), "rb") as handle:
            text = handle.read(MAX_BYTES + 1).decode("utf-8", errors="replace")
        value = json.loads(text) if as_json else text
        if len(text) > MAX_BYTES or not isinstance(value, dict if as_json else str):
            raise ValueError("over 20 MB, or not a JSON object")
    except (OSError, ValueError, RecursionError) as error:
        raise ValueError(name, getattr(error, "strerror", None) or "not valid (%s)" % error)
    report["files"].append(shown(report, folder, name))
    return value

def add(report, rule, folder, name, packages):
    """Add one finding about the file NAME in FOLDER and these PACKAGES (none when the list is empty)."""
    report["findings"] += [dict(RULES[rule], title=RULES[rule]["title"].format(name), rule=rule, where=shown(
        report, folder, name), packages=sorted(set(packages)))] if packages else []

def ignored(folder, name, root):
    """True when the .gitignore in ROOT or in FOLDER lists the file NAME; a later line with ! lets it back in."""
    hits = []
    for place in dict.fromkeys([os.path.abspath(root), os.path.abspath(folder)]):
        paths = (name, os.path.relpath(os.path.join(folder, name), place).replace(os.sep, "/"))
        if os.path.isfile(os.path.join(place, ".gitignore")):
            with open(os.path.join(place, ".gitignore"), encoding="utf-8", errors="replace") as handle:
                lines = [line.strip() for line in handle.read(MAX_BYTES).splitlines() if not line.startswith("#")]
            hits += [line for line in lines if any(fnmatch.fnmatch(path, line.lstrip("!/")) for path in paths)]
    return bool(hits) and not hits[-1].startswith("!")

def manifest(report, folder, names, name, kind, deps, locks, covered=False):
    """The checks every manifest gets. DEPS: {package: version range}; COVERED: a lockfile in a folder above."""
    have = [lock for lock in locks if lock in names]
    hidden = [lock for lock in have or locks[:1] if ignored(folder, lock, report["root"])]
    missing = deps and not (have or hidden or covered)
    add(report, "supply-lock-ignored", folder, name, hidden)
    add(report, "supply-no-lockfile", folder, name, ["no " + " or ".join(locks[:2])] if missing else [])
    add(report, "supply-floating", folder, name, [dep for dep, spec in deps.items() if floats(spec)])
    add(report, "supply-source", folder, name, [dep for dep, spec in deps.items() if OUTSIDE.match(spec.strip())])
    locked(report, folder, name, kind, [(dep, None, None, None, False) for dep in deps])

def locked(report, folder, name, kind, entries):
    """The checks every list of packages gets. ENTRIES: (package, version, licence, host, runs code on install)."""
    alike = [(entry[0], look_alike(entry[0], kind)) for entry in entries]
    add(report, "supply-typosquat", folder, name, ["%s (like %s)" % pair for pair in alike if pair[1]])
    add(report, "supply-registry", folder, name,
        ["%s (%s)" % (entry[0], entry[3]) for entry in entries if entry[3] and entry[3] not in OFFICIAL])
    add(report, "supply-install-script", folder, name, [entry[0] for entry in entries if entry[4]])
    add(report, "supply-licence", folder, name, ["%s (%s)" % (entry[0], entry[2]) for entry in entries if entry[2]
                                                 and all(COPYLEFT.search(part) for part in entry[2].split(" OR "))])
    add(report, "supply-no-licence", folder, name, [entry[0] for entry in entries if entry[2] == ""])
    report["components"] += [(kind, entry[0], str(entry[1]), entry[2] or "") for entry in entries if entry[1]]

def check_npm(report, folder, names, covered):
    """package.json and its lockfile."""
    package = read(report, folder, "package.json", True)
    deps = {dep: str(spec) for key in ("dependencies", "devDependencies", "optionalDependencies")
            for dep, spec in (package.get(key) or {}).items()}
    manifest(report, folder, names, "package.json", "npm", deps, NPM_LOCKS, covered=covered)
    lock = "npm-shrinkwrap.json" if "npm-shrinkwrap.json" in names else "package-lock.json"  # npm reads this one first
    packages = read(report, folder, lock, True).get("packages") if lock in names else {}
    if not isinstance(packages, dict):  # lockfile version 1: its packages would be missing from the SBOM
        report["unreadable"].append({"path": shown(report, folder, lock), "reason": "version 1: npm 7+ rewrites it"})
    entries, bare = [], []
    for key, item in [pair for pair in (packages.items() if isinstance(packages, dict) else ())
                      if "node_modules/" in pair[0] and not pair[1].get("link")]:  # not the project or a workspace
        dep, source = item.get("name") or key.rpartition("node_modules/")[2], str(item.get("resolved") or "")
        host = (host_of(source) or "not a registry: " + source.split(":")[0]) if source else None
        entries.append((dep, item.get("version"), licence_of(item.get("license")), host, item.get("hasInstallScript")))
        bare += [dep] if not item.get("integrity") and not item.get("inBundle") else []
    locked(report, folder, lock, "npm", entries)
    add(report, "supply-no-integrity", folder, lock, bare)

def check_composer(report, folder, names):
    """composer.json and composer.lock."""
    package = read(report, folder, "composer.json", True)
    deps = {dep: str(spec) for key in ("require", "require-dev") for dep, spec in (package.get(key) or {}).items()
            if "/" in dep}  # not php or ext-json
    manifest(report, folder, names, "composer.json", "composer", deps, ["composer.lock"])
    lock = read(report, folder, "composer.lock", True) if "composer.lock" in names else {}
    entries = []
    for entry in (lock.get("packages") or []) + (lock.get("packages-dev") or []):
        host = host_of(entry.get("notification-url")) or "not from packagist.org"  # packagist.org's packages have it
        version, plugin = str(entry.get("version") or "").lstrip("v"), entry.get("type") == "composer-plugin"
        entries.append((entry.get("name"), version, licence_of(entry.get("license")), host, plugin))
    locked(report, folder, "composer.lock", "composer", entries)

def check_requirements(report, folder, names, name):
    """One requirements*.txt: a manifest and, for its == lines, a lockfile too."""
    deps, pins, hosts = {}, [], []
    for line in re.sub(r"\\\r?\n", " ", read(report, folder, name)).splitlines():
        line = re.sub(r"(?:^|\s)#.*", "", line).strip()
        dep = None if "://" in line else REQUIREMENT.match(line)  # git+https://..., name @ https://...: a source
        if re.match(r"(?:-i|-f|--(?:extra-)?index-url|--find-links)\b", line):
            hosts += ["index %s" % host_of(line)] if host_of(line) not in OFFICIAL else []
        elif dep and "==" in dep.group(2) and "*" not in dep.group(2):
            pins.append((norm(dep.group(1)), dep.group(2).split("==")[-1].split()[0].strip("=, "), None, None, False))
        elif dep:
            deps[norm(dep.group(1))] = ""  # no == on the line: not pinned
        elif line and not re.match(r"-[rc]\b|--", line):  # -e ., git+https://..., name @ https://...
            deps[line] = "./" + re.sub(r"^(?:-e|--editable)\s+", "", line)
    manifest(report, folder, names, name, "pypi", deps, [name])
    add(report, "supply-registry", folder, name, hosts)
    locked(report, folder, name, "pypi", pins)

def norm(name):
    """A Python package name as PyPI compares it: lower case, with - for _ and for a dot."""
    return re.sub(r"[-_.]+", "-", name).lower()

def check_python(report, folder, names):
    """requirements*.txt, pyproject.toml, poetry.lock and uv.lock."""
    for name in (texts := sorted(name for name in names if fnmatch.fnmatch(name, "requirements*.txt"))):
        check_requirements(report, folder, names, name)
    if "pyproject.toml" in names:
        text, deps = re.sub(r"(?m)\s+#.*$", "", read(report, folder, "pyproject.toml")), {}
        for title, body in re.findall(r"(?ms)^\[([^\]\n]+)\][^\n]*\n(.*?)(?=^\[|\Z)", text):
            if re.fullmatch(r"tool\.poetry\.(?:group\.[\w-]+\.)?(?:dev-)?dependencies", title):  # name = "^1.2"
                for dep, value in re.findall(r"(?m)^(?!python\b)([\w.-]+)\s*=\s*(.+)$", body):
                    spec = re.search(r"[\"']([^\"']*)[\"']", value)  # the first quoted text: the version range
                    deps[norm(dep)] = "./" if re.search(r"\b(?:git|path|url)\s*=", value) or not spec else spec[1]
            elif title in ("project", "project.optional-dependencies", "dependency-groups"):  # lists of "name>=1.2"
                key = "dependencies" if title == "project" else r"[\w-]+"
                lists = re.findall(r"(?ms)^%s\s*=\s*\[(.*?)\]\s*$" % key, body)
                for item in re.findall(r"[\"']([^\"']+)[\"']", " ".join(lists)):
                    dep = REQUIREMENT.match(item)  # no match: "name @ https://..."
                    deps[norm(dep[1]) if dep else item] = dep[2] if dep else "./"
        manifest(report, folder, names, "pyproject.toml", "pypi", deps, PY_LOCKS + texts)
    for name in [lock for lock in PY_LOCKS[:3] if lock in names]:
        entries = []
        for block in re.split(r"(?m)^\[\[package\]\]\s*$", read(report, folder, name))[1:]:
            dep, version = [re.search(r'(?m)^%s\s*=\s*"([^"]*)"' % key, block) for key in ("name", "version")]
            source = re.search(r'(?m)^source\s*=\s*\{\s*(\w+)\s*=\s*"([^"]*)"'  # uv, then Poetry
                               r'|^\[package\.source\]\s*\n(?:(?!\[).*\n)*?url\s*=\s*"([^"]*)"', block)
            how, url = (source[1] or "source", source[2] or source[3]) if source else ("", "https://pypi.org")
            if dep and version and how not in ("editable", "virtual"):  # those two are the project itself
                entries.append((norm(dep[1]), version[1], None, host_of(url) or "%s %s" % (how, url), False))
        locked(report, folder, name, "pypi", entries)

def check_path(root):
    """Check every folder under ROOT. Returns the report: findings, components, files, not_read, unreadable."""
    report = {"root": root, "findings": [], "components": [], "files": [], "not_read": [], "unreadable": []}
    npm_locked = []  # folders with an npm lockfile: it speaks for the package.json files of the workspaces below
    for folder, subfolders, files in os.walk(root, onerror=lambda error: report["unreadable"].append(
            {"path": shown(report, error.filename or root), "reason": error.strerror or "cannot be opened"})):
        parent = os.path.basename(os.path.abspath(folder))
        subfolders[:] = sorted(d for d in subfolders if d not in SKIP_DIRS and parent + "/" + d not in SKIP_DIRS)
        names = {name for name in files if not os.path.islink(os.path.join(folder, name))}
        try:
            if "package.json" in names:
                check_npm(report, folder, names, any(folder.startswith(top + os.sep) for top in npm_locked))
                npm_locked += [folder] if names & set(NPM_LOCKS) else []
            if "composer.json" in names:
                check_composer(report, folder, names)
            check_python(report, folder, names)
            for lock in sorted(names & set(LOCKS) - {name + "b" for name in names}):  # a bun.lock beats a bun.lockb
                kind, pattern, note = LOCKS[lock]  # supply.json: read as text, or (no pattern) not at all
                found = re.findall(pattern, read(report, folder, lock), re.M) if pattern else []
                locked(report, folder, lock, kind, [(norm(dep) if kind == "pypi" else dep, version, None,
                       host_of(url) or None, False) for dep, version, url in found if "use.local" not in version])
                report["not_read" if pattern else "unreadable"].append(dict(reason=note, **{
                    "file" if pattern else "path": shown(report, folder, lock)}))
        except (OSError, ValueError, TypeError, AttributeError, LookupError, re.error) as error:  # unreadable, odd
            named = isinstance(error, ValueError) and len(error.args) == 2  # read() says which file, and why
            name, reason = error.args if named else ("", "a file here is not what its name says")
            report["unreadable"].append({"path": shown(report, folder, str(name)), "reason": str(reason)})
    report["findings"].sort(key=lambda item: (SEVERITIES.index(item["severity"]), item["where"], item["rule"]))
    return report

def write_sbom(path, components):
    """Write the locked packages as CycloneDX 1.5 JSON; None (an incomplete check) leaves it empty. "" or why not."""
    bom = {"bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1, "components": []}
    for kind, name, version, licence in sorted(components or ()):
        purl = "pkg:%s/%s@%s" % (kind, quote(name, safe="/"), quote(version))  # @scope/name becomes %40scope/name
        item = {"type": "library", "name": name, "version": version, "purl": purl, "bom-ref": purl}
        bom["components"].append(dict(item, licenses=[{"license": {"name": licence}}]) if licence else item)
    try:
        if os.path.islink(path):
            raise OSError(0, "it is a symlink, and this script does not write through one")
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags, 0o644), "w", encoding="utf-8") as handle:
            handle.write("" if components is None else json.dumps(bom, indent=2))
        return "" if components is not None else "the check is incomplete (see above), so the file was left empty"
    except OSError as error:
        return error.strerror or "it cannot be written"

def format_human(report, summary):
    """One block per finding, then what was not read and a one-line summary."""
    lines = []
    for item in report["findings"]:
        names, pad = item["packages"], " " * (len(item["severity"]) + 2)
        item = dict(item, which=", ".join(names[:8]) + (" (+%d more: --json)" % len(names[8:]) if names[8:] else ""))
        lines += ["%s  %s [%s]" % (item["severity"].upper(), item["title"], item["rule"])]
        lines += [pad + "%-7s%s" % (key + ":", item[key]) for key in ("where", "which", "why", "fix")] + [""]
    lines += ["Not read in full: %(file)s (%(reason)s)" % item for item in report["not_read"]]
    lines += ["INCOMPLETE, so not a pass. Could not read %(path)s (%(reason)s)" % item for item in report["unreadable"]]
    counts = ", ".join("%d %s" % (summary[s], s) for s in SEVERITIES if summary[s])
    result = "Findings: %d (%s)." % (summary["total"], counts) if summary["total"] else "No findings."
    if not report["files"]:
        result = "Nothing was checked: no package.json, composer.json, requirements*.txt or pyproject.toml found."
    lines.append("%s Files read: %d. Packages in lockfiles: %d." % (result, len(report["files"]), summary["packages"]))
    lines += ["SBOM " + ("NOT written to %(file)s: %(reason)s" if report["sbom"]["reason"] else "written to %(file)s")
              % report["sbom"]] if report.get("sbom") else []
    return "\n".join(lines).encode("utf-8", "backslashreplace").decode("utf-8")

def main(argv=None):
    """Read the arguments, check PATH, print the report and return the exit code."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: escapes, no crash
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("path", help="folder to check")
    parser.add_argument("--sbom", metavar="FILE", help="also write a CycloneDX 1.5 JSON list of the locked packages")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high", help="exit 1 at this severity or worse")
    args = parser.parse_args(argv)
    os.path.isdir(args.path) or parser.error("%s is not a folder" % args.path)  # exit code 2
    report = check_path(args.path)
    components, _ = {part[:3]: part for part in sorted(report.pop("components"))}, report.pop("root")  # each once
    if args.sbom:
        reason = write_sbom(args.sbom, None if report["unreadable"] else components.values())  # level 3's evidence
        report["sbom"] = {"file": args.sbom, "written": not reason, "reason": reason, "components": len(components)}
    summary = {s: sum(f["severity"] == s for f in report["findings"]) for s in SEVERITIES}
    summary.update(total=len(report["findings"]), packages=len(components), incomplete=bool(report["unreadable"]))
    print(json.dumps(dict(report, summary=summary), indent=2) if args.json else format_human(report, summary))
    failed = any(SEVERITIES.index(f["severity"]) <= SEVERITIES.index(args.fail_on) for f in report["findings"])
    return 2 if report["unreadable"] else int(failed)  # something was not read: that result cannot be trusted

if __name__ == "__main__":
    sys.exit(main())
