#!/usr/bin/env python3
"""Which database the app's own tests reach, before anyone runs them.

Tests can empty the database they reach (Laravel's RefreshDatabase runs migrate:fresh, a set-up can truncate
it). This reads the test settings, also of each workspace (package.json, pnpm-workspace.yaml) and each folder
one down with a set-up of its own, and says per stack whether the tests use the database the app on this
machine uses. It runs, installs and connects to nothing, and never shows a password. Its data: testdb.json.
- laravel (artisan): phpunit.xml(.dist) <env> (force="true" or not) and <server>; .env.testing when APP_ENV is
  testing, else .env; a URL (DB_URL, DATABASE_URL) names the driver and the database. The shell's and a compose
  file's DB_ variables (env_file, environment) win over an <env> without force: not sure when the tests then
  reach the app's database, a value cannot be seen (outside the project, ${NAME}) or the config is cached.
- django (manage.py): its test runner makes test_<NAME>; a TEST NAME that is the NAME is not one of its own.
- node (package.json with a test script): the database variables (DATABASE_URL, DB_*, *_DB, ...) of .env.test
  and the test set-up files against .env and .env.local; TEST_DATABASE_URL when a set-up, config or test file
  reads it. No database package (nor a workspace it uses that lists one) and no node:sqlite or bun:sqlite
  import: no database to empty, unless a test file resets or empties one (listed for every stack).

Usage:
    python3 testdb.py .            the project in this folder
    python3 testdb.py ../shop --json

Exit codes:
    0  every test set-up found uses a database of its own, or none: running the tests is safe
    1  the tests reach the database the app uses here, or this script cannot tell: ask the user first
    2  PATH is not a folder
"""

import argparse
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ElementTree

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdb.json"), encoding="utf-8") as handle:
    DATA = json.load(handle)  # next to this script: database packages, test runners, what resets a database
SKIP = set(".git node_modules vendor venv .venv __pycache__ dist build .next coverage forge-work".split())
MAX_BYTES = 1024 * 1024  # a bigger settings file is not read
LARAVEL_KEYS = ("DB_CONNECTION", "DB_DATABASE", "DB_URL", "DATABASE_URL")
RESETS = re.compile("|".join(DATA["resets"]))
DB_NAME = re.compile(r"(?i)^(?!\w*(?:PASS|PWD|SECRET|TOKEN|KEY|AUTH|CREDENTIAL|USER))(?:\w*DATABASE\w*|DB_\w+|\w+_DB"
                     r"|\w*(?:SQLITE|POSTGRES|MYSQL|MARIADB|MONGO|LIBSQL|TURSO)\w*|PGDATABASE)$")  # never a password
BUILT_IN = re.compile(r"""["']((?:node|bun):sqlite)["']""")  # a database with no package to list
CODE = (".js", ".mjs", ".cjs", ".ts", ".mts", ".cts", ".jsx", ".tsx")
TEST_FILE = re.compile(r"(?:^|/)(?:tests?|__tests__|spec)/|\.(?:test|spec)\.[cm]?[jt]sx?$")
COMPOSE = re.compile(r"(?:docker-)?compose(?:\.[\w-]+)?\.ya?ml$")
ENV_FILE = re.compile(r"(?m)^([ \t]*)env_file[ \t]*:(.*(?:\n\1[ \t]+\S.*)*)")  # the line and those below it
UNSEEN = re.compile(r"<unknown: ([^>]+)>")
ENVIRONMENT = re.compile(r"(?m)^[ \t-]*[\"']?(%s)[\"']?[ \t]*[:=][ \t]*[\"']?([^\"'\s#]*)" % "|".join(LARAVEL_KEYS))
SET_IN_CODE = re.compile(r"""process\.env(?:\.(\w+)|\[\s*["'](\w+)["']\s*\])\s*=\s*["'`]([^"'`]*)["'`]""")
SET_IN_CONFIG = re.compile(r"""["']?(\w+)["']?\s*:\s*["'`]([^"'`]*)["'`]""")  # vitest's env: { NAME: 'value' }
READS = re.compile(r"""(?:process\.env|import\.meta\.env|Bun\.env)(?:\.(\w+)|\[\s*["'](\w+)["']\s*\])""")
SETUP_FILES = re.compile(r"""(?:setupFiles(?:AfterEnv)?|globalSetup)\s*:\s*(\[[^\]]*\]|["'][^"']+["'])""")
TEST_LIKE = re.compile(r"(?i)[_-]?test(?:ing)?\W*$")  # a database named for the tests: app_test, shop-testing
IN_MEMORY = re.compile(r":memory:|mode=memory")

