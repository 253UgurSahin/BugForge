# Three concepts, then one choice

How forge-design finds a look that belongs to this app and no other, and lets the user pick it
before anything is built into the app. It runs after the level is known and before the brief, the
tokens or any change to the app. The stop for the user's choice holds in auto mode too: taste is
theirs, and a look is costly to undo.

## 1. Read the app's world first

A concept comes from what the app is about, never from a list of styles. Collect, in ten minutes,
from the app itself and the user's words (and for a clone: your recon, never the original's look):

- **What it is for, in one sentence**, and the moment someone opens it: where they are, what is in
  their hands, what they are about to do.
- **The things of its world**: materials, tools, places, weather, instruments, paperwork, rituals,
  sounds. An angling app: water at dawn, depth charts, a logbook, a float, permits, knots, scales.
  A bookkeeping app: ledgers, receipts, stamps, a desk lamp, month ends.
- **Its own words**: the names of its screens, the phrases its users use.
- **What it already has that is good**: a logo, a colour, photos, a tone of voice. Keep what is
  theirs; a redesign that throws away a brand the user likes has failed.
- **What every rival looks like**, so that none of the three concepts looks like that.

Write this down in `forge-work/design/world.md`, half a page. Every concept must point back to it.

## 2. Three concepts that really differ

Each concept is one idea from that world, carried through everything. Write for each:

| field | what it holds |
| --- | --- |
| name | two or three words from the app's world ("Chart table", "First light") |
| idea | one sentence a non-designer understands and could repeat |
| type | the heading face and the text face (open fonts), and why they fit the idea |
| colour | the neutrals, the one accent and where it is allowed; light, dark or both |
| shape and space | sharp or round, dense or airy, lines or surfaces |
| signature | the one moment a person will remember, at the chosen level |
| the level in it | what levels 1 to N look like in this idea: at 4 or 5, which scene and what it becomes |
| notice first | what the user sees in the first second |

The three must differ on at least three of: personality of the type, temperature and contrast of
the colour, density, shape, the character of the motion, the hero. Two concepts that are the same
layout in other colours are one concept. Make one of them the safest, one the boldest, and one the
most literal to the app's world; do not say which is which to the user.

At level 4 and 5 the hero is not "a 3D thing": it is the idea made to move. Water for an app
about water, contour lines for an app about places, a ledger that folds for an app about money, a
field of points that settles into the app's own data. Start from the scene kit
(`../forge-design/scenes.md`) and change it until it could only belong here.

None of the three may be the generic look (`../forge-design/review.md`, "The generic look").

## 3. Build three small previews, fast

Each concept becomes one page: `forge-work/design/concepts/a/index.html`, `b/index.html`,
`c/index.html`. A preview is real enough to judge and small enough to build in minutes:

- **The app's own main screen**, with its real words and real numbers: the first view of the
  landing page for a site, or the screen its users open most for an app. Never lorem ipsum. For
  the whole look on an app with data screens, also one small data panel (a number with its trend,
  a small chart) in the concept's style: the dashboards follow the concept the user picks.
- **Moving at the chosen level.** Levels 1 to 3: CSS and a little script. Levels 4 and 5: the
  scene, for real, with `three` installed into the concepts folder, also when the project has it
  (`npm install --prefix forge-work/design/concepts three`), never from a CDN: the server below
  serves that folder only, not the project's own node_modules. The scene's container holds an
  empty `<div data-scene-poster></div>`: the kit marks a scene only once it is live, and that
  child is how the check below sees one still loading and waits for it. Level 5 adds the journey
  (`journey.js`): the preview's first scroll moves the camera through its first chapter. A
  concept that changes a kit scene keeps its own copy next to its page (`a/scene.js`, which
  imports `../kit/stage.js`): a change in `kit/` changes all three.
- **The real fonts**, self-hosted in the concepts folder
  (`npm install --prefix forge-work/design/concepts @fontsource-variable/<name>`, or
  `@fontsource/<name>` when npm answers 404: no variable version, one file per weight;
  `../forge-design/fonts.md`), so the type is judged as it will be. No font CDN.
- **Both widths**: it must hold at 390px and at 1440px. A light and a dark theme when the concept
  has both: `?theme=light|dark` on the URL picks one, and without it the preview follows the
  system setting. It sets `data-theme` on its `<html>` and styles both themes from that, so the
  board switches it without a reload.
