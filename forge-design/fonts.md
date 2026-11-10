# Fonts, per profile

How forge-design design's Step 4 loads the open font it picked, self-hosted, and what `font.sans` in
`forge-work/design/tokens.json` (so `--font-sans`) then holds. The examples use Inter; any open font
on Fontsource works the same way. A heading font from the brief goes in a `font.display` token the
same way. Keep the font's licence file next to its files, and read it: most open fonts are under
the SIL Open Font License, which asks that the licence travels with the font.

- laravel, static: `"Inter Variable"` from Fontsource (`npm install @fontsource-variable/inter`,
  imported in the main JS or CSS file). laravel may instead keep the skeleton's `fonts` option of
  laravel-vite-plugin with your font in it (`bunny("Inter", ...)` gives `"Inter"`): it downloads
  the files at build time and serves them from the app.
- next: Fontsource too (`npm install @fontsource-variable/inter`), loaded in `app/layout.tsx` with
  `localFont({ src: "../node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
  variable: "--font-inter", weight: "100 900" })` from `next/font/local` (one more `../` under
  `src/app/`); put that class on `<html>` so `:root` sees it; `font.sans` is then
  `var(--font-inter), system-ui, sans-serif`. `next/font/google` fetches the font during
  `next build`, which fails offline or behind a proxy: only when the build machine reaches Google.
- django: the .woff2 files from the font's official release in `static/fonts/`, with `@font-face`
  rules (`font-display: swap`) whose `font-family` is exactly the first name in `font.sans`.

No font CDN, ever: it sends every visitor's IP address to a third party (AVG/GDPR). Some Laravel
skeletons and starter kits link fonts.bunny.net in a Blade layout: replace it. The search in
`forge-work/design/components.md` (`## Fonts and icons`) must find nothing after scaffolding.
