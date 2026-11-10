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
  landing page for a site, or the screen its users open most for an app. Never lorem ipsum.
- **Moving at the chosen level.** Levels 1 to 3: CSS and a little script. Levels 4 and 5: the
  scene, for real, when the project has `three` installed (or install it into the concepts folder
  only: `npm install --prefix forge-work/design/concepts three`); never from a CDN.
- **The real fonts**, self-hosted in the concepts folder
  (`npm install --prefix forge-work/design/concepts @fontsource-variable/<name>`), so the type is
  judged as it will be. No font CDN.
- **Both widths**: it must hold at 390px and at 1280px. A light and a dark theme when the concept
  has both (`?theme=light|dark` on the URL picks one; the board sends it).
- One file each, its CSS and script inside it, about 300 lines; no build step.
- A preview never touches the app: nothing outside `forge-work/design/concepts/` changes.

Copy `../forge-design/concepts.example.html` to `forge-work/design/concepts/index.html` and replace
its JSON block with the three concepts (labels in the user's language). That page is the board: the
three previews side by side, to open large, on desktop and phone width, in light and dark.

Check before you show it: open the board with Playwright, no console error, no sideways scroll,
each preview moves (`python3 ../forge-design/changed.py --moves` on frames of each), and save
`forge-work/design/concepts/board.png` plus one screenshot per concept.

## 4. Show them and ask once

Tell the user, in their language, in this order:

1. How to open the board: the full path of `forge-work/design/concepts/index.html`, and the command
   for their system (`open`, `xdg-open` or `start`). Open it for them when you can.
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
