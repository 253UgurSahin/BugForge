# forge-design: dashboard

A part of `/forge-design`. The ground rules, the levels and "show the result" live in its
`SKILL.md` and in `../forge/rules.md` (section 9: show the result; section 10: levels; the tables
are in `../forge/levels.md`): read them first.

Changes the app: at the end the user opens a dashboard on their own data, as rich as the dashboard
level asks and no richer. Reads `forge-work/plan.md` (or, on the user's own app, its schema, screens,
styles and stack: `python3 ../forge-check/detect.py .`); writes the screen and `forge-work/dashboard.md`
(Step 3.1). Recipes, the HUD, 3D bars, the data scene, the shots' sign-in: `../forge-design/dashboard.md`.

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
   own password; too few rows: ask before you add seed rows, or use a fixture) and saves its
   `context.storageState` to `forge-work/design/alice.json` (another reader: the path given third).
5. Tell the user in two or three lines what will happen, in which order, and roughly how long.

## Step 2: the level

1. `python3 ../forge/level.py get dashboard`. It prints the number and the name: work at that level.
2. Exit 1: do Step 3.1, then ask the ONE question of `../forge/rules.md` section 10, "How far should
   I go with the dashboard?" (Dutch: "Hoe ver moet ik gaan met het dashboard?"), with the lines that
   `python3 ../forge/level.py show dashboard` prints (`--nl` in Dutch; the gallery in the BugForge
   repo has no dashboard example yet), and the reader of Step 3.2 in the same message.
   Record it: `python3 ../forge/level.py set dashboard N --said '<their words>'`. Asked in auto mode too.
3. Write `Level: N (Name)` as the first line of `forge-work/dashboard.md` (and of each other
   report), `Served:` under it; no other line starts with `Level:`. Build every row up to that level
   and nothing of the rows above.

What each level adds to the ones below it (how each looks: `../forge-design/dashboard.md` sections 12 to 14):

| level | name | Dutch | what it adds | numbers | built with |
| --- | --- | --- | --- | --- | --- |
| 1 | Subtle | Subtiel | 3 to 5 numbers, one chart, one table; calm | 3 to 5 | inline SVG (chart.py or the app's templates), CSS |
| 2 | Polished | Verzorgd | + tiles with delta and sparkline; 2 or 3 charts; a period filter; every state designed | up to 7 | + skeletons and count-up with CSS and the Web Animations API |
| 3 | Expressive | Expressief | + charts that draw in and morph between periods; drill-down; comparison; a value matrix or heat map; live refresh | up to 9 | + the motion tokens; no library |
| 4 | Showpiece | Showpiece | + a dense HUD composition: a readout strip, panels joined by leader lines, a crosshair linked across charts, 3D-styled charts: CSS 3D or canvas, a sequence log | up to 9 | + CSS 3D or canvas 2D; no library |
| 5 | Cinematic | Cinematisch | + a WebGL data scene: the app's own data as a 3D field (scenes/datascape.js of the scene kit); the camera moves when a filter changes; a plain table of the same data is always one key press away | up to 9 | + Three.js (installed locally) and the scene kit |

## Step 3: who looks, which numbers, and "before"

1. List the screens and API routes that already show numbers (a statistics page, an admin
   dashboard, a route such as `api/.../statistieken`) and whose data each shows. Extend the one that
   fits instead of building a second one, and say which. Two screens of numbers for two readers (a
   user's own statistics, the admin's counts): one report per screen, `forge-work/dashboard.md` and
   `forge-work/dashboard-<screen>.md` (`dashboard-admin.md`), each with its own Level line, reader,
   numbers, `## Built` and checks; the checks on `dashboard.md` read them all. A report from an
   earlier run is updated in place, never renamed `dashboard-<date>.md` (it would count as a screen).
2. Propose the reader from the app and wait for that one yes: whose data (the signed-in user's own,
   a team's, or everyone's for the admin), at which moment, to decide what. For example: "For you as
   an angler, after each trip: which water and which species pay off. OK, or is it for the admin?"
   Auto mode: decide from plan.md's Why, roles and flows, or from the code, and write it down.
3. Pick the numbers that change what that reader does, as many as the level allows (the table
   above). A number that never changes a decision is left out.
   - **More numbers than the level allows** already on the screen (a restyle must not change what
     the app does): keep those that drive the reader's decisions; the only sign that something is
     wrong (failed payments) is never dropped, it stays where the app lists what needs action; the
     rest stay reachable (a detail page, the export), under `## Left` with why.
   - **"The data it already loads"** (design.md Build): the same routes with other parameters (a
     period, a filter) count, a new route or query does not. An item of the level that needs one is
     built all the same, with a read-only query scoped like the rest (Step 7, its second-user test
     too); never a write or a new screen unless the user asks. No item of the level goes under `## Left`.
   Write `## Audience` (reader, moment, decisions, the screen it extends or "new") and `## Numbers`:

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
   forge-work/design/alice.json <dashboard path> <a path that shows the app's menu>` (each other
   report's screen after its reader's own `--state`). A new page: it shows what that address shows now.

