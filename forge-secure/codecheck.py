#!/usr/bin/env python3
"""Quick first pass for risky code in PHP, Python and JavaScript/TypeScript files.

Flags patterns that often lead to security holes and says what, where, why and how to fix.
This is a first pass, not a full scanner: it misses some problems and can flag safe code. For
a deeper scan, run semgrep if it is installed. Lines containing forge:allow are not checked.
Skips node_modules, vendor, build and cache folders and symlinks; big or binary files get a warning.

Usage: python3 codecheck.py PATH [--json] [--fail-on critical|high|medium|low], for example
    python3 codecheck.py . --fail-on medium     (also fail on medium findings)
Exit codes: 0 nothing at or above --fail-on (default: high); 1 at least one finding at or
above it; 2 the path does not exist, cannot be read, or is a file this script cannot check.
"""

import argparse
import json
import os
import re
import sys

SEVERITIES = ["critical", "high", "medium", "low"]  # most severe first
SKIP_DIRS = {".git", "node_modules", "vendor", "venv", ".venv", "__pycache__", "dist", "build",
             ".next", ".nuxt", "out", "coverage", "storage/framework", ".cache", ".idea", ".vscode"}
MAX_BYTES = 1024 * 1024  # bigger files are not checked
LANGUAGES = {".php": "php", ".py": "python", ".js": "js", ".jsx": "js", ".ts": "js", ".tsx": "js",
             ".mjs": "js", ".cjs": "js", ".vue": "js", ".svelte": "js"}
FOOTER = "This is a first pass, not a full scanner. For a deeper scan, run semgrep if it is installed."

# Building blocks and plain-language reasons that the rules below share.
STRING = r"(?:\"[^\"]*\"|'[^']*')"  # a "double" or 'single' quoted string
NOT_METHOD = r"(?<![\w.$])"  # a plain call like eval, not obj.eval
NOT_METHOD_PHP = r"(?<![\w$>:])"  # a plain call like exec, not $db->exec or Foo::exec
PHP_INPUT = r"(?:\$_(?:GET|POST|REQUEST|COOKIE)\b|\$request->(?:input|get|query|post|cookie)\s*\()"
PHP_GLUED = (r"(?:\.=?\s*|\{)" + PHP_INPUT + r"|\$_(?:GET|POST|REQUEST|COOKIE)\[\w+\]"  # "..." . $_GET['id'], "$_GET[id]"
             r"|\bv?sprintf\s*\([^;]{0,300}?" + PHP_INPUT)  # or sprintf("... %s", $_GET['id'])
PHP_SQL = (r"(?i:\bselect\s.{1,200}?\sfrom\s|\binsert\s+into\s|\bupdate\s+\S+\s+set\s|\bdelete\s+from\s)"
           r"|(?:mysqli?_query|pg_query|(?<!request)->query|->exec)\s*\(")  # SQL, or a query call
PHP_SHELL = NOT_METHOD_PHP + r"(?:exec|system|passthru|shell_exec|popen|proc_open)\s*\(|`[^`]*" + PHP_INPUT  # or `...`
PHP_ECHO = r"(?:(?<![$'\">])\b(?:echo|print)\b|<\?=)[^;]{0,300}?" + PHP_INPUT  # echo ... $_GET[..]
PHP_RAW_VAR = (r"(?:DB::raw|\b(?:select|from|where|orWhere|having|orHaving|orderBy|groupBy)Raw)"
               r"\s*\(\s*(?:\$|\"[^\"]*\$|" + STRING + r"\s*\.\s*\$)")  # 1st argument holds a $var
PHP_ESCAPED = r"htmlspecialchars|htmlentities|strip_tags|intval|\(int\)|\be\("  # escaped output
PASSWORD = r"(?i)passw(?:or)?d|(?<![a-z])pass(?![a-z])"  # password, passwd, $pass; not bypass
PY_SQL = (r"\.(?:execute(?:many|script)?|raw|extra)\s*\(\s*(?:\w+\s*=\s*)?\[?\s*"  # 1st argument is
          r"(?:(?i:r?fr?)[\"']|(?:" + STRING + r"|[\w.]+)\s*(?:[%+]|\.format\s*\())")  # f"", or % + .format
