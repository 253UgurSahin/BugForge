# Motion reference

The numbers, the recipes, the patterns per look level and the budgets for `/forge-design motion`
(its steps: `../forge-design/steps/motion.md`; the levels: `../forge/levels.md`). Sections 1 to 7 hold
for every level; the CSS of the recipes is ready in `../forge-design/motion.css`. Level 3 adds section 8,
level 4 section 9, level 5 section 10; section 11 is the budget per level, section 12 the proof that
needs a click, a slow processor or no WebGL. The scene kit of levels 4 and 5 is the folder of
`../forge-design/scenes/stage.js`; the options and API of each file are the comment at its top.

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
  A scroll scene follows the scrollbar and a hero scene runs by itself: neither is a wait.
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

With a theme forge designed: add these to `forge-work/design/tokens.json`, next to what forge-design
design wrote there (`fast`, `base` and `ease` stay as they are), then run the theme.py command in
`forge-work/design/components.md`. The user's own app with no tokens.json: see "Without forge tokens"
below, and never theme.py.
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

`pulse` is one pass of the skeleton sheen, `loop` one round of a marquee. The motion has a
character that fits the chosen concept. Three are a starting point, the same tokens with other
values; the concept tunes them:

| token | calm | lively | technical-HUD |
| --- | --- | --- | --- |
| fast / base / slow / slower | 120 / 200 / 320 / 480ms | 100 / 180 / 280 / 420ms | 80 / 140 / 240 / 400ms |
| ease (standard) | `cubic-bezier(.2,.8,.2,1)` | the same | `cubic-bezier(.2,0,0,1)`: sharper |
| stagger | 30ms | 40ms | 25ms |
| shift-sm / shift / shift-lg | 4 / 8 / 16 | 4 / 12 / 24 | 2 / 8 / 16 |
| character | fades and small rises, no loops, no spring | spring on small controls, staggered lists, count-ups | thin lines that draw themselves, numbers that tick in a mono font, a slow line hero; nothing bounces |

