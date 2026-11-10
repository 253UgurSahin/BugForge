/**
 * journey.js: the director for look level 5. A scroll-driven trip through one 3D scene.
 *
 * A tall section holds a pinned canvas (position: sticky) and a few text chapters that scroll over
 * it. While the section scrolls through the viewport the journey flies the camera along a smooth
 * path through the chapters' keyframes, walks the scene's own progress with it, and tells the page
 * which chapter is current, so the page can light up that text. It feels like one camera move in a
 * film: the scroll is followed with inertia, the move slows (but never stops dead) at each chapter,
 * and a flick or a change of direction bends the move instead of jerking it.
 *
 *   <section class="journey">
 *     <div data-journey-stage aria-hidden="true"></div>       the pinned canvas (made when missing)
 *     <article data-chapter>...</article>                      one per chapter, in order
 *   </section>
 *
 *   import { mount as form } from "./scenes/form.js";
 *   import { mount } from "./scenes/journey.js";
 *   const trip = mount(document.querySelector(".journey"), {
 *     scene: (el) => form(el, { side: "centre", progressEase: 0.05 }),
 *     chapters: [
 *       { at: 0,   camera: { position: [-1, 0.5, 9], target: [-2, 0, 0], fov: 32 }, progress: 0 },
 *       { at: 0.5, camera: { position: [2, -1, 5], target: [0.5, 0, 0] }, progress: 0.5,
 *         phone: { position: [0, -1, 8], target: [0, -0.5, 0] } },
 *       { at: 1,   camera: { position: [0, 8, 6], target: [0, 0, 0], roll: 5 }, progress: 1 },
 *     ],
 *   });
 *   section.addEventListener("chapter", (e) => light(e.detail.index, e.detail.direction));
 *
 * Options (all optional except scene):
 *   scene     a mounted scene of this kit (its handle), or a factory (element) => handle that the
 *             journey calls with the [data-journey-stage] element. A scene you mount yourself: pass
 *             it progressEase: 0.05, as the journey does its own easing.
 *   chapters  [{ at, camera: { position, target, fov, roll }, phone, progress, params }]:
 *             at        0..1, where on the section's scroll this chapter sits. Left out: the middle
 *                       of its [data-chapter] element (centred on screen), or spread evenly.
 *             camera    position and target [x, y, z] (default [0, 0, 9] and [0, 0, 0]), fov in
 *                       degrees (the previous chapter's, else 32), roll in degrees (0).
 *             phone     the same as camera, for a narrow screen (aspect under `narrow`); left out
 *                       parts come from camera.
 *             progress  0..1, what the scene's setProgress gets here (default: evenly spread).
 *             params    { name: number | [numbers] }, blended between chapters and handed to
 *                       onUpdate; params.data also goes to the scene's setData.
 *             via       true: a waypoint, not a chapter. It bends the path (pull the camera back
 *                       while the scene changes shape, say) but has no text, no event and no
 *                       still, and the move does not slow there. Left without at: half-way.
 *   steps       the chapter elements: a selector or a list (default "[data-chapter]" in the section).
 *   inertia     0.65. Seconds the camera lags the scroll on average (it settles in about twice that).
 *   dwell       0.45. 0..1: how much the move slows at a chapter (1 stops there for a moment).
 *   parallax    0.035. The camera leans this much (times its distance) toward the pointer.
 *   drift       0.01. A slow floating of the camera, as if held by hand (times its distance).
 *   narrow      0.8. Below this aspect the phone keyframes are used.
 *   stillWidth  880, stillRatio 0.62. Size in CSS pixels of each reduced-motion still.
 *   focus       [0, 0, 0]. The middle of the subject: a still slides the camera sideways (same
 *               angle, same distance) until this point is in the middle of its frame, since a
 *               still has no text on one side to make room for.
 *   keepScene   false. true leaves a scene you mounted yourself alive after destroy().
 *   onUpdate    fn({ progress, target, index, params }) after every frame of the trip.
 *
 * The section gets data-journey="live" | "still" | "fallback" and data-chapter="<index>", and a
 * "chapter" event (detail: { index, direction: 1 | -1 | 0, chapter }) each time the current
 * chapter changes (direction 0 for the first). Page CSS makes the pin; the journey only adds a
 * sticky style to a stage element it had to make itself.
 *
 * Reduced motion (and keyboard): there is no pinned trip. Each chapter gets its own still frame,
 * rendered once from its keyframe, as an <img> in its [data-chapter-still] element (made as a
 * <figure class="journey-still"> at the end of the chapter when missing): lay it out beside the
 * text with [data-journey="still"] rules. The stills are made again after a theme change or a
 * resize. The page scrolls normally everywhere, so arrow keys, space and Tab work as on any page;
 * goTo(index) scrolls to a chapter from code (a table of contents).
 *
 * Returns { setProgress, setData, setPointer, pause, resume, goTo, destroy, scene, stage }.
 *   setProgress(p)  0..1: fly to that point of the trip; the next scroll takes over again.
 *   setData(values) passed to the scene (chapter params.data wins while it is set).
 *   setPointer, pause, resume: passed to the scene. destroy(): undoes everything it added.
 *
 * Poster: put a [data-scene-poster] image inside the stage element; with no WebGL the section
 * gets data-journey="fallback" and the poster stays, with the chapters scrolling over it.
 *
 * Cost: the scene's own cost and nothing per pixel: a few splines and filters a frame. Under
 * reduced motion, one render and one WebP per chapter, again after a theme change or a resize.
 */
