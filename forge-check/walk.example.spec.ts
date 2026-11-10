// The walk for forge-check test: copy this file to e2e/walk.spec.ts. It opens every route of the app at
// three widths (390 phone, 768 tablet, 1440 desktop), each in the light and the dark colour scheme,
// in a fresh browser context (an empty cache, so every load is a first load). Per page it records
// what a careful tester would note and saves a full-page screenshot. It judges nothing: it writes
// forge-work/test/walk.json, and `python3 ../forge-check/walkcheck.py forge-work/test/walk.json`
// turns that into findings with a severity. So a page with problems does not fail this run. Only a
// page that cannot be loaded does (the app is down, a time-out), or a routes.json it cannot read.
//
// Set-up: e2e/ as the top of ../forge-check/e2e.example.spec.ts says (the same package.json, the
// config with `workers: 1` and the setup project that signs the seed users in once). Nothing new
// to install: it uses @playwright/test and @axe-core/playwright.
//
// The routes come from forge-work/test/routes.json, which you write: every screen of the plan (or
// of the app's router), one entry each, the same names as the screens (S03) where there are any:
//   [
//     { "name": "S01-home",      "path": "/",          "as": null },
//     { "name": "S03-dashboard", "path": "/dashboard", "as": "alice" },
//     { "name": "S04-item",      "path": "/items/1",   "as": "alice" }
//   ]
// name: letters, digits, - and _ only (it is part of the screenshot's file name), each name once.
// path: starts with one /, with the ids of seed records filled in. as: null for a visitor, or the
// seed user whose cookies the setup project saved in .auth/<as>.json ("alice" is .auth/alice.json).
// A page behind a dialog or a tab that has no URL of its own is not a route: cover it in a flow spec.
//
// Run it from e2e/, against your own stack only (scope.py first, as for every spec):
//   FORGE_BASE_URL=http://localhost:8080 FORGE_ROUND=r1 npx playwright test walk
// FORGE_ROUND names the folder of this round's screenshots, forge-work/test/shots/<round>/ (default
// `current`): r1 for the first walk, r2 after the first round of fixes, so
// ../forge-check/shotcheck.py can compare two rounds. A signed-in route whose .auth file is missing
// is skipped and walkcheck.py then says the walk is incomplete: run the setup project first
// (E2E_PASSWORD), or take the route out and write it under "Not tested".
//
// What it writes, forge-work/test/walk.json (../forge-check/walk.md has every field):
//   { "version": 1, "base_url", "round", "widths": [390, 768, 1440], "schemes": ["light", "dark"],
//     "routes": [the routes above], "results": [one per route, width and scheme] }
// One result: route, path, as, width, scheme, loaded, error, skipped, status, redirected_to,
// screenshot, console_errors, page_errors, failed_requests, bad_responses, broken_links,
// links_checked, axe, overflow_px, clipped, overlaps, small_targets, perf, incomplete.
//
// Links: every same-origin link is asked for once per run with a GET, as the route's user. Links
// that look like they change something (log out, delete, ...) are never followed: see UNSAFE_LINK.
import { test, expect, type Page, type Request } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import * as fs from 'fs';
import * as path from 'path';

const BASE_URL = process.env.FORGE_BASE_URL || 'http://localhost:8080';
const ROUND = (process.env.FORGE_ROUND || 'current').replace(/[^\w-]/g, '-');
// forge-work/ is in the project root: one folder up when this runs from e2e/.
const WORK = process.env.FORGE_WORK
  || [path.resolve('forge-work'), path.resolve('..', 'forge-work')].find((dir) => fs.existsSync(dir))
  || path.resolve('..', 'forge-work');
const ROUTES_FILE = path.join(WORK, 'test', 'routes.json');
const WALK_FILE = path.join(WORK, 'test', 'walk.json');
const SHOTS = path.join(WORK, 'test', 'shots', ROUND);
const AUTH_DIR = process.env.FORGE_AUTH_DIR || '.auth'; // where the setup project saves the cookies

const VIEWPORTS = [{ width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }];
const SCHEMES = ['light', 'dark'] as const;
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const ASSETS = ['script', 'stylesheet', 'image', 'font'];
const CAP = 25; // at most this many entries of one kind per page, so walk.json stays small
const MAX_LINKS = 500; // links asked for in one run
// A GET on these could sign the seed user out or change data, so they are not followed.
const UNSAFE_LINK = /log-?out|sign-?out|delete|remove|destroy|unsubscribe|cancel|export|download/i;
// What a user can click or type in. A tap target smaller than 24 by 24 px is hard to hit.
const INTERACTIVE = 'a[href], button, input:not([type="hidden"]), select, textarea, summary, '
  + '[role="button"], [role="link"], [role="checkbox"], [role="switch"], [role="tab"], [role="menuitem"]';

