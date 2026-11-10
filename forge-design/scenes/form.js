/**
 * form.js: a sculptural object made of light, for a hero (look level 4 and 5).
 *
 * Families of thin luminous strands run along a tube that follows a knot from the torus family,
 * and a slow field of noise bends the whole thing so it never reads as a textbook knot. It breathes
 * (one breath in about 8 seconds), turns once in about 75 seconds and leans a few degrees toward
 * the pointer. A few pulses of light run along strands and a handful of nodes glow where strands
 * cross. On a dark page it glows (additive light); on a light page it becomes an ink drawing.
 *
 *   import { mount } from "./scenes/form.js";
 *   const form = mount(document.querySelector(".hero-scene"), { side: "right" });
 *   form.setProgress(0.5);         // 0 the first shape, 0.5 the second, 1 the third, morphing between
 *   form.setData([0.2, 0.9, 0.4]); // the strands swell where the values are high, along the form
 *   form.destroy();
 *
 * Options (all optional; stage.js options such as quality pass straight through):
 *   side       "right" (default), "left" or "centre". On a wide screen the form sits on that side and
 *              runs off the edge, leaving the other side calm for a headline. On a phone (narrow
 *              container) it always sits low and large behind the text, and dimmer.
 *   scale      1. Size of the form against that layout.
 *   strands    160. Strands at high quality; medium draws 70 percent, low 40 percent.
 *   speed      1. Speed of turning, breathing and pulses. 0 holds the motion (the pointer still works).
 *   seed       1. Any number: another bend of the noise, another layout of strands and nodes.
 *   shapes     ["ring", "knot", "coil"]. The three shapes setProgress walks through, picked from
 *              "ring" (an open, twisted band), "knot" (a trefoil rope), "coil" (a tight coil round a
 *              ring), "star" (a five-lobed knot) and "bloom" (three wide lobes).
 *   intensity  1. Brightness on dark, ink strength on light.
 *   stillTime  6. The moment the reduced-motion still shows.
 *
 * setProgress(p)    0..1, eased: morphs through the three shapes (pair it with stage.progressOf).
 * setData(values)   a list of numbers 0..1 spread along the form, start to end of the loop: the tube
 *                   swells and brightens where they are high; [] or null takes it back. Eased.
 * setPointer(x, y)  -1..1, y up: lean toward that point as the real pointer would.
 * pause(), resume(), destroy(), stage: as stage.js describes.
 *
 * Poster: put <img data-scene-poster src="form-poster.webp" alt=""> in the container; it shows
 * until the first frame and again when WebGL is missing. Make it by mounting with { still: true }
 * at the size of the hero and taking a screenshot: that is the reduced-motion frame.
 *
 * Cost: one draw call of thin strips (high: 160 strands x 340 segments, about 110k vertices, each
 * reading 3D simplex noise twice) and one of a dozen points. Low: 64 x 150. No textures, no
 * render targets. Pauses itself off screen (stage.js).
 */
import * as THREE from "three";
import { createStage } from "./stage.js";
import { stageUniforms, common, simplex3D, grain } from "./glsl.js";

// A knot from the torus family: p turns round the axis while it winds q times round a tube of
// radius r at distance R. tube: [width, height, turns of the bundle per loop, turns of the band].
// bend: how much the noise may bend it (a tight coil keeps its rhythm with less).
// tilt: how far (radians) the form leans back from facing the camera, so each shape shows its best side.
const SHAPES = {
  ring: { knot: [1, 2, 1.4, 0.14], tube: [0.34, 0.05, 0, 0.5], bend: 1.0, tilt: 1.0 },
  knot: { knot: [2, 3, 0.98, 0.46], tube: [0.25, 0.25, 2, 0], bend: 1.0, tilt: 0.45 },
  coil: { knot: [1, 15, 1.25, 0.24], tube: [0.07, 0.07, 1, 0.35], bend: 0.35, tilt: 1.0 },
  star: { knot: [2, 5, 1.0, 0.42], tube: [0.17, 0.17, 3, 0], bend: 0.8, tilt: 0.5 },
  bloom: { knot: [3, 2, 0.92, 0.56], tube: [0.22, 0.22, 1, 0], bend: 1.0, tilt: 0.6 },
};
const DATA_SLOTS = 32;

