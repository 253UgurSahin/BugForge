/* Tidewatch, level 5: Cinematic. The trip down the pencil line, directed by the scene kit's journey.js.

   The hero is the first chapter of a journey through one 3D scene (table.js: the chart table). The stage
   is fixed to the screen while the chapters' slips scroll over it; the camera flies along the course:
   the whole sheet under the lamp; down behind the pier head (a waypoint bends the flight, so it never
   skims the table) to 14:20 with the water at its highest; across the roads to the 14:40 fix as the
   ebb starts; low down the Wielingen between the buoys, the sounder reading the water under the keel;
   to the landfall under the red lamp, the boat at the end of the pencil line, where it runs off the
   sheet to Zeebrugge; then up over the whole sheet as the lamp goes out and the room light comes back.
   - The opening: the drawn chart (the poster) draws its course; the 3D sheet then takes its place
     exactly, lifts off the page and settles into the hero's view (table.js).
   - The strip of tools marks the chapter whose slip is nearest the middle of the screen. Each slip is
     paper: it lands on the chart with a spring as it comes in, solid, and no label is ever drawn over it.
   - The night of the landfall is read from where its slip is on the screen, so the red lamp is on
     while that slip is read, whatever the camera's lag; the lamp goes out again as it leaves.
   - The data hook: the scene's setData gets the page's own numbers, read from the page itself: the
     water from the week's tide curve (tide.js), the wind from the day's reading (17 kn SW, easing to
     12 kn by 18:00). The water at each chapter's hour is the level of the water on the sheet, so the
     banks dry as the passage goes on; the wind turns, stirs and speeds the streaks over the water.
   - While nobody scrolls, the hero's clock runs on from "now" (09:40) to the casting off at 14:20: the
     tide rises over the banks, the window opens at 10:58 and its band sweeps out along the course, the
     boat comes to the pier head; the slip says the hour and the water and lights its window.
   - On a slow device the table rests while the page is being scrolled (restWhileScrolling).
   - Callouts follow the buoys and fixes as the camera passes them; the sounder rides with the boat.
   - Tools: "Plain chart" (the drawn chart instead of the 3D, Alt+Shift+C, also with the stills of
     reduced motion), "Tide table" (Alt+Shift+T: to the week, with the table open), and the kit's
     motionToggle, which pauses the scene and depth.js and is remembered.
   Nothing of three.js loads before the page is idle (lazyScene). Reduced motion: no pin and no trip;
   each chapter shows a still of its own view beside its text, and the clock stands at now. Without
   WebGL the drawn chart stays on the stage under the chapters, lit by its lamp as on level 2. */
import { lazyScene, motionToggle } from "../../vendor/scenes/lazy.js";
import { readTide, NOW } from "./tide.js";
  /* the sea bed as numbers (a small module of its own, no three.js): the slips read the depth under the boat */
import { seaBed as bedAt } from "./seabed.js";
  /* the harbour plan of Zeebrugge, laid on the table at the landfall (its markup, its entry and its berth) */
import { harbourSvg, ENTRY, BERTH } from "./harbour.js";

const section = document.getElementById("trip");
const root = document.documentElement;
const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");

/* ---- the page's own numbers ------------------------------------------------------------------ */
const toHours = (text) => { const m = /(\d{1,2}):(\d{2})/.exec(text || ""); return m ? Number(m[1]) + Number(m[2]) / 60 : NaN; };
const tide = readTide();

/* the wind: the day's reading and where it is going (the tile "Wind": 17 kn SW, easing to 12 kn by 18:00) */
function readWind() {
  const tile = [...document.querySelectorAll(".stat")].find((el) => /wind/i.test(el.querySelector(".stat__label")?.textContent || ""));
  const knots = parseFloat(tile?.querySelector("[data-count]")?.getAttribute("data-count")) || 15;
  const words = tile?.querySelector(".stat__second")?.textContent || "";
  const POINTS = { N: 0, NE: 45, E: 90, SE: 135, S: 180, SW: 225, W: 270, NW: 315 };
  const from = POINTS[(/\b(NE|NW|SE|SW|N|E|S|W)\b/.exec(words) || [])[1]] ?? 225;
  const trend = /(\d+(?:\.\d+)?)\s*kn by (\d{1,2}:\d{2})/.exec(tile?.querySelector(".stat__trend")?.textContent || "");
  const later = trend ? Number(trend[1]) : knots, at = trend ? toHours(trend[2]) : NOW + 1;
  return { from, at: (t) => knots + (later - knots) * clamp((t - NOW) / (at - NOW)) };
}
const wind = readWind();
const dataAt = (hour) => [tide.height(hour) / 6, wind.at(hour) / 40, wind.from / 360];

