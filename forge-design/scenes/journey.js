/**
 * journey.js: the director for look level 5. A scroll-driven trip through one 3D scene.
 *
 * A tall section holds a pinned canvas (position: sticky) and text chapters that scroll over it.
 * While the section scrolls, the journey flies the camera along a smooth path through the
 * chapters' keyframes, walks the scene's own progress with it, and tells the page which chapter
 * is current. It plays as one camera move in a film: the scroll is followed with inertia, the move
 * eases through each chapter without stopping, and a flick or a turn of the wheel bends the move
 * instead of jerking it or overshooting.
 *
 *   <section class="journey">
 *     <div data-journey-stage aria-hidden="true"></div>   pinned by page CSS (made, sticky, when missing)
 *     <article data-chapter>...</article> ...              one per chapter, in order
 *   </section>
 *
 *   import { mount as form } from "./scenes/form.js";
 *   const trip = mount(section, {
 *     scene: (el) => form(el, { side: "centre", progressEase: 0.05 }),
 *     chapters: [
 *       { camera: { position: [-1, 0.5, 9], target: [-2, 0, 0], fov: 32 }, progress: 0 },
 *       { camera: { position: [2, -1, 5], target: [0.5, 0, 0] }, progress: 0.5,
 *         phone: { position: [0, -1, 8], target: [0, -2, 0] } },
 *       { camera: { position: [0, 8, 6], target: [0, 0, 0], roll: 5 }, progress: 1 },
 *     ],
 *   });
 *   section.addEventListener("chapter", (e) => light(e.detail.index, e.detail.direction));
 *
 * Options (only scene is needed):
 *   scene       a mounted scene of this kit, or a factory (element) => scene, called with the stage
 *               element. Mount a scene of your own with progressEase: 0.05: the journey eases itself.
 *   chapters    keyframes { at, until, camera, phone, still, progress, params, via, alt }:
 *     at        0..1 on the section's scroll. Default: where its [data-chapter] is centred on screen,
 *               measured again whenever the section, a chapter or the stage changes size.
 *     until     0..1: the chapter stays the current one up to here, for a long chapter whose text
 *               stays while the camera rides on toward the next keyframe (default: at).
 *     camera    { position: [0, 0, 9], target: [0, 0, 0], fov: the one before (32), roll: 0 degrees }.
 *     phone     the same, below the `narrow` aspect; still: the same, for its reduced-motion still
 *               (without it the still slides camera sideways to centre `focus`). Missing parts: camera.
 *     progress  what the scene's setProgress gets here (default: evenly spread 0..1).
 *     params    { name: number | [numbers] } blended along and handed to onUpdate; data -> setData.
 *     via       true: a waypoint that only bends the path (pull back while the shape changes): no
 *               text, no event, no still, no slowing. Without at: half-way between its neighbours.
 *     alt       text for its still image (default "", as the chapter text says it all).
 *   steps       the chapter elements, a selector or a list. Default "[data-chapter]" in the section.
 *   inertia     0.65. Seconds the camera lags the scroll on average (settled in about twice that).
 *   dwell       0.3. How much the move slows at a chapter: 0 not at all, 1 to a stop.
 *   parallax    0.09, drift 0.01. A lean toward the pointer (0.09 swings the camera about 5 degrees
 *               round its target, with a slight roll and a small slide after the pointer) and a slow
 *               hand-held float, as parts of the camera's distance.
 *   narrow      0.8. Below this width/height the phone keyframes are used.
 *   stillWidth  880, stillRatio 0.62: CSS size of a still. focus [0, 0, 0]: the subject's middle.
 *   keepScene   false. true: destroy() leaves a scene you mounted yourself alive.
 *   onUpdate    fn({ progress, target, index, params }) after every frame, and also before the first
 *               frame (index -1, mount() has not returned yet) and before each still is drawn, so a
 *               page can pass the other params on to the scene in time (form's setThread, say).
 *
 * While live, the section also carries --journey-x and --journey-y (0..1 across the stage element,
 * y down, eased with the camera's lean) and --journey-pointer (0..1, eased: is there a pointer), so
 * page CSS can light the side of the scene the pointer is on.
 *
 * The section gets data-journey="live" | "still" | "fallback" and data-journey-chapter="<index>"
 * (data-chapter stays the mark of a chapter), and a "chapter" event (detail { index, direction: 1,
 * -1, or 0 the first time, chapter }) each time the current chapter changes. The page lights the
 * text and does the layout.
 *
 * The camera is the journey's while it runs. It keeps the view on screen from one frame to the
 * next, so whatever the scene works out from it in its own frame, which runs first (a hover
 * raycast, say), matches what the visitor sees, and a scene's own moves of the camera do not move
 * the picture. Between frames its fov is the scene's own, so the scene's layout on a resize does
 * not follow the trip. A scene that sets its own projection in its frame before it raycasts
 * (datascape.js does, for its slide) aims that ray with its own fov: give its chapters that fov
 * (30 for datascape.js) and the hover is exact; with another fov it is off by the ratio of the two.
 *
 * Reduced motion: no pin and no trip. Each chapter gets its own still, rendered from its keyframe
 * into an <img> in its [data-chapter-still] element (a <figure class="journey-still"> is appended
 * to the chapter when there is none); [data-journey="still"] CSS puts it beside the text. Stills are
 * made again after a theme change or a resize. Do not hide the stage element: it draws them.
 * Keyboard: the page scrolls as any page (arrows, space, Tab into a chapter); goTo(index) scrolls
 * to a chapter for a table of contents.
 *
 * Returns { setProgress, setData, setPointer, pause, resume, goTo, destroy, scene, stage }:
 * setProgress(p) flies to p (0..1) until the next scroll; setData goes to the scene (chapter
 * params.data wins); the others go to the scene; destroy() undoes all the journey added.
 *
 * Poster: a [data-scene-poster] image in the stage element. Without WebGL the section gets
 * data-journey="fallback", the poster stays and the chapters scroll over it.
 *
 * Cost: the scene's own, plus a few splines and filters a frame. Under reduced motion one render
 * and one WebP image per chapter, again after a theme change or a resize.
 */
