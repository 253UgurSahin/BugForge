/**
 * glsl.js: shader source for the scene kit, as strings a scene puts together.
 *
 *   import { stageUniforms, simplex3D, fbm, grain } from "./glsl.js";
 *   const fragmentShader = `
 *     ${stageUniforms}
 *     ${simplex3D}
 *     ${fbm}
 *     ${grain}
 *     varying vec2 vUv;
 *     void main() {
 *       float n = fbm(vec3(vUv * 3.0, uTime * 0.05));
 *       gl_FragColor = vec4(mix(uAccent, uAccent2, n * 0.5 + 0.5), 1.0);
 *       #include <colorspace_fragment>
 *       gl_FragColor.rgb += dither(gl_FragCoord.xy);
 *     }`;
 *
 * Every export is plain GLSL for THREE.ShaderMaterial (WebGL 2, so GLSL ES 3.00 behind three's
 * prefix; a RawShaderMaterial must set `precision highp float; precision highp int;` itself).
 * Each piece brings the pieces it needs and is wrapped in an #ifndef guard, so any set of them can
 * go into one shader in any order, and twice does no harm. Put them above your own code.
 *
 * What there is (the functions each export defines):
 *   stageUniforms  the declarations for stage.uniforms: uTime, uResolution, uPixelRatio, uPointer,
 *                  uProgress, uBg, uText, uMuted, uAccent, uAccent2, uSurface, uBorder, uDark.
 *   common         PI, TAU, remap(value, inLow, inHigh, outLow, outHigh), rotate2D(angle) -> mat2.
 *   hash           hashU(uint | ivec2 | ivec3) -> uint; hash(vec2 | vec3) -> float 0..1, the same for
 *                  every point in one unit cell; hash2(vec2) -> vec2, hash3(vec3) -> vec3.
 *   simplex2D      snoise(vec2) -> about -1..1; snoiseGrad(vec2) -> vec3(value, d/dx, d/dy).
 *   simplex3D      snoise(vec3) -> about -1..1; snoiseGrad(vec3) -> vec4(value, d/dx, d/dy, d/dz).
 *   curl           curlNoise(vec2) -> vec2, curlNoise(vec3) -> vec3: a flow field that never piles up
 *                  or thins out. Its length is about 1 on average and seldom over 2.5.
 *   fbm            fbm(vec2), fbm(vec3) -> about -1..1: FBM_OCTAVES layers of simplex noise (5; put
 *                  `#define FBM_OCTAVES 3` above it for fewer, for instance in low quality).
 *   palette        paletteMix(t, a, b), paletteMix(t, a, b, c), paletteMix(t, a, b, c, d): t from 0
 *                  to 1 walks through two, three or four colours with soft joins.
 *   oklab          linearToOklab(vec3), oklabToLinear(vec3), mixOklab(a, b, t): a mix that keeps
 *                  its brightness even, where a plain mix of two strong colours dips or greys.
 *   grain          grain(pixel, time) -> -1..1, new 24 times a second: film grain; and
 *                  dither(pixel) -> vec3 of at most one 8-bit step: add it to the colour last, to
 *                  stop the bands a dark gradient shows.
 *   fog            fogLinear(depth, near, far) and fogExp(depth, density) -> 0 (clear) .. 1 (gone).
 *   pointSize      vertex shader: pointPixels(worldSize, viewDepth, projectionMatrix[1][1],
 *                  uResolution.y) -> gl_PointSize for a point of a size in world units.
 *   pointSprite    fragment shader only: softDot(gl_PointCoord) and softDot(gl_PointCoord, core) ->
 *                  alpha of a soft round point, the second with a solid middle of that radius.
 *   line           fragment shader only: aastep(edge, value); lineAlpha(field, widthPixels) for a
 *                  line where a field is 0; isoLines(value, spacing, widthPixels) for contour lines
 *                  every `spacing`.
 *
 * Colours: stage.uniforms holds linear working colours, as three uses everywhere. Mix them as they
 * are, end the fragment shader with `#include <colorspace_fragment>` (three's own piece, it turns
 * the result into sRGB), and add dither() after that.
 *
 * Where the techniques come from. All of the code here was written for this kit.
 * - Simplex noise: Ken Perlin, "Noise hardware" (SIGGRAPH 2002 course notes); the way it is laid
 *   out here, with the falloff (0.5 - d^2)^4 and its exact gradient, follows Stefan Gustavson,
 *   "Simplex noise demystified" (2005), whose reference code is in the public domain. The patent
 *   on simplex noise ended in 2022.
 * - The twelve gradient directions in 3D: Ken Perlin, "Improving noise" (SIGGRAPH 2002). Turning
 *   the 3D grid so that flat cuts show no rows: Kurt Spencer, OpenSimplex 2 (2020, public domain).
 * - The integer hash: constants of "lowbias32", Chris Wellons, "Prospecting for hash functions"
 *   (2018), public domain.
 * - Curl noise: Bridson, Hourihan and Nordenstam, "Curl-noise for procedural fluid flow"
 *   (SIGGRAPH 2007). Here the curl is taken from the exact gradient, not from differences.
 * - fbm (layers of noise, each twice as fine and half as strong): Mandelbrot and Van Ness (1968),
 *   in graphics since Perlin (1985); turning each layer so the grids do not line up is common use.
 * - Oklab: Björn Ottosson, "A perceptual color space for image processing" (2020), public domain.
 * - Dither with triangular noise: long standard in audio and image work, see Lipshitz, Wannamaker
 *   and Vanderkooy, "Quantization and dither" (1992).
 * - Lines of even width from screen-space derivatives (fwidth, dFdx, dFdy): common use since
 *   Gateau, "Solid wireframe" (NVIDIA, 2007).
 */

