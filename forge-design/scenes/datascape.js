/**
 * datascape.js: the app's own numbers as a sculpture (scene kit, look level 5, dashboard level 5).
 *
 * Two modes. "bars": a grid of slim columns on a dark (or paper) floor, their heights the data,
 * seen from a low three-quarter view. The values that matter stand up as tinted columns with lit
 * caps; values near zero sink into the floor as thin dim tiles; the tallest are picked out in the
 * second accent; the far rows melt into the page (depth fog); a faint reflection and an even dot
 * lattice that fades into the fog ground it. "ridges": the same grid as a stack of ridgelines (a joy
 * plot in 3D): one ribbon per row, with a faint fill beneath that hides the rows behind it.
 *
 * It lives: a soft band of accent light travels slowly to and fro along the rows, lighting the caps
 * and the top of every column it crosses, and the heights breathe a few percent in a slow wave.
 * The pointer leans the key light and the camera, and puts a pool of light on the field below it.
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
 *   intensity  1: the strength of the light, the glow and the bands (0 flat, 2 strong).
 *   onHover    null: gets { index, row, column, value } when the eased pointer rests on a bar or a
 *              ridge (found by a raycast), and null when it leaves. The bar (or ridge) under the
 *              pointer grows by about a tenth and glows along its whole length in the accent; its
 *              four neighbours rise a little, so the light falls off around it.
 *   data       the first values, as for setData. Without them it shows sample data (an app's use
 *              by hour of the day, one row a month), so it is never empty.
 *
 * setData(values): a flat list of numbers or a matrix (a list of rows, at most 64 by 128). A matrix
 *   gives the grid its shape; a flat list of rows x columns numbers fills that grid row by row, any
 *   other length is laid out about twice as wide as deep. Heights run from 0 (or the lowest value,
 *   when below 0) to the highest. Each cell springs to its new height after a short delay that runs
 *   as a wave from the left; a missing number leaves its cell empty; an empty list brings the
 *   sample back. onHover reports the numbers as given.
 * setProgress(p), 0..1: three states. At 0 a low three-quarter view, the field calm and mostly dim.
 *   Towards 0.5 a front of accent light walks from the far rows to the near ones: the rows it has
 *   passed are lit, the rows ahead stay dark. Towards 1 the camera rises and closes in on the
 *   tallest values (second accent) while the rest of the field falls back into the fog. Without
 *   setProgress the field rests in the first state, lit only by the travelling band.
 * setPointer(x, y), pause(), resume(), destroy(), stage: as stage.js describes.
 *
 * Poster: a child `<img data-scene-poster src="datascape.png" alt="">` shows until the first frame
 * and whenever there is no WebGL. Make the picture by mounting with { still: true } and taking a
 * screenshot; reduced motion draws that same still (every value at its height, the band resting
 * at one place, no hover, no breathing). Keep a plain table of the numbers on the page too: a
 * sculpture is not an accessible chart.
 *
 * Cost: three draw calls (floor, reflection, bars) or two (floor, ridges), no textures. Bars are one
 * instanced box; ridges have 4, 6 or 10 points per column and at least 100, 160 or 240 a row (low,
 * medium, high quality; low also drops the reflection). The bands and the breathing are uniforms,
 * so they cost the processor nothing; it runs a spring per cell, a raycast while the pointer is over
 * the scene, and rewrites the buffers only while a spring moves.
 */
import * as THREE from "three";
import { createStage } from "./stage.js";
import { stageUniforms, line, fog, grain } from "./glsl.js";

const WIDTH = 6, TAIL = 1.5;   // the width in world units (all sizes follow); columns a ridge runs on past its data
const SPRING = 70, DAMPING = 10;   // the springs settle in about half a second, with a small overshoot (ratio 0.6)
const MAX_ROWS = 64, MAX_COLUMNS = 128;
const BAND_PERIOD = 13;   // seconds the travelling band takes there and back

