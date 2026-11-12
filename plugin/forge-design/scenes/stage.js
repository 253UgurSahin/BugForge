/**
 * stage.js: the shared runtime under every WebGL scene of the scene kit (look levels 4 and 5).
 *
 * A scene asks for a stage and gets a renderer, a scene graph, a camera and one frame loop that
 * already does the parts that are easy to get wrong: the size and the pixel ratio, the colours of
 * the page and its theme, pausing when nobody looks, reduced motion, weak devices, the pointer,
 * scroll progress, a missing or lost WebGL context, and cleaning up. `three` is a bare import: the
 * app installs it with npm, or a page with no bundler maps it in an import map to a file it serves
 * itself. Needs three r160 or newer (WebGL 2). Nothing else is imported.
 *
 * A SCENE, START TO END
 *
 *   import * as THREE from "three";
 *   import { createStage } from "./stage.js";
 *   import { stageUniforms, simplex3D } from "./glsl.js";
 *
 *   export function mount(container, options = {}) {
 *     const stage = createStage(container, { ...options, stillTime: 6 });
 *     if (stage.failed) return stage.handle();   // no WebGL: the poster shows, every method does nothing
 *     const material = new THREE.ShaderMaterial({
 *       uniforms: { ...stage.uniforms, uAmount: { value: 1 } },   // uTime, uPointer, uAccent ... stay up to date
 *       vertexShader, fragmentShader, transparent: true, depthWrite: false,
 *     });
 *     const mesh = new THREE.Mesh(undefined, material);
 *     stage.scene.add(mesh);
 *     stage.onQuality((quality) => {             // runs now, and again when the stage steps down
 *       mesh.geometry.dispose();                 // keep the object and its material, swap the geometry
 *       mesh.geometry = new THREE.TorusKnotGeometry(1, 0.3, quality.pick(96, 180, 320), 16);
 *     });                                        // the knot is a stand-in: build the app's own thing here
 *                                                // (a ledger, a book, a plate), never ship the knot
 *     stage.onTokens((tokens) => { material.blending = tokens.blending; });   // glow on dark, ink on light
 *     stage.onResize((size) => { stage.camera.position.z = size.aspect < 1 ? 7 : 5; });
 *     stage.onFrame((time, delta) => { mesh.rotation.y = time * 0.1 + stage.pointer.x * 0.3; });
 *     return stage.handle({
 *       setData(values) { material.uniforms.uAmount.value = values[0]; stage.invalidate(); },
 *     });
 *   }
 *
 * THE PAGE
 *
 *   <div class="hero-scene" aria-hidden="true"></div>     an element of its own, with a size from CSS
 *
 * The stage puts one canvas in the container: absolutely placed, filling it, transparent (the page
 * background shows through) and with pointer-events off, so it never blocks a click or a scroll.
 * A container with `position: static` is made `relative`. The container carries the state:
 * no `data-scene` attribute until the first frame is on screen, then `data-scene="live"`, or
 * `data-scene="fallback"` when WebGL is missing, the context is lost, or a frame threw. A child
 * marked `data-scene-poster` is faded out when the scene goes live and shown again on fallback;
 * a poster set as a background image needs one rule:
 * `.hero-scene[data-scene="live"] { background-image: none; }`. A scene behind a whole page belongs
 * in a fixed container the size of the viewport, not in one as tall as the page. Call destroy()
 * when the page or the component goes away.
 *
 * createStage(container, options) -> stage. Never throws. Options (all optional):
 *   quality       "auto" (default), "low", "medium" or "high". Auto starts from the device (processor
 *                 cores, memory, a coarse pointer; software rendering starts low) and steps down, never
 *                 up, when the average time of about 90 frames is over 22 ms.
 *   antialias     true (default). Lines and edges need it; a scene that fills the screen with one
 *                 shader should pass false.
 *   maxDpr        2. The pixel ratio is capped at this, at 1.5 with a coarse pointer and at 1 in low
 *                 quality, and lowered further to keep the drawing buffer within 2.1, 3.6 or 8.3
 *                 million pixels (low, medium, high), however large the screen.
 *   renderScale   1. Draw at a part of that resolution: a number, or [low, medium, high]. A soft
 *                 atmosphere looks the same at 0.5 and costs a quarter.
 *   camera        { fov: 45, near: 0.1, far: 100, position: [0, 0, 5], lookAt: [0, 0, 0] }, or a THREE
 *                 camera of your own.
 *   tokens        other names for the colours, or more of them: { accent: "--brand", glow: "--glow" }
 *                 (the second gives tokens.glow and uniforms.uGlow). A value that does not start
 *                 with -- is read as a CSS colour.
 *   stillTime     8. The moment, in seconds, that the one still frame shows (see "Still frames").
 *   still         false. true behaves as if the visitor asked for reduced motion (a lab page, a test).
 *                 A poster is taken from the page itself under reduced motion: scenes.md section 5.
 *   pointerEase   0.18, progressEase 0.25: seconds the eased pointer and progress need for most of
 *                 the way.
 *   fade          400. Milliseconds the canvas takes to fade in on its first frame; 0 shows it at once.
 * A scene passes its own options straight through, so do not reuse these names for something else.
 *
 * THE STAGE
 *
 *   container, canvas   the element it was given and the canvas inside it.
 *   renderer            THREE.WebGLRenderer: alpha, sRGB output, no tone mapping. null on a failed stage.
 *   scene, camera       THREE.Scene and THREE.PerspectiveCamera. The stage keeps the aspect right and
 *                       leaves the rest of the camera to the scene.
 *   clock               { time, delta, frame }: seconds the scene has run (it stands still while paused),
 *                       seconds since the last frame (0.1 at most, so a tab that was away does not
 *                       jump; 0 in a still frame) and the number of frames drawn.
 *   size                { width, height, aspect, dpr, pixels }: CSS pixels, the pixel ratio in use, and
 *                       pixels, a THREE.Vector2 with the drawing buffer's size.
 *   tokens              { bg, text, muted, accent, accent2, surface, border, css, dark, blending }: the
 *                       page's colours as THREE.Color, read from --color-bg, --color-text,
 *                       --color-text-muted, --color-accent, --color-accent-2, --color-surface and
 *                       --color-border on the container (a missing one gets a sensible stand-in);
 *                       css has the same colours as CSS text; dark is true when the background is dark;
 *                       blending is THREE.AdditiveBlending on dark and THREE.NormalBlending on light.
 *                       The Color objects stay the same objects and change in place: read them, copy
 *                       them (material.color.copy(tokens.accent), in onTokens), never change them.
 *   uniforms            ready to spread into a ShaderMaterial, kept up to date by the stage: uTime,
 *                       uResolution (drawing buffer pixels), uPixelRatio, uPointer (eased, -1..1),
 *                       uProgress (eased, 0..1), uBg, uText, uMuted, uAccent, uAccent2, uSurface, uBorder
 *                       (vec3, linear working colours) and uDark (1 or 0). glsl.js has the matching
 *                       declarations in `stageUniforms`. Do not clone() a material that uses them:
 *                       a clone gets copies, and those stand still.
 *   pointer             { x, y, raw: { x, y }, inside, active, speed }: x and y run from -1 to 1 across the
 *                       container (y up, so raw fits THREE.Raycaster.setFromCamera), eased; raw is where
 *                       the pointer or finger is now, or the middle once it has left; inside says
 *                       whether it is over the container; active whether there is one on the page;
 *                       speed is how fast the eased point moves, in units a second.
 *   quality             { name, value, pick(low, medium, high) }: "low", "medium" or "high", the same as
 *                       0, 0.5 or 1, and pick() returns the argument for the current name.
 *   progress            0..1, as last given to setProgress. progressEased follows it smoothly.
 *   still               true when only still frames are drawn (reduced motion, or the still option).
 *   running             true while the frame loop runs.
 *   failed              false, or why there is no picture: "no-webgl", "no-container" (createStage
 *                       was given no element), "context-lost" or "error" (a frame threw).
 *
 *   onFrame(fn)         fn(time, delta, stage) before every frame is drawn. Returns a function that
 *                       removes it, as every on...() does.
 *   onResize(fn)        fn(size, stage) now (once the container has a size), and whenever the size or
 *                       the pixel ratio changes.
 *   onTokens(fn)        fn(tokens, stage) now, and whenever the theme changes: a data-theme (or any
 *                       other attribute) change on <html> or <body>, a prefers-color-scheme change, or
 *                       a call to refreshTokens().
 *   onQuality(fn)       fn(quality, stage) now, and when the quality changes: build what depends on
 *                       counts here.
 *   onPointer(fn)       fn(pointer, stage) whenever raw changes, also when no frames are drawn.
 *   onDestroy(fn)       fn() when the stage is destroyed: remove what the scene added outside the
 *                       scene graph (its own listeners, DOM nodes, render targets).
 *   setProgress(p)      scroll progress, clamped to 0..1. Pair it with progressOf() below.
 *   setPointer(x, y)    steer the pointer from code (-1..1, y up). The next real move takes over again.
 *   setQuality(name)    "low", "medium", "high", or "auto" to adapt again.
 *   refreshTokens()     read the colours again, after a theme change the stage cannot see.
 *   invalidate()        ask for one new frame when the loop is not running (a still or paused stage)
 *                       and something the picture depends on has changed. Does nothing while it runs.
 *   pause(reason)       stop the loop and the clock. reason is a word of your own ("user" when left
 *   resume(reason)      out); the loop runs again once every reason given to pause() has been resumed,
 *                       the container is on screen and the tab is visible. Reasons never fight.
 *   viewSize(distance)  { width, height } of what the camera sees at that distance (default: the
 *                       distance to the origin), in world units: place things by the visible area.
 *   dispose(object)     take an object out of the scene graph and free its geometries, materials and
 *                       textures (its children's too). For a new count, swap the geometry instead.
 *   handle(methods)     the object a scene's mount() returns: { stage, setProgress, setPointer, setData,
 *                       pause, resume, destroy } plus the scene's own methods, which replace these
 *                       (a setProgress or setPointer of your own should still call the stage's).
 *   destroy()           stop, remove every listener and observer, free the scene graph and the
 *                       renderer, remove the canvas, put the container back. Safe to call twice;
 *                       createStage() on the same container afterwards works.
 *
 *   progressOf(element, mode)   on the stage, and exported next to createStage: how far an element
 *                       has travelled through the viewport, 0..1. "cover" (default): 0 as its top
 *                       enters at the bottom, 1 as its bottom leaves at the top. "contain": for a
 *                       section taller than the screen (a pinned chapter): 0 as its top reaches the
 *                       top, 1 as its bottom reaches the bottom. Typical use:
 *                       stage.onFrame(() => scene.setProgress(progressOf(section)));
 *
 * THE FIRST FRAME
 *
 * Compiling the shaders is the heaviest part of a start, so it gets tasks of its own: at the first
 * frame the stage compiles every material in the scene (three's compileAsync where the browser
 * can compile beside the page, KHR_parallel_shader_compile; else compile(), and the first frame
 * waits for the next quiet moment while the driver works), and only then draws. Build the scene
 * in mount(); a material added later compiles at its first render. Measure the start after
 * data-scene="live" (scenes.md section 8): no single task of the start should come near the
 * 330 to 550 ms that mount, compile and the first frame took together in one task.
 *
 * STILL FRAMES
 *
 * With prefers-reduced-motion: reduce the loop never runs. The stage draws one frame at stillTime
 * with delta 0, and again after a resize, a theme change, a quality change or invalidate(). So a
 * scene must look finished at stillTime with no history: when stage.still is true, set every eased
 * value straight to its target. The still does not follow the pointer or the scroll; call
 * invalidate() only for a real change (new data, a new chapter). A stage that is paused before its
 * first frame shows the same still, so a remembered "motion off" is never an empty box.
 *
 * RULES FOR A SCENE
 *
 * - Return early on stage.failed, as above. Never touch stage.renderer after that.
 * - No requestAnimationFrame, resize, visibility or pointer listener of your own: use the stage.
 * - Every colour comes from stage.tokens or stage.uniforms. In a ShaderMaterial end the fragment
 *   shader with `#include <colorspace_fragment>`, or the colours come out too dark.
 * - Do not paint a flat background: where there is nothing to draw, leave the pixels transparent,
 *   so the page shows through. The one exception is a framed scene, a window onto a place with an
 *   edge of its own (a framed hero, a panel, a map card): it may fill its frame, with colours from
 *   the tokens only (stage.scene.background = stage.tokens.bg, or a backdrop mesh with a gradient
 *   of them), when the container's CSS background is that same colour, so the poster, the
 *   fallback and the first frame match.
 * - Build counts from stage.quality inside onQuality, and dispose() the geometry you replace.
 * - Geometry that the vertex shader moves needs `frustumCulled = false`: three cannot know where
 *   it ends up, and would drop it at the wrong moment.
 * - Things outside the scene graph are yours to free, in onDestroy.
 */