type Route = { name: string; path: string; as: string | null };
type Result = Record<string, unknown> & { route: string; width: number; scheme: string };

// A query string can hold a token, so only the part before it is written down.
const tidy = (text: string) => text.replace(/\?[\w.%-]+=[^\s"')]*/g, '?...').replace(/\s+/g, ' ').slice(0, 300);
const key = (result: { route: string; width: number; scheme: string }) =>
  `${result.route}|${result.width}|${result.scheme}`;

function readRoutes(): Route[] {
  const raw: unknown = JSON.parse(fs.readFileSync(ROUTES_FILE, 'utf8'));
  if (!Array.isArray(raw) || raw.length === 0) throw new Error('it must be a list with at least one route');
  const names = new Set<string>();
  return raw.map((route) => {
    const { name, path: target } = route ?? {};
    const as = route?.as ?? null;
    if (typeof name !== 'string' || !/^[\w-]+$/.test(name)) throw new Error(`bad name: ${JSON.stringify(name)}`);
    if (names.has(name)) throw new Error(`the name ${name} is used twice`);
    if (typeof target !== 'string' || !/^\/(?!\/)/.test(target)) throw new Error(`${name}: path must start with one /`);
    if (as !== null && (typeof as !== 'string' || !/^[\w-]+$/.test(as))) throw new Error(`${name}: bad "as"`);
    names.add(name);
    return { name, path: target, as };
  });
}

let ROUTES: Route[] = [];
let routesError = '';
try {
  ROUTES = readRoutes();
} catch (error) {
  routesError = `cannot use ${ROUTES_FILE}: ${(error as Error).message}`;
}

// walk.json is written after every page, so a crash or a time-out half-way loses nothing.
function save(changed: Result[], fresh = false) {
  let old: Result[] = [];
  if (!fresh) {
    try { old = JSON.parse(fs.readFileSync(WALK_FILE, 'utf8')).results ?? []; } catch { /* no file yet */ }
  }
  const replaced = new Set(changed.map(key));
  const wanted = new Set(ROUTES.flatMap((route) => VIEWPORTS.flatMap(({ width }) =>
    SCHEMES.map((scheme) => key({ route: route.name, width, scheme })))));
  const results = old.filter((result) => wanted.has(key(result)) && !replaced.has(key(result))).concat(changed);
  fs.mkdirSync(path.dirname(WALK_FILE), { recursive: true });
  fs.writeFileSync(WALK_FILE, JSON.stringify({
    version: 1, base_url: BASE_URL, round: ROUND, written: new Date().toISOString(),
    widths: VIEWPORTS.map(({ width }) => width), schemes: SCHEMES, routes: ROUTES, results,
  }, null, 2));
}

// One worker, in order: every test adds its page to the same walk.json.
test.describe.configure({ mode: 'default' });
test.setTimeout(120_000);

const linksSeen = new Set<string>(); // each link is asked for once per run and per user

test('walk: read routes.json and start a fresh walk.json', () => {
  expect(routesError, routesError).toBe('');
  // Every page starts as "not run", so a page the run never reaches is seen as missing, not as fine.
  save(ROUTES.flatMap((route) => VIEWPORTS.flatMap(({ width }) => SCHEMES.map((scheme) => ({
    route: route.name, path: route.path, as: route.as, width, scheme, loaded: false, error: 'not run',
  })))), true);
});

// LCP (when the biggest thing on the screen was drawn) and CLS (how much the page jumped while it
// loaded: the sum of all layout shifts, which is never lower than the official windowed value),
// from the browser's own measurements; TTFB and the load time from the navigation timing.
async function measureSpeed(page: Page) {
  return page.evaluate(() => new Promise<Record<string, number | null>>((resolve) => {
    let lcp = 0;
    let cls = 0;
    try {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) lcp = Math.max(lcp, entry.startTime);
      }).observe({ type: 'largest-contentful-paint', buffered: true });
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries() as any[]) if (!entry.hadRecentInput) cls += entry.value;
      }).observe({ type: 'layout-shift', buffered: true });
    } catch { /* a browser without these measurements: they stay empty */ }
    setTimeout(() => {
      const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
      resolve({
        lcp_ms: lcp ? Math.round(lcp) : null,
        cls: Math.round(cls * 1000) / 1000,
        ttfb_ms: nav ? Math.round(nav.responseStart) : null,
        load_ms: nav && nav.loadEventEnd ? Math.round(nav.loadEventEnd) : null,
      });
    }, 300);
  }));
}

