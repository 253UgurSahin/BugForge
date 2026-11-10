/**
 * form.js: a sculptural object made of light, for a hero (look level 4 and 5).
 *
 * Families of thin luminous strands run along a tube that follows a knot from the torus family,
 * and a slow field of noise bends the whole thing so it never reads as a textbook knot. It breathes
 * (one breath in about 8 seconds), turns once in about 75 seconds and leans up to about 7 degrees
 * toward the pointer. Near strands are wide and bright, far ones thin, dim and cooler, so it reads
 * as a volume. A few pulses of light run along strands and a handful of nodes glow where strands
 * cross. On a dark page it glows (additive light). On a light page it becomes an ink drawing: near
 * strands in a heavier, deeper ink, far ones thinner in the same colour, the pulses short dark
 * strokes that travel along a strand, the nodes small open rings of ink.
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
 *              container) it always sits low and large and dimmer: its upper arcs pass behind the
 *              text at about 40 percent, the rest fills the bottom edge.
 *   scale      1. Size of the form against that layout, kept within 0.3 to 3.
 *   strands    160. Strands at high quality, kept within 12 to 400; medium draws 75 percent, low half.
 *   speed      1. Speed of turning, breathing and pulses. 0 holds the motion (the pointer still works).
 *   seed       1. Any number: another bend of the noise, another layout of strands and nodes.
 *   shapes     ["ring", "knot", "coil"]. The three shapes setProgress walks through, picked from
 *              "ring" (a wide band that goes round twice and crosses itself), "knot" (a trefoil
 *              rope), "coil" (a loose coil of nine round turns about a ring), "star" (a five-lobed knot) and "bloom"
 *              (a wide seven-lobed flower). Every shape winds twice round its axis, so any two
 *              morph into each other without a seam. Between two shapes the tube draws in a little
 *              and the line changes mostly in the middle, so one shape's windings never crowd
 *              onto the other's wide tube.
 *   intensity  1. Brightness on dark, ink strength on light.
 *   stillTime  6. The moment the reduced-motion still shows.
 *
 * setProgress(p)    0..1, eased: morphs through the three shapes (pair it with stage.progressOf).
 * setData(values)   a list of numbers 0..1 spread along the form, start to end of the loop: the tube
 *                   bulges (up to 1.6 times) and brightens where they are high and pinches and dims
 *                   where they are low; [] or null takes it back. Eased. The loop has 32 places;
 *                   each takes the highest value of the part of the list it covers, so a single
 *                   peak in a long list is never lost.
 * setPointer(x, y)  -1..1, y up: lean toward that point as the real pointer would.
 * pause(), resume(), destroy(), stage: as stage.js describes.
 *
 * Poster: put <img data-scene-poster src="form-poster.webp" alt=""> in the container; it shows
 * until the first frame and again when WebGL is missing. Make it by mounting with { still: true }
 * at the size of the hero and taking a screenshot: that is the reduced-motion frame.
 *
 * Cost: one draw call of camera-facing strips and one of 10, 12 or 14 points (low, medium, high).
 * High: 160 strands x 460 segments (about 150k vertices, each reading 3D simplex noise twice) with
 * a soft glow; medium 120 x 360; low 80 x 260 with a narrower glow. No textures, no render targets.
 * It pauses off screen and in a hidden tab (stage.js).
 */
import * as THREE from "three";
import { createStage } from "./stage.js";
import { stageUniforms, common, simplex3D, grain } from "./glsl.js";