// The surface, shared by the strands and the nodes: a point on strand `strand` at s (loop fraction).
const surface = `
${stageUniforms}
${common}
${simplex3D}
uniform vec4 uKnot[3];
uniform vec4 uTube[3];
uniform vec3 uWeights;   // how much of each shape: they add up to 1
uniform float uBend;
uniform float uData[${DATA_SLOTS}];
uniform float uSwell;    // 0 without data
uniform float uClock;    // seconds times speed
uniform vec3 uSeed;
float dataAt(float s) {
  float x = fract(s) * float(${DATA_SLOTS});
  int i = int(floor(x));
  return mix(uData[i], uData[(i + 1) % ${DATA_SLOTS}], fract(x));
}
// The noise is read on a small circle that goes round once per breath (8 seconds), so the bending
// moves and comes back to where it was.
vec3 noiseAt() {
  float phase = uClock * TAU / 8.0;
  return uSeed + 0.42 * vec3(cos(phase), sin(phase), 0.0);
}
// strand: x angle round the tube, y depth (1 = on the skin), z extra turns per loop, w its seed.
// skin returns the direction from the tube's core line to the point: the surface's normal.
vec3 strandPoint(float s, vec4 strand, out vec3 skin) {
  float t = s * TAU;
  vec3 c = vec3(0.0), v = vec3(0.0);
  vec4 tube = vec4(0.0);
  for (int i = 0; i < 3; i++) {
    // The knot's core line and its direction (the derivative, worked out by hand), mixed by weight.
    vec4 k = uKnot[i];
    float w = uWeights[i], a = k.x * t, b = k.y * t, ring = k.z + k.w * cos(b);
    c += w * vec3(ring * cos(a), ring * sin(a), k.w * sin(b));
    v += w * vec3(-k.w * k.y * sin(b) * cos(a) - ring * k.x * sin(a),
                  -k.w * k.y * sin(b) * sin(a) + ring * k.x * cos(a), k.w * k.y * cos(b));
    tube += w * uTube[i];
  }
  // A frame that travels with the line: along it (T), away from the axis (N) and across (B).
  vec3 T = normalize(v);
  vec3 B = normalize(cross(T, normalize(vec3(c.xy, 0.0))));
  vec3 N = cross(B, T);
  // Low-frequency noise, read once at the core line, so a whole section moves together and the
  // tube bends but stays a tube: its value pushes the line outward or in, one slope pushes it out
  // of its plane, another swells the section.
  vec4 n = snoiseGrad(c * 0.34 + noiseAt());
  c += (N * n.x * 0.2 + B * n.w * 0.035) * uBend;
  // Breathing: everything swells a little, once every 8 seconds; data swells it where it is high.
  float breath = sin(uClock * TAU / 8.0);
  float swell = (1.0 + 0.07 * breath + 0.09 * n.z) * (1.0 + uSwell * (dataAt(s) - 0.5) * 1.3);
  // Round the tube: the strand's angle grows along the loop, so it winds as a helix. The section is
  // an ellipse (a flat band for the ring) that may itself turn along the loop.
  float angle = strand.x + t * (tube.z + strand.z);
  vec2 e = rotate2D(t * tube.w) * vec2(cos(angle) * tube.x, sin(angle) * tube.y) * strand.y * swell;
  skin = normalize(N * e.x + B * e.y + T * 1e-5);
  return c + N * e.x + B * e.y;
}
`;

