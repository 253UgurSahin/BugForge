# The design part of /forge-design

A part of `/forge-design`. The ground rules, the levels and "show the result" live in
`../forge-design/SKILL.md` and in `../forge/rules.md` (sections 9 and 10): read them first.

This part decides what the app looks like. On the user's own app (a redesign, or the look picked
in `/forge-improve`) it also builds that look in, so the user sees a different app on their own
screen. A new app (`/forge`, clone or idea mode): it ends with the picked concept and the specs
`/forge-build` builds from, which then runs Judge and Show below. A plan or report alone is a failed
run. The order: read, level, three concepts, the brief, Steps 1 to 5 (the system), build, judge, show.

## What you never take

A system (colour roles, scales, how a form behaves) is not ownable. From another app you never take
(rules.md section 4) its logo, icons, pictures, sounds or a tracing of them; a font it pays for; its
copy; its files (anything from its domain or CDN); its brand colours. Clone mode: list those colours
under `## Original brand colours` in components.md, for brand's sweep only.

## Read the app, and how it runs

- **Say the plan first** (own app), in three lines, before you read anything: what you will do, in
  which order, about how long until they see three previews, and that the app itself changes only
  after they pick one.
- **A new app**: plan.md; clone mode also recon.md and its shots (sizes and layout only). **The
  user's own app**: its screens, words, brand and stack (`python3 ../forge-check/detect.py .`).
  Keep what is theirs and good: a logo, a colour, a voice.
- **What the user looks at** (own app, before any change, rules.md section 9): what serves their
  local URL (a dev server that reloads by itself, a built app, or containers); from which folder
  and branch (`git branch --show-current`, `git worktree list`); and whether a service worker or
  another cache sits in front. Write it under `## How it runs`, the first section of redesign.md.
  Cannot tell: ask one question, "How do you open the app, and at which address?"
- **A work branch in that same folder**, so their dev server shows the work: `git switch -c
  forge/redesign-<yyyymmdd>`; `python3 ../forge/gitguard.py` must exit 0. Before the first install
  or commit, add the line `forge-work/` to the file `git rev-parse --git-path info/exclude` names
  (local only, no file of theirs changes): no node_modules, shot or sign-in file is ever committed.
  Run the app's own tests and write the result: the proof that nothing breaks.
- **Before shots** of every screen you will touch (for the whole look: the data screens too), from
  that URL, into `forge-work/design/shots/before` (`../forge-design/review.md`, section 1; screens
  behind a sign-in: the state file that section names, never a login page in place of the screen).

Then write `forge-work/design/world.md`, as `../forge-design/concepts.md` section 1 says.

## The level

- `python3 ../forge/level.py get look` prints the level on record, such as `4 Showpiece`.
- A level in the user's request ("niveau 4", "showpiece", "level 5") is recorded at once:
  `python3 ../forge/level.py set look 4 --said '<their words>'`. For the whole look on an app with
  data screens, a level with no part named counts for the dashboard too: also run
  `python3 ../forge/level.py set dashboard 4 --said '<the same words>'`, and tell the user in one
  line that the dashboard follows the same level unless they name another.
- Exit 1, no level yet: ask the one question of `../forge/levels.md` ("The one question"), also in
  auto mode, then record the answer the same way.
- Then do exactly what that level asks (the look table of levels.md), never less and never more.

The level shapes the concepts and the specs: the control states (1), what arrives and how (2),
the signature moment and real depth in CSS 3D (3: perspective, rotateX/rotateY and preserve-3d on
cards and panels, `../forge-design/motion.md` section 8), the scene the concept becomes (4), the
journey's chapters (5). The kit scene per kind of concept: water, a lake or a sea: `aurora.js`,
mode `water`; places, depth or height: `contour.js`; a crowd, a flow or numbers: `field.js`; an
object, a tool or a craft: `form.js`. Their options are the comment at the top of each file (next
to `../forge-design/scenes/stage.js`); the mount in a plain page, React and Next is motion.md
section 9. Motion and 3D are built with `../forge-design/steps/motion.md`, in `/forge`'s motion
phase or right after Build for the whole look. Write `Level: N (Name)` in the brief and redesign.md.

## Three concepts

Follow `../forge-design/concepts.md` from start to end: three concepts from the app's own world,
each a small moving preview of the app's main screen with its real words, under
`forge-work/design/concepts/a/`, `b/` and `c/`, on one board made from
`../forge-design/concepts.example.html`. Check the board, tell the user how to open it, give them
`forge-work/design/concepts/board.png`, and ask one question: "Which one: A, B or C, or a mix?"

