/**
 * datascape.js: the app's own numbers as a sculpture (scene kit, look level 5, dashboard level 5).
 *
 * Two modes. "bars": a grid of slim columns on a soft floor, their heights the data, seen from a
 * low three-quarter view. The tops catch an accent light along their rims, low values stay quiet,
 * the tallest are picked out in the second accent, the far rows melt into the page (depth fog) and
 * a faint reflection grounds them. "ridges": the same grid as a stack of ridgelines (a joy plot in
 * 3D): one ribbon per row, with a faint fill beneath that hides the rows behind it.
 *
 *   import { mount } from "./scenes/datascape.js";
 *   const scape = mount(document.querySelector(".hero-scene"), {
 *     mode: "bars", onHover: (cell) => showTooltip(cell),   // { index, row, column, value } or null
 *   });
 *   scape.setData(matrix);            // springs to the new numbers, never a jump
 *   addEventListener("scroll", () => scape.setProgress(scape.stage.progressOf(section)));
 *   scape.destroy();                  // when the page or component goes away
 *
 * Options (all optional; the stage's own options, see stage.js, pass straight through):
 *   mode       "bars" (default) or "ridges".
 *   rows       12, columns 24: the grid of the sample data, and of a flat list of that many numbers.
 *   gap        0.42: the part of each cell left open between two bars (0 none, 0.8 needles).
 *   height     1: how tall the tallest value stands (1.4 taller, 0.7 lower).
 *   side       "right" (default), "left" or "center": where the sculpture sits, away from the
 *              headline. On a tall, narrow screen it sits in the lower third.
 *   intensity  1: the strength of the rim light, the glow and the sweep (0 flat, 2 strong).
 *   onHover    null: gets { index, row, column, value } when the eased pointer rests on a bar or a
 *              ridge (found by a raycast), and null when it leaves.
 *   data       the first values, as for setData. Without them it shows sample data (an app's use
 *              by hour of the day, one row a month), so it is never empty.
 *
 * setData(values): a flat list of numbers or a matrix (a list of rows, at most 64 by 128). A matrix
 *   gives the grid its shape; a flat list of rows x columns numbers fills that grid row by row, any
 *   other length is laid out about twice as wide as deep. Heights run from 0 (or the lowest value,
 *   when below 0) to the highest. Each cell springs to its new height after a short delay that runs
 *   as a wave from the left; a missing number leaves its cell empty; an empty list brings the
 *   sample back. onHover reports the numbers as given.
 * setProgress(p), 0..1: the camera orbits about 30 degrees round the sculpture while a band of
 *   light sweeps across it from left to right. Feed it a section's progress, or a filter change.
 * setPointer(x, y), pause(), resume(), destroy(), stage: as stage.js describes.
 *
 * Poster: a child `<img data-scene-poster src="datascape.png" alt="">` shows until the first frame
 * and whenever there is no WebGL. Make the picture by mounting with { still: true } and taking a
 * screenshot; reduced motion draws that same still (every value at its height, no hover, no sway).
 * Keep a plain table of the numbers on the page too: a sculpture is not an accessible chart.
 *
 * Cost: three draw calls (floor, reflection, bars) or two (floor, ridges), no textures. Bars are one
 * instanced box; ridges have 4, 6 or 10 points per column and at least 100, 160 or 240 a row (low,
 * medium, high quality; low also drops the reflection). The processor runs a spring per cell, a raycast while the pointer is over the
 * scene, and rewrites the buffers only while something moves.
 */
import * as THREE from "three";
import { createStage } from "./stage.js";
import { stageUniforms, line, fog, grain } from "./glsl.js";

const WIDTH = 6, TAIL = 1.5;   // the width in world units (all sizes follow); columns a ridge runs on past its data
const SPRING = 70, DAMPING = 10;   // the springs settle in about half a second, with a small overshoot (ratio 0.6)
const MAX_ROWS = 64, MAX_COLUMNS = 128;

