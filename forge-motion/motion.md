# Motion reference

The numbers, the recipes and the library table for forge-motion. The CSS of the recipes is ready in
`../forge-motion/motion.css`; the hero example is `../forge-motion/wireform.example.js`.

## 1. Principles

Motion has one of four jobs. If a moment has none of them, it gets no motion.

| job | what it tells the user | examples |
| --- | --- | --- |
| state change | "this is now open, selected, saved" | accordion, tab underline, toggle |
| feedback | "your click arrived" | button press, toast, form error shake of 4px |
| orientation | "this came from there, you are now here" | modal, sheet, page transition, scroll reveal |
| delight | "this product is cared for" | hero visual, count-up, chart draw-on: a few per app |

- **The user never waits for an animation.** Clicks work during it, and it can be cut short.
- **One thing moves at a time** per area. A list may stagger; a whole screen may not dance.
- **Enter is slower than exit.** Things arrive in `base` or `slow` and leave in `fast`.
- **Small things move fast, big things slower**, and nothing in the interface takes over 500ms.
- **Travel is a hint, not a journey**: 4 to 24px. Slide a full width only for sheets and drawers.
- **Only `transform` and `opacity` animate.** They run on the compositor (off the main thread), so
  they stay smooth while JavaScript works. Width, height, top, left, margin and padding make the
  browser lay the page out again on every frame.

### Durations

| what changes | time | token |
| --- | --- | --- |
| hover, press, toggle, focus ring offset, colour | 80 to 150ms | `--duration-fast` |
| tooltip, dropdown, tab underline, fade, anything leaving | 150 to 220ms | `--duration-base` |
| modal, toast, accordion, card that expands, scroll reveal | 220 to 350ms | `--duration-slow` |
| sheet, full-screen panel, chart drawing itself, count-up | 350 to 500ms | `--duration-slower` |

By distance: under 100px `base`, 100 to 500px `slow`, more or full screen `slower`. Under 80ms
nobody sees it; above 1s the app feels slow. Loops (skeleton sheen, marquee) are the only longer ones.

### Easing

| token | curve | use it for |
| --- | --- | --- |
| `--ease-standard` | `cubic-bezier(.2,.8,.2,1)`: fast start, soft landing | things that enter or answer the user: nearly everything |
| `--ease-exit` | `cubic-bezier(.4,0,1,1)`: slow start, fast end | things that leave the screen for good |
| `--ease-move` | `cubic-bezier(.4,0,.2,1)`: soft both ends | things that move between two places on screen; loops |
| `--ease-spring` | `cubic-bezier(.34,1.56,.64,1)`: overshoots a little | small delight only: a toggle thumb, a like, a badge |
| `linear` | | scroll-driven animations, spinners, a marquee, opacity-only fades |

Never `--ease-spring` on anything larger than a button, and never the browser's default `ease` by
accident: name the curve.

### Stagger

`--duration-stagger` (20 to 50ms) between items, at most 8 steps, so the last item starts within
about 300ms. Later items arrive together with the eighth. Stagger on first appearance only, never
when data refreshes.

## 2. The motion tokens

Add these to `forge-work/design/tokens.json`, next to what forge-design wrote there (`fast`, `base`
and `ease` stay as they are), then run the theme.py command in `forge-work/design/components.md`.
`../forge-design/theme.py` turns every key of `motion` into `--duration-<key>`, except `ease`
(`--ease-standard`) and keys that start with `ease-` (`--<key>`). Distances are lengths, so they
live in `size` and become `--size-<key>` in px.

```json
{
  "motion": {
    "slow": "320ms",
    "slower": "480ms",
    "stagger": "40ms",
    "pulse": "1600ms",
    "loop": "24s",
    "ease-exit": "cubic-bezier(.4,0,1,1)",
    "ease-move": "cubic-bezier(.4,0,.2,1)",
    "ease-spring": "cubic-bezier(.34,1.56,.64,1)"
  },
  "size": {
    "shift-sm": 4,
    "shift": 12,
    "shift-lg": 24
  }
}
```

