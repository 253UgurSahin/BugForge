/* Tidewatch, level 4: the printed chart as a picture for the 3D table.

   The hero chart is the page's own inline SVG, drawn from one sea bed (the poster of every level). The
   3D table lays that same print over its relief, so nothing of the chart is lost: tints, contours,
   soundings, names, lights, buoys, the rose and the neat line, in the page's own fonts.

   How: the plates of the poster are put together in one SVG of their own, with the page's chart rules
   (every top-level `.chart` rule of the stylesheets) and the colour tokens of one theme, read from the
   `:root` and `:root[data-theme="dark"]` rules of tokens.css, so the day and the night print can both be
   made whatever theme the page shows now. The fonts go in as data, read from the page's own font files
   (the same origin, no other host). The SVG becomes an image, the image is drawn on a canvas.

   chartPictures(hero, { width }) -> { width, height, draw(theme), pencil() }
   draw("day" | "night") -> Promise<canvas>: the print without the pencil, on its paper.
   pencil() -> Promise<Uint8Array>: the pencilled course, its fixes and notes alone, as coverage (a byte
   a pixel, row 0 at the top), so the scene can draw it on whatever surface is on top: the water where
   the course is afloat, the paper where it is dry. */

const THEMES = { day: ":root", night: ':root[data-theme="dark"]' };

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
      if (/animation|transition/.test(rule.cssText) && !/fill|stroke|font/.test(rule.cssText)) continue;
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
      const src = rule.style.getPropertyValue("src");
      const match = /url\(["']?([^"')]+)["']?\)/.exec(src);
      if (!match) continue;
      const url = new URL(match[1], sheet.href || location.href);
      if (url.origin !== location.origin) continue;                    // the page's own files only
      faces.push(asData(url.href).then((data) => data && rule.cssText.replace(match[0], `url("${data}")`)));
    }
  }
  return (await Promise.all(faces)).filter(Boolean).join("\n");
}

const XMLNS = "http://www.w3.org/2000/svg";
const serial = (node) => new XMLSerializer().serializeToString(node);

export function chartPictures(hero, { width = 2048 } = {}) {
  const plates = {
    sea: hero.querySelector(".plate--sea"), land: hero.querySelector(".plate--land"),
    ink: hero.querySelector(".plate--ink"), pencil: hero.querySelector(".plate--pencil"),
  };
  const height = Math.round(width * 0.9);
  const tokens = themeTokens();
  const rules = chartRules();
  const faces = fontFaces();

  /* the inside of a plate, as markup (defs of the sea plate go first: the pencil filter, the hatch, the clip) */
  const inner = (svg) => (svg ? Array.from(svg.childNodes).map((n) => (n.nodeType === 1 ? serial(n) : "")).join("") : "");
  function sheetSVG(theme, parts, extra = "") {
    const vars = Object.entries(tokens[theme]).map(([k, v]) => `${k}:${v}`).join(";");
    return `<svg xmlns="${XMLNS}" xmlns:xlink="http://www.w3.org/1999/xlink" class="chart" viewBox="0 0 1000 900" `
      + `width="${width}" height="${height}" preserveAspectRatio="none">`
      + `<style>${extra}\nsvg{${vars}}\n${rules}\n.chart .c-shadow{display:none}</style>${parts}</svg>`;
  }
  async function paint(markup, fill) {
    const fonts = await faces;
    const text = markup.replace("<style>", `<style>${fonts}\n`);
    const url = URL.createObjectURL(new Blob([text], { type: "image/svg+xml" }));
    try {
      const image = new Image();
      image.decoding = "async";
      image.src = url;
      await image.decode();
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const g = canvas.getContext("2d", { willReadFrequently: !fill });
      if (fill) { g.fillStyle = fill; g.fillRect(0, 0, width, height); }
      g.drawImage(image, 0, 0, width, height);
      return canvas;
    } finally {
      URL.revokeObjectURL(url);
    }
  }
  const defs = plates.sea ? plates.sea.querySelector("defs") : null;
  const defsText = defs ? serial(defs) : "";
  const seaInner = plates.sea ? Array.from(plates.sea.childNodes).filter((n) => n.nodeType === 1 && n.tagName !== "defs").map(serial).join("") : "";
  return {
    width,
    height,
    /* the print on its paper: the day chart on the paper under the lamp, the night print (dark inks
       that let the paper through) on a pale sheet that only the red lamp will light */
    draw(theme) {
      const paper = theme === "night" ? "#efe4da" : (tokens.day["--color-surface"] || "#faf6ec");
      return paint(sheetSVG(theme, defsText + seaInner + inner(plates.land) + inner(plates.ink)), paper);
    },
    /* the pencil alone, in black, read back as coverage */
    async pencil() {
      const canvas = await paint(sheetSVG("day", defsText + inner(plates.pencil),
        ".chart .c-pencil{stroke:#000;stroke-opacity:1}.chart .c-pencil text,.chart .c-pencil .dot{fill:#000;fill-opacity:1}"), null);
      const data = canvas.getContext("2d").getImageData(0, 0, width, height).data;
      const out = new Uint8Array(width * height);
      for (let i = 0, j = 3; i < out.length; i++, j += 4) out[i] = data[j];
      return out;
    },
  };
}
