/**
 * aurora.js: a shader atmosphere that can sit behind a whole page (scene kit, look levels 4 and 5).
 *
 * One rectangle that fills the container, coloured by one fragment shader. Three moods:
 *   "aurora"  slow curtains of light hanging over silk-like folds of colour, as the northern lights
 *             look from far away: the page background stays the main colour, the accent lights the
 *             hem of each curtain, the second accent a higher, broader band above it. On a tall
 *             screen the curtains hang longer and the far ones lower, so a phone sees a sky.
 *   "water"   looking down into clear, shallow water: the moving net of light that a wavy surface
 *             throws on the bottom (caustics), with soft rings that spread where the pointer moves
 *             or a finger taps.
 *   "mist"    three banks of fog, far to near, each a slow ridge with a lit top edge, and a low
 *             light behind them in the second accent; almost without colour, tinted by the accent.
 * On a dark page it is light in the dark; on a light page a pale wash, like watercolour on paper.
 * The two accents are joined round the colour wheel; when the short way passes olive and khaki
 * (teal to orange, say), it takes the long way, through blue and violet, as a real aurora does.
 *
 *   import { mount } from "./scenes/aurora.js";
 *   const sky = mount(document.querySelector(".page-sky"), { mode: "water", calm: "left" });
 *   addEventListener("scroll", () => sky.setProgress(sky.stage.progressOf(document.body)));
 *   sky.setData([0.2, 0.9, 0.4]);   // more energy
 *   sky.destroy();                  // when the page or component goes away
 *
 * For a whole page, give it a fixed container: `.page-sky { position: fixed; inset: 0; z-index: -1; }`.
 *
 * Options (all optional; the stage's own options, see stage.js, pass straight through):
 *   mode        "aurora" (default), "water" or "mist".
 *   calm        "left" (default): the side where the text sits; the effect fades towards it. Also
 *               "right", "top", "bottom", "center" or "none". On a tall, narrow screen "left" and
 *               "right" calm the middle band instead, where text sits on a phone.
 *   calmAmount  0.8: how much of the effect is taken away on the calm side (0 none, 1 all).
 *   intensity   1: how strong the colour is. 0.6 for a busy page, 1.4 for an empty dark one.
 *   speed       1: how fast it moves. 0 stands still.
 *   scale       1: the size of the shapes. 2 is twice as large, 0.5 half.
 *   ripples     true: rings from the pointer in "water" mode.
 *
 * setProgress(p), 0..1: the mood of the page while it scrolls. The balance moves from the accent
 *   to the second accent and the flow calms: in the aurora the second accent takes over the upper
 *   curtains while the hem keeps the accent and its height (clear of the copy), the water grows
 *   deeper (a finer, calmer net), the mist and its light lift. Feed it a section's progress:
 *   sky.setProgress(sky.stage.progressOf(section)).
 * setData(values): numbers 0..1, any length. Their average sets the energy: 0 is a slow, faint
 *   breath, 0.5 the normal look, 1 brighter, faster and more folded. An empty list goes back to 0.5.
 * setPointer(x, y), pause(), resume(), destroy(), stage: as stage.js describes. setMode(name)
 *   switches the mood without a new mount.
 *
 * Poster: give the container a child `<img data-scene-poster src="sky.png" alt="">`, shown until
 * the first frame and again when there is no WebGL; or a background image plus the rule
 * `.page-sky[data-scene="live"] { background-image: none; }`. To make the picture, mount with
 * { still: true } at the size you need and take a screenshot. A plain gradient of --color-bg with
 * a little --color-accent also serves.
 *
 * Cost: one draw call, no textures, nothing moves on the processor. It draws at part of the screen
 * resolution (0.5, 0.6, 0.75 of it for low, medium, high quality: a soft picture loses nothing by
 * it). 2D simplex lookups per pixel, low / high quality: aurora 12 / 19 (two warp layers of 3 to 5
 * octaves, 2 or 3 curtains), water 7 plus 4 or 8 rings, mist 18 / 24 (three fog banks). A phone
 * starts at medium; the stage steps down when frames are slow. Under reduced motion it draws one
 * still frame and stops: no cost at all after that.
 */
