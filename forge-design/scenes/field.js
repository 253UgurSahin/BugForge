/**
 * field.js: a volume of soft points adrift in a slow current (scene kit, look levels 4 and 5).
 *
 * Tens of thousands of points form a twisting ribbon of light, a nebula with a dense core and thin,
 * dark gaps. Every position is worked out on the graphics chip from four random numbers per point
 * and the time, through curl noise (a flow that never piles up), so the processor moves nothing.
 * Depth reads as a camera lens does: points in front of the focus are large, soft and faint, points
 * behind it small and sharp. Colour runs from --color-accent to --color-accent-2 through the volume.
 * On a light page the points are ink: darker in the core, pale and soft in front, thin at the edge.
 * The pointer opens a hollow in the flow: the points part round it with a turn in its edge, and the
 * channel it leaves closes again slowly behind it.
 *
 *   import { mount } from "./scenes/field.js";
 *   const field = mount(document.querySelector(".hero-scene"), { side: "right" });
 *   field.setProgress(0.5);           // the wave sheet
 *   field.setData([0.2, 0.8, 0.5]);   // the sheet takes these heights, left to right
 *   field.destroy();                  // when the page or component goes away
 *
 * Options (all optional; the stage's own options, see stage.js, pass straight through):
 *   count      0: from the quality, 20 000 (low), 60 000 (medium) or 150 000 (high) points. A number
 *              sets it; it is clamped to 2 000 .. 300 000.
 *   formation  "cloud": the formation shown before any setProgress: "cloud", "ring", "wave", "grid".
 *   speed      1: how fast the current runs. 0 stands still; 2 is twice as fast.
 *   spread     1: how far the points stray from the shape (the width of the ribbon, the strength
 *              of the current). 0.6 is tidy, 1.6 is loose.
 *   side       "right": where the mass sits on a wide screen, away from the headline: "right",
 *              "left" or "center". On a phone the field always lies low and wide under the text.
 *   intensity  1: brightness of the points. 0.6 for a busy page, 1.4 for a dark empty one.
 *
 * setProgress(p), 0..1: the formations, each with a soft transition where the points leave one
 *   after the other from left to right and swirl a little on the way: 0 cloud, 0.25 ring, 0.5 wave
 *   sheet, 0.75 grid (a lattice of still nodes that breathes), held to 1. Feed it the scroll:
 *   field.stage.progressOf(section).
 * setData(values): numbers 0..1 (any length, resampled to 64), eased in over about a second. In the
 *   wave they ARE the relief: hills and troughs from left to right, like a tide chart. In the cloud
 *   they swell and pinch the ribbon along its length, in the ring they bulge it, in the grid they
 *   lift the columns towards the viewer. An empty list goes back to the free shape.
 * setPointer(x, y), pause(), resume(), destroy(), stage: as stage.js describes.
 *
 * Poster: give the container a child `<img data-scene-poster src="field.png" alt="">` (shown until
 * the first frame, and again when there is no WebGL), or a background image plus the rule
 * `.hero-scene[data-scene="live"] { background-image: none; }`. To make the picture, mount with
 * { still: true } in the page at the size you need and take a screenshot.
 *
 * Cost: one draw call. The vertex shader evaluates up to two formations and two steps of curl noise
 * (six simplex lookups) per point; in low quality one step (three lookups); none in the grid. 150 000
 * points are meant for a desktop graphics chip; a phone starts at 60 000 and the stage steps down
 * when slow. The fragment work is small round points with no textures.
 */
import * as THREE from "three";
import { createStage } from "./stage.js";
import { stageUniforms, common, curl, pointSize, pointSprite, grain } from "./glsl.js";

const FORMATIONS = ["cloud", "ring", "wave", "grid"];
const COUNTS = [20000, 60000, 150000];   // low, medium, high
const LATTICE = [36, 15];                // grid nodes across and up: 540 nodes
const REFERENCE = 60000;                 // the count the brightness is tuned for
const DATA = 64;                         // data values the shader reads

