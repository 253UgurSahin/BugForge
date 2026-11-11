/* Tidewatch, level 4: the chart table in three dimensions. The hero's one WebGL scene.

   The printed chart (the page's own SVG, made into a picture by print.js) lies on the chart table as a
   sheet, and the sea bed it was drawn from (seabed.js) lifts it into a relief: the land stands up, the
   drying banks stand a little proud of the paper, the channels sink. Over the relief:
   - a thin sheet of water at the height of the tide. Where the bed lies higher the bank is dry and shows
     its printed drying green; where the water covers it, it takes the shoal blue of shallow water, so
     Spijkerplaat and Hooge Platen surface and flood as the tide goes. The tint follows the depth of the
     water now, in two bands as a chart prints them, so the bands shift with the tide; a bright wet line
     marks where the water meets the bank;
   - the lamp. It hangs low over the table and follows the hand (a damped cable), a raking light: the
     slopes that face it brighten and catch its sheen, the banks and the dunes throw soft shadows away
     from it, and it glints on the water. Left alone it sways a little over the river, as a lamp aboard
     does, and walks down the pencil line as the hero leaves. At night it is the red lamp and the chart
     is only there where it shines;
   - the pencil course, its fixes and its notes, drawn on the water where the boat will float (on the
     paper where it is dry), so nothing is ever drawn over them.
   The opening: the scene takes over from the drawn chart in the very pose the page gave it (the
   perspective of level 3, read from the CSS), then the camera comes down to the table while the relief
   rises out of the print, and the water floods in to the height of the tide now. Scrolling away, the
   relief sinks back into the paper and the sheet slides back. The pointer moves the lamp and turns the
   view a little, so the relief is seen from another side.
   Built on the scene kit's stage.js (renderer, colours from the tokens, pointer, pausing, reduced motion
   as one still frame, quality steps, the no-WebGL fallback) and glsl.js (noise, dither). One
   ShaderMaterial for the sheet (the relief, its light and the water are one pass: the water is a plane,
   so where a ray meets it is a sum, not a second drawing), one for the table under it.

   mount(container, options) -> Promise of { stage, setData, setProgress, setPointer, pause, resume,
   destroy }. setData([level]): the water, 0..1 of 6 m above chart datum. setProgress(p): how far the
   hero has scrolled away, 0..1. When the opening is over the container gets the event "tablebuilt". */
import * as THREE from "three";
import { createStage } from "../../vendor/scenes/stage.js";
import { simplex2D, grain } from "../../vendor/scenes/glsl.js";
import { reliefGrid } from "./seabed.js";
import { chartPictures } from "./print.js";

const VS = 0.036;                 // world units (100 chart units each) per metre of height
const DEEP = 7;                   // metres: depths are softened past this, so channels stay channels
const RISE = 1.5;                 // the dry banks and the land stand a little prouder than the depths sink
const WATER_MAX = 6;              // metres: setData's 1
const LAMP_HEIGHT = 1.2;          // world units above the paper: low, so the light rakes
const clamp01 = (v) => Math.min(1, Math.max(0, v));
const phase = (t, a, b) => clamp01((t - a) / (b - a));
const inOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const out3 = (t) => 1 - Math.pow(1 - t, 3);
const soft = (h) => (h >= 0 ? RISE * (h > 4 ? 4 + (h - 4) * 0.35 : h) : -DEEP * Math.tanh(-h / DEEP));   // land: a low plateau
const toWorld = (x, y) => new THREE.Vector3(x / 100 - 5, 0, y / 100 - 4.5);

const vertexShader = /* glsl */ `
uniform sampler2D uHeight;
uniform float uVS;
uniform float uRelief;
varying vec2 vUv;
varying vec3 vPos;
void main() {
  vUv = uv;
  float h = texture2D(uHeight, uv).r;
  vec4 world = modelMatrix * vec4(position.x, h * uVS * uRelief, position.z, 1.0);
  vPos = world.xyz;
  gl_Position = projectionMatrix * viewMatrix * world;
}`;

