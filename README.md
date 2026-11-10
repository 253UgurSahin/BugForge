# BugForge

Claude skills that build working web apps for you, and that read, audit and improve the apps you
already have. Safe by default, clean-room, and written for people to read.

BugForge is a fork of [replica-skill](https://github.com/Jakeschincariol/replica-skill) by Jake
Schincariol (MIT). It keeps the idea (map an app, rebuild it, test it, make it your own) and
changes the rest:

- **It builds.** From a URL, an idea or your repo to a running, tested app, not a to-do list.
- **It reads apps that exist.** Your codebase, your live site, and competitors side by side. Fixes
  go on a separate branch, one small commit per finding, with a test where one can be written.
- **Your stack.** Four stack profiles, and any web profile can be a PWA.
- **Containers, not hosting.** You get a Dockerfile, a compose file and a RUN.md. BugForge never deploys.
- **Stripe with iDEAL**, in test mode only.
- **Safety is a gate.** Scripts check secrets, risky code, dependencies, headers, trackers and the
  container setup, and the work stops until they pass.
- **A look of its own.** A design brief with a concept, not a template; the app is then judged
  from screenshots of itself, in rounds. Dashboards and motion are phases of their own.
- **Tested like a user would.** A browser walks every page at phone, tablet and desktop width, in
  light and dark: console errors, broken links, accessibility, speed against a budget, edge cases.
- **You decide.** A checkpoint after every phase, or auto mode: say "run it all" and it goes from
  phase to phase on its own and fixes what fails. The security go is always yours.

BugForge has 17 skills, the forge skills: `/forge` runs a whole project, and each of the other 16
does one phase. Each script is standard-library Python 3.9+ with tests.

## Quick start

1. Install BugForge (below).
2. Open Claude Code in a new, empty folder (a new app) or in your repo (an existing app).
3. Type `/forge` (installed as a plugin: `/bugforge:forge`) and say what you want:
   - `/forge rebuild https://example.com as my own app` (clone mode)
   - `/forge a booking app for my hair salon` (idea mode)
   - `/forge improve this app` (improve mode)

Claude asks a few questions, runs the first phase, shows you a checkpoint of at most 5 lines plus
the gate's result, and waits. Say "go" to continue, or ask for changes first. Say "run it all on
your own" for auto mode (below). Say "where were we" in a new session to pick up where you left off.

## How /forge works

### Three modes

| mode | you give | phases, in order |
| --- | --- | --- |
| clone | the URL of an app to rebuild | recon, compare\*, plan, design, build, dashboard\*, motion\*, test, diff, brand, launch, secure, pack |
| idea | an idea in your own words | compare\*, plan, design, build, dashboard\*, motion\*, test, brand, launch, secure, pack |
| improve | your own repo | audit, inspect\*, improve, test, secure |

\* optional: skipped only when you say so, and your reason is recorded. secure is never skipped.
In improve mode, `/forge-compare` (competitors), `/forge-design` (a redesign), `/forge-dashboard`,
`/forge-motion` and `/forge-pack` (containers) are there when you ask for them.

Each phase is one skill: recon is `/forge-recon`, pack is `/forge-pack`. You can also call any
skill on its own: "redesign my app", "add a dashboard", "add animations", "test my app" or "is this
safe" each start the skill that does it, on your own repo too.

### The gate

`forge/gate.py` keeps the record in `forge-work/state.json` in your project. Per phase:

1. `gate.py status` names the next phase.
2. Claude runs that phase's skill.
3. `gate.py check <phase>` runs the phase's exit checks (`forge/phasecheck.py`), in your project's
   mode: what the phase's skill promises is there. Its files, with no placeholder of their template
   left (code blocks too) and text of its own in each section that must not stay empty; the phase's
   scripts pass (contrast, bugs, parity, brand sweep, codecheck, secret scan, packcheck, and in
   clone mode the copy check once forge-recon kept the original's text); and the reports of test,
   diff, secure, audit, inspect and improve are newer than the go before them (diff's also newer
   than bugs.md and features.csv, which its fix loop changes).
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
```

### Auto mode

Say it in your own words ("run it all", "do not stop after each phase", "doe alles zelf") and
BugForge goes from phase to phase without waiting. The gate still runs every exit check, and
records each phase with the words you asked for auto mode with. It still stops for:

- the go of the secure phase, always, and any `Verdict: FAIL`;
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
- An existing codebase keeps its stack: `forge-audit/detect.py` names the closest profile.
- Every server profile gets mailpit for development email (`COMPOSE_PROFILES=dev`).

## What you get at the end

Clone and idea mode, in your project root: the app, its tests, and `Dockerfile`,
`docker-compose.yml`, `.env.example`, `.dockerignore`, `RUN.md` (and `nginx.conf` for laravel and
static). RUN.md explains the first start, backups and restore, updates, logs and HTTPS behind your
own reverse proxy. You run it wherever you want.

Improve mode: the fixes you picked on a `forge/improve-<date>` branch, one commit per finding (with
a test where one can be written), and `forge-work/improve.md` with what was fixed, what was skipped
and why, and how to check each fix by hand. Nothing is merged or pushed: that is your step.

Plans, reports and screenshots live in `forge-work/` in your project. It never ships: BugForge keeps
it out of git and out of every image. The reports you will read most:

| file in `forge-work/` | from | what it holds |
| --- | --- | --- |
| `design/brief.md`, `design/review.md` | `/forge-design` | the concept and signature of the look; the scores per screen and round |
| `dashboard.md`, `motion.md` | `/forge-dashboard`, `/forge-motion` | each number with its source; which moments move and why |
| `test-plan.md`, `bugs.md`, `test/` | `/forge-test` | every case and its result; the bugs; the walk's findings and the screenshots per round |
| `security.md`, `sbom.json` | `/forge-secure` | the verdict, the findings and the OWASP coverage table; the list of every locked package |

## The skills

| skill | what it does |
| --- | --- |
| `/forge` | Runs a whole project, phase by phase, with the gate and your go after each phase, or straight through in auto mode. |
| `/forge-recon` | Maps an app from public pages and your own account: screens, flows, components, data model, feature list. |
| `/forge-compare` | Puts 2 to 5 competitors side by side and ranks what their users complain about and miss. |
| `/forge-plan` | Picks the stack profile and PWA with you; writes the schema, routes, payments and build order. |
| `/forge-design` | A design brief with a concept of its own, design tokens and component specs, open fonts and icons, WCAG AA contrast checked; reviews screenshots of the built app in rounds; redesigns an app you already have. |
| `/forge-build` | Scaffolds with the official installer, then builds screen by screen: auth, data access, Stripe with iDEAL, email, jobs. In clone mode it checks that no text is copied from the original. |
| `/forge-dashboard` | Dashboards on the app's own data: the few numbers that matter, each traced to its source, accessible charts, every state, and a second user who sees none of it. |
| `/forge-motion` | Motion that explains: transitions, micro-interactions, scroll and page transitions, a generative hero visual. CSS first, a library only when needed and never from a CDN, reduced motion always. |
| `/forge-test` | Test plan, unit and Playwright tests against the local stack; a walk of every page at three widths in light and dark (console, links, accessibility, speed budget, layout), edge cases, screenshots compared between rounds, a bug list and a fix loop. |
| `/forge-diff` | Scores the clone against the original: features, layout and behaviour. |
| `/forge-brand` | Your own name, palette, logo brief and voice, plus the trademark checks to run; sweeps out the original's name. |
| `/forge-launch` | Landing page, prices in EUR with VAT, privacy policy, terms, cookie check, basic SEO, launch checklist. |
| `/forge-secure` | The security gate: secrets, risky code and where input flows, dependencies and supply chain, headers, active probes and an access check on your own running app, trackers, AVG/GDPR, an OWASP Top 10 coverage table. Verdict PASS or FAIL. |
| `/forge-pack` | Fits the container templates to the app, checks them and runs the stack until it is healthy. |
| `/forge-audit` | Reads your own codebase without changing it: stack, size, tests, end-of-life versions, bugs, security, speed. |
| `/forge-inspect` | Looks at a live URL like a visitor: headers, SEO, accessibility, speed, PWA tags. Active checks only on your own app. |
| `/forge-improve` | Fixes the findings you pick on a new branch, one small commit each, tested where possible. |

## The scripts

Standard-library Python 3.9+, one job each. Every one has `--help`. Unless noted: exit 0 when
clean, 1 when something is at or above `--fail-on` (default `high`), 2 when it could not run (bad
input, or an incomplete scan). Exit 2 is never a pass. `--json` gives machine-readable output.

**forge/**

| usage | what it does |
| --- | --- |
| `gate.py {init,status,check,done,skip} ...` | the gate (above); 1 = refused |
| `phasecheck.py PHASE [--since TIME] [--until TIME] [--mode MODE] [--json]` | the exit checks of one phase, from `phasecheck.json`; gate.py runs it |
| `doccheck.py FILE [--template T] [--section S] [--cases BUGS] [--specs P] [--rows A,B] [--names L] [--moved S] [--json]` | is a report filled in: no placeholder of its template left, text of its own in each section, the test cases, a file a line names, no item left in a section that must end empty; phasecheck runs it |
| `workcheck.py {features,built,tokens,specs,compared,named} ... [--json]` | a phase's work files: the feature list, the design tokens, the end-to-end specs, the compared screenshots, the app's new name; phasecheck runs it |
| `gitguard.py [PATH] [--clean] [--json]` | 0 only on a work branch, never main, master, trunk or production; `--clean`: nothing uncommitted |

**forge-secure/**

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

**forge-audit/** (exit 0, or 2 on a bad path)

| usage | what it does |
| --- | --- |
| `detect.py PATH [--json]` | the stack, versions, databases, tests, CI and the closest forge profile |
| `inventory.py PATH [--json]` | size and health in plain numbers: lines per language, biggest files, TODOs, tests |

**forge-inspect/**

| usage | what it does |
| --- | --- |
| `getpage.py URL OUT [--json]` | loads one page passively and saves its HTML in a new file; 0 or 2 |
| `pagecheck.py URL [--json] [--fail-on L] [--no-pwa]` or `--file FILE [--url URL]` | SEO, accessibility, speed, PWA and mixed-content basics of one page |

**forge-compare/**, **forge-design/**, **forge-build/**, **forge-dashboard/**, **forge-motion/**, **forge-diff/**, **forge-brand/**, **forge-test/**, **forge-pack/**

| usage | what it does |
| --- | --- |
| `reviews.py REVIEWS [--themes F] [--months N] [--today DATE] [--out F] [--json]` | ranks what users hate and ask for, from collected reviews; 0 or 2 |
| `contrast.py TOKENS.json [--json]` or `contrast.py FG BG` | WCAG AA contrast of design tokens; 1 = a pair fails |
| `eyedropper.py IMAGE [X,Y...] [--box X,Y,W,H] [--top N] [--json]` or `eyedropper.py --grey COLOUR...` | exact colours off a 100% screenshot, each with its grey of the same lightness; 0 or 2 |
| `theme.py TOKENS.json --tailwind 4\|3\|no [--write FILE]` | the theme CSS from the design tokens, as components.md maps them; 0 or 2 |
| `pagetext.py PAGE...` | keeps the visible text of the original's saved pages in `forge-work/original-text/`; 0 or 2 |
| `copycheck.py [PATH...] [--words N] [--json]` | runs of 6 or more words the clone shares with the original's kept text; 1 = a run found |
| `chart.py DATA.json --type line\|area\|bar\|spark\|donut [--tokens TOKENS.json] [--title T] [--out FILE] [--json]` | one accessible inline SVG chart from data, no dependencies; 0 or 2 |
| `dashcheck.py DASHBOARD.md [--json] [--fail-on L]` | the numbers table of forge-work/dashboard.md: a definition, a source and a unit for each, no invented data, no misleading chart form |
| `shots.example.mjs BASE_URL OUT_DIR [--no-dark] [--state FILE] [PATH...]` | Node with Playwright, not Python: screenshots of your own app at 390px and 1440px, light and dark, for the look review |
| `motioncheck.py PATH [--json] [--fail-on L]` | motion in the app's code: no reduced-motion rule, layout properties animated, endless loops, an animation library from a CDN |
| `parity.py FEATURES.csv [--visual JSON...] [--json \| --markdown] [--fail-under N]` | feature parity score; 1 = a must-have is missing |
| `imgdiff.py ORIGINAL.png CLONE.png [--out DIFF.png] [--json]` | layout score of two screenshots, colour ignored; 0 or 2 |
| `sweep.py [PATH] [--config F] [--avoid A] [--domains D] [--colors C] [--json]` | the original's names, domains and colours left in the code; 1 = leftovers |
| `bugs.py BUGS.md [--json] [--fail-on L]` | open bugs in forge-work/bugs.md; 1 = one at or above `--fail-on` |
| `walkcheck.py WALK.json [--budget FILE] [--bugs] [--json] [--fail-on L]` | judges the browser walk: errors, broken links, accessibility, layout faults, speed against a budget; `--bugs` prints blocks for bugs.md |
| `shotcheck.py BEFORE_DIR AFTER_DIR [--min SCORE] [--json]` | the screenshots of two rounds, compared with imgdiff.py; 1 = a changed, missing or new shot |
| `packcheck.py PATH [--json] [--fail-on L]` | Dockerfile and the files it copies, compose file, .dockerignore and .env.example |
| `composecheck.py PATH [--json] [--fail-on L]` | the compose part of packcheck, on its own |

Try a few from the root of this repo:

```bash
python3 forge-secure/secretscan.py .
python3 forge-secure/scope.py http://localhost:8080
python3 forge-audit/detect.py .
python3 forge-design/contrast.py '#1a1a1a' '#ffffff'
python3 forge-design/contrast.py forge-design/tokens.json
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
- Copy another app's code, logo, images, fonts, text or brand.
- Print, paste or commit a secret, or open your `.env` while fixing your code.
- Commit on main, force-push, merge or push without your go.
- Mark a phase done on its own (auto mode: only after you asked for it, only when the checks pass,
  and never the secure phase), loosen a test or a scan to get through, invent reviews, testimonials,
  prices or quotes, or give legal advice: the legal and trademark parts are checklists to verify.

The full rules: [`forge/rules.md`](forge/rules.md).

## Install

Needs Claude Code, Python 3.9+, git, and Docker with the compose plugin. Building also uses your
stack's own tools (PHP and Composer, Python, Node: /forge-build says which), or runs them in their
Docker image. Playwright and Lighthouse need Node. Screenshots for the look review use Playwright too.

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

Plugin skills carry the plugin's name in front: `/bugforge:forge`, `/bugforge:forge-audit`. Claude
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

Or copy the folders into your personal skills folder:

```bash
git clone https://github.com/253UgurSahin/BugForge.git
mkdir -p ~/.claude/skills
cp -r BugForge/forge BugForge/forge-* ~/.claude/skills/
```

Copy them all: the skills call each other's scripts with paths like `../forge-secure/scope.py`.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

CI (`.github/workflows/test.yml`) runs on every push and pull request:

- the full test suite on Linux, macOS and Windows, each with Python 3.9 and 3.13, then the repo's
  own secret scan. `tests/test_plan.py` runs the sample service worker (`forge-plan/sw.example.js`)
  in a fake browser with Node, and `tests/test_motion.py` checks the hero example's syntax with it;
  without Node those tests are skipped;
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
