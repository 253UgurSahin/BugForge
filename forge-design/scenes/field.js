/**
 * field.js: a volume of soft points adrift in a slow current (scene kit, look levels 4 and 5).
 *
 * Tens of thousands of points form a twisting ribbon of light, a nebula with a dense core and thin,
 * dark gaps. Every position is worked out on the graphics chip from four random numbers per point
 * and the time, through curl noise (a flow that never piles up), so the processor moves nothing.
 * Depth reads as a camera lens does: points in front of the focus are large, soft and faint, points
 * behind it small and sharp. Colour runs from --color-accent to --color-accent-2 through the volume.
 * The pointer leaves a wake: points part round it and close again behind it.
 *
 *   import { mount } from "./scenes/field.js";
 *   const field = mount(document.querySelector(".hero-scene"), { side: "right" });
 *   field.setProgress(0.5);           // the wave sheet
 *   field.setData([0.2, 0.8, 0.5]);   // the wave follows these heights, left to right
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
 *   sheet, 0.75 grid, held to 1. Feed it the scroll: field.stage.progressOf(section).
 * setData(values): numbers 0..1 (any length, resampled to 32): the height of the wave from left to
 *   right, and the swell of the ribbon along its length. An empty list goes back to the free shape.
 * setPointer(x, y), pause(), resume(), destroy(), stage: as stage.js describes.
 *
 * Poster: give the container a child `<img data-scene-poster src="field.png" alt="">` (shown until
 * the first frame, and again when there is no WebGL), or a background image plus the rule
 * `.hero-scene[data-scene="live"] { background-image: none; }`. To make the picture, mount with
 * { still: true } in the page at the size you need and take a screenshot.
 *
 * Cost: one draw call. The vertex shader evaluates up to two formations and two steps of curl noise
 * (six simplex lookups) per point; in low quality one step (three lookups). 150 000 points are
 * meant for a desktop graphics chip; a phone starts at 60 000 and the stage steps down when slow. The fragment work is small round
 * points with no textures. On a light page only 55% of the points are drawn, with no gas or soft discs.
 */
import * as THREE from "three";
import { createStage } from "./stage.js";
import { stageUniforms, common, curl, pointSize, pointSprite, grain } from "./glsl.js";

const FORMATIONS = ["cloud", "ring", "wave", "grid"];
const COUNTS = [20000, 60000, 150000];   // low, medium, high
const LATTICE = [44, 15, 2];             // grid sites across, up and deep: 1 320 places
const REFERENCE = 60000;                 // the count the brightness is tuned for
const DATA = 32;                         // data values the shader reads