const fragmentShader = /* glsl */ `
uniform sampler2D uMap;
uniform sampler2D uNightMap;
uniform sampler2D uPencil;
uniform sampler2D uHeight;
uniform float uNight;
uniform float uRelief;
uniform float uVS;
uniform float uLevel;
uniform float uWaterY;
uniform float uWater;
uniform float uTime;
uniform float uMaxH;
uniform vec3 uLampPos;
uniform vec3 uLampColor;
uniform float uLampPower;
uniform float uPoolR;
uniform vec3 uAmbient;
uniform float uHill;
uniform vec3 uInk;
uniform vec3 uTint;
uniform vec3 uShoal;
uniform vec3 uShoal2;
uniform vec3 uSheen;
uniform vec3 uWet;
uniform float uTintAmount;
uniform float uSheenAmount;
varying vec2 vUv;
varying vec3 vPos;
${simplex2D}
${grain}

vec2 toUv(vec2 xz) { return vec2((xz.x + 5.0) / 10.0, (xz.y + 4.5) / 9.0); }
float heightAt(vec2 uv) { return texture2D(uHeight, uv).r * uVS * uRelief; }

/* the slope is stored with the height (metres per world unit, east and south), so one read gives both */
vec3 normalAt(vec4 bed) {
  float k = uVS * uRelief;
  return normalize(vec3(-bed.b * k, 1.0, -bed.a * k));
}

/* soft shadows: walk from the point toward the lamp over the height field; the closest miss sets the
   penumbra. The start is jittered per pixel, so few steps give grain, not bands. */
float shadowAt(vec3 p, vec3 dir) {
  float s = 1.0;
  float stepLen = 1.9 / float(STEPS);
  float t = 0.015 + stepLen * fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
  for (int i = 0; i < STEPS; i++) {
    vec3 q = p + dir * t;
    if (q.y > uMaxH) break;
    vec2 uv = toUv(q.xz);
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) break;
    s = min(s, clamp(7.0 * (q.y - heightAt(uv)) / t, 0.0, 1.0));
    t += stepLen;
  }
  return s;
}

float poolAt(vec2 xz) {
  vec2 d = xz - uLampPos.xz;
  return exp(-dot(d, d) / (uPoolR * uPoolR));
}

void main() {
  vec3 P = vPos;
  vec2 uv = vUv;
  vec4 bed = texture2D(uHeight, uv);
  vec3 n = normalAt(bed);
  vec3 albedo = texture2D(uMap, uv).rgb;
  /* the night print is ink on a sheet that only the red lamp lights; its layers of ink are lifted a
     little, so the land reads as a darker print and not as a hole */
  if (uNight > 0.0) albedo = mix(albedo, pow(texture2D(uNightMap, uv).rgb, vec3(0.5)), uNight);

  /* the room: a soft light from the north-west, as a cartographer shades relief */
  vec3 sun = normalize(vec3(-0.55, 0.8, -0.45));
  float hill = clamp(dot(n, sun) / sun.y, 0.0, 2.2);
  float cavity = 1.0 - 0.03 * clamp(-bed.r / 7.0, 0.0, 1.0) * uRelief;
  /* the lamp */
  vec3 toLamp = uLampPos - P;
  vec3 L = normalize(toLamp);
  float pool = poolAt(P.xz);
  float face = max(dot(n, L), 0.0) / max(L.y, 0.12);
  float sh = pool > 0.01 ? shadowAt(P + n * 0.003, L) : 1.0;
  vec3 light = uAmbient * mix(1.0, hill, uHill) * cavity + uLampColor * uLampPower * pool * face * sh;
  vec3 col = albedo * light;
  /* paper has a little sheen: a broad glare where the lamp is seen in it, caught on every slope that
     faces it, so the hand's light runs over the relief */
  vec3 Vp = normalize(cameraPosition - P);
  float sheen = pow(max(dot(n, normalize(L + Vp)), 0.0), 18.0) * pool * sh;
  col += uLampColor * uLampPower * sheen * uSheenAmount;

  /* the water: a plane at the height of the tide, met by the ray from the eye on its way to the bed */
  float depth = uLevel - bed.g;                         // metres of water over this point now
  float aw = fwidth(depth) + 0.002;
  float wet = smoothstep(-aw, aw, depth);
  vec3 V = cameraPosition - P;
  float reach = clamp((uWaterY - P.y) / max(V.y, 1e-4), 0.0, 1.0);
  vec3 Q = P + V * reach * step(0.0, depth);
  vec2 quv = toUv(Q.xz);
  float shown = wet * uWater;
  if (shown > 0.0) {
    vec3 g = snoiseGrad(Q.xz * vec2(2.2, 3.4) + vec2(uTime * 0.05, -uTime * 0.035)) * 0.75;
#if RIPPLES > 1
    g += snoiseGrad(Q.xz * vec2(5.5, 8.0) + vec2(-uTime * 0.09, uTime * 0.07)) * 0.25;
#endif
    vec3 wn = normalize(vec3(-g.y * 0.012, 1.0, -g.z * 0.012));
    vec3 Vq = normalize(cameraPosition - Q);
    vec3 Lq = normalize(uLampPos - Q);
    float fres = pow(1.0 - clamp(dot(wn, Vq), 0.0, 1.0), 5.0);
    float hv = clamp(dot(wn, normalize(Lq + Vq)), 0.0, 1.0);
    float glint = (pow(hv, 320.0) * 3.2 + pow(hv, 60.0) * 0.55 + pow(hv, 14.0) * 0.12) * poolAt(Q.xz) * mix(0.3, 1.0, sh);
    /* the depth bands of the water now, as a chart tints its depths: under 2 m the shoal blue, under 5 m
       the paler blue, deeper water stays clear. They follow the tide, so a bank that dries goes back
       to its printed green, and one that floods turns blue */
    float shoal = 1.0 - smoothstep(1.5, 2.5, depth);
    float pale = 1.0 - smoothstep(4.3, 5.7, depth);
    vec3 lit = uAmbient + uLampColor * uLampPower * poolAt(Q.xz) * 0.5;
    vec3 band = mix(uTint, mix(uShoal2, uShoal, shoal), pale);
    float a = uTintAmount * mix(0.10, mix(0.34, 0.5, shoal), pale) * (1.0 - 0.72 * uNight);   // at night the bands are dim ink
    vec3 water = mix(col, band * mix(lit, vec3(1.0), 0.55), a);
    water += uSheen * fres * 0.5 + uLampColor * uLampPower * glint;
    float lap = 0.5 + 0.5 * sin(uTime * 0.9 + g.x * 4.0);          // the water laps at the bank
    float edge = 1.0 - smoothstep(0.0, 0.04 + 0.07 * lap + 1.5 * aw, depth);
    water = mix(water, uWet * lit, edge * 0.7);
    col = mix(col, water, shown);
  }

  /* the pencil, on whatever lies on top: the water where the course is afloat, the paper where it is dry */
  float cov = mix(texture2D(uPencil, uv).r, texture2D(uPencil, quv).r, step(0.0, depth) * smoothstep(0.0, 1.0, uWater));
  col = mix(col, uInk * mix(vec3(1.0), light, 0.3), clamp(cov * 1.6, 0.0, 0.95));

  gl_FragColor = vec4(col, 1.0);
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy);
}`;