**From level 4 the board needs a server**: a browser refuses module scripts (three, the kit) from
a double-clicked file. Install three into the concepts folder only (`npm install --prefix
forge-work/design/concepts three`), copy `stage.js`, `glsl.js`, `lazy.js` and the scenes you use
into `forge-work/design/concepts/kit/`, and give each preview the import map `{"imports": {"three":
"/node_modules/three/build/three.module.js"}}` and `import ... from "../kit/lazy.js"`: each preview
stays one page. Serve in the background: `python3 -m http.server --bind 127.0.0.1 <free port> -d
forge-work/design/concepts`. Check the board and take `board.png` through that address, and give
the user `http://127.0.0.1:<port>/`, not the file path. Stop the server after the pick.

Stop and wait for the answer. This stop holds in auto mode: taste is the user's, and a look is
costly to undo. Nothing below starts before the choice.

## The brief

Copy `../forge-design/brief.md` to `forge-work/design/brief.md` and fill it in from the chosen
concept: `Concept:` with the user's own words, `Level:`, who uses the app, type, colour, density,
shape, the signature and what it stays away from ("The generic look" in review.md). Every later
choice is tested against it; one with no reason in it is a default: change it. No more taste questions.

## Step 1: measure, do not guess

Colours read by eye are guesses: `python3 ../forge-design/eyedropper.py
forge-work/design/shots/before/home-1440-light.png` lists the colours used most and where (`--box
x,y,w,h` one part, `x,y` one pixel). Own app: what you find (colours, sizes, radii, fonts, how
often) goes under `## Before` in redesign.md. Clone mode: recon's shots give sizes and layout; idea
mode: the concept and plan.md. Estimated values go under `_notes` in tokens.json.

- **Colour roles**, not colours: bg, surface, border, border-input, text, text-muted, accent,
  on-accent, danger, success, warning. Usually 5 to 7 greys.
- **Type scale**: sizes, line heights, weights, snapped to a scale (12, 14, 16, 20, 28, 40).
- **Spacing** (a 4 or 8 base), **radius, shadow, motion** (two or three of each); **layout**;
  **sizes** (borders, focus ring, icons, controls); a **dark theme** when the concept, the app or
  the user has one.

## Step 2: write the tokens and check the contrast

Copy `../forge-design/tokens.json` to `forge-work/design/tokens.json` and fill in the values from
the concept; keep the role names. A dark theme is a `dark` group inside `color` (`"dark": {"bg":
"#0b0d10"}` gives `dark-bg`). Clone mode: the accent is from another colour family than the
original's, and no role takes one of its brand colours.

List every foreground and background combination the app uses under `pairs`, dark ones included,
with the kind as third item when it is not normal text: `large` (24px and up, or 18.66px bold) or
`ui` (input borders, icons, focus rings). Every text colour (`text`, `fg` or `on` in its name) is
in a pair; disabled text, dividers and card borders need none. Then run
`python3 ../forge-design/contrast.py forge-work/design/tokens.json`. WCAG AA is the floor: 4.5:1
for normal text, 3:1 for large text and UI parts. Exit 1: a pair fails (the output names the
nearest passing colour) or a text colour is in no pair; fix it in the tokens, never per component.
Exit 2: the file is wrong (the output says how). The gate runs it too.

## Step 3: the theme, per profile

Values live only in tokens.json: `../forge-design/theme.py` writes the theme file from it
(`--tailwind 4|3|no`, `--write FILE`; again after each change, with contrast.py). The profile is
`Profile:` in plan.md, or what detect.py said:

| Profile | Theme file | Tailwind |
|---|---|---|
| laravel | `resources/css/app.css` | yes: the skeleton and the starter kits come with it |
| django | `static/css/tokens.css`, linked in `base.html` before other CSS | no, unless plan.md says so |
| next | `app/globals.css` (`src/app/` with `src/`), imported in `app/layout.tsx`; Pages Router: the CSS file imported in `pages/_app.tsx` (often `styles/globals.css`) | yes: create-next-app sets it up |
| static | the CSS file `src/main.*` imports (`src/style.css` or `src/index.css`) | no, unless plan.md says so |

The user's own app: its own style entry and the Tailwind major version from its package.json.
Copy `../forge-design/components.md` to `forge-work/design/components.md` and fill in its header,
theme file and theme.py command; its `## Theme` maps every token group to a CSS variable by name.
With `PWA: yes`, the manifest colours and the `theme-color` meta tag take token values.

## Step 4: fonts and icons

- **Font**: the open fonts of the concept (SIL OFL or alike), self-hosted with the licence file
  you read; how each profile loads it: `../forge-design/fonts.md`. **Icons**: one set, Lucide
  (ISC), Heroicons (MIT) or Tabler Icons (MIT), as a package or as SVG files with the licence.
