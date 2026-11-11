/* Tidewatch, level 5: the printed chart as a picture for the 3D table.

   The hero chart is the page's own inline SVG (the poster of every level). This draws that same SVG
   onto a canvas, element by element, so the 3D table can lay it over the relief as its paper: the
   same tints, contours, soundings, names, lights, rose and neat line, in the page's own fonts. It is
   drawn twice, once with the day tokens and once with the night ones, read from tokens.css itself,
   so the scene can turn the chart to night (the landfall) whatever theme the page is in.

   chartPicture(svg, "day" | "night", scale, skip) -> canvas, (1000 x 900) x scale pixels.
   Only what the chart uses is drawn: g, path, circle, ellipse, text and tspan, the hatch pattern;
   the pencil's filter is left out (the scene draws the pencil itself). Nothing is fetched. */

const THEMES = { day: [":root"], night: [':root[data-theme="dark"]'] };
let tokenCache = null;

/* every --custom property of the two theme rules of tokens.css, as written there */
function themeTokens() {
  if (tokenCache) return tokenCache;
  const found = { day: {}, night: {} };
  for (const sheet of Array.from(document.styleSheets)) {
    let rules;
    try { rules = sheet.cssRules; } catch (error) { continue; }   // a sheet from elsewhere: not ours
    for (const rule of Array.from(rules || [])) {
      const own = rule.selectorText && rule.selectorText.trim();
      for (const [name, selectors] of Object.entries(THEMES)) {
        if (!selectors.includes(own)) continue;
        for (let i = 0; i < rule.style.length; i++) {
          const prop = rule.style[i];
          if (prop.startsWith("--")) found[name][prop] = rule.style.getPropertyValue(prop).trim();
        }
      }
    }
  }
  tokenCache = found;
  return found;
}

const STRETCH = [[56, "extra-condensed"], [68, "condensed"], [81, "semi-condensed"], [93, "normal"], [106, "semi-expanded"], [137, "expanded"]];
function stretchKeyword(value) {
  const pct = parseFloat(value);
  if (!Number.isFinite(pct)) return "normal";
  let name = "ultra-condensed";
  for (const [edge, word] of STRETCH) if (pct >= edge) name = word;
  return name;
}
const num = (v, fallback = 0) => { const n = parseFloat(v); return Number.isFinite(n) ? n : fallback; };
const dashes = (value) => (!value || value === "none" ? [] : value.split(/[\s,]+/).map(parseFloat).filter(Number.isFinite));

