/* Tidewatch, level 5: the sea bed under the hero chart, as numbers.

   The very height field that drew the chart on every level (the coast, the drying line, the 2, 5, 10
   and 20 m contours and all 105 soundings of the inline SVG come from it), so the 3D relief agrees
   with the printed chart to the unit. Chart space: x 0..1000 west to east, y 0..900 north to south,
   120 units to the nautical mile. seaBed(x, y) is metres above chart datum: land from 5 m up, the
   drying banks 0 to 3.6 m, water below 0. Made up, but shaped like the mouth of the Westerschelde.

   reliefGrid(columns, rows) samples it for the 3D table: heights and slopes on a grid over the sheet.
   The coast is the costly part (a distance to two long curves for every point), so it is measured
   on a coarse grid and spread over the fine one, which is exact enough: a distance field is smooth. */

export const W = 1000, H = 900, NM = 120;

const NORTH = [[-80, -40], [60, 8], [170, 52], [300, 128], [430, 228], [545, 318], [628, 366], [690, 372],
  [742, 356], [800, 334], [862, 316], [930, 300], [1080, 286]];
const SOUTH = [[-80, 884], [70, 862], [200, 838], [330, 800], [455, 752], [540, 708], [596, 690], [650, 694],
  [720, 716], [800, 742], [890, 762], [1080, 786]];

function catmull(points, per = 24) {
  const out = [];
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i - 1)], p1 = points[i], p2 = points[i + 1], p3 = points[Math.min(points.length - 1, i + 2)];
    for (let k = 0; k < per; k++) {
      const t = k / per, t2 = t * t, t3 = t2 * t;
      out.push([
        0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
        0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3),
      ]);
    }
  }
  out.push(points[points.length - 1]);
  return out;
}
export const northCoast = catmull(NORTH), southCoast = catmull(SOUTH);

/* distance from a point to a polyline, and which side of it the point lies on */
function toLine(line, x, y) {
  let best = Infinity, side = 1;
  for (let i = 0; i < line.length - 1; i++) {
    const ax = line[i][0], ay = line[i][1], bx = line[i + 1][0], by = line[i + 1][1];
    const dx = bx - ax, dy = by - ay;
    let t = ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy);
    t = t < 0 ? 0 : t > 1 ? 1 : t;
    const px = ax + t * dx, py = ay + t * dy, d = (x - px) * (x - px) + (y - py) * (y - py);
    if (d < best) { best = d; side = dx * (y - ay) - dy * (x - ax) >= 0 ? 1 : -1; }
  }
  return [Math.sqrt(best), side];
}
/* water is positive: south of the north coast, north of the south coast */
export function shore(x, y) {
  const [dn, sn] = toLine(northCoast, x, y), [ds, ss] = toLine(southCoast, x, y);
  return [dn * sn, -ds * ss];
}

export const CHANNELS = [
  { name: "Oostgat", depth: 13, width: 27, line: [[-60, 58], [70, 76], [190, 126], [300, 194], [410, 282], [520, 370], [612, 428], [700, 448]] },
  { name: "Wielingen", depth: 13, width: 44, line: [[-60, 776], [130, 752], [310, 700], [440, 640], [540, 572], [640, 492], [740, 448]] },
  { name: "Honte", depth: 13, width: 36, line: [[700, 448], [800, 420], [900, 398], [1060, 386]] },
  { name: "Schaar", depth: 7, width: 22, line: [[640, 600], [740, 584], [860, 580], [1060, 600]] },
  { name: "Deurloo", depth: 6, width: 24, line: [[-60, 448], [120, 444], [290, 468], [430, 500], [540, 540]] },
];
export const BANKS = [
  { name: "Spijkerplaat", at: [812, 496], r: [132, 27], turn: -5, rise: 10.2 },
  { name: "Hooge Platen", at: [850, 668], r: [190, 44], turn: 5, rise: 10.6 },
  { name: "Nolleplaat", at: [388, 398], r: [96, 25], turn: 37, rise: 7.2 },
  { name: "Elleboog", at: [206, 322], r: [150, 34], turn: 30, rise: 8.4 },
  { name: "Raan", at: [150, 580], r: [190, 50], turn: 8, rise: 10.4 },
  { name: "Walvischstaart", at: [352, 566], r: [84, 20], turn: -14, rise: 5.6 },
  { name: "Galgeput", at: [640, 462], r: [50, 22], turn: -22, rise: -11 },
];

