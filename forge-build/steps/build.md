# forge-build build: build

A part of `/forge-build`. Its `SKILL.md` has the ground rules, the levels and how the result is shown: read it first.

Reads `forge-work/plan.md`, `design/` and `features.csv`, in clone mode also `recon.md` and `screens/`. Writes the
app in the project root, the `clone` column of features.csv, `forge-work/build-log.md` and `clone-screens/`.

## Before you start

- No `forge-work/plan.md` with `Profile:` and `PWA:`: stop and run /forge-plan. No `forge-work/design/`: run
  /forge-design, unless the app has styles to follow. Idea mode: screens, flows and states come from plan.md.
- Code already there (login or payments for the user's own app): no scaffold. Do Step 1's branch check, follow the
  code's stack and conventions (`python3 ../forge-check/detect.py .`) and run it the way it runs now.

## Clean room and your own words

- Every line, label, button, empty state and email is written here, fresh, from recon.md and plan.md: never the
  original's HTML, CSS, JS, SVGs or images, nothing loaded from its domain or CDN. Stuck on how something works? Use
  the original as a user (help pages, public walkthroughs, the user's own account where its terms allow it), never
  its code or calls. Matching what a button does is parity, matching its sentence is copying: in clone mode `python3
  ../forge-build/copycheck.py` lists each run of 6+ words the project's files (logged-in pages too) share with the
  original's text forge-research recon kept. Rewrite it, or with the user's OK add it to `forge-work/copy-allow.txt`.

## Where things run

- The stack runs production images: code is copied in when an image is built. After a code or `.env` change,
  `docker compose up -d --build --wait` before you look at it in the browser or take a screenshot.
- Installers, generators (`php artisan make:*`, `manage.py makemigrations`, `drizzle-kit generate`) and tests run on
  this machine: laravel needs PHP 8.3+ with pdo_mysql, Composer and Node, django Python 3.12+ in a `.venv`, next and
  static Node 24. Missing: tell the user what to install (laravel: php.new) and wait. Or run one command in the
  tool's image: `MSYS_NO_PATHCONV=1 docker run --rm -u "$(id -u)" -e HOME=/tmp -v "$PWD":/app -w /app node:24-alpine
  npm install`. Composer's image has a newer PHP (Symfony 8 needs 8.4): fit its lock to this machine with
  `composer config platform.php <this machine's PHP version> && composer update`.
- Tests use the real database engine. The db service publishes no port, so a git-ignored
  `docker-compose.override.yml` publishes it on this machine only (`ports: ["127.0.0.1:3307:3306"]`, PostgreSQL
  `5433:5432`) for the test settings (laravel: `DB_HOST`, `DB_PORT`, `DB_DATABASE=testing` in phpunit.xml).

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
   `database/database.sqlite` (both for SQLite). Then `cp -an <that folder>/app/. .` (dotfiles too, no overwrites;
   GNU cp's `-n` warning is harmless) and, all but django, `npm install`: the images build from its lockfile.
4. Copy forge-build pack's `templates/<profile>/` files over the scaffold's, fitted as Step 3 of `../forge-build/steps/pack.md`
   says (`dockerignore` as `.dockerignore`, `env.example` as `.env.example` plus the old one's names the app reads).
5. `.gitignore` lists `.env`, `docker-compose.override.yml`, `.venv/` and `forge-work/`, never `.env.example` or the
   public `.env.production` (create-next-app's `.env*` needs `!.env.example` and `!.env.production`).
6. Server profiles: `cp .env.example .env` with development values (its comments say which) and new secrets from
   `openssl rand -hex 24` (laravel `APP_KEY`: `php artisan key:generate`), written into the file, never printed.
7. `docker compose up -d --build --wait`: every service healthy, the health URL answers. Open the app with the
   browser console open. The CSP in nginx.conf is strict: allow only what the app needs (Livewire 4:
   `'csp_safe' => true` in `config/livewire.php`, not `'unsafe-eval'`; an inline script: its `sha256-` hash).
   Laravel's own error pages have an inline `<style>` it blocks: add `resources/views/errors/minimal.blade.php`
   (they all extend it) on the app's layout, with no database calls, and test that a 404 has no `<style>`.
8. Commit (Step 6): `build: scaffold <profile> app and compose stack`.

## Step 2: routes, layout and theme

- Routes for every screen (recon.md; idea mode: plan.md), stubs are fine, and the shared layout.
- The theme: run the theme.py command under `## Theme` in `forge-work/design/components.md` and remove the theme
  values the scaffold brought (theme.py names those it still sees). Components use its variables, never raw hex or
  pixel values. A value is missing: add it to tokens.json, then run both commands under `## Theme` again.
- The basic components components.md lists (button, input, dialog) in every state, on `/design` (404 outside dev).
- A seed script (the names forge-check test Step 2 uses) with fake users `alice@example.test` and `bob@example.test`,
  password from `SEED_PASSWORD`, made only in dev and tests (laravel `app()->environment('local', 'testing')`,
  django `DEBUG`, next `NODE_ENV !== "production"`). Reference data goes in a migration. Static: none, no accounts.
- `PWA: yes`, per profiles.md's PWA toggle: in `public/`, `manifest.webmanifest`, `offline.html` with `/offline.css`,
  placeholder icons and `sw.js` from `../forge-plan/sw.example.js` (a static app working offline: vite-plugin-pwa's).

## Step 3: the vertical slice

The core loop from recon.md's flows (idea mode: plan.md's), end to end on the real database with real auth, before
anything else (booking app: create an event type, book a slot on the public page, see it on the dashboard). Ugly is
fine. Checkpoint: show it running (5 lines max: what works, how to try it, what is next); wait for the user's go.

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
  Google scopes such as Calendar need weeks of OAuth verification: tell the user early.
- **Migrations** are checked in and run when the stack starts, never by hand on a server.
- **Tests** with the code, in the profile's runner (PHPUnit or Pest, pytest-django, Vitest), run as "Where things
  run" says: the main path, the access check with a second user, the edge cases that bite (daylight saving, double
  submits, empty lists) and the payment cases in payments.md. End-to-end tests are forge-check test's.

## Step 6: one commit per screen or feature

1. Set the rows in `forge-work/features.csv` (`clone`: `yes`, `partial` with what is missing, `no`, or `skip` with
   why) and add a row to `forge-work/build-log.md` (`| ID | date | status | what | notes |`, new packages in the
   notes). A feature bigger than it looked: say so there and in the chat; never quietly ship half of it.
2. Right before the commit, `python3 ../forge-check/secretscan.py .` must exit 0: a high or critical finding stops
   the commit. Move the secret to `.env`, fix `.gitignore` if it misses `.env`; the user rotates one already in git.
3. The whole test suite passes. Commit with what and why: `build: S07 booking page`, `build: F03 iDEAL deposit`.

## Step 7: finish the build and check in

The full suite passes, `docker compose up -d --build --wait` gives a healthy stack, copycheck.py exits 0 (clone mode),
the look review ran (`../forge-design/review.md`) and /forge-check secure left no critical or high finding open. Checkpoint
(5 lines): must-haves built of total, partial or skipped and why, tests, look scores, security verdict, how to open it.

## Output

The app in the project root, running in its compose stack; in forge-work/ `features.csv` (`clone` filled),
`build-log.md` and, in clone mode, `clone-screens/`; one commit per screen or feature on the work branch.

## Next

`/forge-design dashboard` and `/forge-design motion` (each optional), then `/forge-check test`; or back to `/forge` when it runs the phases.