CSRF_OFF = r"(?:@|[(\[,]\s*)csrf_exempt\b|\bcsrf_exempt\s*\("  # @decorator, list, call, wrapper
JS_BUILT = r"(?:`[^`]*\$\{|" + STRING + r"\s*\+|[\w.$]+\s*\+)"  # `...${x}...`, "..." + x, cmd + x
JS_EXEC = r"(?:(?<![\w.$])exec|\b(?:child_process|childProcess|cp|shell)\.exec|\bexecSync)\s*\(\s*"
JS_SQL = (r"\b(?:query|execute|raw|queryRawUnsafe|executeRawUnsafe)\s*\(\s*"  # a query call whose
          r"(?=[`\"']\s*(?i:select|insert|update|delete)\b)")  # 1st argument starts with SQL
JS_SET_HTML = r"\.(?:inner|outer)HTML\s*\+?=(?!=)(?!\s*([\"'`])\1\s*;?\s*(?://|$))"  # but not = ''
JS_TLS_OFF = (r"\brejectUnauthorized[\"']?\s*[:=]\s*false\b"  # in options, or for the whole app:
              r"|NODE_TLS_REJECT_UNAUTHORIZED[\"'\]]*\s*=\s*[\"']?0")
JS_CORS = (r"(?i)access-control-allow-origin[\"']?\s*[,:]\s*[\"']?\*|\borigin\s*:\s*[\"']\*[\"']"
           r"|\bcors\(\s*\)")  # cors() with no options also lets every origin in
RCE = "if outside input reaches it, an attacker can run their own code"
SHELL = "if any part comes from outside, an attacker can add commands and take over the server"
SQLI = "anyone who controls a value can rewrite the query and read, change or delete your data"
XSS = "input in it can add scripts to the page that steal visitors' logins (cross-site scripting)"
MITM = "anyone on the network path (public Wi-Fi, a hacked router) can read or change the traffic"
FORGED = "other sites can make a logged-in visitor's browser send this request"
PUBLIC = "NEXT_PUBLIC_ values are built into the JavaScript that every visitor downloads"


def rule(rule_id, severity, pattern, title, why, fix, also=None, unless=None, multiline=False):
    """A check: `pattern` matches, `also` (if given) matches too, `unless` (if given) does not."""
    return {"info": {"rule": rule_id, "severity": severity, "title": title, "why": why, "fix": fix},
            "pattern": re.compile(pattern), "also": re.compile(also) if also else None,
            "unless": re.compile(unless) if unless else None, "multiline": multiline}