// Wrap a piece so that a second copy in the same shader is skipped.
const once = (name, body) => `
#ifndef FORGE_${name}
#define FORGE_${name}
${body.trim()}
#endif
`;

export const stageUniforms = once("STAGE_UNIFORMS", `
uniform float uTime;       // seconds the scene has run
uniform vec2 uResolution;  // the drawing buffer, in pixels
uniform float uPixelRatio;
uniform vec2 uPointer;     // eased, -1..1, y up
uniform float uProgress;   // eased scroll progress, 0..1
uniform vec3 uBg;
uniform vec3 uText;
uniform vec3 uMuted;
uniform vec3 uAccent;
uniform vec3 uAccent2;
uniform vec3 uSurface;
uniform vec3 uBorder;
uniform float uDark;       // 1.0 on a dark background, 0.0 on a light one
`);

export const common = once("COMMON", `
#ifndef PI
#define PI 3.141592653589793
#endif
#ifndef TAU
#define TAU 6.283185307179586
#endif
float remap(float value, float inLow, float inHigh, float outLow, float outHigh) {
  return outLow + (outHigh - outLow) * clamp((value - inLow) / (inHigh - inLow), 0.0, 1.0);
}
mat2 rotate2D(float angle) {
  float c = cos(angle), s = sin(angle);
  return mat2(c, s, -s, c);
}
`);

// Whole numbers in, well-mixed whole numbers out. Integers behave the same on every graphics chip,
// which the old fract(sin(x) * 43758.5) trick does not.
export const hash = once("HASH", `
uint hashU(uint x) {
  x ^= x >> 16;
  x *= 0x7feb352dU;
  x ^= x >> 15;
  x *= 0x846ca68bU;
  x ^= x >> 16;
  return x;
}
// A grid point: each coordinate times its own large prime, then one round of mixing. (Mixing every
// coordinate on its own is no better to the eye and makes the noise half as fast again.)
uint hashU(ivec2 p) { return hashU(uint(p.x) * 0x9e3779b1U + uint(p.y) * 0x85ebca77U); }
uint hashU(ivec3 p) { return hashU(uint(p.x) * 0x9e3779b1U + uint(p.y) * 0x85ebca77U + uint(p.z) * 0xc2b2ae3dU); }
float hashToFloat(uint h) { return float(h >> 8) * (1.0 / 16777216.0); } // 24 bits: exact in a float
float hash(vec2 p) { return hashToFloat(hashU(ivec2(floor(p)))); }
float hash(vec3 p) { return hashToFloat(hashU(ivec3(floor(p)))); }
vec2 hash2(vec2 p) {
  uint h = hashU(ivec2(floor(p)));
  return vec2(hashToFloat(h), hashToFloat(hashU(h)));
}
vec3 hash3(vec3 p) {
  uint h = hashU(ivec3(floor(p)));
  uint i = hashU(h);
  return vec3(hashToFloat(h), hashToFloat(i), hashToFloat(hashU(i)));
}
`);

