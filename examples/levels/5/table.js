/* Tidewatch, level 5: the chart table. The page's one WebGL scene, directed by journey.js (trip.js).

   The printed chart (the page's own SVG, printed in layers by print.js) lies on the table as a sheet of
   paper, and the sea bed it was drawn from (seabed.js) lifts it into a relief: the land stands up, the
   banks stand a little proud of the paper, the channels sink, shaded from the north-west as a
   cartographer shades relief and lit by the lamp, whose light throws the relief's shadows. In one pass:
   - the paper and its tints, then the water of the tide over them (a plane at the height of the tide:
     where the bed lies higher the bank is dry and shows its printed green, where the water covers it the
     shoal tint deepens; ripples and the lamp's glint on it; the wind's streaks, the scene kit's GPU
     particles, on open water only), then the ink over the water, so every line and word stays as sharp
     and dark as printed and in register with the banks;
   - the safe window laid along the pencil line as the page draws a window everywhere (magenta hatch with
     solid edges, the pencil line itself left clear), and the boat at the head of it; the pencil, its
     course, fixes, times and bearings, is printed with the ink, exactly as pencilled on the drawn chart;
   - by night the red lamp is all the light there is: the sheet glows where it falls and goes dark toward
     its edges, the tints darken it as on the page's night chart, the ink is dark on the red.
   The opening, at the top of the page: the 3D sheet first draws itself exactly where the drawn chart
   lies, flat, at its size and in its light, so one chart becomes 3D and there are never two; then it
   lifts off the page, its shadow spreading on the table, tips back and settles as the hero's view; the
   relief rises out of the print and the water floods in.
   Colours come from the two theme rules of tokens.css (print.js reads them), so the landfall can go to
   night in the day theme too; the wind's points are the scene kit's field.js on the same stage.

   mount(container, options) -> { stage, setProgress, setData, setPointer, setStory, pause, resume,
   destroy, onCamera, bedAt, level, night, surfaceAt, boatPoint, course }. Options: relief (seabed.js
   reliefGrid()), print { base, baseNight, ink, width, height, tokens } (print.js), course (chart
   points of the pencil line), story ({ p, lamp: [x, z], lampY, reach, night, boat, hatch, follow } at
   points p of the journey), window (the stretch of the course sailed inside the safe window), hero
   { target, dist, el, az, fov, shift } and heroPhone (the hero's view, as an orbit, with its lens shift).
   setProgress(p): the journey's progress. setData([level, wind, from]): the tide (0..1 of 6 m), the wind
   (0..1 of 40 kn) and where it comes from (0..1 of 360 degrees), the page's own numbers (trip.js).
   setStory({ idleHatch, idleBoat, night }): the hero's clock (how far the window has opened while the
   trip waits at its start, and the boat at the pier head once the clock is there), and the night as the
   page reads it from the landfall's slip (null: the story's).
   onCamera(fn): fn(camera) as each frame is drawn, for labels that follow the chart. The container gets
   the event "tableopen" when the opening is over. */
import * as THREE from "three";
import { mount as mountField } from "../../vendor/scenes/field.js";
import { stageUniforms, simplex2D, grain } from "../../vendor/scenes/glsl.js";

export const SHEET = { w: 10, d: 9 };             // world units: 100 chart units each
const VS = 0.034;                                 // world units per metre shown
const DEEP = 8;                                   // metres: depths soften past this, so a hole is no well
const LAND = 3.4;                                 // metres: the land and the dry banks rise toward this, never past it
const WATER_MAX = 6;                              // metres: setData's level 1
const WIND_MAX = 40;                              // knots: setData's wind 1
const OPENING = 2.9;                              // seconds the opening takes
const FADE = 380;                                 // ms the first frame takes to fade in over the drawn chart