PHP_RULES = [
    rule("php-eval", "critical", NOT_METHOD_PHP + r"eval\s*\(", "Text run as PHP code (eval)", RCE,
         "call the code directly; if your team did not write this line, look for a break-in"),
    rule("php-unserialize", "critical", r"\bunserialize\s*\(", "Visitor data read with unserialize",
         RCE, "use json_decode() for anything that comes from a visitor", also=PHP_INPUT),
    rule("php-sql", "critical", PHP_SQL, "Database query built from visitor input", SQLI,
         "use prepared statements with ? placeholders (PDO, mysqli, Laravel)", also=PHP_GLUED),
    rule("php-shell", "critical", PHP_SHELL, "Shell command built from visitor input", SHELL,
         "use escapeshellarg() on each input", also=r"(?<!escapeshellarg\()" + PHP_INPUT),
    rule("php-echo-input", "high", PHP_ECHO, "Visitor input printed into the page unescaped", XSS,
         "escape it with htmlspecialchars(), or use {{ }} in Blade", unless=PHP_ESCAPED),
    rule("php-blade-raw", "medium", r"\{!!", "HTML printed without escaping ({!! !!})", XSS,
         "use {{ }}, which escapes; keep {!! !!} only for HTML you built yourself"),
    rule("php-raw-sql", "high", PHP_RAW_VAR, "Raw database query with a PHP variable inside", SQLI,
         "pass values as bindings, such as whereRaw('price > ?', [$price])"),
    rule("php-weak-hash", "medium", r"(?i)\b(?:md5|sha1)\s*\(", "Password hashed with md5 or sha1",
         "these hashes are quick to crack", "use password_hash() instead", also=PASSWORD),
]
PY_RULES = [
    rule("py-eval", "high", NOT_METHOD + r"(?:eval|exec)\s*\(", "Text run as Python code", RCE,
         "remove it; read data with json.loads or ast.literal_eval instead"),
    rule("py-pickle", "high", r"\bc?[pP]ickle\.loads?\s*\(", "Data loading that can run code", RCE,
         "use json for data from outside; unpickle only files you made yourself"),
    rule("py-yaml-load", "medium", r"\byaml\.(?:unsafe_)?load(?:_all)?\s*\(", "Unsafe YAML loading",
         RCE, "use yaml.safe_load() or Loader=yaml.SafeLoader", unless="SafeLoader"),
    rule("py-shell-true", "high", r"\bshell\s*=\s*True\b", "Command run through the shell", SHELL,
         "drop the shell option and pass a list, such as subprocess.run(['convert', path])"),
    rule("py-os-system", "medium", r"\bos\.system\s*\(", "Shell command run with os.system", SHELL,
         "use subprocess.run() with a list of arguments"),
    rule("py-sql", "critical", PY_SQL, "Database query built with string formatting", SQLI,
         "pass values separately: cursor.execute('... WHERE id = %s', [user_id])", multiline=True),
    rule("py-verify-false", "high", r"\bverify\s*=\s*False\b", "Certificate check turned off", MITM,
         "remove that option; for your own certificate authority pass verify='/path/to/ca.pem'"),
    rule("py-debug", "medium", r"^\s*DEBUG\s*=\s*True\b", "Debug mode on",
         "error pages show settings and code", "read it from the environment; off in production"),
    rule("py-allowed-hosts", "medium", r"\bALLOWED_HOSTS\s*\+?=.{0,200}?[\"']\*[\"']",
         "Any host name accepted", "attackers can make password-reset emails link to their site",
         "list your own domain names, such as ['example.com']"),
    rule("py-mark-safe", "medium", r"\bmark_safe\s*\(", "HTML escaping turned off (mark_safe)", XSS,
         "use format_html(), which escapes each value, or escape() the input first"),
    rule("py-csrf-exempt", "medium", CSRF_OFF, "Forged-request protection turned off", FORGED,
         "remove the exemption; for a webhook, check its signature instead", unless=r"\bimport\b"),
]
JS_RULES = [
    rule("js-eval", "high", NOT_METHOD + r"eval\s*\(|\bnew\s+Function\s*\(",
         "Text run as JavaScript code", RCE, "use JSON.parse() for data and functions for logic"),
    rule("js-raw-html", "medium", r"dangerouslySetInnerHTML|\bv-html\s*=|\{@html|" + JS_SET_HTML,
         "Raw HTML put into the page", XSS, "clean it with DOMPurify.sanitize()", unless="(?i)sanitize"),
    rule("js-shell", "high", JS_EXEC + JS_BUILT, "Shell command built from a string", SHELL,
         "use execFile() or spawn() with a list of arguments, not exec", multiline=True),
    rule("js-sql", "critical", JS_SQL + JS_BUILT, "Database query built from a template or +", SQLI,
         "use placeholders, such as db.query('... WHERE id = $1', [id])", multiline=True),
    rule("js-tls-off", "high", JS_TLS_OFF, "Certificate check turned off", MITM,
         "remove it; to trust your own certificates use the ca option or NODE_EXTRA_CA_CERTS"),
    rule("js-cors-any", "medium", JS_CORS, "Any website may call this API",
         "other sites can use it from your visitors' browsers", "list the sites that may call it"),
    rule("js-next-public", "high", r"\bNEXT_PUBLIC_\w*(?:SECRET|PRIVATE|PASSWORD|TOKEN)",
         "Secret sent to every browser", PUBLIC, "drop the prefix and use it in server code only"),
]
RULES = {"php": PHP_RULES, "python": PY_RULES, "js": JS_RULES}


def fires(rule, lines, index):
    """True when the rule matches line `index` (multiline rules read on while ( or ` is open)."""
    line = text = lines[index]
    if rule["multiline"] and (line.count("(") > line.count(")") or line.count("`") % 2):
        text = "\n".join(lines[index:index + 20])  # read on for at most 20 lines
    match = rule["pattern"].search(text)
    if not match or match.start() >= len(line):  # a match that starts on a later line is not ours
        return False
    if rule["also"] and not rule["also"].search(text):
        return False
    return not (rule["unless"] and rule["unless"].search(text))