import * as THREE from "three";
import { createStage } from "./stage.js";
import { stageUniforms, common, simplex2D, simplex3D, fbm, oklab, grain } from "./glsl.js";

const MODES = { aurora: 0, water: 1, mist: 2 };
const CALM = { left: [-1, 0], right: [1, 0], top: [0, 1], bottom: [0, -1], center: [0, 0], none: [0, 0] };
const RINGS = 8;   // ripples kept at once; the oldest is replaced

// The rectangle covers the screen whatever the camera does. The vertex shader also works out the
// colours once per corner (four times a frame instead of once per pixel): the page's accents,
// brought to a lightness that glows on dark or tints on light.
const vertexShader = `
${stageUniforms}
${common}
${oklab}
varying vec2 vUv;
varying vec3 vLchA, vLchB, vMistFar, vMistNear, vMistRim, vGlow;
varying float vTurn;
// A colour at lightness L (Oklab, 0 black .. 1 white) and with its colourfulness times chroma.
vec3 tone(vec3 c, float L, float chroma) {
  vec3 lab = linearToOklab(c);
  lab.x = L;
  lab.yz *= chroma;
  return clamp(oklabToLinear(lab), 0.0, 1.0);
}
// Oklab as lightness, colourfulness and hue angle, so two hues can be joined round the colour wheel.
vec3 lch(vec3 lab) { return vec3(lab.x, length(lab.yz), atan(lab.z, lab.y)); }
void main() {
  vUv = uv;
  gl_Position = vec4(position.xy, 0.0, 1.0);
  // Dark page: middle lightness, a little less colourful than the token (light, never neon).
  // Light page: pale pigments, as watercolour is pale where it is thin.
  float L = mix(0.86, 0.76, uDark), C = mix(0.95, 0.85, uDark);
  vLchA = lch(linearToOklab(tone(uAccent, L, C)));
  vLchB = lch(linearToOklab(tone(uAccent2, L + 0.04 * uDark, C)));
  // The way round the hue circle from the first accent to the second: the short way, unless it
  // runs through olive and khaki (hue about 112 degrees), which read as dirt, not light. Then the
  // long way, through blue and violet, as a real aurora turns from green to red.
  float turn = mod(vLchB.z - vLchA.z + PI, TAU) - PI;
  float olive = turn >= 0.0 ? mod(1.95 - vLchA.z, TAU) : mod(vLchA.z - 1.95, TAU);
  if (olive > 0.3 && olive < abs(turn) - 0.3 && min(vLchA.y, vLchB.y) > 0.02) turn -= sign(turn) * TAU;
  vTurn = turn;
  // Mist: the haze is the muted text colour leaning to the accent (more so on paper, where a
  // neutral grey would read as dirt). Far banks are pale, near ones deep; the light behind is the
  // second accent.
  vec3 haze = mixOklab(uMuted, uAccent, mix(0.75, 0.4, uDark));
  vMistFar = tone(haze, mix(0.9, 0.42, uDark), mix(1.0, 0.75, uDark));
  vMistNear = tone(haze, mix(0.83, 0.25, uDark), mix(1.0, 0.7, uDark));
  vMistRim = tone(haze, mix(0.78, 0.86, uDark), mix(1.1, 0.45, uDark));
  vGlow = tone(uAccent2, mix(0.9, 0.8, uDark), 0.6);
}`;