/* ---- the course and the chapters --------------------------------------------------------------- */
// the pencil line of the chart: the pier head, the fixes at 14:40 and 15:00, on to where it leaves the
// sheet for Zeebrugge
const COURSE = [[720, 412], [524, 594], [258.6, 694.4], [96, 756], [14, 787]];
const legs = COURSE.slice(1).map((p, i) => Math.hypot(p[0] - COURSE[i][0], p[1] - COURSE[i][1]));
const FIX = [0, legs[0], legs[0] + legs[1]];                        // 14:20, 14:40, 15:00 on the chart
const EDGE = legs.reduce((a, b) => a + b, 0);                         // where the line leaves the sheet
const OFF = 14 + 20 / 60;
const boatAt = (hour) => {                                           // chart units along the line at an hour
  const m = (hour - OFF) * 60;
  if (m <= 0) return 0;
  if (m <= 20) return FIX[1] * (m / 20);
  if (m <= 40) return FIX[1] + (FIX[2] - FIX[1]) * ((m - 20) / 20);
  return Math.min(FIX[2] + ((FIX[2] - FIX[1]) / 20) * (m - 40), EDGE - 2);
};
  /* the chart point at a distance along the pencil line (as table.js places the boat) */
const pointAlong = (d) => {
    let left = d;
    for (let i = 0; i < legs.length; i++) {
        if (left <= legs[i] || i === legs.length - 1) {
            const t = clamp(left / legs[i]), a = COURSE[i], b = COURSE[i + 1];
            return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
        }
        left -= legs[i];
    }
    return COURSE[0];
};
const HOURS = [NOW, OFF, 14 + 40 / 60, 15, 18 + 10 / 60];
const WINDOW = [10 + 58 / 60, 17 + 1 / 60];                           // today's safe window, as on the slip

// a view as an orbit (as table.js reads it), and the camera keyframe it makes
const orbit = (v) => {
  const a = (v.az * Math.PI) / 180, e = (v.el * Math.PI) / 180;
  return { position: [v.target[0] + Math.sin(a) * Math.cos(e) * v.dist, v.target[1] + Math.sin(e) * v.dist, v.target[2] + Math.cos(a) * Math.cos(e) * v.dist], target: v.target, fov: v.fov };
};
// the hero: the sheet big and close in the right half, its lower corner under the slip (the lens shift
// puts it there without turning the view); on a phone the whole sheet below the words, as an object
  /* (the lens shift lifts the sheet so Breskens and the cartouche stand clear above the slip, and the camera
     stands a little further back so the sheet's far corner is not cut by the top of the window) */
const HERO = { target: [1.15, 0, 0.3], dist: 17.4, el: 45, az: 6, fov: 30, shift: [0.43, 0.3] };
  /* (el 36, not 50: seen lower, the sheet is shorter on the screen, so all of it fits between the buttons and the
     strip instead of running on past the fold) */
const HERO_PHONE = { target: [0, 0, 0.15], dist: 50, el: 36, az: 0, fov: 30, shift: [0, -0.55], flight: [0, -0.34] };
// a phone (or a narrow tablet) has the words over the top of the screen: the sheet lies under the buttons as
// wide as the screen, as level 4's does, and runs on under the strip of tools and past the fold (fitted into
// the band between the buttons and the strip it was a strip 200 px high, smaller than level 4's)
function fitPhoneHero() {
  const hero = section && section.querySelector(".trip__step--hero");
  const actions = hero && hero.querySelector(".hero__actions"), bar = section && section.querySelector(".trip__bar-in");
  const vh = window.innerHeight, vw = window.innerWidth;
  if (!actions || !bar || !vh || vw / vh >= 0.8) return;
  const inner = hero.querySelector(".hero__in");
  if (inner) hero.style.setProperty("--hero-room", Math.max(320, vh - (inner.getBoundingClientRect().top + window.scrollY)) + "px");
  const top = actions.getBoundingClientRect().bottom + window.scrollY + 16;
  const bottom = vh - bar.offsetHeight - 4;
  const half = Math.tan((HERO_PHONE.fov * Math.PI) / 360);
  const deep = 9 * Math.sin((HERO_PHONE.el * Math.PI) / 180) + 0.5;          // the sheet and its shadow, seen tipped
  /* fitted by the width alone; its top lies just under the buttons, its foot where the screen allows */
  const byWidth = 11.2 / (2 * half * (vw / vh) * 0.94);
  HERO_PHONE.dist = byWidth;
  const tall = (deep * vh) / (2 * half * byWidth);                            // its height on the screen, in px
  const middle = top + tall / 2;
  void bottom;                                                                // (the strip lies over its foot)
  HERO_PHONE.shift[1] = 1 - (2 * middle) / vh;
}
fitPhoneHero();
if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitPhoneHero);

