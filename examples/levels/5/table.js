/* Tidewatch, level 5: the chart table. The page's one WebGL scene, directed by journey.js (trip.js).

   The printed chart (the page's own SVG, drawn onto a canvas by paper.js) lies on the table as a
   sheet of paper, and the sea bed it was drawn from (seabed.js) lifts it into a relief: the land
   stands up, the banks stand a little proud of the paper, the channels sink. Over it:
   - a sheet of water at the height of the tide. Where the bed is higher, the bank is dry; the 2 m
     line of the water as it stands now (what the boat needs) is drawn on the water and moves with it;
   - the lamp: a point light that follows the hand across the table; the relief takes its light and
     throws its shadows; at night it is the red lamp and the chart is only there where it shines;
   - the pencil course, and the safe window as a band of hatched light along it that fills in as the
     hours pass, its solid edge where the boat is now;
   - wind streaks over the water: the scene kit's GPU particles (field.js, its "wave" sheet), laid on
     the water, turned to the wind and stirred by its strength.
   All of it is one ShaderMaterial of the page's own for the paper, one for the water, field.js for
   the points, on one stage (field.js makes it). Colours come from the page's tokens only.

   mount(container, options) -> { stage, setProgress, setData, setPointer, setStory, pause, resume,
   destroy, lamp, project }. options.relief: seabed.js reliefGrid(); options.day, options.night: the
   chart pictures (canvases); options.course: chart points of the pencil line.
   setData([level, wind, from]): the tide (0..1 of 6 m), the wind (0..1 of 40 kn), where it comes
   from (0..1 of 360 degrees): read from the page's own tide table and readings (trip.js).
   setStory({ hour, lamp: [x, z], night, reach }): the hour of the passage (hatch and boat), where the
   lamp hangs, how far into the night the chart is (0..1), how much of the pencil line is drawn. */
import * as THREE from "three";
import { mount as mountField } from "../../vendor/scenes/field.js";
import { stageUniforms, common, simplex2D, simplex3D, grain, line } from "../../vendor/scenes/glsl.js";

export const SHEET = { w: 10, d: 9 };             // world units: 100 chart units each
const VS = 0.03;                                  // world units per metre of height (about 46 x)
const DEPTH = 11;                                 // metres: depths are softened past this
const WATER_MAX = 6;                              // metres: setData's level 1
const WIND_MAX = 40;                              // knots: setData's wind 1
const SPEED = 5.5 * 120 / 60;                     // chart units a minute at 5.5 knots (120 units a mile)

export const toWorld = (x, y, h = 0) => [(x - 500) / 100, h * VS, (y - 450) / 100];
export const toChart = (wx, wz) => [wx * 100 + 500, wz * 100 + 450];

const reliefGLSL = `
uniform sampler2D uRelief;
uniform float uRise;
const float VS = ${VS.toFixed(4)};
const float DEPTH = ${DEPTH.toFixed(1)};
// metres -> the height drawn: depths soften towards DEPTH, so a hole does not become a well
float shown(float h) { return h >= 0.0 ? h : -DEPTH * (1.0 - exp(h / DEPTH)); }
float shownSlope(float h) { return h >= 0.0 ? 1.0 : exp(h / DEPTH); }
// the relief goes to nothing at the edge of the sheet: the neat line and its margin lie flat
float sheetEdge(vec2 uv) {
  vec2 e = smoothstep(vec2(0.0), vec2(0.035, 0.04), uv) * smoothstep(vec2(0.0), vec2(0.035, 0.04), 1.0 - uv);
  return e.x * e.y;
}
// the soft fold down the sheet, where it was folded once (57 percent across, as on the poster)
float fold(vec2 uv) { float d = (uv.x - 0.57) / 0.035; return -0.018 * exp(-d * d); }
float foldSlope(vec2 uv) { float d = (uv.x - 0.57) / 0.035; return 0.018 * 2.0 * d / 0.035 * exp(-d * d) / ${SHEET.w.toFixed(1)}; }
vec4 bedAt(vec2 uv) { return texture(uRelief, uv); }
// world height of the paper at a chart uv (0..1, y down)
float paperY(vec2 uv) {
  float h = bedAt(uv).x;
  return shown(h) * VS * uRise * sheetEdge(uv) + fold(uv);
}
vec2 uvOfWorld(vec2 xz) { return vec2(xz.x / ${SHEET.w.toFixed(1)} + 0.5, xz.y / ${SHEET.d.toFixed(1)} + 0.5); }
`;

