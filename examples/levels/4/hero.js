/* Tidewatch, level 4: Showpiece. The chart table in three dimensions.

   The hero chart is a sheet of paper lying on the chart table, seen across the table at a slant
   (CSS 3D on #hero-scene, the pose is set in level.css). Its depth area comes alive: the scene kit's
   contour.js draws the sea bed as living depth contours in the chart's own inks (the tokens on the
   container, level.css), kept to the water by a mask of the coast, under the printed land, names,
   buoys and the pencilled course of the same SVG. What the scene replaces (depth tints, contours,
   soundings, bank names) is the SVG's data-scene-poster: it shows until the first frame, and for good
   without WebGL, when the scene fails, or for reduced data.

   - The lamp hangs over the table: its pool of light follows the pointer across the sheet, and under
     it the sea bed rises in a knoll that the contours part around (the stage's pointer, mapped onto
     the slanted sheet exactly, so the knoll is under the hand and not beside it).
   - Scrolling away, the sheet leans further back and the chart travels and zooms (setProgress with
     the hero's progressOf), so the first screen has depth while it leaves.
   - The tide of the hour is the scene's data, read off the page's own tide curve (tide.js): the
     chart's clock runs on from "now", setData raises the banks as the water falls and drowns them as
     it rises, and the slip names the hour and the water, so the chart breathes with the tide.
   - One "Pause motion" button (motionToggle) stops the scene, the lamp and the lean, and remembers it.
   Nothing of three.js loads before the hero is near the screen and the page is idle (lazyScene).
   Reduced motion: no lamp travel, no lean; the stage draws one still frame. */
import { lazyScene, motionToggle } from "../../vendor/scenes/lazy.js";
import { readTide, NOW } from "./tide.js";

const root = document.documentElement;
const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
const hero = document.querySelector(".hero");
const sheet = document.getElementById("hero-scene");
const lamp = sheet && sheet.querySelector(".sheet__lamp");
const shade = sheet && sheet.querySelector(".sheet__shade");
const under = hero && hero.querySelector(".hero__under");
const calm = () => reduce.matches || root.getAttribute("data-motion") === "paused";
const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const tokenOf = (el, name) => getComputedStyle(el).getPropertyValue(name).trim();

/* ---- the scene ------------------------------------------------------------------------------ */
const chart = sheet ? lazyScene(sheet, () => import("../../vendor/scenes/contour.js"), {
  levels: 22,            // a dense chart: a line every 0.07 of the bed's range, like 1 m contours
  lineWidth: 0.85,       // fine pen
  indexEvery: 5,         // every fifth line inked heavier, as the 5 m and 10 m lines of a chart
  indexStrength: 0.9,
  tint: 2.6,             // shoal water tinted in the second hue, a shade deeper per band
  relief: 1.15,          // illuminated contours: the side away from the lamp in heavier ink
  marks: true,           // dots on the tops, crosses in the hollows: the chart's own soundings
  grid: true,            // registration crosses of the graticule
  lift: 2,               // the knoll under the lamp: about ten contours high
  speed: 0.7,            // the bed drifts slowly
  tide: 0.45,            // and the level creeps, as the water does
  scale: 0.8,            // banks and gullies the size of the Westerschelde's at this scale
  calm: "none",          // the area's own mask already clears the words
  fade: 1400,            // the printed banks dissolve slowly into the living ones
  lazy: { timeout: 700 },
}) : null;
motionToggle(document.getElementById("motion"));

/* ---- the sheet's pose, and where a point of the screen lies on the sheet --------------------- */
let toSheet = null;     // 3x3: screen point (relative to the hero) -> sheet pixel (homogeneous)
let lean = 0;           // extra degrees the sheet leans back while the hero scrolls away
const pose = { tilt: 0, turn: 0, lean: 0 };

function readPose() {
  pose.tilt = parseFloat(tokenOf(hero, "--sheet-tilt")) || 0;
  pose.turn = parseFloat(tokenOf(hero, "--sheet-turn")) || 0;
  pose.lean = parseFloat(tokenOf(hero, "--sheet-lean")) || 0;
  const home = tokenOf(hero, "--lamp-home").split(/\s+/).map(Number);
  if (home.length === 2 && home.every(Number.isFinite)) light.home = home;
}