def read(root, name):
    """The text of ROOT/NAME, or None when it is missing, a link, too big or unreadable."""
    path = os.path.join(root, name)
    if os.path.islink(path) or not os.path.isfile(path) or os.path.getsize(path) > MAX_BYTES:
        return None
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None

def dotenv(text, wanted):
    """{name: value} of the lines NAME=value in an .env text whose name WANTED accepts (comments and quotes off)."""
    found = {}
    for line in (text or "").splitlines():
        match = re.match(r"\s*(?:export\s+)?([A-Za-z_]\w*)\s*=\s*(.*)$", line)
        if match and wanted(match.group(1)):
            value = match.group(2).strip()
            quoted = len(value) > 1 and value[0] == value[-1] and value[0] in "\"'"
            found[match.group(1)] = value[1:-1] if quoted else re.sub(r"\s+#.*$", "", value)
    return found

def shown(value):
    """A database setting as it may be printed: no user or password (of a URL, or of key=value parts, quoted too)."""
    value = re.sub(r"(?i)[;&?\s]*\b(?:user(?:name| ?id)?|uid|password|passwd|pwd|auth_?token|token|secret)\s*=\s*"
                   r"(?:'(?:\\.|[^'\\])*'|\"(?:\"\"|[^\"])*\"|\{(?:\}\}|[^}])*\}|[^;&\s]*)", "", str(value))
    match = re.match(r"([a-z][\w+.-]*)://(?:[^@/]*@)?([^/?#]*)(/[^?#]*)?", value, re.I)
    return json.dumps("%s://%s%s" % (match.group(1), match.group(2), match.group(3) or "") if match else value[:120])

def identity(values):
    """(driver, database) of one Laravel connection: a URL's win over DB_CONNECTION and DB_DATABASE, as in Laravel."""
    match = re.match(r"([a-z][\w+.-]*)://(?:[^@/]*@)?[^/?#]*/?([^?#]*)", values.get("DB_URL") or values.get(
        "DATABASE_URL") or "", re.I)
    driver = ((match.group(1) if match else values.get("DB_CONNECTION")) or "the default").lower()
    return DATA["drivers"].get(driver, driver), (match and match.group(2)) or values.get("DB_DATABASE") or "the default"

def walk(root, top="", ends=(".php",) + CODE):
    """The files under ROOT/TOP that end in ENDS, outside SKIP and outside another package (its own package.json)."""
    found = []
    for folder, subfolders, files in os.walk(os.path.join(root, top)):
        subfolders[:] = sorted(name for name in subfolders if name not in SKIP and not os.path.isfile(
            os.path.join(folder, name, "package.json")))
        found += [os.path.relpath(os.path.join(folder, name), root).replace(os.sep, "/") for name in sorted(files)
                  if name.endswith(ends)]
    return found

def container(root, known):
    """The DB_ settings a compose file gives a container (env_file files, then environment lines, ${NAME:-x} from
    KNOWN). "<unknown: X>" where X cannot be seen: a file outside the project or unreadable, a ${NAME} not known."""
    found = {}
    for text in [read(root, name) or "" for name in sorted(os.listdir(root)) if COMPOSE.match(name)]:
        for file in [file for _, block in ENV_FILE.findall(text) for file in re.findall(r"[\w-]*[./][\w./-]*", block)]:
            values = read(root, file) if ".." not in file and file[0] != "/" else None
            found.update(dict.fromkeys(LARAVEL_KEYS, "<unknown: %s>" % file) if values is None else dotenv(
                values, LARAVEL_KEYS.__contains__))  # a file this cannot read may set any of them
        found.update((key, re.sub(r"\$\{?(\w+)(?::?-([^}]*))?\}?", lambda part: known.get(part.group(1)) or part.group(
            2) or "<unknown: ${%s}>" % part.group(1), value)) for key, value in ENVIRONMENT.findall(text))
    return found

def result(stack, kind, where, tests=None, app=None, reset=()):
    """One stack: KIND is own (a database of their own), same (the one the app uses here), unsure or none."""
    return {"stack": stack, "verdict": kind, "where": where, "tests": tests, "app": app, "resets": list(reset)}

