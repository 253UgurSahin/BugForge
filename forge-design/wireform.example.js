/**
 * wireform.example.js: a hero visual with no dependencies. An example to adapt, not a library.
 *
 * It draws a torus knot (a tube that winds round a ring and through its hole) as thin wireframe
 * lines on a 2D canvas. The tube swells and shrinks along its length (it "breathes") and the whole
 * form turns slowly. Everything comes from the formulas below: no model file, no image.
 *
 * Use (an ES module, so import it from the app's own bundle):
 *   <div class="hero-visual"><canvas aria-hidden="true"></canvas></div>
 *   .hero-visual canvas { display: block; width: 100%; height: 100%; }   <- the canvas needs a CSS size
 *   import { createWireform } from "./wireform.js";
 *   const wireform = createWireform(document.querySelector(".hero-visual canvas"), { p: 2, q: 5 });
 *   wireform.destroy();   // when the page or component goes away
 *
 * The canvas is decoration: keep aria-hidden="true" and never put information in it only.
 * Colour comes from a CSS custom property on the canvas or a parent (--color-accent by default),
 * so the design tokens and the dark theme steer it. The glow adds light, so it needs a dark
 * background; on a light one pass { glow: false }.
 *
 * Make it yours: change p and q (2,3 is the trefoil; 3,7 is busier), the numbers in knot(), the
 * swell in project(), or swap knot() for another closed curve.
 *
 * Move to Three.js (npm install three, loaded with import() only on the page that shows it) when
 * you need lighting or filled faces, more than a few thousand lines, post-processing such as bloom
 * or depth of field, or a model file. Under that, this file is smaller and starts faster.
 */

const TAU = Math.PI * 2;
const CAMERA = 5;  // distance of the eye from the middle of the form, in the form's own units
const REACH = 2.2; // half the size of the form, in the same units: decides how big it is drawn
const BANDS = 4;   // lines are sorted into this many depth bands; far bands are fainter

const DEFAULTS = {
  p: 2,                 // how often the knot goes round the ring's axis
  q: 3,                 // how often it goes through the hole
  along: 160,           // steps along the knot (more is smoother and slower)
  around: 10,           // lines around the tube
  tube: 0.32,           // tube radius
  breathe: 0.25,        // how much the tube swells: 0 is a plain tube
  speed: 0.12,          // turning speed, in radians per second (a full turn in about 52 seconds)
  tilt: 0.55,           // how far the form leans towards the viewer, in radians
  glow: true,           // a soft second pass that adds light (dark backgrounds only)
  colorVar: "--color-accent",
  maxDpr: 2,            // sharper than 2 costs a phone a lot and nobody sees it
};

const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const unit = (a) => {
  const length = Math.hypot(a[0], a[1], a[2]) || 1;
  return [a[0] / length, a[1] / length, a[2] / length];
};

