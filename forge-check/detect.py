#!/usr/bin/env python3
"""Tell which stack a project uses, and which forge profile is closest.

Reports languages, frameworks with versions (from the lockfile next to the manifest), databases, containers,
test tools, CI, the theming (Tailwind CSS, Bootstrap, Sass, MUI, Chakra UI, Mantine, CSS-in-JS), the package
manager each lockfile names, and the closest forge profile (laravel, django, next, static or none) with a reason.
Reads manifests and config files in the project folder and two folders down; other files count by name only
(*.php). Never reads .env; of .env.example only the words that name a database count. stacks.json, next to this
script, says which package or file means what. Simple patterns, not a YAML or TOML parser: a strong hint, check it.

Usage:
    python3 detect.py .                describe the project in the current folder
    python3 detect.py ../shop --json   machine-readable output

Exit codes:
    0  done, also when nothing was recognised (the profile is then "none")
    2  bad usage, or PATH is not a folder
"""

import argparse
import fnmatch
import json
import os
import posixpath
import re
import sys

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stacks.json"), encoding="utf-8") as handle:
    STACKS = json.load(handle)
MAX_BYTES = 20 * 1024 * 1024  # read at most this much of a file (lockfiles can be big)
MAX_DEPTH = 2  # the project folder and two folders down
SKIP_FOLDERS = {".git", "node_modules", "vendor", "venv", ".venv", "__pycache__", "dist", "build", ".next",
                ".nuxt", "out", "coverage", ".cache", ".idea", ".vscode", ".devcontainer", "forge-work"}
TIERS = {"laravel": 0, "django": 0, "next": 0, "server": 1, "static": 2}  # profile, server, front end
# The language version, which a manifest lists like a package (package.json's engines.node is kept so).
RUNTIME_KEYS = ["php", "engines.node", "requires-python", "python", "python-version"]
# In stacks.json's database_files, outside comments, group 1 is a word that may name a database:
# POSTGRES_DB=shop, DB_CONNECTION=pgsql, postgres://, django.db.backends.mysql, provider = "mysql".
DATABASE_HINTS = [re.compile(r"^\s*((?:POSTGRES|MYSQL|MARIADB|MONGO)\w*)\s*="),
                  re.compile(r"^\s*DB_CONNECTION\s*=\s*[\"']?(\w+)"), re.compile(r"\b([a-z][a-z0-9+]*)://"),
                  re.compile(r"backends\.(\w+)"), re.compile(r"provider\s*=\s*\"(\w+)\"")]
COMMENT = re.compile(r"(^|\s)(#|//).*")  # a comment to the end of the line; postgres:// is no comment
# Lockfiles are read as plain text: each pattern finds (package, version) pairs.
NAME = r"((?:@[\w.-]+/)?[\w.-]+)"  # a package name, maybe with an npm scope: @next/env
PYTHON_LOCK = [r'\[\[package\]\]\s*name\s*=\s*"([^"]+)"\s*version\s*=\s*"([^"]+)"']
NPM_LOCK = [r'"node_modules/' + NAME + r'":\s*\{\s*"version":\s*"([^"]+)"']  # npm 7+: "node_modules/next"
NPM6_LOCK = r'^([ \t]+)"' + NAME + r'":\s*\{\s*"version":\s*"([^"]+)"'  # npm 6: "next", the least indented
LOCKFILES = {"composer.lock": ("php", [r'"name":\s*"([^"]+)",\s*"version":\s*"v?([^"]+)"']),
             "package-lock.json": ("node", NPM_LOCK), "npm-shrinkwrap.json": ("node", NPM_LOCK),
             "bun.lock": ("node", [r'"' + NAME + r'":\s*\["[^"]*?@(\d[^"]*)"']),  # "next": ["next@15.1.3"
             "yarn.lock": ("node", [r'^"?' + NAME + r'@[^\n]*:\r?\n\s+version:?\s+"?([^"\s]+)']),
             "pnpm-lock.yaml": ("node", [r"^  '?/?" + NAME + r"[@/](\d[^:(_'\s]*)"]),  # /next@14.2.3:
             "poetry.lock": ("python", PYTHON_LOCK), "uv.lock": ("python", PYTHON_LOCK),
             "Pipfile.lock": ("python", [r'"([\w.-]+)":\s*\{[^{}]*?"version":\s*"==([^"]+)"'])}