## Step 4: the layout

Read `../forge-design/dashboard.md` (grid recipes, densities, the HUD). Write `## Layout`:

- **Reading order**: the most important number top left; tiles, then the main chart, then tables.
- **Density**: `calm` at 1, `standard` at 2 and 3 (`dense` if watched all day), `dense` (the HUD) at 4, 5.
- **Responsive** to 390px: tiles in two columns, then one; panels stack in reading order; wide tables
  scroll in their own box. **Light and dark** from the tokens, the brief's default first, a HUD too.
  A worked dense example (its structure, not its looks): `../forge-design/dashboard.example.html`.

## Step 5: the form per number

Write `## Charts` from the chart chooser in the reference (section 1): per number the form and why.
3D only from level 4, as a view next to a table ("bars with depth (CSS 3D) + table").

## Step 6: colours

The tokens are `forge-work/design/tokens.json` from the design part. The user's own app without one:
make it from the app's CSS variables (the same values under forge's names), add only the chart roles
and map those to the app's own variables in its style entry (`--color-chart-1: var(--ac)`). Run
theme.py only when the app's look already comes from tokens.json: on any other app it rewrites the
colours of every screen (with Tailwind 4 it clears Tailwind's own), not only these.

Chart colours are roles, never raw hex in components, as in the tokens template: `chart-1` (the
accent) to `chart-4` (up to `chart-6`), `chart-grid`, the ramp `chart-seq-1` (low) to `chart-seq-5`
for the value matrix (contrast.py cannot check a `color-mix`), a diverging pair only for a meaningful
middle; fit them to the concept, dark values in `color.dark`, each with its pair (marks 3:1; text on
`chart-seq-1` and `chart-seq-5` 4.5:1). `python3 ../forge-design/contrast.py forge-work/design/tokens.json`
must exit 0. Then the Command line under `## Theme` in `forge-work/design/components.md` (it keeps the
theme switch), on a copy of the theme file first (its `--write` to the same name in `forge-work/design/`):
`diff` the copy with the file, only chart variables may differ; then on the file. Colour never carries
meaning alone, and every series is told apart in greyscale (reference section 10).

## Step 7: build it, per stack and per level

- **Say it as you go.** After the first panel works: load the URL, show the user a screenshot of it,
  then one line per finished panel. Never more than about 10 minutes without a line to the user.
- **The code's own stack.** On the user's own app its own data layer, session check and templates
  decide; `../forge-plan/profiles.md` only for its classic mistakes. A new app: plan.md's profile.
- **Queries on the server, under the user's access rules.** A dashboard is the classic place to leak
  another user's data: every aggregate is filtered by the signed-in user or team in the query
  itself, through the same policy or scope the rest of the app uses; never in the browser, never a
  team ID from the URL unchecked. A static site: only the user's own data, never other people's rows.
- **A test with a second user** for every query, drill-down and data feed: user B sees none of user
  A's numbers (403, 404 or B's own totals), and a signed-out request gets nothing.
