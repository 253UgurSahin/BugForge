# The design part of /forge-design

A part of `/forge-design`. The ground rules, the levels and "show the result" live in
`../forge-design/SKILL.md` and in `../forge/rules.md` (sections 9 and 10): read them first.

This part decides what the app looks like. On the user's own app (a redesign, or the look picked
in `/forge-improve`) it also builds that look in, so the user sees a different app on their own
screen. For a new app (`/forge`, clone or idea mode) it ends with the concept the user picked and
the specs `/forge-build` builds from; the build then runs Judge and Show below. A plan or a report
alone is a failed run.

The order: read, level, three concepts, the brief, Steps 1 to 5 (the system), build, judge, show.

## What you never take

A system (colour roles, scales, how a form behaves) is not ownable. From another app you never
take (rules.md section 4) its logo, icons, pictures or sounds, nor a tracing of them; a font it pays
for; its copy; its files (CSS, SVG, images, anything from its domain or CDN); its brand colours.
Clone mode: list the original's colours under `## Original brand colours` in components.md, for
brand's sweep only. The signature colour plus the signature layout is trade dress.

## Read the app, and how it runs

- **A new app**: plan.md, and in clone mode recon.md and its screenshots (for sizes and layout
  only: the feel comes from the concept, never from the original's look).
- **The user's own app**: its screens, its words, its brand, its stack
  (`python3 ../forge-check/detect.py .`). Keep what is theirs and good: a logo, a colour, a voice.
- **What the user looks at** (own app, before any change, rules.md section 9): what serves their
  local URL (a dev server that reloads by itself, a built app, or containers); from which folder
  and branch (`git branch --show-current`, `git worktree list`); and whether a service worker or
  another cache sits in front. Write it under `## How it runs`, the first section of redesign.md.
  Cannot tell: ask one question, "How do you open the app, and at which address?"
- **A work branch in that same folder**, so their dev server shows the work: `git switch -c
  forge/redesign-<yyyymmdd>`, then `python3 ../forge/gitguard.py` must exit 0. Run the app's own
  tests and write the result: that is the proof that nothing breaks later.
- **Before shots** of every screen you will touch, from that URL, into
  `forge-work/design/shots/before` (`../forge-design/review.md`, section 1).

Then write `forge-work/design/world.md`, as `../forge-design/concepts.md` section 1 says.

## The level

Run `python3 ../forge/level.py get look`. It prints the level, such as `4 Showpiece`.

- A level in the user's request ("niveau 4", "showpiece", "level 5") is recorded at once:
  `python3 ../forge/level.py set look 4 --said '<their words>'`.
- Exit 1, no level yet: ask the one question of `../forge/levels.md` ("The one question"): "How
  far should I go with the look?", the lines `python3 ../forge/level.py show look` prints (`--nl`
  in Dutch), and where the examples are. Ask it in auto mode too, then record the answer the same way.
- Then do exactly what that level asks, never less and never more: a level 2 concept has no 3D.

What each level adds (`../forge/levels.md`):

| level | what the person sees | built with |
| --- | --- | --- |
| 1 Subtle (Subtiel) | One clean, consistent design. Every button, link and field reacts to hover, focus and press. Things fade in and out. | CSS only |
| 2 Polished (Verzorgd) | + content arrives piece by piece, pages change with a transition, numbers count up, an outline of the page shows while it loads, messages and dialogs move in and out, a small reaction on every control | CSS, View Transitions, the Web Animations API |
| 3 Expressive (Expressief) | + the page tells a story as you scroll, springy movement, charts that draw themselves and change shape, real depth (cards that tilt, panels in layers, perspective), one signature moment built for this app only | + CSS 3D and scroll-driven animation; `scenes/depth.js` |
| 4 Showpiece | + a living 3D scene at the top, made for what this app is about, light and depth that follow the pointer, 3D inside the screens, depth while scrolling | + Three.js (installed locally), the scene kit |
| 5 Cinematic (Cinematisch) | + a 3D journey driven by scrolling, custom shaders and particles on the graphics card, forms that react to the pointer and to the app's live data, screens that change in 3D space | + the whole scene kit, composed |

Here the level shapes the concepts and the specs: the control states (1), what arrives and how
(2), the signature moment and the depth (3), the scene the concept becomes (4,
`../forge-design/scenes.md`), the journey's chapters (5). The motion and 3D are built with
`../forge-design/steps/motion.md`: in `/forge`'s motion phase, or right after Build for the whole
look. Write `Level: N (Name)` in the brief and in redesign.md.

## Three concepts

Follow `../forge-design/concepts.md` from start to end: three concepts from the app's own world
that really differ, each built as a small moving preview of the app's main screen with its real
words, under `forge-work/design/concepts/a/`, `b/` and `c/`, on one board page made from
`../forge-design/concepts.example.html`. Check the board, then tell the user its full path, how to
open it, and give them the screenshot `forge-work/design/concepts/board.png`. Ask one question: "Which
one: A, B or C, or a mix?"