const shared = `${stageUniforms}
uniform vec4 uSize, uMotion, uFocus, uFloor, uSpot;   // see the uniforms in mount()
uniform vec3 uLight;
uniform vec2 uFog;
// How tall a column stands at (x, z): the heights breathe a few percent in a slow wave.
float breath(vec2 xz) { return 1.0 + uFocus.w * sin(uTime * 0.7 - xz.x * 0.8 - xz.y * 0.6); }`;
const pieces = `${shared}${line}${fog}${grain}
// The light on a place of the sculpture: a little everywhere, more on high values and on the peaks;
// the columns the progress front has passed (uMotion.w, over the width: 0 the left end, 1 the
// right one) and the front itself; the band that travels to and fro over the rows (uMotion.x, over
// the depth: 0 the far row, 1 the near one); the pool under the pointer. 0 is dark, 1 fully lit,
// more is hot.
float beamsAt(vec3 w) {      // the progress front and the travelling band alone
  float u = w.x / (2.0 * uFloor.x) + 0.5, v = w.z / (2.0 * uFloor.y) + 0.5;
  return 1.4 * exp(-pow((u - uMotion.w) / 0.06, 2.0)) + 1.4 * uMotion.z * exp(-pow((v - uMotion.x) / uMotion.y, 2.0));
}
float lightAt(vec3 w, float height, float peak) {
  float u = w.x / (2.0 * uFloor.x) + 0.5, passed = smoothstep(uMotion.w + 0.05, uMotion.w - 0.05, u);
  vec2 s = w.xz - uSpot.xy;
  float spot = uSpot.z * exp(-dot(s, s) / 0.3);
  float ahead = (1.0 - passed) * smoothstep(0.05, 0.3, uProgress);   // what the front has not reached goes darker
  return ((0.1 + 0.35 * height) * (1.0 - 0.85 * ahead) + 0.4 * peak * (1.0 - 0.5 * ahead) + 0.6 * passed + beamsAt(w) + 0.4 * spot) * uSize.w;
}
// Near 1 (setProgress towards 1) everything but the peaks falls back into the fog.
float focusFade(vec3 w) { return uFocus.z * smoothstep(0.35, 1.3, distance(w.xz, uFocus.xy)); }`;
const finish = `
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy) * gl_FragColor.a;`;

// Bars: one box with its base on the floor, drawn once per cell; the shader sizes and places it.
const barVertex = `${shared}
attribute vec2 aCell;   // x and z of the bar's middle
attribute vec4 aState;  // height 0..1, hover 0..1, peak 0..1, 1 when the cell has a value
varying vec3 vLocal, vNormal, vWorld;   // vLocal: x and z across the bar (-0.5..0.5), y up from the floor
varying vec4 vState;
varying float vTop, vDepth;
void main() {
  float h = max(aState.x, 0.008) * uSize.z * breath(aCell);
  h = (h + aState.y * (0.1 * h + 0.05 * uSize.z)) * aState.w;   // hover lifts it by about a tenth
  vec3 p = vec3(aCell.x + position.x * uSize.x * aState.w, position.y * h, aCell.y + position.z * uSize.y * aState.w);
  vWorld = p;
#ifdef MIRROR
  p.y = -p.y;           // the reflection: the same bar upside down under the floor
#endif
  vLocal = vec3(position.x, position.y * h, position.z);
  vNormal = normal; vState = aState; vTop = h;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  vDepth = -mv.z;
  gl_Position = projectionMatrix * mv;
}`;

