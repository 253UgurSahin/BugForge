/* Tidewatch, level 4: the printed chart as pictures for the 3D table (table.js).

   The hero chart is the page's own inline SVG, drawn from one sea bed (the poster of every level), cut
   as level 3 cuts it: the sheet runs from x 140 to 1000 of the chart, with its neat line on four sides.
   The table prints that same SVG on its sheet in two layers, so the water of the tide lies between the
   paper and the ink and never over a word or a line:
   - base(theme): the paper and its tints (the shoal blues, the drying green, the land, the basins), no
     line and no letter. "day" on the day paper; "night" is the night print's tints over white, so it
     reads as how much each tint darkens the sheet that the red lamp lights.
   - ink(): every line, sign and letter (contours, soundings, names, buoys, lights, the rose, the neat
     line) and the pencil (the course, its fixes, times and notes, its line clean), over nothing: the
     day colours with their coverage. The scene keeps them in register with the banks and prints them
     last, so they stay as dark and sharp as on paper; at night it uses their coverage only.
   How: the plates of the poster are put together in one SVG again, with the page's chart rules (every
   top-level `.chart` rule of the stylesheets) and the colour tokens of one theme, read from the `:root`
   and `:root[data-theme="dark"]` rules of tokens.css, so day and night can both be printed whatever theme
   the page shows now. The fonts go in as data, read from the page's own font files (same origin, no
   other host). The SVG becomes an image; the image is drawn on a canvas in bands, with a breath between
   them, so the page never waits long for one big drawing.

   chartPrint(hero, { width }) -> { width, height, base(theme, width), ink() }, each a Promise<canvas>. */

const THEMES = { day: ":root", night: ':root[data-theme="dark"]' };
const XMLNS = "http://www.w3.org/2000/svg";
const VIEW = { x: 140, w: 860, h: 900 };
const breath = () => new Promise((resolve) => setTimeout(resolve, 0));

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
const INKS = ".c-grat, .c-dyke, .c-groyne, .c-town, .c-mole, .c-light, .c-mark, .c-buoy, .c-wreck, .c-diamond, .c-rose, .c-title, .c-fig, .c-snd, .c-pencil, .c-lines, .c-neat, text";
const LAYER = {
  base: `.chart * { stroke: none !important; }
    .chart :is(${INKS}) { display: none !important; }`,
  ink: `.chart .c-sea path, .chart .c-land path, .chart .c-basin path { fill: none !important; }
    .chart .c-pencil { filter: none !important; }
    .chart .c-shadow { display: none !important; }`,
};

export function chartPrint(hero, { width = 2048 } = {}) {
  const tokens = themeTokens();
  const rules = chartRules();
  const faces = fontFaces();
  const serial = (node) => new XMLSerializer().serializeToString(node);
  /* the plates of the poster, in the order they lie on the sheet (the shadows are the poster's own) */
  const plates = [".plate--sea", ".plate--land", ".plate--ink", ".plate--pencil"].map((sel) => hero.querySelector(sel)).filter(Boolean);
  const inner = plates.map((svg) => Array.from(svg.childNodes).filter((n) => n.nodeType === 1).map(serial).join("")).join("");
  const heightOf = (w) => Math.round((w * VIEW.h) / VIEW.w);

  function markup(theme, layer, w, h) {
    const vars = Object.entries(tokens[theme]).map(([k, v]) => `${k}:${v}`).join(";");
    return `<svg xmlns="${XMLNS}" xmlns:xlink="http://www.w3.org/1999/xlink" class="chart" viewBox="${VIEW.x} 0 ${VIEW.w} ${VIEW.h}" `
      + `width="${w}" height="${h}" preserveAspectRatio="none">`
      + `<style>svg{${vars}}\n${rules}\n${LAYER[layer]}</style>${inner}</svg>`;
  }
  async function paint(theme, layer, w, fill) {
    const h = heightOf(w);
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
      const g = canvas.getContext("2d");
      if (fill) { g.fillStyle = fill; g.fillRect(0, 0, w, h); }
      const bands = Math.max(1, Math.ceil(h / 384));
      for (let i = 0; i < bands; i++) {
        const y0 = Math.round((i * h) / bands), y1 = Math.round(((i + 1) * h) / bands);
        await breath();
        g.drawImage(image, 0, (y0 / h) * image.height, image.width, ((y1 - y0) / h) * image.height, 0, y0, w, y1 - y0);
      }
      return canvas;
    } finally {
      URL.revokeObjectURL(url);
    }
  }
  return {
    width,
    height: heightOf(width),
    /* the paper and its tints: by day on the day paper; by night the night tints over white */
    base(theme, w = Math.min(width, 1024)) {
      return paint(theme, "base", w, theme === "night" ? "#ffffff" : (tokens.day["--color-surface"] || "#faf6ec"));
    },
    /* every line, sign and letter of the day print, and the pencil, over nothing */
    ink() { return paint("day", "ink", width, null); },
  };
}