const fragmentShader = `
${stageUniforms}
${common}
${simplex2D}
${simplex3D}
${fbm}
${oklab}
${grain}
uniform float uFlow, uIntensity, uScale, uEnergy, uRingOn;
uniform vec4 uCalm;            // direction x, y; amount; 1 when the screen is tall and narrow
uniform vec4 uRings[${RINGS}];  // centre (scene units), start time, strength
varying vec2 vUv;
varying vec3 vLchA, vLchB, vMistFar, vMistNear, vMistRim, vGlow;
varying float vTurn;

// The page's two accents joined along the colour wheel: t = 0 the first, 1 the second. A straight
// mix of two far-apart hues (teal and orange) passes through grey; this walks round the hue
// circle with lightness and colourfulness kept, the way the vertex shader chose.
vec3 ink(float t) {
  t = clamp(t, 0.0, 1.0);
  vec3 c = mix(vLchA, vLchB, t);
  c.y *= 1.0 - 0.4 * (1.0 - uDark) * sin(PI * t);   // on paper the halfway hues stay pale
  float hue = vLchA.z + vTurn * t;
  return clamp(oklabToLinear(vec3(c.x, c.y * cos(hue), c.y * sin(hue))), 0.0, 1.0);
}

// Scene units: 1 is the geometric mean of width and height, so a phone and a desktop show
// shapes of about the same size, and the middle of the screen is 0. frame: half the width and
// height in those units (0.63 x 0.4 on a 16:10 desktop, 0.34 x 0.73 on a phone).
float unitPixels() { return sqrt(uResolution.x * uResolution.y); }
vec2 frameSize() { return 0.5 * uResolution / unitPixels(); }

// Calm: towards the side where the text sits the effect fades, to 1 - amount. side runs 1 at
// that edge to -1 at the opposite one. On a tall screen with "left" or "right" the text spans the
// width in the middle band, so that band is calmed, gently, and the top and the bottom keep
// their light.
float calmAt() {
  vec2 centred = vUv - 0.5;
  if (uCalm.w > 0.5) return 1.0 - uCalm.z * 0.65 * (1.0 - smoothstep(0.06, 0.3, abs(centred.y + 0.03)));
  float side = dot(centred, uCalm.xy) * 2.0;
  if (dot(uCalm.xy, uCalm.xy) < 0.5) side = 1.0 - 2.4 * length(centred * vec2(0.6, 1.4));
  return 1.0 - uCalm.z * smoothstep(-0.5, 0.45, side);
}

#if MODE == 0
// AURORA. Returns (colour, coverage); main() lays it over the page.
// Each curtain has two bands of light, as the real thing has: a low one in the accent, a thin
// bright seam at the hem with a quick fade upwards, and a high, broad, streaked one in the second
// accent. Scrolling lets the high band take over; the hem keeps its colour and its height.
vec4 sky(vec2 p) {
  float t = uFlow;
  float tall = uCalm.w;
  vec2 q = p / uScale;
  q.y -= tall * 0.07;                        // on a phone the hem crosses at about 40% of the height
  float reach = mix(1.0, 0.45, tall);        // and the curtains hang twice as long, to the top
  // Domain warping: read slow noise and push the plane by it before reading anything else.
  // Straight lines then bend into soft folds, like silk lifted by the wind.
  vec2 drift = vec2(0.02, -0.007) * t;
  vec2 warp = vec2(fbm(q * 0.85 + drift), fbm(q * 0.85 + vec2(5.2, -1.3) - drift * 0.7));
  vec2 s = q + warp * (0.07 + 0.07 * uEnergy);
  float lean = mix(0.2, 0.1, uProgress) * (1.0 - 0.6 * tall);   // the hems rise away from the text
  float warmth = mix(0.2, 1.0, uProgress);
  float hue = 0.0, amount = 0.0;   // the colour (0..1 along ink) is averaged, weighted by light
  for (int i = 0; i < CURTAINS; i++) {
    float fi = float(i);
    float far = fi / float(CURTAINS - 1);              // 0 the nearest curtain .. 1 the farthest
    // Along the curtain: far curtains are stretched, so their folds are smaller, as in perspective.
    // The pointer moves near curtains more than far ones (parallax), so the sky has depth.
    float x = (s.x - uPointer.x * 0.035 * (1.0 - 0.7 * far)) * (1.5 + far * 1.6) + fi * 4.7 + t * (0.035 + 0.02 * fi);
    vec3 wave = snoiseGrad(vec2(x * 0.8, t * 0.04 + fi * 13.0));
    // On a phone the far curtains hang lower instead, towards the horizon, so the lower third
    // has light too; on a wide screen they hang higher, behind the near ones.
    float hem = 0.04 + far * mix(0.13, -0.5, tall) + 0.03 * uProgress + lean * s.x + mix(0.25, 0.1, tall) * s.x * s.x + 0.08 * wave.x - uPointer.y * 0.02 * (1.0 - far);
    // Rays: noise stretched along the height, so the light hangs in vertical streaks.
    // Two sizes of ray: broad bands and fine threads inside them.
    float broad = snoise(vec2(x * 8.0, s.y * 0.6 * reach - t * 0.05));
    float rays = 0.65 * broad + 0.35 * snoise(vec2(x * 23.0, s.y * 1.1 * reach - t * 0.08));
    // Height above the hem. The rays end at slightly different heights, so the hem is a fringe
    // of hanging threads, not the smooth outline of a hill.
    float d = s.y - hem + 0.009 * broad;
    float up = max(d, 0.0) * reach;
    // Where the curtain turns away from us (a steep hem) we look along it, and it is brighter.
    float edgeOn = 1.0 + 0.6 * smoothstep(0.3, 1.5, abs(wave.y));
    float low = smoothstep(-0.03, 0.01, d) * exp(-up * (6.0 + far * 4.0)) * 0.75 + 0.9 * exp(-d * d / 0.0003);
    low *= (0.55 + 0.5 * rays) * edgeOn;
    float high = exp(-pow((up - 0.15 - 0.04 * far) / 0.1, 2.0)) * smoothstep(0.0, 0.1, up);
    high *= warmth * 0.75 * (0.5 + 0.6 * rays) * edgeOn;
    // Under the hem its light is scattered a little into the haze, longer on a phone.
    float under = (0.16 * exp(min(d, 0.0) * mix(26.0, 12.0, tall)) + 0.035 * exp(min(d, 0.0) * 6.0)) * step(d, 0.0);
    float dim = mix(1.0, 0.5, far);
    low = (low + under) * dim;
    high *= dim;
    hue += high + low * 0.15 * far;
    amount += low + high;
  }
  // A faint glow behind the curtains, as their light seen through haze; none below the hems, where
  // the night stays clear.
  float haze = (0.6 + 0.4 * warp.x) * exp(-pow(max(s.y - lean * s.x - 0.12, 0.0) / 0.25, 2.0))
             * smoothstep(0.02, 0.16, s.y - lean * s.x) * 0.1;
  amount += haze;
  // Short joins between the two inks, so little of the sky sits halfway.
  float tint = smoothstep(0.2, 0.8, hue / max(amount, 1e-4));
  // On dark, faint light in the second accent (amber, say) reads as brown: where the light is
  // thin, here or on the calm side, keep it on the cool half of the way.
  float seen = (1.0 - exp(-amount * 1.25)) * calmAt();
  tint = mix(tint, min(tint, 0.45), uDark * (1.0 - smoothstep(0.12, 0.4, seen)));
  return vec4(ink(tint), (1.0 - exp(-amount * 1.25)) * mix(0.92, 0.7, uDark));
}
#elif MODE == 1
// WATER. A wavy surface bends sunlight; where bent rays crowd together, the bottom is bright.
// The surface: two swells that drift across each other, plus the rings. Returned as its slope.
const mat2 TURN = mat2(0.8, 0.6, -0.6, 0.8);
vec2 surfaceSlope(vec2 p) {
  float t = uFlow;
  vec3 a = snoiseGrad(p * 3.0 + vec2(0.075, 0.045) * t);
  vec2 slope = a.yz * 3.0 * 0.0042;
  vec3 b = snoiseGrad(TURN * p * 4.9 - vec2(0.055, -0.09) * t);
  slope += (b.yz * TURN) * 4.9 * 0.0018;   // b.yz * TURN turns the slope back (chain rule)
  for (int i = 0; i < RING_COUNT; i++) {
    vec4 r = uRings[i];
    float age = uTime - r.z;
    if (r.w <= 0.0 || age < 0.0 || age > 6.0) continue;
    vec2 off = p - r.xy;
    float dist = length(off) + 1e-4;
    float radius = 0.02 + age * 0.16;                  // the ring spreads at a steady pace
    float x = (dist - radius) / 0.06;                  // across the ring, in ring widths
    float fade = r.w * exp(-age * 0.75) * uRingOn;
    // height: a wave packet, cos(6x) under a bell exp(-x^2); its slope along the radius:
    float bell = exp(-x * x);
    float dh = fade * 0.0001 * bell * (-2.0 * x * cos(6.0 * x) - 6.0 * sin(6.0 * x)) / 0.06;
    slope += dh * off / dist;
  }
  return slope;
}
vec4 sky(vec2 p) {
  vec2 q = p / uScale;
  // The bottom lies DEPTH below the surface. Light landing at q came through q - DEPTH * slope;
  // how much lands is 1 / (how much that mapping stretches area), the determinant of its
  // Jacobian. Its parts are the slopes of the slope, taken here as small differences.
  float e = 0.004;
  // The bottom is not flat: where it lies deeper the net is larger and softer, where it rises it
  // comes into focus. That variation is what makes it read as depth, not as a pattern.
  float bed = 0.5 + 0.5 * snoise(q * 0.8 + vec2(0.01, 0.0) * uFlow);
  vec2 g = surfaceSlope(q);
  vec2 gx = (surfaceSlope(q + vec2(e, 0.0)) - g) / e;
  vec2 gy = (surfaceSlope(q + vec2(0.0, e)) - g) / e;
  float depth = mix(1.0, 0.75, uProgress) * (0.85 + 0.3 * uEnergy) * (0.75 + 0.45 * bed);
  // Blue light bends a little more than red: a second, slightly deeper focus gives a soft
  // fringe in the second accent beside every line.
  vec2 det;
  for (int k = 0; k < 2; k++) {
    float d = depth * (1.0 + 0.12 * float(k));
    det[k] = (1.0 - d * gx.x) * (1.0 - d * gy.y) - d * d * gx.y * gy.x;
  }
  vec2 lux = 1.0 / (abs(det) + 0.3);                   // 1 / area, kept finite where it folds
  vec2 lines = smoothstep(0.55, 3.3, lux);
  float fringe = max(lines.y - lines.x, 0.0) * 0.5;
  lines *= 0.6 + 0.6 * bed;                            // light fades with the depth of water above
  vec3 tint = ink(0.15 + 0.7 * uProgress), glint = ink(0.25 * uProgress), edge = ink(0.35 + 0.4 * uProgress);
  float base = 0.1 + 0.1 * bed;
  vec3 light = tint * base + glint * lines.x + edge * fringe;
  float amount = base + lines.x + fringe;
  // On a light page the water is a wash, and the lines are where the paper shows through it.
  if (uDark < 0.5) {
    amount = (0.5 + 0.25 * bed) * (1.0 - 0.8 * lines.x);
    light = mix(tint, edge, fringe) * amount;
  }
  return vec4(light / max(amount, 1e-4), (1.0 - exp(-amount * 1.125)) * mix(0.92, 0.62, uDark));
}
#else
// MIST. Three banks of fog, far to near, like hills of cloud seen from a ridge at dawn. Each bank
// is a long, slow ridge: a soft but clear top edge, lit from above, and a fall-off below it, so
// the next bank's top stands out against it. Far banks are smaller, paler and slower; near ones
// larger, deeper and faster (parallax). A low light behind them, in the second accent, glows
// through, away from the calm side.
vec4 sky(vec2 p) {
  float t = uFlow;
  float tall = uCalm.w;
  vec2 frame = frameSize();
  float away = (dot(uCalm.xy, uCalm.xy) > 0.5 && tall < 0.5) ? -uCalm.x : 0.5;
  vec2 lamp = vec2(away * frame.x * 0.6, mix(0.17, 0.34, tall) + 0.08 * uProgress);
  vec2 off = (p - lamp) * vec2(0.6, 1.6);
  float light = exp(-dot(off, off) * mix(7.0, 14.0, uDark));
  float halo = exp(-dot(off, off) * 2.2) * mix(0.12, 0.16, uDark);
  // Premultiplied colour and coverage, built back to front. On dark the wide halo takes the
  // haze's colour: dim amber over black is brown, dim teal is still night.
  vec4 acc = vec4(vGlow * light * 0.7 + mix(vGlow, vMistRim, uDark) * halo, light * 0.7 + halo);
  for (int i = 0; i < 3; i++) {
    float near = float(i) * 0.5;                       // 0 far .. 1 near
    float size = uScale * mix(0.55, 1.35, near);
    vec2 b = p / size + uPointer * 0.02 * (0.2 + near);
    b.x += t * mix(0.005, 0.03, near) + float(i) * 3.7;
    // The ridge: two slow waves along x. Banks lie lower the nearer they are; they lift as the
    // page scrolls.
    float ridge = 0.7 * snoise(vec2(b.x * 1.1, float(i) * 5.3))
                + 0.3 * snoise(vec2(b.x * 2.6, float(i) * 9.1 + t * 0.012));
    float top = mix(mix(0.15, 0.4, tall), mix(-0.2, -0.36, tall), near) + 0.1 * uProgress
              + ridge * mix(0.03, 0.08, near) * uScale;
    // Wisps: flat streaks that drift a little faster than the bank, fraying its edge and body.
    float wisp = fbm(vec2(b.x * 1.8 - t * 0.012, p.y / size * 7.0 + float(i) * 2.3));
    // Billows: the top is not a line but a row of soft rounded heaps that roll slowly along.
    float n = snoise(vec2(b.x * 3.6 - t * 0.01, float(i) * 3.1 + t * 0.006));
    float billow = sqrt(n * n + 0.04);   // abs(), rounded at its crease
    float d = (top - p.y) / size + wisp * 0.014 * (1.0 + near) + billow * 0.02;   // depth below the top
    float edge = smoothstep(-0.01, mix(0.012, 0.02, near), d);      // crisp, never hard
    float fall = mix(0.14, 0.24, near);
    float lit = exp(-max(d, 0.0) / 0.03);                           // the pale top edge
    // How much of this bank covers what lies behind it, and its colour there.
    float cover;
    vec3 c;
    if (uDark > 0.5) {
      // Dark: banks are nearly opaque; the top edge is lit, the body darkens downwards.
      float rim = exp(-max(d, 0.0) / 0.008);
      c = mix(vMistFar, vMistNear, near) * mix(1.0, 0.45, smoothstep(0.0, fall * 1.3, d)) * (0.88 + 0.24 * wisp);
      c = mix(c, vMistRim * mix(1.0, 0.75, near), clamp(lit * mix(0.7, 0.45, near) + rim * 0.45, 0.0, 1.0));
      c += vGlow * light * (1.0 - 0.7 * near) * lit * 0.8;
      // Fog lets some of what is behind it through, most where it thins out below its top.
      cover = edge * mix(0.84, 0.96, near) * (1.0 - 0.3 * smoothstep(0.0, fall * 2.0, d) * (1.0 - near))
            * (0.85 + 0.15 * wisp);
    } else {
      // Light: washes of pigment, densest just under the top and fading to the paper below,
      // with the edge a shade deeper, where a wash dries.
      // The light behind thins the fog in front of it rather than mixing in (peach on mint is grey).
      c = mix(vMistFar, vMistNear, near);
      c = mix(c, vMistRim, lit * 0.5);
      cover = edge * (0.3 + 0.7 * exp(-max(d, 0.0) / fall)) * mix(0.85, 0.95, near) * (0.85 + 0.15 * wisp)
            * (1.0 - 0.45 * light * (1.0 - 0.5 * near));
    }
    acc = acc * (1.0 - cover) + vec4(c * cover, cover);
  }
  return vec4(acc.rgb / max(acc.a, 1e-4), acc.a);
}
#endif

void main() {
  float unit = unitPixels();
  vec2 p = (gl_FragCoord.xy - 0.5 * uResolution) / unit;
  vec4 s = sky(p);
  float alpha = clamp(s.a * uIntensity * calmAt() * (0.85 + 0.3 * uEnergy), 0.0, 0.95);
  gl_FragColor = vec4(s.rgb, alpha);
  #include <colorspace_fragment>
  // Premultiplied out (the material says so), then a film of grain and the dither that stops bands.
  gl_FragColor.rgb = gl_FragColor.rgb * gl_FragColor.a * (1.0 + grain(gl_FragCoord.xy, uTime) * 0.025);
  gl_FragColor += vec4(dither(gl_FragCoord.xy), dither(gl_FragCoord.yx).x);
}`;

