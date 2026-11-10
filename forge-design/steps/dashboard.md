# forge-design: dashboard

A part of `/forge-design`. The ground rules, the levels and "show the result" live in its
`SKILL.md` and in `../forge/rules.md` (section 9: show the result; section 10: levels; the tables
are in `../forge/levels.md`): read them first.

Changes the app: at the end the user opens a dashboard on their own data, as rich as the dashboard
level asks and no richer. Reads `forge-work/plan.md` (or, on the user's own app, its schema, screens,
styles and stack: `python3 ../forge-check/detect.py .`); writes the screen and `forge-work/dashboard.md`.
Recipes, the HUD, the data scene and the sign-in for the shots: `../forge-design/dashboard.md`.

The first thing you do: a level in the user's request ("niveau 3", "showpiece") is recorded at once,
`python3 ../forge/level.py set dashboard 3 --said '<their words>'`. This part asks for the dashboard
level only, never for the look's.

- **Honest numbers.** Every number on the screen traces back to a table and a query. Never a number
  that cannot be traced, never invented data shown as real. Seed data is fine in development: the
  source says `seed` and the screen labels it. No data yet is an empty state, not a made-up chart.
- **Your own design** from the user's numbers and the tokens: never another product's screen or a
  stock template. **Nothing from outside**: no CDN, web font or hosted chart or analytics script.
- **The user's language, plain words**: every message, the hand-over and the checkpoint.

## Step 1: what the user looks at, the branch, the shots

Follow `../forge/rules.md` section 9 from the start.

1. Find out what serves the user's local URL: a dev server that reloads by itself, a built app or
   containers; from which folder and branch (`git branch --show-current`, `git worktree list`); and
   whether a service worker or another cache sits in front. Cannot tell: ask "How do you open the
   app, and at which address?" Write the answer in `forge-work/dashboard.md` as `Served:`.
2. `python3 ../forge/gitguard.py`. Exit 1 on main or master: `git switch -c forge/dashboard` in the
   folder the user's server runs from (never a worktree or a copy), and tell the user the branch
   name. Before and after then come from the same folder.
3. Install Playwright as `../forge-design/review.md` section 1 says (the user's own package.json
   stays as it is) and copy `../forge-design/shots.example.mjs` to `forge-work/design/shots.mjs`.
4. A signed-in app: write `forge-work/design/signin.mjs` as `../forge-design/dashboard.md` section
   15 shows: it signs in a demo or seed user with enough rows to fill every panel (never the user's
   own password; too few rows: ask before you add seed rows) and saves `context.storageState({ path: "forge-work/design/alice.json" })`, the
   file every shot passes to `--state`.
5. Tell the user in two or three lines what will happen, in which order, and roughly how long.

## Step 2: the level

1. `python3 ../forge/level.py get dashboard`. It prints the number and the name: work at that level.
2. Exit 1: do Step 3.1, then ask the ONE question of `../forge/rules.md` section 10, "How far should
   I go with the dashboard?" (Dutch: "Hoe ver moet ik gaan met het dashboard?"), with the lines that
   `python3 ../forge/level.py show dashboard` prints (in Dutch: `show dashboard --nl`) and where the
   examples are (`examples/levels/README.md` in the BugForge repo; no dashboard example there yet),
   and the reader of Step 3.2 in the same message, so the user answers once. Record the answer with
   `python3 ../forge/level.py set dashboard N --said '<their words>'`. Asked in auto mode too.
3. Write `Level: N (Name)` as the first line of `forge-work/dashboard.md`, `Served:` under it; no
   other line starts with `Level:`. Build every row up to that level and nothing of the rows above.

What each level adds to the ones below it:

| level | name | Dutch | what it adds | numbers | built with |
| --- | --- | --- | --- | --- | --- |
| 1 | Subtle | Subtiel | 3 to 5 numbers, one chart, one table; calm | 3 to 5 | inline SVG (chart.py or the app's templates), CSS |
| 2 | Polished | Verzorgd | + tiles with delta and sparkline; 2 or 3 charts; a period filter; every state designed | up to 7 | + skeletons and count-up with CSS and the Web Animations API |
| 3 | Expressive | Expressief | + charts that draw in and morph between periods; drill-down; comparison; a value matrix or heat map; live refresh | up to 9 | + the motion tokens; no library |
| 4 | Showpiece | Showpiece | + a dense HUD composition: a readout strip, panels joined by leader lines, a crosshair linked across charts, 3D-styled charts: CSS 3D or canvas, a sequence log | up to 9 | + CSS 3D or canvas 2D; no library |
| 5 | Cinematic | Cinematisch | + a WebGL data scene: the app's own data as a 3D field (scenes/datascape.js of the scene kit); the camera moves when a filter changes; a plain table of the same data is always one key press away | up to 9 | + Three.js (installed locally) and the scene kit |

What each level looks like on the screen: `../forge-design/dashboard.md` sections 12 to 14.

## Step 3: who looks, which numbers, and "before"

1. List the screens and API routes that already show numbers (a statistics page, an admin
   dashboard, a route such as `api/.../statistieken`) and whose data each shows. Extend the one that
   fits instead of building a second one, and say which.
2. Propose the reader from the app and wait for that one yes: whose data (the signed-in user's own,
   a team's, or everyone's for the admin), at which moment, to decide what. For example: "For you as
   an angler, after each trip: which water and which species pay off. OK, or is it for the admin?"
   Auto mode: decide from plan.md's Why, roles and flows, or from the code, and write it down.
3. Pick the numbers that change what that reader does, as many as the level allows (the table
   above). A number that never changes a decision is left out. Write `## Audience` (reader, moment,
   decisions, the screen it extends or "new") and `## Numbers`:

```markdown
| number | definition | source | unit | period | compared with | form |
| --- | --- | --- | --- | --- | --- | --- |
| Revenue | paid orders, refunds taken off, tax left out | `orders` where status = paid, sum(total_cents) | EUR | this month, Europe/Amsterdam | last month | tile + line, draws in; drill-down to the orders |
```

Definition: what is counted and what is left out. Source: the table and the query. Unit: EUR, %,
percentage points, ms, or the thing counted. Period: with its time zone. Compared with: the earlier
period, a target, or `-` with the reason. Form: from level 3, what will move or drill down ("draws
in", "morphs", "drill-down"). A pipe inside a cell goes in backticks. Run `python3
../forge-design/dashcheck.py forge-work/dashboard.md` (no `--level` yet: Step 11): it must exit 0.

4. The `<dashboard path>`: the screen it extends, or a new path in the app's signed-in area.
   shots.mjs names the pictures after it with each `/` turned into `-` (`/app/statistieken` gives
   `app-statistieken-390-light.png`). "Before", now, before the first change: `node
   forge-work/design/shots.mjs <URL> forge-work/dashboard/before --viewport-only --state
   forge-work/design/alice.json <dashboard path> <a path that shows the app's menu>`. A new page:
   the picture shows what that address shows now.

## Step 4: the layout

Read `../forge-design/dashboard.md` (grid recipes, densities, the HUD). Write `## Layout`:

- **Reading order**: the most important number top left; tiles, then the main chart, then tables.
- **Density**: `calm` at 1, `standard` at 2, at 3 `standard`, or `dense` for a screen that is
  watched all day, `dense` (the HUD) at 4 and 5; sizes from the reference, text never under 11px.
- **Responsive** to 390px: tiles in two columns, then one; panels stack in reading order; wide
  tables scroll in their own box. **Light and dark** from the tokens; a HUD may be dark first.
  `../forge-design/dashboard.example.html` is a worked dense example: its structure, not its looks.

## Step 5: the form per number

Write `## Charts` from the chart chooser in the reference: per number the form and why. One number
beats a chart; a line for time; bars from zero; a table to look up; no pie over 5 parts, no gauge or
dual axis. 3D only from level 4, as a view next to a table ("bars with depth (CSS 3D) + table").

## Step 6: colours

The tokens are `forge-work/design/tokens.json` from the design part. The user's own app without one:
make it from the app's existing CSS variables (the same values under forge's names), add only the
chart roles, and map those to the app's own variables in its style entry (`--color-chart-1:
var(--ac)`). Run theme.py only when the app's look already comes from tokens.json: on any other app
it rewrites the colours of every screen (with Tailwind 4 it clears Tailwind's own), not only these.

Chart colours are roles, never raw hex in components: `chart-1` to `chart-6` (`chart-1` is the
accent), one sequential ramp and, only for a meaningful middle, one diverging pair; their dark values
in `color.dark`, and a pair for each in `pairs` as `["chart-1", "bg", "ui"]` (marks need 3:1). Then:

```bash
python3 ../forge-design/contrast.py forge-work/design/tokens.json     # must exit 0
python3 ../forge-design/theme.py forge-work/design/tokens.json --tailwind <4|3|no> --write <theme file>
```
`--tailwind` is the app's Tailwind major version (package.json) or `no`. Colour never carries
meaning alone, and every series is told apart in greyscale (reference section 10).

## Step 7: build it, per stack and per level

- **Say it as you go.** After the first panel works: load the URL, show the user a screenshot of it,
  then one line per finished panel. Never more than about 10 minutes without a line to the user.
- **The code's own stack.** On the user's own app its own data layer, session check and templates
  decide; `../forge-plan/profiles.md` only for that stack's classic mistakes. A new app: the
  profile plan.md names.
- **Queries on the server, under the user's access rules.** A dashboard is the classic place to leak
  another user's data: every aggregate is filtered by the signed-in user or team in the query
  itself, through the same policy or scope the rest of the app uses; never in the browser, never a
  team ID from the URL unchecked. A static site: only the user's own data, never other people's rows.
- **A test with a second user** for every query, drill-down and data feed: user B sees none of user
  A's numbers (403, 404 or B's own totals), and a signed-out request gets nothing.
- **Fresh numbers.** Query live and say "live", unless a query is slow (over about 200 ms): cache
  only that one, with its freshness on the screen ("updated 1 minute ago", shorter than the live
  refresh) and a cache key that holds the user or team and the period. Money is summed in cents in
  the database. Periods are cut in the business's time zone; SQLite has none, so compute the
  period's edges in the app (Europe/Amsterdam) and pass them to the query as parameters.
- **Inline SVG charts**: `python3 ../forge-design/chart.py` ahead of time, or a small component in
  the app's templates with the anatomy of reference section 6. A library only for zoom, brushing or
  thousands of points: one known package, installed locally, licence noted.
- **Reachable.** Link the dashboard from the app's own menu, so the user can click to it.

**Level 2 adds** the tiles with change and sparkline, the period filter (GET parameters) and the
skeleton and count-up of reference section 12. **Level 3 adds** draw-in and morph, drill-down
through the same scoped query plus one filter, the comparison, the value matrix, and live refresh
every 30 to 60 seconds that stops in a hidden tab and has a pause control. **Level 4 adds** the HUD
of reference section 13, with no library.

**Level 5 adds** the data scene, exactly as reference section 14 says: `npm install three` without
asking again (read its licence, run `python3 ../forge-check/deps.py .`); `../forge-design/scenes/datascape.js`
with `stage.js`, `glsl.js` and `lazy.js` copied into the app's scripts, never loaded from a URL; fed
through `setData` by the same scoped query as the table, mounted with `lazyScene`; no data: the
empty state; the table of the same data one key press away.

## Step 8: every state

Build and write under `## States` what each panel shows when: **loading** (a skeleton of the same
size), **empty** (what to do to get data, never a flat zero line), **error** (a retry; the other
panels still work), **partial** (the period is not over), **stale** (the time of the last update),
**extreme values** (zero, negative, a million, an outlier), **long labels** (60 characters) and
**time zones** (day edges, daylight saving weeks). From level 3 also **live** and **paused**.