# One Python requirement: a name, maybe [extras], maybe a version range: 'psycopg[binary] >= 3.1',
# and from TOML tables 'django ^5.0' (Poetry), 'django *' (Pipfile), 'python_version 3.12'.
REQUIREMENT = re.compile(r"\s*([A-Za-z0-9][\w.-]*)\s*(?:\[[^\]]*\])?\s*(?=$|[(<>=!~;@^*\d])\(?([<>=!~^*\d][^;@()]*)?")
# TOML: a section header; 'django = "^5.0"' or 'django = {version = "^5.0"}' in TABLE sections; a
# 'key = [...]' list, and per section the key whose list holds requirements (*: every key).
TOML_SECTION = re.compile(r"^\s*\[+\s*([^\]\s]+)\s*\]+\s*$", re.M)
TOML_TABLE = re.compile(r"(project|tool\.poetry\.(group\.[\w-]+\.)?(dev-)?dependencies|(dev-)?packages|requires)$")
TOML_TABLE_LINE = re.compile(r"""^\s*["']?([A-Za-z0-9][\w.-]*)["']?\s*=\s*"""
                             r"""(?:\{[^}\n]*?version\s*=\s*)?["']([^"'\n]*)["']""", re.M)
TOML_LIST = re.compile(r"^\s*([\w-]+)\s*=\s*\[(.*?)\]\s*(?:#[^\n]*)?$", re.M | re.S)
TOML_LISTS = {"project": "dependencies", "tool.uv": "dev-dependencies",
              "project.optional-dependencies": "*", "dependency-groups": "*"}


def matches(path, patterns):
    """True when the file name fits a pattern. A pattern with a / fits the end of the path."""
    return any(fnmatch.fnmatchcase("/".join(path.split("/")[-1 - p.count("/"):]), p) for p in patterns)


def as_dict(value):
    return value if isinstance(value, dict) else {}


