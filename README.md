# BugForge

Claude skills that build working web apps for you, and that read, audit and improve the apps you
already have. Safe by default, clean-room, and written for people to read.

BugForge is a fork of [replica-skill](https://github.com/Jakeschincariol/replica-skill) by Jake
Schincariol (MIT). It keeps the idea (map an app, rebuild it, test it, make it your own) and
changes the rest:

- **It builds.** From a URL, an idea or your repo to a running, tested app, not a to-do list.
- **It reads apps that exist.** Your codebase, your live site, and competitors side by side. Fixes
  go on a separate branch, one small commit per finding, with a test where one can be written.
- **You pick the level.** How far it goes, from 1 (Subtle) to 5 (Cinematic), for the look, the
  dashboards, the tests and the security check. Say "niveau 4" or "showpiece"; with no level it
  asks you once.
- **A look from the app's own world.** Three moving concepts drawn from what your app is about,
  you pick one, and that look is built into your app. From level 4 a living 3D scene made for the
  app follows the pointer; at level 5 the page becomes a 3D journey as you scroll.
- **You see the result on your own screen.** Every change shows on your localhost, with before
  and after screenshots, a pixel count that proves it changed, and a short film.
- **Your stack.** Four stack profiles, and any web profile can be a PWA.
- **Containers, not hosting.** You get a Dockerfile, a compose file and a RUN.md. BugForge never deploys.
- **Stripe with iDEAL**, in test mode only.
- **Safety is a gate.** Scripts check secrets, risky code, dependencies, headers, trackers and the
  container setup, and the work stops until they pass.
- **Tested like a user would.** A browser walks every page at phone, tablet and desktop width, in
  light and dark: console errors, broken links, accessibility, speed against a budget, edge cases.
- **You decide.** A checkpoint after every phase, or auto mode: say "run it all" and it goes from
  phase to phase on its own and fixes what fails. The security go is always yours.

BugForge has 8 skills. `/forge` runs a whole project; the other seven each do one kind of work and
have parts you can call on their own, such as `/forge-design motion` or `/forge-check secure`.
Each script is standard-library Python 3.9+ with tests.

## Quick start

1. Install BugForge (below).
2. Open Claude Code in a new, empty folder (a new app) or in your repo (an existing app).
3. Type `/forge` (installed as a plugin: `/bugforge:forge`) and say what you want:
   - `/forge rebuild https://example.com as my own app` (clone mode)
   - `/forge a booking app for my hair salon` (idea mode)
   - `/forge improve this app` (improve mode)

Or ask one skill for one thing, with a level if you like:

- `/forge-design maak mijn app mooier, niveau 4`: three concepts to pick from, then the new look,
  motion and a 3D hero built into your app.
- `/forge-design motion level 3`: scroll storytelling and real depth, no library.
- `/forge-check test grondig`: the tests at level 4 (Thorough).
- `/forge-check secure`: the security gate; it asks how deep.

Claude asks a few questions, runs the first phase, shows you a checkpoint of at most 5 lines plus
the gate's result, and waits. Say "go" to continue, or ask for changes first. Say "run it all on
your own" for auto mode (below). Say "where were we" in a new session to pick up where you left off.

## Levels

Each level includes the ones below it. A level is a promise both ways: never less than it asks,
never more.

| level | look: design, motion and 3D |
| --- | --- |
| 1 Subtle (Subtiel) | Clean and calm. Every button, link and field reacts when you point at it or press it. |
| 2 Polished (Verzorgd) | + content glides in, pages change smoothly, numbers count up, messages slide in and out. |
| 3 Expressive (Expressief) | + scrolling tells a story, cards tilt with real depth, charts draw themselves, one moment only this app has. |
| 4 Showpiece | + a living 3D scene made for this app that follows your pointer, and 3D cards, objects and charts. |
| 5 Cinematic (Cinematisch) | + a 3D journey as you scroll, like a film; the forms react to you and to the app's live data. |

The other three scales:

| level | dashboard | test | secure |
| --- | --- | --- | --- |
| 1 | Subtle: 3 to 5 key numbers, one chart, one table | Quick: the app starts, the main flow works once | Quick: leaked secrets and risky code |
| 2 | Polished: tiles with trends, a period filter, every state | Basic: every user flow, unit tests for the logic | Basic: known holes in packages, headers, trackers |
| 3 | Expressive: charts that draw in, drill down, compare periods | Standard: odd input, every page at 3 widths, no data leaks | Standard: input traced to risky code, OWASP, AVG/GDPR |
| 4 | Showpiece: a control-room screen, linked panels, charts with depth | Thorough: every form, speed limits, offline, keyboard only | Thorough: your running app probed, two users tried on each other's data |
| 5 | Cinematic: your data as a 3D landscape | Exhaustive: every state, hostile input, slow networks | Exhaustive: a threat model, every route against every role |

- Say it in any words, English or Dutch: "niveau 4", "showpiece", "level 2", "grondig", "snel".
  With no level, the skill asks one question with the table above, also in auto mode.
- `forge/level.py` records your choice with your own words in `forge-work/levels.json`. Every
  report carries a `Level: N (Name)` line, and the gate checks that the work is really at that level.
- Inside a forge project, secure never runs below 3 and test never below 2.
- At level 4 and 5 the look installs Three.js (MIT) with npm into your app, never from a CDN, and
  loads it only on the screens that use it, after the page is idle. Weak devices, no WebGL and
  reduced motion get a still picture of the scene. Levels 1 to 3 add no library.

[`forge/levels.md`](forge/levels.md) has every level in full, and what each one must show.

## See it: the gallery

The [`examples/`](examples/) folder holds one made-up app at every look level, and the 3D scene kit
on its own page. They are plain files; the 3D ones need a small local server, because a browser
refuses module scripts from a double-clicked file. From the root of this repo:

```bash
python3 examples/serve.py
```

It serves the folder on http://127.0.0.1:8765 (your machine only) and opens the gallery.

**Tidewatch**, a passage planner for small boats, at the five levels. The page is a paper sea chart
under a lamp; at night the lamp turns red, as it does on a boat. The words, the colours and the
type stay the same at every level; what changes is how much it moves and how deep it goes.

| level | what is new | open |
| --- | --- | --- |
| 1 Subtle | the clean design; every control reacts to hover, focus and press | [`examples/levels/1/`](examples/levels/1/index.html) |
| 2 Polished | content arrives, the tide numbers count up, the passage dialog glides | [`examples/levels/2/`](examples/levels/2/index.html) |
| 3 Expressive | the passage told as you scroll, the harbour cards tilt in real CSS 3D, a signature lamp | [`examples/levels/3/`](examples/levels/3/index.html) |
| 4 Showpiece | the chart table becomes a living 3D relief of contour lines that follows the pointer | [`examples/levels/4/`](examples/levels/4/index.html) |
| 5 Cinematic | "Sail the pencil line": a 3D journey along the course as you scroll, the wind as moving streaks | [`examples/levels/5/`](examples/levels/5/index.html) |

[`examples/levels/README.md`](examples/levels/README.md) explains the concept, the type, the
colours and what each level adds. [`examples/scenes/`](examples/scenes/index.html) shows every scene
of the kit, in light and dark, with its options.

## How /forge works

### Three modes

| mode | you give | phases, in order |
| --- | --- | --- |
| clone | the URL of an app to rebuild | recon, compare\*, plan, design, build, dashboard\*, motion\*, test, diff, brand, launch, secure, pack |
| idea | an idea in your own words | compare\*, plan, design, build, dashboard\*, motion\*, test, brand, launch, secure, pack |
| improve | your own repo | audit, inspect\*, improve, test, secure |

\* optional: skipped only when you say so, and your reason is recorded. secure is never skipped.
In improve mode, `/forge-research compare` (competitors), `/forge-design` (a redesign),
`/forge-design dashboard`, `/forge-design motion` and `/forge-build pack` (containers) are there
when you ask for them.

Each phase is a part of one skill: recon is `/forge-research recon`, pack is `/forge-build pack`.
You can also call any skill on its own: "redesign my app", "add a dashboard", "add animations",
"test my app" or "is this safe" each start the skill that does it, on your own repo too.

### The gate

`forge/gate.py` keeps the record in `forge-work/state.json` in your project. Per phase:

1. `gate.py status` names the next phase.
2. Claude runs that phase's skill.
3. `gate.py check <phase>` runs the phase's exit checks (`forge/phasecheck.py`), in your project's
   mode: what the phase's skill promises is there. Its files, with no placeholder of their template
   left (code blocks too) and text of its own in each section that must not stay empty; the phase's
   scripts pass (contrast, bugs, parity, brand sweep, codecheck, secret scan, packcheck, the level
   checks, and in clone mode the copy check once forge-research recon kept the original's text);
   and the reports of test, diff, secure, audit, inspect and improve are newer than the go before
   them (diff's also newer than bugs.md and features.csv, which its fix loop changes).
4. Claude shows you the skill's checkpoint plus one line with the gate's result, and stops.
5. Only after your go: `gate.py done <phase> --approved '<your exact words>'`. It refuses when a
   check fails, the words are missing, or an earlier phase is still open.

Claude runs these for you, from your project root. To look yourself:

```bash
FORGE=~/.claude/skills   # the folder that holds forge/ and the forge-* folders (gate.py status prints it)
python3 $FORGE/forge/gate.py init --mode idea --about 'a booking app for my salon'   # clone, idea or improve
python3 $FORGE/forge/gate.py status          # every phase and the next step (--json)
python3 $FORGE/forge/gate.py check plan      # the exit checks of one phase (--json)
python3 $FORGE/forge/gate.py done plan --approved 'ja, ga door'
python3 $FORGE/forge/gate.py done plan --auto 'run it all on your own'        # auto mode; refused for secure
python3 $FORGE/forge/gate.py skip compare --reason 'no rivals worth reading'   # the phases with a * only
python3 $FORGE/forge/level.py show look --nl  # the levels, in Dutch
```

### Auto mode

Say it in your own words ("run it all", "do not stop after each phase", "doe alles zelf") and
BugForge goes from phase to phase without waiting. The gate still runs every exit check, and
records each phase with the words you asked for auto mode with. It still stops for:

- the go of the secure phase, always, and any `Verdict: FAIL`;
- the level, when you named none, and your pick of the three concepts: taste is yours;
- a risk to accept, a bug to leave unfixed, a secret to rotate;
- a choice only you can make and that is costly to undo: the app's name, prices, a domain of yours;
- a failure it could not fix in three tries, or a fix that turns out bigger than it looked.

In every mode a failed test, check or scan is fixed at its cause, never by loosening the check.
Say "stop after each phase again" to turn auto mode off.

`init --force` starts over: it forgets every approval, and test, diff, secure, audit, inspect and
improve run again, since their reports must be newer than the new start.

## Stack profiles

| profile | stack | services in docker compose | health URL |
| --- | --- | --- | --- |
| laravel | PHP + MariaDB (Laravel) | nginx, PHP-FPM, MariaDB, queue worker | `/up` |
| django | Python + PostgreSQL or MariaDB (Django) | gunicorn with WhiteNoise, PostgreSQL | `/healthz` |
| next | Node/TypeScript + PostgreSQL (Next.js, self-hosted) | Node standalone server, PostgreSQL | `/api/health` |
| static | static site or SPA (Vite + nginx) | nginx with the built files | `/` |

- **PWA** is a switch, not a profile: `PWA: yes` in `forge-work/plan.md` adds a manifest, icons, a
  service worker, an offline page and safe caching rules (never a signed-in page or a POST).
- `forge-plan/profiles.md` is the one reference: how to pick, versions (with the date they were
  checked), auth, migrations, tests, Stripe library and the classic mistakes per profile.
- An existing codebase keeps its stack: `forge-check/detect.py` names the closest profile.
- Every server profile gets mailpit for development email (`COMPOSE_PROFILES=dev`).

## What you get at the end

Clone and idea mode, in your project root: the app, its tests, and `Dockerfile`,
`docker-compose.yml`, `.env.example`, `.dockerignore`, `RUN.md` (and `nginx.conf` for laravel and
static). RUN.md explains the first start, backups and restore, updates, logs and HTTPS behind your
own reverse proxy. You run it wherever you want.

Improve mode: the fixes you picked on a `forge/improve-<date>` branch, one commit per finding (with
a test where one can be written), and `forge-work/improve.md` with what was fixed, what was skipped
and why, and how to check each fix by hand. A new look goes on a `forge/redesign-<date>` branch in
the folder your dev server runs from, so your own localhost shows it. Nothing is merged or pushed:
that is your step.

Plans, reports and screenshots live in `forge-work/` in your project. It never ships: BugForge keeps
it out of git and out of every image. The reports you will read most:

| file in `forge-work/` | from | what it holds |
| --- | --- | --- |
| `design/concepts/` | `/forge-design` | the board with the three moving concepts you picked from |
| `design/brief.md`, `design/review.md`, `design/shots/` | `/forge-design` | the concept and signature of the look; the scores per screen and round; before and after shots, frames and the film |
| `dashboard.md`, `motion.md` | `/forge-design dashboard`, `/forge-design motion` | each number with its source; which moments move, at which level, and the proof they show |
| `levels.json` | every skill with a level | the levels you chose, in your own words |
| `test-plan.md`, `bugs.md`, `test/` | `/forge-check test` | every case and its result; the bugs; the walk's findings and the screenshots per round |
| `security.md`, `sbom.json` | `/forge-check secure` | the verdict, the findings and the OWASP coverage table; the list of every locked package |

## The skills

| skill | parts | what it does |
| --- | --- | --- |
| `/forge` | | Runs a whole project, phase by phase, with the gate and your go after each phase, or straight through in auto mode. |
| `/forge-research` | recon, compare | Maps an app from public pages and your own account (screens, flows, components, data model, feature list); puts 2 to 5 competitors side by side and ranks what their users complain about and miss. |
| `/forge-plan` | | Picks the stack profile and PWA with you, records the look level; writes the schema, routes, payments and build order. |
| `/forge-design` | design, brand, dashboard, motion | Three moving concepts from the app's own world, then the brief, tokens, open fonts and icons, WCAG AA contrast, and the look built into your app; your own name, palette and voice; dashboards on the app's own data; motion and 3D at your level, with the scene kit. Shows the result on your localhost with proof. |
| `/forge-build` | build, pack | Scaffolds with the official installer, then builds screen by screen: auth, data access, Stripe with iDEAL, email, jobs; fits the container templates and runs the stack until it is healthy. In clone mode it checks that no text is copied from the original. |
| `/forge-check` | test, diff, secure, audit, inspect | Tests at your level (unit, Playwright, a walk of every page at three widths in light and dark, edge cases, a fix loop); scores a clone against the original; the security gate with a verdict PASS or FAIL; reads your codebase without changing it; looks at a live URL like a visitor. |
| `/forge-improve` | | One list of what to improve, from the audits and from the look (a redesign, motion and 3D, dashboards, each at a level), fixed on a new branch, one small commit each, tested where possible. |
| `/forge-launch` | | Landing page in your concept, prices in EUR with VAT, privacy policy, terms, cookie check, basic SEO, launch checklist. |

## The 3D scene kit

`forge-design/scenes/` holds the scenes the look uses from level 4. Each is a starting point that
the concept changes until it could only belong to your app, mounted on its own stage with a still
picture for weak devices, no WebGL and reduced motion. [`forge-design/scenes.md`](forge-design/scenes.md)
says which scene fits which app, which files to copy and how to mount one in each stack.

| file | what it is |
| --- | --- |
| `stage.js` | the runtime under every WebGL scene: size and pixel ratio, the page's colours and theme, pausing when nobody looks, reduced motion, weak devices, the pointer, quality tiers, the fallback |
| `lazy.js` | loads a scene only when it is about to be seen and the browser is idle; one switch for all motion |
| `glsl.js` | shared shader code: noise, grain, the stage's uniforms |
| `aurora.js` | a shader atmosphere behind a page: northern lights, moving water or mist |
| `contour.js` | living contour lines, drawn the way a cartographer draws a depth chart |
| `field.js` | tens of thousands of points adrift in a current, settling into shapes and data |
| `form.js` | a sculptural object made of strands of light, for a hero |
| `datascape.js` | the app's own numbers as a sculpture of columns or ridges |
| `depth.js`, `depth.css` | real depth with CSS 3D only, no WebGL: tilting cards, stacked panels, folds, layered scenes (from level 3) |
| `journey.js` | the director of level 5: a scroll-driven camera trip through a scene, chapter by chapter |

## The scripts

Standard-library Python 3.9+, one job each. Every one has `--help`. Unless noted: exit 0 when
clean, 1 when something is at or above `--fail-on` (default `high`), 2 when it could not run (bad
input, or an incomplete scan). Exit 2 is never a pass. `--json` gives machine-readable output.

**forge/**

| usage | what it does |
| --- | --- |
| `gate.py {init,status,check,done,skip} ...` | the gate (above); 1 = refused |
| `phasecheck.py PHASE [--since TIME] [--until TIME] [--mode MODE] [--json]` | the exit checks of one phase, from `phasecheck.json`; gate.py runs it |
| `level.py {show,set,get,check} ...` | the levels: shows the table, records your choice with your words (`set look 4 --said 'niveau 4'`), checks a report and its evidence against it; 1 = no level yet, or the work is below it |
| `doccheck.py FILE [--template T] [--section S] [--cases BUGS] [--specs P] [--rows A,B] [--names L] [--moved S] [--json]` | is a report filled in: no placeholder of its template left, text of its own in each section, the test cases, a file a line names, no item left in a section that must end empty; phasecheck runs it |
| `workcheck.py {features,built,tokens,specs,compared,named} ... [--json]` | a phase's work files: the feature list, the design tokens, the end-to-end specs, the compared screenshots, the app's new name; phasecheck runs it |
| `gitguard.py [PATH] [--clean] [--json]` | 0 only on a work branch, never main, master, trunk or production; `--clean`: nothing uncommitted |

**forge-research/**

| usage | what it does |
| --- | --- |
| `reviews.py REVIEWS [--themes F] [--months N] [--today DATE] [--out F] [--json]` | ranks what users hate and ask for, from collected reviews; 0 or 2 |

**forge-design/**

| usage | what it does |
| --- | --- |
| `changed.py BEFORE AFTER [--min PERCENT]` or `changed.py --moves FRAME FRAME...` | would a person see the change? Counts the pixels that differ between screenshots of one screen, or between frames that should move; 1 = no visible change |
| `shots.example.mjs BASE_URL OUT_DIR [--no-dark] [--state FILE] [--viewport-only] [--wait MS] [--reduced] [--frames] [--video] [PATH...]` | Node with Playwright, not Python: stills of your own app at 390px and 1440px in light and dark, frames in time, and a film, for the review and the proof |
| `contrast.py TOKENS.json [--json]` or `contrast.py FG BG` | WCAG AA contrast of design tokens; 1 = a pair fails |
| `eyedropper.py IMAGE [X,Y...] [--box X,Y,W,H] [--top N] [--json]` or `eyedropper.py --grey COLOUR...` | exact colours off a 100% screenshot, each with its grey of the same lightness; 0 or 2 |
| `theme.py TOKENS.json --tailwind 4\|3\|no [--write FILE]` | the theme CSS from the design tokens, as components.md maps them; 0 or 2 |
| `motioncount.py PATH [--min N] [--level N\|auto] [--json]` | does the app really move? counts the motion wired into its own stylesheets, templates and scripts, against what the level asks, and lists motion classes no element uses; 1 = too few |
| `motioncheck.py PATH [--json] [--fail-on L]` | motion in the app's code: no reduced-motion rule, layout properties animated, endless loops, an animation library from a CDN |
| `chart.py DATA.json --type line\|area\|bar\|spark\|donut [--tokens TOKENS.json] [--title T] [--out FILE] [--json]` | one accessible inline SVG chart from data, no dependencies; 0 or 2 |
| `dashcheck.py DASHBOARD.md [--level N\|auto] [--json] [--fail-on L]` | the numbers table of forge-work/dashboard.md: a definition, a source and a unit for each, no invented data, no misleading chart form, what the level asks |
| `sweep.py [PATH] [--config F] [--avoid A] [--domains D] [--colors C] [--json]` | the original's names, domains and colours left in the code; 1 = leftovers |

**forge-build/**

| usage | what it does |
| --- | --- |
| `pagetext.py PAGE...` | keeps the visible text of the original's saved pages in `forge-work/original-text/`; 0 or 2 |
| `copycheck.py [PATH...] [--words N] [--json]` | runs of 6 or more words the clone shares with the original's kept text; 1 = a run found |
| `packcheck.py PATH [--json] [--fail-on L]` | Dockerfile and the files it copies, compose file, .dockerignore and .env.example |
| `composecheck.py PATH [--json] [--fail-on L]` | the compose part of packcheck, on its own |

**forge-check/**

| usage | what it does |
| --- | --- |
| `scope.py TARGET [--scope FILE] [--json]` | may active tests run here? 0 = yes (localhost, containers, your listed domains), 1 = passive only |
| `secretscan.py PATH [--json] [--fail-on L]` | keys, tokens, passwords and `.env` files |
| `codecheck.py PATH [--json] [--fail-on L]` | risky code patterns in PHP, Python and JS/TS |
| `flowcheck.py PATH [--json] [--fail-on L]` | request input followed to a risky call, handlers with no owner check, uploads, weak tokens, mass assignment, secrets in logs |
| `deps.py PATH [--json] [--fail-on L] [--strict]` | known holes, through npm audit, composer audit and pip-audit when installed |
| `supply.py PATH [--sbom FILE] [--json] [--fail-on L]` | the supply chain, offline: lockfiles, floating versions, odd sources, look-alike names, install scripts, licences; `--sbom` writes a CycloneDX parts list |
| `headers.py URL [--json] [--fail-on L]` or `--file FILE --url URL` | HTTP security headers, from one passive GET |
| `probe.py URL [--paths FILE] [--scope FILE] [--max-requests N] [--json] [--fail-on L]` | active, your own app only (asks scope.py, else exit 2): exposed files, a database error after a quote, reflected input, debug pages, CORS, open redirects, forms without a CSRF token |
| `authz.py URL --urls FILE --a COOKIES_A --b COOKIES_B [--scope FILE] [--json] [--fail-on L]` | active, your own app only: can a second user or a visitor read the first user's pages? |
| `trackers.py PATH [--json] [--fail-on L]` | third-party services in the code, for the privacy policy |
| `untrusted.py FILE... [--json] [--fail-on L]` | prompt-injection signs in fetched text, before Claude uses it |
| `detect.py PATH [--json]` | the stack, versions, databases, tests, CI and the closest forge profile; 0 or 2 |
| `inventory.py PATH [--json]` | size and health in plain numbers: lines per language, biggest files, TODOs, tests; 0 or 2 |
| `getpage.py URL OUT [--json]` | loads one page passively and saves its HTML in a new file; 0 or 2 |
| `pagecheck.py URL [--json] [--fail-on L] [--no-pwa]` or `--file FILE [--url URL]` | SEO, accessibility, speed, PWA and mixed-content basics of one page |
| `bugs.py BUGS.md [--json] [--fail-on L]` | open bugs in forge-work/bugs.md; 1 = one at or above `--fail-on` |
| `walkcheck.py WALK.json [--budget FILE] [--bugs] [--json] [--fail-on L]` | judges the browser walk: errors, broken links, accessibility, layout faults, speed against a budget; `--bugs` prints blocks for bugs.md |
| `shotcheck.py BEFORE_DIR AFTER_DIR [--min SCORE] [--json]` | the screenshots of two rounds, compared with imgdiff.py; 1 = a changed, missing or new shot |
| `imgdiff.py ORIGINAL.png CLONE.png [--out DIFF.png] [--json]` | layout score of two screenshots, colour ignored; 0 or 2 |
| `parity.py FEATURES.csv [--visual JSON...] [--json \| --markdown] [--fail-under N]` | feature parity score; 1 = a must-have is missing |

**examples/**

| usage | what it does |
| --- | --- |
| `serve.py [--port PORT] [--no-open]` | serves the gallery on 127.0.0.1 and opens it in your browser |

Try a few from the root of this repo:

```bash
python3 forge-check/secretscan.py .
python3 forge-check/scope.py http://localhost:8080
python3 forge-check/detect.py .
python3 forge-design/contrast.py '#1a1a1a' '#ffffff'
python3 forge-design/contrast.py forge-design/tokens.json
python3 forge/level.py show
```

## What BugForge never does

- Deploy, SSH into a server, change DNS, open hosting accounts, or use Vercel, Netlify, Supabase or
  any other platform. It builds containers; running them is your step.
- Buy anything: no domains, trademarks or subscriptions.
- Touch real money: Stripe test keys only. Live keys are yours.
- Run active tests (probes, odd input, scans, load) on a site that is not yours: probe.py and
  authz.py refuse any target scope.py does not allow. Other people's sites get what any visitor
  does: load a page, read the headers.
- Log in to someone else's account, ask for your password, crawl, or scrape against a site's terms.
- Copy another app's code, logo, images, fonts, text, animations, shaders or brand.
- Load a library or a font from a CDN into your app: they are installed with your package manager.
- Print, paste or commit a secret, or open your `.env` while fixing your code.
- Commit on main, force-push, merge or push without your go.
- Mark a phase done on its own (auto mode: only after you asked for it, only when the checks pass,
  and never the secure phase), loosen a test or a scan to get through, invent reviews, testimonials,
  prices or quotes, or give legal advice: the legal and trademark parts are checklists to verify.

The full rules: [`forge/rules.md`](forge/rules.md).

## Install

Needs Claude Code, Python 3.9+, git, and Docker with the compose plugin. Building also uses your
stack's own tools (PHP and Composer, Python, Node: /forge-build says which), or runs them in their
Docker image. Playwright and Lighthouse need Node. Screenshots, frames and films of your app use
Playwright too.

Works on Linux, macOS and Windows: CI runs every script's tests on all three.

- **macOS:** the `python3` from Xcode's command line tools (Python 3.9) is enough; a python.org or
  Homebrew Python works too.
- **Windows:** Claude Code runs the scripts in Git Bash (part of Git for Windows). A python.org
  install has no `python3` there, so Claude runs `py -3` or `python` instead, as
  [`forge/rules.md`](forge/rules.md) tells it.
- **Docker:** CI checks the container templates on Linux. On macOS and Windows, Docker Desktop
  runs the same Linux containers, but CI does not test it there.

As a plugin, in Claude Code, one command at a time:

```
/plugin marketplace add 253UgurSahin/BugForge
```

```
/plugin install bugforge@bugforge
```

Plugin skills carry the plugin's name in front: `/bugforge:forge`, `/bugforge:forge-check audit`. Claude
also picks the right skill when you just say what you want ("audit my code").

Installed it before the rename, as `forge@forge`? Remove that install and its marketplace first, in a
terminal, then run the two commands above:

```bash
claude plugin uninstall forge@forge
```

```bash
claude plugin marketplace remove forge
```

To update, run the next two in a terminal and restart Claude Code. The first fetches the new version, the
second installs it; the second alone finds nothing new.

```bash
claude plugin marketplace update bugforge
```

```bash
claude plugin update bugforge@bugforge
```

Had the 17 skills of an earlier version? The update replaces them with the 8: `/forge-motion` is now
`/forge-design motion`, `/forge-secure` is `/forge-check secure`, and so on. Your `forge-work/`
folders keep working.

Or copy the folders into your personal skills folder:

```bash
git clone https://github.com/253UgurSahin/BugForge.git
mkdir -p ~/.claude/skills
cp -r BugForge/forge BugForge/forge-* ~/.claude/skills/
```

Copy them all: the skills call each other's scripts with paths like `../forge-check/scope.py`.
If you copied the 17 skills of an earlier version, remove those folders first
(`forge-recon`, `forge-compare`, `forge-dashboard`, `forge-motion`, `forge-brand`, `forge-test`,
`forge-diff`, `forge-secure`, `forge-audit`, `forge-inspect`, `forge-pack`).

## Tests

```bash
python3 -m unittest discover -s tests -v
```

CI (`.github/workflows/test.yml`) runs on every push and pull request:

- the full test suite on Linux, macOS and Windows, each with Python 3.9 and 3.13, then the repo's
  own secret scan. With Node, `tests/test_plan.py` runs the sample service worker
  (`forge-plan/sw.example.js`) in a fake browser, `tests/test_scenes.py` runs the scene kit's stage
  and loader in a make-believe browser, and `tests/test_shots.py` checks that the screenshot script
  parses and explains every flag it reads; without Node those tests are skipped. `tests/test_examples.py` checks the gallery:
  every level is there, nothing loads from another host, and its copy of the kit equals the kit;
- per stack profile: the container templates installed in a scratch folder, checked with
  `docker compose config -q` and `packcheck.py --fail-on low`.

## Releasing

Every push to `main`, the default branch, is a release. `.claude-plugin/plugin.json` has no
`version` on purpose: Claude Code then uses the commit as the version, so users get each push with
the two update commands above. With a fixed version they would get nothing until it was raised.
`tests/test_repo.py` keeps it that way.

## Credit and license

MIT. Based on [replica-skill](https://github.com/Jakeschincariol/replica-skill) by Jake
Schincariol ([opusjake.ai](https://opusjake.ai)). The original copyright notice is kept in
[`LICENSE`](LICENSE).

The gallery ships a copy of [three.js](https://threejs.org) (MIT, its licence in
`examples/vendor/three/LICENSE`) and three open font families (SIL Open Font License 1.1, each
licence next to its files in `examples/levels/shared/fonts/`).
