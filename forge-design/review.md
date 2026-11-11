# The look review

How the design part of `/forge-design` judges the look from screenshots of the app itself, in
rounds, shows the result, and redesigns an app that exists. The judge runs after the vertical slice
and at the end of `/forge-build` for a new app, and once at the end of a redesign or of the whole
look (up to three rounds); between groups of screens only the tests and shotcheck.py run. It reads
your own app only: the app on localhost (`../forge-check/scope.py` exits 0).

## 1. Take the shots

At the start of each run, also when a copy from an earlier run is there (an older one reads the new
flags wrongly or not at all): `mkdir -p forge-work/design && cp ../forge-design/shots.example.mjs
forge-work/design/shots.mjs`. Never edit the copy. It finds Playwright in `forge-work/design`, in
the project's `node_modules` or in the folder you run it from (so `cd e2e` works). Neither: install
it next to the copy, which leaves the project's package.json and lockfile as they are (in a new app
too: before `/forge-build` scaffolds it, a package.json in the project root would push the
scaffold's own aside): `npm install --prefix forge-work/design @playwright/test`, then
`cd forge-work/design && npx playwright install chromium`. `node forge-work/design/shots.mjs
--help` explains every flag.

```bash
node forge-work/design/shots.mjs http://localhost:3000 forge-work/design/shots/before --init-script forge-work/design/theme.js / /login --state e2e/.auth/alice.json /dashboard
node forge-work/design/shots.mjs http://localhost:3000 forge-work/design/shots/round-1 --overflow --contrast --init-script forge-work/design/theme.js / /login --state e2e/.auth/alice.json /dashboard
node forge-work/design/shots.mjs http://localhost:3000 forge-work/design/shots/motion --frames --scene-frames --video --init-script forge-work/design/theme.js / --state e2e/.auth/alice.json /dashboard
```

- Each path gives a still of the whole page at 390px and at 1440px wide, in light and in dark:
  `home-390-light.png` ("/" is called home). `--wait 1500` for an app that loads its data after
  the page; `--viewport-only` for the window only, which is faster. A screen whose main area
  scrolls inside a fixed frame is opened up for the still, and a tab bar fixed to the bottom of the
  window is drawn at the bottom of the picture. `--width 390` (one width) with `--viewport-only`
  is a quick look at one screen while you build it.
- **Light and dark** are named by the theme the page says it shows (`data-theme`, a `dark` class,
  its `color-scheme`), not by the system setting asked for; a page that says nothing is named by
  the setting. An app with no dark theme gives one still per width, and the line says so. Never
  `--no-dark` for before shots: the after shots take the same flags, and a dark theme the work
  adds would never be shot. **An app that remembers its theme** (a key in localStorage: find it in
  the app's theme script or switch; components.md's `## Theme` names it later), or that opens in
  one theme whatever the system says, shows that one under both settings. Give it the system's: a
  file `forge-work/design/theme.js` with one line, `localStorage.setItem('theme',
  matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');` (its own key and
  values), and `--init-script forge-work/design/theme.js` on every shots command. Work that may add
  a theme switch or a dark default (a redesign, the whole look) gives it to the before shots too,
  with the key `theme` when the app has none yet (the switch it adds then keeps that key): the old
  app ignores it, and before and after take the same flags. One fixed value for every still:
  `--storage theme=dark`. A theme kept in a cookie goes in the state file.