const vertexShader = `
${stageUniforms}
${common}
${curl}
${pointSize}
attribute vec4 aSeed;         // four random numbers per point; x and y are tied to its grid site
uniform float uSpeed, uSpread, uSize, uAlpha, uWake, uDataOn, uTanHalf, uFocus;
uniform vec2 uDrift;          // the direction the pointer moves in, for the wake
uniform vec4 uCalm;           // the headline's box on screen (-1..1): x min, x max, y min, y max
uniform float uCalmAmount;
uniform float uData[${DATA}];
varying vec3 vColor;
varying float vAlpha, vBlur;

// More random numbers from the fourth seed, each different for k = 1, 2, 3 ...
float rnd(vec4 s, uint k) { return hashToFloat(hashU(uint(s.w * 16777215.0) + k * 0x9e3779b9u)); }
// Two random numbers added: -1..1, most often near 0 (a triangle). Shapes get a dense middle.
float tri(float a, float b) { return a + b - 1.0; }
float dataAt(float x) {
  float f = clamp(x, 0.0, 1.0) * float(${DATA - 1});
  int i = int(f);
  float d = mix(uData[i], uData[min(i + 1, ${DATA - 1})], f - float(i));
  return mix(0.5, d, uDataOn);
}
mat3 turnX(float a) { float c = cos(a), s = sin(a); return mat3(1.0, 0.0, 0.0, 0.0, c, s, 0.0, -s, c); }
mat3 turnY(float a) { float c = cos(a), s = sin(a); return mat3(c, 0.0, -s, 0.0, 1.0, 0.0, s, 0.0, c); }

// CLOUD: a ribbon that twists along its length. u runs along it; the warp below makes u bunch up
// near 0.74 (the slope of u is smallest there), so the right part is dense and the left a thin tail.
vec3 cloud(vec4 s, float t, inout float fade) {
  float u = s.x - 0.75 * sin(TAU * (s.x - 0.74)) / TAU;
  u = (u - (0.0 - 0.75 * sin(TAU * -0.74) / TAU));       // shift so u(0) = 0 and u(1) = 1
  fade = smoothstep(0.0, 0.16, u) * smoothstep(1.0, 0.9, u);
  vec3 spine = vec3(mix(-3.9, 2.6, u), 0.38 * sin(u * 4.4 - 1.3 + t * 0.05) + 0.05,
                    0.8 * sin(u * 2.7 + 0.4) - 0.8);
  float twist = u * 4.2 + t * 0.045;                       // the band turns as it runs and rolls in time
  vec3 across = vec3(0.3 * cos(u * 3.0), cos(twist), sin(twist));
  vec3 thick = vec3(0.0, -sin(twist), cos(twist));
  float width = mix(0.12, 0.95, smoothstep(0.0, 0.75, u)) * (0.55 + 0.9 * dataAt(u));
  return spine + width * (across * tri(s.y, s.z) + thick * 0.12 * tri(rnd(s, 1u), rnd(s, 2u)));
}
// RING: a tilted ring of points that orbit slowly, thicker in a few places along the way round.
vec3 ring(vec4 s, float t, inout float fade) {
  float angle = s.x * TAU + t * (0.05 + 0.03 * s.y);
  float body = 0.6 + 0.4 * sin(angle * 3.0 + 1.7);
  float r = 1.5 + 0.36 * body * tri(s.y, s.z);
  vec3 p = vec3(cos(angle) * r, 0.16 * body * tri(rnd(s, 1u), rnd(s, 2u)), sin(angle) * r);
  return turnY(0.3) * turnX(1.22) * turnY(-0.3) * p + vec3(0.6, 0.05, -0.3);
}
// WAVE: a sheet seen from a little above; travelling swells whose height follows the data.
vec3 wave(vec4 s, float t, inout float fade) {
  float x = (s.x - 0.5) * 6.6 + 0.3, z = (s.y - 0.5) * 4.4;
  float amp = 0.25 + 1.1 * dataAt(s.x);
  float y = amp * (0.32 * sin(x * 1.05 + z * 0.35 - t * 0.55) + 0.14 * sin(x * 2.2 - z * 1.3 - t * 0.8))
          + 0.18 * snoise(vec3(x * 0.35, z * 0.35, t * 0.06));
  fade = smoothstep(0.0, 0.2, s.x) * smoothstep(1.0, 0.92, s.x) * (1.0 - 0.6 * smoothstep(0.6, 1.0, abs(s.y - 0.5) * 2.0));
  return turnX(0.32) * vec3(x, y - 0.1, z * 0.9);
}
// GRID: every point belongs to a lattice site (the position attribute) and sits close round it,
// so each site reads as one soft dot. A slow ripple runs through the rows.
vec3 grid(vec3 site, vec4 s, float t, inout float fade) {
  vec3 p = site * vec3(2.9, 1.15, 0.3) + 0.004 * vec3(tri(s.z, rnd(s, 1u)), tri(rnd(s, 2u), rnd(s, 3u)), 0.0);
  p.y += 0.06 * sin(site.x * 4.0 + site.z * 3.0 - t * 0.6);
  return turnY(-0.5) * turnX(0.12) * p + vec3(0.25, 0.0, -0.9);
}
vec3 formation(int k, vec4 s, float t, inout float fade) {
  if (k == 0) return cloud(s, t, fade);
  if (k == 1) return ring(s, t, fade);
  if (k == 2) return wave(s, t, fade);
  return grid(position, s, t, fade);
}
const vec4 LOOSE = vec4(1.0, 0.35, 0.12, 0.012);   // how much each formation gives way to the current

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
  float fadeA = 1.0, fadeB = 1.0;
  vec3 a = formation(k, s, t, fadeA);
  vec3 b = local > 0.0 ? formation(k + 1, s, t, fadeB) : a;
  vec3 p = mix(a, b, local);
  float fade = mix(fadeA, fadeB, local);
  float loose = mix(LOOSE[k], LOOSE[min(k + 1, 3)], local) + 0.8 * sin(PI * local);   // swirl in flight

  // A tenth of the points are dust: a wide, thin haze in front of and behind the shape, for depth.
  bool dust = s.w < 0.1;
  if (dust) {
    p = vec3(tri(s.x, rnd(s, 3u)) * 6.0, (s.y - 0.5) * 4.0, mix(-5.0, 3.6, s.z));
    fade = 0.6; loose = 0.6;
  }

  // The current: move the point along a curl-noise flow that itself drifts slowly. Two steps, the
  // second finer, pull the soft shape into threads with dense and empty parts.
  vec3 q = p * 0.42 + vec3(0.0, t * 0.022, t * 0.035);
  p += curlNoise(q) * 0.7 * loose * uSpread;
#if CURL_STEPS > 1
  p += curlNoise(p * 1.1 + vec3(t * 0.04, 0.0, 0.0)) * 0.16 * loose * uSpread;
#endif

  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float depth = -mv.z;
  // The wake. Compare the point's direction from the camera with the pointer's: close to the
  // pointer's line of sight, points are pushed out sideways and a little round (a swirl), so the
  // flow parts round it at every depth. uDrift pushes more on the side the pointer moves to.
  vec2 ray = vec2(uPointer.x * uTanHalf * uResolution.x / uResolution.y, uPointer.y * uTanHalf);
  vec2 d = mv.xy / depth - ray;
  // The push grows with the distance from the pointer's line (d itself, not its direction), so the
  // flow spreads and turns there, thinner in the middle, but never leaves a hole.
  float near = exp(-dot(d, d) / 0.012) * uWake;
  mv.xy += (d * 0.9 + vec2(-d.y, d.x) * 1.1 + uDrift * 0.03) * near * depth;

  gl_Position = projectionMatrix * mv;

  // Depth of field: in front of the focus a point grows (blur) and dims by the same area, so it
  // keeps its light but spreads it; behind the focus it stays small and fades a little into the haze.
  float blur = smoothstep(0.4, 3.8, uFocus - depth);
  float grow = 1.0 + mix(1.2, 5.0, uDark) * blur;   // on a light page a big soft disc reads as a smudge
  // One point in sixteen is gas: eight times as wide and very faint. Together they lay a soft glow
  // under the shape, so it reads as a body of light and not as loose grains, even with few points.
  bool gas = !dust && s.w < 0.1625;
  float size = uSize * (0.65 + 0.7 * s.z) * (s.w > 0.988 ? 1.9 : 1.0) * (gas ? 8.0 : 1.0);
  float pixels = pointPixels(size, depth, projectionMatrix[1][1], uResolution.y) * grow;
  float least = 1.6 * uPixelRatio;                      // smaller than this would flicker: draw it
  float alpha = uAlpha * fade / (grow * grow) * 1.8 * min(1.0, pow(pixels / least, 2.0));
  gl_PointSize = max(pixels, least);
  alpha *= 1.0 - 0.65 * smoothstep(uFocus + 0.5, uFocus + 5.5, depth);
  alpha *= (dust ? mix(0.15, 0.55, uDark) : 1.0) * (gas ? 0.09 * uDark : 1.0) * (s.w > 0.988 ? 2.2 : 1.0) * (0.8 + 0.2 * sin(t * 1.3 + s.w * 60.0));

  // Calm behind the headline: points in its box show at a quarter (soft edges, by screen position).
  vec2 screen = gl_Position.xy / gl_Position.w;
  float inBox = smoothstep(uCalm.x - 0.25, uCalm.x + 0.1, screen.x) * smoothstep(uCalm.y + 0.25, uCalm.y - 0.1, screen.x)
              * smoothstep(uCalm.z - 0.3, uCalm.z + 0.1, screen.y) * smoothstep(uCalm.w + 0.3, uCalm.w - 0.1, screen.y);
  alpha *= 1.0 - uCalmAmount * inBox;

  // Colour: accent on the left of the volume, second accent on the right. Each point mostly takes
  // one of the two (a random shift decides where it changes), so the middle is a mingling of both
  // colours and never the grey a half-and-half mix of two opposite colours gives. On a light page
  // the ink is a shade deeper (0.62 in linear light is about 85% of the lightness).
  float hue = smoothstep(0.4, 0.6, (p.x + 3.2) / 6.4 + 0.45 * (rnd(s, 4u) - 0.5));
  vColor = mix(uAccent, uAccent2, hue) * mix(0.62, 1.0, uDark);
  vAlpha = clamp(alpha, 0.0, 1.0);
  vBlur = gas ? 2.0 : blur * uDark;   // on a light page no soft discs and no gas: they read as smudges
}`;