def scan_text(text, language, where):
    """Check the text of one file. `where` is the path shown in the report. No file access."""
    lines, findings = re.split(r"\r\n?|\n", text), []
    for index, line in enumerate(lines):
        for rule in RULES[language]:
            if "forge:allow" not in line and fires(rule, lines, index):
                place = {"where": "%s:%d" % (where, index + 1), "file": where, "line": index + 1}
                findings.append(dict(rule["info"], **place))
    return findings


def language_of(path):
    """Return "php", "python" or "js" for a file type we check, else None."""
    return LANGUAGES.get(os.path.splitext(path)[1].lower())


def files_under(folder):
    """Yield (full path, path shown in the report) for each file of a known type under folder."""
    os.listdir(folder)  # raises OSError when the folder itself cannot be read
    for parent, dirs, files in os.walk(folder, onerror=lambda e: warn(e.filename, e.strerror)):
        here = os.path.basename(os.path.abspath(parent))  # to spot storage/framework
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and here + "/" + d not in SKIP_DIRS)
        for name in sorted(files):  # os.walk skips symlinked folders; we skip symlinked files
            full = os.path.join(parent, name)
            if language_of(name) and os.path.isfile(full) and not os.path.islink(full):
                yield full, os.path.relpath(full, folder).replace(os.sep, "/")


def scan_path(path):
    """Return (findings, files checked) for a file or folder. Raises ValueError or OSError."""
    is_file = os.path.isfile(path)
    if not is_file and not os.path.isdir(path):
        raise ValueError("%s does not exist, or is not a file or folder" % path)
    if is_file and not language_of(path):
        raise ValueError("%s is not a PHP, Python or JS/TS file" % path)
    findings, checked = [], 0
    for full, shown in [(path, path)] if is_file else files_under(path):
        shown = os.fsencode(shown).decode("utf-8", errors="backslashreplace")  # always printable
        try:
            with open(full, "rb") as handle:
                data = handle.read(MAX_BYTES + 1)
        except OSError as error:
            warn(shown, error.strerror)
            continue
        if len(data) > MAX_BYTES or b"\0" in data[:8192]:
            warn(shown, "binary file, or over 1 MB")
            continue
        findings += scan_text(data.decode("utf-8", errors="replace"), language_of(full), shown)
        checked += 1
    if is_file and not checked:
        raise ValueError("could not check %s (see the warning above)" % path)
    return findings, checked


def warn(name, reason):
    """Tell the user that a file or folder was not checked, and why."""
    print("warning: not checked: %s (%s)" % (name, reason), file=sys.stderr)


def format_human(findings, summary):
    """One block per finding, then a one-line summary and the footer."""
    lines = []
    for finding in findings:
        label = finding["severity"].upper()
        pad = " " * (len(label) + 2)
        lines += [label + "  " + finding["title"], pad + "where: " + finding["where"],
                  pad + "why:   " + finding["why"], pad + "fix:   " + finding["fix"], ""]
    total, checked = summary["total"], summary["files_checked"]
    counts = ", ".join("%d %s" % (summary[s], s) for s in SEVERITIES if summary[s])
    if not checked:
        result = "Nothing was checked: no PHP, Python or JS/TS file was found and read."
    elif not total:
        result = "No findings."
    else:
        result = "%d %s: %s." % (total, "finding" if total == 1 else "findings", counts)
    return "\n".join(lines + [result, "Files checked: %d (PHP, Python, JS/TS)." % checked, FOOTER])


def main(argv=None):
    """Check the path from the command line, print the report and return the exit code."""
    parser = argparse.ArgumentParser(description="Quick first-pass check for risky code.")
    parser.add_argument("path", help="file or folder to check")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="high",
                        help="exit 1 when a finding is this severe or worse (default: high)")
    args = parser.parse_args(argv)
    try:
        findings, checked = scan_path(args.path)
    except (OSError, ValueError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    findings.sort(key=lambda f: (SEVERITIES.index(f["severity"]), f["file"], f["line"]))
    summary = {s: sum(f["severity"] == s for f in findings) for s in SEVERITIES}
    summary.update(total=len(findings), files_checked=checked)
    report = {"findings": findings, "summary": summary, "note": FOOTER}
    print(json.dumps(report, indent=2) if args.json else format_human(findings, summary))
    limit = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f["severity"]) <= limit for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
