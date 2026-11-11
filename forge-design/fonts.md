# Fonts, per profile

How forge-design design's Step 4 loads the open font it picked, self-hosted, and what `font.sans` in
`forge-work/design/tokens.json` (so `--font-sans`) then holds. The examples use Inter; any open font
on Fontsource works the same way. Install it with the app's own package manager, which its lockfile
names (`../forge-design/motion.md` section 5): `npm install` below is npm's form, and an app with a
`pnpm-lock.yaml`, `yarn.lock` or `bun.lock` (or `bun.lockb`) takes `pnpm add`, `yarn add` or
`bun add`, never a second lockfile. A heading font from the brief goes in a `font.display` token the
same way. Keep the font's licence file next to its files, and read it: most open fonts are under the
SIL Open Font License, which asks that the licence travels with the font.

Fontsource has two kinds of package. `@fontsource-variable/<name>` holds a variable font, one file
per axis. A font with no variable version (npm answers 404) is `@fontsource/<name>`: one file per
weight (`@fontsource/ibm-plex-mono/400.css`, `files/ibm-plex-mono-latin-400-normal.woff2`), and its
family is the plain name, "IBM Plex Mono", not "... Variable".

- laravel, static: `"Inter Variable"` from Fontsource (`npm install @fontsource-variable/inter`,
  imported in the main JS or CSS file). laravel may instead keep the skeleton's `fonts` option of
  laravel-vite-plugin, with `fontsource("Inter")` (after `npm install @fontsource/inter`, which it
  reads from node_modules) in place of `bunny(...)` or `google(...)`: those download the font from
  that host at build time.
- next: Fontsource too (`npm install @fontsource-variable/inter`), loaded in `app/layout.tsx` with
  `localFont({ src: "../node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
  variable: "--font-inter", weight: "100 900" })` from `next/font/local` (one more `../` under
  `src/app/`); put that class on `<html>` so `:root` sees it; `font.sans` is then
  `var(--font-inter), system-ui, sans-serif`. A width axis (Archivo's `wdth`) needs the `wdth` file,
  which holds weight and width, and the range from the package's `wdth.css`: `src:
  ".../archivo-latin-wdth-normal.woff2", weight: "100 900", declarations: [{ prop: "font-stretch",
  value: "62% 125%" }]`; without it `font-stretch` does nothing. A static font: `src: [{ path:
  ".../ibm-plex-mono-latin-400-normal.woff2", weight: "400" }, ...]`, one entry per weight.
- django: the .woff2 files from the font's official release in `static/fonts/`, with `@font-face`
  rules (`font-display: swap`) whose `font-family` is exactly the first name in `font.sans`.

A font the user's app gets from another host moves to the package manager the same way: a CDN
link, `next/font/google` (it fetches the font during `next build`, which also fails offline or
behind a proxy) or a build-time download such as `bunny(...)`. Keep its family, weights, axes and
variable name, so the app's own CSS stays as it is.

Fontsource's `latin` file holds U+0000-00FF, the punctuation of U+2000-206F (dashes, curly quotes,
the bullet, the ellipsis) and the arrows up and down (U+2191, U+2193), but not left or right (U+2190,
U+2192): those come from the next font in `font.sans`, in another design. Check what the app writes
beyond plain Latin against the `unicode-range` lines in the package's CSS. One it writes often and
no subset holds: draw it as an icon, or put a font that has it next in the stack.

No font CDN, ever: it sends every visitor's IP address to a third party (AVG/GDPR). Some Laravel
skeletons and starter kits link fonts.bunny.net in a Blade layout: replace it. The search in
`forge-work/design/components.md` (`## Fonts and icons`) must find nothing after scaffolding.