- **No font or icon CDN** (it sends every visitor's IP address to a third party, AVG/GDPR).
  components.md carries the search that must find none after scaffolding.

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

Every state the screens show, plus focus, disabled, loading, error and empty, with keyboard and
screen reader behaviour. Targets at least 24 by 24px (WCAG 2.2 AA), 44px for main actions on
mobile. Build on the stack's accessible component base if it has one, else native elements.

## Build

- **A new app**: nothing is built here: go to the checkpoint. `/forge-build` builds the components
  first, on a `/design` page, then the screens.
- **The user's own app**: the theme first (the tokens as CSS variables in its own style entry,
  old values replaced by variables, one commit), then one component per commit, the most used
  first, then screen by screen. Each old value and its token go under `## Mapping` in redesign.md,
  each commit under `## Changed`. No markup or logic change unless accessibility needs it, and then
  a test covers it. Tests pass after each commit; `python3 ../forge-check/secretscan.py .` exits 0
  before it. **Progress**: the first finished screen, before and after; then one line per screen.
- **The whole look**: when the screens are done, go straight on with
  `../forge-design/steps/motion.md` at the same level, then `../forge-design/steps/dashboard.md`
  where the app has data screens, without stopping between the parts. No new questions: the brief
  decides. The before shots above, Judge and Show below cover the whole look, once, so:
  - motion.md: skip Step 1, Step 8 and its Next; of Step 9 do items 1, 2, 4 and 5 (the counts,
    motioncheck, the browser pass, the commits). Its Steps 2 and 3 find the level and the concept.
  - dashboard.md: skip Step 1 (but its sign-in, when there is no state file yet), Step 3.4, Step
    10 and its Next. Restyle the app's existing data screens at the dashboard level, with the data
    they already load; what the level asks that needs more data goes under `## Left` with why. A
    new screen or new query only when the user asks (then Step 7's access test holds). Step 3.2:
    decide the reader from the app's screens and words, write it under `## Audience`, and go on.

## Judge with fresh eyes

Take shots of the app as it is now. With an Agent or Task tool a separate subagent judges them,
from the screenshots, the brief and the generic-look list only (`../forge-design/review.md`
section 2); without one, score them yourself with its rubric. Fix in the tokens or the component,
never per screen, and go again: up to three rounds, in `forge-work/design/review.md`. The whole
look gets this one judge, at the end, with motion scored in the same rounds from the frames.

## Show

Rules.md section 9 for the user's own app (a new app: `/forge-build` does it), as
`../forge-design/review.md` section 5 says:

1. **Make it show**: the branch; a dev server shows it; a built app: `npm run build`, then restart
   `npm start` (ask before you stop a server the user started); containers: rebuild and restart; a
   service worker: bump its cache version, then load the URL twice in one Playwright context and
   check that the new look shows through it.
2. **After shots and proof**: the same command, paths and flags as the before shots, into
   `forge-work/design/shots/after`, then `python3 ../forge-design/changed.py
   forge-work/design/shots/before forge-work/design/shots/after`. Every screen you touched must
   show VISIBLE CHANGE in its own line (exit 0 only means one pair did); one marked NO VISIBLE
   CHANGE is a failure to fix. On screens that should move: frames, a clip and `changed.py --moves`.
   Results under `## Proof` in redesign.md.
3. **Hand over** in plain words: the branch, the address, where to click first, the reduced-motion
   setting, the images and the clip, how to go back, and with a service worker how to drop the old
   one. Merging and deploying stay their step.

## Output

`forge-work/design/brief.md` from its template with every `{{...}}` filled in; `tokens.json`, on
which contrast.py exits 0; and `components.md` from the template with every `<...>` filled in, but
those in the `## Theme` code block (it is the mapping), for example `Profile: next. Tailwind: 4.
Font: Inter (SIL OFL, Fontsource with next/font/local). Icons: Lucide (ISC), as a package.` In clone
mode, its `## Original brand colours` lists the original's colours. Also `world.md`, `concepts/`
with `board.png`, `review.md` once judged, and for the user's own app `forge-work/design/redesign.md`
(review.md, "The redesign report"). `python3 ../forge/level.py check look --report
forge-work/design/brief.md` must exit 0; for the whole look also `python3
../forge-design/motioncount.py . --level auto` (the places and features of the level).

## Next

Checkpoint, at most 5 plain lines. A new app: the concept picked, the palette, the font and icon
set with their licences, how many components are specced, the contrast result; then `/forge-build`.
The user's own app: the hand-over of Show; what changed on which screen, where to look first and
what is left, in plain words (the scores stay in review.md); then `/forge-check test`. Wait for the
user's go. Back to `/forge` or `/forge-improve` when it started there.
