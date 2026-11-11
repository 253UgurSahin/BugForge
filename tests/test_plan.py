"""Tests for forge-plan's reference files: the plan.md template, profiles.md and sw.example.js.

A template filled in the natural way, each sentence of a placeholder on its own line, must still pass
the plan gate: no placeholder may invite a second line that starts with `Profile:` or `PWA:`.
profiles.md stays within the spec's 300 lines. The example service worker keeps the caching rules
of profiles.md, and its offline page is styled offline: the CSP of forge-build pack's templates blocks
inline styles, so the page's CSS is a file the worker stores on install. That test needs Node."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load  # noqa: E402

phasecheck = load("forge", "phasecheck")
TEMPLATE = os.path.join(ROOT, "forge-plan", "plan.md")
PROFILES = os.path.join(ROOT, "forge-plan", "profiles.md")
WORKER = os.path.join(ROOT, "forge-plan", "sw.example.js")
MAX_PROFILES_LINES = 300

# A fake browser for a service worker: one cache, and a network that can go offline. Prints JSON:
# what install stored, and where each request's answer came from (network, cache:/path or failed).
BROWSER = r"""
const fs = require("fs"), vm = require("vm");
const ORIGIN = "http://localhost:8080", stored = new Map(), cacheModes = [];
let online = true;
class Request { constructor(url, init = {}) { this.url = url; this.cache = init.cache || "default"; } }
const key = (r) => new URL(typeof r === "string" ? r : r.url, ORIGIN).href;
const network = async (r) => {
  if (!online) throw new TypeError("Failed to fetch");
  cacheModes.push(typeof r === "string" ? "default" : r.cache || "default");
  const url = key(r);
  return { ok: true, url, from: "network", clone: () => ({ ok: true, url, from: "cache" }) };
};
const cache = {
  add: async (r) => { stored.set(key(r), { ...(await network(r)), from: "cache" }); },
  addAll: async (list) => { for (const r of list) await cache.add(r); },
  put: async (r, res) => { stored.set(key(r), res); },
  match: async (r) => stored.get(key(r)),
};
const caches = { open: async () => cache, keys: async () => [], delete: async () => true,
                 match: cache.match };
const listeners = {};
const self = { location: { origin: ORIGIN }, skipWaiting() {},
               addEventListener: (type, listener) => { listeners[type] = listener; } };
vm.runInNewContext(fs.readFileSync(process.argv[2], "utf8"),
                   { self, caches, fetch: network, URL, Request });