// what the scene shows along the journey (table.js blends it by the journey's progress)
const STORY = [
  { p: 0, lamp: [0.9, 0.3], lampY: 3, reach: [4.6, 4.3], night: 0, boat: 0, hatch: 0, follow: 1, plan: 1 },
  { p: 0.12, lamp: [2.0, -0.2], lampY: 2.8, reach: [3.6, 3.4], night: 0, boat: 0, hatch: 0.6, follow: 0.4 },
  { p: 0.25, lamp: [2.3, -0.45], lampY: 2.6, reach: [2.8, 2.6], night: 0, boat: boatAt(HOURS[1]) + 2, hatch: 1, follow: 0.35, dusk: 0.05 },
  { p: 0.45, lamp: [0.6, 1.2], lampY: 2.5, reach: [2.8, 2.6], night: 0, boat: boatAt(HOURS[2]), hatch: 1, follow: 0.35, dusk: 0.18 },
  { p: 0.65, lamp: [-2.2, 2.4], lampY: 2.4, reach: [2.9, 2.7], night: 0, boat: boatAt(HOURS[3]), hatch: 1, follow: 0.35, dusk: 0.38 },
  { p: 0.75, lamp: [-3.2, 2.9], lampY: 2.4, reach: [3.4, 3.2], night: 0.4, boat: EDGE - 30, hatch: 0.7, follow: 0.3, dusk: 0.6, plan: 1 },
  { p: 0.85, lamp: [-5.6, 3.9], lampY: 2.6, reach: [4.4, 4.1], night: 1, boat: EDGE, hatch: 0.45, follow: 0.3, dusk: 0.8, plan: 1 },
  { p: 1, lamp: [0.6, 0.3], lampY: 3.2, reach: [5.2, 4.8], night: 0, boat: EDGE, hatch: 0.6, follow: 1, dusk: 0, plan: 1 },
];
  /* (dusk: the afternoon's light warming toward sunset chapter by chapter, so the hour shows in the picture;
     back to the room's plain light for the last look over the whole sheet) */

// camera keyframes, world units: the sheet is 10 x 9 round the middle, x east, z south, y up
const CHAPTERS = [
  { camera: orbit(HERO), phone: orbit(HERO_PHONE),                                       // the hero
      /* (the reduced-motion still of the hero: seen steeper and closer, the sheet fills its frame as level 4's
         does; from further back and lower it was a small wide strip) */
    still: { position: [0.15, 12.2, 7.6], target: [0.15, -0.2, 0.35], fov: 33 }, progress: 0, hour: HOURS[0] },
  { via: true, camera: { position: [3.4, 5.2, 5.6], target: [1.4, 0, -0.2], fov: 34 },  // down behind the pier head
    phone: { position: [3.2, 6.2, 5.2], target: [1.7, 0, -0.3], fov: 48 }, progress: 0.12, hour: NOW + (OFF - NOW) * 0.6 },
  { camera: { position: [3.1, 1.75, 2.1], target: [1.75, 0, -0.25], fov: 36 },          // off the pier head
    phone: { position: [3.0, 3.3, 3.4], target: [2.0, 0, 0.45], fov: 50 },
    still: { position: [3.0, 1.9, 2.0], target: [2.15, 0, -0.35], fov: 38 }, progress: 0.25, hour: HOURS[1] },
  { camera: { position: [1.7, 1.7, 3.5], target: [-0.2, 0, 1.25], fov: 38 },            // across the roads to the fix
    phone: { position: [1.5, 3.2, 4.7], target: [0.1, 0, 2.05], fov: 52 },
    still: { position: [1.8, 1.8, 3.6], target: [0.3, 0, 1.45], fov: 40 }, progress: 0.45, hour: HOURS[2] },
  { camera: { position: [0.45, 2.75, 3.95], target: [-2.85, -0.25, 2.6], fov: 40 },     // down the Wielingen
    phone: { position: [0.9, 5.2, 4.9], target: [-2.0, -0.25, 2.8], fov: 54 },
    still: { position: [0.3, 2.6, 4.0], target: [-2.6, -0.25, 2.55], fov: 42 }, progress: 0.65, hour: HOURS[3] },
    /* the landfall looks along the last of the pencil line onto the sheet, the boat at its end on the edge of
       the frame: the chart fills the view (aimed past the sheet's edge, half the frame was bare table) */
    /* round 2: the landfall lands. The harbour plan of Zeebrugge (harbour.js) now lies on the table beyond the
       chart's west edge, the pencil running on over it to the berth: the view takes in the end of the chart
       and the plan, the berth in the middle of the frame, clear of the slip on the left */
  { camera: orbit({ target: [-7.2, 0, 5.0], dist: 6.4, el: 52, az: 58, fov: 40 }),   // the landfall, under the red lamp
    phone: orbit({ target: [-6.9, 0, 4.6], dist: 10.5, el: 60, az: 36, fov: 50 }),
    still: orbit({ target: [-6.6, 0, 4.3], dist: 7.2, el: 46, az: 62, fov: 40 }), progress: 0.85, hour: HOURS[4] },
  { at: 1, camera: { position: [-1.3, 14.2, 12.6], target: [-1.3, 0, 0.9], fov: 34 },       // the whole sheet, in the room light again
    /* (on a phone the whole sheet lies in the middle of the screen, not at its top over half a screen of bare
       paper: the view aims further north, so the sheet sits lower) */
    phone: { position: [-0.6, 26, 20], target: [-0.6, 0, -1.5], fov: 40 }, progress: 1, hour: HOURS[4] },
].map((c) => ({ ...c, params: { hour: c.hour, data: dataAt(c.hour) } }));

