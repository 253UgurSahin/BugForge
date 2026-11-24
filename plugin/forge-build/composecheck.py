#!/usr/bin/env python3
"""Check docker-compose files for settings that make the app unsafe or fragile.

packcheck.py runs this for the compose part of its check; it also works on its own. Reads
docker-compose.yml, compose.yaml and the like in PATH with plain line checks, no YAML library.
Each finding says what, where, why it matters and how to fix it: see the RULES table below.

Usage:
    python3 composecheck.py .                    check the compose files in the current folder
    python3 composecheck.py . --json             machine-readable output
    python3 composecheck.py . --fail-on medium   also fail on medium findings

docker-compose.override.yml and other extra files (compose.prod.yaml) add to the main file
(docker-compose.yml, compose.yaml): a service the main file has keeps its restart policy, build and
image from there. Every rule about safety still applies to them.

A line with a forge:allow comment is not reported. Limits: block-style YAML, the way compose files
are usually written (one-line lists such as ports: ["80:80"] are read too): no extends:, include:
or anchors. A file without a services: block at the start of a line (JSON, for example), or with a
service written as {...}, cannot be checked: exit 2. So are files over 1 MB and links to files
outside PATH. The JSON summary also says whether a service has a healthcheck that is on, and which
Dockerfile stages the services build (packcheck.py uses both).

Exit codes:
    0  nothing at or above --fail-on (default: high)
    1  at least one finding at or above --fail-on
    2  bad usage, no compose file in PATH, or a file could not be read or checked
"""

import os
import re
import sys

from _pack import COMPOSE_FILE, SEVERITIES, arguments, is_written_secret, read, report, unquote  # next to this script

MAIN_FILE = re.compile(r"^(?:docker-)?compose\.ya?ml$")  # the others add to it
ENV_PAIR = re.compile(r"""(?:- )?['"]?([\w.-]+)['"]?\s*(?:=|:\s|:$)(.*)$""")  # NAME: value, - NAME=value
TRUE = r"""['"]?(?i:true|yes|on|y)['"]?$"""  # every value compose reads as true
TOP_RULES = [("privileged", r"privileged:\s*" + TRUE), ("host_net", r"network_mode:\s*['\"]?host\b"),
             ("root", r"user:\s*['\"]?(?:root|0)(?:[:'\"]|$)")]  # keys of the service itself
DATABASES = {"postgres", "postgresql", "postgis", "pgvector", "timescaledb", "timescaledb-ha", "mysql",
             "mysql-server", "mariadb", "percona", "percona-server", "mongo", "mongodb", "redis", "redis-stack",
             "redis-stack-server", "valkey", "keydb", "memcached", "elasticsearch", "opensearch", "couchdb",
             "clickhouse", "clickhouse-server", "cassandra", "influxdb", "cockroach", "mssql", "neo4j"}
LOOPBACK = ("127.", "[::1]", "::1", "localhost")

# rule: (severity, title, why, fix). {0} is the service, {1} a name or an image.
RULES = {
    "privileged": ("critical", "Service {0} runs privileged", "a privileged container can take over the host",
                   "remove privileged: true; add only the capability it needs with cap_add"),
    "sock": ("critical", "Service {0} mounts the Docker socket",
             "whoever controls this container controls Docker, and so the whole machine",
             "remove the docker.sock volume"),
    "secret": ("critical", "Service {0} has the value of {1} written in the compose file",
               "the compose file is shared through git, and the secret with it",
               "move the value to .env and load it with env_file: .env, or write ${{{1}}} here"),
    "db_port": ("high", "Database service {0} is reachable from other machines",
                "its port is open on every network the machine is on",
                "remove the ports: entry (the app reaches it by name) or bind it to 127.0.0.1"),
    "root": ("high", "Service {0} runs as root", "its user: line overrides the image's USER; if someone "
             "breaks into the app, they are root in the container", "remove the user: line"),
    "host_net": ("medium", "Service {0} uses the host network", "every port it opens is open on the machine",
                 "remove network_mode: host and publish only the ports you need"),
    "tag": ("medium", "Image {1} of service {0} is not pinned to a version",
            "a pull can change it under you; a database image can move your data to a new major version",
            "pin a version, at least major.minor, for example postgres:18-alpine"),
    "no_restart": ("low", "Service {0} has no restart policy", "after a crash or a reboot it stays down",
                   "add restart: unless-stopped (a one-off job, such as a migration: restart: \"no\")"),
}


