# Tidewatch: one app at five levels

Tidewatch is a made-up coastal passage planner for small boats. Every folder here is the same page
at another look level of forge-design (`../../plugin/forge/levels.md`): `1/` to `5/`. The page, its words and
its tokens stay the same; what changes is how much it moves and how deep it goes. `shared/` holds what
every level uses: `tokens.css`, `base.css`, `app.js` and the fonts with their licences.

Open them with `python3 examples/serve.py` from the root of the pack.

## The idea in one sentence

The page is a paper sea chart lying under a lamp: the hero is a drawn chart of the approaches to
Vlissingen with today's course pencilled on it, and everything below it is set the way a navigator's
papers are set (ruled like a tide table, lettered like a chart, with the safe window hatched in chart
magenta). At night the lamp turns red, as it does on a boat, and the chart becomes ink on a glowing sheet.

Everything on the page is made up: the app, the harbour data, the numbers.

## Type

Three open families, all SIL Open Font License 1.1, served from `shared/fonts/` with their licence files.
Each has one voice, so the reader can tell who is speaking.

| family | voice | where | axes used |
| --- | --- | --- | --- |
| Newsreader (Production Type) | the chart | headline, headings, harbour names, the day's figures, all chart lettering | `opsz` from 9 px soundings to the 108 px headline (optical sizing on, so small italics stay sturdy and the headline gets its hairlines); `wght` 300 headline, 350 figures, 400 headings, 420 to 500 chart italics, 600 town names |
| Instrument Sans (Instrument) | the app | body text, buttons, links, form fields | `wght` 400, 500, 600; `wdth` 84 to 92 for the small print (units, legend, chart notes), as tide tables use a narrow cut |
| Chivo Mono (Omnibus-Type) | the instruments | labels in capitals, times, bearings, positions, the tide table, the log | `wght` 500 labels, 600 and 700 for the figure that matters |

Why Newsreader: charts print water names in italic and land names upright. Newsreader has a sharp,
classical italic and optical sizes, so the same face can be a 9 px sounding and a 108 px headline. The
one word in italic in the headline ("window") follows that chart rule. Fraunces was the obvious pick and
was left out for being softer and more common.

Contrast in size is real: 108 / 46 / 30 / 26 / 21 / 16 / 13 / 11 px, never two neighbours on one line.
Figures are lining and tabular wherever they stack (tiles, cards, table).

## Colour

Light is the main theme: the chart by day.