const strandVertex = `
${surface}
attribute vec2 aLocal;   // x: 0..1 along the strand, y: -1 or 1, the two edges of the ribbon
attribute vec4 aStrand;
attribute vec3 aSpan;    // where on the loop it starts, how much of the loop it covers, its colour
uniform float uWidth;    // world units
uniform vec2 uFade;      // depth where the form is nearest and farthest
uniform float uIntensity;
uniform float uHalo;     // pixels of soft glow on each side, on dark only
varying float vAcross;   // pixels from the middle of the ribbon
varying float vCore;     // half the line's width in pixels
varying float vAlpha;
varying float vPulse;
varying float vKind;
void main() {
  float s = aSpan.x + aLocal.x * aSpan.y;
  vec3 skin, unused;
  vec3 p0 = strandPoint(s, aStrand, skin);
  vec3 p1 = strandPoint(s + 0.002, aStrand, unused);
  vec4 m0 = modelViewMatrix * vec4(p0, 1.0);
  vec4 c0 = projectionMatrix * m0;
  vec4 c1 = projectionMatrix * (modelViewMatrix * vec4(p1, 1.0));
  // The ribbon faces the camera: push the two edges apart across the line's direction on screen.
  vec2 along = (c1.xy / c1.w - c0.xy / c0.w) * uResolution;
  vec2 across = normalize(vec2(-along.y, along.x) + 1e-6);
  // A pulse: a short bright stretch that runs the strand's length every few seconds.
  float pulse = 0.0;
  if (fract(aStrand.w * 7.31) < 0.075) {
    float at = fract(uClock * 0.11 + aStrand.w * 3.7) * 1.4 - 0.2;
    pulse = exp(-pow((aLocal.x - at) / 0.035, 2.0));
  }
  // Ends taper; data and pulses widen. Width follows depth like a real thread, but never under
  // about a pixel: a thinner line would flicker, so it gets fainter instead.
  float depth = -m0.z;
  float taper = sqrt(sin(PI * aLocal.x));
  float swell = 1.0 + uSwell * (dataAt(s) - 0.5) * 1.6;
  float pixels = uWidth * swell * (1.0 + 1.2 * pulse) * taper * projectionMatrix[1][1] * uResolution.y * 0.5 / depth;
  float core = max(pixels, uPixelRatio);
  float extent = core * 0.5 + uPixelRatio + uDark * uHalo * 1.8 * uPixelRatio; // room for the soft edge and glow
  c0.xy += across * aLocal.y * extent * 2.0 / uResolution * c0.w;
  gl_Position = c0;
  vAcross = aLocal.y * extent;
  vCore = core * 0.5;
  // Brighter where the surface turns away (its normal across the view): the rims of the tube.
  vec3 normal = normalize(normalMatrix * skin);
  float rim = 1.0 - abs(dot(normal, normalize(-m0.xyz)));
  float far = smoothstep(uFade.x, uFade.y, depth);   // 0 in front, 1 at the back
  vAlpha = uIntensity * (pixels / core) * mix(0.3, 1.0, rim * rim) * mix(1.0, 0.18, far)
         * (0.6 + 0.4 * swell) * smoothstep(0.0, 0.18, aLocal.x) * smoothstep(1.0, 0.82, aLocal.x);
  vPulse = pulse * (1.0 - 0.6 * far);
  vKind = aSpan.z;
}`;

