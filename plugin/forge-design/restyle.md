# Restyle an app that exists

How the design part builds the picked look into the user's own app: the method behind the Build step
of `../forge-design/steps/design.md`. The work happens in the folder their dev server runs from, so
each commit shows on their own screen as it lands. Each old value and its token go under
`## Mapping` in redesign.md, each commit under `## Changed`.

## 1. The order, one commit per step

1. **The theme**: the tokens as CSS variables, and every old value in the app replaced (section 2).
   Then **the fonts** of design Step 4 in a commit of their own, with all they change: the font
   package or files and their licence, `package.json` and the lockfile, where they load
   (`next/font/local` in `app/layout.tsx`, an `@font-face`); nothing of it may stay uncommitted.
2. **Components**, one per commit, the most used first (section 4).
3. **One left edge** for every page column (section 5).
4. **Screens**, one at a time, the most used first, with the shells several screens share first
   (section 6).

After each screen, the checks of section 8; each commit through `../forge-design/commit.py`
(section 9).

## 2. The theme commit: by name, then by role and context, with a log you read

On a big app the old values are everywhere: inline style objects, a global stylesheet of thousands
of lines, colour constants in code. The same `#fff` is a panel, a dialog, a field, a label on the
accent or text on a dark band, so a rename by value is wrong half the time. Map each place by the
role of its property (background, text, border, shadow, icon) and by what is around it (a strong
fill next to it, something that floats, a field), and read what changed.

1. **The inventory**, from the project root: `python3 ../forge-design/retheme.py`. Every old
   colour variable, raw colour (hex, `rgb()`, `hsl()`, `oklch()` as in shadcn/ui, `lab()`, `hwb()`,
   `color()`) and Tailwind colour class in the committed files, with how often it plays which role
   and in which context, and the first place. Roles the script cannot name show as `other(NAME)`:
   the app's own property names (an icon's `c=`, a Dutch `kleur`).
2. **The map**: write `forge-work/design/retheme.json` (section 3) from the inventory and the brief.
3. **A dry run**: `python3 ../forge-design/retheme.py --map forge-work/design/retheme.json`. Read
   `forge-work/design/retheme.log`: one line per change, `file:line [rule] property: old -> new
   (role)`. Thousands of lines are read per token and per context: `grep "on-fill"`, `grep
   "float"`, `grep -- "-> var(--color-surface)"`. Fix the map, not the files, and run it again: it
   always starts from the committed files, so nothing compounds. Exit 0 only when nothing is LEFT
   (a place the map does not cover, or a token it names that `tokens.json` does not have), SPLIT or
   KEPT.