// The paper: the relief, its light and its shadows are worked out per vertex (the mesh is fine
// enough that the light reads smooth), so each pixel only reads the printed sheet and draws the
// pencil and the window band over it.
const lightGLSL = `
uniform vec3 uLampPos;
uniform float uLampReach;
// how much of the lamp's light reaches a point past the relief: a few steps toward the lamp
float lampShadow(vec3 p, vec3 L) {
  float lit = 1.0, t = 0.03;
  for (int i = 0; i < 6; i++) {
    vec3 q = p + L * t;
    vec2 uv = uvOfWorld(q.xz);
    if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) break;
    lit = min(lit, clamp((q.y - paperY(uv)) / (0.06 * t) + 0.35, 0.0, 1.0));
    t *= 1.85;
  }
  return lit;
}
// the pool of the lamp: a wide soft cone round the point under it
float poolAt(vec3 world) {
  float across = length(world.xz - uLampPos.xz) / uLampReach;
  return smoothstep(1.9, 0.2, across) / (1.0 + across * across * 1.6);
}
`;

const paperVertex = `
${reliefGLSL}
${lightGLSL}
varying vec2 vUv;
varying vec3 vWorld;
varying vec4 vLight;              // the lamp by day, the room light, the lamp by night, the pool
void main() {
  vUv = vec2(uv.x, 1.0 - uv.y);                   // chart uv: y runs south
  vec4 bed = bedAt(vUv);
  float edge = sheetEdge(vUv);
  vec3 p = position;
  p.y = shown(bed.x) * VS * uRise * edge + fold(vUv);
  vec4 world = modelMatrix * vec4(p, 1.0);
  vWorld = world.xyz;
  // the slope of the paper as drawn, so the light follows the relief
  float k = VS * 100.0 * uRise * edge * shownSlope(bed.x);
  vec3 N = normalize(vec3(-(bed.y * k + foldSlope(vUv) * 100.0), 1.0, -bed.z * k));
  vec3 L = normalize(uLampPos - world.xyz);
  float pool = poolAt(world.xyz);
  float facing = max(dot(N, L), 0.0);
  float shadow = lampShadow(world.xyz + N * 0.004, L);
  float room = 0.82 + 0.18 * dot(N, normalize(vec3(-0.55, 1.0, -0.6)));
  vLight = vec4(pool * mix(0.55, 1.0, facing) * mix(0.45, 1.0, shadow), room,
                pool * mix(0.4, 1.0, facing) * mix(0.25, 1.0, shadow), pool);
  gl_Position = projectionMatrix * viewMatrix * world;
}`;