const strandFragment = `
${stageUniforms}
${grain}
uniform float uHalo;
uniform vec4 uCalm;      // xy: toward where the form sits on screen, z..w: the fade from calm to full
varying float vAcross;
varying float vCore;
varying float vAlpha;
varying float vPulse;
varying float vKind;
void main() {
  float d = abs(vAcross);
  float lineCover = 1.0 - smoothstep(vCore - 0.5 * uPixelRatio, vCore + 0.5 * uPixelRatio, d);
  float glow = uDark * 0.16 * exp(-pow(d / (max(uHalo, 0.01) * uPixelRatio), 2.0)) * step(0.01, uHalo);
  vec2 uv = gl_FragCoord.xy / uResolution - 0.5;
  float calm = mix(0.08, 1.0, smoothstep(uCalm.z, uCalm.w, dot(uv, uCalm.xy) + 0.5));
  vec3 ink = vKind > 0.5 ? uAccent2 : uAccent;
  // On dark, a pulse runs white-hot toward the text colour; on light it is a darker, denser stroke.
  vec3 color = mix(ink, mix(ink, uText, mix(0.75, 0.55, uDark)), vPulse);
  float alpha = (lineCover + glow) * vAlpha * calm * (1.0 + vPulse * mix(1.2, 3.0, uDark)) * (1.0 + vKind * 0.5);
  gl_FragColor = vec4(color, min(alpha, 1.0));
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy) * gl_FragColor.a;
}`;

const nodeVertex = `
${surface}
attribute vec4 aStrand;
attribute vec2 aAt;      // x: where on the loop, y: its own seed
uniform vec2 uFade;
uniform float uNodeSize;
varying float vAlpha;
void main() {
  vec3 skin;
  vec4 m = modelViewMatrix * vec4(strandPoint(aAt.x, aStrand, skin), 1.0);
  gl_Position = projectionMatrix * m;
  float twinkle = 0.75 + 0.25 * sin(uClock * 0.9 + aAt.y * 40.0);
  vAlpha = twinkle * mix(1.0, 0.25, smoothstep(uFade.x, uFade.y, -m.z));
  gl_PointSize = uNodeSize * uPixelRatio * (0.8 + 0.4 * aAt.y) * 7.0 / -m.z;
}`;

const nodeFragment = `
${stageUniforms}
${grain}
uniform vec4 uCalm;
uniform float uIntensity;
varying float vAlpha;
void main() {
  // Dark: a hot point in a soft glow. Light: an ink dot inside a fine ring.
  vec2 q = gl_PointCoord - 0.5;
  float d = length(q) * 2.0, edge = fwidth(d);
  float ring = 1.0 - smoothstep(0.0, edge * 1.5, abs(d - 0.45) - 0.025);
  float inkDot = 1.0 - smoothstep(0.13 - edge, 0.13 + edge, d);
  float light = 1.0 - smoothstep(0.1 - edge, 0.1 + edge, d) + 0.6 * exp(-d * d * 18.0) + 0.3 * exp(-d * d * 5.0);
  vec2 uv = gl_FragCoord.xy / uResolution - 0.5;
  float calm = mix(0.08, 1.0, smoothstep(uCalm.z, uCalm.w, dot(uv, uCalm.xy) + 0.5));
  float alpha = mix(max(inkDot, ring * 0.75), light * (1.0 - smoothstep(0.85, 1.0, d)), uDark)
              * vAlpha * calm * min(uIntensity * 2.0, 1.0);
  vec3 color = mix(mix(uAccent, uText, 0.5), mix(uAccent, uText, 0.45), uDark);
  gl_FragColor = vec4(color, alpha);
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy) * alpha;
}`;