def finding(rule, path, line, *words):
    severity, title, why, fix = RULES[rule]
    return {"severity": severity, "title": title.format(*words), "where": "%s:%d" % (path, line), "why": why,
            "fix": fix.format(*words), "rule": rule, "file": path, "line": line}


def is_pinned(image):
    """True for an image with a version tag or a digest, or a variable. postgres:18 yes; postgres,
    postgres:latest and localhost:5000/db no."""
    tag = image.rsplit("/", 1)[-1].partition(":")[2]  # localhost:5000/db:18 -> 18
    return tag not in ("", "latest") or "@" in image or "$" in image


def is_database(image, service):
    """True for a database image (postgres:18, bitnami/mariadb) or a service named db, app-db or redis."""
    parts = {part.split(":")[0].lower() for part in image.split("@")[0].split("/")}
    named = service.lower() in DATABASES or re.search(r"(?:^|[-_])(?:db|database)$", service.lower())
    return bool(parts & DATABASES or named)


def compose_services(text):
    """{service: [(line number, keys, text)]} for each service in the services: block. KEYS are the
    keys a line sits under inside its service: ("build", "args") for an entry under build: args:.
    The first entry is the service's own line. Comments are cut off."""
    services, entries, stack = {}, None, []  # stack: (indent, key) of each key above the line
    inside, service_indent = False, None  # in the services: block; how far its services are indented
    for number, raw in enumerate(text.splitlines(), 1):
        line = re.sub(r"(?:^|\s+)#.*$", "", raw).rstrip()  # a ' #' inside quotes is cut too: a known limit
        stripped, indent = line.strip(), len(line) - len(line.lstrip())
        if not stripped:
            continue
        if indent == 0:
            inside = stripped.startswith("services:")
            entries, service_indent = None, None
        elif inside and indent <= (service_indent or indent):
            service_indent, stack = indent, []
            entries = services.setdefault(unquote(stripped.split(":")[0]), [(number, (), stripped)])
        elif entries is not None:
            depth = indent + 1 if stripped.startswith("-") else indent  # "- x" may sit level with its key
            while stack and stack[-1][0] >= depth:
                stack.pop()
            entries.append((number, tuple(key for _, key in stack), stripped))
            key = re.match(r"""['"]?([\w.-]+)['"]?:(?:\s|$)""", stripped)  # a key, not a "- item"
            if key:
                stack.append((indent, key.group(1)))
    return services


def flow_items(text):
    """The items of a one-line flow list or map: '["a", b]' -> ['"a"', 'b'], '{A: b}' -> ['A: b']."""
    return [item.strip() for item in text.strip()[1:-1].split(",") if item.strip()]


