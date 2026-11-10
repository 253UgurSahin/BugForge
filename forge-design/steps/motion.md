# forge-design: motion

A part of `/forge-design`. The ground rules, the levels and "show the result" live in its
`SKILL.md` and in `../forge/rules.md` (section 9: show the result; section 10: levels; the tables
are in `../forge/levels.md`): read them first.

Changes the app: when it ends, things on the screens move that did not move before, as much as
the chosen look level asks and no more. A plan, a report or a copied stylesheet that no element
uses is a failed run. An optional phase after build (and dashboard) and before test in clone and
idea mode; on its own it works on the user's own app. Reads `forge-work/design/` and the built
screens; writes the app's own files and `forge-work/motion.md`. Recipes, patterns per level and
budgets: `../forge-design/motion.md`. The scene kit (levels 4 and 5): `../forge-design/scenes.md`.

Also for this part:

- **Build first, write second.** The work is edits to templates, components, stylesheets and
  scripts. Never stop after the inventory or the tokens: go on to Step 6 in the same run.
- **Every animation has a job** (a state change, feedback, orientation or delight), and the user
  must see the difference on the screen they open first, not only after a click.
- **Nothing is taken from another site.** Not its animation code, timings file, Lottie or video
  files, 3D models or shaders, and no hero rebuilt from a screenshot. A reference gives a mood.
- **No CDN, no hosted player, no tracker.** Every script, font, model and animation file is in the
  repo or installed with npm and served by the app.
- **The user's own app**: no forge-work design files, plan or containers is fine: run it as it
  runs now, follow its own CSS variables (`python3 ../forge-check/detect.py .` names the stack),
  work on a branch (`python3 ../forge/gitguard.py` exits 0), keep `forge-work/` out of git.

## Step 1: what the user looks at, and "before"

Follow `../forge/rules.md` section 9 from the start:

1. Find out what serves the user's local URL: a dev server that reloads by itself, a built app
   (`next build` then `next start`, a compiled bundle) or containers; from which folder and branch
   (`git branch --show-current`, `git worktree list`); and whether a service worker or another
   cache sits in front. Cannot tell: ask "How do you open the app, and at which address?" Write the
   answer at the top of `forge-work/motion.md` as `Served:`.
2. Copy `../forge-design/shots.example.mjs` to `forge-work/design/shots.mjs` and take the "before"
   pictures of every screen you will touch, from that URL, before the first change:
   `node forge-work/design/shots.mjs <URL> forge-work/motion-shots/before --viewport-only --frames <paths>`.
3. `python3 ../forge-design/motioncount.py .` and note the number: the places that move now.
4. Tell the user in two or three lines what will happen, in which order, and roughly how long.

## Step 2: the level

1. `python3 ../forge/level.py get look`. It prints the number and the name: work at that level.
2. A level in the user's request ("niveau 4", "showpiece", "level 5") is recorded at once:
   `python3 ../forge/level.py set look 4 --said '<their words>'`.
3. Exit 1 and no level in the request: ask the ONE question of `../forge/rules.md` section 10, with
   the lines `python3 ../forge/level.py show look` prints (in Dutch: `show look --nl`) and where the
   examples are (the gallery in the README of the pack, and its `examples/` folder). Record the
   answer with `set`, in the user's words. This question is asked in auto mode too.
4. Then do exactly what that level asks: every row up to it, nothing of the rows above it.
   Level 2 gets no 3D "as a bonus"; level 5 gets no fades passed off as a journey.

What each level adds (each level builds everything of the levels below it):