- One file each, its CSS and script inside it, about 300 lines; no build step.
- A preview never touches the app: nothing outside `forge-work/design/concepts/` changes.
- How long: about half an hour for the three at levels 1 to 3, about an hour at 4 and 5, where each
  scene is tuned until it belongs to the app. Say that in the plan.

Copy `../forge-design/concepts.example.html` to `forge-work/design/concepts/index.html` and replace
its JSON block with the three concepts (labels and `lang` in the user's language, and each
concept's own default `theme`). That page is the board: the three previews side by side, to open
large, on desktop and phone width, in light and dark.

**The server.** From level 4 the board needs one, and so does a preview that loads a kit file
(`depth.js` at level 3): a browser refuses module scripts from a double-clicked file, so the 3D
stays blank. Copy the kit files the previews use (next to `../forge-design/scenes/lazy.js`) into
`forge-work/design/concepts/kit/`: `depth.js` with `depth.css` from level 3 (tilting cards, stacked
panels; levels 4 and 5 keep them), from level 4 also `stage.js`, `glsl.js`, `lazy.js` and the
scenes you use, and at level 5 `journey.js`. From level 4 give each preview the import map
`{"imports": {"three": "/node_modules/three/build/three.module.js"}}` and `import ... from
"../kit/lazy.js"`; at level 3 `import ... from "../kit/depth.js"` and a link to `../kit/depth.css`
(lazy.js is not copied there). Each preview stays one page. Start it in the background on a free
port (`0` asks for one; on Linux put `setsid` before `nohup`, so it outlives the shell that
started it):

```bash
nohup python3 -u -m http.server --bind 127.0.0.1 0 -d forge-work/design/concepts > forge-work/design/concepts-server.log 2>&1 &
echo $! > forge-work/design/concepts-server.pid
cat forge-work/design/concepts-server.log    # Serving HTTP on 127.0.0.1 port 41234 ...
```

After the pick: `kill "$(cat forge-work/design/concepts-server.pid)"`. At levels 1 to 3 without a
kit file the board also opens by double click; start the server all the same, for the check below.

**Check before you show it**, through `http://127.0.0.1:<port>`: `node forge-work/design/shots.mjs
http://127.0.0.1:<port> forge-work/design/concepts/shots --overflow --scene-frames /a/ /b/ /c/`
(copied as `../forge-design/review.md` section 1 says; levels 2 and 3: `--frames` in place of
`--scene-frames`; level 1, which asks for no motion: neither; level 5: both). It waits until each
scene is live (it sees one loading by its poster child), up to 2 minutes: without a GPU a preview
takes 20 to 40 seconds. Then `python3 ../forge-design/changed.py --moves
forge-work/design/concepts/shots/a-1440-s*.png` (levels 2 and 3: `a-390-f[1-4].png`; level 1: no
`--moves`), and the same for b and c, must say each moves; no line "console" (an error in the page)
and no line "wide". Level 5: also look at `a-390-f5.png` to `-f7.png` yourself, where the
scroll moves the camera (or use the wheel proof of `../forge-design/motion.md` section 12).
Its stills (`a-1440-light.png`, `a-390-dark.png`, ...) are the screenshots per concept, with the
detail the small board loses. Then the board itself: the same command with `--width 1440
--viewport-only --scene-frames /`, and its still `home-1440-light.png` (taken once all three are
live) copied to `forge-work/design/concepts/board.png`.

## 4. Show them and ask once

Tell the user, in their language, in this order:

1. How to open the board: with the server (from level 4, or a preview with a kit file), its
   address `http://127.0.0.1:<port>/`, never the file path, which shows no 3D; without one, the
   full path of `forge-work/design/concepts/index.html`. Give the command for their system
   (`open`, `xdg-open` or `start`) and open it for them when you can. Also give `board.png` and
   the stills per concept. If the address no longer opens when they come back, start the server
   again (the same command, a new port) and give the new address. Say that a click on a preview
   opens it large, where its scene follows their pointer.
2. The three, each in two lines: the letter and name, the idea, what they will notice first.
3. One question: "Which one: A, B or C, or a mix?" Nothing else. Do not recommend one unless they
   ask; if they ask, say which and why in one line.

Then stop and wait. A mix is a real answer ("B, with the colours of A"): restate it in one line in
your reply and go on; do not ask again.

## 5. After the choice

- Write the choice at the top of `forge-work/design/brief.md`: `Concept: B (Bridge at night), with
  the colours of A. The user said: "<their words>"`, then fill in the brief from that concept.
- Keep the concepts folder: it is the record of what was offered. It never ships (forge-work).
- From here the skill builds without more questions about taste. The brief decides.
