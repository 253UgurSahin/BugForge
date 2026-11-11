/* Tidewatch, level 5: the harbour plan of Zeebrugge, the second sheet on the chart table.

   The pencil line of the hero chart runs off its west edge "to Zeebrugge, alongside 1810": the trip
   ended on the edge of the paper, with nowhere to land (every judge asked for the landfall to land on
   Zeebrugge). So as the trip comes in, a harbour plan is laid on the table beside the chart, where the
   line leaves it, and the pencil runs on over it: in past the moles, through the outer port, to a berth
   in the marina, where the boat lies alongside at 18:10.

   The plan is drawn as the hero chart is: an SVG with the very classes of the page's chart rules
   (c-sea, c-land, c-mole, c-basin, c-snd, c-pencil, c-title, c-neat ...), in the same 1000 x 900 chart
   space, so print.js prints it in the same layers (paper, tints, ink), the same fonts and both themes'
   colours, and table.js lights it with the same lamp. Made up, but shaped like Zeebrugge: two long
   moles reaching out into the sea from a low coast, the entrance facing north, the marina in the
   western corner of the outer port.

   harbourSvg() -> an <svg> element (not in the page). BERTH: the chart point of the berth.
   ENTRY: the chart point where the pencil comes onto the plan (its east edge, from the hero chart). */

const XMLNS = "http://www.w3.org/2000/svg";

// where the pencil comes onto the plan (east edge), and the berth it ends at, in plan chart units
export const ENTRY = [1000, 300];
export const BERTH = [356, 716];
// the pencil's way: in from the east, north of the entrance, in through it, across the outer port
export const PENCIL = [ENTRY, [620, 400], [528, 428], [520, 560], [430, 668], BERTH];

/* the plan's markup: tints, land, moles, basins, names, soundings, a light at each pier head, the
   pencil with its times, the title, and the neat line with its frame */