def package_key(ecosystem, name):
    """Package names compare without case; in Python - _ and . are the same too (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower() if ecosystem == "python" else name.lower()


def database_in(word):
    """The database a word points to ('mysql2' -> MySQL, 'pg' -> PostgreSQL), or None."""
    word = word.lower()
    if "pg" in re.split(r"[^a-z0-9]+", word):
        return "PostgreSQL"
    return next((name for name, keys in STACKS["databases"].items() if any(key in word for key in keys)), None)


def python_deps(name, text):
    """{package: version range} from a requirements.txt, pyproject.toml or Pipfile."""
    deps, strings, parts = {}, [], []  # strings: the requirements, 'Django==4.2.11'
    if name.endswith(".txt"):  # a line ending in \ goes on; comments and options (-r, --hash=) are cut
        strings = [re.sub(r"(^|\s)[#-].*", "", line) for line in re.sub(r"\\\r?\n", " ", text).splitlines()]
    else:  # TOML: only dependency sections count, not tool settings such as [tool.ruff]
        parts = TOML_SECTION.split(text)  # [before the first header, name, body, name, body, ...]
    for section, body in zip(parts[1::2], parts[2::2]):
        if TOML_TABLE.match(section):
            strings += [key + " " + spec for key, spec in TOML_TABLE_LINE.findall(body)]
        lists = [items for key, items in TOML_LIST.findall(body) if TOML_LISTS.get(section) in ("*", key)]
        strings += [one or other for items in lists for one, other in re.findall(r'"([^"]*)"|\'([^\']*)\'', items)]
    for match in filter(None, map(REQUIREMENT.match, strings)):  # '>= 4.2, < 5' -> '>=4.2,<5'
        spec = (match.group(2) or "").replace(" ", "")
        deps.setdefault(match.group(1), spec[2:] if spec.startswith("==") and "," not in spec else spec)  # ==4.2 is 4.2
    return deps


def images_in(text):
    """Images in a compose file (image: postgres:16) or Dockerfile (FROM php:8.3-fpm), not build
    stages. FROM must be in capitals: 'from x import y' inside a RUN is Python, not an image."""
    stages = {name.lower() for name in re.findall(r"^\s*FROM\s.*\s(?i:as)\s+(\S+)", text, re.M)}
    found = re.findall(r"^\s*(?:image:\s*[\"']?|FROM\s+(?:--\S+\s+)*)([^\"'\s#]+)", text, re.M)
    return [image for image in dict.fromkeys(found) if image.lower() not in stages | {"scratch"}]


def project_files(root):
    """The files ('a/b.json') in ROOT and MAX_DEPTH folders down, shallow first; no SKIP_FOLDERS, venv or link."""
    found = []
    for folder, subfolders, names in os.walk(root):  # os.walk does not enter symlinked folders
        relative = "" if folder == root else os.path.relpath(folder, root).replace(os.sep, "/")
        depth = relative.count("/") + 1 if relative else 0
        subfolders[:] = [name for name in subfolders if depth < MAX_DEPTH and name not in SKIP_FOLDERS
                         and not os.path.isfile(os.path.join(folder, name, "pyvenv.cfg"))]
        for name in names:  # regular files only: reading a pipe would never end
            if os.path.isfile(os.path.join(folder, name)) and not os.path.islink(os.path.join(folder, name)):
                found.append(posixpath.join(relative, name))
    return sorted(found, key=lambda path: (path.count("/"), path))


def read_file(root, path, found, as_json=False):
    """The text (or JSON object) of a project file, or None with a note when it cannot be used."""
    try:  # utf-8-sig: a byte order mark at the start (Windows editors) is not part of the text
        with open(os.path.join(root, path), encoding="utf-8-sig", errors="replace") as handle:
            text = handle.read(MAX_BYTES)
        return as_dict(json.loads(text)) if as_json else text
    except (OSError, ValueError, RecursionError) as error:  # not JSON, or nested too deep to read
        problem = "could not be read" if isinstance(error, OSError) else "is not valid JSON"
        found["notes"].append("%s %s, skipped" % (path, problem))
        return None


def label(item):
    """'Laravel 11.31.0 (composer.lock)': the name, the version when known, and where it was found."""
    return "%s%s (%s)" % (item["name"], " " + item["version"] if item["version"] else "", item["source"])


def add_item(items, name, source, version="", **extra):
    """Add NAME to a list of items unless it is there already: the first source wins."""
    if name and source and name not in [item["name"] for item in items]:
        items.append(dict(name=name, version=version, source=source, **extra))


def read_manifest(root, path, found):
    """Take what one manifest or lockfile gives into FOUND; forge's own e2e/ (on npm) names no package manager."""
    name = posixpath.basename(path)
    ecosystem, deps, words = "", {}, []
    add_item(found["managers"], None if path.startswith("e2e/") else STACKS["package_managers"].get(name), path)
    if name in ("composer.json", "package.json"):  # composer.json's require holds "php" too
        ecosystem = "php" if name == "composer.json" else "node"
        data = read_file(root, path, found, as_json=True) or {}
        for section in ["require-dev", "require", "devDependencies", "dependencies"]:
            deps.update(as_dict(data.get(section)))
        deps.update(("engines." + key, value) for key, value in as_dict(data.get("engines")).items())
    elif matches(path, STACKS["python_manifests"]):
        ecosystem, deps = "python", python_deps(name, read_file(root, path, found) or "")
    elif name in LOCKFILES:  # its versions are for the manifests in the same folder
        ecosystem, patterns = LOCKFILES[name]
        text = read_file(root, path, found) or ""
        table = found["locked"].setdefault((ecosystem, posixpath.dirname(path)), {})
        pairs = [pair for pattern in patterns for pair in re.findall(pattern, text, re.M)]
        if name in ("package-lock.json", "npm-shrinkwrap.json"):  # npm 6 also nests a package's own packages
            npm6 = re.findall(NPM6_LOCK, text, re.M)
            least = min([len(indent) for indent, _, _ in npm6] or [0])  # the top-level ones are indented least
            pairs += [(package, version) for indent, package, version in npm6 if len(indent) == least]
        for package, version in pairs:
            table.setdefault(package_key(ecosystem, package), (version, path))
    elif matches(path, STACKS["container_files"]):
        words = images_in(read_file(root, path, found) or "")
        found["images"] += [image for image in words if image not in found["images"]]
    elif matches(path, STACKS["database_files"]):
        lines = [COMMENT.sub("", line) for line in (read_file(root, path, found) or "").splitlines()]
        words = [match.group(1) for line in lines for hint in DATABASE_HINTS for match in hint.finditer(line)]
    for word in words + list(deps):  # a database package (pg, mysql2, psycopg) names one too
        add_item(found["databases"], database_in(word), path)
    for package, spec in deps.items():
        found["declared"][ecosystem].setdefault(package_key(ecosystem, package), (str(spec or ""), path))


def known_items(root, files, found):
    """The frameworks and test tools in stacks.json that a manifest declares, else that a telltale file
    gives away, unless its "unless" was found. Versions: the nearest lockfile, else the manifest."""
    items = []
    for known in STACKS["frameworks"]:
        if known.get("unless") in [item["name"] for item in items]:
            continue
        ecosystem, table = known["ecosystem"], found["declared"][known["ecosystem"]]
        keys = [package_key(ecosystem, package) for package in known["packages"]]
        package = next((key for key in keys if key in table), None)
        version, source = table.get(package, ("", None))
        version = version if [package] == keys[:1] else ""  # pytest-django's range says nothing about pytest
        if source:  # a locked version: in the lockfile next to the manifest, else the top folder's (a workspace)
            lock = found["locked"].get((ecosystem, posixpath.dirname(source))) or found["locked"].get((ecosystem, ""), {})
            version, source = lock.get(keys[0], (version, source))
        for path in [] if source else [path for path in files if matches(path, known["telltale"])]:
            word = next((word for name, word in STACKS["telltale_words"].items() if matches(path, [name])), "")
            source = source or (path if word in (read_file(root, path, found) or "").lower() else None)
        add_item(items, known["name"], source, version, role=known["role"], ecosystem=ecosystem)
    return items