`pulse` is one pass of the skeleton sheen, `loop` one round of a marquee. The three directions are
the same tokens with other values:

| token | calm | lively | technical-HUD |
| --- | --- | --- | --- |
| fast / base / slow / slower | 120 / 200 / 320 / 480ms | 100 / 180 / 280 / 420ms | 80 / 140 / 240 / 400ms |
| ease (standard) | `cubic-bezier(.2,.8,.2,1)` | the same | `cubic-bezier(.2,0,0,1)`: sharper |
| stagger | 30ms | 40ms | 25ms |
| shift-sm / shift / shift-lg | 4 / 8 / 16 | 4 / 12 / 24 | 2 / 8 / 16 |
| character | fades and small rises, no loops, no spring | spring on small controls, staggered lists, count-ups | thin lines that draw themselves, numbers that tick in a mono font, a slow wireframe hero; nothing bounces |

Reading a token in JavaScript, so scripts hold no numbers either:

```js
// tokens.js
const root = getComputedStyle(document.documentElement);
export const token = (name) => root.getPropertyValue(name).trim();
export const ms = (name) => {
  const value = token(name);                       // "320ms" or ".32s"
  return value.endsWith("ms") ? parseFloat(value) : parseFloat(value) * 1000;
};
export const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
```

## 3. The layers

Use the first layer that can do the job.

1. **CSS transitions and keyframes**: every state change and all feedback. `@starting-style` gives
   an element an entry transition without JavaScript.
2. **View Transitions**: page to page (`@view-transition`), or one DOM change
   (`document.startViewTransition`). Browsers without it change the page at once: no fallback code.
3. **Scroll**: `IntersectionObserver` adds a class once (works everywhere). `animation-timeline:
   view()` ties progress to the scroll position; put it in `@supports`, the element just stands
   still elsewhere. Never a `scroll` event listener.
4. **Web Animations API** (`element.animate()`): sequences, and values only known at run time. It
   returns an object with `.finished` (a promise), `.cancel()` and `.playbackRate`.
5. **A library**: section 5.

The app's CSP (forge-pack's nginx.conf, Django's CSP middleware, next.config) blocks inline styles
in markup. Scripts may still set them: `element.style.setProperty("--m-tab-x", "40px")` and
`element.animate()` are allowed, a `style="..."` attribute in a template is not.

## 4. Recipes

Each: the markup or script, what people who asked for reduced motion get, and the usual mistake.
The classes are in motion.css. Scripts import `token`, `ms` and `reduce` from tokens.js above.

One script switches the scroll recipes on and pauses loops nobody can see:

```js
// motion.js: load it as a module on every page
document.documentElement.dataset.motion = "on";   // from here on, .m-reveal starts hidden

const seen = new IntersectionObserver((entries) => {
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    entry.target.classList.add("is-visible");
    seen.unobserve(entry.target);                 // once: scrolling back up does not replay it
  }
}, { rootMargin: "0px 0px -10% 0px", threshold: 0.1 });
document.querySelectorAll(".m-reveal, .m-draw, .m-grow").forEach((el) => seen.observe(el));

const visible = new IntersectionObserver((entries) => {
  for (const entry of entries) {
    if (entry.target.dataset.userPaused === "true") continue;   // the user's pause button wins
    entry.target.dataset.paused = String(!entry.isIntersecting);
  }
});
document.querySelectorAll(".m-marquee, .m-skeleton").forEach((el) => visible.observe(el));
```

**Button press.** `<button class="m-press">`. Reduced: no scale; the colour change of the active
state stays. Mistake: a delay before the feedback, or `transition: all`, which also animates the
focus ring and layout.

**Hover lift.** `<a class="card m-lift">`. The shadow is a layer whose opacity changes. Reduced: the
shadow fades in, nothing moves. Mistake: animating `box-shadow` or `top`, and no `@media (hover:
hover)`, so the card stays lifted after a tap on a phone.