import * as THREE from "three";

const TOKEN_NAMES = {
  bg: "--color-bg",
  text: "--color-text",
  muted: "--color-text-muted",
  accent: "--color-accent",
  accent2: "--color-accent-2",
  surface: "--color-surface",
  border: "--color-border",
};
const DEFAULTS = {
  quality: "auto",
  antialias: true,
  maxDpr: 2,
  renderScale: 1,
  tokens: {},
  stillTime: 8,
  still: false,
  pointerEase: 0.18,
  progressEase: 0.25,
  fade: 400,
};
const CAMERA = { fov: 45, near: 0.1, far: 100, position: [0, 0, 5], lookAt: [0, 0, 0] };
const TIERS = ["low", "medium", "high"];
const MAX_PIXELS = { low: 2.1e6, medium: 3.6e6, high: 8.3e6 }; // drawing buffer budget: 1080p, between, 4K
const MAX_DELTA = 0.1;   // seconds: a longer gap between two frames counts as this
const SLOW_FRAME = 22;   // milliseconds: an average above this (under 45 frames a second) is too slow
const SAMPLE = 90;       // frames in one measurement, about a second and a half
const WARM_UP = 12;      // frames left out after a start: shaders compile there

const stages = new WeakMap(); // container -> its live stage, so a second mount replaces the first
const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
const nothing = () => {};

