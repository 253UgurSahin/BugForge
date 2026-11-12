# The scene kit in an app

How to put the scene kit (the folder of `../forge-design/scenes/stage.js`) into an app: which
file does what, which scene fits which concept, and how to install, copy, mount and budget it per
stack. The full API of each file is the comment at its top: read it before you tune a scene. The
levels: `../forge/levels.md`; the recipes around the kit: `../forge-design/motion.md` sections 8 to 12.

## 1. The files, and from which level (levels 1 and 2 use none)

| file | what it is | from level |
| --- | --- | --- |
| `../forge-design/scenes/depth.js` + `../forge-design/scenes/depth.css` | real depth with CSS 3D, no WebGL, no library: tilting cards, stacked panels, folds, a layered hero | 3 Expressive |
| `../forge-design/scenes/stage.js` | the runtime under every WebGL scene: renderer, camera, colours from the tokens, pointer, pausing, reduced motion, quality, fallback, clean-up | 4 Showpiece |
| `../forge-design/scenes/glsl.js` | shader pieces as strings (noise, curl, fbm, palette, grain, fog, lines); the scenes use it, and so do the app's own scene (level 4) and shader (level 5) | 4 |
| `../forge-design/scenes/lazy.js` | `lazyScene()`: loads three and a scene only near the viewport and when the page is idle (never without WebGL), poster until then; `motionToggle()`: one pause button for every scene | 4 |
| `../forge-design/scenes/form.js` | a sculptural form of glowing strands (knot family: ring, knot, coil) that breathes, turns and leans to the pointer | 4 |
| `../forge-design/scenes/field.js` | tens of thousands of GPU particles in a slow current, formations cloud, ring, wave, grid; round points or streaks that turn with their path | 4 |
| `../forge-design/scenes/aurora.js` | a shader atmosphere behind a hero or a whole page, modes `aurora`, `water` (clear, shallow water from above), `mist` | 4 |
| `../forge-design/scenes/contour.js` | living contour lines: a map, a depth chart; flat or tilted in 3D, of invented land or of the app's own outline (one lake, one trail, one plot), with places for the page's labels | 4 |
| `../forge-design/scenes/datascape.js` | the app's own numbers as 3D bars or ridgelines, with hover | 5 (dashboard 5) |
| `../forge-design/scenes/journey.js` | the level-5 director: a scroll trip with a camera through chapters | 5 Cinematic |

## 2. Which scene for which concept

Start from the app's own world (its material, tool, place, ritual), never from the list. Then:

| the concept is about | scene | for example |
| --- | --- | --- |
| a thing that winds: rope, wire, a coil | `form.js` | a knot of rope for a sailing school, a coil for a workshop |
| any other object of the app's world | the app's own scene on `stage.js` (from level 4, below) | a ledger that folds open for a bookkeeping app, an appointment book for a salon |
| a crowd, a flow, numbers, wind | `field.js` (`streak` for wind, rain, traffic, a school of fish) | visitors arriving, a flock, a weather app's wind |
| light, sky, weather; clear water | `aurora.js` (mode `mist` for weather, `water` for clear, shallow water) | a planetarium's sky, a diving school's reef |
| one place: a lake, a trail, a plot | `contour.js` with its `outline`, `view: "tilt"` for 3D | a lake's depth chart from its outline, a hiking route, a vineyard's plot |
| places, depth, height, maps | `contour.js` (`view: "tilt"` for land in 3D) | a hiking app, a pressure map |
| the app's own numbers | `datascape.js` | bookings by hour and month, catches per spot |
| real depth in the interface (level 3 and up) | `depth.js` + `depth.css` | cards that tilt, plans stacked as screens, a hero in layers |
| the level-5 trip through one scene | `journey.js` with `form.js`, `field.js`, `datascape.js` or the app's own scene (`aurora.js` and `contour.js` set their own view) | a rope from its coil to the knot it ties; the lake from far, then close, then under the surface (the app's own scene) |

`aurora.js`'s `water` is clear, shallow, sunlit water seen from above, with the net of light on its
bed: a pool, a reef. Murky inland water (a Dutch lake, a canal, a river) is `mist` over it, its
reflections, or `contour.js` with that water's own outline.