async function get([path, mode = "no-cors", method = "GET"]) {
  const request = { url: new URL(path, ORIGIN).href, method, mode };
  let answer = null;
  listeners.fetch({ request, respondWith: (promise) => { answer = promise; } });
  try {
    const res = await (answer === null ? network(request) : answer);
    await new Promise((done) => setTimeout(done, 0));  // let a cache.put finish
    return !res ? "failed" : res.from === "network" ? "network" : "cache:" + new URL(res.url).pathname;
  } catch (error) {
    return "failed";
  }
}
(async () => {
  let installing;
  listeners.install({ waitUntil: (promise) => { installing = promise; } });
  await installing;
  const requests = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
  const out = { installed: [...stored.keys()].sort(), "install cache modes": [...new Set(cacheModes)] };
  for (const [name, request] of requests.online) out["online " + name] = await get(request);
  online = false;
  for (const [name, request] of requests.offline) out["offline " + name] = await get(request);
  console.log(JSON.stringify(out));
})();
"""
ASSET = "/build/assets/app-4f2a.css"  # a hashed file, under the sample's ASSETS path
REQUESTS = {
    "online": [["page", ["/planner/", "navigate"]], ["asset", [ASSET]], ["api", ["/api/items"]],
               ["post", ["/api/items", "cors", "POST"]], ["other site", ["https://js.stripe.com/v3/"]]],
    "offline": [["page", ["/planner/", "navigate"]], ["offline css", ["/offline.css"]], ["asset", [ASSET]],
                ["api", ["/api/items"]]],
}


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def fill_in(template):
    """The template as a writer fills it in: the two gate lines get a value, and every other
    placeholder becomes its own words with each sentence on a new line."""
    text = re.sub(r"(?m)^Profile: \{\{.*?\}\}$", "Profile: laravel", template)
    text = re.sub(r"(?m)^PWA: \{\{.*?\}\}$", "PWA: no", text)
    return re.sub(r"\{\{(.*?)\}\}", lambda match: re.sub(r"\.\s+", ".\n", match.group(1)), text, flags=re.S)


class PlanTemplateTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, "forge-work"))

    def check(self, text, label, *allowed):
        with open(os.path.join(self.root, "forge-work", "plan.md"), "w", encoding="utf-8") as handle:
            handle.write(text)
        return phasecheck.check_line(self.root, "forge-work/plan.md", label, *allowed)

    def test_a_natural_fill_in_passes_the_gate_lines(self):
        filled = fill_in(read(TEMPLATE))
        self.assertNotIn("{{", filled)
        for label, allowed in (("Profile", ("laravel", "django", "next", "static")), ("PWA", ("yes", "no"))):
            with self.subTest(label=label):
                passed, message = self.check(filled, label, *allowed)
                self.assertTrue(passed, message)

    def test_the_old_trap_is_caught(self):
        """The Why placeholder once ended with `PWA: why or why not.`: filled in, a second PWA line."""
        trap = "Profile: {{laravel | next}}\nPWA: {{yes | no}}\n\n## Why\n\n{{What was not chosen. PWA: why or why not.}}\n"
        passed, message = self.check(fill_in(trap), "PWA", "yes", "no")
        self.assertFalse(passed)
        self.assertIn("needs exactly one line", message)


class ProfilesTests(unittest.TestCase):
    def test_profiles_md_stays_short(self):
        lines = len(read(PROFILES).splitlines())
        self.assertLessEqual(lines, MAX_PROFILES_LINES, "profiles.md is %d lines: trim it" % lines)

    def test_profiles_md_names_the_example_worker(self):
        self.assertIn("`../forge-plan/sw.example.js`", read(PROFILES))


class ServiceWorkerTests(unittest.TestCase):
    """sw.example.js in a fake browser: online first, then offline."""

    def answers(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is not installed")
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        browser, requests = os.path.join(folder, "browser.js"), os.path.join(folder, "requests.json")
        for path, text in ((browser, BROWSER), (requests, json.dumps(REQUESTS))):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        done = subprocess.run([node, browser, WORKER, requests], capture_output=True, encoding="utf-8",
                              errors="replace", timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_the_offline_page_and_its_css_are_stored_on_install(self):
        answers = self.answers()
        self.assertEqual(answers["installed"],
                         ["http://localhost:8080/offline.css", "http://localhost:8080/offline.html"])
        # fetched fresh: laravel's nginx sends them without Cache-Control, so the browser's own
        # HTTP cache may hold an old copy (the colours before forge-design brand)
        self.assertEqual(answers["install cache modes"], ["reload"])

    def test_offline_the_page_is_the_offline_page_with_its_css(self):
        answers = self.answers()
        self.assertEqual(answers["offline page"], "cache:/offline.html")
        self.assertEqual(answers["offline offline css"], "cache:/offline.css",
                         "offline.html would show unstyled: the worker must answer its CSS from the cache")

    def test_the_caching_rules(self):
        answers = self.answers()
        for name in ("page", "asset", "api", "post", "other site"):
            self.assertEqual(answers["online " + name], "network", name)  # pages network first
        self.assertEqual(answers["offline asset"], "cache:" + ASSET)  # hashed assets are kept
        self.assertEqual(answers["offline api"], "failed")  # API responses never are


if __name__ == "__main__":
    unittest.main()