/* ---- callouts: buoys and fixes, named as the camera passes them ------------------------------ */
  /* only the fixes are named: the buoys' own names are printed beside them on the chart, and a label that
     repeats the print was noise (the judges counted W8, W10 and SP2 twice). The fixes say the hour, which the
     print writes as "1440" */
const CALLOUTS = [
  { at: [720, 412], text: "<b>14:20</b> off the pier" },
  { at: [524, 594], text: "<b>14:40</b> fix" },
  { at: [258.6, 694.4], text: "<b>15:00</b> fix" },
];
  /* the boat's draught: the sounder reads the water under her keel, the charted depth plus the tide less this */
const DRAUGHT = 1.5;
const clock = (hour) => { const m = Math.round((((hour % 24) + 24) % 24) * 60) % 1440; return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0"); };

const steps = section ? [...section.querySelectorAll("[data-chapter]")] : [];
const cards = steps.map((step) => step.querySelector(".trip__card")).filter(Boolean);
const marks = section ? [...section.querySelectorAll("[data-go]")] : [];
let live = null, current = -1, tripHour = NOW;

/* the rectangles of the slips on screen now: nothing is named underneath one */
function slipBoxes() {
  const out = [];
  const vh = window.innerHeight;
  for (const card of cards) {
    const r = card.getBoundingClientRect();
    if (r.bottom > -20 && r.top < vh + 20) out.push(r);
  }
  const slip = steps[0] && steps[0].querySelector(".hero__slip");
  if (slip) { const r = slip.getBoundingClientRect(); if (r.bottom > 0 && r.top < vh) out.push(r); }
  return out;
}

function callouts(scene, layer) {
  if (!layer || !scene.onCamera) return () => {};
  const made = CALLOUTS.map((c) => {
    const el = document.createElement("span");
    el.className = "callout";
    el.innerHTML = c.text;
    layer.appendChild(el);
    return { ...c, el, shown: 0 };
  });
  const sounder = document.createElement("span");
  sounder.className = "callout callout--sounder";
  layer.appendChild(sounder);
    /* the flag at the tide gauge in Vlissingen harbour, as on level 4: the hour and the water the slip says,
       standing where the water is measured, while the hero is read (never on the journey's own chapters) */
    const flag = document.createElement("span");
    flag.className = "callout callout--gauge";
    layer.appendChild(flag);
    let flagText = "";
  let last = 0, lastText = "";
  const off = scene.onCamera((camera) => {
    const now = performance.now(), dt = Math.min(0.25, (now - last) / 1000 || 0.016);
    last = now;
    const w = layer.clientWidth, h = layer.clientHeight;
    const boxes = slipBoxes(), bar = section.querySelector(".trip__bar-in");
    const barTop = bar ? bar.getBoundingClientRect().top : h;
    const under = (x, y, x2) => boxes.some((b) => x2 > b.left - 12 && x < b.right + 12 && y > b.top - 18 && y < b.bottom + 18);
    const project = (wx, wy, wz) => {
      const p = camera.position, e = camera.matrixWorldInverse.elements, m = camera.projectionMatrix.elements;
      const x = e[0] * wx + e[4] * wy + e[8] * wz + e[12], y = e[1] * wx + e[5] * wy + e[9] * wz + e[13], z = e[2] * wx + e[6] * wy + e[10] * wz + e[14];
      const cw = m[3] * x + m[7] * y + m[11] * z + m[15];
      const cx = (m[0] * x + m[4] * y + m[8] * z + m[12]) / cw, cy = (m[1] * x + m[5] * y + m[9] * z + m[13]) / cw;
      return { x: (cx + 1) / 2 * w, y: (1 - cy) / 2 * h, behind: z > -0.05, dist: Math.hypot(p.x - wx, p.y - wy, p.z - wz) };
    };
    const opening = scene.opening && scene.opening();
    const boat = scene.boatPoint();
    for (const c of made) {
      const [wx, wz] = [(c.at[0] - 500) / 100, (c.at[1] - 450) / 100];
      const sitting = boat && boat.on && Math.hypot(boat.chart[0] - c.at[0], boat.chart[1] - c.at[1]) < 40;
      const s = project(wx, scene.surfaceAt(c.at[0], c.at[1]) + 0.02, wz);
      const inView = !opening && !s.behind && s.x > -40 && s.x < w - 150 && s.y > 60 && s.y < barTop - 24 && !under(s.x, s.y, s.x + 130);
      const goal = inView && !sitting ? smooth(5.4, 3.4, s.dist) : 0;
      // under a slip a label goes at once; elsewhere it fades in and out with the camera
      c.shown = goal === 0 && !inView ? 0 : c.shown + (goal - c.shown) * Math.min(1, dt * 5);
      if (c.shown < 0.01) { if (c.el.style.opacity !== "0") c.el.style.opacity = "0"; continue; }
      c.el.style.opacity = c.shown.toFixed(3);
      c.el.style.transform = `translate3d(${s.x.toFixed(1)}px, ${(s.y - 7).toFixed(1)}px, 0)`;
    }
      {
          const [gx, gz] = [(GAUGE[0] - 500) / 100, (GAUGE[1] - 450) / 100];
          const s = project(gx, scene.surfaceAt(GAUGE[0], GAUGE[1]) + 0.02, gz);
          const visible = current <= 0 && !opening && !s.behind && s.x > 0 && s.x < w - 160 && s.y > 60 && s.y < barTop - 30 && !under(s.x - 4, s.y - 30, s.x + 150);
          flag.style.opacity = visible ? "1" : "0";
          if (visible) {
              if (gaugeText !== flagText) { flag.innerHTML = gaugeText; flagText = gaugeText; }
              flag.style.transform = `translate3d(${s.x.toFixed(1)}px, ${(s.y - 30).toFixed(1)}px, 0)`;
          }
      }
    // the sounder rides with the boat: the water under the keel, from the tide and the sea bed
    if (boat) {
        /* alongside: the label stands at her berth on the harbour plan, not on the chart's edge */
        const berth = scene.berth && scene.berth();
        const where = berth || boat.world;
      const s = project(where[0], where[1] + 0.03, where[2]);
        /* the tide as the slips give it: the tide table at the hour shown (the scene's water eases behind the
           scroll, and its figure disagreed with the slip's) */
        const tideNow = tide.height(tripHour);
      const depth = Math.max(0, tideNow - scene.bedAt(boat.chart[0], boat.chart[1]));
      const ox = s.x + 18, oy = s.y - 26;
      const visible = (boat.on || Boolean(berth)) && !opening && !s.behind && ox > 0 && ox < w - 350 && oy > 50 && oy < barTop - 30 && s.dist < (berth ? 10 : 7) && !under(ox, oy, ox + 340);
      sounder.style.opacity = visible ? "1" : "0";
      if (visible) {
        const atEnd = Boolean(berth) || boat.chart[0] < 40;
          /* the sum written out, so the figure agrees with the soundings printed round her: charted depth plus
             the tide, less her draught */
          const charted = Math.max(0, -scene.bedAt(boat.chart[0], boat.chart[1]));
          const text = atEnd ? `<b>Zeebrugge</b> alongside · ${clock(tripHour)}`
              : `<b>${Math.max(0, depth - DRAUGHT).toFixed(1)} m</b> under the keel · ${charted.toFixed(1)} chart + ${tideNow.toFixed(1)} tide − ${DRAUGHT}`;
        if (text !== lastText) { sounder.innerHTML = text; lastText = text; }
        sounder.style.transform = `translate3d(${ox.toFixed(1)}px, ${oy.toFixed(1)}px, 0)`;
      }
    }
  });
  return () => { off(); layer.textContent = ""; };
}

/* ---- the slip on the hero: the water of the hour, and its window lit while the hour is inside it --- */
const slip = steps[0] && steps[0].querySelector(".hero__slip");
const readouts = [...document.querySelectorAll("[data-tide]")].map((el) => ({
  el, gauge: el.querySelector(".gauge"), h: el.querySelector("[data-tide-h]"), way: el.querySelector("[data-tide-way]"), time: el.querySelector("[data-tide-time]"),
}));
function wayOf(hour) {
  const rate = tide.height(hour + 0.25) - tide.height(hour - 0.25);
  if (Math.abs(rate) < 0.07) return tide.height(hour) > 2.5 ? "high water" : "low water";
  return rate > 0 ? "rising" : "falling";
}
let toldHour = -1;
  /* what the flag at the gauge says: the same words as the slip ("09:40 1.0 m now", "12:15 3.9 m rising") */
  let gaugeText = "<b>09:40</b> 1.0 m now";
  const GAUGE = [706, 366];                                          // the tide gauge, Vlissingen harbour
function say(hour) {
  const minute = Math.round(hour * 60);
  if (minute === toldHour) return;
  toldHour = minute;
  const metres = tide.height(hour), isNow = Math.abs(hour - NOW) < 1 / 120;
  for (const r of readouts) {
    if (r.h) r.h.textContent = metres.toFixed(1) + " m";
    if (r.way) r.way.textContent = wayOf(hour);
    if (r.time) r.time.textContent = clock(hour) + (isNow ? " now" : "");
      gaugeText = `<b>${clock(hour)}</b> ${metres.toFixed(1)} m ${isNow ? "now" : wayOf(hour)}`;
    if (r.gauge) r.gauge.style.setProperty("--level", clamp(metres / 6).toFixed(3));
    r.el.classList.toggle("is-lapse", !isNow);
  }
  if (slip) slip.classList.toggle("is-open", hour >= WINDOW[0] && hour <= WINDOW[1] && !isNow);
}

// the readings on the slips, worked out from the same numbers the scene gets
function fillReadings() {
  steps.forEach((step, i) => {
    const hour = HOURS[i];
    if (hour === undefined) return;
    const h = tide.height(hour), way = wayOf(hour);
    const water = step.querySelector('[data-read="water"]');
    if (water) water.textContent = `${h.toFixed(1)} m, ${way === "high water" ? "high" : way}`;
    const breeze = step.querySelector('[data-read="wind"]');
    const points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
    if (breeze) breeze.textContent = `${points[Math.round(wind.from / 45) % 8]} ${Math.round(wind.at(hour))} kn`;
      /* the water under the keel at this hour, worked out as the sounder works it (charted depth at the boat
         plus the tide, less the draught), so the slip and the sounder say the same figure */
      const keel = step.querySelector('[data-read="keel"]');
      if (keel && bedAt) {
          const at = pointAlong(boatAt(hour));
          keel.textContent = `${Math.max(0, h - bedAt(at[0], at[1]) - DRAUGHT).toFixed(1)} m`;
      }
  });
}

function showChapter(index) {
  current = index;
  steps.forEach((el, i) => el.toggleAttribute("data-current", i === index));
  marks.forEach((a, i) => { if (i === index) a.setAttribute("aria-current", "step"); else a.removeAttribute("aria-current"); });
}

// the hero's clock: once the opening is over and while the trip waits at its first chapter, the hours
// run on from now to the casting off (two and a half seconds an hour, by the wall's clock, so a slow
// device sees the same hours, only fewer frames of them) and stop there, the window open, the water
// high and the boat waiting at the pier head: where the trip begins. It rides on the stage's own frames,
// so it stops whenever the scene does (reduced motion, paused, out of sight).
function heroClock(journeyHandle) {
  const scene = journeyHandle.scene;
  let hour = NOW, ready = !scene.opening || !scene.opening(), last = 0;
    /* the scale on the slip (level 4's, here from now to casting off): dragging it sets the hour, and the
       clock no longer runs by itself, so what the reader picked stays */
    const scrub = document.getElementById("hero-scrub"), input = document.getElementById("hero-hour");
    let held = false;
    function setHour(h) {
        hour = clamp(h, NOW, OFF);
        scene.setStory({ idleBoat: hour >= OFF ? 1 : 0, idleHatch: smooth(WINDOW[0] - 0.05, WINDOW[0] + 0.45, hour) });
        const data = dataAt(hour);
        CHAPTERS[0].params.data.splice(0, 3, ...data);      // the journey blends on from where the clock is
        CHAPTERS[0].params.hour = hour;
        scene.setData(data);
        say(hour);
        if (input) {
            const minutes = Math.round((hour - NOW) * 60);
            if (Number(input.value) !== minutes && !held) input.value = String(minutes);
            input.setAttribute("aria-valuetext", `${clock(hour)}${Math.abs(hour - NOW) < 1 / 120 ? " now" : ""}, water ${tide.height(hour).toFixed(1)} m, ${wayOf(hour)}`);
        }
    }
    if (input) input.addEventListener("input", () => { held = true; setHour(NOW + Number(input.value) / 60); });
    const offer = () => { ready = true; if (scrub && !journeyHandle.stage.still) scrub.hidden = false; };
    journeyHandle.stage.container.addEventListener("tableopen", offer);
    if (ready) offer();
  return journeyHandle.stage.onFrame(() => {
    const now = performance.now(), delta = last ? Math.min((now - last) / 1000, 1) : 0;
    last = now;
    if (current > 0 || journeyHandle.stage.still || !ready || held || hour >= OFF) return;
      setHour(Math.min(OFF, hour + delta / 2.5));
  });
}

/* ---- a slow device (one that needs more than about a tenth of a second for a frame, as where the scene
   is drawn in software) does not draw the table while the page is being scrolled: a long drawing holds
   up the page's own record of how far it is scrolled, and the strip and the slips would be placed by a
   stale one. The table catches up as soon as the scrolling rests. A device that keeps up never pauses. */
function restWhileScrolling(journeyHandle) {
  const stage = journeyHandle.stage;
  let last = 0, rest = 0, held = false;
  const gaps = [];
  const slow = () => {
    if (gaps.length < 6) return false;
    const sorted = gaps.slice().sort((a, b) => a - b);
    return sorted[Math.floor(sorted.length / 2)] > 110;
  };
  stage.onFrame(() => {
    const now = performance.now();
    if (last && !held) { gaps.push(now - last); if (gaps.length > 12) gaps.shift(); }
    last = now;
  });
  addEventListener("scroll", () => {
    if (stage.still || !slow()) return;
    if (!held) { held = true; journeyHandle.pause("scrolling"); }
    clearTimeout(rest);
    rest = setTimeout(() => { held = false; last = 0; journeyHandle.resume("scrolling"); }, 280);
  }, { passive: true });
}

/* ---- each slip is laid on the chart as it comes in: down from the lamp, settling with a little give */
function spring(duration, bounce) {
  const zeta = 1 - clamp(bounce, 0.05, 0.6), w = (2 * Math.PI) / (duration / 1000), wd = w * Math.sqrt(1 - zeta * zeta);
  const at = (t) => 1 - Math.exp(-zeta * w * t) * (Math.cos(wd * t) + ((zeta * w) / wd) * Math.sin(wd * t));
  const settle = Math.log(1000 * (1 + (zeta * w) / wd)) / (zeta * w), points = [];
  for (let i = 0; i <= 32; i++) points.push(i === 32 ? 1 : +at((settle * i) / 32).toFixed(3));
  const easing = `linear(${points.join(", ")})`;
  const ok = window.CSS && CSS.supports && CSS.supports("transition-timing-function", easing);
  return { duration: Math.round(settle * 1000), easing: ok ? easing : "cubic-bezier(0.34, 1.56, 0.64, 1)" };
}
function landSlips() {
  if (!("IntersectionObserver" in window) || !Element.prototype.animate) return;
  const fall = spring(560, 0.28);
  const seen = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting || reduce.matches || section.getAttribute("data-journey") === "still") continue;
      seen.unobserve(entry.target);
      const rest = getComputedStyle(entry.target).rotate;
      entry.target.animate([{ translate: "6px -34px", rotate: "-3.5deg", scale: "1.03" }, { translate: "0 0", rotate: rest === "none" ? "0deg" : rest, scale: "1" }],
        { duration: fall.duration, easing: fall.easing });
    }
  }, { threshold: 0.12 });
  cards.forEach((card) => seen.observe(card));
}

