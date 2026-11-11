/**
 * datascape.js: the app's own numbers as a sculpture (scene kit, look level 5, dashboard level 5).
 *
 * Two modes. "bars": a dense field of slim columns rising out of a dark (or paper) floor, their
 * heights the data, seen from a low view that runs off the edge of the frame, like a landscape.
 * Each cap is a small light: the cap glows in the accent and its light runs a little way down the
 * column, while the body fades into the floor (dark page) or deepens towards it (light page); the
 * faces turned from the key light are clearly darker; values near zero shrink into the floor. The
 * tallest values are picked out in the second accent, or, when both accents are grey, as near-white
 * caps (near-black on a light page) above mid-grey; the far rows melt into the page (depth fog); a
 * faint reflection over a soft glow (dark page) or a soft contact shadow (light page) grounds the
 * mass. "ridges": the same grid as a stack of ridgelines (a joy plot in 3D): one ribbon per row,
 * with a faint fill beneath that hides the rows behind it.
 *
 * It lives: from the first frame the columns rise from a low relief, in a wave from the front-left
 * corner; a soft band of accent light travels slowly to and fro over the rows, lighting the columns
 * it crosses, and the heights breathe a few percent in a slow wave. The pointer turns the camera (up
 * to about 14 degrees round and 8 up or down), leans the key light, and pools accent light on the
 * floor and on the caps under it.
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
 *   gap        0.18: the part of each cell left open between two columns (0 none: the columns
 *              touch; 0.8 needles).
 *   height     1: how tall the tallest value stands (1.4 taller, 0.7 lower).
 *   side       "right" (default), "left" or "center": where the sculpture sits, away from the
 *              headline. On a tall, narrow screen it sits in the lower third.
 *   intensity  1: the strength of the light, the glow and the bands (0 flat, 2 strong).
 *   onHover    null: gets { index, row, column, value } of the data cell when the eased pointer
 *              rests on its column or ridge (found by a raycast), and null when it leaves. The column
 *              under the pointer rises by about a quarter and glows along its whole length, hottest
 *              at the cap; its neighbours rise a little, so the light falls off around it.
 *   data       the first values, as for setData. Without them it shows sample data (an app's use
 *              by hour of the day, one row a month), so it is never empty.
 *
 * setData(values): a flat list of numbers or a matrix (a list of rows, at most 64 by 128). A matrix
 *   gives the grid its shape; a flat list of rows x columns numbers fills that grid row by row, any
 *   other length is laid out about twice as wide as deep. Heights run from 0 (or the lowest value,
 *   when below 0) to the highest. In "bars" a grid of fewer than 40 columns is filled in, so few
 *   numbers still make a dense field: each cell becomes k by k columns (k up to 8, at most 4096
 *   columns in all) on a smooth surface through the values, and onHover reports the data cell
 *   nearest to the column under the pointer. Each column springs to its new height after a short
 *   delay that runs as a wave from the front-left corner; a missing number leaves its cell empty;
 *   an empty list brings the sample back. onHover reports the numbers as given. In "bars" a column
 *   that joins or leaves the tallest values dims in its old colour and comes back in the new one.
 * setProgress(p), 0..1: three states, and the camera turns round the sculpture from one to the next.
 *   At 0 a low view along the rows, the field calm. Towards 0.5 the camera turns and rises, and a
 *   front of accent light walks over the columns, from the first (left) column of the data to the
 *   last (right) one, over the width, not the rows: a bright line of caps with a sheen on the floor;
 *   the columns it has passed are lit at full accent, the columns ahead fall back to about a third.
 *   Towards 1 the camera rises and closes in on the tallest values (second accent) while the rest of
 *   the field falls back into the fog (in "bars" it also sinks to two fifths of its height).
 *   Without setProgress the field rests in the first state, lit only by the travelling band.
 * setPointer(x, y), pause(), resume(), destroy(), stage: as stage.js describes.
 *
 * Poster: a child `<img data-scene-poster src="datascape.png" alt="">` shows until the first frame
 * and whenever there is no WebGL. Make the picture by mounting with { still: true } and taking a
 * screenshot; reduced motion draws that same still (every value at its height, the band resting
 * at one place, no hover, no breathing). Keep a plain table of the numbers on the page too: a
 * sculpture is not an accessible chart.
 *
 * Cost: three draw calls (floor, reflection, bars) or two (floor, ridges), no textures. Bars are one
 * instanced box (the sample is a field of 24 by 48); ridges have 4, 6 or 10 points per column and
 * at least 100, 160 or 240 a row (low, medium, high quality; low also drops the reflection and draws
 * at three quarters of the resolution, unless renderScale says otherwise). The bands and the
 * breathing are uniforms, so they cost the processor nothing; it runs a spring per column, a raycast
 * while the pointer is over the scene, and rewrites the buffers only while a spring moves.
 */
