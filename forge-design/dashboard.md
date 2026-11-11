# Dashboard reference

For the dashboard part of `/forge-design` (`../forge-design/steps/dashboard.md`). Sizes are px and
come from the design tokens where a token exists (`--space-*`, `--text-*`, `--color-*`); the numbers
here are starting points, not a house style. `../forge-design/dashboard.example.html` shows the dense
layout built from these recipes. What each dashboard level looks like: sections 12 to 14. Shots of a signed-in dashboard: section 15.

## 1. The chart chooser

First ask what the reader wants to know, then pick the form. Go down the table; take the first match.

| the reader wants to know | form | notes |
| --- | --- | --- |
| how much, right now | one number (a KPI tile) | a single number beats any chart; add the comparison as text |
| is it going up or down | number + sparkline | the sparkline has no axis: it only shows the shape |
| how it changed over time | line | time on the x axis, left to right; up to 4 lines, labelled at their ends |
| a total over time and its parts | stacked area, or small charts side by side | at most 4 layers; the largest at the bottom |
| which is biggest (categories) | bars, sorted by value | always from zero; horizontal when the labels are long |
| parts of one whole, 2 to 5 parts | stacked bar, or a donut with the total in the middle | over 5 parts: bars. Never two donuts to compare |
| how two numbers relate | scatter | only for readers who know one; otherwise two bars |
| a pattern over two dimensions (hour by weekday) | value matrix (section 9) | print the values when the cells are big enough |
| against a target | number with the target as text, or a bullet bar | a bar with a mark for the target; not a gauge |
| one exact value among many | table | sorting, a filter; right-align the numbers |
| what just happened | feed or log table | newest first, a time on every row |

Never: 3D, a gauge or speedometer, two y axes in one chart, a pie over 5 parts, a y axis cut off for
bars, smoothed lines that invent values between points, a chart for one or two values, a legend when
a direct label fits, rainbow colours, a red and green pair as the only difference. The one exception
is depth at dashboard level 4 and 5 (sections 13 and 14): a view on top of a flat, honest form, with
every value printed or in a table next to it, never the only way to read a number.

chart.py draws `line`, `area`, `bar`, `spark` and `donut`, and refuses the nonsense above: no points,
values that are not numbers, a donut with negative values or over 6 parts, stacked series of
different lengths. Its exit 2 is a finding about the data or the form, not something to work around.

## 2. The KPI tile

```
REVENUE                      label: what it is, in the reader's words, 11 to 13px, muted
19,089 EUR                   value: the largest text in the tile; the unit smaller, next to it
+7.9% vs last month, better  delta: sign, amount, compared with what, and the word better or worse
~~~~~~/\~~                   sparkline: the same period as the delta, no axis (optional)
1 to 12 March, Europe/Amsterdam   period and time zone; "updated 5 min ago" when cached
```

- **Direction is not goodness.** Up is good for revenue and bad for error rate. Each number records
  which way is good; the colour (success or danger role) and the word follow that, not the sign.
  No target and no "good" direction (a queue length at night): show the delta in the text colour.
- The delta compares like with like: this month so far against the same days last month, or mark the
  period as not finished. Never a full month against half of one.