Stop and wait for the answer. This stop holds in auto mode: taste is the user's, and a look is
costly to undo. Nothing below starts before the choice.

## The brief

Copy `../forge-design/brief.md` to `forge-work/design/brief.md` and fill it in from the chosen
concept: the `Concept:` line with the user's own words, the `Level:` line, then who uses the app,
type, colour, density, shape, the signature and what it stays away from ("The generic look" in
`../forge-design/review.md`). Every later choice is tested against the brief; a choice with no
reason in it is a default: change it. From here on, no more questions about taste.

## Step 1: measure, do not guess

Colours read off a screenshot by eye are guesses: `python3 ../forge-design/eyedropper.py
forge-work/design/shots/before/home-1440-light.png` lists the colours used most and where, `--box
x,y,w,h` those in one part, `x,y` one pixel. The user's own app: write what you find (colours, sizes,
radii, fonts, with how often) under `## Before` in redesign.md. Clone mode: recon's shots give sizes
and layout. Idea mode: the concept and plan.md. Values you estimate go under `_notes` in tokens.json.

- **Colour roles**, not colours: bg, surface, border, border-input, text, text-muted, accent,
  on-accent, danger, success, warning. Usually 5 to 7 greys.
- **Type scale**: sizes, line heights, weights, snapped to a scale (12, 14, 16, 20, 28, 40 is
  common), with the contrast between display and text the brief asks for.
- **Spacing** (a 4 or 8 base), **radius, shadow, motion** (two or three of each); **layout**:
  content width, grid, breakpoints, sidebar, header; **sizes**: borders, focus ring, icons, controls.
- **Dark theme**: when the concept has one, the app already has one, or the user asks for it.

## Step 2: write the tokens and check the contrast

Copy `../forge-design/tokens.json` to `forge-work/design/tokens.json` and fill in the values from
the concept. Keep the role names: brand changes values only. A dark theme is a `dark` group inside
`color` (`"dark": {"bg": "#0b0d10", "text": "#e6e8eb"}`); its colours are then `dark-bg` and
`dark-text`. Clone mode: the accent comes from another colour family than the original's, and no
other role takes one of the original's brand colours.

List every foreground and background combination the app uses under `pairs`, dark ones included,
with the kind as third item when it is not normal text: `large` (24px and up, or 18.66px bold) or
`ui` (input borders, icons, focus rings). Every text colour (`text`, `fg` or `on` in its name)
must be in a pair; disabled text is left out, as WCAG asks nothing of it. Dividers and card
borders are decoration and need no pair. Then run
`python3 ../forge-design/contrast.py forge-work/design/tokens.json`.

WCAG AA is the floor: 4.5:1 for normal text, 3:1 for large text and UI parts (what the European
Accessibility Act points to for most web shops; not legal advice). Exit 1: a pair fails (the output
names the nearest passing colour) or a text colour is in no pair; fix it in the tokens, never per
component. Exit 2: the file is wrong (the output says how). The gate runs it too.

## Step 3: the theme, per profile

tokens.json is the only place values live: `../forge-design/theme.py` writes the app's theme file
from it (`--tailwind 4|3|no`, `--write FILE`), and whoever changes tokens.json later runs it and
contrast.py again. The profile is `Profile:` in plan.md, or what detect.py said:

| Profile | Theme file | Tailwind |
|---|---|---|
| laravel | `resources/css/app.css` | yes: the skeleton and the starter kits come with it |
| django | `static/css/tokens.css`, linked in `base.html` before other CSS | no, unless plan.md says so |
| next | `app/globals.css` (`src/app/` when the project uses `src/`) | yes: create-next-app sets it up |
| static | the CSS file `src/main.*` imports (`src/style.css` or `src/index.css`) | no, unless plan.md says so |

The user's own app: its own style entry (its Tailwind config, its main CSS file), and the Tailwind
major version from its package.json. Copy `../forge-design/components.md` to
`forge-work/design/components.md` and fill in its header, theme file and theme.py command. Its
`## Theme` maps every token group to a CSS variable by name, never by value. With `PWA: yes`, the
manifest's `theme_color` and `background_color` and the `theme-color` meta tag take token values.

## Step 4: fonts and icons

- **Font**: the open fonts of the concept (SIL Open Font License or alike), self-hosted with the
  licence file; read the licence of the files you install. A font CDN sends every visitor's IP
  address to a third party (AVG/GDPR). How each profile loads it: `../forge-design/fonts.md`.
- **Icons**: one set for the whole app, with its licence: Lucide (ISC), Heroicons (MIT) or Tabler
  Icons (MIT), as its package or as SVG files in the repo with the licence file.
