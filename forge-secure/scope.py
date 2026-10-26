#!/usr/bin/env python3
"""Decide whether ACTIVE tests may run against a target. Run it before any active test.

ALLOWED (scans, fuzzing, injection, brute force and load tests may run):
  - localhost, names ending in .localhost or .test, and 0.0.0.0
  - loopback and private addresses: 127.x, 10.x, 172.16-31.x, 192.168.x, ::1, fc00::/7
  - a single name without dots (db, web, my_api): a container or compose service. Run those
    tests from inside your docker network: elsewhere the name may reach another machine.
  - a domain listed in the scope file, or any subdomain of it
PASSIVE ONLY: everything else, such as public sites and IPs, cloud metadata (169.254.x, fe80::),
carrier networks (100.64.x), odd IP spellings (2130706433, 0x7f000001), look-alikes, nip.io names
and bare top-level domains (com). The host is read the way curl reads it (after the scheme and
the last "@"), then normalised (case, trailing dot, IDNA). No DNS lookups. Passwords never show.

Scope file, default forge-work/scope.json in the current folder (only the user adds to it):
    {"own_domains": ["example.com", "app.example.org"]}
Entries are domains with at least one dot: no https://, port, path or wildcard. Names that many
owners share (github.io, herokuapp.com, co.uk, nip.io) are refused. No file: no domain is yours.

Usage:
    python3 scope.py localhost:8080
    python3 scope.py https://staging.example.com/login
    python3 scope.py 192.168.1.20 --scope my-scope.json --json

Exit codes:
    0  ALLOWED: active tests may run against this target
    1  PASSIVE ONLY: no active tests; passive checks (load a page, read headers) are fine
    2  bad input: unreadable target (IPv6 zone ids like %eth0 too), broken or missing scope file
"""

import argparse
import ipaddress
import json
import os
import re
import sys

DEFAULT_SCOPE = os.path.join("forge-work", "scope.json")
PASSIVE_HINT = "Passive checks only (load a page, read headers): no scans, fuzzing or load tests."
NOT_LISTED = "not in the scope file, and not localhost, a private address or a container name"
ADD_TO_SCOPE = 'if %s is yours, confirm it, then add it to the scope file: {"own_domains": ["%s"]}'

SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)  # http://, https://, postgres://
PORT = re.compile(r"^:[0-9]{1,5}$")  # :8080
LABEL = re.compile(r"^[a-z0-9_][a-z0-9_-]{0,62}$")  # one dot-separated part of a name, after IDNA
CONTAINER = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")  # compose service names: db, web, my_api
NUMBER = re.compile(r"^([0-9]+|0x[0-9a-f]*)$")  # 127, 0177 or 0x7f: one part of an IP address
PLAIN_IPV4 = re.compile(r"^(0|[1-9][0-9]{0,2})(\.(0|[1-9][0-9]{0,2})){3}$")  # 127.0.0.1
IP_INSIDE = re.compile(r"(^|\.)[0-9]{1,3}(\.[0-9]{1,3}){3}\.")  # 127.0.0.1.nip.io

TOP_LEVEL = {"com", "net", "org", "info", "biz", "io", "ai", "co", "me", "nl", "be", "de", "eu"}
SHARED = {"github.io", "gitlab.io", "herokuapp.com", "vercel.app", "netlify.app", "pages.dev",
          "web.app", "firebaseapp.com", "appspot.com", "azurewebsites.net", "cloudfront.net",
          "amazonaws.com", "co.uk", "org.uk", "com.au", "co.nz", "nip.io", "sslip.io"}

NETWORKS = [  # (network, allowed, reason); an IP outside all of these is passive only
    ("127.0.0.0/8", True, "a loopback address: this machine"),
    ("::1/128", True, "the IPv6 loopback address: this machine"),
    ("0.0.0.0/32", True, "0.0.0.0 means this machine"),
    ("10.0.0.0/8", True, "a private network address (10.x)"),
    ("172.16.0.0/12", True, "a private network address (172.16.x to 172.31.x)"),
    ("192.168.0.0/16", True, "a private network address (192.168.x)"),
    ("fc00::/7", True, "a private IPv6 address (fc00::/7)"),
    ("169.254.0.0/16", False, "a link-local address: cloud metadata services live here"),
    ("fe80::/10", False, "an IPv6 link-local address: cloud metadata services live here"),
    ("100.64.0.0/10", False, "a carrier network address (100.64.x), shared with other customers"),
]