def check_laravel(root):
    """phpunit.xml, .env.testing or .env, this shell, a container and a cached config: the tests' database."""
    name = next((name for name in ("phpunit.xml", "phpunit.xml.dist") if read(root, name) is not None), None)
    reset = [name for name in walk(root, "tests") if RESETS.search(read(root, name) or "")]  # each test file
    if not name:
        return result("laravel", "unsure", "no phpunit.xml: the tests' settings cannot be read", reset=reset)
    try:
        tree = ElementTree.fromstring(read(root, name))
    except ElementTree.ParseError as error:
        return result("laravel", "unsure", "%s is not valid XML (%s)" % (name, error), reset=reset)
    forced, loose = {}, {}
    for element in tree.iter():  # comments are left out: a DB line in a comment sets nothing
        if element.tag in ("env", "server") and element.get("name"):
            strong = element.tag == "server" or (element.get("force") or "").lower() == "true"
            (forced if strong else loose)[element.get("name")] = element.get("value") or ""
    shell = {key: os.environ[key] for key in LARAVEL_KEYS + ("APP_ENV", "APP_CONFIG_CACHE") if key in os.environ}
    first = {key: forced.get(key) or shell.get(key) or loose.get(key) for key in ("APP_ENV", "APP_CONFIG_CACHE")}
    cache = first["APP_CONFIG_CACHE"] or "bootstrap/cache/config.php"
    if os.path.isfile(os.path.join(root, cache)):
        return result("laravel", "unsure", "the config is cached (%s), so the tests use its database: `php artisan "
                      "config:clear` first, with the user's go, then run this again" % cache, reset=reset)
    env_file = ".env.testing" if first["APP_ENV"] == "testing" and read(root, ".env.testing") is not None else ".env"
    base, dot = dict(dotenv(read(root, env_file), LARAVEL_KEYS.__contains__), **loose), dotenv(read(
        root, ".env"), LARAVEL_KEYS.__contains__)  # the weakest first
    tests, app = {**base, **shell, **forced}, dict(dot, **shell)
    inside = container(root, {**dotenv(read(root, ".env"), DB_NAME.match), **{
        key: value for key, value in os.environ.items() if DB_NAME.match(key)}})  # a container's own DB_ variables
    said = [key for key in ("DB_DATABASE", "DB_URL", "DATABASE_URL") if key in forced or key in loose]
    where = "%s sets %s%s, the rest comes from %s" % (name, ", ".join(said) or "no database", " with force=\"true\""
                                                       * (bool(said) and all(key in forced for key in said)), env_file)
    named = ["%s database %s" % (pair[0], shown(pair[1])) for pair in map(identity, (tests, app, {
        **base, **inside, **forced}, {**dot, **inside}))]  # the tests and the app here, then both in a container
    same = identity(tests) == identity(app) and not IN_MEMORY.search(identity(tests)[1])
    unseen = sorted({hit for key, value in inside.items() if key not in forced for hit in UNSEEN.findall(value)})
    if not same and (unseen or inside and named[2] in named[1::2] and not IN_MEMORY.search(named[2])):
        there = ("some come from %s, which this script cannot see" % " and ".join(unseen), named[1]) if unseen else (
            "there the tests use %s; on this machine %s" % (named[2], named[0]), named[3])  # and the app's database
        return result("laravel", "unsure", where + ". In a container (docker compose exec) the DB_ variables of the "
                      "compose file win over an <env> without force=\"true\": " + there[0], named[0], there[1], reset)
    return result("laravel", "same" if same else "own", where, named[0], named[1], reset)

def check_django(root):
    """Django's test runner makes test_<NAME>; a TEST NAME equal to the NAME is the one exception."""
    hits = []
    for folder, subfolders, files in os.walk(root):
        subfolders[:] = [] if os.path.relpath(folder, root).count(os.sep) >= 2 else sorted(set(subfolders) - SKIP)
        for name in (name for name in sorted(files) if name.endswith(".py")):
            for block in re.findall(r"DATABASES\s*=\s*\{(.*?)\n\}", read(folder, name) or "", re.S):
                names = re.findall(r"[\"']NAME[\"']\s*:\s*([^,}\n]+)", block)
                test = re.findall(r"[\"']TEST[\"']\s*:\s*\{[^{}]*?[\"']NAME[\"']\s*:\s*([^,}\n]+)", block)
                hits += [(os.path.relpath(os.path.join(folder, name), root).replace(os.sep, "/"), names[0].strip(),
                          test[0].strip())] if names and test else []
    same = [hit for hit in hits if hit[1] == hit[2]]
    if same:
        return result("django", "same", "%s: its TEST NAME is its NAME" % same[0][0], same[0][2], same[0][1])
    return result("django", "own", "Django's test runner makes test_<NAME> (or the TEST NAME) and drops it "
                  "afterwards" + ("; %s sets TEST NAME %s" % (hits[0][0], hits[0][2]) if hits else ""))