**Focus ring.** `class="m-ring"`. It appears at once; only its offset settles. Reduced: no settle.
Mistake: `outline: none` plus a ring that fades in over 300ms: keyboard users lose their place.

**Skeleton to content.** `<div class="m-skeleton" aria-hidden="true">` with the size of what will
come, inside a region with `aria-busy="true"`; swap in the content with `class="m-enter"`.
Reduced: a still grey block, content fades in. Mistake: a skeleton for a 50ms wait (it flashes:
show it only after 200ms), or one of another size, so the page jumps.

**List stagger.** `<ul class="m-stagger">`. Reduced: all rows fade in together. Mistake: staggering
50 rows (seconds of waiting), and replaying it on every refresh or re-render.

**Accordion.** The button carries the state; the panel is `m-accordion` with one child.

```html
<button aria-expanded="false" aria-controls="faq-1">Can I cancel?</button>
<div class="m-accordion" id="faq-1" data-open="false"><div><p>Yes, at any time.</p></div></div>
```
```js
button.addEventListener("click", () => {
  const open = button.getAttribute("aria-expanded") !== "true";
  button.setAttribute("aria-expanded", String(open));
  panel.dataset.open = String(open);
});
```

Reduced: the same; `grid-template-rows` is a size change without travel, and it is short. If the
user finds it too much, set its transition to none in the reduce block. Mistake: animating
`height` to `auto` (it cannot) or `max-height: 9999px` (the timing is wrong), and closed content
that still takes Tab focus (the recipe hides it with `visibility`).

**Toast.** The region exists from page load, or screen readers do not announce what lands in it.

```html
<div id="toasts" role="status" aria-live="polite"></div>
```
```js
export function toast(text, region = document.getElementById("toasts")) {
  const el = document.createElement("div");
  el.className = "toast m-enter";
  el.textContent = text;
  region.append(el);
  setTimeout(() => {
    el.classList.replace("m-enter", "m-leave");
    el.addEventListener("animationend", () => el.remove(), { once: true });
  }, 6000);
}
```

Reduced: fades in and out, no rise. Mistake: the only copy of an error in a toast that disappears,
and less than 5 seconds to read it.