- **Fresh numbers.** Query live and say "live"; cache only a slow query (over about 200 ms), for less
  time than the live refresh, with its freshness on the screen ("updated 1 minute ago") and a cache
  key that holds the user or team and the period. Money is summed in cents in the database; periods
  are cut in the business's time zone (SQLite has none: compute the edges in the app and pass them).
- **Inline SVG charts**: `python3 ../forge-design/chart.py`, or a component in the app's templates with
  the anatomy of reference section 6. A library only for zoom or thousands of points, local, licence noted.
- **Reachable.** Link the dashboard from the app's own menu, so the user can click to it.

**Level 2 adds** the tiles with change and sparkline, the period filter (GET parameters) and the
skeleton and count-up of reference section 12. **Level 3 adds** draw-in and morph, drill-down
through the same scoped query plus one filter, the comparison, the value matrix, and live refresh
every 30 to 60 seconds that stops in a hidden tab and has a pause control. **Level 4 adds** the HUD
of reference section 13, with no library; bars with depth from `../forge-design/bars3d.css`.

**Level 5 adds** the data scene of reference section 14, without asking again: `npm install three`
(or the app's own package manager, `../forge-design/motion.md` section 5; read its licence, run `python3
../forge-check/deps.py .`), `../forge-design/scenes/datascape.js` and the kit files it needs copied into
the app's scripts, fed through `setData` by the table's scoped query, mounted with `lazyScene`.

## Step 8: every state

Build and write under `## States` what each panel shows when: **loading** (a skeleton of the same
size), **empty** (what to do to get data, never a flat zero line), **error** (a retry; the other
panels still work), **partial** (the period is not over), **stale** (the time of the last update),
**extreme values** (zero, negative, a million, an outlier), **long labels** (60 characters) and
**time zones** (day edges, daylight saving weeks). From level 3 also **live** and **paused**.
Check the extremes and long labels at 390px with a fixture (reference section 15): nothing may push a
panel or the page sideways. Each panel's error says that it failed, never "no data".

## Step 9: accessibility

Each chart has `role="img"`, a `<title>` and a `<desc>` with a text summary (first, last, lowest,
highest), and its data as a table, on the screen or behind a "show as table" control (reference
section 6). Nothing by hover only; every control, the crosshair too, works by keyboard. Text 4.5:1,
marks 3:1. `aria-live="polite"` on a short summary at most. Reduced motion: the final values at once.

## Step 10: make it show, and prove it

1. Make it show (rules.md section 9): restart or rebuild what serves the URL, bump a service
   worker's cache when it holds old files, and load the URL yourself. Not the user's folder: start
   the app from yours on a free port (its install and `.env` first), or commit and move the work to
   theirs, as rules.md section 9 says (a worktree: `git switch --detach` in yours first).
2. "After": each state file made again (signin.mjs: a session expires), then the before command of
   Step 3.4 exactly, into `forge-work/dashboard/after`. Then the motion, in a second run: `node
   forge-work/design/shots.mjs <URL> forge-work/dashboard/motion --viewport-only --state
   forge-work/design/alice.json --frames --video <dashboard path>` (level 5: `--scene-frames` too;
   other screens as in Step 3.4). Look at each at 390px and 1440px, light and dark: no overlap, no
   cut-off number, reading order holds.
