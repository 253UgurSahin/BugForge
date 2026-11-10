/**
 * aurora.js: a shader atmosphere that can sit behind a whole page (scene kit, look levels 4 and 5).
 *
 * One rectangle that fills the container, coloured by one fragment shader. Three moods:
 *   "aurora"  slow curtains of light hanging over silk-like folds of colour, as the northern lights
 *             look from far away: the page background stays the main colour, the accent lights the
 *             hem of each curtain, the second accent its upper edge.
 *   "water"   looking down into clear, shallow water: the moving net of light that a wavy surface
 *             throws on the bottom (caustics), with soft rings that spread where the pointer moves
 *             or a finger taps.
 *   "mist"    banks of fog drifting at three depths, almost without colour.
 * On a dark page it is light in the dark; on a light page a pale wash, like watercolour on paper.
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
 *   to the second accent, the flow turns and slows: aurora curtains sink and lean the other way,
 *   the water grows deeper (a finer, calmer net), the mist lifts. Feed it a section's progress:
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
 * octaves, 2 or 3 curtains), water 7 plus 4 or 8 rings, mist 13 / 19 (three fog banks). A phone
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
${oklab}
varying vec2 vUv;
varying vec3 vLchA, vLchB, vInkMist;
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
  float L = mix(0.86, 0.74, uDark), C = mix(0.95, 0.8, uDark);
  vLchA = lch(linearToOklab(tone(uAccent, L, C)));
  vLchB = lch(linearToOklab(tone(uAccent2, L - 0.02, C)));
  vec3 mist = mixOklab(uMuted, uAccent, 0.12);
  vInkMist = tone(mist, mix(0.7, 0.8, uDark), 0.6);
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
varying vec3 vLchA, vLchB, vInkMist;

// The page's two accents joined along the colour wheel: t = 0 the first, 1 the second. A straight
// mix of two far-apart hues (teal and orange) passes through grey; this walks round the hue
// circle with lightness and colourfulness kept, as the sky does from green to red.
vec3 ink(float t) {
  t = clamp(t, 0.0, 1.0);
  float turn = mod(vLchB.z - vLchA.z + PI, TAU) - PI;   // the short way round
  vec3 c = mix(vLchA, vLchB, t);
  float hue = vLchA.z + turn * t;
  return clamp(oklabToLinear(vec3(c.x, c.y * cos(hue), c.y * sin(hue))), 0.0, 1.0);
}

// Scene units: 1 is the geometric mean of width and height, so a phone and a desktop show
// shapes of about the same size, and the middle of the screen is 0. frame: half the width and
// height in those units (0.63 x 0.4 on a 16:10 desktop, 0.34 x 0.73 on a phone).
float unitPixels() { return sqrt(uResolution.x * uResolution.y); }
vec2 frameSize() { return 0.5 * uResolution / unitPixels(); }

#if MODE == 0
// AURORA. Returns (colour, amount of light); main() lays it over the page.
vec4 sky(vec2 p) {
  float t = uFlow;
  vec2 frame = frameSize();
  vec2 q = p / uScale;
  q.y -= (frame.y - 0.4) * 0.8;   // on a tall screen the sky hangs from the top, above the text
  // Domain warping: read slow noise and push the plane by it before reading anything else.
  // Straight lines then bend into soft folds, like silk lifted by the wind.
  vec2 drift = vec2(0.02, -0.007) * t;
  vec2 warp = vec2(fbm(q * 0.85 + drift), fbm(q * 0.85 + vec2(5.2, -1.3) - drift * 0.7));
  vec2 s = q + warp * (0.07 + 0.07 * uEnergy);
  float lean = mix(0.22, -0.18, uProgress);   // the curtains slope one way, and turn as you scroll
  float hue = 0.0, amount = 0.0;   // the colour (0..1 along ink) is averaged, weighted by light
  for (int i = 0; i < CURTAINS; i++) {
    float fi = float(i);
    float far = fi / float(CURTAINS - 1);              // 0 the nearest curtain .. 1 the farthest
    // Along the curtain: far curtains are stretched, so their folds are smaller, as in perspective.
    // The pointer moves near curtains more than far ones (parallax), so the sky has depth.
    float x = (s.x - uPointer.x * 0.035 * (1.0 - 0.7 * far)) * (1.5 + far * 1.6) + fi * 4.7 + t * (0.035 + 0.02 * fi);
    vec3 wave = snoiseGrad(vec2(x * 0.8, t * 0.04 + fi * 13.0));
    float hem = -0.02 + far * 0.19 - 0.14 * uProgress + lean * s.x + 0.085 * wave.x - uPointer.y * 0.02 * (1.0 - far);
    float d = s.y - hem;                               // height above the hem
    // Brightest just above a soft hem, then a long fade upwards; far curtains are shorter.
    float body = smoothstep(-0.03, 0.01, d) * exp(-max(d, 0.0) * (5.0 + far * 4.0)) * 0.75;
    body += 0.9 * exp(-d * d / 0.0003);                // the hem itself, a thin brighter seam
    float under = 0.3 * exp(min(d, 0.0) * 14.0) * step(d, 0.0);   // its light scattered a little below
    // Where the curtain turns away from us (a steep hem) we look along it, and it is brighter.
    body *= 1.0 + 0.6 * smoothstep(0.3, 1.5, abs(wave.y));
    // Rays: noise stretched along the height, so the light hangs in vertical streaks.
    // Two sizes of ray: broad bands and fine threads inside them.
    float rays = 0.65 * snoise(vec2(x * 8.0, s.y * 0.6 - t * 0.05))
               + 0.35 * snoise(vec2(x * 23.0, s.y * 1.1 - t * 0.08));
    float c = (body * (0.55 + 0.5 * rays) + under) * mix(1.0, 0.5, far);
    // Colour: near curtains in the accent, turning towards the second accent at their tops and in
    // the farthest curtain. Scrolling turns the whole sky further round, and shifts the weight.
    float along = far * 0.75 + smoothstep(0.0, 0.3, d) * 0.4 + (uProgress - 0.3) * 0.7;
    float weight = mix(1.0 - 0.4 * far, 0.6 + 0.6 * far, uProgress);
    hue += along * c * weight;
    amount += c * weight;
  }
  // A faint glow under and round the curtains, as their light seen through haze.
  float haze = (0.6 + 0.4 * warp.x) * exp(-pow(max(s.y - lean * s.x + 0.05, 0.0) * 2.6, 2.0))
             * smoothstep(-0.7, 0.0, s.y) * 0.16;
  hue += (0.15 + 0.5 * uProgress) * haze;
  amount += haze;
  return vec4(ink(hue / max(amount, 1e-4)), amount);
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
  return vec4(light / max(amount, 1e-4), amount * 0.9);
}
#else
// MIST. Three banks of fog, far to near, lit from behind by a soft light. Each bank drifts at its
// own pace (near ones faster: parallax), is larger the nearer it is, and covers what lies behind.
vec4 sky(vec2 p) {
  float t = uFlow;
  vec2 frame = frameSize();
  // The light sits away from the calm side, high up; on a phone at the top.
  vec2 lamp = uCalm.w > 0.5 ? vec2(0.0, frame.y * 0.7) : vec2(-uCalm.x * frame.x * 0.45, frame.y * 0.35);
  float far2 = dot(p - lamp, p - lamp);
  float glow = exp(-far2 * 4.0);                       // the halo the fog makes of it
  float core = exp(-far2 * 70.0);                      // the light itself, a soft disc
  vec3 lampInk = mix(vInkMist * 1.25, ink(0.2), 0.2);
  float swirl = snoise(p * 1.3 + vec2(0.01, 0.0) * t);
  vec2 warp = vec2(swirl, -0.5 * swirl);
  vec3 colour = vec3(0.0);
  float cover = 0.0;
  for (int i = 0; i < 3; i++) {
    float near = float(i) / 2.0;                       // 0 far .. 1 near
    vec2 q = p / (uScale * (0.65 + near * 0.7)) + uPointer * 0.02 * (0.3 + near);
    q.x += t * (0.008 + near * 0.022) + float(i) * 3.1;
    // The top of a bank: a slow wave along x. Banks lie lower the nearer they are, and lift as
    // the page scrolls.
    float top = frame.y * mix(0.45, -0.5, near) + 0.32 * uProgress
              + 0.06 * snoise(vec2(q.x * 0.9, float(i) * 7.0));
    // Inside a bank: flat wisps, stretched sideways and pushed by the shared warp.
    float wisps = fbm(q * vec2(1.1, 4.2) + warp * 0.5);
    // Densest just under its top, thinning downwards, so the next bank's top shows against it.
    float below = top - p.y + 0.05 * wisps;
    float density = smoothstep(-0.03, 0.05, below) * exp(-max(below, 0.0) * mix(4.5, 1.8, near));
    density *= (0.7 + 0.3 * wisps) * mix(0.45, 0.85, near);
    // Lit from behind: fog in front of the light glows, far fog glows most (it is nearest the light).
    // Far banks melt into the page (atmospheric perspective): dimmer on dark, paler on light.
    vec3 fog = vInkMist * mix(0.55 + 0.4 * near, 1.0, 1.0 - uDark) + lampInk * glow * (0.8 - 0.5 * near) * uDark;
    fog *= 1.0 + 0.8 * exp(-max(below, 0.0) * 25.0) * uDark;   // lit from above: a pale top edge
    density *= mix(1.0, 0.8 + 0.55 * near, 1.0 - uDark);
    colour = mix(colour, fog, density);                // "over": the nearer bank covers
    cover += density * (1.0 - cover);
  }
  // On a light page the light shows as thinner fog; on a dark one the glow itself is faint light.
  float thin = 1.0 - 0.35 * glow * (1.0 - uDark);
  colour *= thin;
  cover *= thin;
  float behind = (glow * 0.18 + core * 0.5) * (1.0 - cover) * uDark;   // seen only where fog is thin
  colour += lampInk * behind;
  cover += behind;
  return vec4(colour / max(cover, 1e-4), cover);
}
#endif

void main() {
  float unit = unitPixels();
  vec2 p = (gl_FragCoord.xy - 0.5 * uResolution) / unit;
  vec4 s = sky(p);
  // Calm: towards the side where the text sits the effect fades. side runs 1 at that edge to -1
  // at the opposite one; a tall screen with "left" or "right" calms the middle band instead.
  vec2 centred = vUv - 0.5;
  float side = dot(centred, uCalm.xy) * 2.0;
  if (uCalm.w > 0.5 || dot(uCalm.xy, uCalm.xy) < 0.5) side = 1.0 - 2.4 * length(centred * vec2(0.6, 1.4));
  float calm = 1.0 - uCalm.z * smoothstep(-0.5, 0.45, side);
  // Coverage grows soft and never reaches all: 1 - e^-x saturates the way thin paint does.
  float alpha = (1.0 - exp(-s.a * 1.25)) * uIntensity * calm * mix(0.92, 0.62, uDark);
  alpha = clamp(alpha * (0.85 + 0.3 * uEnergy), 0.0, 0.92);
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
