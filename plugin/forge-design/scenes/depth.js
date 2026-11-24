/**
 * depth.js: real depth in an interface with CSS 3D only, no WebGL (scene kit, look level 3 and up).
 *
 * Four behaviours, each switched on by a data-depth attribute in the page's own markup:
 *   data-depth="tilt"   a card that leans toward the pointer: the side under the pointer sinks a few
 *                       degrees, children marked data-depth-layer="1|2|3" rise off the card to their
 *                       own height, a soft glare follows the pointer and the shadow grows with the
 *                       lift. On a touch screen (no hover) the card leans gently by its place on the
 *                       screen, so the lean changes as the page scrolls.
 *   data-depth="stack"  a container whose child elements are panels piled behind one another (the
 *                       first child in front). While the stack scrolls in, the panels step forward,
 *                       front panel first, into a cascade where each one peeks out above the next.
 *                       The cascade rises about (panels - 1) x stackGap above the front panel: give
 *                       the stack that much padding-top, or the panels cover what lies above it.
 *   data-depth="fold"   a panel that opens like a page turning, hinged on one side, once it enters the
 *                       viewport. Folds that enter together open one after the other.
 *                       data-depth-axis="left" (default), "right", "top" or "bottom" names the hinge.
 *   data-depth="scene"  a hero whose data-depth-layer children move at their own depth with the
 *                       pointer and with scroll. Negative numbers lie behind, positive ones in front.
 *                       Layers may nest: a layer inside a layer moves on top of its parent.
 * A bare data-depth is a tilt card. A data-depth-layer belongs to the nearest data-depth around it.
 *
 *   <link rel="stylesheet" href="/scenes/depth.css">
 *   import { mount } from "./scenes/depth.js";
 *   const depth = mount(document.querySelector("main"), { tilt: 7 });   // level 3: 6 degrees or more
 *   depth.destroy();          // when the page or the component goes away
 *
 * mount(root, options) finds every [data-depth] inside root (root included) at that moment. For
 * elements added later, mount again (over them or over a root around them): an element an earlier
 * mount still moves is left to it, so nothing moves twice. It returns { setProgress, setData,
 * setPointer, pause, resume, destroy, stage }. Options (all optional; a data-depth-<option>
 * attribute on one element wins for it and is read on every frame, so a page may change it at any
 * time; a value that is not a number where a number belongs keeps the default):
 *   tilt         5     degrees a tilt card leans at its edge (never more than 8: text gets hard to read).
 *                      Look level 3 asks 6 or more at the edge: pass 7 there.
 *   ease         0.55  seconds the eased motion needs for most of the way. Heavy and calm on purpose.
 *   lift         9     pixels each layer number rises above a hovered card (layer 3: 27 px).
 *   raise        16    pixels the whole card comes toward the eye when fully lifted.
 *   rest         0     how raised a tilt card lies when nobody points at it, 0..1: it sits rest x raise
 *                      pixels nearer (drawn flat, as a crisp scale), with a deeper shadow and the glare
 *                      resting where the light comes from; its layers stay flat. data-depth-rest="0.6"
 *                      picks out one plan of three.
 *   light        "-0.5 -0.75"  where the light comes from across a card (x right, y down, -1..1): the
 *                      glare of a raised card rests there when nobody points at it.
 *   glare        true  the soft light that moves across a tilt card.
 *   perspective  1500  pixels between the eye and the screen for tilt cards and folds; a stack takes
 *                      --depth-perspective of depth.css (also 1500px). Smaller is stronger.
 *   touch        true  the gentle scroll tilt on touch screens.
 *   stackGap     56    pixels each stacked panel peeks out above the one in front of it: enough to
 *                      show some of its content, not only its title bar.
 *   stackDepth   80    pixels each stacked panel lies behind the one in front of it.
 *   stackTurn    "4 -6"  degrees (rotateX, rotateY) the whole stack stands turned at rest, so it
 *                      reads as screens in space in a still picture too. "0 0": a flat cascade.
 *   fold         72    degrees a fold starts turned away. foldTime 1.1 seconds the turn takes;
 *                      foldStagger 0.1 seconds between folds that enter together; foldOnce true
 *                      (false: it closes again once it has left the screen).
 *   shift        10    pixels a scene layer moves per layer number when the pointer is at the edge.
 *   turn         2.5   degrees the front layers of a scene turn toward the pointer.
 *   scrollShift  36    pixels a scene layer drifts per layer number over a scroll of its own height.
 *   drift        0.5   degrees a scene's front layers sway on their own, slowly, so a hero is never a
 *                      screenshot; layers also float a few pixels by their number. 0 switches it off.
 *   driftTime    10    seconds one sway takes, at least 2 (the other motions run at their own paces).
 *
 * setProgress(p)   0..1, or null to hand control back to the scroll: pins where every stack and scene
 *                  is, as if scrolled there. 0 is just below the viewport, 0.5 its middle in the middle
 *                  of the screen (a stack has stepped forward, a scene sits at rest), 1 gone above.
 *                  The same scale as progressOf(element, "cover") in stage.js. Folds keep their trigger.
 * setPointer(x, y) steer the pointer from code, -1..1 across the viewport, y up. The next real move
 *                  wins. Anything that is not a number (null, NaN) lets go, as if the pointer left.
 * setData()        does nothing: there is no data here. pause(reason) and resume(reason) stop and start
 *                  the motion; it runs again once every reason has been resumed. stage is null.
 *
 * Manners. Reduced motion, or html[data-motion="paused"] (the switch of lazy.js motionToggle): flat
 * and still, with nothing taken away. Cards lie flat, folds are open, scene layers rest, and a stack
 * shows its cascade as a flat picture. One frame loop serves every element of a mount; it runs only
 * while something moves, on screen, in a visible tab, and sleeps after (a scene with drift moves
 * while it is on screen). Any scroll wakes it, also one inside a scrolling element of the page.
 * Every element is marked data-depth-asleep while it is off screen or paused; depth.css then pauses
 * any CSS animation of the page's own inside it, so small live details (a line that travels, a dot
 * that breathes) stop with the rest. destroy() removes every listener and observer, the glare
 * elements it added, and every style and attribute it wrote.
 *
 * What it owns: the transform and transform-origin of each element it moves, the opacity of folds
 * and the z-index of stack panels and of a raised card; put a resting turn of your own in the CSS
 * rotate, translate or scale properties, which add to it.
 * depth.css gives the shadows (--depth-shadow), the glare and the shade, and uses the ::after of
 * stack panels and folds. Overflow, opacity or a filter on a tilt card flattens its layers: put those
 * on a child. Colours come only from the page's --color-* tokens.
 *
 * Sharp edges and text: depth comes from transform and shadow only, never blur. Whatever turns in 3D
 * has its text resampled, so what lies still is drawn flat where it can be: at rest a card's or a
 * fold's transform is removed or replaced by its exact flat equal (a raised card as a scale), a
 * scene's layers keep a translate on whole pixels, and a stack with stackTurn "0 0" rests as a
 * cascade of translate plus scale on whole pixels. All of these the browser draws crisp. Three
 * things stay in 3D, so their text stays resampled: a stack turned by stackTurn (the default
 * "4 -6"; "0 0" gives crisp text), a tilt card on a touch screen (it keeps its lean), and the front
 * layers of a scene while drift sways them (as long as it is on screen; drift 0 lets them rest) or
 * a pointer over it turns them. Keep the tilt small. Each tilt card has its own perspective(), so a
 * card at the end of a row rises as straight as one in the middle.
 *
 * Poster: none needed; without JavaScript every element is the plain page. Cost, no library:
 * depth.js is 39 KB of source with these notes, 12 KB minified and 5 KB minified and gzipped
 * (terser -c -m, then gzip -9); depth.css is 8 KB of source, 1 KB minified and gzipped. Per frame,
 * only the elements on screen that still move: one measurement each, then writes of transform,
 * opacity and custom properties. Shadows repaint while a card lifts.
 */