import * as THREE from "three";
import { progressOf } from "./stage.js";

const DEFAULTS = { inertia: 0.65, dwell: 0.3, parallax: 0.09, drift: 0.01, narrow: 0.8,
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
 * Fritsch and Butland): the slope at each point is the gentler of its two sides, and 0 where the
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
  for (const [key, v] of Object.entries(list[0] || {})) {
    const along = (j) => list.map((p) => (j < 0 ? finite(p[key], v) : finite((p[key] || [])[j], v[j])));
    if (Array.isArray(v)) out[key] = v.map((_, j) => monotone(along(j), i, u));
    else if (Number.isFinite(Number(v))) out[key] = monotone(along(-1), i, u);
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
      host = root.insertBefore(document.createElement("div"), root.firstChild);
      host.setAttribute("data-journey-stage", "");
      host.setAttribute("aria-hidden", "true");
      host.style.cssText = "position:sticky;top:0;height:100vh;margin-bottom:-100vh;overflow:hidden";
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
    root.removeAttribute("data-journey-chapter");
    for (const name of ["--journey-x", "--journey-y", "--journey-pointer"]) root.style.removeProperty(name);
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
    const like = (p = {}) => ({ position: vec(p.position, wide.position.toArray()), target: vec(p.target, wide.target.toArray()),
                                fov: finite(p.fov, wide.fov), roll: finite(p.roll, cam.roll || 0) * DEG });
    const phone = like(c.phone), still = like(c.still);
    still.own = Boolean(c.still);
    const via = Boolean(c.via) && i > 0 && i < n - 1;
    return { at: c.at, until: c.until, wide, phone, still, via, chapter: via ? -1 : told++,
             progress: finite(c.progress, n > 1 ? i / (n - 1) : 0), params: c.params || {} };
  });
  const told2key = keys.filter((k) => !k.via).map((k) => keys.indexOf(k)); // chapter number -> keyframe
  // Uniform Catmull-Rom: a curve through every keyframe whose direction and speed run on without
  // a break through each of them (the slope at a keyframe is the line between its two neighbours).
  const path = (layout) => {
    const curve = (name) => (n > 1 ? new THREE.CatmullRomCurve3(keys.map((k) => k[layout][name].clone()), false, "catmullrom", 0.5) : null);
    return { position: curve("position"), target: curve("target"), fov: keys.map((k) => k[layout].fov),
             roll: keys.map((k) => k[layout].roll) };
  };
  const paths = { wide: path("wide"), phone: path("phone"), still: path("still") };
  const progressList = keys.map((k) => k.progress), paramList = keys.map((k) => k.params);
  let ats = [], untils = [];

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
    untils = keys.map((k, i) => Math.max(ats[i], Number.isFinite(Number(k.until)) ? clamp(Number(k.until), 0, 1) : ats[i]));
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
  const turn = new THREE.Matrix4();
  // The camera is the journey's while it runs. Its matrices are set in place() and nowhere else
  // (three's own updates of them are off), so from one frame to the next they hold the view on
  // screen: a scene's own frame, which runs before the journey's, works out what it needs from the
  // camera (a hover raycast, say) against what the visitor sees, and a scene that moves the camera
  // itself no longer moves the picture. Only the fov is the scene's own again after each frame (the
  // projection matrix keeps the drawn view), so a layout worked out from it on a resize (viewSize)
  // does not change with the trip. destroy() gives the scene its camera back as it was.
  const home = { position: camera.position.clone(), quaternion: camera.quaternion.clone(), up: camera.up.clone(),
                 fov: camera.fov, matrix: camera.matrixAutoUpdate, world: camera.matrixWorldAutoUpdate };
  let ownFov = camera.fov, lent = false;
  camera.matrixAutoUpdate = camera.matrixWorldAutoUpdate = false;
  const fovBack = () => { if (lent) camera.fov = ownFov; lent = false; };
  const giveBack = () => {
    fovBack();
    camera.matrixAutoUpdate = home.matrix; camera.matrixWorldAutoUpdate = home.world;
    camera.position.copy(home.position); camera.quaternion.copy(home.quaternion); camera.up.copy(home.up);
    camera.fov = home.fov; camera.updateMatrixWorld(true); camera.updateProjectionMatrix();
  };
  let leanX = 0, leanY = 0, present = 0;
  function place(i, u, time, delta, moving) {
    const own = !moving && keys[i + Math.round(u)] && keys[i + Math.round(u)].still.own; // a still of its own
    const p = paths[own ? "still" : stage.size.aspect < o.narrow ? "phone" : "wide"];
    const g = n > 1 ? (i + u) / (n - 1) : 0;
    if (p.position) { p.position.getPoint(g, eye); p.target.getPoint(g, look); }
    else { eye.copy(keys[0].wide.position); look.copy(keys[0].wide.target); }
    const ease = (v, t) => (moving ? THREE.MathUtils.damp(v, t, 2, delta) : 0);
    leanX = ease(leanX, stage.pointer.x);
    leanY = ease(leanY, stage.pointer.y);
    present = ease(present, stage.pointer.active ? 1 : 0);
    forward.subVectors(look, eye);
    const distance = forward.length();
    forward.normalize();
    right.crossVectors(forward, THREE.Object3D.DEFAULT_UP).normalize();
    up.crossVectors(right, forward);
    const float = moving ? o.drift : 0; // two slow waves that never line up: no visible loop
    let dx = (leanX * o.parallax + float * Math.sin(time * 0.23)) * distance;
    let dy = (leanY * o.parallax * 0.6 + float * 0.7 * Math.sin(time * 0.17 + 1.3)) * distance;
    if (!moving && !own) { // a still: the focus point's offset across the view, removed by sliding eye and target alike
      toFocus.subVectors(focus, eye);
      dx = toFocus.dot(right);
      dy = toFocus.dot(up);
      look.addScaledVector(right, dx).addScaledVector(up, dy);
    } // moving: only the eye moves, so the lean and the float turn the view round the target
    camera.position.copy(eye).addScaledVector(right, dx).addScaledVector(up, dy);
    // Moving: keep the distance, so the lean swings the camera round its target (an orbit), roll a
    // little with it, and slide eye and target together a third as far the other way: the subject
    // turns toward the pointer and drifts a little after it, so the lean reads at any distance.
    if (moving) {
      camera.position.sub(look).setLength(distance).add(look);
      const slide = -0.35 * o.parallax * distance;
      toFocus.copy(right).multiplyScalar(leanX * slide).addScaledVector(up, leanY * 0.6 * slide);
      camera.position.add(toFocus);
      look.add(toFocus);
    }
    camera.up.copy(THREE.Object3D.DEFAULT_UP);
    turn.lookAt(camera.position, look, camera.up); // camera.lookAt() would read the held matrixWorld
    camera.quaternion.setFromRotationMatrix(turn);
    camera.rotateZ(monotone(p.roll, i, u) - (moving ? leanX * o.parallax * 0.3 : 0));
    if (!lent) ownFov = camera.fov; // the scene may have changed its own since the last frame
    lent = true;
    camera.fov = monotone(p.fov, i, u);
    camera.updateProjectionMatrix();
    camera.updateMatrix();
    if (camera.parent) camera.matrixWorld.multiplyMatrices(camera.parent.matrixWorld, camera.matrix);
    else camera.matrixWorld.copy(camera.matrix);
    camera.matrixWorldInverse.copy(camera.matrixWorld).invert();
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
  // The page's onUpdate, outside a frame (before the first one, before a still): a mistake in it
  // is reported, and the journey goes on.
  function tell(state) {
    try { if (o.onUpdate) o.onUpdate(state); } catch (error) { console.error(error); }
  }
  function announce(index, direction) {
    current = index;
    root.setAttribute("data-journey-chapter", String(index)); // not data-chapter: that marks the chapters
    root.dispatchEvent(new CustomEvent("chapter", { detail: { index, direction, chapter: raw[told2key[index]] } }));
  }
  // Put the scene where the scroll already is before its first frame, so a page that opens half
  // way down does not show the first chapter for a moment.
  function prime() {
    target = lastRead = progressOf(root, "contain");
    trip = follower.snap(target);
    const { i, u } = locate(trip);
    tell({ progress: trip, target, index: -1, params: applyScene(i, u) });
  }
  offs.push(stage.onFrame((time, delta) => {
    if (stage.still) { // a still being made: its chapter's camera, nothing else
      if (rendering) place(...Object.values(locate(ats[told2key[stillIndex]])), 0, 0, false);
      return;
    }
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
    const css = root.style;
    css.setProperty("--journey-x", ((leanX + 1) / 2).toFixed(4));
    css.setProperty("--journey-y", ((1 - leanY) / 2).toFixed(4));
    css.setProperty("--journey-pointer", present.toFixed(3));
    // The current chapter is the nearest keyframe (or stretch, with until); a new one has to be
    // nearer by HOLD, so the text does not flicker when the trip rests half-way.
    const gap = (c) => { const k = told2key[c]; return Math.max(ats[k] - trip, trip - untils[k], 0); };
    let best = 0;
    for (let c = 1; c < told2key.length; c++) if (gap(c) < gap(best)) best = c;
    if (current < 0) announce(best, 0);
    else if (best !== current && gap(best) + HOLD < gap(current)) announce(best, best > current ? 1 : -1);
    if (o.onUpdate) o.onUpdate({ progress: trip, target, index: current, params });
  }));

  // 5. Reduced motion: one still per chapter. The stage draws only when asked (invalidate); each
  //    frame is read back right after three has drawn it, while the picture is still in the buffer.
  const stills = [];
  let stillIndex = 0, rendering = false, queued = false, savedStyle = null;
  const owned = [];
  const make = (parent, tag, mark) => {
    const node = parent.appendChild(document.createElement(tag));
    node.setAttribute(mark, "");
    owned.push(node);
    return node;
  };
  function slots() { // chapter -> its <img>, made (and later removed) where the page has none
    return told2key.map((key, i) => {
      if (!steps[i]) return null;
      let slot = steps[i].querySelector("[data-chapter-still]");
      if (!slot) (slot = make(steps[i], "figure", "data-chapter-still")).className = "journey-still";
      const img = slot.querySelector("img[data-journey-still]") || make(slot, "img", "data-journey-still");
      img.alt = raw[key].alt || "";
      return img;
    });
  }
  function renderStill() {
    const at = ats[told2key[stillIndex]], { i, u } = locate(at);
    // Before the frame: the stage eases progress, and the scene its own params, before it draws.
    tell({ progress: at, target: at, index: stillIndex, params: applyScene(i, u) });
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
    fovBack();
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
  // The chapters' places also move while the pinned stage keeps its size: a web font that loads,
  // content added, a <details> opened. Measuring changes no layout, so this cannot feed itself.
  if (typeof ResizeObserver === "function") {
    const layout = new ResizeObserver(() => measure());
    for (const element of [root, ...steps]) if (element && element.nodeType === 1) layout.observe(element);
    offs.push(() => layout.disconnect());
  }
  offs.push(stage.onTokens(() => { if (stage.still && stills.length) makeStills(); }));
  measure();
  setMode(stage.still);
  if (!stage.still) prime();
  // The stage turns still or live when the visitor's setting changes; the layout follows here.
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)"), onReduced = () => setMode(stage.still);
  reduced.addEventListener("change", onReduced);
  offs.push(() => reduced.removeEventListener("change", onReduced));
  offs.push(() => setMode(false), () => { stage.scene.onAfterRender = nothing; giveBack(); });

  function goTo(index) {
    const c = clamp(Math.round(finite(index, 0)), 0, told2key.length - 1);
    if (stage.still) { if (steps[c]) steps[c].scrollIntoView({ block: "start" }); return; }
    const box = root.getBoundingClientRect(), extra = box.height - (window.innerHeight || 0);
    window.scrollTo({ top: window.scrollY + box.top + ats[told2key[c]] * Math.max(extra, 0), behavior: "smooth" });
  }

  return {
    scene,
    stage,
    goTo,
    setProgress(p) { if (Number.isFinite(Number(p))) target = clamp(Number(p), 0, 1); },
    setData(values) { if (scene.setData) scene.setData(values); },
    setPointer(x, y) { if (scene.setPointer) scene.setPointer(x, y); },
    pause(reason) { scene.pause(reason); },
    resume(reason) { scene.resume(reason); },
    destroy: undo, // offs empties itself, so a second call does nothing
  };
}
