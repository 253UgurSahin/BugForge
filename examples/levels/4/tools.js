/* Tidewatch, level 4: the instruments on the chart table, a pencil and a pair of dividers.

   Every judge of the gallery asked for the same thing: a chart table is not only a chart, it has the
   instruments of the one who plans on it. So on level 4's sheet lie a pencil (on Walcheren, north of the
   course) and a pair of dividers (standing on the Hooge Platen, a mile and a bit between their points),
   lit by the sheet's own lamp and room, and throwing shadows on the paper.

   - The shadows: each instrument is a few capsules (a segment with a radius). For a point on the paper
     each capsule is projected from the lamp onto the paper's height; the point lies in its shadow by its
     distance to the projected segment, with an edge that softens the higher the part stands (the raised
     hinge throws a soft shadow, the pencil lying on the paper a sharp one). toolGLSL is that function, for
     the sheet's shader; no shadow map, a handful of segments.
   - The relief of level 4 rises in the opening and sinks as the hero leaves (uRelief), so the instruments
     are laid on it again every frame (place(relief)): they always rest on the paper, never float or sink.
   - They come in once the sheet is built (shown 0..1), their shadows with them.

   makeTools({ scene, toWorld, surface, uniforms }) -> { uniforms (for the sheet's shader), place(relief, shown) }
   surface(x, y): the relief's full height (world units) at a chart point, before uRelief scales it. */
import * as THREE from "three";

export const TOOLS = 4;

/* the shadow function: needs uLampPos (the sheet's shader has it) */
export const toolGLSL = /* glsl */ `
uniform vec4 uToolA[${TOOLS}];   // xyz: one end (world), w: radius
uniform vec4 uToolB[${TOOLS}];   // xyz: the other end, w: 1 if in use
uniform float uToolsOn;
float toolShade(vec3 P) {
    float lit = 1.0;
    if (uToolsOn < 0.002) return lit;
    for (int i = 0; i < ${TOOLS}; i++) {
        if (uToolB[i].w < 0.5) continue;
        vec3 a = uToolA[i].xyz, b = uToolB[i].xyz;
        float ka = (uLampPos.y - P.y) / max(uLampPos.y - a.y, 0.05);
        float kb = (uLampPos.y - P.y) / max(uLampPos.y - b.y, 0.05);
        vec2 pa = uLampPos.xz + (a.xz - uLampPos.xz) * ka, pb = uLampPos.xz + (b.xz - uLampPos.xz) * kb;
        vec2 ab = pb - pa;
        float t = clamp(dot(P.xz - pa, ab) / max(dot(ab, ab), 1e-5), 0.0, 1.0);
        float d = length(P.xz - pa - ab * t);
        float height = max(mix(a.y, b.y, t) - P.y, 0.0);
        float pen = 0.004 + height * 0.2;
        float rs = uToolA[i].w * mix(ka, kb, t);
        lit = min(lit, mix(1.0, 0.45, (1.0 - smoothstep(rs - pen, rs + pen, d)) * step(0.0, height - 0.001)));
    }
    return mix(1.0, lit, uToolsOn);
}
`;

/* the instruments' own material: the sheet's room light and lamp (by night both are the red lamp's, as
   level 4's tokens set them), a highlight on the steel and on the lacquer */
const vertex = /* glsl */ `
varying vec3 vN;
varying vec3 vW;
void main() {
    vec4 world = modelMatrix * vec4(position, 1.0);
    vW = world.xyz;
    vN = normalize(mat3(modelMatrix) * normal);
    gl_Position = projectionMatrix * viewMatrix * world;
}`;
const fragment = /* glsl */ `
uniform vec3 uLampPos, uLampColor, uRoom, uColor;
uniform float uLampPower, uPoolR, uMetal, uShown, uNight;
varying vec3 vN;
varying vec3 vW;
void main() {
    vec3 n = normalize(vN);
    if (!gl_FrontFacing) n = -n;
    vec3 L = normalize(uLampPos - vW), V = normalize(cameraPosition - vW);
    float pool = 1.0 - smoothstep(0.3, 1.0, length(vW.xz - uLampPos.xz) / uPoolR);
    float diff = max(dot(n, L), 0.0);
    float room = 0.55 + 0.35 * max(n.y, 0.0);
    float spec = pow(max(dot(n, normalize(L + V)), 0.0), mix(28.0, 90.0, uMetal)) * mix(0.15, 1.2, uMetal);
    // steel mirrors the room above it as well, so it reads as metal from any side
    float sky = uMetal * 0.3 * smoothstep(0.0, 1.0, reflect(-V, n).y);
    // by night a dark object under the red lamp would vanish: it takes the lamp's colour, by its own lightness
    vec3 albedo = mix(uColor, vec3(0.25 + dot(uColor, vec3(0.3, 0.59, 0.11)) * 1.3), uNight);
    vec3 light = uRoom * room + uLampColor * uLampPower * pool * diff * 0.9;
    vec3 col = albedo * light + uLampColor * uLampPower * (spec * (0.3 + 0.7 * pool)) + uRoom * sky;
    // by night the cabin is dark outside the pool: the instruments keep a faint rim of the red lamp, so they
    // stay things on the table and do not sink into the dark paper
    float rim = pow(1.0 - max(dot(n, V), 0.0), 2.0);
    col += uLampColor * uNight * (0.05 + 0.25 * rim + 0.2 * sky);
    gl_FragColor = vec4(col, uShown);
    #include <colorspace_fragment>
}`;

