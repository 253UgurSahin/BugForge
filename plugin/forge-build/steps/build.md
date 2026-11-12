# forge-build: build

A part of `/forge-build`. The ground rules, the levels and "show the result" live in its
`SKILL.md` and in `../forge/rules.md` (section 9: show the result; section 10: levels; the tables
are in `../forge/levels.md`): read them first.

Reads `forge-work/plan.md`, `features.csv` and what the design part of `/forge-design` left in
`forge-work/design/`; in clone mode also `recon.md` and `screens/`. Writes the app in the project
root, the `clone` column of features.csv, `forge-work/build-log.md`, `clone-screens/` and the
shots under `forge-work/design/shots/`.

## Before you start

- No `forge-work/plan.md` with `Profile:` and `PWA:`: stop and run `/forge-plan`. No
  `forge-work/design/brief.md`: run `/forge-design` (its design part) first, unless the app has
  styles to follow. Idea mode: screens, flows and states come from plan.md.
- **Build what the user picked.** The brief's `Concept:` line is the concept the user chose from
  the three previews, and its preview in `forge-work/design/concepts/<letter>/` is the picture of
  the main screen to build towards. tokens.json, components.md and the brief are the specs: build
  from them, and ask no more questions about taste. A choice the specs do not make goes the way the
  brief points; write it in the build log's notes.