const paperFragment = `
${stageUniforms}
${common}
${simplex2D}
${grain}
uniform sampler2D uDay;
uniform sampler2D uNight;
uniform float uNightMix;
uniform vec4 uCourse[8];          // xy: chart point, z: distance along the course to it
uniform int uCourseN;
uniform float uBoat;              // chart units along the course: where the boat is now
uniform float uWinFrom, uWinTo;   // the stretch of the course sailed inside the safe window
uniform float uReach;             // how much of the pencil line is drawn (chart units)
uniform float uHatchOn;           // 0..1: the window band shown at all
uniform vec3 uWindow;             // the window's colour (the accent) by day
uniform vec3 uLamp, uLampMid;     // the lamp's light on the paper, by day (page tokens)
uniform vec3 uNightBg, uNightLamp, uNightLampMid, uNightAccent;
uniform vec3 uPencil;
varying vec2 vUv;
varying vec3 vWorld;
varying vec4 vLight;

// distance (chart units) to the course, and how far along it the nearest point lies
vec2 course(vec2 c) {
  float best = 1e9, along = 0.0;
  for (int i = 0; i < 7; i++) {
    if (i >= uCourseN - 1) break;
    vec2 a = uCourse[i].xy, b = uCourse[i + 1].xy, ab = b - a;
    float t = clamp(dot(c - a, ab) / max(dot(ab, ab), 1e-4), 0.0, 1.0);
    float d = length(c - a - ab * t);
    if (d < best) { best = d; along = uCourse[i].z + t * (uCourse[i + 1].z - uCourse[i].z); }
  }
  return vec2(best, along);
}

void main() {
  vec2 uv = vUv;
  vec2 chart = uv * vec2(1000.0, 900.0);
  float lamp = vLight.x, room = vLight.y, glow = vLight.z, pool = vLight.w;
  vec3 color = vec3(0.0);
  // ---- day: the printed sheet in room light, brighter and warmer in the pool
  if (uNightMix < 0.999) {
    vec3 day = texture(uDay, uv).rgb;
    color = day * (0.86 * room + 0.2 * lamp * uLamp) * (1.0 - 0.05 * (1.0 - pool));
  }
  // ---- night: ink on a sheet that glows where the lamp falls, as on the page at night
  if (uNightMix > 0.001) {
    vec4 night = texture(uNight, uv);             // premultiplied: the chart's dark inks over nothing
    vec3 sheet = mix(uNightBg, uNightLampMid, smoothstep(0.0, 0.55, glow));
    sheet = mix(sheet, uNightLamp, smoothstep(0.35, 1.0, glow));
    sheet *= 0.92 + 0.08 * room;
    color = mix(color, sheet * (1.0 - night.a) + night.rgb * (0.35 + 0.65 * glow), uNightMix);
  }

  // ---- the pencil line and its fixes: graphite, a little broken by the grain of the paper
  vec2 c = course(chart);
  float fw = fwidth(c.x);
  if (c.x < 30.0) {
    float pencil = (1.0 - smoothstep(1.05 - 0.6 * fw - 0.15, 1.05 + 0.6 * fw + 0.15, c.x)) * step(c.y, uReach + 0.5);
    pencil *= 0.78 + 0.22 * smoothstep(-0.4, 0.6, snoise(chart * 1.7));
    float fixes = 0.0;
    for (int i = 0; i < 3; i++) {
      if (i >= uCourseN - 1) break;
      float r = length(chart - uCourse[i].xy), fr = fwidth(r);
      float ring = 1.0 - smoothstep(0.85, 0.85 + fr + 0.2, abs(r - 6.2));
      float spot = 1.0 - smoothstep(1.4, 1.4 + fr + 0.2, r);
      fixes = max(fixes, max(ring, spot) * step(uCourse[i].z, uReach + 1.0));
    }
    vec3 graphite = mix(uPencil, vec3(0.02), uNightMix);
    color = mix(color, graphite, max(pencil, fixes) * mix(0.85, 0.95, uNightMix));

    // ---- the safe window: a band of hatched light along the course, from the casting off to where
    // the boat is now (or to where the window closes), its solid edge where the boat is
    float head = min(uBoat, uWinTo);
    float corridor = 1.0 - smoothstep(15.0, 21.0, c.x);
    float sailed = smoothstep(uWinFrom - 2.0, uWinFrom + 2.0, c.y) * (1.0 - smoothstep(head - 1.5, head + 1.5, c.y));
    float band = corridor * sailed * uHatchOn;
    float stripe = dot(chart, vec2(0.78801075, 0.61566148)) / 5.0;   // 38 degrees, every 5 units
    float fs = fwidth(stripe);
    float hatch = 1.0 - smoothstep(0.17 - fs, 0.17 + fs, abs(fract(stripe) - 0.5) * 2.0 - 0.66);
    float moving = step(uWinFrom + 1.0, uBoat);
    float bar = (1.0 - smoothstep(1.2, 1.2 + fwidth(c.y) * 1.5, abs(c.y - head))) * corridor * uHatchOn * moving;
    vec3 win = mix(uWindow, uNightAccent, uNightMix);
    color = mix(color, win, band * mix(0.07, 0.14, uNightMix));
    color = mix(color, win, band * hatch * mix(0.62, 0.8, uNightMix));
    color = mix(color, win, bar * 0.95);
  }
  // the boat: a small solid diamond at the head of the band, in the window's colour
  if (uHatchOn > 0.01 && uBoat > uWinFrom + 1.0) {
    vec2 boatAt = uCourse[0].xy;
    for (int i = 0; i < 7; i++) {
      if (i >= uCourseN - 1) break;
      if (uBoat >= uCourse[i].z && uBoat <= uCourse[i + 1].z) {
        float t = (uBoat - uCourse[i].z) / max(uCourse[i + 1].z - uCourse[i].z, 1e-3);
        boatAt = mix(uCourse[i].xy, uCourse[i + 1].xy, t);
      }
    }
    vec2 rel = abs(chart - boatAt);
    float diamond = 1.0 - smoothstep(4.2, 4.2 + fwidth(rel.x + rel.y) + 0.3, rel.x + rel.y * 1.15);
    color = mix(color, mix(uWindow, uNightAccent, uNightMix), diamond * uHatchOn);
  }

  gl_FragColor = vec4(color, 1.0);
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy);
}`;

const waterVertex = `
varying vec2 vUv;
varying vec3 vWorld;
void main() {
  vUv = vec2(uv.x, 1.0 - uv.y);
  vec4 world = modelMatrix * vec4(position, 1.0);
  vWorld = world.xyz;
  gl_Position = projectionMatrix * viewMatrix * world;
}`;