// A knot from the torus family: it turns p times round the axis while it winds q times round a tube
// of radius r at distance R. Every shape has p = 2 (a coil that goes round once is drawn twice), so
// a morph between two of them always closes. tube: [half width, half height, turns of the bundle
// per loop, turns of the band]. follow: 1 when the tube's frame follows the winding (a tight coil,
// where a frame tied to the axis would flip at every turn). bend: how much the noise may bend it.
// tilt: how far (radians) the form leans back from facing the camera, to show its best side.
const SHAPES = {
  ring: { knot: [2, 1, 1.05, 0.45], tube: [0.3, 0.08, 0, 1], follow: 0, bend: 1.0, tilt: 0.5 },
  knot: { knot: [2, 3, 0.98, 0.46], tube: [0.25, 0.25, 2, 0], follow: 0, bend: 1.0, tilt: 0.45 },
  coil: { knot: [2, 18, 1.32, 0.3], tube: [0.14, 0.14, 1, 0], follow: 1, bend: 0.35, tilt: 0.62, reach: 0.45 },
  star: { knot: [2, 5, 1.0, 0.42], tube: [0.17, 0.17, 3, 0], follow: 0, bend: 0.8, tilt: 0.5 },
  bloom: { knot: [2, 7, 0.95, 0.5], tube: [0.12, 0.12, 1, 0], follow: 0, bend: 0.8, tilt: 0.35 },
};
const DATA_SLOTS = 32;

// The surface, shared by the strands and the nodes: a point on strand `strand` at s (loop fraction).
const surface = `
${stageUniforms}
${common}
${simplex3D}
uniform vec4 uKnot[3], uTube[3];
uniform vec3 uWeights;   // how much of each shape's line: they add up to 1
uniform vec3 uTubeWeights; // the same for the tube round it, which may change ahead of the line
uniform float uNarrow;   // 1, less while two shapes cross: the tube draws in so the two do not tangle
uniform vec3 uFollow;    // per shape: 1 when the frame follows the winding
uniform float uData[${DATA_SLOTS}], uSwell;   // uSwell: 0 without data
uniform float uClock, uBend;                  // uClock: seconds times speed
uniform float uReach;                         // how much of its span each strand draws
uniform vec3 uSeed;
// The data along the loop, read between its slots with a Catmull-Rom curve: smooth, no kinks.
float dataAt(float s) {
  const int n = ${DATA_SLOTS};
  float x = fract(s) * float(n), f = fract(x);
  int i = int(floor(x));
  float a = uData[(i + n - 1) % n], b = uData[i], c = uData[(i + 1) % n], d = uData[(i + 2) % n];
  return clamp(b + 0.5 * f * (c - a + f * (2.0 * a - 5.0 * b + 4.0 * c - d + f * (3.0 * (b - c) + d - a))), 0.0, 1.0);
}
// How far the tube swells with the data at s: pinched where low, bulging where high.
float dataSwell(float s) {
  float level = smoothstep(0.05, 0.95, dataAt(s));
  return mix(1.0, mix(0.35, 1.6, level), uSwell);
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
  // The knots are mixed as distance from the axis, angle round it and height, not as points:
  // a plain mix of two knots can pass through the axis mid-morph, and crumple there. The first and
  // second derivatives along t come along, worked out by hand, for the direction and the bend.
  float rho = 0.0, turn = 0.0, z = 0.0, dRho = 0.0, dZ = 0.0, ddRho = 0.0, ddZ = 0.0, wind = 0.0;
  vec4 tube = vec4(0.0);
  for (int i = 0; i < 3; i++) {
    vec4 k = uKnot[i];
    float w = uWeights[i], b = k.y * t, cb = cos(b), sb = sin(b);
    rho += w * (k.z + k.w * cb);
    dRho -= w * k.w * k.y * sb;
    ddRho -= w * k.w * k.y * k.y * cb;
    z += w * k.w * sb;
    dZ += w * k.w * k.y * cb;
    ddZ -= w * k.w * k.y * k.y * sb;
    turn += w * k.x;
    wind += w * k.y * uFollow[i];
    tube += uTubeWeights[i] * uTube[i];
  }
  vec3 radial = vec3(cos(turn * t), sin(turn * t), 0.0), across = vec3(-radial.y, radial.x, 0.0);
  vec3 c = rho * radial + vec3(0.0, 0.0, z);
  // Velocity and acceleration in the turning frame (radial, across, up), then the curvature.
  vec3 v = vec3(dRho, rho * turn, dZ);
  vec3 a = vec3(ddRho - rho * turn * turn, 2.0 * dRho * turn, ddZ);
  float speed = length(v);
  float curvature = length(cross(v, a)) / (speed * speed * speed);
  vec3 T = (v.x * radial + v.y * across + vec3(0.0, 0.0, v.z)) / speed;
  // A frame round the line, from a reference direction that never lies along it: away from the
  // axis, or for a coil the direction from the ring to the wire, which turns with the winding.
  float psi = t * wind;
  vec3 ref = cos(psi) * radial + vec3(0.0, 0.0, sin(psi));
  vec3 N = normalize(ref - dot(ref, T) * T);
  vec3 B = cross(T, N);
  // Low-frequency noise, read once at the core line, so a whole section moves together and the
  // tube bends but stays a tube. It pushes in world directions, never along the frame, so a fast
  // turning frame cannot kink the line.
  vec4 n = snoiseGrad(c * 0.34 + noiseAt());
  c += (radial * n.x * 0.2 + vec3(0.0, 0.0, n.y * 0.05)) * uBend;
  // Breathing: everything swells a little, once every 8 seconds; data swells it where it is high.
  float breath = sin(uClock * TAU / 8.0);
  float swell = (1.0 + 0.07 * breath + 0.09 * n.z) * dataSwell(s) * uNarrow;
  // Never wider than the bend of the line allows: a tube wider than its turn folds into spikes. A
  // smooth minimum, not a hard one, so the width never turns a corner between two neighbours, with
  // room left for the extra bend the noise adds.
  float limit = 0.6 / max(curvature * max(tube.x, tube.y), 0.0001);
  swell = swell / pow(1.0 + pow(swell / limit, 4.0), 0.25);
  // Round the tube: the strand's angle grows along the loop, so it winds as a helix. The section is
  // an ellipse (a flat band for the ring) that may itself turn along the loop.
  float angle = strand.x + t * (tube.z + strand.z);
  vec2 e = rotate2D(t * tube.w) * vec2(cos(angle) * tube.x, sin(angle) * tube.y) * strand.y * swell;
  skin = normalize(N * e.x + B * e.y + T * 1e-5);
  return c + N * e.x + B * e.y;
}
`;