4. **Write it**: the same command with `--write`, then theme.py (Step 3's command), in that order:
   retheme.py leaves a file alone once something else changed it (KEPT: theme.py's block, a hand
   edit); `--force` starts such a file again from the commit, and theme.py then runs again. After
   the theme commit a run reads theme.py's block as the tokens it is, so it lists only what is old.
5. **The hand pass**, for what the log shows wrong and what a script cannot see: helpers that
   compute colours (`mix()`, `shade()`, a palette object: note under `## Mapping` the name of each
   function that takes or returns a colour, for section 4's search), colours built from strings,
   and the old definitions (`:root { --ink: #14181a }`), which go: theme.py's block holds the new
   ones, and nothing may set a colour twice.
6. **Look before the commit**: the main screens in both themes, text on its own background
   everywhere (no dark on dark, no white band left over).

**A constant used in more than one role** (the landing's `W = "#fff"` as a background and as text)
breaks when its value is re-pointed: as the panel tone it made the closing headline dark on dark.
Split it into one constant per role and map each; never change its value. retheme.py names each one
as SPLIT and leaves it alone: it reads the uses in the constant's own file and, for one that is
exported, in every script that imports it (`import { W }`, or `import * as colors` and `colors.W`);
an exported one with no use it can read is SPLIT too, so check it by hand. One used in one role
only is mapped by it.

**What stays a literal colour.** `var()` works only where the page's CSS applies, and not where code
computes with the value. These keep a real colour from tokens.json, one per theme, written by hand
(retheme.py lists them as LITERAL):

- the `theme-color` meta: one per theme, `<meta name="theme-color" media="(prefers-color-scheme:
  dark)" content="#0b1214">` and the light one (Next: `viewport.themeColor` as a list of `{ media,
  color }`); with the app's own switch the theme script also sets its `content` when it sets
  `data-theme`. `var(--color-accent)` there is ignored by every browser;
- the web manifest (`theme_color`, `background_color`: the default theme's), an OG image drawn by
  Satori (`next/og`), Next's `global-error` page (it renders without the app's CSS);
- e-mails, as mail clients drop `var()`: a mail folder (`emails/`, `app/Mail/`, `user_mailer/`), a
  file named for mail (`lib/server/mail.ts`, `mailer.js`; a page such as `verify-email.blade.php`
  or `EmailInput.tsx` is no e-mail) and a file that imports nodemailer or react-email;
- a canvas or a map style: read the variable with `getComputedStyle` when it draws, and again when
  `data-theme` changes. retheme.py keeps the raw colours of a file that imports Chart.js or
  ECharts (its classes still follow the theme), and a constant a canvas draws with
  (`ctx.fillStyle = DOT`; one also used in a style is SPLIT);
- a theme that computes with its values: Sass and Less variables (`$primary: #0d6efd`, a
  `$theme-colors` map, `@brand`; also in a component's `<style lang="scss">`), and a JS theme
  (`createTheme`, `extendTheme`, `createSystem`, `createVuetify`, a Mantine theme object:
  retheme.py keeps every colour of such a file).
  `../forge-design/components.md`, the paragraph "A theme that computes with its values", says what
  goes there (`$primary: $color-accent;`, `tokens.color.accent`). Where nothing computes with a
  Sass variable, `var(--color-accent)` lets it follow the theme;
- a colour handed to a function, `mix(#fff, $ink, 10%)`, `darken()`, MUI's `alpha()`,
  `new THREE.Color()`, or inside `url("data:image/svg+xml,...")`: give it the token's value.

Check the served page: `curl -s <URL> | grep -io '<meta name="theme-color"[^>]*>'` shows a colour.

**Tailwind 4** (`--tailwind 4`): theme.py's `@theme` block starts with `--color-*: initial` and
`--breakpoint-*: initial`, so from the theme commit on Tailwind's own colours and breakpoints are
gone: `bg-gray-100`, `text-white`, `bg-black/80` and `2xl:` give no CSS, and `@apply bg-gray-100`
stops the build. So this same commit turns every colour class into its role, until the search under
`## Theme` in components.md finds none. retheme.py does it with the map's colours, in an app whose CSS
loads Tailwind only (Bootstrap has a `bg-white` of its own, and keeps it): `bg-gray-100` to
`bg-surface`, `text-white` in a class list with a strong fill (`bg-blue-600`, mapped to the accent)
to the `text on-fill` entry; it drops `dark:` colour classes, as the tokens switch by themselves.
Every breakpoint the app uses goes into the `breakpoint` group of tokens.json (Tailwind's own `2xl`
is 1536). The app's own colour names in its old `@theme` (`bg-brand`) are mapped by hand. Else every
screen not yet redone loses its colours on the user's screen at once.

## 3. The map

```json
{
  "vars": {"--ac": "--color-accent", "--ink": "--color-text",
           "--line": {"border": "--color-border", "bg": "--color-tint-strong"}},
  "colours": {
    "#fff": {"bg": "--color-surface", "bg float": "--color-raised", "bg field": "--color-field",
             "text": "--color-text", "text on-fill": "--color-on-accent", "icon": "currentColor"},
    "rgba(20,24,26,.06)": "--color-tint",
    "gray-100": {"bg": "--color-surface", "border": "--color-border"}
  },
  "props": {"c": "icon", "kleur": "text"},
  "words": {"float": ["lade", "kiezer"], "field": ["veld"]},
  "keep": ["#d9552b"],
  "skip": ["app/opengraph-image.tsx", "components/illustrations/"]
}
```

- `vars`: an old variable to its token by name; one that plays two roles gets one per role.
- `colours`: a colour in any spelling (`#fff`, `white`, `rgb(255 255 255)`) or a Tailwind colour
  name (`gray-100`) to a token, or one per role and context. A key is a role (`bg`, `text`,
  `border`, `shadow`, `icon`, `other`), a role and a flag (`text on-fill`, `bg float`, `bg field`),
  or `*` for any role; the most exact one wins. A colour with alpha takes its own entry, or its
  colour's token mixed: `color-mix(in srgb, var(--color-surface) 70%, transparent)`.
- A value that is not a token (`currentColor`, `transparent`) is written as it is. A Tailwind class
  takes the role's name: `--color-surface` gives `bg-surface`. Each token the map names is a colour
  of `forge-work/design/tokens.json` (theme.py writes `--color-<name>` for each): add one such as
  `raised` or `field` there first, with its pairs. A name nothing sets (`--tint-2`) makes its places
  lose their colour, so retheme.py leaves such places LEFT.
- `props`: the role of the app's own property names (the inventory's `other(NAME)`).
- `words`: the app's own words for what floats and for a field, on top of the English ones (menu,
  dialog, popover, toast, dropdown, drawer; input, select, field, search).
- `keep`: colours that stay (an illustration's own); `skip`: files and folders it leaves alone.

## 4. Components

One per commit, the most used first; components.md's `files` line names every place it lives.

- **Class families**: when one component is many old class families (`.btn-*`, `.knop-*`,
  `.actie-knop`), give it one rule block at the end of the style entry that the old classes join,
  `:is(.btn, .knop, .actie-knop) { ... }`, or rename them to the new class in the markup. `:is()`
  takes the weight of its heaviest member: keep the members single classes. An old `!important`
  beats the new block, hover and focus too: `grep -n "!important"` in the style entry, and remove
  the ones of this component in its commit.
- **The accent** stays where the brief puts it: the main action, the current place, links, focus
  and the signature. Per component, and again per screen, search its token, its Tailwind classes
  and the app's own helpers that tint it: the functions that take or return a colour, which the
  hand pass of section 2 noted. On `.`, with the excludes of the search under `## Theme` in
  components.md:
  `grep -rnE "color-accent|(bg|text|border|ring|outline|fill|stroke|from|via|to|shadow|decoration)-accent\b|(^|[^-])mix\(|<helper>\("`,
  one `|<helper>\(` per helper (the trial app's: `|soft\(|deep\(`); `(^|[^-])` leaves out the
  `color-mix(` of theme.py's tints. Glows, gradients on a headline, ripples and icon wells move to
  a neutral (`text-muted`, `border`) or a line, or to a second accent only when the brief names
  one; icon wells are neutral.

## 5. One left edge

Before the screens, put every page column on the brief's left edge: one shared width and gutter
(`--layout-content`), not each page centring its own width (titles that start at 276, 318 and 458 px
at 1440 look like three apps). Check it on three screens at 1440: the `left` of their page title
(`getBoundingClientRect().left` in the browser) is one number, and two of their stills side by side
(`python3 ../forge-design/changed.py --two-up OUT.png A.png B.png`) start at the same x.

## 6. Screens and shells

- **One screen at a time**, the most used first: finish one, commit it, then start the next.
- **Its rules in a block of their own** at the end of the style entry, so later rules win and a
  commit can take or leave them: `/* forge: screen S10 Overzicht */` up to `/* forge: end screen
  S10 Overzicht */`. (A file per screen imported at the top of the entry loses to the old rules
  below it.) In a Tailwind app the screen's own files hold its look.
- **A component fix found during a screen** gets its own commit first, without the screen's block:
  `commit.py --without "app/globals.css:screen S10 Overzicht"` (section 9).
- **A shell several screens share** (one auth layout for sign-in and sign-up, one settings section,
  one layout for every text page): one commit that names every screen it changes; then look at each
  of them. The next commits hold what is one screen's own.
- **A scene in the composition** (a hero, a head, a side panel): build its container now at its
  real size, with its still: a poster taken from the picked preview at that size (as
  `../forge-design/scenes.md` section 2 says, "The poster"), or a still the app draws from the
  screen's own data. It is the reduced-motion and no-WebGL state anyway, so no reviewer sees an
  empty half; the motion part mounts the live scene on it (scenes.md section 5).

## 7. What may change

The markup, as far as the picked concept and the level need: classes (in a Tailwind app the look
lives there), wrappers, the order and grouping of elements, a hero, the layout the picked preview
shows, a scene's container with its still. Never what the app does: routes, links, form fields and
their names, handlers, data, and the text its tests look for. Every control, link and action stays;
what only decorates may go (a glow, a blob, a frame the concept does not have).

- **Words** the composition needs (a label over the last catch, an empty-state line, a caption) may
  be added, in the app's own content files, in every language it has and in its voice; list them
  under `## Changed`. A visual that could be read as data the app does not have gets a caption that
  says so: a depth chart drawn from a water's outline says it has no measured depths ("Geen gemeten
  diepte").
- **A change for accessibility** (an `aria-current`, a label, the focus order) gets a test: in the
  app's own UI tests when it has them. With server tests only: a small Playwright script in
  `forge-work/design/checks/` (Playwright as `../forge-design/review.md` section 1 installs it) that
  loads the screen with the state file, checks the attribute and exits 1 when it is missing, run as
  a `--check` of each commit; the walk of `/forge-check test` (axe on every page,
  `../forge-check/walkcheck.py`) covers it for good later. Say which under `## Changed`.

## 8. After each screen, and the progress image

- Make it show first (design Show, item 1; in Laravel with no `public/hot`, `npm run build`).
- **Its stills and the sideways check**, in one run with the before shots' flags (`--state`,
  `--init-script`) and the screen's paths, into a folder of its own, never `before` (shots.mjs
  writes over what is there): `node forge-work/design/shots.mjs <URL>
  forge-work/design/shots/check --overflow <the before shots' flags> <its paths>`. It takes 390 and
  1440 in both themes: look at each still. It must exit 0 with no line `wide` (a grid rule without
  its media query pushes a phone form off the screen).
- The served `theme-color` is still a colour (section 2), and the accent check of section 4.
- An error right after a save (a hydration error, a missing module) is often the dev server still
  compiling: reload once, and chase it only when it comes back.
- **Progress**, once the shell is done: the main screen before and after in one image, shown to the
  user. `node forge-work/design/shots.mjs <URL> forge-work/design/shots/progress --width 1440 <the
  before shots' flags> <main path>`, then `python3 ../forge-design/changed.py --two-up
  forge-work/design/shots/progress/<name>-two-up.png forge-work/design/shots/before/<name>-1440-light.png
  forge-work/design/shots/progress/<name>-1440-light.png` (`-dark` for an app that shows dark).
  After that, one line per screen.

## 9. The commit

`python3 ../forge-design/commit.py -m "style: S10 Overzicht" --check "npm test" app/page.tsx
app/globals.css` runs each `--check` (the app's tests, its typecheck: what `Tests before:` in
redesign.md ran), then `../forge/gitguard.py` and `../forge-check/secretscan.py`, and commits only
the files named; `--without FILE:NAME` leaves a block out for a later commit, `--no-check` is for an
app with no tests at all. With `Tests before: not run (the user's call)` (testdb.py exit 1 and no
go), `--check` is the typecheck or the build, never the tests. A path in `forge-work/` or a file
staged before is refused. Run it from the app's folder (in a monorepo, `apps/web`). The message says
what changed on which screen; one line per commit goes under `## Changed`.