/* the table round the sheet: the lamp's pool on it, and the soft shadow of the sheet */
const tableVertex = /* glsl */ `
varying vec3 vPos;
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vPos = world.xyz;
  gl_Position = projectionMatrix * viewMatrix * world;
}`;
const tableFragment = /* glsl */ `
uniform vec3 uLampPos;
uniform float uPoolR;
uniform vec3 uGlow;
uniform float uGlowA;
uniform vec3 uShade;
uniform float uShadeA;
uniform float uDim;
uniform vec2 uResolution;
varying vec3 vPos;
${grain}
void main() {
  vec2 d = vPos.xz - uLampPos.xz;
  float near = exp(-dot(d, d) / (uPoolR * uPoolR * 2.4));
  vec2 sp = gl_FragCoord.xy / uResolution;
  float inside = smoothstep(0.0, 0.14, sp.x) * smoothstep(0.0, 0.14, 1.0 - sp.x) * smoothstep(0.0, 0.14, sp.y) * smoothstep(0.0, 0.14, 1.0 - sp.y);
  float glow = near * uGlowA;
  vec2 q = abs(vPos.xz + uLampPos.xz * 0.018) - vec2(5.0, 4.5);   // pushed away from the lamp
  float box = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0);
  float shade = max((1.0 - smoothstep(-0.05, 0.42, box)) * uShadeA, (1.0 - near) * uDim * inside);   // the sheet's shadow, the room beyond the lamp
  float alpha = 1.0 - (1.0 - glow) * (1.0 - shade);
  vec3 col = mix(uGlow, uShade, shade / max(glow + shade, 1e-4));
  gl_FragColor = vec4(col, alpha);
  #include <colorspace_fragment>
  gl_FragColor.rgb += dither(gl_FragCoord.xy);
}`;