def read_host(target):
    """(host, whether a login "user@" came first) from a URL, host, host:port or IP address.
    Like curl: the host comes after the scheme and the last "@", before the port and / ? #."""
    if any(ch.isspace() or not ch.isprintable() or ch == "\\" for ch in target):
        raise ValueError("it contains spaces, invisible characters or backslashes")
    scheme = SCHEME.match(target)
    rest = target[scheme.end():] if scheme else target
    for end in "/?#":  # the host part stops at the first / ? or #
        rest = rest.split(end)[0]
    _, at, host_port = rest.rpartition("@")  # the host comes after the last "@"
    if "%" in host_port:  # zone ids (fe80::1%eth0): Python and curl read them differently
        raise ValueError("it has a % in the host: leave out IPv6 zone ids (%eth0) and %-codes")
    if host_port.startswith("["):  # [::1] or [::1]:8080
        host, bracket, port = host_port[1:].partition("]")
        if not bracket or ":" not in host:
            raise ValueError("square brackets are only for IPv6 addresses, like [::1]:8080")
    elif host_port.count(":") > 1 and not (scheme or at):  # a bare IPv6 address such as ::1
        host, port = host_port, ""
    else:
        host, colon, port = host_port.partition(":")
        port = colon + port
    if port and not (PORT.match(port) and 0 < int(port[1:]) <= 65535):  # port is "" or ":8080"
        raise ValueError("the port must be a number from 1 to 65535")
    return host, bool(at)


def normalize_name(name):
    """A host name as lowercase ASCII without a trailing dot, the way DNS sees it. ValueError if
    invalid. International names become punycode (bücher.de -> xn--bcher-kva.de)."""
    name = name.lower()
    if "ß" in name or "ς" in name:  # browsers and curl turn these into a different domain
        raise ValueError("it contains ß or ς, which tools read differently; use punycode (xn--)")
    try:
        name = name.encode("idna").decode("ascii")  # also folds fullwidth letters and dots
    except UnicodeError:
        raise ValueError("not a valid host name")
    name = name[:-1] if name.endswith(".") else name  # example.com. is example.com
    if len(name) > 253 or not all(LABEL.match(label) for label in name.split(".")):
        raise ValueError("not a valid host name")
    return name