def find_languages(found, files):
    """PHP, JavaScript or TypeScript, and Python: from the manifests, else from file names."""
    languages = []
    for ecosystem, about in STACKS["ecosystems"].items():
        declared, name = found["declared"][ecosystem], about["language"]
        version = next((declared[key][0] for key in RUNTIME_KEYS if key in declared), "")
        sources = [path for _, path in declared.values()] + [path for path in files if matches(path, about["files"])]
        if ecosystem == "node":  # engines.node is the Node version, not a JavaScript version
            name = "TypeScript" if "typescript" in declared else name
            version = version and "on Node " + version
        add_item(languages, name, (sources or [None])[0], version)
    return languages


def pick_profile(frameworks, languages, databases, files):
    """The closest forge profile and why: see TIERS, then the framework nearest the top folder (a tie keeps
    the order of stacks.json). PHP, a Python manifest or a database mean a server: never static then."""
    ranked = sorted(frameworks, key=lambda item: (TIERS[item["role"]], item["source"].count("/")))
    best = ranked[0] if ranked else {"role": None}
    if best["role"] in ("laravel", "django", "next"):
        return best["role"], label(best) + "."
    if best["role"] == "server":
        return "none", ("%s has no forge profile. The nearest in the same language is %s, but forge does not move "
                        "an app to another stack." % (best["name"], STACKS["ecosystems"][best["ecosystem"]]["profile"]))
    server_side = [i for i in languages if i["name"] == "PHP" or matches(i["source"], STACKS["python_manifests"])]
    if server_side or databases:
        return "none", "%s, but no server framework forge has a profile for." % label((server_side + databases)[0])
    if best["role"] == "static":
        return "static", "%s front end without a server framework: nginx serves the built files." % best["name"]
    if "index.html" in files:
        return "static", "plain HTML files without a framework."
    if languages:
        return "none", "%s, but no framework forge has a profile for." % label(languages[0])
    return "none", "no manifests or source files found. Is this the project's top folder?"


def describe(root):
    """Read the manifests under ROOT and describe the stack: the dict that --json prints."""
    files = project_files(root)
    found = {"declared": {"php": {}, "node": {}, "python": {}}, "locked": {}, "databases": [], "images": [],
             "notes": [], "managers": []}
    for path in files:
        read_manifest(root, path, found)
    items = known_items(root, files, found)
    frameworks = [item for item in items if item["role"] not in ("test", "theming")]
    languages = find_languages(found, files)
    ci = []
    for name, pattern in STACKS["ci_files"].items():  # from the top folder: the pattern fits the whole path
        add_item(ci, name, next((path for path in files if fnmatch.fnmatchcase(path, pattern)), None), role="ci")
    containers = [path for path in files if matches(path, STACKS["container_files"])]
    profile, reason = pick_profile(frameworks, languages, found["databases"], files)
    return {"path": os.path.abspath(root), "profile": profile, "reason": reason, "languages": languages,
            "frameworks": frameworks, "databases": found["databases"], "containerised": bool(containers),
            "container_files": containers, "images": found["images"],
            "tests": [item for item in items if item["role"] == "test"], "ci": ci, "notes": found["notes"],
            "theming": [item for item in items if item["role"] == "theming"], "package_managers": found["managers"]}


def format_human(result):
    """The plain-text report. What does not print shows as an escape (\\n): a file name cannot add lines."""
    def show(items):
        return ", ".join(label(item) for item in items) or "none found"
    containers = "yes: " + ", ".join(result["container_files"]) if result["containerised"] else "no"
    lines = ["Project:     " + result["path"], "", "Languages:   " + show(result["languages"]),
             "Frameworks:  " + show(result["frameworks"]), "Databases:   " + show(result["databases"]),
             "Containers:  " + containers, "Images:      " + (", ".join(result["images"]) or "none"),
             "Tests:       " + show(result["tests"]), "CI:          " + show(result["ci"]),
             "Theming:     " + show(result["theming"]), "Package manager: " + show(result["package_managers"]), "",
             "Closest forge profile: " + result["profile"], "Why: " + result["reason"]]
    lines += ["Note: " + note for note in result["notes"]]
    return "\n".join("".join(c if c.isprintable() else repr(c)[1:-1] for c in line) for line in lines)


def main(argv=None):
    """Run from the command line. Returns the exit code: 0, or 2 for a bad path."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="backslashreplace")  # cp1252 pipes: escapes, no crash
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("path", help="the project folder")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.path):
        print("error: %s is not a folder that exists" % args.path, file=sys.stderr)
        return 2
    print(json.dumps(describe(args.path), indent=2) if args.json else format_human(describe(args.path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
