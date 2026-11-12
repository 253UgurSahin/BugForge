/* Tidewatch, level 4: the chart table in three dimensions. The hero's one WebGL scene.

   The printed chart lies on the chart table as a sheet of paper, cut as the drawn chart is (x 140 to 1000,
   with its neat line on four sides), and the sea bed it was drawn from (seabed.js) lifts it into a relief:
   the land stands up as a raised plateau, the drying banks stand proud of the paper, the channels sink.
   - The print is the page's own SVG in two layers (print.js): the paper and its tints below, every line
     and letter above. Between them lies the water of the tide, so no word or line is ever under water:
     a clear glaze over the channels, a shoal tint over every bank it covers (so Spijkerplaat and Hooge
     Platen go under at high water and come back at low water), a bright line where it meets the bank,
     and the lamp's glints on its ripples.
   - The lamp hangs low over the table and follows the hand on its cable: a pool of warm light by day,
     the red night lamp at night, where the chart is only there inside its pool (dark ink on a red sheet,
     the print outside it a dim red). Its light rakes the relief: slopes that face it brighten, and the
     banks, the land and the turned-up corner throw soft shadows away from it.
   - The paper: the fold it has always had is a soft valley the lamp rakes across, the top right corner
     has turned up (its back shows, and its shadow lies on the chart), the cut edge has its thickness,
     and the sheet throws its shadow on the table.
   The view is the drawn chart's own: the camera is worked out from the CSS perspective of the poster
   (.sheet in its .hero__scene), so the first frame lies exactly over the drawn sheet and the change is
   a cross-fade, never a jump. Then the relief rises out of the print and the water comes in. The pointer
   turns the view a little and moves the lamp; scrolling away, the relief sinks back into the paper.
   Built on the scene kit's stage.js (renderer, tokens, pointer, pausing, reduced motion as one still
   frame, quality steps, the no-WebGL fallback) and glsl.js (noise, dither). The build is cut into small
   pieces with a breath between them, so the page never waits long for it.

   mount(container, options) -> Promise of { stage, setData, setProgress, setPointer, pause, resume,
   destroy }. setData([level, banks]): the water, 0..1 of 6 m above chart datum; banks 1 while the page
   shows an hour other than now: the lamp then leaves the hand and hangs over the banks that flood and dry
   (Spijkerplaat and Hooge Platen), so the tide is lit wherever the hand is (on the slip's own controls). setProgress(p): how far the hero
   has scrolled away, 0..1. The container gets the event "tablebuilt" when the opening is over, and the
   custom properties --gauge-x and --gauge-y: where the tide gauge at Vlissingen is on screen, in pixels
   of the container, for the page's label of the hour. */
import * as THREE from "three";
import { createStage } from "../../vendor/scenes/stage.js";
import { simplex2D, grain } from "../../vendor/scenes/glsl.js";
import { reliefRows } from "./seabed.js";
import { chartPrint } from "./print.js";

const X0 = 140, CW = 860, CH = 900;                // the sheet, in chart units
const SW = CW / 100, SD = CH / 100;                // and in world units: 8.6 by 9
const VS = 0.1;                                    // world units per metre shown: banks that stand up, seen from the side
const WATER_MAX = 6;                               // metres: setData's 1
const LAMP_HEIGHT = 1.9;                           // world units above the paper: low enough that the light rakes
const CURL = 100;                                  // chart units along each edge: the corner turned up
const CURL_TURN = 2.8;                             // radians the corner has turned over (160 degrees): a dog-ear, lifted a little
const FOLD_X = (X0 + 0.57 * CW - X0 - CW / 2) / 100;   // the fold, at 57 percent of the sheet, as level 3
const GAUGE = [706, 366];                          // the tide gauge, Vlissingen harbour
const clamp01 = (v) => Math.min(1, Math.max(0, v));
const phase = (t, a, b) => clamp01((t - a) / (b - a));
const inOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const breath = () => new Promise((resolve) => setTimeout(resolve, 0));
const toWorld = (x, y) => new THREE.Vector3((x - X0 - CW / 2) / 100, 0, (y - CH / 2) / 100);
/* metres of the bed as shown: the drying banks stand proud, the land is a low plateau, depths are softened */
const shown = (h) => (h >= 0 ? (h < 4.2 ? 1.45 * h : 6.1 + (h - 4.2) * 0.18) : -2.6 * Math.tanh(-h / 6));

const sheetVertex = /* glsl */ `
uniform sampler2D uHeight;
uniform float uRelief;
uniform float uFold;
uniform vec4 uHinge;          // a point on the corner's hinge (x, z) and the way out to the corner (x, z)
varying vec2 vUv;
varying vec3 vPos;
void main() {
  vec3 p = position;
  float past = dot(p.xz - uHinge.xy, uHinge.zw);
  if (past > 0.0) p.xz -= uHinge.zw * past;          // the corner is turned up: the sheet ends at its hinge
  vUv = vec2(p.x / ${SW.toFixed(2)} + 0.5, p.z / ${SD.toFixed(2)} + 0.5);
  float dx = p.x - ${FOLD_X.toFixed(4)};
  p.y = texture2D(uHeight, vUv).r * ${VS.toFixed(4)} * uRelief - uFold * exp(-dx * dx / 0.05);
  vec4 world = modelMatrix * vec4(p, 1.0);
  vPos = world.xyz;
  gl_Position = projectionMatrix * viewMatrix * world;
}`;