const DEFAULTS = {
  tilt: 5, ease: 0.55, lift: 9, raise: 16, glare: true, perspective: 1500, touch: true,
  rest: 0, light: "-0.5 -0.75", stackGap: 56, stackDepth: 80, stackTurn: "4 -6",
  fold: 72, foldTime: 1.1, foldStagger: 0.1, foldOnce: true,
  shift: 10, turn: 2.5, scrollShift: 36, drift: 0.5, driftTime: 10,
};
const MAX_TILT = 8;
// On a touch screen a card at the top or bottom of the screen leans this part of its tilt (2.25
// degrees at the default 5): a sheet held below or above the eye, its text still easy to read. It
// lies a third raised: shadow enough to say it can be touched, less than a hovered card's full lift.
const TOUCH = { lean: 0.45, lift: 0.35 };
// The stack's entrance, for panel i (0 in front):
const ENTRY = {
  drop: 110,    // px it starts below its place: a clear rise, about a title bar and two rows of content
  fan: 0.2,     // plus this part of the gap per panel behind, so the pile arrives fanned out and closes up
  far: 1.6,     // stack depths it starts behind the screen, so it comes from deep in the page,
  farStep: 1.4, // plus this many per panel behind (at rest each lies 1 deeper): back panels travel most
  tip: 14,      // degrees it starts tipped back about its bottom edge: reads as standing up, never edge-on
  lag: 0.45,    // part of the progress before the last panel starts: one after another, close together
};
// Each panel further back sinks 24 percent further into the page colour, but never past 70 percent,
// so the last one still shows its content; its shadow is 30 percent weaker, as it lies nearer the
// panel behind it.
const PANEL = { dim: 0.24, dimMost: 0.7, shadowStep: 0.3 };
// A fold opens once its top is above the lowest tenth of the screen and its bottom is below the top
// 6 percent: a panel showing only a sliver at an edge waits, so its turn is seen. Turned edge-on it
// would be at most 55 percent in shade: a page turned from the light, not a black one.
const FOLD = { below: 0.9, above: 0.06, shade: 0.55 };
// A scene's own slow life. Every layer floats `across` px sideways and `upDown` px up and down per
// layer number (water rises and falls more than it drifts); front layers also turn, the sway in
// degrees about the vertical axis and `nod` of it about the horizontal one, as a hung picture swings
// more than it nods. Each motion has its own pace, as a part of driftTime (1 for the sway): 1.21,
// 0.83 and 1.37 are far from simple ratios of each other and of 1, so the whole takes minutes to
// repeat. Each motion starts at its own point of the cycle (the offsets, in radians), and the layers
// are spread over it, `spread` per place in the page and `byNumber` per layer number, so no two move
// in step. The sway fades in over `wake` seconds: the first frame is the resting picture.
const DRIFT = { across: 3, upDown: 5, nod: 0.7, paceAcross: 1.21, paceUpDown: 0.83, paceNod: 1.37,
  offAcross: 2, offUpDown: 1, offNod: 0.6, spread: 1.7, byNumber: 0.9, wake: 3 };
