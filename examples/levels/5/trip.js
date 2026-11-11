/* Tidewatch, level 5: Cinematic. The trip down the pencil line, directed by the scene kit's journey.js.

   The hero is the first chapter of a journey through one 3D scene (table.js: the chart table). The
   stage stays pinned while the chapters scroll over it; the camera flies along the course in five
   moves: the whole sheet under the lamp; down to the pier head at 14:20 with the water at its highest;
   across the roads to the 14:40 fix as the ebb starts; low down the Wielingen between the buoys, the
   sounder reading the water under the keel; then up over the whole sheet for the landfall, by night.
   - The journey's chapter event lights the current slip and the matching mark in the strip of tools.
   - The data hook: the scene's setData gets the page's own numbers, read from the page itself: the
     water from the tide table (high and low waters, joined as a tide curve joins them), the wind from
     the day's reading (17 kn SW, easing to 12 kn by 18:00). The water at each chapter's hour is the
     level of the sheet of water, so the banks dry as the passage goes on; the wind turns and stirs
     the points over the water.
   - While nobody scrolls, the hero's clock runs on from "now" (09:40) toward the casting off: the
     tide rises over the banks, the window opens at 10:58 and its band lights up along the course; the
     slip says the hour and the water.
   - Callouts follow the buoys and fixes as the camera passes them; the sounder rides with the boat.
   - Tools: "Plain chart" (the drawn chart instead of the 3D, Alt+Shift+C), "Tide table" (Alt+Shift+T),
     and the kit's motionToggle, which pauses the scene and depth.js and is remembered.
   Nothing of three.js loads before the page is idle (lazyScene). Reduced motion: no pin and no trip;
   each chapter shows a still of its own view beside its text, and the clock stands at now. Without
   WebGL the drawn chart stays pinned under the chapters. */
import { lazyScene, motionToggle } from "../../vendor/scenes/lazy.js";
import { mount as mountDepth } from "../../vendor/scenes/depth.js";

const section = document.getElementById("trip");
const root = document.documentElement;
const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };

/* ---- the page's own numbers ------------------------------------------------------------------ */
const toHours = (text) => { const m = /(\d{1,2}):(\d{2})/.exec(text || ""); return m ? Number(m[1]) + Number(m[2]) / 60 : NaN; };

/* the high and low waters of the week, from the tide table: hours from Tuesday 00:00, metres */
function readTide() {
  const turns = [];
  document.querySelectorAll("#tide-table tbody tr").forEach((row, day) => {
    row.querySelectorAll("td").forEach((cell) => {
      const time = toHours(cell.querySelector("time") && cell.querySelector("time").textContent);
      const h = parseFloat(cell.querySelector(".tt__h") && cell.querySelector(".tt__h").textContent);
      const kind = cell.getAttribute("data-label") || "";
      if (Number.isFinite(time) && Number.isFinite(h)) turns.push({ t: day * 24 + time, h, high: /high/i.test(kind) });
    });
  });
  turns.sort((a, b) => a.t - b.t);
  // between a high and a low water the tide follows half a cosine, as a tide table is read
  return (t) => {
    if (turns.length < 2) return 2.5;
    let i = turns.findIndex((x) => x.t > t);
    if (i <= 0) i = i === 0 ? 1 : turns.length - 1;
    const a = turns[i - 1], b = turns[i];
    const f = clamp((t - a.t) / (b.t - a.t));
    return a.h + (b.h - a.h) * (1 - Math.cos(Math.PI * f)) / 2;
  };
}

/* the wind: the day's reading and where it is going (the tile "Wind": 17 kn SW, easing to 12 kn by 18:00) */
function readWind() {
  const tile = [...document.querySelectorAll(".stat")].find((el) => /wind/i.test(el.querySelector(".stat__label")?.textContent || ""));
  const now = toHours(document.querySelector(".tide__nowlabel")?.textContent) || 9 + 40 / 60;
  const knots = parseFloat(tile?.querySelector("[data-count]")?.getAttribute("data-count")) || 15;
  const words = tile?.querySelector(".stat__second")?.textContent || "";
  const POINTS = { N: 0, NE: 45, E: 90, SE: 135, S: 180, SW: 225, W: 270, NW: 315 };
  const from = POINTS[(/\b(NE|NW|SE|SW|N|E|S|W)\b/.exec(words) || [])[1]] ?? 225;
  const trend = /(\d+(?:\.\d+)?)\s*kn by (\d{1,2}:\d{2})/.exec(tile?.querySelector(".stat__trend")?.textContent || "");
  const later = trend ? Number(trend[1]) : knots, at = trend ? toHours(trend[2]) : now + 1;
  return { now, from, at: (t) => knots + (later - knots) * clamp((t - now) / (at - now)) };
}

