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
| `../forge-design/scenes/glsl.js` | shader pieces as strings (noise, curl, fbm, palette, grain, fog, lines); the scenes use it, and so does the app's own shader at level 5 | 4 |
| `../forge-design/scenes/lazy.js` | `lazyScene()`: loads three and a scene only near the viewport and when the page is idle, poster until then; `motionToggle()`: one pause button for every scene | 4 |
| `../forge-design/scenes/form.js` | a sculptural form of glowing strands (knot family) that breathes, turns and leans to the pointer | 4 |
| `../forge-design/scenes/field.js` | tens of thousands of GPU particles in a slow current, formations cloud, ring, wave, grid | 4 |
| `../forge-design/scenes/aurora.js` | a shader atmosphere behind a hero or a whole page, modes `aurora`, `water`, `mist` | 4 |
| `../forge-design/scenes/contour.js` | living contour lines of a moving height field: a map, a depth chart | 4 |
| `../forge-design/scenes/datascape.js` | the app's own numbers as 3D bars or ridgelines, with hover | 5 (dashboard 5) |
| `../forge-design/scenes/journey.js` | the level-5 director: a scroll trip with a camera through chapters | 5 Cinematic |

## 2. Which scene for which concept

Start from the app's own world (its material, tool, place, ritual), never from the list. Then:

| the concept is about | scene | for example |
| --- | --- | --- |
| an object, a tool, a craft | `form.js` | a knot of rope for a sailing school, a coil for a workshop |
| a crowd, a flow, numbers, wind | `field.js` | visitors arriving, a flock, a weather app's wind |
| light, sky, water, weather | `aurora.js` (mode `water` for water, `mist` for weather) | an angling app's lake, a planetarium's sky |
| places, depth, height, maps | `contour.js` | a hiking app, a lake's depth chart, a pressure map |
| the app's own numbers | `datascape.js` | bookings by hour and month, catches per spot |
| real depth in the interface (level 3 and up) | `depth.js` + `depth.css` | cards that tilt, plans stacked as screens, a hero in layers |
| the level-5 trip through one scene | `journey.js` with one of the scenes above | the lake from far, then close, then under the surface |

**Make it belong to one app.** A kit scene on its defaults is a failed hero.
- **Options** (the comment at the top of each scene): shape, the calm side for the text, scale,
  speed, intensity, from the concept: `form.js` with its own `shapes` and `seed`, `aurora.js` with
  `mode: "water"` and `calm: "left"`, `contour.js` with more `levels` for a dense chart.
- **Palette from the tokens.** The stage reads `--color-bg`, `--color-text`, `--color-text-muted`,
  `--color-accent`, `--color-accent-2`, `--color-surface` and `--color-border` on the container and
  follows the theme; never a colour in the options. Other names: the stage option
  `tokens: { accent: "--brand-500", accent2: "--brand-300" }`.
- **The poster**: a still of the tuned scene. Mount with `still: true` at the hero's size, take a
  Playwright screenshot of the container (PNG, or JPEG at quality 80), under 100 KB (`motion.md`
  section 9). It shows until the first frame, without WebGL and for reduced data.
- **setData from the app's data**: real numbers from a screen that already loads them, as 0..1
  (datascape takes them as they are). No private numbers on a public page; a new endpoint needs
  the user's yes first (`motion.md` section 10).

## 3. Install three, read its licence

`npm install three` in the app (`npm ls three` shows the version; the kit needs r160 or newer).
At look level 4 and 5 the level is the user's yes: no new question, never a CDN. Read
`node_modules/three/LICENSE` (MIT), write version and licence under `## Libraries` in the report,
run `python3 ../forge-check/deps.py .`. A page with no bundler serves its own copy of
`node_modules/three/build/three.module.js` and `three.core.js` (the first imports the second).

## 4. Copy the kit into the app

Copy the files (never link to them) into one `scenes/` folder of the app's scripts:
`resources/js/scenes/` (Laravel), `lib/scenes/` (Next), `src/scenes/` (Vite), `static/js/scenes/`
(Django). Keep the names: they import each other as `./stage.js` and `./glsl.js`.

| the app uses | copy |
| --- | --- |
| `form.js`, `field.js`, `aurora.js`, `contour.js` or `datascape.js` | that scene, `stage.js`, `glsl.js`, `lazy.js` |
| `journey.js` | `journey.js`, the scene it directs, `stage.js`, `glsl.js`, `lazy.js` |
| its own shader at level 5 | `stage.js`, `glsl.js`, `lazy.js` and its own scene file next to them |
| `depth.js` | `depth.js` and `depth.css` only: no three |

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
addEventListener("scroll", () => hero.setProgress(Math.min(scrollY / innerHeight, 1)), { passive: true });
```

**Vite (laravel, static).** `npm install three` next to Vite's `package.json`. The page carries the
container and the button (in Blade: the HTML above without the import map, poster in `public/img/`);
the entry (`resources/js/app.js` or `src/main.ts`) loads the hero only on a page that has one,
`if (document.querySelector(".hero-scene")) import("./hero.js");`, and Vite splits three off.
```js
// resources/js/hero.js or src/hero.js
import { lazyScene, motionToggle } from "./scenes/lazy.js";

