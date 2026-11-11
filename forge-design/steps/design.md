# The design part of /forge-design

A part of `/forge-design`. The ground rules, the levels and "show the result" live in
`../forge-design/SKILL.md` and in `../forge/rules.md` (sections 9 and 10): read them first.

This part decides what the app looks like. On the user's own app (a redesign, or the look picked in
`/forge-improve`) it also builds that look in, so the user sees a different app on their own screen.
A new app (`/forge`, clone or idea mode) ends with the picked concept and the specs `/forge-build`
builds from, which runs Judge and Show below. A plan or report alone is a failed run. The order: the
plan (a level in the request is recorded then), read, level, three concepts, the brief, Steps 1 to 6
(the system), build, judge, show.

## What you never take

A system (colour roles, scales, how a form behaves) is not ownable. From another app you never take
(rules.md section 4) its logo, icons, pictures, sounds or a tracing of them; a font it pays for; its
copy; its files (anything from its domain or CDN); its brand colours. Clone mode: list those colours
under `## Original brand colours` in components.md, for brand's sweep only.

## Read the app, and how it runs

- **Say the plan first** (own app), in three lines, before you read anything: what you will do, in
  which order, how long until the three previews (about half an hour at levels 1 to 3, an hour at 4
  and 5), and that the app changes only after the pick. A level in the request: record it now.
- **A new app**: plan.md; clone mode also recon.md and its shots (sizes and layout only). **The
  user's own app**: its screens, words, brand and stack (`python3 ../forge-check/detect.py .`). Keep
  what is theirs and good (a logo, a colour, a font, its own icons, a voice): the brief's `## Keep`.
- **What the user looks at** (own app, before any change, rules.md section 9): what serves their
  local URL, from which folder and branch, and what cache sits in front. Write it under `## How it
  runs`, the first section of redesign.md (review.md, "The redesign report"). Cannot tell: ask.
- **A work branch in that same folder**, so their dev server shows the work: `git switch -c
  forge/redesign-<yyyymmdd>`; `python3 ../forge/gitguard.py` must exit 0. Before the first install
  or commit, `git status --short` must not list `forge-work/` (level.py writes its `.gitignore` with
  a level; before that, add `forge-work/` to the file `git rev-parse --git-path info/exclude` names).
- **The app's own tests**, the proof that nothing breaks, their result in redesign.md's `Tests
  before:`. Tests can empty the database they reach: first `python3 ../forge-check/testdb.py .`.
  Exit 0: a database of their own (or none), run them. Exit 1 (the database the app uses here, or it
  cannot tell): ask the user before you run them. No go: `Tests before: not run (the user's call)`,
  and each commit's `--check` is then the typecheck or the build, never the tests.
- **Before shots** of every screen you will touch (the whole look: the data screens too), from that
  URL, into `forge-work/design/shots/before`, as `../forge-design/review.md` section 1 says: never
  `--no-dark`, signed-in screens after their `--state`, `--init-script forge-work/design/theme.js`
  for the theme, and with a service worker its kept profile (section 5, item 2) now. The whole
  look: motion's count before too (`../forge-design/steps/motion.md` Step 1.3).
- **Then write `forge-work/design/world.md`**, as `../forge-design/concepts.md` section 1 says
  (rivals: two or three public home pages, to see what they all do; take nothing; offline, say so).

## The level

Record a level the request gives (`python3 ../forge/level.py set look N --said '<their words>'`), or
ask the one question, as `../forge-design/SKILL.md` ("The level") says (the whole look: the
dashboard's too), also in auto mode, before the concepts. Then do exactly what the look table of
`../forge/levels.md` asks, never less and never more; it shapes the concepts and the specs (the kit,
from `depth.js` at level 3 up: `../forge-design/scenes.md`). Write `Level: N (Name)` in the brief
and redesign.md. Motion and 3D are built with `../forge-design/steps/motion.md`: in `/forge`'s
motion phase, or right after Build for the whole look and for design alone at level 2 to 5 on the
user's own app (what those levels add is motion's work; Build says how; tell the user in one line).

## Three concepts