**Without forge tokens** (the user's own app, its own look). Do not make a tokens.json and do not
run theme.py: with `--tailwind 4` it writes `@theme static { --color-*: initial; --breakpoint-*:
initial; }`, which removes every Tailwind colour and every `sm:`, `md:` and `lg:` breakpoint the
app has. Add a plain block at the end of the app's main stylesheet (next: `app/globals.css`), with
each variable below that the app does not define yet, the values from the character, the colours
mapped to the app's own variables or values:

```css
:root {                                   /* forge-design motion: read by motion.css and the scene kit */
  --duration-fast: 120ms; --duration-base: 200ms; --duration-slow: 320ms; --duration-slower: 480ms;
  --duration-stagger: 30ms; --duration-pulse: 1600ms; --duration-loop: 24s;
  --ease-standard: cubic-bezier(.2,.8,.2,1); --ease-exit: cubic-bezier(.4,0,1,1);
  --ease-move: cubic-bezier(.4,0,.2,1); --ease-spring: cubic-bezier(.34,1.56,.64,1);
  --size-shift-sm: 4px; --size-shift: 8px; --size-shift-lg: 16px; --size-ring: 2px;
  --radius-sm: 4px; --shadow-pop: 0 8px 24px rgb(0 0 0 / .12);
  --color-accent: var(--their-accent);     /* the app's own: a brand variable, or a Tailwind one */
  --color-surface: var(--their-surface); --color-border: var(--their-border);
  --color-bg: var(--their-background); --color-text: var(--their-foreground);   /* levels 4 and 5 */
}
```

Then check in the browser that each one has a value, for example
`getComputedStyle(document.documentElement).getPropertyValue("--color-accent")`: a missing or
misspelt one makes its rule do nothing, without an error. Leave out what the app already has:
Tailwind 4 has its own `--radius-sm`, and a second one here would change every `rounded-sm`. A
dark theme of the app's own: map the colours inside its dark rule too.

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
5. **CSS 3D** (level 3 and up): `perspective`, `rotateX`/`rotateY` and `translateZ` on cards and
   panels (section 8, "Tilt card").
6. **WebGL** (level 4 and up): a scene of the kit, mounted lazily (section 9).
7. **A library** other than three: section 5.

The app's CSP (forge-build pack's nginx.conf, Django's CSP middleware, next.config) blocks inline styles
in markup. Scripts may still set them: `element.style.setProperty("--m-tab-x", "40px")` and
`element.animate()` are allowed, a `style="..."` attribute in a template is not.

## 4. Recipes

Each: the markup or script, what people who asked for reduced motion get, and the usual mistake.
The classes are in motion.css. Scripts import `token`, `ms` and `reduce` from tokens.js above.

One script switches the scroll recipes on and pauses loops nobody can see:

```js
// motion.js: load it as a module on every page (next: <MotionRuntime/> below)
document.documentElement.dataset.motion ||= "on";   // from here on, .m-reveal starts hidden;
                                                    // ||= keeps "paused" from the kit's motionToggle

const seen = new IntersectionObserver((entries) => {
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    entry.target.classList.add("is-visible");
    seen.unobserve(entry.target);                 // once: scrolling back up does not replay it
  }
}, { threshold: 0.1 });                          // no negative rootMargin: see the mistake below
document.querySelectorAll(".m-reveal, .m-draw, .m-grow").forEach((el) => seen.observe(el));

const visible = new IntersectionObserver((entries) => {
  for (const entry of entries) {
    if (entry.target.dataset.userPaused === "true") continue;   // the user's pause button wins
    entry.target.dataset.paused = String(!entry.isIntersecting);
  }
});
document.querySelectorAll(".m-marquee, .m-skeleton").forEach((el) => visible.observe(el));
```

Where motion.css and motion.js go:

| stack | motion.css | motion.js |
| --- | --- | --- |
| laravel | `resources/css/motion.css`, imported in `app.css` after the other imports | `resources/js/motion.js`, imported from `app.js` |
| django | `static/css/motion.css`, linked after `tokens.css` | `static/js/motion.js`, `<script type="module">` in the base template |
| next, Tailwind 4 | `app/motion.css`, in `globals.css` right after `@import "tailwindcss";` as `@import "./motion.css" layer(components);` | `<MotionRuntime/>` below, once in `app/layout.tsx` |
| next, no Tailwind | `app/motion.css`, imported in `app/layout.tsx` after `globals.css` | the same |
| static | imported in `src/main.*`; no bundler: a `<link>` on every page | `src/motion.js` from `src/main.*`, or a module script |

Why the layer: Tailwind 4 puts every utility in a cascade layer, and CSS outside any layer beats
every layer whatever the order. Unlayered, `.m-lift { position: relative }` undoes an `absolute`
class and an `m-` transition replaces a `transition-*` class. Inside `layer(components)` the
utilities win; where an element has Tailwind transition classes, add the property there
(`transition-[color,transform]`) instead of an `m-` class.

**Next (App Router).** The layout stays while the pages under it change on the client, so a script
that runs once never sees the elements of the next page: they keep `opacity: 0` and the content
looks gone. A client component observes whatever arrives, on every route:

```jsx
"use client";
// app/motion-runtime.jsx: motion.js for Next; <MotionRuntime /> once, inside <body> of app/layout.tsx
// (a .jsx file is fine in a TypeScript app; as .tsx, write (entry.target as HTMLElement).dataset)
import { useEffect } from "react";

const PICK = ".m-reveal:not(.is-visible), .m-draw:not(.is-visible), .m-grow:not(.is-visible)";

export default function MotionRuntime() {
  useEffect(() => {
    document.documentElement.dataset.motion ||= "on";
    const seen = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add("is-visible");
        seen.unobserve(entry.target);
      }
    }, { threshold: 0.1 });
    const visible = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.target.dataset.userPaused === "true") continue;
        entry.target.dataset.paused = String(!entry.isIntersecting);
      }
    });
    let frame = 0;
    const watch = () => {
      frame = 0;
      document.querySelectorAll(PICK).forEach((el) => seen.observe(el));   // observing twice is harmless
      document.querySelectorAll(".m-marquee, .m-skeleton").forEach((el) => visible.observe(el));
    };
    watch();
    const added = new MutationObserver(() => { frame ||= requestAnimationFrame(watch); });
    added.observe(document.body, { childList: true, subtree: true });   // route changes, streamed parts
    return () => { added.disconnect(); seen.disconnect(); visible.disconnect(); cancelAnimationFrame(frame); };
  }, []);
  return null;
}
```

Check it the way a user meets it: open a signed-in screen, click to the next one in the app's own
menu, and see its content (section 12's click proof), not only after a reload.

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
Frameworks change pages on the client, where `@view-transition { navigation: auto; }` never runs
(it is for full page loads only). Next: the `TurnLink` of section 10; Livewire's navigate and
others: read the docs of the installed version, and prove it with frames across a click (section 12).

**Scroll reveal, IntersectionObserver.** `class="m-reveal"` plus motion.js above. Reduced: a fade
without the rise. Mistake: hiding content in CSS with no script running (blank page: the recipe
hides only after motion.js set `data-motion`), revealing things above the fold, a threshold of
0.5 on a block taller than the screen, and a negative `rootMargin`: with either, the last block
of a page may never count as seen and stays invisible.

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

CSS and the Web Animations API first. Levels 1 to 3 add no library. From level 4 three is part of
the level; any other library is justified only by a row of this table, and each one goes into
`## Libraries` of `forge-work/motion.md` with the reason.

| library | take it when | do not take it for | size, measured 10 Nov 2026 (min / gzip) | licence: verify |
| --- | --- | --- | --- | --- |
| GSAP 3.15 (`gsap`) | a timeline of 5+ steps that must be scrubbed, reversed or tied to scroll with pinning; morphing or drawing complex SVG | fades, reveals, one-off sequences | core 73 / 28 KB, ScrollTrigger 45 / 18 KB | not open source: package.json names "Standard 'no charge' license" with a link and ships no licence file. Read the linked page and tell the user its conditions |
| Three.js 0.187 (`three`) | look level 4 and 5: the scene kit needs it, and the level is the user's yes, so install it without asking again | levels 1 to 3: no WebGL there | a small scene after tree-shaking: about 540 / 134 KB | MIT, in `LICENSE` |
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

The hero is the chosen concept made to move: the one picture people remember. It comes from the
brief (`forge-work/design/brief.md`), never from a style list and never from a stock shape.

- **From the app's world, drawn by code.** Water and depth contours for an angling app, a ledger
  that folds for a bookkeeping app, a field of points that settles into the app's own numbers.
  Do not trace, measure or rebuild a reference image, another site's hero or a stock animation. A
  reference tells you the mood (dark, thin lines, slow), never the shape.
- **Per level.** Levels 1 and 2 have no hero visual: the heading, the type and the page's own
  entrance carry the first screen. Level 3: the signature moment may be a drawn line piece on a
  2D canvas; start from `../forge-design/wireform.example.js` and change its formulas until it is
  the concept's own shape. Levels 4 and 5: a WebGL scene from the kit (section 9), tuned until it
  could only belong here; a plain torus knot, a default particle cloud or the kit's own defaults
  are a failed hero.
- **Technical look**: a near-black background from the tokens, 1px lines in the accent at
  different opacities, one glow pass, digits in `--font-mono` with `tabular-nums`, slow movement
  (a full turn takes 40 to 60 seconds). No scan lines that flicker, no glitch effects: they flash.
- **It is decoration.** `aria-hidden="true"`, no text inside it, the page's heading and button are
  HTML on top, readable in light and dark. With reduced motion it shows one still frame.
- **It has a budget** (section 11): sharpness capped at 2 device pixels per CSS pixel, paused
  off-screen and in hidden tabs, nothing of three in the first load.

## 7. Accessibility and performance, in numbers

| rule | number | how to check |
| --- | --- | --- |
| reduced motion | every animation has a reduce version: a fade or nothing; no information lost | browser with reduced motion on: every screen still shows everything |
| flashing | nothing flashes more than 3 times in a second (WCAG 2.3.1) | watch loops and error states; no strobing, no fast blinking |
| moving by itself | over 5 seconds: a way to pause, stop or hide it (WCAG 2.2.2) | marquee, hero, autoplay video |
| off-screen and hidden tabs | loops stop | motioncheck.py; a scene's container gets no new frames while scrolled away (stage.js pauses it) |
| what animates | `transform` and `opacity` (exceptions: accordion rows, a chart's stroke) | motioncheck.py |
| long tasks | none over 50ms caused by animation | `longestTaskMs` of the proof script (section 12) |
| frame rate | 60 a second on a mid-range phone: 4x CPU slowdown | `fps` of the proof script (section 12), which sets the slowdown |
| script added | per level: section 11 | the build output's file sizes |
| focus | never lost: after a modal closes it is back on its button; after a page transition on the new heading | Tab through each transition |
| layout shift | motion never pushes content around (CLS stays under 0.1) | skeletons have the size of their content |

## 8. Level 3: Expressive

Everything above, plus scroll storytelling, springs, charts that draw and morph, real depth with
CSS 3D and one signature moment. No library: CSS and the Web Animations API. Each pattern ran
in Chromium with motion on and with reduced motion.

**Sticky scroll scene.** A section three screens tall whose stage stays in place while its steps
follow the scroll. The script writes the progress (0 to 1) as `--progress` and the current step as
`data-at`; CSS does the rest.

```html
<section class="story" data-story>
  <div class="story__stage">
    <svg class="story__chart" aria-hidden="true">...</svg>
    <ol class="story__steps">
      <li data-step>The lake at dawn</li><li data-step>Where the fish were</li><li data-step>Your best spot</li>
    </ol>
  </div>
</section>
```
```css
.story { height: 300vh; }                         /* three screens of scrolling for one scene */
.story__stage { position: sticky; top: 0; height: 100vh; display: grid; place-items: center; overflow: clip; }
.story__steps > * { opacity: .35; }
.story[data-at="0"] li:nth-child(1), .story[data-at="1"] li:nth-child(2), .story[data-at="2"] li:nth-child(3) { opacity: 1; }
@media (prefers-reduced-motion: no-preference) {
  .story__chart { transform: translateX(calc((1 - var(--progress, 1)) * -30%)) scale(calc(.8 + var(--progress, 1) * .2)); }
  .story__steps > * { transition: opacity var(--duration-slow) linear; }
}
@media (prefers-reduced-motion: reduce) {
  .story { height: auto; }
  .story__stage { position: static; height: auto; }
  .story__steps > * { opacity: 1; }
}
```
```js
// story.js: the scroll progress of a sticky scene, 0 at its start and 1 at its end
import { reduce } from "./tokens.js";

export function story(section, onProgress = () => {}) {
  const steps = section.querySelectorAll("[data-step]").length || 1;
  let frame = 0;
  const update = () => {
    const box = section.getBoundingClientRect();
    const progress = Math.min(Math.max(-box.top / (box.height - innerHeight), 0), 1);
    section.style.setProperty("--progress", progress.toFixed(4));
    section.dataset.at = String(Math.min(Math.floor(progress * steps), steps - 1));
    onProgress(progress);                                  // a scene: hero.setProgress(progress)
    frame = requestAnimationFrame(update);
  };
  const near = new IntersectionObserver(([entry]) => {     // runs only while the section is on screen
    cancelAnimationFrame(frame);
    if (entry.isIntersecting && !reduce.matches) frame = requestAnimationFrame(update);
  });
  near.observe(section);
  return () => { near.disconnect(); cancelAnimationFrame(frame); };
}
```

Reduced: the section is as tall as its content, every step is there at full strength, and the
chart stands in its end state (`--progress` falls back to 1). Mistake: an ancestor with
`overflow: hidden` or `auto` (sticky then never sticks: use `clip`), a section so short that the
scene is over in one flick, text people must read moving with the scroll, and a `scroll` listener
that sets `top` or `height`.

**Spring.** A real spring, from a duration token and a bounce, as a CSS `linear()` curve that the
Web Animations API plays. Browsers without `linear()` get the `--ease-spring` curve.

```js
// spring.js: a real spring for element.animate(), from a duration token and a bounce
export function spring(duration, bounce = 0.2) {
  const zeta = 1 - Math.min(Math.max(bounce, 0.05), 0.6);      // damping: 1 would not overshoot
  const w = (2 * Math.PI) / (duration / 1000);                  // one swing in about `duration`
  const wd = w * Math.sqrt(1 - zeta * zeta);
  const at = (t) => 1 - Math.exp(-zeta * w * t) * (Math.cos(wd * t) + ((zeta * w) / wd) * Math.sin(wd * t));
  const settle = Math.log(1000 * (1 + (zeta * w) / wd)) / (zeta * w);   // seconds to within 0.1%
  const points = Array.from({ length: 41 }, (_, i) => (i === 40 ? 1 : +at((settle * i) / 40).toFixed(3)));
  const easing = `linear(${points.join(", ")})`;
  const supported = globalThis.CSS?.supports?.("transition-timing-function", easing);
  return { duration: Math.round(settle * 1000), easing: supported ? easing : null };
}
```
```js
import { spring } from "./spring.js";
import { ms, token, reduce } from "./tokens.js";

export function pop(card) {
  if (reduce.matches) return;
  const { duration, easing } = spring(ms("--duration-slow"), 0.35);
  card.animate([{ transform: "scale(.92)" }, { transform: "none" }],
               { duration, easing: easing ?? token("--ease-spring") });
}
```

A bounce of 0.2 overshoots about 1 percent, 0.35 about 7 percent, 0.6 (the most it takes) about 25
percent. Reduced: nothing; the card is already in its end state. Mistake: a spring on a whole
panel or page (it wobbles the reading place), a bounce over 0.4 on anything with text, and a
spring on things that leave (they use `--ease-exit`).

**Chart that morphs between periods.** Bars scale to their new share; a short stagger shows which
bar changed most.

```css
.bars { display: flex; align-items: end; gap: 4px; height: 160px; }
.bars__bar { flex: 1; height: 100%; transform-origin: bottom; transform: scaleY(var(--value, 0)); background: var(--color-accent); }
@media (prefers-reduced-motion: no-preference) {
  .bars__bar { transition: transform var(--duration-slower) var(--ease-move);
               transition-delay: calc(var(--index, 0) * var(--duration-stagger)); }
}
```
```js
export function showPeriod(chart, values) {
  const top = Math.max(...values, 1e-9);
  chart.querySelectorAll(".bars__bar").forEach((bar, index) => {
    bar.style.setProperty("--index", String(index));
    bar.style.setProperty("--value", String((values[index] ?? 0) / top));
  });
}
```

Reduced: the bars jump to their new height. Mistake: animating `height` (layout on every frame),
the values only in the bars (keep the numbers as labels or a table), and a line chart morphed by
animating `d`, which only some browsers do: draw the new line with `m-draw` instead.

**Tilt card with depth.js.** Cards that lean toward the pointer, with a layer inside at its own
depth, in perspective set once on their container. CSS and a small `depth.js` that you write into
the app from this recipe, outside its `scenes/` folder: the kit has no depth.js of its own yet
(when one sits next to stage.js, its top comment says how to use it instead).

```html
<div class="deck">
  <article class="card tilt">
    <img src="/img/spot.webp" alt="The north bank at dawn">
    <h3 class="tilt__layer">North bank</h3>
  </article>
</div>
```
```css
.deck { perspective: 900px; }                          /* once, on the container */
.tilt { transform: rotateX(var(--tilt-x, 0deg)) rotateY(var(--tilt-y, 0deg)); transform-style: preserve-3d; }
.tilt__layer { transform: translateZ(var(--size-shift-lg)); }   /* nearer than the card */
@media (prefers-reduced-motion: no-preference) {
  .tilt { transition: transform var(--duration-base) var(--ease-standard); }
}
@media (prefers-reduced-motion: reduce) { .tilt, .tilt__layer { transform: none; } }
```
```js
// depth.js of the app: a card leans toward the pointer, at most `most` degrees
import { reduce } from "./tokens.js";

export function tilt(card, most = 6) {
  if (reduce.matches || !matchMedia("(hover: hover)").matches) return () => {};
  const move = (event) => {
    const box = card.getBoundingClientRect();
    const x = (event.clientX - box.left) / box.width - 0.5;      // -0.5 .. 0.5
    const y = (event.clientY - box.top) / box.height - 0.5;
    card.style.setProperty("--tilt-y", (x * most * 2).toFixed(2) + "deg");
    card.style.setProperty("--tilt-x", (-y * most * 2).toFixed(2) + "deg");
  };
  const rest = () => { card.style.setProperty("--tilt-x", "0deg"); card.style.setProperty("--tilt-y", "0deg"); };
  card.addEventListener("pointermove", move, { passive: true });
  card.addEventListener("pointerleave", rest);
  return () => { card.removeEventListener("pointermove", move); card.removeEventListener("pointerleave", rest); };
}
```

In React, call it in a `useEffect` and return what it returns. Panels stacked in perspective are
the same container with `rotateX(8deg)` and a `translateZ` per panel. A card stays a normal link or
button: the tilt is a transform on top. Reduced: the cards lie flat and still; hover gives the
shadow of `m-lift`. Mistake: a tilt over about 8 degrees (text gets hard to read), tilting a whole
form or table, `overflow: hidden` on the card (it flattens the layers), depth on touch screens
where nobody hovers, and a perspective set on each card instead of once on their container.

**The signature moment.** One moment that could only belong to this app, from the concept: a
float that dips when a catch is saved, a stamp that lands on a paid invoice, a tide line that
rises to today's height. It is built from the patterns above, placed where people look first, and
written in the inventory as its own row.

## 9. Level 4: Showpiece

Everything above, plus a WebGL hero from the scene kit, light and depth that follow the pointer,
3D inside the interface and depth while scrolling. Which scene: `form.js` for a shape (an object,
a tool, a craft), `field.js` for particles (a crowd, a flow, numbers; it takes `setData`),
`aurora.js` for light (water, a sky, a sea; mode `water`), `contour.js` for lines over a map
(places, depth, height). The options and API of each are the comment at its top; the mount per
stack is below (a plain page, React and Next).

- `npm install three` in the app; the level is the user's yes, so do not ask again. Read the
  licence of the installed version (MIT, in `node_modules/three/LICENSE`) and write it in
  `## Libraries`.
- Copy `stage.js`, `glsl.js`, `lazy.js` and the scene into a `scenes/` folder of the app's scripts:
  the app serves them itself.
- The hero container gets a poster: a still of the scene. Mount it once with `{ still: true }` at
  the size of the hero and take a screenshot of the container with Playwright, as PNG or as JPEG
  at quality 80 (`await page.locator(".hero-scene").screenshot({ path: "public/hero-poster.jpg",
  type: "jpeg", quality: 80 })`), under 100 KB, next to the app's images. Playwright writes no
  WebP; install no converter for it.

**Mounting a kit scene in a plain page.** With no bundler, an import map points `three` at a file
the app serves itself: copy `node_modules/three/build/three.module.js` and `three.core.js` to the
app's static folder with an npm script, never from a CDN. The import map is inline, so a strict
CSP needs its hash in `script-src`.

```html
<script type="importmap">{ "imports": { "three": "/static/vendor/three/three.module.js" } }</script>
<div class="hero-scene" aria-hidden="true"><img data-scene-poster src="/static/img/hero-poster.jpg" alt=""></div>
<button type="button" id="motion">Pause motion</button>
<script type="module" src="/static/js/hero.js"></script>
```
```js
// hero.js
import { lazyScene, motionToggle } from "./scenes/lazy.js";
import { story } from "./story.js";

const hero = lazyScene(document.querySelector(".hero-scene"), () => import("./scenes/form.js"),
                       { side: "right", shapes: ["ring", "knot", "coil"] });
motionToggle(document.querySelector("#motion"));
story(document.querySelector("[data-story]"), (progress) => hero.setProgress(progress));
```
```css
.hero-scene { position: relative; min-height: 80vh; }
.hero-scene [data-scene-poster] { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
@media (prefers-reduced-motion: reduce) { #motion { display: none; } }
```

Nothing of three loads until the hero is near the screen and the page is idle; the poster shows
until the first frame, and stays when WebGL is missing (`data-scene="fallback"`). Reduced: the
stage draws one still frame; the toggle is hidden. Mistake: importing the scene at the top of a
module (three is then in the first load), a hero with no size of its own (the canvas is 0 high),
a poster that does not match the still (the page jumps), and text inside the container.

**Mounting a kit scene in React (and Next).** A client component; the effect mounts, its cleanup
destroys. React runs effects twice in development: `destroy()` and a new `lazyScene()` on the same
element are safe.

```jsx
"use client";
import { useEffect, useRef } from "react";
import { lazyScene } from "../scenes/lazy.js";

export default function Hero({ progress = 0 }) {
  const box = useRef(null);
  const scene = useRef(null);
  useEffect(() => {
    scene.current = lazyScene(box.current, () => import("../scenes/form.js"), { side: "right" });
    return () => scene.current.destroy();
  }, []);
  useEffect(() => { scene.current?.setProgress(progress); }, [progress]);
  return (
    <div ref={box} className="hero-scene" aria-hidden="true">
      <img data-scene-poster src="/hero-poster.jpg" alt="" />
    </div>
  );
}
```

lazy.js imports nothing, so this component costs the first load almost nothing, and the dynamic
`import()` makes Next and Vite split the scene and three into their own file. Reduced: as above.
Mistake: `lazyScene` called during render (it runs on the server and on every render), no cleanup
(a second WebGL context on every page change, until the browser drops the oldest), and the scene
remounted on every prop change instead of fed through its methods.

## 10. Level 5: Cinematic

Everything above, plus a scroll-driven journey, custom shaders, GPU particles, forms that react to
the pointer and to the app's live data, and screens that change in 3D space.

- **The journey**: a tall section whose chapters move the camera, with each chapter's text
  brought in by the page. The kit has no `journey.js` yet: build it from story.js (section 8) and
  the scene's camera, as below (`chapters.js`). The chapters come from the direction, not a demo.
- **Custom shaders**: a `THREE.ShaderMaterial` in the app's own code that spreads `stage.uniforms`
  (time, pointer, progress, the theme's colours) and builds on the noise of `glsl.js`; the fragment
  shader ends with `#include <colorspace_fragment>`. The comment at the top of `stage.js` shows a
  whole scene. A kit scene used as it is does not count as the app's own shader.
- **GPU particles**: `field.js`, its formations set by `setProgress`, its amplitude by `setData`.

**The journey.** Chapters along the scroll of a sticky section (the `.story` markup and CSS of
section 8, one `[data-step]` per chapter). Each chapter has a camera position and a progress for
the scene; between two chapters both ease. For `form.js` and `field.js`, which leave the camera to
the page; `aurora.js` and `contour.js` are flat shaders, so their journey is `setProgress` only.

```js
// chapters.js of the app (outside its scenes/ folder): the camera through chapters, from the scroll
import { story } from "./story.js";

export async function journey(section, hero, chapters, onChapter = () => {}) {
  const scene = await hero.ready;                  // lazyScene's promise of the scene; null: no WebGL
  if (!scene) return () => {};
  const { camera } = scene.stage;
  let current = -1;
  return story(section, (progress) => {
    const i = Math.max(chapters.findLastIndex((c) => c.at <= progress), 0);
    const a = chapters[i], b = chapters[Math.min(i + 1, chapters.length - 1)];
    const t = b === a ? 0 : Math.min((progress - a.at) / (b.at - a.at), 1);
    const e = t * t * (3 - 2 * t);                 // soft at both ends
    camera.position.set(...a.camera.map((v, k) => v + (b.camera[k] - v) * e));
    camera.lookAt(0, 0, 0);
    scene.setProgress(a.progress + (b.progress - a.progress) * e);
    if (i !== current) onChapter((current = i));  // the page shows that chapter's text
  });
}
```
```js
journey(document.querySelector("[data-story]"), hero, [
  { at: 0, camera: [0, 0, 6], progress: 0 },       // far: the whole lake
  { at: 0.4, camera: [2, 1, 3], progress: 0.5 },   // closer: where the fish were
  { at: 0.8, camera: [0, -1, 2], progress: 1 },    // under the surface: your best spot
]);
```

Reduced: story.js never runs its loop, so the scene shows its still frame and every chapter's text
stands in the section, which is as tall as its content. Mistake: a camera that cuts between
chapters (ease it), chapters so short that one flick of the wheel skips two, and text that people
must read moving with the camera.

**The data hook.** `setData` gets the app's own numbers, never made-up ones, as numbers from 0 to
1 (what each scene does with them: its comment). Where:

- On a signed-in screen that already loads them (an overview, a statistics page): the hero or a
  scene of that screen. In Next the page (a server component) already has the rows; pass them as
  a prop to the client scene component and call `setData` in a `useEffect` on that prop.
- Not on a public page: the landing page's hero is seen by everyone, so it gets no one's private
  numbers. A new API route, or private data on a public page, changes what the app does and who
  sees what: ask the user first, and build neither without a yes.
- Live refresh only from an endpoint the app already has and that screen already uses, same
  origin: `feed()` below.

```jsx
// in the client component of a signed-in screen: rows came from the page's own data loading;
// share() is in feed.js below
useEffect(() => { scene.current?.setData(share(rows.map((row) => row.count))); }, [rows]);
```

**Feeding setData from fetched data.** From an endpoint the screen already uses, the same
origin, every so often while someone looks:

```js
// feed.js: pull the app's own data every so often and hand it to whatever shows it
export function feed(url, use, every = 30000) {
  let controller;
  const pull = async () => {
    if (document.hidden) return;                          // nobody looks: no request
    controller?.abort();
    controller = new AbortController();
    try {
      const response = await fetch(url, { signal: controller.signal, headers: { accept: "application/json" } });
      if (response.ok) use(await response.json());
    } catch {
      // offline, or aborted: the scene and the numbers keep their last values
    }
  };
  pull();
  const timer = setInterval(pull, every);
  return () => { clearInterval(timer); controller?.abort(); };
}

export const share = (numbers) => {                       // to 0..1, the largest is 1
  const top = Math.max(...numbers, 1e-9);
  return numbers.map((n) => Math.max(n, 0) / top);
};
```
```js
import { feed, share } from "./feed.js";

feed(endpointTheScreenAlreadyUses, (rows) => {          // the same URL the screen loads, not a new one
  scene.setData(share(rows.map((row) => row.count)));
  setCatches(rows.reduce((sum, row) => sum + row.count, 0));   // the count below
});
```

Reduced: the still frame is drawn again with the new values (the stage redraws on new data).
Mistake: data from another host (it is not the app's, and the browser sends that host every
visitor's address), a request every second, a scene that waits for data before its first frame,
and private numbers shown in a way the page itself does not show them.

**A count that follows live data.** A number that moves to each new value from where it stands
now, also when a new value arrives half-way. The screen reader gets the new value once.

```html
<span class="sr-only" id="catches-label" data-unit="catches">49 catches</span>
<span class="tile__value" id="catches" aria-hidden="true" data-value="49">49</span>
```
```js
// livecount.js: a number that moves to each new value from where it stands now
import { ms, reduce } from "./tokens.js";

export function liveCount(el, label) {
  const format = new Intl.NumberFormat(document.documentElement.lang || undefined);
  let shown = Number(el.dataset.value) || 0;
  let frame = 0;
  return (value) => {
    cancelAnimationFrame(frame);
    label.textContent = `${format.format(value)} ${label.dataset.unit}`;   // read out once, not per step
    if (reduce.matches || document.hidden) {
      shown = value;
      el.textContent = format.format(value);
      return;
    }
    const from = shown;
    const duration = ms("--duration-slower");
    let start;
    const step = (now) => {
      start ??= now;
      const progress = Math.min((now - start) / duration, 1);
      shown = from + (value - from) * (1 - (1 - progress) ** 3);   // a new value mid-way starts from here
      el.textContent = format.format(Math.round(shown));
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
  };
}
```

Use it as `const setCatches = liveCount(document.querySelector("#catches"),
document.querySelector("#catches-label"))`. Reduced: the new number at once. Mistake: counting
from 0 on every refresh, an `aria-live` region on the moving digits (it reads out every step), and
digits that jiggle (give the value `font-variant-numeric: tabular-nums`).

**Screens that change in 3D space.** The page change of section 4, turned in perspective. The
browser plays these rules on a full page load between two pages (`@view-transition`) and inside
`document.startViewTransition()`; within one page, `swap()` of section 4 plays it.

```css
@media (prefers-reduced-motion: no-preference) {
  ::view-transition-old(root) { animation: screen-out var(--duration-slower) var(--ease-move) both; transform-origin: left center; }
  ::view-transition-new(root) { animation: screen-in var(--duration-slower) var(--ease-move) both; transform-origin: right center; }
}
@keyframes screen-out { to { opacity: 0; transform: perspective(1600px) rotateY(10deg) translateZ(-160px); } }
@keyframes screen-in { from { opacity: 0; transform: perspective(1600px) rotateY(-10deg) translateZ(-160px); } }
```

For a scene that stays between screens, keep its container in the layout outside the part that
changes, and move its camera (`setProgress`, or the journey's next chapter) on each route change.
Reduced: the plain change of page. Mistake: a turn over 15 degrees or longer than 500ms on every
navigation (people feel it in their stomach), and a scene remounted on every page change.

**Next and other client-side routers.** Next changes pages on the client, so neither of those
runs and nothing turns, although the CSS is there. Wrap its navigation in a view transition that
waits until the new route has rendered:

```jsx
"use client";
// app/turn-link.jsx: <TurnLink href="/catches">Catches</TurnLink> in the app's main menu,
// and <RouteTurn /> once in app/layout.tsx, next to <MotionRuntime />
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

let rendered = null;                               // resolves when the new route is on screen

export function RouteTurn() {
  const path = usePathname();
  useEffect(() => { rendered?.(); rendered = null; }, [path]);
  return null;
}

export function TurnLink({ href, onClick, ...rest }) {
  const router = useRouter();
  const path = usePathname();
  const go = (event) => {
    onClick?.(event);
    const plain = event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
    if (!plain || event.defaultPrevented || href === path || !document.startViewTransition
        || matchMedia("(prefers-reduced-motion: reduce)").matches) return;   // Next's own change
    event.preventDefault();
    document.startViewTransition(() => new Promise((done) => {
      rendered = done;
      setTimeout(done, 1500);                      // never hold the page if the route does not change
      router.push(href);
    }));
  };
  return <Link href={href} onClick={go} {...rest} />;
}
```

Newer Next versions may have a view transition option of their own (`experimental.viewTransition`):
use it instead only when the docs of the installed version name it. Either way the proof is frames
taken across a click (section 12), never a reload: a reload is a full page load and plays the CSS
whether the client change works or not.

## 11. The budget per level

Measured on the built app: gzip sizes from the build output, frames and long tasks with the
proof script of section 12 (4x CPU slowdown for a mid-range phone).

Build in a copy, never in the folder where the user's dev server runs: `next dev` and `next build`
both write `.next`, and a build there can break the running server. A copy of the work branch
outside the project does it: `git worktree add <a temp folder> <the work branch>`, then in that
folder `npm ci` and the build (`npm run build`); read the sizes from its output (`du` plus `gzip
-c | wc -c` on the files the page loads), then `git worktree remove <that folder>`. The same holds
for any stack whose dev server and build share an output folder.

| level | motion code in the first load | loaded later | frames | also |
| --- | --- | --- | --- | --- |
| 1 Subtle | motion.css, about 4 KB; scripts none or under 2 KB | nothing | 60 a second | no layout shift |
| 2 Polished | under 15 KB for all motion code | nothing | 60 a second on a mid-range phone (390px, 4x CPU slowdown) | CLS under 0.1, no long task over 50ms |
| 3 Expressive | under 25 KB, the tilt and story scripts included | nothing | the same, also while a sticky scene scrolls | no library |
| 4 Showpiece | the same as level 3: nothing of three | the hero (three after tree-shaking, the kit and one scene) under 200 KB, only on the screens that show it, after the page is idle; a poster under 100 KB | 60 on a mid-range laptop; 30 or more on a mid-range phone at low quality | the largest paint is the heading or the poster, never later than before |
| 5 Cinematic | the same as level 3 | the scenes, the journey and the shaders together under 300 KB; one WebGL context per page | the same as level 4, also during the journey | GPU particles at the count the stage's quality picks |

## 12. The proof that needs a click, a slow processor or no WebGL

shots.mjs only loads pages; it never clicks. Three things need more: content that arrives by a
client-side page change (Next, section 4), a page change in 3D (section 10), and the budget on a
slow processor or with WebGL off (section 11). Write this script to `forge-work/design/clicks.mjs`
(it finds Playwright where shots.mjs does) and run it on the user's own app only:

```js
// clicks.mjs BASE FROM LINK OUT [--state FILE] [--no-webgl]
//   node forge-work/design/clicks.mjs <URL> /overview "Catches" forge-work/motion-shots/clicks --state forge-work/design/auth.json
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const [base, from, link, out, ...flags] = process.argv.slice(2);
const state = flags.includes("--state") ? flags[flags.indexOf("--state") + 1] : undefined;
const noWebgl = flags.includes("--no-webgl");
const browser = await chromium.launch({ args: noWebgl ? ["--disable-webgl"] : [] });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, storageState: state,
                                           reducedMotion: "no-preference" });
const page = await context.newPage();
page.on("console", (message) => { if (message.type() === "error") console.log("console error:", message.text()); });
await page.goto(new URL(from, base).href, { waitUntil: "networkidle" });
mkdirSync(out, { recursive: true });

const cdp = await context.newCDPSession(page);                  // a mid-range phone: 4x slower
await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
const speed = await page.evaluate(() => new Promise((done) => {
  let frames = 0, longest = 0;
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) longest = Math.max(longest, entry.duration);
  }).observe({ type: "longtask" });
  const start = performance.now();
  const tick = (now) => (++frames, now - start < 3000 ? requestAnimationFrame(tick)
    : done({ fps: Math.round(frames / 3), longestTaskMs: Math.round(longest) }));
  requestAnimationFrame(tick);
}));
await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
const fallback = await page.locator('[data-scene="fallback"]').count();
console.log(JSON.stringify({ ...speed, webgl: !noWebgl, sceneFallbacks: fallback }));

await page.getByRole("link", { name: link }).first().click();   // the page change a user makes
for (let i = 1; i <= 8; i++) {
  await page.screenshot({ path: `${out}/click-f${i}.png` });
  await page.waitForTimeout(60);
}
await page.waitForLoadState("networkidle");
await page.waitForTimeout(1500);                                // entrances and reveals are over
await page.screenshot({ path: `${out}/click-after.png` });
console.log("after the click:", page.url());
await browser.close();
```

- **Content after a client-side change**: look at `click-after.png`: the new screen's content is
  there, nothing left blank where a reveal waits. Do it for each signed-in route, from a link of
  the screen before it.
- **A page change in 3D**: `python3 ../forge-design/changed.py --moves
  forge-work/motion-shots/clicks/click-f*.png` says it moves, and the frames show the turn, not a
  cut.
- **Budget**: `fps` and `longestTaskMs` against the table of section 11 (frames with the 4x
  slowdown, no long task over 50ms). From level 4 run it once more with `--no-webgl`:
  `sceneFallbacks` is at least 1 on a page with a scene, and the poster shows in the pictures.

Write the numbers and the paths under `## Checks` of `forge-work/motion.md`.