// The layout checks, in the page: sideways scrolling, text that is cut off without an ellipsis,
// something to click that lies under something else to click, and tap targets under 24 px.
async function measureLayout(page: Page) {
  return page.evaluate(({ selector, cap }) => {
    const label = (element: Element) => {
      const words = (element.getAttribute('aria-label') || (element as HTMLElement).innerText
        || element.getAttribute('placeholder') || element.getAttribute('name') || '')
        .trim().replace(/\s+/g, ' ').slice(0, 60);
      return `<${element.tagName.toLowerCase()}${element.id ? ` id="${element.id}"` : ''}>${words ? ` "${words}"` : ''}`;
    };
    const visible = (element: Element) => {
      const box = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return box.width > 0 && box.height > 0 && style.visibility !== 'hidden' && style.opacity !== '0';
    };
    const root = document.documentElement;
    const overflow_px = Math.max(0, root.scrollWidth - root.clientWidth);

    const clipped: { element: string; direction: string }[] = [];
    for (const element of Array.from(document.querySelectorAll<HTMLElement>('body *'))) {
      if (clipped.length >= cap) break;
      const ownText = Array.from(element.childNodes).some((node) =>
        node.nodeType === Node.TEXT_NODE && (node.textContent || '').trim() !== '');
      if (!ownText || !visible(element)) continue;
      const box = element.getBoundingClientRect();
      if (box.width < 16 || box.height < 8) continue; // text hidden on purpose, for screen readers only
      const style = getComputedStyle(element);
      const hides = (value: string) => value === 'hidden' || value === 'clip';
      const sideways = element.scrollWidth > element.clientWidth + 1 && hides(style.overflowX)
        && style.textOverflow !== 'ellipsis';
      const down = element.scrollHeight > element.clientHeight + 4 && hides(style.overflowY)
        && ['', 'none'].includes(style.getPropertyValue('-webkit-line-clamp'));
      if (sideways || down) clipped.push({ element: label(element), direction: sideways ? 'sideways' : 'down' });
    }

    const overlaps: { element: string; covered_by: string }[] = [];
    const small_targets: { element: string; width: number; height: number }[] = [];
    const controls = Array.from(document.querySelectorAll<HTMLElement>(selector))
      .filter((element) => visible(element) && !(element as HTMLButtonElement).disabled).slice(0, 300);
    for (const element of controls) {
      const size = element.getBoundingClientRect();
      const inlineLink = element.tagName === 'A' && getComputedStyle(element).display === 'inline';
      const labelled = ((element as HTMLInputElement).labels?.length ?? 0) > 0; // the label is a target too
      if ((size.width < 24 || size.height < 24) && !inlineLink && !labelled && small_targets.length < cap) {
        small_targets.push({ element: label(element), width: Math.round(size.width), height: Math.round(size.height) });
      }
      // Bring it to the middle of the screen and ask the browser what is on top at its centre.
      element.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' as ScrollBehavior });
      const box = element.getBoundingClientRect();
      const onTop = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
      const other = onTop ? onTop.closest(selector) : null;
      if (other && other !== element && !element.contains(other) && !other.contains(element)
        && overlaps.length < cap) {
        overlaps.push({ element: label(element), covered_by: label(other) });
      }
    }
    window.scrollTo(0, 0);

    const links = Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href]'))
      .map((anchor) => ({ href: anchor.href, text: label(anchor) }));
    return { overflow_px, clipped, overlaps, small_targets, links };
  }, { selector: INTERACTIVE, cap: CAP });
}

