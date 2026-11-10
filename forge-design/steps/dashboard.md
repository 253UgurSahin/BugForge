# forge-design: dashboard

A part of `/forge-design`. The ground rules, the levels and "show the result" live in its
`SKILL.md` and in `../forge/rules.md` (section 9: show the result; section 10: levels; the tables
are in `../forge/levels.md`): read them first.

Changes the app: when it ends, the user opens a dashboard on their own data, as rich as the chosen
dashboard level asks and no richer. Reads `forge-work/plan.md`, `forge-work/design/tokens.json` and the
app's own schema; writes the dashboard screen in the app and `forge-work/dashboard.md`. On the
user's own app (no plan.md): read the schema and the existing styles, and follow the code's stack
(`python3 ../forge-check/detect.py .`). Recipes, the HUD and the data scene: `../forge-design/dashboard.md`.

Also for this part:

- **Honest numbers.** Every number on the screen traces back to a table and a query. Never a number
  that cannot be traced, never invented data shown as real. Seed data is fine in development: the
  source says `seed` and the screen labels it. No data yet is an empty state, not a made-up chart.
- **Your own design**, made here from the user's numbers and the design tokens. Never rebuild
  another product's dashboard screen, and no stock template look.
- **Nothing from outside.** No CDN, no web font, no hosted chart or analytics script. A library
  only where Step 7 allows it, installed from the package registry and bundled with the app.

## Step 1: what the user looks at, and "before"

Follow `../forge/rules.md` section 9 from the start:

1. Find out what serves the user's local URL: a dev server that reloads by itself, a built app or
   containers; from which folder and branch (`git branch --show-current`, `git worktree list`); and
   whether a service worker or another cache sits in front. Cannot tell: ask "How do you open the
   app, and at which address?" Write the answer at the top of `forge-work/dashboard.md` as `Served:`.
2. Copy `../forge-design/shots.example.mjs` to `forge-work/design/shots.mjs` (once per project) and
   take the "before" pictures of the address the dashboard will live at, before the first change:
   `node forge-work/design/shots.mjs <URL> forge-work/dashboard/before --viewport-only --state
   <saved sign-in> /dashboard`. A new page: the picture shows what that address shows now.
3. Tell the user in two or three lines what will happen, in which order, and roughly how long.

## Step 2: the level

1. `python3 ../forge/level.py get dashboard`. It prints the number and the name: work at that level.
2. A level in the user's request ("niveau 4", "showpiece", "level 5") is recorded at once:
   `python3 ../forge/level.py set dashboard 4 --said '<their words>'`.
3. Exit 1 and no level in the request: ask the ONE question of `../forge/rules.md` section 10,
   "How far should I go with the dashboard?", with the lines that
   `python3 ../forge/level.py show dashboard` prints (in Dutch: `show dashboard --nl`) and where
   the examples are (the README gallery of the pack, its `examples/` folder). Record the answer
   with `set`, in the user's words. This question is asked in auto mode too.
4. Then do exactly what that level asks: every row up to it, nothing of the rows above it. Level 1
   gets no live refresh "as a bonus"; level 5 gets no tilted tiles passed off as a data scene.

What each level adds (each level builds everything of the levels below it):