// Calm where the headline is: fade the form out toward the side of the screen away from it.
const calm = `
uniform vec4 uCalm;      // xy: toward where the form sits on screen, zw: the fade from calm to full
uniform float uCalmLow;  // how much is left on the calm side
float calmAt(vec2 pixel) {
  return mix(uCalmLow, 1.0, smoothstep(uCalm.z, uCalm.w, dot(pixel / uResolution - 0.5, uCalm.xy) + 0.5));
}`;

// A pulse: a bright head and a tail behind it, x in loop fractions behind (negative) or ahead.
const pulseShape = `
float pulseAt(float x, float head, float tail) {
  return x > 0.0 ? exp(-x * x / (head * head)) : exp(x / tail);
}`;

const strandVertex = `
${surface}
${pulseShape}
attribute vec2 aLocal;   // x: 0..1 along the strand, y: -1 or 1, the two edges of the ribbon
attribute vec4 aStrand;
attribute vec3 aSpan;    // where on the loop it starts, how much of the loop it covers, its colour
uniform float uWidth;    // world units
uniform vec2 uFade;      // depth where the form is nearest and farthest
uniform float uIntensity;  // brightness times density: a thin tube packs its strands tighter
uniform float uHalo;     // pixels of soft glow on each side, on dark only
uniform float uPulses;   // the share of strands that carry a pulse
// vAcross: pixels from the middle of the ribbon; vCore: half the line's width in pixels.
varying float vAcross, vCore, vAlpha, vKind, vFar, vHead, vLoop, vLength;
void main() {
  float span = aSpan.y * uReach;
  float s = aSpan.x + aLocal.x * span;
  vec3 skin, unused;
  vec3 p0 = strandPoint(s, aStrand, skin);
  vec3 p1 = strandPoint(s + 0.002, aStrand, unused);
  vec4 m0 = modelViewMatrix * vec4(p0, 1.0);
  vec4 c0 = projectionMatrix * m0;
  vec4 m1 = modelViewMatrix * vec4(p1, 1.0);
  vec4 c1 = projectionMatrix * m1;
  // The ribbon faces the camera: push the two edges apart across the line's direction on screen.
  vec2 along = (c1.xy / c1.w - c0.xy / c0.w) * uResolution;
  vec2 across = normalize(vec2(-along.y, along.x) + 1e-6);
  // Where a strand runs straight at the camera its picture folds back on itself and the ribbon
  // has no clear direction: a spike. Fade it out there, by how short it looks against its length.
  float seen = length(along) / max(length(m1.xyz - m0.xyz) * projectionMatrix[1][1] * uResolution.y * 0.5 / -m0.z, 1e-6);
  float endOn = smoothstep(0.2, 0.6, seen);
  // Some strands carry a pulse that runs their length every 9 seconds. The fragment shader draws
  // it sharp; here a wide version of it makes the ribbon room to swell and glow.
  vHead = -10.0;
  if (fract(aStrand.w * 7.31) < uPulses) vHead = fract(uClock / 9.0 + aStrand.w * 5.3) * 1.3 - 0.15;
  float pulse = vHead > -5.0 ? pulseAt((aLocal.x - vHead) * span, 0.01, 0.035) : 0.0;
  // Width follows depth like a real thread: near strands about three times as wide as far ones,
  // but never under about a pixel: a thinner line would flicker, so it gets fainter instead.
  float depth = -m0.z;
  float far = smoothstep(uFade.x, uFade.y, depth);   // 0 in front, 1 at the back
  // About one strand in ten leads: wider and brighter, it gives the bundle its lines.
  float lead = step(fract(aStrand.w * 13.7), 0.1);
  float taper = sqrt(sin(PI * aLocal.x));
  float level = smoothstep(0.1, 0.9, dataAt(s));
  float data = mix(1.0, mix(0.45, 2.0, level), uSwell);
  // On light a pulse is a heavier stroke of ink, so it swells more than the glow does on dark.
  float pixels = uWidth * data * (1.0 + mix(1.8, 0.7, uDark) * pulse) * (1.0 + 0.6 * lead)
               * mix(mix(2.1, 1.75, uDark), mix(0.5, 0.6, uDark), far) * taper
               * projectionMatrix[1][1] * uResolution.y * 0.5 / depth;
  float core = max(pixels, uPixelRatio);
  float halo = uDark * uHalo * uPixelRatio * (1.0 + 1.5 * pulse) * mix(1.2, 0.6, far);
  float extent = core * 0.5 + uPixelRatio + halo * 1.8; // room for the soft edge and the glow
  c0.xy += across * aLocal.y * extent * 2.0 / uResolution * c0.w;
  gl_Position = c0;
  vAcross = aLocal.y * extent;
  vCore = core * 0.5;
  // Brighter where the surface turns away (its normal across the view): the rims of the tube. On
  // light the back keeps more of its ink: thinner lines of the same colour, not a pale haze.
  vec3 normal = normalize(normalMatrix * skin);
  float rim = 1.0 - abs(dot(normal, normalize(-m0.xyz)));
  vAlpha = uIntensity * (pixels / core) * mix(mix(0.55, 0.3, uDark), 1.0, rim * rim)
         * mix(1.0, mix(0.34, 0.16, uDark), far) * (1.0 + 0.5 * lead)
         * mix(1.0, mix(0.06, 2.0, level), uSwell)
         * smoothstep(0.0, 0.16, aLocal.x) * smoothstep(1.0, 0.84, aLocal.x) * endOn;
  vKind = aSpan.z;
  vFar = far;
  vLoop = aLocal.x;
  vLength = span;
}`;