Follow `../forge-design/concepts.md` from start to end: three concepts from the app's own world,
each a small moving preview of the app's main screen with its real words, under
`forge-work/design/concepts/a/`, `b/` and `c/`, on one board made from
`../forge-design/concepts.example.html`. Check the board, tell the user how to open it, give them
`forge-work/design/concepts/board.png`, and ask one question: "Which one: A, B or C, or a mix?"
From level 4, and at level 3 when a preview loads `depth.js`, the board needs the server of its
section 3 (from a file the 3D stays blank): give the user `http://127.0.0.1:<port>/`, not the path.

Stop and wait for the answer. This stop holds in auto mode: taste is the user's, and a look is
costly to undo. Nothing below starts before the choice.

## The brief

Copy `../forge-design/brief.md` to `forge-work/design/brief.md` and fill it in from the chosen
concept, `Concept:` in the user's own words, `Picked by:` (the user, or who picked for them and why;
the hand-over says it again) and `## Keep` (the app's own taste that stays, even where "The generic
look" in review.md lists it) included. Every later choice is tested against it; one with no reason
in it is a default: change it. No more taste questions.

## Step 1: measure, do not guess

Colours read by eye are guesses: `python3 ../forge-design/eyedropper.py
forge-work/design/shots/before/home-1440-light.png` (`-dark.png` when the app shows only dark; an
improve run: `forge-work/improve/shots/before/`) lists the colours used most and where (`--box
x,y,w,h` one part, `x,y` one pixel). Own app: what you find (colours, sizes, radii, fonts, how
often) goes under `## Before` in redesign.md. Clone mode: recon's shots give sizes and layout; idea
mode: the concept and plan.md. Estimated values go under `_notes` in tokens.json.

- **Colour roles**, not colours: bg, surface, border, border-input, text, text-muted, accent,
  on-accent, danger, success, warning. Usually 5 to 7 greys.
- A **type scale** (sizes, line heights, weights: 12, 14, 16, 20, 28, 40), **spacing** (a 4 or 8
  base), **radius, shadow, motion** (two or three of each), **layout**, **sizes** (borders, focus
  ring, icons, controls); a **dark theme** when the concept, the app or the user has one.

## Step 2: write the tokens and check the contrast

Copy `../forge-design/tokens.json` to `forge-work/design/tokens.json` and fill in the values from
the concept; keep the role names. Its notes say what else a group takes (a type step's width and
tracking, tints that mix tokens, the motion keys motion.css reads: add them now). A dark theme is a
`dark` group inside `color` (`"dark": {"bg": "#0b0d10"}` gives `dark-bg`). Clone mode: the accent
is from another colour family than the original's, and no role takes one of its brand colours.

List every foreground and background combination the app uses under `pairs`, dark ones included,
as its `_pairs` note says. Then `python3 ../forge-design/contrast.py forge-work/design/tokens.json`
(WCAG AA is the floor; the gate runs it too). Exit 1: a pair fails (it names the nearest passing
colour) or a text colour is in no pair: fix the tokens, never a component. Exit 2: the file is wrong.

## Step 3: the theme, per profile

Values live only in tokens.json; `../forge-design/theme.py` writes the theme from them. Copy
`../forge-design/components.md` to `forge-work/design/components.md` and fill in its header, theme
file and command, as its note under `Command:` says per profile (plan.md's `Profile:`, or what
detect.py said; the user's own app: its own style entry, the Tailwind major of its package.json,
`--tailwind no` when no markup uses a utility class). A theme that computes with its values
(Bootstrap's Sass, MUI, Chakra, Mantine) also gets literal ones (`--format scss` or `js`). With a
dark group the command also carries the switch: the app's own (a concept that opens dark changes its
default) or a new Light, Dark, System (Licht, Donker, Systeem); components.md's `## Theme` says how.

Run it without `--write` to check what it prints. The app's own file gets it only in the theme
commit (Build item 1, right after retheme.py: `../forge-design/restyle.md` section 2), then after
each change to the tokens: earlier, Tailwind 4's block clears the colour classes of every screen not
yet redone. With `PWA: yes`, the `theme-color` meta takes the tokens' literal values, one per theme,
and the manifest the default theme's (`var()` does not work there: restyle.md section 2).

## Step 4: fonts and icons

- **Font**: the open fonts of the concept (SIL OFL or alike), self-hosted with the licence file
  you read, as `../forge-design/fonts.md` says per profile; on the user's own app, a font from a
  CDN or `next/font/google` (fetched from Google at build time) moves too.
- **Icons**: the app's own set when it has one, new icons drawn in the same hand; else one set:
  Lucide (ISC), Heroicons (MIT) or Tabler Icons (MIT), as a package or SVG files with the licence.
- **No font or icon CDN** (it sends every visitor's IP address to a third party, AVG/GDPR):
  components.md carries the search that must find none after scaffolding.

## Step 5: component specs

For every component in recon.md's list (idea mode: what the screens in plan.md need; the user's
own app: what its screens use, the most used first), one block; one per kind is fine (every
button in one), and on the user's own app its `files` line names where each lives, by every name:

```
Button
  variants  primary, secondary, ghost, danger
  sizes     sm 32px, md 40px, lg 48px
  states    default, hover, active, focus-visible (2px ring, accent), disabled, loading
  motion    hover lift 2px, press scale 0.98, duration fast (from level 1)
  tokens    bg accent, text on-accent, radius md, type sm/600
  a11y      real <button>, visible focus, loading keeps the label for screen readers
  used on   S02, S07, S09
  files     components/ui/Button.tsx (Button, Knop), the class families .btn-*, .actie-*
```

Every state the screens show, plus focus, disabled, loading, error and empty, with keyboard and
screen reader behaviour. Targets at least 24 by 24px (WCAG 2.2 AA), 44px for main actions on
mobile. A size relative to its container gets a floor, checked where it is smallest (`max(16%,
96px)`, never a sixth alone). Build on the stack's accessible component base, else native elements.

## Step 6: look at the system before the build

The user's own app (a new app: `/forge-build`'s `/design` page): one page,
`forge-work/design/specimen/index.html`, with the type scale, the colour pairs, the key components
in their states, and the shell's rows (header, rail, tab bar) at their real widths with every
control the specs put there. Its theme: the theme command with `--tailwind no` and `--write
forge-work/design/specimen/theme.css`, on `<html data-theme="system">` (with `--dark-selector`, one
line of script sets that class or attribute while `prefers-color-scheme` is dark); the font files,
licence and `@font-face` next to it (and `--font-inter` or the like, when `font.sans` reads one).
Serve it as concepts.md section 3 does (`-d forge-work/design/specimen`, its own log and pid file),
shoot it through that address in each theme at 1440 and 390 (`../forge-design/review.md` section
1) and stop the server. Look at every shot; fix in the tokens or specs what shrinks or does not fit.

