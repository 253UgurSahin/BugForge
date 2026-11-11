/* Tidewatch, level 4, the layer it shares with level 3 (Expressive): depth in the interface and a
   story told by the scroll. No WebGL here; the scene is hero.js.
   - Real springs: one spring, worked out from the duration tokens, becomes --ease-spring for the
     whole page (a CSS linear() curve); the pencil fixes, the lamp switch and the icons settle on it.
   - Paper with depth (the scene kit's depth.js): the slip on the chart and the passage cards lean
     toward the hand and lift their figures off the paper; the three margin notes open like pages.
   - The week as a scroll story: the tide section stays on screen while a pencil cursor runs through
     the seven days; it reads the height off the curve, names the day and the hour, and says when it
     is inside a safe window, whose hatch and time light up as it passes.
   - The curve morphs: Height or Stream. The stream is the rate at which the water rises and falls,
     drawn as knots of flood above the slack-water line and ebb below it; the line springs from one
     shape to the other, the dashed 2 m line becomes slack water, and the scale changes with it.
   Reduced motion: no springs, the cards lie flat, the notes are open, the section scrolls as a
   normal one and the cursor rests at "now". */
import { mount as mountDepth } from "../../vendor/scenes/depth.js";
import { readTide, NOW } from "./tide.js";

const root = document.documentElement;
const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const style = getComputedStyle(root);
const ms = (name) => { const v = style.getPropertyValue(name).trim(); return /ms$/.test(v) ? parseFloat(v) : parseFloat(v) * 1000; };

/* ---- a real spring, as a CSS curve ------------------------------------------------------------ */
export function spring(duration, bounce = 0.2) {
  const zeta = 1 - Math.min(Math.max(bounce, 0.05), 0.6);   // damping: 1 would not overshoot
  const w = (2 * Math.PI) / (duration / 1000);                // one swing in about `duration`
  const wd = w * Math.sqrt(1 - zeta * zeta);
  const at = (t) => 1 - Math.exp(-zeta * w * t) * (Math.cos(wd * t) + ((zeta * w) / wd) * Math.sin(wd * t));
  const settle = Math.log(1000 * (1 + (zeta * w) / wd)) / (zeta * w);
  const points = Array.from({ length: 41 }, (_, i) => (i === 40 ? 1 : +at((settle * i) / 40).toFixed(3)));
  const easing = `linear(${points.join(", ")})`;
  const supported = window.CSS && CSS.supports && CSS.supports("transition-timing-function", easing);
  return { duration: Math.round(settle * 1000), easing: supported ? easing : null };
}
const bouncy = spring(ms("--duration-slow") || 320, 0.32);
if (bouncy.easing && !reduce.matches) root.style.setProperty("--ease-spring", bouncy.easing);

/* ---- paper with depth ------------------------------------------------------------------------- */
const main = document.querySelector("main");
if (main) mountDepth(main, { tilt: 5, lift: 8, raise: 14, ease: 0.5, fold: 64, foldTime: 1.05, foldStagger: 0.14 });

/* ---- the curve morphs: height, or the stream it makes ------------------------------------------- */
const figure = document.getElementById("tide-chart");
const morph = { mix: 0, to: 0, v: 0, frame: 0, last: 0, listeners: [] };
if (figure) {
  const curve = figure.querySelector(".tide__curve"), area = figure.querySelector(".tide__area");
  const need = figure.querySelector(".tide__need"), desc = figure.querySelector("desc");
  const nums = (curve.getAttribute("d").match(/-?\d+(?:\.\d+)?/g) || []).map(Number);
  const xs = [], hy = [];
  for (let i = 0; i + 1 < nums.length; i += 2) { xs.push(nums[i]); hy.push(nums[i + 1]); }
  // the rate of rise and fall, metres an hour (a point every quarter of an hour), and the stream it
  // drives: knots, flood up and ebb down, 2.6 knots at the strongest (the Wielingen at springs)
  const rate = hy.map((_, i) => {
    const a = Math.max(0, i - 1), b = Math.min(hy.length - 1, i + 1);
    return ((hy[a] - hy[b]) / 100) / (((xs[b] - xs[a]) || 2.5) / 10);
  });
  const peak = Math.max(...rate.map(Math.abs), 1e-6);
  const KNOTS = 2.6, SLACK = 325;                      // y of slack water; 100 units a knot
  const sy = rate.map((r) => SLACK - (r / peak) * KNOTS * 100);
  const index = (hour) => Math.min(Math.max((hour * 10) / 2.5, 0), xs.length - 1);
  morph.yAt = (hour) => {                              // the y of the curve as it is drawn now
    const f = index(hour), i = Math.floor(f), t = f - i, j = Math.min(i + 1, xs.length - 1);
    const h = hy[i] + (hy[j] - hy[i]) * t, st = sy[i] + (sy[j] - sy[i]) * t;
    return h + (st - h) * morph.mix;
  };
  morph.streamAt = (hour) => (rate[Math.round(index(hour))] / peak) * KNOTS;
  const descs = { height: desc ? desc.textContent : "", stream: "The tidal stream at Vlissingen over the same week: flood above the slack-water line, ebb below it, up to 2.6 knots at springs. Safe windows are hatched." };
  const draw = () => {
    const m = morph.mix;
    let d = "";
    for (let i = 0; i < xs.length; i++) d += (i ? "L" : "M") + xs[i] + " " + (hy[i] + (sy[i] - hy[i]) * m).toFixed(1);
    curve.setAttribute("d", d);
    area.setAttribute("d", d + "L1680 650L0 650Z");
    need.setAttribute("d", `M0 ${(400 + (SLACK - 400) * m).toFixed(1)}H1680`);
    for (const fn of morph.listeners) fn();
  };
  const step = (now) => {
    morph.frame = 0;
    const dt = morph.last ? Math.min(0.05, (now - morph.last) / 1000) : 1 / 60;
    morph.last = now;
    // a spring with a little give (stiffness 120, damping 15): it overshoots by a few percent
    const force = 120 * (morph.to - morph.mix) - 15 * morph.v;
    morph.v += force * dt;
    morph.mix += morph.v * dt;
    if (Math.abs(morph.to - morph.mix) < 0.001 && Math.abs(morph.v) < 0.01) { morph.mix = morph.to; morph.v = 0; }
    draw();
    if (morph.mix !== morph.to || morph.v) morph.frame = requestAnimationFrame(step); else morph.last = 0;
  };
  const buttons = [...document.querySelectorAll(".seg__btn")];
  const choose = (kind) => {
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.curve === kind)));
    figure.setAttribute("data-curve", kind);
    if (desc) desc.textContent = descs[kind];
    morph.to = kind === "stream" ? 1 : 0;
    if (reduce.matches) { morph.mix = morph.to; morph.v = 0; draw(); return; }
    if (!morph.frame) morph.frame = requestAnimationFrame(step);
  };
  buttons.forEach((b) => b.addEventListener("click", () => choose(b.dataset.curve)));
}