- **Signed-in screens** need `--state FILE` before their paths, or every shot is the login page.
  It counts for the paths after it, so one run takes the public, member and admin screens: `/
  /login --state member.json /app --state admin.json /admin` (a sign-in page before any
  `--state`: signed in, it sends you on). Use a saved state the project has (`e2e/.auth/*.json`
  from `/forge-check test`'s setup, or `forge-work/design/alice.json`). None yet: sign in the
  app's own demo or seed account as `../forge-design/steps/dashboard.md` Step 1 does; no such
  account: ask the user to sign in once, themselves, in the window that `cd forge-work/design &&
  npx playwright codegen --save-storage=alice.json <URL>` opens, and to close it. Never ask for a
  password in the chat (rules.md section 5). The file holds a live session: it stays in
  `forge-work/`, out of git. A session expires: a screen that lands on a sign-in page is never
  saved as that screen, its line says "a sign-in page", and the run exits 1. Sign in again.
- A plain run asks the app for reduced motion, so each still is the page at rest and the same in
  every round: that is what is scored and compared. Motion does not show in these stills, and
  depth does not either: cards and stacks lie flat (`../forge-design/scenes/depth.js`) and a scene
  shows its poster. So from level 3 the judge also gets the stills of the round's movement run
  below, which are taken with motion on (section 2).
- **Before and after** (rules.md section 9): the same command, paths and flags both times, into
  `before` and `after`, so `python3 ../forge-design/changed.py forge-work/design/shots/before
  forge-work/design/shots/after` compares like with like. Renew each state file right before the
  after shots (the way you made it), as a long run outlives a session. A service worker: make the
  kept profile of section 5, item 2 now, with the before shots. The work made the app keep a theme
  (a switch, a dark default) and the before command had no `--init-script`: give the after command
  `--init-script forge-work/design/theme.js` all the same (the old app ignored it), or only one
  theme is shot. The sign: the after run prints a "same" line the before run did not, or changed.py
  finds no name in both (`-light` before, only `-dark` after). Still "same" with it: theme.js sets
  another key or value than the app now reads (components.md `## Theme`); fix it and shoot again.
- **Movement**, in a folder of its own: `--frames` adds `home-390-f1.png` to `-f7.png` (the
  entrance in its first second, then three steps of scrolling), `--scene-frames` adds
  `home-1440-s1.png` to `-s6.png` (the scenes in the window, once they are live, over 3 seconds
  with the pointer moving and nothing scrolled; a scene still loading is seen only by its
  `data-scene-poster` child, and each line gives the first scene's size in the window, for the
  level's minimum in `../forge/levels.md`), `--video` a film of each page at 1440px
  (`home-1440.webm`), `--reduced` the stills a person who asked for less motion gets. With any of
  the first three nothing is frozen. Then `python3 ../forge-design/changed.py --moves
  forge-work/design/shots/motion/home-390-f[1-4].png` says whether the entrance moves, and
  `--moves` on `home-1440-s*.png` whether the scene does. Never give `--moves` the frames f5 to f7:
  they differ by the scroll alone, also where nothing moves; look at those, and at the film, yourself.
- **Checks**, on any run: `--overflow` lists each page that scrolls sideways at a width (in an app
  with a fixed frame, each whose main panel, the one that scrolls down, does), with what sticks
  out; `--contrast` measures every text on the page against what is behind it, in each theme, at
  rest and, for the controls in the window, on hover and on focus. Token pairs passing
  `contrast.py` is not enough: a label on a tab can still vanish. Run both on each round's shots
  before the judge (section 2). Each line they print is a finding: look at that text in its still
  before you change a token (a layer the page paints can fool the measure), and fix what you see
  there. A panel built to scroll sideways (a board of columns, a timeline) is no fault: leave it,
  and write its line with why where the part writes its checks (`## Checks`; in redesign.md,
  `## Proof`). The texts it names as not measured (up to five, with their place): look at each in
  its still.
- One line per file, with the status the server gave. Exit 1: a page did not load, it landed on a
  sign-in page, a scene never went live, or a check found something (the line says which). Exit 2:
  wrong use, or no Playwright. Count on 10 seconds a page, 45 with `--frames` and `--video`; a scene
  without a GPU can take up to a minute more per picture of its page (the wait stops at 2 minutes).
- States a path cannot show (an open dialog, an error, an empty list) get their own shot by hand
  or from a spec. Screenshots stay in `forge-work/`: they never ship.

## 2. Fresh eyes: a separate judge

Who built a screen sees what they meant, not what is there. So when the session has an Agent or
Task tool, a separate subagent judges each round. Give it only these: the paths of this round's
stills, and from level 3 also those of the stills its movement run took (section 1, Movement: the
same screens with motion on, where cards lean and scenes are live), `forge-work/design/brief.md`,
the level's line from `python3 ../forge/level.py show look` with its row of "What each look level
shows" in `../forge/levels.md` (what and how big), the theme the app opens in (the theme command's
`--default` under `## Theme` in components.md; with `--dark-selector`, the brief's `Dark theme:`
line; none: the system's), the list "The generic look" below with the two sentences above it, and
the before stills of the user's own app, or the stills of the level below when a level is built on
it (only to see what must stay). Never the code, the plan, earlier rounds, what you changed or your
own view. An audit (`../forge-check/steps/audit.md`) has no brief and no level: it says what goes in
the brief's place, the level lines get "none", and At rest and Big enough are left out. Send this,
with the paths, the line, the row, the theme and the list filled in:

```text
You judge the look of an app from screenshots only. Open each file below and look at it; open
nothing else. File names are <screen>-<width>-<light|dark>.png.
Screenshots: <absolute paths of this round's stills>
These are the reduced-motion version: cards lie flat and a scene shows its still picture.
The same screens with motion on: <absolute paths of the movement run's stills, or none>
The design brief: <absolute path of forge-work/design/brief.md>
The level it must show: <the level's line>
What that level shows at rest, and how big: <its row of levels.md, what and how big>
The theme it opens in: <light | dark | the system's, so both>
How it looked before (only to see what must stay; not for scores): <the before stills, or the level
below's, or none>
The generic look, which this app must avoid (an item the brief keeps under ## Keep is the app's own
taste, not a fault): <the list, pasted with the two sentences above it>

For each screen, score each line 0 (wrong), 1 (acceptable) or 2 (good), on what you see:
hierarchy (the eye lands on the one thing the screen is for), type (few sizes, clear steps,
readable lines), space (more between groups than inside them, nothing cramped at 390px),
alignment (shared edges), colour (the accent only on the main action and the current state),
density (as the brief says, the same on every screen), consistency (one radius, border, shadow and
icon style), states (designed, not default), responsive (390px is a design of its own),
authenticity (the brief's concept and signature are visible, nothing from the generic look),
polish (no cut-off text, double borders or blurry images).
Then the three weakest things on that screen: where, what is wrong, what would fix it.
Then answer yes or no per screen, with what you saw for each no:
- At rest: the top of its -1440- and -390- stills in the theme it opens in, those with motion on
  where given (the first 900 and 844 px, as a person sees it who opens the screen and does
  nothing), already shows the level, and nothing there is smaller, further away or harder to read
  than before. What shows only lower down, only in the other theme or only after a click does not
  count.
- Big enough: each minimum of the level's row that these pictures can show is met in them (a
  scene's share of the screen, a lean, layers apart, frames that differ; a lean, layers and a live
  scene show only with motion on); name any they cannot show.
- Readable: every word reads well in both themes and in every state shown: a selected tab and the
  others, the current page in a menu, labels on buttons. A label that sinks into its background is a no.
- Phone: the -390- stills are a design of their own, with what makes the screen (a scene, a chart, a
  map) or a phone version of it, never an empty place where the desktop has one. A still picture
  of a scene with the page's own header or menu painted into it is a no.
- Kept: everything the before stills show is still there (each section, chapter, chart, table, effect
  and piece of printed content), restyled or built upon, not dropped.
Answer per screen: its total out of 22, the eleven scores, the three weakest things, the five answers.
Then one line: does the whole app look like the brief's concept, and which item of the generic look
you saw, if any. Be strict. Do not guess what was meant. Do not soften a score.
```

**The whole look** (design, motion and dashboards in one job) gets this one judge, with motion in
the same rounds: add the paths of this round's frames (`--frames`, `<screen>-390-f1.png` to `-f4.png`;
`--scene-frames`, `<screen>-1440-s1.png` to `-s6.png` and `-390-`), and when a screen has a pinned
stage, its wheel frames (`wheel-w*.png`, `../forge-design/motion.md` section 12). Add to the prompt:
"Frames named -f1 to -f4 are one screen over its first second; -s1 to -s6 its scene over three
seconds, nothing scrolled, the pointer moving across it. Score one more line from them, motion: 0
nothing moves or it fights the concept, 1 it moves but could be any app, or does less or more than
the level, 2 the concept moves, at the level. Answer three more per screen with a scene or a stage:
Own: could this scene only belong to this app (a kit's form in the app's colours is a no)? Adds: does
it give life to what the screen shows (a chart keeps its figures and names, a map its places), and
not lay a pattern over it or put one in its place? Holds: in every wheel frame, does the pinned stage
sit in the same place, with no card cut in half and no control pushed off the screen?" Totals are
then out of 24.

Write its scores and answers in `forge-work/design/review.md` as they are, with `judge: fresh eyes`.
You may add a line where you disagree; you never change its score. Fix each no first, then its
weakest things.

## 3. No subagent: the rubric

Open every shot (read the PNG: do not judge from the code) next to `forge-work/design/brief.md`.
Score each screen 0, 1 or 2 on each line: 0 = wrong, 1 = acceptable, 2 = good. Write `judge: self`.

| line | what a 2 looks like |
| --- | --- |
| hierarchy | the eye lands on the one thing the screen is for; one main action per screen |
| type | two or three sizes per screen, clear steps between them, lines of 45 to 75 characters, no orphans |
| space | spacing from the scale only; more space between groups than inside them; nothing cramped at 390px |
| alignment | a few shared edges; numbers right-aligned in tables; icons optically centred |
| colour | the accent only on the main action and the current state; neutrals do the rest; contrast.py exits 0 |
| density | fits the brief: calm, standard or dense, the same on every screen |
| consistency | one radius family, one border weight, one shadow style, one icon set, the same component everywhere |
| states | hover, focus, disabled, loading, empty and error are designed, not default |
| responsive | 390px is a design of its own, not the desktop squeezed: no side scroll, targets 44px for main actions |
| authenticity | the brief's concept and signature are visible; nothing from "The generic look" below |
| polish | no cut-off text, no double borders, no misaligned baselines, images sharp at 2x |

Then the yes or no answers of section 2 for each screen (at rest, big enough, readable, phone,
kept; in the whole look also own, adds and holds), and for each no what you saw. From level 3 judge
at rest and big enough on the movement run's stills: in the plain ones cards lie flat.

Measure where you can instead of guessing: `python3 ../forge-design/eyedropper.py <shot> --box x,y,w,h`
for a colour that looks off, `python3 ../forge-design/contrast.py '#fg' '#bg'` for a pair, the shots
run with `--contrast --overflow` (section 1) for every text as it renders, in both themes, at rest,
on hover and on focus, and for sideways scroll, and the walk of `/forge-check test`
(`../forge-check/walkcheck.py`) for cut-off text and small targets.

## 4. Write it down, fix, go again

`forge-work/design/review.md` starts with what serves the URL (rules.md section 9), then one block
per round:

```markdown
## Round 1 (2026-11-10, commit 3f2a1c9, judge: fresh eyes)
| screen | score / 22 | no | weakest things | fixes |
| --- | --- | --- | --- | --- |
| home | 15 | readable: the inactive tab labels sink into the panel in dark | two main actions; the stat row is as loud as the headline; cards inside cards | tab labels in text-muted; one main action; stat row in text-muted; flat list |
```

- Fix in the tokens or the component, never per screen: a fix that only one screen gets is a sign
  the system is wrong. After a token change run
  `theme.py` and `contrast.py` again, and the shots with `--contrast`.
- Let the app reload or rebuild it, take the next round in a new folder (`round-2`), and compare:
  `python3 ../forge-check/shotcheck.py forge-work/design/shots/round-1 forge-work/design/shots/round-2`
  lists every screen whose layout moved, so a fix that broke another screen shows.
- Stop when every screen has 18 or more (20 of 24 in the whole look), no line is 0 and no answer is
  no, or after three rounds: then list what is left under `## Left` with why. Never score higher,
  or argue a score up, to stop sooner.
- In the whole look at level 4 and 5, the screen with the scene also needs 2 on motion and 2 on
  authenticity. A 1 there is a scene that could be any app's, a failed hero
  (`../forge-design/scenes.md` section 2): fix it first, whatever the total.
- One commit per round: `style: look review round 2`, after the tests pass.

## 5. Show: make it show, prove it, hand it over

What the Show step of `../forge-design/steps/design.md` asks, in full (rules.md section 9):

1. **Make it show.** Say which branch the work is on. Work in the folder their server runs from,
   so a dev server shows it within a second. A built app (`next build` then `next start`, or
   `output: "standalone"`): the two commands are `npm run build`, then restart `npm start` (or what
   its package.json names); ask before you stop a server the user started, as it is their process.
   Laravel shows a changed Blade file at once, but its CSS and JS only while Vite's `npm run dev`
   runs (it writes `public/hot`); no `public/hot`: `npm run build` after each change to them (Sail:
   `sail npm run build`; Octane: then `php artisan octane:reload`). Containers: rebuild and restart
   them. A worktree or copy: start the app from your folder on a free port (install from the
   lockfile and copy their `.env` in first, never printed) and give that address, or move the
   branch to their folder with rules.md section 9's commands (a plain `git switch` there fails).
2. **A service worker** (a `sw.js`, a `navigator.serviceWorker.register` call, next-pwa or
   serwist): Playwright's fresh profile has none yet, so its shots can show the new look while the
   user's own browser, where the production build once registered a worker on the same address,
   still serves the old pages. Bump the worker's cache name or version in this branch. A fresh
   profile cannot test the bump: it registers the new worker from the new files and shows the new
   look either way. So before the first change (with the before shots), open the URL once in a
   profile kept on disk, `chromium.launchPersistentContext('forge-work/design/sw-profile')`, and
   wait for `navigator.serviceWorker.ready` (10 seconds at most) before you close it: it now holds
   the old worker and its cache, as the user's browser does. Not ready by then: no worker
   registers from that URL; write that under `## How it runs`. After the work, open that profile
   again, load the URL, wait 5 seconds, load it again, and look at a still of the window next to
   the after shot. Still the old look: close it, open it and load once more, as a user who closes
   every tab of the app does. New now: the worker waits until every tab is closed; say so in the
   hand-over. Still old: the bump did not reach the worker (another file, or the app was not
   rebuilt); fix that and test again. No kept profile: say in the hand-over that the old worker
   was not tested. Load the URL yourself.
3. **After shots** with the same command, paths and flags as the before shots (each state file
   made again first: a screen that lands on a sign-in page fails; an app the work made keep a theme
   gets `--init-script` too: section 1, "Before and after"), into
   `forge-work/design/shots/after`, then `python3 ../forge-design/changed.py
   forge-work/design/shots/before forge-work/design/shots/after`. Exit 0 only means that at least
   one pair changed: read its line per pair. Every screen you touched must say VISIBLE CHANGE; a
   touched screen marked NO VISIBLE CHANGE is a failure to fix: find which reason of rules.md
   section 9 it is, fix it, take the shots again. Exit 2 is never a pass. A picture that comes
   from a host the session cannot reach (map tiles, a video service): test its new style on a
   stand-in the app serves itself, write that under `## Left`, and name it in the hand-over as the
   first thing to look at.
4. **Movement.** On screens that should move, frames and a clip into their own folder (`--frames
   --scene-frames --video`, section 1). `python3 ../forge-design/changed.py --moves` must exit 0 on
   each screen's f1 to f4 (`<name>-390-f[1-4].png`, the entrance), and on a screen with a scene on
   its `<name>-1440-s*.png`. All results go under `## Proof` in redesign.md.
5. **Hand over** in plain words: the branch; the address that shows it now; who picked the
   concept (the brief's `Picked by:`) and that they can still pick another; where to click, in
   order, to see the best moment first; that a system set to reduced motion shows the calm
   version, and how to check that setting; the paths of the before and after images and the clip;
   how to go back (`git switch <their branch>`; Laravel with no `public/hot`: then `npm run build`,
   as git leaves `public/build` as it is). With a service worker add: "Still the old look?
   Open DevTools, Application, Service workers, click Unregister (or press Ctrl+Shift+R), then
   reload." Merging and deploying stay their step.

## The generic look

What makes an app look like every other one made in a hurry. Each is allowed only when the brief
asks for it by name, as its `## Keep` does for the app's own taste.

- A purple-to-blue gradient, gradient text, or a glowing blob behind the headline.
- A centred headline, a centred paragraph, two buttons, then three cards with an icon each.
- Every corner 12 to 16px with the same soft shadow; cards inside cards.
- One font at two weights for everything, with no contrast in size.
- Glass blur on every surface; a dark theme that is the light one inverted.
- Emoji as icons; stock 3D or flat people illustrations; a decorative chart with invented numbers.
- The accent colour on everything: links, icons, borders, badges and headings at once.
- Every section the same height and weight, so nothing is first.
- Placeholder copy ("Welcome back!", "Supercharge your workflow") where the product's own words belong.
- A 3D object that has nothing to do with the app (a random torus, floating cubes, a globe for an
  app that is not about places).

What to do instead comes from the brief: the concept decides the type, the neutrals, the density
and the signature detail. When a choice has no reason in the brief, it is probably a default.

## Redesign: an app that exists

For the user's own app, on its own or when `/forge-improve` picks the look. Behaviour stays; only
the look changes. The steps are those of `../forge-design/steps/design.md`; here is what they ask
of a redesign in particular.

1. Know what the user looks at (rules.md section 9) and write it under `## How it runs`. Work in
   the folder their server runs from, on a new branch `forge/redesign-<yyyymmdd>`;
   `python3 ../forge/gitguard.py` must exit 0. Keep `forge-work/` out of git (the design part's
   "A work branch"). The app's own tests run and pass first: the proof that nothing breaks later.
   Tests can empty the database they reach: first `python3 ../forge-check/testdb.py .`. Exit 0: a
   database of their own (or none), run them. Exit 1 (the database the app uses here, or it cannot
   tell): ask the user before you run them.
2. Before shots of every screen you will touch into `forge-work/design/shots/before` (with a
   service worker, also the kept profile of section 5, item 2). Measure
   what is there with eyedropper.py and write the colours, sizes, radii and fonts found, with how
   often, under `## Before`: most apps have three greys too many.
3. The level, the three concepts and the user's pick, then the brief, tokens.json and
   components.md. Under `## Mapping`: each old value and the token that replaces it.
4. The order and the method of design.md's Build, one commit per step (how:
   `../forge-design/restyle.md`): the theme first (the tokens as CSS variables in the app's own
   style entry, every old value replaced; with Tailwind 4 every colour class turned into its
   role), then one component per commit, the most used first, then one left edge, then screen by
   screen. The markup may change as far as the picked concept and the level need (classes,
   wrappers, the order and grouping of elements, a hero, the layout its preview shows); never what
   the app does (routes, links, form fields and their names, handlers, data, the text its tests
   look for). A change for accessibility gets a test (restyle.md section 7).
5. After each group: the app's tests (item 1 says when), the walk of `/forge-check test` if it is
   set up, and shotcheck.py against `before`: screens you did not touch must not move. The judge
   (section 2) comes once, at the end.
6. Make it show, after shots, proof and the hand-over, as section 5 says. Nothing is merged or
   pushed: that is the user's step.

### The redesign report

`forge-work/design/redesign.md`:

```markdown
# Redesign: Slotwise
Date: 2026-11-10   Branch: forge/redesign-20261110   Started from: main at 3f2a1c9
Level: 4 (Showpiece)
Concept: B (Open book). The user said: "B, with the colours of A"
Picked by: the user
Tests before: 140 passed; after: 140 passed.

## How it runs
npm run dev in this folder, on http://localhost:3000; no service worker.
## Before
## Mapping
## Changed
## Proof
changed.py before after: VISIBLE CHANGE on 12 of 12 pairs. --moves on home-390-f[1-4]: something
moves; on home-1440-s*: the scene moves.
Clip: forge-work/design/shots/motion/home-1440.webm
## Left
```

Each section gets its own lines: `## Changed` one line per commit (hash, component), `## Left`
what the review left and why, or "nothing".
