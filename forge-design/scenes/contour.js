/**
 * contour.js: living contour lines (scene kit, look levels 4 and 5).
 *
 * The isolines of a slowly moving height field, drawn the way a cartographer draws a depth chart:
 * thin lines of the same width everywhere on screen, every fifth line stronger (the index line),
 * a layer tint that steps up one shade per index band so the high ground reads in relief, lines
 * lit from the upper left (brighter and a little wider on the slopes that face the light), small
 * marks on the tops and in the hollows like soundings, and registration crosses of a map grid.
 * The land drifts and reshapes slowly, and the water level creeps, so the lines are always on the
 * move; the pointer lifts a knoll that the lines part and crowd around. Dark page: fine light
 * lines, index lines in the accent. Light page: ink on paper, the second accent only in the marks.
 *
 *   import { mount } from "./scenes/contour.js";
 *   const chart = mount(document.querySelector(".hero-scene"), { calm: "left" });
 *   addEventListener("scroll", () => chart.setProgress(chart.stage.progressOf(heroSection)));
 *   chart.setData([0.2, 0.8, 0.5, 0.9]);   // a range of hills across the chart
 *   chart.destroy();                        // when the page or component goes away
 *
 * Options (all optional; the stage's own options, see stage.js, pass straight through):
 *   levels         16: contour intervals over the height range. More is a denser chart.
 *   lineWidth      1: CSS pixels of a contour line (index lines: see indexStrength).
 *   indexEvery     5: every so many lines is an index line. 0 makes them all the same.
 *   indexStrength  1: how much index lines stand out, 0..2. 0 draws them with the width, colour
 *                  and strength of the others (they only still survive on a cliff); 1 is 1.7
 *                  times as wide, stronger and in the accent on a dark page; 2 is 2.4 times as
 *                  wide and stronger again.
 *   tint           1: the layer tint between index lines (0 none, 2 twice as strong).
 *   relief         1: lines lit from the upper left (0 flat).
 *   marks          true: a dot on each top, a small x in each hollow.
 *   grid           true: small crosses where the lines of a map grid meet.
 *   lift           1: the knoll under the pointer (0 none).
 *   speed          1: how fast the land drifts and the water level creeps. 0 stands still.
 *   tide           1: how fast the level creeps on its own (0: only the drift moves the lines).
 *   scale          1: the size of the landforms. 2 is twice as large.
 *   calm           "left" (default): where the text sits. There the chart thins out, level by
 *                  level: the in-between lines go first, then the index lines, then everything,
 *                  in a soft fade with no edge of its own. Also "right", "top", "bottom",
 *                  "center", "none". On a tall, narrow screen "left", "right" and "center" calm
 *                  a band across the middle, where a phone puts the copy.
 *   calmBox        [x0, y0, x1, y1]: the text block itself, as parts of the container (0..1, from
 *                  the top left), when the presets do not fit the page. The calm covers it and
 *                  fades out round it.
 *   calmAmount     1: how calm that side is (0 not at all, 1 empty behind the text).
 *
 * setProgress(p), 0..1: travel over the map. The chart slides to new ground and zooms in by about
 *   1.6 times, so scrolling feels like moving over a map. The calm stays where the text is.
 *   Feed it a section's progress: chart.setProgress(chart.stage.progressOf(section)).
 * setData(values): numbers 0..1, any length. They raise a range of hills on the open side of the
 *   chart, running from top to bottom, the first value on the left (a list longer than 16 is
 *   averaged down to 16). The range follows the noise of the land, so it reads as terrain, not as
 *   a test pattern. It rises and settles over a second; an empty list lowers it again.
 * setPointer(x, y), pause(), resume(), destroy(), stage: as stage.js describes.
 *
 * Poster: give the container a child `<img data-scene-poster src="chart.png" alt="">`, shown until
 * the first frame and again when there is no WebGL; or a background image plus the rule
 * `.hero-scene[data-scene="live"] { background-image: none; }`. To make the picture, mount with
 * { still: true } at the size you need and take a screenshot. Under reduced motion the scene draws
 * that same still, with no pointer knoll.
 *
 * Cost: one rectangle, one draw call, no textures, no work on the processor beyond a few numbers a
 * frame. Per pixel: 2D simplex noise with its exact slope, 2 lookups for the warp plus 3 or 4
 * layers (3 on low, 4 on medium and high: high differs only in the pixel ratio the stage allows),
 * and a few screen-space derivatives; only the pixels within about 12 device pixels of a top, a
 * hollow or a saddle read the land six times more, to place a mark exactly. Lines must be sharp,
 * so it draws at full resolution (the stage caps the pixel ratio); on a weak device the stage
 * steps down to fewer layers and a pixel ratio of 1. Fill rate is what it costs: give it the
 * hero, not a page. It can run for weeks: the numbers that move the land stay bounded.
 */