def check_node(root, deps, linked=frozenset()):
    """.env.test and the set-up files against .env and .env.local; LINKED: workspaces that reach a database."""
    code = walk(root, "", CODE)
    specs = [name for name in code if TEST_FILE.search(name)]
    configs = [name for name in sorted(os.listdir(root)) if re.match(r"(vitest|vite|jest)\.(config|workspace)\.", name)]
    setups = [re.sub(r"^\./", "", path) for name in configs for found in SETUP_FILES.findall(read(root, name) or "")
              for path in re.findall(r"[\"']([^\"']+)[\"']", found)]
    setups += [name for name in DATA["setups"] if read(root, name) is not None]  # found without a config
    reset = [name for name in dict.fromkeys(setups + specs) if RESETS.search(read(root, name) or "")]
    clients = sorted(deps & (set(DATA["packages"]) | linked)) or sorted({hit for name in code for hit in
                                                                       BUILT_IN.findall(read(root, name) or "")})
    if not clients:
        return result("node", "unsure" if reset else "none", "package.json has no database package and no file "
                      "imports node:sqlite" + (", but test files empty a database" if reset else ""), reset=reset)
    tests, sources = {}, []
    for name in [".env.test", ".env.test.local"] + list(dict.fromkeys(setups)) + configs:
        text = read(root, name) or ""
        found = dotenv(text, DB_NAME.match) if name.startswith(".env") else {
            one or two: value for one, two, value in SET_IN_CODE.findall(text)}
        block = re.search(r"\benv\s*:\s*\{([^{}]*)\}", text) if name in configs else None  # vitest's test.env
        found.update(SET_IN_CONFIG.findall(block.group(1)) if block else [])
        found = {key: value for key, value in found.items() if DB_NAME.match(key)}
        tests, sources = {**tests, **found}, sources + [name] * bool(found)
    app = {key: value for name in DATA["app_env"] for key, value in dotenv(read(root, name), DB_NAME.match).items()}
    reads = {one or two for name in setups + configs + specs for one, two in READS.findall(read(root, name) or "")}
    named = {key: app.pop(key) for key in list(app) if "TEST" in key.upper()}  # TEST_DATABASE_URL: not the app's
    named.update({key: value for key, value in os.environ.items() if "TEST" in key.upper() and DB_NAME.match(key)})
    for key in [key for key in named if key not in tests and key in reads]:  # the tests' own, when they read it
        tests[key], sources = named[key], sources + ["this shell" if key in os.environ else "an .env file"]
    asked = sorted(key for key in reads if "TEST" in key.upper() and DB_NAME.match(key))
    uses = ", ".join("%s=%s" % (key, shown(value)) for key, value in sorted(app.items())) or None
    if not tests:
        return result("node", "unsure", "the test set-up reads %s, which is not set here: set it to a database of its "
                      "own (a name that ends in _test) when you run the tests" % ", ".join(asked) if asked else
                      "the app uses %s, and no .env.test or test set-up file sets a database variable"
                      % ", ".join(clients), app=uses, reset=reset)
    places = {shown(value) for value in app.values()}  # a database: its scheme, host and name, never who signs in
    own = [key for key in sorted(tests, key=lambda key: ("DATABASE" not in key.upper(), key))
           if IN_MEMORY.search(tests[key]) or (key in app and shown(tests[key]) != shown(app[key]))
           or (key not in app and TEST_LIKE.search(tests[key]))
           or ("TEST" in key.upper() and tests[key] and shown(tests[key]) not in places)]
    key = (own or sorted(tests, key=lambda key: ("DATABASE" not in key.upper(), key)))[0]
    where = "%s sets %s to %s" % (" and ".join(sources), key, shown(tests[key]))
    if not own and any(key not in app and "TEST" not in key.upper() for key in tests):
        return result("node", "unsure", where + ", which the app's .env files do not set", app=uses, reset=reset)
    match = key if key in app else (sorted(app, key=lambda name: (shown(app[name]) != shown(tests[key]), "DATABASE"
                                                                  not in name.upper(), name)) or [key])[0]
    return result("node", "own" if own else "same", where, "%s=%s" % (key, shown(tests[key])),
                  "%s=%s" % (match, shown(app.get(match, ""))), reset)