const vertexShader = `
${stageUniforms}
${common}
${curl}
${pointSize}
attribute vec4 aSeed;         // four random numbers per point; x follows its grid node across
uniform float uSpeed, uSpread, uSize, uAlpha, uDataOn, uFocus, uGridShift;
uniform float uWake, uWakeRadius, uSwirl;
uniform vec2 uView;           // the canvas in CSS pixels
uniform vec2 uTrail;          // where the pointer was a moment ago (-1..1): the tail of the wake
uniform vec4 uCalm;           // the headline's box on screen (-1..1): x min, x max, y min, y max
uniform float uCalmAmount;
uniform float uData[${DATA}];
varying vec3 vColor;
varying float vAlpha, vBlur, vSharp;

// More random numbers from the fourth seed, each different for k = 1, 2, 3 ...
float rnd(vec4 s, uint k) { return hashToFloat(hashU(uint(s.w * 16777215.0) + k * 0x9e3779b9u)); }
// Two random numbers added: -1..1, most often near 0 (a triangle). Shapes get a dense middle.
float tri(float a, float b) { return a + b - 1.0; }
// The data at x (0..1), a smooth curve through the values (Catmull-Rom); 0.5 while there is none.
float dataAt(float x) {
  float f = clamp(x, 0.0, 1.0) * float(${DATA - 1});
  int i = int(floor(f));
  float u = f - float(i);
  float p0 = uData[max(i - 1, 0)], p1 = uData[i], p2 = uData[min(i + 1, ${DATA - 1})], p3 = uData[min(i + 2, ${DATA - 1})];
  float d = p1 + 0.5 * u * (p2 - p0 + u * (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3 + u * (3.0 * (p1 - p2) + p3 - p0)));
  return mix(0.5, clamp(d, 0.0, 1.0), uDataOn);
}
mat3 turnX(float a) { float c = cos(a), s = sin(a); return mat3(1.0, 0.0, 0.0, 0.0, c, s, 0.0, -s, c); }
mat3 turnY(float a) { float c = cos(a), s = sin(a); return mat3(c, 0.0, -s, 0.0, 1.0, 0.0, s, 0.0, c); }

// Each formation gives a position, how visible the point is there (fade) and how close it is to
// the dense heart of the shape (core, 0..1): on a light page the edge thins out to a haze.

// CLOUD: a ribbon that twists along its length. u runs along it; the warp below makes u bunch up
// near 0.74 (the slope of u is smallest there), so the right part is dense and the left a thin tail.
vec3 cloud(vec4 s, float t, inout float fade, inout float core) {
  float u = s.x - 0.75 * sin(TAU * (s.x - 0.74)) / TAU;
  u = (u - (0.0 - 0.75 * sin(TAU * -0.74) / TAU));       // shift so u(0) = 0 and u(1) = 1
  fade = smoothstep(0.04, 0.3, u) * smoothstep(1.0, 0.9, u);
  vec3 spine = vec3(mix(-3.7, 2.35, u), 0.36 * sin(u * 4.4 - 1.3 + t * 0.05) + 0.02,
                    0.8 * sin(u * 2.7 + 0.4) - 0.8);
  float twist = u * 4.2 + t * 0.045;                       // the band turns as it runs and rolls in time
  vec3 across = vec3(0.3 * cos(u * 3.0), cos(twist), sin(twist));
  vec3 thick = vec3(0.0, -sin(twist), cos(twist));
  // A little narrower while the band faces the viewer, so the form stays inside the frame.
  float width = mix(0.12, 0.8, smoothstep(0.0, 0.75, u)) * (0.3 + 1.4 * dataAt(u)) * (1.0 - 0.25 * abs(cos(twist)));
  float a = tri(s.y, s.z);
  core = (1.0 - abs(a)) * smoothstep(0.3, 0.7, u);
  return spine + width * (across * a + thick * 0.12 * tri(rnd(s, 1u), rnd(s, 2u)));
}
// RING: a tilted ring of points that orbit slowly, thicker in a few places along the way round.
vec3 ring(vec4 s, float t, inout float fade, inout float core) {
  float angle = s.x * TAU + t * (0.05 + 0.03 * s.y);
  float body = 0.6 + 0.4 * sin(angle * 3.0 + 1.7);
  float a = tri(s.y, s.z);
  float r = 1.5 + 0.36 * body * a + 0.9 * (dataAt(fract(angle / TAU)) - 0.5);
  core = (1.0 - abs(a)) * (0.4 + 0.6 * body);
  vec3 p = vec3(cos(angle) * r, 0.16 * body * tri(rnd(s, 1u), rnd(s, 2u)), sin(angle) * r);
  return turnY(0.3) * turnX(1.22) * turnY(-0.3) * p + vec3(0.6, 0.05, -0.3);
}
// WAVE: a sheet seen from a little above. Free, it carries travelling swells; with data the values
// become its relief from left to right, and only a small swell runs over them.
vec3 wave(vec4 s, float t, inout float fade, inout float core) {
  float x = (s.x - 0.5) * 6.6 + 0.3, z = (s.y - 0.5) * 4.4;
  float swell = 0.32 * sin(x * 1.05 + z * 0.35 - t * 0.55) + 0.14 * sin(x * 2.2 - z * 1.3 - t * 0.8);
  float relief = (dataAt(s.x) - 0.5) * 2.1 * (1.0 - 0.35 * abs(s.y - 0.5) * 2.0);
  float y = mix(0.8 * swell, relief + 0.3 * swell, uDataOn) + 0.18 * snoise(vec3(x * 0.35, z * 0.35, t * 0.06));
  float edge = abs(s.y - 0.5) * 2.0;
  fade = smoothstep(0.0, 0.2, s.x) * smoothstep(1.0, 0.84, s.x) * (1.0 - 0.6 * smoothstep(0.6, 1.0, edge));
  core = 1.0 - edge * edge;
  return turnX(0.32) * vec3(x, y - 0.1, z * 0.9);
}
// GRID: a lattice like the squares of a chart. The position attribute holds the node (x and y,
// 0..1 across and up) and the point's number within it (z: 0, 1, 2 ...). Even numbers sit exactly on
// the node, in a fixed set of sizes, so every node is the same clean dot with a soft halo; odd
// numbers are strewn along the lines to the next node, a fine thread. The plane lies like a chart on
// a table: the near rows large and soft, the far rows small and sharp. Its rim dissolves (no hard
// edge, nothing near the headline), a slow swell breathes through it, and data lifts its columns.
vec3 grid(vec3 node, vec4 s, float t, inout float fade, inout float core) {
  vec2 cell = vec2(1.0 / ${LATTICE[0]}.0, 1.0 / ${LATTICE[1]}.0);
  vec2 at = node.xy;
  if (mod(node.z, 2.0) > 0.5) at += (rnd(s, 8u) < 0.62 ? vec2(cell.x, 0.0) : vec2(0.0, cell.y)) * rnd(s, 9u);
  vec2 g = at - 0.5;
  vec3 p = vec3(g.x * 5.8, g.y * 4.2, 0.0);
  p.z += 0.1 * sin(g.x * 5.0 + g.y * 4.0 - t * 0.35) + 1.0 * (dataAt(at.x) - 0.5);
  vec2 e = abs(g) * 2.0;                                    // 0 in the middle, 1 at the rim
  float rim = pow(pow(e.x, 3.0) + pow(e.y, 3.0), 1.0 / 3.0);
  fade = (1.0 - smoothstep(0.45, 0.97, rim)) * smoothstep(0.02, 0.4, at.x);
  core = 1.0 - rim;
  return turnY(0.32) * turnX(-1.05) * p + vec3(uGridShift, -0.18, -0.35);
}
vec3 formation(int k, vec4 s, float t, inout float fade, inout float core) {
  if (k == 0) return cloud(s, t, fade, core);
  if (k == 1) return ring(s, t, fade, core);
  if (k == 2) return wave(s, t, fade, core);
  return grid(position, s, t, fade, core);
}
const vec4 LOOSE = vec4(1.0, 0.35, 0.12, 0.0);   // how much each formation gives way to the current

void main() {
  vec4 s = aSeed;
  float t = uTime * uSpeed;
  // Which two formations, and how far between them. Each point sets off a little later the further
  // right it is, plus a random part, and takes 45% of the way to arrive: a staggered sweep.
  float stagePos = min(uProgress * 4.0, 3.0);
  int k = int(floor(min(stagePos, 2.999)));
  float f = stagePos - float(k);
  float delay = 0.55 * (0.7 * s.x + 0.3 * s.z);
  float local = clamp((f - delay) / 0.45, 0.0, 1.0);
  local = local * local * local * (local * (local * 6.0 - 15.0) + 10.0);   // smootherstep: still at both ends
  float fadeA = 1.0, fadeB = 1.0, coreA = 0.5, coreB = 0.5;
  vec3 a = formation(k, s, t, fadeA, coreA);
  vec3 b = local > 0.0 ? formation(k + 1, s, t, fadeB, coreB) : a;
  vec3 p = mix(a, b, local);
  float fade = mix(fadeA, fadeB, local), core = mix(coreA, coreB, local);
  float loose = mix(LOOSE[k], LOOSE[min(k + 1, 3)], local) + 0.8 * sin(PI * local);   // swirl in flight
  // How far into the grid: there every point joins a node, so the special roles below give way.
  float order = k == 2 ? local : 0.0;

  // A tenth of the points are dust: a wide, thin haze in front of and behind the shape, for depth.
  float dust = (s.w < 0.1 ? 1.0 : 0.0) * (1.0 - order);
  if (dust > 0.0) {
    vec3 haze = vec3(tri(s.x, rnd(s, 3u)) * 6.0, (s.y - 0.5) * 4.0, mix(-5.0, 3.6, s.z));
    p = mix(p, haze, dust);
    fade = mix(fade, 0.6, dust); loose = mix(loose, 0.6, dust); core = mix(core, 0.0, dust);
  }
  // One point in sixteen is gas: eight times as wide and very faint, a soft glow (or on a light
  // page a pale wash) under the shape. One in a hundred is a spark: larger and brighter.
  float gas = (s.w >= 0.1 && s.w < 0.1625 ? 1.0 : 0.0) * (1.0 - order);
  float spark = (s.w > 0.988 ? 1.0 : 0.0) * (1.0 - order);

  // The current: move the point along a curl-noise flow that itself drifts slowly. Two steps, the
  // second finer, pull the soft shape into threads with dense and empty parts.
  if (loose > 0.0005) {
    vec3 q = p * 0.42 + vec3(0.0, t * 0.022, t * 0.035);
    p += curlNoise(q) * 0.7 * loose * uSpread;
#if CURL_STEPS > 1
    p += curlNoise(p * 1.1 + vec3(t * 0.04, 0.0, 0.0)) * 0.16 * loose * uSpread;
#endif
  }

  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float depth = -mv.z;
  gl_Position = projectionMatrix * mv;
  vec2 screen = gl_Position.xy / gl_Position.w;

  // The wake, on screen and in CSS pixels. The pointer drags a channel from where it was a moment
  // ago (uTrail) to where it is; round that line each point is moved outwards so that its distance
  // r becomes sqrt(r^2 + R^2). That leaves a clean hollow of radius R and keeps the density outside
  // it the same (the area is kept, as in a real flow round an obstacle), and far points hardly move.
  // A turn that is strongest near the hollow bends the threads of the current into an eddy.
  float rimLight = 0.0;
  if (uWake > 0.001) {
    vec2 halfView = 0.5 * uView;
    vec2 here = screen * halfView, head = uPointer * halfView, tail = uTrail * halfView;
    vec2 seg = head - tail;
    float h = clamp(dot(here - tail, seg) / max(dot(seg, seg), 1.0), 0.0, 1.0);
    vec2 centre = tail + seg * h;
    float behind = (1.0 - h) * length(seg);                 // pixels back along the channel
    // Each point has its own edge, so the rim is soft; in the grid a node moves as one.
    float jitter = mix(rnd(s, 5u), hash(position.xy * 977.0), order);
    float radius = uWakeRadius * uWake * (0.8 + 0.4 * jitter) * mix(0.25, 1.0, exp(-behind / (2.2 * uWakeRadius)));
    vec2 away = here - centre;
    float r2 = dot(away, away), R2 = radius * radius;
    float angle = rnd(s, 6u) * TAU;
    vec2 dir = r2 > 0.01 ? away * inversesqrt(r2) : vec2(cos(angle), sin(angle));
    float pull = R2 / (r2 + R2 + 0.0001);                   // 1 at the centre, 1/r^2 further out
    dir = rotate2D(uSwirl * (1.0 - 0.6 * order) * pull * sqrt(pull)) * dir;
    here = centre + dir * sqrt(r2 + R2);
    screen = here / halfView;
    gl_Position.xy = screen * gl_Position.w;
    rimLight = uWake * 3.2 * R2 / (r2 + 3.2 * R2);         // a soft light round the pointer, wider than the hollow
  }

  // Depth of field: in front of the focus a point grows (blur) and dims by the same area, so it
  // keeps its light but spreads it; behind the focus it stays small and fades a little into the haze.
  float dark = uDark;
  float blur = smoothstep(0.4, 3.8, uFocus - depth);
  float far = smoothstep(uFocus + 0.5, uFocus + 5.5, depth);
  // On a light page only the far points are crisp specks; the rest are a little larger and softer,
  // so that together they lay down a tone, as ink does in water, and not a spatter of dots.
  float sharp = max(mix(smoothstep(0.0, 0.5, far), 1.0, dark), order);
  float grow = (1.0 + mix(3.2, 5.0, dark) * blur) * (1.0 + 0.45 * (1.0 - sharp));
  // In the grid a node is a stack of points of many sizes (a bright middle, a soft halo); a thread
  // point is small and faint.
  float thread = order * step(0.5, mod(position.z, 2.0));
  float rank = mod(floor(position.z * 0.5), 6.0) / 5.0;
  float gridSize = thread > 0.0 ? 0.7 : 0.5 + 3.2 * rank * rank;
  float size = uSize * mix(0.65 + 0.7 * s.z, gridSize, order) * (1.0 + 0.9 * spark) * (1.0 + 7.0 * gas);
  float pixels = pointPixels(size, depth, projectionMatrix[1][1], uResolution.y) * grow;
  float least = 1.6 * uPixelRatio;                      // smaller than this would flicker: draw it
  float alpha = uAlpha * fade / (grow * grow) * 1.8 * min(1.0, pow(pixels / least, 2.0));
  gl_PointSize = clamp(pixels, least, 64.0 * uPixelRatio);   // a cap: a huge disc costs much and adds nothing
  alpha *= 1.0 - mix(0.5, 0.65, dark) * far;
  alpha *= mix(1.0, mix(0.1, 0.55, dark), dust) * mix(1.0, mix(0.2, 0.09, dark), gas) * (1.0 + 1.2 * spark);
  alpha *= mix(0.8 + 0.2 * sin(t * 1.3 + s.w * 60.0), thread > 0.0 ? mix(0.3, 0.45, dark) : mix(0.75, 0.4, dark) / gridSize, order);   // twinkle; none in the grid
  // On a light page ink only gathers where the shape is dense: the edge thins out to a quiet haze.
  alpha *= mix(mix(0.12, 1.5, smoothstep(0.05, 0.85, core)), 1.0, max(dark, order));
  alpha *= 1.0 + rimLight * (0.8 + 5.0 * dust);          // the motes round the hollow catch the light

  // Calm behind the headline: points in its box show at a fraction (soft edges, by screen position);
  // in the grid not at all, so the lattice never reads as part of the text.
  float inBox = smoothstep(uCalm.x - 0.25, uCalm.x + 0.1, screen.x) * smoothstep(uCalm.y + 0.25, uCalm.y - 0.1, screen.x)
              * smoothstep(uCalm.z - 0.3, uCalm.z + 0.1, screen.y) * smoothstep(uCalm.w + 0.3, uCalm.w - 0.1, screen.y);
  alpha *= 1.0 - mix(uCalmAmount, 1.0, order) * inBox;
  // And the form stays whole: it thins out before it reaches the edge of the frame.
  alpha *= smoothstep(1.0, 0.82, abs(screen.y)) * smoothstep(1.0, 0.86, abs(screen.x));

  // Colour: accent on the left of the volume, second accent on the right. Each point mostly takes
  // one of the two (a random shift decides where it changes), so the middle is a mingling of both
  // colours and never the grey a half-and-half mix of two opposite colours gives.
  float hue = smoothstep(0.4, 0.6, (p.x + 3.2) / 6.4 + 0.45 * (rnd(s, 4u) - 0.5));
  vec3 color = mix(uAccent, uAccent2, hue);
  // On a light page: ink. Deeper in the core, paler (more water than ink) in front of the focus,
  // far away and in the wash of the gas.
  vec3 ink = color * mix(mix(0.72, 0.4, smoothstep(0.3, 0.95, core)), 0.55, order);
  ink = mix(mix(ink, color, gas), uBg, clamp(0.85 * sqrt(blur) + 0.3 * far + 0.3 * gas, 0.0, 0.85));   // gas: a clear, pale wash
  vColor = mix(ink, color, dark);
  vAlpha = clamp(alpha, 0.0, 1.0);
  vBlur = gas > 0.5 ? 2.0 : blur;
  vSharp = sharp;
}`;