const sheetFragment = /* glsl */ `
uniform sampler2D uBase;
uniform sampler2D uBaseNight;
uniform sampler2D uInk;
uniform sampler2D uHeight;
uniform float uNight;
uniform float uRelief;
uniform float uFold;
uniform float uLevel;
uniform float uWater;
uniform float uTime;
uniform float uMaxH;
uniform float uSteps;
uniform float uRipples;
uniform vec3 uLampPos;
uniform vec3 uLampColor;
uniform float uLampPower;
uniform float uPoolR;
uniform float uPoolEdge;
uniform vec3 uRoom;
uniform float uHill;
uniform vec3 uShoal;
uniform vec3 uDeep;           // the water's colour where it stands deep: a darker teal by day, a deep red by night
uniform vec3 uLine;
uniform vec3 uGlint;
uniform vec3 uInkNight;
uniform vec3 uInkGlow;
uniform vec4 uHinge;
uniform float uFlap;
varying vec2 vUv;
varying vec3 vPos;
${simplex2D}
${grain}

vec2 uvOf(vec2 xz) { return vec2(xz.x / ${SW.toFixed(2)} + 0.5, xz.y / ${SD.toFixed(2)} + 0.5); }
float heightAt(vec2 xz) { return texture2D(uHeight, uvOf(xz)).r * ${VS.toFixed(4)} * uRelief; }

/* soft shadows: walk from the point toward the lamp over the height field; the closest miss sets the
   penumbra. The start is jittered per pixel, so few steps give grain, not bands */
float shadowAt(vec3 p, vec3 dir) {
  float s = 1.0;
  float stepLen = 1.7 / max(uSteps, 1.0);
  float t = 0.02 + stepLen * 0.5;
  for (int i = 0; i < 16; i++) {
    if (float(i) >= uSteps) break;
    vec3 q = p + dir * t;
    if (q.y > uMaxH) break;
    vec2 uv = uvOf(q.xz);
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) break;
    s = min(s, clamp(4.5 * (q.y - heightAt(q.xz)) / t, 0.0, 1.0));
    t += stepLen;
  }
  return smoothstep(0.0, 1.0, s);
}

void main() {
  vec3 P = vPos;
  vec2 uv = vUv;
  vec4 bed = texture2D(uHeight, uv);
  float k = ${VS.toFixed(4)} * uRelief;
  float dx = P.x - ${FOLD_X.toFixed(4)};
  float foldSlope = uFold * 2.0 * dx / 0.05 * exp(-dx * dx / 0.05);
  vec3 n = normalize(vec3(-bed.b * k - foldSlope, 1.0, -bed.a * k));

  /* the paper: by day its print; by night the night tints on a sheet only the red lamp lights */
  vec3 dayPaper = texture2D(uBase, uv).rgb;
  vec3 nightPaper = texture2D(uBaseNight, uv).rgb;
  vec3 albedo = mix(dayPaper, nightPaper, uNight);

  /* the room: a soft light from the north-west, as a cartographer shades relief */
  vec3 sun = normalize(vec3(-0.6, 0.7, -0.4));
  float hill = clamp(dot(n, sun) / sun.y, 0.0, 2.2);
  /* the lamp: its pool, how much each slope faces it, and the shadows of what stands between */
  vec3 toLamp = uLampPos - P;
  vec3 L = normalize(toLamp);
  float r = length(P.xz - uLampPos.xz) / uPoolR;
  float pool = 1.0 - smoothstep(uPoolEdge, 1.0, r);
    /* how much a slope faces the lamp, kept soft: paper scatters light, so a slope turned away is in
       shade, never black (a hard 0 drew the fold as a dark bar through the pool at night) */
    float face = 0.4 + 0.6 * min(max(dot(n, L), 0.0) / max(L.y, 0.2), 1.4);
    /* a shadow on paper under a lamp is soft and never black either: the room still lights it */
    float sh = pool > 0.01 ? mix(0.66, 1.0, shadowAt(P + n * 0.003, L)) : 1.0;
  /* the corner that turned up lies over the chart near its hinge: its shade */
  float inSide = -dot(P.xz - uHinge.xy, uHinge.zw);
  vec2 along = vec2(-uHinge.w, uHinge.z);
  float span = ${(CURL / 100 / Math.SQRT2).toFixed(4)};
  float flapShade = uFlap * (0.35 + 0.65 * smoothstep(span * 0.96, 0.0, inSide)) * smoothstep(-0.01, 0.03, inSide) * smoothstep(0.035, -0.02, abs(dot(P.xz - uHinge.xy, along)) + inSide - span * 0.94);
  float lit = sh * (1.0 - 0.55 * flapShade);
  /* the crease itself: the paper was folded here, a hairline of shade along it */
  float crease = exp(-dx * dx / 0.0016);
  vec3 light = uRoom * mix(1.0, hill, uHill) * (1.0 - 0.3 * flapShade) + uLampColor * uLampPower * pool * face * lit;
  vec3 col = albedo * light * (1.0 - 0.11 * crease * (1.0 - uNight * 0.5));
  /* paper has a little sheen where the lamp is seen in it, caught on every slope that faces it */
  vec3 V = normalize(cameraPosition - P);
    /* (kept faint: stronger, it smeared the name on the top of Spijkerplaat at low water) */
    col += uLampColor * uLampPower * pow(max(dot(n, normalize(L + V)), 0.0), 40.0) * pool * lit * 0.015 * (1.0 - 0.8 * uNight);

  /* the water of the tide, between the paper and the ink */
  float lap = 0.03 * sin(uTime * 1.15) + 0.014 * sin(uTime * 2.7 + 1.3);
  float depth = uLevel + lap - bed.g;                 // metres of water over this point now
  float aw = fwidth(depth) + 0.0005;
  float wet = smoothstep(-aw, aw, depth) * uWater;
  if (wet > 0.0) {
    vec2 w = P.xz * vec2(2.3, 3.4) + vec2(uTime * 0.05, -uTime * 0.034);
    vec3 g = snoiseGrad(w) * 0.7;
    if (uRipples > 1.5) g += snoiseGrad(P.xz * vec2(6.2, 8.8) + vec2(-uTime * 0.09, uTime * 0.07)) * 0.3;
    vec3 wn = normalize(vec3(-g.y * 0.018, 1.0, -g.z * 0.018));
    float onBank = smoothstep(-0.6, 0.4, bed.g);      // the bed is a bank or a beach that dries, not a channel
      /* how much of the water's own colour shows: a trace over the channels (their tint is printed), and over
         a bank that floods a clear sea-glass that deepens with the depth, so a bank under water and the same
         bank dry look plainly different in one still frame (at 0.26 to 0.62 the tide hardly showed) */
      float a = mix(0.05, mix(0.42, 0.78, smoothstep(0.0, 1.1, depth)), onBank);
    /* a slow sheen runs down the river with the stream */
    float sheen = 0.5 + 0.5 * sin(dot(P.xz, vec2(0.55, -0.9)) * 1.6 - uTime * 0.45 + g.x * 0.6);
    vec3 waterLight = uRoom + uLampColor * uLampPower * pool * 0.65;
      /* the water has a depth colour: sea-glass over the banks, a darker teal as the channel deepens, so the
         river reads as water and not as a tint (a trace of it over the channels, more over a flooded bank) */
      float deep = smoothstep(1.5, 9.0, depth);
      a = max(a, 0.3 * deep);
      vec3 water = mix(col, mix(uShoal, uDeep, deep) * waterLight, a);
      /* the sheen is a faint moving light, never a white film: at 0.14 it laid a milky haze over the river */
      water += uLampColor * uLampPower * pool * 0.045 * sheen * sheen * sheen * (1.0 - onBank * 0.7) * (1.0 - 0.6 * uNight);
    vec3 H = normalize(normalize(uLampPos - P) + V);
    float hv = clamp(dot(wn, H), 0.0, 1.0);
    /* the lamp's glints on the ripples: small and few. Stronger, they burned a white glare into the middle
       of the chart over Spijkerplaat */
    float glint = (pow(hv, 600.0) * 1.1 + pow(hv, 90.0) * 0.12) * pool * sh * (1.0 - 0.8 * uNight);
    water += uGlint * uLampPower * glint;
    col = mix(col, water, wet);
  }
  /* where the water meets the bank: a fine bright line, and the wet sand a little darker above it */
  float edge = clamp(1.0 - abs(depth) / (fwidth(depth) * 0.9 + 0.0005), 0.0, 1.0) * uWater * step(0.0, 0.5 - abs(bed.g) * 0.06);
  float damp = (1.0 - smoothstep(0.0, 0.22, -depth)) * step(depth, 0.0) * uWater;
  col *= 1.0 - 0.08 * damp;
  col = mix(col, uLine * (uRoom + uLampColor * uLampPower * pool), edge * 0.6);

    /* the ink, on top of everything. By day as printed: the lamp only shades it a little (more made the
       magenta rose brown). By night pale rose: bright where the lamp lights the sheet, softer in the gloom. */
    vec4 ink = texture2D(uInk, uv, -0.65);
    vec3 dayInk = ink.rgb * mix(1.0, clamp(light.r, 0.75, 1.0), 0.3);
    /* the print carries pale halos of paper colour round the figures that sit on a line (as charts do). By
       day they are paper; by night they must not glow: the night print takes only the dark part of the ink
       (its colour, unpremultiplied, darker than paper), so halos drop out and only lines and letters glow */
    vec3 inkColour = ink.rgb / max(ink.a, 0.001);
    float inkDark = 1.0 - smoothstep(0.42, 0.72, dot(inkColour, vec3(0.299, 0.587, 0.114)));
    float nightA = ink.a * inkDark;
    float paperLit = smoothstep(0.025, 0.12, col.r);
    vec3 nightInk = mix(uInkGlow, uInkNight, paperLit);
    vec3 dayCol = col * (1.0 - ink.a) + dayInk;
    vec3 nightCol = col * (1.0 - nightA) + nightInk * nightA;
    col = mix(dayCol, nightCol, uNight);

  gl_FragColor = vec4(col, 1.0);
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy);
}`;