import * as THREE from "three";
import { createStage } from "./stage.js";
import { stageUniforms, simplex2D, line, grain } from "./glsl.js";

// The text block per preset, as [x0, y0, x1, y1] parts of the container from the top left.
const CALM = {
  left: [0, 0.27, 0.37, 0.73], right: [0.63, 0.27, 1, 0.73], top: [0, 0, 1, 0.3], bottom: [0, 0.7, 1, 1],
  center: [0.3, 0.32, 0.7, 0.68],
};
const NARROW = [0, 0.34, 1, 0.66];   // a phone: the copy spans the width, in a band across the middle
const RIDGES = 16;     // at most this many data values; a longer list is averaged down
const MAP = 1.5;       // map units across one scene unit at scale 1: about two hills per screen height
const ORIGIN = [3.1, -1.7];   // where the map starts: ground with a good mix of hills and basins (by eye)
const TRAVEL = [2.6, 1.1];    // how far setProgress(1) moves it: about 1.5 screens along a gentle diagonal
const DRIFT = [0.012, 0.004]; // map units a second the map drifts: a hill crosses its own width in ~80 s
// The flow is bent round a circle 2 / BENT flow-seconds across, so the numbers the shader gets stay
// under a few hundred map units however long the page stays open (float32 would lose the finest
// layer and the marks after a few days of straight drift). One turn takes about 17 hours at speed 1,
// far too slow to see.
const BENT = 1e-4;

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
uniform vec3 uView;     // where the map is: offset x, y (map units), map units per scene unit
uniform vec2 uFlow;     // the flow: as long as the time run at the chosen speed, bent round a wide
                        // circle so it stays small (see the onFrame code)
uniform vec4 uStyle;    // contour interval, line width (CSS px), index strength, tint
uniform vec4 uLook;     // marks on, relief, index every, grid on
uniform vec4 uCalmBox;  // the text block: x0, y0, x1, y1 (0..1 from the top left)
uniform vec2 uCalm;     // how calm (0..1), the width of the fade round the block (scene units)
uniform vec4 uHill;     // the pointer knoll: centre (scene units), presence 0..1, height
uniform float uTide;    // the water level, in heights: added to the land, so the lines creep
uniform float uRidge[${RIDGES}];
uniform float uRidgeCount;
uniform vec2 uRidgeSpan;
uniform float uRidgeHeight;
varying vec2 vUv;

const float WARP = 0.38;         // how far the broad noise pushes the map (map units)
const float KNOLL = 0.1;         // width of the knoll under the pointer (scene units)
const float LENS = 0.2;          // width of the ground the knoll pushes aside (scene units)
const float PUSH = 0.62;         // how far it is pushed: under 1, or the ground would fold over itself
const float SLIDE = 0.006;       // noise units a second each layer slides, times its number
const float BEND = 0.007;        // noise units a second the broad push slides: whole forms bend in minutes
const float BROAD = 0.32;        // the broad push is read at this part of the map's scale: about three
                                 // times wider than the first layer, so it bends hills, not slopes
const float SWELL = 0.42;        // how much the broad push lifts and sinks the land (the first layer is 0.5)
const mat2 rotate45 = mat2(0.70710678, 0.70710678, -0.70710678, 0.70710678);

// Scene units: 1 is the geometric mean of width and height, the middle of the screen is 0.
float unitPixels() { return sqrt(uResolution.x * uResolution.y); }
vec2 frameSize() { return 0.5 * uResolution / unitPixels(); }

// The flow carried in the direction dir: dir times the flow at first, turning with the circle.
vec2 drift(vec2 dir) { return mat2(dir, vec2(-dir.y, dir.x)) * uFlow; }