const waterFragment = `
${stageUniforms}
${common}
${simplex2D}
${grain}
${line}
${reliefGLSL}
${lightGLSL}
uniform float uLevel;             // metres above datum: the tide now
uniform float uNightMix;
uniform vec2 uWind;               // where the wind blows to (chart xy, unit) times its strength 0..1
uniform float uRipple;            // time, run at the wind's pace
uniform vec3 uWaterTint, uShoal;
uniform vec3 uLamp, uNightBg, uNightLamp, uNightLampMid;
uniform sampler2D uWindTex;       // the wind's points, drawn this frame from the same camera
uniform float uWindOn;
varying vec2 vUv;
varying vec3 vWorld;

void main() {
  vec2 uv = vUv;
  vec2 chart = uv * vec2(1000.0, 900.0);
  float edge = sheetEdge(uv);
  float bed = bedAt(uv).x;
  float depth = uLevel - bed;                     // metres of water here, now
  if (depth <= 0.0 || edge < 0.5) discard;

  // ripples: two layers of noise sliding downwind, stronger with the wind
  float strength = length(uWind);
  vec2 w = strength > 0.001 ? uWind / strength : vec2(0.7, -0.7);
  vec2 q = chart * 0.045;
  vec3 n1 = snoiseGrad(q * vec2(1.0, 2.2) + w * uRipple * 0.6);
  vec3 n2 = snoiseGrad(q * 2.7 + w * uRipple * 1.3 + 7.3);
  vec2 slope = (n1.yz * 0.6 + n2.yz * 0.35) * (0.05 + 0.22 * strength);
  vec3 N = normalize(vec3(-slope.x, 1.0, -slope.y));
  vec3 V = normalize(cameraPosition - vWorld);
  float fresnel = 0.03 + 0.97 * pow(1.0 - max(dot(N, V), 0.0), 5.0);

  // the lamp seen in the water: a soft highlight where the surface mirrors it toward the eye
  vec3 L = normalize(uLampPos - vWorld);
  vec3 H = normalize(L + V);
  float across = length(vWorld.xz - uLampPos.xz) / uLampReach;
  float pool = 1.0 / (1.0 + across * across * 1.6);
  float glint = pow(max(dot(N, H), 0.0), 180.0) * 1.6 + pow(max(dot(N, H), 0.0), 22.0) * 0.12;

  // depth tint: shallow water is clear, deep water a little denser
  float body = smoothstep(0.0, 9.0, depth);
  float a = mix(0.08, 0.3, body) + fresnel * 0.25;
  // where the water meets a bank: a fine wet line
  float shoreLine = 1.0 - smoothstep(0.0, 0.18 + fwidth(depth) * 1.5, depth);
  // the 2 m line of the water as it is now: what a boat of 1.6 m needs, moving with the tide;
  // and the 5 m line, fainter
  float two = lineAlpha(depth - 2.0, 1.3) * (1.0 - smoothstep(0.0, 0.5, fwidth(depth)));
  float five = lineAlpha(depth - 5.0, 0.9) * 0.45 * (1.0 - smoothstep(0.0, 0.5, fwidth(depth)));

  vec3 dayCol = uWaterTint;
  vec3 nightCol = mix(uNightBg, uNightLampMid, pool * 0.6);
  vec3 col = mix(dayCol, nightCol, uNightMix);
  vec3 lampCol = mix(uLamp, uNightLamp * 1.6, uNightMix);
  vec3 lines = mix(uShoal, uNightLamp * 1.3, uNightMix);
  vec4 acc = vec4(col * a, a);
  acc = acc * (1.0 - two * 0.75) + vec4(lines * two * 0.75, two * 0.75);
  acc = acc * (1.0 - five) + vec4(lines * five, five);
  float sh = shoreLine * mix(0.55, 0.5, uNightMix);
  vec3 wet = mix(vec3(1.0), uNightLamp * 1.5, uNightMix);
  acc = acc * (1.0 - sh) + vec4(wet * sh, sh);
  float g = clamp(glint * (0.35 + 0.65 * pool), 0.0, 1.0);
  acc.rgb += lampCol * g * mix(0.85, 1.2, uNightMix);
  acc.a = clamp(acc.a + g * 0.6, 0.0, 1.0);
  // the wind over the water: field.js's points, only on open water, faint in the shallows, and
  // brighter in the lamp's pool at night
  vec4 pts = texture(uWindTex, gl_FragCoord.xy / uResolution) * uWindOn * smoothstep(0.1, 1.2, depth);
  pts.rgb *= mix(1.0, 0.55 + 1.1 * pool, uNightMix);
  acc.rgb = acc.rgb * (1.0 - pts.a * (1.0 - uDark)) + pts.rgb;
  acc.a = clamp(acc.a + pts.a * (1.0 - acc.a), 0.0, 1.0);
  acc *= edge;
  gl_FragColor = vec4(acc.rgb / max(acc.a, 1e-4), acc.a);
  #include <colorspace_fragment>
}`;

