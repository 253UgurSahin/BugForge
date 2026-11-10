// Pictures of your own app, taken with Playwright: stills for the look review (../forge-design/review.md),
// and frames and a film that prove a change shows and moves (rule 9 in ../forge/rules.md).
// Copy this file to forge-work/design/shots.mjs and run it from the project folder, or from e2e/ when
// Playwright is installed there: it looks for @playwright/test (or playwright) in both places.
//
//   node forge-work/design/shots.mjs http://localhost:8080 forge-work/design/shots/round-1 / /login
//   node forge-work/design/shots.mjs BASE OUT --state e2e/.auth/alice.json /dashboard /settings
//   node forge-work/design/shots.mjs BASE OUT --no-dark --viewport-only --wait 1500 /
//   node forge-work/design/shots.mjs BASE OUT --frames --video --reduced / /dashboard
//   node forge-work/design/shots.mjs --help
//
// Every PATH gives a still of the whole page at 390px and at 1440px wide, in light and in dark:
// OUT/<name>-390-light.png. "/" is called home, "/settings/billing?tab=2" settings-billing-tab-2.
// A PATH starts at the root of the site, whatever path BASE has: /pages/a/ is BASE's origin + /pages/a/.
// No PATH: the page at BASE itself. The page is first scrolled to its end and back once, so that
// pictures that load late and parts that only appear on scroll are in the still.
//
//   --no-dark        no dark stills: for an app without a dark theme
//   --state FILE     signed in, with a Playwright storage state (the file forge-check test's setup writes)
//   --viewport-only  stills of the window only, not of the whole page: faster, and the form
//                    ../forge-design/changed.py compares fastest
//   --wait MS        MS milliseconds more before the first picture of each page, for an app that loads
//                    its data after the page; the frames start that much later too
//   --reduced        also the stills a person who asked for less motion gets: <name>-390-reduced.png
//   --frames         also frames in time, per width, in light: <name>-390-f1.png to -f4.png at about 0,
//                    150, 400 and 900 ms after the page starts showing (its entrance), then -f5.png to
//                    -f7.png scrolled a third, two thirds and all the way down (what scrolling brings).
//                    `python3 ../forge-design/changed.py --moves OUT/<name>-390-f*.png` reads them in
//                    order. f1 to f4 differ only when the page itself changes; f5 to f7 also by the scroll
//   --video          also a film of each page at 1440px wide: the entrance, the pointer crossing the
//                    first screen, then a slow scroll to the end: <name>-1440.webm
//
// Which run freezes motion, and why. A plain run (no --frames, no --video) asks the app for reduced
// motion, as --reduced does. Each still is then the page at rest, and the same page gives the same
// picture in every round: that is what the look review scores and what two rounds are compared on. A
// change that is only motion does not show in such stills. So with --frames or --video nothing is
// frozen: stills, frames and film show the page with its motion on, whatever this computer's own
// setting is, and a still is taken once the entrance is over.
//
// It never waits forever. A page gets 30 seconds to answer and to load, then 5 more for the network to
// go quiet and for its fonts. A page that keeps loading after that is shot as it is, and its line says so.
// One line per file: the status the server gave, then the file. Exit 0: every page loaded. Exit 1: a
// page did not (no answer, an error status, or not a page of BASE). Exit 2: wrong use, or no Playwright.
// Count on 10 seconds a page for a plain run, and on 45 with --frames, --video and --reduced.
// It only looks: it loads a page, scrolls it and moves the pointer over it, as a visitor would, never
// clicks or types, and only opens pages of the BASE you give. Run it on your own app.
import { readFileSync } from 'node:fs';
import { mkdir, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const WIDTHS = [390, 1440]; // a phone and a desktop; the window is 844 or 900 high
const FRAME_AT = [0, 150, 400, 900]; // ms after the page starts showing: its entrance
const SCROLL_STEPS = 3; // then a frame a third, two thirds and all the way down
const LOAD_LIMIT = 30000; // ms a page gets to answer and to load
const QUIET_LIMIT = 5000; // ms more for the network to go quiet and for its fonts
const ENTRANCE = 1200; // ms: with motion on, a still waits this long for an entrance or a reveal to end
const ARRIVE = 600; // ms after a scroll, so that what it brings has arrived
const THROUGH = { speed: 6000, longest: 2500 }; // px a second and ms: once through the page before a still
const FILM = { width: 1440, speed: 450, longest: 20000, hold: 1000, tick: 40 }; // px a second, and ms

const USAGE = `usage: node shots.mjs BASE_URL OUT_DIR [--no-dark] [--state FILE] [--viewport-only] [--wait MS]
                      [--reduced] [--frames] [--video] [PATH...]     (--help explains each one)`;
const stop = (why) => {
  console.error(`${why}\n${USAGE}`);
  process.exit(2);
};
const firstLine = (error) => String(error.message ?? error).split('\n')[0];

// --help prints the comment at the top of this file.
function help() {
  const lines = readFileSync(new URL(import.meta.url), 'utf8').split(/\r?\n/);
  const end = lines.findIndex((line) => !line.startsWith('//'));
  console.log(lines.slice(0, end).map((line) => line.slice(3)).join('\n'));
  process.exit(0);
}

const flags = { dark: true, state: undefined, fullPage: true, wait: 0, reduced: false, frames: false, video: false };
const plain = []; // BASE_URL, OUT_DIR and the paths
for (const args = process.argv.slice(2); args.length;) {
  const arg = args.shift();
  if (arg === '--no-dark') flags.dark = false;
  else if (arg === '--viewport-only') flags.fullPage = false;
  else if (['--reduced', '--frames', '--video'].includes(arg)) flags[arg.slice(2)] = true;
  else if (arg === '--state') flags.state = args.shift() ?? stop('--state needs a file');
  else if (arg === '--wait') flags.wait = Number(args.shift() ?? stop('--wait needs a number'));
  else if (arg === '--help' || arg === '-h') help();
  else if (arg.startsWith('-')) stop(`unknown option ${arg}`);
  else plain.push(arg);
}
const [base, out, ...paths] = plain;
let site = null;
try {
  site = new URL(base);
} catch { /* not an address: stopped on the next line */ }
if (!site || !out || !/^https?:$/.test(site.protocol)) stop('give the address of your app (http://...) and a folder');
if (!(flags.wait >= 0 && flags.wait <= 60000)) stop('--wait takes milliseconds, from 0 to 60000');
if (flags.state) {
  try {
    JSON.parse(readFileSync(flags.state, 'utf8'));
  } catch {
    stop(`--state: ${flags.state} is not a storage state file that can be read`);
  }
}

// "/" becomes "home", "/settings/billing?tab=2" becomes "settings-billing-tab-2".
const nameOf = (path) => path.replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'home';

let failed = 0;
const targets = []; // the pages to shoot: only pages of BASE
for (const path of paths.length ? paths : [site.pathname + site.search]) {
  let url = null;
  try {
    url = new URL(path, site);
  } catch { /* not an address: skipped below */ }
  if (url && url.origin === site.origin) targets.push({ path, href: url.href, name: nameOf(path) });
  else {
    console.error(`skipped ${path}: not on ${base}`);
    failed += 1;
  }
}

// Playwright is looked for next to this file (the project's own node_modules) and in the folder you
// run it from (so `cd e2e` works), as @playwright/test and then as playwright.
function findPlaywright() {
  for (const from of [import.meta.url, join(process.cwd(), 'shots.mjs')]) {
    for (const name of ['@playwright/test', 'playwright']) {
      try {
        return createRequire(from)(name);
      } catch (error) {
        if (error.code !== 'MODULE_NOT_FOUND') throw error;
      }
    }
  }
  console.error('Playwright is not installed here. Run this from e2e/, or first: npm i -D -E @playwright/test');
  return process.exit(2);
}
const { chromium } = findPlaywright();
// page.screenshot() waits for the fonts by itself, for as long as its timeout. ready() below does that
// wait with a shorter limit and says so in the line, so Playwright's own wait is switched off. In a
// version without this switch, a font that never comes fails the still after 30 seconds instead.
process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = '1';
const browser = await chromium.launch().catch((error) => {
  console.error(String(error.message ?? error)); // Playwright says here how to install its browser
  process.exit(2);
});

// Gives up on a step after `ms`, so a page that is stuck cannot stop the run.
const within = (ms, step) => Promise.race([
  step,
  new Promise((_, late) => setTimeout(late, ms, new Error(`the page did not answer in ${ms / 1000} s`))),
]);

// A page that led to another site is never shot.
function onSite(page) {
  const now = new URL(page.url());
  if (now.origin !== site.origin) throw new Error(`it led to ${now.origin}, which is not ${site.origin}`);
}

// Every still and frame goes through here: `take` writes the file, and the file gets its one line.
async function save(page, shot, tail, note, take) {
  onSite(page);
  const file = `${shot.stem}-${tail}.png`;
  await take(file);
  console.log(`${shot.status} ${file}${note ? `  (${note})` : ''}`);
}

// Ready for a picture: loaded, the network quiet, the fonts in. Each wait has a limit, so a page that
// keeps loading (it polls, it streams, a font never comes) is shot as it is. Returns what to say then.
// A page that did not finish loading in time gets 5 seconds for it in its next pictures, not 30 again.
const slow = new Set();
const patience = (shot) => (slow.has(shot.path) ? QUIET_LIMIT : LOAD_LIMIT);
async function ready(page, shot) {
  const busy = [];
  await page.waitForLoadState('load', { timeout: patience(shot) }).catch(() => {
    slow.add(shot.path);
    busy.push('loading');
  });
  const until = Date.now() + QUIET_LIMIT;
  await page.waitForLoadState('networkidle', { timeout: QUIET_LIMIT }).catch(() => busy.push('using the network'));
  const fontsIn = () => document.fonts.status === 'loaded';
  await page.waitForFunction(fontsIn, null, { timeout: Math.max(500, until - Date.now()) })
    .catch(() => busy.push('fetching a font'));
  return busy.length ? `shot while still ${busy.join(', ')}` : '';
}

// Runs in the page: scrolls it to `to` (0 the top, 1 the end) at `speed` px a second, in at most
// `longest` ms, and returns how many px that was. What scrolls is the page itself, or else its largest
// panel that scrolls: many apps keep a fixed frame and scroll inside it.
function glide({ to, speed, longest }) {
  let part = document.scrollingElement || document.documentElement;
  if (part.scrollHeight - part.clientHeight < 2) {
    let largest = 0;
    for (const panel of document.querySelectorAll('*')) {
      const area = panel.clientWidth * panel.clientHeight;
      const room = panel.scrollHeight - panel.clientHeight;
      if (area > largest && room > 1 && /auto|scroll|overlay/.test(getComputedStyle(panel).overflowY)) {
        largest = area;
        part = panel;
      }
    }
  }
  const from = part.scrollTop;
  const px = to * (part.scrollHeight - part.clientHeight) - from;
  const ms = Math.min((Math.abs(px) / speed) * 1000, longest);
  return new Promise((done) => {
    const start = performance.now();
    const step = (now) => {
      const share = ms ? Math.min(1, Math.max(0, now - start) / ms) : 1;
      part.scrollTo({ top: from + px * share, behavior: 'instant' });
      if (share < 1) requestAnimationFrame(step);  // forge:allow: a scroll that ends, not a loop
      else done(Math.round(px));
    };
    requestAnimationFrame(step);  // forge:allow: the first step of that scroll
  });
}
const scroll = (page, to, { speed, longest }) => within(longest + QUIET_LIMIT, page.evaluate(glide, { to, speed, longest }));

// A still: the whole page, or the window with --viewport-only.
async function still(page, shot, job) {
  const note = await ready(page, shot);
  await page.waitForTimeout(flags.wait);
  if (flags.fullPage) {
    await scroll(page, 1, THROUGH); // to the end: late pictures load, what appears on scroll appears
    await scroll(page, 0, { speed: 1, longest: 0 }); // and back to the top at once
  }
  // Frozen, the page is at rest. With motion on, its entrance and what the scroll brought must be over.
  await page.waitForTimeout(job.frozen ? (flags.fullPage ? ARRIVE : 0) : ENTRANCE);
  await save(page, shot, job.tail, note, (path) => page.screenshot({ path, fullPage: flags.fullPage }));
}

// Frames: f1 to f4 over the first second, then f5 to f7 while scrolling down in steps. A frame is the
// window as it is at that moment, so it is asked of the browser itself: page.screenshot() would first
// get the page ready for a picture, and that takes time.
async function frames(page, shot) {
  const chrome = await page.context().newCDPSession(page);
  const grab = async (file) => {
    const asked = chrome.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true });
    await writeFile(file, Buffer.from((await within(QUIET_LIMIT, asked)).data, 'base64'));
  };
  // The page starts showing at the first frame the browser draws of it: an entrance starts there too.
  const firstFrame = () => new Promise((drawn) => requestAnimationFrame(drawn));
  await within(patience(shot), page.evaluate(firstFrame)).catch(() => {});
  const shown = Date.now();
  for (const [index, at] of FRAME_AT.entries()) {
    await page.waitForTimeout(Math.max(0, shown + flags.wait + at - Date.now()));
    await save(page, shot, `f${index + 1}`, `${Date.now() - shown} ms after the page showed`, grab);
  }
  const note = await ready(page, shot);
  let scrolled = 0;
  for (let step = 1; step <= SCROLL_STEPS; step += 1) {
    scrolled += await scroll(page, step / SCROLL_STEPS, { speed: 4000, longest: 400 });
    await page.waitForTimeout(ARRIVE);
    const where = scrolled ? `scrolled ${step}/${SCROLL_STEPS} down` : 'the page does not scroll';
    await save(page, shot, `f${FRAME_AT.length + step}`, note ? `${where}, ${note}` : where, grab);
  }
}