/* wait until the drawn chart's own opening is over, so the scene takes over from a sheet at rest */
function settled(hero, cap = 3200) {
  const running = typeof document.getAnimations === "function"
    ? document.getAnimations().filter((a) => {
      const target = a.effect && a.effect.target;
      return target && hero.contains(target) && a.playState === "running" && a.effect.getTiming().iterations !== Infinity;
    })
    : [];
  const line = () => (document.timeline && document.timeline.currentTime != null ? document.timeline.currentTime : performance.now());
  const until = line() + cap;
  const capped = new Promise((resolve) => {
    const check = () => (line() >= until ? resolve() : setTimeout(check, 100));
    setTimeout(check, 100);
  });
  return Promise.race([Promise.all(running.map((a) => a.finished.catch(() => null))), capped]);
}

/* the camera of the drawn chart: level 3's CSS perspective, turned into a camera over the sheet */
function posterPose(container, sheet, plate) {
  if (!sheet || !plate) return null;
  const cs = getComputedStyle(container);
  const P = parseFloat(cs.perspective);
  const W = container.clientWidth, H = container.clientHeight;
  if (!P || !W || !H) return null;
  const [ox, oy] = cs.perspectiveOrigin.split(" ").map(parseFloat);
  const ss = getComputedStyle(sheet);
  const [tx, ty] = ss.transformOrigin.split(" ").map(parseFloat);
  let M;
  try { M = new DOMMatrix(ss.transform === "none" ? undefined : ss.transform); } catch (error) { return null; }
  const A = new DOMMatrix().translate(sheet.offsetLeft + tx, sheet.offsetTop + ty).multiply(M).translate(-tx, -ty);
  const inv = A.inverse();
  const ps = getComputedStyle(plate);
  const bw = parseFloat(ps.width) || sheet.offsetWidth, bh = parseFloat(ps.height) || sheet.offsetHeight;
  const sw = sheet.offsetWidth, sh = sheet.offsetHeight;
  const bx = sw - bw, by = sh - bh, s = Math.max(bw / 1000, bh / 900);
  /* sheet px -> chart units -> world */
  const world = (u, v, w) => new THREE.Vector3((1000 - (bx + bw - u) / s) / 100 - 5, w / s / 100, (900 - (by + bh - v) / s) / 100 - 4.5);
  const dir = (d) => new THREE.Vector3(d.x, d.z, d.y).normalize();
  const c = inv.transformPoint(new DOMPoint(ox, oy, P, 1));
  const f = inv.transformPoint(new DOMPoint(0, 0, -1, 0));
  const up = inv.transformPoint(new DOMPoint(0, -1, 0, 0));
  const pos = world(c.x, c.y, c.z);
  const m = new THREE.Matrix4().lookAt(pos, pos.clone().add(dir(f)), dir(up));
  return { pos, quat: new THREE.Quaternion().setFromRotationMatrix(m), l: -ox / P, r: (W - ox) / P, t: oy / P, b: -(H - oy) / P };
}

function lookPose(target, azimuth, elevation, distance, fov, aspect, cx, cy) {
  const a = (azimuth * Math.PI) / 180, e = (elevation * Math.PI) / 180;
  const pos = target.clone().add(new THREE.Vector3(Math.sin(a) * Math.cos(e), Math.sin(e), Math.cos(a) * Math.cos(e)).multiplyScalar(distance));
  const m = new THREE.Matrix4().lookAt(pos, target, new THREE.Vector3(0, 1, 0));
  const t = Math.tan((fov * Math.PI) / 360), r = t * aspect;
  return { pos, quat: new THREE.Quaternion().setFromRotationMatrix(m), l: -r * (1 + cx), r: r * (1 - cx), t: t * (1 - cy), b: -t * (1 + cy) };
}

function blendPose(a, b, k, into) {
  into.pos.lerpVectors(a.pos, b.pos, k);
  into.quat.slerpQuaternions(a.quat, b.quat, k);
  for (const key of ["l", "r", "t", "b"]) into[key] = a[key] + (b[key] - a[key]) * k;
  return into;
}

