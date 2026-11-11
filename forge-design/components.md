# Design

Profile: <laravel|django|next|static>. Tailwind: <4|3|no>.
Font: <name> (<licence>, <Fontsource | Fontsource with next/font/local | laravel-vite-plugin fonts with fontsource() | files in static/fonts/>).
Icons: <the app's own set | Lucide (ISC) | Heroicons (MIT) | Tabler Icons (MIT)>, as <its own components | package | SVG files in the repo>.

## Theme

File: <the theme file for the profile, from forge-design design Step 3>
Command: python3 ../forge-design/theme.py forge-work/design/tokens.json --tailwind <4|3|no> --default system --write <the file above>

<!-- The theme file and Tailwind per profile, for a new app (the user's own app: its own style entry):
     laravel: resources/css/app.css; Tailwind yes, as the skeleton and the starter kits come with it.
     django: static/css/tokens.css, linked in base.html before other CSS; no Tailwind unless plan.md says so.
     next: app/globals.css (src/app/ with src/), imported in app/layout.tsx; Pages Router: the CSS file
     pages/_app.tsx imports (often styles/globals.css); Tailwind yes, as create-next-app sets it up.
     static: the CSS file src/main.* imports (src/style.css or src/index.css); no Tailwind unless plan.md says so. -->

Values live only in `forge-work/design/tokens.json`. The command above writes the file above from it
and follows the mapping below (names only, so it never goes stale). Once that file is written
(forge-build build, or design Build item 1 in the theme commit), run it again after any change to
tokens.json, then `python3 ../forge-design/contrast.py forge-work/design/tokens.json`; before that,
only design Step 6's copy for the specimen. Components use these variables, never raw hex or px.
`--default system` is the switch of design Step 3: `--default dark` or `--default light` when the
concept opens in that theme, `--dark-selector .dark` in its place when the app has a switch of its
own. It stays in the line, so every later run keeps it; with no dark group it does nothing.

```css
:root {                                     /* Tailwind 4: @theme static { }, see below */
  --color-<role>: <color.role>;             /* one line per colour role */
  --font-sans: <font.sans>;
  --font-mono: <font.mono>;
  --text-<step>: <size>px;                  /* three lines per type step */
  --text-<step>--line-height: <line>px;
  --text-<step>--font-weight: <weight>;
  --text-<step>--font-stretch: <stretch>;   /* only a step with stretch: 125 is 125% */
  --text-<step>--letter-spacing: <tracking>;  /* only a step with tracking: -0.02 is -0.02em */
  --space-<n>: <value>px;                   /* per space value, n = value / 4: --space-4 is 16px, --space-1_5 is 6px */
  --radius-<name>: <value>px;
  --shadow-<name>: <value>;
  --ease-standard: <motion.ease>;
}
:root {                                     /* a plain :root, with Tailwind 4 too */
  color-scheme: light;                      /* with a dark group */
  --duration-fast: <motion.fast>;
  --duration-base: <motion.base>;
  --layout-<name>: <value>px;               /* content, sidebar, header */
  --size-<name>: <value>px;                 /* borders, focus ring, icons, controls, a dialog */
}
@media (prefers-color-scheme: dark) {       /* only with a dark group; --default system, as here */
  :root:not([data-theme="light"]) {         /* --default light or dark: :root[data-theme="system"] */
    color-scheme: dark;
    --color-<role>: <color.dark.role>;
  }
}
:root[data-theme="dark"] { color-scheme: dark; --color-<role>: <color.dark.role>; }
/* Breakpoints go into media queries as numbers, @media (min-width: 768px): var() fails there. */
```

The switch: `data-theme` on `<html>` holds the person's choice, `light`, `dark` or `system`, and no
attribute means the concept's default. `--default dark` writes the dark colours where `data-theme`
is neither `light` nor `system`, and for `system` while the device is dark. `--dark-selector .dark`
writes them for `:root.dark` only, with no media query: the app's own switch (the Appearance setting
of Laravel's starter kits; next-themes, whose default is `'[data-theme="dark"]'` and shadcn's setting
`.dark`) sets it and works out "system" itself. With such a switch, a concept that opens dark changes
its default (the value it takes while nothing is stored, such as next-themes' `defaultTheme`), or
keeps it and has both themes designed as equals; the brief says which. Each theme sets
`color-scheme`, so form controls and scrollbars follow. A new switch keeps the choice where the app
keeps preferences (its settings or localStorage, one key such as `theme`; a new cookie only where
its cookie page allows one, and list it there or on its privacy page), and sets it before the first
paint with one inline script in `<head>` (or in the inline script the app already has), with the
nonce of the app's CSP when it has one (a React app rendered on the server, such as Next.js, also
needs `suppressHydrationWarning` on `<html>`: the script changes it before React hydrates):
`<script>try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark"||t==="system")document.documentElement.dataset.theme=t}catch(e){}</script>`.
The kit's scenes follow by themselves; a map or a chart that draws on a canvas reads its colours
again when `data-theme` changes. Write the key and its values here: the shots follow each still's
system setting with `--init-script forge-work/design/theme.js`, and `--storage KEY=VALUE` is for one
fixed theme only (`../forge-design/review.md` section 1).