export const toWorld = (x, y) => [(x - 500) / 100, (y - 450) / 100];
const soft = (h) => (h >= 0 ? LAND * Math.tanh(h / 3) : -DEEP * (1 - Math.exp(h / DEEP)));
export const shownHeight = (h) => soft(h) * VS;
const clamp01 = (v) => Math.min(1, Math.max(0, v));
const smooth = (a, b, x) => { const t = clamp01((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const inOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

/* ---- shader parts -------------------------------------------------------------------------------- */
const reliefGLSL = /* glsl */ `
uniform sampler2D uRelief;        // r: height shown (m), g: the bed (m above datum), b, a: slope east, south
uniform float uRise;
const float VS = ${VS.toFixed(4)};
`;

const poolGLSL = /* glsl */ `
uniform vec3 uLampPos;
uniform vec2 uDayReach, uNightReach;  // the pools' radii, east-west and north-south, world units
uniform vec3 uNightBg, uNightLamp, uNightLampMid;
// the page's lamp: a radial gradient from its colour to its middle at 48 percent, then to nothing
float dayPool(vec2 xz) {
  float r = length((xz - uLampPos.xz) / uDayReach);
  return r < 0.48 ? mix(1.0, 0.62, r / 0.48) : mix(0.62, 0.0, smoothstep(0.0, 1.0, (r - 0.48) / 0.52));
}
// the red lamp: its colour, its middle at 48 percent, the room at the edge, as the night chart's lamp
// (mixed as the page mixes a gradient, in the colours as written, so it falls off as the poster's does)
vec3 nightGlow(vec2 xz) {
  float r = length((xz - uLampPos.xz) / uNightReach);
  vec3 a = pow(uNightLamp, vec3(1.0 / 2.2)), m = pow(uNightLampMid, vec3(1.0 / 2.2)), b = pow(uNightBg, vec3(1.0 / 2.2));
  vec3 g = r < 0.48 ? mix(a, m, r / 0.48) : mix(m, b, smoothstep(0.0, 1.0, (r - 0.48) / 0.52));
  return pow(g, vec3(2.2));
}
`;

const paperVertex = /* glsl */ `
${reliefGLSL}
uniform mat4 uOpen;
varying vec2 vUv;
varying vec3 vWorld;
void main() {
  vUv = vec2(uv.x, 1.0 - uv.y);                   // chart uv: y runs south
  vec4 bed = texture(uRelief, vUv);
  vec3 p = position;
  p.y = bed.r * VS * uRise;
  vec4 world = modelMatrix * vec4(p, 1.0);
  vWorld = world.xyz;                             // the light is worked out on the sheet as it lies
  gl_Position = projectionMatrix * viewMatrix * (uOpen * world);
}`;

const paperFragment = /* glsl */ `
${stageUniforms}
${simplex2D}
${grain}
${reliefGLSL}
${poolGLSL}
uniform sampler2D uBase, uBaseNight, uInk, uWindTex;
uniform float uNight, uLampOn, uPosterLamp, uWater, uLevel, uLevelY, uRipple, uWindOn, uMaxH;
uniform vec2 uWind, uStreak, uDrift, uHaze;
uniform vec3 uPaper, uLampRatio, uWaterTint, uShoal, uInk1, uMagenta1, uWindow0, uWindow1, uRoom0;
uniform vec4 uCourse[COURSE_POINTS];   // xy: chart point, z: distance along the course to it
uniform float uBoat, uWinFrom, uWinTo, uHatchOn, uBoatOn;
uniform vec2 uBoatAt;
varying vec2 vUv;
varying vec3 vWorld;

vec3 toLinear(vec3 c) { return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(0.04045, c)); }
vec2 toUv(vec2 xz) { return vec2(xz.x / 10.0 + 0.5, xz.y / 9.0 + 0.5); }
float heightAt(vec2 uv) { return texture(uRelief, uv).r * VS * uRise; }

// soft shadows of the relief: from the point toward the lamp over the height field; the start is
// jittered per pixel, so few steps give grain and not bands
float shadowAt(vec3 p, vec3 dir) {
  float s = 1.0, stepLen = 2.2 / float(STEPS);
  float t = 0.012 + stepLen * fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
  for (int i = 0; i < STEPS; i++) {
    vec3 q = p + dir * t;
    if (q.y > uMaxH * uRise + 0.01) break;
    vec2 uv = toUv(q.xz);
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) break;
    s = min(s, clamp(7.0 * (q.y - heightAt(uv)) / t, 0.0, 1.0));
    t += stepLen;
  }
  return s;
}

// distance (chart units) to the course, and how far along it the nearest point lies
vec2 course(vec2 c) {
  float best = 1e9, along = 0.0;
  for (int i = 0; i < COURSE_POINTS - 1; i++) {
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
  vec4 bed = texture(uRelief, uv);
  vec3 P = vWorld;
  float k = VS * uRise;
  vec3 n = normalize(vec3(-bed.b * k, 1.0, -bed.a * k));
  vec3 L = normalize(uLampPos - P);
  vec3 V = normalize(cameraPosition - P);
  float px = max(length(fwidth(chart)), 1e-4);    // one pixel in chart units, taken before any branch
  float depth = uLevel - bed.g;                   // metres of water over this point now
  float aw = fwidth(depth) + 0.002;
  float wet = smoothstep(-aw, aw, depth) * uWater;
  bool showDay = uNight < 0.999, showNight = uNight > 0.001;

  // ---- the light. The room from the north-west, as a cartographer shades relief; the lamp: its pool,
  // the slopes that face it, the shadows of the relief away from it. At the very start (uPosterLamp)
  // the lamp lights the bare paper only, as the page's lamp shines through the drawn chart.
  vec3 sun = normalize(vec3(-0.55, 0.8, -0.45));
  float hill = mix(1.0, clamp(dot(n, sun) / sun.y, 0.55, 1.35), 0.75 * uRise);
  float face = clamp(dot(n, L) / max(L.y, 0.2), 0.0, 1.6);
  float sh = 1.0;
#if STEPS > 0
  if (uRise > 0.02) sh = mix(1.0, shadowAt(P + n * 0.003, L), uRise);
#endif

  // ---- the water of the tide: a plane at its height, met by the eye's ray on its way to the bed
  float glint = 0.0, foam = 0.0, shallow = 0.0, wa = 0.0;
  if (wet > 0.001) {
    float reach = clamp((uLevelY - P.y) / max(V.y * length(cameraPosition - P), 1e-4), 0.0, 1.0);
    vec3 Q = P + (cameraPosition - P) * reach;
    float strength = length(uWind);
    vec2 w = strength > 0.001 ? uWind / strength : vec2(0.7, -0.7);
    vec3 g = snoiseGrad(Q.xz * vec2(2.3, 3.4) + w * uRipple * 0.5) * 0.7
           + snoiseGrad(Q.xz * vec2(6.1, 8.4) - w.yx * uRipple * 0.8) * 0.3;
    vec3 wn = normalize(vec3(-g.y * (0.008 + 0.022 * strength), 1.0, -g.z * (0.008 + 0.022 * strength)));
    vec3 Vq = normalize(cameraPosition - Q), Lq = normalize(uLampPos - Q);
    float hv = clamp(dot(wn, normalize(Lq + Vq)), 0.0, 1.0);
    glint = (pow(hv, 280.0) * 2.6 + pow(hv, 48.0) * 0.4) * (0.25 + 0.75 * sh) * wet;
    // the shoal tint deepens where the water stands shallow over a bank, a clearer wash over the deeps:
    // the banks surface and flood with the tide, with no line drawn of their own
    shallow = 1.0 - smoothstep(0.6, 3.2, depth);
    wa = (0.05 + 0.2 * shallow) * smoothstep(0.0, 0.35, depth + 0.1) * wet;
    // the wind over the water by day: the points' sharp cores, drawn out down the wind into short streaks
    if (uWindOn > 0.0 && showDay) {
      vec2 at = gl_FragCoord.xy / uResolution;
      float pts = 0.0, wsum = 0.0;
      for (int i = 0; i < STREAK_TAPS; i++) {
        float kk = float(i), wgt = 1.0 - kk / float(STREAK_TAPS);
        pts += smoothstep(0.08, 0.26, texture(uWindTex, fract(at - uDrift + uStreak * kk)).a) * wgt;
        wsum += wgt;
      }
      vec2 crossWind = vec2(-w.y, w.x);
      vec2 lanePos = vec2(dot(chart, crossWind) * 0.034, dot(chart, w) * 0.0045 - uRipple * 0.05);
      float lane = smoothstep(-0.1, 0.6, snoise(lanePos) * 0.75 + snoise(lanePos * 2.3 + 4.1) * 0.35);
      foam = clamp(pts * 2.0 / wsum, 0.0, 0.45) * uWindOn * smoothstep(0.8, 2.5, depth) * mix(0.15, 1.0, lane) * wet;
    }
  }

  vec4 ink = texture(uInk, uv);
  vec3 c = ink.a > 0.003 ? ink.rgb / ink.a : vec3(0.0);
  vec2 cr = course(chart);
  float band = 0.0, hatch = 0.0, rim = 0.0;
  if (cr.x < 12.0 && uHatchOn > 0.002) {
    // the safe window along the pencil line: magenta hatch with solid edges; as it opens it sweeps out
    // from the pier head; behind the boat full, ahead of it fainter; the pencil line itself stays clear
    float winHead = uWinFrom + (uWinTo - uWinFrom) * smoothstep(0.0, 0.6, uHatchOn);
    float corridor = 1.0 - smoothstep(7.0, 7.0 + max(px * 1.2, 0.6), cr.x);
    float inWin = smoothstep(uWinFrom - 2.0, uWinFrom + 2.0, cr.y) * (1.0 - smoothstep(winHead - 6.0, winHead, cr.y));
    float ahead = smoothstep(uBoat - 1.5, uBoat + 1.5, cr.y) * step(uWinFrom + 1.0, uBoat);
    float on = min(1.0, uHatchOn * 1.25);
    band = corridor * inWin * on * mix(1.0, 0.5, ahead);
    float stripe = dot(chart, vec2(0.78801075, 0.61566148)) / 4.0;   // 38 degrees, every 4 units
    float q = abs(fract(stripe) - 0.5) * 2.0;
    float fs = 1.5 * px / 4.0;
    hatch = smoothstep(0.76 - fs, 0.76 + fs, q) * smoothstep(1.3, 2.6, cr.x);
    rim = (1.0 - smoothstep(0.35, 0.35 + px, abs(cr.x - 7.0))) * inWin * on;
  }
  float r = length(chart - uBoatAt);
  float boatHalo = (1.0 - smoothstep(4.6, 4.6 + px + 0.2, r)) * uBoatOn;
  float boatDot = (1.0 - smoothstep(3.1, 3.1 + px + 0.2, r)) * uBoatOn;

  vec3 color = vec3(0.0);
  if (showDay) {
    vec3 base = texture(uBase, uv).rgb;
    float paper = 1.0 - smoothstep(0.004, 0.03, distance(base, uPaper));
    float pool = dayPool(P.xz) * uLampOn * mix(1.0, paper, uPosterLamp);
    float lampLit = mix(1.0, clamp(face, 0.0, 1.25) * mix(0.3, 1.0, sh), uRise);
    // the room keeps the paper as the page shows it; the lamp warms and brightens its pool, and its
    // light is what the relief's shadows take away
    vec3 dayLight = vec3(mix(1.0, 0.95, uRise) * hill);
    dayLight *= mix(vec3(1.0), uLampRatio * mix(1.0, 1.05, uRise), pool * lampLit);
    vec3 day = base * dayLight;
    day = mix(day, mix(uWaterTint, uShoal, shallow * 0.55) * dayLight, wa);
    day += uLampRatio * 0.9 * glint * (0.35 + 0.65 * pool);
    day = mix(day, dayLight, foam * 0.5);
    // the ink over the water, lit as the paper is; then the window's hatch, then the boat
    day = mix(day, toLinear(c) * mix(vec3(1.0), dayLight, 0.4), ink.a);
    day = mix(day, uWindow0 * dayLight, band * 0.07);
    day = mix(day, uWindow0 * dayLight, band * hatch * 0.72);
    day = mix(day, uWindow0 * dayLight, rim * 0.65);
    day = mix(day, uPaper * dayLight * 1.04, boatHalo);
    day = mix(day, uWindow0, boatDot);
    color = day;
  }
  if (showNight) {
    // by night the red lamp is all the light there is: the sheet glows where it falls and goes dark
    // toward its edges, the tints darken it, the ink is dark on the red (the paper halos of the figures
    // go, the magenta of the lights and the rose turns to the lamp's dim red)
    vec3 glow = nightGlow(P.xz) * mix(1.0, mix(0.84, 1.14, clamp(face, 0.0, 1.2)) * mix(0.74, 1.0, sh), uRise);
    vec3 night = glow * texture(uBaseNight, uv).rgb;
    night = night * mix(1.0, 0.9, wet * smoothstep(0.0, 2.0, depth)) + glow * glint * 0.5;
    if (ink.a > 0.003) {
      float light = dot(c, vec3(0.3, 0.59, 0.11));
      float magenta = clamp((c.r - c.g) * 3.0 - 0.4, 0.0, 1.0);
      float halo = smoothstep(0.62, 0.86, light);
      night = mix(night, mix(uInk1, uMagenta1 * (0.6 + 0.6 * glow / max(uNightLamp, vec3(0.01))), magenta), ink.a * (1.0 - halo) * 0.94);
    }
    night = mix(night, uWindow1, band * hatch * 0.3 + rim * 0.2);
    night = mix(night, uNightLampMid * 0.6, boatHalo);
    night = mix(night, uWindow1, boatDot);
    color = mix(color, night, uNight);
  }
  // the far side of the sheet melts a little into the room, so a low view has depth and no hard edge
  float haze = smoothstep(uHaze.x, uHaze.y, distance(cameraPosition, P)) * 0.4;
  color = mix(color, mix(uRoom0, uNightBg, uNight), haze);
  gl_FragColor = vec4(color, 1.0);
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy);
}`;

/* the table round the sheet: the sheet's soft shadow, and the lamp's light falling past the paper */
const tableVertex = /* glsl */ `
varying vec3 vWorld;
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vWorld = world.xyz;
  gl_Position = projectionMatrix * viewMatrix * world;
}`;
const tableFragment = /* glsl */ `
${grain}
${poolGLSL}
uniform float uNight, uLampOn, uLift, uShadowOn;
uniform vec3 uShade, uLampGlow;
varying vec3 vWorld;
void main() {
  // under the sheet the table is never seen: where the relief sinks the channels below the table's
  // plane it must not show through them (only while the sheet is lifted is its shadow drawn there)
  if (uLift < 0.02 && abs(vWorld.x) < 4.995 && abs(vWorld.z) < 4.495) discard;
  vec2 away = normalize(vWorld.xz - uLampPos.xz + 1e-4) * (0.07 + 0.55 * uLift);
  vec2 q = abs(vWorld.xz - away) - vec2(5.0, 4.5);
  float d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0);
  float blur = 0.1 + 1.1 * uLift;
  float shade = (1.0 - smoothstep(-0.02, blur + 0.32, d)) * mix(0.34, 0.16, uLift) * uShadowOn;
  // the lamp on the table round the sheet: by day a faint warm light, by night the red lamp's spill
  float spill = dayPool(vWorld.xz) * uLampOn * 0.5 * (1.0 - uNight);
  vec3 nightCol = mix(uNightBg, nightGlow(vWorld.xz), 0.55);      // the table takes less of the lamp than the paper
  float nightA = uNight * clamp(length(nightCol - uNightBg) * 6.0, 0.0, 1.0);
  float shadeA = shade * (1.0 - 0.6 * uNight);
  vec3 col = uLampGlow * spill;
  float alpha = spill * 0.35;
  col = mix(col, nightCol, nightA);
  alpha = max(alpha, nightA);
  col = mix(col, uShade * mix(1.0, 0.2, uNight), shadeA);
  alpha = alpha + shadeA - alpha * shadeA;
  gl_FragColor = vec4(col, alpha);
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy);
}`;

/* ---- textures -------------------------------------------------------------------------------------- */
/* the relief: per texel the height shown (m, softened, flat at the edges), the bed (m above datum; the
   margin past the neat line is dry), and the slope of what is shown, east and south, per world unit */
function reliefTexture(relief) {
  const { columns: C, rows: R, height } = relief;
  const shown = new Float32Array(C * R);
  let maxH = 0;
  for (let r = 0; r < R; r++) {
    for (let c = 0; c < C; c++) {
      const k = r * C + c, x = (c / (C - 1)) * 1000, y = (r / (R - 1)) * 900;
      const edge = Math.min(x, 987.5 - x, y, 887.5 - y);
      const u = clamp01(edge / 60), f = u * u * (3 - 2 * u);
      shown[k] = soft(height[k]) * f;
      maxH = Math.max(maxH, shown[k]);
    }
  }
  const data = new Uint16Array(C * R * 4), half = THREE.DataUtils.toHalfFloat;
  const dx = 10 / (C - 1), dz = 9 / (R - 1);
  for (let r = 0; r < R; r++) {
    for (let c = 0; c < C; c++) {
      const k = r * C + c, x = (c / (C - 1)) * 1000, y = (r / (R - 1)) * 900;
      const e = shown[r * C + Math.min(c + 1, C - 1)], w = shown[r * C + Math.max(c - 1, 0)];
      const s = shown[Math.min(r + 1, R - 1) * C + c], n = shown[Math.max(r - 1, 0) * C + c];
      data[k * 4] = half(shown[k]);
      data[k * 4 + 1] = half(x > 987.5 || y > 887.5 ? 99 : height[k]);
      data[k * 4 + 2] = half((e - w) / (dx * (Math.min(c + 1, C - 1) - Math.max(c - 1, 0))));
      data[k * 4 + 3] = half((s - n) / (dz * (Math.min(r + 1, R - 1) - Math.max(r - 1, 0))));
    }
  }
  const texture = new THREE.DataTexture(data, C, R, THREE.RGBAFormat, THREE.HalfFloatType);
  texture.minFilter = texture.magFilter = THREE.LinearFilter;
  texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.needsUpdate = true;
  return { texture, maxH: maxH * VS };
}

function canvasTexture(canvas, { srgb, premultiplied, aniso }) {
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  texture.flipY = false;                          // row 0 of the canvas is the north edge, as in the relief
  texture.premultiplyAlpha = Boolean(premultiplied);
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = true;
  texture.anisotropy = aniso;
  // once on the graphics chip the canvas is not needed again: let it go
  texture.onUpdate = () => { texture.onUpdate = null; setTimeout(() => { canvas.width = canvas.height = 1; }, 0); };
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

/* a view as an orbit round a target: azimuth from the south, elevation from the table; straight down
   (90 degrees) is north up on the screen, as the chart lies */
const orbitUp = new THREE.Vector3(), orbitM = new THREE.Matrix4();
function orbitPose(v, position, quaternion) {
  const a = THREE.MathUtils.degToRad(v.az), e = THREE.MathUtils.degToRad(Math.min(v.el, 90));
  position.set(v.target[0] + Math.sin(a) * Math.cos(e) * v.dist, v.target[1] + Math.sin(e) * v.dist, v.target[2] + Math.cos(a) * Math.cos(e) * v.dist);
  orbitUp.set(-Math.sin(a), 0, -Math.cos(a));
  orbitM.lookAt(position, new THREE.Vector3(...v.target), orbitUp);
  quaternion.setFromRotationMatrix(orbitM);
}
const lerpView = (a, b, t) => ({
  target: a.target.map((x, i) => x + (b.target[i] - x) * t), dist: Math.exp(Math.log(a.dist) + (Math.log(b.dist) - Math.log(a.dist)) * t),
  el: a.el + (b.el - a.el) * t, az: a.az + (b.az - a.az) * t, fov: a.fov + (b.fov - a.fov) * t,
  shift: [a.shift[0] + (b.shift[0] - a.shift[0]) * t, a.shift[1] + (b.shift[1] - a.shift[1]) * t],
});

const colour = (value, fallback) => {
  const c = new THREE.Color();
  try { c.setStyle(value && !/^rgba?\(.*,\s*0\s*\)$/.test(value) ? value : fallback); } catch (error) { c.setStyle(fallback); }
  return c;
};

export function mount(container, options = {}) {
  const o = { course: [[720, 412], [524, 594], [258.6, 694.4], [96, 756], [14, 787]], ...options };
  const fine = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  const wind = mountField(container, {
    formation: "wave", spread: 0.5, speed: 0.6, intensity: 0.4, count: fine ? 9000 : 5000, side: "center", renderScale: 1,
    camera: { fov: 30, near: 0.05, far: 200, position: [0, 9, 13], lookAt: [0, 0, 0] },
    stillTime: 9, fade: FADE,
    ...o.stage,
    tokens: { accent: "--wind-a", accent2: "--wind-b", ...((o.stage && o.stage.tokens) || {}) },
  });
  const stage = wind.stage;
  if (!stage || stage.failed || !stage.renderer || !o.relief || !o.print) return wind;

  const scene = stage.scene;
  const renderer = stage.renderer;
  // sharp at a slant: anisotropic filtering, cheap on a graphics chip, costly where it is drawn in software
  const aniso = Math.min(stage.quality.name === "low" ? 1 : fine ? 16 : 8, renderer.capabilities.getMaxAnisotropy());
  const relief = reliefTexture(o.relief);
  const bed = bedSampler(o.relief);
  const baseTex = canvasTexture(o.print.base, { srgb: true, aniso });
  const nightTex = canvasTexture(o.print.baseNight, { srgb: true, aniso });
  const inkTex = canvasTexture(o.print.ink, { srgb: false, premultiplied: true, aniso });

  // ---- the colours: the day and the night print's own tokens, whatever the page's theme
  const day = o.print.tokens.day, nightT = o.print.tokens.night, css = getComputedStyle(container);
  const paperC = colour(day["--color-bg"], "#f2ebdd");
  const lampC = colour(day["--color-lamp"], "#fffdf4");
  const C = {
    paper: paperC, lampRatio: new THREE.Vector3(lampC.r / paperC.r, lampC.g / paperC.g, lampC.b / paperC.b),
    water: colour(day["--color-water"], "#cde0e2"), shoal: colour(day["--color-chart-shoal"], "#bedae0"),
    ink1: colour(nightT["--color-chart-ink"], "#170705"),
    magenta1: colour(nightT["--color-chart-magenta"], "#8f3525"), window0: colour(day["--color-accent"], "#a8155b"),
    window1: colour(nightT["--color-accent"], "#ff6a4d"), nightBg: colour(nightT["--color-bg"], "#130c0a"),
    nightLamp: colour(nightT["--color-lamp"], "#a62d17"), nightLampMid: colour(nightT["--color-lamp-mid"], "#57170d"),
    shade: colour(css.getPropertyValue("--color-relief").trim().replace(/,\s*[\d.]+\)$/, ")").replace("rgba", "rgb"), "#4a340e"),
  };

  // ---- the course: chart points and the distance to each, for the shader and the boat
  const course = o.course.map((p) => [p[0], p[1], 0]);
  for (let i = 1; i < course.length; i++) course[i][2] = course[i - 1][2] + Math.hypot(course[i][0] - course[i - 1][0], course[i][1] - course[i - 1][1]);

  const shared = {
    uLampPos: { value: new THREE.Vector3(0.6, 3, 0.4) },
    uDayReach: { value: new THREE.Vector2(4.6, 4.3) }, uNightReach: { value: new THREE.Vector2(4.6, 4.3) },
    uNightBg: { value: C.nightBg }, uNightLamp: { value: C.nightLamp }, uNightLampMid: { value: C.nightLampMid },
    uNight: { value: 0 }, uLampOn: { value: 1 },
  };
  const paper = new THREE.ShaderMaterial({
    uniforms: {
      ...stage.uniforms, ...shared,
      uRelief: { value: relief.texture }, uRise: { value: stage.still ? 1 : 0 }, uMaxH: { value: relief.maxH + 0.01 },
      uOpen: { value: new THREE.Matrix4() },
      uBase: { value: baseTex }, uBaseNight: { value: nightTex }, uInk: { value: inkTex },
      uWindTex: { value: null }, uWindOn: { value: 1 }, uStreak: { value: new THREE.Vector2() }, uDrift: { value: new THREE.Vector2() },
      uPosterLamp: { value: stage.still ? 0 : 1 }, uWater: { value: stage.still ? 1 : 0 }, uLevel: { value: 1 }, uLevelY: { value: 0 },
      uRipple: { value: 0 }, uWind: { value: new THREE.Vector2(0.4, -0.4) }, uHaze: { value: new THREE.Vector2(30, 60) },
      uPaper: { value: C.paper }, uLampRatio: { value: C.lampRatio }, uWaterTint: { value: C.water }, uShoal: { value: C.shoal },
      uInk1: { value: C.ink1 },
      uMagenta1: { value: C.magenta1 }, uWindow0: { value: C.window0 }, uWindow1: { value: C.window1 }, uRoom0: { value: C.paper },
      uCourse: { value: course.map((p) => new THREE.Vector4(p[0], p[1], p[2], 0)) },
      uBoat: { value: 0 }, uBoatAt: { value: new THREE.Vector2(course[0][0], course[0][1]) }, uWinFrom: { value: 0 }, uWinTo: { value: 1e5 },
      uHatchOn: { value: 0 }, uBoatOn: { value: 0 },
    },
    defines: { COURSE_POINTS: course.length, STEPS: 8, STREAK_TAPS: 10 },
    vertexShader: paperVertex, fragmentShader: paperFragment,
  });
  const sheet = new THREE.Mesh(new THREE.BufferGeometry(), paper);
  sheet.frustumCulled = false;
  scene.add(sheet);

  const tableMat = new THREE.ShaderMaterial({
    uniforms: { ...shared, uLift: { value: 0 }, uShadowOn: { value: stage.still ? 1 : 0 }, uShade: { value: C.shade }, uLampGlow: { value: lampC } },
    vertexShader: tableVertex, fragmentShader: tableFragment, transparent: true, depthWrite: false,
  });
  const table = new THREE.Mesh(new THREE.PlaneGeometry(60, 60, 1, 1).rotateX(-Math.PI / 2), tableMat);
  table.position.y = -0.004;
  table.renderOrder = -1;
  scene.add(table);

  // ---- the wind: field.js's wave sheet, laid on the water and turned to the wind, drawn on its own
  // into a picture the paper reads, so the streaks lie only on open water
  const fieldGroup = scene.children.find((child) => child.isGroup && child.children.some((c) => c.isPoints));
  const points = fieldGroup && fieldGroup.children.find((c) => c.isPoints);
  if (points) points.material.uniforms.uDark = { value: 1 };   // a mask only: every point a sharp core
  const rig = new THREE.Group(), squash = new THREE.Group(), untilt = new THREE.Group();
  untilt.rotation.x = -0.32;
  rig.add(squash); squash.add(untilt);
  if (fieldGroup) untilt.add(fieldGroup);
  const windScene = new THREE.Scene();
  const windPose = new THREE.Group();
  windPose.matrixAutoUpdate = false;
  windScene.add(windPose);
  windPose.add(rig);
  const windTarget = new THREE.WebGLRenderTarget(4, 4, { depthBuffer: false, stencilBuffer: false });
  paper.uniforms.uWindTex.value = windTarget.texture;
  rig.position.set(-0.3, 0, 0.8);
  squash.scale.set(1.5, 0.08, 1.3);
  stage.onResize((size) => { windTarget.setSize(size.pixels.x, size.pixels.y); });
  stage.onDestroy(() => { windTarget.dispose(); stage.dispose(rig); });
  const streakA = new THREE.Vector3(), streakB = new THREE.Vector3();
  const windOnScreen = new THREE.Vector2(0.7, -0.7);
  sheet.onBeforeRender = (r, _s, camera) => {
    if (!points || paper.uniforms.uWindOn.value <= 0 || paper.uniforms.uWater.value <= 0.01) return;
    const u = paper.uniforms.uWind.value, strength = u.length();
    streakA.copy(rig.position).applyMatrix4(windPose.matrix).project(camera);
    streakB.set(rig.position.x + u.x * 0.5, rig.position.y, rig.position.z + u.y * 0.5).applyMatrix4(windPose.matrix).project(camera);
    let dx = (streakB.x - streakA.x) * 0.5, dy = (streakB.y - streakA.y) * 0.5;
    const taps = paper.defines.STREAK_TAPS;
    const len = Math.hypot(dx, dy), pxl = 2.5 / Math.max(stage.size.pixels.x, 1);
    const most = Math.min(taps * pxl, 0.004 + 0.03 * Math.min(1, strength * 2.2));
    if (len > 1e-6) { dx *= most / len; dy *= most / len; windOnScreen.set(dx / most, dy / most); }
    paper.uniforms.uStreak.value.set(dx / taps, dy / taps);
    const before = r.getRenderTarget();
    r.setRenderTarget(windTarget);
    r.clear(true, false, false);
    r.render(windScene, camera);
    r.setRenderTarget(before);
  };

  // the sheet's pose in the opening: lift 1 is in the air, a little toward the eye and tipped; the
  // paper and the wind share it, the shadow on the table stays where it is
  const openM = paper.uniforms.uOpen.value, turnX = new THREE.Matrix4(), turnZ = new THREE.Matrix4();
  function placeSheet(lift, tip) {
    if (lift <= 0 && tip <= 0) openM.identity();
    else {
      openM.makeTranslation(0, 0.9 * lift, 0);
      openM.multiply(turnX.makeRotationX(-0.05 * tip)).multiply(turnZ.makeRotationZ(0.035 * tip));
    }
    windPose.matrix.copy(openM);
    windPose.matrixWorldNeedsUpdate = true;
    tableMat.uniforms.uLift.value = lift;
  }

  // the course at a distance along it: chart point
  const along = (d) => {
    for (let i = 0; i < course.length - 1; i++) {
      if (d <= course[i + 1][2] || i === course.length - 2) {
        const t = clamp01((d - course[i][2]) / Math.max(course[i + 1][2] - course[i][2], 1e-3));
        return [course[i][0] + (course[i + 1][0] - course[i][0]) * t, course[i][1] + (course[i + 1][1] - course[i][1]) * t];
      }
    }
    return course[0].slice(0, 2);
  };

  // ---- the story by the journey's progress, and the page's own data
  const story = (Array.isArray(o.story) && o.story.length ? o.story : [{ p: 0 }]).slice().sort((x, y) => x.p - y.p);
  const BASE = { lamp: [0.6, 0.4], lampY: 3, reach: [4.6, 4.3], night: 0, boat: 0, hatch: 0, follow: 1 };
  const blendStory = (p) => {
    let i = 0;
    while (i < story.length - 2 && p > story[i + 1].p) i++;
    const a = { ...BASE, ...story[i] }, b = { ...BASE, ...(story[i + 1] || story[i]) };
    const t = b.p > a.p ? THREE.MathUtils.smootherstep(p, a.p, b.p) : 0;
    const mix = (x, y) => x + (y - x) * t;
    return { lamp: [mix(a.lamp[0], b.lamp[0]), mix(a.lamp[1], b.lamp[1])], lampY: mix(a.lampY, b.lampY),
             reach: [mix(a.reach[0], b.reach[0]), mix(a.reach[1], b.reach[1])], night: mix(a.night, b.night),
             boat: mix(a.boat, b.boat), hatch: mix(a.hatch, b.hatch), follow: mix(a.follow, b.follow) };
  };
  if (Array.isArray(o.window)) { paper.uniforms.uWinFrom.value = o.window[0]; paper.uniforms.uWinTo.value = o.window[1]; }
  const want = { progress: 0, level: 1, wind: 0.4, from: 225, idleHatch: null, idleBoat: 0, night: null, dark: false };
  const first = blendStory(0);
  const now = { level: want.level, wind: want.wind, night: 0, boat: first.boat, hatch: first.hatch, idleBoat: 0,
                lamp: [...first.lamp], lampY: first.lampY, reach: [...first.reach] };
  let ripple = 0, aim = null, wall = 0;
  const ray = new THREE.Raycaster(), plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), hit = new THREE.Vector3(), ndc = new THREE.Vector2();
  const onCamera = [];
  const lookDir = new THREE.Vector3();

  stage.onQuality((quality) => {
    const [sx, sz] = quality.pick([160, 144], [256, 230], [320, 288]);
    sheet.geometry.dispose();
    sheet.geometry = new THREE.PlaneGeometry(SHEET.w, SHEET.d, sx, sz).rotateX(-Math.PI / 2);
    const steps = quality.pick(4, 8, 12), taps = quality.pick(6, 10, 12);
    if (paper.defines.STEPS !== steps || paper.defines.STREAK_TAPS !== taps) {
      paper.defines.STEPS = steps; paper.defines.STREAK_TAPS = taps; paper.needsUpdate = true;
    }
  });
  stage.onTokens((tokens) => { want.dark = tokens.dark; if (stage.still) now.night = want.dark ? 1 : now.night; });

  // ---- the opening: from the drawn chart, exactly where it lies, to the hero's view
  const narrowQuery = window.matchMedia("(max-width: 60rem)");
  let poster = null;                              // the drawn chart's view and its lamp, measured
  function measurePoster() {
    const svg = container.querySelector("svg.trip__poster");
    const box = container.getBoundingClientRect();
    if (!svg || !box.width || !box.height) return null;
    const r = svg.getBoundingClientRect();
    if (!r.width || !r.height) return null;
    const s = Math.max(r.width / 1000, r.height / 900);                 // preserveAspectRatio slice
    const x0 = r.right - 1000 * s - box.left, y0 = r.bottom - 900 * s - box.top;   // xMax yMax
    const fov = 30;
    const [tx, tz] = toWorld((box.width / 2 - x0) / s, (box.height / 2 - y0) / s);
    const dist = box.height / (2 * Math.tan(THREE.MathUtils.degToRad(fov / 2)) * 100 * s);
    // the page's lamp over the drawn chart (the stage's ::before): its middle and its radii, on the chart
    const before = getComputedStyle(container, "::before");
    const left = parseFloat(before.left) || 0, right = parseFloat(before.right) || 0;
    const lw = box.width - left - right, lh = box.height;
    const [cxp, cyp, rxp, ryp] = narrowQuery.matches ? [0.58, 0.82, 0.95, 0.34] : [0.5, 0.51, 0.41, 0.46];
    const [lx, lz] = toWorld((left + lw * cxp - x0) / s, (lh * cyp - y0) / s);
    return { view: { target: [tx, 0, tz], dist, el: 90, az: 0, fov, shift: [0, 0] },
             lamp: [lx, lz], reach: [(lw * rxp) / s / 100, (lh * ryp) / s / 100] };
  }
  const heroView = () => (stage.size.aspect < 0.8 ? o.heroPhone || o.hero : o.hero) || null;
  // started: the first frame was drawn at the drawn chart; opened: seconds into the opening (null: none)
  let opened = null, openStart = 0, openDone = stage.still;
  const tmpPos = new THREE.Vector3(), tmpQuat = new THREE.Quaternion(), shiftM = new THREE.Matrix4();
  const journeyPos = new THREE.Vector3(), journeyQuat = new THREE.Quaternion();
  const clockNow = () => (document.timeline && document.timeline.currentTime != null ? document.timeline.currentTime : performance.now()) / 1000;

  // the lens shift: the hero's (its subject beside or below the words), blended out as the trip starts;
  // on a phone the slips lie over the top of the screen, so the flight keeps its subject low (h.flight)
  function heroShift() {
    const h = heroView();
    if (!h || stage.still) return [0, 0];
    const k = 1 - smooth(0.0, 0.1, want.progress);
    const f = h.flight ? smooth(0.06, 0.2, want.progress) * (1 - smooth(0.88, 0.98, want.progress)) : 0;
    const fl = h.flight || [0, 0];
    return [h.shift[0] * k + fl[0] * f, h.shift[1] * k + fl[1] * f];
  }

  // where the hand points on the table, with the camera this frame is drawn with; the opening's camera
  // and the hero's lens shift are put on the journey's camera here, just before it draws
  scene.onBeforeRender = (_r, _s, camera) => {
    let shift = heroShift();
    if (!openDone && poster && opened !== null) {
      const h = heroView();
      if (h) {
        const t = clamp01(opened / OPENING);
        const k = inOut(smooth(0.06, 0.94, t));
        const v = lerpView(poster.view, h, k);
        journeyPos.copy(camera.position);
        journeyQuat.copy(camera.quaternion);
        orbitPose(v, tmpPos, tmpQuat);
        const w = smooth(0.82, 1.0, t);           // the last moment hands over to the journey's own camera
        camera.position.copy(tmpPos).lerp(journeyPos, w);
        camera.quaternion.copy(tmpQuat).slerp(journeyQuat, w);
        camera.fov = v.fov + (camera.fov - v.fov) * w;
        camera.updateMatrix();
        camera.matrixWorld.copy(camera.matrix);
        camera.matrixWorldInverse.copy(camera.matrixWorld).invert();
        shift = [v.shift[0] + (shift[0] - v.shift[0]) * w, v.shift[1] + (shift[1] - v.shift[1]) * w];
      }
    }
    camera.updateProjectionMatrix();
    if (shift[0] || shift[1]) {
      camera.projectionMatrix.premultiply(shiftM.makeTranslation(shift[0], shift[1], 0));
      camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
    }
    camera.getWorldDirection(lookDir);
    const toTable = lookDir.y < -0.05 ? camera.position.y / -lookDir.y : 30;
    paper.uniforms.uHaze.value.set(toTable * 1.6, toTable * 3.6);
    if (stage.pointer.active && !stage.still && openDone) {
      ndc.set(stage.pointer.x, stage.pointer.y);
      ray.setFromCamera(ndc, camera);
      aim = ray.ray.intersectPlane(plane, hit) ? [hit.x, hit.z] : null;
    } else aim = null;
    for (const fn of onCamera.slice()) fn(camera);
  };

  stage.onFrame((time) => {
    const still = stage.still;
    const wallNow = clockNow(), dt = wall ? Math.min(wallNow - wall, 0.25) : 0;
    wall = stage.running && !still ? wallNow : 0;
    const ease = (from, to, seconds) => (still || !dt ? to : from + (to - from) * (1 - Math.exp(-dt / seconds)));
    const s = blendStory(want.progress);
    if (fieldGroup) { fieldGroup.position.set(0, 0, 0); fieldGroup.scale.setScalar(1); fieldGroup.rotation.set(0, 0, 0); }
    if (points) {
      const u = points.material.uniforms;
      u.uCalmAmount.value = 0;
      u.uFocus.value = 0.4;
      stage.camera.getWorldDirection(lookDir);
      const toTable = lookDir.y < -0.05 ? stage.camera.position.y / -lookDir.y : 14;
      u.uSize.value = 0.02 * Math.min(1, Math.max(0.4, toTable / 13));
    }

    // the opening. The first frame lies exactly on the drawn chart; once the canvas has faded in over it,
    // the sheet lifts, tips back into the hero's view and settles; the relief and the water come with it.
    // Opened half way down the page, or still, the table is simply there.
    if (opened === null && !openDone) {
      if (still || want.progress > 0.03) { openDone = true; container.dispatchEvent(new CustomEvent("tableopen")); }
      else {
        poster = measurePoster();
        if (!poster) { openDone = true; container.dispatchEvent(new CustomEvent("tableopen")); }
        else { opened = 0; openStart = wallNow + FADE / 1000 + 0.12; }
      }
    }
    let t = 1;
    if (!openDone && opened !== null) {
      opened = Math.max(0, wallNow - openStart);
      if (want.progress > 0.03) opened = Math.max(opened, OPENING * 0.999);
      t = clamp01(opened / OPENING);
      if (t >= 1) { openDone = true; opened = null; container.dispatchEvent(new CustomEvent("tableopen")); }
    }
    const lift = openDone ? 0 : Math.sin(Math.PI * smooth(0.02, 0.88, t)) * (1 - smooth(0.6, 0.92, t));
    placeSheet(Math.max(0, lift) * 0.55, Math.max(0, lift));
    const rise = openDone ? 1 : smooth(0.3, 0.92, t);
    paper.uniforms.uRise.value = rise;
    paper.uniforms.uPosterLamp.value = openDone ? 0 : 1 - smooth(0.1, 0.6, t);
    paper.uniforms.uWater.value = openDone ? 1 : smooth(0.55, 1.0, t);
    tableMat.uniforms.uShadowOn.value = openDone ? 1 : smooth(0.05, 0.4, t);
    const handOver = openDone ? 1 : smooth(0.15, 0.85, t);  // the lamp from the page's to the scene's

    // the hero's clock (setStory idleHatch) holds the window band only at the very start
    const idle = want.idleHatch === null ? 0 : 1 - smooth(0.01, 0.1, want.progress);
    const hatchGoal = (s.hatch + ((want.idleHatch ?? s.hatch) - s.hatch) * idle) * (openDone ? 1 : 0);
    now.level = ease(now.level, want.level, 0.6);
    now.wind = ease(now.wind, want.wind, 0.8);
    const nightGoal = want.dark ? 1 : (want.night ?? s.night);
    now.night = ease(now.night, nightGoal, 0.32);
    now.boat = ease(now.boat, s.boat, 0.3);
    now.hatch = ease(now.hatch, hatchGoal, 0.45);
    now.lampY = ease(now.lampY, s.lampY, 0.4);
    now.reach[0] = ease(now.reach[0], s.reach[0], 0.4);
    now.reach[1] = ease(now.reach[1], s.reach[1], 0.4);
    // the lamp hangs where the story puts it, leans to the hand, and sways a little as a lamp aboard does
    const target = [...s.lamp];
    if (aim) {
      target[0] += (Math.min(Math.max(aim[0], -5.2), 5.2) - target[0]) * s.follow;
      target[1] += (Math.min(Math.max(aim[1], -4.6), 4.6) - target[1]) * s.follow;
    }
    if (!still) {
      const swing = aim ? 0.3 : 1;
      target[0] += swing * (0.22 * Math.sin(time * 0.53) + 0.08 * Math.sin(time * 1.31 + 0.7));
      target[1] += swing * (0.15 * Math.sin(time * 0.41 + 1.9) + 0.06 * Math.sin(time * 1.07));
    }
    now.lamp[0] = ease(now.lamp[0], target[0], 0.38);
    now.lamp[1] = ease(now.lamp[1], target[1], 0.38);
    const lampAt = [now.lamp[0], now.lamp[1]], reach = [...now.reach];
    if (poster && handOver < 1) {               // the opening starts from the page's own lamp over the drawn chart
      for (let i = 0; i < 2; i++) {
        lampAt[i] = poster.lamp[i] + (lampAt[i] - poster.lamp[i]) * handOver;
        reach[i] = poster.reach[i] + (reach[i] - poster.reach[i]) * handOver;
      }
    }
    shared.uLampPos.value.set(lampAt[0], now.lampY, lampAt[1]);
    shared.uDayReach.value.set(reach[0], reach[1]);
    // the red lamp is all the light there is, so its pool reaches further: the print stays readable in
    // it and falls to dark only toward the edges of the sheet (at the start, the page's own lamp exactly)
    const wider = 1 + 0.3 * handOver;
    shared.uNightReach.value.set(reach[0] * wider, reach[1] * wider);
    shared.uNight.value = now.night;
    const level = Math.min(now.level, 5.4);
    paper.uniforms.uLevel.value = level;
    paper.uniforms.uLevelY.value = shownHeight(level) * rise + 0.0005;
    // the wind: the points' sheet turns to where it blows and lies on the water
    const toward = ((want.from + 180) * Math.PI) / 180;
    const wx = Math.sin(toward), wz = -Math.cos(toward);
    rig.rotation.y = Math.atan2(-wz, wx);
    rig.position.y = paper.uniforms.uLevelY.value + 0.01;
    paper.uniforms.uWind.value.set(wx * now.wind, wz * now.wind);
    ripple += dt * (0.25 + now.wind * 1.6);
    if (!still && dt) {
      const drift = paper.uniforms.uDrift.value, pace = dt * (0.006 + 0.03 * now.wind);
      drift.set((drift.x + windOnScreen.x * pace) % 1, (drift.y + windOnScreen.y * pace) % 1);
    }
    paper.uniforms.uRipple.value = still ? 3 : ripple;
    paper.uniforms.uBoat.value = now.boat;
    paper.uniforms.uBoatAt.value.set(...along(now.boat));
    paper.uniforms.uHatchOn.value = now.hatch;
    // the boat shows once it has cast off, or while it waits at the pier head at the end of the hero's clock
    now.idleBoat = ease(now.idleBoat, want.idleBoat * (1 - smooth(0.01, 0.08, want.progress)), 0.5);
    paper.uniforms.uBoatOn.value = Math.max(smooth(0.5, 4, now.boat), now.idleBoat);
  });

  const handle = stage.handle({
    setProgress(p) { if (Number.isFinite(Number(p))) { want.progress = clamp01(Number(p)); stage.invalidate(); } },
    setData(values) {
      const list = Array.from(values || [], Number);
      if (Number.isFinite(list[0])) want.level = clamp01(list[0]) * WATER_MAX;
      if (Number.isFinite(list[1])) want.wind = clamp01(list[1]);
      if (Number.isFinite(list[2])) want.from = clamp01(list[2]) * 360;
      // the sea under the wind: the stronger it blows, the higher the crests of the points' sheet
      const knots = want.wind * WIND_MAX, amp = Math.min(0.42, 0.04 + knots / 60);
      wind.setData(Array.from({ length: 36 }, (_, i) => 0.5 + amp * Math.sin(i * 1.7) * (0.6 + 0.4 * Math.sin(i * 0.37))));
      if (points) points.material.uniforms.uSpeed.value = 0.35 + knots / 26;
      stage.invalidate();
    },
    setStory(extra = {}) {
      if ("idleHatch" in extra) want.idleHatch = Number.isFinite(extra.idleHatch) ? extra.idleHatch : null;
      if ("night" in extra) want.night = Number.isFinite(extra.night) ? clamp01(extra.night) : null;
      if ("idleBoat" in extra) want.idleBoat = clamp01(Number(extra.idleBoat) || 0);
      stage.invalidate();
    },
    onCamera(fn) { onCamera.push(fn); return () => { const at = onCamera.indexOf(fn); if (at !== -1) onCamera.splice(at, 1); }; },
    bedAt: bed,
    level: () => now.level,
    night: () => now.night,
    opening: () => !openDone,
    surfaceAt(x, y) { return shownHeight(bed(x, y)) * paper.uniforms.uRise.value; },
    boatPoint() {
      const c = along(now.boat), w = toWorld(c[0], c[1]);
      return { chart: c, world: [w[0], shownHeight(bed(c[0], c[1])) * paper.uniforms.uRise.value, w[1]],
               on: now.boat > 1 && now.hatch > 0.5 && c[0] > 8 && c[0] < 992 && c[1] > 8 && c[1] < 892 };
    },
    course,
    destroy() {
      scene.onBeforeRender = () => {};
      sheet.onBeforeRender = () => {};
      onCamera.length = 0;
      if (handle.dispose) handle.dispose();
      for (const t of [relief.texture, baseTex, nightTex, inkTex]) t.dispose();
      wind.destroy();
    },
  });
  return handle;
}