- Code already there (login or payments for the user's own app): no scaffold. Do Step 1's branch
  check, follow the code's stack and conventions (`python3 ../forge-check/detect.py .`) and run it
  the way it runs now. New screens follow its look, or the specs when the design part ran. With no
  brief there is no look review (Steps 3 and 7); the before and after shots are still taken. Tests
  can empty the database they reach: before their first run, `python3 ../forge-check/testdb.py .`.
  Exit 0: run them. Exit 1 (the database the app uses here, or it cannot tell): ask the user first,
  in auto mode too; no go: only the tests that reach no database (`../forge-check/steps/test.md`
  Step 2.6), the rest in the build log as not run.

## The level

Run `python3 ../forge/level.py get look`. The design part recorded it; it prints, say, `2 Polished`.

- A level in the user's request ("niveau 4", "showpiece", "level 5") is recorded at once:
  `python3 ../forge/level.py set look 4 --said '<their words>'`.
- Exit 1, no level yet: ask the one question of `../forge/levels.md` ("The one question"), with the
  lines `python3 ../forge/level.py show look` prints (`--nl` in Dutch) and where the examples are.
  Ask it in auto mode too, then record the answer the same way. One exception: a feature added to
  the user's own app in its own look (no design part ran) has no look level: the log says
  `Level: none, the app's own look`.
- Then do exactly what that level asks of the build, never less and never more.

What each level adds (`../forge/levels.md`):

| level | what the person sees | built with |
| --- | --- | --- |
| 1 Subtle (Subtiel) | One clean, consistent design. Every button, link and field reacts to hover, focus and press. Things fade in and out. | CSS only |
| 2 Polished (Verzorgd) | + content arrives piece by piece, pages change with a transition, numbers count up, an outline of the page shows while it loads, messages and dialogs move in and out, a small reaction on every control | CSS, View Transitions, the Web Animations API |
| 3 Expressive (Expressief) | + the page tells a story as you scroll, springy movement, charts that draw themselves and change shape, real depth (cards that tilt, panels in layers, perspective), one signature moment built for this app only | + CSS 3D and scroll-driven animation; `scenes/depth.js` of the scene kit |
| 4 Showpiece | + a living 3D scene at the top, made for what this app is about, light and depth that follow the pointer, 3D inside the screens (cards, objects, charts), depth while scrolling | + Three.js (installed locally), the scene kit |
| 5 Cinematic (Cinematisch) | + a 3D journey driven by scrolling, custom shaders and particles on the graphics card, forms that react to the pointer and to the app's live data, screens that change in 3D space | + the whole scene kit, composed |

The build lays the base of that level: the design system and every state and `motion` line the
component specs give at it (level 1: hover, focus and press on every control, fades; from level 2:
the loading outline, and messages and dialogs that move in and out). The rest of the level is
built after the build, by the motion part of `/forge-design`: entrances, page transitions, scroll,
depth, the scenes and Three.js. Dashboards are its dashboard part, at the dashboard level. Here a
screen of numbers gets only what plan.md's screen asks for. Write `Level: N (Name)` as the first
line under the title of build-log.md.

## Clean room and your own words

- Every line, label, button, empty state and email is written here, fresh, from recon.md and plan.md: never the
  original's HTML, CSS, JS, SVGs or images, nothing loaded from its domain or CDN. Stuck on how something works? Use
  the original as a user (help pages, public walkthroughs, the user's own account where its terms allow it), never
  its code or calls. Matching what a button does is parity, matching its sentence is copying: in clone mode `python3
  ../forge-build/copycheck.py` lists each run of 6+ words the project's files (logged-in pages too) share with the
  original's text that `/forge-research recon` kept. Rewrite it, or with the user's OK add it to
  `forge-work/copy-allow.txt`.

## Where things run

- **What the user looks at** (rules.md section 9). A new app: its compose stack, on
  `http://localhost:8080` (`APP_PORT` in `.env`), from the project folder and the work branch. The
  user's own app: find out what serves their local URL (a dev server that reloads by itself, a built
  app, or containers), from which folder and branch (`git branch --show-current`, `git worktree
  list`), and whether a service worker sits in front. Cannot tell: ask "How do you open the app, and
  at which address?" Write it under `## How it runs` in build-log.md, above its table. Work in that
  folder itself, never in a git worktree or a copy: the user's server would not see it.
- **Make it show** after a code or `.env` change, before you look at it in the browser or take a screenshot. A
  new app's stack runs production images (code is copied in when an image is built), so rebuild it:
  `docker compose up -d --build --wait`. The user's own app, as `## How it runs` says: a dev server shows it by
  itself (Laravel: CSS and JS only while `npm run dev` runs; no `public/hot`: `npm run build` after each change
  to them); a built app: build it again and restart it the way it was started (Next.js: `npm run build`, then
  `npm start`; Laravel or Django behind a server: what that server needs); containers: `docker compose up -d
  --build --wait` too. Ask before you stop a server the user started.
- Installers, generators (`php artisan make:*`, `manage.py makemigrations`, `drizzle-kit generate`) and tests run on
  this machine: laravel needs PHP 8.3+ with pdo_mysql, Composer and Node, django Python 3.12+ in a `.venv`, next and
  static Node 24. Missing: tell the user what to install (laravel: php.new) and wait. Or run one command in the
  tool's image: `MSYS_NO_PATHCONV=1 docker run --rm -u "$(id -u)" -e HOME=/tmp -v "$PWD":/app -w /app node:24-alpine
  npm install`. Composer's image has a newer PHP (Symfony 8 needs 8.4): fit its lock to this machine with
  `composer config platform.php <this machine's PHP version> && composer update`.
- Tests use the real database engine. The db service publishes no port, so a git-ignored
  `docker-compose.override.yml` publishes it on this machine only (`ports: ["127.0.0.1:3307:3306"]`, PostgreSQL
  `5433:5432`) for the test settings (laravel: `DB_HOST` 127.0.0.1, `DB_PORT` 3307 and `DB_DATABASE` testing in
  phpunit.xml, each with `force="true"` as `../forge-plan/profiles.md` says: without it the `.env` that compose
  gives a container wins there, and `../forge-check/testdb.py` stops the tests as not sure).
- **Shots**: `../forge-design/review.md` section 1 says how (`forge-work/design/shots.mjs`, a copy of
  `../forge-design/shots.example.mjs`). Signed-in screens: a short Playwright script signs alice in
  and saves `context.storageState({ path: "forge-work/design/alice.json" })`; then `--state` that file.

## Step 1: branch, scaffold, start the stack

1. `python3 ../forge/gitguard.py` must exit 0: a named branch that is not main. Exit 1: `git switch -c forge/build`.
   Exit 2, no repo: `git init -b main && git commit --allow-empty -m "start"` (the merge base), then the switch.
2. Scaffold in an empty temp folder (the root holds `forge-work/`), as plan.md and `../forge-plan/profiles.md` say:
   - laravel: `composer create-project laravel/laravel app`, or for a starter kit (the global `laravel/installer`)
     `laravel new app --livewire --phpunit --npm --no-boost -n` (or `--react`, `--vue`, `--svelte`, `--pest`)
   - django: `django-admin startproject config .`, in the project root itself, from a `.venv` with Django
   - next: `npx create-next-app@latest app --yes --use-npm --disable-git`
   - static: `npm create vite@latest app -- --template <the template in plan.md>`
3. In the temp folder delete `.git`, `node_modules` and `.next`, for laravel also the installer's `.env` and
   `database/database.sqlite` (both for SQLite). A `package.json` or lockfile already in the project root would be
   kept over the scaffold's: stop and name it; an older Playwright install (only `@playwright/test` in it) moves to
   `forge-work/old-root/`, anything else: ask. Then `cp -an <that folder>/app/. .` (dotfiles too, no overwrites;
   GNU cp's `-n` warning is harmless) and, all but django, `npm install`: the images build from its lockfile.
4. Copy the container templates of the pack part, this skill's `templates/<profile>/`, over the scaffold's files,
   fitted as Step 3 of `../forge-build/steps/pack.md` says (`dockerignore` as `.dockerignore`, `env.example` as
   `.env.example` plus the old one's names the app reads).
5. `.gitignore` lists `.env`, `docker-compose.override.yml`, `.venv/` and `forge-work/`, never `.env.example` or the
   public `.env.production` (create-next-app's `.env*` needs `!.env.example` and `!.env.production`).
6. Server profiles: `cp .env.example .env` with development values (its comments say which) and new secrets from
   `openssl rand -hex 24` (laravel `APP_KEY`: `php artisan key:generate`), written into the file, never printed.
7. `docker compose up -d --build --wait`: every service healthy, the health URL answers. Open the app with the
   browser console open. The CSP in nginx.conf is strict: allow only what the app needs (Livewire 4:
   `'csp_safe' => true` in `config/livewire.php`, not `'unsafe-eval'`; an inline script: its `sha256-` hash).
   Laravel's own error pages have an inline `<style>` it blocks: add `resources/views/errors/minimal.blade.php`
   (they all extend it) on the app's layout, with no database calls, and test that a 404 has no `<style>`.
8. **Before shots.** A new app has nothing yet, so the scaffold's start page is the before: shots of `/` and of
   the path of each screen in plan.md or recon.md (what that address shows now: a 404 page is a before too, and
   the run's exit 1 for it is expected here) into `forge-work/design/shots/before`, so each built screen has a
   pair. A path the scaffold sends to its sign-in page gets no before (shots.mjs saves none there): name it in
   build-log.md, so its missing pair is expected. The user's own app: every screen you will touch, before the
   first change.
9. Commit (Step 6): `build: scaffold <profile> app and compose stack`. Then tell the user what comes, in which
   order (plan.md's build order) and roughly how long.

## Step 2: routes, layout and theme

- Routes for every screen (recon.md; idea mode: plan.md), stubs are fine, and the shared layout.
- The theme: run the theme.py command under `## Theme` in `forge-work/design/components.md` and remove the theme
  values the scaffold brought (theme.py names those it still sees). Components use its variables, never raw hex or
  pixel values. A value is missing: add it to tokens.json, then run both commands under `## Theme` again.
- The basic components components.md lists (button, input, dialog) in every state, with the motion their specs
  give at the level, on `/design` (404 outside dev).
- A seed script (the names Step 2 of `/forge-check test` uses) with fake users `alice@example.test` and
  `bob@example.test`, password from `SEED_PASSWORD`, made only in dev and tests (laravel
  `app()->environment('local', 'testing')`, django `DEBUG`, next `NODE_ENV !== "production"`). Reference data goes
  in a migration. Static: none, no accounts.
- `PWA: yes`, per profiles.md's PWA toggle: in `public/`, `manifest.webmanifest`, `offline.html` with `/offline.css`,
  placeholder icons and `sw.js` from `../forge-plan/sw.example.js` (a static app working offline: vite-plugin-pwa's).

## Step 3: the vertical slice

The core loop from recon.md's flows (idea mode: plan.md's), end to end on the real database with real auth, before
anything else (booking app: create an event type, book a slot on the public page, see it on the dashboard). It uses
the basic components of Step 2; the finish of each screen comes in Step 4.

1. Make it show as "Where things run" says (a new app: `docker compose up -d --build --wait`) and load the slice's
   screens on its address.
2. Shots of those screens into `forge-work/design/shots/round-1`, and the first round of the look review on them
   (`../forge-design/review.md`, sections 2 to 4). What it finds wrong in the system (tokens, a component) is
   fixed now, before the other screens copy it.
3. Checkpoint, at most 5 lines: what works, the address and what to click, in order, to try the loop; the paths of
   the shots and the review's scores; what is next. Wait for the user's go; in auto mode, give these lines as a
   report and go on (rules.md section 7).

## Step 4: screen by screen

Work in plan.md's build order: must, should, could, then the fixes from compare. Per screen read its row in recon.md
or plan.md and build it from the basic components with real data through the data access layer. Done when:

- [ ] every state it lists works, plus empty, loading, error and no permission; a 60 character name fits
- [ ] it works at 390px and 1440px wide and by keyboard only: semantic HTML, labels, visible focus, alt text
- [ ] no console errors, no copy of the original (copycheck.py), tests for the main path and the access check
- [ ] clone mode: the layout and hierarchy of its reference shots, not their pixels; each has one under its name in
      `clone-screens/`, in the state its row under `## Reference screenshots` in recon.md gives (data, item, action,
      scroll): as loaded, `npx playwright screenshot --viewport-size=1440,900 <url> <file>` (or 390,844; logged in:
      `--load-storage`); any other state needs a short Playwright script that clicks there, at deviceScaleFactor 1

After each finished screen, one line to the user: the screen, its address, what to try.

## Step 5: the backend and its tests, as the screens need them

- **Auth**: the profile's default. Email verification, password reset, rate limits on login, sign up and anything
  that sends email, HttpOnly Secure session cookies, real account deletion, data export.
- **Data access**: every query on a user's records is scoped to the owner or checked by one policy function ("may
  this user do this to this record?"). A second user gets 404 or 403, never the data. A link for guests (a booking,
  a receipt) carries a random token, never a sequential ID.
- **Input**: validated on the server on every route; only allowed fields reach the model.
- **Payments**: Stripe Checkout with iDEAL in test mode, as `../forge-build/payments.md` says (section 1 first).
- **Email**: SMTP settings from `.env`, Mailpit in development, templates written fresh, sent by a job.
- **Uploads**: checked on the server by size and content type, random names, a named volume outside the web root.
- **Jobs**: anything slow runs in the profile's worker, with retries. Anything on a clock (reminders) also needs a
  scheduler service built like the worker (laravel: `php artisan schedule:work`).
- **Time**: moments (an appointment) in UTC, shown in the business's time zone, not the viewer's. Opening hours and
  weekly availability as local times plus the zone (`Europe/Amsterdam`), so daylight saving cannot shift them.
- **Accounts, keys, packages**: the user creates every account and key (Stripe test mode, SMTP, OAuth apps); you
  never sign up or type a password, card or live key. Official APIs, fewest scopes, well-known maintained packages.
  Google scopes such as Calendar need weeks of OAuth verification: tell the user early. plan.md has payments: in
  the message that starts the build, ask the user to put the Stripe test keys in `.env` (payments.md section 2;
  never in the chat). Until they are there, and in auto mode without them, Stripe is mocked in the tests and the
  keys go under "For you" in the checkpoint; the build does not wait for them.
- **Migrations** are checked in and run when the stack starts, never by hand on a server.
- **Tests** with the code, in the profile's runner (PHPUnit or Pest, pytest-django, Vitest), run as "Where things
  run" says: the main path, the access check with a second user, the edge cases that bite (daylight saving, double
  submits, empty lists) and the payment cases in payments.md. End-to-end tests come later, in `/forge-check test`.

## Step 6: one commit per screen or feature

1. Set the rows in `forge-work/features.csv` (`clone`: `yes`, `partial` with what is missing, `no`, or `skip` with
   why) and add a row to `forge-work/build-log.md` (`| ID | date | status | what | notes |`, new packages in the
   notes). A feature bigger than it looked: say so there and in the chat; never quietly ship half of it.
2. Right before the commit, `python3 ../forge-check/secretscan.py .` must exit 0: a high or critical finding stops
   the commit. Move the secret to `.env`, fix `.gitignore` if it misses `.env`; the user rotates one already in git.
3. The whole test suite passes. Commit with what and why: `build: S07 booking page`, `build: F03 iDEAL deposit`.

## Step 7: finish the build, show it and check in

1. The full suite passes, the app runs the way `## How it runs` says (a new app: `docker compose up -d --build
   --wait` gives a healthy stack), and copycheck.py exits 0 (clone mode).
2. **Make it show**, as "Where things run" says: a new app's stack was just rebuilt from the work branch; the
   user's own app, a built app or containers, is rebuilt and restarted now (a dev server already shows it).
   `PWA: yes`: bump `VERSION` in `sw.js`, so a browser that ran the app before drops its old files. Load every
   screen on the address yourself.
3. **After shots** of every screen into `forge-work/design/shots/after`, with the flags of the before shots. Then
   `python3 ../forge-design/changed.py forge-work/design/shots/before forge-work/design/shots/after` must exit 0
   (VISIBLE CHANGE; it compares the pairs both folders hold). Exit 1: find which reason of rules.md section 9 it
   is and fix that. Exit 2 is never a pass.
4. **The look review** on every screen, rounds numbered on from the slice's, as `../forge-design/review.md`
   section 4 says, in `forge-work/design/review.md`.
5. `/forge-check secure` has run with no critical or high finding open.
6. Checkpoint, at most 5 lines: must-haves built of total, partial or skipped and why; tests; the look scores and
   the level; the security verdict; and the hand-over of rules.md section 9: the branch, the address, where to
   click first, the paths of the before and after shots, how to go back. Motion and dashboards come next.

## Output

The app in the project root, running in its compose stack (the user's own app: the way it ran before); in
forge-work/ `features.csv` (`clone` filled), `build-log.md` (`Level:`, `## How it runs`, the table), `design/shots/`
and `design/review.md` and, in clone mode, `clone-screens/`; one commit per screen or feature on the work branch.

## Next

The dashboard and motion parts of `/forge-design`, at the levels the user chose (in `/forge` each is an optional
phase; motion is skipped only at look level 1, rules.md section 10), then `/forge-check test`; or back to `/forge`
when it runs the phases.
