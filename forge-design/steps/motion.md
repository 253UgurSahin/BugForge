# forge-design: motion

A part of `/forge-design`. The ground rules, the levels and "show the result" live in its
`SKILL.md` and in `../forge/rules.md` (section 9: show the result; section 10: levels; the tables
are in `../forge/levels.md`): read them first.

Changes the app: when it ends, things on the screens move that did not move before, as much as
the chosen look level asks and no more. A plan, a report or a stylesheet no element uses is a
failed run. An optional phase after build (and dashboard) in clone and idea mode; on its own it
works on the user's own app. Writes the app's own files and `forge-work/motion.md`. Recipes,
budgets and the proof script: `../forge-design/motion.md`. The scene kit (levels 4 and 5) is the
folder of `../forge-design/scenes/stage.js`; the API of each file is the comment at its top.

Also for this part:

- **Build first, write second.** The work is edits to templates, components, stylesheets and
  scripts. Never stop after the inventory or the tokens: go on to Step 6 in the same run.
- **Every animation has a job** (a state change, feedback, orientation or delight), and the user
  must see the difference on the screen they open first, not only after a click.
- **Nothing is taken from another site**: no animation code, Lottie or video file, 3D model or
  shader, no hero rebuilt from a screenshot. **No CDN, no hosted player, no tracker**: every file
  is in the repo or installed with npm and served by the app.
- **The user's own app**: no forge-work design files, plan or containers is fine: run it as it
  runs now, follow its own CSS variables (`python3 ../forge-check/detect.py .` names the stack),
  work on a branch (`python3 ../forge/gitguard.py` exits 0). Keep `forge-work/` out of git without
  changing a tracked file: add the line `forge-work/` to `.git/info/exclude`.

## Step 1: what the user looks at, and "before"

A level in the request ("niveau 5"): record it first (Step 2.1). Then rules.md section 9:

1. What serves the user's local URL: a dev server that reloads by itself, a built app (`next
   build` then `next start`) or containers; from which folder and branch
   (`git branch --show-current`, `git worktree list`). A service worker (`public/sw.js`): read
   its fetch handler; when it caches CSS, scripts or pages, their browser can keep old files that
   Playwright (a fresh profile) never shows. Cannot tell: ask "How do you open the app, and at
   which address?" Write it at the top of `forge-work/motion.md` as `Served:`.
2. Copy `../forge-design/shots.example.mjs` to `forge-work/design/shots.mjs`. No Playwright: section
   1 of `../forge-design/review.md` installs it outside the app's package.json. **Behind a
   sign-in**: a state file the project has, or ask the user once to sign in themselves in the
   window of `cd forge-work/design && npx playwright codegen --save-storage=auth.json <login URL>`
   and close it (never a password in the chat). Then every shots command here gets `--state
   forge-work/design/auth.json`; check that each signed-in picture shows its screen, not the login.
   "Before", every screen you will touch, from that URL: `node forge-work/design/shots.mjs <URL>
   forge-work/motion-shots/before --viewport-only --frames --state <that file> <paths>`.
3. `python3 ../forge-design/motioncount.py .` and note the number: the places that move now.
4. Tell the user in two or three lines what happens, in which order, how long, Step 3's direction.

## Step 2: the level

1. A level in the user's request ("niveau 4", "showpiece", "level 5") is recorded at once, before
   Step 1: `python3 ../forge/level.py set look 5 --said '<their words>'`. Do not ask about it again.
2. None in the request: `python3 ../forge/level.py get look`. Exit 1: ask the ONE question of
   `../forge/rules.md` section 10 (`python3 ../forge/level.py show look`, in Dutch `--nl`, and where
   the examples are); this is asked in auto mode too. Record the answer with `set`, their words.
3. Then do exactly what that level asks, never less and never more: level 2 gets no 3D "as a
   bonus"; level 5 gets no fades passed off as a journey.

What each level adds (each level builds everything of the levels below it):

| level | name | Dutch | what it adds | built with |
| --- | --- | --- | --- | --- |
| 1 | Subtle | Subtiel | a clean, consistent design system; feedback on every control: hover, focus, press; fades | CSS only |
| 2 | Polished | Verzorgd | + content arrives: enter, stagger; page transitions; numbers count up; skeleton to content; toasts and dialogs move in and out; micro-interactions on every control | CSS, View Transitions, Web Animations API |
| 3 | Expressive | Expressief | + scroll storytelling: reveals, sticky scenes, parallax layers; springs; charts that draw and morph; real depth with CSS 3D: tilting cards, layered panels, perspective; one signature moment built for this app only | + CSS 3D, scroll-driven animation; the app's own `depth.js` (motion.md section 8) |
| 4 | Showpiece | Showpiece | + a WebGL hero scene made for this app's concept: a generative form, a particle field, a shader atmosphere or a contour field; cursor-reactive light and depth; 3D inside the interface: cards, objects, charts; depth while scrolling; Three.js installed without asking again (npm, local, never a CDN), loaded lazily and only on the screens that use it; a still poster for weak devices, for no WebGL and for reduced motion | + Three.js (installed locally), the scene kit |
| 5 | Cinematic | Cinematisch | + a scroll-driven 3D journey: a camera that moves through chapters; custom shaders; GPU particles; forms that react to the pointer and to the app's live data; screens that change in 3D space | + the whole scene kit, composed |

## Step 3: the concept

1. A `Concept:` line at the top of `forge-work/design/brief.md`: the motion is that concept moving,
   its signature moment at this level, a character (calm, lively, technical) that fits. No new
   question about taste.
2. None, on the user's own app that keeps its look (they asked for motion, not a new look): no
   concepts.md, whose concepts bring new type and colour that this part never builds. Read the
   app's world (`../forge-design/concepts.md` section 1, in five lines), choose a signature moment,
   a character (motion.md section 2) and at level 4 and 5 a scene that fit its look as it is. Say
   it in two lines with Step 1.4 (the user may ask for another direction) and build. No stop.
3. None, and the look is new too (a new app, or the user also asked for a new look): the three
   concepts of concepts.md first, at this level, and its one question: A, B, C or a mix. Stop and
   wait; this stop holds in auto mode. Write the choice in the brief as its section 5 says.

Write it under `## Direction`: the world or concept, the moment, the character, the level in it.