import * as THREE from "three";
import { createStage } from "./stage.js";
import { stageUniforms, line, fog, grain } from "./glsl.js";

const WIDTH = 6, TAIL = 1.5;   // the width in world units (all sizes follow); columns a ridge runs on past its data
const SPRING = 70, DAMPING = 10;   // the springs settle in about half a second, with a small overshoot (ratio 0.6)
const MAX_ROWS = 64, MAX_COLUMNS = 128;
const DENSE = 40, MAX_CELLS = 4096;   // bars: a grid with fewer columns is filled in, up to this many columns in all
const BAND_PERIOD = 13;   // seconds the travelling band takes there and back
const RISE = 0.25;        // seconds the rising wave takes from the front-left corner to the far end

const shared = `${stageUniforms}
uniform vec4 uSize, uMotion, uFocus, uFloor, uSpot;   // see the uniforms in mount()
uniform vec3 uLight, uTone, uPeak;
uniform vec2 uFog;
// How tall a column stands at (x, z): the heights breathe a few percent in a slow wave.
float breath(vec2 xz) { return 1.0 + uFocus.w * sin(uTime * 0.7 - xz.x * 0.8 - xz.y * 0.6); }`;
const pieces = `${shared}${line}${fog}${grain}
// The progress front (uMotion.w) walks over the width, over the columns from left to right:
// u is 0 at the left end, 1 at the right one. passedAt is 1 where it has been, aheadAt 1 for the
// columns it has not reached yet (only once setProgress has started), frontAt the line itself.
float acrossAt(vec3 w) { return w.x / (2.0 * uFloor.x) + 0.5; }
float passedAt(vec3 w) { return smoothstep(uMotion.w + 0.03, uMotion.w - 0.03, acrossAt(w)); }
float aheadAt(vec3 w) { return smoothstep(uMotion.w + 0.02, uMotion.w + 0.07, acrossAt(w)) * smoothstep(0.05, 0.3, uProgress); }
float frontAt(vec3 w) { return exp(-pow((acrossAt(w) - uMotion.w) / 0.055, 2.0)); }
// The band that travels to and fro over the rows (uMotion.x, over the depth: 0 the far row, 1 the
// near one), and the pool under the pointer.
float bandAt(vec3 w) { return uMotion.z * exp(-pow((w.z / (2.0 * uFloor.y) + 0.5 - uMotion.x) / uMotion.y, 2.0)); }
float spotAt(vec3 w) { vec2 s = w.xz - uSpot.xy; return uSpot.z * exp(-dot(s, s) / 0.5); }
// The pointer on screen: what is drawn within about a tenth of the height of it catches its light
// too, so the caps under the pointer light up even where its ray meets the floor far behind them.
float haloAt() {
  vec2 s = (gl_FragCoord.xy / uResolution * 2.0 - 1.0 - uPointer) * vec2(uResolution.x / uResolution.y, 1.0);
  return uSpot.z * exp(-dot(s, s) / 0.05);
}
// The light on a place of the sculpture: a little everywhere, more on high values and on the peaks,
// on what the front has passed and on the front itself, in the band and under the pointer (the
// floor leaves the halo out). 0 is dark, 1 fully lit, more is hot.
float lightAt(vec3 w, float height, float peak) {
  return (0.12 + 0.4 * height + 0.4 * peak + 0.55 * passedAt(w) + 1.8 * frontAt(w) + 1.3 * bandAt(w) + 1.1 * spotAt(w)) * uSize.w;
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
  // Near 1 (setProgress) the columns away from the peaks sink to two fifths, so the peaks stand clear.
  float sink = uFocus.z * smoothstep(0.35, 1.3, distance(aCell, uFocus.xy)) * (1.0 - aState.z);
  float h = max(aState.x, 0.008) * uSize.z * breath(aCell) * (1.0 - 0.6 * sink);
  h = (h + aState.y * (0.25 * h + 0.06 * uSize.z)) * aState.w;   // hover lifts it by about a quarter
  float foot = aState.w * smoothstep(0.004, 0.07, aState.x + aState.y);   // values near zero shrink into the floor
  vec3 p = vec3(aCell.x + position.x * uSize.x * foot, position.y * h, aCell.y + position.z * uSize.y * foot);
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

// The key light comes from over the camera's right shoulder (uLight, leaning with the pointer).
// uDark switches between light on a dark page and tinted paper on a light one; every colour mixes
// stage tokens.
const barFragment = `${pieces}
varying vec3 vLocal, vNormal, vWorld;
varying vec4 vState;
varying float vTop, vDepth;
// The colour of a column: the base tone, or the peak tone for the tallest values. A column that
// changes group does not pass through a grey mix of the two: it dims in its old colour and comes
// back up in the new one.
// Colours are mixed in display space (as a designer mixes them) and turned back into linear light
// at the end, so a 10 percent tint looks like 10 percent, also in the dark. The stage colours come
// in display space already (uShown..., worked out once in mount()).
uniform vec3 uShownBg, uShownSurface, uShownBorder, uShownText, uShownTone, uShownPeak;
vec3 toneOf(float peak, vec3 bg) {
  vec3 tone = peak > 0.5 ? uShownPeak : uShownTone;
  return mix(mix(bg, tone, 0.4), tone, abs(2.0 * peak - 1.0));
}
void main() {
  vec3 n = normalize(vNormal);
  vec3 bg = uShownBg, surface = uShownSurface, border = uShownBorder, text = uShownText;
  float height = vState.x, hover = vState.y, peak = vState.z;
  float lit = lightAt(vWorld, height, peak) + 1.6 * haloAt() * uSize.w + 0.8 * hover, glowing = clamp(lit, 0.0, 1.0), hot = clamp(lit - 1.0, 0.0, 1.0);
  float stand = smoothstep(0.01, 0.07, height);     // near-zero values sink into the floor
  vec3 tone = toneOf(peak, bg), color;
  vec3 flare = mix(tone, text, mix(0.25, 0.6, uDark));   // white-hot on a dark page, deeper on paper
  float fromTop = vTop - vLocal.y, rise = clamp(vLocal.y / max(vTop, 0.0001), 0.0, 1.0);
  if (n.y > 0.5) {
    // The cap is where the light comes from: the tone at full strength, hot where the light is.
    vec3 night = mix(mix(bg, tone, 0.8), mix(tone, text, 0.55), glowing);
    vec3 paper = mix(mix(surface, tone, 0.6), tone, glowing);
    color = mix(mix(paper, night, uDark), flare, clamp(hot * 0.85 + hover * 0.7, 0.0, 1.0));
  } else {
    // A side: turned to the key light or away from it (the shaded side clearly darker). On a dark
    // page tinted glass that fades into the floor; on paper a tint that deepens towards the floor.
    float facing = smoothstep(0.15, 0.85, clamp(dot(n, normalize(uLight)) * 0.5 + 0.5, 0.0, 1.0));
    float passed = passedAt(vWorld) * smoothstep(0.05, 0.3, uProgress) * (1.0 - uFocus.z);   // at full accent behind the front
    vec3 glass = mix(surface, tone, 0.08 + 0.16 * glowing + 0.3 * passed);
    vec3 night = mix(bg, glass, (0.04 + 0.85 * pow(rise, 2.4)) * mix(0.4, 1.0, facing));
    vec3 deep = mix(tone, text, 0.35);
    vec3 face = mix(mix(surface, tone, 0.12 + 0.12 * glowing + 0.3 * passed), mix(tone, deep, 0.4), 0.9 * pow(1.0 - rise, 0.9));
    vec3 paper = mix(mix(face, deep, 0.5), face, facing);
    color = mix(paper, night, uDark);
    // The cap's light runs a little way down the column (all of it when hovered); a bright lip
    // where the side meets the cap.
    float bleed = exp(-fromTop / (0.04 * uSize.z + 0.012));
    float glow = bleed * (0.35 + 0.5 * glowing) * mix(0.35, 1.0, uDark) + hover * (0.25 + 0.5 * rise) + hot * bleed * 0.4;
    color = mix(color, mix(tone, flare, hot * uDark), clamp(glow, 0.0, 1.0));
    color = mix(color, mix(tone, flare, 0.5 * uDark), lineAlpha(fromTop, 1.3 * uPixelRatio) * (0.45 + 0.55 * glowing));
  }
  color = mix(mix(bg, mix(border, surface, uDark), 0.25), color, 0.04 + 0.96 * stand);
  color = mix(bg, color, 1.0 - 0.68 * aheadAt(vWorld));   // the columns the front has not reached
  float haze = max(fogLinear(vDepth, uFog.x, uFog.y), focusFade(vWorld));
  gl_FragColor = vec4(pow(mix(color, bg, haze * 0.94), vec3(2.2)), 1.0);
#ifdef MIRROR
  gl_FragColor.a = (1.0 - smoothstep(0.0, 0.55 * uSize.z, vLocal.y)) * mix(0.05, 0.2, uDark) * (1.0 - haze) * stand;
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
  float hover = vRidge.w, peak = vRidge.z, lit = lightAt(vWorld, vRidge.y, peak) + haloAt() * uSize.w;
  float glowing = clamp(lit, 0.0, 1.0), hot = clamp(lit - 1.0, 0.0, 1.0);
  vec3 tone = mix(uTone, uPeak, peak);
  float lineA = lineAlpha(field, (mix(1.7, 1.3, uDark) + 0.9 * glowing + 1.2 * hover) * uPixelRatio);
  vec3 lineColor = mix(mix(uMuted, tone, mix(0.6, 0.35, uDark) + mix(0.4, 0.65, uDark) * glowing), uText, (0.4 * hover + 0.35 * hot) * mix(0.4, 1.0, uDark));
  float glow = exp(field / (0.05 + 0.1 * uSize.z)) * (0.06 + 0.3 * glowing + 0.4 * hover);
  vec3 fill = mix(uBg, tone, mix(0.12, 0.035, uDark) + mix(0.2, 0.05, uDark) * clamp(vWorld.y / uSize.z, 0.0, 1.0));
  fill = mix(fill, tone, clamp(glow, 0.0, 1.0) * mix(0.8, 1.0, uDark));
  float fillA = step(field, 0.0) * mix(0.82, 0.97, clamp(vWorld.y / max(vRidge.x, 0.001), 0.0, 1.0));
  float haze = max(fogLinear(vDepth, uFog.x, uFog.y), focusFade(vWorld));
  vec3 color = mix(uBg, mix(fill, lineColor, lineA), 1.0 - 0.68 * aheadAt(vWorld));
  gl_FragColor = vec4(mix(color, uBg, haze * 0.94), max(fillA, lineA));
  ${finish}
}`;

// The floor: a faint lattice of dots around the sculpture (every second cell corner, fading out),
// a soft pool of light (dark page) or a contact shadow (light page) under it, a sheen where the
// progress front crosses it (on and just around the field), and a pool of accent under the
// pointer. The travelling band lights the columns only: on the open floor it would show as a
// streak running out of the frame.
const floorFragment = `${pieces}
varying vec3 vWorld;
varying float vDepth;
void main() {
  vec2 q = vWorld.xz;
  vec3 w = vec3(q.x, 0.0, q.y);
  float away = length(max(abs(q) - uFloor.xy, 0.0));      // 0 under the sculpture, then world units
  vec2 g = (q + uFloor.xy) / max(uFloor.zw, 0.0001);      // in lattice steps: the corners at whole numbers
  float pixel = max(length(fwidth(q)), 0.00001);          // world units across one buffer pixel
  float dist = length((g - floor(g + 0.5)) * uFloor.zw) / pixel;
  float dots = (1.0 - smoothstep(0.55, 1.35, dist / uPixelRatio)) * smoothstep(5.0, 11.0, uFloor.z / pixel);
  dots *= smoothstep(0.02, 0.25, away) * (1.0 - smoothstep(0.2, 1.4, away)) * step(0.0001, uFloor.z) * mix(0.32, 0.3, uDark);
  float light = clamp(lightAt(w, 0.0, 0.0) - 0.12 * uSize.w, 0.0, 1.5);
  float pool = (1.0 - smoothstep(-0.25, 0.9, away)) * mix(0.15, 0.07, uDark);
  vec3 poolColor = mix(mix(uText, uTone, 0.3), uTone, uDark);
  float spot = spotAt(w) * mix(0.14, 0.24, uDark) * uSize.w;
  float sheen = 3.0 * frontAt(w) * smoothstep(0.05, 0.2, uProgress) * (1.0 - smoothstep(0.2, 1.1, away)) * mix(0.07, 0.16, uDark) * uSize.w;
  vec3 dotColor = mix(mix(uBorder, uMuted, 0.55), uTone, clamp(light, 0.0, 1.0) * 0.8);
  vec3 color = (dotColor * dots + poolColor * pool + uTone * (spot + sheen)) / max(dots + pool + spot + sheen, 0.0001);
  float fade = 1.0 - max(fogLinear(vDepth, uFog.x, uFog.y), focusFade(w));
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

/**
 * The field the bars stand in: with fewer than DENSE columns each data cell becomes k by k columns
 * on a Catmull-Rom surface through the values (kept between the lowest and the highest), so a few
 * numbers still make a dense field. source[i] is the data cell nearest to column i; a column whose
 * nearest cell has no value stays empty.
 */
function fieldOf(data, dense) {
  let k = dense ? Math.max(1, Math.min(8, Math.ceil(DENSE / data.columns))) : 1;
  while (k > 1 && data.rows * data.columns * k * k > MAX_CELLS) k--;
  const rows = data.rows * k, columns = data.columns * k, n = rows * columns;
  const values = new Array(n), source = new Int32Array(n);
  const finite = data.values.filter(Number.isFinite), low = Math.min(...finite), high = Math.max(...finite);
  const clampTo = (v, last) => Math.max(0, Math.min(last, v));
  const curve = (p0, p1, p2, p3, f) => 0.5 * (2 * p1 + (p2 - p0) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f + (3 * p1 - p0 - 3 * p2 + p3) * f * f * f);
  for (let i = 0; i < n; i++) {
    const y = (Math.floor(i / columns) + 0.5) / k - 0.5, x = ((i % columns) + 0.5) / k - 0.5;
    const near = clampTo(Math.round(y), data.rows - 1) * data.columns + clampTo(Math.round(x), data.columns - 1);
    const own = data.values[near];
    source[i] = near;
    if (k === 1 || !Number.isFinite(own)) { values[i] = own; continue; }
    const r = Math.floor(y), c = Math.floor(x);
    const at = (dr, dc) => {
      const v = data.values[clampTo(r + dr, data.rows - 1) * data.columns + clampTo(c + dc, data.columns - 1)];
      return Number.isFinite(v) ? v : own;
    };
    const row = (dr) => curve(at(dr, -1), at(dr, 0), at(dr, 1), at(dr, 2), x - c);
    values[i] = Math.min(high, Math.max(low, curve(row(-1), row(0), row(1), row(2), y - r)));
  }
  return { rows, columns, values, source, k };
}

export function mount(container, options = {}) {
  const o = { mode: "bars", rows: 12, columns: 24, gap: 0.18, height: 1, side: "right", intensity: 1, onHover: null, ...options };
  o.rows = Math.max(1, Math.min(MAX_ROWS, Math.round(o.rows) || 12));
  o.columns = Math.max(2, Math.min(MAX_COLUMNS, Math.round(o.columns) || 24));
  const number = (v, low, high, fallback) => Math.min(high, Math.max(low, Number.isFinite(Number(v)) ? Number(v) : fallback));
  [o.gap, o.height, o.intensity] = [number(o.gap, 0, 0.9, 0.18), number(o.height, 0.2, 3, 1), number(o.intensity, 0, 3, 1)];
  const ridges = o.mode === "ridges";
  // A weak device (low quality) draws at three quarters of the resolution: the field fills much of
  // the screen, and its glow hides the softer edges.
  const stage = createStage(container, { stillTime: 6, fade: 200, renderScale: [0.75, 1, 1], camera: { fov: 30, near: 0.5, far: 80 }, ...options });
  if (stage.failed) return stage.handle();
  const { scene, camera } = stage;

  const uniforms = {
    ...stage.uniforms,
    uSize: { value: new THREE.Vector4() },     // bar width x, bar width z, tallest height, intensity
    uMotion: { value: new THREE.Vector4() },   // travelling band: place 0..1 over the depth, width, strength; progress front 0..1 over the width
    uFocus: { value: new THREE.Vector4() },    // x and z of the peaks, how far the rest has fallen back, breathing amount
    uFloor: { value: new THREE.Vector4() },    // half width, half depth, lattice step x (0: no dots), z
    uSpot: { value: new THREE.Vector4() },     // x and z of the pool under the pointer, its strength
    uLight: { value: new THREE.Vector3(0, 0, 1) },   // the key light's direction
    uTone: { value: new THREE.Color() },       // the colour of the field, and of the tallest values
    uPeak: { value: new THREE.Color() },
    uFog: { value: new THREE.Vector2() },      // fog from, fog full (distance from the camera)
  };
  for (const name of ["Bg", "Surface", "Border", "Text", "Tone", "Peak"]) uniforms["uShown" + name] = { value: new THREE.Color() };
  const material = (vertexShader, fragmentShader, extra) => new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader, ...extra });
  const see = { transparent: true, depthWrite: false };
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2), material(plainVertex, floorFragment, see));
  let bars = null, mirror = null, ribbon = null;
  scene.add(floor);

  // The two tones. When both accents are grey (a mono palette) the hue cannot pick out the peaks,
  // so luminance does: the accent furthest from the page for the peaks, the other one for the rest.
  stage.onTokens((tokens) => {
    const chroma = (c) => { const s = c.clone().convertLinearToSRGB(); return Math.max(s.r, s.g, s.b) - Math.min(s.r, s.g, s.b); };
    const lum = (c) => 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
    const far = (c) => Math.abs(lum(c) - lum(tokens.bg));
    if (chroma(tokens.accent) < 0.1 && chroma(tokens.accent2) < 0.1) {
      const [peakTone, rest] = far(tokens.accent) >= far(tokens.accent2) ? [tokens.accent, tokens.accent2] : [tokens.accent2, tokens.accent];
      uniforms.uPeak.value.copy(peakTone);
      uniforms.uTone.value.copy(Math.abs(far(peakTone) - far(rest)) > 0.1 ? rest : tokens.muted);
    } else {
      uniforms.uTone.value.copy(tokens.accent);
      uniforms.uPeak.value.copy(tokens.accent2);
    }
    // The bars mix their colours in display space: turn them once here, not in every pixel.
    const display = { Bg: tokens.bg, Surface: tokens.surface, Border: tokens.border, Text: tokens.text, Tone: uniforms.uTone.value, Peak: uniforms.uPeak.value };
    for (const [name, c] of Object.entries(display)) uniforms["uShown" + name].value.setRGB(c.r ** (1 / 2.2), c.g ** (1 / 2.2), c.b ** (1 / 2.2));
  });

  // The data as given, and per column of the field the height on screen, a spring to the goal.
  let data = { rows: 0, columns: 0, values: [] }, grid = { rows: 0, columns: 0, values: [], source: new Int32Array(0), k: 1 };
  let shown, speed, goal, wait, hover, peak, peakGoal, present;
  const span = { pitchX: 0.25, pitchZ: 0.25, depth: 3, tall: 2 }, focus = new THREE.Vector3();
  let moving = true, hovered = -1, reported = -1, sub = 6, every = 6, samples = 0, slot = new Int32Array(0);
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
    // apart, and neither gets much deeper than two thirds of the width. The gap is the part of a
    // cell left open, so 0 closes it.
    span.pitchX = WIDTH / (ridges ? grid.columns - 1 + 2 * TAIL : grid.columns);
    span.pitchZ = ridges ? Math.min(0.42, 4.4 / grid.rows) : Math.min(span.pitchX, 4 / grid.rows);
    span.depth = span.pitchZ * grid.rows;
    span.tall = (ridges ? 1.15 : 2.1) * o.height;
    const bar = span.pitchX * (1 - o.gap);
    uniforms.uSize.value.set(bar, span.pitchZ * (1 - o.gap), span.tall, o.intensity);
    uniforms.uFloor.value.set(WIDTH / 2, span.depth / 2, ridges ? 0 : 2 * span.pitchX, 2 * span.pitchZ);
    floor.scale.set(WIDTH + 2.6, 1, span.depth + 2.6);
    build();
  }

  function setValues(input) {
    const first = !grid.values.length;   // the first numbers rise from a low relief, so the first frame is a picture
    data = shapeOf(input, o);
    const next = fieldOf(data, !ridges);
    if (next.rows !== grid.rows || next.columns !== grid.columns) reshape(next);
    else grid = next;
    const order = grid.values.map((v, i) => [v, i]).filter(([v]) => Number.isFinite(v)).sort((a, b) => b[0] - a[0]);
    const high = order[0][0], low = Math.min(0, order[order.length - 1][0]);
    const peaks = new Set(order.slice(0, Math.max(1, Math.round(order.length * 0.035))).map(([, i]) => i));
    const corner = Math.hypot(WIDTH, span.depth);
    focus.set(0, 0, 0);
    grid.values.forEach((v, i) => {
      const r = Math.floor(i / grid.columns), c = i % grid.columns;
      present[i] = Number.isFinite(v) ? 1 : 0;
      goal[i] = present[i] ? (v - low) / (high - low || 1) : 0;
      peakGoal[i] = peaks.has(i) && high > low ? 1 : 0;
      // The rise runs as a wave from the front-left corner (the first column of the nearest row).
      wait[i] = (RISE * Math.hypot(c * span.pitchX, (grid.rows - 1 - r) * span.pitchZ)) / corner;
      if (first) [shown[i], peak[i]] = [0.3 * goal[i], peakGoal[i]];
      if (peaks.has(i)) focus.add({ x: cellX(c), y: goal[i], z: rowZ(r) });
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
      geometry.setIndex(Array.from(geometry.index.array).filter((_, k) => k < 18 || k >= 24));   // no bottom face: it stands on the floor
      // The columns are stored nearest first (as the camera usually sees them), so the depth test
      // skips what nearer columns hide instead of shading it again; slot[i] is where cell i went.
      const cells = new Float32Array(n * 2), near = (i) => barX(i % grid.columns) * 0.84 + rowZ(Math.floor(i / grid.columns)) * 0.54;
      const order = Array.from({ length: n }, (_, i) => i).sort((a, b) => near(b) - near(a));
      slot = new Int32Array(n);
      order.forEach((i, j) => { slot[i] = j; cells.set([barX(i % grid.columns), rowZ(Math.floor(i / grid.columns))], j * 2); });
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
      for (let i = 0; i < shown.length; i++) state.array.set([Math.max(0, shown[i]), hover[i], peak[i], present[i]], slot[i] * 4);
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

  // The raycast: the column under the eased pointer, or -1. Bars are tested as boxes as wide as
  // their cell (so the gaps do not flicker); ridges front to back, as the area under each curve.
  const raycaster = new THREE.Raycaster(), box = new THREE.Box3(), hit = new THREE.Vector3(), at = new THREE.Vector2();
  function pick() {
    if (!stage.pointer.inside || stage.still) return -1;
    const ray = raycaster.ray;
    let best = -1, nearest = Infinity;
    for (let i = 0; !ridges && i < shown.length; i++) {
      const x = barX(i % grid.columns), z = rowZ(Math.floor(i / grid.columns));
      box.min.set(x - span.pitchX / 2, 0, z - span.pitchZ / 2);
      const fall = uniforms.uFocus.value.z * smooth(Math.min(1, Math.max(0, (Math.hypot(x - focus.x, z - focus.z) - 0.35) / 0.95))) * (1 - peak[i]);
      box.max.set(x + span.pitchX / 2, Math.max(shown[i] * (1 - 0.6 * fall), 0.015) * span.tall, z + span.pitchZ / 2);   // as drawn, sunk or not
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
  // 1 for the hovered column, falling off with the distance in columns (about one data cell wide).
  function hoverGoalOf(i) {
    if (hovered < 0) return 0;
    const dr = Math.floor(i / grid.columns) - Math.floor(hovered / grid.columns), dc = (i % grid.columns) - (hovered % grid.columns);
    const d2 = dr * dr + dc * dc, k2 = grid.k * grid.k;
    return d2 === 0 ? 1 : d2 > 9 * k2 ? 0 : Math.exp(-d2 / (0.9 * k2));
  }

  // The camera has three states (setProgress 0, 0.5 and 1), each [turn round the field, height
  // above the floor (both in radians), distance (a share of the one that fits the free part of the
  // screen), slide right, slide down (shares of the screen)]. Bars: at rest low and close, the far
  // end of the field clear of the headline, the near rows running off the bottom and the right edge;
  // at 0.5 turned and raised to watch the front cross; at 1 up and in on the peaks. Ridges keep a
  // calmer path. setViewOffset slides the picture over without turning the camera.
  const VIEWS = ridges
    ? [[0.525, 0.27, 0.86, 0.19, 0.02], [0.8, 0.3, 0.86, 0.19, 0.02], [1.075, 0.47, 0.757, 0.19, 0.02]]
    : [[1.15, 0.26, 0.46, 0.275, 0.1], [0.95, 0.58, 0.6, 0.275, 0.1], [1.075, 0.63, 0.67, 0.19, 0.02]];
  const AIM = ridges ? [0, 0] : [0.5, 0.3];   // x and z the camera looks at in the middle state
  let fit = 1;
  stage.onResize((size) => {
    const room = size.aspect < 0.9 ? [1, 0.36] : [o.side === "center" ? 0.8 : 0.52, 0.72];   // share of width, height
    const tan = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    fit = 1 / Math.min(tan * room[1], tan * size.aspect * room[0]);
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
    const half = smooth(Math.min(1, p / 0.5));                                // the first half: to the middle state
    const rise = smooth(Math.min(1, Math.max(0, (p - 0.45) / 0.55)));          // the last part: up and in, onto the peaks
    const blend = (k) => { const m = VIEWS[0][k] + (VIEWS[1][k] - VIEWS[0][k]) * half; return m + (VIEWS[2][k] - m) * rise; };
    const turn = blend(0) + (still ? 0 : Math.sin(time * 0.09) * 0.04);
    const az = turn + pointer.x * 0.25, el = blend(1) + pointer.y * 0.14;     // the pointer turns it a few degrees
    const { width, height, aspect } = stage.size, narrow = aspect < 0.9;   // a tall, narrow screen: further off, in the lower third
    const radius = 0.5 * Math.hypot(WIDTH, Math.max(span.depth, 3.6), span.tall * 0.7), distance = radius * fit * blend(2) * (narrow ? 1.43 : 1);
    const across = narrow ? 0 : ({ right: 1, left: -1 }[o.side] || 0) * blend(3), down = narrow ? 0.33 : blend(4);
    camera.setViewOffset(width, height, -across * width, -down * height, width, height);
    target.set(AIM[0] * half, span.tall * 0.2, AIM[1] * half).lerp(close.set(focus.x, span.tall * (0.25 + 0.3 * focus.y), focus.z), rise);
    camera.position.set(Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el)).multiplyScalar(distance).add(target);
    camera.lookAt(target);
    camera.updateMatrixWorld();
    uniforms.uFog.value.set(distance - radius * 0.35, distance + radius * (0.85 - 0.3 * rise));
    // The band goes there and back over the rows, slowest at the ends; a still frame rests it at one
    // place. The progress front walks over the width from just before the left end to past the right one.
    const band = still ? 0.62 : 0.5 - 0.48 * Math.cos((time * 2 * Math.PI) / BAND_PERIOD);
    uniforms.uMotion.value.set(band, 0.13, 0.95 * (1 - 0.5 * smooth(Math.min(1, p / 0.4))), -0.15 + 1.3 * p);
    uniforms.uFocus.value.set(focus.x, focus.z, 0.92 * smooth(Math.min(1, Math.max(0, (p - 0.55) / 0.45))), still ? 0 : 0.045);
    // The key light comes from over the camera's right shoulder, so the faces turned most to the
    // camera are lit and the others clearly shaded; it leans with the pointer. The pool of light
    // sits where the pointer meets the field.
    const key = turn + 0.7 + pointer.x * 0.6;
    uniforms.uLight.value.set(Math.sin(key), 0, Math.cos(key));
    raycaster.setFromCamera(at.set(pointer.x, pointer.y), camera);
    plane.constant = -span.tall * 0.2;
    const ground = raycaster.ray.intersectPlane(plane, hit);
    spot += ((stage.pointer.active && !still ? 1 : 0) - spot) * (1 - Math.exp(-delta * 4));
    if (ground) uniforms.uSpot.value.set(THREE.MathUtils.clamp(hit.x, -WIDTH / 2, WIDTH / 2), THREE.MathUtils.clamp(hit.z, -span.depth / 2, span.depth / 2), 0, 0);
    uniforms.uSpot.value.z = spot;
  }

  stage.onFrame((time, delta) => {
    place(time, delta);
    const now = pick();
    if (now !== hovered) {
      hovered = now;
      moving = true;
      const cell = now < 0 ? -1 : grid.source[now];
      if (cell !== reported) {
        reported = cell;
        const report = cell < 0 ? null : { index: cell, row: Math.floor(cell / data.columns), column: cell % data.columns, value: data.values[cell] };
        if (typeof o.onHover === "function") o.onHover(report);
      }
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

  stage.onDestroy(() => { if (reported >= 0 && typeof o.onHover === "function") o.onHover(null); });
  setValues(o.data);
  return stage.handle({ setData: setValues });
}