// A film: the entrance, the pointer crossing the first screen (so what reacts to it shows), then a
// slow scroll to the end. Playwright records the window from the moment the page opens.
async function film(page, shot) {
  await ready(page, shot);
  await page.waitForTimeout(FILM.hold + flags.wait);
  for (let step = 0; step <= 30; step += 1) {
    const x = shot.width * (0.3 + (0.4 * step) / 30);
    const y = shot.height * (0.5 - 0.15 * Math.sin((Math.PI * step) / 30));
    await page.mouse.move(x, y);
    await page.waitForTimeout(FILM.tick);
  }
  const started = Date.now();
  const px = await scroll(page, 1, FILM);
  const seconds = ((Date.now() - started) / 1000).toFixed(1);
  await page.waitForTimeout(FILM.hold);
  onSite(page);
  const file = `${shot.stem}.webm`;
  await page.close(); // the film is whole once its page is closed
  await page.video().saveAs(file);
  await page.video().delete(); // the working copy in the temp folder
  console.log(`${shot.status} ${file}  (${px ? `scrolled ${px} px in ${seconds} s` : 'the page does not scroll'})`);
}

// What to make of every page. `frozen` asks the app for reduced motion (see the top of this file).
const moving = flags.frames || flags.video;
const jobs = [];
for (const scheme of flags.dark ? ['light', 'dark'] : ['light']) {
  for (const width of WIDTHS) jobs.push({ make: still, width, scheme, tail: scheme, frozen: !moving });
}
for (const width of flags.reduced ? WIDTHS : []) {
  jobs.push({ make: still, width, scheme: 'light', tail: 'reduced', frozen: true });
}
for (const width of flags.frames ? WIDTHS : []) {
  jobs.push({ make: frames, width, scheme: 'light', tail: 'frames', frozen: false });
}
if (flags.video) jobs.push({ make: film, width: FILM.width, scheme: 'light', tail: 'film', frozen: false });