function place() {
  if (!sheet) return;
  const tilt = pose.tilt + lean * pose.lean;
  const transform = `rotateX(${tilt.toFixed(3)}deg) rotateZ(${pose.turn}deg)`;
  sheet.style.transform = transform;
  if (under) under.style.transform = transform;   // the sheet's shadow on the table, in the same plane
  // The whole map from the sheet's own pixels to the hero's: the parent's perspective about its
  // origin, the sheet's place, its transform about its origin. With z = 0 on the sheet that is a
  // plane-to-plane map, a 3x3 matrix; its inverse finds the sheet point under the pointer.
  const hs = getComputedStyle(hero), ss = getComputedStyle(sheet);
  const P = parseFloat(hs.perspective) || 0;
  const [px, py] = hs.perspectiveOrigin.split(" ").map(parseFloat);
  const [ox, oy] = ss.transformOrigin.split(" ").map(parseFloat);
  let m = new DOMMatrix();
  if (P > 0) {
    const persp = new DOMMatrix();
    persp.m34 = -1 / P;
    m = m.translate(px, py).multiply(persp).translate(-px, -py);
  }
  m = m.translate(sheet.offsetLeft + ox, sheet.offsetTop + oy)
    .multiply(new DOMMatrix(transform)).translate(-ox, -oy);   // the pose, not the computed style: an entrance may be running
  toSheet = invert3([m.m11, m.m21, m.m41, m.m12, m.m22, m.m42, m.m14, m.m24, m.m44]);
}

function invert3(a) {
  const [a0, a1, a2, a3, a4, a5, a6, a7, a8] = a;
  const c0 = a4 * a8 - a5 * a7, c1 = a5 * a6 - a3 * a8, c2 = a3 * a7 - a4 * a6;
  const det = a0 * c0 + a1 * c1 + a2 * c2;
  if (!det) return null;
  return [c0, a2 * a7 - a1 * a8, a1 * a5 - a2 * a4, c1, a0 * a8 - a2 * a6, a2 * a3 - a0 * a5,
    c2, a1 * a6 - a0 * a7, a0 * a4 - a1 * a3].map((v) => v / det);
}

// clientX, clientY -> { u, v } across the sheet, 0..1 from its top left (outside the sheet: beyond)
function sheetPoint(x, y) {
  if (!toSheet) return null;
  const box = hero.getBoundingClientRect();
  const X = x - box.left, Y = y - box.top, t = toSheet;
  const w = t[6] * X + t[7] * Y + t[8];
  if (!w) return null;
  return { u: (t[0] * X + t[1] * Y + t[2]) / w / sheet.offsetWidth, v: (t[3] * X + t[4] * Y + t[5]) / w / sheet.offsetHeight };
}

/* ---- the lamp: its pool follows the hand across the sheet, eased like a lamp on a swinging arm -- */
const light = { u: 0.62, v: 0.5, tu: 0.62, tv: 0.5, vu: 0, vv: 0, home: [0.62, 0.5] };
let lampFrame = 0, lampLast = 0;
function aimLamp(u, v) {
  light.tu = clamp(u, -0.1, 1.1);
  light.tv = clamp(v, -0.1, 1.1);
  if (!lampFrame && !calm()) lampFrame = requestAnimationFrame(swing);
}
function drawLamp() {
  const w = sheet.offsetWidth, h = sheet.offsetHeight;
  const t = `translate(${(light.u * w).toFixed(1)}px, ${(light.v * h).toFixed(1)}px)`;
  if (lamp) lamp.style.transform = t;
  if (shade) shade.style.transform = t;
}
function swing(now) {
  lampFrame = 0;
  const dt = lampLast ? Math.min(0.05, (now - lampLast) / 1000) : 1 / 60;
  lampLast = now;
  // a critically damped spring: no overshoot, about 0.6 s to settle
  const omega = 7, e = Math.exp(-omega * dt);
  let moving = false;
  for (const [k, vk, tk] of [["u", "vu", "tu"], ["v", "vv", "tv"]]) {
    const c = light[k] - light[tk], kk = light[vk] + omega * c;
    light[k] = light[tk] + (c + kk * dt) * e;
    light[vk] = (light[vk] - omega * kk * dt) * e;
    if (Math.abs(light[k] - light[tk]) > 0.0005 || Math.abs(light[vk]) > 0.001) moving = true;
  }
  drawLamp();
  if (moving && !calm() && !document.hidden) lampFrame = requestAnimationFrame(swing);
  else lampLast = 0;
}

/* ---- the tide of the hour: the scene's data, and the line on the slip that names it ------------
   The chart's hour runs on from "now" at an hour every few seconds, through the week the tide
   curve shows; setData gets how far the water has fallen, so the banks dry out on the ebb and
   drown on the flood. Reduced motion or paused: the hour stands at now. */