Tints that mix tokens (`tint`, `tint-strong`, `scrim` in the template: hovers, wells, skeletons, a
dialog backdrop) are written once and follow the theme by themselves, as `--color-tint` and so on.

A theme that computes with its values needs them as literal values, from the same tokens: var()
breaks it. Bootstrap's Sass (`tint-color()`, `mix()`): `--write resources/sass/_tokens.scss`
(.scss picks `--format scss`), imported before Bootstrap, then `$primary: $color-accent;`. MUI,
Chakra or Mantine: `--write src/theme/tokens.ts`, a module the theme file imports
(`tokens.color.accent`, `tokens.color.dark.bg`). Add that run to the command above with `&&`; the
CSS variables stay for the app's own CSS.

Tailwind 4 (`--tailwind 4`): the first block is `@theme static { }`, right after
`@import "tailwindcss";`. It starts with `--color-*: initial;`, so only your roles exist
(`bg-surface`, `text-text-muted`), and has `--breakpoint-*: initial;` plus one `--breakpoint-` line
per breakpoint (`--breakpoint-md: 768px;`), so `md:` follows the measured breakpoints. It leaves out
`--space-*`: Tailwind's own 4px `--spacing` makes `p-4` 16px. `static` writes out every variable, so
the dark block works without `dark:` classes. Use the plain `:root` values as
`duration-(--duration-fast)`, `max-w-(--layout-content)` and `h-(--size-control)`. A `text-<step>`
class sets the size, line height, weight and letter spacing, not the stretch: a component sets
`font-stretch: var(--text-<step>--font-stretch)` itself. Type steps and radii that share a name with
Tailwind's own (`text-lg`, `text-xl`, `rounded-md`, `rounded-lg`) take the tokens' size, line
height and weight (and radius) at once, also on screens not yet redone: look at those screens in
the theme commit. Without
`--dark-selector`, the block ends with `@custom-variant dark` on the same switch, so the app's own
`dark:` classes (a logo swap `hidden dark:block`, `dark:invert`) follow the person's choice too; an
older `@custom-variant dark` line of the app's own is removed.

On an app that already has Tailwind classes this clears the rest: `bg-gray-100`, `text-white`,
`bg-black/80` and `2xl:` give no CSS any more, and `@apply bg-gray-100` stops the build. Each
becomes its role, or its breakpoint goes into tokens.json (Tailwind's own `2xl` is 1536), until this
search finds no class (a word in a URL or in prose may stay):
`grep -rnoIE "(\b(bg|text|border(-[trblxyse])?|ring(-offset)?|outline|divide|fill|stroke|from|via|to|shadow|accent|caret|decoration|placeholder)|--color)-(white|black|[a-z]+-[0-9]{2,3})\b" --exclude-dir=node_modules --exclude-dir=vendor --exclude-dir=.git --exclude-dir=forge-work --exclude-dir=.next --exclude-dir=dist --exclude-dir=build --exclude-dir=storage --exclude-dir=staticfiles .`

Tailwind 3 (`--tailwind 3`): both `:root` blocks, mapped in tailwind.config.js, for example
`colors: { surface: "var(--color-surface)" }`, with `screens` from the breakpoints. Without
`--dark-selector`, the block holds a comment with the `darkMode` line for that file (it starts
`/* tailwind.config.js`), so `dark:` classes follow the same switch (Tailwind 3.4.1 and later;
before that, they keep following the device).

Animations sit inside `@media (prefers-reduced-motion: no-preference)`.

## Fonts and icons

- `font.sans` in tokens.json (so `--font-sans`) holds: <the value forge-design design Step 4 gives this profile>
- Font files and their licence file live in: <path>
- No font or icon CDN. After scaffolding, this search of the sources (binary files, dependencies
  and build output skipped) finds nothing; `next/font/google` counts too: it fetches the font from
  Google at build time, with no address in the source:
  `grep -rnIE "fonts\.(bunny\.net|googleapis\.com|gstatic\.com)|use\.typekit\.net|kit\.fontawesome\.com|api\.iconify\.design|next/font/google" --exclude-dir=node_modules --exclude-dir=vendor --exclude-dir=.git --exclude-dir=forge-work --exclude-dir=.next --exclude-dir=dist --exclude-dir=build --exclude-dir=staticfiles .`

## Original brand colours

Clone mode only (idea mode: write none). Never used; listed for forge-design brand's sweep: their accent,
a second brand colour, and the tinted colours their text, lines or backgrounds had.

- <#hex> (their accent)

## Components

One block per component, or per kind (every button in one), as in forge-design design Step 5; on
the user's own app each with its `files` line: where it lives, by every name it goes by. A size
relative to its container has a floor, checked where the component is smallest (`max(16%, 96px)`).
A row of the shell (header, rail, tab bar) gives its width and every control in it, so the specimen
of Step 6 draws it at that width.