export const simplex2D = hash + once("SIMPLEX_2D", `
// A unit vector for a grid point, the same every time.
vec2 simplexDirection(ivec2 cell) {
  float angle = hashToFloat(hashU(cell)) * 6.283185307179586;
  return vec2(cos(angle), sin(angle));
}
// x: the noise, about -1..1. yz: its exact slope.
vec3 snoiseGrad(vec2 p) {
  const float SKEW = 0.3660254037844386;    // (sqrt(3) - 1) / 2: squashes the plane so triangles fill squares
  const float UNSKEW = 0.21132486540518713; // (3 - sqrt(3)) / 6: and back
  vec2 cell = floor(p + (p.x + p.y) * SKEW);
  vec2 d0 = p - cell + (cell.x + cell.y) * UNSKEW;             // from the cell's first corner to p
  vec2 side = d0.x >= d0.y ? vec2(1.0, 0.0) : vec2(0.0, 1.0);  // which of the cell's two triangles
  vec2 d1 = d0 - side + UNSKEW;
  vec2 d2 = d0 - 1.0 + 2.0 * UNSKEW;
  ivec2 corner = ivec2(cell);
  vec2 g0 = simplexDirection(corner);
  vec2 g1 = simplexDirection(corner + ivec2(side));
  vec2 g2 = simplexDirection(corner + 1);
  // Each corner adds a slope that fades to nothing half a unit away: (0.5 - distance^2)^4.
  vec3 fade = max(0.5 - vec3(dot(d0, d0), dot(d1, d1), dot(d2, d2)), 0.0);
  vec3 fade2 = fade * fade, fade4 = fade2 * fade2;
  vec3 along = vec3(dot(g0, d0), dot(g1, d1), dot(g2, d2));
  vec3 pull = -8.0 * fade2 * fade * along;
  vec2 slope = pull.x * d0 + pull.y * d1 + pull.z * d2 + fade4.x * g0 + fade4.y * g1 + fade4.z * g2;
  return 99.0 * vec3(dot(fade4, along), slope);
}
float snoise(vec2 p) { return snoiseGrad(p).x; }
`);

export const simplex3D = hash + once("SIMPLEX_3D", `
// One of the twelve directions from the middle of a cube to the middle of an edge.
vec3 simplexDirection(ivec3 cell) {
  uint h = hashU(cell);
  float a = (h & 1u) == 0u ? 1.0 : -1.0;
  float b = (h & 2u) == 0u ? 1.0 : -1.0;
  uint axis = (h >> 2) % 3u; // the axis this direction has no part in
  return axis == 0u ? vec3(0.0, a, b) : (axis == 1u ? vec3(a, 0.0, b) : vec3(a, b, 0.0));
}
// x: the noise, about -1..1. yzw: its exact slope.
vec4 snoiseGrad(vec3 p) {
  // Turn the grid so that its long diagonal lies along z. A flat cut (z fixed: the usual "2D noise
  // that changes in time") then goes through the grid where it looks the same in every direction;
  // without the turn such a cut shows rows.
  const mat3 TURN = mat3(0.70710678, -0.70710678, 0.0, 0.40824829, 0.40824829, -0.81649658, 0.57735027, 0.57735027, 0.57735027);
  p = TURN * p;
  vec3 cell = floor(p + (p.x + p.y + p.z) / 3.0);
  vec3 d0 = p - cell + (cell.x + cell.y + cell.z) / 6.0; // from the cell's first corner to p
  // The cell is cut into six pieces; p is in the one found by walking from the first corner to the
  // last along the largest part of d0 first. Rank the parts: 2 largest, 0 smallest; a tie goes to
  // x, then y, so there is always exactly one order.
  float xy = step(d0.y, d0.x), yz = step(d0.z, d0.y), xz = step(d0.z, d0.x);
  vec3 rank = vec3(xy + xz, 1.0 - xy + yz, 2.0 - xz - yz);
  vec3 step1 = step(1.5, rank), step2 = step(0.5, rank);
  vec3 d1 = d0 - step1 + 1.0 / 6.0;
  vec3 d2 = d0 - step2 + 1.0 / 3.0;
  vec3 d3 = d0 - 0.5;
  ivec3 corner = ivec3(cell);
  vec3 g0 = simplexDirection(corner);
  vec3 g1 = simplexDirection(corner + ivec3(step1));
  vec3 g2 = simplexDirection(corner + ivec3(step2));
  vec3 g3 = simplexDirection(corner + 1);
  // 0.5 and not the often-used 0.6: with 0.6 a corner still counts a little outside its own pieces,
  // which leaves faint creases in the slope, and so in anything that flows along the curl.
  vec4 fade = max(0.5 - vec4(dot(d0, d0), dot(d1, d1), dot(d2, d2), dot(d3, d3)), 0.0);
  vec4 fade2 = fade * fade, fade4 = fade2 * fade2;
  vec4 along = vec4(dot(g0, d0), dot(g1, d1), dot(g2, d2), dot(g3, d3));
  vec4 pull = -8.0 * fade2 * fade * along;
  vec3 slope = pull.x * d0 + pull.y * d1 + pull.z * d2 + pull.w * d3
             + fade4.x * g0 + fade4.y * g1 + fade4.z * g2 + fade4.w * g3;
  return 76.8 * vec4(dot(fade4, along), slope * TURN); // slope * TURN turns the slope back
}
float snoise(vec3 p) { return snoiseGrad(p).x; }
`);