/* the corner that has turned up: the same print on its face, the back of the paper on the other side */
const flapVertex = /* glsl */ `
varying vec2 vUv;
varying vec3 vPos;
varying vec3 vNormal2;
void main() {
  vUv = uv;
  vec4 world = modelMatrix * vec4(position, 1.0);
  vPos = world.xyz;
  vNormal2 = normalize(mat3(modelMatrix) * normal);
  gl_Position = projectionMatrix * viewMatrix * world;
}`;
const flapFragment = /* glsl */ `
uniform sampler2D uBase;
uniform sampler2D uBaseNight;
uniform sampler2D uInk;
uniform float uNight;
uniform vec3 uLampPos;
uniform vec3 uLampColor;
uniform float uLampPower;
uniform float uPoolR;
uniform float uPoolEdge;
uniform vec3 uRoom;
uniform vec3 uBack;
varying vec2 vUv;
varying vec3 vPos;
varying vec3 vNormal2;
${grain}
void main() {
  vec3 n = gl_FrontFacing ? vNormal2 : -vNormal2;
  vec3 L = normalize(uLampPos - vPos);
  float r = length(vPos.xz - uLampPos.xz) / uPoolR;
  float pool = 1.0 - smoothstep(uPoolEdge, 1.0, r);
  float face = max(dot(n, L), 0.0) / max(L.y, 0.2);
  float room = 0.55 + 0.45 * clamp(n.y, 0.0, 1.0);
  vec3 light = uRoom * room + uLampColor * uLampPower * pool * face;
  vec3 col;
  if (gl_FrontFacing) {
    vec4 ink = texture2D(uInk, vUv);
    col = mix(texture2D(uBase, vUv).rgb, texture2D(uBaseNight, vUv).rgb, uNight) * light;
    col = col * (1.0 - ink.a) + ink.rgb * (1.0 - uNight);
  } else {
    col = uBack * light;
  }
  gl_FragColor = vec4(col, 1.0);
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy);
}`;

/* the cut edge of the paper, and the table under the sheet: the lamp's light on it and the sheet's shadow */
const plainVertex = /* glsl */ `
varying vec3 vPos;
varying vec3 vNormal2;
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vPos = world.xyz;
  vNormal2 = normalize(mat3(modelMatrix) * normal);
  gl_Position = projectionMatrix * viewMatrix * world;
}`;
const edgeFragment = /* glsl */ `
uniform vec3 uLampPos;
uniform vec3 uLampColor;
uniform float uLampPower;
uniform float uPoolR;
uniform vec3 uRoom;
uniform vec3 uCut;
varying vec3 vPos;
varying vec3 vNormal2;
${grain}
void main() {
  float r = length(vPos.xz - uLampPos.xz) / uPoolR;
  float pool = 1.0 - smoothstep(0.4, 1.15, r);
  float face = max(dot(vNormal2, normalize(uLampPos - vPos)), 0.0);
  vec3 col = uCut * (uRoom * (0.62 + 0.25 * max(vNormal2.z, 0.0)) + uLampColor * uLampPower * pool * face * 0.8);
  gl_FragColor = vec4(col, 1.0);
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy);
}`;
const tableFragment = /* glsl */ `
uniform vec3 uLampPos;
uniform float uPoolR;
uniform vec3 uGlow;
uniform float uGlowA;
uniform vec3 uShade;
uniform float uShadeA;
varying vec3 vPos;
${grain}
float box(vec2 p, vec2 hs) { vec2 q = abs(p) - hs; return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0); }
void main() {
  vec2 d = vPos.xz - uLampPos.xz;
  float glow = exp(-dot(d, d) / (uPoolR * uPoolR * 1.6)) * uGlowA;
  vec2 away = normalize(vPos.xz - uLampPos.xz + 1e-4) * 0.16;          // the shadow falls away from the lamp
  float b = box(vPos.xz - away * 0.6 - vec2(0.05, 0.1), vec2(${(SW / 2).toFixed(2)}, ${(SD / 2).toFixed(2)}));
  float shade = (1.0 - smoothstep(-0.12, 0.5, b)) * uShadeA;
  float alpha = 1.0 - (1.0 - glow) * (1.0 - shade);
  vec3 col = mix(uGlow, uShade, shade / max(glow + shade, 1e-4));
  gl_FragColor = vec4(col, alpha);
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy);
}`;