## Step 4: the inventory for this level

A table in `forge-work/motion.md` under `## Inventory`, one row per moment, per screen:

| screen | moment | job | what is built | the file to change | what reduced motion shows |
| --- | --- | --- | --- | --- | --- |
| S01 landing | first view | delight | the chart hero (level 4: `contour.js`, drawn as the concept's map) | `resources/js/hero.js`, `welcome.blade.php` | the poster, a still frame |
| S01 landing | first view | delight | (next) the hero, `field.js` as the app's water | `app/(marketing)/page.tsx`, `components/Hero.tsx` | the poster |
| S03 catches | statistics load | state change | bars draw in, totals count up | `app/(app)/catches/page.tsx`, `components/CatchStats.tsx` | the end state |

- Every row of every level up to the chosen one, on each screen it fits (the table of Step 2).
  Screens used all day (a table, a form) get feedback and state changes; the strong moments go to
  the landing page, the first run, empty states and the dashboard. The best moment plays when a
  screen loads or scrolls, not only after a click: mark the row to see first.

## Step 5: the motion tokens

- **The user's own app with no `forge-work/design/tokens.json`**: do NOT create one and do NOT run
  theme.py: with `--tailwind 4` it clears every Tailwind colour and every `sm:`, `md:`, `lg:`
  breakpoint, and the whole app breaks. The variables motion.css reads go in a plain `:root` block
  at the end of the app's main stylesheet (next: `app/globals.css`), colours mapped to the app's
  own: motion.md section 2, "Without forge tokens", has the list and the check.
- **A theme forge designed**: the values live in `forge-work/design/tokens.json` only. Add the keys
  of motion.md section 2 with the character's values, then run the theme.py command under `##
  Theme` in `forge-work/design/components.md`.

Components and scripts use the variables (scripts through `getComputedStyle`), never a raw `200ms`
or `cubic-bezier(...)`. The names and values go under `## Tokens`.

## Step 6: build, level by level

Shared layer first, then screen by screen. After the first screen, show the user its before and
after; then one line per finished screen. Commit the shared layer, then each screen when it is
done, once `python3 ../forge-check/secretscan.py .` and `python3 ../forge/gitguard.py` exit 0
(`motion: S03 catches count-up and chart draw-on`). Step 9 is the final proof, not the first commit.

**Levels 1 and 2: the recipes, in the app's own templates.** Copy `../forge-design/motion.css`,
load it after the theme and run motion.js on every page, per stack as motion.md section 4 says
(next with Tailwind 4: `@import "./motion.css" layer(components);` in `globals.css`, and
`<MotionRuntime/>` in `app/layout.tsx`, or client-side page changes leave new content hidden). A
class does nothing until an element carries it: put the classes and scripts of motion.md section 4
into the app's own templates and components. An element with its own transition (a rule, Tailwind
classes) gets the property added there (`transition-[color,transform]`). Level 1: press, hover
lift, focus ring and fades on every control, the reduced-motion rule. Level 2 adds: enter and
stagger, skeleton to content, dialogs, menus and toasts, count-up, chart draw-on, scroll reveal,
page transitions. Per row, the first layer of motion.md section 3 that does the job.