/* ---- the week as a scroll story ---------------------------------------------------------------- */
const story = document.getElementById("tide-story");
const tide = readTide();
if (story && tide) {
  const stage = story.querySelector(".story__stage");
  const plot = story.querySelector(".tide__plot");
  const scrub = document.getElementById("tide-scrub");
  const days = [...story.querySelectorAll(".tide__days > span")];
  const windows = [...story.querySelectorAll(".tide__window")];
  const times = [...story.querySelectorAll(".tide__times > span")];
  const out = { day: scrub.querySelector(".scrub__day"), time: scrub.querySelector(".scrub__time"), h: scrub.querySelector(".scrub__h") };
  let frame = 0, near = false, lastText = "", lastDay = -1, lastWindow = -2;

  const show = (hour) => {
    const w = plot.clientWidth, h = plot.clientHeight;
    const metres = tide.height(hour);
    const y = morph.yAt ? morph.yAt(hour) : 600 - metres * 100;
    const stream = morph.mix > 0.5 && morph.streamAt ? morph.streamAt(hour) : null;
    scrub.style.transform = `translateX(${((hour / tide.hours) * w).toFixed(1)}px)`;
    scrub.style.setProperty("--dot-y", `${((y / 650) * h).toFixed(1)}px`);
    scrub.classList.toggle("is-late", hour / tide.hours > 0.8);   // the label flips to the left near the end
    const reading = stream === null ? metres.toFixed(1) + " m " + (tide.rising(hour) ? "↑" : "↓")
      : Math.abs(stream).toFixed(1) + " kn " + (Math.abs(stream) < 0.15 ? "slack" : stream > 0 ? "flood" : "ebb");
    const text = tide.day(hour) + tide.clock(hour) + reading;
    if (text !== lastText) {
      lastText = text;
      out.day.textContent = tide.day(hour);
      out.time.textContent = tide.clock(hour);
      out.h.textContent = reading;
    }
    const inWindow = tide.windowAt(hour);
    scrub.classList.toggle("is-safe", inWindow >= 0);
    if (inWindow !== lastWindow) {
      windows.forEach((el, i) => el.classList.toggle("is-current", i === inWindow));
      lastWindow = inWindow;
    }
    const day = Math.min(6, Math.floor(hour / 24));
    if (day !== lastDay) {
      days.forEach((el, i) => el.classList.toggle("is-scrub", i === day));
      times.forEach((el, i) => el.classList.toggle("is-scrub", i === day));
      lastDay = day;
    }
  };

  let lastHour = NOW;
  morph.listeners.push(() => show(lastHour));     // the cursor rides the curve while it morphs
  const update = () => {
    frame = 0;
    const box = story.getBoundingClientRect();
    const run = Math.max(box.height - stage.offsetHeight, 1);
    const p = root.hasAttribute("data-story") ? clamp(-box.top / run) : 0;
    lastHour = NOW + p * (tide.hours - 0.5 - NOW);
    show(lastHour);
  };
  const request = () => { if (near && !frame) frame = requestAnimationFrame(update); };
  // The stage is pinned (level.css, html[data-story]) only when it fits on the screen with room to
  // spare, and never for reduced motion: then the section simply scrolls and the cursor rests.
  const measure = () => {
    const fits = stage.offsetHeight + 64 <= window.innerHeight;
    if (fits && !reduce.matches) root.setAttribute("data-story", "on"); else root.removeAttribute("data-story");
    story.style.setProperty("--story-stage", stage.offsetHeight + "px");
    request();
  };

  new IntersectionObserver(([entry]) => { near = entry.isIntersecting; request(); }, { rootMargin: "20% 0px" }).observe(story);
  new ResizeObserver(measure).observe(stage);
  window.addEventListener("resize", measure, { passive: true });
  window.addEventListener("scroll", request, { passive: true });
  reduce.addEventListener("change", measure);
  measure();
  near = true;
  update();
}