for (const route of ROUTES) {
  for (const viewport of VIEWPORTS) {
    for (const scheme of SCHEMES) {
      test(`walk ${route.name} ${viewport.width} ${scheme}`, async ({ browser }) => {
        const result: Result = {
          route: route.name, path: route.path, as: route.as, width: viewport.width, scheme,
          loaded: false, error: null, incomplete: [] as string[],
        };
        const incomplete = result.incomplete as string[];
        const state = route.as ? path.resolve(AUTH_DIR, `${route.as}.json`) : undefined;
        if (state && !fs.existsSync(state)) {
          result.skipped = `no saved sign-in for ${route.as} (${AUTH_DIR}/${route.as}.json): run the setup project with E2E_PASSWORD`;
          save([result]);
          test.skip(true, result.skipped as string);
        }

        const context = await browser.newContext({
          baseURL: BASE_URL, viewport, colorScheme: scheme, reducedMotion: 'reduce', storageState: state,
        });
        const page = await context.newPage();
        const console_errors: string[] = [];
        const page_errors: string[] = [];
        const failed_requests: object[] = [];
        const bad_responses: object[] = [];
        const sizes: Promise<number>[] = [];
        const origin = new URL(BASE_URL).origin;
        const sameOrigin = (url: string) => { try { return new URL(url).origin === origin; } catch { return false; } };
        const describe = (request: Request) => ({
          url: tidy(request.url()), method: request.method(), type: request.resourceType(),
          same_origin: sameOrigin(request.url()),
        });

        page.on('console', (message) => {
          // The browser logs every failed response as "Failed to load resource"; those are in
          // bad_responses already.
          if (message.type() === 'error' && !message.text().startsWith('Failed to load resource')
            && console_errors.length < CAP) console_errors.push(tidy(message.text()));
        });
        page.on('pageerror', (error) => { if (page_errors.length < CAP) page_errors.push(tidy(error.message)); });
        page.on('requestfailed', (request) => {
          const why = request.failure()?.errorText || 'failed';
          // ERR_ABORTED: the page or the browser cancelled it itself (a navigation, a closed stream).
          if (!why.includes('ERR_ABORTED') && failed_requests.length < CAP) {
            failed_requests.push({ ...describe(request), error: why });
          }
        });
        page.on('requestfinished', (request) => {
          sizes.push(request.sizes().then((size) => size.responseBodySize + size.responseHeadersSize, () => 0));
        });
        page.on('response', (response) => {
          const request = response.request();
          const isThePage = request.isNavigationRequest() && request.frame() === page.mainFrame();
          if (response.status() >= 400 && !isThePage && bad_responses.length < CAP) {
            bad_responses.push({
              ...describe(request), status: response.status(),
              own_asset: ASSETS.includes(request.resourceType()) && sameOrigin(request.url()),
            });
          }
        });

        try {
          const response = await page.goto(route.path, { waitUntil: 'load', timeout: 45_000 });
          // Give late requests five seconds to settle; a page that keeps polling is not an error.
          await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {});
          result.loaded = true;
          result.status = response ? response.status() : null;
          const landed = new URL(page.url());
          const same = (a: string, b: string) => a.replace(/\/+$/, '') === b.replace(/\/+$/, '');
          result.redirected_to = same(landed.pathname, new URL(route.path, BASE_URL).pathname)
            ? null : tidy(landed.pathname);

          const speed = await measureSpeed(page).catch((error) => {
            incomplete.push(`speed: ${tidy(String(error))}`);
            return {};
          });
          const transferred = await Promise.all(sizes);
          result.perf = {
            ...speed, requests: transferred.length,
            transfer_bytes: transferred.reduce((sum, bytes) => sum + bytes, 0),
          };

          try {
            const axe = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
            result.axe = axe.violations.map((violation) => ({
              id: violation.id, impact: violation.impact ?? 'minor', help: violation.help,
              help_url: violation.helpUrl, nodes: violation.nodes.length,
              targets: violation.nodes.slice(0, 5).map((node) => tidy(node.target.join(' '))),
            }));
          } catch (error) {
            incomplete.push(`axe: ${tidy(String(error))}`);
          }

          let links: { href: string; text: string }[] = [];
          try {
            const layout = await measureLayout(page);
            links = layout.links;
            result.overflow_px = layout.overflow_px;
            result.clipped = layout.clipped;
            result.overlaps = layout.overlaps;
            result.small_targets = layout.small_targets;
          } catch (error) {
            incomplete.push(`layout: ${tidy(String(error))}`);
          }

          // After the layout check scrolled the whole page, so lazy pictures are in the screenshot.
          await page.waitForLoadState('networkidle', { timeout: 3_000 }).catch(() => {});
          const shot = `${route.name}-${viewport.width}-${scheme}.png`;
          try {
            fs.mkdirSync(SHOTS, { recursive: true });
            await page.screenshot({ path: path.join(SHOTS, shot), fullPage: true, animations: 'disabled' });
            result.screenshot = `forge-work/test/shots/${ROUND}/${shot}`;
          } catch (error) {
            incomplete.push(`screenshot: ${tidy(String(error))}`);
          }

          const broken_links: object[] = [];
          let checked = 0;
          for (const link of links) {
            let url: URL;
            try { url = new URL(link.href); } catch { continue; }
            url.hash = '';
            const seen = `${route.as}|${url.href}`;
            if (!/^https?:$/.test(url.protocol) || url.origin !== origin || UNSAFE_LINK.test(url.href)
              || linksSeen.has(seen) || linksSeen.size >= MAX_LINKS) continue;
            linksSeen.add(seen);
            checked += 1;
            const status = await context.request.get(url.href, { timeout: 15_000 })
              .then((answer) => answer.status(), () => 0);
            if (status === 404 || status === 410 || status >= 500) {
              broken_links.push({ url: tidy(url.pathname + url.search), status, text: link.text });
            }
          }
          result.broken_links = broken_links;
          result.links_checked = checked;
        } catch (error) {
          result.error = tidy(String(error));
        } finally {
          Object.assign(result, { console_errors, page_errors, failed_requests, bad_responses });
          save([result]);
          await context.close();
        }
        // The only way a page fails this run: it could not be loaded at all.
        expect(result.loaded, `${route.path} could not be loaded: ${result.error}`).toBe(true);
      });
    }
  }
}