const shared = `${stageUniforms}
uniform vec4 uSize, uMotion, uFloor;   // see the uniforms in mount()
uniform vec2 uFog;`;
const pieces = `${shared}${line}${fog}${grain}
// Two soft bands of light across the width: one where setProgress puts it (uMotion.x), one that
// drifts by now and then on its own (uMotion.z, uMotion.w as strong). u runs 0..1 over the width.
float sweepAt(float x) {
  float u = x / ${WIDTH.toFixed(1)} + 0.5;
  return (exp(-pow((u - uMotion.x) / uMotion.y, 2.0)) + uMotion.w * exp(-pow((u - uMotion.z) / uMotion.y, 2.0))) * uSize.w;
}
// The accent a value is lit with: quiet (towards the muted text colour) when low, full when high.
vec3 litBy(float value, float peak) { return mix(uMuted, mix(uAccent, uAccent2, peak), 0.3 + 0.7 * smoothstep(0.0, 0.6, value)); }`;
const finish = `
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy) * gl_FragColor.a;`;

// Bars: one box with its base on the floor, drawn once per cell; the shader sizes and places it.
const barVertex = `${shared}
attribute vec2 aCell;   // x and z of the bar's middle
attribute vec4 aState;  // height 0..1, hover 0..1, peak 0..1, 1 when the cell has a value
varying vec3 vLocal, vNormal;   // vLocal: x and z across the bar (-0.5..0.5), y up from the floor
varying vec4 vState;
varying float vTop, vDepth, vX;
void main() {
  float h = (max(aState.x, 0.015) + aState.y * 0.07) * uSize.z * aState.w;   // hover makes it grow
  vec3 p = vec3(aCell.x + position.x * uSize.x * aState.w, position.y * h, aCell.y + position.z * uSize.y * aState.w);
#ifdef MIRROR
  p.y = -p.y;           // the reflection: the same bar upside down under the floor
#endif
  vLocal = vec3(position.x, position.y * h, position.z);
  vNormal = normal; vState = aState; vTop = h; vX = aCell.x;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  vDepth = -mv.z;
  gl_Position = projectionMatrix * mv;
}`;

// The light comes from the front left and above. uDark switches between light on a dark page and
// ink and paper on a light one; every colour is a mix of the stage tokens.
const barFragment = `${pieces}
varying vec3 vLocal, vNormal;
varying vec4 vState;
varying float vTop, vDepth, vX;
void main() {
  vec3 n = normalize(vNormal);
  float height = vState.x, hover = vState.y, sweep = sweepAt(vX), rim;
  float w = 1.6 * uPixelRatio;                 // the rim, in buffer pixels (the inner half shows)
  vec3 lit = litBy(height, vState.z), color;
  if (n.y > 0.5) {
    // The top: from a faint tint to the full accent as the value rises; a thin rim of light round it.
    rim = max(lineAlpha(0.5 - abs(vLocal.x), w), lineAlpha(0.5 - abs(vLocal.z), w));
    color = mix(mix(uSurface, lit, mix(0.12, 0.2, uDark)), lit, pow(height, 1.5));
    color = mix(color, uText, hover * 0.45 + sweep * 0.25);
  } else {
    // A side: turned to the key light or away from it, darker towards the floor, and lit by the top
    // for a short way down (further on the tallest).
    float facing = clamp(dot(n, normalize(vec3(-0.55, 0.0, 0.85))) * 0.5 + 0.5, 0.0, 1.0);
    float fromTop = vTop - vLocal.y, rise = smoothstep(0.0, uSize.z, vLocal.y);
    rim = max(lineAlpha(fromTop, w), 0.22 * lineAlpha(0.5 - abs(abs(n.x) > 0.5 ? vLocal.z : vLocal.x), w));
    vec3 night = mix(mix(uBg, uSurface, 0.6), mix(uSurface, uBorder, 0.35 + 0.65 * facing), 0.3 + 0.7 * rise);
    vec3 shade = mix(uBorder, uMuted, 0.3);
    vec3 paper = mix(mix(shade, uBorder, 0.4), mix(shade, uSurface, facing * facing), 0.45 + 0.55 * rise);
    color = mix(paper, night, uDark);
    float glow = exp(-fromTop / (0.045 + 0.07 * vState.z)) * (0.04 + 0.45 * height + 0.5 * hover + 0.3 * sweep);
    color = mix(color, lit, clamp(glow * uSize.w, 0.0, 1.0) * mix(0.5, 1.0, uDark));
  }
  vec3 rimColor = mix(lit, uText, mix(0.2, 0.35, uDark) + 0.4 * hover);
  color = mix(color, rimColor, rim * clamp(0.85 * uSize.w, 0.0, 1.0) * (0.3 + 0.7 * sqrt(height) + hover));
  float haze = fogLinear(vDepth, uFog.x, uFog.y);
  gl_FragColor = vec4(mix(color, uBg, haze * 0.92), 1.0);
#ifdef MIRROR
  gl_FragColor.a = (1.0 - smoothstep(0.0, 0.3 * uSize.z, vLocal.y)) * mix(0.08, 0.14, uDark) * (1.0 - haze);
#endif
  ${finish}
}`;

