# forge levels

How far a forge skill goes. One scale, 1 to 5, in four domains: look, dashboard, test and secure.
A level includes everything below it. The user picks the level, by number or by name, in English or
Dutch. No skill picks one for them, and none works at a level that was not given. A level is a
promise in both directions: never less than it asks, and never more (`../forge/rules.md` section 10).

- The data: `../forge/levels.json`, the one place for every name, alias, summary and requirement.
- The script: `../forge/level.py` shows the tables, records the choice and checks the work against it.
- The record: `forge-work/levels.json` in the user's project, written only by level.py.

This file says the same in plain words. Where it and levels.json differ, levels.json is right.

## look: design, motion and 3D

| level | name | Dutch | what the person sees | built with |
| --- | --- | --- | --- | --- |
| 1 | Subtle | Subtiel | One clean, consistent design. Every button, link and field reacts to hover, focus and press. Things fade in and out. | CSS only |
| 2 | Polished | Verzorgd | + content arrives piece by piece, pages change with a transition, numbers count up, an outline of the page shows while it loads, messages and dialogs move in and out, a small reaction on every control | CSS, View Transitions, the Web Animations API |
| 3 | Expressive | Expressief | + the page tells a story as you scroll (things appear, scenes stay in place, layers move at their own speed), springy movement, charts that draw themselves and change shape, real depth (cards that tilt, panels in layers, perspective), one signature moment built for this app only | + CSS 3D and scroll-driven animation; `scenes/depth.js` of the scene kit |
| 4 | Showpiece | Showpiece | + a living 3D scene at the top of the app, made for what this app is about (a form drawn by code, a field of particles, an atmosphere of light, or moving contour lines), light and depth that follow the pointer, 3D inside the screens (cards, objects, charts), depth while scrolling | + Three.js (installed locally), the scene kit |
| 5 | Cinematic | Cinematisch | + a 3D journey driven by scrolling (a camera that moves through chapters), custom shaders and particles computed on the graphics card, forms that react to the pointer and to the app's live data, screens that change in 3D space | + the whole scene kit, composed |

Also understood: calm, rustig, minimal, minimaal, minimum (1); polish, gepolijst, netjes (2); lively,
levendig (3); show piece, pronkstuk (4); cinema, film, filmisch, 4d, max, maximal, maximaal, maximum (5).

- Levels 1 to 3 add no library. From level 4 Three.js is installed without asking again (npm,
  local, never a CDN), loaded only on the screens that use it and only when it is needed, with a
  still picture for weak devices, for browsers without WebGL and for people who asked for less
  motion. GSAP only when a scrubbed timeline really needs it; its licence is the user's call.
- "4D" is level 5: 3D that lives. It changes over time and reacts to the pointer, to scrolling, to
  touch and to the app's own live data.
- The look always follows the app's own taste. A higher level is more of that taste, never a
  house style pasted on.
- What the app's own code must hold at each level is counted by `../forge-design/motioncount.py`
  (`--level N`), so this domain has no evidence files.

## dashboard

| level | name | Dutch | the dashboard |
| --- | --- | --- | --- |
| 1 | Subtle | Subtiel | 3 to 5 numbers, one chart, one table. Calm. |
| 2 | Polished | Verzorgd | + each number as a tile with its change and a small trend line, 2 or 3 charts, a filter for the period, every state designed (loading, empty, error) |
| 3 | Expressive | Expressief | + charts that draw in and change shape between periods, a click through to the rows behind a number, comparison, a matrix of values or a heat map, live refresh |
| 4 | Showpiece | Showpiece | + a dense "control room" layout: a strip of live readouts, panels joined by thin lines, one crosshair that moves across all charts together, charts with a 3D look (CSS 3D or canvas), a log of what happened in order |
| 5 | Cinematic | Cinematisch | + the app's own data as a 3D field (`scenes/datascape.js` of the scene kit); the camera moves when a filter changes; a plain table of the same data is always one key press away |

Also understood, as for look: calm, rustig, minimal, minimaal, minimum (1); polish, gepolijst, netjes (2);
lively, levendig (3); show piece, pronkstuk (4); cinema, film, filmisch, 4d, max, maximal, maximaal, maximum (5).

## test