const tide = readTide();
const gauge = document.getElementById("slip-tide");
const SECONDS_AN_HOUR = 3.2;
let hour = NOW, tideFrame = 0, tideLast = 0, shown = "";
function tell() {
  const metres = tide.height(hour);
  if (chart) chart.setData([1 - tide.level(hour)]);
  const text = tide.clock(hour).slice(0, 4) + "0";   // to the ten minutes, so it reads calmly
  if (gauge && text !== shown) {
    shown = text;
    gauge.querySelector(".gauge__h").textContent = metres.toFixed(1) + " m";
    gauge.querySelector(".gauge__time").textContent = text;
    gauge.querySelector(".gauge__way").textContent = tide.rising(hour) ? "rising" : "falling";
    gauge.style.setProperty("--level", tide.level(hour).toFixed(3));
  }
}
function runTide(now) {
  tideFrame = 0;
  const dt = tideLast ? Math.min(0.1, (now - tideLast) / 1000) : 0;
  tideLast = now;
  hour += dt / SECONDS_AN_HOUR;
  if (hour > tide.hours - 1) hour = NOW;
  tell();
  startTide();
}
function startTide() {
  // only while the scene is there to show it: on the poster the slip keeps the hour of "now"
  const live = chart && chart.scene && !chart.scene.stage.failed;
  if (tideFrame || !live || calm() || document.hidden || !heroSeen) { tideLast = 0; return; }
  tideFrame = requestAnimationFrame(runTide);
}
let heroSeen = true;

/* ---- wiring --------------------------------------------------------------------------------- */
if (sheet) {
  readPose();
  [light.u, light.v] = [light.tu, light.tv] = light.home;
  place();
  drawLamp();
  const onResize = () => { readPose(); place(); aimLamp(light.home[0], light.home[1]); drawLamp(); };
  new ResizeObserver(onResize).observe(hero);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", onResize);

  // Scrolling away: the sheet leans back. Only while the hero is on screen, and not when still.
  let onScreen = true, scrollFrame = 0;
  const leanNow = () => {
    scrollFrame = 0;
    const box = hero.getBoundingClientRect();
    lean = calm() ? 0 : clamp(-box.top / Math.max(box.height * 0.8, 1));
    place();
  };
  window.addEventListener("scroll", () => { if (onScreen && !scrollFrame) scrollFrame = requestAnimationFrame(leanNow); }, { passive: true });
  new IntersectionObserver(([entry]) => {
    onScreen = heroSeen = entry.isIntersecting;
    if (heroSeen) startTide();
  }).observe(hero);
  document.addEventListener("visibilitychange", startTide);
  // the motion switch (lazy.js) and reduced motion: the clock and the lamp stop where they are
  new MutationObserver(() => { if (!calm()) startTide(); }).observe(root, { attributes: true, attributeFilter: ["data-motion"] });
  reduce.addEventListener("change", () => { hour = NOW; tell(); startTide(); });
  tell();
  startTide();

  // The pointer, mapped onto the slanted sheet. Registered once the scene is there, so it runs
  // after the stage's own listener and puts the knoll where the hand really is.
  const follow = (x, y) => {
    const at = sheetPoint(x, y);
    if (!at) return;
    const inside = at.u >= 0 && at.u <= 1 && at.v >= 0 && at.v <= 1;
    const live = chart && chart.scene;
    if (live) {
      if (inside) live.setPointer(at.u * 2 - 1, 1 - at.v * 2);
      else live.stage.pointer.inside = false;
    }
    if (inside) aimLamp(at.u, at.v); else aimLamp(light.home[0], light.home[1]);
  };
  const onMove = (event) => follow(event.clientX, event.clientY);
  const onTouch = (event) => { const t = event.touches[0]; if (t) follow(t.clientX, t.clientY); };
  window.addEventListener("pointermove", onMove, { passive: true });
  window.addEventListener("touchstart", onTouch, { passive: true });
  window.addEventListener("touchmove", onTouch, { passive: true });
  document.documentElement.addEventListener("pointerleave", () => aimLamp(light.home[0], light.home[1]), { passive: true });

  if (chart) {
    chart.ready.then((live) => {
      if (!live) return;
      // re-register after the stage's listeners, so ours has the last word on the pointer
      for (const [type, fn] of [["pointermove", onMove], ["touchstart", onTouch], ["touchmove", onTouch]]) {
        window.removeEventListener(type, fn);
        window.addEventListener(type, fn, { passive: true });
      }
      // depth while scrolling: the hero's own progress through the viewport drives the travel
      live.stage.onFrame(() => live.setProgress(clamp((live.stage.progressOf(hero) - 0.5) * 2)));
      startTide();
    });
  }
}