## Step 9: accessibility

Each chart has `role="img"`, a `<title>` and a `<desc>` with a text summary (first, last, lowest,
highest), and its data as a table, on the screen or behind a "show as table" control (reference
section 6). Nothing by hover only; every control, the crosshair too, works by keyboard. Text 4.5:1,
marks 3:1. `aria-live="polite"` on a short summary at most. Reduced motion: the final values at once.

## Step 10: make it show, and prove it

1. Make it show (rules.md section 9): restart or rebuild what serves the URL, bump a service
   worker's cache when it holds old files, and load the URL yourself. Not the user's folder: start
   the app from yours on a free port, or give the one command that switches theirs (`git switch`).
2. "After": the before command of Step 3.4 exactly, into `forge-work/dashboard/after`. Then the
   motion, in a second run: `node forge-work/design/shots.mjs <URL> forge-work/dashboard/motion
   --viewport-only --state forge-work/design/alice.json --frames --video <dashboard path>`. Look at
   each picture at 390px and 1440px, light and dark: no overlap, no cut-off number, reading order holds.
3. `python3 ../forge-design/changed.py forge-work/dashboard/before forge-work/dashboard/after` must
   say VISIBLE CHANGE. From level 2, `python3 ../forge-design/changed.py --moves
   forge-work/dashboard/motion/<name>-390-f[1-4].png` (`<name>` as in Step 3.4; the entrance frames
   only: f5 to f7 differ by scrolling alone) must say that something moves. "No visible change" is never a finished run:
   find which reason of rules.md section 9 it is and fix that first.