/* wait until the drawn chart's own opening is over, so the scene takes over from a sheet at rest */
function settled(hero, cap = 2600) {
  const running = typeof document.getAnimations === "function"
    ? document.getAnimations().filter((a) => {
      const target = a.effect && a.effect.target;
      return target && hero.contains(target) && a.playState === "running" && a.effect.getTiming().iterations !== Infinity;
    })
    : [];
  const capped = new Promise((resolve) => setTimeout(resolve, cap));
  return Promise.race([Promise.all(running.map((a) => a.finished.catch(() => null))), capped]);
}

/* the camera of the drawn chart: the CSS perspective of .hero__scene and the transform of .sheet in it,
   turned into a camera over the 3D sheet, with the same lens (an off-centre frustum), so both meet */
function cssPose(container, sheet) {
  if (!sheet) return null;
  const cs = getComputedStyle(container);
  const P = parseFloat(cs.perspective);
  const W = container.clientWidth, H = container.clientHeight;
  const sw = sheet.offsetWidth, sh = sheet.offsetHeight;
  if (!P || !W || !H || !sw || !sh) return null;
  const [ox, oy] = cs.perspectiveOrigin.split(" ").map(parseFloat);
  const ss = getComputedStyle(sheet);
  const [tx, ty] = ss.transformOrigin.split(" ").map(parseFloat);
  let M;
  try { M = new DOMMatrix(ss.transform === "none" ? undefined : ss.transform); } catch (error) { return null; }
  const A = new DOMMatrix().translate(sheet.offsetLeft + tx, sheet.offsetTop + ty).multiply(M).translate(-tx, -ty);
  const inv = A.inverse();
  const s = sw / SW;                                   // pixels of the sheet per world unit
  const world = (u, v, w) => new THREE.Vector3(u / s - SW / 2, w / s, v / s - SD / 2);
  const dir = (d) => new THREE.Vector3(d.x, d.z, d.y).normalize();
  const c = inv.transformPoint(new DOMPoint(ox, oy, P, 1));
  const f = inv.transformPoint(new DOMPoint(0, 0, -1, 0));
  const up = inv.transformPoint(new DOMPoint(0, -1, 0, 0));
  const pos = world(c.x / c.w, c.y / c.w, c.z / c.w);
  const m = new THREE.Matrix4().lookAt(pos, pos.clone().add(dir(f)), dir(up));
  return { pos, quat: new THREE.Quaternion().setFromRotationMatrix(m), l: -ox / P, r: (W - ox) / P, t: oy / P, b: -(H - oy) / P };
}

