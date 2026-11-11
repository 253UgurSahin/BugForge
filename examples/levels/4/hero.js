/* Tidewatch, level 4: Showpiece. The page's side of the chart table; the scene itself is table.js.

   - The scene is mounted lazily on the hero's chart area (lazyScene): nothing of three.js loads before
     the hero is near the screen and the page has a quiet moment, and the drawn chart of level 3 is its
     poster: it shows until the first frame, and for good without WebGL, for reduced data or if the scene
     fails. Once the scene is live the hero gets .is-3d, so the drawn lamp steps aside.
   - The water of the hour. The page's own tide curve (tide.js) gives the height at "now", Tuesday 09:40,
     and that is the scene's data: the sheet of water stands at it. The slip says it, and on a phone the
     corner of the chart: the height, rising or falling, and the hour. When the water floods in, at the
     end of the opening, the figure rises with it.
   - "Next 12 hours" is a time-lapse the reader starts, never a clock that runs by itself: the hour runs
     from now to 21:40 in fourteen seconds, the water rises over the banks to high water at 14:26 and
     falls until they dry again; the readout names the hour and says it is not now; the slip's window
     lights while the hour is inside it. At the end, or with "Back to now", it comes back to 09:40.
   - As the hero scrolls away the scene gets its progress: the relief sinks back into the print and the
     sheet slides back.
   - One "Pause motion" button (motionToggle) stops the scene and depth.js, and is remembered. With
     reduced motion the scene is one still frame, so the button and the time-lapse are not offered. */
import { lazyScene, motionToggle } from "../../vendor/scenes/lazy.js";
import { readTide, NOW } from "./tide.js";

const root = document.documentElement;
const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
const hero = document.querySelector(".hero");
const box = document.getElementById("hero-scene");
const slip = hero && hero.querySelector(".hero__slip");
const play = document.getElementById("tide-play");
const playText = play && play.querySelector("[data-play-text]");
const tide = readTide();
const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const smooth = (t) => t * t * (3 - 2 * t);

const scene = box ? lazyScene(box, () => import("./table.js"), { lazy: { timeout: 400 } }) : null;
motionToggle(document.getElementById("motion"));

/* ---- the water of the hour, in words ------------------------------------------------------------- */
const readouts = [...document.querySelectorAll("[data-tide]")].map((el) => ({
  el, gauge: el.querySelector(".gauge"), h: el.querySelector("[data-tide-h]"),
  way: el.querySelector("[data-tide-way]"), time: el.querySelector("[data-tide-time]"),
}));
function wayOf(hour) {
  const rate = tide.height(hour + 0.25) - tide.height(hour - 0.25);
  if (Math.abs(rate) < 0.07) return tide.height(hour) > 2.5 ? "high water" : "low water";
  return rate > 0 ? "rising" : "falling";
}
function say(hour, metres = tide.height(hour), lapse = false) {
  for (const r of readouts) {
    r.h.textContent = metres.toFixed(1) + " m";
    r.way.textContent = wayOf(hour);
    r.time.textContent = tide.clock(hour) + (lapse ? "" : " now");
    r.gauge.style.setProperty("--level", clamp(metres / 6).toFixed(3));
    r.el.classList.toggle("is-lapse", lapse);
  }
  if (slip) slip.classList.toggle("is-open", lapse && tide.safe(hour));
}
say(NOW);

if (scene) {
  scene.setData([tide.height(NOW) / 6]);

  /* live: the drawn lamp steps aside, and the figure rises with the water as it floods in */
  let wasLive = false;
  new MutationObserver(() => {
    const live = box.getAttribute("data-scene") === "live";
    hero.classList.toggle("is-3d", live);
    if (live && !wasLive && !reduce.matches && root.getAttribute("data-motion") !== "paused") rise();
    wasLive = live;
  }).observe(box, { attributes: true, attributeFilter: ["data-scene"] });
  const timeline = () => (document.timeline && document.timeline.currentTime != null ? document.timeline.currentTime : performance.now());
  function rise() {
    const start = timeline() + 1250, end = start + 1550, target = tide.height(NOW);
    const step = () => {
      const k = smooth(clamp((timeline() - start) / (end - start)));
      if (lapse.on) return;
      say(NOW, target * (0.15 + 0.85 * k));
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  box.addEventListener("tablebuilt", () => { if (play && !reduce.matches) play.hidden = false; });

  /* ---- "Next 12 hours": the reader's own time-lapse ----------------------------------------------- */
  const HOURS = 12, RUN = 14000, HOLD = 1400, BACK = 1600;
  const lapse = { on: false, t0: 0, frame: 0, back: null };
  function setPlay(on) {
    lapse.on = on;
    play.setAttribute("aria-pressed", String(on));
    playText.textContent = on ? "Back to now" : "Next 12 hours";
  }
  function show(hour, isLapse) {
    scene.setData([tide.height(hour) / 6]);
    say(hour, tide.height(hour), isLapse);
  }
  function tick(now) {
    lapse.frame = 0;
    if (!lapse.on) return;
    const t = now - lapse.t0;
    let hour;
    if (lapse.back !== null) {                                   /* back to now, easing */
      const k = smooth(clamp((now - lapse.back.at) / BACK));
      hour = lapse.back.from + (NOW - lapse.back.from) * k;
      if (k >= 1) { setPlay(false); show(NOW, false); return; }
    } else if (t < RUN) {
      hour = NOW + HOURS * smooth(clamp(t / RUN)) ;
    } else {
      hour = NOW + HOURS;
      if (t > RUN + HOLD) lapse.back = { at: now, from: hour };
    }
    show(hour, true);
    lapse.frame = requestAnimationFrame(tick);
  }
  function stop() {
    if (!lapse.on) return;
    cancelAnimationFrame(lapse.frame);
    setPlay(false);
    show(NOW, false);
  }
  if (play) {
    play.addEventListener("click", () => {
      if (lapse.on && lapse.back === null) {                     /* "Back to now": ease home */
        const t = performance.now() - lapse.t0;
        lapse.back = { at: performance.now(), from: NOW + HOURS * smooth(clamp(t / RUN)) };
        return;
      }
      if (lapse.on) return;
      setPlay(true);
      lapse.t0 = performance.now();
      lapse.back = null;
      lapse.frame = requestAnimationFrame(tick);
    });
    /* motion switched off, or less motion asked for: no time-lapse, the water stands at now */
    new MutationObserver(() => {
      const paused = root.getAttribute("data-motion") === "paused";
      if (paused) stop();
      play.disabled = paused;
    }).observe(root, { attributes: true, attributeFilter: ["data-motion"] });
    play.disabled = root.getAttribute("data-motion") === "paused";
    reduce.addEventListener("change", () => { if (reduce.matches) { stop(); play.hidden = true; } });
    /* nobody watching (scrolled away, another tab): the time-lapse stops and the water is back at now */
    new IntersectionObserver((entries) => { if (!entries[0].isIntersecting) stop(); }).observe(hero);
    document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
  }

  /* ---- the scroll: the relief sinks back and the sheet slides back as the hero leaves -------------- */
  let frame = 0;
  const leave = () => {
    frame = 0;
    const r = hero.getBoundingClientRect();
    scene.setProgress(clamp(-r.top / (r.height * 0.85)));
  };
  addEventListener("scroll", () => { if (!frame) frame = requestAnimationFrame(leave); }, { passive: true });
  leave();
}