- A percentage change of a small base ("+300%", from 1 to 4) misleads: show the two values instead.
- Four to six tiles in a row at most. A tile is a link to its detail when there is one.
- States: loading (a grey block the size of the value), no data ("No orders yet. Share your booking
  link to get the first one."), error ("Could not load. Try again"), stale (the time, in the warning role).

## 3. Number formatting

Format on the server or with the platform's `Intl.NumberFormat`, in the app's locale, never by hand.

| what | rule | example (en) | example (nl) |
| --- | --- | --- | --- |
| money | integer cents in the database, currency code from the row, no float maths | EUR 1,234.50 or €1,234.50 | € 1.234,50 |
| large money on tiles | whole units from 1,000 up; abbreviate only when space forces it | €19,089 / €1.2M | € 19.089 / € 1,2 mln |
| counts | thousands separators from 1,000 | 12,480 | 12.480 |
| percent | one decimal under 10%, none above; the sign for a change | 4.2% / 42% / +7.9% | 4,2% |
| change of a percentage | percentage points, not percent: 4.2% to 4.6% is +0.4 pt (it is also +9.5%) | +0.4 pt | +0,4 pp |
| durations | one unit that fits: ms under 1 s, then s, min, h | 212 ms / 1.4 s | 212 ms / 1,4 s |
| rounding | round for display only, at the last step; totals are summed from unrounded values | | |
| zero and none | 0 is a value; no data is a dash with a reason, never 0 | 0 / - | |
| negative | a real minus sign or a hyphen in front; never brackets or red alone | -120 | |
| dates and times | the business's time zone, named once per screen; ISO in `datetime=` attributes | 12 Mar, 14:00 | 12 mrt 14:00 |

Numbers that are compared sit in columns with `font-variant-numeric: tabular-nums` and are
right-aligned, so the digits line up. Values in a chart use the same format as the tile next to it.
chart.py prints English thousands separators and at most two decimals inside the SVG; for another
locale write the component in the app's templates (section 6).

## 4. Grid recipes

```css
/* tiles: as many per row as fit, never narrower than 180px, no media query needed */
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--space-4); }

/* the page: 12 columns on wide screens; panels say how many they span */
.board { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: var(--space-4); }
.panel-main { grid-column: span 8; }
.panel-side { grid-column: span 4; }

/* subgrid: label, value and delta line up across all tiles of a row */
.tiles { grid-auto-rows: auto; }
.tile { display: grid; grid-row: span 3; grid-template-rows: subgrid; }

/* container queries: a panel adapts to its own width, not the window's, so it works in any column */
.board { container-type: inline-size; }
@container (max-width: 860px) { .panel-main, .panel-side { grid-column: 1 / -1; } }
@container (max-width: 420px) { .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
```

- `minmax(0, 1fr)`, not `1fr`: a long number or a wide table can then never push a column wider.
  Grid and flex items that hold text get `min-width: 0` as well: a 60-character name then wraps or
  is cut with its full text reachable, and never pushes the page sideways at 390px.
- Reading order is source order. Do not reorder panels with `order` or grid placement on small
  screens: keyboard and screen reader users would get a different order than the eye.
- 390px: one column of panels, tiles in two columns; a table scrolls inside `overflow-x: auto` on a
  focusable wrapper (`tabindex="0"`, `role="region"`, a label); touch targets stay 44px.
- Fix the height of chart panels (or use `aspect-ratio`) so loading and loaded are the same size.

## 5. The three densities

| | calm | standard | dense (HUD) |
| --- | --- | --- | --- |
| dashboard level | 1 | 2 and 3 | 4 and 5 (3 when the reader watches it all day) |
| for | an owner who looks once a day or week | a team that works in it daily | people who watch it all day, on a big screen |
| numbers on screen | 3 to 5 | 5 to 7 | 7 to 9, in groups |
| page padding / gap | 32 / 24 | 24 / 16 | 16 / 12 |
| panel padding | 24 | 16 | 12 |
| tile value | 32 to 40, weight 600 to 700 | 24 to 28 | 20 to 22, tabular figures (monospace for a technical concept) |
| label | 13 to 14 | 12 to 13 | 11 to 13; capitals and letter-spacing .08em when the concept's type uses them |
| body and table text | 16 | 14 | 12 to 13 |
| table row height | 48 | 40 | 28 to 32 |
| chart height | 280 to 360 | 220 to 280 | 84 to 220 |
| panel look | surface, radius, a soft shadow | surface, radius, a 1px border | 1px frame, the brief's smallest radius, no shadow |
| theme | the brief's default | the brief's default, both themes | the brief's default (dark first only for a technical concept), both themes |

Never under 11px, at any density. Dense means less padding and smaller type, not less contrast.
Phones get one level calmer than the desktop: a dense screen at 390px is the standard sizes.

## 6. SVG chart anatomy

Every chart, from chart.py or written in the app's templates, has the same parts:

```html
<figure>
  <figcaption>Orders per day</figcaption>
  <svg viewBox="0 0 640 280" role="img" aria-labelledby="c1-t c1-d">
    <title id="c1-t">Orders per day, 1 to 12 March</title>
    <desc id="c1-d">12 points, first 22, last 34, lowest 11 on 3 March, highest 96 on 8 March.</desc>
    <!-- grid lines with 1-2-5 ticks, the zero baseline, the marks, direct labels -->
  </svg>
  <details><summary>Show as table</summary><table>...</table></details>
</figure>
```

- **Ticks** in steps of 1, 2 or 5 times a power of ten, four to six of them; grid lines faint, the
  zero baseline in the text colour. Bars and areas start at zero. A line may start elsewhere.
- **Labels beat legends**: up to 4 series are labelled at the end of their line. More series than 6:
  the top 5 and "Other". Mark the one point that matters (the peak, today) with a leader line.
- **Colours** are CSS variables (`var(--color-chart-1)`), so light, dark and the rebrand need no
  change. Series also differ by dash pattern, shape or position.
- **Text does not scale.** A chart that stretches with its panel keeps only the shapes in an SVG with
  `preserveAspectRatio="none"` and `vector-effect: non-scaling-stroke`; the axis labels and callouts
  are HTML around it, placed by percentage (the example page does this). A chart with text inside
  the SVG (chart.py) is made at the size it is shown: `--width` near the panel's width.
- **Untrusted data.** Labels come from the database, so they are escaped by the template, never
  pasted into markup. No inline event handlers. A strict Content-Security-Policy blocks `style=`
  attributes: use presentation attributes (`fill`, `stroke`) or classes.
- **Interaction**: a focusable point (`tabindex="0"`) per value that matters, with its text in an
  `aria-label`; the tooltip opens on focus as well as hover and closes on Escape. Thousands of
  points or zooming: then a library, bundled locally, with the table still next to it.

## 7. The HUD pattern

A dense screen. It works when every element is data; it fails when it is costume. Its parts (the
strip, the panels, the leader lines, the crosshair, the log, the charts with depth) are what
dashboard level 4 asks for. How they look is the brief's: its type, colours, default theme and
ornament. A warm or calm concept gets a warm, calm HUD, never a control room pasted on (a higher
level is more of the app's own taste: `../forge/levels.md`). Monospace values, capitals, panel
numbers, corner ticks and dark first belong to a technical concept (an instrument, a chart room, a lab).

- **Readout strip** across the top: 5 to 8 small tiles in one row (`auto-fit, minmax(150px, 1fr)`),
  1px lines between them, a small label (11 to 13px; capitals when the concept's type uses them),
  the value at 20 to 22px with tabular figures (monospace for a technical concept), the unit small,
  the delta in words. It is a `<dl>`: label `<dt>`, value `<dd>`.
- **Panels**: a 1px frame in the border role on the surface role, 12px padding, a small heading the
  log or an alert can refer to: its name, or a panel number on the right ("P-03") for a technical
  concept. Corner ticks (two 8px borders), only where the concept has such ornament, are
  decoration: `::before` and `::after`, nothing in the markup; in the accent only when the brief
  allows the accent on decoration, else in the `border-input` role.
- **Leader lines** join a main panel to the detail panels that split its numbers (the orders of P-01
  by region, by channel, by status), or a point to its callout. Draw them as one stretched SVG in its
  own grid column between the panels (`preserveAspectRatio="none"`, 1px `currentColor`,
  `aria-hidden="true"`), each ending at the measured centre of its panel: a `ResizeObserver` on the
  panels sets the path, as the side panels take the height their content needs (equal `1fr` rows
  stretch the main chart and leave panels half empty). Hide the column when the panels stack. A
  leader line must point at something: a screen whose side panels are not parts of the main chart
  (a list of what needs attention) draws none and says so under `## Built` (`none:` and why).
- **Value matrix**: section 9. **Dot field**: one mark per unit (workers, seats, days), state by
  shape as well as colour (filled, ring, diamond), a key with counts under it, and the counts as its
  accessible name.
- **Sparkline panel**: a three-column grid (name, sparkline, last value), one row per thing, all
  sparklines on the same time span.
- **Sequence log**: a real table, newest first: sequence number, time with its zone, event, result
  as a word (OK, Retry, Failed). Tabular figures (monospace for a technical concept), 28px rows, the
  event column may wrap.
- **Colour**: one accent for data, the text roles, and the danger role for what needs action. If
  everything glows, nothing is urgent. No fake scan lines, no blinking, no decorative numbers.
- **Theme**: the brief's default theme, dark first only when the concept is; both sets from the
  tokens, `color-scheme` set per theme.

## 8. Tables

- Numbers right-aligned with tabular figures; text left-aligned; the unit in the header, not in
  every cell. A caption or heading says what the rows are and for which period.
- **Sorting**: the header cell holds a `<button>`; the sorted column has `aria-sort="ascending"` or
  `"descending"`; sort on the server, with the sort key checked against a list of allowed columns.
- **Sticky header**: `thead th { position: sticky; top: 0; }` with a solid background, inside a
  wrapper with a set height. The first column may stick as well on wide tables.
- **Filters** above the table, as a form with labels: they work without script (GET parameters, so
  a filtered view has a link), show how many rows match, and have one "clear" control. The filter
  never widens access: the tenant filter is added on the server, after and apart from the user's.
- **Pagination** (the default): 25 or 50 rows, "1 to 25 of 312", server side with a stable order
  (a unique last sort key). **Virtual scrolling** only for thousands of rows that must be scanned in
  one go; it breaks find-in-page and needs careful keyboard work, so pick it late.
- Empty: one row that says why and what to do. Long text: wrap, or cut with the full text reachable.
  A row action is a link or button in the row, not a click on the whole row.

## 9. The value matrix

A matrix of values (hour by weekday, region by channel) is an HTML `<table>` with `<th scope>` on
both axes: it can be read out and looked up, which a picture cannot. Tint each cell on the
sequential ramp in five steps, by class: `.t1 { background: var(--color-chart-seq-1); }` up to
`.t5` and `chart-seq-5`, roles in tokens.json with their dark values. contrast.py checks the text on
the lightest and the darkest step (4.5:1); it cannot check a `color-mix` of the accent, so that is no
ramp. Print the value in every cell: the tint helps the eye, the number carries the meaning. Totals
go in a last row and column when they are asked for. Over about 12 by 12 cells: drop the numbers,
add a title per cell.

## 10. Colour sets

- **Categorical** (`chart-1` to `chart-6`): `chart-1` is the accent; the others turn the hue and
  alternate lighter and darker, so neighbours differ in lightness too. Each has 3:1 against the
  background. Over 6 categories: group the rest as "Other" in the muted text role.
- **Sequential**: one hue from faint to full, 5 steps, light means low (on dark: dim means low):
  `chart-seq-1` to `chart-seq-5`, the text on the first and the last step as pairs.
- **Diverging**: only when the middle means something (zero, a target): two hues with a neutral
  middle, never red against green; orange against blue survives every common colour blindness.
- **Status** uses the success, warning and danger roles, always with a word or a shape.
- All of them are roles in tokens.json with their dark values, checked by
  `python3 ../forge-design/contrast.py forge-work/design/tokens.json`.

## 11. The classic mistakes

- A number without a definition: "users" (signed up, active, paying?), revenue with or without tax.
- Another tenant's rows in a total: the filter was in the screen, not in the query, or the cache key
  had no team in it. Test with a second user, every time.
- Sample data left in: a chart of invented values next to real ones, with nothing to tell them apart.
- Averages that hide the problem: a mean response time instead of the 95th percentile; an average
  of averages; a total next to a count with a different filter.
- Comparing a month that is not over with a full one, or days cut at UTC midnight for a Dutch shop.
- Too much: fifteen tiles, six colours, a legend to decode, a chart for every column in the table.
- Decoration as data: gauges, 3D, gradients on bars, an animated counter that hides the value for a second.
- Colour alone: red and green deltas with no sign, a status dot with no word.
- A chart with no empty state: a flat line at zero looks like bad news, not like "no data yet".
- Hover only: the exact value lives in a tooltip that a phone, a keyboard and a screen reader never see.
- A slow query run again on every visit with no freshness time; or a cache on a fast query, which only adds a stale number and a key that can leak.

## 12. What each level looks like

A level includes everything below it, and nothing above it (`../forge/levels.md`). Durations and
curves come from the motion tokens; under `prefers-reduced-motion: reduce` nothing draws in, morphs
or counts: the final values show at once, and no information is lost.

- **1 Subtle**: calm. One row of 3 to 5 tiles (value, label, the comparison as text), under it one
  chart that answers the main question (usually a line over time), under that one table with the
  rows behind the numbers. The default period only. Motion: hover and focus feedback, a fade in.
  At 1440px it fits on one screen without scrolling.
- **2 Polished**: standard. Tiles with their change and a sparkline (section 2), 2 or 3 charts on
  the 12-column board (8 and 4), a period filter as a form with GET parameters (7 days, 30 days,
  this month, a range of your own), so a period has a link. Every state of the steps file is
  designed. Motion: skeleton to content, numbers count up once (at most 600 ms, the final value is
  in the markup from the start), a period change fades the panels across.
- **3 Expressive**: standard, or dense for a screen that is watched all day. Charts draw in (a
  line by its `stroke-dashoffset`, bars grow from the zero baseline) and morph between periods
  (the same number of points: move each point; else fade across). **Drill-down**: a tile, bar or
  cell is a link to the rows behind it, with its own URL, served by the same scoped query plus one
  filter. **Comparison**: the earlier period as a faint second line, or a change column. A value
  matrix (section 9). **Live refresh**: every 30 to 60 seconds, or server-sent events; it stops in
  a hidden tab, has a pause control, and only a short summary is `aria-live="polite"`.
- **4 Showpiece**: dense: the HUD composition of section 13. Its parts are the level; its type,
  colours, theme and ornament are the concept's (section 7), dark first only when the concept is.
- **5 Cinematic**: section 13 plus the data scene of section 14, which shows the same data as the
  table and the matrix in 3D. The table stays one key press away.

Name what moves or drills down in the form column of `## Numbers` ("line, draws in, morphs
between periods; drill-down to the orders"): `dashcheck.py --level 3` and up looks for it.

## 13. The HUD composition (level 4)

Everything that matters on one screen, at 1440 by 900. Every element is data. The parts below are
the level; their type, colour, theme and ornament come from the brief (section 7), so the sketch
shows the structure, not a look:

```
+--------------------------------------------------------------------------------+
| READOUT STRIP  5 to 8 readouts, a <dl>                  updated 14:02 CET  [||] |
+-----------------------------------+----+---------------------------------------+
| P-01 main chart, time axis        |  / | P-02 detail                           |
|      the crosshair runs here      | -- | P-03 detail                           |
|                                   |  \ | P-04 detail                           |
+-----------------------------------+----+---------------------------------------+
| P-05 value matrix or depth chart        | P-06 sequence log, newest first      |
+-----------------------------------------+--------------------------------------+
```

- **Grid**: the strip spans all 12 columns; then the main panel 7, the leader-line column 1, three
  detail panels stacked in 4, each as tall as its content; then two panels of 6. Panel numbers
  (P-01) let the log refer to them.
- **The linked crosshair**: one position (an index on the shared time axis) drives a thin vertical
  line on every chart with that axis. One small script holds the position and sends a custom event;
  each chart listens. Pointer: it follows. Keyboard: the arrow keys on the focused main chart move
  it, Home and End jump, Escape lets go. One text line under the strip says the time and the values
  at that moment, updated at most twice a second. Readouts that are period totals keep their period
  value; only while the crosshair is held or chosen, each adds the moment's value in its sub-line
  ("on 7 Nov: 4"). Charts on another axis do not follow it. Move the line on the compositor: an
  overlay with `container-type: inline-size`, the line at `translate: calc((var(--i) + .5) /
  var(--n) * 100cqw) 0` with a transition on `translate`; never `left` with a transition (layout).
- **Charts with a 3D look**: CSS 3D (a panel tilted by at most 12 degrees with `perspective` on its
  parent, bars as faces with a side and a top: `../forge-design/bars3d.css` is the recipe) or canvas
  2D drawn with depth (an isometric grid of bars). The depth is a view: no strong perspective (a
  near bar must never look bigger than a far bar of the same value), one baseline, every value
  printed or in the table next to it. Write it in the form column with its table: "bars with depth
  (CSS 3D) + table". The bars grow by `translateY`, never by `scaleY` (it squashes the top and side
  faces) or `height` (layout); the crosshair runs behind them; the kit's `depth.js` may lean the
  plane, with the bars inside a `data-depth-layer` wrapper (depth.js writes `transform` on a layer).
- **Leader lines** and the **sequence log**: section 7. The log takes the events the readouts
  react to (an import finished, a threshold crossed), with the panel number.
- **Motion**: a readout that changes tints its background once (300 ms, never a blink), a new log
  row slides in, the crosshair follows the pointer without lag.
- **390px**: the strip in two columns, panels stacked in source order, the leader column hidden,
  the crosshair moved by tapping the chart and by two buttons (earlier, later).
- **The look's scene on the same screen.** At look level 4 or 5 the app's first screen holds the
  living scene (`../forge/levels.md`, "What each look level shows": a third of the height at 1440,
  the full width at 390). When that first screen is this data screen, the scene is the HUD's top
  band, fed by the screen's own numbers (the kit scene's `setData`, values 0 to 1, from the same
  scoped query), with the readout strip right under it (or on it over a scrim, text 4.5:1); the
  panels start below, so the HUD may run past 900px. When the app's first screen is another one,
  the scene stays there and the HUD keeps its 1440 by 900.

## 14. The data scene (level 5)

- **What**: `../forge-design/scenes/datascape.js` from the scene kit shows a matrix of the app's
  own values (region by week, hour by weekday) as a 3D field of bars or ridgelines. It needs three
  (through the app's own package manager, `../forge-design/motion.md` section 5; never a CDN) and
  the kit's `stage.js`, `glsl.js` and `lazy.js` next to it. Read the comment at the top of
  datascape.js for its options before you use them.
- **Fed from the server**: the same query as the table and the matrix, under the same access rules,
  returns the rows, the columns and the values for the signed-in user's team and the period. The
  page passes the values to `setData`. The scene draws sample values when it gets none: mount it
  only when there is data, and show the empty state otherwise. Heights may be scaled from 0 to 1 in
  the page; the real values stay in the table and in the tooltip.
- **A filter changes**: fetch the new matrix, call `setData` (the bars spring to their new
  heights) and ease `setProgress` over the change, which moves the camera. The page's own text
  says what changed ("week 12 to 24, region North").
- **Hover**: `onHover({index, row, column, value})` shows an HTML tooltip (escaped text) and marks
  the matching table cell; `onHover(null)` hides it. The keyboard path is the table, not the canvas.
- **Accessible**: the scene's container has `role="img"` and an `aria-label` with the text summary
  (what, period, highest and lowest). The table of the same data is one key press away: a button
  "Show as table (T)" with `aria-keyshortcuts="t"`; T outside a text field does the same. It swaps
  the scene for the table and moves focus to the table's caption; the same key goes back. The
  table is in the page from the start, so a screen reader and find-in-page always reach it.
- **Calm by default**: `lazyScene` loads three only when the panel is near and the page is idle,
  with a poster (a still of the scene) until then. Without WebGL the container gets
  `data-scene="fallback"` and the poster stays; under `prefers-reduced-motion` the scene draws one
  still frame; one `motionToggle` button pauses every scene. One scene per screen; `destroy()` when
  the dashboard is left in an app that does not reload the page.

## 15. Shots of a signed-in dashboard

`../forge-design/shots.example.mjs` only looks: it never clicks or types. A dashboard behind a
sign-in therefore needs a saved session, or before and after both show the sign-in page and
changed.py finds no change. Write `forge-work/design/signin.mjs` once, next to `shots.mjs` (so it
finds the same Playwright), and fit the three form lines to the app's own sign-in form:

```js
// DEMO_EMAIL=.. DEMO_PASSWORD=.. node forge-work/design/signin.mjs http://localhost:3000 /app/statistieken
// another reader, their own file: ... signin.mjs http://localhost:3000 /admin forge-work/design/admin.json
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
let pw; try { pw = require('@playwright/test'); } catch { pw = require('playwright'); }
const [base, path = '/', state = 'forge-work/design/alice.json'] = process.argv.slice(2);
const { DEMO_EMAIL: email, DEMO_PASSWORD: password } = process.env;
if (!base || !email || !password) { console.error('usage: DEMO_EMAIL=.. DEMO_PASSWORD=.. node signin.mjs BASE [PATH] [STATE]'); process.exit(2); }
const browser = await pw.chromium.launch();
const context = await browser.newContext();
const page = await context.newPage();
const errors = [];
page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
page.on('pageerror', (error) => errors.push(String(error)));
await page.goto(new URL('/login', base).href);
await page.getByLabel(/e-?mail/i).fill(email);
await page.getByLabel(/password|wachtwoord/i).fill(password);
await page.getByRole('button', { name: /sign in|log in|inloggen/i }).click();
await page.waitForURL((url) => !url.pathname.startsWith('/login'));
await context.storageState({ path: state });
errors.length = 0; // only the errors of the dashboard itself
await page.goto(new URL(path, base).href, { waitUntil: 'load' });
await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {}); // a live refresh never goes quiet
await page.waitForTimeout(1500);
console.log(errors.length ? errors.join('\n') : 'no console errors on ' + path);
await browser.close();
process.exit(errors.length ? 1 : 0);
```

- The account is a demo or seed user: the app's own demo-account or seed script when it has one,
  else one you create in the dev database after the user's yes. Never the user's own password, and
  never a password in a file: give it in the command's environment.
- That user has enough rows to fill every panel (a week of catches is not enough for a heat map by
  month). A near-empty dev database shows empty states: honest, but nothing of the level shows.
  Ask before you add seed rows; the screen labels them seed, and the checkpoint says so.
- Each state file (`alice.json`, `admin.json`) holds a session: it stays in `forge-work/`
  (git-ignored, never shipped) and is passed as `--state` to the shots of its reader's screens,
  before and after alike.
- Run it again after the build: it prints each console error of the dashboard and exits 1 on any.

**The full states with a fixture.** No yes for seed rows (the whole look asks nothing after the
pick), and always for the extremes and long labels of the steps' Step 8: a fixture, never in the
user's database. Make the rows with the app's own code (its statistics function on invented rows: a
month of 1,234, a 60-character name, one failed load) and save them as
`forge-work/design/fixture.json`. The hand-over says which state the user's own data shows ("few").

- **Data the browser fetches** (an API route the page calls): `forge-work/design/fixture.mjs` below,
  next to `shots.mjs` as signin.mjs is, answers that route with the fixture and takes the shots at
  390 and 1440 itself (shots.mjs only looks, so it cannot do this).
- **A screen the server renders** (Blade, Django templates, Next.js server components, a period in
  GET parameters) has no route the browser can answer: give the fixture rows to a copy of the dev
  database behind a second instance of the app, run from a copy of the folder on a free port
  (`../forge/rules.md` section 9: install there, copy `.env` in, never printed; Next.js runs one dev
  server per folder). An SQLite file inside the project comes along in that copy; a database server
  (MySQL, PostgreSQL): a second database from a dump, only with the user's yes. Before any row goes
  in, point the copy at its own database through the environment, never by editing `.env`: the
  second database (`DB_DATABASE=`, `DATABASE_URL=`), and SQLite too, as `.env` often names the file
  by an absolute path that still leads to the user's own (`DB_DATABASE=<the copy>/database/database.sqlite`).
  That goes for the second instance and for every command that puts the rows in (a seeder, tinker,
  a shell). Check first, with that environment, where it writes (Laravel: `php artisan db:show`; Django:
  `connection.settings_dict['NAME']` in `manage.py shell`), or the rows land in the user's database.
  Put the rows in the copy, sign in on that address (signin.mjs, a state file of its own), run
  fixture.mjs there with `-` for the route, then stop that instance and delete the copy and its
  database. The user's own database is never touched.

```js
// node forge-work/design/fixture.mjs http://localhost:3000 /app/statistieken forge-work/dashboard/fixture '**/api/stats**'
// a screen the server renders, on the second instance: ... fixture.mjs http://localhost:3001 /app/statistieken OUT - STATE
// a screen nobody signs in for: STATE none
import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
const require = createRequire(import.meta.url);
let pw; try { pw = require('@playwright/test'); } catch { pw = require('playwright'); }
const [base, path, out, pattern = '-', state = 'forge-work/design/alice.json'] = process.argv.slice(2);
if (!out) { console.error('usage: node fixture.mjs BASE PATH OUT [ROUTE|-] [STATE|none]'); process.exit(2); }
if (state !== 'none' && !existsSync(state)) { console.error(`no ${state}: run signin.mjs first`); process.exit(2); }
const fixture = pattern === '-' ? null : JSON.parse(readFileSync('forge-work/design/fixture.json', 'utf8'));
const asked = new URL(path, base);
const bare = (name) => name.replace(/\/+$/, '') || '/';
mkdirSync(out, { recursive: true });
const browser = await pw.chromium.launch();
let failed = 0;
for (const [width, height] of [[390, 844], [1440, 900]]) {
  const context = await browser.newContext({ storageState: state === 'none' ? undefined : state,
    viewport: { width, height }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  if (fixture) await page.route(pattern, (route) => route.fulfill({ json: fixture }));
  const response = await page.goto(asked.href, { waitUntil: 'load' });
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {}); // a live refresh never goes quiet
  const landed = new URL(page.url()).pathname; // a redirect to the sign-in page answers 200 too
  const away = bare(landed) !== bare(asked.pathname) ? `it led to ${landed}, not ${asked.pathname}`
    : await page.locator('input[type="password"]:visible').count() ? `${landed} shows a password field` : '';
  const sideways = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  if (!away) await page.screenshot({ path: `${out}/fixture-${width}.png`, fullPage: true });
  const problem = away ? `${away}: a sign-in page? sign in again (signin.mjs); no picture`
    : !response?.ok() ? `status ${response?.status()}` : sideways ? 'WIDE, it scrolls sideways' : '';
  console.log(`${out}/fixture-${width}.png: ${problem || 'fits'}`);
  failed += problem ? 1 : 0;
  await context.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
```

Look at both pictures yourself: a long label wraps or is cut with its full text reachable, a
million fits its tile, the failed panel says it failed while the others still show.