| level | name | Dutch | what it adds | built with |
| --- | --- | --- | --- | --- |
| 1 | Subtle | Subtiel | a clean, consistent design system; feedback on every control: hover, focus, press; fades | CSS only |
| 2 | Polished | Verzorgd | + content arrives: enter, stagger; page transitions; numbers count up; skeleton to content; toasts and dialogs move in and out; micro-interactions on every control | CSS, View Transitions, Web Animations API |
| 3 | Expressive | Expressief | + scroll storytelling: reveals, sticky scenes, parallax layers; springs; charts that draw and morph; real depth with CSS 3D: tilting cards, layered panels, perspective; one signature moment built for this app only | + CSS 3D, scroll-driven animation; `depth.js` of the scene kit |
| 4 | Showpiece | Showpiece | + a WebGL hero scene made for this app's concept: a generative form, a particle field, a shader atmosphere or a contour field; cursor-reactive light and depth; 3D inside the interface: cards, objects, charts; depth while scrolling; Three.js installed without asking again (npm, local, never a CDN), loaded lazily and only on the screens that use it; a still poster for weak devices, for no WebGL and for reduced motion | + Three.js (installed locally), the scene kit |
| 5 | Cinematic | Cinematisch | + a scroll-driven 3D journey: a camera that moves through chapters; custom shaders; GPU particles; forms that react to the pointer and to the app's live data; screens that change in 3D space | + the whole scene kit, composed |

## Step 3: the concept

1. Look for a `Concept:` line at the top of `forge-work/design/brief.md`.
2. None (no concept was chosen in this project yet): do the three concepts of
   `../forge-design/concepts.md` first, at this level: the app's world, three previews that move
   at this level, the board, and its one question: A, B, C or a mix. Stop and wait for the answer;
   this stop holds in auto mode. Write the choice in the brief as concepts.md section 5 says.
3. With a concept: follow the brief. The motion is that concept moving: its signature moment at
   this level, and a character (calm, lively or technical) that fits it. Do not ask about taste
   again. Write under `## Direction`: the concept, its signature moment, the character, and how
   the level shows in it.

## Step 4: the inventory for this level

A table in `forge-work/motion.md` under `## Inventory`, one row per moment, per screen:

| screen | moment | job | what is built | the file to change | what reduced motion shows |
| --- | --- | --- | --- | --- | --- |
| S01 landing | first view | delight | the chart hero (level 4: `contour.js`, drawn as the concept's map) | `resources/js/hero.js`, `welcome.blade.php` | the poster, a still frame |

- It holds every row of every level up to the chosen one, on each screen it fits. Level 1 and 2:
  every control, list, dialog, toast, loading state, number and page change. Level 3: at least
  one scroll story, the springs, the charts, the depth and the signature moment. Level 4: the hero
  on the first screen people see, and 3D inside the interface. Level 5: the journey, the shaders,
  the data hook and the change between screens.
- A screen people use all day (a table, a form) gets feedback and state changes; the strong
  moments go to the landing page, the first run, empty states and the dashboard. The best moment
  plays when a screen loads or scrolls, not only after a click: mark the row to see first.

## Step 5: the motion tokens

Durations, easings, distances and stagger live in `forge-work/design/tokens.json`, nowhere else.
Add the keys of motion.md section 2 with the values of the character: `slow`, `slower`,
`stagger`, `pulse`, `loop`, `ease-exit`, `ease-move` and `ease-spring` in `motion`; `shift-sm`,
`shift` and `shift-lg` in `size`. Keep `fast`, `base` and `ease`. Then run the theme.py command
under `## Theme` in components.md: it writes `--duration-*`, `--ease-*` and `--size-shift*`.
Components and scripts use those variables (scripts through `getComputedStyle`), never a raw
`200ms` or `cubic-bezier(...)`. Own app without tokens: every variable motion.css reads (its top
lists them, lengths in px) goes in the app's main stylesheet; a missing one fails silently. The
scene kit reads the colours (`--color-bg`, `--color-text`, `--color-accent` and more: stage.js).

## Step 6: build, level by level

Shared layer first, then screen by screen. After the first screen, show the user its before and
after; then one line per finished screen. One commit per screen (Step 9).

**Levels 1 and 2: the recipes, in the app's own templates.** Copy `../forge-design/motion.css` next
to the theme file and load it after the theme (laravel: `resources/css/motion.css`, imported in
`app.css` after the other imports; django: `static/css/motion.css`, linked after `tokens.css`;
next: imported in `app/layout.tsx` after `globals.css`; static: imported in `src/main.*`, or with
no bundler a `<link>` on every page). A rule in it does nothing until an element carries its class:
the work is putting the classes and the scripts of motion.md section 4 into the app's own templates
and components. An element whose own rule has a `transition` gets the new property added to that
rule, not a class that would replace it. Level 1: press, hover lift, focus ring and fades on every
control, and the reduced-motion rule. Level 2 adds: enter and stagger, skeleton to content,
dialogs, menus and toasts in and out, count-up, chart draw-on, scroll reveal, page transitions.
Per row, the first layer of motion.md section 3 that does the job.

**Level 3 adds** scroll storytelling (a sticky scene whose steps follow the scroll progress, reveals,
parallax layers), springs from the Web Animations API, charts that draw in and morph between
periods, and real depth: copy `../forge-design/scenes/depth.js` and `../forge-design/scenes/depth.css`
into the app's scripts and styles and put its attributes on cards and panels (tilt, layers,
perspective). Then the signature moment of the concept, built for this app only. Patterns:
motion.md section 8. No library.