// The key light comes from the front left (uLight, leaning with the pointer). uDark switches
// between light on a dark page and tinted paper on a light one; every colour mixes stage tokens.
const barFragment = `${pieces}
varying vec3 vLocal, vNormal, vWorld;
varying vec4 vState;
varying float vTop, vDepth;
// Colours are mixed in display space (as a designer mixes them) and turned back into linear light
// at the end, so a 10 percent tint looks like 10 percent, also in the dark.
vec3 shown(vec3 c) { return pow(max(c, 0.0), vec3(1.0 / 2.2)); }
void main() {
  vec3 n = normalize(vNormal);
  vec3 bg = shown(uBg), surface = shown(uSurface), border = shown(uBorder), muted = shown(uMuted), text = shown(uText);
  float height = vState.x, hover = vState.y, peak = vState.z, rim;
  float lit = lightAt(vWorld, height, peak), glowing = clamp(lit, 0.0, 1.0), hot = clamp(lit - 1.0, 0.0, 1.0);
  float stand = smoothstep(0.03, 0.24, height);     // near-zero values sink into the floor
  float w = 1.4 * uPixelRatio;                      // the rim, in buffer pixels (the inner half shows)
  vec3 tone = shown(mix(uAccent, uAccent2, peak)), color;
  float fromTop = vTop - vLocal.y, rise = clamp(vLocal.y / max(vTop, 0.0001), 0.0, 1.0);
  if (n.y > 0.5) {
    // The cap: filled with the accent, brighter where the light is; white-hot in the band.
    rim = max(lineAlpha(0.5 - abs(vLocal.x), w), lineAlpha(0.5 - abs(vLocal.z), w));
    vec3 night = mix(border, tone, 0.18 + 0.82 * glowing);
    vec3 paper = mix(surface, tone, 0.36 + 0.6 * glowing);
    color = mix(paper, night, uDark);
    color = mix(color, mix(tone, text, uDark * 0.7), clamp(hot * mix(0.9, 0.6, uDark) + hover * 0.5, 0.0, 1.0));
  } else {
    // A side: turned to the key light or away from it, darker towards the floor, tinted with the
    // accent towards its cap, and lit by the cap over its top fifth (all the way down when hovered).
    float facing = clamp(dot(n, normalize(uLight)) * 0.5 + 0.5, 0.0, 1.0);
    float top = exp(-fromTop / (0.2 * vTop + 0.015));
    rim = max(lineAlpha(fromTop, w), 0.22 * lineAlpha(0.5 - abs(abs(n.x) > 0.5 ? vLocal.z : vLocal.x), w));
    vec3 night = mix(mix(surface, border, 0.1 + 0.75 * facing), tone, 0.03 + 0.05 * facing);
    night = mix(mix(bg, surface, 0.5), night, 0.35 + 0.65 * rise);
    vec3 face = mix(surface, tone, (0.12 + 0.14 * rise) * (1.0 + 0.7 * peak));
    vec3 paper = mix(mix(face, mix(muted, tone, 0.35), 0.45), face, facing);
    paper = mix(paper, border, (1.0 - rise) * 0.25);
    color = mix(paper, night, uDark);
    float glow = (top * (0.12 + 0.7 * glowing) + 0.22 * glowing * glowing * rise) * mix(0.85, 1.0, uDark) + hover * (0.35 + 0.35 * rise) + hot * top * 0.5;
    color = mix(color, mix(tone, text, hover * 0.3 * uDark), clamp(glow, 0.0, 1.0));
  }
  vec3 rimColor = mix(tone, text, uDark * 0.3 + 0.4 * hover + 0.3 * hot);
  color = mix(color, rimColor, rim * (0.3 + 0.7 * glowing) * mix(0.6, 1.0, uDark));
  color = mix(mix(mix(bg, border, 0.3), surface, 0.4 * uDark), color, 0.05 + 0.95 * stand);
  float haze = max(fogLinear(vDepth, uFog.x, uFog.y), focusFade(vWorld));
  gl_FragColor = vec4(pow(mix(color, bg, haze * 0.94), vec3(2.2)), 1.0);
#ifdef MIRROR
  gl_FragColor.a = (1.0 - smoothstep(0.0, 0.3 * uSize.z, vLocal.y)) * mix(0.07, 0.14, uDark) * (1.0 - haze) * stand;
#endif
  ${finish}
}`;

