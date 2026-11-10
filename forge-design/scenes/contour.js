/**
 * contour.js: living contour lines (scene kit, look levels 4 and 5).
 *
 * The isolines of a slowly moving height field, drawn the way a cartographer draws a depth chart:
 * thin lines of the same width everywhere on screen, every fifth line stronger (the index line),
 * the faintest tint between levels, lines lit from the upper left so the land reads in relief,
 * small marks on the tops and in the hollows like soundings, and registration crosses of a map grid.
 * The land drifts and reshapes slowly; the pointer lifts a soft hill that the lines flow around.
 * Dark page: fine light lines, index lines in the accent. Light page: ink on paper, the second
 * accent only in the marks.
 *
 *   import { mount } from "./scenes/contour.js";
 *   const chart = mount(document.querySelector(".hero-scene"), { calm: "left" });
 *   addEventListener("scroll", () => chart.setProgress(chart.stage.progressOf(heroSection)));
 *   chart.setData([0.2, 0.8, 0.5, 0.9]);   // ridges across the chart
 *   chart.destroy();                        // when the page or component goes away
 *
 * Options (all optional; the stage's own options, see stage.js, pass straight through):
 *   levels         16: contour intervals over the height range. More is a denser chart.
 *   lineWidth      1: CSS pixels of a contour line. Index lines are 1.7 times as wide.
 *   indexEvery     5: every so many lines is an index line. 0 makes them all the same.
 *   indexStrength  1: how much index lines stand out (0 like the others, 1.5 bolder).
 *   tint           1: the colour between levels (0 none, 2 twice as strong).
 *   relief         1: lines brighter on slopes that face the light, dimmer on the others (0 flat).
 *   marks          true: a dot on each top, a cross in each hollow.
 *   grid           true: small crosses where the lines of a map grid meet.
 *   lift           1: the height of the hill under the pointer (0 none).
 *   speed          1: how fast the land drifts and reshapes. 0 stands still.
 *   scale          1: the size of the landforms. 2 is twice as large.
 *   calm           "left" (default): the side where the text sits. There the land flattens into
 *                  a plain with few lines, and they fade. Also "right", "top", "bottom", "center",
 *                  "none". On a tall, narrow screen "left" and "right" calm the middle band.
 *   calmAmount     0.85: how calm that side is (0 not at all, 1 empty).
 *
 * setProgress(p), 0..1: travel over the map. The chart slides to new ground and zooms in by about
 *   1.6 times, so scrolling feels like moving over a map. Feed it a section's progress:
 *   chart.setProgress(chart.stage.progressOf(section)).
 * setData(values): numbers 0..1, any length. Each value raises one ridge, a range that runs from
 *   top to bottom and is highest in the middle, side by side on the open side of the chart, the
 *   first value on the left (a longer list than 12 is averaged down to 12 ridges). They rise and
 *   settle over a second; an empty list lowers them again.
 * setPointer(x, y), pause(), resume(), destroy(), stage: as stage.js describes.
 *
 * Poster: give the container a child `<img data-scene-poster src="chart.png" alt="">`, shown until
 * the first frame and again when there is no WebGL; or a background image plus the rule
 * `.hero-scene[data-scene="live"] { background-image: none; }`. To make the picture, mount with
 * { still: true } at the size you need and take a screenshot. Under reduced motion the scene draws
 * that same still, with no pointer hill.
 *
 * Cost: one rectangle, one draw call, no textures, no work on the processor beyond a few numbers a
 * frame. Per pixel: 2D simplex noise with its exact slope, 2 lookups for the warp plus 3, 4 or 5
 * layers (low, medium, high), and a few screen-space derivatives. Lines must be sharp, so it draws
 * at full resolution (the stage caps the pixel ratio); on a weak device the stage steps down to
 * fewer layers and a pixel ratio of 1. Fill rate is what it costs: give it the hero, not a page.
 */
import * as THREE from "three";
import { createStage } from "./stage.js";
import { stageUniforms, simplex2D, line, grain } from "./glsl.js";

const CALM = { left: [-1, 0], right: [1, 0], top: [0, 1], bottom: [0, -1], center: [0, 0], none: [0, 0] };
const RIDGES = 12;     // at most this many data ridges; a longer list is averaged down
const MAP = 1.5;       // map units across one scene unit at scale 1: about two hills per screen height