- **No font or icon CDN.** components.md carries the search that must find none after scaffolding.

## Step 5: component specs

For every component in recon.md's list (idea mode: what the screens in plan.md need; the user's
own app: what its screens use, the most used first), one block:

```
Button
  variants  primary, secondary, ghost, danger
  sizes     sm 32px, md 40px, lg 48px
  states    default, hover, active, focus-visible (2px ring, accent), disabled, loading
  motion    hover lift 2px, press scale 0.98, duration fast (from level 1)
  tokens    bg accent, text on-accent, radius md, type sm/600
  a11y      real <button>, visible focus, loading keeps the label for screen readers
  used on   S02, S07, S09
```

Every state the screens show, plus focus, disabled, loading, error and empty; keyboard and screen
reader behaviour is part of the spec. Targets are at least 24 by 24px (WCAG 2.2 AA), 44px for the
main actions on mobile. Build on the stack's accessible component base if it has one (shadcn/ui in
Laravel's React starter kit), else native elements.

## Build

- **A new app**: nothing is built here: go to the checkpoint. `/forge-build` builds the components
  first, on a `/design` page, then the screens.
- **The user's own app**: say at the start what will happen, in which order and roughly how long.
  Then the theme first: the tokens as CSS variables in the app's own style entry, old values
  replaced by variables, one commit. Then one component per commit, the most used first, then
  screen by screen. Write each old value and the token that replaces it under `## Mapping` in
  redesign.md, and each commit under `## Changed`. No markup or logic change unless a component needs
  it for accessibility, and then a test covers it. The app's tests pass after each commit, and
  `python3 ../forge-check/secretscan.py .` exits 0 before it (rules.md section 5).
- **Progress**: when the first screen is done, show it before and after (a shot of that screen
  now, next to its before shot); then one line per finished screen.
- **The whole look**: when the screens are done, go straight on with
  `../forge-design/steps/motion.md` at the same level, then `../forge-design/steps/dashboard.md`
  where the app has data screens. No new questions about taste: the brief decides. Judge and Show
  below then cover the whole look, once.

## Judge with fresh eyes

Take shots of the app as it is now. When the session has an Agent or Task tool, a separate
subagent judges them: give it only the screenshots, the brief and the generic-look list, and ask
for scores and the three weakest things per screen (`../forge-design/review.md` has what to send
it). No such tool: score them yourself with the rubric there. Fix in the tokens or the component,
never per screen, and go again: up to three rounds, in `forge-work/design/review.md`.

## Show

Rules.md section 9, step by step, for the user's own app (a new app: `/forge-build` does this with
the address it serves the app on):

1. **Make it show.** Say which branch the work is on. You worked in the folder their server runs
   from, so a dev server shows it; a built app or containers: rebuild and restart them. A service
   worker: say whether it is active, and bump its cache when it holds old files. Load the URL yourself.
2. **After shots** with the same command, paths and flags as the before shots, into
   `forge-work/design/shots/after`. Then `python3 ../forge-design/changed.py
   forge-work/design/shots/before forge-work/design/shots/after` must exit 0 (VISIBLE CHANGE).
   Exit 1: find which reason of rules.md section 9 it is, fix that, take the shots again. Exit 2
   is never a pass.
3. **Movement.** On screens that should move, frames and a clip (`--frames --video`, review.md
   section 1), and `python3 ../forge-design/changed.py --moves` on each screen's frames must exit 0.
   Write the results under `## Proof` in redesign.md.
4. **Hand over** in plain words: the branch; the address that shows it now; where to click, in
   order, to see the best moment first; that a system set to reduced motion shows the calm
   version, and how to check that setting; the paths of the before and after images and the clip;
   how to go back (`git switch <their branch>`). Merging and deploying stay their step.

## Output

`forge-work/design/brief.md` from its template with every `{{...}}` filled in; `tokens.json`, on
which contrast.py exits 0; and `components.md` from the template with every `<...>` filled in, but
those in the `## Theme` code block (it is the mapping), for example `Profile: next. Tailwind: 4.
Font: Inter (SIL OFL, Fontsource with next/font/local). Icons: Lucide (ISC), as a package.` In clone
mode, its `## Original brand colours` lists the original's colours for brand's sweep only. Also
`world.md`, `concepts/` with `board.png`, and `review.md` once the app is judged. The user's own
app adds `forge-work/design/redesign.md`, in the form `../forge-design/review.md` gives
("The redesign report"). `python3 ../forge/level.py check look --report forge-work/design/brief.md`
must exit 0.

## Next

Checkpoint, at most 5 plain lines. A new app: the concept picked, the palette, the font and icon
set with their licences, how many components are specced, the contrast result; then `/forge-build`.
The user's own app: the hand-over of Show, the review's last scores and what is left; then
`/forge-check test`. Wait for the user's go. Back to `/forge` or `/forge-improve` when it started there.