export function createWireform(canvas, options = {}) {
  const o = { ...DEFAULTS, ...options };
  const ctx = canvas.getContext("2d");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const points = new Float32Array(o.along * o.around * 3); // x, y on screen and depth, per point
  const bands = Array.from({ length: BANDS }, () => []);
  let width = 1, height = 1, dpr = 1, color = "", time = 0, last = 0, frame = 0, onScreen = true;

  // 1. The skeleton, worked out once: the knot's centre line, and for each step two unit vectors
  //    at right angles to it. A circle drawn with those two vectors is one ring of the tube.
  const knot = (t) => {
    const radius = 1 + 0.45 * Math.cos(o.q * t);
    return [radius * Math.cos(o.p * t), radius * Math.sin(o.p * t), 0.45 * Math.sin(o.q * t)];
  };
  const centre = [], side = [], up = [];
  for (let i = 0; i < o.along; i++) {
    const t = (i / o.along) * TAU;
    const here = knot(t);
    const forward = unit(sub(knot(t + 0.001), here));
    const across = unit(cross(forward, here)); // "here" points away from the middle: a steady reference
    centre.push(here);
    side.push(across);
    up.push(cross(forward, across));
  }

  // 2. One frame's points: place each point on its ring, turn the form, then project it. Things
  //    further away are drawn smaller (the divide by distance), which is all "3D" means here.
  function project() {
    const spin = time * o.speed, lean = o.tilt + 0.15 * Math.sin(time * 0.25);
    const cosSpin = Math.cos(spin), sinSpin = Math.sin(spin), cosLean = Math.cos(lean), sinLean = Math.sin(lean);
    const size = Math.min(width, height) / 2 / REACH;
    for (let i = 0, n = 0; i < o.along; i++) {
      const c = centre[i], s = side[i], u = up[i], t = (i / o.along) * TAU;
      for (let j = 0; j < o.around; j++, n += 3) {
        const angle = (j / o.around) * TAU;
        const radius = o.tube * (1 + o.breathe * Math.sin(3 * t + 2 * angle + time * 0.8)); // the breathing
        const a = Math.cos(angle) * radius, b = Math.sin(angle) * radius;
        const x = c[0] + s[0] * a + u[0] * b, y = c[1] + s[1] * a + u[1] * b, z = c[2] + s[2] * a + u[2] * b;
        const x1 = x * cosSpin + z * sinSpin, z1 = z * cosSpin - x * sinSpin; // turn round the upright axis
        const y1 = y * cosLean - z1 * sinLean, z2 = y * sinLean + z1 * cosLean; // lean towards the viewer
        const near = CAMERA / (CAMERA + z2);
        points[n] = width / 2 + x1 * near * size;
        points[n + 1] = height / 2 + y1 * near * size;
        points[n + 2] = z2;
      }
    }
  }

  // 3. Draw. Each line goes into a depth band, and each band is one stroke() call: far fewer
  //    calls than one per line, which is what keeps this at 60 frames a second on a phone.
  function draw() {
    project();
    bands.forEach((band) => { band.length = 0; });
    const add = (a, b) => {
      const depth = (points[a + 2] + points[b + 2]) / 2; // from -REACH (near) to +REACH (far)
      const band = Math.max(0, Math.min(BANDS - 1, Math.floor(((depth + REACH) / (2 * REACH)) * BANDS)));
      bands[band].push(points[a], points[a + 1], points[b], points[b + 1]);
    };
    for (let i = 0; i < o.along; i++) {
      const next = (i + 1) % o.along;
      for (let j = 0; j < o.around; j++) {
        const here = (i * o.around + j) * 3;
        add(here, (next * o.around + j) * 3);                                       // along the tube
        if (i % 2 === 0) add(here, (i * o.around + ((j + 1) % o.around)) * 3);      // every second ring
      }
    }
    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = color;
    ctx.globalCompositeOperation = o.glow ? "lighter" : "source-over";
    for (let band = BANDS - 1; band >= 0; band--) { // far first, near on top
      const lines = bands[band], nearness = 1 - band / BANDS;
      ctx.beginPath();
      for (let n = 0; n < lines.length; n += 4) {
        ctx.moveTo(lines[n], lines[n + 1]);
        ctx.lineTo(lines[n + 2], lines[n + 3]);
      }
      if (o.glow) { // the glow: the same lines again, wide and faint. Much cheaper than shadowBlur.
        ctx.lineWidth = 4 * dpr;
        ctx.globalAlpha = 0.06 * nearness;
        ctx.stroke();
      }
      ctx.lineWidth = dpr * 0.75;
      ctx.globalAlpha = 0.15 + 0.6 * nearness;
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  // 4. The loop runs only while someone can see it and has not asked for less motion.
  function tick(now) {
    time += Math.min((now - last) / 1000, 0.05); // a long gap (tab was away) must not make it jump
    last = now;
    draw();
    frame = requestAnimationFrame(tick);
  }
  function update() {
    const run = onScreen && !document.hidden && !reduced.matches;
    if (run && !frame) {
      last = performance.now();
      frame = requestAnimationFrame(tick);
    } else if (!run && frame) {
      cancelAnimationFrame(frame);
      frame = 0;
    }
    if (!run && onScreen) draw(); // reduced motion: one still frame, so the picture is still there
  }

  // 5. Keep the drawing as sharp as the screen, and follow the container's size and the theme.
  function resize() {
    const box = canvas.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, o.maxDpr);
    width = canvas.width = Math.max(1, Math.round(box.width * dpr));
    height = canvas.height = Math.max(1, Math.round(box.height * dpr));
    const style = getComputedStyle(canvas);
    color = style.getPropertyValue(o.colorVar).trim() || style.color; // no token: the text colour
    if (!frame) draw();
  }

  const sizeWatcher = new ResizeObserver(resize);
  const viewWatcher = new IntersectionObserver(([entry]) => {
    onScreen = entry.isIntersecting;
    update();
  });
  sizeWatcher.observe(canvas);
  viewWatcher.observe(canvas);
  document.addEventListener("visibilitychange", update);
  reduced.addEventListener("change", update);
  resize();
  update();

  return {
    redraw: resize, // call after the theme changes, so the new colour is read
    destroy() {
      cancelAnimationFrame(frame);
      frame = 0;
      sizeWatcher.disconnect();
      viewWatcher.disconnect();
      document.removeEventListener("visibilitychange", update);
      reduced.removeEventListener("change", update);
    },
  };
}