**Level 3 adds** scroll storytelling (a sticky scene whose steps follow the scroll, reveals,
parallax layers), springs, charts that draw in and morph between periods, real depth in CSS 3D
(perspective on a container, rotateX, rotateY, translateZ on its cards and panels: the app's own
`depth.js` of motion.md section 8, as the kit has none yet), and the signature moment, built for
this app only. Patterns: motion.md section 8. No library.

**Level 4 adds** a WebGL hero from the kit: `form.js` (a shape: an object, a tool, a craft),
`field.js` (particles: a crowd, a flow, numbers), `aurora.js` (light: water, a sky, a sea; mode
`water`) or `contour.js` (lines over a map: places, depth, height). `npm install three` without
asking again (the level said yes); read `node_modules/three/LICENSE`, write it under `##
Libraries`, run `python3 ../forge-check/deps.py .`. Copy `stage.js`, `glsl.js`, `lazy.js` and the
scene (next to `../forge-design/scenes/lazy.js`) into a `scenes/` folder of the app, never from a
URL. Tune its options and colours until it could only belong to this app: a plain torus knot is a
failed hero. Mount it with `lazyScene`, with a poster (`data-scene-poster`: PNG, or JPEG at
quality 80, under 100 KB) and one `motionToggle` button. The pointer moves its light,
`setProgress` with the scroll gives depth, CSS 3D gives 3D inside the interface. Plain page, React
and Next: motion.md section 9.

**Level 5 adds** (motion.md section 10): **the scroll journey**, chapters that move the camera (the
kit has no `journey.js` yet: the recipe of section 10, story.js and the scene's camera); **a
custom shader**, a `ShaderMaterial` in the app's own code on `glsl.js` (a kit scene alone is not
one); **GPU particles**, `field.js`; **the data hook**, `setData` fed from data a signed-in screen
already loads (the overview, the statistics), on that screen; a new endpoint, or the user's data
on a public page such as the landing hero: ask first, it changes what the app does and who sees
what; **screens that change in 3D space**: next's client navigation runs no page transition, so
the `TurnLink` of section 10. GSAP only when a scrubbed timeline needs it; its licence is the
user's call: show the conditions and wait.

At every level: movement sits inside `@media (prefers-reduced-motion: no-preference)`; fades may
stay outside. The app's CSP stays as strict as it is: no inline `style` attribute in templates, no
`unsafe-eval`. Scripts set custom properties with `element.style.setProperty()`.

## Step 7: accessibility and performance rules

- **Reduced motion**: every animation has a `reduce` version (a fade, or nothing) that removes no
  information. Scripts check `matchMedia`; a scene draws one still frame.
- **No flashing** over three times a second. What moves by itself over 5 seconds has a pause (the
  motion toggle); loops stop off-screen and in hidden tabs. **Only `transform` and `opacity`
  animate** (but an accordion's grid rows and a chart's stroke).
- **Budget**: this level's in motion.md section 11; no long task over 50ms from animation.
- **Focus is never lost**: a closed dialog returns it to its button; keyboard order stays. Text
  stays readable over every scene and layer, in light and dark.

## Step 8: make it show, then judge with fresh eyes

