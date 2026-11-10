/**
 * depth.js: real depth in an interface with CSS 3D only, no WebGL (scene kit, look level 3 and up).
 *
 * Four behaviours, each switched on by a data-depth attribute in the page's own markup:
 *   data-depth="tilt"   a card that leans toward the pointer: the side under the pointer sinks a few
 *                       degrees, children marked data-depth-layer="1|2|3" rise off the card to their
 *                       own height, a soft glare follows the pointer and the shadow grows with the
 *                       lift. On a touch screen (no hover) the card tilts gently with its place on the
 *                       screen while the page scrolls.
 *   data-depth="stack"  a container whose child elements are panels piled behind one another (the
 *                       first child in front). While the stack scrolls in, the panels step forward,
 *                       front panel first, into a cascade where each one peeks out above the next.
 *   data-depth="fold"   a panel that opens like a page turning, hinged on one side, once it enters the
 *                       viewport. Folds that enter together open one after the other.
 *                       data-depth-axis="left" (default), "right", "top" or "bottom" names the hinge.
 *   data-depth="scene"  a hero whose data-depth-layer children move at their own depth with the
 *                       pointer and with scroll. Negative numbers lie behind, positive ones in front.
 *                       Layers may nest: a layer inside a layer moves on top of its parent.
 * A data-depth-layer belongs to the nearest data-depth element around it.
 *
 *   <link rel="stylesheet" href="/scenes/depth.css">
 *   import { mount } from "./scenes/depth.js";
 *   const depth = mount(document.querySelector("main"), { tilt: 4 });
 *   depth.destroy();          // when the page or the component goes away
 *
 * mount(root, options) finds every [data-depth] inside root (root included) at that moment; mount
 * again after adding new ones. It returns { setProgress, setData, setPointer, pause, resume, destroy,
 * stage }. Options (all optional; a data-depth-<option> attribute on one element wins for it):
 *   tilt         5     degrees a tilt card leans at its edge (never more than 8: text gets hard to read).
 *   ease         0.55  seconds the eased motion needs for most of the way. Heavy and calm on purpose.
 *   lift         9     pixels each layer number rises above a hovered card (layer 3: 27 px).
 *   rest         0     how raised a tilt card lies when nobody points at it, 0..1: a larger shadow
 *                      only, the layers stay flat. data-depth-rest="0.4" picks out one plan of three.
 *   glare        true  the soft light that moves across a tilt card.
 *   perspective  1500  pixels between the eye and the screen. Smaller is stronger.
 *   touch        true  the gentle scroll tilt on touch screens.
 *   stackGap     30    pixels each stacked panel peeks out above the one in front of it.
 *   stackDepth   80    pixels each stacked panel lies behind the one in front of it.
 *   fold         72    degrees a fold starts turned away. foldTime 1.1 seconds the turn takes;
 *                      foldStagger 0.1 seconds between folds that enter together; foldOnce true
 *                      (false: it closes again once it has left the screen).
 *   shift        10    pixels a scene layer moves per layer number when the pointer is at the edge.
 *   turn         2.5   degrees the front layers of a scene turn toward the pointer.
 *   scrollShift  36    pixels a scene layer drifts per layer number over a scroll of its own height.
 *
 * setProgress(p)   0..1, or null to hand control back to the scroll: pins where every stack and scene
 *                  is, as if scrolled there. 0 is just below the viewport, 0.5 its middle in the middle
 *                  of the screen (a stack has stepped forward, a scene sits at rest), 1 gone above.
 *                  The same scale as progressOf(element, "cover") in stage.js. Folds keep their trigger.
 * setPointer(x, y) steer the pointer from code, -1..1 across the viewport, y up. The next real move wins.
 * setData()        does nothing: there is no data here. pause(reason) and resume(reason) stop and start
 *                  the motion; it runs again once every reason has been resumed. stage is null.
 *
 * Manners. Reduced motion, or html[data-motion="paused"] (the switch of lazy.js motionToggle): flat
 * and still. Cards lie flat, folds are open, scene layers rest, and a stack shows its cascade as a
 * flat picture. One frame loop serves every element; it runs only while something moves, on screen,
 * in a visible tab, and sleeps after. destroy() removes every listener and observer, the glare
 * elements it added, and every style and attribute it wrote.
 *
 * What it owns: the transform of each element it moves (and opacity of folds, z-index of panels);
 * put a resting turn of your own in the CSS rotate, translate or scale properties, which add to it.
 * depth.css gives the shadows (--depth-shadow), the glare and the shade, and uses the ::after of
 * stack panels and folds. Overflow, opacity or a filter on a tilt card flattens its layers: put those
 * on a child. Colours come only from the page's --color-* tokens.
 *
 * Sharp edges and text: at rest every transform is removed or replaced by its exact flat equal (a
 * stack's cascade as translate plus scale, which the browser draws crisp) on whole pixels; depth
 * comes from transform and shadow only, never blur. While a card leans its text is resampled, so
 * keep the tilt small. Each tilt card has its own perspective(), so a card at the end of a row rises
 * as straight as one in the middle.
 *
 * Poster: none needed; without JavaScript every element is the plain page. Cost: about 6 KB, no
 * library; per frame, only the elements on screen that still move: one measurement each, then
 * writes of transform, opacity and custom properties. Shadows repaint while a card lifts.
 */

