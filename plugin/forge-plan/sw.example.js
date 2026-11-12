// Example service worker for `PWA: yes`, following the caching rules in profiles.md (PWA toggle).
// Copy it to public/sw.js and set ASSETS to the profile's hashed assets path (profiles.md, Where).
// Bump VERSION with every release: the new worker then stores everything again, and the old
// cache is deleted when it takes over.
//
// Pages come from the network; when there is none, the offline page. Hashed assets come from the
// cache, stored the first time they load. The offline page and its CSS are stored when the worker
// installs: the CSP blocks inline styles, so offline.html links /offline.css and needs no other
// file. Never stored: other pages, API responses, POSTs and other non-GET requests, other domains
// (Stripe).
const VERSION = "v1", CACHE = "app-" + VERSION, ASSETS = "/build/assets/";
const OFFLINE = "/offline.html", PRECACHE = [OFFLINE, "/offline.css"];
// Installing fetches them fresh ("reload"), not the copy in the browser's own HTTP cache.
self.addEventListener("install", (e) => e.waitUntil(caches.open(CACHE).then((c) =>
  c.addAll(PRECACHE.map((path) => new Request(path, { cache: "reload" }))))));
self.addEventListener("activate", (e) => e.waitUntil(caches.keys().then((keys) =>
  Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))));
self.addEventListener("message", (e) => { if (e.data === "SKIP_WAITING") self.skipWaiting(); });
self.addEventListener("fetch", (e) => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return; // network only
  if (req.mode === "navigate") return e.respondWith(fetch(req).catch(() => caches.match(OFFLINE)));
  if (!url.pathname.startsWith(ASSETS) && !PRECACHE.includes(url.pathname)) return; // not stored
  e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
    if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
    return res;
  })));
});