// Layers of noise, each twice as fine and 0.42 as strong (a little under half: smooth land, with the
// fine layers only as grain), and the slope of their sum. Layer i is read at A q (A doubles and turns 37 degrees each time, so the grids never line up), and by the
// chain rule its slope with respect to q is A-transposed times the slope the noise reports. Each
// layer slides its own way, slowly, finer ones faster: their sum keeps changing shape, which costs
// far less than noise in three dimensions with time as the third.
vec3 layers(vec2 q) {
  vec3 sum = vec3(0.0);
  float weight = 0.5;
  mat2 A = mat2(1.0);
  for (int i = 0; i < OCTAVES; i++) {
    float turn = float(i) * 2.4;   // 2.4 radians apart, near the golden angle: no two slide alike
    vec3 n = snoiseGrad(A * q + drift(vec2(cos(turn), sin(turn))) * SLIDE * float(i + 1));
    sum += weight * vec3(n.x, transpose(A) * n.yz);
    A = mat2(1.6, 1.2, -1.2, 1.6) * A;
    weight *= 0.42;
  }
  return sum;
}

// The data as a range of hills: the values, spread evenly over the span uRidgeSpan of the width
// (u 0..1 across the container), joined into one smooth profile (each value weighs in with a bell
// curve half a step wide, and the weights are shared out), fading to nothing past either end.
// Returns (height 0..1, d/du).
vec2 profile(float u) {
  float n = uRidgeCount;
  float span = uRidgeSpan.y - uRidgeSpan.x;
  float x = (u - uRidgeSpan.x) / span * n - 0.5;      // value i sits at x = i
  float nearest = floor(x + 0.5);
  float w = 0.0, f = 0.0, dw = 0.0, df = 0.0;
  for (int j = -2; j <= 2; j++) {
    float i = clamp(nearest + float(j), 0.0, n - 1.0);
    if (abs(i - nearest - float(j)) > 0.5) continue;
    float d = x - i;
    float b = exp(-2.0 * d * d);
    float v = uRidge[int(i)];
    w += b; f += b * v; dw += -4.0 * d * b; df += -4.0 * d * b * v;
  }
  if (w < 1e-5) return vec2(0.0);
  float value = f / w, slope = (df - value * dw) / w;
  float t0 = clamp(x + 1.2, 0.0, 1.0), t1 = clamp(n + 0.2 - x, 0.0, 1.0);
  float e0 = t0 * t0 * (3.0 - 2.0 * t0), e1 = t1 * t1 * (3.0 - 2.0 * t1);
  float de = 6.0 * t0 * (1.0 - t0) * e1 - 6.0 * t1 * (1.0 - t1) * e0;
  return vec2(value * e0 * e1, (slope * e0 * e1 + value * de) * n / span);
}

// The land at q (scene units), with no pointer: vec3(height, d/dx, d/dy).
vec3 land(vec2 q) {
  float k = uView.z;
  vec2 m = q * k + uView.xy;                              // map coordinates
  // Two broad, slow noises push the map before the layers are read. That draws the land out into
  // long, winding forms, as water and weather shape it, instead of round blobs. The push changes
  // the coordinates by a matrix J (how the read point moves when m moves): the slope goes back
  // through it.
  vec3 wx = snoiseGrad(m * BROAD + drift(vec2(0.6, -0.4)) * BEND);
  vec3 wy = snoiseGrad(m * BROAD + vec2(17.3, -9.1) + drift(vec2(-0.3, 0.7)) * BEND);   // 17.3, -9.1: far from wx
  vec2 r = m + WARP * vec2(wx.x, wy.x);
  mat2 J = mat2(1.0) + WARP * BROAD * mat2(wx.y, wy.y, wx.z, wy.z);
  vec3 f = layers(r);
  // The broad noise that pushes y also lifts and sinks the land as a whole: highlands with dense
  // slopes and wide open basins, instead of the same busy ground everywhere.
  float h = f.x + SWELL * wy.x;
  vec2 slope = (transpose(J) * f.yz + SWELL * BROAD * wy.yz) * k;
  if (uRidgeHeight > 0.001) {
    // The data range runs from top to bottom, highest in the middle band, and follows the land:
    // its line wanders with the warp (by up to about 7 and 3.5 percent of the width), and the
    // land's own folds stay on its flanks.
    vec2 frame = frameSize();
    float wander = 0.07 * wx.x + 0.035 * wy.x;
    float u = q.x / (2.0 * frame.x) + 0.5 + wander;
    vec2 dudq = vec2(1.0 / (2.0 * frame.x), 0.0) + (0.07 * wx.yz + 0.035 * wy.yz) * BROAD * k;
    vec2 ridge = profile(u);
    // The band: full across the middle, a fifth (exp(-1.6)) at the top and bottom edges.
    float yy = q.y / frame.y;
    float band = exp(-1.6 * yy * yy);
    vec2 dband = vec2(0.0, band * -3.2 * yy / frame.y);
    // The range is 0.8 of its height plus a quarter of the land's own relief, so the land's texture
    // rides on it.
    float lift = uRidgeHeight * (0.8 + 0.25 * f.x);
    float rise = lift * ridge.x * band;
    vec2 drise = uRidgeHeight * (0.25 * f.yz * k * ridge.x * band)
               + lift * (ridge.y * dudq * band + ridge.x * dband);
    // The ground under the band sinks, by up to 45 percent at the full height the JS sets (0.5),
    // so the range stands out of a low plain instead of piling onto the hills.
    float press = 1.0 - 0.45 * min(uRidgeHeight / 0.5, 1.0) * band;
    vec2 dpress = -0.45 * min(uRidgeHeight / 0.5, 1.0) * dband;
    slope = slope * press + h * dpress + drise;
    h = h * press + rise;
  }
  return vec3(h, slope);
}