const strandFragment = `
${stageUniforms}
${grain}
${pulseShape}
uniform float uHalo;
${calm}
varying float vAcross, vCore, vAlpha, vKind, vFar, vHead, vLoop, vLength;
void main() {
  // The pulse, sharp: a head about 20 pixels long, a tail of about 60 on a desktop hero, and a
  // faint wake behind that, so the strand it runs on lights up for a while.
  float x = (vLoop - vHead) * vLength;
  float pulse = vHead > -5.0 ? pulseAt(x, 0.0045, 0.016) + 0.22 * pulseAt(x, 0.001, 0.09) : 0.0;
  float d = abs(vAcross);
  float lineCover = 1.0 - smoothstep(vCore - 0.5 * uPixelRatio, vCore + 0.5 * uPixelRatio, d);
  float haloWidth = max(uHalo, 0.01) * uPixelRatio * (1.0 + 1.5 * pulse) * mix(1.2, 0.6, vFar);
  float glow = uDark * (0.18 + 0.5 * pulse) * exp(-d * d / (haloWidth * haloWidth)) * step(0.01, uHalo);
  float calm = calmAt(gl_FragCoord.xy);
  vec3 ink = vKind > 0.5 ? uAccent2 : uAccent;
  // The far side recedes. On dark it turns darker and cooler, toward the muted text colour. On light
  // it keeps its colour and the near side gets the weight: a deeper ink in front.
  ink = mix(ink, uMuted * 0.5, vFar * 0.55 * uDark);
  ink *= mix(mix(0.7, 1.0, vFar), 1.0, uDark);
  // On dark, a pulse runs white-hot toward the text colour; on light it is a dark, heavy stroke.
  vec3 color = mix(ink, mix(ink * 0.35, uText, uDark), min(pulse * mix(0.9, 0.85, uDark), 1.0));
  // The second accent is one thread in seven: on light it stays a little lighter than the first, so
  // it reads as an occasional thread and not the heaviest line.
  float alpha = (lineCover + glow) * vAlpha * calm * (1.0 + pulse * mix(2.5, 6.0, uDark))
              * (1.0 + vKind * mix(-0.1, 0.5, uDark));
  gl_FragColor = vec4(color, min(alpha, 1.0));
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy) * gl_FragColor.a;
}`;