// The floor and the ridges: plain meshes in world space.
const plainVertex = `${shared}
attribute vec4 aRidge;  // ridges: the line's height here (world units), the value 0..1, peak 0..1, hover 0..1
varying vec4 vRidge;
varying vec3 vWorld;
varying float vDepth;
void main() {
  vRidge = aRidge;
  vec4 world = modelMatrix * vec4(position, 1.0);
#ifdef RIDGE
  float b = breath(world.xz);
  world.y *= b; vRidge.x *= b;
#endif
  vec4 mv = viewMatrix * world;
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
  float hover = vRidge.w, peak = vRidge.z, lit = lightAt(vWorld, vRidge.y, peak);
  float glowing = clamp(lit, 0.0, 1.0), hot = clamp(lit - 1.0, 0.0, 1.0);
  vec3 tone = mix(uAccent, uAccent2, peak);
  float lineA = lineAlpha(field, (mix(1.7, 1.3, uDark) + 0.9 * glowing + 1.2 * hover) * uPixelRatio);
  vec3 lineColor = mix(mix(uMuted, tone, mix(0.6, 0.35, uDark) + mix(0.4, 0.65, uDark) * glowing), uText, (0.4 * hover + 0.35 * hot) * mix(0.4, 1.0, uDark));
  float glow = exp(field / (0.05 + 0.1 * uSize.z)) * (0.06 + 0.3 * glowing + 0.4 * hover);
  vec3 fill = mix(uBg, tone, mix(0.12, 0.035, uDark) + mix(0.2, 0.05, uDark) * clamp(vWorld.y / uSize.z, 0.0, 1.0));
  fill = mix(fill, tone, clamp(glow, 0.0, 1.0) * mix(0.8, 1.0, uDark));
  float fillA = step(field, 0.0) * mix(0.82, 0.97, clamp(vWorld.y / max(vRidge.x, 0.001), 0.0, 1.0));
  float haze = max(fogLinear(vDepth, uFog.x, uFog.y), focusFade(vWorld));
  gl_FragColor = vec4(mix(mix(fill, lineColor, lineA), uBg, haze * 0.94), max(fillA, lineA));
  ${finish}
}`;

// The floor: an even lattice of faint dots where four cells meet, running on past the bars and
// fading into the fog, lit where a band passes; a soft pool of light (dark page) or shade (light
// page) under the sculpture, and a pool of accent under the pointer.
const floorFragment = `${pieces}
varying vec3 vWorld;
varying float vDepth;
void main() {
  vec2 q = vWorld.xz;
  float away = length(max(abs(q) - uFloor.xy, 0.0));      // 0 under the sculpture, then world units
  vec2 g = (q + uFloor.xy) / max(uFloor.zw, 0.0001);      // in cells: the corners at whole numbers
  float pixel = max(length(fwidth(q)), 0.00001);          // world units across one buffer pixel
  float dist = length((g - floor(g + 0.5)) * uFloor.zw) / pixel;
  float dots = (1.0 - smoothstep(0.55, 1.35, dist / uPixelRatio)) * smoothstep(5.0, 11.0, uFloor.z / pixel);
  dots *= (1.0 - smoothstep(0.0, 1.7, away)) * step(0.0001, uFloor.z) * mix(0.5, 0.42, uDark);
  float light = clamp(lightAt(vec3(q.x, 0.0, q.y), 0.0, 0.0) - 0.06 * uSize.w, 0.0, 1.5);
  float pool = (1.0 - smoothstep(-0.6, 1.4, away - 0.15 * min(uFloor.x, uFloor.y))) * mix(0.035, 0.07, uDark);
  vec2 s = q - uSpot.xy;
  float spot = uSpot.z * exp(-dot(s, s) / 0.45) * mix(0.08, 0.16, uDark) * uSize.w;
  vec3 dotColor = mix(mix(uBorder, uMuted, 0.55), uAccent, clamp(light, 0.0, 1.0) * 0.8);
  float sheen = beamsAt(vec3(q.x, 0.0, q.y)) * (1.0 - smoothstep(0.0, 1.2, away)) * mix(0.04, 0.11, uDark) * uSize.w;
  vec3 color = (dotColor * dots + mix(uText, uAccent, uDark) * pool + uAccent * (spot + sheen)) / max(dots + pool + spot + sheen, 0.0001);
  float fade = 1.0 - max(fogLinear(vDepth, uFog.x, uFog.y), focusFade(vec3(q.x, 0.0, q.y)));
  gl_FragColor = vec4(color, (dots * (0.6 + 0.4 * clamp(light, 0.0, 1.0)) + pool + spot + sheen) * fade);
  ${finish}
}`;