const DEFAULTS = {
  tilt: 5, ease: 0.55, lift: 9, glare: true, perspective: 1500, touch: true,
  rest: 0, stackGap: 30, stackDepth: 80, fold: 72, foldTime: 1.1, foldStagger: 0.1, foldOnce: true,
  shift: 10, turn: 2.5, scrollShift: 36,
};
const MAX_TILT = 8;
// A fold's hinge, and the turn that sends its free edge away from the eye: rotateY(+a) moves the
// right edge back, rotateX(-a) the bottom edge.
const HINGES = { left: ["0% 50%", "rotateY", 1], right: ["100% 50%", "rotateY", -1],
  top: ["50% 0%", "rotateX", -1], bottom: ["50% 100%", "rotateX", 1] };
const WRITTEN = ["transform", "transform-origin", "opacity", "z-index", "--depth-lift", "--depth-sx", "--depth-sy",
  "--depth-gx", "--depth-gy", "--depth-ga", "--depth-gm", "--depth-dim", "--depth-shade"];
const MARKS = ["data-depth-tone", "data-depth-moving", "data-depth-flat"];
const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const mix = (a, b, t) => a + (b - a) * t;
const smooth = (t) => t * t * (3 - 2 * t);
const px = (v) => Math.round(v * 100) / 100;

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
  if (Math.abs(s.x - s.to) < 0.002 && Math.abs(s.v) < 0.01) { s.x = s.to; s.v = 0; return true; }
  return false;
}

// Where an element is laid out, without its own transform: a tilting card's drawn box changes with
// the tilt, and measuring that would move the target it is easing toward.
function layoutRect(el) {
  let left = -window.scrollX, top = -window.scrollY;
  for (let node = el; node; node = node.offsetParent) { left += node.offsetLeft; top += node.offsetTop; }
  return { left, top, width: el.offsetWidth, height: el.offsetHeight, bottom: top + el.offsetHeight };
}