export async function mount(container, options = {}) {
  const hero = container.closest(".hero") || document.body;
  const sheetEl = container.querySelector(".sheet");
  const plateEl = container.querySelector(".plate--land");
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches || options.still;
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const fine = window.matchMedia("(hover: hover) and (pointer: fine)");

  /* 1. what the scene is made of: the print and the sea bed. The drawn chart shows meanwhile. Without
     WebGL 2 none of it is made: the stage below says "fallback" at once and the drawn chart stays. */
  let probe = null;
  try { probe = document.createElement("canvas").getContext("webgl2"); } catch (error) { probe = null; }
  if (!probe) return createStage(container, options).handle();
  const lose = probe.getExtension("WEBGL_lose_context");
  if (lose) lose.loseContext();
  if (!reduce) await settled(hero);
  const pictures = chartPictures(hero, { width: coarse ? 1536 : 2048 });
  const nightNow = () => {
    const set = document.documentElement.getAttribute("data-theme");
    return set ? set === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  };
  const firstTheme = nightNow() ? "night" : "day";
  const [firstMap, pencil] = await Promise.all([pictures.draw(firstTheme), pictures.pencil()]);
  const COLS = 257, ROWS = 232;
  const { heights } = reliefGrid(COLS, ROWS);
  const shown = new Float32Array(COLS * ROWS);
  let maxH = 0;
  for (let j = 0; j < ROWS; j++) {
    for (let i = 0; i < COLS; i++) {
      const k = j * COLS + i, x = (i / (COLS - 1)) * 1000, y = (j / (ROWS - 1)) * 900;
      const edge = Math.min(x, 987.5 - x, y, 887.5 - y);
      const u = Math.min(1, Math.max(0, edge / 70)), f = u * u * (3 - 2 * u);   // the relief comes down to the paper at the edges
      shown[k] = soft(heights[k]) * f;
      maxH = Math.max(maxH, shown[k]);
    }
  }
  /* per texel: the height shown, the bed in metres (the water reads it), and the slope east and south */
  const half = new Uint16Array(COLS * ROWS * 4), dx = 10 / (COLS - 1), dz = 9 / (ROWS - 1);
  for (let j = 0; j < ROWS; j++) {
    for (let i = 0; i < COLS; i++) {
      const k = j * COLS + i, x = (i / (COLS - 1)) * 1000, y = (j / (ROWS - 1)) * 900;
      const edge = Math.min(x, 987.5 - x, y, 887.5 - y);
      const e = shown[j * COLS + Math.min(i + 1, COLS - 1)], w = shown[j * COLS + Math.max(i - 1, 0)];
      const s = shown[Math.min(j + 1, ROWS - 1) * COLS + i], n = shown[Math.max(j - 1, 0) * COLS + i];
      half[k * 4] = THREE.DataUtils.toHalfFloat(shown[k]);
      half[k * 4 + 1] = THREE.DataUtils.toHalfFloat(edge <= 0 ? 99 : heights[k]);   // outside the neat line: dry paper
      half[k * 4 + 2] = THREE.DataUtils.toHalfFloat((e - w) / (dx * (Math.min(i + 1, COLS - 1) - Math.max(i - 1, 0))));
      half[k * 4 + 3] = THREE.DataUtils.toHalfFloat((s - n) / (dz * (Math.min(j + 1, ROWS - 1) - Math.max(j - 1, 0))));
    }
  }

  /* 2. the stage */
  const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 80);
  const stage = createStage(container, {
    fade: 520, stillTime: 6, pointerEase: 0.16, ...options, camera,
    tokens: { lamp: "--color-lamp", core: "--color-lamp-core", pencil: "--color-chart-pencil", shade: "--color-relief", shoal: "--color-chart-shoal", shoal2: "--color-chart-shoal-2", deep: "--color-water" },
  });
  if (stage.failed) return stage.handle();
  const { renderer, scene } = stage;
  const aniso = Math.min(8, renderer.capabilities.getMaxAnisotropy());

  const mapTexture = (canvas) => {
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.flipY = false;
    texture.anisotropy = aniso;
    texture.minFilter = THREE.LinearMipmapLinearFilter;
    texture.generateMipmaps = true;
    return texture;
  };
  const maps = { [firstTheme]: mapTexture(firstMap) };
  const pencilTexture = new THREE.DataTexture(pencil, pictures.width, pictures.height, THREE.RedFormat, THREE.UnsignedByteType);
  pencilTexture.minFilter = THREE.LinearMipmapLinearFilter;
  pencilTexture.magFilter = THREE.LinearFilter;
  pencilTexture.generateMipmaps = true;
  pencilTexture.anisotropy = aniso;
  pencilTexture.needsUpdate = true;
  const heightTexture = new THREE.DataTexture(half, COLS, ROWS, THREE.RGBAFormat, THREE.HalfFloatType);
  heightTexture.minFilter = THREE.LinearFilter;
  heightTexture.magFilter = THREE.LinearFilter;
  heightTexture.wrapS = heightTexture.wrapT = THREE.ClampToEdgeWrapping;
  heightTexture.needsUpdate = true;

  /* the sheet: a grid over the chart, x east and z south, raised by the vertex shader */
  function sheetGeometry(cols, rows) {
    const geometry = new THREE.PlaneGeometry(10, 9, cols - 1, rows - 1);
    geometry.rotateX(-Math.PI / 2);                      // lies on the table; plane uv v runs north to south after this
    const uv = geometry.attributes.uv;
    for (let i = 0; i < uv.count; i++) uv.setY(i, 1 - uv.getY(i));   // v = 0 at the north edge, as the pictures
    return geometry;
  }
  const uniforms = {
    uMap: { value: maps[firstTheme] }, uNightMap: { value: maps[firstTheme] }, uPencil: { value: pencilTexture },
    uHeight: { value: heightTexture },
    uNight: { value: firstTheme === "night" ? 1 : 0 }, uRelief: { value: 0 }, uVS: { value: VS },
    uLevel: { value: 1 }, uWaterY: { value: 0 }, uWater: { value: 0 }, uTime: { value: 6 },
    uMaxH: { value: maxH * VS + 0.02 }, uLampPos: { value: new THREE.Vector3(0.5, LAMP_HEIGHT, 0.4) },
    uLampColor: { value: new THREE.Color() }, uLampPower: { value: 0.3 }, uPoolR: { value: 2.2 },
    uAmbient: { value: new THREE.Color() }, uHill: { value: 0.5 }, uInk: { value: new THREE.Color() },
    uTint: { value: new THREE.Color() }, uShoal: { value: new THREE.Color() }, uShoal2: { value: new THREE.Color() },
    uSheen: { value: new THREE.Color() }, uWet: { value: new THREE.Color() },
    uTintAmount: { value: 1 }, uSheenAmount: { value: 0.16 },
  };
  if (firstTheme === "day") uniforms.uNightMap.value = maps.day; else uniforms.uMap.value = maps.night;
  const material = new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader, defines: { STEPS: 12, RIPPLES: 2 } });
  const sheet = new THREE.Mesh(sheetGeometry(COLS, ROWS), material);
  sheet.frustumCulled = false;
  scene.add(sheet);

  const tableUniforms = {
    uLampPos: uniforms.uLampPos, uPoolR: uniforms.uPoolR, uGlow: { value: new THREE.Color() }, uGlowA: { value: 0.5 },
    uShade: { value: new THREE.Color() }, uShadeA: { value: 0.25 }, uDim: { value: 0.1 }, uResolution: stage.uniforms.uResolution,
  };
  const table = new THREE.Mesh(new THREE.PlaneGeometry(40, 40).rotateX(-Math.PI / 2),
    new THREE.ShaderMaterial({ uniforms: tableUniforms, vertexShader: tableVertex, fragmentShader: tableFragment, transparent: true, depthWrite: false }));
  table.position.y = -0.004;
  table.renderOrder = -1;
  scene.add(table);

  /* 3. light and colour from the page's tokens: the day lamp over paper, or the red lamp at night */
  let night = firstTheme === "night" ? 1 : 0, nightTarget = night, making = null, gone = false;
  stage.onDestroy(() => { gone = true; });
  function wantMap(theme) {
    if (maps[theme] || making) return;
    making = pictures.draw(theme).then((canvas) => {
      making = null;
      if (gone) return;
      maps[theme] = mapTexture(canvas);
      if (theme === "day") uniforms.uMap.value = maps.day; else uniforms.uNightMap.value = maps.night;
      stage.invalidate();
    }).catch(() => { making = null; });
  }
  stage.onTokens((tokens) => {
    nightTarget = tokens.dark ? 1 : 0;
    wantMap(tokens.dark ? "night" : "day");
    if (tokens.dark) {
      uniforms.uAmbient.value.copy(tokens.lamp).multiplyScalar(0.16);
      uniforms.uLampColor.value.copy(tokens.core);                     // the red lamp's hot core
      uniforms.uInk.value.copy(tokens.pencil);
      uniforms.uTint.value.setRGB(0.004, 0.0012, 0.001);
      uniforms.uShoal.value.setRGB(0.012, 0.003, 0.002);
      uniforms.uShoal2.value.setRGB(0.02, 0.006, 0.004);
      uniforms.uSheen.value.copy(tokens.lamp).multiplyScalar(0.25);
      uniforms.uWet.value.copy(tokens.accent);
      uniforms.uHill.value = 0.2;
      uniforms.uSheenAmount.value = 0.22;
      tableUniforms.uGlow.value.copy(tokens.lamp);
      tableUniforms.uGlowA.value = 0.5;
      tableUniforms.uShade.value.setRGB(0, 0, 0);
      tableUniforms.uShadeA.value = 0.55;
      tableUniforms.uDim.value = 0.0;
    } else {
      uniforms.uAmbient.value.setRGB(0.80, 0.785, 0.76);
      uniforms.uLampColor.value.copy(tokens.lamp).multiply(new THREE.Color(1.0, 0.86, 0.62));   // a warm bulb
      uniforms.uInk.value.copy(tokens.pencil).multiplyScalar(0.7);
      uniforms.uTint.value.copy(tokens.deep);
      uniforms.uShoal.value.copy(tokens.shoal);
      uniforms.uShoal2.value.copy(tokens.shoal2);
      uniforms.uSheen.value.setRGB(0.9, 0.92, 0.9);
      uniforms.uWet.value.setRGB(1.0, 0.99, 0.96);
      uniforms.uHill.value = 0.75;
      uniforms.uSheenAmount.value = 0.16;
      tableUniforms.uGlow.value.copy(tokens.lamp);
      tableUniforms.uGlowA.value = 0.55;
      tableUniforms.uShade.value.copy(tokens.shade);
      tableUniforms.uShadeA.value = 0.3;
      tableUniforms.uDim.value = 0.1;
    }
    if (stage.still) night = nightTarget;
  });
  stage.onQuality((quality) => {
    material.defines.STEPS = quality.pick(7, 12, 16);
    material.defines.RIPPLES = quality.pick(1, 2, 2);
    material.needsUpdate = true;
  });
  /* the second print, for the other lamp, once the scene is up and the page is quiet */
  const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 900));
  idle(() => wantMap(firstTheme === "day" ? "night" : "day"));

  /* 4. the camera: from the drawn chart's pose down to the table, and with the pointer and the scroll */
  const narrowQuery = window.matchMedia("(max-width: 60rem)");
  let poster = null;
  const pose = { pos: new THREE.Vector3(), quat: new THREE.Quaternion(), l: -1, r: 1, t: 1, b: -1 };
  function restPose(px, py, leave) {
    const narrow = narrowQuery.matches, aspect = stage.size.aspect || 1;
    if (narrow) {
      /* a phone: the chart shows under the words, so the view is composed for that band: Vlissingen,
         the pier and the pencil line out of it, Spijkerplaat to the east */
      return lookPose(toWorld(650, 470), -6 + px * 2.2, 46 - leave * 9 + py * 1.2, 14 * (1 + leave * 0.2), 30, aspect, 0.0, -0.6);
    }
    /* a narrower chart area (a small laptop) steps back and looks further east, so the neat line, the
       banks and the title stay in view; the west lies under the words anyway */
    const narrower = Math.min(1, Math.max(0, (0.946 - aspect) / 0.346));
    return lookPose(toWorld(600 + 90 * narrower, 480), 6 + px * 2.6, 44 - leave * 10 + py * 1.4,
      (15.5 + 3.5 * narrower) * (1 + leave * 0.2), 30, aspect, -0.2, 0.15);
  }
  function applyPose(p) {
    camera.position.copy(p.pos);
    camera.quaternion.copy(p.quat);
    camera.updateMatrixWorld();
    const n = camera.near;
    camera.projectionMatrix.makePerspective(p.l * n, p.r * n, p.t * n, p.b * n, n, camera.far);
    camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
  }
  stage.onResize(() => { poster = posterPose(container, sheetEl, plateEl); });

  /* 5. the lamp on its cable */
  const lamp = { x: toWorld(560, 410).x, z: toWorld(560, 410).z, vx: 0, vz: 0 };
  const ray = new THREE.Vector3();
  function pointerOnTable() {
    const p = stage.pointer;
    if (!p.active || !p.inside || !fine.matches || p.raw.x < -0.62) return null;
    ray.set(p.raw.x, p.raw.y, 0.5).unproject(camera).sub(camera.position).normalize();
    if (ray.y > -0.02) return null;
    const t = -camera.position.y / ray.y;
    return { x: Math.max(-5.6, Math.min(5.6, camera.position.x + ray.x * t)), z: Math.max(-5, Math.min(5, camera.position.z + ray.z * t)) };
  }

  /* 6. the frame. The opening and the easing run on the clock of the wall, not on the stage's clock
     (which stands still while paused and takes at most a tenth of a second a frame), so a slow device
     sees the same moments, only fewer of them. */
  let level = 1.03, levelShown = level, progress = 0, opened = null, built = false, last = 0;
  const view = { x: 0, y: 0 };
  const ease = (dt, seconds) => (dt ? 1 - Math.exp(-dt / seconds) : 1);
  /* the document's own timeline: the wall clock, unless the animations of the page are slowed down
     (DevTools), and then the opening slows with them */
  const clockNow = () => ((document.timeline && document.timeline.currentTime != null) ? document.timeline.currentTime : performance.now()) / 1000;
  stage.onFrame(() => {
    const now = clockNow();
    const live = stage.running && !stage.still;
    const dt = live && last ? Math.min(now - last, 0.5) : 0;
    last = live ? now : 0;
    if (opened === null) opened = live ? now : -99;
    const t = live && !built ? now - opened : 99;
    const kCam = inOut(phase(t, 0.12, 1.95));
    const kRelief = inOut(phase(t, 0.2, 1.8));
    const kWater = out3(phase(t, 1.25, 2.8));
    const kLamp = inOut(phase(t, 0.1, 1.3));
    if (!built && t >= 2.8) {
      built = true;
      container.dispatchEvent(new CustomEvent("tablebuilt"));
    }
    /* the scroll: the relief sinks back into the paper and the sheet slides back */
    progress += (stage.progress - progress) * ease(dt, 0.22);
    const leave = progress;
    /* the pointer turns the view a little */
    const p = stage.pointer, follow = built && fine.matches && p.active && p.inside;
    view.x += ((follow ? p.raw.x : 0) - view.x) * ease(dt, 0.7);
    view.y += ((follow ? p.raw.y : 0) - view.y) * ease(dt, 0.7);
    const rest = restPose(view.x, view.y, leave);
    if (poster && kCam < 1) blendPose(poster, rest, kCam, pose); else blendPose(rest, rest, 0, pose);
    applyPose(pose);

    uniforms.uRelief.value = kRelief * (1 - leave * 0.75);
    night += (nightTarget - night) * ease(dt, 0.12);
    uniforms.uNight.value = night;
    /* the water floods in to the height of the tide, then follows it */
    const target = built || !live ? level : level - 1.6 * (1 - kWater);
    levelShown += (target - levelShown) * ease(dt, built ? 0.45 : 0.06);
    uniforms.uLevel.value = levelShown;
    uniforms.uWaterY.value = soft(levelShown) * VS * uniforms.uRelief.value + 0.0005;
    uniforms.uWater.value = kWater;

    /* the lamp: to the hand, or to its place over the river (down the pencil line as the hero leaves);
       a lamp on a cable, so it swings after the hand and settles */
    const hand = built ? pointerOnTable() : null;
    let tx, tz;
    if (hand) { tx = hand.x; tz = hand.z; } else {
      const a = toWorld(560, 410), b = toWorld(524, 594), walk = Math.min(1, leave * 1.2);
      /* a lamp aboard sways on its cable, slowly, never twice the same way */
      tx = a.x + (b.x - a.x) * walk + (live ? Math.sin(now * 0.71) * 0.26 + Math.sin(now * 0.29) * 0.14 : 0);
      tz = a.z + (b.z - a.z) * walk + (live ? Math.cos(now * 0.53) * 0.17 + Math.sin(now * 0.37) * 0.06 : 0);
    }
    if (!dt) { lamp.x = tx; lamp.z = tz; lamp.vx = lamp.vz = 0; } else {
      const w = 5.2, z = 0.62, steps = Math.ceil(dt / (1 / 60)), h = dt / steps;
      for (let i = 0; i < steps; i++) {
        lamp.vx += (w * w * (tx - lamp.x) - 2 * z * w * lamp.vx) * h;
        lamp.vz += (w * w * (tz - lamp.z) - 2 * z * w * lamp.vz) * h;
        lamp.x += lamp.vx * h;
        lamp.z += lamp.vz * h;
      }
    }
    uniforms.uLampPos.value.set(lamp.x, LAMP_HEIGHT, lamp.z);
    uniforms.uLampPower.value = (night > 0.5 ? 1.5 : 0.66) * (0.55 + 0.45 * kLamp);
    uniforms.uPoolR.value = night > 0.5 ? 2.1 : 1.4;
    if (live) uniforms.uTime.value = now % 1000;
  });

  return stage.handle({
    setData(values) {
      const v = Array.isArray(values) ? Number(values[0]) : Number(values);
      if (!Number.isFinite(v)) return;
      level = clamp01(v) * WATER_MAX;
      if (stage.still) levelShown = level;
      stage.invalidate();
    },
    setProgress(p) {
      stage.setProgress(p);
      if (stage.still) progress = stage.progress;
    },
  });
}
