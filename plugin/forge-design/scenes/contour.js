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
 *   chart.stage.onFrame(() => chart.setProgress(chart.stage.progressOf(heroSection)));   // no scroll listener
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
 *                  fades out round it. Given, it wins over calm ("none" included).
 *   calmAmount     1: how calm that side is (0 not at all, 1 empty behind the text).
 *   view           "flat" (default): the chart drawn straight onto the screen. "tilt": the chart as
 *                  a sheet of land seen at an angle, in perspective, with its relief raised in 3D:
 *                  the hills stand up and hide what lies behind them, the pointer turns the view a
 *                  few degrees, the grid crosses lie on the land, and the marks give way to the
 *                  page's own labels (onLabels, with an outline).
 *   angle          40: in "tilt", how high the eye stands above the land, in degrees: 90 looks
 *                  straight down, 25 looks low over it.
 *   height         1: in "tilt", how high the relief stands (0 lies flat, 2 twice as high).
 *   outline        the app's own place: one lake, one trail, one plot. A GeoJSON geometry, Feature
 *                  or FeatureCollection (Polygon, MultiPolygon, LineString, MultiLineString, as
 *                  [lon, lat]), or a list of rings and lines of [x, y] points with y up (flip the y
 *                  of an SVG), where a ring is a list whose last point is its first. An area (a
 *                  ring) gets its edge as one firm line and, inside, lines that follow that edge
 *                  round islands and into bays (see sink); a line (a trail) is drawn as a route over
 *                  the land, cleared of the lines under it, with a dot at each end. The outline
 *                  stays put while the land round it drifts, and fits into the open part of the
 *                  container beside the calm (or into fitBox). marks are off with an outline: they
 *                  would read as soundings the app never took.
 *   sink           1: how an area's inside lies. 1 a basin, deepest furthest from its edge, its
 *                  lines closest along the edge (a lake); 0 flat, its edge and a tint only (a plot,
 *                  a park); -1 rising the same way (an island, a hill). The shape comes from the
 *                  outline alone, never from measured depths: say so in a caption on the page.
 *   land           how much of the kit's own invented land shows: 1 without an outline; with one
 *                  0.35, fading out away from the outline. 0 draws only the outline.
 *   fill           the colour inside an area: a CSS colour or a token name ("--color-water").
 *                  Default: the accent.
 *   fitBox         [x0, y0, x1, y1]: the part of the container the outline fills, as parts of the
 *                  container from the top left. Default: the largest open part beside the calm.
 *   labels         places to follow, with an outline: [x, y] points in the outline's own units
 *                  ([lon, lat] for GeoJSON), or "middle" (deepest inside the area; the middle of a
 *                  trail when there is no area).
 *   onLabels       fn(points), points [{ x, y, visible }] in CSS pixels from the container's top
 *                  left, one per entry of labels, in their order; called after each frame in which
 *                  one moved a quarter of a pixel or more, and after a resize. The page puts its
 *                  real text there (the water's name, a jetty, start and finish) in its own
 *                  elements over the canvas: el.style.transform = `translate(${x}px, ${y}px)`.
 *   phone          { below: 600, calmBox, fitBox }: the calm and the outline's place while the
 *                  container is narrower than `below` CSS pixels, where a phone puts the copy.
 *
 * setProgress(p), 0..1: travel over the map. The chart slides to new ground and zooms in by about
 *   1.6 times, so scrolling feels like moving over a map. The calm stays where the text is.
 *   Feed it a section's progress: chart.setProgress(chart.stage.progressOf(section)). With an
 *   outline the chart zooms in a fifth on it instead; in "tilt" the eye also comes lower and closer.
 * setData(values): numbers 0..1, any length. They raise a range of hills on the open side of the
 *   chart, running from top to bottom, the first value on the left (a list longer than 16 is
 *   averaged down to 16). The range follows the noise of the land, so it reads as terrain, not as
 *   a test pattern. It rises and settles over a second; an empty list lowers it again. With an
 *   outline it does nothing: the chart is the outline's.
 * setPointer(x, y), pause(), resume(), destroy(), stage: as stage.js describes.
 *
 * Poster: give the container a child `<img data-scene-poster src="chart.png" alt="">`, shown until
 * the first frame and again when there is no WebGL; or a background image plus the rule
 * `.hero-scene[data-scene="live"] { background-image: none; }`. Take the picture from the page
 * itself under reduced motion (the stage draws this still, with no pointer knoll), one per theme
 * and shape, with the page's header and text hidden: scenes.md section 5.
 *
 * Cost: one rectangle, one draw call, no textures, no work on the processor beyond a few numbers a
 * frame. Per pixel: 2D simplex noise with its exact slope, 2 lookups for the warp plus 3 or 4
 * layers (3 on low, 4 on medium and high: high differs only in the pixel ratio the stage allows),
 * and a few screen-space derivatives; only the pixels within about 12 device pixels of a top, a
 * hollow or a saddle read the land six times more, to place a mark exactly. Lines must be sharp,
 * so it draws at full resolution (the stage caps the pixel ratio); on a weak device the stage
 * steps down to fewer layers and a pixel ratio of 1. Fill rate is what it costs: give it the
 * hero, not a page. It can run for weeks: the numbers that move the land stay bounded.
 * "tilt" draws a sheet of 9 000 to 50 000 points (by quality) twice, a depth pass first so the
 * hills hide what lies behind them, and every point reads the land as a pixel does. An outline
 * adds one small texture, made once on the processor in a few milliseconds (the signed distance
 * to the area's edge), and a trail up to 63 segments per pixel.
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
// The outline and "tilt".
const ROUTE = 64;          // trail points the shader reads: a longer trail is simplified to fit
const FIELD = 320;         // cells of an area's distance field along its longer side, margins included
const BREAK = [1e4, 1e4];  // between two lines of a trail
const SHEET = 26;          // "tilt" without an outline: world units across the sheet of land
const SHEET_SCALE = 0.2;   // "tilt": scene units of the map per world unit of the sheet
const SHAPE_WORLD = 6;     // "tilt" with an outline: world units along the longer side of its box
const TILT_DISTANCE = 7.5; // "tilt" without an outline: the eye's distance from the middle of the land

// The rectangle covers the screen whatever the camera does.
const vertexShader = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}`;

// The land, and the outline's shape: shared by the fragment shader and, in "tilt", by the vertex
// shader that raises the sheet. Comes after stageUniforms and simplex2D.
const landCode = `
uniform vec3 uView;     // where the map is: offset x, y (map units), map units per scene unit
uniform vec2 uFlow;     // the flow: as long as the time run at the chosen speed, bent round a wide
                        // circle so it stays small (see the onFrame code)
uniform vec4 uHill;     // the pointer knoll: centre (scene units), presence 0..1, height
uniform float uTide;    // the water level, in heights: added to the land, so the lines creep
uniform float uRidge[${RIDGES}];
uniform float uRidgeCount;
uniform vec2 uRidgeSpan;
uniform float uRidgeHeight;

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

#ifdef HAS_SHAPE
// THE OUTLINE, in its own units n: the middle of its box at 0, the longer side of the box 1.
uniform vec3 uShapePlace;   // where n = 0 lies (scene units), and scene units per n unit
uniform float uSink;        // 1 a basin, 0 flat, -1 a rise
uniform float uLand;        // how much of the invented land shows round the outline
vec2 shapeCoord(vec2 p) { return (p - uShapePlace.xy) / uShapePlace.z; }
#ifdef HAS_AREA
uniform sampler2D uAreaField;   // the signed distance to the area's edge (n units): + inside
uniform vec4 uAreaGrid;         // the field's lower left corner and its size (n units)
uniform float uAreaDeep;        // the largest distance inside (n units)
#endif
#ifdef HAS_ROUTE
uniform vec4 uRoute[${ROUTE / 2}];   // the trail's points (n units), two per vec4; one far away is a break
uniform float uRouteCount;
vec2 routePoint(int k) { vec4 pair = uRoute[k / 2]; return k - (k / 2) * 2 == 0 ? pair.xy : pair.zw; }
// The distance to the trail and to the nearest of its ends (n units).
vec2 routeAt(vec2 n) {
  float best = 1e3, end = 1e3;
  vec2 a = routePoint(0);
  bool aBreak = abs(a.x) > 100.0, before = true;   // before: the point ahead of a is a break (or none)
  for (int k = 1; k < ${ROUTE}; k++) {
    if (float(k) >= uRouteCount) break;
    vec2 b = routePoint(k);
    bool bBreak = abs(b.x) > 100.0;
    if (!aBreak && !bBreak) {
      vec2 ab = b - a, an = n - a;
      float f = clamp(dot(an, ab) / max(dot(ab, ab), 1e-12), 0.0, 1.0);
      best = min(best, length(an - ab * f));
    }
    if (!aBreak && (before || bBreak)) end = min(end, length(n - a));   // a starts or ends a line
    before = aBreak;
    a = b;
    aBreak = bBreak;
  }
  if (!aBreak) end = min(end, length(n - a));   // the very last point
  return vec2(best, end);
}
#endif
#ifdef HAS_AREA
float areaDistance(vec2 n) { return texture2D(uAreaField, (n - uAreaGrid.xy) / uAreaGrid.zw).r; }
// An area sinks (uSink 1) by a depth that grows from its edge, steep along the edge and flat in
// the middle, as a lake's bed does. 0.75: the land's own half range.
float bedAt(float d) { return -uSink * (1.0 - pow(1.0 - clamp(d / uAreaDeep, 0.0, 1.0), 1.8)) * 0.75; }
// The slope of the bed at p, per scene unit: central differences one cell of the field apart.
vec2 bedSlope(vec2 p) {
  vec2 n = shapeCoord(p), cell = uAreaGrid.zw / vec2(textureSize(uAreaField, 0));
  vec2 dx = vec2(cell.x, 0.0), dy = vec2(0.0, cell.y);
  return vec2(bedAt(areaDistance(n + dx)) - bedAt(areaDistance(n - dx)),
              bedAt(areaDistance(n + dy)) - bedAt(areaDistance(n - dy))) / (2.0 * cell * uShapePlace.z);
}
#endif
// The outline's part at p: vec4(height, distance to the area's edge (+ inside), distance to the
// trail, distance to a trail's end).
vec4 shapeAt(vec2 p) {
  vec2 n = shapeCoord(p);
  vec4 s = vec4(0.0, -1.0, 1e3, 1e3);
#ifdef HAS_AREA
  s.y = areaDistance(n);
  s.x = bedAt(s.y);
#endif
#ifdef HAS_ROUTE
  s.zw = routeAt(n);
#endif
  return s;
}
// How far outside the outline (n units): 0 on it, and inside an area.
float awayFrom(vec4 s) {
  float away = 1e3;
#ifdef HAS_AREA
  away = max(-s.y, 0.0);
#endif
#ifdef HAS_ROUTE
  away = min(away, s.z);
#endif
  return away;
}
// The invented land's share of the height round an outline: a calm third of the free land's, and a
// fifth of that deep inside an area, so the lines there follow the edge and are not the land's.
float landWeight(vec4 s) {
  float deep = 0.0;
#ifdef HAS_AREA
  deep = clamp(s.y / uAreaDeep, 0.0, 1.0);
#endif
  return 0.35 * (1.0 - 0.8 * smoothstep(0.0, 0.3, deep));
}
// How strongly lines show: inside an area they are the area's own (all of them); round the outline
// the land's show at uLand, fading out a third of the outline's size away. Only their strength
// fades, never the land's height, or the fade itself would draw rings round the outline.
float landShow(vec4 s) {
  float inside = 0.0;
#ifdef HAS_AREA
  inside = smoothstep(-0.004, 0.004, s.y);
#endif
  return mix(uLand * (1.0 - smoothstep(0.05, 0.4, awayFrom(s))), 1.0, inside);
}
#endif

// The whole height at p: the land with the pointer's knoll, the outline's shape, the water level.
float heightAt(vec2 p) {
  vec3 t = terrain(p);
#ifdef HAS_SHAPE
  vec4 s = shapeAt(p);
  return s.x + landWeight(s) * t.x + uTide;
#else
  return t.x + uTide;
#endif
}
`;

// "tilt": a sheet on the ground (y = 0) raised by the land's height. q, the map's scene units, runs
// east along x and north along -z, away from the eye.
const tiltVertex = `
${stageUniforms}
${simplex2D}
${landCode}
uniform float uSheetScale;   // scene units per world unit on the sheet
uniform float uRaise;        // world units per unit of height
varying vec2 vQ;
varying vec2 vSheet;         // 0..1 across the sheet; 1 is the far edge
varying float vDepth;        // distance from the eye, world units
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vec2 q = vec2(world.x, -world.z) * uSheetScale;
  world.y += heightAt(q) * uRaise;
  vQ = q;
  vSheet = uv;
  vec4 view = viewMatrix * world;
  vDepth = -view.z;
  gl_Position = projectionMatrix * view;
}`;

// The depth pass of "tilt": writes only how near the sheet is, so the colour pass draws the front.
const depthFragment = `
void main() { gl_FragColor = vec4(0.0); }`;

const fragmentShader = `
${stageUniforms}
${simplex2D}
${line}
${grain}
${landCode}
uniform vec4 uStyle;    // contour interval, line width (CSS px), index strength, tint
uniform vec4 uLook;     // marks on, relief, index every, grid on
uniform vec4 uCalmBox;  // the text block: x0, y0, x1, y1 (0..1 from the top left)
uniform vec2 uCalm;     // how calm (0..1), the width of the fade round the block (scene units)
#ifdef VIEW_TILT
uniform vec2 uFog;      // the far land fades between these distances from the eye
uniform float uSheetScale;
uniform float uRaise;
varying vec2 vQ;
varying vec2 vSheet;
varying float vDepth;
#else
varying vec2 vUv;
#endif
#ifdef HAS_SHAPE
uniform vec4 uGridAt;   // the outline's own map grid: its step and a point where two lines meet (n units)
#endif
#ifdef HAS_FILL
uniform vec3 uFill;     // the area's colour (the fill option)
#endif

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