**The app's own scene.** `form.js` draws only knots, rings and coils, and a knot that stands in for
a ledger, a book, a ticket or a plate is the random torus of the generic look. When no scene above
draws the concept's thing, write the app's own scene, from level 4. The comment at the top of
`../forge-design/scenes/stage.js` is a whole scene: swap its torus knot for that thing's own
geometry, built in code, and keep the rules listed there. Copy, mount and budget it as a kit scene
(sections 4, 5 and 8).

**Make it belong to one app.** A kit scene on its defaults is a failed hero.
- **Options** (the comment at the top of each scene): shape, the calm side for the text, scale,
  speed, intensity, from the concept: `form.js` with its own `shapes` and `seed`, `aurora.js` with
  `mode: "mist"` and `calm: "left"`, `contour.js` with more `levels` for a dense chart, with the
  place's own `outline` and `view: "tilt"`, `field.js` with `streak` for things on their way.
- **Only what the app knows.** A scene of a real place or object draws only what the app has: its
  outline, its route, its own numbers. No figures it does not have (no depths of a lake nobody
  measured, no soundings, no made-up heights), and a caption on the page that says what is drawn:
  "The lake's shape, from its outline. No measured depths." `contour.js` with an outline draws no
  marks for that reason.
- **Life in the content, never instead of it.** A live layer over something real that the screen
  already shows (a printed chart, a photo, a map, the app's numbers) puts the life into that thing:
  its depth bands breathe with the tide, a lamp lights the real chart, its own numbers rise. It
  never covers it with a generic pattern: contour lines laid over a printed sea chart, hiding its
  tints, figures and names, are wallpaper, not a chart. Check the screen with the scene live:
  everything it showed before is still there and still readable.
- **See-through, or framed.** A scene leaves the page's background showing through. A framed
  scene, a window onto a place with an edge of its own (a framed hero, a panel, a map card), may
  fill its frame with the tokens' colours: stage.js, "Rules for a scene".
- **The phone gets the scene or its own composition, never nothing.** `field.js` and `contour.js`
  take a `phone` option (where the form and the calm sit below 600 px wide); another scene gets a
  container of its own size and calm side on a phone. Check 390 wide with the page's real text
  over the scene: no line or particle runs through a figure, a headline or the lead.
- **Palette from the tokens.** The stage reads `--color-bg`, `--color-text`, `--color-text-muted`,
  `--color-accent`, `--color-accent-2`, `--color-surface` and `--color-border` on the container and
  follows the theme; never a colour in the options. Other names: the stage option
  `tokens: { accent: "--brand-500", accent2: "--brand-300" }`.
- **The poster**: a still of the tuned scene, one per theme and per shape (wide and phone), taken
  from the page itself with none of the page's chrome in it (section 5), each under 100 KB
  (`motion.md` section 9). It shows until the first frame, without WebGL and for reduced data.
- **setData from the app's data**: real numbers from a screen that already loads them, as 0..1
  (datascape takes them as they are). No private numbers on a public page; a new endpoint needs
  the user's yes first (`motion.md` section 10).

## 3. Install three, read its licence

Install three with the app's own package manager, as its lockfile says: `npm install three`,
`pnpm add three`, `yarn add three` or `bun add three` (the table in `motion.md` section 5; never a
second lockfile). `npm ls three` shows the version (`pnpm ls three`, `yarn why three`); the kit
needs r160 or newer. At look level 4 and 5 the level is the user's yes: no new question, never a
CDN. Read `node_modules/three/LICENSE` (MIT), write version and licence under `## Libraries` in
the report, run `python3 ../forge-check/deps.py .`. A page with no bundler serves its own copy of
`node_modules/three/build/three.module.js` and `three.core.js` (the first imports the second).

## 4. Copy the kit into the app

Copy the files (never link to them) into one `scenes/` folder of the app's scripts:
`resources/js/scenes/` (Laravel), `lib/scenes/` (Next; `src/lib/scenes/` when tsconfig.json maps
`@/*` to `./src/*`), `src/scenes/` (Vite), `static/js/scenes/` (Django). Keep the names: they
import each other as `./stage.js` and `./glsl.js`.

| the app uses | copy |
| --- | --- |
| `form.js`, `field.js`, `aurora.js`, `contour.js` or `datascape.js` | that scene, `stage.js`, `glsl.js`, `lazy.js` |
| `journey.js` | `journey.js`, the scene it directs, `stage.js`, `glsl.js`, `lazy.js` |
| its own scene (level 4, when no kit scene draws the concept's thing) or its own shader (level 5) | `stage.js`, `glsl.js`, `lazy.js` and its own scene file next to them |
| `depth.js` (level 3 and up, also next to a WebGL scene) | `depth.js` and `depth.css`: no three |

From the project root: `cp ../forge-design/scenes/stage.js resources/js/scenes/`, and so on for
each file. In TypeScript keep `allowJs` on (Next has it by default).

## 5. Mount it: lazyScene, a poster, one motionToggle

In every stack: a container with a size of its own and a poster child, `lazyScene()` with a
dynamic `import()` as loader (three is never in the first load), one `motionToggle()` per page.
```css
.hero-scene { position: relative; min-height: 80vh; }
.hero-scene [data-scene-poster] { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
@media (prefers-reduced-motion: reduce) { #motion { display: none; } }
```

**A plain page, with an import map.** The map is inline, so a strict CSP needs its hash in
`script-src`; it comes before every module script.
```html
<script type="importmap">{ "imports": { "three": "/vendor/three/three.module.js" } }</script>
<div class="hero-scene" aria-hidden="true"><img data-scene-poster src="/img/hero-poster.jpg" alt=""></div>
<button type="button" id="motion">Pause motion</button>
<script type="module" src="/js/hero.js"></script>
```
```js
// js/hero.js
import { lazyScene, motionToggle } from "./scenes/lazy.js";

const box = document.querySelector(".hero-scene");
const hero = lazyScene(box, () => import("./scenes/aurora.js"), { mode: "water", calm: "left", intensity: 0.8 });
motionToggle(document.querySelector("#motion"));
// depth while scrolling: where the hero is, read in the scene's own frames
hero.ready.then((scene) => scene && scene.stage.onFrame(() => scene.setProgress(scene.stage.progressOf(box))));
```
Never a scroll listener for it (`motion.md` section 3): in an app whose main area scrolls inside a
fixed frame no window scroll event fires and `scrollY` stays 0, while `progressOf` in the frame
loop (or `story()`, `motion.md` section 8) follows any scrolling container.

**Vite (laravel, static).** Install three (section 3) next to Vite's `package.json`. The page
carries the container and the button (in Blade: the HTML above without the import map, poster in
`public/img/`); the entry (`resources/js/app.js` or `src/main.ts`) loads the hero only on a page
that has one, `if (document.querySelector(".hero-scene")) import("./hero.js");`, and Vite splits
three off. Where pages change without a reload: in HTML the server renders (Livewire's
`wire:navigate`, Turbo), mount it through `startMotion`'s mounts instead (`motion.md` section 4):
they start a scene on each element that appears and stop it when it leaves; in a component
(Inertia's Vue, React or Svelte pages), from its own lifecycle (`motion.md` section 9, "Mounting
where pages change without a reload").
```js
// resources/js/hero.js or src/hero.js
import { lazyScene, motionToggle } from "./scenes/lazy.js";

const hero = lazyScene(document.querySelector(".hero-scene"), () => import("./scenes/contour.js"),
                       { calm: "left", levels: 18, lineWidth: 1.2 });
motionToggle(document.querySelector("#motion"));
fetch("/api/spots/depths").then((response) => response.json())
  .then((depths) => hero.setData(depths.map((d) => d / Math.max(...depths, 1))));
```

**One place from its own outline** (a lake, a trail, a plot): `contour.js` with the GeoJSON the app
already has, in 3D, and the place's name as real text the page moves over the canvas (an element
next to the container, not in it: the container is `aria-hidden`).
```js
// js/water.js: the water page's lake, from its outline
import { lazyScene } from "./scenes/lazy.js";

const name = document.querySelector(".water-name");
fetch("/api/waters/12/outline").then((response) => response.json()).then((outline) => {
  lazyScene(document.querySelector(".water-scene"), () => import("./scenes/contour.js"), {
    outline, view: "tilt", fill: "--color-water", calm: "none", labels: ["middle"],
    onLabels: ([at]) => { name.hidden = !at.visible; name.style.transform = `translate(${at.x}px, ${at.y}px)`; },
  });
});
```

**Next.js App Router.** A client component mounts in `useEffect` and destroys on unmount; the page
imports a wrapper with `dynamic(..., { ssr: false })`: no server rendering of the scene, the poster
still does. Effects run twice in development: `destroy()` then `lazyScene()` again is safe.
```jsx
"use client";
// components/HeroScene.jsx
import { useEffect, useRef } from "react";
import { lazyScene } from "@/lib/scenes/lazy.js";

export default function HeroScene({ values }) {
  const box = useRef(null);
  const scene = useRef(null);
  useEffect(() => {
    scene.current = lazyScene(box.current, () => import("@/lib/scenes/field.js"), { side: "right", formation: "wave" });
    return () => scene.current.destroy();
  }, []);
  useEffect(() => { if (values) scene.current?.setData(values); }, [values]);
  return <div ref={box} className="hero-scene" aria-hidden="true"><img data-scene-poster src="/hero-poster.jpg" alt="" /></div>;
}
```
```jsx
"use client";
// components/Hero.jsx: what the page imports; the loading poster is the same markup, rendered on the server
import dynamic from "next/dynamic";

const Poster = () => (
  <div className="hero-scene" aria-hidden="true"><img data-scene-poster src="/hero-poster.jpg" alt="" /></div>
);
export default dynamic(() => import("./HeroScene"), { ssr: false, loading: Poster });
```
```jsx
"use client";
// components/MotionButton.jsx: once, in app/layout.tsx
import { useEffect, useRef } from "react";
import { motionToggle } from "@/lib/scenes/lazy.js";

export default function MotionButton() {
  const button = useRef(null);
  useEffect(() => motionToggle(button.current).destroy, []);
  return <button type="button" id="motion" ref={button}>Pause motion</button>;
}
```
The `values` prop comes from the server component of a signed-in page that already has the rows.

**Django.** No bundler: a static module and an import map. Install three at the root (section 3) and
an npm script that copies three into `static/vendor/three/` (committed: the image needs no Node); the
kit in `static/js/scenes/`, `static/js/hero.js` as for a plain page, the map's hash in `SECURE_CSP`.
```json
{ "scripts": { "vendor:three": "node -e \"const fs=require('fs');fs.mkdirSync('static/vendor/three',{recursive:true});for(const f of ['build/three.module.js','build/three.core.js','LICENSE'])fs.copyFileSync('node_modules/three/'+f,'static/vendor/three/'+f.split('/').pop())\"" } }
```
```html
{% load static %}
<script type="importmap">{ "imports": { "three": "{% static 'vendor/three/three.module.js' %}" } }</script>
<div class="hero-scene" aria-hidden="true"><img data-scene-poster src="{% static 'img/hero-poster.jpg' %}" alt=""></div>
<button type="button" id="motion">Pause motion</button>
<script type="module" src="{% static 'js/hero.js' %}"></script>
```

**A poster per theme and shape.** One `<img data-scene-poster>` cannot follow a theme the visitor
picked, nor a phone layout. Give the container an empty `<div data-scene-poster></div>` (the stage
fades it as it would an image) and put the pictures in theme blocks of your own as CSS backgrounds:
the browser fetches only the one that shows.
```css
:root { --hero-poster: url(/img/hero-light-wide.jpg); --hero-poster-phone: url(/img/hero-light-phone.jpg); }
:root[data-theme="dark"] { --hero-poster: url(/img/hero-dark-wide.jpg); --hero-poster-phone: url(/img/hero-dark-phone.jpg); }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --hero-poster: url(/img/hero-dark-wide.jpg); --hero-poster-phone: url(/img/hero-dark-phone.jpg); }
}
.hero-scene [data-scene-poster] { position: absolute; inset: 0; background: center / cover no-repeat var(--hero-poster); }
@media (max-width: 600px) { .hero-scene [data-scene-poster] { background-image: var(--hero-poster-phone); } }
```
These are the selectors `theme.py` writes with `--default system`. Use the ones it wrote for the
app, in blocks of your own in the theme file after its end mark `/* forge theme end */`. Never put
them between its marks: its next run (after a token change or a rebrand) replaces all that is
there, and the poster goes blank. With `--default light` the media query holds
`:root[data-theme="system"]`; with `--default dark` it does too, and the block that is dark at any
time is `:root:not([data-theme="light"], [data-theme="system"])` in place of
`:root[data-theme="dark"]`, so a first visit with nothing stored gets the dark poster; with
`--dark-selector .dark` there is one `:root.dark` block and no media query.

Take each one from the page itself while the app runs: reduced motion (the stage draws its still),
the theme shown the way the app shows it (`## Theme` of `components.md`: an attribute or a class),
and the text over the scene, the header and nav (also one placed over the hero) and every fixed or
sticky element (a tab bar, a cookie bar, a floating button) hidden, so no poster holds page chrome;
anything else drawn over the scene joins `COPY`'s selector list. A scene lower on the page starts
only near the screen, so the script scrolls it into view first. Write the script next to the
shots, so it finds Playwright where `shots.mjs` does and stays out of the app's own files; the
pictures go next to the app's own images (`public/img/` here, `static/img/` in Django). Look at
each poster before it ships.
```js
// forge-work/design/poster.mjs: node forge-work/design/poster.mjs from the project root, while the app runs
import { chromium } from "@playwright/test";

const BASE = "http://127.0.0.1:3000/", SCENE = ".hero-scene", COPY = ".hero-copy";
// how this app shows a theme; with --dark-selector .dark:
// (theme) => document.documentElement.classList.toggle("dark", theme === "dark")
const show = (theme) => document.documentElement.setAttribute("data-theme", theme);
// the text over the scene, the header and nav, and every fixed or sticky element, never the scene or what holds it
const bare = ([scene, copy]) => {
  const keep = new Set();
  for (let el = document.querySelector(scene); el; el = el.parentElement) keep.add(el);
  for (const el of document.querySelectorAll("body *")) {
    const chrome = /^(fixed|sticky)$/.test(getComputedStyle(el).position) || el.matches("header, nav");
    if ((chrome && !keep.has(el)) || el.matches(copy)) el.style.setProperty("visibility", "hidden", "important");
  }
};

const browser = await chromium.launch();
for (const [shape, viewport] of [["wide", { width: 1440, height: 900 }], ["phone", { width: 390, height: 844 }]]) {
  for (const theme of ["light", "dark"]) {
    // a page behind a sign-in: add storageState with the state file of the shots
    const page = await browser.newPage({ viewport, reducedMotion: "reduce", colorScheme: theme });
    await page.goto(BASE);
    await page.evaluate(show, theme);
    await page.locator(SCENE).scrollIntoViewIfNeeded();   // a scene lower on the page starts only near the screen
    await page.waitForSelector(`${SCENE}[data-scene="live"]`, { timeout: 120000 });
    await page.evaluate(bare, [SCENE, COPY]);
    await page.waitForTimeout(500);
    await page.locator(SCENE).screenshot({ path: `public/img/hero-${theme}-${shape}.jpg`, type: "jpeg", quality: 80 });
    await page.close();
  }
}
await browser.close();
```
A page that shows the scene's picture but never mounts the scene (a sign-in page) gets a
transparent PNG instead: the same capture from a small page on 127.0.0.1 that holds only the
container, with `screenshot({ omitBackground: true })`.

## 6. The journey on a page (level 5)

A tall section, a sticky stage element for the canvas, one `[data-chapter]` per chapter over it.
The journey flies the camera through the keyframes, walks the scene's `setProgress` along and
fires a `chapter` event; the page lights the text. It directs `form.js`, `field.js`,
`datascape.js` or the app's own scene (section 2); here a sailing school's rope, which winds.
```html
<section class="journey" id="trip">
  <div data-journey-stage aria-hidden="true"><img data-scene-poster src="/img/trip-poster.jpg" alt=""></div>
  <article data-chapter><h2>A line, coiled on deck</h2><p>...</p></article>
  <article data-chapter><h2>One knot, tied in three moves</h2><p>...</p></article>
  <article data-chapter><h2>Made fast to the ring</h2><p>...</p></article>
</section>
```
```css
.journey [data-journey-stage] { position: sticky; top: 0; height: 100vh; margin-bottom: -100vh; overflow: hidden; }
.journey [data-scene-poster] { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.journey [data-chapter] { position: relative; min-height: 100vh; display: grid; align-content: center; max-width: 34rem; }
.journey[data-journey="live"] [data-chapter]:not([data-current]) { opacity: 0.35; }
.journey[data-journey="still"] [data-chapter] { min-height: auto; grid-template-columns: 1fr 1fr; gap: 2rem; max-width: none; }
.journey-still img { width: 100%; height: auto; }
```
```js
import { lazyScene } from "./scenes/lazy.js";

const section = document.querySelector("#trip");
const chapters = [...section.querySelectorAll("[data-chapter]")];
const trip = lazyScene(section, async () => {
  const [journey, form] = await Promise.all([import("./scenes/journey.js"), import("./scenes/form.js")]);
  return { mount: (el, options) => journey.mount(el, { ...options,
    scene: (stageEl) => form.mount(stageEl, { side: "centre", shapes: ["coil", "knot", "ring"], progressEase: 0.05 }) }) };
}, {
  chapters: [
    { camera: { position: [-1, 0.5, 9], target: [-2, 0, 0], fov: 32 }, progress: 0, alt: "The coiled line" },
    { camera: { position: [2, -1, 5], target: [0.5, 0, 0] }, progress: 0.5, phone: { position: [0, -1, 8] } },
    { camera: { position: [0, 8, 6], target: [0, 0, 0], roll: 5 }, progress: 1 },
  ],
  inertia: 0.65,
  dwell: 0.3,
});
section.addEventListener("chapter", (event) => {
  chapters.forEach((el, i) => el.toggleAttribute("data-current", i === event.detail.index));
});
// a table of contents: goTo(index) scrolls to a chapter
document.querySelector("#to-ring").addEventListener("click", () => trip.ready.then((live) => live && live.goTo(2)));
```

The section gets `data-journey="live"`, `"still"` or `"fallback"`. **Reduced motion shows
stills**: no pin, no trip; each chapter gets a still of its keyframe in a `<figure
class="journey-still">` (or its own `[data-chapter-still]`), beside the text. Do not hide the stage
element: it draws them. No WebGL: the poster stays under the chapters. The chapters come from the
direction; one WebGL scene per page, so a page with a journey makes it its hero.

## 7. depth.js: real depth from level 3

No WebGL, no three, about 5 KB minified and gzipped (12 KB minified), driven by attributes in the app's own markup: `data-depth-layer="1|2|3"`
lifts a child (negative lies behind); `data-depth-<option>` on one element overrides an option.
```html
<link rel="stylesheet" href="/js/scenes/depth.css">
<ul class="spots">
  <li class="card" data-depth="tilt">
    <img data-depth-layer="1" src="/img/north-bank.jpg" alt="The north bank at dawn">
    <h3 data-depth-layer="2">North bank</h3>
  </li>
  <li class="card" data-depth="tilt" data-depth-rest="0.6">...</li>
</ul>
<div class="plans" data-depth="stack"><section>Free</section><section>Club</section><section>Pro</section></div>
<article data-depth="fold" data-depth-axis="left">...</article>
<header data-depth="scene">
  <div class="hills" data-depth-layer="-1"></div>
  <h1 data-depth-layer="1">The lake, mapped</h1>
</header>
```
```js
import { mount } from "./scenes/depth.js";

const depth = mount(document.querySelector("main"), { tilt: 7, stackGap: 56, fold: 72 });
// tilt 7: level 3 asks a lean of 6 degrees or more at a card's edge (levels.md); the default is 5
// after adding new [data-depth] elements: depth.destroy(), then mount() again
```

`tilt` leans a card to the pointer (on touch, gently with the scroll), `stack` steps its panels
forward as it scrolls in, `fold` opens like a page, `scene` moves its layers with pointer and scroll.
Any scroll moves them, also one inside a main area that scrolls in a fixed frame. React:
`mount(ref.current)` in a `useEffect` that returns its `destroy`. No overflow, opacity or filter on
a tilt card (it flattens the layers). Reduced motion or the toggle: flat and still, with nothing
taken away: cards lie flat, folds stay open, a stack shows its cascade as a flat picture.

## 8. The budget, and what the stage already does

| level | first load | loaded later | frames |
| --- | --- | --- | --- |
| 3 | depth.js and depth.css, about 5 KB plus 1 KB minified and gzipped, inside the 25 KB of all motion code | nothing | 60 a second, also while a stack scrolls |
| 4 | nothing of three | three after tree-shaking, the kit and one scene under 200 KB, only on the screens with it, after the page is idle; a poster under 100 KB | 60 on a mid-range laptop, 30 or more on a mid-range phone at low quality |
| 5 | the same as level 4 | scenes, journey and shaders together under 300 KB; one WebGL context per page | the same, also during the journey |

Measure on a build in a copy (`motion.md` section 11). **The start** comes in steps, each a task
of its own: three and the scene arrive and are evaluated, a quiet moment, `mount()` builds the
renderer and the geometry, the stage compiles the shaders, then the first frame. Measure it after
the scene is live: the longest task from the page load until `data-scene="live"`, and for a few
seconds after. Each step should stay near the 50 ms budget on a mid-range laptop with a graphics
chip; three's own evaluation is one task that cannot be split: report it apart. Without a graphics
chip (a headless browser, where `WEBGL_debug_renderer_info` names SwiftShader) every frame is
itself a long task: report the renderer with the numbers and compare before with after.
```js
// in a Playwright check of a production build: the long tasks until the scene is live, and after
await page.addInitScript(() => {
  window.longTasks = [];
  new PerformanceObserver((list) => window.longTasks.push(...list.getEntries().map((task) => Math.round(task.duration))))
    .observe({ type: "longtask", buffered: true });
});
await page.goto("http://127.0.0.1:3000/");
await page.waitForSelector('[data-scene="live"]', { timeout: 120000 });
const untilLive = await page.evaluate(() => { window.liveAt = window.longTasks.length; return Math.max(0, ...window.longTasks); });
await page.waitForTimeout(3000);
const afterLive = await page.evaluate(() => Math.max(0, ...window.longTasks.slice(window.liveAt)));
```
`clicks.mjs` of `motion.md` section 12 reports the same: `startupLongestTaskMs` until the scene is
live (at full speed, as above), and `longestTaskMs` for three seconds after it with the processor
slowed four times (a mid-range phone: `motion.md` section 11's budget).

What the stage already does, so the page does not:
- **Pause**: off screen and in a hidden tab, resuming cleanly; `motionToggle` pauses every
  `lazyScene` scene (and depth.js) and remembers the choice.
- **Reduced motion**: no loop; one still, composed frame, redrawn after a resize or a theme change.
- **Quality**: `auto` starts from the device (cores, memory, a coarse pointer) and steps down when
  frames take too long; the pixel ratio is capped (2, 1.5 on a phone). `quality: "low"` forces it.
- **Fallback**: no WebGL, a lost context or a frame that throws: `data-scene="fallback"` on the
  container, the poster stays. `lazyScene` keeps it when the loader fails, and for reduced data;
  without WebGL 2 it never fetches three at all.
- **The motion switch and the runtime**: `motionToggle` sets `data-motion="paused"` on `<html>`
  and, when motion comes back, `"on"`; it never removes the attribute, so the reveals of
  `motion.md`'s runtime (hidden only under `html[data-motion]`) keep working on a page with a scene.
- **Clean-up**: `destroy()` frees every geometry, material, texture, listener and observer.

Left to the page: a container with a size, a poster that matches the still, text readable over
the scene in light and dark, `destroy()` when the component goes away.