def projects(root, package):
    """Folders below ROOT with a project: the workspaces listed (package.json, pnpm-workspace.yaml) and one down."""
    listed = package.get("workspaces") if isinstance(package, dict) else None
    listed = listed.get("packages") if isinstance(listed, dict) else listed
    patterns = [item for item in (listed if isinstance(listed, list) else []) if isinstance(item, str)] + ["*"]
    patterns += re.findall(r"(?m)^\s*-\s*[\"']?([^\"'\s#]+)", read(root, "pnpm-workspace.yaml") or "")
    found = [os.path.relpath(os.path.dirname(path), root).replace(os.sep, "/") for pattern in patterns
             if not pattern.startswith("!") for name in ("package.json", "artisan", "manage.py")
             for path in sorted(glob.glob(os.path.join(glob.escape(root), pattern, name)))]
    return [name for name in dict.fromkeys(found) if name != "." and not set(name.split("/")) & (SKIP | {"e2e"})
            and not os.path.islink(os.path.join(root, name.split("/")[0]))]  # never through a symlink

def manifest(root):
    """ROOT's package.json and the names under its (dev)dependencies: ({}, set()) without one, None when broken."""
    try:
        package = json.loads(read(root, "package.json") or "{}")
    except ValueError:
        return None, set()
    package = package if isinstance(package, dict) else {}
    return package, {name for key in ("dependencies", "devDependencies") for name in (package.get(key) or {})}

def check(root, top=True, linked=frozenset()):
    """The result per stack this script knows, and one for a test set-up of another stack; at the top also those
    of each project below it (projects) that are not "none". LINKED: the workspaces that reach a database."""
    results, (package, deps) = [], manifest(root)
    results += [checker(root) for name, checker in (("artisan", check_laravel), ("manage.py", check_django))
                if os.path.isfile(os.path.join(root, name))]
    if package is None:
        results.append(result("node", "unsure", "package.json is not valid JSON"))
    folders, linked = projects(root, package) if top else [], set(linked)
    uses = [(str(item.get("name")), names) for item, names in (manifest(os.path.join(root, one)) for one in folders)
            if item]  # each workspace's name and what it lists
    for _ in uses:  # a workspace that lists a database package, or uses one that does (workspace:* or its name)
        linked |= {name for name, names in uses if names & (set(DATA["packages"]) | linked)}
    script = str(((package or {}).get("scripts") or {}).get("test") or "")
    if (script and "no test specified" not in script) or deps & set(DATA["runners"]):
        results.append(check_node(root, deps, linked))
    other = [name for name in DATA["other"] if os.path.isfile(os.path.join(root, name))][:0 if results else 1]
    results += [result(name, "unsure", "a stack this script does not read: find its test settings") for name in other]
    for folder in folders:
        results += [dict(item, stack="%s in %s" % (item["stack"], folder)) for item in check(os.path.join(
            root, folder), False, linked) if item["verdict"] != "none"]
    return results

def line(item):
    """One plain line per stack: its words (testdb.json), where they come from, the files that empty a database."""
    stack, app = item["stack"].split()[0], " (the app uses %s)" % item["app"] if item["app"] else ""
    words = DATA["words"][item["verdict"]] % dict(item, app=app, advice=DATA["advice"].get(stack, "a test database"))
    detail = " Tests: %(tests)s; the app: %(app)s." % item if item["verdict"] == "own" and item["app"] else ""
    reset = " %d file(s) reset or empty the database: %s." % (len(item["resets"]), ", ".join(item["resets"][:3])) \
        if item["resets"] else ""
    return "%s: %s (%s.)%s%s" % (item["stack"], words, item["where"], detail, reset)

def main(argv=None):
    """Read the arguments, check PATH, print the result and return the exit code."""
    for stream in (sys.stdout, sys.stderr):  # what the console cannot show comes out as \u escapes, not a crash
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("path", help="the project folder")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.path):
        print("error: %s is not a folder" % args.path, file=sys.stderr)
        return 2
    results = check(os.path.abspath(args.path))
    safe = all(item["verdict"] in ("own", "none") for item in results)
    print(json.dumps({"stacks": results, "safe": safe}, indent=2) if args.json else "\n".join(map(line, results))
          or "No test set-up found: no phpunit.xml, manage.py or package.json test script, so no test of its own runs.")
    return 0 if safe else 1

if __name__ == "__main__":
    sys.exit(main())