// The rectangle covers the screen whatever the camera does.
const vertexShader = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}`;

const fragmentShader = `
${stageUniforms}
${simplex2D}
${line}
${grain}
uniform vec4 uView;     // where the map is: offset x, y (map units), map units per scene unit, flow
uniform vec4 uStyle;    // contour interval, line width (CSS px), index strength, tint
uniform vec4 uLook;     // marks on, relief, index every, grid on
uniform vec4 uCalm;     // direction x, y; amount; 1 when the screen is tall and narrow
uniform vec3 uHill;     // the pointer hill: centre (scene units), height
uniform float uRidge[${RIDGES}];
uniform float uRidgeCount;
uniform vec2 uRidgeSpan;
uniform float uRidgeHeight;
varying vec2 vUv;

const float WARP = 0.38;         // how far the broad noise pushes the map (map units)
const float HILL = 0.13;         // width of the pointer hill (scene units)
const mat2 rotate45 = mat2(0.70710678, 0.70710678, -0.70710678, 0.70710678);

// Scene units: 1 is the geometric mean of width and height, the middle of the screen is 0.
float unitPixels() { return sqrt(uResolution.x * uResolution.y); }
vec2 frameSize() { return 0.5 * uResolution / unitPixels(); }

// Layers of noise, each twice as fine and half as strong, and the slope of their sum. Layer i is
// read at A q (A doubles and turns 37 degrees each time, so the grids never line up), and by the
// chain rule its slope with respect to q is A-transposed times the slope the noise reports. Each
// layer slides its own way, slowly, finer ones faster: their sum keeps changing shape, which costs
// far less than noise in three dimensions with time as the third. Slowly indeed: a contour moves
// by the change in height over the slope, so a tenth of a level is already a visible step.
vec3 layers(vec2 q, float flow) {
  vec3 sum = vec3(0.0);
  float weight = 0.5;
  mat2 A = mat2(1.0);
  for (int i = 0; i < OCTAVES; i++) {
    float turn = float(i) * 2.4;
    vec3 n = snoiseGrad(A * q + vec2(cos(turn), sin(turn)) * flow * 0.004 * float(i + 1));
    sum += weight * vec3(n.x, transpose(A) * n.yz);
    A = mat2(1.6, 1.2, -1.2, 1.6) * A;
    weight *= 0.42;
  }
  return sum;
}

// The data as ridges: one crest per value, spread evenly over the span uRidgeSpan of the width
// (u 0..1 across the container), each a bell curve across u, as high as its value. Crests are one
// step apart and a bell is 0.3 steps wide, so only the three nearest count. Returns (height, d/du).
vec2 ridges(float u) {
  float n = uRidgeCount;
  float x = (u - uRidgeSpan.x) / (uRidgeSpan.y - uRidgeSpan.x) * n - 0.5;
  float nearest = floor(x + 0.5);
  vec2 sum = vec2(0.0);
  for (int j = -1; j <= 1; j++) {
    float i = nearest + float(j);
    if (i < 0.0 || i > n - 1.0) continue;
    float d = x - i;
    float bell = uRidge[int(i)] * exp(-d * d / 0.09);
    sum += vec2(bell, bell * -2.0 * d / 0.09 * n / (uRidgeSpan.y - uRidgeSpan.x));
  }
  return sum;
}

// The height at p (scene units) and its slope there: vec3(height, d/dx, d/dy).
vec3 terrain(vec2 p) {
  float k = uView.z, flow = uView.w;
  vec2 m = p * k + uView.xy;                              // map coordinates
  // Two broad, slow noises push the map before the layers are read. That draws the land out into
  // long, winding forms, as water and weather shape it, instead of round blobs. The push changes
  // the coordinates by a matrix J (how q moves when m moves): the slope goes back through it.
  vec3 wx = snoiseGrad(m * 0.32 + vec2(0.6, -0.4) * flow * 0.005);
  vec3 wy = snoiseGrad(m * 0.32 + vec2(17.3, -9.1) + vec2(-0.3, 0.7) * flow * 0.005);
  vec2 q = m + WARP * vec2(wx.x, wy.x);
  mat2 J = mat2(1.0) + WARP * 0.32 * mat2(wx.y, wy.y, wx.z, wy.z);
  vec3 f = layers(q, flow);
  // The broad noise that pushes y also lifts and sinks the land as a whole: highlands with dense
  // slopes and wide open basins, instead of the same busy ground everywhere. Free: it is read anyway.
  float h = f.x + 0.42 * wy.x;
  vec2 slope = (transpose(J) * f.yz + 0.42 * 0.32 * wy.yz) * k;
  // Ridges from the data, running from top to bottom, highest in the middle band (a bell curve in
  // y), wobbled by the warp so they do not run ruler-straight: a folded range, read left to right.
  vec2 frame = frameSize();
  float u = p.x / (2.0 * frame.x) + 0.5 + 0.03 * wx.x;
  vec2 ridge = ridges(u);
  float band = exp(-3.0 * p.y * p.y / (frame.y * frame.y));
  // Where the data stands, the land underneath is pressed down a little so the ranges read clearly.
  float press = 1.0 - 0.5 * min(uRidgeHeight / 0.45, 1.0) * band;
  h = h * press + uRidgeHeight * ridge.x * band;
  slope = slope * press + uRidgeHeight * vec2(ridge.y * band / (2.0 * frame.x), ridge.x * band * -6.0 * p.y / (frame.y * frame.y));
  // The pointer hill: a bell curve. Its slope is the bell times -2 r / width^2.
  vec2 r = p - uHill.xy;
  float bell = uHill.z * exp(-dot(r, r) / (HILL * HILL));
  h += bell;
  slope += bell * -2.0 * r / (HILL * HILL);
  return vec3(h, slope);
}