**Modal and sheet.** A native `<dialog class="m-modal">` (or `m-sheet`), opened with
`dialog.showModal()` and closed with `dialog.close()`. The browser traps focus, closes on Escape
and gives focus back to the button that opened it. Reduced: fade only. Mistake: a `div` overlay
that leaves focus behind it, and an exit that never shows because `display: none` applies at once
(the recipe's `allow-discrete` lines fix that where the browser has them).

**Tab underline.** One line for the whole tab list.

```html
<div class="m-tabs" role="tablist"> ...tabs... <span class="m-tabs__line" aria-hidden="true"></span></div>
```
```js
export function moveLine(tabs) {
  const line = tabs.querySelector(".m-tabs__line");
  const tab = tabs.querySelector('[aria-selected="true"]');
  line.style.setProperty("--m-tab-x", tab.offsetLeft + "px");
  line.style.setProperty("--m-tab-scale", String(tab.offsetWidth / tabs.offsetWidth));
}
new ResizeObserver(() => moveLine(tabs)).observe(tabs);   // also call it when the selection changes
```

Reduced: the line jumps to the new tab. Mistake: animating `left` and `width`, or a line per tab
that fades, which loses the "it moved there" message.

**Page transition.** Between pages of one site, motion.css turns on a short cross-fade
(`@view-transition { navigation: auto; }`); both pages must load that CSS. For one DOM change:

```js
export function swap(update) {
  if (!document.startViewTransition || reduce.matches) return update();
  return document.startViewTransition(update).finished;
}
```

To carry one element across, give it the same `view-transition-name` on both pages, and that name
to nothing else. After a client-side page change, move focus to the new page's `<h1 tabindex="-1">`.
Reduced: none. Mistake: the same `view-transition-name` twice on a page (the whole transition is
skipped), a transition over 300ms on every navigation, and focus left on a link that is gone.
Frameworks wrap this API (React, Next, Livewire's navigate): read the docs of the installed version.

**Scroll reveal, IntersectionObserver.** `class="m-reveal"` plus motion.js above. Reduced: a fade
without the rise. Mistake: hiding content in CSS with no script running (blank page: the recipe
hides only after motion.js set `data-motion`), revealing things above the fold, and a threshold of
0.5 on a block taller than the screen, which then never shows.

**Scroll reveal, animation-timeline.** `class="m-reveal-scroll"`: no script, progress follows the
scrollbar. Reduced, and in browsers without it: the element is simply there. Mistake: writing
`animation-timeline` before the `animation` shorthand (the shorthand resets it), and no `@supports`.

**Number count-up.** The real number is in the HTML for screen readers and for no-script; the
visible copy counts (`sr-only`: the app's class that hides text from the eye only).

```html
<span class="sr-only">1,280 bookings</span>
<span class="m-count" aria-hidden="true" data-value="1280">1,280</span>
```
```js
export function countUp(el) {
  const target = Number(el.dataset.value);
  const format = new Intl.NumberFormat(document.documentElement.lang || undefined);
  const duration = ms("--duration-slower") * 1.5;
  let start;
  const step = (now) => {
    start ??= now;
    const progress = Math.min((now - start) / duration, 1);
    el.textContent = format.format(Math.round(target * (1 - (1 - progress) ** 3)));   // soft landing
    if (progress < 1) requestAnimationFrame(step);
  };
  const seen = new IntersectionObserver(([entry]) => {
    if (!entry.isIntersecting) return;
    seen.disconnect();
    if (!reduce.matches) requestAnimationFrame(step);   // reduced: the number already stands there
  });
  seen.observe(el);
}
```

Reduced: the final number, at once. Mistake: digits that jiggle (no `tabular-nums`), counting for
seconds, counting before it is on screen, and a live region that reads out every step.

**Chart draw-on.** `<path class="m-draw" pathLength="1" ...>` for a line, `class="m-grow"` with
`--m-index` set per bar for bars, plus motion.js. `pathLength="1"` makes the dash maths the same
for every line, so no script measures anything. Reduced: the finished chart. Mistake: the values
only in the animation (keep a table or labels), measuring each path with `getTotalLength()`, and
drawing longer than 800ms.

**Parallax, done safely.** `class="m-parallax"` on a decorative layer: it drifts 24px against the
scroll, in CSS, only where `animation-timeline` exists. Reduced: nothing. Mistake: a `scroll`
listener that sets `top` or `background-position`, parallax on text, and large distances: this is
the effect that most often makes people feel sick.

**Marquee that pauses.** Items twice in the track (the copy `aria-hidden="true"`), and a real
pause button, because hover does not exist on a phone or a keyboard:

```html
<div class="m-marquee" id="logos"><div class="m-marquee__track"> ...items... ...copy... </div></div>
<button type="button" aria-pressed="false" aria-controls="logos">Pause</button>
```
```js
pause.addEventListener("click", () => {
  const paused = pause.getAttribute("aria-pressed") !== "true";
  pause.setAttribute("aria-pressed", String(paused));
  marquee.dataset.userPaused = String(paused);
  marquee.dataset.paused = String(paused);
});
```

motion.js leaves an element with `data-user-paused="true"` alone, so the user's pause holds.
Reduced: it stands still and scrolls sideways by hand. Mistake: no way to stop it (anything that
moves by itself for more than 5 seconds needs one: WCAG 2.2.2), and text people must read in it.

**Cursor glow.** `class="m-glow"` on a card, pointer devices only.

```js
document.querySelectorAll(".m-glow").forEach((el) => {
  el.addEventListener("pointermove", (event) => {
    const box = el.getBoundingClientRect();
    el.style.setProperty("--m-glow-x", event.clientX - box.left + "px");
    el.style.setProperty("--m-glow-y", event.clientY - box.top + "px");
  }, { passive: true });
});
```

Reduced: the same (it only follows the user's own hand); drop it if the app's users ask. Mistake: a
page-wide element chasing the cursor through `top` and `left`, or a custom cursor that replaces
the system one.

**A sequence with the Web Animations API.**

```js
export async function celebrate(badge) {
  if (reduce.matches) return;
  await badge.animate(
    [{ transform: "scale(.8)", opacity: 0 }, { transform: "none", opacity: 1 }],
    { duration: ms("--duration-slow"), easing: token("--ease-spring") },
  ).finished;
  badge.animate([{ opacity: 1 }, { opacity: 0.6 }, { opacity: 1 }], { duration: ms("--duration-slower") });
}
```

Reduced: nothing; the badge is already in its end state, because the end state is the CSS and the
animation only leads up to it. Mistake: `fill: "forwards"` to hold an end state (the element is
then stuck with it), and no reduced-motion check, because CSS media queries do not reach scripts.

## 5. Libraries

CSS and the Web Animations API first. A library is justified only by a row of this table, and each
one goes into `## Libraries` of `forge-work/motion.md` with the reason.

| library | take it when | do not take it for | size, measured 10 Nov 2026 (min / gzip) | licence: verify |
| --- | --- | --- | --- | --- |
| GSAP 3.15 (`gsap`) | a timeline of 5+ steps that must be scrubbed, reversed or tied to scroll with pinning; morphing or drawing complex SVG | fades, reveals, one-off sequences | core 73 / 28 KB, ScrollTrigger 45 / 18 KB | not open source: package.json names "Standard 'no charge' license" with a link and ships no licence file. Read the linked page and tell the user its conditions |
| Three.js 0.187 (`three`) | real 3D: lighting, filled faces, thousands of lines, post-processing, a model file | a wireframe of a few thousand lines: adapt wireform.example.js | a small scene after tree-shaking: about 540 / 134 KB | MIT, in `LICENSE` |
| lottie-web 5.13 (`lottie-web`) | an animation a designer exported from After Effects, owned by the user | anything you could write in CSS; files from a stock site without a licence for this use | `lottie_light` (SVG only) 168 / 46 KB; full 306 / 76 KB | MIT, in `LICENSE.md`. The animation file has its own licence: ask the user where it came from |
| Motion 14 (`motion`) | a React app (next) that needs layout or gesture animation | plain enter and exit: CSS does it | import only what is used; the whole package is 189 / 63 KB | MIT |

Versions, sizes and licences change. For the version you install: `npm view <package> license`,
then read the licence file in `node_modules/<package>/` (and the page it links to when there is
none). Write into motion.md what you read, not what this table says. A licence that is not a
standard open one (GSAP's) is the user's decision: show them the conditions and wait.

Rules for every library:

- **Local and bundled.** `npm install <package>`, imported from the app's own code. Never a
  `<script src="https://...">`, an `import` from a URL, an import map to a CDN, or a hosted player:
  a CDN sees every visitor's IP address, and a file changed there runs in the app. Lottie files and
  models live in the repo.
- **Lazy.** Never in the first bundle. Load it when its element comes near the screen:

```js
const hero = document.querySelector("[data-hero]");
if (hero) {
  const near = new IntersectionObserver(async ([entry]) => {
    if (!entry.isIntersecting) return;
    near.disconnect();
    const { start } = await import("./hero.js");   // hero.js imports three or gsap
    start(hero);
  }, { rootMargin: "200px" });
  near.observe(hero);
}
```

- **Reduced motion in the script.** Check `reduce.matches` before anything runs, and listen for
  `change`. GSAP has `gsap.matchMedia()` for this. Show the end state or one still frame.
- **Paused when unseen.** Stop the render loop off-screen and on `visibilitychange` (three:
  `renderer.setAnimationLoop(null)`; GSAP: `timeline.pause()`; Lottie: `animation.pause()`).
- **Fits the CSP.** The full lottie-web build runs expressions through `eval`, which the app's CSP
  blocks, rightly: use `lottie-web/build/player/lottie_light` (no expressions). Players built on
  WebAssembly need `'wasm-unsafe-eval'` and often fetch their `.wasm` from a CDN: avoid them.
- **Cleaned up.** On page change or unmount: kill timelines, dispose geometries, materials and the
  renderer, remove listeners.

Lazy loading per profile:

| profile | where the code lives | how it loads |
| --- | --- | --- |
| laravel | `resources/js/hero.js`, imported with `import()` from `resources/js/app.js` | Vite splits it into its own file under `/build/assets/` |
| static | `src/hero.ts`, `import()` from `src/main.ts` | Vite, the same |
| next | a client component `Hero.tsx`; the page uses `dynamic(() => import("./Hero"), { ssr: false })` from a client component, or `import()` inside `useEffect` | Next splits it; nothing runs on the server |
| django | no bundler by default: add one build step, `npx esbuild static_src/hero.js --bundle --format=esm --minify --outfile=static/js/hero.js` (esbuild as a dev dependency, the command as an npm script, run before `collectstatic` in the Dockerfile's build stage) | the template gives the hashed URL, `<div data-hero data-src="{% static 'js/hero.js' %}">`, and the page script does `import(hero.dataset.src)` |

## 6. The hero visual

A generative piece is drawn by code from formulas. It is the user's idea: ask for it in their words
("something like a slowly turning knot of light", "a field of dots that follows the cursor").

- **From maths, never from a picture.** Do not trace, measure or rebuild a reference image, another
  site's hero or a stock animation. A reference tells you the mood (dark, thin lines, slow), not
  the shape. Pick the shape yourself: a parametric curve, a noise field, a lattice, a spirograph.
- **Start from `../forge-motion/wireform.example.js`** and change its formulas. Its top says when
  Three.js is the better tool.
- **Technical-HUD look**: a near-black background from the tokens, 1px lines in the accent at
  different opacities, one glow pass, digits in `--font-mono` with `tabular-nums`, slow movement
  (a full turn takes 40 to 60 seconds). No scan lines that flicker, no glitch effects: they flash.
- **It is decoration.** `aria-hidden="true"`, no text inside it, the page's heading and button are
  HTML on top. With reduced motion it draws one still frame.
- **It has a budget**: sharpness capped at 2 device pixels per CSS pixel, paused off-screen and in
  hidden tabs, one `stroke()` per group of lines, not per line.

## 7. Accessibility and performance, in numbers

| rule | number | how to check |
| --- | --- | --- |
| reduced motion | every animation has a reduce version: a fade or nothing; no information lost | browser with reduced motion on: every screen still shows everything |
| flashing | nothing flashes more than 3 times in a second (WCAG 2.3.1) | watch loops and error states; no strobing, no fast blinking |
| moving by itself | over 5 seconds: a way to pause, stop or hide it (WCAG 2.2.2) | marquee, hero, autoplay video |
| off-screen and hidden tabs | loops stop | motioncheck.py; the Performance panel shows no frames while scrolled away |
| what animates | `transform` and `opacity` (exceptions: accordion rows, a chart's stroke) | motioncheck.py |
| long tasks | none over 50ms caused by animation | Performance panel, or a `PerformanceObserver` for `longtask` |
| frame rate | 60 a second on a mid-range phone: DevTools at 390px with 4x CPU slowdown | the Performance panel's frames row |
| script added | first load: under 15 KB gzip for all motion code; a lazy hero: under 150 KB gzip | the build output's file sizes |
| focus | never lost: after a modal closes it is back on its button; after a page transition on the new heading | Tab through each transition |
| layout shift | motion never pushes content around (CLS stays under 0.1) | skeletons have the size of their content |