import * as THREE from "three";
import { progressOf } from "./stage.js";

const DEFAULTS = { inertia: 0.65, dwell: 0.45, parallax: 0.035, drift: 0.01, narrow: 0.8,
                   stillWidth: 880, stillRatio: 0.62, focus: [0, 0, 0], keepScene: false };
const FILTERS = 3;       // how many smoothing stages follow the scroll (see Follower)
const HOLD = 0.012;      // hysteresis of the chapter switch, in progress units
const DEG = Math.PI / 180;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const finite = (v, fallback) => (Number.isFinite(Number(v)) ? Number(v) : fallback);

/**
 * Follows the scroll with inertia, and can never overshoot. Three identical "move part of the
 * remaining way" smoothers in a row: each one's output is a weighted average of its input's past,
 * with weights that are all positive, so the result never leaves the range the scroll has been in
 * (no overshoot, also after a flick), and with three in a row its speed and its acceleration
 * change smoothly (no jerk when the scroll changes direction). k = 1 - e^(-dt/tau) makes it the
 * same at 30 and 120 frames a second.
 */
class Follower {
  constructor(value = 0) { this.stages = new Array(FILTERS).fill(value); }
  snap(value) { this.stages.fill(value); return value; }
  step(target, delta, settle) {
    const k = 1 - Math.exp(-delta / Math.max(settle / FILTERS, 0.001));
    let input = target;
    for (let i = 0; i < FILTERS; i++) input = this.stages[i] += (input - this.stages[i]) * k;
    return input;
  }
}

/**
 * A curve through the values of a list that never goes past any of them (monotone cubic, after
 * Fritsch and Carlson): the slope at each point is the gentler of its two sides, and 0 where the
 * values turn. i is the segment, u 0..1 inside it.
 */