| level | name | Dutch | what is tested | the gate asks for |
| --- | --- | --- | --- | --- |
| 1 | Quick | Snel | The app starts, the main flow works once, no error in the browser console. Minutes. | nothing more |
| 2 | Basic | Basis | + one test per flow of the way it should go, unit tests for the logic that matters | nothing more |
| 3 | Standard | Standaard | + edge cases and cases that must fail, the walk (every page at 3 widths, in light and dark: errors, links, accessibility, layout, speed), the check that a second user cannot reach the first one's data | `forge-work/test/walk.json` |
| 4 | Thorough | Grondig | + the edge helpers on every form, the speed budget enforced, screenshots compared between rounds, offline and PWA, a pass with the keyboard only | an edge spec, `e2e/**/edge*.spec.*`, and two rounds of screenshots, `forge-work/test/shots/r1/*.png` and `forge-work/test/shots/r2/*.png` |
| 5 | Exhaustive | Uitputtend | + every route in every state, hostile and oversized input on every field (the user's own app only), two tabs at once, time zones and summer time, a matrix of slow networks, each spec run three times to catch a test that fails only now and then | nothing more |

Also understood: fast, vlug, smoke, minimal, minimaal, minimum (1); normal, normaal, gewoon (3);
deep, diep, uitgebreid (4); max, maximal, maximaal, maximum (5).

## secure

| level | name | Dutch | what is checked | the gate asks for |
| --- | --- | --- | --- | --- |
| 1 | Quick | Snel | Secrets and risky code (secretscan, codecheck). Only on its own, never as a forge phase. | nothing more |
| 2 | Basic | Basis | + dependencies, headers, trackers. Only on its own too. | nothing more |
| 3 | Standard | Standaard | + flowcheck, the supply chain with a parts list (SBOM), the framework checks, the AVG/GDPR list, the OWASP coverage table | `forge-work/sbom.json` |
| 4 | Thorough | Grondig | + the active probe and the two-user access check on the running app (the user's own app only), semgrep when it is installed, the container checks | `forge-work/security/probe.json` and `forge-work/security/authz.json`, the `--json` output of probe.py and authz.py; or a line in the report with the words `no running app` and then why there was none |
| 5 | Exhaustive | Uitputtend | + a threat model per entry point by reading the code (auth, session, payment, upload), an access matrix of every route against every role, abuse and rate-limit cases, a scan of the git history for secrets, a licence review. Each finding tells the attack as a story. | nothing more |

Also understood: fast, vlug, minimal, minimaal, minimum (1); normal, normaal, gewoon (3); deep,
diep, uitgebreid (4); max, maximal, maximaal, maximum (5).

The floor: inside a forge project (a `forge-work/state.json` is there) secure never runs below
level 3. Levels 1 and 2 are for a check on its own. The line about no running app goes under
`## Not checked` of security.md, the words first and then the reason, for example `- probe.py and
authz.py: no running app, the user runs no containers on this machine`.

## How to give a level

A level in the user's request is recorded at once, with their own words: "niveau 4", "showpiece",
"level 5", "quick test", "grondig", "alles op 3". Run level.py from the project root.

```
python3 ../forge/level.py set look 4 --said 'maak het uiterlijk niveau 4'
python3 ../forge/level.py set test snel --said 'doe maar een snelle test'
python3 ../forge/level.py set all 3 --said 'alles op 3'
```

- The domain is `look`, `dashboard`, `test`, `secure`, or `all` for every domain at once.
- The level is 1 to 5, or a name or alias from the tables above, in any letter case. It is one
  scale, so a name of another domain counts as its number: `set all showpiece` records 4 for every
  domain, which is Thorough for test and secure.
- `--said` holds the user's own words, as they typed them. Without them, or with a placeholder,
  level.py refuses. Never record a level the user did not give, and never raise or lower one yourself.
- Setting one domain keeps the others. Setting a domain again replaces it: the user may change
  their mind at any time.
- Inside a forge project `set` raises a secure level below 3 to 3 and prints a note. Tell the user.

## Reading and checking a level

- `python3 ../forge/level.py get look` prints the number and the name, such as `4 Showpiece`.
  Exit 1: no level chosen yet, so ask the question below; or secure is on record below its floor
  in a forge project, and the message gives the command that records it again.
- Scripts that need the level take `--level N` or `--level auto`. Auto reads the record; with no
  record they stop with exit 2 and "ask the user". There is never a silent default.
- The report of the work says which level it was done at, in exactly one line: `Level: 4` or
  `Level: 4 (Showpiece)`. The name, in English or Dutch, must be the one of that level.
- `python3 ../forge/level.py check secure --report forge-work/security.md` passes (exit 0) when a
  level is chosen, the report has that one line with the same level, the files in "the gate asks
  for" are there for that level and every level below it, and the floor holds. A file must hold
  something; links and node_modules do not count. Exit 1 names each thing that is missing and what
  to do about it: do the work. Never write a file only to pass, and never change the level yourself.
- Exit 2 from any command: it could not run. Show the user the message as it is.

## The one question

No level in the request: ask, once, before the work starts. Also in auto mode, because taste and
depth are the user's. One question, with the table of `level.py show` and where the examples are.

For one domain. The first line is "How far should I go with the look?", "... with the dashboard?",
"... with testing?" or "... with the security check?". The table is what
`python3 ../forge/level.py show look` prints. The last line is for look and dashboard only: test
and secure have no examples.

```text
How far should I go with the look? Pick a level from 1 to 5, by its number or its name.

look: design, motion and 3D. Each level includes the ones below it.
  1 Subtle (Subtiel)         Clean and calm. Every button, link and field reacts when you point at it or press it.
  2 Polished (Verzorgd)      + content glides in, pages change smoothly, numbers count up, messages slide in and out.
  3 Expressive (Expressief)  + scrolling tells a story, cards tilt with real depth, charts draw themselves, one moment only this app has.
  4 Showpiece                + a living 3D scene made for this app that follows your pointer, and 3D cards, objects and charts.
  5 Cinematic (Cinematisch)  + a 3D journey as you scroll, like a film; the forms react to you and to the app's live data.

Examples of every level are in the BugForge repo: the gallery in its README and the examples/ folder.
```

In Dutch. The first line is "Hoe ver moet ik gaan met het uiterlijk?", "... met het dashboard?",
"... met testen?" or "... met de beveiligingscontrole?". The table is `show look --nl`.

```text
Hoe ver moet ik gaan met het uiterlijk? Kies een niveau van 1 tot 5, met het cijfer of de naam.

look: ontwerp, beweging en 3D. Elk niveau bevat de lagere niveaus.
  1 Subtiel (Subtle)         Strak en rustig. Elke knop, link en elk veld reageert als je erop wijst of drukt.
  2 Verzorgd (Polished)      + inhoud schuift in beeld, pagina's wisselen vloeiend, getallen tellen op, meldingen schuiven in en uit.
  3 Expressief (Expressive)  + scrollen vertelt een verhaal, kaarten kantelen in 3D, grafieken tekenen zich, een moment dat alleen deze app heeft.
  4 Showpiece                + een levende 3D-scene voor deze app die je aanwijzer volgt, en kaarten, objecten en grafieken in 3D.
  5 Cinematisch (Cinematic)  + een 3D-reis bij het scrollen, als een film; de vormen reageren op jou en op de live data van de app.

Voorbeelden van elk niveau staan in de BugForge-repo: de galerij in de README en de map examples/.
```

`/forge` asks once at the start, for all four domains. The tables are `show` with no domain (in
Dutch: `show --nl`), under one of these lines:

```text
How far should I go, from 1 to 5? One level for everything, or one for each part: look, dashboard, test, secure.
Hoe ver moet ik gaan, van 1 tot 5? Een niveau voor alles, of een per onderdeel: look, dashboard, test, secure.
```

Then record the answer with `set`, with the user's words.

## The record

`forge-work/levels.json`, one entry for each domain that has a level:

```json
{
  "look": {"level": 4, "said": "maak het uiterlijk niveau 4", "at": "2026-11-10T14:03:11+01:00"},
  "secure": {"level": 3, "said": "alles op 3", "at": "2026-11-10T14:03:40+01:00"}
}
```

Only level.py writes it: a temporary file next to it, then a rename. Never edit it by hand. level.py
never reads a levels.json that is a link and never writes into a forge-work that is a link. When
it says the record is damaged or linked, show the user the message and change nothing yourself.