/** A small seeded random generator, so a seed always gives the same form. */
function random(seed) {
  let state = (Math.floor(Math.abs(seed) * 9973) + 0x6d2b79f5) >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let x = Math.imul(state ^ (state >>> 15), 1 | state);
    x ^= x + Math.imul(x ^ (x >>> 7), 61 | x);
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

/** The strands: two families on the skin that wind opposite ways, and a few inside. */
function makeStrands(count, seed) {
  const rand = random(seed);
  const list = [];
  const families = [Math.round(count * 0.64), Math.round(count * 0.22)];
  for (let i = 0; i < count; i++) {
    const family = i < families[0] ? 0 : i < families[0] + families[1] ? 1 : 2;
    const n = family < 2 ? families[family] : 1;
    const index = family === 0 ? i : i - families[0];
    const angle = family < 2 ? (index / n) * Math.PI * 2 + (rand() - 0.5) * 0.25 : rand() * Math.PI * 2;
    const depth = family < 2 ? 1 : 0.3 + rand() * 0.5;
    const turns = family === 0 ? 0.8 + rand() * 0.4 : family === 1 ? -1.1 - rand() * 0.3 : (rand() - 0.5) * 1.2;
    // Most strands cover most of the loop; a few short ones break the regularity.
    const length = rand() < 0.2 ? 0.25 + rand() * 0.3 : 0.6 + rand() * 0.38;
    list.push({ family, angle, depth, turns, seed: rand(), start: rand(), length, kind: rand() < 1 / 7 ? 1 : 0 });
  }
  return list;
}

/** Nodes where a strand of one family crosses one of the other: same place on the loop, same angle. */
function makeNodes(strands, wanted, seed) {
  const rand = random(seed + 17);
  const a = strands.filter((s) => s.family === 0), b = strands.filter((s) => s.family === 1);
  const nodes = [];
  for (let tries = 0; tries < 400 && nodes.length < wanted && a.length && b.length; tries++) {
    const i = a[Math.floor(rand() * a.length)], j = b[Math.floor(rand() * b.length)];
    // angle_i + 2 pi s turns_i = angle_j + 2 pi s turns_j + 2 pi m, solved for s.
    const m = Math.floor(rand() * 4) - 1;
    const s = (m - (i.angle - j.angle) / (Math.PI * 2)) / (i.turns - j.turns);
    const inside = (k) => s > k.start + k.length * 0.15 && s < k.start + k.length * 0.85;
    if (!inside(i) || !inside(j)) continue;
    if (nodes.some((node) => Math.abs(((node.s - s) % 1 + 1.5) % 1 - 0.5) < 0.05)) continue; // spread them out
    nodes.push({ strand: i, s, seed: rand() });
  }
  return nodes;
}

function buildStrandGeometry(strands, segments) {
  const verts = strands.length * (segments + 1) * 2;
  const local = new Float32Array(verts * 2), strand = new Float32Array(verts * 4), span = new Float32Array(verts * 3);
  const index = [];
  let v = 0;
  strands.forEach((s, k) => {
    for (let j = 0; j <= segments; j++) {
      for (const side of [-1, 1]) {
        local.set([j / segments, side], v * 2);
        strand.set([s.angle, s.depth, s.turns, s.seed], v * 4);
        span.set([s.start, s.length, s.kind], v * 3);
        v += 1;
      }
      if (j < segments) {
        const at = (k * (segments + 1) + j) * 2;
        index.push(at, at + 1, at + 2, at + 1, at + 3, at + 2);
      }
    }
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(verts * 3), 3)); // placed in the shader
  geometry.setAttribute("aLocal", new THREE.BufferAttribute(local, 2));
  geometry.setAttribute("aStrand", new THREE.BufferAttribute(strand, 4));
  geometry.setAttribute("aSpan", new THREE.BufferAttribute(span, 3));
  geometry.setIndex(verts > 65535 ? new THREE.Uint32BufferAttribute(index, 1) : new THREE.Uint16BufferAttribute(index, 1));
  return geometry;
}

function buildNodeGeometry(nodes) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(nodes.length * 3), 3));
  geometry.setAttribute("aStrand", new THREE.BufferAttribute(new Float32Array(
    nodes.flatMap((n) => [n.strand.angle, n.strand.depth, n.strand.turns, n.strand.seed])), 4));
  geometry.setAttribute("aAt", new THREE.BufferAttribute(new Float32Array(nodes.flatMap((n) => [n.s, n.seed])), 2));
  return geometry;
}