// The land at p (scene units) as the pointer shapes it. Round the pointer the ground is pushed
// outwards (the point read moves towards the pointer, p' = c + r (1 - s), s a bell), so the lines
// part there and crowd round the rim; then a knoll rises in the gap. vec3(height, d/dx, d/dy).
vec3 terrain(vec2 p) {
  vec2 r = p - uHill.xy;
  float rr = dot(r, r);
  float s = PUSH * uHill.z * exp(-rr / (LENS * LENS));
  vec3 t = land(uHill.xy + r * (1.0 - s));
  // How p' moves with p: (1 - s) I + (2 s / LENS^2) r r^T, the same both ways round.
  mat2 J = mat2(1.0 - s) + (2.0 * s / (LENS * LENS)) * mat2(r.x * r.x, r.x * r.y, r.x * r.y, r.y * r.y);
  vec2 slope = J * t.yz;
  float bell = uHill.z * uHill.w * exp(-rr / (KNOLL * KNOLL));
  return vec3(t.x + bell, slope - bell * 2.0 * r / (KNOLL * KNOLL));
}

// How calm the chart is at a pixel: 1 on the text block, falling off smoothly round it. Measured
// in scene units, so the fade is as wide on a phone as on a wall screen, relative to its size.
float calmAt(vec2 pixel) {
  vec2 uv = vec2(pixel.x / uResolution.x, 1.0 - pixel.y / uResolution.y);
  vec2 outside = max(max(uCalmBox.xy - uv, uv - uCalmBox.zw), 0.0) * uResolution / unitPixels();
  float d = clamp(length(outside) / uCalm.y, 0.0, 1.0);
  return uCalm.x * (1.0 - d * d * (3.0 - 2.0 * d));
}

// Lay a colour with coverage a over what is there (premultiplied).
void over(inout vec4 acc, vec3 color, float a) { acc = acc * (1.0 - a) + vec4(color * a, a); }