// A fold's hinge, and the turn that sends its free edge away from the eye: rotateY(+a) moves the
// right edge back, rotateX(-a) the bottom edge.
const HINGES = { left: ["0% 50%", "rotateY", 1], right: ["100% 50%", "rotateY", -1],
  top: ["50% 0%", "rotateX", -1], bottom: ["50% 100%", "rotateX", 1] };
const WRITTEN = ["transform", "transform-origin", "opacity", "z-index", "--depth-lift", "--depth-sx", "--depth-sy",
  "--depth-gx", "--depth-gy", "--depth-ga", "--depth-gm", "--depth-dim", "--depth-shade"];
const MARKS = ["data-depth-tone", "data-depth-moving", "data-depth-flat", "data-depth-asleep"];
// Every element a live mount() moves, so a second mount() over the same page leaves it alone.
const owned = new WeakSet();
// NaN gives lo, so a bad number can never reach a spring and stay there.
const clamp = (v, lo = 0, hi = 1) => (v > lo ? (v < hi ? v : hi) : lo);
const mix = (a, b, t) => a + (b - a) * t;
const smooth = (t) => t * t * (3 - 2 * t);
// Two decimals: finer than a screen can show, and the style strings stay short.
const px = (v) => Math.round(v * 100) / 100;
const TAU = Math.PI * 2;
const RAD = Math.PI / 180;
// "4 -6" -> [4, -6]; anything unreadable counts as 0.
const pair = (text) => { const [a, b] = String(text).trim().split(/[\s,]+/).map(Number); return [a || 0, b || 0]; };

// A critically damped spring: the fastest way to a target that never overshoots, with no sudden
// start. Solved exactly, so it moves the same at 30 or 144 frames a second. With c the distance
// still to go and k = speed + omega * c, after dt seconds:
//   distance = (c + k dt) e^(-omega dt),   speed = (speed - omega k dt) e^(-omega dt).
// It covers about 90 percent of the way in 4 / omega seconds, so omega = 4 / ease.
function spring(value = 0) { return { x: value, v: 0, to: value }; }
function settle(s, omega, dt, snap = false) {
  if (snap) { s.x = s.to; s.v = 0; return true; }
  const c = s.x - s.to, k = s.v + omega * c, e = Math.exp(-omega * dt);
  s.x = s.to + (c + k * dt) * e;
  s.v = (s.v - omega * k * dt) * e;
  // Within 0.002 (px, degrees or parts of the way) and slower than 0.01 a second: nothing to see.
  if (Math.abs(s.x - s.to) < 0.002 && Math.abs(s.v) < 0.01) { s.x = s.to; s.v = 0; return true; }
  return false;
}

// How far the middle of the box a leaning card fills lies from the card's own middle. The card is
// drawn as perspective(P) translateZ(z) rotateX(a) rotateY(b) about its middle, which stays in place,
// but the near side is drawn larger, so the box around it shifts toward that side.
function leanShift(w, h, { P, z, a, b }) {
  if (!a && !b) return [0, 0];
  const xs = [], ys = [], [ca, sa, cb, sb] = [Math.cos(a * RAD), Math.sin(a * RAD), Math.cos(b * RAD), Math.sin(b * RAD)];
  for (const [x, y] of [[-w / 2, -h / 2], [w / 2, -h / 2], [-w / 2, h / 2], [w / 2, h / 2]]) {
    // rotateY first: z = -x sin b; then rotateX; then translateZ; then the perspective divide.
    const zb = -x * sb, k = P / (P - (y * sa + zb * ca + z));
    xs.push(x * cb * k); ys.push((y * ca - zb * sa) * k);
  }
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
}

// Where a tilt card lies on the screen without its own lean. getBoundingClientRect() knows every
// scrolled container, fixed or sticky place and transform around the card, but it also sees the lean
// depth.js drew last frame; that shift is taken back out, so the pointer reads the card as it lies
// and a measurement never moves the target the card is easing toward.
function cardRect(item) {
  const el = item.el, box = el.getBoundingClientRect(), w = el.offsetWidth, h = el.offsetHeight;
  const [dx, dy] = item.drawn ? leanShift(w, h, item.drawn) : [0, 0];
  const left = (box.left + box.right - w) / 2 - dx, top = (box.top + box.bottom - h) / 2 - dy;
  return { left, top, width: w, height: h, bottom: top + h };
}