// One 1 x 1 canvas for every colour that has to be read back as sRGB, shared by every stage.
let probeContext = null;
function probe2d() {
  if (!probeContext) {
    const probe = document.createElement("canvas");
    probe.width = probe.height = 1;
    probeContext = probe.getContext("2d", { willReadFrequently: true });
  }
  return probeContext;
}

/** How far ELEMENT has travelled through the viewport, 0..1. See the top of this file. */
export function progressOf(element, mode = "cover") {
  const box = element.getBoundingClientRect();
  const view = window.innerHeight || document.documentElement.clientHeight || 1;
  if (mode !== "contain") return clamp((view - box.top) / (view + box.height), 0, 1);
  const extra = box.height - view; // above 0: taller than the screen
  if (extra === 0) return box.top <= 0 ? 1 : 0;
  return clamp(extra > 0 ? -box.top / extra : (view - box.bottom) / -extra, 0, 1);
}

/** Is this WebGL context drawn by the processor instead of a graphics chip? Then start low. */
function softwareRendering(gl) {
  let name = String(gl.getParameter(gl.RENDERER) || "");
  if (/webkit webgl/i.test(name)) { // Chromium hides the name here and gives it through the extension
    const info = gl.getExtension("WEBGL_debug_renderer_info");
    if (info) name = String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL) || "");
  }
  return /swiftshader|llvmpipe|softpipe|software|basic render/i.test(name);
}