const nodeVertex = `
${surface}
attribute vec4 aStrand;
attribute vec2 aAt;      // x: where on the loop, y: its own seed
uniform vec2 uFade;
uniform float uNodeSize; // pixels across the whole sprite
varying float vAlpha, vSize;
void main() {
  vec3 skin;
  vec4 m = modelViewMatrix * vec4(strandPoint(aAt.x, aStrand, skin), 1.0);
  gl_Position = projectionMatrix * m;
  float far = smoothstep(uFade.x, uFade.y, -m.z);
  float twinkle = 0.8 + 0.2 * sin(uClock * 0.9 + aAt.y * 40.0);
  vAlpha = twinkle * mix(1.0, 0.7, far);
  vSize = uNodeSize * uPixelRatio * (0.85 + 0.3 * aAt.y) * mix(1.0, 0.7, far);
  gl_PointSize = vSize;
}`;

const nodeFragment = `
${stageUniforms}
${grain}
${calm}
uniform float uIntensity;
varying float vAlpha, vSize;
void main() {
  float r = length(gl_PointCoord - 0.5) * vSize;   // pixels from the middle
  float px = uPixelRatio;
  // Dark: a hot core of about 3 pixels in a soft halo about 14 wide, and a faint wider bloom.
  float core = 1.0 - smoothstep(1.8 * px, 2.8 * px, r);
  float light = core + 0.85 * exp(-r * r / (40.0 * px * px)) + 0.3 * exp(-r * r / (260.0 * px * px));
  light *= 1.0 - smoothstep(vSize * 0.4, vSize * 0.5, r);
  // Light: an open ring of ink about 9 pixels across, soft at its edges, round a small dot.
  float ring = 1.0 - smoothstep(0.9 * px, 1.7 * px, abs(r - 0.27 * vSize));
  float inkDot = max(ring, 0.8 * (1.0 - smoothstep(0.9 * px, 1.7 * px, r)));
  float calm = calmAt(gl_FragCoord.xy);
  float alpha = mix(inkDot * 0.9, min(light, 1.0), uDark) * vAlpha * calm * min(uIntensity * 2.2, 1.0);
  vec3 color = mix(uAccent * 0.5, mix(uAccent, uText, 0.35 + 0.6 * core), uDark);
  gl_FragColor = vec4(color, alpha);
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy) * alpha;
}`;

