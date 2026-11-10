/**
 * lazy.js: load a scene only when it is about to be seen, and one switch for all motion.
 *
 * This file imports nothing, so it costs a page almost nothing. Three.js and the scene are only
 * fetched by the loader you pass, and that runs when the container is near the viewport AND the
 * browser has a quiet moment. Until then, and for good when the visitor asked for reduced data,
 * the container shows its poster.
 *
 *   import { lazyScene, motionToggle } from "./scenes/lazy.js";
 *   const box = document.querySelector(".hero-scene");
 *   const hero = lazyScene(box, () => import("./scenes/form.js"), { quality: "auto" });
 *   hero.setProgress(0.4);                      // safe at once: kept, and passed on when the scene is there
 *   motionToggle(document.querySelector("#motion"));
 *
 * THE POSTER. A still picture of the scene (a screenshot of it mounted with { still: true } will
 * do), given in one of two ways:
 *
 *   <div class="hero-scene" aria-hidden="true">
 *     <img data-scene-poster src="/img/hero-poster.webp" alt="">      a child marked data-scene-poster
 *   </div>
 *
 *   .hero-scene { background: center / cover no-repeat url(/img/hero-poster.webp); }   or a background image
 *   .hero-scene[data-scene="live"] { background-image: none; }       ... taken away once the scene is live
 *
 * The scene's stage sets data-scene="live" on the container when its first frame is on screen and
 * fades a data-scene-poster child out by itself. When WebGL is missing, or the scene cannot be
 * loaded or throws, the container gets data-scene="fallback" and the poster simply stays.
 *
 * lazyScene(container, loader, options) -> handle
 *   loader     () => import("./scenes/form.js"): anything that returns a promise of a module with
 *              mount(container, options).
 *   options    passed to mount() as they are, except options.lazy:
 *                lazy.margin   "50%": how far outside the viewport still counts as near (half a
 *                              screen above and below). Any CSS length or percentage.
 *                lazy.timeout  2000: the longest wait for a quiet moment, in milliseconds. A scene at
 *                              the top of the page that must be there fast can pass 300, or call load().
 *   handle     setProgress(p), setData(values), setPointer(x, y): passed on to the scene. Before it
 *              has loaded, the last call of each is kept and passed on then.
 *              pause(reason), resume(reason): the same, with the reasons a stage knows.
 *              load(): load now, whatever the viewport, the browser or reduced data say (a "show
 *              the 3D scene" button). Returns ready.
 *              destroy(): stop waiting, or destroy the scene. Safe to call twice.
 *              ready: a promise of the scene's own handle; null when it failed or was destroyed. It
 *              never rejects. Use it for a scene's own extra methods.
 *              scene: the scene's own handle, or null. state: "waiting", "reduced-data", "loading",
 *              "ready", "failed" or "destroyed". error: what went wrong, after "failed".
 *
 * motionToggle(button) -> { destroy() }
 *   Wires a real <button type="button">Pause motion</button>. A click pauses every scene mounted
 *   through lazyScene, the next click lets them run again. The button gets aria-pressed="true"
 *   while motion is paused (so keep its text the same in both states), the choice is kept in
 *   localStorage and holds on the next page, and <html> carries data-motion="paused" so CSS can
 *   follow: html[data-motion="paused"] .marquee { animation-play-state: paused; }
 *   A paused scene shows a still frame, never an empty box. Visitors who asked their system for
 *   reduced motion get that still frame whatever the button says, so hide it for them:
 *   @media (prefers-reduced-motion: reduce) { #motion { display: none; } }
 *   motionPaused() tells the current choice, setMotionPaused(true | false) sets it from code.
 */

const STORE_KEY = "forge-scenes-motion"; // localStorage: "paused" while the visitor has motion switched off
const TOGGLE = "motion-toggle";          // the reason given to pause(): it never undoes a pause of the page's own
const handles = new Set();               // every lazyScene handle that is not destroyed
const buttons = new Set();               // every button motionToggle wired
let paused = null;                       // null: not read from storage yet

export function motionPaused() {
  if (paused === null) {
    paused = false;
    try {
      paused = window.localStorage.getItem(STORE_KEY) === "paused";
    } catch (error) {
      // Storage is switched off or not allowed here: start with motion on.
    }
  }
  return paused;
}

export function setMotionPaused(value) {
  paused = Boolean(value);
  try {
    if (paused) window.localStorage.setItem(STORE_KEY, "paused");
    else window.localStorage.removeItem(STORE_KEY);
  } catch (error) {
    // Private mode, or storage switched off: the choice holds for this page only.
  }
  reflect();
  for (const handle of handles) {
    if (paused) handle.pause(TOGGLE);
    else handle.resume(TOGGLE);
  }
}

// Show the choice where the page can see it: on the buttons and on <html>.
function reflect() {
  const now = motionPaused();
  for (const button of buttons) button.setAttribute("aria-pressed", String(now));
  if (now) document.documentElement.setAttribute("data-motion", "paused");
  else document.documentElement.removeAttribute("data-motion");
}