export async function mount(container, options = {}) {
  const hero = container.closest(".hero") || document.body;
  const sheetEl = container.querySelector(".sheet");
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches || options.still;
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const fine = window.matchMedia("(hover: hover) and (pointer: fine)");

  /* 1. what the scene is made of: the print and the sea bed, a little at a time while the drawn chart
     shows. Without WebGL 2 none of it is made: the stage says "fallback" at once and the drawn chart stays. */
  let probe = null;
  try { probe = document.createElement("canvas").getContext("webgl2"); } catch (error) { probe = null; }
  if (!probe) return createStage(container, options).handle();
  const lose = probe.getExtension("WEBGL_lose_context");
  if (lose) lose.loseContext();
  if (!reduce) await settled(hero);
  const nightNow = () => {
    const set = document.documentElement.getAttribute("data-theme");
    return set ? set === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  };
  const onScreen = sheetEl ? sheetEl.getBoundingClientRect().width : container.clientWidth;
    /* the ink is printed at 2.6 texels per screen pixel of the sheet (at most 3072): seen at a slant, a texture
     loses detail across the slope, and at 1.35 the chart's lettering came out softer than level 3's */
  const inkWidth = Math.max(1536, Math.min(3072, Math.round((onScreen * Math.min(window.devicePixelRatio || 1, 2) * 2.6) / 256) * 256));
  const print = chartPrint(hero, { width: inkWidth });
  const firstTheme = nightNow() ? "night" : "day";
  const baseFirst = await print.base(firstTheme);
  const inkCanvas = await print.ink();
  const COLS = 221, ROWS = 232;
  const work = reliefRows(COLS, ROWS, { x0: X0, x1: X0 + CW });
  let step = work.next();
  while (!step.done) { await breath(); step = work.next(); }
  const { heights } = step.value;
  const shownH = new Float32Array(COLS * ROWS);
  let maxH = 0;
  for (let j = 0; j < ROWS; j++) {
    for (let i = 0; i < COLS; i++) {
      const k = j * COLS + i, x = (i / (COLS - 1)) * CW, y = (j / (ROWS - 1)) * CH;
      const edge = Math.min(x - 12.5, CW - 12.5 - x, y - 12.5, CH - 12.5 - y);
      const u = clamp01((edge - 4) / 150), f = u * u * (3 - 2 * u);   // the relief rises out of the paper: none at the neat line, all of it inside
      shownH[k] = shown(heights[k]) * f;
      maxH = Math.max(maxH, shownH[k]);
    }
  }
  await breath();
  /* per texel: the height shown, the bed in metres (the water reads it), the slope east and south */
  const half = new Uint16Array(COLS * ROWS * 4), dxW = SW / (COLS - 1), dzW = SD / (ROWS - 1);
  for (let j = 0; j < ROWS; j++) {
    for (let i = 0; i < COLS; i++) {
      const k = j * COLS + i, x = (i / (COLS - 1)) * CW, y = (j / (ROWS - 1)) * CH;
      const inside = x > 12.5 && x < CW - 12.5 && y > 12.5 && y < CH - 12.5;
      const e = shownH[j * COLS + Math.min(i + 1, COLS - 1)], w = shownH[j * COLS + Math.max(i - 1, 0)];
      const s = shownH[Math.min(j + 1, ROWS - 1) * COLS + i], n = shownH[Math.max(j - 1, 0) * COLS + i];
      half[k * 4] = THREE.DataUtils.toHalfFloat(shownH[k]);
      half[k * 4 + 1] = THREE.DataUtils.toHalfFloat(inside ? heights[k] : 99);   // outside the neat line: dry paper
      half[k * 4 + 2] = THREE.DataUtils.toHalfFloat((e - w) / (dxW * (Math.min(i + 1, COLS - 1) - Math.max(i - 1, 0))));
      half[k * 4 + 3] = THREE.DataUtils.toHalfFloat((s - n) / (dzW * (Math.min(j + 1, ROWS - 1) - Math.max(j - 1, 0))));
    }
    if (j % 58 === 57) await breath();
  }

  /* 2. the stage */
  const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 80);
  const stage = createStage(container, {
    fade: 450, stillTime: 6, pointerEase: 0.16, ...options, camera,
    tokens: { lamp: "--color-lamp", core: "--color-lamp-core", shoal: "--color-chart-shoal", surface2: "--color-surface", cut: "--l4-cut", back: "--l4-back", glowInk: "--l4-ink-glow" },
  });
  if (stage.failed) return stage.handle();
  const { renderer, scene } = stage;
  const aniso = Math.min(8, renderer.capabilities.getMaxAnisotropy());

  const canvasTexture = (canvas, srgb = true) => {
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    texture.flipY = false;
    texture.anisotropy = aniso;
    texture.minFilter = THREE.LinearMipmapLinearFilter;
    texture.generateMipmaps = true;
    return texture;
  };
  const bases = { [firstTheme]: canvasTexture(baseFirst) };
  const inkTexture = canvasTexture(inkCanvas);
  inkTexture.premultiplyAlpha = true;
  const heightTexture = new THREE.DataTexture(half, COLS, ROWS, THREE.RGBAFormat, THREE.HalfFloatType);
  heightTexture.minFilter = THREE.LinearFilter;
  heightTexture.magFilter = THREE.LinearFilter;
  heightTexture.wrapS = heightTexture.wrapT = THREE.ClampToEdgeWrapping;
  heightTexture.needsUpdate = true;

  /* the corner's hinge: from CURL units left of the top right corner to CURL units below it */
  const cornerA = toWorld(X0 + CW - CURL, 0), cornerB = toWorld(X0 + CW, CURL);
  const hingeMid = cornerA.clone().add(cornerB).multiplyScalar(0.5);
  const out = new THREE.Vector2(1, -1).normalize();                  // from the hinge out to the corner (x east, z south)
  const uniforms = {
    uBase: { value: bases[firstTheme] }, uBaseNight: { value: bases[firstTheme] }, uInk: { value: inkTexture },
    uHeight: { value: heightTexture }, uNight: { value: firstTheme === "night" ? 1 : 0 }, uRelief: { value: 0 },
    uFold: { value: 0.075 }, uLevel: { value: 1 }, uWater: { value: 0 }, uTime: { value: 6 },
    uMaxH: { value: maxH * VS + 0.03 }, uSteps: { value: 12 }, uRipples: { value: 2 },
    uLampPos: { value: new THREE.Vector3(0.6, LAMP_HEIGHT, 0.3) }, uLampColor: { value: new THREE.Color() },
    uLampPower: { value: 0.35 }, uPoolR: { value: 2.6 }, uPoolEdge: { value: 0.3 }, uRoom: { value: new THREE.Color() },
    uHill: { value: 0.6 }, uShoal: { value: new THREE.Color() }, uDeep: { value: new THREE.Color() }, uLine: { value: new THREE.Color() }, uGlint: { value: new THREE.Color() },
    uInkNight: { value: new THREE.Color() }, uInkGlow: { value: new THREE.Color() },
    uHinge: { value: new THREE.Vector4(hingeMid.x, hingeMid.z, out.x, out.y) }, uFlap: { value: 0 },
  };
  if (firstTheme === "day") uniforms.uBaseNight.value = bases.day; else uniforms.uBase.value = bases.night;
  const sheetMaterial = new THREE.ShaderMaterial({ uniforms, vertexShader: sheetVertex, fragmentShader: sheetFragment });
  const sheetGeometry = new THREE.PlaneGeometry(SW, SD, 172, 180).rotateX(-Math.PI / 2);
  const sheet = new THREE.Mesh(sheetGeometry, sheetMaterial);
  sheet.frustumCulled = false;
  scene.add(sheet);

  /* the turned-up corner: a curled flap on the hinge, its face printed, its back blank */
  const flapUniforms = {
    uBase: uniforms.uBase, uBaseNight: uniforms.uBaseNight, uInk: uniforms.uInk, uNight: uniforms.uNight,
    uLampPos: uniforms.uLampPos, uLampColor: uniforms.uLampColor, uLampPower: uniforms.uLampPower,
    uPoolR: uniforms.uPoolR, uPoolEdge: uniforms.uPoolEdge, uRoom: uniforms.uRoom, uBack: { value: new THREE.Color() },
  };
  const flapGeometry = new THREE.BufferGeometry();
  const ROWS_F = 7, span = (CURL / 100) / Math.SQRT2;
  const flapState = { turn: 0 };
  function bendFlap(turn) {
    /* a strip of rows parallel to the hinge, each turned a little more, so the corner curls */
    const pos = [], uv = [], index = [];
    const along = new THREE.Vector2(-out.y, out.x);
    for (let r = 0; r <= ROWS_F; r++) {
      const d = (r / ROWS_F) * span;                  // how far from the hinge, before the turn
      const halfW = span - d;                         // the triangle narrows to its tip
      let px = 0, py = 0;
      for (let q = 0; q < r; q++) {                   // walk out along the curl
        const a = turn * Math.min(1, (q + 0.5) / 1.6), seg = span / ROWS_F;   // the paper bends at the fold, then lies flat
        px += Math.cos(a) * seg; py += Math.sin(a) * seg;
      }
      for (const side of [-1, 1]) {
        const w = side * Math.max(halfW, 0.0001);
        const x = hingeMid.x + out.x * px + along.x * w, z = hingeMid.z + out.y * px + along.y * w;
        pos.push(x, py, z);
        const cx = hingeMid.x + out.x * d + along.x * w, cz = hingeMid.z + out.y * d + along.y * w;   // where it lay on the sheet
        uv.push(cx / SW + 0.5, cz / SD + 0.5);
      }
    }
    for (let r = 0; r < ROWS_F; r++) {
      const a = r * 2, b = a + 1, c = a + 2, d2 = a + 3;
      index.push(a, b, c, b, d2, c);
    }
    flapGeometry.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    flapGeometry.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
    flapGeometry.setIndex(index);
    flapGeometry.computeVertexNormals();
    flapState.turn = turn;
  }
  bendFlap(0);
  const flap = new THREE.Mesh(flapGeometry, new THREE.ShaderMaterial({ uniforms: flapUniforms, vertexShader: flapVertex, fragmentShader: flapFragment, side: THREE.DoubleSide }));
  flap.frustumCulled = false;
  flap.position.y = 0.002;
  scene.add(flap);

  /* the cut edge: the sheet's outline, the corner cut off, drawn down to the table */
  const THICK = 0.034;
  const outline = [toWorld(X0, 0), cornerA, cornerB, toWorld(X0 + CW, CH), toWorld(X0, CH)];
  const edgePos = [], edgeNormal = [];
  for (let i = 0; i < outline.length; i++) {
    const a = outline[i], b = outline[(i + 1) % outline.length];
    const nx = b.z - a.z, nz = -(b.x - a.x), len = Math.hypot(nx, nz) || 1;
    const quad = [[a.x, 0, a.z], [b.x, 0, b.z], [b.x, -THICK, b.z], [a.x, 0, a.z], [b.x, -THICK, b.z], [a.x, -THICK, a.z]];
    for (const v of quad) { edgePos.push(...v); edgeNormal.push(-nx / len, 0, -nz / len); }
  }
  const edgeGeometry = new THREE.BufferGeometry();
  edgeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(edgePos, 3));
  edgeGeometry.setAttribute("normal", new THREE.Float32BufferAttribute(edgeNormal, 3));
  const edgeUniforms = { uLampPos: uniforms.uLampPos, uLampColor: uniforms.uLampColor, uLampPower: uniforms.uLampPower, uPoolR: uniforms.uPoolR, uRoom: uniforms.uRoom, uCut: { value: new THREE.Color() } };
  const edgeMesh = new THREE.Mesh(edgeGeometry, new THREE.ShaderMaterial({ uniforms: edgeUniforms, vertexShader: plainVertex, fragmentShader: edgeFragment, side: THREE.DoubleSide }));
  scene.add(edgeMesh);
  sheet.position.y = 0;

  const tableUniforms = {
    uLampPos: uniforms.uLampPos, uPoolR: uniforms.uPoolR, uGlow: { value: new THREE.Color() }, uGlowA: { value: 0.4 },
    uShade: { value: new THREE.Color() }, uShadeA: { value: 0.3 },
  };
  const table = new THREE.Mesh(new THREE.PlaneGeometry(16, 16).rotateX(-Math.PI / 2),
    new THREE.ShaderMaterial({
      uniforms: tableUniforms, vertexShader: plainVertex, fragmentShader: tableFragment, depthWrite: false,
      /* drawn first, with the opaque things, and blended onto the page: the sheet always lies over it, also
         where its channels sink below the table's own height (as a transparent object it would be drawn last,
         over them, as a film) */
      transparent: false, blending: THREE.CustomBlending, blendEquation: THREE.AddEquation,
      blendSrc: THREE.SrcAlphaFactor, blendDst: THREE.OneMinusSrcAlphaFactor, blendSrcAlpha: THREE.OneFactor, blendDstAlpha: THREE.OneMinusSrcAlphaFactor,
    }));
  table.position.y = -THICK - 0.002;
  table.renderOrder = -1;
  scene.add(table);

  /* 3. light and colour from the page's tokens: the day lamp over paper, or the red lamp at night */
  let night = firstTheme === "night" ? 1 : 0, nightTarget = night, making = null, gone = false;
  stage.onDestroy(() => { gone = true; });
  function wantBase(theme) {
    if (bases[theme] || making) return;
    making = print.base(theme).then((canvas) => {
      making = null;
      if (gone) return;
      bases[theme] = canvasTexture(canvas);
      if (theme === "day") uniforms.uBase.value = bases.day; else uniforms.uBaseNight.value = bases.night;
      stage.invalidate();
    }).catch(() => { making = null; });
  }
  stage.onTokens((tokens) => {
    nightTarget = tokens.dark ? 1 : 0;
    wantBase(tokens.dark ? "night" : "day");
    if (tokens.dark) {
        /* the room at night: the red lamp's light thrown back by the cabin, enough to see the chart outside
           the pool as a dim red sheet (at 0.035 it was black, and the pool a hard disc in it) */
        uniforms.uRoom.value.copy(tokens.lamp).multiplyScalar(0.14);
      uniforms.uLampColor.value.copy(tokens.lamp);                 // the red lamp
      uniforms.uShoal.value.setRGB(0.3, 0.07, 0.04);
        uniforms.uDeep.value.setRGB(0.12, 0.02, 0.01);
      uniforms.uLine.value.copy(tokens.lamp).multiplyScalar(0.9);
      uniforms.uGlint.value.copy(tokens.lamp);
        /* the print at night is pale rose, as level 3's sheet has it: bright where the lamp lights the
           paper, a softer rose in the gloom, so every word reads anywhere on the sheet (dark ink on the red
           only read in the middle of the pool). Linear values: #ffd6c8 and #c98c7a */
        uniforms.uInkNight.value.setRGB(1.0, 0.67, 0.58);
        uniforms.uInkGlow.value.setRGB(0.58, 0.26, 0.19);
      uniforms.uHill.value = 0.15;
        uniforms.uPoolEdge.value = 0.2;               // the pool fades from near its middle: a lamp, not a disc
      flapUniforms.uBack.value.copy(tokens.back);
      edgeUniforms.uCut.value.copy(tokens.cut);
      tableUniforms.uGlow.value.copy(tokens.lamp);
      tableUniforms.uGlowA.value = 0.26;
      tableUniforms.uShade.value.setRGB(0, 0, 0);
      tableUniforms.uShadeA.value = 0.6;
    } else {
        /* the room beyond the lamp: a warm shade, a step darker than the pool, so by day the lamp is a pool of
           light you can see and its rake shades the relief (at 0.78 with a weak lamp it was a flat grey film) */
        uniforms.uRoom.value.setRGB(0.76, 0.7, 0.6);
        /* a warm bulb, yellower than paper, so its pool reads as lamplight and not as a pale haze */
        uniforms.uLampColor.value.copy(tokens.lamp).lerp(new THREE.Color(1, 0.74, 0.4), 0.85);
        /* the water by day: a sea-glass deeper than the printed shoal tint (#7fb5bf, linear below), so water lying
           over a bank reads as water, not as the pale tint it covers */
        uniforms.uShoal.value.setRGB(0.21, 0.46, 0.52);
        uniforms.uDeep.value.setRGB(0.05, 0.2, 0.26);   // #3e7a8a
      uniforms.uLine.value.setRGB(1, 0.99, 0.95);
      uniforms.uGlint.value.setRGB(1, 0.96, 0.86);
      uniforms.uInkNight.value.setRGB(0, 0, 0);
      uniforms.uInkGlow.value.setRGB(0, 0, 0);
      uniforms.uHill.value = 0.8;
      uniforms.uPoolEdge.value = 0.38;
      flapUniforms.uBack.value.copy(tokens.back);
      edgeUniforms.uCut.value.copy(tokens.cut);
      tableUniforms.uGlow.value.copy(tokens.lamp);
      tableUniforms.uGlowA.value = 0.42;
      tableUniforms.uShade.value.setRGB(0.19, 0.13, 0.04);
      tableUniforms.uShadeA.value = 0.34;
    }
    if (stage.still) night = nightTarget;
  });
  stage.onQuality((quality) => {
    uniforms.uSteps.value = quality.pick(6, 11, 15);
    uniforms.uRipples.value = quality.pick(1, 2, 2);
  });
  /* the other lamp's print, once the scene is up and the page is quiet */
  const quiet = window.requestIdleCallback || ((fn) => setTimeout(fn, 900));
  quiet(() => wantBase(firstTheme === "day" ? "night" : "day"), { timeout: 4000 });

  /* 4. the camera: the drawn chart's own view, turned a little by the pointer, lifted as the hero leaves */
  let pose = null;
  const look = { pos: new THREE.Vector3(), quat: new THREE.Quaternion() };
  const pivot = new THREE.Vector3(0.4, 0, 0.6);
  const qYaw = new THREE.Quaternion(), qPitch = new THREE.Quaternion(), axisY = new THREE.Vector3(0, 1, 0), right = new THREE.Vector3();
  function applyPose(yaw, pitch, back) {
    if (!pose) return;
    qYaw.setFromAxisAngle(axisY, yaw);
    right.set(1, 0, 0).applyQuaternion(pose.quat);
    qPitch.setFromAxisAngle(right, pitch);
    const q = qYaw.clone().multiply(qPitch);
    look.pos.copy(pose.pos).sub(pivot).multiplyScalar(1 + back).applyQuaternion(q).add(pivot);
    look.quat.copy(q).multiply(pose.quat);
    camera.position.copy(look.pos);
    camera.quaternion.copy(look.quat);
    camera.updateMatrixWorld();
    const n = camera.near;
    camera.projectionMatrix.makePerspective(pose.l * n, pose.r * n, pose.t * n, pose.b * n, n, camera.far);
    camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
  }
  stage.onResize(() => { pose = cssPose(container, sheetEl); });

  /* 5. the lamp on its cable */
  const restAt = toWorld(700, 470), bankAt = toWorld(820, 585);   // over the river; over the banks that dry
  const lamp = { x: restAt.x, z: restAt.z, vx: 0, vz: 0 };
  const ray = new THREE.Vector3();
  function pointerOnTable() {
    const p = stage.pointer;
    /* over the table, or over the words beside it (the lamp then leans to the sheet's west edge); anywhere else
       (the top bar, below the hero) it goes back to its place */
    const beside = !p.inside && p.raw.x <= -0.999 && Math.abs(p.raw.y) < 0.999;
    if (!p.active || !fine.matches || !(p.inside || beside)) return null;
    ray.set(p.raw.x, p.raw.y, 0.5).unproject(camera).sub(camera.position).normalize();
    if (ray.y > -0.02) return null;
    const t = -camera.position.y / ray.y;
    return { x: Math.max(-SW / 2 - 0.2, Math.min(SW / 2 + 0.2, camera.position.x + ray.x * t)), z: Math.max(-SD / 2 - 0.2, Math.min(SD / 2 + 0.2, camera.position.z + ray.z * t)) };
  }

  /* 6. the frame. The opening and the easing run on the clock of the wall, not on the stage's clock
     (which stands still while paused and takes at most a tenth of a second a frame), so a slow device
     sees the same moments, only fewer of them. */
  let settledAt = -99;   // when the opening ended (the wall clock), for the lean-in after it
  let level = 1.0, levelShown = level, progress = 0, opened = null, built = false, last = 0, flapTurn = 0, banks = 0;
  const view = { x: 0, y: 0 };
  const ease = (dt, seconds) => (dt ? 1 - Math.exp(-dt / seconds) : 1);
  const clockNow = () => ((document.timeline && document.timeline.currentTime != null) ? document.timeline.currentTime : performance.now()) / 1000;
  const gauge = toWorld(GAUGE[0], GAUGE[1]), gaugeOnScreen = new THREE.Vector3();
  let gaugeWas = "";
  /* 7. on demand: while nothing changes but the slow life of the water and the lamp's sway, the table draws
     a frame now and then instead of every frame, and wakes at once for the hand, the scroll, the hour or
     a theme. On a quick device "now and then" is 15 a second; on a slow one less, so the page stays free. */
  const userPauses = new Set();
  let activeUntil = 0, idle = false, idleTimer = 0, frameCost = 0.016;
  function wake(seconds = 2.6) {
    activeUntil = Math.max(activeUntil, clockNow() + seconds);
    if (!idle) return;
    idle = false;
    clearTimeout(idleTimer);
    stage.resume("idle");
  }
  function idleTick() {
    if (!idle) return;
    if (!userPauses.size) stage.invalidate();
    idleTimer = setTimeout(idleTick, Math.max(66, frameCost * 3000));
  }
  function goIdle() {
    if (idle || stage.still) return;
    idle = true;
    stage.pause("idle");
    idleTimer = setTimeout(idleTick, Math.max(66, frameCost * 3000));
  }
  stage.onDestroy(() => clearTimeout(idleTimer));
  stage.onPointer(() => wake());
  stage.onTokens(() => wake(1.5));
  stage.onResize(() => wake(1));

  stage.onFrame(() => {
    const now = clockNow();
    const live = !stage.still && (stage.running || idle) && !userPauses.size;
    const dt = live && last ? Math.min(now - last, 0.5) : 0;
    if (stage.running && last && now - last < 1) frameCost += (now - last - frameCost) * 0.1;
    last = live ? now : 0;
    if (opened === null) opened = live ? now : -99;
    const t = live && !built ? now - opened : 99;
    const kRelief = inOut(phase(t, 0.55, 1.75));
    const kWater = inOut(phase(t, 1.3, 2.3));
    const kCurl = inOut(phase(t, 0.35, 1.5));
    if (!built && t >= 2.3) {
      built = true;
        settledAt = live ? now : -99;
      container.dispatchEvent(new CustomEvent("tablebuilt"));
    }
    progress += (stage.progress - progress) * ease(dt, 0.22);
    const leave = progress;
      /* once the relief stands, the reader leans in: the camera comes down lower over the table and swings a
         little to the east, so the banks are seen from the side and show their height (straight from the
         drawn sheet's view the relief read as an emboss). The first frame still lies on the drawn sheet;
         this follows over 1.8 s, small enough that the sheet stays inside its canvas. A still frame (reduced motion) shows the leaned-in view at once. */
      const kLean = built ? (settledAt < 0 || !live ? 1 : inOut(phase(now - settledAt, 0, 1.8))) : 0;
    /* the pointer turns the view a little: the relief is seen from another side */
    const p = stage.pointer, follow = built && fine.matches && p.active;
    view.x += ((follow ? p.raw.x : 0) - view.x) * ease(dt, 0.6);
    view.y += ((follow ? p.raw.y : 0) - view.y) * ease(dt, 0.6);
      /* the pointer's turn is larger than before (0.085 and 0.05 rad read as hardly anything) */
      applyPose(-view.x * 0.1 - kLean * 0.035, view.y * 0.06 + kLean * 0.09 - leave * 0.12, leave * 0.18);

    uniforms.uRelief.value = kRelief * (1 - leave * 0.8);
    const turn = Math.PI - (Math.PI - CURL_TURN) * kCurl;   // from folded flat, as the drawn sheet has it, to lifted
    if (Math.abs(turn - flapTurn) > 0.002) { flapTurn = turn; bendFlap(turn); }
    uniforms.uFlap.value = kCurl;
    night += (nightTarget - night) * ease(dt, 0.15);
    uniforms.uNight.value = night;
    levelShown += (level - levelShown) * ease(dt, built ? 0.35 : 0.05);
    uniforms.uLevel.value = levelShown;
    uniforms.uWater.value = kWater;

    /* the lamp: to the hand, or to its place over the river (down the pencil line as the hero leaves);
       a lamp on a cable, so it swings after the hand and settles */
    const hand = built && !banks ? pointerOnTable() : null;
    let tx, tz;
    if (hand) { tx = hand.x; tz = hand.z; } else {
      const b = toWorld(524, 594), walk = Math.min(1, leave * 1.2);
      const home = banks ? bankAt : restAt, sway = banks ? 0.5 : 1;
      tx = home.x + (b.x - home.x) * walk + (live ? (Math.sin(now * 0.43) * 0.42 + Math.sin(now * 0.17) * 0.2) * sway : 0);
      tz = home.z + (b.z - home.z) * walk + (live ? (Math.cos(now * 0.37) * 0.26 + Math.sin(now * 0.23) * 0.12) * sway : 0);
    }
    if (!dt) { lamp.x = tx; lamp.z = tz; lamp.vx = lamp.vz = 0; } else {
      const w = 5.4, z = 0.6, steps = Math.ceil(dt / (1 / 60)), h = dt / steps;
      for (let i = 0; i < steps; i++) {
        lamp.vx += (w * w * (tx - lamp.x) - 2 * z * w * lamp.vx) * h;
        lamp.vz += (w * w * (tz - lamp.z) - 2 * z * w * lamp.vz) * h;
        lamp.x += lamp.vx * h;
        lamp.z += lamp.vz * h;
      }
    }
    uniforms.uLampPos.value.set(lamp.x, LAMP_HEIGHT, lamp.z);
      /* by night a wider, softer pool at less power: at 2.3 the red saturated into one flat colour */
      uniforms.uLampPower.value = night > 0.5 ? 1.7 : 0.36;
      uniforms.uPoolR.value = night > 0.5 ? 3.3 : 2.15;
    if (live) uniforms.uTime.value = now % 1000;
    if (built && !idle && stage.running && now > activeUntil && !hand && Math.abs(level - levelShown) < 0.004
      && Math.abs(stage.progress - progress) < 0.002 && Math.hypot(tx - lamp.x, tz - lamp.z) < 0.12) goIdle();

    /* where the tide gauge is on the screen, for the page's label of the hour */
    gaugeOnScreen.set(gauge.x, 0.012, gauge.z).project(camera);
    const gx = ((gaugeOnScreen.x + 1) / 2) * stage.size.width, gy = ((1 - gaugeOnScreen.y) / 2) * stage.size.height;
    const key = gx.toFixed(1) + " " + gy.toFixed(1);
    if (key !== gaugeWas) {
      gaugeWas = key;
      container.style.setProperty("--gauge-x", gx.toFixed(1) + "px");
      container.style.setProperty("--gauge-y", gy.toFixed(1) + "px");
    }
  });

  return stage.handle({
    setData(values) {
      const v = Array.isArray(values) ? Number(values[0]) : Number(values);
      if (!Number.isFinite(v)) return;
      const next = clamp01(v) * WATER_MAX, nextBanks = Array.isArray(values) && Number(values[1]) > 0 ? 1 : 0;
      if (next !== level || nextBanks !== banks) wake(1.8);
      level = next;
      banks = nextBanks;
      if (stage.still || userPauses.size) levelShown = level;
      stage.invalidate();
    },
    setProgress(p) {
      if (Math.abs(p - stage.progress) > 1e-4) wake(1.2);
      stage.setProgress(p);
      if (stage.still || userPauses.size) progress = stage.progress;
      if (userPauses.size) stage.invalidate();
    },
    pause(reason = "user") { userPauses.add(String(reason)); stage.pause(reason); },
    resume(reason = "user") { userPauses.delete(String(reason)); stage.resume(reason); wake(); },
  });
}