// The floor and the ridges: plain meshes in world space.
const plainVertex = `
attribute vec4 aRidge;  // ridges: the line's height here (world units), the value 0..1, peak 0..1, hover 0..1
varying vec4 vRidge;
varying vec3 vWorld;
varying float vDepth;
void main() {
  vRidge = aRidge;
  vec4 world = modelMatrix * vec4(position, 1.0), mv = viewMatrix * world;
  vWorld = world.xyz;
  vDepth = -mv.z;
  gl_Position = projectionMatrix * mv;
}`;

// A ridge: a line of even width where the height field meets its curve, and under it a fill of the
// page colour with a breath of accent, glowing just below the line, almost opaque so that the
// ridges behind are hidden, as on a printed joy plot. Rows are drawn back to front.
const ridgeFragment = `${pieces}
varying vec4 vRidge;
varying vec3 vWorld;
varying float vDepth;
void main() {
  float field = vWorld.y - vRidge.x;         // 0 on the line, below 0 in the fill
  float hover = vRidge.w, sweep = sweepAt(vWorld.x);
  float lineA = lineAlpha(field, (1.4 + 1.2 * hover) * uPixelRatio);
  vec3 lineColor = mix(litBy(vRidge.y, vRidge.z), uText, 0.4 * hover + 0.3 * sweep);
  float glow = exp(field / (0.05 + 0.08 * uSize.z)) * (0.12 + 0.25 * hover + 0.1 * sweep) * uSize.w;
  vec3 fill = mix(uBg, uAccent, 0.035 + 0.05 * clamp(vWorld.y / uSize.z, 0.0, 1.0));
  fill = mix(fill, mix(uAccent, uAccent2, vRidge.z), glow * mix(0.6, 1.0, uDark));
  float fillA = step(field, 0.0) * mix(0.82, 0.97, clamp(vWorld.y / max(vRidge.x, 0.001), 0.0, 1.0));
  float haze = fogLinear(vDepth, uFog.x, uFog.y);
  gl_FragColor = vec4(mix(mix(fill, lineColor, lineA), uBg, haze * 0.92), max(fillA, lineA));
  ${finish}
}`;