const hero = lazyScene(document.querySelector(".hero-scene"), () => import("./scenes/contour.js"),
                       { calm: "left", levels: 18, lineWidth: 1.2 });
motionToggle(document.querySelector("#motion"));
fetch("/api/spots/depths").then((response) => response.json())
  .then((depths) => hero.setData(depths.map((d) => d / Math.max(...depths, 1))));
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

**Django.** No bundler: a static module and an import map. `npm install three` at the root and an
npm script that copies three into `static/vendor/three/` (committed: the image needs no Node); the
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

## 6. The journey on a page (level 5)

A tall section, a sticky stage element for the canvas, one `[data-chapter]` per chapter over it.
The journey flies the camera through the keyframes, walks the scene's `setProgress` along and
fires a `chapter` event; the page lights the text.
```html
<section class="journey" id="trip">
  <div data-journey-stage aria-hidden="true"><img data-scene-poster src="/img/trip-poster.jpg" alt=""></div>
  <article data-chapter><h2>The lake at dawn</h2><p>...</p></article>
  <article data-chapter><h2>Where the fish were</h2><p>...</p></article>
  <article data-chapter><h2>Your best spot</h2><p>...</p></article>
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
    scene: (stageEl) => form.mount(stageEl, { side: "centre", shapes: ["ring", "knot", "coil"], progressEase: 0.05 }) }) };
}, {
  chapters: [
    { camera: { position: [-1, 0.5, 9], target: [-2, 0, 0], fov: 32 }, progress: 0, alt: "The whole lake" },
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
document.querySelector("#to-spot").addEventListener("click", () => trip.ready.then((live) => live && live.goTo(2)));
```

The section gets `data-journey="live"`, `"still"` or `"fallback"`. **Reduced motion shows
stills**: no pin, no trip; each chapter gets a still of its keyframe in a `<figure
class="journey-still">` (or its own `[data-chapter-still]`), beside the text. Do not hide the stage
element: it draws them. No WebGL: the poster stays under the chapters. The chapters come from the
direction; one WebGL scene per page, so a page with a journey makes it its hero.

## 7. depth.js: real depth from level 3

No WebGL, no three, about 6 KB, driven by attributes in the app's own markup: `data-depth-layer="1|2|3"`
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

const depth = mount(document.querySelector("main"), { tilt: 5, stackGap: 56, fold: 72 });
// after adding new [data-depth] elements: depth.destroy(), then mount() again
```

`tilt` leans a card to the pointer (on touch, gently with the scroll), `stack` steps its panels
forward as it scrolls in, `fold` opens like a page, `scene` moves its layers with pointer and scroll.
React: `mount(ref.current)` in a `useEffect` that returns its `destroy`. No overflow, opacity or
filter on a tilt card (it flattens the layers). Reduced motion or the toggle: flat and still.

## 8. The budget, and what the stage already does

| level | first load | loaded later | frames |
| --- | --- | --- | --- |
| 3 | depth.js and depth.css, about 6 KB plus the CSS, inside the 25 KB of all motion code | nothing | 60 a second, also while a stack scrolls |
| 4 | nothing of three | three after tree-shaking, the kit and one scene under 200 KB, only on the screens with it, after the page is idle; a poster under 100 KB | 60 on a mid-range laptop, 30 or more on a mid-range phone at low quality |
| 5 | the same as level 4 | scenes, journey and shaders together under 300 KB; one WebGL context per page | the same, also during the journey |

Measure on a build in a copy (`motion.md` section 11). What the stage already does, so the page
does not:
- **Pause**: off screen and in a hidden tab, resuming cleanly; `motionToggle` pauses every
  `lazyScene` scene (and depth.js) and remembers the choice.
- **Reduced motion**: no loop; one still, composed frame, redrawn after a resize or a theme change.
- **Quality**: `auto` starts from the device (cores, memory, a coarse pointer) and steps down when
  frames take too long; the pixel ratio is capped (2, 1.5 on a phone). `quality: "low"` forces it.
- **Fallback**: no WebGL, a lost context or a frame that throws: `data-scene="fallback"` on the
  container, the poster stays. `lazyScene` keeps it when the loader fails, and for reduced data.
- **Clean-up**: `destroy()` frees every geometry, material, texture, listener and observer.

Left to the page: a container with a size, a poster that matches the still, text readable over
the scene in light and dark, `destroy()` when the component goes away.