function markup() {
    // the coast: low dunes from west to east, the port cut into it
    const coast = "M-20 812 C140 806 230 800 300 796 L318 790 L330 760 L376 742 L438 744 L470 764 "
        + "L640 770 L700 748 L752 754 L770 776 C840 772 920 764 1020 758 L1020 920 L-20 920 Z";
    // the two moles: long curves from the coast out to the pier heads either side of the entrance
    const westMole = "M300 796 C298 700 330 590 392 522 C430 482 470 466 498 462";
    const eastMole = "M770 776 C780 690 748 596 690 530 C650 488 604 470 566 466";
    // the outer port's water inside the moles is deep (dredged): a clearer wash than the shoals outside
    const port = "M318 790 C318 700 346 604 402 540 C438 500 474 484 498 480 L566 482 "
        + "C598 486 640 502 676 540 C730 600 756 690 752 754 L700 748 L640 770 L470 764 L438 744 L376 742 L330 760 Z";
    // shoal water outside: a band along the coast, and a bank to the north-west
    const shoal = "M-20 640 C120 650 220 690 290 720 L300 796 C230 800 140 806 -20 812 Z "
        + "M780 700 C860 690 940 690 1020 676 L1020 758 C920 764 840 772 770 776 Z";
    const shoal2 = "M-20 560 C120 570 230 620 300 676 L300 796 C230 800 140 806 -20 812 Z "
        + "M770 640 C860 626 940 620 1020 610 L1020 758 C920 764 840 772 770 776 Z";
    const bank = "M90 300 C150 270 260 280 300 320 C330 352 280 392 200 392 C120 392 60 340 90 300 Z";
    const soundings = [
        [120, 120, "14", "2"], [300, 160, "15", "6"], [520, 140, "16", "1"], [920, 260, "13", "8"],
        [880, 420, "12", "5"], [140, 470, "9", "6"], [200, 340, "3", "4"], [540, 330, "14", "0"],
        [520, 620, "13", "5"], [600, 560, "13", "7"], [640, 680, "11", "0"], [100, 600, "5", "2"], [900, 600, "6", "8"],
        [410, 640, "8", "4"],
    ].map(([x, y, a, b]) => `<text x="${x}" y="${y}">${a}<tspan class="d" dy="7">${b}</tspan></text>`).join("");
    const pencil = PENCIL.map((p, i) => (i ? "L" : "M") + p[0] + " " + p[1]).join("");
    return `
<style>
/* the plan is a third the size of the chart on the table, so its print is drawn about 2.6 times larger:
   the chart's own rules, with the sizes of its letters and lines scaled (these follow the page's rules, so
   at the same specificity they win; the layers' !important rules still decide what each layer shows) */
.chart .t-town { font-size: 40px; }
.chart .t-water { font-size: 46px; }
.chart .t-water.t-sm { font-size: 30px; }
.chart .t-bank { font-size: 32px; }
.chart .t-place { font-size: 30px; }
.chart .t-small { font-size: 24px; }
.chart .c-snd text { font-size: 30px; }
.chart .c-snd .d { font-size: 20px; }
.chart .c-pencil { stroke-width: 5px; }
.chart .c-pencil text { font-size: 38px; }
.chart .c-pencil .time, .chart .c-pencil .note { font-size: 36px; }
.chart .c-title .k { font-size: 22px; }
.chart .c-title .n { font-size: 62px; }
.chart .c-title .s { font-size: 34px; }
.chart .c-title path { stroke-width: 1.5px; }
.chart .c-land path { stroke-width: 3px; }
.chart .c-mole path { stroke-width: 5px; }
.chart .c-basin path { stroke-width: 2px; }
.chart .c-shoal, .chart .c-shoal2 { stroke-width: 2px; }
.chart .c-dry { stroke-width: 2px; stroke-dasharray: 1.6 6; }
.chart .c-deep { stroke-width: 1.8px; }
.chart .c-grat path { stroke-width: 1.3px; }
.chart .c-town path { stroke-width: 1.3px; }
</style>
<defs>
<filter id="pencil" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="1.5" xChannelSelector="R" yChannelSelector="G"/></filter>
<pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(38)"><path d="M0 0V5" class="hatch"/></pattern>
</defs>
<g class="c-sea">
<path class="c-shoal2" d="${shoal2}"/>
<path class="c-shoal" d="${shoal}"/>
<path class="c-dry" d="${bank}"/>
<path class="c-deep" d="${port}"/>
</g>
<g class="c-grat"><path d="M0 300H986"/><path d="M0 600H986"/><path d="M333 0V886"/><path d="M666 0V886"/></g>
<g class="c-land"><path d="${coast}"/></g>
<g class="c-town">
<path d="M380 760L430 756L462 772L452 800L400 806L372 792Z"/>
<path d="M640 784L700 768L760 790L740 820L668 824Z"/>
<path d="M150 830L220 822L260 840L232 862L170 860Z"/>
</g>
<g class="c-mole"><path d="${westMole}"/><path d="${eastMole}"/>
<path d="M330 760L376 742"/><path d="M640 770L700 748"/></g>
<g class="c-basin"><path d="M330 704L392 700L398 734L334 740Z"/><path d="M560 690L640 690L640 740L560 744Z"/></g>
<text class="t-town" x="560" y="850">ZEEBRUGGE</text>
<text class="t-water" x="400" y="220" transform="rotate(-6 400 220)">Pas van het Zand</text>
<text class="t-water t-sm" x="610" y="650">Voorhaven</text>
<text class="t-place" x="300" y="664">Marina</text>
<text class="t-bank" x="196" y="372" transform="rotate(-4 196 372)">Bol van Heist</text>
<g class="c-light" transform="translate(498 462) scale(2.4)"><path class="flare" transform="rotate(300)" d="M0 -3C4 -9 4.6 -16 0 -25C-4.6 -16 -4 -9 0 -3Z"/><circle r="2.1"/></g>
<text class="t-small" x="300" y="486" text-anchor="end">F.G 12m</text>
<g class="c-light" transform="translate(566 466) scale(2.4)"><path class="flare" transform="rotate(60)" d="M0 -3C4 -9 4.6 -16 0 -25C-4.6 -16 -4 -9 0 -3Z"/><circle r="2.1"/></g>
<text class="t-small" x="588" y="474" text-anchor="start">F.R 12m</text>
<g class="c-snd">${soundings}</g>
<g class="c-pencil" filter="url(#pencil)">
<path class="course" d="${pencil}"/>
<g class="fix"><circle cx="528" cy="428" r="14"/><circle class="dot" cx="528" cy="428" r="3"/></g>
<text class="time" x="380" y="396" transform="rotate(-8 380 396)">1745</text>
<text class="note" transform="translate(640 296) rotate(-14)"><tspan x="0">from the Wielingen</tspan><tspan x="0" dy="38">249° T</tspan></text>
<text class="note" transform="translate(90 720) rotate(-4)"><tspan x="0">alongside</tspan><tspan x="0" dy="38">1810</tspan></text>
</g>
<g class="c-mark" transform="translate(${BERTH[0]} ${BERTH[1]}) rotate(-142) scale(3.4)"><path d="M0 -11C4 -6 4.2 4 3.2 9L-3.2 9C-4.2 4 -4 -6 0 -11Z" style="fill: var(--color-accent); stroke: none"/><path d="M0 3.6L1.6 7.4L-1.6 7.4Z" style="fill: var(--color-bg); stroke: none"/></g>
<g class="c-title" transform="translate(800 118)">
<text class="k" y="-44">NORTH SEA · BELGIUM</text><text class="n" y="16">Zeebrugge</text><text class="s" y="60">Harbour plan</text>
</g>
<g class="c-neat"><path class="paper" d="M987.5 0H1000V900H0V887.5H987.5Z"/></g>`;
}

/* the plan as an <svg> element, as print.js reads the hero chart (its child nodes) */
export function harbourSvg() {
    const svg = document.createElementNS(XMLNS, "svg");
    svg.setAttribute("viewBox", "0 0 1000 900");
    svg.innerHTML = markup();
    return svg;
}