const num = (v, fallback, lo, hi) => (Number.isFinite(Number(v)) ? Math.min(hi, Math.max(lo, Number(v))) : fallback);
const damp = (from, to, rate, dt) => THREE.MathUtils.damp(from, to, rate, dt);

function reliefTexture(relief) {
  const { columns, rows, height } = relief;
  const dx = 1000 / (columns - 1), dy = 900 / (rows - 1);
  const data = new Uint16Array(columns * rows * 4);
  const at = (c, r) => height[Math.min(rows - 1, Math.max(0, r)) * columns + Math.min(columns - 1, Math.max(0, c))];
  const half = THREE.DataUtils.toHalfFloat;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < columns; c++) {
      const i = (r * columns + c) * 4;
      data[i] = half(at(c, r));
      data[i + 1] = half((at(c + 1, r) - at(c - 1, r)) / (2 * dx));
      data[i + 2] = half((at(c, r + 1) - at(c, r - 1)) / (2 * dy));
      data[i + 3] = half(1);
    }
  }
  const texture = new THREE.DataTexture(data, columns, rows, THREE.RGBAFormat, THREE.HalfFloatType);
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.needsUpdate = true;
  return texture;
}

function pictureTexture(canvas, renderer, premultiplied) {
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.premultiplyAlpha = Boolean(premultiplied);
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = true;
  texture.needsUpdate = true;
  return texture;
}

/* bed height (metres) at a chart point, from the relief grid: for the boat's sounder and the labels */
function bedSampler(relief) {
  const { columns, rows, height } = relief;
  return (x, y) => {
    const fx = Math.min(Math.max(x / 1000, 0), 1) * (columns - 1), fy = Math.min(Math.max(y / 900, 0), 1) * (rows - 1);
    const c = Math.min(Math.floor(fx), columns - 2), r = Math.min(Math.floor(fy), rows - 2), tx = fx - c, ty = fy - r;
    const h = (cc, rr) => height[rr * columns + cc];
    return (h(c, r) * (1 - tx) + h(c + 1, r) * tx) * (1 - ty) + (h(c, r + 1) * (1 - tx) + h(c + 1, r + 1) * tx) * ty;
  };
}
export function shownHeight(h) { return (h >= 0 ? h : -DEPTH * (1 - Math.exp(h / DEPTH))) * VS; }