// The floor: a small cross where four cells meet, under the bars only, and a soft pool of light (on
// a dark page) or shade (on a light one) that sets the sculpture down.
const floorFragment = `${pieces}
varying vec3 vWorld;
varying float vDepth;
void main() {
  vec2 q = vWorld.xz;
  float away = length(max(abs(q) - uFloor.xy, 0.0));      // 0 under the sculpture, then world units
  vec2 g = (q + uFloor.xy) / max(uFloor.zw, 0.0001);      // in cells: the corners at whole numbers
  vec2 near = abs(g - floor(g + 0.5)), arm = near * uFloor.zw;   // to the nearest corner: cells, world
  float cross = max(lineAlpha(near.y, uPixelRatio) * (1.0 - smoothstep(0.025, 0.04, arm.x)),
                    lineAlpha(near.x, uPixelRatio) * (1.0 - smoothstep(0.025, 0.04, arm.y)));
  cross *= (1.0 - smoothstep(0.0, 0.6 * uFloor.z, away)) * step(0.0001, uFloor.z) * 0.58;
  float pool = (1.0 - smoothstep(-0.6, 1.4, away - 0.15 * min(uFloor.x, uFloor.y))) * mix(0.035, 0.07, uDark);
  vec3 color = (mix(uBorder, uMuted, 0.4) * cross + mix(uText, uAccent, uDark) * pool) / max(cross + pool, 0.0001);
  gl_FragColor = vec4(color, (cross + pool) * (1.0 - fogLinear(vDepth, uFog.x, uFog.y)));
  ${finish}
}`;