function monotone(values, i, u) {
  const n = values.length;
  if (n < 2) return values[0];
  const slope = (k) => values[clamp(k + 1, 0, n - 1)] - values[clamp(k, 0, n - 1)];
  const tangent = (k) => {
    const a = k > 0 ? slope(k - 1) : slope(k), b = k < n - 1 ? slope(k) : slope(k - 1);
    return a * b <= 0 ? 0 : (2 * a * b) / (a + b); // harmonic mean: never steeper than either side
  };
  const p0 = values[i], p1 = values[Math.min(i + 1, n - 1)], m0 = tangent(i), m1 = tangent(i + 1);
  const u2 = u * u, u3 = u2 * u; // cubic Hermite: the curve that starts at p0 with slope m0 and ends at p1 with m1
  return (2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * m0 + (-2 * u3 + 3 * u2) * p1 + (u3 - u2) * m1;
}

/** Blend params ({ name: number | [numbers] }) with the same curve as everything else. */
function blendParams(list, i, u) {
  const out = {};
  for (const key of Object.keys(list[0] || {})) {
    const first = list[0][key];
    if (Array.isArray(first)) {
      out[key] = first.map((_, j) => monotone(list.map((p) => finite((p[key] || [])[j], first[j])), i, u));
    } else if (Number.isFinite(Number(first))) {
      out[key] = monotone(list.map((p) => finite(p[key], first)), i, u);
    }
  }
  return out;
}

export function mount(section, options = {}) {
  const o = { ...DEFAULTS, ...options };
  const root = section && section.nodeType === 1 ? section : null;
  const offs = [];   // what destroy() undoes, newest last
  const nothing = () => {};
  const empty = { setProgress: nothing, setData: nothing, setPointer: nothing, pause: nothing,
                  resume: nothing, goTo: nothing, destroy: nothing, scene: null, stage: null };
  if (!root) return empty;
  const steps = Array.from(typeof o.steps === "string" || !o.steps
    ? root.querySelectorAll(o.steps || "[data-chapter]") : o.steps);

  // 1. The scene, and the pinned element it draws in.
  let host = root.querySelector("[data-journey-stage]");
  let scene = o.scene;
  if (typeof scene === "function") {
    if (!host) { // no stage element in the page: make a pinned one that takes no room in the flow
      host = document.createElement("div");
      host.setAttribute("data-journey-stage", "");
      host.setAttribute("aria-hidden", "true");
      host.style.cssText = "position:sticky;top:0;height:100vh;margin-bottom:-100vh;overflow:hidden";
      root.insertBefore(host, root.firstChild);
      offs.push(() => host.remove());
    }
    try { scene = scene(host); } catch (error) { console.error(error); scene = null; }
  }
  const stage = scene && scene.stage;
  if (scene && stage && !host) host = stage.container.closest("[data-journey-stage]") || stage.container;
  offs.push(() => { if (scene && !(o.keepScene && typeof o.scene !== "function")) scene.destroy(); });
  const undo = () => {
    for (const off of offs.splice(0).reverse()) off();
    root.removeAttribute("data-journey");
    root.removeAttribute("data-chapter");
  };
  if (!stage || stage.failed || !stage.camera) {
    root.setAttribute("data-journey", "fallback");
    return { ...empty, scene, destroy: undo };
  }

  // 2. The chapters: keyframes filled in, then one path for the camera and one for where it looks.
  //    A "via" keyframe only shapes the path: no text, no event, no still, no slowing down.
  const raw = (Array.isArray(o.chapters) && o.chapters.length ? o.chapters : [{}]).map((c) => c || {});
  const n = raw.length;
  let fov = 32, told = 0;
  const keys = raw.map((c, i) => {
    const cam = c.camera || {};
    fov = finite(cam.fov, fov);
    const vec = (v, d) => new THREE.Vector3(...[0, 1, 2].map((k) => finite((v || d)[k], d[k])));
    const wide = { position: vec(cam.position, [0, 0, 9]), target: vec(cam.target, [0, 0, 0]), fov, roll: finite(cam.roll, 0) * DEG };
    const p = c.phone || {};
    const phone = { position: vec(p.position, wide.position.toArray()), target: vec(p.target, wide.target.toArray()),
                    fov: finite(p.fov, wide.fov), roll: finite(p.roll, cam.roll || 0) * DEG };
    const via = Boolean(c.via) && i > 0 && i < n - 1;
    return { at: c.at, wide, phone, via, chapter: via ? -1 : told++, progress: finite(c.progress, n > 1 ? i / (n - 1) : 0),
             params: c.params || {} };
  });
  const told2key = keys.filter((k) => !k.via).map((k) => keys.indexOf(k)); // chapter number -> keyframe
  // Uniform Catmull-Rom: a curve through every keyframe whose direction and speed run on without
  // a break through each of them (the slope at a keyframe is the line between its two neighbours).
  const path = (layout) => {
    const curve = (name) => (n > 1 ? new THREE.CatmullRomCurve3(keys.map((k) => k[layout][name].clone()), false, "catmullrom", 0.5) : null);
    return { position: curve("position"), target: curve("target"), fov: keys.map((k) => k[layout].fov),
             roll: keys.map((k) => k[layout].roll) };
  };
  const paths = { wide: path("wide"), phone: path("phone") };
  const progressList = keys.map((k) => k.progress), paramList = keys.map((k) => k.params);
  let ats = [];

  // Where each keyframe sits on the scroll: given; for a chapter, where its text is centred on
  // screen; for a via, half-way between its neighbours.
  function measure() {
    const box = root.getBoundingClientRect(), view = window.innerHeight || 1, extra = box.height - view;
    ats = keys.map((k, i) => {
      if (Number.isFinite(Number(k.at))) return clamp(Number(k.at), 0, 1);
      const step = steps[k.chapter];
      if (step && extra > 0) {
        const b = step.getBoundingClientRect();
        return clamp((b.top - box.top + b.height / 2 - view / 2) / extra, 0, 1);
      }
      return k.via ? NaN : (n > 1 ? i / (n - 1) : 0);
    });
    ats.forEach((v, i) => { if (Number.isNaN(v)) ats[i] = (ats[i - 1] + (Number.isNaN(ats[i + 1]) ? ats[i - 1] : ats[i + 1])) / 2; });
    for (let i = 1; i < n; i++) ats[i] = Math.max(ats[i], ats[i - 1]); // in order, whatever was given
  }

  // Trip position s (0..1) -> segment i and u (0..1) inside it. u is bent by a cubic whose slope
  // at each end is chosen so the camera's speed is the same just before and just after a
  // keyframe, even when the two segments take different lengths of scroll; at a chapter that
  // speed is lowered by dwell, so the move eases through it without stopping.
  function locate(s) {
    let i = 0;
    while (i < n - 2 && s > ats[i + 1]) i++;
    const span = ats[i + 1] - ats[i];
    if (n < 2 || !(span > 0)) return { i, u: s > ats[i] ? 1 : 0 };
    const u = clamp((s - ats[i]) / span, 0, 1);
    const before = i > 0 ? ats[i] - ats[i - 1] : span, after = i < n - 2 ? ats[i + 2] - ats[i + 1] : span;
    const calm = (k) => (keys[k].via ? 1 : 1 - clamp(o.dwell, 0, 1));
    const s0 = calm(i) * (2 * span) / (before + span), s1 = calm(i + 1) * (2 * span) / (span + after);
    const u2 = u * u, u3 = u2 * u; // Hermite: from 0 with slope s0 to 1 with slope s1
    return { i, u: (u3 - 2 * u2 + u) * s0 + (3 * u2 - 2 * u3) + (u3 - u2) * s1 };
  }

  // 3. Placing the camera: on the path, then a lean toward the pointer and a slow hand-held float,
  //    both measured in the camera's own right and up directions so they never change the framing.
  const camera = stage.camera, eye = new THREE.Vector3(), look = new THREE.Vector3();
  const forward = new THREE.Vector3(), right = new THREE.Vector3(), up = new THREE.Vector3();
  const focus = new THREE.Vector3(...[0, 1, 2].map((k) => finite((o.focus || [])[k], 0))), toFocus = new THREE.Vector3();
  let leanX = 0, leanY = 0;
  function place(i, u, time, delta, moving) {
    const p = paths[stage.size.aspect < o.narrow ? "phone" : "wide"];
    const g = n > 1 ? (i + u) / (n - 1) : 0;
    if (p.position) { p.position.getPoint(g, eye); p.target.getPoint(g, look); }
    else { eye.copy(keys[0].wide.position); look.copy(keys[0].wide.target); }
    const ease = (v, t) => (moving ? THREE.MathUtils.damp(v, t, 2, delta) : 0);
    leanX = ease(leanX, stage.pointer.x);
    leanY = ease(leanY, stage.pointer.y);
    forward.subVectors(look, eye);
    const distance = forward.length();
    forward.normalize();
    right.crossVectors(forward, THREE.Object3D.DEFAULT_UP).normalize();
    up.crossVectors(right, forward);
    const float = moving ? o.drift : 0; // two slow waves that never line up: no visible loop
    let dx = (leanX * o.parallax + float * Math.sin(time * 0.23)) * distance;
    let dy = (leanY * o.parallax * 0.6 + float * 0.7 * Math.sin(time * 0.17 + 1.3)) * distance;
    if (!moving) { // a still: the focus point's offset across the view, removed by sliding eye and target alike
      toFocus.subVectors(focus, eye);
      dx = toFocus.dot(right);
      dy = toFocus.dot(up);
      look.addScaledVector(right, dx).addScaledVector(up, dy);
    } // moving: only the eye moves, so the lean and the float turn the view round the target
    camera.position.copy(eye).addScaledVector(right, dx).addScaledVector(up, dy);
    camera.up.copy(THREE.Object3D.DEFAULT_UP);
    camera.lookAt(look);
    camera.rotateZ(monotone(p.roll, i, u));
    camera.fov = monotone(p.fov, i, u);
    camera.updateProjectionMatrix();
  }

  // 4. The moving trip.
  const follower = new Follower(0);
  let target = 0, lastRead = -1, lastWall = 0, current = -1, trip = 0, data = null;
  function applyScene(i, u) {
    scene.setProgress(clamp(monotone(progressList, i, u), 0, 1));
    const params = blendParams(paramList, i, u);
    if (params.data && scene.setData) {
      const changed = !data || params.data.some((v, k) => Math.abs(v - data[k]) > 1e-4);
      if (changed) scene.setData((data = params.data));
    }
    return params;
  }
  function announce(index, direction) {
    current = index;
    root.setAttribute("data-chapter", String(index));
    root.dispatchEvent(new CustomEvent("chapter", { detail: { index, direction, chapter: raw[told2key[index]] } }));
  }
  // Put the scene where the scroll already is before its first frame, so a page that opens half
  // way down does not show the first chapter for a moment.
  function prime() {
    target = lastRead = progressOf(root, "contain");
    trip = follower.snap(target);
    const { i, u } = locate(trip);
    place(i, u, 0, 0, true);
    applyScene(i, u);
  }
  stage.onFrame((time, delta) => {
    if (stage.still) return;
    const now = performance.now();
    // Read the scroll; a change takes over from setProgress. After a gap with no frames (the
    // section was off screen) while the trip sat at an end, jump: the visitor came back elsewhere.
    const read = progressOf(root, "contain");
    if (read !== lastRead) { target = read; lastRead = read; }
    const away = now - lastWall > 300 && (trip <= 0.001 || trip >= 0.999);
    trip = current < 0 || away ? follower.snap(target) : follower.step(target, delta, o.inertia);
    lastWall = now;
    const { i, u } = locate(trip);
    place(i, u, time, delta, true);
    const params = applyScene(i, u);
    // The current chapter is the nearest keyframe; a new one has to be nearer by HOLD, so the
    // text does not flicker when the trip rests half-way.
    const gap = (c) => Math.abs(trip - ats[told2key[c]]);
    let best = 0;
    for (let c = 1; c < told2key.length; c++) if (gap(c) < gap(best)) best = c;
    if (current < 0) announce(best, 0);
    else if (best !== current && gap(best) + HOLD < gap(current)) {
      announce(best, best > current ? 1 : -1);
    }
    if (o.onUpdate) o.onUpdate({ progress: trip, target, index: current, params });
  });

  // 5. Reduced motion: one still per chapter. The stage draws only when asked (invalidate); each
  //    frame is read back right after three has drawn it, while the picture is still in the buffer.
  const stills = [];
  let stillIndex = 0, rendering = false, queued = false, savedStyle = null;
  const owned = [];
  function slots() {
    return told2key.map((key, i) => {
      const step = steps[i];
      if (!step) return null;
      let slot = step.querySelector("[data-chapter-still]");
      if (!slot) {
        slot = document.createElement("figure");
        slot.className = "journey-still";
        slot.setAttribute("data-chapter-still", "");
        step.appendChild(slot);
        owned.push(slot);
      }
      let img = slot.querySelector("img[data-journey-still]");
      if (!img) {
        img = document.createElement("img");
        img.setAttribute("data-journey-still", "");
        img.alt = raw[key].alt || "";
        img.decoding = "async";
        slot.appendChild(img);
        owned.push(img);
      }
      return img;
    });
  }
  function renderStill() {
    const { i, u } = locate(ats[told2key[stillIndex]]);
    place(i, u, 0, 0, false);
    applyScene(i, u);
    stage.invalidate();
  }
  function makeStills() {
    if (rendering) { queued = true; return; }
    measure();
    rendering = true;
    stillIndex = 0;
    renderStill();
  }
  stage.scene.onAfterRender = () => {
    if (!stage.still || !rendering) return;
    const img = stills[stillIndex];
    if (img) {
      try { img.src = stage.canvas.toDataURL("image/webp", 0.9); } catch (error) { /* a tainted canvas: leave the slot empty */ }
    }
    // The next one after this frame has finished: an invalidate() inside it would be swallowed.
    Promise.resolve().then(() => {
      if (stillIndex < told2key.length - 1) { stillIndex += 1; renderStill(); return; }
      rendering = false;
      if (queued) { queued = false; makeStills(); }
    });
  };

  function setMode(still) {
    root.setAttribute("data-journey", still ? "still" : "live");
    if (still) {
      // Draw off-screen at the size of a still: fixed, so the stage always counts as on screen.
      if (savedStyle === null) savedStyle = host.style.cssText;
      const width = Math.min(o.stillWidth, (steps[0] || root).clientWidth || o.stillWidth);
      host.style.cssText = `position:fixed;left:0;top:0;width:${width}px;height:${Math.round(width * o.stillRatio)}px;`
        + "opacity:0;pointer-events:none;z-index:-1;margin:0";
      stills.splice(0, stills.length, ...slots());
      makeStills();
    } else {
      if (savedStyle !== null) host.style.cssText = savedStyle;
      savedStyle = null;
      for (const node of owned.splice(0)) node.remove();
      stills.length = 0;
      current = -1; // the next frame snaps to the scroll and announces the chapter
    }
  }
  offs.push(stage.onResize(() => { measure(); if (stage.still && stills.length) makeStills(); }));
  offs.push(stage.onTokens(() => { if (stage.still && stills.length) makeStills(); }));
  measure();
  setMode(stage.still);
  if (!stage.still) prime();
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const onReduced = () => setMode(stage.still);
  if (reduced.addEventListener) {
    reduced.addEventListener("change", onReduced);
    offs.push(() => reduced.removeEventListener("change", onReduced));
  }
  offs.push(() => setMode(false), () => { stage.scene.onAfterRender = nothing; });

  function goTo(index) {
    const c = clamp(Math.round(finite(index, 0)), 0, told2key.length - 1);
    if (stage.still) { if (steps[c]) steps[c].scrollIntoView({ block: "start" }); return; }
    const box = root.getBoundingClientRect(), extra = box.height - (window.innerHeight || 0);
    window.scrollTo({ top: window.scrollY + box.top + ats[told2key[c]] * Math.max(extra, 0), behavior: "smooth" });
  }

  let destroyed = false;
  return {
    scene,
    stage,
    goTo,
    setProgress(p) { if (Number.isFinite(Number(p))) target = clamp(Number(p), 0, 1); },
    setData(values) { if (scene.setData) scene.setData(values); },
    setPointer(x, y) { if (scene.setPointer) scene.setPointer(x, y); },
    pause(reason) { scene.pause(reason); },
    resume(reason) { scene.resume(reason); },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      undo();
    },
  };
}