export const curl = simplex2D + simplex3D + once("CURL", `
// In 2D the flow runs along the contour lines of one noise field.
vec2 curlNoise(vec2 p) {
  vec3 n = snoiseGrad(p);
  return 0.3 * vec2(n.z, -n.y);
}
// In 3D it is the curl of three noise fields: the same noise, read at three places far apart.
vec3 curlNoise(vec3 p) {
  vec3 a = snoiseGrad(p).yzw;
  vec3 b = snoiseGrad(p + vec3(31.416, -47.853, 12.679)).yzw;
  vec3 c = snoiseGrad(p + vec3(-23.394, 15.213, 61.937)).yzw;
  return 0.25 * vec3(c.y - b.z, a.z - c.x, b.x - a.y);
}
`);

export const fbm = simplex2D + simplex3D + once("FBM", `
#ifndef FBM_OCTAVES
#define FBM_OCTAVES 5
#endif
float fbm(vec2 p) {
  float sum = 0.0, weight = 0.5;
  for (int i = 0; i < FBM_OCTAVES; i++) {
    sum += weight * snoise(p);
    p = mat2(1.8461538, 0.7692308, -0.7692308, 1.8461538) * p; // twice as fine, turned by 22.6 degrees
    weight *= 0.5;
  }
  return sum;
}
float fbm(vec3 p) {
  float sum = 0.0, weight = 0.5;
  for (int i = 0; i < FBM_OCTAVES; i++) {
    sum += weight * snoise(p);
    // twice as fine, turned a sixth of a turn round the diagonal
    p = mat3(1.3333333, 1.3333333, -0.6666667, -0.6666667, 1.3333333, 1.3333333, 1.3333333, -0.6666667, 1.3333333) * p;
    weight *= 0.5;
  }
  return sum;
}
`);

export const palette = once("PALETTE", `
vec3 paletteMix(float t, vec3 a, vec3 b) {
  return mix(a, b, smoothstep(0.0, 1.0, t));
}
vec3 paletteMix(float t, vec3 a, vec3 b, vec3 c) {
  float s = clamp(t, 0.0, 1.0) * 2.0;
  return mix(mix(a, b, smoothstep(0.0, 1.0, s)), c, smoothstep(1.0, 2.0, s));
}
vec3 paletteMix(float t, vec3 a, vec3 b, vec3 c, vec3 d) {
  float s = clamp(t, 0.0, 1.0) * 3.0;
  vec3 color = mix(a, b, smoothstep(0.0, 1.0, s));
  color = mix(color, c, smoothstep(1.0, 2.0, s));
  return mix(color, d, smoothstep(2.0, 3.0, s));
}
`);