// Opens one page in a browser window of its own, so no cache or service worker of an earlier page sits
// in between, lets the job make its pictures, and closes it. False: the page gave no answer.
const errorPages = new Set();
async function visit(target, job) {
  const size = { width: job.width, height: job.width < 600 ? 844 : 900 };
  let context = null;
  let answered = false;
  try {
    context = await browser.newContext({
      viewport: size,
      deviceScaleFactor: 1, // 100%: eyedropper.py, imgdiff.py and changed.py read real pixels
      colorScheme: job.scheme,
      reducedMotion: job.frozen ? 'reduce' : 'no-preference',
      storageState: flags.state,
      recordVideo: job.make === film ? { dir: tmpdir(), size } : undefined,
    });
    context.setDefaultTimeout(LOAD_LIMIT); // nothing Playwright does here waits longer
    const page = await context.newPage();
    const response = await page.goto(target.href, { waitUntil: 'commit' }).catch((error) => {
      throw new Error(`no answer. Is the app running at ${site.origin}? (${firstLine(error)})`);
    });
    onSite(page);
    answered = true;
    const status = response ? response.status() : '---';
    if (status >= 400 && !errorPages.has(target.path)) {
      errorPages.add(target.path);
      console.error(`failed ${target.path}: the server answered ${status}, so the pictures show its error page`);
      failed += 1;
    }
    const stem = join(out, `${target.name}-${job.width}`);
    await job.make(page, { ...size, status, stem, path: target.path }, job);
  } catch (error) {
    console.error(`failed ${target.path} at ${job.width}px ${job.tail}: ${firstLine(error)}`);
    failed += 1;
  } finally {
    if (context) await context.close().catch(() => {});
  }
  return answered;
}

try {
  await mkdir(out, { recursive: true });
  for (const target of targets) {
    for (const job of jobs) {
      if (!(await visit(target, job))) break; // no answer: not tried again in the other settings
    }
  }
} finally {
  await browser.close();
}
process.exit(failed ? 1 : 0);
