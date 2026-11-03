# Design

Profile: <laravel|django|next|static>. Tailwind: <4|3|no>.
Font: <name> (<licence>, <Fontsource | Fontsource with next/font/local | laravel-vite-plugin fonts | files in static/fonts/>).
Icons: <Lucide (ISC) | Heroicons (MIT) | Tabler Icons (MIT)>, as <package | SVG files in the repo>.

## Theme

File: <the theme file for the profile, from forge-design Step 3>

Values live only in `forge-work/design/tokens.json`. forge-build writes the file above from it with
this command, which follows the mapping below (names only, so it never goes stale):
`python3 ../forge-design/theme.py forge-work/design/tokens.json --tailwind <4|3|no> --write <the file above>`.
After any change to tokens.json, run it again, then `python3 ../forge-design/contrast.py
forge-work/design/tokens.json`. Components use these variables, never raw hex or px.

```css
:root {                                     /* Tailwind 4: @theme static { }, see below */
  --color-<role>: <color.role>;             /* one line per colour role */
  --font-sans: <font.sans>;
  --font-mono: <font.mono>;
  --text-<step>: <size>px;                  /* three lines per type step */
  --text-<step>--line-height: <line>px;
  --text-<step>--font-weight: <weight>;
  --space-<n>: <value>px;                   /* per space value, n = value / 4: --space-4 is 16px, --space-1_5 is 6px */
  --radius-<name>: <value>px;
  --shadow-<name>: <value>;
  --ease-standard: <motion.ease>;
}
:root {                                     /* a plain :root, with Tailwind 4 too */
  --duration-fast: <motion.fast>;
  --duration-base: <motion.base>;
  --layout-<name>: <value>px;               /* content, sidebar, header */
  --size-<name>: <value>px;                 /* borders, focus ring, icons, controls, a dialog */
}
@media (prefers-color-scheme: dark) {       /* only with a dark group in tokens.json */
  :root { --color-<role>: <color.dark.role>; }
}
/* Breakpoints go into media queries as numbers, @media (min-width: 768px): var() fails there. */
```

Tailwind 4 (`--tailwind 4`): the first block is `@theme static { }`, right after
`@import "tailwindcss";`. It starts with `--color-*: initial;`, so only your roles exist
(`bg-surface`, `text-text-muted`), and has `--breakpoint-*: initial;` plus one `--breakpoint-` line
per breakpoint (`--breakpoint-md: 768px;`), so `md:` follows the measured breakpoints. It leaves out
`--space-*`: Tailwind's own 4px `--spacing` makes `p-4` 16px. `static` writes out every variable, so
the dark block works without `dark:` classes. Use the plain `:root` values as
`duration-(--duration-fast)`, `max-w-(--layout-content)` and `h-(--size-control)`.

Tailwind 3 (`--tailwind 3`): both `:root` blocks, mapped in tailwind.config.js, for example
`colors: { surface: "var(--color-surface)" }`, with `screens` from the breakpoints.

Animations sit inside `@media (prefers-reduced-motion: no-preference)`.

## Fonts and icons

- `font.sans` in tokens.json (so `--font-sans`) holds: <the value forge-design Step 4 gives this profile>
- Font files and their licence file live in: <path>
- No font or icon CDN. After scaffolding, this search of the sources (binary files, dependencies
  and build output skipped) finds nothing:
  `grep -rnIE "fonts\.(bunny\.net|googleapis\.com|gstatic\.com)|use\.typekit\.net|kit\.fontawesome\.com|api\.iconify\.design" --exclude-dir=node_modules --exclude-dir=vendor --exclude-dir=.git --exclude-dir=forge-work --exclude-dir=.next --exclude-dir=dist --exclude-dir=build --exclude-dir=staticfiles .`

## Original brand colours

Clone mode only (idea mode: write none). Never used; listed for forge-brand's sweep: their accent,
a second brand colour, and the tinted colours their text, lines or backgrounds had.

- <#hex> (their accent)

## Components

One block per component, as in forge-design Step 5.