/* the veil over the hero lifts as its words leave; the strip marks the chapter whose slip is nearest the
   middle of the screen (read from the page itself, so it is right however far the camera lags) */
function onScroll() {
  const vh = window.innerHeight || 1;
  const hero = steps[0] ? steps[0].getBoundingClientRect() : null;
  if (hero) section.style.setProperty("--trip-hero", (1 - smooth(0.04, 0.42, -hero.top / vh)).toFixed(3));
  let best = 0, gap = Infinity;
  steps.forEach((step, i) => {
    const box = (i === 0 ? step : step.querySelector(".trip__card") || step).getBoundingClientRect();
    const d = i === 0 ? Math.max(0, -box.top - vh * 0.35) : Math.abs(box.top + box.height / 2 - vh * 0.5);
    if (d < gap) { gap = d; best = i; }
  });
  if (best !== current) showChapter(best);
}
function landfallNight() {
  const card = cards[cards.length - 1];
  if (!card) return 0;
  const vh = window.innerHeight || 1, r = card.getBoundingClientRect();
  const dusk = smooth(1.02, 0.66, (r.top + r.height / 2) / vh);        // as its slip comes up into view
  const dawn = smooth(0.24, -0.12, r.bottom / vh);                      // and once it has gone over the top
  return dusk * (1 - dawn);
}

