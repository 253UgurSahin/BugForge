/* Tidewatch, level 4: Showpiece. The page's side of the chart table; the scene itself is table.js.

   - The scene is mounted lazily on the hero's chart area (lazyScene): nothing of three.js loads before
     the hero is near the screen and the page has a quiet moment. The drawn chart is its poster: it shows
     until the scene has painted over it, and for good without WebGL or if the scene fails. Once the scene
     is live the hero gets .is-3d and the drawn sheet steps aside under it.
   - The water of the hour. The page's own tide curve (tide.js) gives the height at "now", Tuesday 09:40:
     the scene's sheet of water stands at it and the slip says it. A figure marked "now" is always the
     water now; any other hour is said with its own time and never with "now".
   - The reader's own hour: a scale on the slip runs from now to twelve hours ahead. Drag it (or use the
     arrow keys) and the water on the chart rises and falls to that hour, the slip and the label at the
     tide gauge on the chart say the hour and the height, and the slip's window lights while the hour is
     inside it. "Next 12 hours" plays the scale through: high water at 14:26, low water near 21:00. On the
     first view, once the 3D chart is up, it plays once by itself, so the tide is seen before it is asked
     for; then everything comes back to now.
   - As the hero scrolls away the scene gets its progress: the relief sinks back into the print.
   - One "Pause motion" button stops the scene and depth.js and is remembered (lazy.js); it says what it
     will do: "Pause motion" or "Play motion". While motion is paused the scale still works, a still
     frame at a time, and the play button says it waits for motion. With reduced motion the scene is one
     still frame: no play button and no first-view run, the scale works the same. */
import { lazyScene, motionPaused, setMotionPaused } from "../../vendor/scenes/lazy.js";
import { readTide, NOW } from "./tide.js";

const root = document.documentElement;
const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
const hero = document.querySelector(".hero");
const box = document.getElementById("hero-scene");
const slip = hero && hero.querySelector(".hero__slip");
const scrubber = document.getElementById("tide-scrub");
const range = document.getElementById("tide-hour");
const play = document.getElementById("tide-play");
const playText = play && play.querySelector("[data-play-text]");
const motion = document.getElementById("motion");
const motionText = motion && motion.querySelector("[data-motion-text]");
const tide = readTide();
const SPAN = 720;                                    // minutes on the scale: twelve hours from now
const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const smooth = (t) => t * t * (3 - 2 * t);
const timeline = () => (document.timeline && document.timeline.currentTime != null ? document.timeline.currentTime : performance.now());

const scene = box ? lazyScene(box, () => import("./table.js"), { lazy: { timeout: 400 } }) : null;

/* ---- the motion switch: it says what a click will do ------------------------------------------------ */
function showMotion() {
  if (!motion) return;
  const paused = motionPaused();
  motionText.textContent = paused ? "Play motion" : "Pause motion";
  motion.classList.toggle("is-paused", paused);
  if (play) {
    play.disabled = paused;
    if (paused && !lapse.on) playText.textContent = "Plays when motion is on";
    else if (!lapse.on) playText.textContent = "Next 12 hours";
  }
}
if (motion) motion.addEventListener("click", () => { setMotionPaused(!motionPaused()); if (motionPaused()) stop(); showMotion(); });

/* ---- the water of an hour, in words ------------------------------------------------------------------ */
const readouts = [...document.querySelectorAll("[data-tide]")].map((el) => ({
  el, gauge: el.querySelector(".gauge"), h: el.querySelector("[data-tide-h]"),
  way: el.querySelector("[data-tide-way]"), time: el.querySelector("[data-tide-time]"),
}));
const clockLabel = box && box.querySelector(".tideclock");
const clock = clockLabel && { time: clockLabel.querySelector("[data-clock-time]"), h: clockLabel.querySelector("[data-clock-h]"), way: clockLabel.querySelector("[data-clock-way]") };
function wayOf(hour) {
  const rate = tide.height(hour + 0.25) - tide.height(hour - 0.25);
  if (Math.abs(rate) < 0.07) return tide.height(hour) > 2.5 ? "high water" : "low water";
  return rate > 0 ? "rising" : "falling";
}
function say(minutes) {
  const hour = NOW + minutes / 60, metres = tide.height(hour), lapse = minutes > 0;
  const h = metres.toFixed(1) + " m", way = wayOf(hour), at = tide.clock(hour);
  for (const r of readouts) {
    r.h.textContent = h;
    r.way.textContent = way;
    r.time.textContent = lapse ? at : at + " now";
    if (r.gauge) r.gauge.style.setProperty("--level", clamp(metres / 6).toFixed(3));
    r.el.classList.toggle("is-lapse", lapse);
  }
  if (clock) {
    clock.time.textContent = at;
    clock.h.textContent = h;
    clock.way.textContent = lapse ? way : "now";
    clockLabel.classList.toggle("is-lapse", lapse);
  }
  if (range) {
    range.value = String(minutes);
    range.setAttribute("aria-valuetext", (lapse ? at : at + " now") + ", water " + h + ", " + way);
    range.style.setProperty("--at", (minutes / SPAN).toFixed(4));
  }
  if (slip) slip.classList.toggle("is-open", lapse && tide.safe(hour));
  if (scene) scene.setData([metres / 6, lapse ? 1 : 0]);   /* another hour: the lamp lights the banks */
}