## Build

- **A new app**: nothing is built here: go to the checkpoint. `/forge-build` builds the components
  first, on a `/design` page, then the screens.
- **The user's own app**: one commit per step, each through `python3 ../forge-design/commit.py`, in
  this order; `../forge-design/restyle.md` has the method and the commands (its section in
  brackets). Each old value and its token go under `## Mapping` in redesign.md, each commit under
  `## Changed`.
  1. **The theme** (2, 3): `python3 ../forge-design/retheme.py` and its log, then theme.py, then a
     hand pass; with Tailwind 4, every colour class gets its role and every breakpoint the app uses
     goes into tokens.json in this same commit. Then **the fonts** of Step 4 in a commit of their
     own, with `package.json` and the lockfile.
  2. **Components** (4), one per commit, the most used first.
  3. **One left edge** (5) for every page column, checked on three screens.
  4. **Screens** (6), one at a time, the most used first; a shell several share first; a scene's
     container gets its still now (motion makes it live).
- **What may change** (7): the markup and the words, as far as the picked concept and the level
  need; never what the app does (routes, links, form fields and their names, handlers, data, the
  text its tests look for).
- **After each screen** (8): make it show (Show, item 1); its stills at 390 and 1440 in both themes
  into `forge-work/design/shots/check`, never `before`, looked at; `--overflow` exits 0; the accent
  only where the brief puts it; the served `theme-color` is a colour. **Progress**, after the shell:
  the main screen before and after in one image; then one line per screen.