// A small cross where two lines of a grid meet (step apart, through 0), about 3 CSS pixels each
// way. coord is in any units: the screen says how many pixels they are. Where the crosses would
// crowd (far off in "tilt"), they fade.
float crossAt(vec2 coord, vec2 step_) {
  vec2 cell = (fract(coord / step_ + 0.5) - 0.5) * step_;
  vec2 perPx = max(vec2(length(vec2(dFdx(coord.x), dFdy(coord.x))), length(vec2(dFdx(coord.y), dFdy(coord.y)))), vec2(1e-9));
  vec2 ac = abs(cell) / perPx / uPixelRatio;
  float apart = min(step_.x / perPx.x, step_.y / perPx.y) / uPixelRatio;
  return (1.0 - smoothstep(0.3, 0.9, min(ac.x, ac.y))) * (1.0 - smoothstep(3.0, 4.0, max(ac.x, ac.y)))
       * smoothstep(16.0, 32.0, apart);
}

void main() {
  float unit = unitPixels();
#ifdef VIEW_TILT
  vec2 p = vQ;
#else
  vec2 p = (gl_FragCoord.xy - 0.5 * uResolution) / unit;
#endif
  vec3 t = terrain(p);
  float interval = uStyle.x;
#ifdef HAS_SHAPE
  vec4 s = shapeAt(p);
  float h = s.x + landWeight(s) * t.x + uTide;
  vec2 n = shapeCoord(p);
  float perN = max(0.5 * (length(dFdx(n)) + length(dFdy(n))), 1e-9);   // n units per device pixel
  vec2 slope = landWeight(s) * t.yz;
#ifdef HAS_AREA
  slope += bedSlope(p);
#endif
#else
  float h = t.x + uTide;
  vec2 slope = t.yz;
#endif

  // The calm: the pointer clears a little of it, so the plain answers the hand too.
  vec2 toHill = p - uHill.xy;
  // Most of all round the edge of the text block, hardly at all behind the words themselves: within
  // about a quarter of a scene unit of the hand (exp(-d^2 / 0.06)) it takes away up to 0.75 of the
  // calm, less as the calm nears 1, and only 0.12 (3 x 0.04) where the calm is full.
  float calm = calmAt(gl_FragCoord.xy);
  calm = max(calm - uHill.z * exp(-dot(toHill, toHill) / 0.06) * min(0.75, 3.0 * (1.04 - calm)), 0.0);

  // Pixels from one contour to the next here: the interval over the slope per pixel.
#if defined(VIEW_TILT) || defined(HAS_SHAPE)
  // How far p moves from one pixel to the next (in perspective that changes over the screen): the
  // slope on screen is the slope on the map taken through it.
  vec2 perPixel = transpose(mat2(dFdx(p), dFdy(p))) * slope;
#else
  vec2 perPixel = slope / unit;
#endif
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
  // is small (within about 30 pixels), as on a real chart. Only in the flat view of the land alone:
  // in "tilt" the page's labels take their place, and with an outline they would read as soundings.
  float mark = 0.0, tiny = 0.0;
#if !defined(VIEW_TILT) && !defined(HAS_SHAPE)
  mat2 H = mat2(dFdx(perPixel), dFdy(perPixel));
  H = 0.5 * (H + transpose(H));
  vec2 to = -inverse(H) * perPixel;
  // A ring round a top or a hollow so small (under about 3 CSS pixels at its longest) that it would
  // print as a speck of dust. In a bowl the drop to the top, half of g.to, is the same all round the
  // ring, and so is its long radius, sqrt(2 drop / the weaker curvature): every pixel of the ring
  // finds the same answer from its own numbers, so the ring goes whole. It goes with or without marks.
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
#endif
#ifdef HAS_SHAPE
  // The land's lines fade away from the outline. And ground so flat that its lines would lie more
  // than a screen apart gets none: a flat stretch would otherwise sit on one level and fill with it.
  float show = landShow(s) * (1.0 - smoothstep(0.5, 1.0, gap / max(uResolution.x, uResolution.y)));
  minor *= show;
  index *= show;
#endif
  minor *= 1.0 - tiny;
  index *= 1.0 - tiny;

  // Registration crosses where the lines of a map grid meet, half a map unit apart; they move with
  // the map, so travel shows even over flat ground. Each fades by the calm at its own centre.
#if defined(HAS_SHAPE)
  // With an outline the grid is the outline's own: a round step of its units (degrees for
  // GeoJSON), fixed to it, so the crosses mark real coordinates.
  float grid = 0.7 * uLook.w * crossAt(n - uGridAt.zw, uGridAt.xy) * (1.0 - smoothstep(0.0, 0.5, calm))
             * (1.0 - smoothstep(0.08, 0.4, awayFrom(s)));   // round the outline only, as the land
#elif defined(VIEW_TILT)
  float grid = uLook.w * crossAt(p * uView.z + uView.xy, vec2(0.5)) * (1.0 - smoothstep(0.0, 0.5, calm));
#else
  vec2 cell = (fract((p * uView.z + uView.xy) / 0.5 + 0.5) - 0.5) * 0.5 / uView.z * unit;
  vec2 ac = abs(cell) / uPixelRatio;
  float grid = uLook.w * (1.0 - smoothstep(0.3, 0.9, min(ac.x, ac.y))) * (1.0 - smoothstep(3.0, 4.0, max(ac.x, ac.y)));
  grid *= 1.0 - smoothstep(0.0, 0.5, calmAt(gl_FragCoord.xy - cell));
#endif

  // Layer tint: one shade per index band, a step at every index line as on a printed chart, a
  // few percent stronger with each band up. It goes first in the calm, so a step in the tint
  // never shows without its line.
  float step_ = interval * every;
  // Low ground and water get none, so the tint never lies over the whole chart as a sheet.
  float bandMid = (floor(h / step_) + 0.5) * step_ - uTide;
  // None at a height of -0.3 and below, full from 0.6 up (the land spans about -0.75..0.75).
  float high = clamp((bandMid + 0.3) / 0.9, 0.0, 1.0);
#ifdef HAS_SHAPE
  // Round an outline the land is low and calm (a third of the free land's height): a shade per
  // line where it rises, none inside the area (it has its own fill), fading with the land's lines.
  float rise = landWeight(s) * t.x;
  high = clamp(floor(max(rise, 0.0) / interval) * interval / 0.26, 0.0, 1.0) * landShow(s);
#ifdef HAS_AREA
  high *= 1.0 - smoothstep(-0.5 * perN, 0.5 * perN, s.y);
#endif
#endif
#ifdef VIEW_TILT
  float tintCalm = (1.0 - calm) * (1.0 - calm);   // the sheet's own edges fade it below
#else
  float tintCalm = (1.0 - calm) * (1.0 - calm) * smoothstep(0.0, 0.3, vUv.y) * smoothstep(0.0, 0.3, 1.0 - vUv.y);
#endif

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
#ifdef VIEW_TILT
  // The lamp: the raised land is shaded as a relief model under a light from the far left, so the
  // hills read as forms and a near hill's edge as an edge. On paper the slopes that turn away get a
  // little ink; on a dark page the slopes that face the light glow a little. relief sets how much.
  vec3 normal = normalize(vec3(-uRaise * uSheetScale * slope.x, 1.0, uRaise * uSheetScale * slope.y));
  float facing = dot(normal, normalize(vec3(-1.0, 1.4, -1.0)));
  float away = clamp((0.703 - facing) * 2.4, 0.0, 1.0), toward = clamp((facing - 0.703) * 2.4, 0.0, 1.0);   // 0.703: flat ground
  float lamp = uLook.y * (1.0 - calm);
#ifdef HAS_SHAPE
  lamp *= landShow(s);   // round an outline the shading fades with the land's lines
#endif
  over(acc, uText, (1.0 - dark) * away * 0.11 * lamp);
  over(acc, mix(uText, uAccent, 0.35), dark * toward * 0.1 * lamp);
#endif
#ifdef HAS_AREA
  // The area's inside: a tint one step deeper every second line in from its edge, as on a printed
  // depth chart. The steps follow the outline's own shape, so they never flicker with the land.
  float inside = smoothstep(-0.5 * perN, 0.5 * perN, s.y);
  float band = floor(abs(s.x) / (2.0 * interval)) * 2.0 * interval / 0.75;
#ifdef HAS_FILL
  vec3 fillInk = uFill;
#else
  vec3 fillInk = uAccent;
#endif
  over(acc, fillInk, inside * (0.05 + 0.13 * band) * mix(1.0, 1.25, dark) * uStyle.w * (1.0 - 0.7 * calm));
#endif
  over(acc, uMuted, grid * mix(0.36, 0.32, dark));
  over(acc, uText, minor * 0.3 * glow * keepMinor);
  over(acc, indexInk, index * indexAlpha * glow * keepIndex);
  over(acc, markInk, mark * 0.9);
#ifdef HAS_AREA
  // The edge itself: one firm line, the strongest on the chart. The calm thins it last of all. The
  // field is a true distance, so pixels are its value over the n units one pixel spans.
  float edgeWidth = uStyle.y * uPixelRatio * 1.8;
  float edgeLine = 1.0 - smoothstep(0.5 * edgeWidth - 0.5, 0.5 * edgeWidth + 0.5, abs(s.y) / perN);
  over(acc, uText, edgeLine * mix(0.78, 0.86, dark) * max(keepIndex, 0.3));
#endif
#ifdef HAS_ROUTE
  // The trail: the lines under it are cleared in a band a little wider than the route (as a map
  // gives a road its casing), then the route in the accent, and a dot at each end. The distance to
  // the trail has a crease along it, where its slope on screen means nothing: pixels come from perN.
  float routeWidth = uStyle.y * uPixelRatio * 2.2, casingWidth = routeWidth + 5.0 * uPixelRatio;
  float routeAway = s.z / perN;                                          // device px to the trail
  float route = 1.0 - smoothstep(0.5 * routeWidth - 0.5, 0.5 * routeWidth + 0.5, routeAway);
  float endAt = s.w / perN / uPixelRatio;                                // CSS px to the nearest end
  float clearing = max(1.0 - smoothstep(0.5 * casingWidth - 0.5, 0.5 * casingWidth + 0.5, routeAway),
                       1.0 - smoothstep(5.0, 6.0, endAt));
  acc *= 1.0 - 0.9 * clearing;
  over(acc, uAccent, max(route, 1.0 - smoothstep(3.0, 4.0, endAt)) * 0.95 * max(keepIndex, 0.3));
#endif
#ifdef VIEW_TILT
  // Fade softly at the sheet's edges, most softly at the far one, with the distance, and toward the
  // top and bottom of the container, so the land dissolves before the horizon and the page's edge.
  float screenY = gl_FragCoord.y / uResolution.y;
  float edge = smoothstep(0.0, 0.1, vSheet.x) * smoothstep(0.0, 0.1, 1.0 - vSheet.x)
             * smoothstep(0.0, 0.12, vSheet.y) * smoothstep(0.0, 0.32, 1.0 - vSheet.y)
             * smoothstep(0.0, 0.1, screenY) * smoothstep(0.0, 0.24, 1.0 - screenY);
  acc *= edge * edge * (3.0 - 2.0 * edge) * (1.0 - smoothstep(uFog.x, uFog.y, vDepth));
#else
  // Fade softly at the top and bottom edges, where the hero meets the page.
  float edge = smoothstep(0.0, 0.14, vUv.y) * smoothstep(0.0, 0.14, 1.0 - vUv.y);
  acc *= edge * edge * (3.0 - 2.0 * edge);
#endif

  gl_FragColor = vec4(acc.rgb / max(acc.a, 1e-5), acc.a);
  #include <colorspace_fragment>
  gl_FragColor.rgb *= gl_FragColor.a;    // premultiplied out, as the material says
  gl_FragColor += vec4(dither(gl_FragCoord.xy), dither(gl_FragCoord.yx).x) * min(gl_FragColor.a * 8.0, 1.0);
}`;

const num = (value, fallback, low, high) => (Number.isFinite(Number(value)) && value !== null && value !== ""
  ? Math.min(high, Math.max(low, Number(value))) : fallback);
const ease = (x) => x * x * (3 - 2 * x);

// A calmBox given wins over calm, "none" included: a phone's calmBox calms the phone of a page whose
// wide layout has no text over the chart.
function calmBox(o, aspect) {
  if (Array.isArray(o.calmBox) && o.calmBox.length === 4) {
    const [x0, y0, x1, y1] = o.calmBox.map((v) => num(v, 0, 0, 1));
    return [Math.min(x0, x1), Math.min(y0, y1), Math.max(x0, x1), Math.max(y0, y1)];
  }
  if (o.calm === "none") return null;
  const name = CALM[o.calm] ? o.calm : "left";
  if (aspect < 0.85 && (name === "left" || name === "right" || name === "center")) return NARROW;
  return CALM[name];
}

// THE OUTLINE. GeoJSON into lists of [lon, lat]: areas (rings, holes included) and lines.
function geoParts(geometry, out) {
  if (!geometry || typeof geometry !== "object") return out;
  const c = Array.isArray(geometry.coordinates) ? geometry.coordinates : [];
  if (geometry.type === "Feature") geoParts(geometry.geometry, out);
  else if (geometry.type === "FeatureCollection") for (const f of geometry.features || []) geoParts(f, out);
  else if (geometry.type === "GeometryCollection") for (const g of geometry.geometries || []) geoParts(g, out);
  else if (geometry.type === "Polygon") for (const ring of c) out.areas.push(ring);
  else if (geometry.type === "MultiPolygon") for (const polygon of c) for (const ring of polygon || []) out.areas.push(ring);
  else if (geometry.type === "LineString") out.lines.push(c);
  else if (geometry.type === "MultiLineString") for (const part of c) out.lines.push(part);
  return out;
}

// The outline in n units: the middle of its box at 0, the longer side of the box 1, y up. A degree
// of longitude is shortened by the cosine of the latitude, so a GeoJSON shape keeps its own form.
// null when nothing in it can be drawn.
function readOutline(outline) {
  const parts = { areas: [], lines: [] };
  const geo = Boolean(outline) && !Array.isArray(outline) && typeof outline === "object";
  if (geo) geoParts(outline, parts);
  else if (Array.isArray(outline)) {
    const list = Array.isArray(outline[0]) && typeof outline[0][0] === "number" ? [outline] : outline;
    for (const ring of list) {
      if (!Array.isArray(ring) || ring.length < 2) continue;
      const a = ring[0], b = ring[ring.length - 1];
      const closed = ring.length > 3 && Array.isArray(a) && Array.isArray(b) && a[0] === b[0] && a[1] === b[1];
      (closed ? parts.areas : parts.lines).push(ring);
    }
  }
  const clean = (list, least) => list.map((ring) => (Array.isArray(ring) ? ring : [])
    .filter((pt) => Array.isArray(pt) && Number.isFinite(Number(pt[0])) && Number.isFinite(Number(pt[1])))
    .map((pt) => [Number(pt[0]), Number(pt[1])])).filter((ring) => ring.length >= least);
  const areas = clean(parts.areas, 3), lines = clean(parts.lines, 2), all = areas.concat(lines);
  let y0 = Infinity, y1 = -Infinity, x0 = Infinity, x1 = -Infinity;
  for (const ring of all) for (const pt of ring) { y0 = Math.min(y0, pt[1]); y1 = Math.max(y1, pt[1]); }
  if (!(y1 >= y0)) return null;
  const kx = geo ? Math.max(Math.cos((((y0 + y1) / 2) * Math.PI) / 180), 0.01) : 1;
  for (const ring of all) for (const pt of ring) { x0 = Math.min(x0, pt[0] * kx); x1 = Math.max(x1, pt[0] * kx); }
  const L = Math.max(x1 - x0, y1 - y0), mx = (x0 + x1) / 2, my = (y0 + y1) / 2;
  if (!(L > 0)) return null;
  const toN = (x, y) => [(x * kx - mx) / L, (y - my) / L];
  const n = (ring) => ring.map((pt) => toN(pt[0], pt[1]));
  return { areas: areas.map(n), lines: lines.map(n), size: [(x1 - x0) / L, (y1 - y0) / L], toN, kx, L, mx, my };
}

// The signed distance to the areas' edge on a grid, in n units (+ inside): the chamfer distance of
// the filled rings (even-odd, so holes and islands are rings too), softened by three passes of a
// 3 x 3 mean so the bed has no ridge along its middle. Also how deep it gets, and where.
function areaField(shape) {
  const margin = 0.3;
  const w = shape.size[0] + 2 * margin, h = shape.size[1] + 2 * margin, cell = Math.max(w, h) / FIELD;
  const gw = Math.max(8, Math.ceil(w / cell)), gh = Math.max(8, Math.ceil(h / cell));
  const x0 = (-gw * cell) / 2, y0 = (-gh * cell) / 2;
  const canvas = document.createElement("canvas");
  canvas.width = gw;
  canvas.height = gh;
  const g = canvas.getContext("2d", { willReadFrequently: true });
  if (!g || typeof Path2D !== "function") return null;
  g.setTransform(1 / cell, 0, 0, -1 / cell, -x0 / cell, gh + y0 / cell);   // n units to pixels, y up
  const path = new Path2D();
  for (const ring of shape.areas) {
    path.moveTo(ring[0][0], ring[0][1]);
    for (let i = 1; i < ring.length; i++) path.lineTo(ring[i][0], ring[i][1]);
    path.closePath();
  }
  g.fill(path, "evenodd");
  const alpha = g.getImageData(0, 0, gw, gh).data;
  const count = gw * gh, BIG = 1e9, R2 = Math.SQRT2;
  const cover = new Float32Array(count);   // how much of each cell the fill covers; row 0 is the bottom
  for (let r = 0; r < gh; r++) for (let c = 0; c < gw; c++) cover[r * gw + c] = alpha[((gh - 1 - r) * gw + c) * 4 + 3] / 255;
  // The edge's own cells know how far the edge is from their middle: a cell the edge cuts through
  // is covered about (0.5 + that distance) of the way, and a whole cell next to an empty one has
  // the edge on its side, half a cell away. From there two chamfer passes carry the distance out.
  const d = new Float32Array(count);
  const wet = (i) => cover[i] > 0.5;
  for (let y = 0; y < gh; y++) for (let x = 0; x < gw; x++) {
    const i = y * gw + x, a = cover[i], w = wet(i);
    const edge = (x > 0 && wet(i - 1) !== w) || (x < gw - 1 && wet(i + 1) !== w)
      || (y > 0 && wet(i - gw) !== w) || (y < gh - 1 && wet(i + gw) !== w);
    d[i] = a > 0.02 && a < 0.98 ? Math.abs(a - 0.5) : edge ? 0.5 : BIG;
  }
  const at = (x, y) => (x < 0 || y < 0 || x >= gw || y >= gh ? BIG : d[y * gw + x]);
  for (let y = 0; y < gh; y++) for (let x = 0; x < gw; x++) {
    const i = y * gw + x;
    d[i] = Math.min(d[i], at(x - 1, y) + 1, at(x, y - 1) + 1, at(x - 1, y - 1) + R2, at(x + 1, y - 1) + R2);
  }
  for (let y = gh - 1; y >= 0; y--) for (let x = gw - 1; x >= 0; x--) {
    const i = y * gw + x;
    d[i] = Math.min(d[i], at(x + 1, y) + 1, at(x, y + 1) + 1, at(x + 1, y + 1) + R2, at(x - 1, y + 1) + R2);
  }
  let values = new Float32Array(count);
  for (let i = 0; i < count; i++) values[i] = (cover[i] > 0.5 ? 1 : -1) * Math.min(d[i], BIG / 2) * cell;
  const soft = new Float32Array(count);
  for (let pass = 0; pass < 3; pass++) {
    for (let y = 0; y < gh; y++) for (let x = 0; x < gw; x++) {
      let sum = 0, k = 0;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const xx = x + dx, yy = y + dy;
        if (xx >= 0 && yy >= 0 && xx < gw && yy < gh) { sum += values[yy * gw + xx]; k++; }
      }
      soft[y * gw + x] = sum / k;
    }
    values = Float32Array.from(soft);
  }
  let deep = 0, deepest = 0;
  for (let i = 0; i < count; i++) if (values[i] > deep) { deep = values[i]; deepest = i; }
  if (!(deep > 0)) return null;
  const middle = [x0 + ((deepest % gw) + 0.5) * cell, y0 + (Math.floor(deepest / gw) + 0.5) * cell];
  const data = new Uint16Array(count);
  for (let i = 0; i < count; i++) data[i] = THREE.DataUtils.toHalfFloat(values[i]);
  const texture = new THREE.DataTexture(data, gw, gh, THREE.RedFormat, THREE.HalfFloatType);
  texture.minFilter = texture.magFilter = THREE.LinearFilter;
  texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.needsUpdate = true;
  return { texture, grid: [x0, y0, gw * cell, gh * cell], deep, middle };
}

// A line with fewer points that stays within tolerance of it (Douglas-Peucker).
function simplify(line, tolerance) {
  if (line.length <= 2) return line.slice();
  const keep = new Uint8Array(line.length);
  keep[0] = keep[line.length - 1] = 1;
  const stack = [[0, line.length - 1]];
  while (stack.length) {
    const [a, b] = stack.pop();
    const [ax, ay] = line[a], dx = line[b][0] - ax, dy = line[b][1] - ay, length = Math.hypot(dx, dy) || 1e-12;
    let far = -1, most = tolerance;
    for (let i = a + 1; i < b; i++) {
      const d = Math.abs((line[i][0] - ax) * dy - (line[i][1] - ay) * dx) / length;
      if (d > most) { most = d; far = i; }
    }
    if (far >= 0) { keep[far] = 1; stack.push([a, far], [far, b]); }
  }
  return line.filter((point, i) => keep[i]);
}

// The trail's points for the shader: every line simplified until all of them, with a break between
// two lines, fit in ROUTE points. Also the point half way along.
function routeOf(lines) {
  let tolerance = 0.0008, points = [];
  for (let round = 0; round < 40; round++) {
    points = [];
    lines.forEach((line, i) => { if (i) points.push(BREAK); points.push(...simplify(line, tolerance)); });
    if (points.length <= ROUTE) break;
    tolerance *= 1.5;
  }
  points = points.slice(0, ROUTE);
  const pieces = [];
  let total = 0;
  for (const line of lines) for (let i = 1; i < line.length; i++) {
    const d = Math.hypot(line[i][0] - line[i - 1][0], line[i][1] - line[i - 1][1]);
    pieces.push([line[i - 1], line[i], d]);
    total += d;
  }
  let middle = lines[0][0], walked = 0;
  for (const [a, b, d] of pieces) {
    if (walked + d >= total / 2) {
      const f = d > 0 ? (total / 2 - walked) / d : 0;
      middle = [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
      break;
    }
    walked += d;
  }
  return { points, middle };
}

// A round step for a map grid about a quarter of span long: 1, 2 or 5 times a power of ten.
function niceStep(span) {
  const power = Math.pow(10, Math.floor(Math.log10(span)));
  const m = span / power;
  return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * power;
}

// The largest part of the container beside the calm box that the outline can fill: left of it,
// right of it, above or below (the whole container without a calm), as [x0, y0, x1, y1]. Beside
// the text wins over a band above or below it unless the band is clearly larger.
function openBox(box, aspect, ratio) {
  const m = 0.04;
  const sides = !box ? [[m, m, 1 - m, 1 - m]] : [
    [m, m, box[0] - m, 1 - m], [box[2] + m, m, 1 - m, 1 - m], [m, m, 1 - m, box[1] - m], [m, box[3] + m, 1 - m, 1 - m]];
  let best = [m, m, 1 - m, 1 - m], most = 0;
  sides.forEach((side, i) => {
    const w = (side[2] - side[0]) * aspect, h = side[3] - side[1];   // in container heights
    if (w < 0.05 || h < 0.05) return;
    const fits = Math.min(w / ratio, h) * (box && i < 2 ? 1.25 : 1);   // the outline's height when it fills the side
    if (fits > most) { most = fits; best = side; }
  });
  return best;
}

export function mount(container, options = {}) {
  const o = {
    levels: 16, lineWidth: 1, indexEvery: 5, indexStrength: 1, tint: 1, relief: 1, marks: true, grid: true,
    lift: 1, speed: 1, tide: 1, scale: 1, calm: "left", calmAmount: 1, view: "flat", angle: 40, height: 1,
    sink: 1, ...options,
  };
  const tilt = o.view === "tilt";
  const fill = typeof o.fill === "string" && o.fill.trim() ? o.fill.trim() : null;
  const stage = createStage(container, {
    antialias: tilt, stillTime: 9,
    camera: tilt ? { fov: 35, near: 0.1, far: 400, position: [0, 5, 4], lookAt: [0, 0, 0] } : undefined,
    ...options,
    tokens: fill ? { ...(options.tokens || {}), fill } : options.tokens,   // tokens.fill and uFill
  });
  if (stage.failed) return stage.handle();

  const interval = 1.5 / num(o.levels, 16, 4, 60);   // the land spans about -0.75..0.75
  const speed = num(o.speed, 1, 0, 10);
  const tide = num(o.tide, 1, 0, 5) * interval * 0.08;   // heights a second: a level in about 12 s
  const lift = num(o.lift, 1, 0, 3);
  const ridges = new Float32Array(RIDGES), ridgeTarget = new Float32Array(RIDGES);
  let ridgeHeight = 0, ridgeHeightTarget = 0, flow = 0, presence = 0;

  // The outline: an area becomes a distance field in a texture, a trail a list of points.
  const shape = o.outline ? readOutline(o.outline) : null;
  const area = shape && shape.areas.length ? areaField(shape) : null;
  const route = shape && shape.lines.length ? routeOf(shape.lines) : null;
  const shaped = Boolean(area || route);
  if (o.outline && !shaped) console.warn("contour.js: the outline has no ring or line to draw, so the land is drawn alone.");
  const defines = {};
  if (tilt) defines.VIEW_TILT = 1;
  if (shaped) defines.HAS_SHAPE = 1;
  if (area) defines.HAS_AREA = 1;
  if (route) defines.HAS_ROUTE = 1;
  if (shaped && fill) defines.HAS_FILL = 1;
  const routeSlots = Array.from({ length: ROUTE / 2 }, (_, i) => {
    const a = (route && route.points[2 * i]) || BREAK, b = (route && route.points[2 * i + 1]) || BREAK;
    return new THREE.Vector4(a[0], a[1], b[0], b[1]);
  });
  let gridAt = [1, 1, 0, 0];
  if (shaped) {   // the outline's own grid: a round step of its units (degrees for GeoJSON) through a round point
    const step = niceStep(shape.L / 4);
    const origin = shape.toN(Math.round(shape.mx / shape.kx / step) * step, Math.round(shape.my / step) * step);
    gridAt = [(step * shape.kx) / shape.L, step / shape.L, origin[0], origin[1]];
  }

  const uniforms = {
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
    uSheetScale: { value: SHEET_SCALE },
    uRaise: { value: 1.1 * num(o.height, 1, 0, 3) },   // world units per unit of height: about 1.6 from hollow to top
    uFog: { value: new THREE.Vector2(10, 30) },
    uShapePlace: { value: new THREE.Vector3(0, 0, tilt ? SHEET_SCALE * SHAPE_WORLD : 1) },
    uSink: { value: num(o.sink, 1, -2, 2) },
    uLand: { value: num(o.land, 0.35, 0, 1) },
    uAreaField: { value: area ? area.texture : null },
    uAreaGrid: { value: new THREE.Vector4(...(area ? area.grid : [0, 0, 1, 1])) },
    uAreaDeep: { value: area ? area.deep : 1 },
    uRoute: { value: routeSlots },
    uRouteCount: { value: route ? route.points.length : 0 },
    uGridAt: { value: new THREE.Vector4(...gridAt) },
  };
  const material = new THREE.ShaderMaterial({
    uniforms, defines: { ...defines, OCTAVES: 3 }, vertexShader: tilt ? tiltVertex : vertexShader, fragmentShader,
    transparent: true, premultipliedAlpha: true, depthTest: tilt, depthWrite: false, depthFunc: THREE.LessEqualDepth,
  });
  // "tilt" draws the sheet twice: first only how near it is, then the colour of what is in front, so
  // a hill hides the land behind it. The depth pass lies a hair further back, so the front passes.
  const depthMaterial = tilt ? new THREE.ShaderMaterial({
    uniforms, defines: { ...defines, OCTAVES: 3 }, vertexShader: tiltVertex, fragmentShader: depthFragment,
    colorWrite: false, depthWrite: true, depthTest: true, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
  }) : null;
  // Flat: one rectangle over the screen. "tilt": the sheet, its points by quality (below).
  const meshes = [new THREE.Mesh(tilt ? new THREE.BufferGeometry() : new THREE.PlaneGeometry(2, 2), material)];
  if (depthMaterial) {
    meshes.unshift(new THREE.Mesh(meshes[0].geometry, depthMaterial));
    meshes[0].renderOrder = -1;
  }
  for (const mesh of meshes) {
    mesh.frustumCulled = false;   // placed by the vertex shader, never by the camera
    stage.scene.add(mesh);
  }
  // The sheet of "tilt" in world units: the land round the middle, or the outline's field.
  const extent = area ? [area.grid[2], area.grid[3]] : shaped ? [shape.size[0] + 0.6, shape.size[1] + 0.6] : null;
  const sheetSize = extent ? [extent[0] * SHAPE_WORLD, extent[1] * SHAPE_WORLD] : [SHEET, SHEET];

  // Shader cost follows the quality: the number of noise layers is compiled in. High keeps 4: a
  // fifth layer is so fine that its ripples, not the land, set the tops, and the flats fill with marks.
  stage.onQuality((quality) => {
    const next = { ...defines, OCTAVES: quality.pick(3, 4, 4) };
    for (const m of [material, depthMaterial]) if (m) { m.defines = next; m.needsUpdate = true; }
    if (tilt) {   // about 110, 170 or 230 points along the sheet's longer side
      const long = quality.pick(110, 170, 230), [sw, sd] = sheetSize, most = Math.max(sw, sd);
      const geometry = new THREE.PlaneGeometry(sw, sd, Math.max(2, Math.round((long * sw) / most)),
        Math.max(2, Math.round((long * sd) / most))).rotateX(-Math.PI / 2);
      meshes[0].geometry.dispose();
      for (const mesh of meshes) mesh.geometry = geometry;
    }
    stage.invalidate();
  });

  // "tilt": the eye on a sphere round the target, from the south (+z) and above.
  const target = new THREE.Vector3(), eye = new THREE.Vector3(), probe = new THREE.Vector3();
  const ray = new THREE.Raycaster(), ground = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const hit = new THREE.Vector3(), aim = new THREE.Vector2();
  const angle = THREE.MathUtils.degToRad(num(o.angle, 40, 20, 90));
  let distance = TILT_DISTANCE, half = [0.9, 0.9], flatPlace = { x: 0, y: 0, s: 1 };
  const fitPoints = [];   // "tilt" with an outline: what must be in view (its points and its deepest one)
  if (tilt && shaped) {
    const all = shape.areas.concat(shape.lines).flat();
    for (let i = 0, every = Math.max(1, Math.floor(all.length / 160)); i < all.length; i += every) {
      fitPoints.push(new THREE.Vector3(all[i][0] * SHAPE_WORLD, 0, -all[i][1] * SHAPE_WORLD));
    }
    if (area) fitPoints.push(new THREE.Vector3(area.middle[0] * SHAPE_WORLD, -0.75 * uniforms.uSink.value * uniforms.uRaise.value, -area.middle[1] * SHAPE_WORLD));
  }
  function place(azimuth, elevation, far) {
    const c = Math.cos(elevation);
    eye.set(Math.sin(azimuth) * c, Math.sin(elevation), Math.cos(azimuth) * c).multiplyScalar(far).add(target);
    stage.camera.position.copy(eye);
    if (elevation > 1.55) stage.camera.up.set(-Math.sin(azimuth), 0, -Math.cos(azimuth));   // from right above: north up
    else stage.camera.up.set(0, 1, 0);
    stage.camera.lookAt(target);
    stage.camera.updateMatrixWorld();
  }
  function fitsAt(far) {
    place(0, angle, far);
    for (const point of fitPoints) {
      probe.copy(point).project(stage.camera);
      if (probe.z > 1 || Math.abs(probe.x) > half[0] || Math.abs(probe.y) > half[1]) return false;
    }
    return true;
  }

  stage.onResize((size) => {
    const phone = o.phone && typeof o.phone === "object" && size.width < num(o.phone.below, 600, 0, 10000) ? o.phone : null;
    const placed = phone ? { ...o, calmBox: phone.calmBox || o.calmBox, fitBox: phone.fitBox || o.fitBox } : o;
    const box = calmBox(placed, size.aspect);
    const u = material.uniforms;
    u.uCalmBox.value.set(...(box || [0, 0, 0, 0]));
    u.uCalm.value.set(box ? num(o.calmAmount, 1, 0, 1) : 0, size.aspect < 0.85 ? 0.24 : 0.2);
    // The data range stands on the open side, not under the text.
    const open = box && box[2] - box[0] < 0.7 ? (box[0] < 0.5 - (box[2] - 0.5) ? [box[2] + 0.06, 0.97] : [0.03, box[0] - 0.06]) : [0.04, 0.96];
    u.uRidgeSpan.value.set(open[0], Math.max(open[1], open[0] + 0.2));
    if (!shaped) {
      if (tilt) place(0, angle, distance);
      return;
    }
    // The outline fills the open part beside the calm (or fitBox).
    const given = Array.isArray(placed.fitBox) && placed.fitBox.length === 4 ? placed.fitBox.map((v) => num(v, 0, 0, 1)) : null;
    // Seen at an angle, the outline's depth is foreshortened: it looks wider than it is.
    const ratio = shape.size[0] / Math.max(shape.size[1], 1e-6) / (tilt ? Math.max(Math.sin(angle), 0.3) : 1);
    const f = given || openBox(box, size.aspect, ratio);
    const x0 = Math.min(f[0], f[2]), x1 = Math.max(f[0], f[2]), y0 = Math.min(f[1], f[3]), y1 = Math.max(f[1], f[3]);
    if (tilt) {
      // The eye steps back until every point of the outline is inside the box (seen at rest), and a
      // shift of the lens puts the box's middle where the view's middle was.
      const nx = [x0 * 2 - 1, x1 * 2 - 1], ny = [1 - y1 * 2, 1 - y0 * 2];
      half = [((nx[1] - nx[0]) / 2) * 0.9, ((ny[1] - ny[0]) / 2) * 0.9];
      stage.camera.clearViewOffset();
      let near = 0.5, far = 400;
      for (let i = 0; i < 24; i++) { const mid = (near + far) / 2; if (fitsAt(mid)) far = mid; else near = mid; }
      distance = far;
      stage.camera.setViewOffset(size.width, size.height, (-(nx[0] + nx[1]) / 2) * (size.width / 2),
        ((ny[0] + ny[1]) / 2) * (size.height / 2), size.width, size.height);
      place(0, angle, distance);
    } else {
      const unit = Math.sqrt(size.width * size.height), W = size.width / unit, H = size.height / unit;
      const bx = [(x0 - 0.5) * W, (x1 - 0.5) * W], by = [(0.5 - y1) * H, (0.5 - y0) * H];
      flatPlace = { x: (bx[0] + bx[1]) / 2, y: (by[0] + by[1]) / 2,
                    s: 0.92 * Math.min((bx[1] - bx[0]) / Math.max(shape.size[0], 1e-6), (by[1] - by[0]) / Math.max(shape.size[1], 1e-6)) };
    }
  });

  // Labels: where the page's own labels go, in CSS pixels of the container.
  const onLabels = typeof o.onLabels === "function" ? o.onLabels : null;
  const labelAt = (entry) => {
    if (entry === "middle") return area ? area.middle : route ? route.middle : null;
    const x = Array.isArray(entry) ? Number(entry[0]) : NaN, y = Array.isArray(entry) ? Number(entry[1]) : NaN;
    return Number.isFinite(x) && Number.isFinite(y) ? shape.toN(x, y) : null;
  };
  const labelPoints = shaped && onLabels && Array.isArray(o.labels) ? o.labels.map(labelAt) : [];
  let told = null;
  function tellLabels() {
    const W = stage.size.width, H = stage.size.height, unit = Math.sqrt(W * H) || 1, at = uniforms.uShapePlace.value;
    const points = labelPoints.map((n) => {
      if (!n) return { x: 0, y: 0, visible: false };
      let x, y, visible;
      if (tilt) {
        probe.set(n[0] * SHAPE_WORLD, 0, -n[1] * SHAPE_WORLD).project(stage.camera);
        x = ((probe.x + 1) / 2) * W;
        y = ((1 - probe.y) / 2) * H;
        visible = probe.z < 1 && Math.abs(probe.x) <= 1 && Math.abs(probe.y) <= 1;
      } else {
        x = (at.x + n[0] * at.z) * unit + W / 2;
        y = H / 2 - (at.y + n[1] * at.z) * unit;
        visible = x >= 0 && x <= W && y >= 0 && y <= H;
      }
      return { x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100, visible };
    });
    const same = told && points.every((pt, i) => Math.abs(pt.x - told[i].x) < 0.25 && Math.abs(pt.y - told[i].y) < 0.25
      && pt.visible === told[i].visible);
    if (same) return;
    told = points;
    try { onLabels(points.map((pt) => ({ ...pt }))); } catch (error) { console.error(error); }   // the chart goes on
  }

  stage.onFrame((time, delta) => {
    const u = material.uniforms;
    const still = stage.still;
    const damp = (from, to, rate) => (still ? to : THREE.MathUtils.damp(from, to, rate, delta));
    // Flow is time at the chosen speed, added up so a change of speed never makes the land jump.
    flow = still ? time * speed : flow + delta * speed;
    // The level repeats every index band, so it is kept within one: the lines, the tint and the
    // marks look the same, and the number never grows. With an outline the level breathes instead,
    // a third of a line up and down in about half a minute: the lines inside it stay its own.
    u.uTide.value = shaped ? interval * 0.35 * Math.sin(flow * 0.21 * num(o.tide, 1, 0, 5))
      : (flow * tide) % (interval * Math.max(u.uLook.value.z, 1));
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
    const fit = tilt ? 1 : Math.pow(Math.min(1, Math.max(0.45, unit / 1100)), 0.75);
    if (shaped) {
      // The outline stays put; the progress zooms in a fifth on it (flat), the land drifts round it.
      const zoom = tilt ? 1 : 1 + 0.2 * p;
      const kBase = (MAP / num(o.scale, 1, 0.2, 5)) * fit, k = kBase / zoom;
      const cx = tilt ? 0 : flatPlace.x, cy = tilt ? 0 : flatPlace.y;   // zoom round the outline's middle
      u.uView.value.set(ORIGIN[0] + DRIFT[0] * fx - DRIFT[1] * fy + cx * (kBase - k),
        ORIGIN[1] + DRIFT[1] * fx + DRIFT[0] * fy + cy * (kBase - k), k);
      if (!tilt) u.uShapePlace.value.set(flatPlace.x, flatPlace.y, flatPlace.s * zoom);
    } else {
      // "tilt" travels without the zoom: the eye comes closer instead.
      const k = (MAP / num(o.scale, 1, 0.2, 5)) * (tilt ? 1 : 1 - 0.38 * p) * fit;
      u.uView.value.set(ORIGIN[0] + p * TRAVEL[0] + DRIFT[0] * fx - DRIFT[1] * fy,
        ORIGIN[1] + p * TRAVEL[1] + DRIFT[1] * fx + DRIFT[0] * fy, k);
    }
    // The knoll grows while the pointer is over the scene and sinks when it leaves.
    presence = damp(presence, stage.pointer.inside && !still && lift > 0 ? 1 : 0, 4);
    if (tilt) {
      // The view turns a few degrees with the pointer and drifts slowly; scrolling brings the eye
      // lower and closer. A still frame shows the view at rest.
      const sway = still ? 0 : 1;
      const azimuth = sway * (stage.pointer.x * 0.14 + Math.sin(time * 0.07) * 0.04);
      const elevation = Math.min(1.5707, Math.max(0.3, angle - 0.1 * p
        + sway * (stage.pointer.y * 0.04 + Math.sin(time * 0.11) * 0.015)));
      place(azimuth, elevation, distance * (1 - 0.12 * p));
      u.uFog.value.set(distance * 1.0, distance * 1.65);   // the far land fades out before the top edge
      // The knoll stands where the pointer meets the sheet.
      let found = false;
      if (presence > 0.001) {
        ray.setFromCamera(aim.set(stage.pointer.x, stage.pointer.y), stage.camera);
        found = ray.ray.intersectPlane(ground, hit) !== null;
      }
      if (found) u.uHill.value.set(hit.x * SHEET_SCALE, -hit.z * SHEET_SCALE, presence, lift * 0.4);
      else u.uHill.value.z = 0;
    } else {
      u.uHill.value.set((stage.pointer.x * stage.size.width) / (2 * unit), (stage.pointer.y * stage.size.height) / (2 * unit),
        presence, lift * 0.4);   // 0.4 high at lift 1: about four contour intervals at 16 levels
    }
    if (labelPoints.length) tellLabels();
    // The range rises and settles towards the data.
    ridgeHeight = damp(ridgeHeight, ridgeHeightTarget, 2.5);
    for (let i = 0; i < RIDGES; i++) ridges[i] = damp(ridges[i], ridgeTarget[i], 2.5);
    u.uRidgeHeight.value = ridgeHeight;
  });

  return stage.handle({
    setData(values) {
      if (shaped) return;   // the chart is the outline's: no hills of data next to a real place
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