// Is the page dark? Read --color-bg as the browser computes it, on a probe element. Dark is a
// lightness under half way, or a luminance (of the encoded channels) under 0.4, about where light
// text starts to read better than dark.
function darkPage(root) {
  const probe = document.createElement("span");
  probe.style.cssText = "position:absolute;display:none;color:var(--color-bg, Canvas)";
  root.appendChild(probe);
  const text = getComputedStyle(probe).color;
  probe.remove();
  const n = (text.match(/[\d.]+%?/g) || []).map(parseFloat);
  if (/^(ok)?l(ch|ab)\(/.test(text)) return n[0] < (text.includes("%") ? 50 : text.startsWith("ok") ? 0.5 : 50);
  if (n.length < 3) return false;
  const scale = /^color\(/.test(text) ? 1 : 255; // color(srgb 0.1 0.1 0.1) or rgb(26, 26, 26)
  return 0.2126 * n[0] / scale + 0.7152 * n[1] / scale + 0.0722 * n[2] / scale < 0.4;
}

export function mount(root = document.body, options = {}) {
  const m = startDepth(root, options);
  findElements(m);
  listen(m);
  tone(m);
  asleep(m);
  still(m);
  // Before the first frame, fold panels must already be turned away, or they would flash open.
  if (!flat(m)) {
    for (const item of m.items) {
      if (item.kind === KINDS.fold) KINDS.fold.update(m, item, { top: 1e9, bottom: 1e9 }, { h: 1, batch: 0, dt: 0, now: 0 });
    }
  }
  return depthHandle(m);
}

// What one mount() keeps: every function below takes it as `m`.
function startDepth(root, options) {
  const o = { ...DEFAULTS, ...options };
  for (const name in DEFAULTS) { // a number option that is not a number (NaN, null, "x") keeps the default
    if (typeof DEFAULTS[name] !== "number") continue;
    const value = typeof o[name] === "string" && o[name].trim() ? Number(o[name]) : o[name];
    o[name] = Number.isFinite(value) ? value : DEFAULTS[name];
  }
  return {
    o, root,
    reduced: window.matchMedia("(prefers-reduced-motion: reduce)"),
    hover: window.matchMedia("(hover: hover) and (pointer: fine)"),
    scheme: window.matchMedia("(prefers-color-scheme: dark)"),
    pointer: { x: 0, y: 0, has: false }, pauses: new Set(), items: [], cleanups: [],
    frame: 0, last: 0, forced: null, destroyed: false,
    touched: new Map(), // element -> its own inline values of what depth.js writes
  };
}

const flat = (m) => m.reduced.matches || document.documentElement.getAttribute("data-motion") === "paused";

function optionOf(m, el, name) {
  const o = m.o;
  const own = el.getAttribute("data-depth-" + name.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase()));
  if (own === null) return o[name];
  if (typeof o[name] === "number") return Number.isFinite(Number(own)) ? Number(own) : o[name];
  return typeof o[name] === "boolean" ? own !== "false" : own;
}

// 4 / ease: the spring's omega (see settle); never under 0.05 s, where it would divide by zero.
const pace = (m, el) => 4 / Math.max(0.05, optionOf(m, el, "ease"));

function layersOf(el) {
  return [...el.querySelectorAll("[data-depth-layer]")]
    .filter((layer) => layer.closest("[data-depth]") === el)
    .map((layer) => ({ el: layer, n: Number(layer.getAttribute("data-depth-layer")) || 0,
      top: !layer.parentElement.closest("[data-depth-layer]") ||
        layer.parentElement.closest("[data-depth-layer], [data-depth]") === el }));
}

function write(m, el, name, value) {
  if (!m.touched.has(el)) m.touched.set(el, WRITTEN.map((p) => [p, el.style.getPropertyValue(p)]));
  if (value === "" || value === null) el.style.removeProperty(name);
  else el.style.setProperty(name, value);
}

// ---- Each kind: make(m, item) builds its state, update(m, item, rect, view) moves it one frame
// (view: the screen's height h, the folds opened so far this frame, the step dt in seconds and the
// time now) and returns true once nothing moves any more.

function makeTilt(m, item) {
  Object.assign(item, { rx: spring(), ry: spring(), lift: spring(clamp(optionOf(m, item.el, "rest"))), gx: spring(), gy: spring() });
  if (!optionOf(m, item.el, "glare")) return;
  item.glare = item.el.appendChild(Object.assign(document.createElement("span"), { className: "depth-glare" }));
  item.glare.setAttribute("aria-hidden", "true");
}

function updateTilt(m, item, r, view) {
  aimTilt(m, item, r, view);
  const w = pace(m, item.el);
  let done = true;
  for (const key of ["rx", "ry", "lift", "gx", "gy"]) done = settle(item[key], w, view.dt, flat(m)) && done;
  drawTilt(m, item);
  return done;
}

// Where a tilt card's springs go: toward the pointer, by its place on a touch screen, or to rest.
function aimTilt(m, item, r, view) {
  const el = item.el, tilt = Math.min(MAX_TILT, optionOf(m, el, "tilt")), pointer = m.pointer;
  const rest = clamp(optionOf(m, el, "rest")), [lx, ly] = pair(optionOf(m, el, "light"));
  // Nobody points: a raised card keeps its glare where the light comes from.
  let u = 0, v = 0, lift = rest, gu = lx * rest, gv = ly * rest;
  if (!flat(m) && m.hover.matches) {
    // Where the pointer is on the card, -1..1 from its middle to each edge.
    const pu = (pointer.x - r.left - r.width / 2) / (r.width / 2);
    const pv = (pointer.y - r.top - r.height / 2) / (r.height / 2);
    if (pointer.has && Math.abs(pu) <= 1 && Math.abs(pv) <= 1) { u = gu = pu; v = gv = pv; lift = 1; }
  } else if (!flat(m) && optionOf(m, el, "touch")) {
    // No hover: lean with the card's place on the screen, as a sheet held below or above the eye.
    v = gv = -TOUCH.lean * clamp((r.top + r.height / 2 - view.h / 2) / (view.h / 2), -1, 1);
    lift = Math.max(rest, TOUCH.lift);
  }
  // The side under the pointer sinks: rotateY(+) moves the right edge away, rotateX(+) the top.
  item.ry.to = u * tilt; item.rx.to = -v * tilt; item.lift.to = lift; item.gx.to = gu; item.gy.to = gv;
}

function drawTilt(m, item) {
  const el = item.el;
  // P at least twice the raise, so the card can never reach the eye.
  const l = clamp(item.lift.x), raise = optionOf(m, el, "raise");
  const P = Math.max(1, 2 * raise, optionOf(m, el, "perspective"));
  // The card comes toward the eye with its lift. Lying still, that is drawn as its exact flat
  // equal: translateZ(z) under perspective P about the middle is scale(P / (P - z)).
  // Under 0.05 px (a 20th of a pixel) the raise is not drawn at all.
  const z = flat(m) ? 0 : l * raise;
  const flatNow = item.rx.x === 0 && item.ry.x === 0;
  if (flatNow) write(m, el, "transform", z < 0.05 ? "" : `scale(${(P / (P - z)).toFixed(4)})`);
  else write(m, el, "transform", `perspective(${P}px) translateZ(${px(z)}px) rotateX(${px(item.rx.x)}deg) rotateY(${px(item.ry.x)}deg)`);
  item.drawn = { P, z: flatNow ? 0 : px(z), a: flatNow ? 0 : px(item.rx.x), b: flatNow ? 0 : px(item.ry.x) };
  if (z >= 0.05) write(m, el, "z-index", "1"); else write(m, el, "z-index", "");
  // The shade lies on the side away from the pointer: a gradient whose CSS angle a points from
  // the pointer across the card, (sin a, -cos a) = -(gx, gy), so a = atan2(-gx, gy).
  const reach = Math.min(1, Math.hypot(item.gx.x, item.gy.x));
  for (const [name, value] of [["lift", l], ["sx", -item.ry.x / MAX_TILT], ["sy", item.rx.x / MAX_TILT],
    ["gx", item.gx.x], ["gy", item.gy.x], ["gm", reach]]) write(m, el, "--depth-" + name, value ? value.toFixed(3) : "");
  write(m, el, "--depth-ga", reach ? `${px((Math.atan2(-item.gx.x, item.gy.x) * 180) / Math.PI)}deg` : "");
  // Layers rise only with the part of the lift that the pointer adds, so at rest they lie flat.
  const rest = clamp(optionOf(m, el, "rest"));
  const rise = optionOf(m, el, "lift"), hand = rest < 1 ? clamp((l - rest) / (1 - rest)) : 0;
  for (const layer of item.layers) {
    const lz = hand * layer.n * rise;
    write(m, layer.el, "transform", Math.abs(lz) < 0.01 ? "" : `translateZ(${px(lz)}px)`);
  }
}

function makeStack(m, item) {
  item.panels = [...item.el.children].filter((c) => c.nodeType === 1 && !c.hasAttribute("data-depth-skip"));
  item.p = spring(flat(m) ? 1 : 0);
  item.panels.forEach((panel, i) => write(m, panel, "z-index", String(item.panels.length - i)));
}

// Read before any write: the eye's distance and the point it looks from, in the stack's own
// pixels (perspective and perspective-origin in depth.css), where each panel's top left corner
// lies in the stack, and the height of each panel.
function measureStack(m, item) {
  const style = getComputedStyle(item.el);
  item.P = parseFloat(style.perspective) || optionOf(m, item.el, "perspective");
  item.origin = style.perspectiveOrigin.split(" ").map(parseFloat);
  item.corners = item.panels.map((panel) => (panel.offsetParent === item.el
    ? [panel.offsetLeft + item.el.clientLeft, panel.offsetTop + item.el.clientTop]
    : [panel.offsetLeft - item.el.offsetLeft, panel.offsetTop - item.el.offsetTop]));
  item.heights = item.panels.map((panel) => panel.offsetHeight);
  item.width = item.el.clientWidth;
}

function updateStack(m, item, r, view) {
  const el = item.el, gap = optionOf(m, el, "stackGap"), depth = optionOf(m, el, "stackDepth");
  const P = Math.max(1, item.P || optionOf(m, el, "perspective"));
  // 0 as the stack's top enters at the bottom, 1 once its middle reaches the middle of the screen.
  item.p.to = flat(m) ? 1 : clamp(2 * (m.forced ?? (view.h - r.top) / (view.h + r.height)));
  const done = settle(item.p, pace(m, el), view.dt, flat(m));
  const n = item.panels.length, lag = n > 1 ? ENTRY.lag / (n - 1) : 0;
  // The whole stack stands turned a few degrees, about the middle of its front panel, so its
  // depth shows in a still picture as well. Flat and still: no turn, the flat cascade.
  const [tx, ty] = flat(m) ? [0, 0] : pair(optionOf(m, el, "stackTurn"));
  const cx = Math.round((item.width || 0) / 2), cy = Math.round((item.heights[0] || 0) / 2);
  const turn = tx || ty ? `translate(${cx}px, ${cy}px) rotateX(${tx}deg) rotateY(${ty}deg) translate(${-cx}px, ${-cy}px) ` : "";
  const look = { gap, depth, P, n, lag, turn };
  item.panels.forEach((panel, i) => placePanel(m, item, i, look));
  return done;
}

function placePanel(m, item, i, { gap, depth, P, n, lag, turn }) {
  const panel = item.panels[i];
  // Each panel has its own window of the progress: the front one goes first.
  const t = smooth(clamp((item.p.x - i * lag) / (1 - (n - 1) * lag)));
  const y = mix(ENTRY.drop + i * gap * ENTRY.fan, -i * gap, t);
  const z = mix(-depth * (ENTRY.far + i * ENTRY.farStep), -i * depth, t);
  const tip = mix(ENTRY.tip, 0, t), h = item.heights[i];
  // Shade and shadow stay fixed per panel while it moves: changing them would repaint the
  // whole panel every frame, where a transform alone is only composited.
  write(m, panel, "--depth-dim", Math.min(PANEL.dimMost, i * PANEL.dim).toFixed(2));
  write(m, panel, "--depth-lift", Math.max(0, 1 - i * PANEL.shadowStep).toFixed(2));
  write(m, panel, "transform-origin", "0 0");
  // Below a 100th of a degree, a 100th of a pixel deep and half a pixel high: nothing to draw.
  if (tip > 0.01) {
    // Standing up: turned back about its bottom edge, rising from below and far behind.
    write(m, panel, "transform", `${turn}translate3d(0, ${px(y + h)}px, ${px(z)}px) rotateX(${px(tip)}deg) translateY(${-h}px)`);
  } else if (turn) {
    write(m, panel, "transform", `${turn}translate3d(0, ${px(y)}px, ${px(z)}px)`);
  } else if (Math.abs(z) < 0.01 && Math.abs(y) < 0.5) {
    write(m, panel, "transform", "");
  } else {
    // At rest, the same picture drawn flat: under perspective P a point z deep is scaled by
    // s = P / (P - z) toward the eye point. As a 2D transform about the panel's own top left
    // corner: move the eye point (seen from that corner) to 0, scale by s, move back, then
    // the offset y (also scaled). Flat layers stay crisp; on whole pixels they stay sharp.
    const s = P / (P - z), [ox, oy] = item.origin, [left, top] = item.corners[i] || [0, 0];
    write(m, panel, "transform", `translate(${Math.round((ox - left) * (1 - s))}px, ${Math.round((oy - top) * (1 - s) + y * s)}px) scale(${s.toFixed(4)})`);
  }
}

function makeFold(m, item) {
  const f = flat(m) ? 1 : 0; // f: how far it has opened, 0..1, along a fixed clock
  Object.assign(item, { f, goal: f, from: f, since: 0, open: Boolean(f), startAt: 0 });
}

function updateFold(m, item, r, view) {
  const el = item.el, now = view.now;
  triggerFold(m, item, r, view);
  // A page turn has a fixed length (foldTime) and ends exactly flat, where a spring's long tail
  // would leave a row of panels a degree crooked. Its pace is a quartic ease-out,
  // 1 - (1 - f)^4: fast off the hinge, then a long, soft landing.
  // The clock is the wall clock, not the sum of frame steps, so a slow device ends on time too.
  const target = item.open && now >= item.startAt ? 1 : 0;
  if (target !== item.goal) Object.assign(item, { goal: target, from: item.f, since: now });
  const run = (now - item.since) / 1000 / optionOf(m, el, "foldTime");
  item.f = clamp(target ? item.from + run : item.from - run);
  const done = item.f === target && now >= item.startAt;
  drawFold(m, item);
  return done;
}

// Open a fold that came into view (after the ones that came with it), or close it once it has
// left again when foldOnce is false.
function triggerFold(m, item, r, view) {
  const el = item.el;
  if (flat(m)) Object.assign(item, { open: true, f: 1, goal: 1, from: 1 });
  const inView = r.top < view.h * FOLD.below && r.bottom > view.h * FOLD.above;
  if (!item.open && inView) {
    item.open = true;
    item.startAt = view.now + view.batch * optionOf(m, el, "foldStagger") * 1000;
    view.batch += 1;
  } else if (item.open && !optionOf(m, el, "foldOnce") && !flat(m) && (r.top > view.h || r.bottom < 0)) {
    item.open = false;
  }
}

function drawFold(m, item) {
  const el = item.el, closed = optionOf(m, el, "fold");
  const a = closed * Math.pow(1 - item.f, 4);
  const [hinge, axis, sign] = HINGES[el.getAttribute("data-depth-axis")] || HINGES.left;
  write(m, el, "transform-origin", a ? hinge : "");
  write(m, el, "transform", a ? `perspective(${Math.max(1, optionOf(m, el, "perspective"))}px) ${axis}(${px(sign * a)}deg)` : "");
  // A page turned away catches less light: the shade grows with the angle. The first fifth of
  // the turn also fades it in, so the thin edge-on sliver never pops.
  write(m, el, "--depth-shade", a ? (FOLD.shade * Math.sin(a * RAD)).toFixed(3) : "");
  write(m, el, "opacity", a > closed * 0.8 ? (clamp((closed - a) / (closed * 0.2))).toFixed(3) : "");
}

function makeScene(m, item) {
  Object.assign(item, { px: spring(), py: spring(), d: spring(), t: 0 });
}

function updateScene(m, item, r, view) {
  const el = item.el, still = flat(m), pointer = m.pointer, dt = view.dt;
  // Its own slow life (DRIFT): a clock that runs only while the scene is drawn, and a sway that
  // fades in over the first seconds so the first frame is the resting picture. A sway of 2 s
  // or less would be a shiver, not a sway.
  const sway = still ? 0 : Math.max(0, optionOf(m, el, "drift"));
  item.t = sway ? item.t + dt : 0;
  const period = Math.max(2, optionOf(m, el, "driftTime")), wake = smooth(clamp(item.t / DRIFT.wake));
  const wave = (part, phase) => sway * wake * Math.sin((TAU * item.t) / (period * part) + phase);
  let u = 0, v = 0;
  if (!still && pointer.has && m.hover.matches) {
    u = clamp((pointer.x - r.left - r.width / 2) / (r.width / 2), -1, 1);
    v = clamp((pointer.y - r.top - r.height / 2) / (r.height / 2), -1, 1);
    if (pointer.y < r.top || pointer.y > r.bottom) u = v = 0;
  }
  // Scroll: -1 below, 0 with its middle in the middle of the screen, 1 above.
  const d = still ? 0 : 2 * (m.forced ?? (view.h - r.top) / (view.h + r.height)) - 1;
  item.px.to = u; item.py.to = v; item.d.to = clamp(d, -1, 1);
  const w = pace(m, el);
  let done = true;
  for (const key of ["px", "py", "d"]) done = settle(item[key], w, dt, still) && done;
  const motion = { item, wave, sway, done, shift: optionOf(m, el, "shift"), drift: optionOf(m, el, "scrollShift"),
                   turn: optionOf(m, el, "turn") };
  item.layers.forEach((layer, k) => moveLayer(m, layer, k, motion));
  return done && !sway;
}

// Parallax: a near layer (n > 0) moves against the pointer, a far one (n < 0) with it, each by
// its number; with scroll, near layers rise faster than the page and far ones lag behind.
// The sway: front layers turn a fraction of a degree, every layer floats a few pixels by its
// number (a layer 0 as if it were 1), each on its own phase, so nothing moves in step.
function moveLayer(m, layer, k, { item, wave, sway, done, shift, drift, turn }) {
  const front = layer.top && layer.n > 0, phase = k * DRIFT.spread + layer.n * DRIFT.byNumber;
  const x = -item.px.x * layer.n * shift + wave(DRIFT.paceAcross, phase + DRIFT.offAcross) * layer.n * DRIFT.across;
  const y = -item.py.x * layer.n * shift - item.d.x * layer.n * drift
    + wave(DRIFT.paceUpDown, phase + DRIFT.offUpDown) * (layer.n || 1) * DRIFT.upDown;
  const ry = front ? item.px.x * turn + wave(1, phase) : 0;
  const rx = front ? -item.py.x * turn + wave(DRIFT.paceNod, phase + DRIFT.offNod) * DRIFT.nod : 0;
  const moving = !done || ry !== 0 || rx !== 0 || sway > 0;
  const tx = moving ? px(x) : Math.round(x), ty = moving ? px(y) : Math.round(y);
  if (ry || rx) write(m, layer.el, "transform", `translate3d(${tx}px, ${ty}px, 0) rotateX(${px(rx)}deg) rotateY(${px(ry)}deg)`);
  else write(m, layer.el, "transform", tx || ty ? `translate(${tx}px, ${ty}px)` : "");
}

const KINDS = {
  tilt: { rect: cardRect, make: makeTilt, update: updateTilt },
  stack: { make: makeStack, measure: measureStack, update: updateStack },
  fold: { make: makeFold, update: updateFold },
  scene: { make: makeScene, update: updateScene },
};

// ---- Find the elements.
function findElements(m) {
  const root = m.root;
  const found = [...(root.matches && root.matches("[data-depth]") ? [root] : []), ...root.querySelectorAll("[data-depth]")];
  for (const el of found) {
    const kind = KINDS[el.getAttribute("data-depth") || "tilt"]; // a bare data-depth is a tilt card
    if (!kind || owned.has(el)) continue; // another live mount() already moves it
    owned.add(el);
    const item = { el, kind, visible: false, layers: layersOf(el) };
    kind.make(m, item);
    m.items.push(item);
  }
}

function measure(m, item) {
  if (item.kind.measure) item.kind.measure(m, item);
  return item.kind.rect ? item.kind.rect(item) : item.el.getBoundingClientRect();
}

// ---- One frame loop for all of them. Reads every rectangle first, then writes, so the browser
// lays out at most once a frame.
function tick(m, now) {
  m.frame = 0;
  // A step is at most 50 ms: after a stall (a busy main thread) the motion goes on, it does not jump.
  const dt = m.last ? Math.min(0.05, (now - m.last) / 1000) : 1 / 60;
  m.last = now;
  const view = { h: window.innerHeight || 1, batch: 0, dt, now };
  const live = m.items.filter((item) => item.visible);
  const rects = live.map((item) => measure(m, item));
  let busy = false;
  live.forEach((item, i) => {
    const done = item.kind.update(m, item, rects[i], view);
    if (done) item.el.removeAttribute("data-depth-moving"); else item.el.setAttribute("data-depth-moving", "");
    busy = busy || !done;
  });
  if (busy && !flat(m)) wake(m); else m.last = 0;
}

// Flat and still needs no frames: still() draws every change of that state at once.
function wake(m) {
  if (m.frame || m.destroyed || m.pauses.size || document.hidden || flat(m)) return;
  m.frame = window.requestAnimationFrame((now) => tick(m, now));
}

function stop(m) {
  if (m.frame) window.cancelAnimationFrame(m.frame);
  m.frame = 0;
  m.last = 0;
}

// A still picture: one frame with no time passing, every eased value set straight to its target.
function still(m) {
  for (const item of m.items) item.el.toggleAttribute("data-depth-flat", flat(m));
  if (!flat(m)) { wake(m); return; }
  stop(m);
  const view = { h: window.innerHeight || 1, batch: 0, dt: 0, now: 0 };
  for (const item of m.items) {
    view.now = performance.now();
    item.kind.update(m, item, measure(m, item), view);
    item.el.removeAttribute("data-depth-moving");
  }
}

// Off screen, paused or flat: depth.css pauses the page's own CSS animations inside the element.
function asleep(m) {
  for (const item of m.items) item.el.toggleAttribute("data-depth-asleep", !item.visible || m.pauses.size > 0 || flat(m));
}

// ---- The page's colours: light or dark decides how shadows and glare are mixed in depth.css.
function tone(m) {
  const dark = darkPage(m.root.nodeType === 1 ? m.root : document.body);
  for (const item of m.items) item.el.setAttribute("data-depth-tone", dark ? "dark" : "light");
}

// ---- Listeners, each with its remover.
function listen(m) {
  const on = (target, type, fn, opts = { passive: true }) => {
    target.addEventListener(type, fn, opts);
    m.cleanups.push(() => target.removeEventListener(type, fn, opts));
  };
  const awake = () => wake(m), again = () => { asleep(m); still(m); };
  on(window, "pointermove", (e) => {
    if (e.pointerType === "touch") return; // touch tilts with the scroll instead
    Object.assign(m.pointer, { x: e.clientX, y: e.clientY, has: true }); wake(m);
  });
  const gone = () => { m.pointer.has = false; wake(m); };
  on(document.documentElement, "pointerleave", gone);
  on(window, "blur", gone);
  // Scroll events of an element do not bubble: listening in the capture phase on the document
  // hears every scroll, the page's own and that of a main area scrolling inside a fixed frame.
  on(document, "scroll", awake, { capture: true, passive: true });
  on(window, "resize", () => (flat(m) ? still(m) : wake(m)));
  on(document, "visibilitychange", () => (document.hidden ? stop(m) : wake(m)));
  on(m.reduced, "change", again);
  on(m.hover, "change", awake);
  on(m.scheme, "change", () => tone(m));
  const watcher = new MutationObserver((changes) => {
    if (changes.some((c) => c.attributeName === "data-motion")) again();
    else tone(m);
  });
  watcher.observe(document.documentElement, { attributes: true, attributeFilter: ["data-motion", "data-theme", "class", "style"] });
  if (document.body) watcher.observe(document.body, { attributes: true, attributeFilter: ["data-theme", "class"] });
  m.cleanups.push(() => watcher.disconnect());
  watchView(m);
}

function watchView(m) {
  if (typeof IntersectionObserver !== "function") {
    for (const item of m.items) item.visible = true;
    return;
  }
  const seen = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const item = m.items.find((it) => it.el === entry.target);
      if (item) item.visible = entry.isIntersecting;
    }
    asleep(m);
    if (flat(m)) still(m); else wake(m);
  }, { rootMargin: "15% 0px" }); // wakes a little before it is seen, so it is in place when it appears
  for (const item of m.items) seen.observe(item.el);
  m.cleanups.push(() => seen.disconnect());
}

