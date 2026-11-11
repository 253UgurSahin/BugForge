"""Tests for forge-design/scenes: the scene kit for look levels 4 and 5.

Every .js file in the folder is checked, so a scene added later is covered without a change here:
it parses as an ES module, imports nothing but "three" and the files next to it, names no other
host, leaves the frame loop to stage.js, and a file that mounts a scene also takes it down and
handles a missing WebGL (problems() below holds these rules, and RuleTests shows each one fire).
The comment at the top of stage.js, lazy.js and glsl.js must name everything the code offers,
because scene authors work from that comment. The folder also has to pass motioncheck.py.

stage.js and lazy.js are also run, in Node with a make-believe browser and a stand-in for
three.js (the kit ships without three; only the gallery has a copy): the loop, pausing, reduced motion, the theme, the
pointer, quality, the fallback and destroy(), and for lazy.js that nothing loads too early. So
are depth.js in a panel that scrolls inside a fixed frame, contour.js's outline work (GeoJSON and
point lists, the trail cut to fit, the place beside the text, label places, the phone's calm) and
field.js's phone and streak options. Those tests need Node and are skipped without it. What only
a real browser can show (real WebGL, real pixels) is proved by hand with Playwright when the kit
changes, not here."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load  # noqa: E402

motioncheck = load("forge-design", "motioncheck")
SCENES = os.path.join(ROOT, "forge-design", "scenes")
COMMENT = re.compile(r"/\*.*?\*/|(?<![:\w])//[^\n]*", re.S)  # not the // of a URL
STATIC_IMPORT = re.compile(r"""(?m)^\s*(?:import\s*["']|import\b[^"';()]*?\bfrom\s*["']"""
                           r"""|export\s*(?:\*|\{)[^"';]*?\bfrom\s*["'])([^"']+)["']""")
DYNAMIC_IMPORT = re.compile(r"""\bimport\s*\(\s*(?:(["'`])([^"'`]*)\1\s*\))?""")
STAGE_MEMBER = re.compile(r"(?m)^    (\w+)\s*[,:(]")  # `name,`  `name: value,`  `name(args) {`
MOUNTS = re.compile(r"export\s+(?:async\s+)?function\s+mount\b|export\s+const\s+mount\b|export\s*\{[^}]*\bmount\b")
SEES_ITSELF_OUT = re.compile(r"IntersectionObserver|visibilitychange|document\.hidden")

# A stand-in for three.js with only what stage.js touches. It counts what the stage asks of it.
THREE = r"""
export const SRGBColorSpace = "srgb", NoToneMapping = 0, NormalBlending = 1, AdditiveBlending = 2;
export const calls = { render: 0, dispose: 0, contextLoss: 0, disposed: [] };
const linear = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
export class Color {
  constructor() { this.r = this.g = this.b = 1; }
  setRGB(r, g, b) { this.r = linear(r); this.g = linear(g); this.b = linear(b); return this; }
}
export class Vector2 {
  constructor(x = 0, y = 0) { this.x = x; this.y = y; }
  set(x, y) { this.x = x; this.y = y; return this; }
  copy(v) { return this.set(v.x, v.y); }
  lerp(v, t) { return this.set(this.x + (v.x - this.x) * t, this.y + (v.y - this.y) * t); }
}
class Node3 {
  constructor() { this.children = []; this.parent = null; }
  add(child) { this.children.push(child); child.parent = this; return this; }
  remove(child) { this.children = this.children.filter((item) => item !== child); child.parent = null; }
  clear() { this.children = []; }
  traverse(fn) { fn(this); for (const child of this.children) child.traverse(fn); }
}
export class Scene extends Node3 {}
export class Mesh extends Node3 { // a geometry, a material and a texture in a uniform: all three must be freed
  constructor(name, material) {
    super();
    const freed = (part) => () => calls.disposed.push(name + "." + part);
    this.geometry = { dispose: freed("geometry") };
    this.material = { uniforms: { uMap: { value: { isTexture: true, dispose: freed("texture") } } },
                      dispose: freed("material") };
    if (name && typeof name === "object") this.geometry = name;   // new Mesh(geometry, material), as a scene makes it
    if (material) this.material = material;
  }
}
export class PerspectiveCamera {
  constructor(fov, aspect, near, far) {
    Object.assign(this, { fov, aspect, near, far, zoom: 1, isCamera: true, isPerspectiveCamera: true, updates: 0 });
    this.position = { x: 0, y: 0, z: 0, set(x, y, z) { Object.assign(this, { x, y, z }); },
                      length() { return Math.hypot(this.x, this.y, this.z); } };
  }
  lookAt() {}
  updateProjectionMatrix() { this.updates += 1; }
}
export class WebGLRenderer {
  constructor({ canvas }) { this.domElement = canvas; this.ratio = 1; }
  setClearColor() {}
  setPixelRatio(value) { this.ratio = value; }
  setSize(width, height) {
    this.domElement.width = Math.floor(width * this.ratio);
    this.domElement.height = Math.floor(height * this.ratio);
  }
  render() { calls.render += 1; }
  dispose() { calls.dispose += 1; }
  forceContextLoss() { calls.contextLoss += 1; }
}
// What contour.js and field.js add, as plain holders: enough to mount them flat and read their
// uniforms and placement. Nothing is drawn.
export class Vector3 {
  constructor(x = 0, y = 0, z = 0) { this.set(x, y, z); }
  set(x, y, z) { Object.assign(this, { x, y, z }); return this; }
  copy(v) { return this.set(v.x, v.y, v.z); }
}
export class Vector4 {
  constructor(x = 0, y = 0, z = 0, w = 0) { this.set(x, y, z, w); }
  set(x, y, z, w) { Object.assign(this, { x, y, z, w }); return this; }
}
export class ShaderMaterial { constructor(params) { Object.assign(this, params); } dispose() {} }
export class BufferGeometry {
  constructor() { this.attributes = {}; this.drawRange = { start: 0, count: Infinity }; }
  setAttribute(name, attribute) { this.attributes[name] = attribute; return this; }
  setDrawRange(start, count) { this.drawRange = { start, count }; }
  dispose() {}
}
export class PlaneGeometry extends BufferGeometry { rotateX() { return this; } }
export class BufferAttribute { constructor(array, itemSize) { Object.assign(this, { array, itemSize }); } }
const triple = (v) => ({ x: v, y: v, z: v, set(x, y, z) { Object.assign(this, { x, y, z }); return this; },
                         setScalar(s) { return this.set(s, s, s); } });
export class Group extends Node3 {
  constructor() { super(); Object.assign(this, { position: triple(0), scale: triple(1), rotation: triple(0) }); }
}
export class Points extends Group { constructor(geometry, material) { super(); Object.assign(this, { geometry, material }); } }
export class Raycaster { constructor() { this.ray = { intersectPlane: () => null }; } setFromCamera() {} }
export class Plane { constructor(normal, constant) { Object.assign(this, { normal, constant }); } }
export const MathUtils = { degToRad: (degrees) => (degrees * Math.PI) / 180,
                           damp: (x, y, lambda, dt) => x + (y - x) * (1 - Math.exp(-lambda * dt)) };
"""

# A make-believe browser: enough of window, document and the observers for stage.js and lazy.js,
# with every listener, observer, frame, idle callback and timer kept where the test can see it.
BROWSER = r"""
export function makeBrowser({ reduced = false, webgl = true, saveData = false, idle = true, storage = true } = {}) {
  const b = { listeners: [], frames: new Map(), frameId: 0, observers: [], now: 1000, idle: [], timers: [],
              store: new Map(), reduced, vars: { "--color-bg": "#070b0e", "--color-text": "#e9f0ee",
                                                 "--color-accent": "#3fd0bb" } };
  const target = (name) => ({
    name,
    addEventListener(type, fn, how) {
      b.listeners.push({ name, type, fn, passive: Boolean(how && how.passive), capture: how === true || Boolean(how && how.capture) });
    },
    removeEventListener(type, fn) {
      const at = b.listeners.findIndex((l) => l.name === name && l.type === type && l.fn === fn);
      if (at !== -1) b.listeners.splice(at, 1);
    },
  });
  const attributes = (node) => Object.assign(node, {
    attrs: {},
    setAttribute(key, value) { node.attrs[key] = String(value); },
    getAttribute(key) { return key in node.attrs ? node.attrs[key] : null; },
    removeAttribute(key) { delete node.attrs[key]; },
  });
  const gl = { RENDERER: 1, getParameter: (name) => (name === 1 ? "Test GPU" : 8192), getExtension: () => null };
  const makeCanvas = () => attributes(Object.assign(target("canvas"), {
    style: { cssText: "", color: "", opacity: "", transition: "" }, width: 300, height: 150,
    getContext: (kind) => (kind === "webgl2" && webgl ? gl : null),
    remove() {
      if (this.parent) this.parent.children = this.parent.children.filter((item) => item !== this);
      this.parent = null;
    },
  }));
  b.container = attributes(Object.assign(target("container"), {
    clientWidth: 800, clientHeight: 400, style: { position: "" }, children: [], nodeType: 1, parentNode: null,
    get firstChild() { return this.children[0] || null; },
    insertBefore(node) { this.children.unshift(node); node.parent = this; },
    querySelectorAll: () => [],
    getBoundingClientRect() { return { left: 100, top: 50, width: this.clientWidth, height: this.clientHeight }; },
  }));
  const queries = {};
  const media = (query) => (queries[query] = queries[query] || Object.defineProperty(target("media " + query),
    "matches", { get: () => (/reduced-motion/.test(query) ? b.reduced : false) }));
  const observer = (kind) => class {
    constructor(callback) { Object.assign(this, { kind, callback, on: false }); b.observers.push(this); }
    observe() { this.on = true; }
    disconnect() { this.on = false; }
  };
  const active = (kind) => b.observers.filter((item) => item.on && (!kind || item.kind === kind));
  b.active = (kind) => active(kind).length;
  b.fire = (name, type, event = {}) => {
    for (const l of b.listeners.filter((item) => item.name === name && item.type === type)) l.fn(event);
  };
  b.see = (visible) => { for (const item of active("intersection")) item.callback([{ isIntersecting: visible }]); };
  b.resize = (width, height) => {
    Object.assign(b.container, { clientWidth: width, clientHeight: height });
    for (const item of active("resize")) item.callback([]);
  };
  b.theme = (vars) => { Object.assign(b.vars, vars); for (const item of active("mutation")) item.callback([]); };
  // Run the frame that is waiting, ms milliseconds after the last one. Returns whether there was one.
  b.step = (ms = 16) => {
    b.now += ms;
    const waiting = [...b.frames.values()];
    b.frames.clear();
    for (const fn of waiting) fn(b.now);
    return waiting.length > 0;
  };
  b.runIdle = () => { for (const fn of b.idle.splice(0)) fn(); };
  const rgb = (value) => {
    const m = /^#(..)(..)(..)$/.exec(value);
    return m ? `rgb(${parseInt(m[1], 16)}, ${parseInt(m[2], 16)}, ${parseInt(m[3], 16)})` : "";
  };
  const guarded = (fn) => (...args) => { if (!storage) throw new Error("storage is off"); return fn(...args); };
  const localStorage = { getItem: guarded((key) => (b.store.has(key) ? b.store.get(key) : null)),
                         setItem: guarded((key, value) => { b.store.set(key, String(value)); }),
                         removeItem: guarded((key) => { b.store.delete(key); }) };
  const window = Object.assign(target("window"), {
    devicePixelRatio: 3, innerHeight: 900, matchMedia: media, localStorage,
    requestIdleCallback: idle ? (fn) => b.idle.push(fn) : undefined,
    cancelIdleCallback() { b.idle.length = 0; },
  });
  const document = Object.assign(target("document"), {
    hidden: false, documentElement: attributes(target("html")), body: attributes(target("body")),
    createElement: () => makeCanvas(),
  });
  const page = { position: "static", color: "rgb(233, 240, 238)", backgroundColor: "rgba(0, 0, 0, 0)",
                 colorScheme: "normal", getPropertyValue: (name) => b.vars[name] || "" };
  Object.assign(globalThis, {
    window, document,
    getComputedStyle: (node) => (node.name === "canvas" ? { color: rgb(node.style.color), opacity: "0" } : page),
    requestAnimationFrame: (fn) => { b.frames.set(++b.frameId, fn); return b.frameId; },
    cancelAnimationFrame: (id) => { b.frames.delete(id); },
    ResizeObserver: observer("resize"), IntersectionObserver: observer("intersection"),
    MutationObserver: observer("mutation"),
    setTimeout: (fn, ms) => b.timers.push({ fn, ms }), clearTimeout() {},
  });
  Object.defineProperty(globalThis, "navigator", { configurable: true, writable: true,
    value: { hardwareConcurrency: 8, deviceMemory: 8, connection: { saveData } } });
  return b;
}
"""

# Drives stage.js through one situation (the mode) and prints what happened as JSON.
STAGE_RUN = r"""
import { makeBrowser } from "./browser.mjs";
const mode = process.argv[2];
const b = makeBrowser({ reduced: mode === "reduced", webgl: mode !== "nowebgl" });
const THREE = await import("three");
const { createStage, progressOf } = await import("./scenes/stage.js");
const out = {}, logged = [];
console.error = (...args) => logged.push(String(args[0]));
const attr = () => b.container.getAttribute("data-scene");
const round = (value) => Math.round(value * 1000) / 1000;
const follow = (stage) => {
  const log = { frames: [], resize: 0, tokens: 0, quality: 0, pointer: 0, destroyed: 0 };
  stage.onFrame((time, delta) => log.frames.push([time, delta]));
  stage.onResize(() => { log.resize += 1; });
  stage.onTokens(() => { log.tokens += 1; });
  stage.onQuality(() => { log.quality += 1; });
  stage.onPointer(() => { log.pointer += 1; });
  stage.onDestroy(() => { log.destroyed += 1; });
  return log;
};

if (mode === "moving") {
  const stage = createStage(b.container, { quality: "high", fade: 0 });
  const log = follow(stage);
  out.start = { canvases: b.container.children.length, position: b.container.style.position,
                size: [stage.size.width, stage.size.height, stage.size.dpr],
                buffer: [stage.canvas.width, stage.canvas.height], aspect: stage.camera.aspect,
                calledAtOnce: [log.resize, log.tokens, log.quality], dark: stage.tokens.dark,
                additive: stage.tokens.blending === THREE.AdditiveBlending, css: { ...stage.tokens.css },
                running: stage.running, waiting: b.frames.size, failed: stage.failed, attr: attr() };
  b.see(true);
  out.seen = [stage.running, b.frames.size];
  b.step(); b.step(); b.step();
  out.threeFrames = { renders: THREE.calls.render, frame: stage.clock.frame, time: round(stage.clock.time),
                      firstDelta: log.frames[0][1], attr: attr(), opacity: stage.canvas.style.opacity,
                      uTime: round(stage.uniforms.uTime.value) };
  b.step(5000);
  out.longGap = [stage.clock.delta, round(stage.clock.time)];
  stage.pause();
  out.paused = [stage.running, b.frames.size, b.step(), round(stage.clock.time)];
  stage.resume();
  b.step(700);
  out.resumed = [stage.running, stage.clock.delta, round(stage.clock.time)];
  stage.pause("a"); stage.pause("b"); stage.resume("a");
  out.reasons = [stage.running];
  stage.resume("b");
  out.reasons.push(stage.running);
  stage.pause(); b.see(false); b.see(true);                   // on screen again, but paused by hand
  out.fights = [stage.running];
  document.hidden = true; b.fire("document", "visibilitychange");
  document.hidden = false; b.fire("document", "visibilitychange");
  out.fights.push(stage.running);                             // visible again, still paused by hand
  stage.resume();
  out.fights.push(stage.running);
  b.see(false);
  out.offScreen = [stage.running, b.frames.size];
  b.see(true);
  document.hidden = true; b.fire("document", "visibilitychange");
  out.hidden = [stage.running, b.frames.size];
  document.hidden = false; b.fire("document", "visibilitychange");
  out.back = stage.running;
  const updates = stage.camera.updates;
  b.resize(400, 400);
  out.resized = { buffer: [stage.canvas.width, stage.canvas.height], aspect: stage.camera.aspect, calls: log.resize,
                  cameraUpdated: stage.camera.updates > updates, pixels: [stage.size.pixels.x, stage.size.pixels.y] };
  b.resize(400, 400);
  out.sameSize = log.resize;
  b.theme({ "--color-bg": "#f6f7f5", "--color-text": "#111715" });
  out.light = { dark: stage.tokens.dark, normal: stage.tokens.blending === THREE.NormalBlending,
                uDark: stage.uniforms.uDark.value, calls: log.tokens, bg: stage.tokens.css.bg };
  b.theme({});
  out.sameTheme = log.tokens;
  b.fire("window", "pointermove", { clientX: 500, clientY: 50 });   // the container is 400 wide at 100, 50
  out.pointer = { raw: [stage.pointer.raw.x, stage.pointer.raw.y], eased: [stage.pointer.x, stage.pointer.y],
                  inside: stage.pointer.inside, active: stage.pointer.active, calls: log.pointer };
  b.step(); b.step();
  out.easing = [round(stage.pointer.x), round(stage.uniforms.uPointer.value.x), stage.pointer.speed > 0];
  for (let i = 0; i < 200; i++) b.step();
  out.eased = [round(stage.pointer.x), round(stage.pointer.y)];
  b.fire("window", "touchmove", { touches: [{ clientX: 300, clientY: 250 }] });
  out.touch = [stage.pointer.raw.x, stage.pointer.raw.y, stage.pointer.active];
  b.fire("window", "touchend", { touches: [] });
  out.lifted = [stage.pointer.raw.x, stage.pointer.raw.y, stage.pointer.active];
  b.fire("window", "pointermove", { clientX: 5000, clientY: 250 });
  out.outside = [stage.pointer.raw.x, stage.pointer.inside];
  stage.setPointer(0.5, -0.25);
  out.setPointer = [stage.pointer.raw.x, stage.pointer.raw.y];
  out.passive = b.listeners.filter((l) => /pointer|touch/.test(l.type)).every((l) => l.passive);
  out.pointerTargets = [...new Set(b.listeners.filter((l) => /pointer|touch/.test(l.type)).map((l) => l.name))].sort();
  stage.setProgress(5); out.progress = [stage.progress];
  stage.setProgress(-1); out.progress.push(stage.progress);
  stage.setProgress(0.4); stage.setProgress(NaN); stage.setProgress("x"); out.progress.push(stage.progress);
  b.step(); b.step(2000);
  out.progressEased = round(stage.progressEased);
  stage.setQuality("low");
  out.low = [stage.quality.name, stage.quality.value, stage.quality.pick(1, 2, 3), stage.size.dpr, log.quality];
  stage.setQuality("medium");
  out.medium = [stage.quality.name, stage.quality.value, stage.quality.pick(1, 2, 3), stage.size.dpr];
  out.view = stage.viewSize(5);
  const kept = new THREE.Mesh("kept"), dropped = new THREE.Mesh("dropped");
  stage.scene.add(kept); stage.scene.add(dropped);
  stage.dispose(dropped);
  out.dispose = [THREE.calls.disposed.slice(), stage.scene.children.length];
  const handle = stage.handle({ setData: () => "data" });
  out.handle = [Object.keys(handle).sort(), handle.setData(), handle.stage === stage];
  out.mounted = [b.listeners.length > 10, b.observers.filter((o) => o.on).map((o) => o.kind).sort()];
  stage.destroy(); stage.destroy();
  out.destroyed = { listeners: b.listeners.length, observers: b.active(), waiting: b.frames.size,
                    canvases: b.container.children.length, attr: attr(), position: b.container.style.position,
                    rendererDisposed: THREE.calls.dispose, contextGivenBack: THREE.calls.contextLoss,
                    freed: THREE.calls.disposed.slice(3), destroyCalls: log.destroyed, running: stage.running };
  const frames = log.frames.length, renders = THREE.calls.render;
  b.see(true); b.resize(900, 300); b.theme({ "--color-bg": "#000000" });
  stage.resume(); stage.invalidate(); stage.setProgress(1); stage.setPointer(0, 0); stage.setQuality("high");
  out.afterDestroy = [b.step(), log.frames.length - frames, THREE.calls.render - renders, b.frames.size,
                      typeof stage.onFrame(() => {})];
  const second = createStage(b.container, { quality: "medium" });
  b.see(true); b.step();
  out.second = [b.container.children.length, second.clock.frame, attr()];
  const third = createStage(b.container, {});                 // on top of a live one: the old one goes first
  out.replaced = [b.container.children.length, second.running, b.active()];
  third.destroy();
  const box = (top, height) => ({ getBoundingClientRect: () => ({ top, height, bottom: top + height }) });
  out.sameHelper = third.progressOf === progressOf;
  out.cover = [900, 300, -300, 2000].map((top) => progressOf(box(top, 300)));
  out.contain = [[0, 1800], [-450, 1800], [-900, 1800], [600, 300], [0, 300]]
    .map(([top, height]) => progressOf(box(top, height), "contain"));
}

if (mode === "reduced") {
  const stage = createStage(b.container, { stillTime: 5 });
  const log = follow(stage);
  b.see(true);
  out.first = { ran: b.step(), renders: THREE.calls.render, time: stage.clock.time, delta: stage.clock.delta,
                waiting: b.frames.size, running: stage.running, still: stage.still, attr: attr() };
  out.idle = [b.step(), b.step(), THREE.calls.render];
  b.fire("window", "pointermove", { clientX: 500, clientY: 50 });
  stage.setProgress(0.5); stage.pause(); stage.resume();
  out.noRedraw = [b.frames.size, THREE.calls.render, log.pointer];
  b.resize(600, 300); b.step();
  out.afterResize = [THREE.calls.render, stage.camera.aspect, b.frames.size];
  b.theme({ "--color-bg": "#f6f7f5" }); b.step();
  out.afterTheme = [THREE.calls.render, stage.tokens.dark];
  stage.invalidate(); stage.invalidate(); stage.invalidate(); b.step(); b.step();
  out.afterInvalidate = [THREE.calls.render, stage.progressEased];
  b.reduced = false; b.fire("media (prefers-reduced-motion: reduce)", "change");
  b.step(); b.step(); b.step();
  out.switchedOff = [stage.running, stage.still, round(stage.clock.time)];
  b.reduced = true; b.fire("media (prefers-reduced-motion: reduce)", "change");
  const before = THREE.calls.render;
  b.step(); b.step();
  out.switchedOn = [stage.running, stage.still, stage.clock.time, THREE.calls.render - before, b.frames.size];
  stage.destroy();
  out.destroyed = [b.listeners.length, b.active()];
}

if (mode === "pausedfirst") { // paused before anything was drawn: one still, then it runs on from there
  const stage = createStage(b.container, { stillTime: 5 });
  stage.pause("motion-toggle");
  b.see(true);
  out.first = [b.step(), THREE.calls.render, stage.clock.time, stage.running, b.frames.size, attr()];
  stage.resume("motion-toggle");
  b.step(); b.step();
  out.resumed = [stage.running, round(stage.clock.time), THREE.calls.render];
  const still = createStage(b.container, { still: true, stillTime: 2 });
  b.see(true); b.step(); b.step();
  out.option = [still.clock.time, still.running, still.clock.frame];
}

if (mode === "nowebgl") {
  const stage = createStage(b.container, {});
  out.failed = stage.failed;
  out.attr = attr();
  out.touched = [b.container.children.length, b.listeners.length, b.observers.length, b.frames.size, stage.renderer];
  out.threw = [];
  const ran = (name) => () => { out.threw.push(name + " called back"); };
  const calls = { onFrame: [ran("onFrame")], onResize: [ran("onResize")], onTokens: [ran("onTokens")],
                  onQuality: [ran("onQuality")], onPointer: [ran("onPointer")], onDestroy: [() => {}],
                  setProgress: [0.5], setPointer: [0.1, 0.1], setQuality: ["low"], refreshTokens: [],
                  invalidate: [], pause: ["x"], resume: ["x"], viewSize: [], dispose: [null], handle: [] };
  for (const [name, args] of Object.entries(calls)) {
    try { stage[name](...args); } catch (error) { out.threw.push(name + ": " + error.message); }
  }
  out.every = Object.keys(calls).sort();
  const handle = stage.handle();
  for (const name of ["setProgress", "setData", "setPointer", "pause", "resume"]) {
    try { handle[name](0.2, 0.2); } catch (error) { out.threw.push("handle." + name + ": " + error.message); }
  }
  out.quiet = [b.listeners.length, b.frames.size, b.step()];
  handle.destroy(); handle.destroy();
  out.attrAfterDestroy = attr();
  const nowhere = createStage(null, {});                      // a selector that matched nothing
  nowhere.onFrame(ran("onFrame")); nowhere.setProgress(1); nowhere.pause(); nowhere.invalidate();
  nowhere.handle().destroy();
  out.nowhere = [nowhere.failed, createStage(undefined).failed, createStage("#hero").failed, b.frames.size];
}

if (mode === "broken") {
  const stage = createStage(b.container, { quality: "high" });
  b.see(true); b.step();
  let prevented = false;
  b.fire("canvas", "webglcontextlost", { preventDefault: () => { prevented = true; } });
  out.lost = [stage.failed, attr(), prevented, stage.running, b.frames.size, stage.canvas.style.opacity];
  b.fire("canvas", "webglcontextrestored", {});
  b.step(); b.step();
  out.restored = [stage.failed, attr(), stage.running, stage.canvas.style.opacity];
  stage.onFrame(() => { throw new Error("boom"); });
  b.step();
  out.threw = [stage.failed, attr(), stage.running, b.frames.size, logged];
  stage.destroy();
  out.attrAfterDestroy = attr();
}

if (mode === "compiling") { // a renderer that compiles ahead: the shaders get tasks of their own, then the first frame
  const count = (name) => function () { THREE.calls[name] = (THREE.calls[name] || 0) + 1; };
  THREE.WebGLRenderer.prototype.compile = count("compiled");
  THREE.WebGLRenderer.prototype.getContext = () => ({ flush: count("flushed") });
  const stage = createStage(b.container, { quality: "high", fade: 0 });
  b.see(true);
  out.first = [b.step(), THREE.calls.render, THREE.calls.compiled, THREE.calls.flushed, attr(), b.idle.length];
  b.runIdle(); b.step();
  out.after = [THREE.calls.render, attr(), THREE.calls.compiled];
  stage.destroy();
  // With KHR_parallel_shader_compile: compileAsync, and the first frame once it has settled.
  THREE.WebGLRenderer.prototype.compileAsync = function () { count("compiledAsync")(); return Promise.resolve(); };
  Object.defineProperty(THREE.WebGLRenderer.prototype, "extensions",
    { configurable: true, get: () => ({ has: (name) => name === "KHR_parallel_shader_compile" }) });
  const before = THREE.calls.render;
  const parallel = createStage(b.container, { quality: "high", fade: 0 });
  b.see(true); b.step();
  out.async = [THREE.calls.render - before, THREE.calls.compiledAsync, attr()];
  await new Promise((resolve) => setImmediate(resolve));
  b.step();
  out.asyncAfter = [THREE.calls.render - before, attr()];
  parallel.destroy();
}

if (mode === "auto") { // a strong device by its numbers; then frames 16, 30 and 60 ms apart
  out.runs = {};
  for (const [name, gap, count] of [["fast", 16, 250], ["slow", 30, 250], ["verySlow", 60, 60]]) {
    const stage = createStage(b.container, { quality: "auto" });
    out.runs[name] = [];
    stage.onQuality((quality) => out.runs[name].push(quality.name + "@" + stage.clock.frame));
    b.see(true);
    for (let i = 0; i < count; i++) b.step(gap);
    stage.destroy();
  }
  out.guess = [4, 2].map((cores) => {
    navigator.hardwareConcurrency = cores;
    const stage = createStage(b.container, { quality: "auto" });
    stage.destroy();
    return stage.quality.name;
  });
}
console.log(JSON.stringify(out));
"""

# The same for lazy.js. Every mode is a fresh Node process, because lazy.js remembers the motion choice.
LAZY_RUN = r"""
import { makeBrowser } from "./browser.mjs";
const mode = process.argv[2];
const b = makeBrowser({ saveData: mode === "savedata", idle: mode !== "noidle", storage: mode !== "nostorage",
                       webgl: mode !== "nowebgl" });
if (mode === "remembered") b.store.set("forge-scenes-motion", "paused");
const logged = [];
console.error = (...args) => logged.push(String(args[0]));
const { lazyScene, motionToggle, motionPaused, setMotionPaused } = await import("./scenes/lazy.js");
const out = {}, made = [];
const settle = () => new Promise((resolve) => setImmediate(resolve)); // let the promises in lazy.js run
const attr = () => b.container.getAttribute("data-scene");
const fakeScene = () => {
  const scene = { calls: [], destroyed: 0, destroy() { scene.destroyed += 1; } };
  for (const name of ["setProgress", "setData", "setPointer", "pause", "resume"]) {
    scene[name] = (...args) => scene.calls.push([name, ...args]);
  }
  made.push(scene);
  return scene;
};
let loads = 0, mountedWith = null;
const loader = () => {
  loads += 1;
  return Promise.resolve({ mount(container, options) {
    mountedWith = [container === b.container, options];
    return fakeScene();
  } });
};
// Near, and every quiet moment it asks for: the one before the load, the one between module and mount.
const near = async () => { b.see(true); for (let i = 0; i < 3; i++) { b.runIdle(); await settle(); } };
const makeButton = () => {
  const button = { attrs: {}, fns: [], setAttribute(key, value) { button.attrs[key] = value; },
                   addEventListener(type, fn) { button.fns.push(fn); },
                   removeEventListener(type, fn) { button.fns = button.fns.filter((item) => item !== fn); },
                   click() { for (const fn of button.fns.slice()) fn(); } };
  return button;
};

if (mode === "normal") {
  const handle = lazyScene(b.container, loader, { quality: "low", lazy: { margin: "25%", timeout: 500 } });
  handle.setProgress(0.2); handle.setData([1]); handle.setProgress(0.7);
  handle.pause("page"); handle.pause("gone"); handle.resume("gone");
  await settle();
  out.waiting = [handle.state, loads, b.idle.length, handle.scene];
  b.see(false); await settle();
  out.notNear = [loads, b.idle.length];
  b.see(true); await settle();
  out.nearNotIdle = [loads, b.idle.length, handle.state, b.active("intersection")];
  b.runIdle(); await settle();
  out.breathing = [loads, handle.state, b.idle.length, made.length];   // loaded, and mount() waits for a quiet moment
  b.runIdle(); await settle();
  const scene = made[0];
  out.loaded = { loads, state: handle.state, scene: handle.scene === scene, ready: (await handle.ready) === scene,
                 mountedWith, calls: scene.calls.slice() };
  handle.setPointer(0.1, 0.2); handle.pause(); handle.resume(); handle.load();
  out.forwarded = [scene.calls.slice(3), loads];
  handle.destroy(); handle.destroy(); handle.setProgress(1);
  out.destroyed = [handle.state, scene.destroyed, scene.calls.length];
  const early = lazyScene(b.container, loader, {});
  early.destroy();
  await near();
  out.destroyedEarly = [loads, early.state, await early.ready, b.active("intersection")];
  let release = null;
  const slow = lazyScene(b.container, () => new Promise((resolve) => { release = resolve; }), {});
  await near();
  slow.destroy();
  release({ mount: () => fakeScene() });
  await settle();
  out.destroyedWhileLoading = [slow.state, made.length, await slow.ready];
}

if (mode === "savedata") {
  const handle = lazyScene(b.container, loader, {});
  await near();
  out.kept = [handle.state, loads, b.observers.length, b.idle.length];
  handle.setProgress(0.3);
  const loading = handle.load();
  await settle(); b.runIdle();
  const scene = await loading;
  out.forced = [handle.state, loads, scene.calls];
}

if (mode === "noidle") { // no requestIdleCallback (Safari): a short timer instead
  const handle = lazyScene(b.container, loader, {});
  b.see(true); await settle();
  out.timer = [loads, b.timers.map((timer) => timer.ms)];
  b.timers[0].fn(); await settle();
  out.between = [loads, handle.state, b.timers.map((timer) => timer.ms)];   // the pause before mount(): a task
  b.timers[1].fn(); await settle();
  out.after = [loads, handle.state];
}

if (mode === "nowebgl") { // no WebGL 2: three is never fetched, the poster stays, quietly
  const handle = lazyScene(b.container, loader, {});
  await near();
  out.noWebgl = [handle.state, loads, attr(), await handle.ready, /WebGL/.test(String(handle.error)), logged.length];
  const plain = lazyScene(b.container, loader, { lazy: { webgl: false } });   // a loader that needs no WebGL
  await near();
  out.optedOut = [plain.state, loads];
}

if (mode === "runtime") { // a motion runtime set "on" before the kit came: the kit keeps it
  const html = document.documentElement, button = makeButton();
  html.setAttribute("data-motion", "on");
  const handle = lazyScene(b.container, loader, {});
  motionToggle(button);
  await near();
  out.kept = html.getAttribute("data-motion");
  button.click();
  out.paused = html.getAttribute("data-motion");
  button.click();
  out.back = html.getAttribute("data-motion");
  html.setAttribute("data-motion", "reveal");   // a value of the page's own is left alone
  setMotionPaused(false);
  out.other = html.getAttribute("data-motion");
  handle.destroy();
}

if (mode === "failing") {
  const handle = lazyScene(b.container, () => Promise.reject(new Error("offline")), {});
  await near();
  out.rejected = [handle.state, attr(), await handle.ready, String(handle.error), logged.length];
  handle.destroy();
  out.attrAfterDestroy = attr();
  const empty = lazyScene(b.container, () => Promise.resolve({}), {});
  await near();
  out.noMount = [empty.state, String(empty.error)];
  const thrower = lazyScene(b.container, () => Promise.resolve({ mount() { throw new Error("mount broke"); } }), {});
  await near();
  out.mountThrew = [thrower.state, attr(), await thrower.ready];
  let asked = 0;
  const nowhere = lazyScene(null, () => { asked += 1; return Promise.resolve({}); }, {}); // no such element
  nowhere.setProgress(1); nowhere.pause(); nowhere.load();
  await near();
  out.nowhere = [nowhere.state, await nowhere.ready, asked, typeof motionToggle(null).destroy];
}

if (mode === "toggle" || mode === "nostorage" || mode === "remembered") {
  const first = makeButton(), second = makeButton(), html = document.documentElement;
  const pressed = () => [first.attrs["aria-pressed"], second.attrs["aria-pressed"]];
  const stored = () => b.store.get("forge-scenes-motion") || null;
  out.start = motionPaused();
  const handle = lazyScene(b.container, loader, {});
  await near();
  const scene = made[0];
  out.mounted = scene.calls.slice();
  const toggle = motionToggle(first);
  motionToggle(second);
  out.wired = [pressed(), html.getAttribute("data-motion")];
  scene.calls.length = 0;
  first.click();
  out.clicked = [pressed(), html.getAttribute("data-motion"), stored(), scene.calls.slice(), motionPaused()];
  const later = lazyScene(b.container, loader, {});
  await near();
  out.mountedLater = made[1].calls.slice();
  scene.calls.length = 0;
  second.click();
  out.clickedAgain = [pressed(), html.getAttribute("data-motion"), stored(), scene.calls.slice(),
                      made[1].calls.slice(-1)];
  toggle.destroy();
  first.click();
  out.unwired = [first.fns.length, motionPaused() === out.clickedAgain[0][0].startsWith("t")];
  handle.destroy(); later.destroy();
  scene.calls.length = 0;
  setMotionPaused(true); setMotionPaused(false);
  out.destroyedHandlesLeftAlone = scene.calls.length;
}
console.log(JSON.stringify(out));
"""

# depth.js in an app whose main area scrolls inside a fixed frame. An element's own scroll event
# does not bubble: only capture listeners on the window and the document hear it. The page's own
# scroll is fired at the document and bubbles to the window.
DEPTH_RUN = r"""
import { makeBrowser } from "./browser.mjs";
const b = makeBrowser();
window.requestAnimationFrame = requestAnimationFrame;
window.cancelAnimationFrame = cancelAnimationFrame;
const computed = getComputedStyle;
globalThis.getComputedStyle = (node) => (node.box ? { position: "static", perspective: "1500px", perspectiveOrigin: "300px 0px" }
                                                  : computed(node));
const has = (node, selector) => selector.split(",").some((one) => /^\[[\w-]+\]$/.test(one.trim())
  && one.trim().slice(1, -1) in (node.attrs || {}));
const node = (attrs = {}, children = [], box = { top: 0, height: 300 }) => {
  const n = {
    nodeType: 1, attrs: { ...attrs }, children: [], parentElement: null, box,
    offsetWidth: 600, offsetHeight: box.height, offsetLeft: 0, offsetTop: 0, offsetParent: null,
    clientWidth: 600, clientLeft: 0, clientTop: 0,
    style: { props: {}, getPropertyValue(p) { return this.props[p] || ""; }, setProperty(p, v) { this.props[p] = String(v); },
             removeProperty(p) { delete this.props[p]; } },
    getAttribute: (key) => (key in n.attrs ? n.attrs[key] : null),
    setAttribute: (key, value) => { n.attrs[key] = String(value); },
    removeAttribute: (key) => { delete n.attrs[key]; },
    hasAttribute: (key) => key in n.attrs,
    toggleAttribute: (key, on) => { if (on) n.attrs[key] = ""; else delete n.attrs[key]; return Boolean(on); },
    matches: (selector) => has(n, selector),
    closest: (selector) => { for (let e = n; e; e = e.parentElement) if (has(e, selector)) return e; return null; },
    querySelectorAll: (selector) => {
      const found = [], walk = (e) => { for (const c of e.children || []) { if (has(c, selector)) found.push(c); walk(c); } };
      walk(n);
      return found;
    },
    appendChild: (child) => { n.children.push(child); child.parentElement = n; child.parent = n; return child; },
    getBoundingClientRect: () => ({ left: 0, width: 600, right: 600, top: n.box.top, height: n.box.height,
                                    bottom: n.box.top + n.box.height }),
  };
  for (const child of children) n.appendChild(child);
  return n;
};
const panels = [node(), node(), node()];
const stack = node({ "data-depth": "stack" }, panels, { top: 700, height: 300 });
const card = node({ "data-depth": "tilt" }, [], { top: 700, height: 200 });
const { mount } = await import("./scenes/depth.js");
const depth = mount(node({}, [card, stack]), { tilt: 7 });
b.observers.find((o) => o.kind === "intersection" && o.on)
  .callback([card, stack].map((target) => ({ target, isIntersecting: true })));
const settle = () => { let frames = 0; while (b.step(16) && frames < 3000) frames += 1; return frames; };
const drawn = () => [panels[1].style.props.transform || "", card.style.props.transform || ""];
const scroll = (where) => {
  const heard = b.listeners.filter((l) => l.type === "scroll" && (l.name === "window" || l.name === "document")
    && (where === "page" || l.capture));
  for (const l of heard) l.fn({});
  return heard.length;
};
const out = {};
out.first = settle();
out.resting = [b.frames.size, ...drawn()];
stack.box.top = 300; card.box.top = 300;                 // the panel scrolled 400 px: both rose on the screen
out.panel = [scroll("panel"), b.frames.size];
out.second = settle();
out.after = [b.frames.size, ...drawn()];
stack.box.top = 900;                                     // the page itself scrolled back
out.page = [scroll("page"), b.frames.size];
settle();
depth.destroy();
out.left = b.listeners.filter((l) => l.type === "scroll").length;
console.log(JSON.stringify(out));
"""

# contour.js's outline work, sliced out of the file with the constants it needs (see ContourTests).
CONTOUR_HELPERS_RUN = r"""
const { calmBox, readOutline, routeOf, openBox, CALM, NARROW, BREAK, ROUTE } = await import("./contour.helpers.mjs");
const square = (lon, lat, d) => [[lon, lat], [lon + d, lat], [lon + d, lat + d], [lon, lat + d], [lon, lat]];
const counts = (shape) => [shape.areas.length, shape.lines.length];
const round = (list) => list.map((v) => Math.round(v * 1000) / 1000);
const out = {};
const lake = readOutline({ type: "Polygon", coordinates: [square(5, 52, 0.1)] });
out.lake = [...counts(lake), ...round(lake.size)];
out.island = counts(readOutline({ type: "Feature", geometry: { type: "Polygon",
  coordinates: [square(5, 52, 0.1), square(5.03, 52.03, 0.02)] } }));
out.collection = counts(readOutline({ type: "FeatureCollection", features: [
  { type: "Feature", geometry: { type: "MultiPolygon", coordinates: [[square(0, 0, 1)], [square(2, 0, 1)]] } },
  { type: "Feature", geometry: { type: "LineString", coordinates: [[0, 2], [3, 2]] } }] }));
out.points = [counts(readOutline([[0, 0], [1, 0], [1, 1]])), counts(readOutline([[0, 0], [1, 0], [1, 1], [0, 0]])),
              counts(readOutline([[[0, 0], [2, 0]], [[0, 1], [1, 1], [1, 2], [0, 1]]]))];
out.nothing = [readOutline(null), readOutline([]), readOutline({ type: "Point", coordinates: [5, 52] }),
               readOutline([[0, 0], [0, 0]])];
const wiggle = (from, n) => Array.from({ length: n }, (_, i) => [from + i / n, Math.sin(i / 7) * 0.2]);
const trail = routeOf([wiggle(0, 1000), wiggle(2, 1000)]);
out.trail = [trail.points.length, ROUTE, trail.points.filter((p) => p === BREAK).length,
             trail.middle.length === 2 && trail.middle.every(Number.isFinite)];
out.open = [round(openBox(CALM.left, 1.6, 1)), round(openBox(CALM.top, 1.6, 4)), round(openBox(null, 1, 1))];
out.calm = [calmBox({ calm: "none" }, 1.6), calmBox({ calm: "left" }, 0.5), calmBox({ calm: "wobbly" }, 1.6),
            calmBox({ calm: "none", calmBox: [0.9, 0.6, 0.1, 0.95] }, 0.5), calmBox({ calm: "left", calmBox: [1, 2] }, 1.6)];
out.named = [CALM.left, NARROW];
console.log(JSON.stringify(out));
"""

# contour.js mounted flat with a trail: label places for the page, and the phone's own calm.
CONTOUR_RUN = r"""
import { makeBrowser } from "./browser.mjs";
const b = makeBrowser();
const { mount } = await import("./scenes/contour.js");
const told = [];
const trail = [[[0, 0], [1, 0.2], [2, 0.1], [3, 0.6]], [[3, 1], [4, 1.4]]];   // two lines, y up
const chart = mount(b.container, { outline: trail, calm: "none", labels: ["middle", [0, 0], "nowhere"],
  onLabels: (points) => { told.push(points); throw new Error("a page error"); },
  phone: { below: 600, calmBox: [0.05, 0.6, 0.95, 0.95] } });
const errors = [];
console.error = (...args) => errors.push(String(args[0]));
const u = chart.stage.scene.children[0].material.uniforms;
const calm = () => [u.uCalmBox.value.x, u.uCalmBox.value.y, u.uCalmBox.value.z, u.uCalmBox.value.w, u.uCalm.value.x];
const out = { wide: calm(), route: u.uRouteCount.value, defines: Object.keys(chart.stage.scene.children[0].material.defines).sort() };
b.see(true); b.step(); b.step(); b.step();
out.labels = told.map((points) => points.map((p) => Object.keys(p).sort().join(",")));
out.first = told[0];
out.quiet = told.length;                     // nothing moved after the first frame: no call
out.errors = errors.length;
b.resize(390, 844); b.step();
out.phone = calm();
out.afterResize = told.length;
out.data = (chart.setData([0.2, 0.9]), u.uRidgeHeight.value);   // the chart is the outline's
chart.destroy();
console.log(JSON.stringify(out));
"""

# field.js: where the phone option puts the form and its calm, and what streak changes.
FIELD_RUN = r"""
import { makeBrowser } from "./browser.mjs";
const b = makeBrowser();
const { mount } = await import("./scenes/field.js");
const round = (v) => Math.round(v * 1000) / 1000;
const look = (scene) => {
  const group = scene.stage.scene.children[0], points = group.children[0], u = points.material.uniforms;
  return { calm: [u.uCalm.value.x, u.uCalm.value.y, u.uCalm.value.z, u.uCalm.value.w].map(round), amount: u.uCalmAmount.value,
           position: [round(group.position.x), round(group.position.y)], scale: round(group.scale.x),
           width: round(scene.stage.viewSize(7.2).width), height: round(scene.stage.viewSize(7.2).height),
           streak: [u.uStreak.value, points.material.defines.STREAK || 0], count: points.geometry.drawRange.count };
};
const out = {};
b.resize(390, 844);
let field = mount(b.container, { phone: { below: 600, at: [0.5, 0.3], size: 0.8, calmBox: [0.1, 0.55, 0.9, 0.95] } });
out.phone = look(field);
b.resize(1440, 800);
out.wide = look(field);
field.destroy();
field = mount(b.container, { streak: 1 });
out.streak = look(field);
field.destroy();
field = mount(b.container, {});
out.round = look(field);
field.destroy();
console.log(JSON.stringify(out));
"""


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def scene_files():
    """Every .js file in forge-design/scenes, sorted."""
    return sorted(name for name in os.listdir(SCENES) if name.endswith(".js"))


def code_of(name):
    """A file's code without its comments. The GLSL inside strings loses its comments too, which is fine."""
    return COMMENT.sub("", read(os.path.join(SCENES, name)))


def imports_in(code):
    """(what the code imports, problems): every `import ... from`, `export ... from` and import()."""
    found, wrong = STATIC_IMPORT.findall(code), []
    for match in DYNAMIC_IMPORT.finditer(code):
        if match.group(1) is None:
            wrong.append("has a dynamic import that does not name its file as plain text")
        else:
            found.append(match.group(2))
    if re.search(r"\brequire\s*\(", code):
        wrong.append("uses require(): the kit is ES modules only")
    return found, wrong


def problems(name, source, neighbours):
    """What is wrong with one file of the kit, in plain words. An empty list: it keeps the rules.

    - It imports nothing but "three" and files next to it (no three/addons, no other package).
    - It names no other host, also not in a comment.
    - Only stage.js asks for frames. A scene draws in stage.onFrame(), so it stops off-screen, in a
      hidden tab, when paused and for reduced motion. A file with no WebGL (it imports neither three
      nor the stage) cannot use the stage: if it asks for frames, it has to do that stopping itself.
    - A file that exports mount() also takes the scene down, and one that makes a stage looks at
      stage.failed, so a browser without WebGL gets the poster and not an exception."""
    code = COMMENT.sub("", source)
    found, wrong = imports_in(code)
    for what in found:
        neighbour = re.fullmatch(r"\./([\w.-]+\.js)", what)
        if what != "three" and not (neighbour and neighbour.group(1) in neighbours):
            wrong.append('imports "%s": only "three" and ./<a file in scenes/>.js are allowed' % what)
    if re.search(r"(?i)https?://", source):
        wrong.append("names another host (http:// or https://)")
    if name != "stage.js" and "requestAnimationFrame" in code:
        if {"three", "./stage.js"} & set(found):
            wrong.append("calls requestAnimationFrame: use stage.onFrame(fn) or stage.invalidate()")
        elif "prefers-reduced-motion" not in code or not SEES_ITSELF_OUT.search(code):
            wrong.append("has a frame loop of its own that does not stop for reduced motion and when unseen")
    if MOUNTS.search(code) and not re.search(r"\bdestroy\b|\.handle\(", code):  # handle() brings destroy()
        wrong.append("exports mount() but never destroys")
    if name != "stage.js" and "createStage(" in code and not re.search(r"\.failed\b", code):
        wrong.append("makes a stage and never looks at stage.failed")
    return wrong


def header_of(name):
    """The comment at the top of a file: what a developer reads instead of the code."""
    source = read(os.path.join(SCENES, name))
    return source[:source.index("*/")]


def contour_helpers():
    """contour.js's own outline helpers as a module of their own: its constants (CALM up to the
    shaders) and its functions (num up to mount), which need neither three nor a browser."""
    source = read(os.path.join(SCENES, "contour.js"))
    part = (source[source.index("const CALM = {"):source.index("// The rectangle covers the screen")]
            + source[source.index("const num ="):source.index("export function mount")])
    return part + "\nexport { calmBox, readOutline, routeOf, openBox, CALM, NARROW, BREAK, ROUTE };\n"


class KitTests(unittest.TestCase):
    """What holds for every file in the folder, the ones still to come included."""

    def test_the_runtime_is_there(self):
        self.assertTrue({"stage.js", "glsl.js", "lazy.js"} <= set(scene_files()))

    def test_every_file_keeps_the_rules(self):
        for name in scene_files():
            with self.subTest(file=name):
                self.assertEqual(problems(name, read(os.path.join(SCENES, name)), scene_files()), [])

    def test_the_runtime_imports_what_it_should(self):
        self.assertEqual(imports_in(code_of("stage.js")), (["three"], []))
        self.assertEqual(imports_in(code_of("glsl.js")), ([], []))
        self.assertEqual(imports_in(code_of("lazy.js")), ([], []), "or three would load with the page")
        self.assertIn("requestAnimationFrame(", code_of("stage.js"))
        self.assertIn("cancelAnimationFrame(", code_of("stage.js"))

    def test_motioncheck_finds_nothing(self):
        """The kit is copied into apps, and those are checked with motioncheck.py: it must pass itself."""
        report = motioncheck.scan_path(SCENES, "low")
        self.assertEqual(report["findings"], [])
        self.assertGreaterEqual(report["summary"]["files_checked"], len(scene_files()))


class HeaderTests(unittest.TestCase):
    """Scene authors work from the comment at the top, so it must name everything the code offers."""

    def test_stage_names_every_public_member(self):
        source = read(os.path.join(SCENES, "stage.js"))
        header = header_of("stage.js")
        exported = re.findall(r"(?m)^export (?:async )?function (\w+)", source)
        self.assertEqual(sorted(exported), ["createStage", "progressOf"])
        members = STAGE_MEMBER.findall(re.search(r"\n  const stage = \{\n(.*?)\n  \};\n", source, re.S).group(1))
        self.assertGreater(len(members), 25, "the stage object was not found as written")
        for name in exported + members:
            method = name in exported or re.search(r"\n    %s: \(|\n  function %s\(" % (name, name), source)
            with self.subTest(member=name):
                self.assertRegex(header, r"\b%s%s" % (name, r"\(" if method else r"\b"),
                                 "the comment at the top of stage.js does not name %s" % name)
        for name in ["onFrame", "onResize", "onTokens", "onQuality", "onPointer", "onDestroy", "setProgress",
                     "setPointer", "setQuality", "refreshTokens", "invalidate", "pause", "resume", "viewSize",
                     "dispose", "handle", "progressOf", "destroy", "renderer", "scene", "camera", "clock", "tokens",
                     "uniforms", "pointer", "size", "quality", "progress", "failed", "still", "running"]:
            self.assertIn(name, members, "stage.%s is gone: scenes are written against it" % name)
        for option in re.findall(r"(?m)^  (\w+):", source[source.index("const DEFAULTS"):source.index("const CAMERA")]):
            self.assertRegex(header, r"\b%s\b" % option, "option %s is not in the comment" % option)
        names = source[source.index("const TOKEN_NAMES"):source.index("const DEFAULTS")]
        for name in re.findall(r"(--color-[\w-]+)", names):
            self.assertIn(name, header)

    def test_stage_handles_what_it_promises(self):
        code = code_of("stage.js")
        self.assertRegex(code, r"matchMedia\(\"\(prefers-reduced-motion: reduce\)\"\)")  # on one line: motioncheck
        for part in ["prefers-color-scheme", "pointer: coarse", "ResizeObserver", "IntersectionObserver",
                     "MutationObserver", "visibilitychange", "devicePixelRatio", "hardwareConcurrency", "deviceMemory",
                     "webglcontextlost", "webglcontextrestored", "forceContextLoss", 'data-scene", "fallback"',
                     'data-scene", "live"', "SRGBColorSpace", "alpha: true", "passive: true", "getComputedStyle"]:
            self.assertIn(part, code)
        self.assertNotRegex(code, r"#[0-9a-fA-F]{6}\b", "colours come from the page, not from the stage")

    def test_lazy_names_what_it_offers(self):
        source, header = read(os.path.join(SCENES, "lazy.js")), header_of("lazy.js")
        exported = re.findall(r"(?m)^export (?:async )?function (\w+)", source)
        self.assertEqual(sorted(exported), ["lazyScene", "motionPaused", "motionToggle", "setMotionPaused"])
        handle = re.search(r"\n  const handle = \{\n(.*?)\n  \};\n", source, re.S).group(1)
        members = re.findall(r"(?m)^    (?:get )?(\w+)\s*[,:(]", handle)
        self.assertEqual(sorted(members), ["destroy", "error", "load", "pause", "ready", "resume", "scene", "setData",
                                           "setPointer", "setProgress", "state"])
        for name in exported + members + ["data-scene-poster", "aria-pressed", "data-motion", "lazy.margin",
                                          "lazy.timeout", "background"]:
            self.assertIn(name, header)
        for state in re.findall(r'state = "([\w-]+)"', source):
            self.assertIn('"%s"' % state, header)
        code = code_of("lazy.js")
        for part in ["requestIdleCallback", "setTimeout", "IntersectionObserver", "saveData", "localStorage",
                     "aria-pressed"]:
            self.assertIn(part, code)
        self.assertNotIn("three", code, "lazy.js must not mention three: the loader brings it")
        storage = [m.start() for m in re.finditer(r"localStorage\.", code)]
        self.assertEqual(len(storage), 3)
        for at in storage:  # each use sits in a try block: private mode and blocked storage throw
            self.assertRegex(code[max(0, at - 120):at], r"try \{")

    def test_glsl_names_every_piece_and_where_it_comes_from(self):
        source, header = read(os.path.join(SCENES, "glsl.js")), header_of("glsl.js")
        pieces = re.findall(r"(?m)^export const (\w+) =", source)
        self.assertTrue({"simplex2D", "simplex3D", "curl", "fbm", "palette", "grain", "fog", "pointSprite", "line",
                         "stageUniforms"} <= set(pieces))
        self.assertEqual(re.findall(r"(?m)^export (?!const )", source), [], "only named string exports")
        for name in pieces:
            self.assertRegex(header, r"(?m)^ \*   %s\b" % name, "glsl.js does not describe %s at the top" % name)
        for word in ["Perlin", "Gustavson", "Bridson", "Ottosson", "public domain", "written for this kit"]:
            self.assertIn(word, header)
        for function in ["snoise", "snoiseGrad", "curlNoise", "fbm", "paletteMix", "grain", "dither", "fogLinear",
                         "softDot", "pointPixels", "lineAlpha", "isoLines", "aastep", "mixOklab"]:
            self.assertRegex(source[len(header):], r"\b%s\(" % function)
            self.assertIn(function, header)
        stage = code_of("stage.js")  # the stage's own uniforms and one per colour: all declared for shaders
        uniforms = re.findall(r"\b(u[A-Z]\w+): \{ value", stage)
        uniforms += ["u" + name[0].upper() + name[1:] for name in re.findall(r"(?m)^  (\w+): \"--color", stage)]
        self.assertGreaterEqual(len(uniforms), 13)
        for uniform in uniforms:
            self.assertTrue(re.search(r"uniform \w+ %s;" % uniform, source), "stageUniforms lacks " + uniform)
            self.assertIn(uniform, header_of("stage.js"))


class Sandbox(unittest.TestCase):
    """A folder with the scenes, the stand-in three and the make-believe browser, made once per class."""

    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        if not cls.node:
            return
        cls.folder = tempfile.mkdtemp()
        cls.addClassCleanup(shutil.rmtree, cls.folder, ignore_errors=True)
        shutil.copytree(SCENES, os.path.join(cls.folder, "scenes"))
        three = os.path.join(cls.folder, "node_modules", "three")
        os.makedirs(three)
        files = {"package.json": '{"type": "module"}', "browser.mjs": BROWSER, "stage.run.mjs": STAGE_RUN,
                 "lazy.run.mjs": LAZY_RUN, "depth.run.mjs": DEPTH_RUN, "contour.run.mjs": CONTOUR_RUN,
                 "field.run.mjs": FIELD_RUN, "contour.helpers.run.mjs": CONTOUR_HELPERS_RUN,
                 "contour.helpers.mjs": contour_helpers(), os.path.join(three, "index.js"): THREE,
                 os.path.join(three, "package.json"): '{"name": "three", "type": "module", "main": "index.js"}'}
        for name, text in files.items():
            with open(os.path.join(cls.folder, name), "w", encoding="utf-8") as handle:
                handle.write(text)

    def run_node(self, *args):
        if not self.node:
            self.skipTest("node is not installed")
        done = subprocess.run([self.node] + list(args), cwd=self.folder, timeout=60, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def play(self, script, mode):
        return json.loads(self.run_node(script, mode))


class ModuleTests(Sandbox):
    def test_every_file_parses_as_a_module(self):
        for name in scene_files():
            with self.subTest(file=name):
                self.run_node("--check", os.path.join("scenes", name))

    def test_glsl_pieces_are_guarded_strings(self):
        show = ("const count = (text, pattern) => (String(text).match(pattern) || []).length;"
                "import('./scenes/glsl.js').then((m) => console.log(JSON.stringify(Object.entries(m).map(([name, text])"
                " => [name, typeof text, count(text, /#ifndef FORGE_/g),"
                " count(text, /#endif/g) - count(text, /#ifndef (?!FORGE_)/g),"
                " /\\b(flat|distance|sample|input|output|smooth)\\s*[=;,)]/.test(text)]))))")
        pieces = json.loads(self.run_node("--input-type=module", "-e", show))
        self.assertGreaterEqual(len(pieces), 12)
        for name, kind, guards, ends, reserved in pieces:
            with self.subTest(piece=name):
                self.assertEqual(kind, "string")
                self.assertGreaterEqual(guards, 1, "each piece is wrapped in #ifndef FORGE_..., so twice does no harm")
                self.assertEqual(guards, ends, "#ifndef and #endif do not pair up")
                self.assertFalse(reserved, "a GLSL word used as a name (flat, distance, sample ...)")


class StageTests(Sandbox):
    def test_draws_sizes_pauses_and_follows_the_page(self):
        out = self.play("stage.run.mjs", "moving")
        start = out["start"]
        self.assertEqual((start["canvases"], start["position"], start["failed"], start["attr"]),
                         (1, "relative", False, None))
        self.assertEqual((start["size"], start["buffer"], start["aspect"]),
                         ([800, 400, 2], [1600, 800], 2))  # a 3x screen: capped at 2
        self.assertEqual(start["calledAtOnce"], [1, 1, 1])  # onResize, onTokens, onQuality call back at once
        self.assertEqual((start["dark"], start["additive"]), (True, True))
        self.assertEqual(start["css"], {"bg": "#070b0e", "text": "#e9f0ee", "accent": "#3fd0bb",  # as given ...
                                        "accent2": "rgb(63 208 187)", "surface": "rgb(7 11 14)",  # ... or stand-ins
                                        "muted": "rgb(143 148 148)", "border": "rgb(52 57 59)"})
        self.assertEqual((start["running"], start["waiting"]), (False, 0))  # nothing until it is seen
        self.assertEqual(out["seen"], [True, 1])
        self.assertEqual(out["threeFrames"], {"renders": 3, "frame": 3, "time": 0.032, "firstDelta": 0, "attr": "live",
                                              "opacity": "1", "uTime": 0.032})
        self.assertEqual(out["longGap"], [0.1, 0.132])  # five seconds away count as a tenth
        self.assertEqual(out["paused"], [False, 0, False, 0.132])  # no frame waiting, none ran, time stood still
        self.assertEqual(out["resumed"], [True, 0, 0.132])  # the first frame after a pause has no delta
        self.assertEqual(out["reasons"], [False, True])
        self.assertEqual(out["fights"], [False, False, True])
        self.assertEqual((out["offScreen"], out["hidden"], out["back"]), ([False, 0], [False, 0], True))
        self.assertEqual(out["resized"], {"buffer": [800, 800], "aspect": 1, "calls": 2, "cameraUpdated": True,
                                          "pixels": [800, 800]})
        self.assertEqual(out["sameSize"], 2)
        self.assertEqual(out["light"], {"dark": False, "normal": True, "uDark": 0, "calls": 2, "bg": "#f6f7f5"})
        self.assertEqual(out["sameTheme"], 2)  # an attribute changed, no colour did: no call
        self.assertEqual(out["pointer"], {"raw": [1, 1], "eased": [0, 0], "inside": True, "active": True, "calls": 1})
        self.assertEqual(out["easing"], [0.085, 0.085, True])
        self.assertEqual(out["eased"], [1, 1])
        self.assertEqual((out["touch"], out["lifted"]), ([0, 0, True], [0, 0, False]))
        self.assertEqual((out["outside"], out["setPointer"]), ([1, False], [0.5, -0.25]))
        self.assertTrue(out["passive"])
        self.assertEqual(out["pointerTargets"], ["html", "window"])  # never the canvas: it sits behind the text
        self.assertEqual((out["progress"], out["progressEased"]), ([1, 0, 0.4], 0.148))
        self.assertEqual((out["low"], out["medium"]), (["low", 0, 1, 1, 2], ["medium", 0.5, 2, 2]))
        self.assertAlmostEqual(out["view"]["height"], 4.1421, places=3)  # 2 * tan(45 / 2) * 5
        self.assertEqual(out["dispose"], [["dropped.geometry", "dropped.texture", "dropped.material"], 1])
        self.assertEqual(out["handle"], [["destroy", "pause", "resume", "setData", "setPointer", "setProgress",
                                          "stage"], "data", True])
        self.assertEqual(out["mounted"], [True, ["intersection", "mutation", "resize"]])
        self.assertEqual(out["destroyed"], {
            "listeners": 0, "observers": 0, "waiting": 0, "canvases": 0, "attr": None, "position": "",
            "rendererDisposed": 1, "contextGivenBack": 1, "freed": ["kept.geometry", "kept.texture", "kept.material"],
            "destroyCalls": 1, "running": False})
        self.assertEqual(out["afterDestroy"], [False, 0, 0, 0, "function"])
        self.assertEqual((out["second"], out["replaced"]), ([1, 1, "live"], [1, False, 3]))
        self.assertTrue(out["sameHelper"])  # stage.progressOf is the exported progressOf
        self.assertEqual((out["cover"], out["contain"]), ([0, 0.5, 1, 0], [0, 0.5, 1, 0, 1]))

    def test_reduced_motion_is_one_still_frame_until_something_changes(self):
        out = self.play("stage.run.mjs", "reduced")
        self.assertEqual(out["first"], {"ran": True, "renders": 1, "time": 5, "delta": 0, "waiting": 0,
                                        "running": False, "still": True, "attr": "live"})
        self.assertEqual(out["idle"], [False, False, 1])
        self.assertEqual(out["noRedraw"], [0, 1, 1])  # pointer, progress, pause, resume: no frame asked for
        self.assertEqual(out["afterResize"], [2, 2, 0])
        self.assertEqual(out["afterTheme"], [3, False])
        self.assertEqual(out["afterInvalidate"], [4, 0.5])  # three calls, one frame; progress is not eased in a still
        self.assertEqual(out["switchedOff"], [True, False, 5.032])  # the preference changed: it runs on from the still
        self.assertEqual(out["switchedOn"], [False, True, 5, 1, 0])
        self.assertEqual(out["destroyed"], [0, 0])

    def test_paused_before_the_first_frame_still_shows_a_picture(self):
        out = self.play("stage.run.mjs", "pausedfirst")
        self.assertEqual(out["first"], [True, 1, 5, False, 0, "live"])
        self.assertEqual(out["resumed"], [True, 5.016, 3])
        self.assertEqual(out["option"], [2, False, 1])  # { still: true } does what reduced motion does

    def test_no_webgl_is_a_quiet_fallback(self):
        out = self.play("stage.run.mjs", "nowebgl")
        self.assertEqual((out["failed"], out["attr"], out["threw"]), ("no-webgl", "fallback", []))
        self.assertEqual(out["touched"], [0, 0, 0, 0, None])  # no canvas, listener, observer or frame; no renderer
        self.assertEqual(out["quiet"], [0, 0, False])
        self.assertIsNone(out["attrAfterDestroy"])
        self.assertEqual(out["nowhere"], ["no-container", "no-container", "no-container", 0])  # no element: no crash
        source = read(os.path.join(SCENES, "stage.js"))
        called = set(out["every"])  # every function of the stage was called on the failed one
        for name in STAGE_MEMBER.findall(re.search(r"\n  const stage = \{\n(.*?)\n  \};\n", source, re.S).group(1)):
            if re.search(r"\n    %s: \(|\n  function %s\(" % (name, name), source) and name != "destroy":
                self.assertIn(name, called, "call stage.%s() in the nowebgl run too" % name)

    def test_a_lost_context_and_a_throwing_scene_fall_back(self):
        out = self.play("stage.run.mjs", "broken")
        self.assertEqual(out["lost"], ["context-lost", "fallback", True, False, 0, "0"])
        self.assertEqual(out["restored"], [False, "live", True, "1"])
        self.assertEqual(out["threw"], ["error", "fallback", False, 0, ["Error: boom"]])
        self.assertIsNone(out["attrAfterDestroy"])

    def test_shaders_compile_in_tasks_of_their_own_before_the_first_frame(self):
        out = self.play("stage.run.mjs", "compiling")
        # first frame: compile and hand over (flush), draw nothing, wait for a quiet moment
        self.assertEqual(out["first"], [True, 0, 1, 1, None, 1])
        self.assertEqual(out["after"], [1, "live", 1])  # then the first frame, compiled once
        self.assertEqual(out["async"], [0, 1, None])  # compileAsync where the browser compiles beside the page
        self.assertEqual(out["asyncAfter"], [1, "live"])

    def test_auto_quality_starts_from_the_device_and_steps_down(self):
        out = self.play("stage.run.mjs", "auto")
        self.assertEqual(out["runs"], {"fast": ["high@0"], "slow": ["high@0", "medium@103", "low@205"],
                                       "verySlow": ["high@0", "low@43"]})
        self.assertEqual(out["guess"], ["medium", "low"])  # four cores, two cores


class LazyTests(Sandbox):
    def test_nothing_loads_until_near_and_idle(self):
        out = self.play("lazy.run.mjs", "normal")
        self.assertEqual(out["waiting"], ["waiting", 0, 0, None])
        self.assertEqual(out["notNear"], [0, 0])
        self.assertEqual(out["nearNotIdle"], [0, 1, "waiting", 0])  # near: one idle callback asked for, no load yet
        self.assertEqual(out["breathing"], [1, "loading", 1, 0])  # loaded; mount() waits for the next quiet moment
        loaded = out["loaded"]
        self.assertEqual((loaded["loads"], loaded["state"], loaded["scene"], loaded["ready"]), (1, "ready", True, True))
        self.assertEqual(loaded["mountedWith"], [True, {"quality": "low"}])  # options.lazy stays behind
        self.assertEqual(loaded["calls"],  # what was asked before it loaded: the last call of each kind
                         [["pause", "page"], ["setData", [1]], ["setProgress", 0.7]])
        self.assertEqual(out["forwarded"], [[["setPointer", 0.1, 0.2], ["pause", "user"], ["resume", "user"]], 1])
        self.assertEqual(out["destroyed"], ["destroyed", 1, 6])
        self.assertEqual(out["destroyedEarly"], [1, "destroyed", None, 0])
        self.assertEqual(out["destroyedWhileLoading"], ["destroyed", 1, None])

    def test_reduced_data_keeps_the_poster(self):
        out = self.play("lazy.run.mjs", "savedata")
        self.assertEqual(out["kept"], ["reduced-data", 0, 0, 0])  # not even an observer
        self.assertEqual(out["forced"], ["ready", 1, [["setProgress", 0.3]]])  # load() is the way in

    def test_without_requestidlecallback_a_timer_does_it(self):
        out = self.play("lazy.run.mjs", "noidle")
        self.assertEqual((out["timer"], out["after"]), ([0, [200]], [1, "ready"]))
        self.assertEqual(out["between"], [1, "loading", [200, 0]])  # module and mount(): two tasks

    def test_without_webgl_three_is_never_loaded(self):
        out = self.play("lazy.run.mjs", "nowebgl")
        self.assertEqual(out["noWebgl"], ["failed", 0, "fallback", None, True, 0])  # no download, no console error
        self.assertEqual(out["optedOut"], ["ready", 1])  # lazy.webgl false: a loader that needs no WebGL

    def test_a_scene_that_cannot_load_leaves_the_poster(self):
        out = self.play("lazy.run.mjs", "failing")
        self.assertEqual(out["rejected"], ["failed", "fallback", None, "Error: offline", 1])
        self.assertIsNone(out["attrAfterDestroy"])
        self.assertEqual(out["noMount"][0], "failed")
        self.assertIn("no mount()", out["noMount"][1])
        self.assertEqual(out["mountThrew"], ["failed", "fallback", None])
        self.assertEqual(out["nowhere"], ["failed", None, 0, "function"])  # no container, no button: no crash

    def test_motion_toggle(self):
        pause, resume = [["pause", "motion-toggle"]], [["resume", "motion-toggle"]]
        for mode, stored in (("toggle", "paused"), ("nostorage", None)):  # storage that throws: it still works
            with self.subTest(mode=mode):
                out = self.play("lazy.run.mjs", mode)
                self.assertEqual((out["start"], out["mounted"]), (False, []))
                self.assertEqual(out["wired"], [["false", "false"], None])
                self.assertEqual(out["clicked"], [["true", "true"], "paused", stored, pause, True])
                self.assertEqual(out["mountedLater"], pause)  # a scene that arrives while motion is off starts paused
                # motion on again: "on", never removed (a runtime's reveals wait for html[data-motion])
                self.assertEqual(out["clickedAgain"], [["false", "false"], "on", None, resume, resume])
                self.assertEqual(out["unwired"], [0, True])
                self.assertEqual(out["destroyedHandlesLeftAlone"], 0)
        out = self.play("lazy.run.mjs", "remembered")  # switched off on an earlier page
        self.assertEqual((out["start"], out["mounted"]), (True, pause))
        self.assertEqual(out["wired"], [["true", "true"], "paused"])
        self.assertEqual(out["clicked"], [["false", "false"], "on", None, resume, False])
        self.assertEqual(out["clickedAgain"], [["true", "true"], "paused", "paused", pause, pause])

    def test_a_scene_keeps_the_motion_runtimes_on(self):
        """motion.md's runtime sets data-motion="on" and its reveals hide only under it: a mount or a
        wired button must not take it away, or no reveal plays on a page with a scene."""
        out = self.play("lazy.run.mjs", "runtime")
        self.assertEqual((out["kept"], out["paused"], out["back"], out["other"]), ("on", "paused", "on", "reveal"))


class DepthTests(Sandbox):
    def test_a_scroll_inside_a_scrolling_panel_moves_the_depth(self):
        """An app whose main area scrolls inside a fixed frame fires no window scroll event: depth.js
        must still hear it, or a stack stays where it came into view and a touch tilt never changes."""
        out = json.loads(self.run_node("depth.run.mjs"))
        self.assertGreater(out["first"], 10)
        waiting, panel, card = out["resting"]
        self.assertEqual(waiting, 0)  # settled: the loop sleeps
        self.assertIn("rotateX(12.58deg)", panel)  # a third of the way in: the panel still stands tipped back
        self.assertIn("rotateX(2.45deg)", card)  # low on the screen: the card leans back (touch, tilt 7)
        self.assertEqual(out["panel"], [1, 1])  # the panel's own scroll is heard, and a frame is asked for
        waiting, panel, card = out["after"]
        self.assertGreater(out["second"], 10)
        self.assertEqual(waiting, 0)
        self.assertTrue(panel.endswith("translate3d(0, -56px, -80px)"), panel)  # stepped forward into the cascade
        self.assertIn("rotateX(-0.35deg)", card)  # now above the middle: it leans the other way
        self.assertEqual(out["page"], [1, 1])  # the page's own scroll still wakes it
        self.assertEqual(out["left"], 0)  # destroy() takes the listener away


class ContourTests(Sandbox):
    """contour.js's own work on an outline, which only a browser check would show otherwise."""

    def test_outlines_are_read_into_rings_and_lines(self):
        out = json.loads(self.run_node("contour.helpers.run.mjs"))
        self.assertEqual(out["lake"], [1, 0, 0.615, 1])  # 0.1 degrees at 52N: cos(52.05) as wide as it is high
        self.assertEqual(out["island"], [2, 0])  # a hole is a ring of its own
        self.assertEqual(out["collection"], [2, 1])  # every polygon of every feature, and the line
        self.assertEqual(out["points"], [[0, 1], [1, 0], [1, 1]])  # open: a line; closed: an area; both
        self.assertEqual(out["nothing"], [None, None, None, None])  # nothing to draw, a point, a dot
        points, most, breaks, middle = out["trail"]
        self.assertLessEqual(points, most)  # 2000 points cut to what the shader reads
        self.assertGreater(points, 20)
        self.assertEqual((most, breaks, middle), (64, 1, True))  # a break between its two lines

    def test_the_outline_goes_beside_the_text(self):
        out = json.loads(self.run_node("contour.helpers.run.mjs"))
        left_calm, narrow = out["named"]
        beside, below, whole = out["open"]
        self.assertGreater(beside[0], left_calm[2])  # right of a calm on the left
        self.assertEqual(beside, [0.41, 0.04, 0.96, 0.96])
        self.assertEqual(below, [0.04, 0.34, 0.96, 0.96])  # a wide outline under a calm band at the top
        self.assertEqual(whole, [0.04, 0.04, 0.96, 0.96])  # no calm: all of it
        self.assertEqual(out["calm"], [None, narrow, left_calm, [0.1, 0.6, 0.9, 0.95], left_calm])

    def test_a_trail_gives_the_page_its_label_places_and_the_phone_its_calm(self):
        out = json.loads(self.run_node("contour.run.mjs"))
        self.assertEqual(out["route"], 7)  # 4 points, a break, 2 points
        self.assertEqual(out["defines"], ["HAS_ROUTE", "HAS_SHAPE", "OCTAVES"])
        self.assertEqual(out["wide"], [0, 0, 0, 0, 0])  # calm "none": no calm on the wide screen
        self.assertEqual(out["labels"], [["visible,x,y"] * 3])
        middle, start, nowhere = out["first"]
        self.assertTrue(middle["visible"] and start["visible"])
        self.assertTrue(0 < start["x"] < middle["x"] < 800 and 0 < middle["y"] < 400, out["first"])
        self.assertEqual(nowhere, {"x": 0, "y": 0, "visible": False})  # an entry it cannot place
        self.assertEqual((out["quiet"], out["errors"]), (1, 1))  # no call while nothing moves; the page's error is logged
        self.assertEqual(out["phone"], [0.05, 0.6, 0.95, 0.95, 1])  # the phone's calmBox, although calm is "none"
        self.assertEqual(out["afterResize"], 2)  # the labels move with the new size
        self.assertEqual(out["data"], 0)  # setData raises no hills next to a real place


class FieldTests(Sandbox):
    def test_the_phone_option_places_the_form_and_its_calm(self):
        out = json.loads(self.run_node("field.run.mjs"))
        phone, wide = out["phone"], out["wide"]
        self.assertEqual(phone["calm"], [-0.8, 0.8, -0.9, -0.1])  # calmBox [0.1, 0.55, 0.9, 0.95] in -1..1
        self.assertEqual(phone["amount"], 0.92)
        self.assertAlmostEqual(phone["scale"] * 6.1 / phone["width"], 0.8, places=2)  # size 0.8 of the width
        self.assertAlmostEqual(phone["position"][1], 0.2 * phone["height"], places=2)  # its middle at 30% from the top
        self.assertAlmostEqual(phone["position"][0], 0.65 * phone["scale"], places=2)  # the cloud's middle centred
        self.assertEqual((wide["calm"], wide["amount"]), ([-1, 0, -0.7, 0.7], 0.94))  # wider than 600: the usual side

    def test_streak_draws_a_third_of_the_points_as_streaks(self):
        out = json.loads(self.run_node("field.run.mjs"))
        self.assertEqual((out["round"]["streak"], out["round"]["count"]), ([0, 0], 150000))  # the default: round
        self.assertEqual((out["streak"]["streak"], out["streak"]["count"]), ([1, 1], 50000))


class RuleTests(unittest.TestCase):
    """The rules themselves: each one fires on a file that breaks it, and none on files that do not."""

    SCENE = ('import * as THREE from "three";\nimport { createStage } from "./stage.js";\n'
             "export function mount(container, options) {\n  const stage = createStage(container, options);\n"
             "  if (stage.failed) return stage.handle();\n  stage.onFrame(() => {});\n  return stage.handle();\n}\n")
    HOST = "https:" + "//cdn.example.com/three.js"  # in two pieces: this file must pass its own rule

    def check(self, source, name="new.js"):
        return problems(name, source, ["stage.js", "glsl.js", "lazy.js", name])

    def test_a_good_scene_is_quiet(self):
        self.assertEqual(self.check(self.SCENE), [])
        self.assertEqual(self.check('import { fbm } from "./glsl.js";\n' + self.SCENE), [])
        self.assertEqual(self.check("export const a = 1; // requestAnimationFrame only in a comment\n"), [])
        own = self.SCENE.replace("return stage.handle();\n}", "return { destroy() { stage.destroy(); } };\n}")
        self.assertEqual(self.check(own), [])

    def test_imports(self):
        for line in ['import { OrbitControls } from "three/addons/controls/OrbitControls.js";',
                     'import gsap from "gsap";', 'import "./missing.js";', 'export * from "../motion.js";',
                     'const m = await import("lodash");']:
            with self.subTest(line=line):
                self.assertIn('only "three" and', "".join(self.check(line + "\n" + self.SCENE)))
        self.assertIn("plain text", "".join(self.check("const load = (path) => import(path);\n")))
        self.assertIn("require()", "".join(self.check('const three = require("three");\n')))

    def test_other_hosts(self):
        host = ["names another host (http:// or https://)"]
        self.assertEqual(self.check("// see %s\nexport const a = 1;\n" % self.HOST), host)
        self.assertEqual(self.check('const url = "%s";\n' % self.HOST.replace("https", "HTTP")), host)

    def test_frames(self):
        loop = "function tick() { requestAnimationFrame(tick); }\n"
        asks = 'matchMedia("(prefers-reduced-motion: reduce)");\n'
        self.assertEqual(self.check(self.SCENE + loop),
                         ["calls requestAnimationFrame: use stage.onFrame(fn) or stage.invalidate()"])
        self.assertEqual(self.check(self.SCENE + loop, "stage.js"), [])  # the stage itself may
        self.assertIn("a frame loop of its own", "".join(self.check(loop)))  # no WebGL, and no stopping
        self.assertIn("a frame loop of its own", "".join(self.check(loop + asks)))  # half of the stopping
        self.assertEqual(self.check(loop + asks + "new IntersectionObserver(() => {});\n"), [])

    def test_mount_destroy_and_no_webgl(self):
        never = ["exports mount() but never destroys"]
        bare = "export function mount(container) { return { setProgress() {} }; }\n"
        self.assertEqual(self.check(bare), never)
        self.assertEqual(self.check("export const mount = (el) => ({ setProgress() {} });\n"), never)
        self.assertEqual(self.check("function mount() {}\nexport { mount };\n"), never)
        self.assertEqual(self.check(bare.replace("setProgress() {}", "destroy() {}")), [])
        blind = self.SCENE.replace("  if (stage.failed) return stage.handle();\n", "")
        self.assertEqual(self.check(blind), ["makes a stage and never looks at stage.failed"])


class HelperTests(unittest.TestCase):
    """The rules are only as good as what finds imports, comments and the stage's members."""

    def test_imports_are_found(self):
        code = ('import * as THREE from "three";\nimport { a,\n  b } from \'./glsl.js\';\nexport { c } from "./x.js";\n'
                'const later = () => import("./form.js");\nconst no = "import me";\nexport const d = "./not.js";\n')
        self.assertEqual(imports_in(code), (["three", "./glsl.js", "./x.js", "./form.js"], []))
        self.assertEqual(STATIC_IMPORT.findall('import "three/addons/controls/OrbitControls.js";'),
                         ["three/addons/controls/OrbitControls.js"])

    def test_comments_are_taken_out(self):
        text = "/* requestAnimationFrame */ a(); // requestAnimationFrame\nb();\n"
        self.assertEqual(COMMENT.sub("", text), " a(); \nb();\n")

    def test_stage_members_are_found(self):
        literal = "    container,\n    progress: 0,\n    onFrame: (fn) => x(fn),\n    go(a) {\n      deeper: 1,\n"
        self.assertEqual(STAGE_MEMBER.findall(literal), ["container", "progress", "onFrame", "go"])


if __name__ == "__main__":
    unittest.main()
