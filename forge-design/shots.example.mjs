// Pictures of your own app, taken with Playwright: stills for the look review (../forge-design/review.md),
// and frames and a film that prove a change shows and moves (rule 9 in ../forge/rules.md).
// Copy this file to forge-work/design/shots.mjs and run it from the project folder, or from e2e/ when
// Playwright is installed there: it looks for @playwright/test (or playwright) in both places.
//
//   node forge-work/design/shots.mjs http://localhost:8080 forge-work/design/shots/round-1 / /login
//   node forge-work/design/shots.mjs BASE OUT / /login --state e2e/.auth/alice.json /dashboard /settings
//   node forge-work/design/shots.mjs BASE OUT --viewport-only --wait 1500 --init-script theme.js /
//   node forge-work/design/shots.mjs BASE OUT --frames --scene-frames --video --reduced / /dashboard
//   node forge-work/design/shots.mjs BASE OUT --width 390 --overflow --contrast /checkout
//   node forge-work/design/shots.mjs --help
//
// Every PATH gives a still of the whole page at 390px and at 1440px wide, in light and in dark:
// OUT/<name>-390-light.png. "/" is called home, "/settings/billing?tab=2" settings-billing-tab-2.
// A PATH starts at the root of the site, whatever path BASE has: /pages/a/ is BASE's origin + /pages/a/.
// No PATH: the page at BASE itself. The page is first scrolled to its end and back once, so that
// pictures that load late and parts that only appear on scroll are in the still. An app that keeps a
// fixed frame and scrolls a panel inside it gets that panel opened up for the still, and a bar fixed
// to the bottom of the window (a tab bar) is drawn at the bottom of the picture, not in its middle.
// A still is named by the theme the page says it shows (data-theme or a dark class on <html>, or its
// color-scheme), not by the system setting asked for; a page that says nothing is named by the setting.
// An app that keeps its own theme shows that one under both settings, and a page painted the same under
// both is one page: then there is one still, and the line says so.
//
//   --no-dark        no stills with the system set to dark: for a quick look only, never for before
//                    shots (the after shots take the same flags, so a new dark theme would go unseen)
//   --width PX       only this width, not 390 and 1440; give it again for more widths
//   --state FILE     signed in with this Playwright storage state (the file forge-check test's setup
//                    writes), for the PATHs after it; `--state none` signs out again. So one run takes
//                    public, member and admin pages: / /login --state member.json /app --state admin.json
//                    /admin. A --state after the last PATH counts for the PATHs that have none
//   --storage KEY=VALUE  this localStorage item is set for BASE before the page's own scripts run: one
//                    of the app's remembered choices, such as its theme; give it again for more
//   --init-script FILE  this script runs in every page before the page's own. For an app that keeps
//                    its theme in localStorage, one line in it gives each still the theme its system
//                    setting asks for (its own key and values in place of 'theme', 'dark' and 'light'):
//                    localStorage.setItem('theme', matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
//   --viewport-only  stills of the window only, not of the whole page: faster, and the form
//                    ../forge-design/changed.py compares fastest
//   --wait MS        MS milliseconds more before the first picture of each page, for an app that loads
//                    its data after the page; the frames start that much later too
//   --reduced        also the stills a person who asked for less motion gets: <name>-390-reduced.png
//   --frames         also frames in time, per width, in light: <name>-390-f1.png to -f4.png at about 0,
//                    150, 400 and 900 ms after the page starts showing (its entrance), then -f5.png to
//                    -f7.png scrolled a third, two thirds and all the way down (what scrolling brings).
//                    `python3 ../forge-design/changed.py --moves OUT/<name>-390-f[1-4].png` says whether
//                    the entrance moves. Never give it f5 to f7: they differ by the scroll alone, even
//                    where nothing moves, so look at those and at the film yourself. Each line says when
//                    its frame was taken: with a live WebGL scene and no GPU one frame can take most of a
//                    second, so a moment shorter than that is measured in the page (requestAnimationFrame
//                    writing the element's place and opacity into a list), not seen in frames
//   --scene-frames   also frames of the scenes, per width, in light: <name>-1440-s1.png to -s6.png over
//                    about 3 seconds, with nothing scrolled and the pointer moving across the scene, taken
//                    once every scene in the window is live (data-scene="live", the kit's sign). A scene
//                    that is still loading is waited for only by its data-scene-poster child: give one
//                    that has none (a preview, a poster only in CSS) an empty <div data-scene-poster></div>.
//                    Up to 2 minutes for that: without a GPU a scene can take 40 seconds. The lines give
//                    the first scene's size in the window, for the level's minimum (../forge/levels.md).
//                    `python3 ../forge-design/changed.py --moves
//                    OUT/<name>-1440-s*.png` says whether the scene moves (and -390-s*.png on the phone)
//   --video          also a film of each page at 1440px wide: the entrance, the pointer crossing the
//                    first screen, then a slow scroll to the end: <name>-1440.webm
//   --overflow       a check per page, width and theme: a page wider than the window (it scrolls
//                    sideways), or in an app that keeps a fixed frame its main scroll panel (the largest
//                    that scrolls down; a board of columns that only scrolls sideways is not one) wider
//                    than itself, gets a line "wide" naming what sticks out, and the run exits 1
//   --contrast       a check per page, width and theme: each text a person can see against what is
//                    behind it, at rest, and for the controls in the window also on hover and on focus.
//                    Under WCAG AA (4.5:1; 3:1 from 24px, or 18.66px bold) it gets a line "low contrast"
//                    and the run exits 1. A shade laid over a whole box (a ::before) and a box behind the
//                    whole page (fixed and as large as the window, or from the page's top to its end)
//                    count as what is behind. Text over a picture, a canvas, a video or a box placed
//                    beside it (a hero's layer that fills the first screen, a panel whose order the page
//                    does not say) is counted, not measured: the line names up to five with their place,
//                    to look at in the still. Disabled controls are left out, as WCAG does
//
// Which run freezes motion, and why. A plain run (no --frames, --scene-frames or --video) asks the
// app for reduced motion, as --reduced does. Each still is then the page at rest, and the same page
// gives the same picture in every round: that is what the look review scores and what two rounds are
// compared on. A change that is only motion does not show in such stills. So with --frames,
// --scene-frames or --video nothing is frozen: stills, frames and film show the page with its motion
// on, whatever this computer's own setting is, and a still is taken once the entrance is over and the
// scenes in the window are live.
//
// It never waits forever. A page gets 30 seconds to answer and to load, then 5 more for the network to
// go quiet and for its fonts; its scenes get 2 minutes to go live. A page that keeps loading after that
// is shot as it is, and its line says so. One line per file: the status the server gave, then the file.
// A line "console" for each error the page itself reports (a script that throws, a file it could not
// load), once per page: it does not change the exit code, but read each one.
// Exit 0: every page loaded (and passed --overflow and --contrast). Exit 1: a page did not (no answer,
// an error status, a page of another site, or a sign-in page in place of the screen: sign in again),
// a scene never went live, or a check found something. Exit 2: wrong use, or no Playwright.
// Count on 10 seconds a page for a plain run, and on 45 with --frames, --video and --reduced; a scene
// without a GPU adds up to a minute to each picture of its page.
// It only looks: it loads a page, scrolls it, moves the pointer over it and focuses its controls, as a
// visitor would, never clicks or types, and only opens pages of the BASE you give. Run it on your own app.
import { readFileSync } from 'node:fs';
import { mkdir, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { basename, join } from 'node:path';

const WIDTHS = [390, 1440]; // a phone and a desktop; the window is 844 or 900 high
const FRAME_AT = [0, 150, 400, 900]; // ms after the page starts showing: its entrance
const SCROLL_STEPS = 3; // then a frame a third, two thirds and all the way down
const SCENE_FRAMES = 6; // s1 to s6, about 550 ms apart, while the pointer crosses the scene
const LOAD_LIMIT = 30000; // ms a page gets to answer and to load
const QUIET_LIMIT = 5000; // ms more for the network to go quiet and for its fonts
const SCENE_LIMIT = 120000; // ms the scenes in the window get to go live: without a GPU, 40 s happens
const FIND_LIMIT = 5000; // ms after the page loaded for a scene to show up in the window, or there is none
const SETTLE = 1000; // ms after the scenes went live: the kit fades the poster out and the canvas in (400)
const ENTRANCE = 1200; // ms: with motion on, a still waits this long for an entrance or a reveal to end
const ARRIVE = 600; // ms after a scroll, so that what it brings has arrived
const THROUGH = { speed: 6000, longest: 2500 }; // px a second and ms: once through the page before a still
const FILM = { width: 1440, speed: 450, longest: 20000, hold: 1000, tick: 40 }; // px a second, and ms
const CONTROLS = 40; // --contrast: at most this many controls in the window get a hover and a focus
// Where apps send a visitor to sign in. Landing there in place of the screen asked for is never a still.
const SIGN_IN = /(^|\/)(log[-_]?in|sign[-_]?in|auth|sessions?|inloggen|aanmelden|anmelden|connexion)(\/|\.|$)/i;

const USAGE = `usage: node shots.mjs BASE_URL OUT_DIR [--no-dark] [--width PX] [--state FILE|none] [--storage KEY=VALUE]
                      [--init-script FILE] [--viewport-only] [--wait MS] [--reduced] [--frames]
                      [--scene-frames] [--video] [--overflow] [--contrast] [PATH...]   (--help explains each)`;
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

const flags = { dark: true, widths: [], fullPage: true, wait: 0, reduced: false, frames: false, scenes: false,
  video: false, overflow: false, contrast: false, storage: [], initScript: undefined };
const plain = []; // BASE_URL and OUT_DIR
const paths = []; // each PATH with the --state in force where it stands
let state; // the storage state for the PATHs read next: undefined is signed out
let trailing = false; // a --state came after the last PATH so far
const next = (args, flag) => args.shift() ?? stop(`${flag} needs a value`);
for (const args = process.argv.slice(2); args.length;) {
  const arg = args.shift();
  if (arg === '--no-dark') flags.dark = false;
  else if (arg === '--viewport-only') flags.fullPage = false;
  else if (['--reduced', '--frames', '--video', '--overflow', '--contrast'].includes(arg)) flags[arg.slice(2)] = true;
  else if (arg === '--scene-frames') flags.scenes = true;
  else if (arg === '--width') flags.widths.push(Number(next(args, arg)));
  else if (arg === '--storage') flags.storage.push(next(args, arg));
  else if (arg === '--init-script') flags.initScript = next(args, arg);
  else if (arg === '--wait') flags.wait = Number(next(args, arg));
  else if (arg === '--state') {
    state = next(args, arg);
    if (state === 'none') state = undefined;
    trailing = true;
  } else if (arg === '--help' || arg === '-h') help();
  else if (arg.startsWith('-')) stop(`unknown option ${arg}`);
  else if (plain.length < 2) plain.push(arg);
  else {
    paths.push({ path: arg, state });
    trailing = false;
  }
}
for (const item of trailing && state ? paths : []) item.state ??= state; // BASE OUT /a /b --state FILE
const [base, out] = plain;
let site = null;
try {
  site = new URL(base);
} catch { /* not an address: stopped on the next line */ }
if (!site || !out || !/^https?:$/.test(site.protocol)) stop('give the address of your app (http://...) and a folder');
if (!(flags.wait >= 0 && flags.wait <= 60000)) stop('--wait takes milliseconds, from 0 to 60000');
if (!flags.widths.every((width) => Number.isInteger(width) && width >= 240 && width <= 3840)) {
  stop('--width takes whole pixels, from 240 to 3840');
}
const widths = flags.widths.length ? [...new Set(flags.widths)] : WIDTHS;
const storage = flags.storage.map((pair) => {
  const at = pair.indexOf('=');
  return at > 0 ? [pair.slice(0, at), pair.slice(at + 1)] : stop(`--storage takes KEY=VALUE, not ${pair}`);
});
if (!paths.length) paths.push({ path: site.pathname + site.search, state });
for (const file of new Set(paths.map((item) => item.state).filter(Boolean))) {
  try {
    JSON.parse(readFileSync(file, 'utf8'));
  } catch {
    stop(`--state: ${file} is not a storage state file that can be read`);
  }
}
if (flags.initScript) {
  try {
    readFileSync(flags.initScript, 'utf8');
  } catch {
    stop(`--init-script: ${flags.initScript} is not a file that can be read`);
  }
}

// "/" becomes "home", "/settings/billing?tab=2" becomes "settings-billing-tab-2".
const nameOf = (path) => path.replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'home';

let failed = 0;
const targets = []; // the pages to shoot: only pages of BASE
const names = new Set(); // the same PATH twice (signed out and signed in) gets the state's name too
for (const { path, state: file } of paths) {
  let url = null;
  try {
    url = new URL(path, site);
  } catch { /* not an address: skipped below */ }
  if (url && url.origin === site.origin) {
    const who = file ? nameOf(basename(file, '.json')) : 'public';
    const first = names.has(nameOf(path)) ? `${nameOf(path)}-${who}` : nameOf(path);
    let name = first;
    for (let count = 2; names.has(name); count += 1) name = `${first}-${count}`;
    names.add(name);
    targets.push({ path, href: url.href, name, state: file, asked: url.pathname });
  } else {
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
  console.error('Playwright is not installed here. Run this from e2e/, or install it next to this file, which leaves '
    + 'the project as it is: npm install --prefix forge-work/design @playwright/test, then cd forge-work/design && '
    + 'npx playwright install chromium (../forge-design/review.md section 1)');
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

// A page that led to another site is never shot, nor a sign-in page in place of the screen asked for:
// an expired session would otherwise give a login form under the screen's name, which changed.py then
// counts as a change. Another path on the site (a locale, a trailing slash) is said in the line.
async function arrived(page, shot) {
  const now = new URL(page.url());
  if (now.origin !== site.origin) throw new Error(`it led to ${now.origin}, which is not ${site.origin}`);
  const bare = (path) => path.replace(/\/+$/, '') || '/';
  if (bare(now.pathname) === bare(shot.asked)) return '';
  const form = await page.locator('input[type="password"]:visible').count().catch(() => 0);
  if (!SIGN_IN.test(now.pathname) && !form) return `it led to ${now.pathname}`;
  throw new Error(`it led to ${now.pathname}, a sign-in page, in place of ${shot.asked}: ${shot.state
    ? `the session in ${shot.state} has expired, so sign in again` : 'it needs --state'} (review.md section 1)`);
}

// Every still and frame goes through here: `take` writes the file, and the file gets its one line.
async function save(page, shot, tail, note, take) {
  const away = await arrived(page, shot);
  const file = `${shot.stem}-${tail}.png`;
  await take(file);
  const said = [away, note].filter(Boolean).join(', ');
  console.log(`${shot.status} ${file}${said ? `  (${said})` : ''}`);
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

// Runs in the page: `theme`, the theme it says it shows, "light" or "dark" (data-theme or a dark class
// on <html>, or its color-scheme), or "" when it says none; and `print`, a number made of the colours it
// paints its elements in. A page that says nothing is never named by its paint (a light page with a dark
// hero would pass for dark): two system settings that give the same print gave the same page.
function themeShown() {
  let theme = '';
  for (const node of [document.documentElement, document.body]) {
    for (const name of ['data-theme', 'data-color-scheme', 'data-mode', 'data-bs-theme']) {
      const value = node?.getAttribute(name);
      if (!theme && (value === 'dark' || value === 'light')) theme = value;
    }
    if (!theme && node?.classList.contains('dark')) theme = 'dark';
  }
  const scheme = getComputedStyle(document.documentElement).colorScheme.replace('only ', '');
  if (!theme && (scheme === 'dark' || scheme === 'light')) theme = scheme;
  let print = 0;
  for (const node of [...document.querySelectorAll('html, body, body *')].slice(0, 5000)) {
    const style = getComputedStyle(node);
    for (const char of `${style.color}|${style.backgroundColor}|${style.backgroundImage}|${style.borderTopColor};`) {
      print = (Math.imul(print, 31) + char.charCodeAt(0)) | 0;
    }
  }
  return { theme, print };
}

// Runs in the page, and in each frame of BASE in it: the scenes in the window. A scene is an element
// with data-scene (the kit's stage sets "live", or "fallback" with no WebGL), or the box around a
// data-scene-poster, which shows while its scene loads. A scene out of the window is not waited for.
function scenesHere() {
  const boxes = new Set(document.querySelectorAll('[data-scene]'));
  for (const poster of document.querySelectorAll('[data-scene-poster]')) {
    boxes.add(poster.closest('[data-scene]') || poster.parentElement);
  }
  const seen = { live: 0, fallback: 0, waiting: 0, box: null };
  for (const box of boxes) {
    const edge = box.getBoundingClientRect();
    const x = Math.max(0, edge.left);
    const y = Math.max(0, edge.top);
    const width = Math.min(innerWidth, edge.right) - x;
    const height = Math.min(innerHeight, edge.bottom) - y;
    if (width < 2 || height < 2) continue;
    const now = box.getAttribute('data-scene');
    seen[now === 'live' || now === 'fallback' ? now : 'waiting'] += 1;
    seen.box ??= { x, y, width, height };
  }
  return seen;
}

// Runs in the page, before a still of the whole page. An app that keeps a fixed frame and scrolls a
// panel inside it gets that panel opened up, so the still holds what a person scrolls to there; a bar
// fixed to the bottom of the window (a tab bar) moves to the bottom of the picture. `undo` puts it back.
function unfold(undo) {
  const changes = (window.forgeShotsUnfold ??= []);
  if (undo) {
    for (const [node, name, value, priority] of changes.splice(0).reverse()) node.style.setProperty(name, value, priority);
    return '';
  }
  const set = (node, name, value) => {
    changes.push([node, name, node.style.getPropertyValue(name), node.style.getPropertyPriority(name)]);
    node.style.setProperty(name, value, 'important');
  };
  const root = document.scrollingElement || document.documentElement;
  let panel = null;
  let largest = 0.25 * innerWidth * innerHeight; // the screen's own content, not a list in a corner
  for (const node of root.scrollHeight - root.clientHeight < 2 ? document.querySelectorAll('body *') : []) {
    const area = node.clientWidth * node.clientHeight;
    // At least half the window wide: a list beside a map stays shut, as opened it would stretch the map
    if (area > largest && node.clientWidth >= innerWidth / 2 && node.scrollHeight - node.clientHeight > 1
        && /auto|scroll|overlay/.test(getComputedStyle(node).overflowY)) {
      largest = area;
      panel = node;
    }
  }
  for (let node = panel; node; node = node.parentElement) {
    for (const [name, value] of [['height', 'auto'], ['max-height', 'none'], ['overflow', 'visible']]) {
      set(node, name, value);
    }
  }
  const below = root.scrollHeight - innerHeight;
  const bars = [];
  for (const node of below > 0 ? document.querySelectorAll('body *') : []) {
    const edge = node.getBoundingClientRect();
    const low = edge.height && edge.top >= innerHeight / 2 && edge.height < innerHeight / 2; // in the bottom half
    if (low && !bars.some((bar) => bar.contains(node)) && getComputedStyle(node).position === 'fixed') {
      set(node, 'translate', `0 ${below}px`);
      bars.push(node);
    }
  }
  return [panel && 'its scroll panel opened up (looks broken there? take it again with --viewport-only)',
    bars.length && `${bars.length} bar(s) fixed to the bottom of the window drawn at the bottom of the page`]
    .filter(Boolean).join(', ');
}

// Runs in the page: how much wider than the window it is (it scrolls sideways), and the outer parts that
// stick out past the right edge with nothing around them that clips them. An app that keeps a fixed frame
// (the page itself does not scroll) is asked the same of its main scroll panel, the largest one that
// scrolls down, of a quarter of the window or more (the one unfold() and glide() pick): there a phone
// layout that is too wide scrolls sideways inside the frame. A board of columns or a table's own wrapper,
// built to scroll sideways, does not scroll down, so it is never that panel. Null when it fits.
function sideways() {
  const root = document.documentElement;
  let box = root.scrollWidth > root.clientWidth ? root : null;
  if (!box && root.scrollHeight - root.clientHeight < 2) {
    let largest = 0.25 * innerWidth * innerHeight;
    for (const node of document.querySelectorAll('body, body *')) {
      const area = node.clientWidth * node.clientHeight;
      const style = area > largest && node.scrollHeight - node.clientHeight > 1 && getComputedStyle(node);
      if (style && /auto|scroll|overlay/.test(style.overflowY)) {
        largest = area;
        box = /auto|scroll|overlay/.test(style.overflowX) && node.scrollWidth > node.clientWidth + 1 ? node : null;
      }
    }
  }
  if (!box) return null;
  const right = (box === root ? 0 : box.getBoundingClientRect().left + box.clientLeft) + box.clientWidth;
  const clipped = (node) => {
    for (let up = node.parentElement; up && up !== box && up !== root; up = up.parentElement) {
      if (getComputedStyle(up).overflowX !== 'visible') return true;
    }
    return false;
  };
  const parts = [];
  for (const node of (box === root ? document.body : box).querySelectorAll('*')) {
    const edge = node.getBoundingClientRect();
    if (parts.length === 3 || !edge.width || edge.right <= right + 1) continue;
    if (parts.some((part) => part.contains(node)) || getComputedStyle(node).position === 'fixed' || clipped(node)) continue;
    parts.push(node);
  }
  const name = (node) => node.tagName.toLowerCase() + (node.id ? `#${node.id}` : '')
    + [...node.classList].slice(0, 2).map((part) => `.${part}`).join('');
  const path = (node) => (node.parentElement && node.parentElement !== document.body ? `${name(node.parentElement)} > ` : '')
    + name(node);
  return { width: box.scrollWidth, window: box.clientWidth, panel: box === root ? '' : name(box),
    parts: parts.map((node) => `${path(node)} (to ${Math.round(node.getBoundingClientRect().right)}px)`) };
}

// Runs in the page: text a person can see against what is behind it, as WCAG 2 measures it (4.5:1, or
// 3:1 from 24px or 18.66px bold). `which` is "page" (all its text), "controls" (it keeps the controls
// in the window and returns their middles) or the number of one of those: its text now, `state` being
// "focus" (focused, then let go) or "hover" (the pointer is on it). Left out, as WCAG does: hidden text,
// disabled controls; also text in an svg and text hidden from screen readers. Text over a picture, a
// canvas or a video, over or under a box the page places beside it, or painted by its background, is
// counted, not measured. A shade over a whole box (a ::before or ::after) is laid over that box's own
// background. A background picture is measured on the colour under it: that colour shows while the
// picture loads, or when it does not.
function contrast({ which, state, limit }) {
  const paint = Object.assign(document.createElement('canvas'), { width: 1, height: 1 })
    .getContext('2d', { willReadFrequently: true });
  const rgba = (colour) => { // any colour the browser computes, as red, green and blue (0-255) and alpha
    paint.clearRect(0, 0, 1, 1);
    paint.fillStyle = '#000';
    paint.fillStyle = colour;
    paint.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = paint.getImageData(0, 0, 1, 1).data;
    return [r, g, b, a / 255];
  };
  const over = (top, under) => [0, 1, 2].map((i) => top[i] * top[3] + under[i] * (1 - top[3])).concat(1);
  const glow = (colour) => colour.slice(0, 3).reduce((sum, value, i) => {
    const v = value / 255;
    return sum + [0.2126, 0.7152, 0.0722][i] * (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  }, 0);
  const ratio = (one, two) => (Math.max(glow(one), glow(two)) + 0.05) / (Math.min(glow(one), glow(two)) + 0.05);
  const scheme = getComputedStyle(document.documentElement).colorScheme;
  const base = /dark/.test(scheme) && (!/light/.test(scheme) || matchMedia('(prefers-color-scheme: dark)').matches)
    ? [18, 18, 18, 1] : [255, 255, 255, 1]; // what the browser paints under a page with no background
  const pictures = [...document.querySelectorAll('img, picture, video, canvas, iframe, object, embed, svg')]
    .filter((node) => !node.parentElement?.closest('svg')).map((node) => [node, node.getBoundingClientRect()])
    .filter(([, edge]) => edge.width * edge.height >= 600);
  const covered = (node, edge) => pictures.some(([picture, p]) => !node.contains(picture)
    && p.left < edge.right && p.right > edge.left && p.top < edge.bottom && p.bottom > edge.top);
  // Boxes the page places itself (position absolute or fixed) that paint a colour or a picture. One that
  // holds no text, sits at z-index 0 or below and is behind the whole page (fixed and as large as the
  // window, or absolute and as wide as the window from the page's top to its end) is a backdrop: it counts
  // as behind every text. Any other one (such as a hero's layer that fills only the first screen) over the
  // middle of a text it is not around makes that text unmeasured: which of the two is on top depends on
  // the order and z-index of whole branches, which this does not work out. Text below that layer is
  // measured as usual. Asked once per still: the calls for one control reuse what the first call found.
  const findBoxes = () => {
    const found = { placed: [], backdrops: [] };
    const end = document.documentElement.scrollHeight;
    for (const box of document.querySelectorAll('body *')) {
      const style = getComputedStyle(box);
      if (!/absolute|fixed/.test(style.position) || style.visibility === 'hidden' || Number(style.opacity) < 0.05
          || (rgba(style.backgroundColor)[3] < 0.1 && style.backgroundImage === 'none')) continue;
      const edge = box.getBoundingClientRect();
      if (edge.width * edge.height < 600) continue;
      const whole = edge.left <= 0 && edge.right >= innerWidth && (style.position === 'fixed'
        ? edge.top <= 0 && edge.bottom >= innerHeight : edge.top + scrollY <= 0 && edge.bottom + scrollY >= end - 1);
      if (whole && !box.textContent.trim() && !(parseInt(style.zIndex, 10) > 0)) found.backdrops.push(style);
      else found.placed.push([box, edge]);
    }
    return found;
  };
  const boxes = typeof which === 'number' && window.forgeShotsBoxes ? window.forgeShotsBoxes
    : (window.forgeShotsBoxes = findBoxes());
  const beside = (node, edge) => {
    const [x, y] = [edge.left + edge.width / 2, edge.top + edge.height / 2];
    return boxes.placed.some(([box, b]) => !box.contains(node) && b.left <= x && x <= b.right && b.top <= y && y <= b.bottom);
  };
  const known = new Map(); // node -> the colours behind its text, laid over each other from the page up
  const behind = (node) => { // a gradient adds each of its colours: the worst of them decides
    if (!node) return { colours: [base], fade: 1, picture: false };
    if (known.has(node)) return known.get(node);
    const below = behind(node.parentElement);
    const style = getComputedStyle(node);
    const layers = [[style, 1]]; // its own background, then a shade over its whole box (a ::before, an ::after)
    const edge = style.position !== 'static' && node.getBoundingClientRect();
    for (const pseudo of edge && edge.width && edge.height ? ['::before', '::after'] : []) {
      const shade = getComputedStyle(node, pseudo);
      if (shade.content !== 'none' && shade.display !== 'none' && /absolute|fixed/.test(shade.position)
          && parseFloat(shade.width) >= 0.9 * edge.width && parseFloat(shade.height) >= 0.9 * edge.height) {
        layers.push([shade, Number(shade.opacity)]);
      }
    }
    if (node === document.body) layers.push(...boxes.backdrops.map((backdrop) => [backdrop, Number(backdrop.opacity)]));
    let { colours, picture } = below;
    for (const [layer, fade] of layers) {
      const tint = (colour) => rgba(colour).map((value, i) => (i === 3 ? value * fade : value));
      const stops = layer.backgroundImage.match(/(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\([^()]*\)/g) || [];
      colours = colours.map((colour) => over(tint(layer.backgroundColor), colour));
      if (stops.length) colours = colours.flatMap((colour) => stops.map((stop) => over(tint(stop), colour))).slice(0, 16);
      picture ||= layer.backgroundImage.includes('url(');
    }
    const found = { colours, fade: below.fade * Number(style.opacity), picture };
    known.set(node, found);
    return found;
  };
  const left = 'svg, [aria-hidden="true"], [disabled], [aria-disabled="true"], [inert]'; // never measured
  const shown = (node) => {
    const edge = node.getBoundingClientRect();
    return edge.width >= 2 && edge.height >= 2 && !node.closest(left)
      && (node.checkVisibility?.({ checkOpacity: true, checkVisibilityCSS: true }) ?? true);
  };
  const name = (node) => node.tagName.toLowerCase() + (node.id ? `#${node.id}` : '')
    + [...node.classList].slice(0, 2).map((part) => `.${part}`).join('');
  const result = { read: 0, unmeasured: [], low: [] };
  const measure = (node, text, pseudo) => {
    const style = getComputedStyle(node, pseudo);
    const edge = node.getBoundingClientRect();
    const { colours, fade, picture } = behind(node);
    const ink = rgba(style.color);
    const parent = node.parentElement && node.parentElement !== document.body ? `${name(node.parentElement)} > ` : '';
    const spot = { text, where: parent + name(node), down: Math.round(edge.top + scrollY) };
    if (ink[3] * fade < 0.1 || covered(node, edge) || beside(node, edge)) return void result.unmeasured.push(spot);
    result.read += 1;
    const size = parseFloat(style.fontSize);
    const need = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700) ? 3 : 4.5;
    const worst = Math.min(...colours.map((under) => ratio(over([ink[0], ink[1], ink[2], ink[3] * fade], under), under)));
    if (worst >= need) return;
    result.low.push({ ...spot, ratio: Math.floor(worst * 100) / 100, need, size: Math.round(size), picture });
  };
  const scan = (top) => {
    const done = new Set();
    for (const walk = document.createTreeWalker(top, NodeFilter.SHOW_TEXT); walk.nextNode();) {
      const node = walk.currentNode.parentElement;
      const text = walk.currentNode.textContent.replace(/\s+/g, ' ').trim();
      if (text.length < 2 || !node || done.has(node) || !shown(node)) continue;
      done.add(node);
      measure(node, text.slice(0, 40));
    }
    for (const field of top.querySelectorAll('input[placeholder], textarea[placeholder]')) {
      if (!field.value && field.placeholder.trim() && shown(field)) {
        measure(field, `placeholder "${field.placeholder.trim().slice(0, 30)}"`, '::placeholder');
      }
    }
  };
  if (which === 'page') scan(document.body);
  else if (which === 'controls') {
    const inside = (edge) => edge.top >= 0 && edge.left >= 0 && edge.bottom <= innerHeight && edge.right <= innerWidth;
    window.forgeShotsControls = [...document.querySelectorAll('a[href], button, summary, select, [role="button"], '
      + '[role="tab"], [role="link"], [role="menuitem"], [role="option"], [tabindex]:not([tabindex="-1"])')]
      .filter((node) => node.textContent.trim() && shown(node) && inside(node.getBoundingClientRect())).slice(0, limit);
    return window.forgeShotsControls.map((node) => {
      const edge = node.getBoundingClientRect();
      return { x: edge.left + edge.width / 2, y: edge.top + edge.height / 2 };
    });
  } else {
    const node = window.forgeShotsControls?.[which];
    if (!node?.isConnected) return result;
    if (state === 'focus') node.focus({ preventScroll: true, focusVisible: true });
    for (const run of document.getAnimations()) { // the state itself, not a step of its transition
      if (run instanceof CSSTransition) run.finish();
    }
    scan(node);
    if (state === 'focus') node.blur();
  }
  return result;
}

// The scenes in the window: in the page, and in the frames of BASE inside it (a board of previews).
// `box` is where the first one is (the pointer crosses it), `size` the first one's box in the page itself.
async function scenes(page) {
  const seen = { live: 0, fallback: 0, waiting: 0, box: null, size: null };
  const { width, height } = page.viewportSize();
  for (const frame of page.frames()) {
    const main = frame === page.mainFrame();
    try {
      let edge = null;
      if (!main) {
        if (new URL(frame.url()).origin !== site.origin) continue;
        const box = await (await frame.frameElement()).boundingBox();
        const x = Math.max(0, box?.x ?? width);
        const y = Math.max(0, box?.y ?? height);
        edge = { x, y, width: Math.min(width, box.x + box.width) - x, height: Math.min(height, box.y + box.height) - y };
        if (edge.width < 2 || edge.height < 2) continue; // a frame out of the window
      }
      const here = await frame.evaluate(scenesHere);
      for (const key of ['live', 'fallback', 'waiting']) seen[key] += here[key];
      if (here.box && !seen.box) seen.box = main ? here.box : edge;
      if (here.box && main) seen.size = here.box;
    } catch { /* a frame that went away while it was asked */ }
  }
  return seen;
}

// Waits until every scene in the window is live: SCENE_LIMIT at most, and `find` ms for one to show up
// at all (a still does not wait for a scene it does not see). Returns what it saw, and what to say.
async function live(page, find) {
  const start = Date.now();
  let seen = await scenes(page);
  for (;;) {
    const waited = Date.now() - start;
    if (waited > SCENE_LIMIT || (!seen.waiting && (seen.live || seen.fallback || waited >= find))) break;
    await page.waitForTimeout(250);
    seen = await scenes(page);
  }
  const seconds = Math.round((Date.now() - start) / 1000);
  if (seen.live) await page.waitForTimeout(SETTLE);
  const { width, height } = page.viewportSize(); // the size a level asks for: ../forge/levels.md
  const size = seen.size && `the first ${Math.round(seen.size.width)} x ${Math.round(seen.size.height)} px in the `
    + `window (${Math.round((100 * seen.size.width) / width)}% of its width, `
    + `${Math.round((100 * seen.size.height) / height)}% of its height)`;
  const said = [seen.live && `${seen.live} scene(s) live after ${seconds} s`,
    seen.fallback && `${seen.fallback} scene(s) on their poster: no WebGL here, or the scene failed`,
    seen.waiting && `${seen.waiting} scene(s) never went live in ${SCENE_LIMIT / 1000} s`, size].filter(Boolean).join(', ');
  return { seen, said };
}

// --overflow and --contrast, for one still. A finding is a line, and the run exits 1.
async function overflowCheck(page, shot, theme) {
  const wide = await page.evaluate(sideways);
  if (!wide) return;
  failed += 1;
  const parts = wide.parts.length ? `; sticking out: ${wide.parts.join(', ')}` : '';
  const what = wide.panel ? `its scroll panel ${wide.panel} is ${wide.width}px wide inside ${wide.window}px`
    : `the page is ${wide.width}px wide in a window of ${wide.window}px`;
  console.log(`wide  ${shot.path} at ${shot.width}px ${theme}: ${what}, so it scrolls sideways${parts}`);
}
async function contrastCheck(page, shot, theme, file) {
  const rest = await page.evaluate(contrast, { which: 'page' });
  const low = rest.low.map((item) => ({ ...item, state: '' }));
  const spots = await page.evaluate(contrast, { which: 'controls', limit: CONTROLS });
  for (const [index, spot] of spots.entries()) {
    const focused = await page.evaluate(contrast, { which: index, state: 'focus' });
    await page.mouse.move(spot.x, spot.y);
    const hovered = await page.evaluate(contrast, { which: index, state: 'hover' });
    low.push(...focused.low.map((item) => ({ ...item, state: 'on focus' })),
      ...hovered.low.map((item) => ({ ...item, state: 'on hover' })));
  }
  await page.mouse.move(0, 0);
  const keys = new Set(); // the same text, place and ratio in three states is one fault, said once
  const faults = low.filter((item) => {
    const key = `${item.text}|${item.where}|${item.ratio}`;
    return !keys.has(key) && keys.add(key);
  });
  const where = `${shot.path} at ${shot.width}px ${theme}`;
  for (const item of faults.slice(0, 8)) {
    const picture = item.picture ? ', over a background picture: measured on the colour under it' : '';
    console.log(`low contrast  ${where}${item.state ? `, ${item.state}` : ''}: "${item.text}" ${item.ratio.toFixed(2)}:1 `
      + `where ${item.need}:1 is needed (${item.size}px, ${item.where}, ${item.down}px down${picture})`);
  }
  if (faults.length > 8) console.log(`low contrast  ${where}: and ${faults.length - 8} more`);
  const off = rest.unmeasured; // named with their place, up to five, so each can be found in the still
  const named = off.slice(0, 5).map((item) => `"${item.text}" (${item.where}, ${item.down}px down)`).join(', ');
  const unmeasured = off.length ? `; ${off.length} over a picture, a canvas, a video or a box placed beside it, not `
    + `measured: look at ${named}${off.length > 5 ? ` and ${off.length - 5} more` : ''} in ${basename(file)}` : '';
  const count = (number, one) => `${number} ${one}${number === 1 ? '' : 's'}`;
  console.log(`contrast  ${where}: ${count(rest.read, 'text')} and ${count(spots.length, 'control')} read, `
    + `${faults.length ? `${faults.length} under WCAG AA` : 'all at WCAG AA'}${unmeasured}`);
  if (faults.length) failed += 1;
}

// A still: the whole page, or the window with --viewport-only, named by the theme the page says it shows,
// else by the system setting. The same theme twice at one width (an app that keeps its own theme), or a
// page that says none and is painted the same under both settings, is taken once. Then the checks.
const written = new Map(); // the stills of this run, and the print of the page in each (themeShown)
async function still(page, shot, job) {
  const note = [await ready(page, shot)];
  await page.waitForTimeout(flags.wait);
  if (!job.frozen) note.push((await live(page, 0)).said); // with motion on, a still shows the scene live
  else if ((await scenes(page)).waiting) note.push('a scene in the window was still loading: its poster shows');
  const shown = job.tail === 'reduced' ? { theme: 'reduced', print: null } : await page.evaluate(themeShown);
  const theme = shown.theme || job.scheme;
  const file = `${shot.stem}-${theme}.png`;
  const twin = shown.theme ? undefined : ['light', 'dark'].map((name) => `${shot.stem}-${name}.png`)
    .find((name) => written.has(name) && written.get(name) === shown.print);
  if (written.has(file) || twin) {
    const why = twin ? `the page names no theme and looks as in ${basename(twin)}` : `the app shows its ${theme} theme too`;
    console.log(`same ${twin || file}: with the system set to ${job.scheme} ${why}, so that still is not taken twice `
      + '(for an app that keeps its own theme: --storage or --init-script)');
    return;
  }
  if (flags.fullPage) {
    await scroll(page, 1, THROUGH); // to the end: late pictures load, what appears on scroll appears
    await scroll(page, 0, { speed: 1, longest: 0 }); // and back to the top at once
  }
  // Frozen, the page is at rest. With motion on, its entrance and what the scroll brought must be over.
  await page.waitForTimeout(job.frozen ? (flags.fullPage ? ARRIVE : 0) : ENTRANCE);
  const checks = job.tail !== 'reduced';
  if (checks && flags.overflow) await overflowCheck(page, shot, theme);
  const opened = flags.fullPage ? await page.evaluate(unfold) : '';
  await save(page, shot, theme, note.concat(opened).filter(Boolean).join(', '),
    (path) => page.screenshot({ path, fullPage: flags.fullPage }));
  written.set(file, shown.print);
  if (opened) await page.evaluate(unfold, true);
  if (checks && flags.contrast) await contrastCheck(page, shot, theme, file);
}

// A frame is the window as it is at that moment, so it is asked of the browser itself:
// page.screenshot() would first get the page ready for a picture, and that takes time.
async function grabber(page) {
  const chrome = await page.context().newCDPSession(page);
  return async (file) => {
    const asked = chrome.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true });
    await writeFile(file, Buffer.from((await within(QUIET_LIMIT, asked)).data, 'base64'));
  };
}

// Scene frames: s1 to s6 over about 3 seconds, once the scenes in the window are live, with nothing
// scrolled and the pointer moving across the first of them. A scene that moves by itself or follows
// the pointer differs from frame to frame; one that stands still, or never went live, does not.
async function sceneFrames(page, shot) {
  const grab = await grabber(page);
  const note = await ready(page, shot);
  await page.waitForTimeout(flags.wait);
  const { seen, said } = await live(page, FIND_LIMIT + flags.wait);
  if (seen.waiting) {
    console.error(`failed ${shot.path} at ${shot.width}px scene frames: ${said}, so they show it loading`);
    failed += 1;
  }
  const box = seen.box || { x: 0, y: 0, width: shot.width, height: shot.height };
  const spot = (share) => ({ x: box.x + box.width * (0.2 + 0.6 * share),
    y: box.y + box.height * (0.5 - 0.2 * Math.sin(Math.PI * share)) });
  await page.mouse.move(spot(0).x, spot(0).y);
  const start = Date.now();
  for (let index = 1; index <= SCENE_FRAMES; index += 1) {
    for (let step = 1; index > 1 && step <= 10; step += 1) { // half a second of the pointer moving
      const to = spot((index - 2 + step / 10) / (SCENE_FRAMES - 1));
      await page.mouse.move(to.x, to.y);
      await page.waitForTimeout(50);
    }
    const when = `${((Date.now() - start) / 1000).toFixed(1)} s in`;
    const none = 'no scene in the window (a scene still loading shows only by its data-scene-poster child)';
    await save(page, shot, `s${index}`, [said || none, when, note].filter(Boolean).join(', '), grab);
  }
}

// Frames: f1 to f4 over the first second, then f5 to f7 while scrolling down in steps.
async function frames(page, shot) {
  const grab = await grabber(page);
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
  const away = await arrived(page, shot);
  const file = `${shot.stem}.webm`;
  await page.close(); // the film is whole once its page is closed
  await page.video().saveAs(file);
  await page.video().delete(); // the working copy in the temp folder
  const said = [px ? `scrolled ${px} px in ${seconds} s` : 'the page does not scroll', away].filter(Boolean);
  console.log(`${shot.status} ${file}  (${said.join(', ')})`);
}

// Runs in each page before its own scripts: the --storage items, for pages of BASE only.
function remember({ origin, pairs }) {
  if (location.origin !== origin) return;
  try {
    for (const [key, value] of pairs) localStorage.setItem(key, value);
  } catch { /* storage is switched off for this page: there is nothing to set */ }
}

// What to make of every page. `frozen` asks the app for reduced motion (see the top of this file).
const moving = flags.frames || flags.scenes || flags.video;
const jobs = [];
for (const scheme of flags.dark ? ['light', 'dark'] : ['light']) {
  for (const width of widths) jobs.push({ make: still, width, scheme, tail: scheme, frozen: !moving });
}
for (const width of flags.reduced ? widths : []) {
  jobs.push({ make: still, width, scheme: 'light', tail: 'reduced', frozen: true });
}
for (const width of flags.frames ? widths : []) {
  jobs.push({ make: frames, width, scheme: 'light', tail: 'frames', frozen: false });
}
for (const width of flags.scenes ? widths : []) {
  jobs.push({ make: sceneFrames, width, scheme: 'light', tail: 'scene frames', frozen: false });
}
if (flags.video) jobs.push({ make: film, width: FILM.width, scheme: 'light', tail: 'film', frozen: false });

// Opens one page in a browser window of its own, so no cache or service worker of an earlier page sits
// in between, lets the job make its pictures, and closes it. False: the page gave no answer.
const errorPages = new Set();
const said = new Map(); // page name -> the console errors already said for it
async function visit(target, job) {
  const size = { width: job.width, height: job.width < 600 ? 844 : 900 };
  const errors = []; // what the page itself reports as broken: said after the job, once per page
  const told = said.get(target.name) ?? said.set(target.name, new Set()).get(target.name);
  let context = null;
  let answered = false;
  try {
    context = await browser.newContext({
      viewport: size,
      deviceScaleFactor: 1, // 100%: eyedropper.py, imgdiff.py and changed.py read real pixels
      colorScheme: job.scheme,
      reducedMotion: job.frozen ? 'reduce' : 'no-preference',
      storageState: target.state,
      recordVideo: job.make === film ? { dir: tmpdir(), size } : undefined,
    });
    context.setDefaultTimeout(LOAD_LIMIT); // nothing Playwright does here waits longer
    if (storage.length) await context.addInitScript(remember, { origin: site.origin, pairs: storage });
    if (flags.initScript) await context.addInitScript({ path: flags.initScript });
    const page = await context.newPage();
    page.on('pageerror', (error) => errors.push(firstLine(error)));
    page.on('console', (message) => {
      if (message.type() !== 'error') return;
      const from = /^https?:/.test(message.location().url ?? '') ? new URL(message.location().url) : null;
      const where = from ? ` (${from.origin}${from.pathname})` : ''; // never the query: it can hold a key
      errors.push(message.text().split('\n')[0] + where);
    });
    const response = await page.goto(target.href, { waitUntil: 'commit' }).catch((error) => {
      throw new Error(`no answer. Is the app running at ${site.origin}? (${firstLine(error)})`);
    });
    const shot = { ...size, path: target.path, asked: target.asked, state: target.state };
    await arrived(page, shot); // another site, or the sign-in page: not tried again in the other settings
    answered = true;
    const status = response ? response.status() : '---';
    if (status >= 400 && !errorPages.has(target.name)) {
      errorPages.add(target.name);
      console.error(`failed ${target.path}: the server answered ${status}, so the pictures show its error page`);
      failed += 1;
    }
    await job.make(page, { ...shot, status, stem: join(out, `${target.name}-${job.width}`) }, job);
  } catch (error) {
    console.error(`failed ${target.path} at ${job.width}px ${job.tail}: ${firstLine(error)}`);
    failed += 1;
  } finally {
    for (const text of errors) {
      if (!told.has(text) && told.size < 10) console.log(`console  ${target.path}: ${text.slice(0, 240)}`);
      told.add(text);
    }
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
