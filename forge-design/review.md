# The look review

How the design part of `/forge-design` judges the look from screenshots of the app itself, in
rounds, shows the result, and redesigns an app that exists. The judge runs after the vertical slice
and at the end of `/forge-build` for a new app, and once at the end of a redesign or of the whole
look (up to three rounds); between groups of screens only the tests and shotcheck.py run. It reads
your own app only: the app on localhost (`../forge-check/scope.py` exits 0).

## 1. Take the shots

Once: `mkdir -p forge-work/design && cp ../forge-design/shots.example.mjs forge-work/design/shots.mjs`.
It finds Playwright next to that copy (the project's `node_modules`) or in the folder you run it
from (so `cd e2e` works). Neither: in a new app, `npm i -D -E @playwright/test`; in the user's own
app, leave their package.json as it is: `npm install --prefix forge-work/design @playwright/test`,
then `cd forge-work/design && npx playwright install chromium`. `node forge-work/design/shots.mjs
--help` explains every flag.

```bash
node forge-work/design/shots.mjs http://localhost:3000 forge-work/design/shots/before / /login /dashboard
node forge-work/design/shots.mjs http://localhost:3000 forge-work/design/shots/round-1 / /login /dashboard
node forge-work/design/shots.mjs http://localhost:3000 forge-work/design/shots/motion --frames --video / /dashboard
```

- Each path gives a still of the whole page at 390px and at 1440px wide, in light and in dark:
  `home-390-light.png` ("/" is called home). `--no-dark` for an app without a dark theme;
  `--wait 1500` for an app that loads its data after the page; `--viewport-only` for the window
  only, which is faster.
- **Signed-in screens** need `--state FILE`, or every shot is the login page. Use a saved state
  the project has (`e2e/.auth/*.json` from `/forge-check test`'s setup, or
  `forge-work/design/alice.json`). None yet: sign in the app's own demo or seed account as
  `../forge-design/steps/dashboard.md` Step 1 does; no such account: ask the user to sign in once,
  themselves, in the window that `cd forge-work/design && npx playwright codegen
  --save-storage=alice.json <URL>` opens, and to close it. Never ask for a password in the chat
  (rules.md section 5). The file holds a live session: it stays in `forge-work/`, out of git.
- A plain run asks the app for reduced motion, so each still is the page at rest and the same in
  every round: that is what is scored and compared. Motion does not show in these stills.
- **Before and after** (rules.md section 9): the same command, paths and flags both times, into
  `before` and `after`, so `python3 ../forge-design/changed.py forge-work/design/shots/before
  forge-work/design/shots/after` compares like with like.
- **Movement**, in a folder of its own: `--frames` adds `home-390-f1.png` to `-f7.png` (the
  entrance, then three steps of scrolling), `--video` a film of each page at 1440px
  (`home-1440.webm`), `--reduced` the stills a person who asked for less motion gets. With
  `--frames` or `--video` nothing is frozen. Then `python3 ../forge-design/changed.py --moves
  forge-work/design/shots/motion/home-390-f*.png` says whether something moves.
- One line per file, with the status the server gave. Exit 1: a page did not load (the line says
  which). Exit 2: wrong use, or no Playwright. Count on 10 seconds a page, 45 with `--frames` and `--video`.
- States a path cannot show (an open dialog, an error, an empty list) get their own shot by hand
  or from a spec. Screenshots stay in `forge-work/`: they never ship.

## 2. Fresh eyes: a separate judge

Who built a screen sees what they meant, not what is there. So when the session has an Agent or
Task tool, a separate subagent judges each round. Give it only three things: the paths of this
round's stills, `forge-work/design/brief.md`, and the list "The generic look" below. Never the
code, the plan, earlier rounds, what you changed or your own view. Send this, with the paths and
the list filled in:

```text
You judge the look of an app from screenshots only. Open each file below and look at it; open
nothing else. File names are <screen>-<width>-<light|dark>.png.
Screenshots: <absolute paths of this round's stills>
The design brief: <absolute path of forge-work/design/brief.md>
The generic look, which this app must avoid: <the list, pasted>

For each screen, score each line 0 (wrong), 1 (acceptable) or 2 (good), on what you see:
hierarchy (the eye lands on the one thing the screen is for), type (few sizes, clear steps,
readable lines), space (more between groups than inside them, nothing cramped at 390px),
alignment (shared edges), colour (the accent only on the main action and the current state),
density (as the brief says, the same on every screen), consistency (one radius, border, shadow and
icon style), states (designed, not default), responsive (390px is a design of its own),
authenticity (the brief's concept and signature are visible, nothing from the generic look),
polish (no cut-off text, double borders or blurry images).
Then the three weakest things on that screen: where, what is wrong, what would fix it.
Answer per screen: its total out of 22, the eleven scores, the three weakest things. Then one line:
does the whole app look like the brief's concept, and which item of the generic look you saw, if any.
Be strict. Do not guess what was meant. Do not soften a score.
```

**The whole look** (design, motion and dashboards in one job) gets this one judge, with motion in
the same rounds: add the paths of this round's frames (`--frames`, `<screen>-390-f1.png` to `-f7.png`)
and the level's line from `python3 ../forge/level.py show look`, and add to the prompt: "Frames
named -f1 to -f7 are one screen over its first second and three steps of scrolling. Score one more
line from them, motion: 0 nothing moves or it fights the concept, 1 it moves but could be any app,
or does less or more than the level, 2 the concept moves, at the level." Totals are then out of 24.

Write its scores in `forge-work/design/review.md` as they are, with `judge: fresh eyes`. You may
add a line where you disagree; you never change its score. Fix its weakest things first.

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

Measure where you can instead of guessing: `python3 ../forge-design/eyedropper.py <shot> --box x,y,w,h`
for a colour that looks off, `python3 ../forge-design/contrast.py '#fg' '#bg'` for a pair, and the
walk of `/forge-check test` (`../forge-check/walkcheck.py`) for overflow, cut-off text and small targets.

## 4. Write it down, fix, go again

`forge-work/design/review.md` starts with what serves the URL (rules.md section 9), then one block
per round:

```markdown
## Round 1 (2026-11-10, commit 3f2a1c9, judge: fresh eyes)
| screen | score / 22 | weakest things | fixes |
| --- | --- | --- | --- |
| home | 15 | two main actions; the stat row is as loud as the headline; cards inside cards | one main action; stat row in text-muted; flat list |
```

- Fix in the tokens or the component, never per screen: a fix that only one screen gets is a sign
  the system is wrong. After a token change run `theme.py` and `contrast.py` again.
- Let the app reload or rebuild it, take the next round in a new folder (`round-2`), and compare:
  `python3 ../forge-check/shotcheck.py forge-work/design/shots/round-1 forge-work/design/shots/round-2`
  lists every screen whose layout moved, so a fix that broke another screen shows.
- Stop when every screen has 18 or more (20 of 24 in the whole look) and no line is 0, or after
  three rounds: then list what is left under `## Left` with why. Never score higher, or argue a
  score up, to stop sooner.
- One commit per round: `style: look review round 2`, after the tests pass.

## 5. Show: make it show, prove it, hand it over

What the Show step of `../forge-design/steps/design.md` asks, in full (rules.md section 9):

1. **Make it show.** Say which branch the work is on. Work in the folder their server runs from,
   so a dev server shows it within a second. A built app (`next build` then `next start`, or
   `output: "standalone"`): the two commands are `npm run build`, then restart `npm start` (or what
   its package.json names); ask before you stop a server the user started, as it is their process.
   Containers: rebuild and restart them. A worktree or copy: start the app from your folder on a
   free port and give that address.
2. **A service worker** (a `sw.js`, a `navigator.serviceWorker.register` call, next-pwa or
   serwist): Playwright's fresh profile has none yet, so its shots can show the new look while the
   user's own browser, where the production build once registered a worker on the same address,
   still serves the old pages. Bump the worker's cache name or version in this branch. Then load
   the URL twice in one Playwright context (the second load goes through the registered worker)
   and check that the new look shows. Load the URL yourself.
3. **After shots** with the same command, paths and flags as the before shots, into
   `forge-work/design/shots/after`, then `python3 ../forge-design/changed.py
   forge-work/design/shots/before forge-work/design/shots/after`. Exit 0 only means that at least
   one pair changed: read its line per pair. Every screen you touched must say VISIBLE CHANGE; a
   touched screen marked NO VISIBLE CHANGE is a failure to fix: find which reason of rules.md
   section 9 it is, fix it, take the shots again. Exit 2 is never a pass.
4. **Movement.** On screens that should move, frames and a clip into their own folder (`--frames
   --video`, section 1), and `python3 ../forge-design/changed.py --moves` on each screen's frames
   must exit 0. All results go under `## Proof` in redesign.md.
5. **Hand over** in plain words: the branch; the address that shows it now; where to click, in
   order, to see the best moment first; that a system set to reduced motion shows the calm
   version, and how to check that setting; the paths of the before and after images and the clip;
   how to go back (`git switch <their branch>`). With a service worker add: "Still the old look?
   Open DevTools, Application, Service workers, click Unregister (or press Ctrl+Shift+R), then
   reload." Merging and deploying stay their step.

## The generic look

What makes an app look like every other one made in a hurry. Each is allowed only when the brief
asks for it by name.

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
2. Before shots of every screen you will touch into `forge-work/design/shots/before`. Measure
   what is there with eyedropper.py and write the colours, sizes, radii and fonts found, with how
   often, under `## Before`: most apps have three greys too many.
3. The level, the three concepts and the user's pick, then the brief, tokens.json and
   components.md. Under `## Mapping`: each old value and the token that replaces it.
4. Theme first: the tokens as CSS variables in the app's own style entry (its Tailwind config, its
   CSS file), old values replaced by variables, one commit. Then one component per commit, the
   most used first, then screen by screen. No markup or logic change unless a component needs it
   for accessibility; when it does, a test covers it.
5. After each group: the app's tests, the walk of `/forge-check test` if it is set up, and
   shotcheck.py against `before`: screens you did not touch must not move. The judge (section 2)
   comes once, at the end.
6. Make it show, after shots, proof and the hand-over, as section 5 says. Nothing is merged or
   pushed: that is the user's step.

### The redesign report

`forge-work/design/redesign.md`:

```markdown
# Redesign: Slotwise
Date: 2026-11-10   Branch: forge/redesign-20261110   Started from: main at 3f2a1c9
Level: 4 (Showpiece)
Concept: B (Open book). The user said: "B, with the colours of A"
Tests before: 140 passed; after: 140 passed.

## How it runs
npm run dev in this folder, on http://localhost:3000; no service worker.
## Before
## Mapping
## Changed
## Proof
changed.py before after: VISIBLE CHANGE on 12 of 12 pairs. --moves on home-390: something moves.
Clip: forge-work/design/shots/motion/home-1440.webm
## Left
```

Each section gets its own lines: `## Changed` one line per commit (hash, component), `## Left`
what the review left and why, or "nothing".