export function mount(container, options = {}) {
  const o = { side: "right", scale: 1, strands: 160, speed: 1, seed: 1, intensity: 1,
              shapes: ["ring", "knot", "coil"], ...options };
  const stage = createStage(container, { stillTime: 6, ...options, camera: { fov: 32, position: [0, 0, 9] } });
  if (stage.failed) return stage.handle();
  const num = (value, fallback) => (Number.isFinite(Number(value)) ? Number(value) : fallback);
  const speed = Math.max(0, num(o.speed, 1)), seed = num(o.seed, 1);
  const shapes = [0, 1, 2].map((i) => SHAPES[(o.shapes || [])[i]] || SHAPES[["ring", "knot", "coil"][i]]);
  const seedRand = random(seed + 5);

  const shared = {
    ...stage.uniforms,
    uKnot: { value: shapes.map((s) => new THREE.Vector4(...s.knot)) },
    uTube: { value: shapes.map((s) => new THREE.Vector4(...s.tube)) },
    uWeights: { value: new THREE.Vector3(1, 0, 0) },
    uData: { value: new Array(DATA_SLOTS).fill(0.5) },
    uSwell: { value: 0 },
    uBend: { value: 1 },
    uClock: { value: 0 },
    uSeed: { value: new THREE.Vector3(seedRand() * 40, seedRand() * 40, seedRand() * 40) },
    uFade: { value: new THREE.Vector2(7, 11) },
    uCalm: { value: new THREE.Vector4(1, 0, 0.3, 0.52) },
    uIntensity: { value: 1 },
    uWidth: { value: 0.011 },
    uNodeSize: { value: 15 },
    uHalo: { value: 2 },
  };
  // One uniforms object for both materials, so a value set once reaches both.
  const strandMaterial = new THREE.ShaderMaterial({ uniforms: shared, vertexShader: strandVertex,
    fragmentShader: strandFragment, transparent: true, depthWrite: false, depthTest: false, side: THREE.DoubleSide });
  const nodeMaterial = new THREE.ShaderMaterial({ uniforms: shared, vertexShader: nodeVertex,
    fragmentShader: nodeFragment, transparent: true, depthWrite: false, depthTest: false });

  const place = new THREE.Group();   // where it sits, how large, and the lean toward the pointer
  const form = new THREE.Group();    // its own tilt and slow turn
  const strands = new THREE.Mesh(undefined, strandMaterial);
  const nodes = new THREE.Points(undefined, nodeMaterial);
  strands.frustumCulled = nodes.frustumCulled = false; // the shader places every vertex
  nodes.renderOrder = 1;
  form.add(strands, nodes);
  place.add(form);
  stage.scene.add(place);

  // Fewer strands (low quality) each draw a little stronger, so the whole keeps its weight.
  let dim = 1;
  const setIntensity = () => {
    shared.uIntensity.value = num(o.intensity, 1) * dim * (stage.tokens.dark ? 0.5 : 0.7) * stage.quality.pick(1.25, 1.1, 1);
  };
  stage.onQuality((quality) => {
    const count = Math.max(12, Math.round(num(o.strands, 160) * quality.pick(0.5, 0.75, 1)));
    const list = makeStrands(count, seed);
    strands.geometry.dispose();
    strands.geometry = buildStrandGeometry(list, quality.pick(220, 300, 400));
    nodes.geometry.dispose();
    nodes.geometry = buildNodeGeometry(makeNodes(list, quality.pick(6, 9, 12), seed));
    shared.uHalo.value = quality.pick(0, 1.6, 2.2);   // the glow doubles the pixels drawn: not on weak devices
    setIntensity();
  });

  stage.onTokens((tokens) => {
    strandMaterial.blending = nodeMaterial.blending = tokens.blending; // glow on dark, ink on light
    shared.uWidth.value = tokens.dark ? 0.011 : 0.013;
    setIntensity();
  });

  stage.onResize((size) => {
    const view = stage.viewSize(9);
    const phone = size.aspect < 0.8;
    const sign = o.side === "left" ? -1 : o.side === "centre" || o.side === "center" ? 0 : 1;
    const scale = num(o.scale, 1);
    let x = 0, y = 0, diameter;
    if (phone) {             // low and large behind the text
      diameter = Math.max(view.width * 1.35, view.height * 0.55) * scale;
      y = -view.height * 0.24;
      dim = 0.6;
      shared.uCalm.value.set(0, 0, -1, 0);
    } else {                 // to one side, running off the edge
      diameter = Math.min(view.height * 1.12, view.width * 0.8) * scale;
      x = sign * (view.width * 0.5 - diameter * 0.36);
      y = -view.height * 0.02;
      dim = sign === 0 ? 0.75 : 1;
      shared.uCalm.value.set(sign, 0, sign === 0 ? -1 : 0.28, sign === 0 ? 0 : 0.55);
    }
    place.position.set(x, y, 0);
    place.scale.setScalar(diameter / 4);  // the shapes are about 4 units across
    const reach = diameter * 0.55;
    shared.uFade.value.set(9 - reach, 9 + reach);
    shared.uNodeSize.value = (phone ? 20 : 34) * place.scale.x;
    setIntensity();
  });

  // Eased state: the morph, the lean and the data, each its own pace.
  let morph = 0, leanX = 0, leanY = 0, swell = 0, swellTarget = 0;
  const data = shared.uData.value, dataTarget = new Array(DATA_SLOTS).fill(0.5);
  stage.onFrame((time, delta) => {
    const jump = stage.still || stage.clock.frame === 0;
    const ease = (value, target, rate) => (jump ? target : THREE.MathUtils.damp(value, target, rate, delta));
    // Progress walks the three shapes: 0 the first, 0.5 the second, 1 the third, smoothly between.
    morph = ease(morph, stage.progressEased * 2, 2.2);
    const w = [0, 1, 2].map((i) => Math.max(0, 1 - Math.abs(morph - i)));
    const smooth = w.map((v) => v * v * (3 - 2 * v)), total = smooth[0] + smooth[1] + smooth[2] || 1;
    shared.uWeights.value.set(smooth[0] / total, smooth[1] / total, smooth[2] / total);
    const mixed = (key) => (smooth[0] * shapes[0][key] + smooth[1] * shapes[1][key] + smooth[2] * shapes[2][key]) / total;
    const tilt = mixed("tilt");
    shared.uBend.value = mixed("bend");
    leanX = ease(leanX, stage.pointer.x, 1.6);
    leanY = ease(leanY, stage.pointer.y, 1.6);
    swell = ease(swell, swellTarget, 2.5);
    shared.uSwell.value = swell;
    for (let i = 0; i < DATA_SLOTS; i++) data[i] = ease(data[i], dataTarget[i], 2.5);
    const clock = time * speed;
    shared.uClock.value = clock;
    // One turn in 75 seconds round its own axis, a slow sway of the tilt, and a lean of up to
    // about 7 degrees toward the pointer.
    form.rotation.set(-tilt + 0.06 * Math.sin(clock * 0.13), 0.32 + 0.05 * Math.sin(clock * 0.09),
                      seed * 1.7 + clock * (Math.PI * 2) / 75);
    place.rotation.set(-leanY * 0.12, leanX * 0.16, 0);
  });

  return stage.handle({
    setData(values) {
      const list = Array.from(values || [], Number).filter(Number.isFinite).map((v) => Math.min(1, Math.max(0, v)));
      swellTarget = list.length ? 1 : 0;
      for (let i = 0; i < DATA_SLOTS; i++) {   // spread the list along the loop, reading between its values
        const at = list.length > 1 ? (i / DATA_SLOTS) * list.length : 0, k = Math.floor(at);
        dataTarget[i] = list.length ? list[k % list.length] + (list[(k + 1) % list.length] - list[k % list.length]) * (at - k) : 0.5;
      }
      stage.invalidate();
    },
  });
}