const fragmentShader = `
${stageUniforms}
${pointSprite}
${grain}
varying vec3 vColor;
varying float vAlpha, vBlur, vSharp;
void main() {
  // In focus: a small dot with a firm middle. Out of focus: an even disc with a soft rim, as a lens
  // draws a light that is too near. Gas (2): only the soft falloff.
  float r = length(gl_PointCoord - 0.5) * 2.0;
  float disc = (1.0 - smoothstep(0.55, 1.0, r)) * 0.7 + 0.3 * softDot(gl_PointCoord);
  float spot = mix(softDot(gl_PointCoord), softDot(gl_PointCoord, 0.35), vSharp);
  float alpha = (vBlur > 1.5 ? softDot(gl_PointCoord) : mix(spot, disc, vBlur)) * vAlpha;
  if (alpha < 0.003) discard;
  gl_FragColor = vec4(vColor, alpha);
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy) * alpha;
}`;

const pick = (value, list, fallback) => (list.includes(value) ? value : fallback);
const number = (value, fallback, low, high) =>
  (Number.isFinite(Number(value)) && value !== null && value !== "" ? Math.min(high, Math.max(low, Number(value))) : fallback);

export function mount(container, options = {}) {
  const settings = {
    count: options.count ? number(options.count, 0, 2000, 300000) : 0,
    formation: pick(options.formation, FORMATIONS, "cloud"),
    speed: number(options.speed, 1, 0, 4),
    spread: number(options.spread, 1, 0.2, 2.5),
    side: pick(options.side, ["right", "left", "center"], "right"),
    intensity: number(options.intensity, 1, 0, 3),
  };
  const stage = createStage(container, {
    stillTime: 14, camera: { fov: 38, position: [0, 0.35, 7.2], lookAt: [0, 0, 0] }, ...options,
  });
  if (stage.failed) return stage.handle();

  const dataNow = new Float32Array(DATA).fill(0.5), dataGoal = new Float32Array(DATA).fill(0.5);
  const uniforms = {
    ...stage.uniforms,
    uSpeed: { value: settings.speed }, uSpread: { value: settings.spread }, uSize: { value: 0.016 },
    uAlpha: { value: 0.3 }, uDataOn: { value: 0 }, uData: { value: dataNow }, uFocus: { value: 7.2 },
    uGridShift: { value: 0.4 },
    uWake: { value: 0 }, uWakeRadius: { value: 64 }, uSwirl: { value: 0.9 },
    uView: { value: new THREE.Vector2(1, 1) }, uTrail: { value: new THREE.Vector2() },
    uCalm: { value: new THREE.Vector4(-1, -0.1, -0.7, 0.7) }, uCalmAmount: { value: 0.75 },
  };
  const material = new THREE.ShaderMaterial({
    uniforms, vertexShader, fragmentShader, defines: { CURL_STEPS: 2 },
    transparent: true, depthWrite: false, depthTest: false,
  });
  const points = new THREE.Points(new THREE.BufferGeometry(), material);
  points.frustumCulled = false;             // the vertex shader places the points: three cannot know where
  const group = new THREE.Group();
  group.add(points);
  stage.scene.add(group);

  let count = 0, fit = 1, baseSize = 0.016, dataOn = 0, dataOnGoal = 0, wake = 0;
  const trail = new THREE.Vector2(), target = new THREE.Vector2();

  // Brightness: many points share the light, few points each carry more. On a light page each
  // point is a thin wash of ink, so the shape only darkens where many of them meet.
  function setAlpha() {
    const dark = stage.tokens.dark;
    const share = Math.pow(REFERENCE / Math.max(count, 1), 0.85);
    uniforms.uAlpha.value = settings.intensity * share * (dark ? 0.2 : 0.22) * Math.min(1, 0.35 + 0.65 * fit);
    points.geometry.setDrawRange(0, count);
  }

  stage.onQuality((quality) => {
    count = Math.round(settings.count || quality.pick(...COUNTS));
    const [nx, ny] = LATTICE, nodes = nx * ny;
    const seeds = new Float32Array(count * 4), slots = new Float32Array(count * 3);
    let state = 0x2f6b1d;                   // a fixed start: the field looks the same on every load
    const random = () => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 4294967296; };
    for (let i = 0; i < count; i++) {
      // Points take the nodes in turn, so every node gets the same number of points (give or take one).
      const node = i % nodes, ix = node % nx, iy = Math.floor(node / nx);
      slots.set([(ix + 0.5) / nx, (iy + 0.5) / ny, Math.floor(i / nodes)], i * 3);
      // seed x follows the node across (still even from 0 to 1), so a point keeps its place from
      // left to right in every formation and the transitions read as a flow.
      seeds.set([(ix + random()) / nx, random(), random(), random()], i * 4);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(slots, 3));
    geometry.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 4));
    points.geometry.dispose();
    points.geometry = geometry;
    material.defines.CURL_STEPS = quality.name === "low" ? 1 : 2;
    uniforms.uSize.value = baseSize * quality.pick(1.12, 1.05, 1);   // fewer points: each a little larger
    material.needsUpdate = true;
    setAlpha();
  });

  stage.onTokens((tokens) => {
    material.blending = tokens.blending;    // light added on dark, ink laid down on light
    setAlpha();
  });

  // Composition. Wide: the mass to one side, the headline's half kept calm. Phone: low and wide,
  // under the text. In between: lower and a little smaller.
  stage.onResize((size) => {
    const view = stage.viewSize(7.2);
    const sign = settings.side === "left" ? -1 : 1, centred = settings.side === "center";
    let scale = 1;
    if (size.aspect >= 1.1) {
      scale = Math.min(1.12, view.width / 7.2);
      group.position.set(centred ? 0 : sign * view.width * 0.14, 0.05, 0);
      group.scale.set(centred ? scale : sign * scale, scale, scale);   // "left" mirrors the field
      uniforms.uCalm.value.set(sign < 0 ? 0.0 : -1, sign < 0 ? 1 : 0.0, -0.7, 0.7);
      uniforms.uCalmAmount.value = centred ? 0.45 : 0.94;
      uniforms.uGridShift.value = centred ? 0 : 0.45;
    } else {
      const phone = size.aspect < 0.8;
      scale = view.width / (phone ? 5.2 : 6.4);
      group.position.set(0, -view.height * (phone ? 0.34 : 0.26), 0);
      group.scale.setScalar(scale);
      uniforms.uCalm.value.set(-1.2, 1.2, phone ? -0.32 : -0.25, 0.75);
      uniforms.uCalmAmount.value = 0.6;
      uniforms.uGridShift.value = 0;
    }
    fit = scale;                                         // a smaller field packs its light closer: dim it
    setAlpha();
    baseSize = 0.016 * Math.sqrt(scale);                 // points shrink less than the shape
    uniforms.uSize.value = baseSize * stage.quality.pick(1.12, 1.05, 1);
    uniforms.uView.value.set(size.width, size.height);
    // The hollow the pointer opens: about 130 px across on a desktop, a little less on a phone.
    uniforms.uWakeRadius.value = Math.min(72, Math.max(40, Math.min(size.width, size.height) * 0.072));
  });

  stage.onFrame((time, delta) => {
    const p = stage.pointer, still = stage.still;
    // The wake opens while a pointer is over the field and closes slowly when it leaves. Its tail
    // follows the pointer about a second behind, so a moving pointer leaves a channel that closes.
    const wakeGoal = p.inside && !still ? 1 : 0;
    wake = still ? wakeGoal : THREE.MathUtils.damp(wake, wakeGoal, wakeGoal > wake ? 3 : 1.2, delta);
    uniforms.uWake.value = wake;
    if (still || wake < 0.001) trail.set(p.x, p.y);
    else trail.lerp(target.set(p.x, p.y), 1 - Math.exp(-delta / 0.9));
    uniforms.uTrail.value.copy(trail);
    uniforms.uSwirl.value = 1.1 + 0.35 * Math.sin(time * 0.45) + Math.min(1, p.speed * 0.5) * 0.6;
    // Data eases towards its new values in about a second.
    const k = still ? 1 : 1 - Math.exp(-delta * 2.5);
    for (let i = 0; i < DATA; i++) dataNow[i] += (dataGoal[i] - dataNow[i]) * k;
    dataOn += (dataOnGoal - dataOn) * k;
    uniforms.uDataOn.value = dataOn;
    // The whole field turns a few degrees towards the pointer and sways slowly: parallax depth.
    const sway = still ? 0 : Math.sin(time * 0.07) * 0.05;
    group.rotation.set(-p.y * 0.05, p.x * 0.1 + sway, 0);
  });

  stage.setProgress(FORMATIONS.indexOf(settings.formation) / 4);
  let shownStop = Math.round(stage.progress * 4);

  return stage.handle({
    setProgress(value) {
      stage.setProgress(value);
      const stop = Math.round(stage.progress * 4);
      if (stop !== shownStop) { shownStop = stop; stage.invalidate(); }   // a still frame shows the new formation
    },
    setData(values) {
      const list = Array.from(values || [], Number).filter(Number.isFinite);
      dataOnGoal = list.length ? 1 : 0;
      for (let i = 0; i < DATA && list.length; i++) {
        const at = (i / (DATA - 1)) * (list.length - 1), j = Math.floor(at), f = at - j;
        const v = list[j] * (1 - f) + (list[Math.min(j + 1, list.length - 1)] * f);
        dataGoal[i] = Math.min(1, Math.max(0, v));
      }
      stage.invalidate();
    },
  });
}