def check_ip(ip):
    """(allowed, reason) for one IP address."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return check_ip(ip.ipv4_mapped)  # ::ffff:127.0.0.1 is 127.0.0.1 written as IPv6
    for network, allowed, reason in NETWORKS:
        if ip in ipaddress.ip_network(network):
            return allowed, reason
    return False, "an IP address outside this machine and your private networks"


def check_name(name, own_domains):
    """(allowed, reason) for a host name already cleaned up by normalize_name."""
    if all(NUMBER.match(part) for part in name.split(".")):  # tools read this as an IP address
        if PLAIN_IPV4.match(name) and all(int(part) <= 255 for part in name.split(".")):
            return check_ip(ipaddress.IPv4Address(name))
        return False, ("an IP address written in an unusual way (one number, hex, octal or "
                       "shortened); tools read these differently, so write it like 127.0.0.1")
    if name == "localhost" or name.endswith(".localhost"):
        return True, "localhost always means this machine"
    if name.endswith(".test"):
        return True, ".test names are reserved for testing and never exist on the internet"
    if name in TOP_LEVEL:  # like a container name, but outside docker it reaches the internet
        return False, "%s is a top-level internet domain, not a container name" % name
    if CONTAINER.match(name):
        return True, "a single name without dots: a container or service in your docker network"
    # Own domains come before the nip.io check, so a name like 10.0.0.1.example.com stays yours.
    for domain in own_domains:
        if name == domain or name.endswith("." + domain):
            return True, "%s (with its subdomains) is listed as yours in the scope file" % domain
    if IP_INSIDE.search(name + "."):
        return False, "a public wildcard DNS name (like nip.io); use the IP in it instead"
    for domain in own_domains:
        if domain in name:
            return False, "this only looks like %s (which is yours): it is another domain" % domain
    return False, NOT_LISTED


def decide(target, own_domains):
    """{"host", "allowed", "reason", "fix"} for one target ("fix" may be empty). ValueError if
    the target is unreadable. own_domains is the list that load_scope returns."""
    host, has_login = read_host(target)
    if ":" in host:  # after read_host, only IPv6 addresses contain a colon
        host = str(ipaddress.IPv6Address(host))  # the short form; ValueError if it is not IPv6
        allowed, reason = check_ip(ipaddress.IPv6Address(host))
    else:
        host = normalize_name(host)
        allowed, reason = check_name(host, own_domains)
    fix = ADD_TO_SCOPE % (host, host) if reason == NOT_LISTED and "." in host else ""
    if has_login:
        reason += '; the text before "@" is a login name, not the host'
    return {"host": host, "allowed": allowed, "reason": reason, "fix": fix}


def check_entry(entry):
    """One own_domains entry, cleaned up by normalize_name. ValueError says what is wrong."""
    start = "own_domains entry %s: " % json.dumps(entry)
    if not isinstance(entry, str):
        raise ValueError(start + "must be a text string")
    if any(ch in entry for ch in "*/:@"):
        raise ValueError(start + "write only the domain name: no https://, port, path or wildcard")
    try:
        name = normalize_name(entry)
    except ValueError as error:
        raise ValueError(start + str(error))
    if "." not in name or all(NUMBER.match(part) for part in name.split(".")):
        raise ValueError(start + "use a domain with at least one dot, like example.com, not an IP")
    if name in SHARED or name.endswith((".nip.io", ".sslip.io")):
        raise ValueError(start + "shared by many owners; list your own part, like myapp.github.io")
    return name


def load_scope(path):
    """The own domains in a scope file, cleaned up. ValueError for a missing or broken file."""
    try:
        with open(path, encoding="utf-8-sig") as handle:  # -sig: a BOM from Windows is fine
            data = json.load(handle)
    except OSError as error:
        raise ValueError("cannot read %s: %s" % (path, error.strerror or error))
    except (ValueError, RecursionError) as error:  # bad JSON, not UTF-8, or nested too deep
        raise ValueError("%s is not valid JSON: %s" % (path, error))
    if not isinstance(data, dict) or not isinstance(data.get("own_domains"), list):
        raise ValueError('%s must look like {"own_domains": ["example.com"]}' % path)
    return [check_entry(entry) for entry in data["own_domains"]]


def safe_target(target):
    """The target as it may be printed: everything before the last "@" (a login that may hold a
    password) becomes ****, and invisible characters become <U+XXXX>."""
    if "@" in target:
        target = "****" + target[target.rindex("@"):]
    return "".join(ch if ch.isprintable() else "<U+%04X>" % ord(ch) for ch in target)


def format_human(result):
    """The plain-text report: verdict, reason, scope file, and for PASSIVE ONLY what to do."""
    scope = "own domains: %d" % len(result["own_domains"])
    if not result["scope_file_found"]:
        scope = "not found: no domain is yours"
    lines = ["%s: %s" % (result["verdict"], result["host"]), "reason: " + result["reason"],
             "scope file: %s (%s)" % (result["scope_file"], scope)]
    if result["fix"]:
        lines.append("fix: " + result["fix"])
    if not result["allowed"]:
        lines.append(PASSIVE_HINT)
    return "\n".join(lines)


def main(argv=None):
    """Read the arguments, decide, and print the verdict. Returns the exit code."""
    parser = argparse.ArgumentParser(description="May active tests run against a target?")
    parser.add_argument("target", help="URL, host, host:port or IP address")
    parser.add_argument("--scope", help="scope file (default: forge-work/scope.json here)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    scope_file = args.scope or DEFAULT_SCOPE
    found = os.path.exists(scope_file)
    try:  # a missing default file means no own domains; a missing --scope file is an error
        own_domains = load_scope(scope_file) if found or args.scope else []
    except ValueError as error:
        print("error: scope file: %s" % error, file=sys.stderr)
        return 2
    try:
        result = decide(args.target, own_domains)
    except ValueError as error:
        target = safe_target(args.target)[:200]
        print('error: cannot read target "%s": %s' % (target, error), file=sys.stderr)
        return 2
    verdict = "ALLOWED" if result["allowed"] else "PASSIVE ONLY"
    result.update(target=safe_target(args.target), verdict=verdict, scope_file=scope_file,
                  scope_file_found=found, own_domains=own_domains)
    print(json.dumps(result, indent=2) if args.json else format_human(result))
    return 0 if result["allowed"] else 1


if __name__ == "__main__":
    sys.exit(main())