// Is the page dark? Read --color-bg as the browser computes it, on a probe element.
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
  const o = { ...DEFAULTS, ...options };
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const hover = window.matchMedia("(hover: hover) and (pointer: fine)");
  const scheme = window.matchMedia("(prefers-color-scheme: dark)");
  const pointer = { x: 0, y: 0, has: false }, pauses = new Set(), items = [], cleanups = [];
  let frame = 0, last = 0, forced = null, destroyed = false;

  const flat = () => reduced.matches || document.documentElement.getAttribute("data-motion") === "paused";
  const optionOf = (el, name) => {
    const own = el.getAttribute("data-depth-" + name.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase()));
    if (own === null) return o[name];
    return typeof o[name] === "number" ? Number(own) : own !== "false";
  };
  const layersOf = (el) => [...el.querySelectorAll("[data-depth-layer]")]
    .filter((layer) => layer.closest("[data-depth]") === el)
    .map((layer) => ({ el: layer, n: Number(layer.getAttribute("data-depth-layer")) || 0,
      top: !layer.parentElement.closest("[data-depth-layer]") ||
        layer.parentElement.closest("[data-depth-layer], [data-depth]") === el }));
  const touched = new Map(); // element -> its own inline values of what depth.js writes
  const write = (el, name, value) => {
    if (!touched.has(el)) touched.set(el, WRITTEN.map((p) => [p, el.style.getPropertyValue(p)]));
    if (value === "" || value === null) el.style.removeProperty(name);
    else el.style.setProperty(name, value);
  };

  // ---- Each kind: make(el) builds its state, update(item, rect, dt, view) moves it one frame and
  // returns true once nothing moves any more.
  const kinds = {
    tilt: {
      rect: layoutRect,
      make(item) {
        Object.assign(item, { rx: spring(), ry: spring(), lift: spring(clamp(optionOf(item.el, "rest"))), gx: spring(), gy: spring() });
        if (!optionOf(item.el, "glare")) return;
        item.glare = item.el.appendChild(Object.assign(document.createElement("span"), { className: "depth-glare" }));
        item.glare.setAttribute("aria-hidden", "true");
      },
      update(item, r, dt, view) {
        const el = item.el, tilt = Math.min(MAX_TILT, optionOf(el, "tilt"));
        const rest = clamp(optionOf(el, "rest"));
        let u = 0, v = 0, lift = rest; // flat and still: nothing leans
        if (!flat() && hover.matches) {
          // Where the pointer is on the card, -1..1 from its middle to each edge.
          const pu = (pointer.x - r.left - r.width / 2) / (r.width / 2);
          const pv = (pointer.y - r.top - r.height / 2) / (r.height / 2);
          if (pointer.has && Math.abs(pu) <= 1 && Math.abs(pv) <= 1) { u = pu; v = pv; lift = 1; }
        } else if (!flat() && optionOf(el, "touch")) {
          // No hover: lean with the card's place on the screen, as a sheet held below or above the eye.
          v = -0.45 * clamp((r.top + r.height / 2 - view.h / 2) / (view.h / 2), -1, 1);
          lift = Math.max(rest, 0.35);
        }
        // The side under the pointer sinks: rotateY(+) moves the right edge away, rotateX(+) the top.
        item.ry.to = u * tilt; item.rx.to = -v * tilt; item.lift.to = lift; item.gx.to = u; item.gy.to = v;
        const w = 4 / optionOf(el, "ease");
        let done = true;
        for (const key of ["rx", "ry", "lift", "gx", "gy"]) done = settle(item[key], w, dt, flat()) && done;
        const flatNow = item.rx.x === 0 && item.ry.x === 0;
        write(el, "transform", flatNow ? "" : `perspective(${optionOf(el, "perspective")}px) rotateX(${px(item.rx.x)}deg) rotateY(${px(item.ry.x)}deg)`);
        const l = clamp(item.lift.x);
        // The shade lies on the side away from the pointer: a gradient whose CSS angle a points from
        // the pointer across the card, (sin a, -cos a) = -(gx, gy), so a = atan2(-gx, gy).
        const reach = Math.min(1, Math.hypot(item.gx.x, item.gy.x));
        for (const [name, value] of [["lift", l], ["sx", -item.ry.x / MAX_TILT], ["sy", item.rx.x / MAX_TILT],
          ["gx", item.gx.x], ["gy", item.gy.x], ["gm", reach]]) write(el, "--depth-" + name, value ? value.toFixed(3) : "");
        write(el, "--depth-ga", reach ? `${px((Math.atan2(-item.gx.x, item.gy.x) * 180) / Math.PI)}deg` : "");
        // Layers rise only with the part of the lift that the pointer adds, so at rest they lie flat.
        const rise = optionOf(el, "lift"), hand = rest < 1 ? clamp((l - rest) / (1 - rest)) : 0;
        for (const layer of item.layers) {
          const z = hand * layer.n * rise;
          write(layer.el, "transform", Math.abs(z) < 0.01 ? "" : `translateZ(${px(z)}px)`);
        }
        return done;
      },
    },

    stack: {
      make(item) {
        item.panels = [...item.el.children].filter((c) => c.nodeType === 1 && !c.hasAttribute("data-depth-skip"));
        item.p = spring(flat() ? 1 : 0);
        item.panels.forEach((panel, i) => write(panel, "z-index", String(item.panels.length - i)));
      },
      // Read before any write: the point the eye looks from, in the stack's own pixels
      // (perspective-origin in depth.css), and the height of each panel.
      measure(item) {
        item.origin = getComputedStyle(item.el).perspectiveOrigin.split(" ").map(parseFloat);
        item.heights = item.panels.map((panel) => panel.offsetHeight);
      },
      update(item, r, dt, view) {
        const el = item.el, gap = optionOf(el, "stackGap"), depth = optionOf(el, "stackDepth");
        const P = optionOf(el, "perspective");
        // 0 as the stack's top enters at the bottom, 1 once its middle reaches the middle of the screen.
        item.p.to = flat() ? 1 : clamp(2 * (forced ?? (view.h - r.top) / (view.h + r.height)));
        const done = settle(item.p, 4 / optionOf(el, "ease"), dt, flat());
        const n = item.panels.length, lag = n > 1 ? 0.45 / (n - 1) : 0;
        item.panels.forEach((panel, i) => {
          // Each panel has its own window of the progress: the front one goes first.
          const t = smooth(clamp((item.p.x - i * lag) / (1 - (n - 1) * lag)));
          const y = mix(110 + i * gap * 0.2, -i * gap, t), z = mix(-depth * (1.6 + i * 1.4), -i * depth, t);
          const tip = mix(14, 0, t), h = item.heights[i];
          // Shade and shadow stay fixed per panel while it moves: changing them would repaint the
          // whole panel every frame, where a transform alone is only composited.
          write(panel, "--depth-dim", Math.min(0.62, i * 0.2).toFixed(2));
          write(panel, "--depth-lift", Math.max(0, 1 - i * 0.3).toFixed(2));
          write(panel, "transform-origin", "0 0");
          if (tip > 0.01) {
            // Standing up: turned back about its bottom edge, rising from below and far behind.
            write(panel, "transform", `translate3d(0, ${px(y + h)}px, ${px(z)}px) rotateX(${px(tip)}deg) translateY(${-h}px)`);
          } else if (Math.abs(z) < 0.01 && Math.abs(y) < 0.5) {
            write(panel, "transform", "");
          } else {
            // At rest, the same picture drawn flat: under perspective P a point z deep is scaled by
            // s = P / (P - z) toward the eye point. As a 2D transform: move the eye point to 0,
            // scale by s, move back, then the offset y (also scaled). Flat layers stay crisp.
            const s = P / (P - z), [ox, oy] = item.origin;
            write(panel, "transform", `translate(${Math.round(ox * (1 - s))}px, ${Math.round(oy * (1 - s) + y * s)}px) scale(${s.toFixed(4)})`);
          }
        });
        return done;
      },
    },

    fold: {
      make(item) {
        const f = flat() ? 1 : 0; // f: how far it has opened, 0..1, along a fixed clock
        Object.assign(item, { f, goal: f, from: f, since: 0, open: Boolean(f), startAt: 0 });
      },
      update(item, r, dt, view, now) {
        const el = item.el, closed = optionOf(el, "fold");
        if (flat()) Object.assign(item, { open: true, f: 1, goal: 1, from: 1 });
        const inView = r.top < view.h * 0.9 && r.bottom > view.h * 0.06;
        if (!item.open && inView) {
          item.open = true;
          item.startAt = now + view.batch * optionOf(el, "foldStagger") * 1000;
          view.batch += 1;
        } else if (item.open && !optionOf(el, "foldOnce") && !flat() && (r.top > view.h || r.bottom < 0)) {
          item.open = false;
        }
        // A page turn has a fixed length (foldTime) and ends exactly flat, where a spring's long tail
        // would leave a row of panels a degree crooked. Its pace is a quartic ease-out,
        // 1 - (1 - f)^4: fast off the hinge, then a long, soft landing.
        // The clock is the wall clock, not the sum of frame steps, so a slow device ends on time too.
        const target = item.open && now >= item.startAt ? 1 : 0;
        if (target !== item.goal) Object.assign(item, { goal: target, from: item.f, since: now });
        const run = (now - item.since) / 1000 / optionOf(el, "foldTime");
        item.f = clamp(target ? item.from + run : item.from - run);
        const done = item.f === target && now >= item.startAt;
        const a = closed * Math.pow(1 - item.f, 4);
        const [hinge, axis, sign] = HINGES[el.getAttribute("data-depth-axis")] || HINGES.left;
        write(el, "transform-origin", a ? hinge : "");
        write(el, "transform", a ? `perspective(${optionOf(el, "perspective")}px) ${axis}(${px(sign * a)}deg)` : "");
        // A page turned away catches less light: the shade grows with the angle. The first fifth of
        // the turn also fades it in, so the thin edge-on sliver never pops.
        write(el, "--depth-shade", a ? (0.55 * Math.sin((a * Math.PI) / 180)).toFixed(3) : "");
        write(el, "opacity", a > closed * 0.8 ? (clamp((closed - a) / (closed * 0.2))).toFixed(3) : "");
        return done;
      },
    },

    scene: {
      make(item) { Object.assign(item, { px: spring(), py: spring(), d: spring() }); },
      update(item, r, dt, view) {
        const el = item.el, still = flat();
        let u = 0, v = 0;
        if (!still && pointer.has && hover.matches) {
          u = clamp((pointer.x - r.left - r.width / 2) / (r.width / 2), -1, 1);
          v = clamp((pointer.y - r.top - r.height / 2) / (r.height / 2), -1, 1);
          if (pointer.y < r.top || pointer.y > r.bottom) u = v = 0;
        }
        // Scroll: -1 below, 0 with its middle in the middle of the screen, 1 above.
        const d = still ? 0 : 2 * (forced ?? (view.h - r.top) / (view.h + r.height)) - 1;
        item.px.to = u; item.py.to = v; item.d.to = clamp(d, -1, 1);
        const w = 4 / optionOf(el, "ease");
        let done = true;
        for (const key of ["px", "py", "d"]) done = settle(item[key], w, dt, still) && done;
        const shift = optionOf(el, "shift"), drift = optionOf(el, "scrollShift"), turn = optionOf(el, "turn");
        for (const layer of item.layers) {
          // Parallax: a near layer (n > 0) moves against the pointer, a far one (n < 0) with it, each by
          // its number; with scroll, near layers rise faster than the page and far ones lag behind.
          const x = -item.px.x * layer.n * shift, y = -item.py.x * layer.n * shift - item.d.x * layer.n * drift;
          const ry = layer.top && layer.n > 0 ? item.px.x * turn : 0, rx = layer.top && layer.n > 0 ? -item.py.x * turn : 0;
          const moving = !done || ry !== 0 || rx !== 0;
          const tx = moving ? px(x) : Math.round(x), ty = moving ? px(y) : Math.round(y);
          if (ry || rx) write(layer.el, "transform", `translate3d(${tx}px, ${ty}px, 0) rotateX(${px(rx)}deg) rotateY(${px(ry)}deg)`);
          else write(layer.el, "transform", tx || ty ? `translate(${tx}px, ${ty}px)` : "");
        }
        return done;
      },
    },
  };

  // ---- Find the elements.
  const found = [...(root.matches && root.matches("[data-depth]") ? [root] : []), ...root.querySelectorAll("[data-depth]")];
  for (const el of found) {
    const kind = kinds[el.getAttribute("data-depth")];
    if (!kind) continue;
    const item = { el, kind, visible: false, layers: layersOf(el) };
    kind.make(item);
    items.push(item);
  }

  const measure = (item) => {
    if (item.kind.measure) item.kind.measure(item);
    return item.kind.rect ? item.kind.rect(item.el) : item.el.getBoundingClientRect();
  };

  // ---- One frame loop for all of them. Reads every rectangle first, then writes, so the browser
  // lays out at most once a frame.
  function tick(now) {
    frame = 0;
    const dt = last ? Math.min(0.05, (now - last) / 1000) : 1 / 60;
    last = now;
    const view = { h: window.innerHeight || 1, batch: 0 };
    const live = items.filter((item) => item.visible);
    const rects = live.map(measure);
    let busy = false;
    live.forEach((item, i) => {
      const done = item.kind.update(item, rects[i], dt, view, now);
      if (done) item.el.removeAttribute("data-depth-moving"); else item.el.setAttribute("data-depth-moving", "");
      busy = busy || !done;
    });
    if (busy && !flat()) wake(); else last = 0;
  }
  function wake() {
    if (frame || destroyed || pauses.size || document.hidden) return;
    frame = window.requestAnimationFrame(tick);
  }
  const stop = () => { if (frame) window.cancelAnimationFrame(frame); frame = 0; last = 0; };
  // A still picture: one frame with no time passing, every eased value set straight to its target.
  function still() {
    for (const item of items) item.el.toggleAttribute("data-depth-flat", flat());
    if (!flat()) { wake(); return; }
    stop();
    const view = { h: window.innerHeight || 1, batch: 0 };
    for (const item of items) {
      item.kind.update(item, measure(item), 0, view, performance.now());
      item.el.removeAttribute("data-depth-moving");
    }
  }

  // ---- The page's colours: light or dark decides how shadows and glare are mixed in depth.css.
  function tone() {
    const dark = darkPage(root.nodeType === 1 ? root : document.body);
    for (const item of items) item.el.setAttribute("data-depth-tone", dark ? "dark" : "light");
  }

  // ---- Listeners, each with its remover.
  const on = (target, type, fn, opts = { passive: true }) => {
    target.addEventListener(type, fn, opts);
    cleanups.push(() => target.removeEventListener(type, fn, opts));
  };
  on(window, "pointermove", (e) => {
    if (e.pointerType === "touch") return; // touch tilts with the scroll instead
    pointer.x = e.clientX; pointer.y = e.clientY; pointer.has = true; wake();
  });
  const gone = () => { pointer.has = false; wake(); };
  on(document.documentElement, "pointerleave", gone);
  on(window, "blur", gone);
  on(window, "scroll", wake);
  on(window, "resize", () => (flat() ? still() : wake()));
  on(document, "visibilitychange", () => (document.hidden ? stop() : wake()));
  on(reduced, "change", still);
  on(hover, "change", wake);
  on(scheme, "change", tone);
  const watcher = new MutationObserver((changes) => {
    if (changes.some((c) => c.attributeName === "data-motion")) still();
    else tone();
  });
  watcher.observe(document.documentElement, { attributes: true, attributeFilter: ["data-motion", "data-theme", "class", "style"] });
  if (document.body) watcher.observe(document.body, { attributes: true, attributeFilter: ["data-theme", "class"] });
  cleanups.push(() => watcher.disconnect());
  if (typeof IntersectionObserver === "function") {
    const seen = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        const item = items.find((it) => it.el === entry.target);
        if (item) item.visible = entry.isIntersecting;
      }
      if (flat()) still(); else wake();
    }, { rootMargin: "15% 0px" });
    for (const item of items) seen.observe(item.el);
    cleanups.push(() => seen.disconnect());
  } else {
    for (const item of items) item.visible = true;
  }

  tone();
  still();
  // Before the first frame, fold panels must already be turned away, or they would flash open.
  if (!flat()) for (const item of items) if (item.kind === kinds.fold) kinds.fold.update(item, { top: 1e9, bottom: 1e9 }, 0, { h: 1, batch: 0 }, 0);

  return {
    stage: null,
    setProgress(p) { forced = p === null || p === undefined ? null : clamp(Number(p) || 0); if (flat()) still(); else wake(); },
    setData() {},
    setPointer(x, y) {
      Object.assign(pointer, { x: ((clamp(x, -1, 1) + 1) / 2) * innerWidth, y: ((1 - clamp(y, -1, 1)) / 2) * innerHeight, has: true });
      wake();
    },
    pause(reason = "user") { pauses.add(reason); stop(); },
    resume(reason = "user") { pauses.delete(reason); wake(); },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      stop();
      for (const cleanup of cleanups.splice(0)) cleanup();
      for (const [el, saved] of touched) for (const [name, value] of saved) {
        if (value) el.style.setProperty(name, value); else el.style.removeProperty(name);
      }
      for (const item of items) for (const mark of MARKS) item.el.removeAttribute(mark);
      for (const item of items) if (item.glare) item.glare.remove();
      touched.clear();
      items.length = 0;
    },
  };
}