export function motionToggle(button) {
  if (!button) return { destroy() {} }; // a page without the button
  const onClick = () => setMotionPaused(!motionPaused());
  button.addEventListener("click", onClick);
  buttons.add(button);
  reflect();
  return {
    destroy() {
      button.removeEventListener("click", onClick);
      buttons.delete(button);
    },
  };
}

export function lazyScene(container, loader, options = {}) {
  const { lazy = {}, ...sceneOptions } = options;
  const margin = lazy.margin === undefined ? "50%" : lazy.margin;
  const timeout = lazy.timeout === undefined ? 2000 : lazy.timeout;
  const calls = new Map();  // method name -> the arguments of its last call, for when the scene is there
  const pauses = new Set(); // reasons given to pause() and not resumed yet
  const waits = [];         // functions that cancel whatever is still waiting
  let scene = null, state = "waiting", started = false, markedFallback = false, settle = null;
  const ready = new Promise((resolve) => { settle = resolve; });

  const forward = (name) => (...args) => {
    if (state === "destroyed") return;
    if (scene) {
      if (typeof scene[name] === "function") scene[name](...args);
    } else {
      calls.delete(name); // so the map keeps the order of the last calls
      calls.set(name, args);
    }
  };
  const stopWaiting = () => { for (const cancel of waits.splice(0)) cancel(); };

  function load() {
    if (started || state === "destroyed" || state === "failed") return ready;
    started = true;
    stopWaiting();
    state = "loading";
    Promise.resolve()
      .then(loader)
      .then((module) => {
        const mount = module && (module.mount || (module.default && module.default.mount));
        if (typeof mount !== "function") throw new TypeError("lazyScene: the loaded module has no mount()");
        return state === "destroyed" ? null : mount(container, sceneOptions);
      })
      .then((mounted) => {
        if (state === "destroyed") { // destroyed while it was loading
          if (mounted && typeof mounted.destroy === "function") mounted.destroy();
          return;
        }
        if (!mounted) throw new TypeError("lazyScene: mount() returned nothing");
        scene = mounted;
        state = "ready";
        for (const reason of pauses) if (typeof scene.pause === "function") scene.pause(reason);
        for (const [name, args] of calls) if (typeof scene[name] === "function") scene[name](...args);
        calls.clear();
        settle(scene);
      })
      .catch((error) => {
        if (state === "destroyed") return;
        state = "failed";
        handle.error = error;
        markedFallback = true;
        container.setAttribute("data-scene", "fallback"); // the same sign a stage gives: the poster stays
        console.error("lazyScene: the scene could not be loaded, so the poster stays.", error);
        settle(null);
      });
    return ready;
  }

  function destroy() {
    if (state === "destroyed") return;
    stopWaiting();
    handles.delete(handle);
    const mounted = scene;
    scene = null;
    state = "destroyed";
    calls.clear();
    if (mounted && typeof mounted.destroy === "function") mounted.destroy();
    if (markedFallback) container.removeAttribute("data-scene");
    settle(null); // does nothing when ready was already settled
  }

  const handle = {
    ready,
    error: null,
    get scene() { return scene; },
    get state() { return state; },
    setProgress: forward("setProgress"),
    setData: forward("setData"),
    setPointer: forward("setPointer"),
    pause(reason = "user") {
      if (state === "destroyed") return;
      pauses.add(reason);
      if (scene && typeof scene.pause === "function") scene.pause(reason);
    },
    resume(reason = "user") {
      if (state === "destroyed") return;
      pauses.delete(reason);
      if (scene && typeof scene.resume === "function") scene.resume(reason);
    },
    load,
    destroy,
  };
  if (!container || container.nodeType !== 1) { // a selector that matched nothing: say so, and do nothing
    state = "failed";
    handle.error = new TypeError("lazyScene: there is no container");
    console.error(handle.error);
    settle(null);
    return handle;
  }
  handles.add(handle);
  if (motionPaused()) pauses.add(TOGGLE); // switched off on an earlier page: the scene starts as a still
  reflect();

  // Reduced data (Chromium's "Lite mode", Android's data saver): three.js is several hundred
  // kilobytes the visitor asked not to spend. The poster stays until the page calls load().
  if (navigator.connection && navigator.connection.saveData) {
    state = "reduced-data";
    return handle;
  }

  // First: near the viewport. Then: a quiet moment, so the download and the shader compilation do
  // not compete with the page's own first paint.
  const whenIdle = () => {
    if (typeof window.requestIdleCallback === "function") {
      const id = window.requestIdleCallback(load, { timeout });
      waits.push(() => window.cancelIdleCallback(id));
    } else { // Safari has no requestIdleCallback: a short timer is the nearest thing
      const id = setTimeout(load, 200);
      waits.push(() => clearTimeout(id));
    }
  };
  if (typeof IntersectionObserver === "function") {
    const watcher = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      stopWaiting();
      whenIdle();
    }, { rootMargin: `${margin} 0px` });
    watcher.observe(container);
    waits.push(() => watcher.disconnect());
  } else {
    whenIdle();
  }
  return handle;
}