function depthHandle(m) {
  const { pointer, pauses } = m;
  return {
    stage: null,
    setProgress(p) { m.forced = p === null || p === undefined ? null : clamp(Number(p) || 0); if (flat(m)) still(m); else wake(m); },
    setData() {},
    setPointer(x, y) {
      const u = Number(x), v = Number(y);
      // Not a number (null, NaN, Infinity): let go, as if the pointer had left the page.
      if (x === null || y === null || !Number.isFinite(u) || !Number.isFinite(v)) pointer.has = false;
      else Object.assign(pointer, { x: ((clamp(u, -1, 1) + 1) / 2) * innerWidth, y: ((1 - clamp(v, -1, 1)) / 2) * innerHeight, has: true });
      wake(m);
    },
    pause(reason = "user") { pauses.add(reason); asleep(m); stop(m); },
    resume(reason = "user") { pauses.delete(reason); asleep(m); wake(m); },
    destroy: () => destroy(m),
  };
}

function destroy(m) {
  if (m.destroyed) return;
  m.destroyed = true;
  stop(m);
  for (const cleanup of m.cleanups.splice(0)) cleanup();
  for (const [el, saved] of m.touched) for (const [name, value] of saved) {
    if (value) el.style.setProperty(name, value); else el.style.removeProperty(name);
  }
  for (const item of m.items) for (const mark of MARKS) item.el.removeAttribute(mark);
  for (const item of m.items) if (item.glare) item.glare.remove();
  for (const item of m.items) owned.delete(item.el);
  m.touched.clear();
  m.items.length = 0;
}