- Neutral with a point of view: warm chart paper (`--color-bg` #f2ebdd), a lighter sheet for anything
  that lies on top of it (`--color-surface`), a shaded one for wells (`--color-sunk`), and one ink, a
  deep sea blue-black (`--color-text` #0e2a3b) that is also the rule colour and the footer.
- One accent: chart magenta (`--color-accent` #a8155b), the colour charts print their overlays in. It is
  allowed on two things only: the main action (the hero "Plan a passage" button, the dialog's submit) and
  the safe window (hatch and top bar in the tide curve, the cards, the table, the hero slip, figure A).
  Focus rings and the switched-on lamp use it as "current state". The top bar button is ink, so the first
  screen has one magenta button.
- Second hue, never a control: shoal blue (`--color-accent-2`) for depth contours; the water under the
  tide curve is the chart's own shallow-water tint. The hero chart has the usual chart tints (buff land,
  green drying banks, two blues for shoal water) as `--color-chart-*` tokens.

Dark is the same chart at night under a red-safe lamp, designed on its own, not inverted. The page goes
to a warm near-black, text to a pale warm paper, and the accent becomes the lamp itself (#ff6a4d with dark
text on it). Under red light blue and green ink go dark, so the chart tints become shades of black on a
sheet that glows red where the lamp falls; the neat line and the compass rose stay as a dim red print in
the gloom outside the pool.

All 40 text and control pairs of both themes pass WCAG AA with `plugin/forge-design/contrast.py`
(lowest text pair 5.17:1, lowest control edge 3.62:1).

## Shape and space

- Printed, so square. One radius family: 2 px where a finger presses, 0 elsewhere. No pills, no blur.
- Lines do the work: a 2 px ink rule opens every section, hairlines divide inside it, as in a tide table.
- Shadow only where paper lies on paper: the hero slip, a passage card on hover, the dialog.
- One spacing scale (4 8 12 16 24 32 48 64 96). More space between groups than inside them: 64 above a
  section head, 48 under it, 24 inside a card.
- Paper grain is an inline SVG noise in a token, very quiet. A soft fold runs down the chart.

## Layout

- Left-aligned on one content edge (1320 px). The top bar's right edge, the chart's neat line and every
  section rule share the right edge.
- Hero: text on the left, the chart on the right half, fading out towards the words so the headline can
  run over it like a chart title. The chart keeps its real border (the neat line with minutes of latitude
  and longitude) on the right and at the bottom. A slip of paper lies across the border with today's
  window: the product's answer, in the first screen.
- Each section has its own build so nothing repeats: four readings in a ruled band; one wide curve with
  a timetable row under it; four slips; three margin notes with a small figure each; a field of ink with
  a scale bar to close.
- 390 px is its own design: links in a ruled row under the bar, the chart behind and below the text, the
  readings 2 by 2, the tide table folded to one block per day, cards in one column.

## The parts worth knowing

- The hero chart is one inline SVG drawn from a single height field : coast,
  drying line, 2, 5, 10 and 20 m contours, tints and the 105 soundings all come from the same sea bed, so
  the figures agree with the lines. Soundings are set as on a chart: metres, with the decimetres dropped
  below the line; drying heights underlined.
- The tide curve, the table behind "Show as table", the tiles, the card strips and the dialog's answer
  all read one tide model (six harmonic parts, springs on Friday). The curve is an
  inline SVG that stretches; its labels are HTML so they stay sharp at any width.
- A safe window is where daylight, wind under 20 kn and 2.0 m of tide hold together. It always looks the
  same: magenta hatch with a solid top edge.
- The page is plain HTML, CSS and a little script, with no request to another host.

## Motion (level 1)

Feedback and fades only: buttons, links, the lamp switch, cards and fields answer hover, focus and
press; the dialog, the tide table and the plan note fade in. Nothing moves on load or on scroll.
`prefers-reduced-motion` removes all of it. `motioncount.py`: 11 places in 2 files; `motioncheck.py`: no
findings.

## What the hero area becomes at level 4 and 5

The area is `<div class="hero__scene" id="hero-scene">`. The SVG inside it (`.hero__poster`) stays as
the poster for no WebGL, weak devices and reduced motion. The mask that fades the area under the text is
on the element itself, so the words stay legible over whatever is mounted there.

**Level 4, Showpiece: the chart table in three dimensions.** The sheet lies on the table and the
camera looks across it at a low angle. It is the app's own scene on the kit's `stage.js` and `glsl.js`
(`table.js`), because no kit scene draws a printed chart: the poster SVG is printed into the texture in
two layers (`print.js`), paper and tints under the water, every line and letter on top, so the chart's
own figures and names stay readable. The sea bed is the same `seaBed(x, y)` that drew the poster, now a
real surface (`seabed.js`): banks stand proud of the paper and channels sink. The lamp is the light of the
scene: a warm pool follows the pointer, rakes the relief and the fold; in the dark theme it is the red
lamp. A clear glaze of water lies over the relief at the height of the tide, so Spijkerplaat and Hooge
Platen dry and flood; on first view the next 12 hours play once by themselves, and the slip's scale lets
you drag through them. The first 3D frame lies exactly on the drawn sheet, so the hand-over does not jump.
The pencil course and its fixes are drawn on the surface; the slip, the cards and the notes tilt as
paper (`depth.js`). On a phone the whole tilted sheet and the slip fit the first screen.

**Level 5, Cinematic: sail the pencil line.** Scroll drives a camera along the course (`journey.js`):
the whole sheet under the lamp; down to the pier head at 14:20 with the water at its highest; across the
roads to the 14:40 waypoint as the ebb starts and the banks come out; down the Wielingen between the
buoys while soundings pass as labels; then the lamp turns red and the chart goes to night for the
landfall. A custom shader draws the paper, the ink contours and the safe window as a band of hatched
light that sweeps over the chart as the hours pass. GPU particles are wind streaks over the water: their
direction and strength come from the wind data, the water level from the tide, the drawn course from the
passage the reader picked. The plain chart and the tide table stay one key press away.