// Lay a colour with coverage a over what is there (premultiplied).
void over(inout vec4 acc, vec3 color, float a) { acc = acc * (1.0 - a) + vec4(color * a, a); }

void main() {
  float unit = unitPixels();
  vec2 p = (gl_FragCoord.xy - 0.5 * uResolution) / unit;
  vec3 t = terrain(p);
  float interval = uStyle.x;

  // Calm: towards the text the land sinks into a plain halfway between two levels, so the lines
  // spread apart and stop, rather than being cut off; what is left there also fades.
  vec2 centred = vUv - 0.5;
  float side = dot(centred, uCalm.xy) * 2.0;
  if (uCalm.w > 0.5 || dot(uCalm.xy, uCalm.xy) < 0.5) side = 1.0 - 2.6 * length(centred * vec2(0.5, 1.5));
  float calmSide = smoothstep(-0.3, 0.45, side);
  float calm = uCalm.z * calmSide;
  float flatten = min(0.97, calm * 1.14);
  float h = mix(t.x, 0.5 * interval, flatten);
  vec2 slope = t.yz * (1.0 - flatten);

  // Pixels from one contour to the next here: the interval over the slope per pixel.
  vec2 perPixel = slope / unit;
  float gap = interval / max(length(perPixel), 1e-7);
  float width = uStyle.y * uPixelRatio;
  float every = max(uLook.z, 1.0);
  // The lines themselves: glsl.js's isoLines turns the distance to the next level into pixels
  // with the screen-space derivative, so every line is equally wide however steep the land is.
  float minor = isoLines(h, interval, width);
  float index = uLook.z > 0.5 ? isoLines(h, interval * every, width * mix(1.0, 1.7, min(uStyle.z, 1.0))) : 0.0;
  // Where the lines crowd closer than a few pixels they would merge into a grey smear and shimmer.
  // A cartographer leaves out the in-between lines on a cliff and keeps the index lines; so here.
  minor *= smoothstep(2.0 * width + 1.0, 4.0 * width + 3.0, gap);
  index *= smoothstep(0.8 * width + 1.0, 2.0 * width + 2.0, gap * every);
  minor *= 1.0 - index;

  // Light from the upper left. "lit" is 1 on a slope that faces it, -1 on one that turns away.
  // Lines brighten on lit slopes and dim on the shaded ones (illuminated contours, after Kitiro
  // Tanaka). Nothing else is shaded: a wash on the slopes reads as dust, not as relief.
  float steep = length(slope);
  float lit = steep > 1e-5 ? dot(-slope / steep, normalize(vec2(-0.8, 0.6))) : 0.0;
  float glow = 1.0 + uLook.y * 0.45 * lit * (uDark * 2.0 - 1.0);

  // Tint between levels, in steps from one index line to the next as on a printed chart: each step
  // one shade, stronger towards the high ground.
  float step_ = interval * every;
  float band = (floor(h / step_) + 0.5) * step_;
  float high = smoothstep(-0.6, 0.6, band);

  // Marks. Near a top or a hollow the land is nearly a bowl, so one Newton step, -H^-1 g (H the
  // curvature and g the slope, both per pixel), points from this pixel to the exact top: its length
  // is the distance in pixels. H is how the exact slope changes from one pixel to the next. A
  // saddle (curvature of mixed sign, det H < 0) gets no mark. Nor does a top with no contour close
  // round it: the bowl, as gently curved as its weakest direction, must reach the next level
  // within about 30 pixels, so marks sit only inside the innermost rings, as on a real chart.
  float mark = 0.0, top = 0.0;
  mat2 H = mat2(dFdx(perPixel), dFdy(perPixel));
  H = 0.5 * (H + transpose(H));
  float det = determinant(H);
  if (uLook.x > 0.5 && det > 0.0) {
    vec2 to = -inverse(H) * perPixel;
    top = H[0][0] < 0.0 ? 1.0 : 0.0;
    float half_ = 0.5 * (H[0][0] + H[1][1]);
    float weakest = abs(half_) - sqrt(max(half_ * half_ - det, 0.0));   // the smaller |eigenvalue|
    float level = (h + 0.5 * dot(perPixel, to)) / interval;   // the height of the top itself
    float toLevel = (top > 0.5 ? level - floor(level) : ceil(level) - level) * interval;
    float reach = sqrt(2.0 * toLevel / max(weakest, 1e-12)) / uPixelRatio;
    float strong = (1.0 - smoothstep(24.0, 32.0, reach)) * smoothstep(0.5, 1.5, abs(level)) * (1.0 - calm);
    float r = length(to) / uPixelRatio;
    float spot = 1.0 - smoothstep(1.5, 2.4, r);                    // a top: a solid dot
    vec2 a = abs(rotate45 * to) / uPixelRatio;                         // a hollow: a small x
    float ex = (1.0 - smoothstep(0.3, 0.95, min(a.x, a.y))) * (1.0 - smoothstep(2.6, 3.4, max(a.x, a.y)));
    mark = strong * mix(ex, spot, top);
  }

  // Registration crosses where the lines of a map grid meet, half a map unit apart; they move with
  // the map, so travel shows even over flat ground.
  vec2 cell = (fract((p * uView.z + uView.xy) / 0.5 + 0.5) - 0.5) * 0.5 / uView.z * unit / uPixelRatio;
  vec2 ac = abs(cell);
  float grid = uLook.w * (1.0 - smoothstep(0.3, 0.9, min(ac.x, ac.y))) * (1.0 - smoothstep(3.0, 4.0, max(ac.x, ac.y)));

  // Colours, all from the page: dark page light on dark with the accent on the index lines; light
  // page ink on paper, the second accent only in the marks.
  float dark = uDark;
  vec3 ink = uText;
  vec3 indexInk = mix(uText, uAccent, dark);
  vec3 markInk = mix(uAccent2, uText, dark);
  vec4 acc = vec4(0.0);
  over(acc, uAccent, uStyle.w * mix(0.0, 0.075, high) * mix(0.7, 1.0, dark) * (1.0 - calm));
  over(acc, uMuted, grid * mix(0.32, 0.3, dark));
  over(acc, ink, minor * mix(0.26, 0.28, dark) * glow);
  over(acc, indexInk, index * mix(0.52, 0.68, dark) * mix(0.55, 1.0, min(uStyle.z, 1.0)) * glow);
  over(acc, markInk, mark * 0.85);
  // Fade with the calm side and softly at the top and bottom edges, where the hero meets the page.
  float edge = smoothstep(0.0, 0.08, vUv.y) * (1.0 - smoothstep(0.9, 1.0, vUv.y));
  acc *= (1.0 - calm * 0.75) * edge;

  gl_FragColor = vec4(acc.rgb / max(acc.a, 1e-5), acc.a);
  #include <colorspace_fragment>
  gl_FragColor.rgb *= gl_FragColor.a;    // premultiplied out, as the material says
  gl_FragColor += vec4(dither(gl_FragCoord.xy), 0.0) * gl_FragColor.a;
}`;

const num = (value, fallback, low, high) => (Number.isFinite(Number(value)) && value !== null && value !== ""
  ? Math.min(high, Math.max(low, Number(value))) : fallback);
const ease = (x) => x * x * (3 - 2 * x);

export function mount(container, options = {}) {
  const o = {
    levels: 16, lineWidth: 1, indexEvery: 5, indexStrength: 1, tint: 1, relief: 1, marks: true, grid: true,
    lift: 1, speed: 1, scale: 1, calm: "left", calmAmount: 0.85, ...options,
  };
  const stage = createStage(container, { antialias: false, stillTime: 9, ...options });
  if (stage.failed) return stage.handle();

  const interval = 1.5 / num(o.levels, 16, 4, 60);   // the land spans about -0.75..0.75
  const speed = num(o.speed, 1, 0, 10);
  const lift = num(o.lift, 1, 0, 3) * 0.55;
  const ridges = new Float32Array(RIDGES), ridgeTarget = new Float32Array(RIDGES);
  let ridgeHeight = 0, ridgeHeightTarget = 0, flow = 0, hill = 0;

  const material = new THREE.ShaderMaterial({
    uniforms: {
      ...stage.uniforms,
      uView: { value: new THREE.Vector4(0, 0, MAP, 0) },
      uStyle: { value: new THREE.Vector4(interval, num(o.lineWidth, 1, 0.5, 4),
        num(o.indexStrength, 1, 0, 2), num(o.tint, 1, 0, 3)) },
      uLook: { value: new THREE.Vector4(o.marks === false ? 0 : 1, num(o.relief, 1, 0, 2),
        Math.round(num(o.indexEvery, 5, 0, 20)), o.grid === false ? 0 : 1) },
      uCalm: { value: new THREE.Vector4() },
      uHill: { value: new THREE.Vector3() },
      uRidge: { value: ridges },
      uRidgeHeight: { value: 0 },
      uRidgeCount: { value: 1 },
      uRidgeSpan: { value: new THREE.Vector2(0, 1) },
    },
    vertexShader, fragmentShader,
    transparent: true, premultipliedAlpha: true, depthTest: false, depthWrite: false,
  });
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
  quad.frustumCulled = false;   // placed by the vertex shader, never by the camera
  stage.scene.add(quad);

  // Shader cost follows the quality: the number of noise layers is compiled in.
  stage.onQuality((quality) => {
    material.defines = { OCTAVES: quality.pick(3, 4, 5) };
    material.needsUpdate = true;
    stage.invalidate();
  });

  stage.onResize((size) => {
    const [x, y] = CALM[o.calm] || CALM.left;
    const sideways = x !== 0 && size.aspect < 0.85;   // a phone: the text spans the width
    material.uniforms.uCalm.value.set(x, y, o.calm === "none" ? 0 : num(o.calmAmount, 0.85, 0, 1), sideways ? 1 : 0);
    // The ridges stand on the open side, not under the text.
    material.uniforms.uRidgeSpan.value.set(x < 0 && !sideways ? 0.45 : 0.04, x > 0 && !sideways ? 0.55 : 0.96);
  });

  stage.onFrame((time, delta) => {
    const u = material.uniforms;
    const still = stage.still;
    const damp = (from, to, rate) => (still ? to : THREE.MathUtils.damp(from, to, rate, delta));
    // Flow is time at the chosen speed, added up so a change of speed never makes the land jump.
    flow = still ? time * speed : flow + delta * speed;
    // Travel: the progress slides the map along a gentle diagonal and zooms in (fewer map units
    // per scene unit); the flow adds a slow drift of its own.
    const p = ease(stage.progressEased);
    // A small screen sees fewer map units, so its landforms keep a size a finger and eye can read.
    const unit = Math.sqrt(stage.size.width * stage.size.height) || 1;
    const fit = Math.pow(Math.min(1, Math.max(0.45, unit / 1100)), 0.75);
    const k = (MAP / num(o.scale, 1, 0.2, 5)) * (1 - 0.38 * p) * fit;
    u.uView.value.set(3.1 + p * 2.6 + flow * 0.012, -1.7 + p * 1.1 + flow * 0.004, k, flow);
    // The pointer hill grows while the pointer is over the scene and sinks when it leaves.
    hill = damp(hill, stage.pointer.inside && !still ? lift : 0, 2.2);
    u.uHill.value.set((stage.pointer.x * stage.size.width) / (2 * unit), (stage.pointer.y * stage.size.height) / (2 * unit), hill);
    // The ridges rise and settle towards the data.
    ridgeHeight = damp(ridgeHeight, ridgeHeightTarget, 2.5);
    for (let i = 0; i < RIDGES; i++) ridges[i] = damp(ridges[i], ridgeTarget[i], 2.5);
    u.uRidgeHeight.value = ridgeHeight;
  });

  return stage.handle({
    setData(values) {
      const list = Array.from(values || [], Number).filter(Number.isFinite).map((v) => Math.min(1, Math.max(0, v)));
      ridgeHeightTarget = list.length ? 0.45 : 0;
      // One ridge per value; a longer list is averaged down to 12, each ridge the mean of its share.
      const count = Math.min(list.length, RIDGES);
      if (count) material.uniforms.uRidgeCount.value = count;
      for (let i = 0; i < count; i++) {
        const from = Math.floor((i * list.length) / count), to = Math.floor(((i + 1) * list.length) / count);
        ridgeTarget[i] = list.slice(from, to).reduce((a, b) => a + b, 0) / (to - from);
      }
      stage.invalidate();
    },
  });
}