export const oklab = once("OKLAB", `
vec3 linearToOklab(vec3 c) {
  vec3 lms = mat3(0.4122214708, 0.2119034982, 0.0883024619,
                  0.5363325363, 0.6806995451, 0.2817188376,
                  0.0514459929, 0.1073969566, 0.6299787005) * c;
  lms = pow(max(lms, 0.0), vec3(1.0 / 3.0));
  return mat3(0.2104542553, 1.9779984951, 0.0259040371,
              0.7936177850, -2.4285922050, 0.7827717662,
              -0.0040720468, 0.4505937099, -0.8086757660) * lms;
}
vec3 oklabToLinear(vec3 c) {
  vec3 lms = mat3(1.0, 1.0, 1.0,
                  0.3963377774, -0.1055613458, -0.0894841775,
                  0.2158037573, -0.0638541728, -1.2914855480) * c;
  lms = lms * lms * lms;
  return mat3(4.0767416621, -1.2684380046, -0.0041960863,
              -3.3077115913, 2.6097574011, -0.7034186147,
              0.2309699292, -0.3413193965, 1.7076147010) * lms;
}
vec3 mixOklab(vec3 a, vec3 b, float t) {
  return max(oklabToLinear(mix(linearToOklab(a), linearToOklab(b), t)), 0.0);
}
`);

export const grain = hash + once("GRAIN", `
// pixel: gl_FragCoord.xy. Typical use: color += grain(gl_FragCoord.xy, uTime) * 0.03.
float grain(vec2 pixel, float time) {
  return hashToFloat(hashU(ivec3(ivec2(pixel), int(floor(time * 24.0))))) * 2.0 - 1.0;
}
// Two hashes added give noise that is most often near 0 (a triangle), which hides the steps of an
// 8-bit canvas without showing a pattern of its own. On a see-through pixel, multiply by its alpha.
vec3 dither(vec2 pixel) {
  uint h = hashU(ivec2(pixel));
  return vec3((float(h & 0xffffu) + float(h >> 16)) / 65535.0 - 1.0) / 255.0;
}
`);

export const fog = once("FOG", `
// 0 at near or closer, 1 at far or beyond. Mix towards uBg with it, or on a see-through canvas
// lower the alpha by it, so far things melt into the page.
float fogLinear(float depth, float near, float far) {
  return smoothstep(near, far, depth);
}
float fogExp(float depth, float density) {
  return 1.0 - exp(-density * density * depth * depth);
}
`);

// Vertex shader, for THREE.Points.
export const pointSize = once("POINT_SIZE", `
// gl_PointSize for a point that is worldSize wide, viewDepth in front of the camera:
//   gl_PointSize = pointPixels(0.05, -mvPosition.z, projectionMatrix[1][1], uResolution.y);
float pointPixels(float worldSize, float viewDepth, float projectionScale, float bufferHeight) {
  return worldSize * projectionScale * bufferHeight * 0.5 / max(viewDepth, 0.0001);
}
`);

// Fragment shader only (it uses fwidth), for THREE.Points.
export const pointSprite = once("POINT_SPRITE", `
// 1 in the middle of the point, 0 at its rim, soft in between.
float softDot(vec2 pointCoord) {
  float d = min(length(pointCoord - 0.5) * 2.0, 1.0);
  float glow = 1.0 - d * d;
  return glow * glow;
}
// The same with a solid middle of radius core (0..1) and a clean edge round it.
float softDot(vec2 pointCoord, float core) {
  float d = length(pointCoord - 0.5) * 2.0;
  float edge = max(fwidth(d), 0.0001);
  return max(softDot(pointCoord), 1.0 - smoothstep(core - edge, core + edge, d));
}
`);

// Fragment shader only (it uses fwidth, dFdx and dFdy).
export const line = once("LINE", `
// step() with an edge exactly one pixel soft.
float aastep(float edge, float value) {
  float soft = max(fwidth(value) * 0.5, 0.000001);
  return smoothstep(edge - soft, edge + soft, value);
}
// How much of this pixel a line covers that runs where "field" is 0 (any value that grows away
// from the line). The slope of the field on screen turns it into pixels, so the line is as wide
// in pixels everywhere; its length is used and not fwidth's sum, which thins diagonal lines.
float lineAlpha(float field, float widthPixels) {
  float pixels = abs(field) / max(length(vec2(dFdx(field), dFdy(field))), 0.000001);
  return 1.0 - smoothstep(widthPixels * 0.5 - 0.5, widthPixels * 0.5 + 0.5, pixels);
}
// Contour lines of a field: one line at every multiple of spacing.
float isoLines(float value, float spacing, float widthPixels) {
  float v = value / spacing;
  float pixels = abs(fract(v - 0.5) - 0.5) / max(length(vec2(dFdx(v), dFdy(v))), 0.000001);
  return 1.0 - smoothstep(widthPixels * 0.5 - 0.5, widthPixels * 0.5 + 0.5, pixels);
}
`);