export function mount(container, options = {}) {
  const o = { course: [[720, 412], [524, 594], [258.6, 694.4], [96, 756], [-140, 846]], ...options };
  const wind = mountField(container, {
    formation: "wave", spread: 0.55, speed: 0.6, intensity: 0.9, side: "center",
    camera: { fov: 32, near: 0.05, far: 160, position: [0, 9, 13], lookAt: [0, 0, 0] },
    stillTime: 9,
    ...o.stage,
    tokens: {
      accent: "--wind-a", accent2: "--wind-b", window: "--color-accent", lamp: "--color-lamp", lampMid: "--color-lamp-mid",
      pencil: "--color-chart-pencil", waterTint: "--table-water", shoal: "--color-accent-2",
      nightBg: "--night-bg", nightLamp: "--night-lamp", nightLampMid: "--night-lamp-mid", nightAccent: "--night-accent",
      ...((o.stage && o.stage.tokens) || {}),
    },
  });
  const stage = wind.stage;
  if (!stage || stage.failed || !stage.renderer || !o.relief) return wind;

  const scene = stage.scene;
  const relief = reliefTexture(o.relief);
  const bed = bedSampler(o.relief);
  const dayTex = pictureTexture(o.day, stage.renderer, false);
  const nightTex = pictureTexture(o.night, stage.renderer, true);

  // ---- the course: chart points and the distance to each, for the shader and the boat
  const course = o.course.map((p) => [p[0], p[1], 0]);
  for (let i = 1; i < course.length; i++) course[i][2] = course[i - 1][2] + Math.hypot(course[i][0] - course[i - 1][0], course[i][1] - course[i - 1][1]);
  const courseUniform = Array.from({ length: 8 }, (_, i) => new THREE.Vector4(...(course[Math.min(i, course.length - 1)] || [0, 0, 0]), 0));

  const shared = {
    uRelief: { value: relief }, uRise: { value: stage.still ? 1 : 0 },
    uLampPos: { value: new THREE.Vector3(1.4, 3.6, -0.2) }, uLampReach: { value: 3.4 },
    uNightMix: { value: 0 },
  };
  const paper = new THREE.ShaderMaterial({
    uniforms: {
      ...stage.uniforms, ...shared,
      uDay: { value: dayTex }, uNight: { value: nightTex },
      uCourse: { value: courseUniform }, uCourseN: { value: course.length },
      uBoat: { value: 0 }, uWinFrom: { value: 0 }, uWinTo: { value: 1e5 }, uReach: { value: stage.still ? 1e5 : 0 },
      uHatchOn: { value: 0 },
    },
    vertexShader: paperVertex, fragmentShader: paperFragment,
  });
  const sheet = new THREE.Mesh(new THREE.BufferGeometry(), paper);
  sheet.renderOrder = 0;
  scene.add(sheet);

  const waterMat = new THREE.ShaderMaterial({
    uniforms: {
      ...stage.uniforms, ...shared,
      uLevel: { value: 2.5 }, uWind: { value: new THREE.Vector2(0.4, -0.4) }, uRipple: { value: 0 },
      uWindTex: { value: null }, uWindOn: { value: 1 },
    },
    vertexShader: waterVertex, fragmentShader: waterFragment,
    transparent: true, depthWrite: false,
  });
  const water = new THREE.Mesh(new THREE.PlaneGeometry(SHEET.w, SHEET.d, 1, 1).rotateX(-Math.PI / 2), waterMat);
  water.renderOrder = 1;
  scene.add(water);

  // ---- the wind: field.js's wave sheet, laid on the water and turned to the wind
  const fieldGroup = scene.children.find((child) => child.isGroup && child.children.some((c) => c.isPoints));
  const points = fieldGroup && fieldGroup.children.find((c) => c.isPoints);
  const rig = new THREE.Group(), squash = new THREE.Group(), untilt = new THREE.Group();
  untilt.rotation.x = -0.32;                       // the wave sheet comes tilted 0.32 rad toward its camera
  rig.add(squash); squash.add(untilt);
  if (fieldGroup) untilt.add(fieldGroup);
  // the points are drawn on their own, into a picture the water lays over itself: so they lie only
  // on open water, never on a bank, the land or past the edge of the sheet
  const windScene = new THREE.Scene();
  windScene.add(rig);
  const windTarget = new THREE.WebGLRenderTarget(4, 4, { depthBuffer: false, stencilBuffer: false });
  waterMat.uniforms.uWindTex.value = windTarget.texture;
  rig.position.set(-0.3, 0, 0.8);                 // the middle of the river
  squash.scale.set(1.5, 0.08, 1.3);
  stage.onResize((size) => { windTarget.setSize(size.pixels.x, size.pixels.y); });
  stage.onDestroy(() => { windTarget.dispose(); stage.dispose(rig); });
  water.onBeforeRender = (renderer, _scene, camera) => {
    if (!points || waterMat.uniforms.uWindOn.value <= 0) return;
    const before = renderer.getRenderTarget();
    renderer.setRenderTarget(windTarget);
    renderer.clear(true, false, false);
    renderer.render(windScene, camera);
    renderer.setRenderTarget(before);
  };

  // ---- the story, by the journey's progress (options.story: { p, hour, lamp, lampY, reachLamp, night,
  //      boat, hatch, follow, reach } at points along it), and the page's own data (setData)
  const story = (Array.isArray(o.story) && o.story.length ? o.story : [{ p: 0 }]).slice().sort((x, y) => x.p - y.p);
  const BASE = { lamp: [1.4, -0.2], lampY: 3.6, reachLamp: 3.4, night: 0, boat: 0, hatch: 0, follow: 1, reach: 1e5 };
  const blendStory = (p) => {
    let i = 0;
    while (i < story.length - 2 && p > story[i + 1].p) i++;
    const a = { ...BASE, ...story[i] }, b = { ...BASE, ...(story[i + 1] || story[i]) };
    const span = b.p - a.p, t = span > 0 ? THREE.MathUtils.smootherstep(p, a.p, b.p) : 0;
    const mix = (x, y) => x + (y - x) * t;
    return { lamp: [mix(a.lamp[0], b.lamp[0]), mix(a.lamp[1], b.lamp[1])], lampY: mix(a.lampY, b.lampY),
             reachLamp: mix(a.reachLamp, b.reachLamp), night: mix(a.night, b.night), boat: mix(a.boat, b.boat),
             hatch: mix(a.hatch, b.hatch), follow: mix(a.follow, b.follow), reach: mix(a.reach, b.reach) };
  };
  if (Array.isArray(o.window)) { paper.uniforms.uWinFrom.value = o.window[0]; paper.uniforms.uWinTo.value = o.window[1]; }
  const want = { progress: 0, level: 2.5, wind: 0.4, from: 225, idleHatch: null, dark: false };
  const first = blendStory(0);
  const now = { level: want.level, wind: want.wind, night: first.night, boat: first.boat, hatch: first.hatch,
                reach: stage.still ? first.reach : 0, lamp: [...first.lamp], lampY: first.lampY, reachLamp: first.reachLamp };
  let ripple = 0, opening = stage.still ? 1 : 0, aim = null, started = false;
  const ray = new THREE.Raycaster(), plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), hit = new THREE.Vector3(), ndc = new THREE.Vector2();
  const onCamera = [];                             // functions that need the camera of this frame

  // the mesh carries the relief and its light, so its density follows the quality; so does the
  // sharpness of the printed sheet at a slant (anisotropic filtering)
  stage.onQuality((quality) => {
    const [sx, sz] = quality.pick([120, 108], [240, 216], [340, 306]);
    sheet.geometry.dispose();
    sheet.geometry = new THREE.PlaneGeometry(SHEET.w, SHEET.d, sx, sz).rotateX(-Math.PI / 2);
    const aniso = Math.min(quality.pick(1, 4, 8), stage.renderer.capabilities.getMaxAnisotropy());
    for (const t of [dayTex, nightTex]) { if (t.anisotropy !== aniso) { t.anisotropy = aniso; t.needsUpdate = true; } }
  });

  stage.onTokens((tokens) => { want.dark = tokens.dark; });

  // where the hand points on the table, with the camera this frame is drawn with
  scene.onBeforeRender = (renderer, _scene, camera) => {
    if (stage.pointer.active && !stage.still) {
      ndc.set(stage.pointer.x, stage.pointer.y);
      ray.setFromCamera(ndc, camera);
      aim = ray.ray.intersectPlane(plane, hit) ? [hit.x, hit.z] : null;
    } else aim = null;
    for (const fn of onCamera.slice()) fn(camera, renderer);
  };

  stage.onFrame((time, delta) => {
    const still = stage.still;
    const ease = (from, to, rate) => (still ? to : damp(from, to, rate, delta));
    const s = blendStory(want.progress);
    // field.js lays its sheet out for a hero of its own; here it lies on the water, so undo that
    if (fieldGroup) { fieldGroup.position.set(0, 0, 0); fieldGroup.scale.setScalar(1); fieldGroup.rotation.set(0, 0, 0); }
    if (points) {
      const u = points.material.uniforms;
      u.uCalmAmount.value = 0;                     // the page keeps its own text clear
      u.uFocus.value = stage.camera.position.distanceTo(rig.position) * 0.9;
    }
    // the opening, on the first frames at the top of the page: the relief rises out of the paper and
    // the pencil draws the course. Opened half way down the page, the table is simply there.
    if (!started) { started = true; if (want.progress > 0.05) opening = 1; }
    if (!still && opening < 1) opening = Math.min(1, opening + delta / 2.8);
    const o1 = still ? 1 : opening;
    shared.uRise.value = 1 - Math.pow(1 - Math.min(1, o1 * 1.1), 3);
    // the hero's clock (setStory idleHatch) holds the window band only at the very start
    const idle = want.idleHatch === null ? 0 : 1 - THREE.MathUtils.smoothstep(want.progress, 0.01, 0.1);
    const hatchGoal = s.hatch + ((want.idleHatch ?? s.hatch) - s.hatch) * idle;
    now.level = ease(now.level, want.level, 1.6);
    now.wind = ease(now.wind, want.wind, 1.2);
    now.night = ease(now.night, want.dark ? 1 : s.night, 2.4);
    now.boat = ease(now.boat, s.boat, 4);
    now.hatch = ease(now.hatch, hatchGoal, 2.4);
    now.lampY = ease(now.lampY, s.lampY, 2.4);
    now.reachLamp = ease(now.reachLamp, s.reachLamp, 2.4);
    const reachGoal = s.reach * (still ? 1 : THREE.MathUtils.smoothstep(o1, 0.3, 1));
    now.reach = still ? reachGoal : now.reach + (reachGoal - now.reach) * Math.min(1, delta * 2.6);
    // the lamp hangs where the story puts it, and leans to the hand
    const target = [...s.lamp];
    if (aim) {
      target[0] += (Math.min(Math.max(aim[0], -5.2), 5.2) - target[0]) * s.follow;
      target[1] += (Math.min(Math.max(aim[1], -4.6), 4.6) - target[1]) * s.follow;
    }
    now.lamp[0] = ease(now.lamp[0], target[0], 2.6);
    now.lamp[1] = ease(now.lamp[1], target[1], 2.6);
    shared.uLampPos.value.set(now.lamp[0], now.lampY, now.lamp[1]);
    shared.uLampReach.value = now.reachLamp;
    shared.uNightMix.value = now.night;
    waterMat.uniforms.uLevel.value = now.level;
    water.position.y = shownHeight(now.level) * shared.uRise.value;
    // the wind: the points' sheet turns to where it blows and lies on the water
    const toward = ((want.from + 180) * Math.PI) / 180;          // the compass bearing it blows to
    const wx = Math.sin(toward), wz = -Math.cos(toward);          // east and south in world units
    rig.rotation.y = Math.atan2(-wz, wx);
    rig.position.y = water.position.y + 0.01;
    waterMat.uniforms.uWind.value.set(wx * now.wind, wz * now.wind);
    ripple += (still ? 0 : delta) * (0.25 + now.wind * 1.6);
    waterMat.uniforms.uRipple.value = still ? 3 : ripple;
    paper.uniforms.uBoat.value = now.boat;
    paper.uniforms.uReach.value = now.reach;
    paper.uniforms.uHatchOn.value = now.hatch;
  });

  // the course at a distance along it: chart point, and whether it is on the sheet
  const along = (d) => {
    for (let i = 0; i < course.length - 1; i++) {
      if (d <= course[i + 1][2] || i === course.length - 2) {
        const t = Math.min(1, Math.max(0, (d - course[i][2]) / Math.max(course[i + 1][2] - course[i][2], 1e-3)));
        return [course[i][0] + (course[i + 1][0] - course[i][0]) * t, course[i][1] + (course[i + 1][1] - course[i][1]) * t];
      }
    }
    return course[0].slice(0, 2);
  };

  const handle = stage.handle({
    setProgress(p) { if (Number.isFinite(Number(p))) { want.progress = Math.min(1, Math.max(0, Number(p))); stage.invalidate(); } },
    setData(values) {
      const list = Array.from(values || [], Number);
      if (Number.isFinite(list[0])) want.level = Math.min(1, Math.max(0, list[0])) * WATER_MAX;
      if (Number.isFinite(list[1])) want.wind = Math.min(1, Math.max(0, list[1]));
      if (Number.isFinite(list[2])) want.from = Math.min(1, Math.max(0, list[2])) * 360;
      // the sea under the wind: the stronger it blows, the higher the crests of the points' sheet
      const knots = want.wind * WIND_MAX, amp = Math.min(0.42, 0.04 + knots / 60);
      wind.setData(Array.from({ length: 36 }, (_, i) => 0.5 + amp * Math.sin(i * 1.7) * (0.6 + 0.4 * Math.sin(i * 0.37))));
      if (points) points.material.uniforms.uSpeed.value = 0.35 + knots / 26;
      stage.invalidate();
    },
    setStory(extra = {}) {
      if ("idleHatch" in extra) want.idleHatch = Number.isFinite(extra.idleHatch) ? extra.idleHatch : null;
      stage.invalidate();
    },
    onCamera(fn) { onCamera.push(fn); return () => { const at = onCamera.indexOf(fn); if (at !== -1) onCamera.splice(at, 1); }; },
    bedAt: bed,
    level: () => now.level,
    // world height at a chart point: the paper, or the water over it
    surfaceAt(x, y) { return Math.max(shownHeight(bed(x, y)), shownHeight(now.level)) * shared.uRise.value; },
    boatPoint() {
      const c = along(now.boat), w = toWorld(c[0], c[1]);
      return { chart: c, world: [w[0], shownHeight(now.level) * shared.uRise.value, w[2]],
               on: now.boat > 1 && now.hatch > 0.5 && c[0] > 8 && c[0] < 992 && c[1] > 8 && c[1] < 892 };
    },
    course,
    destroy() {
      scene.onBeforeRender = () => {};
      water.onBeforeRender = () => {};
      onCamera.length = 0;
      if (handle.dispose) handle.dispose();
      wind.destroy();
    },
  });
  if (/debug/.test(location.hash)) window.__table = { THREE, stage, paper, waterMat, water, sheet, dayTex, nightTex, points, windTarget, rig };   // DEBUG-REMOVE
  handle.courseLength = course[course.length - 1][2];
  handle.speed = SPEED;
  return handle;
}