const tide = readTide();
const wind = readWind();
const NOW = wind.now;
const dataAt = (hour) => [tide(hour) / 6, wind.at(hour) / 40, wind.from / 360];
const clock = (hour) => { const m = Math.round((((hour % 24) + 24) % 24) * 60) % 1440; return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0"); };

/* ---- the course and the chapters --------------------------------------------------------------- */
// the pencil line of the chart: the pier head, the fixes at 14:40 and 15:00, on past the chart's edge
const COURSE = [[720, 412], [524, 594], [258.6, 694.4], [96, 756], [-140, 846]];
const legs = COURSE.slice(1).map((p, i) => Math.hypot(p[0] - COURSE[i][0], p[1] - COURSE[i][1]));
const FIX = [0, legs[0], legs[0] + legs[1]];                       // 14:20, 14:40, 15:00 on the chart
const EDGE = legs[0] + legs[1] + legs[2];                           // where the line leaves the chart
const boatAt = (hour) => {                                         // chart units along the line at an hour
  const m = (hour - (14 + 20 / 60)) * 60;
  if (m <= 0) return 0;
  if (m <= 20) return FIX[1] * (m / 20);
  if (m <= 40) return FIX[1] + (FIX[2] - FIX[1]) * ((m - 20) / 20);
  return Math.min(FIX[2] + ((FIX[2] - FIX[1]) / 20) * (m - 40), EDGE + legs[3]);
};
const HOURS = [NOW, 14 + 20 / 60, 14 + 40 / 60, 15, 18 + 10 / 60];
const WINDOW = [10 + 58 / 60, 17 + 1 / 60];                          // today's safe window, as on the slip

// what the scene shows at each chapter (table.js reads it by the journey's progress)
const STORY = [
  { p: 0, hour: NOW, lamp: [1.5, 0.1], lampY: 4.2, reachLamp: 3.6, night: 0, boat: 0, hatch: 0, follow: 1, reach: EDGE + legs[3] },
  { p: 0.25, hour: HOURS[1], lamp: [2.15, -0.45], lampY: 2.6, reachLamp: 2.4, night: 0, boat: boatAt(HOURS[1]) + 2, hatch: 1, follow: 0.35, reach: EDGE + legs[3] },
  { p: 0.5, hour: HOURS[2], lamp: [0.6, 1.2], lampY: 2.4, reachLamp: 2.4, night: 0, boat: boatAt(HOURS[2]), hatch: 1, follow: 0.35, reach: EDGE + legs[3] },
  { p: 0.75, hour: HOURS[3], lamp: [-2.2, 2.4], lampY: 2.2, reachLamp: 2.3, night: 0.12, boat: boatAt(HOURS[3]), hatch: 1, follow: 0.35, reach: EDGE + legs[3] },
  { p: 1, hour: HOURS[4], lamp: [-3.4, 3.0], lampY: 3.6, reachLamp: 3.3, night: 1, boat: EDGE + legs[3], hatch: 1, follow: 0.6, reach: EDGE + legs[3] },
];

// camera keyframes, world units: the sheet is 10 x 9 round the middle, x east, z south, y up
const CHAPTERS = [
  { camera: { position: [-1.3, 8.6, 10.2], target: [-2.0, -0.4, 0.4], fov: 30 },
    phone: { position: [0.6, 13.6, 8.8], target: [0.4, 0, -1.6], fov: 34 },
    still: { position: [0.2, 9.4, 9.6], target: [0.3, -0.2, 0.3], fov: 32 }, alt: "" },
  { camera: { position: [3.5, 1.35, -1.5], target: [1.25, -0.05, 0.55], fov: 36 },
    phone: { position: [3.9, 2.4, -2.1], target: [1.6, -0.2, 0.2], fov: 44 } },
  { camera: { position: [2.25, 1.05, 0.55], target: [-0.15, -0.05, 1.85], fov: 38 },
    phone: { position: [2.6, 1.9, 0.1], target: [0.2, -0.2, 1.6], fov: 46 } },
  { camera: { position: [-0.55, 0.62, 1.7], target: [-3.7, -0.12, 3.15], fov: 40 },
    phone: { position: [-0.2, 1.2, 1.2], target: [-3.2, -0.2, 2.9], fov: 48 } },
  { camera: { position: [0.4, 9.8, 8.2], target: [-0.9, -0.3, 0.6], fov: 32 },
    phone: { position: [0.2, 14.4, 7.6], target: [-0.6, 0, -1.4], fov: 36 } },
].map((c, i) => ({ ...c, progress: STORY[i].p, params: { hour: HOURS[i], night: STORY[i].night, data: dataAt(HOURS[i]) } }));

/* ---- callouts: buoys and fixes, named as the camera passes them ------------------------------ */
const CALLOUTS = [
  { at: [720, 412], text: "<b>14:20</b> off the pier" },
  { at: [580, 398], text: "<b>SG1</b> green", kind: "green" },
  { at: [752, 466], text: "<b>SP2</b> red", kind: "red" },
  { at: [524, 594], text: "<b>14:40</b> fix" },
  { at: [468, 560], text: "<b>W10</b> red", kind: "red" },
  { at: [548, 632], text: "<b>Songa</b> green", kind: "green" },
  { at: [340, 632], text: "<b>W8</b> red", kind: "red" },
  { at: [410, 708], text: "<b>W9</b> green", kind: "green" },
  { at: [258.6, 694.4], text: "<b>15:00</b> fix" },
  { at: [196, 690], text: "<b>W6</b> red", kind: "red" },
  { at: [262, 762], text: "<b>W7</b> green", kind: "green" },
];

function callouts(scene, layer) {
  if (!layer || !scene.onCamera) return () => {};
  const made = CALLOUTS.map((c) => {
    const el = document.createElement("span");
    el.className = "callout" + (c.kind === "red" ? " callout--red" : "");
    el.innerHTML = c.text;
    layer.appendChild(el);
    return { ...c, el, shown: 0 };
  });
  const sounder = document.createElement("span");
  sounder.className = "callout callout--sounder";
  layer.appendChild(sounder);
  const v = { x: 0, y: 0, z: 0 };
  let last = 0, lastText = "";
  const off = scene.onCamera((camera) => {
    const now = performance.now(), dt = Math.min(0.1, (now - last) / 1000 || 0.016);
    last = now;
    const w = layer.clientWidth, h = layer.clientHeight;
    const project = (wx, wy, wz) => {
      v.x = wx; v.y = wy; v.z = wz;
      const p = camera.position, e = camera.matrixWorldInverse.elements, m = camera.projectionMatrix.elements;
      const x = e[0] * wx + e[4] * wy + e[8] * wz + e[12], y = e[1] * wx + e[5] * wy + e[9] * wz + e[13], z = e[2] * wx + e[6] * wy + e[10] * wz + e[14];
      const cw = m[3] * x + m[7] * y + m[11] * z + m[15];
      const cx = (m[0] * x + m[4] * y + m[8] * z + m[12]) / cw, cy = (m[1] * x + m[5] * y + m[9] * z + m[13]) / cw;
      return { x: (cx + 1) / 2 * w, y: (1 - cy) / 2 * h, behind: z > -0.05, dist: Math.hypot(p.x - wx, p.y - wy, p.z - wz) };
    };
    for (const c of made) {
      const [wx, wz] = [(c.at[0] - 500) / 100, (c.at[1] - 450) / 100];
      const s = project(wx, scene.surfaceAt(c.at[0], c.at[1]) + 0.02, wz);
      const inView = !s.behind && s.x > -40 && s.x < w - 140 && s.y > 60 && s.y < h - 90;
      const goal = inView ? smooth(5.2, 3.2, s.dist) : 0;
      c.shown += (goal - c.shown) * Math.min(1, dt * 5);
      if (c.shown < 0.01) { if (c.el.style.opacity !== "0") c.el.style.opacity = "0"; continue; }
      c.el.style.opacity = c.shown.toFixed(3);
      c.el.style.transform = `translate3d(${s.x.toFixed(1)}px, ${(s.y - 7).toFixed(1)}px, 0)`;
    }
    // the sounder rides with the boat: the water under the keel, from the tide and the sea bed
    const b = scene.boatPoint();
    if (b) {
      const s = project(b.world[0], b.world[1] + 0.03, b.world[2]);
      const depth = Math.max(0, scene.level() - scene.bedAt(b.chart[0], b.chart[1]));
      const visible = b.on && !s.behind && s.x > 0 && s.x < w - 120 && s.y > 60 && s.y < h - 90 && s.dist < 6;
      sounder.style.opacity = visible ? "1" : "0";
      if (visible) {
        const text = `<b>${depth.toFixed(1)} m</b> under the keel`;
        if (text !== lastText) { sounder.innerHTML = text; lastText = text; }
        sounder.style.transform = `translate3d(${(s.x + 18).toFixed(1)}px, ${(s.y - 26).toFixed(1)}px, 0)`;
      }
    }
  });
  return () => { off(); layer.textContent = ""; };
}

/* ---- the stage: one journey through the chart table ------------------------------------------ */
const steps = section ? [...section.querySelectorAll("[data-chapter]")] : [];
const marks = section ? [...section.querySelectorAll("[data-go]")] : [];
const gauge = document.getElementById("slip-gauge");
let live = null, current = -1, idle = { hour: NOW, last: 0, frame: 0 };

function showChapter(index) {
  current = index;
  steps.forEach((el, i) => el.toggleAttribute("data-current", i === index));
  marks.forEach((a, i) => { if (i === index) a.setAttribute("aria-current", "step"); else a.removeAttribute("aria-current"); });
}

function tellGauge(hour) {
  if (!gauge) return;
  const h = tide(hour), rising = tide(hour + 0.25) > h;
  gauge.querySelector(".gauge__h").textContent = h.toFixed(1) + " m";
  gauge.querySelector(".gauge__way").textContent = rising ? "rising" : "falling";
  gauge.querySelector(".gauge__time").textContent = clock(hour);
  gauge.style.setProperty("--level", clamp((h - 0.5) / 4.6).toFixed(3));
}

// the readings on the slips, worked out from the same numbers the scene gets
function fillReadings() {
  steps.forEach((step, i) => {
    const hour = HOURS[i];
    if (hour === undefined) return;
    const h = tide(hour), rising = tide(hour + 0.25) > h, top = Math.abs(tide(hour + 0.2) - tide(hour - 0.2)) < 0.03;
    const water = step.querySelector('[data-read="water"]');
    if (water) water.textContent = `${h.toFixed(1)} m, ${top ? "high" : rising ? "rising" : "falling"}`;
    const breeze = step.querySelector('[data-read="wind"]');
    const points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
    if (breeze) breeze.textContent = `${points[Math.round(wind.from / 45) % 8]} ${Math.round(wind.at(hour))} kn`;
  });
}

function idleClock(scene) {
  // the hero's clock: while the trip waits at its first chapter, the hours run on from now toward
  // the casting off (about four seconds an hour), then start again. Not under reduced motion.
  const run = (t) => {
    idle.frame = 0;
    const dt = idle.last ? Math.min(0.1, (t - idle.last) / 1000) : 0;
    idle.last = t;
    const resting = current <= 0 && live && live.stage && live.stage.running && !document.hidden;
    if (resting) {
      idle.hour += dt / 4.2;
      if (idle.hour > HOURS[1] + 0.9) idle.hour = NOW;
      const hour = Math.min(idle.hour, HOURS[1]);
      const data = dataAt(hour);
      CHAPTERS[0].params.data.splice(0, 3, ...data);          // the journey blends from where the clock is
      CHAPTERS[0].params.hour = hour;
      scene.setStory({ idleHatch: smooth(WINDOW[0] - 0.05, WINDOW[0] + 0.35, hour) });
      scene.setData(data);
      tellGauge(hour);
    }
    if (live && !reduce.matches) idle.frame = requestAnimationFrame(run);
  };
  if (!idle.frame && !reduce.matches) idle.frame = requestAnimationFrame(run);
}
document.addEventListener("visibilitychange", () => { idle.last = 0; });

if (section && steps.length) {
  fillReadings();
  tellGauge(NOW);
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const trip = lazyScene(section, async () => {
    const [journey, table, bed, paper] = await Promise.all([
      import("../../vendor/scenes/journey.js"), import("./table.js"), import("./seabed.js"), import("./paper.js"),
    ]);
    // the relief and the two printed sheets are made before the stage, between other work
    const pause = () => new Promise((resolve) => setTimeout(resolve, 0));
    const relief = bed.reliefGrid(coarse ? 288 : 384, coarse ? 260 : 346, 4);
    await pause();
    const svg = section.querySelector("svg.trip__poster");
    const scale = coarse ? 1.6 : 2.2;
    const day = paper.chartPicture(svg, "day", scale);
    await pause();
    const night = paper.chartPicture(svg, "night", scale);
    await pause();
    return {
      mount: (el, options) => journey.mount(el, {
        ...options,
        scene: (stageEl) => {
          const scene = table.mount(stageEl, { relief, day, night, course: COURSE, story: STORY, window: [0, EDGE + legs[3]] });
          scene.dispose = callouts(scene, stageEl.querySelector(".trip__labels"));
          return scene;
        },
      }),
    };
  }, {
    chapters: CHAPTERS,
    inertia: 0.75,
    dwell: 0.4,
    parallax: 0.05,
    drift: 0.006,
    focus: [0.4, 0, 0.6],
    stillWidth: 880,
    stillRatio: 0.6,
    onUpdate: ({ params }) => {
      section.style.setProperty("--trip-night", clamp(params.night || 0).toFixed(3));
      section.toggleAttribute("data-night-now", (params.night || 0) > 0.5);
      if (current > 0 || (params.hour || NOW) > NOW + 0.01) tellGauge(params.hour || NOW);
    },
    lazy: { timeout: 400, margin: "100%" },
  });
  section.addEventListener("chapter", (event) => showChapter(event.detail.index));
  trip.ready.then((journeyHandle) => {
    live = journeyHandle;
    if (!journeyHandle || !journeyHandle.scene || !journeyHandle.scene.setStory) return;
    if (!reduce.matches) idleClock(journeyHandle.scene);
    reduce.addEventListener("change", () => { if (!reduce.matches) idleClock(journeyHandle.scene); });
  });

  // the chapter marks: a table of contents that flies there
  marks.forEach((a) => a.addEventListener("click", (event) => {
    if (!live || !live.goTo || section.getAttribute("data-journey") !== "live") return;
    event.preventDefault();
    live.goTo(Number(a.getAttribute("data-go")));
  }));
  // no journey (no WebGL, or before it loads): the slips are still lit as they pass
  if ("IntersectionObserver" in window) {
    const seen = new IntersectionObserver((entries) => {
      if (section.getAttribute("data-journey") === "live") return;
      const best = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (best) showChapter(steps.indexOf(best.target));
    }, { threshold: [0.35, 0.6] });
    steps.forEach((step) => seen.observe(step));
  }

  // the plain chart, one key press away: the drawn chart instead of the 3D table
  const plain = document.getElementById("plain-chart");
  if (plain) plain.addEventListener("click", () => {
    const on = !section.hasAttribute("data-plain");
    section.toggleAttribute("data-plain", on);
    plain.setAttribute("aria-pressed", String(on));
    if (on) trip.pause("plain"); else trip.resume("plain");
  });
  // the tide table, one key press away: to the week and open the table
  const toTable = document.getElementById("to-table");
  if (toTable) toTable.addEventListener("click", () => {
    const table = document.getElementById("tide-table"), toggle = document.getElementById("table-toggle");
    if (table && table.hidden && toggle) toggle.click();
  });
  motionToggle(document.getElementById("motion"));
  showChapter(0);
}

/* ---- paper with depth: the slip and the passage cards lean to the hand, the notes open as pages */
const main = document.querySelector("main");
if (main) mountDepth(main, { tilt: 4, lift: 7, raise: 12, ease: 0.55, fold: 70, foldTime: 1, foldStagger: 0.12 });