export function mount(container, options = {}) {
  const o = { mode: "aurora", calm: "left", calmAmount: 0.8, intensity: 1, speed: 1, scale: 1, ripples: true, ...options };
  const stage = createStage(container, { antialias: false, renderScale: [0.5, 0.6, 0.75], stillTime: 7, ...options });
  if (stage.failed) return stage.handle({ setMode() {} });
  const num = (value, fallback, low, high) => (Number.isFinite(Number(value)) ? Math.min(high, Math.max(low, Number(value))) : fallback);
  const rings = Array.from({ length: RINGS }, () => new THREE.Vector4(0, 0, 0, 0));
  const material = new THREE.ShaderMaterial({
    uniforms: {
      ...stage.uniforms,
      uFlow: { value: 0 },
      uIntensity: { value: num(o.intensity, 1, 0, 3) },
      uScale: { value: num(o.scale, 1, 0.2, 5) },
      uEnergy: { value: 0.5 },
      uRingOn: { value: o.ripples === false ? 0 : 1 },
      uCalm: { value: new THREE.Vector4() },
      uRings: { value: rings },
    },
    vertexShader, fragmentShader,
    transparent: true, premultipliedAlpha: true, depthTest: false, depthWrite: false,
  });
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
  quad.frustumCulled = false;   // placed by the vertex shader, never by the camera
  stage.scene.add(quad);

  let mode = MODES[o.mode] === undefined ? 0 : MODES[o.mode];
  let flow = 0, energy = 0.5, energyTarget = 0.5, nextRing = 0, lastRing = null;
  const speed = num(o.speed, 1, 0, 10);

  // Shader cost follows the quality: octaves, curtains, noise layers and rings are compiled in.
  function build() {
    const q = stage.quality;
    material.defines = {
      MODE: mode,
      FBM_OCTAVES: q.pick(3, 4, 5),
      CURTAINS: q.pick(2, 3, 3),
      RING_COUNT: q.pick(4, RINGS, RINGS),
    };
    material.needsUpdate = true;
    stage.invalidate();
  }
  stage.onQuality(build);

  stage.onResize((size) => {
    const [x, y] = CALM[o.calm] || CALM.left;
    const sideways = x !== 0 && size.aspect < 0.85;   // a phone: the text spans the width
    material.uniforms.uCalm.value.set(x, y, o.calm === "none" ? 0 : num(o.calmAmount, 0.8, 0, 1), sideways ? 1 : 0);
  });

  // A ring where the pointer has moved far enough, or a finger came down. stage.pointer runs -1..1
  // over the container; the shader wants scene units, which depend on the shape of the container.
  stage.onPointer((pointer) => {
    if (mode !== 1 || stage.still || !pointer.active || o.ripples === false) return;
    const now = stage.clock.time;
    const { x, y } = pointer.raw;
    const moved = lastRing ? Math.hypot(x - lastRing.x, y - lastRing.y) : 1;
    if (moved < 0.12 && now - (lastRing ? lastRing.t : -9) < 0.9) return;
    if (moved < 0.02) return;
    const unit = Math.sqrt(stage.size.width * stage.size.height) || 1;
    rings[nextRing].set((x * stage.size.width) / (2 * unit), (y * stage.size.height) / (2 * unit), now, Math.min(1, 0.5 + moved));
    nextRing = (nextRing + 1) % RINGS;
    lastRing = { x, y, t: now };
  });

  stage.onFrame((time, delta) => {
    // Flow is time that runs at the chosen speed and the data's energy, added up frame by frame so a
    // change of speed never makes the picture jump.
    energy = stage.still ? energyTarget : THREE.MathUtils.damp(energy, energyTarget, 1.5, delta);
    flow = stage.still ? time * speed : flow + delta * speed * (0.55 + 0.9 * energy);
    material.uniforms.uFlow.value = flow;
    material.uniforms.uEnergy.value = energy;
  });

  return stage.handle({
    setData(values) {
      const list = Array.from(values || [], Number).filter(Number.isFinite);
      energyTarget = list.length ? Math.min(1, Math.max(0, list.reduce((a, b) => a + b, 0) / list.length)) : 0.5;
      stage.invalidate();
    },
    setMode(name) {
      if (MODES[name] === undefined || MODES[name] === mode) return;
      mode = MODES[name];
      build();
    },
  });
}