/* the safe window on the scale: where daylight, wind and tide hold together in the next twelve hours */
if (scrubber) {
  let from = -1, to = -1;
  for (let m = 0; m <= SPAN; m += 5) if (tide.safe(NOW + m / 60)) { if (from < 0) from = m; to = m; }
  if (from >= 0) {
    scrubber.style.setProperty("--win-a", (from / SPAN).toFixed(4));
    scrubber.style.setProperty("--win-b", (to / SPAN).toFixed(4));
  }
}

/* ---- the reader's hour: the scale, and "Next 12 hours" that plays it -------------------------------- */
const RUN = 11000, HOLD = 1200, BACK = 1500;
const lapse = { on: false, t0: 0, frame: 0, back: null, from: 0 };
function setPlay(on) {
  lapse.on = on;
  if (!play) return;
  play.setAttribute("aria-pressed", String(on));
  playText.textContent = on ? "Back to now" : (motionPaused() ? "Plays when motion is on" : "Next 12 hours");
}
function tick() {
  lapse.frame = 0;
  if (!lapse.on) return;
  const now = timeline(), t = now - lapse.t0;
  let minutes;
  if (lapse.back) {                                              /* back to now, easing */
    const k = smooth(clamp((now - lapse.back.at) / BACK));
    minutes = lapse.back.from * (1 - k);
    if (k >= 1) { setPlay(false); say(0); return; }
  } else if (t < RUN) {
    minutes = lapse.from + (SPAN - lapse.from) * smooth(clamp(t / RUN));
  } else {
    minutes = SPAN;
    if (t > RUN + HOLD) lapse.back = { at: now, from: SPAN };
  }
  say(Math.round(minutes));
  lapse.frame = requestAnimationFrame(tick);
}
function start(from = 0) {
  if (lapse.on || motionPaused() || reduce.matches) return;
  setPlay(true);
  lapse.t0 = timeline();
  lapse.from = from;
  lapse.back = null;
  lapse.frame = requestAnimationFrame(tick);
}
function stop() {
  if (!lapse.on) return;
  cancelAnimationFrame(lapse.frame);
  setPlay(false);
  say(0);
}
if (play) {
  play.addEventListener("click", () => {
    if (lapse.on && !lapse.back) { lapse.back = { at: timeline(), from: Number(range.value) }; return; }
    if (lapse.on) return;
    start(Number(range.value) >= SPAN ? 0 : Number(range.value));
  });
}
if (range) {
  range.addEventListener("input", () => {
    if (lapse.on) { cancelAnimationFrame(lapse.frame); setPlay(false); }
    say(Number(range.value));
  });
}
say(0);
showMotion();

if (scene) {
  /* live: the drawn sheet steps aside under the 3D one, the scale is offered, and on the first view the
     next twelve hours play once by themselves */
  let firstRun = false;
  new MutationObserver(() => {
    const live = box.getAttribute("data-scene") === "live";
    hero.classList.toggle("is-3d", live);
  }).observe(box, { attributes: true, attributeFilter: ["data-scene"] });
  box.addEventListener("tablebuilt", () => {
    if (scrubber) scrubber.hidden = false;
    if (play) play.hidden = reduce.matches;
    showMotion();
    if (firstRun || reduce.matches || motionPaused()) return;
    firstRun = true;
    const r = hero.getBoundingClientRect();
    if (r.bottom < window.innerHeight * 0.4 || document.hidden) return;   /* nobody is looking at it */
    setTimeout(() => { if (Number(range.value) === 0) start(0); }, 500);
  });
  reduce.addEventListener("change", () => { if (reduce.matches) stop(); if (play) play.hidden = reduce.matches; });
  /* nobody watching (scrolled away, another tab): a running hour stops and the water is back at now */
  new IntersectionObserver((entries) => { if (!entries[0].isIntersecting) stop(); }).observe(hero);
  document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });

  /* ---- the scroll: the relief sinks back into the print as the hero leaves ----------------------------- */
  let frame = 0;
  const leave = () => {
    frame = 0;
    const r = hero.getBoundingClientRect();
    scene.setProgress(clamp(-r.top / (r.height * 0.85)));
  };
  addEventListener("scroll", () => { if (!frame) frame = requestAnimationFrame(leave); }, { passive: true });
  leave();
}