/** The quality "auto" starts with: a guess from the device. Measuring corrects it downwards. */
function guessQuality(gl, coarse) {
  if (softwareRendering(gl)) return "low";
  const cores = navigator.hardwareConcurrency || 4;
  const memory = navigator.deviceMemory || 8; // gigabytes; only Chromium tells
  let tier = coarse ? 1 : 2;                  // a phone or tablet starts in the middle
  if (cores <= 4 || memory <= 4) tier -= 1;
  if (cores <= 2 || memory <= 2) tier = 0;
  return TIERS[Math.max(0, tier)];
}

/** Free every geometry, material and texture under ROOT (ROOT included). */
function disposeTree(root) {
  const disposeMaterial = (material) => {
    for (const value of Object.values(material)) if (value && value.isTexture) value.dispose();
    for (const uniform of Object.values(material.uniforms || {})) {
      const values = uniform && Array.isArray(uniform.value) ? uniform.value : [uniform && uniform.value];
      for (const value of values) if (value && value.isTexture) value.dispose();
    }
    material.dispose();
  };
  root.traverse((object) => {
    if (object.geometry) object.geometry.dispose();
    for (const material of [].concat(object.material || [])) disposeMaterial(material);
    for (const key of ["background", "environment"]) {
      if (object[key] && object[key].isTexture) object[key].dispose();
    }
    if (typeof object.dispose === "function") object.dispose(); // instanced meshes, lights with shadows
  });
}

