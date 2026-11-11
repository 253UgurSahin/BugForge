/* Tidewatch, level 5: the printed chart as pictures for the 3D chart table (table.js).

   The hero chart is the page's own inline SVG (the poster of every level). The table prints that same SVG
   on its sheet, in three layers, so the water of the tide can lie between the paper and the ink and never
   over a word or a line:
   - base(theme): the paper and its tints (the sea's shoal tints, the drying banks, the land, the harbour
     basins, the margin), no line and no letter. "day" on the day paper; "night" is the night print's tints
     over white, so it reads as how much each tint darkens the sheet the red lamp lights.
   - ink(): every line, sign and letter of the day print (contours, soundings, names, buoys, lights, the
     rose, the neat line), over nothing: the colours with their coverage (premultiplied).
   - pencil(): the pencilled course, its fixes, times, bearings and notes, as coverage (a byte a pixel).
   How: the SVG is put together again with the page's chart rules (every top-level `.chart` rule of the
   stylesheets) and the colour tokens of one theme, read from the `:root` and `:root[data-theme="dark"]`
   rules of tokens.css, so day and night can both be printed whatever theme the page shows now. The fonts go
   in as data, read from the page's own font files (same origin, no other host). The SVG becomes an image,
   the image is drawn on a canvas at the size asked for, so the print is as sharp as the camera comes close.

   chartPrint(svg, { width }) -> { width, height, tokens, base(theme, width), ink(), pencil() } */

const THEMES = { day: ":root", night: ':root[data-theme="dark"]' };
const breath = () => new Promise((resolve) => setTimeout(resolve, 0));
const XMLNS = "http://www.w3.org/2000/svg";

/* every custom property set by the day rule, and the night rule on top of it */
function themeTokens() {
  const found = { day: {}, night: {} };
  for (const sheet of Array.from(document.styleSheets)) {
    let rules;
    try { rules = sheet.cssRules; } catch (error) { continue; }
    for (const rule of Array.from(rules || [])) {
      if (!rule.style || !rule.selectorText) continue;
      const selector = rule.selectorText.trim();
      for (const [name, wanted] of Object.entries(THEMES)) {
        if (selector !== wanted) continue;
        for (let i = 0; i < rule.style.length; i++) {
          const prop = rule.style[i];
          if (prop.startsWith("--")) found[name][prop] = rule.style.getPropertyValue(prop).trim();
        }
      }
    }
  }
  return { day: found.day, night: { ...found.day, ...found.night } };
}

/* the chart's own rules, as text: only rules at the top level (no motion, no narrow-screen rules) */
function chartRules() {
  const out = [];
  for (const sheet of Array.from(document.styleSheets)) {
    let rules;
    try { rules = sheet.cssRules; } catch (error) { continue; }
    for (const rule of Array.from(rules || [])) {
      if (rule.type !== 1 || !/\.chart\b/.test(rule.selectorText || "")) continue;
      out.push(rule.cssText.replace(/\b(animation|transition)[^;]*;/g, ""));
    }
  }
  return out.join("\n");
}

const fontCache = new Map();
function asData(url) {
  if (!fontCache.has(url)) {
    fontCache.set(url, fetch(url).then((response) => (response.ok ? response.blob() : null)).then((blob) => new Promise((resolve) => {
      if (!blob) { resolve(null); return; }
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    })).catch(() => null));
  }
  return fontCache.get(url);
}

/* the page's @font-face rules, with each file as data */
async function fontFaces() {
  const faces = [];
  for (const sheet of Array.from(document.styleSheets)) {
    let rules;
    try { rules = sheet.cssRules; } catch (error) { continue; }
    for (const rule of Array.from(rules || [])) {
      if (rule.type !== 5) continue;                                   // CSSFontFaceRule
      const match = /url\(["']?([^"')]+)["']?\)/.exec(rule.style.getPropertyValue("src"));
      if (!match) continue;
      const url = new URL(match[1], sheet.href || location.href);
      if (url.origin !== location.origin) continue;                    // the page's own files only
      faces.push(asData(url.href).then((data) => data && rule.cssText.replace(match[0], `url("${data}")`)));
    }
  }
  return (await Promise.all(faces)).filter(Boolean).join("\n");
}