**Level 4 adds** a WebGL hero from the scene kit. `../forge-design/scenes.md` says which scene fits
the concept and how to wire it per stack. In short:

1. `npm install three` in the project, without asking again: the level said yes. Read the licence
   of the version installed (`node_modules/three/LICENSE`), write it under `## Libraries`, and run
   `python3 ../forge-check/deps.py .`.
2. Copy the kit's `stage.js`, `glsl.js`, `lazy.js` and the scene (they sit next to
   `../forge-design/scenes/lazy.js`) into a `scenes/` folder of the app's scripts. Never load them, or three, from a URL.
3. The hero is the chosen concept made to move, never a stock shape: tune the scene's options,
   shapes and colours until it could only belong to this app (water for an app about water,
   contour lines for an app about places). A plain torus knot is a failed hero.
4. Mount it with `lazyScene` (nothing of three loads before the hero is near and the page is
   idle), give it a poster (a still of the scene, `data-scene-poster`), and wire one `motionToggle`
   button that pauses every scene. The pointer moves its light and depth; `setProgress` with the
   scroll gives depth while scrolling; depth.js gives 3D inside the interface.

Patterns: motion.md section 9.

**Level 5 adds** the scroll journey (the kit's `journey.js` moves the camera through the chapters
of a section), custom shaders (a `ShaderMaterial` built on `glsl.js`), GPU particles (`field.js`), a data
hook (`setData` fed from the app's own data, never made-up numbers), and screens that change in 3D
space (a view transition in perspective, or a scene that stays between screens while its camera
moves). GSAP only when a scrubbed timeline really needs it; its licence is the user's call: show
the conditions and wait. Patterns: motion.md section 10.

At every level: movement sits inside `@media (prefers-reduced-motion: no-preference)`; fades may
stay outside. The app's CSP stays as strict as it is: no inline `style` attribute in templates, no
`unsafe-eval`. Scripts set custom properties with `element.style.setProperty()`.

## Step 7: accessibility and performance rules

- **Reduced motion**: every animation has a `prefers-reduced-motion: reduce` version (a fade, or
  nothing) that removes no information. Scripts check `matchMedia`; a scene draws one still frame.
- **No flashing** more than three times a second. What moves by itself for over 5 seconds has a
  pause (the motion toggle), and loops stop off-screen and in hidden tabs.
- **Only `transform` and `opacity` animate** (but an accordion's grid rows and a chart's stroke).
- **Budget**: the one for this level in motion.md section 11; no long task over 50ms from animation.
- **Focus is never lost**: a closed dialog returns it to its button; keyboard order does not change.
  Text stays readable over every scene and layer, in light and dark.

## Step 8: make it show, then judge with fresh eyes

1. Make it show (rules.md section 9): restart or rebuild what serves the URL, bump a service
   worker's cache when it holds old files, and load the URL yourself. Work in a worktree or copy:
   start the app from your folder on a free port, or give the one command that switches the
   user's folder to the branch.
2. Take frames from that URL: `node forge-work/design/shots.mjs <URL>
   forge-work/motion-shots/round-1 --frames <paths>`.
3. Have them judged by eyes that did not build it: when the Agent or Task tool exists, a separate
   subagent gets the frames, the brief, the level's row of the table above and "The generic look"
   of `../forge-design/review.md`, and scores each screen from 1 to 10 on: the concept shows, the
   level shows (no less, no more), it looks made for this app, it is calm where people work. No
   such tool: score with the rubric of review.md yourself, from the pictures only. Under 8: fix the
   weakest point and go again, up to three rounds. Write the scores under `## Checks`.

## Step 9: prove it, commit

1. `python3 ../forge-design/motioncount.py . --level auto` must exit 0, with at least 8 places (the
   gate also runs `motioncount.py . --min 8`), well above Step 1. It lists what the level still
   misses and each motion class no element uses (put it to work, or delete its rule). `git diff
   --stat` since the phase began shows templates or components, not only stylesheets.
2. `python3 ../forge-design/motioncheck.py . --fail-on medium` must exit 0; a false positive gets
   `forge:allow` only with the user's OK.
3. "After", from the URL of Step 8: `node forge-work/design/shots.mjs <URL> forge-work/motion-shots/after
   --viewport-only --frames --video --reduced <paths>`. Then
   `python3 ../forge-design/changed.py forge-work/motion-shots/before forge-work/motion-shots/after`
   must say VISIBLE CHANGE, and `python3 ../forge-design/changed.py --moves
   forge-work/motion-shots/after/<name>-390-f*.png` must say that something moves, for each screen
   that should move. "No visible change" is never a finished run: find which reason of rules.md
   section 9 it is and fix that first. The `-reduced` stills must show everything, nothing hidden.
4. In the browser, each screen at 390px and 1440px: no console errors, focus in the right place,
   no layout jump, the budget of Step 7. From level 4: also with WebGL off (the poster shows).
5. `python3 ../forge/level.py check look --report forge-work/motion.md` exits 0. The app's tests
   still pass. `python3 ../forge-check/secretscan.py .` exits 0. Clone mode:
   `python3 ../forge-build/copycheck.py` exits 0. Commit the shared layer (tokens, motion.css, kit,
   scripts) first, then per screen or effect: `motion: S03 dashboard count-up and chart draw-on`.

## Output

The motion in the app, on the work branch, and `forge-work/motion.md`. Its first lines are
`Level: N (Name)` (exactly one such line, the level from Step 2) and `Served:` (Step 1), then:

- `## Direction`: the concept, its signature moment, the character, how the level shows in it.
- `## Inventory`: the table of Step 4, with a done column.
- `## Tokens`: the token names added and their values.
- `## Libraries`: package, version, licence as read, why, size added, where loaded (from level 4:
  three, at least); or "none: CSS and the Web Animations API only".
- `## Checks`: motioncount.py's number before and after and its level result, motioncheck.py's
  result, changed.py's verdicts, the fresh-eyes scores, the browser pass per width and setting,
  the measured budget numbers, and the paths of the before and after pictures and of the clip.

## Next

Hand it over as rules.md section 9 says, in plain words: the branch the work is on; the address
that shows it now; where to click, in order, to see the best moment first; that a system set to
reduced motion shows the calm version, and how to check that setting; the paths of the before and
after pictures and of the recorded clip (`forge-work/motion-shots/after/<name>-1440.webm`); and
how to go back (`git switch <their branch>`). Merging and deploying stay their step.

Checkpoint: at most 5 plain lines: the level and the concept, what now moves on which screens
(motioncount.py before and after), the libraries added with their licences (or none), the check
results, and the clip to watch. Wait for the user's go. Then `/forge-check test`, or back to
`/forge` when it runs the phases.
