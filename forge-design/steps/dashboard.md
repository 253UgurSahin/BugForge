# forge-design design: dashboard

A part of `/forge-design`. Its `SKILL.md` has the ground rules, the levels and how the result is shown: read it first.

Reads `forge-work/plan.md`, `forge-work/design/tokens.json` and the app's own schema. Writes the dashboard
screen in the app and `forge-work/dashboard.md`. On the user's own app (no plan.md): read the schema and
the existing styles, and follow the code's stack (`python3 ../forge-check/detect.py .`).

Also for this skill:

- **Honest numbers.** Every number on the screen traces back to a table and a query. Never a number
  that cannot be traced, never invented data shown as real. Seed data is fine in development: the
  source says `seed` and the screen labels it. No data yet is an empty state, not a made-up chart.
- **Your own design**, made here from the user's numbers and the design tokens. Never rebuild
  another product's dashboard screen, and no stock template look.
- **Nothing from outside.** No CDN, no web font, no hosted chart or analytics script. A chart library
  only when Step 5 allows it, installed from the package registry and bundled with the app.

## Step 1: who looks, which decisions, which numbers

Ask one question: "Who opens this dashboard, how often, and what do they decide with it?" (auto
mode: decide from plan.md's Why, roles and flows, and write the choice down). Then pick at most 5
to 7 numbers that change what that reader does. A number that never changes a decision is left out.
Write `## Audience` (reader, moment, decisions) and `## Numbers` in `forge-work/dashboard.md`:

```markdown
| number | definition | source | unit | period | compared with | form |
| --- | --- | --- | --- | --- | --- | --- |
| Revenue | paid orders, refunds taken off, tax left out | `orders` where status = paid, sum(total_cents) | EUR | this month, Europe/Amsterdam | last month | tile + line |
```

Definition: exactly what is counted and what is left out. Source: the table and the query or filter.
Unit: EUR, %, percentage points, ms, or the thing counted. Period: with its time zone. Compared
with: the earlier period, a target, or `-` with the reason. A pipe inside a cell goes in backticks.
Run `python3 ../forge-design/dashcheck.py forge-work/dashboard.md`: it must exit 0.

## Step 2: the layout

Read `../forge-design/dashboard.md` (grid recipes, densities, the HUD pattern). Write `## Layout`:

- **Grid and reading order.** The most important number top left, then left to right, top to bottom:
  tiles first, the main chart under them, detail tables and feeds last. One screen, one question.
- **Density**: `calm` (a business overview), `standard` (a daily work screen) or `dense` (a HUD for
  people who watch it all day). Take the sizes from the reference. Dense is still readable: text of
  11px or more, real contrast, no decoration that carries no data.
- **Responsive** down to 390px: tiles go to two columns, then one; panels stack in reading order;
  wide tables scroll inside their own box; nothing is hidden on a phone that a decision needs.
- **Light and dark** from the tokens (`color` and `color.dark`). A HUD may be dark by default; it
  still follows the tokens, so the rebrand and the contrast check keep working.

`../forge-design/dashboard.example.html` is one worked dense example. Use its structure, not its
content or its looks: your screen is built from this app's numbers and tokens.

## Step 3: the form per number

Use the chart chooser in the reference and write `## Charts`: per number the form and why. In short:
one number beats a chart; a line for time; bars for comparison, from zero; a table for looking things
up; no pie or donut over 5 parts; no 3D, gauge or dual axis. Run dashcheck.py again after changes.

## Step 4: colours

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

## Step 5: build it, per profile

`python3 ../forge/gitguard.py` must exit 0 first. Then, as `../forge-plan/profiles.md` has the stack:

- **Queries on the server, under the user's access rules.** A dashboard is the classic place to leak
  another tenant's data: every aggregate is filtered by the signed-in user or team in the query
  itself, through the same policy or scope the rest of the app uses. Never filter in the browser,
  never take a team ID from the URL without checking it. laravel: scoped Eloquent queries in a
  controller or Livewire component; django: querysets filtered on `request.user` in the view; next:
  server components or route handlers reading the session; static: no server, so only the user's
  own data in the browser or figures built into the site, never a JSON with other people's rows.
- **A test with a second user** for every query: user B sees none of user A's numbers (403, 404 or
  B's own totals), and a signed-out request gets nothing.
- **Aggregates are cached with a stated freshness** ("updated 5 minutes ago"). The cache key holds
  the user or team and the period; a shared key leaks as surely as a missing filter. Money is
  summed in cents in the database, periods are cut in the business's time zone.
- **Charts are inline SVG first.** Ahead of time (the static profile's build, a job, a report):
  `python3 ../forge-design/chart.py data.json --type line --out <file>` (`--help` has the data
  shape; without `--tokens` it follows the theme's CSS variables). Rendered per request or
  interactive: a small component in the app's own templates with the same anatomy (reference, "SVG
  chart anatomy"). A chart library only when the interaction needs it (zoom, brushing, thousands of
  points): one well-known package, installed locally, bundled, with its licence in the build log.
- Numbers are formatted as the reference says (tabular figures, thousands, EUR, percentage points).

## Step 6: every state

Build and write under `## States` what each panel shows when: **loading** (a skeleton of the same
size, no layout jump), **empty** (what to do to get data, never a flat zero line), **error** (what
failed, a retry, the other panels still work), **partial** (the period is not over: say so, or
compare like with like), **stale** (the time of the last update, and a mark when it is too old),
**extreme values** (zero, negative, a million, one huge outlier), **long labels** (60 characters,
no overlap) and **time zones** (day edges in the business's zone, daylight saving weeks).

## Step 7: accessibility

- Each chart has `role="img"`, a `<title>` and a `<desc>` with a text summary (first, last, lowest,
  highest), and its data as a table: on the screen, behind a "show as table" control, or as a link.
- Nothing by hover only: tooltips open on keyboard focus as well, can be dismissed, and the values
  that matter are printed on the chart or in the table. Every control is reachable by keyboard.
- Text meets 4.5:1, marks 3:1. Live numbers do not announce every tick: `aria-live="polite"` on a
  summary at most. Animation follows `prefers-reduced-motion`.

## Step 8: check and commit

1. `python3 ../forge-design/dashcheck.py forge-work/dashboard.md` exits 0.
2. `python3 ../forge-design/contrast.py forge-work/design/tokens.json` exits 0, chart roles included. A
   colour chart.py derived (`--tokens ... --json` lists `colours`) becomes a `chart-N` role first.
3. The access test with the second user passes, with the rest of the suite.
4. Rebuild the stack and take screenshots at 390px and 1440px, light and dark, into
   `forge-work/dashboard/`: `npx playwright screenshot --viewport-size=390,844 <url> <file>`. Look
   at each: no overlap, no cut-off number, the reading order holds.
5. Write `## Checks` with each result. `python3 ../forge-check/secretscan.py .` exits 0, then one
   commit: `build: dashboard`.

## Output

- The dashboard screen in the app, its queries, the second-user test and one commit.
- `forge-work/dashboard.md` with the sections `## Audience`, `## Numbers`, `## Layout`, `## Charts`,
  `## States` and `## Checks`; screenshots in `forge-work/dashboard/`.

## Next

Checkpoint, at most 5 plain lines: who it is for and the numbers shown; the density and the forms;
the access test and the checks; what is seed data or not built; how to open it. Wait for the user's
go. Then /forge-design motion or /forge-check test, or back to /forge when it runs the phases.