/** Made-up numbers, the same every time: an app's use by hour of the day, one row a month. */
function sampleData(rows, columns) {
  let seed = 11;
  const random = () => (seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296;
  const bump = (x, at, width) => Math.exp(-(((x - at) / width) ** 2));
  const values = [];
  for (let r = 0; r < rows; r++) {
    const season = 0.55 + 0.45 * Math.sin((Math.PI * (r + 0.5)) / rows);   // a fuller summer
    const shift = (random() - 0.5) * 2, amount = 0.8 + 0.4 * random();   // each month its own
    for (let c = 0; c < columns; c++) {
      const hour = ((c + 0.5) * 24) / columns;   // a morning, an afternoon and an evening peak
      const day = 0.05 + 0.75 * bump(hour, 9.5 + shift, 2.2) + bump(hour, 15 + shift, 2.6) + 0.4 * bump(hour, 20.5, 1.6);
      values.push(day * season * amount * (0.85 + 0.3 * random()));
    }
  }
  return values;
}

/** A flat list or a matrix -> { rows, columns, values (row by row, NaN where there is none) }. */
function shapeOf(input, o) {
  const list = input && typeof input.length === "number" ? Array.from(input) : [];
  const num = (v) => (v === null || v === "" || !Number.isFinite(Number(v)) ? NaN : Number(v));
  if (list.length && list.every((row) => row && typeof row === "object" && typeof row.length === "number")) {
    const rows = Math.min(list.length, MAX_ROWS);
    const columns = Math.min(MAX_COLUMNS, Math.max(...list.slice(0, rows).map((row) => row.length)));
    const values = [];
    for (let r = 0; r < rows; r++) for (let c = 0; c < columns; c++) values.push(num(list[r][c]));
    if (columns > 0 && values.some(Number.isFinite)) return { rows, columns, values };
  } else if (list.some((v) => Number.isFinite(num(v)))) {
    const n = Math.min(list.length, MAX_ROWS * MAX_COLUMNS);
    const columns = n === o.rows * o.columns ? o.columns : Math.min(MAX_COLUMNS, Math.max(2, Math.round(Math.sqrt(n * 2))));
    const rows = Math.ceil(n / columns);
    return { rows, columns, values: Array.from({ length: rows * columns }, (_, i) => (i < n ? num(list[i]) : NaN)) };
  }
  return { rows: o.rows, columns: o.columns, values: sampleData(o.rows, o.columns) };
}

export function mount(container, options = {}) {
  const o = { mode: "bars", rows: 12, columns: 24, gap: 0.42, height: 1, side: "right", intensity: 1, onHover: null, ...options };
  o.rows = Math.max(1, Math.min(MAX_ROWS, Math.round(o.rows) || 12));
  o.columns = Math.max(2, Math.min(MAX_COLUMNS, Math.round(o.columns) || 24));
  const number = (v, low, high, fallback) => Math.min(high, Math.max(low, Number.isFinite(Number(v)) ? Number(v) : fallback));
  [o.gap, o.height, o.intensity] = [number(o.gap, 0, 0.9, 0.42), number(o.height, 0.2, 3, 1), number(o.intensity, 0, 3, 1)];
  const ridges = o.mode === "ridges";
  const stage = createStage(container, { stillTime: 6, camera: { fov: 30, near: 0.5, far: 80 }, ...options });
  if (stage.failed) return stage.handle();
  const { scene, camera } = stage;

  const uniforms = {
    ...stage.uniforms,
    uSize: { value: new THREE.Vector4() },     // bar width x, bar width z, tallest height, intensity
    uMotion: { value: new THREE.Vector4() },   // sweep position 0..1 across the width, sweep width
    uFloor: { value: new THREE.Vector4() },    // half width, half depth, cell size x (0: no crosses), z
    uFog: { value: new THREE.Vector2() },      // fog from, fog full (distance from the camera)
  };
  const material = (vertexShader, fragmentShader, extra) => new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader, ...extra });
  const see = { transparent: true, depthWrite: false };
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2), material(plainVertex, floorFragment, see));
  let bars = null, mirror = null, ribbon = null;
  scene.add(floor);

  // The data: per cell the value as given, and a spring from the height on screen to the goal.
  let grid = { rows: 0, columns: 0, values: [] }, shown, speed, goal, wait, hover, peak, peakGoal, present;
  const span = { pitchX: 0.25, pitchZ: 0.25, depth: 3, tall: 2 };
  let moving = true, hovered = -1, sub = 6, every = 6, samples = 0;
  const rowZ = (r) => (r + 0.5 - grid.rows / 2) * span.pitchZ;
  const barX = (c) => (c + 0.5 - grid.columns / 2) * span.pitchX;
  const ridgeX = (s) => -WIDTH / 2 + (s + TAIL) * span.pitchX;

  function reshape(next) {
    const old = { grid, shown, speed, hover, peak };
    grid = next;
    const n = grid.rows * grid.columns;
    [shown, speed, goal, wait, hover, peak, peakGoal, present] = Array.from({ length: 8 }, () => new Float32Array(n));
    for (let r = 0; old.shown && r < Math.min(grid.rows, old.grid.rows); r++) {   // keep what was on screen
      for (let c = 0; c < Math.min(grid.columns, old.grid.columns); c++) {
        const i = r * grid.columns + c, j = r * old.grid.columns + c;
        [shown[i], speed[i], hover[i], peak[i]] = [old.shown[j], old.speed[j], old.hover[j], old.peak[j]];
      }
    }
    // Columns share the width. Bar rows are as deep as the columns are wide, ridges lie further
    // apart, and neither gets much deeper than two thirds of the width. A few cells give slim
    // columns far apart, not fat blocks.
    span.pitchX = WIDTH / (ridges ? grid.columns - 1 + 2 * TAIL : grid.columns);
    span.pitchZ = ridges ? Math.min(0.42, 4.4 / grid.rows) : Math.min(span.pitchX, 4 / grid.rows);
    span.depth = span.pitchZ * grid.rows;
    span.tall = (ridges ? 1.15 : 2.1) * o.height;
    const bar = Math.min(span.pitchX * (1 - o.gap), 0.1 * span.tall);
    uniforms.uSize.value.set(bar, Math.min(span.pitchZ * (1 - o.gap), bar), span.tall, o.intensity);
    uniforms.uFloor.value.set(WIDTH / 2, span.depth / 2, ridges ? 0 : span.pitchX, span.pitchZ);
    floor.scale.set(WIDTH + 4, 1, span.depth + 4);
    build();
  }

  function setValues(input) {
    const next = shapeOf(input, o);
    if (next.rows !== grid.rows || next.columns !== grid.columns) reshape(next);
    else grid.values = next.values;
    const order = grid.values.map((v, i) => [v, i]).filter(([v]) => Number.isFinite(v)).sort((a, b) => b[0] - a[0]);
    const high = order[0][0], low = Math.min(0, order[order.length - 1][0]);
    const peaks = new Set(order.slice(0, Math.max(1, Math.round(order.length * 0.035))).map(([, i]) => i));
    grid.values.forEach((v, i) => {
      present[i] = Number.isFinite(v) ? 1 : 0;
      goal[i] = present[i] ? (v - low) / (high - low || 1) : 0;
      peakGoal[i] = peaks.has(i) && high > low ? 1 : 0;
      wait[i] = 0.45 * ((i % grid.columns) / grid.columns) + 0.2 * (Math.floor(i / grid.columns) / grid.rows);
    });
    moving = true;
    stage.invalidate();
  }

  function build() {
    const n = grid.rows * grid.columns;
    for (const old of [bars, mirror, ribbon]) if (old) stage.dispose(old);
    let mesh;
    if (!ridges) {
      const geometry = new THREE.InstancedBufferGeometry().copy(new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0));
      const cells = new Float32Array(n * 2);
      for (let i = 0; i < n; i++) cells.set([barX(i % grid.columns), rowZ(Math.floor(i / grid.columns))], i * 2);
      geometry.setAttribute("aCell", new THREE.InstancedBufferAttribute(cells, 2));
      geometry.setAttribute("aState", new THREE.InstancedBufferAttribute(new Float32Array(n * 4), 4).setUsage(THREE.DynamicDrawUsage));
      geometry.instanceCount = n;
      mesh = bars = new THREE.Mesh(geometry, material(barVertex, barFragment));
      mirror = new THREE.Mesh(geometry, material(barVertex, barFragment, { ...see, defines: { MIRROR: 1 }, side: THREE.BackSide }));
      mirror.visible = stage.quality.name !== "low";
    } else {
      // Per row, points along x, each a pair (on the floor, on the line). Rows are stored back to
      // front, so drawing in order lets each fill cover the ridges behind it.
      const across = grid.columns - 1 + 2 * TAIL;   // at least about 100, 160 or 240 points along a ridge
      every = Math.max(sub, Math.ceil(stage.quality.pick(100, 160, 240) / across));
      samples = Math.round(across * every) + 1;
      const geometry = new THREE.BufferGeometry(), index = [];
      for (let v = 2; v < grid.rows * samples * 2; v += 2) if ((v / 2) % samples) index.push(v - 2, v, v - 1, v - 1, v, v + 1);
      geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(grid.rows * samples * 6), 3).setUsage(THREE.DynamicDrawUsage));
      geometry.setAttribute("aRidge", new THREE.BufferAttribute(new Float32Array(grid.rows * samples * 8), 4).setUsage(THREE.DynamicDrawUsage));
      geometry.setIndex(index);
      mesh = ribbon = new THREE.Mesh(geometry, material(plainVertex, ridgeFragment, { ...see, side: THREE.DoubleSide }));
    }
    for (const each of [mesh, ridges ? null : mirror]) if (each) { each.frustumCulled = false; each.renderOrder = 1; scene.add(each); }
    moving = true;
  }

  const smooth = (t) => t * t * (3 - 2 * t);
  // A ridge's height at s (in columns, may run past either end): a Catmull-Rom curve through the
  // values on screen, which passes exactly through each of them, and a smooth fall in the tails.
  function ridgeAt(r, s) {
    const last = grid.columns - 1, at = (c) => shown[r * grid.columns + Math.max(0, Math.min(last, c))];
    const fall = s < 0 ? smooth(Math.max(0, 1 + s / TAIL)) : s > last ? smooth(Math.max(0, 1 - (s - last) / TAIL)) : 1;
    const x = Math.max(0, Math.min(last, s)), i = Math.min(Math.floor(x), last - 1), f = x - i;
    const p0 = at(i - 1), p1 = at(i), p2 = at(i + 1), p3 = at(i + 2);
    const v = 0.5 * (2 * p1 + (p2 - p0) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f + (3 * p1 - p0 - 3 * p2 + p3) * f * f * f);
    return Math.max(0, v) * fall;
  }

  // Copy the springs into the buffers the shaders read.
  function write() {
    if (!ridges) {
      const state = bars.geometry.attributes.aState;
      for (let i = 0; i < shown.length; i++) state.array.set([Math.max(0, shown[i]), hover[i], peak[i], present[i]], i * 4);
      state.needsUpdate = true;
      return;
    }
    const { position, aRidge: ridge } = ribbon.geometry.attributes;
    for (let r = 0; r < grid.rows; r++) {
      const lift = Math.max(...hover.subarray(r * grid.columns, (r + 1) * grid.columns));
      for (let k = 0; k < samples; k++) {
        const s = k / every - TAIL, value = ridgeAt(r, s), y = value * (1 + lift * 0.12) * span.tall, v = (r * samples + k) * 2;
        let glow = 0;   // the second accent near a peak: the strongest peak within two columns, fading
        for (let c = Math.max(0, Math.ceil(s - 2)); c <= Math.min(grid.columns - 1, s + 2); c++) {
          glow = Math.max(glow, peak[r * grid.columns + c] * Math.exp(-(((s - c) / 0.9) ** 2)));
        }
        // The top point stands a little above the line, so the whole width of the line is drawn.
        position.array.set([ridgeX(s), 0, rowZ(r), ridgeX(s), y + 0.04 * span.tall, rowZ(r)], v * 3);
        ridge.array.set([y, value, glow, lift, y, value, glow, lift], v * 4);
      }
    }
    position.needsUpdate = ridge.needsUpdate = true;
  }

  // The raycast: the cell under the eased pointer, or -1. Bars are tested as boxes as wide as their
  // cell (so the gaps do not flicker); ridges front to back, as the area under each curve.
  const raycaster = new THREE.Raycaster(), box = new THREE.Box3(), hit = new THREE.Vector3(), at = new THREE.Vector2();
  function pick() {
    if (!stage.pointer.inside || stage.still) return -1;
    raycaster.setFromCamera(at.set(stage.pointer.x, stage.pointer.y), camera);
    const ray = raycaster.ray;
    let best = -1, nearest = Infinity;
    for (let i = 0; !ridges && i < shown.length; i++) {
      const x = barX(i % grid.columns), z = rowZ(Math.floor(i / grid.columns));
      box.min.set(x - span.pitchX / 2, 0, z - span.pitchZ / 2);
      box.max.set(x + span.pitchX / 2, Math.max(shown[i], 0.015) * span.tall, z + span.pitchZ / 2);
      const d = present[i] && ray.intersectBox(box, hit) ? hit.distanceTo(ray.origin) : Infinity;
      if (d < nearest) { nearest = d; best = i; }
    }
    for (let r = grid.rows - 1; ridges && r >= 0 && Math.abs(ray.direction.z) > 1e-6; r--) {
      const t = (rowZ(r) - ray.origin.z) / ray.direction.z;
      hit.copy(ray.direction).multiplyScalar(t).add(ray.origin);
      const s = (hit.x + WIDTH / 2) / span.pitchX - TAIL;
      if (t > 0 && s > -0.5 && s < grid.columns - 0.5 && hit.y >= 0 && hit.y <= ridgeAt(r, s) * span.tall + 0.05) {
        return r * grid.columns + Math.round(Math.max(0, Math.min(grid.columns - 1, s)));
      }
    }
    return best;
  }

  // The camera: a low three-quarter view with the near end to the right, fitted to the free part of
  // the screen. setViewOffset slides the picture over without turning the camera.
  let fit = 1;
  stage.onResize((size) => {
    const narrow = size.aspect < 0.9;
    const across = narrow ? 0 : { right: 0.19, left: -0.19 }[o.side] || 0, down = narrow ? 0.29 : 0.02;
    const room = narrow ? [1, 0.36] : [o.side === "center" ? 0.8 : 0.52, 0.72];   // share of width, height
    const tan = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    fit = 1 / Math.min(tan * room[1], tan * size.aspect * room[0]);
    camera.setViewOffset(size.width, size.height, -across * size.width, -down * size.height, size.width, size.height);
  });

  stage.onQuality((quality) => {
    if (mirror) mirror.visible = quality.name !== "low";
    sub = quality.pick(4, 6, 10);
    if (ribbon) build();
  });

  const target = new THREE.Vector3();
  function place(time) {
    const still = stage.still, p = stage.progressEased, pointer = still ? { x: 0, y: 0 } : stage.pointer;
    const az = 0.8 + (p - 0.5) * 0.5 + (still ? 0 : Math.sin(time * 0.09) * 0.05) + pointer.x * 0.05;   // round the sculpture
    const el = 0.3 + (0.5 - p) * 0.08 + pointer.y * 0.03;                                               // above the floor
    const radius = 0.5 * Math.hypot(WIDTH, Math.max(span.depth, 3.6), span.tall * 0.7), distance = radius * fit * 0.86;
    target.set(0, span.tall * 0.22, 0);
    camera.position.set(Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el)).multiplyScalar(distance).add(target);
    camera.lookAt(target);
    uniforms.uFog.value.set(distance - radius * 0.45, distance + radius * 0.75);
    // The drifting band crosses in four seconds once every sixteen, and rests in a still frame.
    uniforms.uMotion.value.set(-0.25 + p * 1.5, 0.1, ((time % 16) / 4) * 1.5 - 0.25, still ? 0 : 0.35);
  }

  stage.onFrame((time, delta) => {
    place(time);
    const now = pick();
    if (now !== hovered) {
      hovered = now;
      moving = true;
      const cell = now < 0 ? null : { index: now, row: Math.floor(now / grid.columns), column: now % grid.columns, value: grid.values[now] };
      if (typeof o.onHover === "function") o.onHover(cell);
    }
    if (!moving) return;
    // Springs in small fixed steps, so they move the same at any frame rate; a still frame shows
    // every value at its goal at once.
    let busy = false;
    const steps = Math.ceil(delta * 120), dt = steps ? delta / steps : 0, k = 1 - Math.exp(-delta * 9);
    for (let i = 0; i < shown.length; i++) {
      const hoverGoal = i === hovered ? 1 : 0;
      if (stage.still) { shown[i] = goal[i]; speed[i] = hover[i] = 0; peak[i] = peakGoal[i]; continue; }
      hover[i] += (hoverGoal - hover[i]) * k;
      peak[i] += (peakGoal[i] - peak[i]) * k * 0.4;
      if (wait[i] > 0) { wait[i] -= delta; busy = true; continue; }
      for (let s = 0; s < steps; s++) {
        speed[i] += (SPRING * (goal[i] - shown[i]) - DAMPING * speed[i]) * dt;
        shown[i] += speed[i] * dt;
      }
      busy = busy || Math.abs(goal[i] - shown[i]) + Math.abs(speed[i]) > 1e-4
        || Math.abs(hover[i] - hoverGoal) + Math.abs(peak[i] - peakGoal[i]) > 1e-3;
    }
    write();
    moving = busy;
  });

  stage.onDestroy(() => { if (hovered >= 0 && typeof o.onHover === "function") o.onHover(null); });
  setValues(o.data);
  return stage.handle({ setData: setValues });
}