function seeded(seed) { let s = seed >>> 0; return () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296); }
const rnd = seeded(51260334);
const WAVES = Array.from({ length: 9 }, (_, i) => {
  const a = rnd() * Math.PI * 2, f = (0.006 + rnd() * 0.02) * (i < 4 ? 1 : 2.4);
  return { kx: Math.cos(a) * f, ky: Math.sin(a) * f, ph: rnd() * Math.PI * 2, amp: i < 4 ? 0.62 : 0.26 };
});

/* metres above chart datum, given the two signed distances to the coasts (water positive) */
function bedFrom(x, y, dn, ds, channels) {
  const s = Math.min(dn, ds);
  if (s <= 0) return 5 + Math.min(-s, 120) * 0.03;
  const fall = (d, len) => 5 - 14.2 * (1 - Math.exp(-d / len));
  const south = 62 + 46 * Math.min(1, Math.max(0, (x - 520) / 300));   // the flats widen to the east
  let e = Math.max(fall(dn, 34), fall(ds, south));
  for (let i = 0; i < CHANNELS.length; i++) {
    const d = channels ? channels[i] : toLine(CHANNELS[i].line, x, y)[0], c = CHANNELS[i];
    e -= c.depth * Math.exp(-(d * d) / (c.width * c.width));
  }
  for (const b of BANKS) {
    const t = (b.turn * Math.PI) / 180, dx = x - b.at[0], dy = y - b.at[1];
    const u = (dx * Math.cos(t) + dy * Math.sin(t)) / b.r[0], v = (-dx * Math.sin(t) + dy * Math.cos(t)) / b.r[1];
    e += b.rise * Math.exp(-(u * u + v * v));
  }
  const calm = Math.min(1, s / 60);                                       // no ripples in the surf line
  for (const w of WAVES) e += calm * w.amp * Math.sin(x * w.kx + y * w.ky + w.ph);
  return e > 2.2 ? 2.2 + 1.4 * Math.tanh((e - 2.2) / 1.4) : e;           // a bank dries, it never becomes land
}

export function seaBed(x, y) {
  const [dn, ds] = shore(x, y);
  return bedFrom(x, y, dn, ds, null);
}

/* The relief for the 3D table: COLUMNS x ROWS points spread evenly over the sheet (0..W, 0..H),
   row 0 at the top (north). Returns { columns, rows, height } with metres above datum. The distance
   to the two coasts (two long curves: the costly part) is measured exactly on a grid STEP times
   coarser and interpolated, which is exact enough for a distance field; the rest at every point. */
export function reliefGrid(columns, rows, step = 3) {
  const cc = Math.ceil((columns - 1) / step) + 1, cr = Math.ceil((rows - 1) / step) + 1;
  const coarse = new Float32Array(cc * cr * 2);
  for (let j = 0; j < cr; j++) {
    for (let i = 0; i < cc; i++) {
      const x = (Math.min(i * step, columns - 1) / (columns - 1)) * W, y = (Math.min(j * step, rows - 1) / (rows - 1)) * H;
      const [dn, ds] = shore(x, y), at = (j * cc + i) * 2;
      coarse[at] = dn; coarse[at + 1] = ds;
    }
  }
  const height = new Float32Array(columns * rows);
  for (let r = 0; r < rows; r++) {
    const fy = Math.min(r, rows - 1) / step, j0 = Math.min(Math.floor(fy), cr - 2), ty = fy - j0;
    for (let c = 0; c < columns; c++) {
      const fx = c / step, i0 = Math.min(Math.floor(fx), cc - 2), tx = fx - i0;
      const a = (j0 * cc + i0) * 2, b = a + 2, d = a + cc * 2, e = d + 2;
      const lerp = (k) => (coarse[a + k] * (1 - tx) + coarse[b + k] * tx) * (1 - ty) + (coarse[d + k] * (1 - tx) + coarse[e + k] * tx) * ty;
      const x = (c / (columns - 1)) * W, y = (r / (rows - 1)) * H;
      height[r * columns + c] = bedFrom(x, y, lerp(0), lerp(1), null);
    }
  }
  return { columns, rows, height };
}