const fragmentShader = `
${stageUniforms}
${pointSprite}
${grain}
varying vec3 vColor;
varying float vAlpha, vBlur;
void main() {
  // In focus: a small dot with a firm middle. Out of focus: an even disc with a soft rim, as a lens
  // draws a light that is too near.
  float r = length(gl_PointCoord - 0.5) * 2.0;
  float disc = (1.0 - smoothstep(0.62, 1.0, r)) * 0.75 + 0.25 * softDot(gl_PointCoord);
  float alpha = (vBlur > 1.5 ? softDot(gl_PointCoord) : mix(softDot(gl_PointCoord, 0.35), disc, vBlur)) * vAlpha;   // 2: gas
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
    uAlpha: { value: 0.3 }, uWake: { value: 0 }, uDrift: { value: new THREE.Vector2() },
    uDataOn: { value: 0 }, uData: { value: dataNow }, uFocus: { value: 7.2 },
    uTanHalf: { value: Math.tan((stage.camera.fov * Math.PI) / 360) },
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
  const drift = new THREE.Vector2(), lastPointer = new THREE.Vector2(), moved = new THREE.Vector2();

  // Brightness: many points share the light, few points each carry more; the light page less again.
  function setAlpha() {
    const dark = stage.tokens.dark;
    const share = Math.pow(REFERENCE / Math.max(count, 1), 0.85);
    uniforms.uAlpha.value = settings.intensity * share * (dark ? 0.2 : 0.4) * Math.min(1, 0.35 + 0.65 * fit);
    points.geometry.setDrawRange(0, dark ? count : Math.round(count * 0.55));
  }

  stage.onQuality((quality) => {
    count = Math.round(settings.count || quality.pick(...COUNTS));
    const [nx, ny, nz] = LATTICE, sites = nx * ny * nz;
    const seeds = new Float32Array(count * 4), slots = new Float32Array(count * 3);
    let state = 0x2f6b1d;                   // a fixed start: the field looks the same on every load
    const random = () => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 4294967296; };
    for (let i = 0; i < count; i++) {
      // Points take the sites in turn, so any first part of the list (the light page) fills them all.
      const site = i % sites, ix = site % nx, iy = Math.floor(site / nx) % ny, iz = Math.floor(site / (nx * ny));
      slots.set([((ix + 0.5) / nx) * 2 - 1, ((iy + 0.5) / ny) * 2 - 1, ((iz + 0.5) / nz) * 2 - 1], i * 3);
      // seed x and y follow the site across and in depth (still even from 0 to 1), so a point
      // keeps its place from left to right in every formation and the transitions read as a flow.
      seeds.set([(ix + random()) / nx, (iz + random()) / nz, random(), random()], i * 4);
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
      scale = Math.min(1.15, view.width / 7.2);
      group.position.set(centred ? 0 : sign * view.width * 0.14, 0.05, 0);
      group.scale.set(centred ? scale : sign * scale, scale, scale);   // "left" mirrors the field
      uniforms.uCalm.value.set(sign < 0 ? 0.0 : -1, sign < 0 ? 1 : 0.0, -0.7, 0.7);
      uniforms.uCalmAmount.value = centred ? 0.45 : 0.85;
    } else {
      const phone = size.aspect < 0.8;
      scale = view.width / (phone ? 5.2 : 6.4);
      group.position.set(0, -view.height * (phone ? 0.34 : 0.26), 0);
      group.scale.setScalar(scale);
      uniforms.uCalm.value.set(-1.2, 1.2, phone ? -0.32 : -0.25, 0.75);
      uniforms.uCalmAmount.value = 0.6;
    }
    fit = scale;                                         // a smaller field packs its light closer: dim it
    setAlpha();
    baseSize = 0.016 * Math.sqrt(scale);                 // points shrink less than the shape
    uniforms.uSize.value = baseSize * stage.quality.pick(1.12, 1.05, 1);
  });

  stage.onFrame((time, delta) => {
    const p = stage.pointer, still = stage.still;
    // The wake fades in while a pointer is over the field and grows a little with its speed.
    const wakeGoal = p.inside && !still ? Math.min(1, 0.6 + 0.4 * p.speed) : 0;
    wake = still ? wakeGoal : THREE.MathUtils.damp(wake, wakeGoal, 2.5, delta);
    uniforms.uWake.value = wake;
    moved.set(p.x - lastPointer.x, p.y - lastPointer.y).clampLength(0, 0.05).multiplyScalar(20);   // which way, 0..1
    drift.lerp(moved, still ? 1 : 1 - Math.exp(-delta * 3));
    lastPointer.set(p.x, p.y);
    uniforms.uDrift.value.copy(still ? drift.set(0, 0) : drift);
    // Data eases towards its new values in about a second.
    const k = still ? 1 : 1 - Math.exp(-delta * 2.5);
    for (let i = 0; i < DATA; i++) dataNow[i] += (dataGoal[i] - dataNow[i]) * k;
    dataOn += (dataOnGoal - dataOn) * k;
    uniforms.uDataOn.value = dataOn;
    // The whole field turns a few degrees towards the pointer and sways slowly: parallax depth.
    const sway = still ? 0 : Math.sin(time * 0.07) * 0.05;
    group.rotation.set(-p.y * 0.07, p.x * 0.14 + sway, 0);
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