def check_service(name, lines, path, main=()):
    """(findings, has a healthcheck that is on, build target or None) for one service. MAIN: its
    lines in the main file when this is an override file, for what it keeps from there."""
    findings, ports = [], []  # ports: [line number, the host IP it is bound to]
    image, target, built, health = None, None, False, False
    for number, keys, line in lines[1:]:
        top = keys == ()  # a key of the service itself
        findings += [finding(rule, path, number, name) for rule, pattern in TOP_RULES
                     if top and re.match(pattern, line)]
        if "docker.sock" in line:
            findings.append(finding("sock", path, number, name))
        flow = re.match(r"(?:environment|args):\s*([\[{].*)$", line)
        if flow and keys in ((), ("build",)):
            pairs = flow_items(flow.group(1))  # environment: ["A=b"] or {A: b}
        else:
            pairs = [line] if keys[-1:] == ("environment",) or keys[-2:] == ("build", "args") else []
        for pair in [ENV_PAIR.match(item) for item in pairs]:
            if pair and is_written_secret(pair.group(1), pair.group(2)):
                findings.append(finding("secret", path, number, name, pair.group(1)))
        if top and re.match(r"ports:\s*\[", line):  # ports: ["5432:5432"]
            ports += [[number, unquote(item)] for item in flow_items(line.split(":", 1)[1])]
        if keys == ("ports",) and line.startswith("- "):  # "127.0.0.1:5432:5432", or long syntax
            item = unquote(line[2:])
            ports.append([number, "" if re.match(r"[a-z_]+:\s", item) else item])
        if keys == ("ports",) and re.match(r"(?:- )?host_ip:", line) and ports:
            ports[-1][1] = unquote(line.split(":", 1)[1])
        if top and line.startswith("image:"):
            image = (number, unquote(line.split(":", 1)[1]))
        built = built or (top and line.startswith("build:"))
        if top and line.startswith("healthcheck:"):
            health = True
        if keys == ("healthcheck",) and re.match(r"disable:\s*" + TRUE + r"|test:\W*NONE\b", line):
            health = False  # disable: true, or test: ["NONE"]
        if keys == ("build",) and line.startswith("target:"):
            target = unquote(line.split(":", 1)[1]).lower()
    kept = [line for _, keys, line in main[1:] if keys == ()]  # from the main file
    built = built or any(line.startswith("build:") for line in kept)
    if image and not built and not is_pinned(image[1]):  # with build:, image: names the built image
        findings.append(finding("tag", path, image[0], name, image[1]))
    kept_image = next((unquote(line.split(":", 1)[1]) for line in kept if line.startswith("image:")), "")
    if is_database(image[1] if image else kept_image, name):
        findings += [finding("db_port", path, number, name) for number, bound in ports
                     if not bound.startswith(LOOPBACK)]
    if not any(re.match(r"restart(?:_policy)?:", line) for _, _, line in lines[1:] + list(main[1:])):
        findings.append(finding("no_restart", path, lines[0][0], name))
    return findings, health, target


def check_compose(text, path, main=None):
    """(findings, has a healthcheck, build targets) for the text of one compose file. MAIN: the
    services of the main file when this file adds to it. Raises ValueError when it has no
    services: block that this script can read."""
    services = compose_services(text)
    if not services:
        raise ValueError("could not read the services in %s: it must be block-style YAML with "
                         "services: at the start of a line" % path)
    findings, healthcheck, targets, raw = [], False, set(), text.splitlines()
    for service, lines in services.items():
        if re.match(r"[^:]+:\s*\{", lines[0][2]):  # app: {image: x}, a one-line map
            raise ValueError("could not read service %s in %s: write it as block-style YAML" % (service, path))
        found, has_check, target = check_service(service, lines, path, (main or {}).get(service, ()))
        findings += [f for f in found if "forge:allow" not in raw[f["line"] - 1]]  # the user's opt-out
        healthcheck = healthcheck or has_check
        targets |= {target} if target else set()
    return findings, healthcheck, targets


def check_folder(root):
    """(findings sorted most severe first, files checked, has a healthcheck, build targets)."""
    findings, checked, healthcheck, targets, main = [], [], False, set(), {}
    texts = {name: read(root, name) for name in sorted(os.listdir(root)) if COMPOSE_FILE.match(name)}
    for name in [name for name in texts if MAIN_FILE.match(name)]:
        for service, lines in compose_services(texts[name]).items():
            main.setdefault(service, lines)
    for name, text in texts.items():
        found, has_check, built = check_compose(text, name, None if MAIN_FILE.match(name) else main)
        findings += found
        healthcheck = healthcheck or has_check
        targets |= built
        checked.append(name)
    if not checked:
        raise ValueError("no compose file (docker-compose.yml, compose.yaml, ...) in " + root)
    findings.sort(key=lambda f: SEVERITIES.index(f["severity"]))
    return findings, checked, healthcheck, sorted(targets)


def main(argv=None):
    args = arguments("Check docker-compose files for unsafe settings.", argv)
    if not os.path.isdir(args.path):
        print("error: %s is not a folder that exists" % args.path, file=sys.stderr)
        return 2
    try:
        findings, checked, healthcheck, targets = check_folder(args.path)
    except (OSError, ValueError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    return report(findings, checked, args, healthcheck=healthcheck, targets=targets)

if __name__ == "__main__":
    sys.exit(main())