function font(cs) {
  return `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
}

function setFont(ctx, cs) {
  ctx.font = font(cs);
  if ("fontStretch" in ctx) ctx.fontStretch = stretchKeyword(cs.fontStretch);
  if ("letterSpacing" in ctx) ctx.letterSpacing = cs.letterSpacing === "normal" ? "0px" : cs.letterSpacing;
}

function paint(ctx, path, cs, alpha, hatch, fillRule) {
  const fill = cs.fill, stroke = cs.stroke;
  if (fill && fill !== "none") {
    ctx.globalAlpha = alpha * num(cs.fillOpacity, 1);
    ctx.fillStyle = fill.startsWith("url(") ? hatch || "rgba(0,0,0,0)" : fill;
    ctx.fill(path, fillRule === "evenodd" ? "evenodd" : "nonzero");
  }
  const width = num(cs.strokeWidth, 1);
  if (stroke && stroke !== "none" && width > 0) {
    ctx.globalAlpha = alpha * num(cs.strokeOpacity, 1);
    ctx.strokeStyle = stroke;
    ctx.lineWidth = width;
    ctx.lineCap = cs.strokeLinecap || "butt";
    ctx.lineJoin = cs.strokeLinejoin || "miter";
    ctx.setLineDash(dashes(cs.strokeDasharray));
    ctx.stroke(path);
    ctx.setLineDash([]);
  }
}

/* one <text>: its runs (the text itself and each tspan), laid out in chunks that start where a tspan
   gives its own x, each chunk anchored as a whole */
function drawText(ctx, el, alpha) {
  const base = getComputedStyle(el);
  const chunks = [];
  let x = num(el.getAttribute("x")), y = num(el.getAttribute("y")) + num(el.getAttribute("dy"));
  let chunk = { x, runs: [] };
  chunks.push(chunk);
  for (const node of Array.from(el.childNodes)) {
    if (node.nodeType === 3) {
      if (node.data.trim() || chunk.runs.length) chunk.runs.push({ text: node.data, cs: base, y });
    } else if (node.nodeType === 1 && node.tagName.toLowerCase() === "tspan") {
      const cs = getComputedStyle(node);
      if (node.hasAttribute("x")) { chunk = { x: num(node.getAttribute("x")), runs: [] }; chunks.push(chunk); }
      y += num(node.getAttribute("dy"));
      chunk.runs.push({ text: node.textContent, cs, y });
    }
  }
  const anchor = base.textAnchor || "start";
  for (const c of chunks) {
    let width = 0;
    for (const run of c.runs) { setFont(ctx, run.cs); run.width = ctx.measureText(run.text).width; width += run.width; }
    let at = c.x - (anchor === "middle" ? width / 2 : anchor === "end" ? width : 0);
    for (const run of c.runs) {
      const cs = run.cs;
      setFont(ctx, cs);
      ctx.textAlign = "left";
      ctx.textBaseline = "alphabetic";
      const halo = /^stroke/.test(cs.paintOrder || "") && cs.stroke && cs.stroke !== "none";
      if (halo) {
        ctx.globalAlpha = alpha * num(cs.strokeOpacity, 1);
        ctx.strokeStyle = cs.stroke;
        ctx.lineWidth = num(cs.strokeWidth, 1);
        ctx.lineJoin = "round";
        ctx.strokeText(run.text, at, run.y);
      }
      if (cs.fill && cs.fill !== "none") {
        ctx.globalAlpha = alpha * num(cs.fillOpacity, 1);
        ctx.fillStyle = cs.fill;
        ctx.fillText(run.text, at, run.y);
        if (/underline/.test(cs.textDecorationLine || cs.textDecoration || "")) {
          const size = num(cs.fontSize, 10);
          ctx.fillRect(at, run.y + size * 0.14, run.width - num(cs.letterSpacing, 0), Math.max(size * 0.06, 0.5));
        }
      }
      at += run.width;
    }
  }
}

function walk(ctx, el, alpha, hatch, skip) {
  const tag = el.tagName.toLowerCase();
  if (tag === "defs" || tag === "title" || tag === "desc" || (skip && el.matches(skip))) return;
  const cs = getComputedStyle(el);
  if (cs.display === "none") return;
  const opacity = alpha * num(cs.opacity, 1);
  if (opacity <= 0.001) return;
  ctx.save();
  const own = el.transform && el.transform.baseVal && el.transform.baseVal.consolidate && el.transform.baseVal.consolidate();
  if (own) { const m = own.matrix; ctx.transform(m.a, m.b, m.c, m.d, m.e, m.f); }
  if (tag === "g" || tag === "svg") {
    for (const child of Array.from(el.children)) walk(ctx, child, opacity, hatch, skip);
  } else if (tag === "path") {
    paint(ctx, new Path2D(el.getAttribute("d") || ""), cs, opacity, hatch, cs.fillRule || el.getAttribute("fill-rule"));
  } else if (tag === "circle") {
    const p = new Path2D();
    p.arc(num(el.getAttribute("cx")), num(el.getAttribute("cy")), num(el.getAttribute("r")), 0, Math.PI * 2);
    paint(ctx, p, cs, opacity, hatch);
  } else if (tag === "ellipse") {
    const p = new Path2D();
    p.ellipse(num(el.getAttribute("cx")), num(el.getAttribute("cy")), num(el.getAttribute("rx")), num(el.getAttribute("ry")), 0, 0, Math.PI * 2);
    paint(ctx, p, cs, opacity, hatch);
  } else if (tag === "text") {
    drawText(ctx, el, opacity);
  }
  ctx.restore();
}

/* the hatch of the built-up areas: a 5-unit ruling turned 38 degrees, as the SVG's own pattern */
function hatchPattern(ctx, svg, scale) {
  const line = svg.querySelector("pattern path");
  const pattern = svg.querySelector("pattern");
  if (!line || !pattern) return null;
  const cs = getComputedStyle(line);
  const size = num(pattern.getAttribute("width"), 5);
  const tile = document.createElement("canvas");
  tile.width = tile.height = Math.max(2, Math.round(size * scale));
  const t = tile.getContext("2d");
  t.globalAlpha = num(cs.strokeOpacity, 1);
  t.strokeStyle = cs.stroke;
  t.lineWidth = num(cs.strokeWidth, 0.7) * scale;
  t.beginPath(); t.moveTo(0, 0); t.lineTo(0, tile.height); t.moveTo(tile.width, 0); t.lineTo(tile.width, tile.height); t.stroke();
  const fill = ctx.createPattern(tile, "repeat");
  const turn = /rotate\(\s*(-?[\d.]+)/.exec(pattern.getAttribute("patternTransform") || "");
  if (fill && fill.setTransform) fill.setTransform(new DOMMatrix().rotate(turn ? Number(turn[1]) : 0).scale(size / tile.width));
  return fill;
}

export function chartPicture(svg, theme, scale = 2, skip = ".c-pencil") {
  const tokens = themeTokens()[theme] || {};
  const host = document.createElement("div");
  host.setAttribute("aria-hidden", "true");
  host.style.cssText = "position:fixed;left:-20000px;top:0;width:1000px;height:900px;opacity:0;pointer-events:none;contain:strict";
  for (const [name, value] of Object.entries(tokens)) host.style.setProperty(name, value);
  const clone = svg.cloneNode(true);
  clone.setAttribute("class", "chart");
  clone.removeAttribute("style");
  for (const withId of clone.querySelectorAll("[id]")) withId.removeAttribute("id");
  clone.style.cssText = "position:absolute;left:0;top:0;width:1000px;height:900px";
  host.appendChild(clone);
  document.body.appendChild(host);
  const canvas = document.createElement("canvas");
  const box = (clone.getAttribute("viewBox") || "0 0 1000 900").split(/[\s,]+/).map(Number);
  canvas.width = Math.round(box[2] * scale);
  canvas.height = Math.round(box[3] * scale);
  const ctx = canvas.getContext("2d");
  try {
    if (theme === "day") {                                  // the paper the chart is printed on
      ctx.fillStyle = tokens["--color-bg"] || getComputedStyle(host).getPropertyValue("--color-bg") || "#f2ebdd";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
    ctx.scale(scale, scale);
    ctx.translate(-box[0], -box[1]);
    const hatch = hatchPattern(ctx, clone, scale);
    for (const child of Array.from(clone.children)) walk(ctx, child, 1, hatch, skip);
  } finally {
    host.remove();
  }
  return canvas;
}