3. `python3 ../forge-design/changed.py forge-work/dashboard/before forge-work/dashboard/after` must
   say VISIBLE CHANGE. From level 2, `python3 ../forge-design/changed.py --moves
   forge-work/dashboard/motion/<name>-390-f[1-4].png` (`<name>` as in Step 3.4; the entrance frames
   only: f5 to f7 differ by scrolling alone) must say that something moves; at level 5 also `--moves`
   on its `<name>-1440-s*.png`: the scene moves. "No visible change" is never a finished run: find
   which reason of rules.md section 9 it is, fix that first.
4. No console errors: `DEMO_EMAIL=<the demo user's email> DEMO_PASSWORD=<its password> node
   forge-work/design/signin.mjs <URL> <dashboard path>` prints each error of that page and exits 1
   on any (per screen, its own reader's state file third). By hand: the "show as table" control,
   the keyboard path; from level 5 also WebGL off (the poster shows) and reduced motion (one still).

## Step 11: check and commit

1. Write `## Built` in each report: a row `| item | where | how |` for each item up to the level (its
   name in the first cell), its where the file (from the project root) and line that does it (`| draws
   in and morphs | app/app/statistieken/Line.tsx:41 | stroke-dashoffset |`). Items: 1 numbers, chart,
   table; 2 sparkline, period filter, states; 3 draws in and morphs, drill-down, comparison, value
   matrix, live refresh; 4 readout strip, leader lines, crosshair, 3D-styled charts, sequence log; 5
   data scene, camera, table one key away. No file: build it. Leader lines: `none:` and why (section 7).
2. `python3 ../forge-design/dashcheck.py forge-work/dashboard.md --level auto` and
   `python3 ../forge-design/dashbuilt.py forge-work/dashboard.md --level auto` exit 0 (each also reads
   every `dashboard-<screen>.md`; dashbuilt.py opens each place under `## Built`).
3. `python3 ../forge-design/contrast.py forge-work/design/tokens.json` exits 0, chart roles included. A
   colour chart.py derived (`--tokens ... --json` lists `colours`) becomes a `chart-N` role first.
4. The access test with the second user passes, with the rest of the suite. Tests can empty the
   database they reach: before their first run, `python3 ../forge-check/testdb.py .`; exit 1, ask first.
5. `python3 ../forge/level.py check dashboard --report forge-work/dashboard.md` exits 0 (each report).
6. Write `## Checks`: one plain line per check ("dashcheck.py: exit 0, 7 numbers"); pasted output
   goes in a code block. `python3 ../forge-check/secretscan.py .` exits 0, then the commits: the
   queries and their test first, then the screen: `build: dashboard`.

## Output

- The dashboard screen in the app, linked from its menu, its queries, the second-user test and the commits.
- `forge-work/dashboard.md`, and a `dashboard-<screen>.md` like it for each other screen of numbers:
  first `Level: N (Name)` (exactly one such line, the level of Step 2) and `Served:` (Step 1), then
  `## Audience`, `## Numbers`, `## Layout`, `## Charts`, `## States`, `## Built` and `## Checks` (one
  line per check, dashcheck.py's, dashbuilt.py's and changed.py's results, the paths of the pictures
  and the clip); `## Left` for the numbers over the level's count, with why (never an item of the
  level). Pictures in `forge-work/dashboard/before`, `after` and `motion`.

## Next

Hand it over as rules.md section 9 says, in the user's language and plain words: the branch; the
address and the menu item that leads there; where to click first ("Click a bar to see the catches
behind it"); that reduced motion shows the calm version, and where that setting is; that the shots
use the demo account, and which state the user's own data shows (two rows: "few"; the full states
were checked with a fixture); the pictures and the clip (`forge-work/dashboard/motion/<name>-1440.webm`);
how to go back (`git switch <their branch>`).

Checkpoint, at most 5 plain lines in the user's language: the level, who it is for and the numbers;
what moves and where to click; "Another account cannot see your numbers (tested)" and the checks;
what is example (seed) data or not built; the clip to watch. Merging and deploying stay their step.
Wait for the user's go. Then `/forge-design motion` or `/forge-check test`, or back to `/forge`.