export function createStage(element, options = {}) {
  // No element to draw in (a selector that matched nothing): that ends as a failed stage, not as a crash.
  const container = element && element.nodeType === 1 ? element : document.createElement("div");
  if (stages.has(container)) stages.get(container).destroy(); // mounted twice: hot reload, a double effect
  const o = { ...DEFAULTS, ...options };
  const tokenNames = { ...TOKEN_NAMES, ...o.tokens };
  const reducedQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const lists = { frame: [], resize: [], tokens: [], quality: [], pointer: [], destroy: [] };
  const cleanups = [];   // one function per listener and observer: destroy() runs them all
  const pauses = new Set();
  const posters = [];    // [poster element, its inline opacity, its inline transition]
  let destroyed = false, inView = typeof IntersectionObserver !== "function", rafId = 0, last = null;
  let dirty = true;      // the picture on screen is out of date (or there is none yet)
  let live = false, auto = !TIERS.includes(o.quality), tokenSignature = null, madeRelative = false;
  let samples = -WARM_UP, sampleTotal = 0, maxSide = 4096;

  const listen = (target, type, fn, how) => {
    target.addEventListener(type, fn, how);
    cleanups.push(() => target.removeEventListener(type, fn, how));
  };
  const watch = (query, fn) => { // Safari before 14 has addListener only
    if (query.addEventListener) listen(query, "change", fn);
    else if (query.addListener) { query.addListener(fn); cleanups.push(() => query.removeListener(fn)); }
  };
  const emit = (list, ...args) => { for (const fn of list.slice()) fn(...args, stage); };
  const subscribe = (list, fn, now) => {
    if (destroyed || !renderer || typeof fn !== "function") return nothing;
    list.push(fn);
    const first = now && now();
    if (first) fn(first, stage);
    return () => { const at = list.indexOf(fn); if (at !== -1) list.splice(at, 1); };
  };

  // 1. The canvas and the WebGL context. The context is asked for here, not by three, so a browser
  //    without WebGL 2 ends in the fallback quietly instead of in an exception and a console error.
  const canvas = document.createElement("canvas");
  canvas.setAttribute("aria-hidden", "true");
  canvas.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;display:block;"
    + "pointer-events:none;opacity:0"; // invisible until the first frame is drawn
  let renderer = null, gl = null;
  try {
    const wanted = { alpha: true, antialias: o.antialias !== false, depth: true, stencil: false,
                     premultipliedAlpha: true, powerPreference: "high-performance" };
    if (container === element) gl = canvas.getContext("webgl2", wanted);
    if (gl) {
      renderer = new THREE.WebGLRenderer({ canvas, context: gl, alpha: true, antialias: o.antialias !== false,
                                           premultipliedAlpha: true, stencil: false });
      renderer.setClearColor(0x000000, 0);                 // transparent: the page is the background
      renderer.outputColorSpace = THREE.SRGBColorSpace;    // CSS colours are sRGB, and so is the canvas
      renderer.toneMapping = THREE.NoToneMapping;          // a token must come out as the colour it is
      maxSide = gl.getParameter(gl.MAX_RENDERBUFFER_SIZE) || maxSide;
    }
  } catch (error) {
    renderer = null;
  }

  const scene = new THREE.Scene();
  const camera = o.camera && o.camera.isCamera ? o.camera : (() => {
    const c = { ...CAMERA, ...o.camera };
    const made = new THREE.PerspectiveCamera(c.fov, 1, c.near, c.far);
    made.position.set(c.position[0], c.position[1], c.position[2]);
    made.lookAt(c.lookAt[0], c.lookAt[1], c.lookAt[2]);
    return made;
  })();
  const clock = { time: 0, delta: 0, frame: 0 };
  const size = { width: 0, height: 0, aspect: 1, dpr: 1, pixels: new THREE.Vector2(1, 1) };
  const pointer = { x: 0, y: 0, raw: { x: 0, y: 0 }, inside: false, active: false, speed: 0 };
  const quality = { name: "high", value: 1 };
  quality.pick = (low, medium, high) => [low, medium, high][TIERS.indexOf(quality.name)];
  const tokens = { css: {}, dark: false, blending: THREE.NormalBlending };
  for (const name of Object.keys(tokenNames)) tokens[name] = new THREE.Color();
  const uniforms = {
    uTime: { value: 0 }, uResolution: { value: size.pixels }, uPixelRatio: { value: 1 },
    uPointer: { value: new THREE.Vector2() }, uProgress: { value: 0 }, uDark: { value: 0 },
  };
  for (const name of Object.keys(tokenNames)) { // uBg, uText, uAccent ...: the same Color objects, so they follow
    uniforms["u" + name[0].toUpperCase() + name.slice(1)] = { value: tokens[name] };
  }

  const stage = {
    container,
    canvas,
    renderer,
    scene,
    camera,
    clock,
    size,
    tokens,
    uniforms,
    pointer,
    quality,
    progress: 0,
    progressEased: 0,
    still: Boolean(o.still) || reducedQuery.matches,
    running: false,
    failed: renderer ? false : (container === element ? "no-webgl" : "no-container"),
    onFrame: (fn) => subscribe(lists.frame, fn),
    onResize: (fn) => subscribe(lists.resize, fn, () => (size.width > 0 && size.height > 0 ? size : null)),
    onTokens: (fn) => subscribe(lists.tokens, fn, () => tokens),
    onQuality: (fn) => subscribe(lists.quality, fn, () => quality),
    onPointer: (fn) => subscribe(lists.pointer, fn),
    onDestroy: (fn) => subscribe(lists.destroy, fn),
    setProgress,
    setPointer,
    setQuality,
    refreshTokens,
    invalidate,
    pause,
    resume,
    viewSize,
    dispose,
    handle,
    progressOf,
    destroy,
  };
  stages.set(container, stage);

  // 2. The loop. One requestAnimationFrame at a time, asked for in schedule() only. update() works
  //    out from every reason at once whether the loop should run, so the reasons cannot fight.
  const visible = () => !destroyed && !stage.failed && inView && !document.hidden
    && size.width > 0 && size.height > 0;

  function update() {
    const run = visible() && !stage.still && pauses.size === 0;
    if (run && !stage.running) { last = null; samples = -WARM_UP; sampleTotal = 0; } // a fresh start: no delta
    stage.running = run;
    if (run || (visible() && dirty)) schedule();
    else if (rafId) { cancelAnimationFrame(rafId); rafId = 0; }
  }

  function schedule() {
    if (!rafId) rafId = requestAnimationFrame(tick);
  }

  // The shaders are compiled before the first frame, in tasks of their own (see "The first frame"
  // at the top). With KHR_parallel_shader_compile the driver builds them while the page goes on and
  // three only polls; without it compile() hands them to the driver, and the first frame comes at
  // the next quiet moment, so the wait falls outside the frame and outside mount().
  let compiled = !renderer || typeof renderer.compile !== "function", compiling = false;
  function compileFirst() {
    if (compiling) return;
    compiling = true;
    const done = () => {
      compiled = true;
      if (destroyed) return;
      dirty = true;
      update();
    };
    const extensions = renderer.extensions;
    // has() asks without a console warning; compileAsync() warns where the extension is missing.
    const parallel = extensions && typeof extensions.has === "function" && extensions.has("KHR_parallel_shader_compile");
    if (parallel && typeof renderer.compileAsync === "function") {
      renderer.compileAsync(stage.scene, stage.camera).catch(nothing).then(done);
      return;
    }
    try { renderer.compile(stage.scene, stage.camera); } catch (error) { /* the first render says what is wrong */ }
    try { renderer.getContext().flush(); } catch (error) { /* a lost context: the first render falls back */ }
    if (typeof window.requestIdleCallback === "function") window.requestIdleCallback(done, { timeout: 400 });
    else setTimeout(done, 120);
  }

  function tick(now) {
    rafId = 0;
    if (!visible()) return;
    if (!compiled) { compileFirst(); return; } // nothing is drawn until the shaders are there; done() asks again
    if (stage.running) {
      const gap = last === null ? 0 : now - last; // milliseconds since the last frame
      last = now;
      clock.delta = Math.min(gap / 1000, MAX_DELTA);
      clock.time += clock.delta;
      ease(clock.delta);
      if (draw()) { measure(gap); schedule(); }
    } else if (dirty) { // one still frame: reduced motion, or paused with nothing on screen yet
      if (stage.still || clock.frame === 0) clock.time = o.stillTime;
      clock.delta = 0;
      ease(0);
      draw();
    }
  }

  function draw() {
    try {
      uniforms.uTime.value = clock.time;
      uniforms.uProgress.value = stage.progressEased;
      uniforms.uPointer.value.set(pointer.x, pointer.y);
      emit(lists.frame, clock.time, clock.delta);
      if (destroyed) return false; // a callback destroyed the stage
      renderer.render(stage.scene, stage.camera);
    } catch (error) { // a scene that throws must not leave half a picture: show the poster, and say why
      fail("error");
      console.error(error);
      return false;
    }
    clock.frame += 1;
    dirty = false;
    if (!live) goLive();
    return true;
  }

  // Move the eased pointer and progress towards their targets, the same at every frame rate.
  function ease(delta) {
    const still = delta === 0;
    const px = pointer.x, py = pointer.y;
    const k = still ? 0 : 1 - Math.exp(-delta / Math.max(o.pointerEase, 0.001));
    pointer.x += (pointer.raw.x - pointer.x) * k;
    pointer.y += (pointer.raw.y - pointer.y) * k;
    pointer.speed = still ? 0 : Math.hypot(pointer.x - px, pointer.y - py) / delta;
    const jump = still || clock.frame === 0; // a still, or nothing drawn yet: start where the page put it
    const j = jump ? 1 : 1 - Math.exp(-delta / Math.max(o.progressEase, 0.001));
    stage.progressEased += (stage.progress - stage.progressEased) * j;
  }

  // Quality "auto": time the frames, and step down when a window of them was too slow on average.
  function measure(gap) {
    if (!auto || quality.name === "low" || gap <= 0 || gap > 250) return; // 250 ms: a hiccup, not a frame rate
    samples += 1;
    if (samples <= 0) return;
    sampleTotal += gap;
    const average = sampleTotal / samples;
    if (samples < SAMPLE && !(samples >= SAMPLE / 3 && average > SLOW_FRAME * 2)) return;
    if (average > SLOW_FRAME) applyQuality(average > SLOW_FRAME * 2 ? "low" : TIERS[TIERS.indexOf(quality.name) - 1]);
    samples = -WARM_UP;
    sampleTotal = 0;
  }

  function applyQuality(name) {
    if (!TIERS.includes(name) || name === quality.name) return;
    quality.name = name;
    quality.value = TIERS.indexOf(name) / 2;
    resize();
    emit(lists.quality, quality);
    invalidate();
  }

  function setQuality(name) {
    if (destroyed || !renderer) return;
    auto = !TIERS.includes(name);
    applyQuality(auto ? guessQuality(gl, coarse) : name);
  }

  // 3. Size. The canvas is out of the flow, so it can never change the container it measures.
  function resize() {
    if (destroyed || !renderer) return;
    const width = container.clientWidth, height = container.clientHeight;
    const scale = Array.isArray(o.renderScale) ? o.renderScale[TIERS.indexOf(quality.name)] : o.renderScale;
    const cap = quality.name === "low" ? 1 : Math.min(o.maxDpr, coarse ? 1.5 : 2);
    let dpr = Math.min(window.devicePixelRatio || 1, cap) * (scale || 1);
    const area = width * height * dpr * dpr;
    if (area > MAX_PIXELS[quality.name]) dpr *= Math.sqrt(MAX_PIXELS[quality.name] / area);
    if (Math.max(width, height) * dpr > maxSide) dpr = maxSide / Math.max(width, height);
    if (width === size.width && height === size.height && dpr === size.dpr) return;
    size.width = width;
    size.height = height;
    size.aspect = width / height || 1;
    size.dpr = dpr;
    if (width > 0 && height > 0) {
      renderer.setPixelRatio(dpr);
      renderer.setSize(width, height, false); // false: the CSS size stays 100%
      size.pixels.set(canvas.width, canvas.height);
      uniforms.uPixelRatio.value = dpr;
      if (stage.camera.isPerspectiveCamera) {
        stage.camera.aspect = size.aspect;
        stage.camera.updateProjectionMatrix();
      }
      emit(lists.resize, size);
      dirty = true; // resizing a canvas empties it
    }
    update();
  }

  // 4. Colours. Any CSS colour becomes [r, g, b] in 0..1, or null. The browser does the work: the
  //    canvas shows no text, so its `color` is free to use as a probe, and that resolves var(),
  //    light-dark(), color-mix() and names. What is left in a wider colour space (oklch, lab,
  //    display-p3) is painted on one shared 1 x 1 canvas and read back as sRGB (probe2d: made with
  //    willReadFrequently, so the read-back stays on the processor and never stalls the GPU).
  function resolveColor(value) {
    if (!value) return null;
    canvas.style.color = "";
    canvas.style.color = value;
    if (!canvas.style.color) return null; // not a colour
    const computed = getComputedStyle(canvas).color;
    canvas.style.color = "";
    const numbers = (computed.match(/-?[\d.]+(?:e-?\d+)?%?/g) || []).map(parseFloat);
    const scale = /^rgba?\(/.test(computed) ? 255 : (/^color\(srgb /.test(computed) ? 1 : 0);
    if (scale && numbers.length >= 3) return numbers.slice(0, 3).map((n) => clamp(n / scale, 0, 1));
    try {
      const context = probe2d();
      context.clearRect(0, 0, 1, 1);
      context.fillStyle = computed;
      context.fillRect(0, 0, 1, 1);
      return Array.from(context.getImageData(0, 0, 1, 1).data.slice(0, 3), (n) => n / 255);
    } catch (error) {
      return null;
    }
  }

  // The colour behind the container: the first background up the tree that is not see-through.
  function backdrop() {
    for (let node = container; node && node.nodeType === 1; node = node.parentNode) {
      const color = getComputedStyle(node).backgroundColor;
      const numbers = (color.match(/-?[\d.]+/g) || []).map(parseFloat);
      const alpha = /^rgba\(|\/ /.test(color) ? numbers[numbers.length - 1] : 1;
      const seeThrough = color === "transparent" || alpha === 0;
      if (!seeThrough) return resolveColor(color) || [1, 1, 1];
    }
    const scheme = getComputedStyle(document.documentElement).colorScheme || "";
    return /dark/.test(scheme) && (darkQuery.matches || !/light/.test(scheme)) ? [0.07, 0.07, 0.07] : [1, 1, 1];
  }

  function refreshTokens() {
    if (destroyed || !renderer) return;
    const style = getComputedStyle(container);
    const raw = {};
    for (const [name, source] of Object.entries(tokenNames)) {
      raw[name] = String(source).startsWith("--") ? style.getPropertyValue(source).trim() : String(source);
    }
    // Reading is cheap, resolving is not: stop here when nothing a colour can depend on has changed.
    const signature = [style.colorScheme, style.color, style.backgroundColor, ...Object.values(raw)].join("|");
    if (signature === tokenSignature) return;
    tokenSignature = signature;
    const mix = (a, b, t) => a.map((value, i) => value + (b[i] - value) * t);
    const found = {};
    for (const name of Object.keys(tokenNames)) found[name] = resolveColor(raw[name]);
    const rgb = { ...found };
    rgb.bg = found.bg || backdrop();
    rgb.text = found.text || resolveColor(style.color) || [0, 0, 0];
    rgb.accent = found.accent || rgb.text;
    rgb.accent2 = found.accent2 || rgb.accent;
    rgb.surface = found.surface || rgb.bg;
    rgb.border = found.border || mix(rgb.bg, rgb.text, 0.2);
    rgb.muted = found.muted || mix(rgb.bg, rgb.text, 0.6);
    for (const name of Object.keys(tokenNames)) {
      const [r, g, b] = rgb[name] || rgb.text;
      tokens[name].setRGB(r, g, b, THREE.SRGBColorSpace); // stored as linear working colour, as three expects
      const stand = [r, g, b].map((value) => Math.round(value * 255)).join(" ");
      tokens.css[name] = found[name] ? raw[name] : `rgb(${stand})`;
    }
    // Relative luminance of the background (the Color holds linear values). Under 0.2 light adds up
    // to a glow that reads; above it only darker "ink" does.
    tokens.dark = 0.2126 * tokens.bg.r + 0.7152 * tokens.bg.g + 0.0722 * tokens.bg.b < 0.2;
    tokens.blending = tokens.dark ? THREE.AdditiveBlending : THREE.NormalBlending;
    uniforms.uDark.value = tokens.dark ? 1 : 0;
    emit(lists.tokens, tokens);
    invalidate();
  }

  // 5. Pointer and progress.
  function setRaw(x, y, active) {
    if (x === pointer.raw.x && y === pointer.raw.y && active === pointer.active) return;
    pointer.raw.x = x;
    pointer.raw.y = y;
    pointer.active = active;
    emit(lists.pointer, pointer);
  }

  function pointerAt(clientX, clientY) {
    const box = container.getBoundingClientRect();
    if (!box.width || !box.height) return;
    const x = ((clientX - box.left) / box.width) * 2 - 1;
    const y = 1 - ((clientY - box.top) / box.height) * 2;
    pointer.inside = Math.abs(x) <= 1 && Math.abs(y) <= 1;
    setRaw(clamp(x, -1, 1), clamp(y, -1, 1), true);
  }

  function pointerGone() { // the pointer left the page, or the finger lifted: ease back to the middle
    pointer.inside = false;
    setRaw(0, 0, false);
  }

  function setPointer(x, y) {
    if (destroyed || !renderer || !Number.isFinite(x) || !Number.isFinite(y)) return;
    pointer.inside = true;
    setRaw(clamp(x, -1, 1), clamp(y, -1, 1), true);
  }

  function setProgress(p) {
    if (destroyed || !Number.isFinite(Number(p))) return;
    stage.progress = clamp(Number(p), 0, 1);
  }

  // 6. What a scene and a page call.
  function invalidate() {
    if (destroyed || !renderer) return;
    dirty = true;
    update();
  }

  function pause(reason = "user") {
    if (destroyed) return;
    pauses.add(String(reason));
    update();
  }

  function resume(reason = "user") {
    if (destroyed) return;
    pauses.delete(String(reason));
    update();
  }

  function viewSize(distance = stage.camera.position.length()) {
    const cam = stage.camera;
    if (cam.isPerspectiveCamera) {
      const height = (2 * Math.tan((cam.fov * Math.PI) / 360) * distance) / cam.zoom;
      return { width: height * cam.aspect, height };
    }
    return { width: (cam.right - cam.left) / cam.zoom, height: (cam.top - cam.bottom) / cam.zoom };
  }

  function dispose(object) {
    if (!object) return;
    if (object.parent) object.parent.remove(object);
    disposeTree(object);
  }

  function handle(methods = {}) {
    return { stage, setProgress, setPointer, setData: nothing, pause, resume, destroy, ...methods };
  }

  // 7. Live, fallback and the poster.
  function showPosters(show) {
    for (const [poster, opacity, transition] of posters) {
      poster.style.transition = show || stage.still || !o.fade ? transition : `opacity ${o.fade}ms ease-out`;
      poster.style.opacity = show ? opacity : "0";
    }
  }

  function goLive() {
    live = true;
    container.setAttribute("data-scene", "live");
    void getComputedStyle(canvas).opacity; // read it once, so the change below is a transition, not a jump
    if (o.fade && !stage.still) canvas.style.transition = `opacity ${o.fade}ms ease-out`;
    canvas.style.opacity = "1";
    showPosters(false);
  }

  function fail(reason) {
    stage.failed = reason;
    live = false;
    container.setAttribute("data-scene", "fallback");
    canvas.style.transition = "";
    canvas.style.opacity = "0";
    showPosters(true);
    update();
  }

  function destroy() {
    if (destroyed) return;
    destroyed = true;
    stage.running = false;
    for (const fn of lists.destroy.slice()) {
      try { fn(); } catch (error) { console.error(error); } // one scene's mistake must not stop the clean-up
    }
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
    for (const off of cleanups.splice(0)) off();
    for (const list of Object.values(lists)) list.length = 0;
    disposeTree(stage.scene);
    stage.scene.clear();
    if (renderer) {
      renderer.dispose();          // also takes three's own context listeners off the canvas
      renderer.forceContextLoss(); // give the context back now: a browser allows only about sixteen
    }
    canvas.remove();
    showPosters(true);
    posters.length = 0;
    container.removeAttribute("data-scene");
    if (madeRelative) container.style.position = "";
    if (stages.get(container) === stage) stages.delete(container);
  }

  // 8. No WebGL (or no container): say so and stop here. Every method above is already a no-op.
  if (!renderer) {
    container.setAttribute("data-scene", "fallback");
    return stage;
  }

  // 9. Into the page, and the things that change after that.
  if (getComputedStyle(container).position === "static") {
    container.style.position = "relative";
    madeRelative = true;
  }
  for (const poster of container.querySelectorAll("[data-scene-poster]")) {
    posters.push([poster, poster.style.opacity, poster.style.transition]);
  }
  container.insertBefore(canvas, container.firstChild);
  quality.name = auto ? guessQuality(gl, coarse) : o.quality;
  quality.value = TIERS.indexOf(quality.name) / 2;
  resize();
  refreshTokens();

  if (typeof ResizeObserver === "function") {
    const sizeWatcher = new ResizeObserver(resize);
    sizeWatcher.observe(container);
    cleanups.push(() => sizeWatcher.disconnect());
  }
  listen(window, "resize", resize, { passive: true }); // also catches a zoom or a move to another screen
  if (typeof IntersectionObserver === "function") {
    const viewWatcher = new IntersectionObserver((entries) => {
      inView = entries[entries.length - 1].isIntersecting;
      update();
    });
    viewWatcher.observe(container);
    cleanups.push(() => viewWatcher.disconnect());
  }
  listen(document, "visibilitychange", update);
  watch(reducedQuery, () => {
    stage.still = Boolean(o.still) || reducedQuery.matches;
    invalidate();
  });
  watch(darkQuery, refreshTokens);
  if (typeof MutationObserver === "function") { // data-theme, a class such as "dark", an inline style
    const themeWatcher = new MutationObserver(refreshTokens);
    themeWatcher.observe(document.documentElement, { attributes: true });
    if (document.body) themeWatcher.observe(document.body, { attributes: true });
    cleanups.push(() => themeWatcher.disconnect());
  }
  // The pointer is read from the window: the canvas usually sits behind text and never gets the
  // event. Every listener is passive, so none of them can hold up a scroll.
  const passive = { passive: true };
  const onPointer = (event) => pointerAt(event.clientX, event.clientY);
  const onTouch = (event) => {
    const touch = event.touches[0];
    if (touch) pointerAt(touch.clientX, touch.clientY);
    else pointerGone();
  };
  listen(window, "pointermove", onPointer, passive);
  listen(window, "pointerdown", onPointer, passive);
  listen(window, "touchstart", onTouch, passive);
  listen(window, "touchmove", onTouch, passive); // goes on while the page scrolls; pointermove stops there
  listen(window, "touchend", onTouch, passive);
  listen(window, "touchcancel", onTouch, passive);
  listen(document.documentElement, "pointerleave", pointerGone, passive);
  listen(window, "blur", pointerGone, passive);
  // A lost context empties the canvas: show the poster at once. Most are restored, and three then
  // builds its state again by itself; one that is not restored simply stays on the poster.
  listen(canvas, "webglcontextlost", (event) => {
    event.preventDefault(); // without this the browser never restores it
    fail("context-lost");
  });
  listen(canvas, "webglcontextrestored", () => {
    if (stage.failed !== "context-lost") return; // a scene that threw stays down
    stage.failed = false;
    invalidate();
  });

  update();
  return stage;
}