/** A small seeded random generator, so a seed always gives the same form. */
function random(seed) {
  let state = (Math.floor(Math.abs(seed) * 9973) + 1831565813) >>> 0;
  return () => {
    state = (state + 1831565813) >>> 0;
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
  const gap = 0.5 / wanted;   // spread them along the loop
  for (let tries = 0; tries < 2000 && nodes.length < wanted && a.length && b.length; tries++) {
    const i = a[Math.floor(rand() * a.length)], j = b[Math.floor(rand() * b.length)];
    // Only where both strands are drawn at every reach and away from their faded ends.
    const lo = Math.max(i.start + i.length * 0.15, j.start + j.length * 0.15);
    const hi = Math.min(i.start + i.length * 0.36, j.start + j.length * 0.36);
    if (hi <= lo) continue;
    // angle_i + 2 pi s turns_i = angle_j + 2 pi s turns_j + 2 pi m, solved for s: every crossing of
    // the pair in [lo, hi] has a whole m between the values at the two ends; take one at random.
    const dt = i.turns - j.turns, da = (i.angle - j.angle) / (Math.PI * 2);
    const m0 = lo * dt + da, m1 = hi * dt + da;
    const first = Math.ceil(Math.min(m0, m1)), last = Math.floor(Math.max(m0, m1));
    if (last < first) continue;
    const s = (first + Math.floor(rand() * (last - first + 1)) - da) / dt;
    if (nodes.some((node) => Math.abs(((node.s - s) % 1 + 1.5) % 1 - 0.5) < gap)) continue;
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
  const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value));
  const strandCount = clamp(Math.round(num(o.strands, 160)), 12, 400), scale = clamp(num(o.scale, 1), 0.3, 3);
  const shapes = [0, 1, 2].map((i) => SHAPES[(o.shapes || [])[i]] || SHAPES[["ring", "knot", "coil"][i]])
    .map((shape) => ({ reach: 1, ...shape, thick: Math.max(shape.tube[0], shape.tube[1]) }));
  const seedRand = random(seed + 5);

  const shared = {
    ...stage.uniforms,
    uKnot: { value: shapes.map((s) => new THREE.Vector4(...s.knot)) },
    uTube: { value: shapes.map((s) => new THREE.Vector4(...s.tube)) },
    uFollow: { value: new THREE.Vector3(...shapes.map((s) => s.follow)) },
    uWeights: { value: new THREE.Vector3(1, 0, 0) }, uTubeWeights: { value: new THREE.Vector3(1, 0, 0) },
    uNarrow: { value: 1 }, uCalmLow: { value: 0.05 }, uBend: { value: 1 }, uClock: { value: 0 },
    uData: { value: new Array(DATA_SLOTS).fill(0.5) }, uSwell: { value: 0 },
    uSeed: { value: new THREE.Vector3(seedRand() * 40, seedRand() * 40, seedRand() * 40) },
    uFade: { value: new THREE.Vector2(7, 11) }, uCalm: { value: new THREE.Vector4(1, 0, 0.3, 0.52) },
    uIntensity: { value: 1 }, uWidth: { value: 0.01 }, uNodeSize: { value: 30 }, uHalo: { value: 2 },
    uPulses: { value: 0.11 }, uReach: { value: 1 },
  };
  // One uniforms object for both materials, so a value set once reaches both.
  const strandMaterial = new THREE.ShaderMaterial({ uniforms: shared, vertexShader: strandVertex,
    fragmentShader: strandFragment, transparent: true, depthWrite: false, depthTest: false, side: THREE.DoubleSide });
  const nodeMaterial = new THREE.ShaderMaterial({ uniforms: shared, vertexShader: nodeVertex,
    fragmentShader: nodeFragment, transparent: true, depthWrite: false, depthTest: false });

  const place = new THREE.Group(), form = new THREE.Group(); // place: where, how large, the lean; form: tilt, turn
  const strands = new THREE.Mesh(undefined, strandMaterial);
  const nodes = new THREE.Points(undefined, nodeMaterial);
  strands.frustumCulled = nodes.frustumCulled = false; // the shader places every vertex
  nodes.renderOrder = 1;
  stage.scene.add(place.add(form.add(strands, nodes)));

  // Fewer strands (low quality) each draw a little stronger, so the whole keeps its weight.
  let dim = 1, intensity = 1, phone = false;
  const setIntensity = () => {
    intensity = num(o.intensity, 1) * dim * (stage.tokens.dark ? 0.5 : 0.62) * stage.quality.pick(1.55, 1.2, 1);
  };
  const setNodeSize = () => {
    shared.uNodeSize.value = stage.tokens.dark ? (phone ? 30 : 40) : 15;
  };
  stage.onQuality((quality) => {
    const count = Math.max(12, Math.round(strandCount * quality.pick(0.5, 0.75, 1)));
    const list = makeStrands(count, seed);
    strands.geometry.dispose();
    strands.geometry = buildStrandGeometry(list, quality.pick(260, 360, 460));
    nodes.geometry.dispose();
    nodes.geometry = buildNodeGeometry(makeNodes(list, quality.pick(10, 12, 14), seed));
    shared.uHalo.value = quality.pick(1.6, 1.9, 2.2);   // the glow widens the pixels drawn: narrower on weak devices
    shared.uPulses.value = quality.pick(0.14, 0.11, 0.09); // about the same number of pulses at every count
    setIntensity();
  });

  stage.onTokens((tokens) => {
    strandMaterial.blending = nodeMaterial.blending = tokens.blending; // glow on dark, ink on light
    shared.uWidth.value = tokens.dark ? 0.01 : 0.011;
    setIntensity();
    setNodeSize();
  });

  stage.onResize((size) => {
    const view = stage.viewSize(9);
    phone = size.aspect < 0.8;
    const sign = o.side === "left" ? -1 : o.side === "centre" || o.side === "center" ? 0 : 1;
    let x = 0, y = 0, diameter;
    if (phone) {             // low and large: its upper arcs pass dimmed behind the text, the rest fills the bottom
      diameter = Math.max(view.width * 1.85, view.height * 0.58) * scale;
      y = -view.height * 0.23;
      dim = 0.7;
      shared.uCalm.value.set(0, -1, 0.6, 0.86);
      shared.uCalmLow.value = 0.4;
    } else {                 // to one side, running off the edge
      diameter = Math.min(view.height * 1.18, view.width * 0.82) * scale;
      x = sign * (view.width * 0.5 - diameter * 0.3);
      y = -view.height * 0.02;
      dim = sign === 0 ? 0.75 : 1;
      shared.uCalm.value.set(sign, 0, sign === 0 ? -1 : 0.28, sign === 0 ? 0 : 0.55);
      shared.uCalmLow.value = 0.05;
    }
    place.position.set(x, y, 0);
    place.scale.setScalar(diameter / 4);  // the shapes are about 4 units across
    const reach = diameter * 0.45;
    shared.uFade.value.set(9 - reach, 9 + reach);
    setIntensity();
    setNodeSize();
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
    const tube = smooth.map((v) => v / total);
    // The line changes mostly in the middle of a crossing (the cube sharpens it), the tube evenly, and
    // the tube draws in while they cross: a wide tube never carries the next shape's tight windings,
    // which would crowd into ruffles. cross is 0 on a shape and 1 halfway between two.
    const cubed = tube.map((v) => v * v * v), cubedTotal = cubed[0] + cubed[1] + cubed[2] || 1;
    const line = cubed.map((v) => v / cubedTotal);
    const cross = Math.min(1, 2 * (1 - tube[0] * tube[0] - tube[1] * tube[1] - tube[2] * tube[2]));
    shared.uWeights.value.set(...line);
    shared.uTubeWeights.value.set(...tube);
    shared.uNarrow.value = 1 - 0.4 * cross;
    const mixed = (key, k = line) => k[0] * shapes[0][key] + k[1] * shapes[1][key] + k[2] * shapes[2][key];
    const tilt = mixed("tilt");
    shared.uBend.value = mixed("bend");
    shared.uReach.value = mixed("reach");
    // A thin tube packs its strands close together: draw each fainter so it does not burn out, and a
    // little fainter again mid-crossing, where two shapes share the strands.
    shared.uIntensity.value = intensity * (1 - 0.2 * cross)
      * (0.5 + 0.5 * THREE.MathUtils.smoothstep(mixed("thick", tube) * shared.uNarrow.value, 0.05, 0.22));
    leanX = ease(leanX, stage.pointer.x, 1.6);
    leanY = ease(leanY, stage.pointer.y, 1.6);
    shared.uSwell.value = swell = ease(swell, swellTarget, 2.5);
    for (let i = 0; i < DATA_SLOTS; i++) data[i] = ease(data[i], dataTarget[i], 2.5);
    const clock = (shared.uClock.value = time * speed);
    // One turn in 75 seconds round its own axis, a slow sway of the tilt, and a lean of up to
    // about 7 degrees toward the pointer.
    form.rotation.set(-tilt + 0.06 * Math.sin(clock * 0.13), 0.32 + 0.05 * Math.sin(clock * 0.09),
                      seed * 1.7 + clock * (Math.PI * 2) / 75);
    place.rotation.set(-leanY * 0.12, leanX * 0.12, 0);   // 0.12 radians: about 7 degrees
  });

  return stage.handle({
    setData(values) {
      const list = Array.from(values || [], Number).filter(Number.isFinite).map((v) => Math.min(1, Math.max(0, v)));
      swellTarget = list.length ? 1 : 0;
      // Spread the list round the loop. Each slot takes the highest value of the stretch of the list it
      // covers (read as a line between the values, and round the loop), so a single peak never falls
      // between two slots, however long or short the list.
      const n = list.length;
      const at = (x) => { const k = Math.floor(x), f = x - k, a = list[((k % n) + n) % n]; return a + (list[(((k + 1) % n) + n) % n] - a) * f; };
      for (let i = 0; i < DATA_SLOTS; i++) {
        if (!n) { dataTarget[i] = 0.5; continue; }
        const lo = ((i - 0.5) / DATA_SLOTS) * n, hi = ((i + 0.5) / DATA_SLOTS) * n;
        let top = Math.max(at(lo), at(hi));
        for (let k = Math.ceil(lo); k <= hi; k++) top = Math.max(top, at(k));
        dataTarget[i] = top;
      }
      stage.invalidate();
    },
  });
}