void main() {
  float unit = unitPixels();
  vec2 p = (gl_FragCoord.xy - 0.5 * uResolution) / unit;
  vec3 t = terrain(p);
  float interval = uStyle.x;
  float h = t.x + uTide;
  vec2 slope = t.yz;

  // The calm: the pointer clears a little of it, so the plain answers the hand too.
  vec2 toHill = p - uHill.xy;
  // Most of all round the edge of the text block, hardly at all behind the words themselves: within
  // about a quarter of a scene unit of the hand (exp(-d^2 / 0.06)) it takes away up to 0.75 of the
  // calm, less as the calm nears 1, and only 0.12 (3 x 0.04) where the calm is full.
  float calm = calmAt(gl_FragCoord.xy);
  calm = max(calm - uHill.z * exp(-dot(toHill, toHill) / 0.06) * min(0.75, 3.0 * (1.04 - calm)), 0.0);

  // Pixels from one contour to the next here: the interval over the slope per pixel.
  vec2 perPixel = slope / unit;
  float gap = interval / max(length(perPixel), 1e-7);
  float every = max(uLook.z, 1.0);

  // Light from the upper left. "lit" is 1 on a slope that faces it, -1 on one that turns away.
  // On a dark page lit lines are brighter and a little wider; on paper the shaded side gets the
  // heavier ink (illuminated contours, after Kitiro Tanaka).
  float steep = length(slope);
  float lit = steep > 1e-5 ? dot(-slope / steep, normalize(vec2(-0.8, 0.6))) : 0.0;
  float shade = uLook.y * lit * (uDark * 2.0 - 1.0);
  float width = uStyle.y * uPixelRatio * (1.0 + 0.22 * shade);
  float glow = 1.0 + 0.5 * shade;

  // The lines themselves: glsl.js's isoLines turns the distance to the next level into pixels
  // with the screen-space derivative, so every line is equally wide however steep the land is.
  // indexStrength: 0..1 brings in the width, the colour and the strength of an index line; past 1
  // only width and strength grow (1.7 times as wide at 1, 2.4 at 2).
  float strength = uStyle.z, bold = min(strength, 1.0);
  float minor = isoLines(h, interval, width);
  float index = uLook.z > 0.5 ? isoLines(h, interval * every, width * (1.0 + 0.7 * strength)) : 0.0;
  // Where the lines crowd closer than a few pixels they would merge into a grey smear and shimmer.
  // A cartographer leaves out the in-between lines on a cliff and keeps the index lines; so here.
  minor *= smoothstep(2.0 * width + 1.0, 4.0 * width + 3.0, gap);
  index *= smoothstep(0.8 * width + 1.0, 2.0 * width + 2.0, gap * every);
  minor *= 1.0 - index;

  // Marks. Near a top or a hollow the land is nearly a bowl, so one Newton step, -H^-1 g (H the
  // curvature and g the slope, both per pixel), points from this pixel to the top. H is how the
  // exact slope changes from one pixel to the next. Close to the top the land is read again
  // at that point and the step is taken twice more: every pixel of a mark then agrees on where the
  // top is, how high it is and how calm the chart is there, so a mark is drawn whole or not at
  // all. A saddle (det H < 0) gets no mark. A top gets one only when the innermost ring round it
  // is small (within about 30 pixels), as on a real chart.
  float mark = 0.0;
  mat2 H = mat2(dFdx(perPixel), dFdy(perPixel));
  H = 0.5 * (H + transpose(H));
  vec2 to = -inverse(H) * perPixel;
  // A ring round a top or a hollow so small (under about 3 CSS pixels at its longest) that it would
  // print as a speck of dust. In a bowl the drop to the top, half of g.to, is the same all round the
  // ring, and so is its long radius, sqrt(2 drop / the weaker curvature): every pixel of the ring
  // finds the same answer from its own numbers, so the ring goes whole. It goes with or without marks.
  float tiny = 0.0;
  float detH = determinant(H);
  if (detH > 0.0) {
    float midH = 0.5 * (H[0][0] + H[1][1]);
    float weakH = abs(midH) - sqrt(max(midH * midH - detH, 0.0));
    float span = sqrt(abs(dot(perPixel, to)) / max(weakH, 1e-12)) / uPixelRatio;
    tiny = 1.0 - smoothstep(2.5, 4.0, span);
  }
  if (uLook.x > 0.5 && length(to) < 12.0 * uPixelRatio) {
    // At the first guess, read the land and its curvature exactly (the slope four pixels on) and
    // step again; there, close to the top for every pixel round it, read them once more and take
    // the last step. So every pixel of a mark finds the same top, to a fraction of a pixel, and
    // judges it by the same numbers. (One loop, not six calls: the shader stays small and
    // compiles fast on weak devices.)
    vec2 at = gl_FragCoord.xy + to;
    vec3 c1 = vec3(0.0), cx = vec3(0.0);
    mat2 C = mat2(1.0);
    for (int i = 0; i < 6; i++) {
      int k = i - (i / 3) * 3;
      vec2 pixel = at + vec2(k == 1 ? 4.0 : 0.0, k == 2 ? 4.0 : 0.0);
      vec3 here = terrain((pixel - 0.5 * uResolution) / unit);
      if (k == 0) c1 = here;
      else if (k == 1) cx = here;
      else {
        C = mat2(cx.yz - c1.yz, here.yz - c1.yz) / (4.0 * unit);
        C = 0.5 * (C + transpose(C));
        if (i == 2 && abs(determinant(C)) > 1e-24) at -= inverse(C) * (c1.yz / unit);
      }
    }
    float det = determinant(C);
    float half_ = 0.5 * (C[0][0] + C[1][1]);
    float root = sqrt(max(half_ * half_ - det, 0.0));
    float weakest = abs(half_) - root, strongest = abs(half_) + root;   // |eigenvalues|
    // A saddle gets no mark, nor does a top drawn out into a long ridge or trough (its curvature
    // along under a quarter of that across): there no single point is the top, and the pixels
    // round it would not agree where it is.
    if (det > 0.0) {
      vec2 g = c1.yz / unit;
      vec2 last = -inverse(C) * g;
      vec2 centre = at + last;
      to = centre - gl_FragCoord.xy;
      float top = C[0][0] < 0.0 ? 1.0 : 0.0;
      float level = (c1.x + uTide + 0.5 * dot(g, last)) / interval;       // the height of the top itself
      float toLevel = (top > 0.5 ? level - floor(level) : ceil(level) - level) * interval;
      float reach = sqrt(2.0 * toLevel / max(weakest, 1e-12)) / uPixelRatio;   // CSS px to the innermost ring
      float calmThere = calmAt(centre);
      // Settled: the last step was under a pixel, so the steps have closed in on one point. On a
      // flat stretch with fine ripples they jump about instead, and a pixel can land next to a
      // "top" that its neighbours never find: a speck. Those get no mark.
      float settled = 1.0 - smoothstep(0.35, 0.9, length(last));
      float r = length(to) / uPixelRatio;
      float spot = 1.0 - smoothstep(1.4, 2.3, r);                         // a top: a solid dot
      vec2 a = abs(rotate45 * to) / uPixelRatio;                          // a hollow: a small x
      float ex = (1.0 - smoothstep(0.35, 0.95, min(a.x, a.y))) * (1.0 - smoothstep(2.6, 3.4, max(a.x, a.y)));
      // Every test fades in over a range rather than switching, so a top on the edge of one is
      // drawn whole and faint, never in pieces.
      float keep = settled * smoothstep(0.22, 0.35, weakest / strongest) * (1.0 - smoothstep(20.0, 38.0, reach))
                 * (1.0 - smoothstep(0.0, 0.3, calmThere));
      mark = keep * mix(ex, spot, top);
    }
  }
  minor *= 1.0 - tiny;
  index *= 1.0 - tiny;

  // Registration crosses where the lines of a map grid meet, half a map unit apart; they move with
  // the map, so travel shows even over flat ground. Each fades by the calm at its own centre.
  vec2 cell = (fract((p * uView.z + uView.xy) / 0.5 + 0.5) - 0.5) * 0.5 / uView.z * unit;
  vec2 ac = abs(cell) / uPixelRatio;
  float grid = uLook.w * (1.0 - smoothstep(0.3, 0.9, min(ac.x, ac.y))) * (1.0 - smoothstep(3.0, 4.0, max(ac.x, ac.y)));
  grid *= 1.0 - smoothstep(0.0, 0.5, calmAt(gl_FragCoord.xy - cell));

  // Layer tint: one shade per index band, a step at every index line as on a printed chart, a
  // few percent stronger with each band up. It goes first in the calm, so a step in the tint
  // never shows without its line.
  float step_ = interval * every;
  // Low ground and water get none, so the tint never lies over the whole chart as a sheet.
  float bandMid = (floor(h / step_) + 0.5) * step_ - uTide;
  // None at a height of -0.3 and below, full from 0.6 up (the land spans about -0.75..0.75).
  float high = clamp((bandMid + 0.3) / 0.9, 0.0, 1.0);
  float tintCalm = (1.0 - calm) * (1.0 - calm) * smoothstep(0.0, 0.3, vUv.y) * smoothstep(0.0, 0.3, 1.0 - vUv.y);

  // The calm thins the chart level by level: the in-between lines go first, the index lines last.
  float keepMinor = 1.0 - smoothstep(0.05, 0.55, calm);
  float keepIndex = 1.0 - smoothstep(0.3, 0.92, calm);

  // Colours, all from the page: dark page light on dark with the accent on the index lines; light
  // page ink on paper, the second accent only in the marks.
  float dark = uDark;
  // The strengths are by eye: a line 0.3, an index line 0.62 on paper and 0.72 on dark (light on
  // dark looks thinner), the grid a little stronger than a line because its crosses are short, and
  // the tint's top shade 8.5 percent of the accent on paper, 12 on dark, where it shows less.
  vec3 indexInk = mix(uText, mix(uText, uAccent, dark), bold);
  vec3 markInk = mix(uAccent2, uText, dark);
  float indexAlpha = mix(0.3, mix(0.62, 0.72, dark), bold) * (1.0 + 0.35 * max(strength - 1.0, 0.0));
  vec4 acc = vec4(0.0);
  over(acc, uAccent, uStyle.w * high * mix(0.085, 0.12, dark) * tintCalm);
  over(acc, uMuted, grid * mix(0.36, 0.32, dark));
  over(acc, uText, minor * 0.3 * glow * keepMinor);
  over(acc, indexInk, index * indexAlpha * glow * keepIndex);
  over(acc, markInk, mark * 0.9);
  // Fade softly at the top and bottom edges, where the hero meets the page.
  float edge = smoothstep(0.0, 0.14, vUv.y) * smoothstep(0.0, 0.14, 1.0 - vUv.y);
  acc *= edge * edge * (3.0 - 2.0 * edge);

  gl_FragColor = vec4(acc.rgb / max(acc.a, 1e-5), acc.a);
  #include <colorspace_fragment>
  gl_FragColor.rgb *= gl_FragColor.a;    // premultiplied out, as the material says
  gl_FragColor += vec4(dither(gl_FragCoord.xy), dither(gl_FragCoord.yx).x) * min(gl_FragColor.a * 8.0, 1.0);
}`;

const num = (value, fallback, low, high) => (Number.isFinite(Number(value)) && value !== null && value !== ""
  ? Math.min(high, Math.max(low, Number(value))) : fallback);
const ease = (x) => x * x * (3 - 2 * x);

function calmBox(o, aspect) {
  if (o.calm === "none") return null;
  if (Array.isArray(o.calmBox) && o.calmBox.length === 4) {
    const [x0, y0, x1, y1] = o.calmBox.map((v) => num(v, 0, 0, 1));
    return [Math.min(x0, x1), Math.min(y0, y1), Math.max(x0, x1), Math.max(y0, y1)];
  }
  const name = CALM[o.calm] ? o.calm : "left";
  if (aspect < 0.85 && (name === "left" || name === "right" || name === "center")) return NARROW;
  return CALM[name];
}

export function mount(container, options = {}) {
  const o = {
    levels: 16, lineWidth: 1, indexEvery: 5, indexStrength: 1, tint: 1, relief: 1, marks: true, grid: true,
    lift: 1, speed: 1, tide: 1, scale: 1, calm: "left", calmAmount: 1, ...options,
  };
  const stage = createStage(container, { antialias: false, stillTime: 9, ...options });
  if (stage.failed) return stage.handle();

  const interval = 1.5 / num(o.levels, 16, 4, 60);   // the land spans about -0.75..0.75
  const speed = num(o.speed, 1, 0, 10);
  const tide = num(o.tide, 1, 0, 5) * interval * 0.08;   // heights a second: a level in about 12 s
  const lift = num(o.lift, 1, 0, 3);
  const ridges = new Float32Array(RIDGES), ridgeTarget = new Float32Array(RIDGES);
  let ridgeHeight = 0, ridgeHeightTarget = 0, flow = 0, presence = 0;

  const material = new THREE.ShaderMaterial({
    uniforms: {
      ...stage.uniforms,
      uView: { value: new THREE.Vector3(0, 0, MAP) },
      uFlow: { value: new THREE.Vector2(0, 0) },
      uStyle: { value: new THREE.Vector4(interval, num(o.lineWidth, 1, 0.5, 4),
        num(o.indexStrength, 1, 0, 2), num(o.tint, 1, 0, 3)) },
      uLook: { value: new THREE.Vector4(o.marks === false ? 0 : 1, num(o.relief, 1, 0, 2),
        Math.round(num(o.indexEvery, 5, 0, 20)), o.grid === false ? 0 : 1) },
      uCalmBox: { value: new THREE.Vector4(0, 0, 0, 0) },
      uCalm: { value: new THREE.Vector2(0, 0.2) },
      uHill: { value: new THREE.Vector4() },
      uTide: { value: 0 },
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

  // Shader cost follows the quality: the number of noise layers is compiled in. High keeps 4: a
  // fifth layer is so fine that its ripples, not the land, set the tops, and the flats fill with marks.
  stage.onQuality((quality) => {
    material.defines = { OCTAVES: quality.pick(3, 4, 4) };
    material.needsUpdate = true;
    stage.invalidate();
  });

  stage.onResize((size) => {
    const box = calmBox(o, size.aspect);
    const u = material.uniforms;
    u.uCalmBox.value.set(...(box || [0, 0, 0, 0]));
    u.uCalm.value.set(box ? num(o.calmAmount, 1, 0, 1) : 0, size.aspect < 0.85 ? 0.24 : 0.2);
    // The data range stands on the open side, not under the text.
    const open = box && box[2] - box[0] < 0.7 ? (box[0] < 0.5 - (box[2] - 0.5) ? [box[2] + 0.06, 0.97] : [0.03, box[0] - 0.06]) : [0.04, 0.96];
    u.uRidgeSpan.value.set(open[0], Math.max(open[1], open[0] + 0.2));
  });

  stage.onFrame((time, delta) => {
    const u = material.uniforms;
    const still = stage.still;
    const damp = (from, to, rate) => (still ? to : THREE.MathUtils.damp(from, to, rate, delta));
    // Flow is time at the chosen speed, added up so a change of speed never makes the land jump.
    flow = still ? time * speed : flow + delta * speed;
    // The level repeats every index band, so it is kept within one: the lines, the tint and the
    // marks look the same, and the number never grows.
    u.uTide.value = (flow * tide) % (interval * Math.max(u.uLook.value.z, 1));
    // The flow along its circle (BENT above): (flow, 0) at first, bounded for ever.
    const fx = Math.sin(BENT * flow) / BENT, fy = (1 - Math.cos(BENT * flow)) / BENT;
    u.uFlow.value.set(fx, fy);
    // Travel: the progress slides the map along a gentle diagonal and zooms in (fewer map units
    // per scene unit); the flow adds a slow drift of its own.
    const p = ease(stage.progressEased);
    // A small screen sees fewer map units, so its landforms keep a size a finger and eye can read:
    // below a scene unit of 1100 px (a laptop) the map shrinks with the 0.75 power of the size, to
    // at most 0.55 (0.45 ^ 0.75) times as many map units on a small phone.
    const unit = Math.sqrt(stage.size.width * stage.size.height) || 1;
    const fit = Math.pow(Math.min(1, Math.max(0.45, unit / 1100)), 0.75);
    const k = (MAP / num(o.scale, 1, 0.2, 5)) * (1 - 0.38 * p) * fit;
    u.uView.value.set(ORIGIN[0] + p * TRAVEL[0] + DRIFT[0] * fx - DRIFT[1] * fy,
      ORIGIN[1] + p * TRAVEL[1] + DRIFT[1] * fx + DRIFT[0] * fy, k);
    // The knoll grows while the pointer is over the scene and sinks when it leaves.
    presence = damp(presence, stage.pointer.inside && !still && lift > 0 ? 1 : 0, 4);
    u.uHill.value.set((stage.pointer.x * stage.size.width) / (2 * unit), (stage.pointer.y * stage.size.height) / (2 * unit),
      presence, lift * 0.4);   // 0.4 high at lift 1: about four contour intervals at 16 levels
    // The range rises and settles towards the data.
    ridgeHeight = damp(ridgeHeight, ridgeHeightTarget, 2.5);
    for (let i = 0; i < RIDGES; i++) ridges[i] = damp(ridges[i], ridgeTarget[i], 2.5);
    u.uRidgeHeight.value = ridgeHeight;
  });

  return stage.handle({
    setData(values) {
      const list = Array.from(values || [], Number).filter(Number.isFinite).map((v) => Math.min(1, Math.max(0, v)));
      ridgeHeightTarget = list.length ? 0.5 : 0;   // a third of the land's height range: about five lines
      // One value per slot; a longer list is averaged down to 16, each slot the mean of its share.
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