- **The whole look** (and design alone at level 2 to 5, without the dashboard unless the user named
  it): when the screens are done, go straight on with `../forge-design/steps/motion.md` at the same
  level, then `../forge-design/steps/dashboard.md` for each screen of numbers (its Step 3.1),
  without stopping between the parts. No new questions: the brief decides. The before shots, Judge
  and Show cover the whole look, once, so:
  - motion.md: skip Step 1 (its count before came with the before shots), Step 8 and its Next; of
    Step 9 do items 1, 2, 4 and 5, and of item 3 the `--reduced` stills, the click proof where links
    change the page without a reload, and a pinned stage's wheel steps; Show's shots and `--moves`
    do the rest. Its Steps 2 and 3 find the level and the concept.
  - dashboard.md: skip Step 1 (but its sign-in, when there is no state file yet), Step 3.4, Step
    10 and its Next. Restyle the app's data screens at the dashboard level with the data they
    already load; an item of the level that needs more is built as Step 3.3 says (a read-only query
    scoped like the rest, Step 7's second-user test; no write, no new screen), never left out. Step
    3.2: decide the reader from the app's screens and words, write it under `## Audience`, go on.

## Judge with fresh eyes

Take shots of the app as it is now. With an Agent or Task tool a separate subagent judges them,
with only what `../forge-design/review.md` section 2 lists (this round's stills, the brief, the
level's line and its row, the theme it opens in, the generic look, the before stills); without one,
score them yourself with its rubric. Fix in the tokens or the component, never per screen, and go
again: up to three rounds, in `forge-work/design/review.md`. The whole look (and design alone at
level 2 to 5 on the user's own app) gets this one judge, at the end, with motion scored in the same
rounds from the frames.

## Show

Rules.md section 9 for the user's own app (a new app: `/forge-build` does it); each step in full in
`../forge-design/review.md` section 5:

1. **Make it show**: the branch; a dev server shows it (Laravel: its CSS and JS only while `npm run
   dev` runs, else `npm run build` after each change to them); a built app: rebuild, then restart
   (ask before you stop a server the user started); containers: rebuild and restart; a service
   worker: bump its cache and check in the profile kept at the before shots (section 5, item 2).
2. **After shots and proof**: the before shots' command, paths and flags (each state file made again
   first: an old session lands on the sign-in page) into `forge-work/design/shots/after`, then
   `python3 ../forge-design/changed.py forge-work/design/shots/before forge-work/design/shots/after`:
   every screen you touched says VISIBLE CHANGE in its own line (exit 0 only means one pair did);
   NO VISIBLE CHANGE is a failure to fix. Screens that should move: frames and a clip, and
   `changed.py --moves` on their `<name>-390-f[1-4].png` and on a scene's `<name>-1440-s*.png`
   (`--scene-frames`). Results under `## Proof` in redesign.md.
3. **Hand over** in plain words: the branch, the address, who picked the concept (the brief's
   `Picked by:`) and that they can still pick another, where to click first, the reduced-motion
   setting, the images and the clip, the words added, how to go back (`git switch <their branch>`;
   Laravel with no `public/hot`: then `npm run build`), and with a service worker how to drop the
   old one. Merging and deploying stay their step.

## Output

`forge-work/design/brief.md` from its template with every `{{...}}` filled in; `tokens.json`, on
which contrast.py exits 0; and `components.md` from the template with every `<...>` filled in, but
those in the `## Theme` code block (it is the mapping), and in clone mode its `## Original brand
colours` lists the original's colours. Also `world.md`, `concepts/` with `board.png`, `review.md`
once judged, and on the user's own app `specimen/` with its shots and `redesign.md` (review.md, "The
redesign report"). `python3 ../forge/level.py check look --report forge-work/design/brief.md` must
exit 0; for the whole look, and design alone at level 2 to 5 on the user's own app, also
`python3 ../forge-design/motioncount.py . --level auto` (the places and features of the level).

## Next

Checkpoint, at most 5 plain lines. A new app: the concept picked, the palette, the font and icon
set with their licences, how many components are specced, the contrast result; then `/forge-build`.
The user's own app: the hand-over of Show; what changed on which screen, where to look first and
what is left, in plain words (the scores stay in review.md); then `/forge-check test`. Wait for the
user's go. Back to `/forge` or `/forge-improve` when it started there.