if (section && steps.length) {
  fillReadings();
  say(NOW);
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const poster = section.querySelector("svg.trip__poster");
  // wait until the drawn chart's own opening is over (the course pencilled, the slip laid), so the 3D
  // sheet takes over from a chart at rest
  const settled = (cap = 4000) => {
    const running = typeof document.getAnimations === "function"
      ? document.getAnimations().filter((a) => {
        const target = a.effect && a.effect.target;
        return target && section.contains(target) && a.playState === "running" && a.effect.getTiming().iterations !== Infinity;
      }) : [];
    return Promise.race([Promise.all(running.map((a) => a.finished.catch(() => null))), new Promise((r) => setTimeout(r, cap))]);
  };
  const trip = lazyScene(section, async () => {
    const [journey, table, bed, print] = await Promise.all([
      import("../../vendor/scenes/journey.js"), import("./table.js"), import("./seabed.js"), import("./print.js"),
    ]);
    // without WebGL 2 the stage will not start: skip the work below, the journey shows the poster
    let probe = null;
    try { probe = document.createElement("canvas").getContext("webgl2"); } catch (error) { probe = null; }
    if (!probe) return { mount: (el, options) => journey.mount(el, { ...options, scene: (stageEl) => table.mount(stageEl, {}) }) };
    const lose = probe.getExtension("WEBGL_lose_context");
    if (lose) lose.loseContext();
    const pause = () => new Promise((resolve) => setTimeout(resolve, 0));
    // the relief and the print are made before the stage, between other work; the print as sharp as the
    // camera comes close (a phone draws fewer pixels and gets half)
    const relief = bed.reliefGrid(coarse ? 257 : 385, coarse ? 232 : 347, 4);
    await pause();
    const chart = print.chartPrint(poster, { width: coarse ? 2048 : 4096 });
    const [base, baseNight, ink] = [await chart.base("day"), await chart.base("night"), await chart.ink()];
      // the harbour plan, printed the same way (a smaller sheet, so a smaller print)
      await pause();
      const harbour = print.chartPrint(harbourSvg(), { width: coarse ? 1024 : 2048 });
      const plan = { base: await harbour.base("day"), baseNight: await harbour.base("night"), ink: await harbour.ink(), entry: ENTRY, berth: BERTH };
    if (!reduce.matches && window.scrollY < 40) await settled();
    return {
      mount: (el, options) => journey.mount(el, {
        ...options,
        scene: (stageEl) => {
          const scene = table.mount(stageEl, {
            relief, course: COURSE, story: STORY, window: [0, EDGE], hero: HERO, heroPhone: HERO_PHONE, plan,
            print: { base, baseNight, ink, width: chart.width, height: chart.height, tokens: chart.tokens },
          });
          scene.dispose = callouts(scene, stageEl.querySelector(".trip__labels"));
          return scene;
        },
      }),
    };
  }, {
    chapters: CHAPTERS,
    inertia: 0.2,
    dwell: 0.35,
    parallax: 0.04,
    drift: 0.005,
    focus: [0.4, 0, 0.6],
    stillWidth: 880,
    stillRatio: 0.8,      // taller stills: the sheet seen from above is nearly square (at 0.6 it was a strip)
    onUpdate: ({ params, progress }) => {
      // also called before each still is drawn: the stage only follows the live trip
      if (section.getAttribute("data-journey") !== "live") return;
      tripHour = params.hour || NOW;
      const night = landfallNight();
      if (live && live.scene && live.scene.setStory) live.scene.setStory({ night });
      const shown = live && live.scene && live.scene.night ? live.scene.night() : night;
      section.style.setProperty("--trip-night", clamp(shown).toFixed(3));
      section.toggleAttribute("data-night-now", shown > 0.5);
      if (current > 0 || progress > 0.02) say(params.hour || NOW);
    },
    lazy: { timeout: 400, margin: "100%" },
  });
  trip.ready.then((journeyHandle) => {
    live = journeyHandle;
    if (journeyHandle && journeyHandle.stage && journeyHandle.scene && journeyHandle.scene.setStory) {
      heroClock(journeyHandle);
      restWhileScrolling(journeyHandle);
    }
  });

  // the chapter marks: a table of contents that flies there
  marks.forEach((a) => a.addEventListener("click", (event) => {
    if (!live || !live.goTo || section.getAttribute("data-journey") !== "live") return;
    event.preventDefault();
    live.goTo(Number(a.getAttribute("data-go")));
  }));
  landSlips();
  let ticking = 0;
  addEventListener("scroll", () => { if (!ticking) ticking = requestAnimationFrame(() => { ticking = 0; onScroll(); }); }, { passive: true });
  addEventListener("resize", () => { onScroll(); fitPhoneHero(); });
  onScroll();

  // the plain chart, one key press away: the drawn chart instead of the 3D table. Live, the drawn chart
  // (the poster) comes back over the stage; with stills (reduced motion) a copy of it takes the place of
  // the stills in the hero
  const plain = document.getElementById("plain-chart");
  const plainStill = () => {
    if (section.querySelector(".trip__plain") || !poster || !steps[0]) return;
    const figure = document.createElement("figure");
    figure.className = "trip__plain";
    figure.setAttribute("aria-hidden", "true");
    const copy = poster.cloneNode(true);
    copy.setAttribute("class", "chart");
    copy.removeAttribute("data-scene-poster");
    copy.removeAttribute("data-enter");
    copy.querySelectorAll("defs, [id]").forEach((el) => (el.tagName.toLowerCase() === "defs" ? el.remove() : el.removeAttribute("id")));
    figure.appendChild(copy);
    steps[0].appendChild(figure);
  };
  if (plain) plain.addEventListener("click", () => {
    const on = !section.hasAttribute("data-plain");
    if (on) plainStill();
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
  // from anywhere on the page (not while typing in a field): Alt+Shift+T the tide table, Alt+Shift+C the plain chart
  document.addEventListener("keydown", (event) => {
    if (!event.altKey || !event.shiftKey || event.ctrlKey || event.metaKey) return;
    if (event.target.closest && event.target.closest("input, select, textarea, [contenteditable]")) return;
    if (event.code === "KeyT" && toTable) { event.preventDefault(); toTable.click(); }
    if (event.code === "KeyC" && plain && /^(live|still)$/.test(section.getAttribute("data-journey") || "")) { event.preventDefault(); plain.click(); plain.focus({ preventScroll: true }); }
  });
  motionToggle(document.getElementById("motion"));
  showChapter(0);
}