1. Make it show (rules.md section 9): restart or rebuild what serves the URL, load it yourself. A
   service worker that caches CSS, scripts or pages (Step 1.1): change its cache name. A worktree
   or copy: start the app from it on a free port, or give the command that switches their folder.
2. Frames: `node forge-work/design/shots.mjs <URL> forge-work/motion-shots/round-1 --frames
   --state <file> <paths>`.
3. Judged by eyes that did not build it: with the Agent or Task tool, a separate subagent gets the
   frames, `## Direction`, the level's row of Step 2's table and "The generic look" of
   `../forge-design/review.md`, and scores each screen 1 to 10: the direction shows, the level
   shows (no less, no more), it looks made for this app, it is calm where people work. No such
   tool: the rubric of review.md, from the pictures only. Under 8: fix the weakest point and go
   again, up to three rounds. Scores under `## Checks`.

## Step 9: prove it, commit

1. `python3 ../forge-design/motioncount.py . --level auto` must exit 0: level 1 needs 5 places,
   level 2 12, levels 3 to 5 at least 20, in 2 files or more, well above Step 1 (the gate also
   runs `motioncount.py . --min 8`). It lists what the level misses and each motion class no
   element uses (put it to work, or delete its rule). `git diff --stat` shows templates or
   components, not only stylesheets. Level 5: the count cannot tell it from level 4, so write under `## Checks` that
   the journey's frames differ, a `ShaderMaterial` is in the app's own code, `setData` gets real
   data, and the 3D screen change shows in frames across a click (motion.md section 12).
2. `python3 ../forge-design/motioncheck.py . --fail-on medium` must exit 0; a false positive gets
   `forge:allow` only with the user's OK.
3. "After", from the URL of Step 8: `node forge-work/design/shots.mjs <URL> forge-work/motion-shots/after
   --viewport-only --frames --video --reduced --state <that file> <paths>`. Then
   `python3 ../forge-design/changed.py forge-work/motion-shots/before forge-work/motion-shots/after`
   must say VISIBLE CHANGE, and `python3 ../forge-design/changed.py --moves
   forge-work/motion-shots/after/<name>-390-f*.png` that something moves, for each screen that
   should move; "no visible change": find the reason (rules.md section 9) and fix it. The
   `-reduced` stills show everything. Next: motion.md section 12's click proof on each route.
4. Each screen at 390px and 1440px: no console errors, focus right, no layout jump, the budget
   measured as motion.md sections 11 and 12 say (sizes from a build in a copy, never where their
   dev server runs; 4x CPU slowdown, and from level 4 WebGL off with the poster showing).
5. `python3 ../forge/level.py check look --report forge-work/motion.md`, `python3
   ../forge-check/secretscan.py .` and in clone mode `python3 ../forge-build/copycheck.py` exit 0;
   the app's tests pass. Commit what these checks changed.

## Output

The motion in the app, on the work branch, and `forge-work/motion.md`. Its first lines are
`Level: N (Name)` (exactly one such line, the level from Step 2) and `Served:` (Step 1), then:

- `## Direction`: the world or concept, its signature moment, the character, how the level shows.
- `## Inventory`: the table of Step 4, with a done column.
- `## Tokens`: the token or variable names added and their values.
- `## Libraries`: package, version, licence as read, why, size added, where loaded (from level 4:
  three, at least); or "none: CSS and the Web Animations API only".
- `## Checks`: motioncount.py before and after with its level result, motioncheck.py, changed.py,
  the scores, the browser pass, the budget as measured, the paths of the pictures and the clip.

## Next

Hand it over as rules.md section 9 says: the branch; the address that shows it now; where to
click, in order, for the best moment first; that reduced motion shows the calm version, and how to
check that setting; the paths of the pictures and of the clip,
`forge-work/motion-shots/after/<name>-1440.webm`; a caching service worker: reload twice, or
DevTools, Application, Service workers, Unregister; how to go back (`git switch <their branch>`).
Merging and deploying are theirs.

Checkpoint, at most 5 plain lines: the level and direction, what now moves where (motioncount.py
before and after), libraries and licences (or none), the checks, the clip. Wait for the user's go.
Then `/forge-check test`, or back to `/forge` when it runs the phases.