| level | name | Dutch | what it adds | numbers | built with |
| --- | --- | --- | --- | --- | --- |
| 1 | Subtle | Subtiel | 3 to 5 numbers, one chart, one table; calm | 3 to 5 | inline SVG (chart.py or the app's templates), CSS |
| 2 | Polished | Verzorgd | + tiles with delta and sparkline; 2 or 3 charts; a period filter; every state designed | up to 7 | + skeletons and count-up with CSS and the Web Animations API |
| 3 | Expressive | Expressief | + charts that draw in and morph between periods; drill-down; comparison; a value matrix or heat map; live refresh | up to 9 | + the motion tokens; no library |
| 4 | Showpiece | Showpiece | + a dense HUD composition: a readout strip, panels joined by leader lines, a crosshair linked across charts, 3D-styled charts: CSS 3D or canvas, a sequence log | up to 9 | + CSS 3D or canvas 2D; no library |
| 5 | Cinematic | Cinematisch | + a WebGL data scene: the app's own data as a 3D field (scenes/datascape.js of the scene kit); the camera moves when a filter changes; a plain table of the same data is always one key press away | up to 9 | + Three.js (installed locally) and the scene kit |

What each level looks like on the screen: `../forge-design/dashboard.md` sections 12 to 14.

## Step 3: who looks, which decisions, which numbers

Ask one question: "Who opens this dashboard, how often, and what do they decide with it?" (auto
mode: decide from plan.md's Why, roles and flows, and write the choice down). Then pick the numbers
that change what that reader does, as many as the level allows (the table above). A number that
never changes a decision is left out. Write `## Audience` (reader, moment, decisions) and `## Numbers`:

```markdown
| number | definition | source | unit | period | compared with | form |
| --- | --- | --- | --- | --- | --- | --- |
| Revenue | paid orders, refunds taken off, tax left out | `orders` where status = paid, sum(total_cents) | EUR | this month, Europe/Amsterdam | last month | tile + line, draws in; drill-down to the orders |
```

Definition: exactly what is counted and what is left out. Source: the table and the query or filter.
Unit: EUR, %, percentage points, ms, or the thing counted. Period: with its time zone. Compared
with: the earlier period, a target, or `-` with the reason. A pipe inside a cell goes in backticks.
Form: from level 3, name what moves or drills down ("draws in", "morphs", "drill-down").
Run `python3 ../forge-design/dashcheck.py forge-work/dashboard.md --level auto`: it must exit 0.

## Step 4: the layout

Read `../forge-design/dashboard.md` (grid recipes, densities, the HUD). Write `## Layout`:

- **Grid and reading order.** The most important number top left, then left to right, top to bottom:
  tiles first, the main chart under them, detail tables and feeds last. One screen, one question.
- **Density** by level: `calm` at 1, `standard` at 2 and 3, `dense` (the HUD) at 4 and 5. Take the
  sizes from the reference. Dense is still readable: text of 11px or more, real contrast, nothing
  that carries no data. Level 4 and 5 follow the composition of reference section 13.
- **Responsive** down to 390px: tiles go to two columns, then one; panels stack in reading order;
  wide tables scroll inside their own box; nothing is hidden on a phone that a decision needs.
- **Light and dark** from the tokens (`color` and `color.dark`). A HUD may be dark by default; it
  still follows the tokens, so the rebrand and the contrast check keep working.

`../forge-design/dashboard.example.html` is a worked dense example: use its structure, not its looks.

## Step 5: the form per number

Use the chart chooser in the reference and write `## Charts`: per number the form and why. In short:
one number beats a chart; a line for time; bars for comparison, from zero; a table for looking things
up; no pie or donut over 5 parts; no gauge or dual axis. No 3D below level 4; at 4 and 5 depth is a
view on a flat form, with every value printed or in a table next to it ("bars with depth (CSS 3D) +
table"). Run dashcheck.py again after changes.

## Step 6: colours

Add chart colours to `forge-work/design/tokens.json` as roles, never as raw hex in components:
`chart-1` to `chart-6` (categorical, `chart-1` is the accent), one sequential ramp (the accent from
faint to full) and, only if a number has a meaningful middle, one diverging pair. Add the dark ones
to `color.dark`, and a pair for each in `pairs` as `["chart-1", "bg", "ui"]` (marks need 3:1). Then:

```bash
python3 ../forge-design/contrast.py forge-work/design/tokens.json     # must exit 0
python3 ../forge-design/theme.py forge-work/design/tokens.json --tailwind <4|3|no> --write <theme file>
```

Colour-blind safety: neighbours differ in lightness as well as hue, and colour never carries meaning
alone. Each series has a label, lines a dash pattern, states a shape or a word ("failed"), deltas
a sign and the word better or worse. Look at the screen with the browser's vision-deficiency
emulation (Chrome DevTools, Rendering) and in greyscale: every series must still be told apart.

## Step 7: build it, per profile and per level

`python3 ../forge/gitguard.py` must exit 0 first. Then, as `../forge-plan/profiles.md` has the stack:

- **Queries on the server, under the user's access rules.** A dashboard is the classic place to leak
  another tenant's data: every aggregate is filtered by the signed-in user or team in the query
  itself, through the same policy or scope the rest of the app uses. Never filter in the browser,
  never take a team ID from the URL without checking it. laravel: scoped Eloquent queries in a
  controller or Livewire component; django: querysets filtered on `request.user` in the view; next:
  server components or route handlers reading the session; static: no server, so only the user's
  own data in the browser or figures built into the site, never a JSON with other people's rows.
- **A test with a second user** for every query, drill-down and data feed: user B sees none of user
  A's numbers (403, 404 or B's own totals), and a signed-out request gets nothing.
- **Aggregates are cached with a stated freshness** ("updated 5 minutes ago"). The cache key holds
  the user or team and the period; a shared key leaks as surely as a missing filter. Money is
  summed in cents in the database, periods are cut in the business's time zone.
- **Charts are inline SVG first.** Ahead of time: `python3 ../forge-design/chart.py data.json --type
  line --out <file>` (`--help` has the data shape; without `--tokens` it follows the theme's CSS
  variables). Per request or interactive: a small component in the app's own templates with the
  same anatomy (reference section 6). A chart library only when the interaction needs it (zoom,
  brushing, thousands of points): one well-known package, installed locally, with its licence noted.
- Numbers are formatted as the reference says (tabular figures, thousands, EUR, percentage points).

**Level 2 adds** the tiles with change and sparkline, the period filter (GET parameters, so each
period has a link) and the skeleton and count-up of reference section 12. **Level 3 adds** draw-in
and morph, drill-down through the same scoped query plus one filter, the comparison, the value
matrix, and live refresh that stops in a hidden tab. **Level 4 adds** the HUD of reference section
13: the readout strip, leader lines, the linked crosshair (pointer and keyboard), charts with a 3D
look in CSS 3D or canvas 2D, and the sequence log. No library for any of these.

**Level 5 adds** the data scene of reference section 14:

1. `npm install three` in the project, without asking again: the level said yes. Read the licence of
   the version installed (`node_modules/three/LICENSE`) and run `python3 ../forge-check/deps.py .`.
2. Copy `../forge-design/scenes/datascape.js` with `stage.js`, `glsl.js` and `lazy.js` from the same
   folder into a `scenes/` folder of the app's scripts. Never load them, or three, from a URL.
3. Feed it from the server: the same scoped query as the table returns the matrix, and the page
   passes it to `setData`. A filter change fetches the new matrix, calls `setData` and eases
   `setProgress`, so the camera moves. Mount it with `lazyScene`, with a poster for weak devices,
   no WebGL and reduced motion. No data: the empty state, never the scene's sample values.
4. The table of the same data is one key press away (reference section 14) and always in the page.

## Step 8: every state

Build and write under `## States` what each panel shows when: **loading** (a skeleton of the same
size, no layout jump), **empty** (what to do to get data, never a flat zero line), **error** (what
failed, a retry, the other panels still work), **partial** (the period is not over: say so, or
compare like with like), **stale** (the time of the last update, and a mark when it is too old),
**extreme values** (zero, negative, a million, one huge outlier), **long labels** (60 characters,
no overlap) and **time zones** (day edges in the business's zone, daylight saving weeks). From level
3 also **live** (a refresh that fails keeps the last values and says so) and **paused**.

## Step 9: accessibility

- Each chart has `role="img"`, a `<title>` and a `<desc>` with a text summary (first, last, lowest,
  highest), and its data as a table: on the screen, behind a "show as table" control, or as a link.
  The data scene of level 5 has the same summary in its `aria-label`, and its table one key away.
- Nothing by hover only: tooltips open on keyboard focus as well, can be dismissed, and the values
  that matter are printed on the chart or in the table. Every control, the crosshair too, works by keyboard.
- Text meets 4.5:1, marks 3:1. Live numbers do not announce every tick: `aria-live="polite"` on a
  summary at most. Under `prefers-reduced-motion` the final values show at once, nothing is lost.

## Step 10: make it show, and prove it

1. Make it show (rules.md section 9): restart or rebuild what serves the URL, bump a service
   worker's cache when it holds old files, and load the URL yourself. Work in a worktree or copy:
   start the app from your folder on a free port, or give the one command that switches the
   user's folder to the branch. After the first finished panel, show the user its before and
   after; then one line per finished panel.
2. "After", from that URL: `node forge-work/design/shots.mjs <URL> forge-work/dashboard/after
   --viewport-only --state <saved sign-in> --frames --video /dashboard`. Look at each picture at
   390px and 1440px, light and dark: no overlap, no cut-off number, the reading order holds.
3. `python3 ../forge-design/changed.py forge-work/dashboard/before forge-work/dashboard/after` must
   say VISIBLE CHANGE. From level 2, `python3 ../forge-design/changed.py --moves
   forge-work/dashboard/after/dashboard-390-f*.png` must say that something moves. "No visible
   change" is never a finished run: find which reason of rules.md section 9 it is and fix that first.
4. In the browser: no console errors; the "show as table" control and the keyboard path work; from
   level 5 also with WebGL off (the poster shows) and with reduced motion (one still frame).

## Step 11: check and commit

1. `python3 ../forge-design/dashcheck.py forge-work/dashboard.md --level auto` exits 0.
2. `python3 ../forge-design/contrast.py forge-work/design/tokens.json` exits 0, chart roles included. A
   colour chart.py derived (`--tokens ... --json` lists `colours`) becomes a `chart-N` role first.
3. The access test with the second user passes, with the rest of the suite.
4. `python3 ../forge/level.py check dashboard --report forge-work/dashboard.md` exits 0.
5. Write `## Checks` with each result. `python3 ../forge-check/secretscan.py .` exits 0, then the
   commits: the queries and their test first, then the screen: `build: dashboard`.

## Output

- The dashboard screen in the app, its queries, the second-user test and the commits.
- `forge-work/dashboard.md`. Its first lines are `Level: N (Name)` (exactly one such line, the level
  of Step 2) and `Served:` (Step 1), then the sections `## Audience`, `## Numbers`, `## Layout`,
  `## Charts`, `## States` and `## Checks` (with dashcheck.py's and changed.py's results and the
  paths of the pictures and the clip). Pictures in `forge-work/dashboard/before` and `after`.

## Next

Hand it over as rules.md section 9 says, in plain words: the branch the work is on; the address
that shows it now; where to click first (the period filter, a drill-down, the T key at level 5);
that a system set to reduced motion shows the calm version, and how to check that setting; the
paths of the before and after pictures and of the clip (`forge-work/dashboard/after/dashboard-1440.webm`);
and how to go back (`git switch <their branch>`). Merging and deploying stay their step.

Checkpoint, at most 5 plain lines: the level, who it is for and the numbers shown; the forms and
what moves; the access test and the checks; what is seed data or not built; the clip to watch.
Wait for the user's go. Then `/forge-design motion` or `/forge-check test`, or back to `/forge`
when it runs the phases.