export function makeTools({ scene, toWorld, surface, uniforms }) {
    const group = new THREE.Group();
    group.visible = false;
    scene.add(group);
    const toolUniforms = {
        uToolA: { value: Array.from({ length: TOOLS }, () => new THREE.Vector4()) },
        uToolB: { value: Array.from({ length: TOOLS }, () => new THREE.Vector4()) },
        uToolsOn: { value: 0 },
    };
    const shown = { value: 0 };
    const mats = [];
    const material = (hex, metal) => {
        const m = new THREE.ShaderMaterial({
            uniforms: {
                uLampPos: uniforms.uLampPos, uLampColor: uniforms.uLampColor, uRoom: uniforms.uRoom, uLampPower: uniforms.uLampPower,
                uPoolR: uniforms.uPoolR, uNight: uniforms.uNight, uColor: { value: new THREE.Color(hex) }, uMetal: { value: metal }, uShown: shown,
            },
            vertexShader: vertex, fragmentShader: fragment, transparent: true,
        });
        mats.push(m);
        return m;
    };
    // a part: a cylinder (or a cone, r1 at a, r2 at b) between two points, placed again by set(a, b)
    const up = new THREE.Vector3(0, 1, 0), A = new THREE.Vector3(), B = new THREE.Vector3();
    function part(r1, r2, mat, sides) {
        const mesh = new THREE.Mesh(new THREE.CylinderGeometry(r2, r1, 1, sides, 1), mat);
        group.add(mesh);
        return (a, b) => {
            A.set(...a); B.set(...b);
            mesh.position.copy(A).add(B).multiplyScalar(0.5);
            mesh.scale.set(1, Math.max(A.distanceTo(B), 1e-4), 1);
            mesh.quaternion.setFromUnitVectors(up, B.sub(A).normalize());
        };
    }

    // the pencil on Walcheren, west of the fold: hexagonal navy lacquer, brass ferrule, wood, graphite
    const R = 0.034;
    const pencil = {
        a: [440, 215], b: [585, 265],
        parts: [part(R * 0.98, R * 0.98, material("#b9a26a", 0.6), 16), part(R, R, material("#1f3346", 0.15), 6),
                part(R, R * 0.3, material("#d8b98a", 0), 6), part(R * 0.3, 0.002, material("#33343a", 0.4), 6)],
    };
    // the dividers on the Hooge Platen: two steel legs from a raised hinge, the hinge, its handle
    const steel = material("#a7adb1", 1), dark = material("#5d6366", 0.8);
    const dividers = {
        a: [760, 712], b: [902, 694],
        legs: [part(0.024, 0.005, steel, 12), part(0.024, 0.005, steel, 12)],
        hinge: part(0.034, 0.034, dark, 16), handle: part(0.012, 0.01, steel, 10),
    };

    let lastRelief = -1;
    /* lay them on the relief as it stands now (relief: uRelief 0..1), and show them (0..1) */
    function place(relief, show) {
        shown.value = show;
        toolUniforms.uToolsOn.value = show;
        group.visible = show > 0.003;
        if (Math.abs(relief - lastRelief) < 1e-4) return;
        lastRelief = relief;
        const caps = [];
        {
            const pa = toWorld(...pencil.a), pb = toWorld(...pencil.b);
            const ya = surface(...pencil.a) * relief + R, yb = surface(...pencil.b) * relief + R;
            const dir = new THREE.Vector3(pb.x - pa.x, yb - ya, pb.z - pa.z), len = dir.length();
            dir.normalize();
            const at = (k) => [pa.x + dir.x * k, ya + dir.y * k, pa.z + dir.z * k];
            pencil.parts[0](at(0), at(0.07));
            pencil.parts[1](at(0.07), at(len - 0.16));
            pencil.parts[2](at(len - 0.16), at(len - 0.03));
            pencil.parts[3](at(len - 0.03), at(len));
            caps.push([at(0), at(len), R]);
        }
        {
            const p1 = toWorld(...dividers.a), p2 = toWorld(...dividers.b);
            const y1 = surface(...dividers.a) * relief + 0.002, y2 = surface(...dividers.b) * relief + 0.002;
            const hinge = [(p1.x + p2.x) / 2, Math.max(y1, y2) + 0.44, (p1.z + p2.z) / 2 - 0.28];
            dividers.legs[0](hinge, [p1.x, y1, p1.z]);
            dividers.legs[1](hinge, [p2.x, y2, p2.z]);
            const ax = new THREE.Vector3(p2.x - p1.x, 0, p2.z - p1.z).normalize().multiplyScalar(0.03);
            dividers.hinge([hinge[0] - ax.x, hinge[1], hinge[2] - ax.z], [hinge[0] + ax.x, hinge[1], hinge[2] + ax.z]);
            const top = [hinge[0] + 0.02, hinge[1] + 0.13, hinge[2]];
            dividers.handle(hinge, top);
            caps.push([hinge, [p1.x, y1, p1.z], 0.016], [hinge, [p2.x, y2, p2.z], 0.016], [hinge, top, 0.012]);
        }
        caps.slice(0, TOOLS).forEach(([a, b, r], i) => {
            toolUniforms.uToolA.value[i].set(a[0], a[1], a[2], r);
            toolUniforms.uToolB.value[i].set(b[0], b[1], b[2], 1);
        });
    }
    return { uniforms: toolUniforms, place, group };
}
