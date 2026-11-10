# Dashboard reference

For forge-design dashboard. Sizes are px and come from the design tokens where a token exists
(`--space-*`, `--text-*`, `--color-*`); the numbers here are starting points, not a house style.
`../forge-design/dashboard.example.html` shows the dense level built from these recipes.

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
a direct label fits, rainbow colours, a red and green pair as the only difference.

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
- Reading order is source order. Do not reorder panels with `order` or grid placement on small
  screens: keyboard and screen reader users would get a different order than the eye.
- 390px: one column of panels, tiles in two columns; a table scrolls inside `overflow-x: auto` on a
  focusable wrapper (`tabindex="0"`, `role="region"`, a label); touch targets stay 44px.
- Fix the height of chart panels (or use `aspect-ratio`) so loading and loaded are the same size.

## 5. The three density levels

| | calm | standard | dense (HUD) |
| --- | --- | --- | --- |
| for | an owner who looks once a day or week | a team that works in it daily | people who watch it all day, on a big screen |
| numbers on screen | 3 to 5 | 5 to 7 | 7 to 9, in groups |
| page padding / gap | 32 / 24 | 24 / 16 | 16 / 12 |
| panel padding | 24 | 16 | 12 |
| tile value | 32 to 40, weight 600 to 700 | 24 to 28 | 20 to 22, monospace |
| label | 13 to 14 | 12 to 13 | 11, capitals, letter-spacing .08em |
| body and table text | 16 | 14 | 12 to 13 |
| table row height | 48 | 40 | 28 to 32 |
| chart height | 280 to 360 | 220 to 280 | 84 to 220 |
| panel look | surface, radius, a soft shadow | surface, radius, a 1px border | 1px frame, no radius, no shadow |
| theme | light first | light and dark | dark first, light still works |

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

A dense, dark, technical screen. It works when every element is data; it fails when it is costume.

- **Readout strip** across the top: 5 to 8 small tiles in one row (`auto-fit, minmax(150px, 1fr)`),
  1px lines between them, label in 11px capitals, value in 20 to 22px monospace with tabular
  figures, the unit small, the delta in words. It is a `<dl>`: label `<dt>`, value `<dd>`.
- **Panels**: a 1px frame in the border role on the surface role, 12px padding, a small heading with
  a panel number on the right ("P-03") that the log or an alert can refer to. Corner ticks (two 8px
  borders in the accent) are decoration: `::before` and `::after`, nothing in the markup.
- **Leader lines** join a main panel to its detail panels, or a point to its callout. Draw them as
  one stretched SVG in its own grid column between the panels (`preserveAspectRatio="none"`, 1px
  `currentColor`, `aria-hidden="true"`), ending where the side panels' centres are: with three equal
  rows that is 1/6, 1/2 and 5/6 of the height. Hide the column when the panels stack. A leader line
  must point at something; lines that only fill space are noise.
- **Value matrix**: section 9. **Dot field**: one mark per unit (workers, seats, days), state by
  shape as well as colour (filled, ring, diamond), a key with counts under it, and the counts as its
  accessible name.
- **Sparkline panel**: a three-column grid (name, sparkline, last value), one row per thing, all
  sparklines on the same time span.
- **Sequence log**: a real table, newest first: sequence number, time with its zone, event, result
  as a word (OK, Retry, Failed). Monospace, 28px rows, the event column may wrap.
- **Colour**: one accent for data, the text roles, and the danger role for what needs action. If
  everything glows, nothing is urgent. No fake scan lines, no blinking, no decorative numbers.
- Dark first: set `color-scheme: light dark` and take both sets from the tokens.

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
both axes: it can be read out and looked up, which a picture cannot. Tint each cell on a sequential
ramp in five steps, by class (`.t1` to `.t5`), with the accent mixed into the surface:
`background: color-mix(in srgb, var(--color-accent) calc(var(--t) * 7%), transparent)`. Keep the
tint light enough that the text role still has 4.5:1 on the darkest step, and print the value in
every cell: the tint helps the eye, the number carries the meaning. Totals go in a last row and
column when they are asked for. Over about 12 by 12 cells: drop the numbers, add a title per cell.

## 10. Colour sets

- **Categorical** (`chart-1` to `chart-6`): `chart-1` is the accent; the others turn the hue and
  alternate lighter and darker, so neighbours differ in lightness too. Each has 3:1 against the
  background. Over 6 categories: group the rest as "Other" in the muted text role.
- **Sequential**: one hue from faint to full, 5 steps, light means low (on dark: dim means low).
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
- A dashboard that loads everything on every visit: no cache, no freshness time, a slow first screen.