/** Made-up numbers, the same every time: an app's use by hour of the day, one row a month. */
function sampleData(rows, columns) {
  let seed = 11;
  const random = () => (seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296;
  const bump = (x, at, width) => Math.exp(-(((x - at) / width) ** 2));
  const values = [];
  for (let r = 0; r < rows; r++) {
    const season = 0.5 + 0.5 * Math.sin((Math.PI * (r + 0.5)) / rows);   // a fuller summer
    const shift = (random() - 0.5) * 2, amount = 0.8 + 0.4 * random();   // each month its own
    for (let c = 0; c < columns; c++) {
      const hour = ((c + 0.5) * 24) / columns;   // a morning, an afternoon and an evening peak; quiet nights
      const day = 0.012 + 0.7 * bump(hour, 9.5 + shift, 2) + bump(hour, 15 + shift, 2.4) + 0.4 * bump(hour, 20.5, 1.5);
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
    uMotion: { value: new THREE.Vector4() },   // travelling band: place 0..1 over the depth, width, strength; progress front 0..1 over the width
    uFocus: { value: new THREE.Vector4() },    // x and z of the peaks, how far the rest has fallen back, breathing amount
    uFloor: { value: new THREE.Vector4() },    // half width, half depth, cell size x (0: no dots), z
    uSpot: { value: new THREE.Vector4() },     // x and z of the pool under the pointer, its strength
    uLight: { value: new THREE.Vector3(-0.55, 0, 0.85) },   // the key light's direction
    uFog: { value: new THREE.Vector2() },      // fog from, fog full (distance from the camera)
  };
  const material = (vertexShader, fragmentShader, extra) => new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader, ...extra });
  const see = { transparent: true, depthWrite: false };
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2), material(plainVertex, floorFragment, see));
  let bars = null, mirror = null, ribbon = null;
  scene.add(floor);

  // The data: per cell the value as given, and a spring from the height on screen to the goal.
  let grid = { rows: 0, columns: 0, values: [] }, shown, speed, goal, wait, hover, peak, peakGoal, present;
  const span = { pitchX: 0.25, pitchZ: 0.25, depth: 3, tall: 2 }, focus = new THREE.Vector3();
  let moving = true, hovered = -1, sub = 6, every = 6, samples = 0;
  const rowZ = (r) => (r + 0.5 - grid.rows / 2) * span.pitchZ;
  const barX = (c) => (c + 0.5 - grid.columns / 2) * span.pitchX;
  const ridgeX = (s) => -WIDTH / 2 + (s + TAIL) * span.pitchX;
  const cellX = (c) => (ridges ? ridgeX(c) : barX(c));

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
    floor.scale.set(WIDTH + 5, 1, span.depth + 5);
    build();
  }

  function setValues(input) {
    const next = shapeOf(input, o);
    if (next.rows !== grid.rows || next.columns !== grid.columns) reshape(next);
    else grid.values = next.values;
    const order = grid.values.map((v, i) => [v, i]).filter(([v]) => Number.isFinite(v)).sort((a, b) => b[0] - a[0]);
    const high = order[0][0], low = Math.min(0, order[order.length - 1][0]);
    const peaks = new Set(order.slice(0, Math.max(1, Math.round(order.length * 0.035))).map(([, i]) => i));
    focus.set(0, 0, 0);
    grid.values.forEach((v, i) => {
      present[i] = Number.isFinite(v) ? 1 : 0;
      goal[i] = present[i] ? (v - low) / (high - low || 1) : 0;
      peakGoal[i] = peaks.has(i) && high > low ? 1 : 0;
      wait[i] = 0.45 * ((i % grid.columns) / grid.columns) + 0.2 * (Math.floor(i / grid.columns) / grid.rows);
      if (peaks.has(i)) focus.add({ x: cellX(i % grid.columns), y: goal[i], z: rowZ(Math.floor(i / grid.columns)) });
    });
    focus.divideScalar(peaks.size);   // where the camera goes at the end: the middle of the peaks
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
      mesh = ribbon = new THREE.Mesh(geometry, material(plainVertex, ridgeFragment, { ...see, side: THREE.DoubleSide, defines: { RIDGE: 1 } }));
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
  // 1 for the hovered cell, 0.4 for its four neighbours, 0 elsewhere.
  function hoverGoalOf(i) {
    if (hovered < 0) return 0;
    if (i === hovered) return 1;
    const dr = Math.abs(Math.floor(i / grid.columns) - Math.floor(hovered / grid.columns));
    const dc = Math.abs((i % grid.columns) - (hovered % grid.columns));
    return dr + dc === 1 ? 0.4 : 0;
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

  const target = new THREE.Vector3(), close = new THREE.Vector3(), plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  let spot = 0;
  function place(time, delta) {
    const still = stage.still, p = stage.progressEased, pointer = still ? { x: 0, y: 0 } : stage.pointer;
    const rise = smooth(Math.min(1, Math.max(0, (p - 0.45) / 0.55)));   // the last part: up and in, onto the peaks
    const az = 0.8 + (p - 0.5) * 0.55 + (still ? 0 : Math.sin(time * 0.09) * 0.04) + pointer.x * 0.2;   // round the sculpture
    const el = 0.27 + 0.06 * p + (ridges ? 0.14 : 0.3) * rise + pointer.y * 0.09;                                           // above the floor
    const radius = 0.5 * Math.hypot(WIDTH, Math.max(span.depth, 3.6), span.tall * 0.7), distance = radius * fit * 0.86 * (1 - (ridges ? 0.12 : 0.22) * rise);
    target.set(0, span.tall * 0.22, 0).lerp(close.set(focus.x, span.tall * (0.25 + 0.3 * focus.y), focus.z), rise);
    camera.position.set(Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el)).multiplyScalar(distance).add(target);
    camera.lookAt(target);
    camera.updateMatrixWorld();
    uniforms.uFog.value.set(distance - radius * 0.45, distance + radius * (0.75 - 0.25 * rise));
    // The band goes there and back over the rows, slowest at the ends; a still frame rests it at one
    // place. The progress front walks over the width from just before the left end to past the right one.
    const band = still ? 0.62 : 0.5 - 0.48 * Math.cos((time * 2 * Math.PI) / BAND_PERIOD);
    uniforms.uMotion.value.set(band, 0.13, 0.95 * (1 - 0.5 * smooth(Math.min(1, p / 0.4))), -0.15 + 1.3 * p);
    uniforms.uFocus.value.set(focus.x, focus.z, 0.92 * smooth(Math.min(1, Math.max(0, (p - 0.55) / 0.45))), still ? 0 : 0.045);
    // The key light leans with the pointer; the pool of light sits where the pointer meets the field.
    uniforms.uLight.value.set(-0.55 + pointer.x * 0.75, 0, 0.85 - pointer.y * 0.35);
    raycaster.setFromCamera(at.set(pointer.x, pointer.y), camera);
    plane.constant = -span.tall * 0.2;
    const ground = raycaster.ray.intersectPlane(plane, hit);
    spot += ((stage.pointer.inside && !still && ground ? 1 : 0) - spot) * (1 - Math.exp(-delta * 4));
    if (ground) uniforms.uSpot.value.set(THREE.MathUtils.clamp(hit.x, -WIDTH / 2 - 0.3, WIDTH / 2 + 0.3), THREE.MathUtils.clamp(hit.z, -span.depth / 2 - 0.3, span.depth / 2 + 0.3), 0, 0);
    uniforms.uSpot.value.z = spot;
  }

  stage.onFrame((time, delta) => {
    place(time, delta);
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
      const hoverGoal = hoverGoalOf(i);
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