4. No console errors: `node forge-work/design/signin.mjs <URL> <dashboard path>` prints each error
   of that page and exits 1 on any. By hand: the "show as table" control and the keyboard path; from
   level 5 also with WebGL off (the poster shows) and with reduced motion (one still frame).

## Step 11: check and commit

1. `python3 ../forge-design/dashcheck.py forge-work/dashboard.md --level auto` exits 0.
2. `python3 ../forge-design/contrast.py forge-work/design/tokens.json` exits 0, chart roles included. A
   colour chart.py derived (`--tokens ... --json` lists `colours`) becomes a `chart-N` role first.
3. The access test with the second user passes, with the rest of the suite.
4. `python3 ../forge/level.py check dashboard --report forge-work/dashboard.md` exits 0.
5. Write `## Built`: for each item of the level table up to the level, the file and line in the app
   that does it (`draws in: app/app/statistieken/Line.tsx:41, stroke-dashoffset`). No file: build it.
6. Write `## Checks`: one plain line per check ("dashcheck.py: exit 0, 7 numbers"); pasted output
   goes in a code block. `python3 ../forge-check/secretscan.py .` exits 0, then the commits: the
   queries and their test first, then the screen: `build: dashboard`.

## Output

- The dashboard screen in the app, linked from its menu, its queries, the second-user test and the commits.
- `forge-work/dashboard.md`. Its first lines are `Level: N (Name)` (exactly one such line, the level
  of Step 2) and `Served:` (Step 1), then the sections `## Audience`, `## Numbers`, `## Layout`,
  `## Charts`, `## States`, `## Built` and `## Checks` (one line per check, with dashcheck.py's and
  changed.py's results and the paths of the pictures and the clip). Pictures in
  `forge-work/dashboard/before`, `after` and `motion`.

## Next

Hand it over as rules.md section 9 says, in the user's language and plain words: the branch; the
address and the menu item that leads there; where to click first ("Click a bar to see the catches
behind it"); that reduced motion shows the calm version, and where that setting is; that the shots
use the demo account; the paths of the pictures and the clip
(`forge-work/dashboard/motion/<name>-1440.webm`); how to go back (`git switch <their branch>`).

Checkpoint, at most 5 plain lines in the user's language: the level, who it is for and the numbers;
what moves and where to click; "Another account cannot see your numbers (tested)" and the checks;
what is example (seed) data or not built; the clip to watch. Merging and deploying stay their step.
Wait for the user's go. Then `/forge-design motion` or `/forge-check test`, or back to `/forge`.