/* what each layer leaves out */
const INKS = ".c-grat, .c-dyke, .c-groyne, .c-town, .c-mole, .c-light, .c-mark, .c-buoy, .c-wreck, .c-diamond, .c-rose, .c-title, .c-fig, .c-snd, .c-pencil, text";
const LAYER = {
  base: `.chart * { stroke: none !important; }
    .chart :is(${INKS}) { display: none !important; }
    .chart .c-neat > :not(.paper) { display: none !important; }`,
  ink: `.chart .c-sea path, .chart .c-land path, .chart .c-basin path { fill: none !important; }
    .chart .c-neat .paper, .chart .c-pencil { display: none !important; }`,
  pencil: `.chart > :not(defs):not(.c-pencil) { display: none !important; }
    .chart .c-pencil { stroke: #000 !important; stroke-opacity: 1 !important; filter: none !important; }
    .chart .c-pencil text, .chart .c-pencil .dot { fill: #000 !important; fill-opacity: 1 !important; }`,
};

export function chartPrint(svg, { width = 4096 } = {}) {
  const tokens = themeTokens();
  const rules = chartRules();
  const faces = fontFaces();
  const serial = (node) => new XMLSerializer().serializeToString(node);
  const inner = Array.from(svg.childNodes).filter((n) => n.nodeType === 1).map(serial).join("");

  function markup(theme, layer, w, h) {
    const vars = Object.entries(tokens[theme]).map(([k, v]) => `${k}:${v}`).join(";");
    return `<svg xmlns="${XMLNS}" xmlns:xlink="http://www.w3.org/1999/xlink" class="chart" viewBox="0 0 1000 900" `
      + `width="${w}" height="${h}" preserveAspectRatio="none">`
      + `<style>svg{${vars}}\n${rules}\n${LAYER[layer]}</style>${inner}</svg>`;
  }
  async function paint(theme, layer, w, fill) {
    const h = Math.round(w * 0.9);
    const fonts = await faces;
    const text = markup(theme, layer, w, h).replace("<style>", `<style>${fonts}\n`);
    const url = URL.createObjectURL(new Blob([text], { type: "image/svg+xml" }));
    try {
      const image = new Image();
      image.decoding = "async";
      image.src = url;
      await image.decode();
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const g = canvas.getContext("2d", { willReadFrequently: layer === "pencil" });
      if (fill) { g.fillStyle = fill; g.fillRect(0, 0, w, h); }
      // in bands, with a breath between them, so the page never waits long for one big drawing
      const bands = Math.max(1, Math.ceil(h / 1024));
      for (let i = 0; i < bands; i++) {
        const y0 = Math.round((i * h) / bands), y1 = Math.round(((i + 1) * h) / bands);
        g.drawImage(image, 0, y0, w, y1 - y0, 0, y0, w, y1 - y0);
        if (i < bands - 1) await breath();
      }
      return canvas;
    } finally {
      URL.revokeObjectURL(url);
    }
  }
  return {
    width,
    height: Math.round(width * 0.9),
    tokens,
    /* the paper and its tints: by day on the day paper; by night the night tints over white */
    base(theme, w = Math.min(width, 2048)) {
      return paint(theme, "base", w, theme === "night" ? "#ffffff" : (tokens.day["--color-bg"] || "#f2ebdd"));
    },
    /* every line, sign and letter of the day print, over nothing */
    ink() { return paint("day", "ink", width, null); },
    /* the pencil alone, read back as coverage, row 0 at the top */
    async pencil() {
      const canvas = await paint("day", "pencil", width, null);
      const g = canvas.getContext("2d"), w = canvas.width, h = canvas.height, out = new Uint8Array(w * h);
      for (let y = 0; y < h; y += 512) {
        const rows = Math.min(512, h - y), data = g.getImageData(0, y, w, rows).data;
        for (let i = 0, j = 3, k = y * w; i < w * rows; i++, j += 4) out[k + i] = data[j];
        await breath();
      }
      canvas.width = canvas.height = 1;
      return out;
    },
  };
}
