# The look review

How forge-design design judges the app it designed, from screenshots of the app itself, in rounds. Used
after the vertical slice and at the end of forge-build build, and after every group of screens in a
redesign. It reads your own app only: the stack on localhost (`../forge-check/scope.py` exits 0).

## 1. Take the shots

Once: `mkdir -p forge-work/design && cp ../forge-design/shots.example.mjs forge-work/design/shots.mjs`
(Playwright comes from `e2e/`: run it from there, or `npm i -D -E @playwright/test` in the project).

```bash
node forge-work/design/shots.mjs http://localhost:8080 forge-work/design/shots/round-1 / /login /dashboard
```

Each path gives four PNGs: 390px and 1440px wide, light and dark (dark only when tokens.json has a
dark group: add `--no-dark` otherwise). Signed-in screens: `--state e2e/.auth/alice.json`, the file
forge-check test's setup writes. States a path cannot show (an open dialog, an error, an empty list) get
their own shot by hand or from a spec. Screenshots stay in `forge-work/`: they never ship.

## 2. Look, then score

Open every shot (read the PNG: do not judge from the code) next to `forge-work/design/brief.md`.
Score each screen 0, 1 or 2 on each line: 0 = wrong, 1 = acceptable, 2 = good.

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
for a colour that looks off, `python3 ../forge-design/contrast.py '#fg' '#bg'` for a pair, and
forge-check test's walk (`../forge-check/walkcheck.py`) for overflow, cut-off text and small targets.

## 3. Write it down, fix, go again

`forge-work/design/review.md`, one block per round:

```markdown
## Round 1 (2026-11-10, commit 3f2a1c9)
| screen | score / 22 | weakest lines | fixes |
| --- | --- | --- | --- |
| S03 dashboard | 15 | hierarchy, density | one main action; cut the second stat row |
```

- Fix in the tokens or the component, never per screen: a fix that only one screen gets is a sign
  the system is wrong. After a token change run `theme.py` and `contrast.py` again.
- Rebuild the stack, take the next round in a new folder (`round-2`), and compare:
  `python3 ../forge-check/shotcheck.py forge-work/design/shots/round-1 forge-work/design/shots/round-2`
  lists every screen whose layout moved, so a fix that broke another screen shows.
- Stop when every screen has 18 or more and no line is 0, or after three rounds: then list what is
  left under `## Left` with why. Never score higher to stop sooner.
- One commit per round: `style: look review round 2`, after the tests pass.

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

What to do instead comes from the brief: the concept decides the type, the neutrals, the density
and the signature detail. When a choice has no reason in the brief, it is probably a default.

## Redesign: an app that exists

For the user's own app (improve mode, or on its own). Behaviour stays; only the look changes.

1. `python3 ../forge/gitguard.py` must exit 0 on a new branch `forge/redesign-<date>`. The app's
   own tests run and pass first: that is the proof nothing breaks later.
2. Baseline: shots of every screen into `forge-work/design/shots/before`. Measure what is there
   with eyedropper.py and write the colours, sizes, radii and fonts found, with how often, in
   `forge-work/design/redesign.md` under `## Before`: most apps have three greys too many.
3. The brief with the user (auto mode: decide, and say it can change), then tokens.json and
   components.md as in forge-design design's steps. Under `## Mapping` in redesign.md: each old value and
   the token that replaces it.
4. Theme first: the tokens as CSS variables in the app's own style entry (its Tailwind config, its
   CSS file), old values replaced by variables, one commit. Then one component per commit, the
   most used first, then screen by screen. No markup or logic change unless a component needs it
   for accessibility; when it does, a test covers it.
5. After each group: the app's tests, forge-check test's walk if it is set up, and a look review round
   against `before` with shotcheck.py: screens you did not touch must not move.
6. Report `forge-work/design/redesign.md`: `## Before`, `## Mapping`, `## Changed` (commit per
   component), `## Left`. Nothing is merged or pushed: that is the user's step.
