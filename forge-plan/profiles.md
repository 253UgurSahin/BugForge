# Stack profiles

The one reference for forge's four stack profiles and the PWA toggle. forge-plan picks a profile
with the user; forge-build, forge-test and forge-pack follow it. Everything runs in the user's own
docker compose stack: no Vercel, Netlify, Supabase or any other managed hosting or database.

**Versions checked 27 October 2026** on npm, PyPI, Packagist and Docker Hub. Policy: the current
stable or LTS release, and the image tags forge-pack's templates use. More than three months after
that date, check again (`npm view next version`, `pip index versions django`, `composer show -a
laravel/framework`).

## How to pick a profile

Ask only what the user has not already told you, one question at a time:

1. Is there an existing codebase? Run `python3 ../forge-audit/detect.py .` and use the profile it
   names: forge does not move an app to another stack. It names `none` (Rails, Flask, ...): no
   profile fits, so stop and tell the user.
2. Does whoever maintains it know PHP, Python or TypeScript already? Prefer that one.
3. Does it need accounts, a database, payments or emails? If not: static.
4. Should people install it on their phone or use it offline? Then `PWA: yes`. A native app-store
   app is outside forge: offer a PWA instead.

| kind of app | default | why |
| --- | --- | --- |
| landing page, docs, portfolio, brochure site | static | nothing to run but nginx |
| front end for an API that already exists | static | the API owns accounts and data |
| accounts and forms: bookings, a shop, a SaaS with payments | laravel | auth, queues and mail built in; Stripe through Cashier |
| admin-heavy or data-heavy, or needs Python libraries (data, PDF, ML) | django | the admin and the Python ecosystem |
| very interactive UI with a lot of client state, a React team | next | React on server and client in one app |

No preference and no clear row: laravel. Write the reason in plan.md either way.

## Shared by all profiles

- One app, no microservices. Secrets only in `.env` (git-ignored); `.env.example` lists every name
  with a fake value.
- End-to-end tests: Playwright (`@playwright/test` 1.64) against the running compose stack, the
  same way for every profile (/forge-test has the example spec).
- TLS and the public domain belong to the user's own reverse proxy, outside forge.

## Shared by the server profiles (laravel, django, next)

- One database. Uploaded files live in a named volume. Times stored in UTC. Money as integer cents
  plus a currency code (`EUR`).
- Dev and prod compose have the same shape. Dev adds `mailpit` (`axllent/mailpit:v1.32`, SMTP on
  port 1025, web inbox on 8025); prod sends mail through the user's own SMTP provider from `.env`.
- Database service: named volume, healthcheck, no published port (or `127.0.0.1` only); the app
  waits for it with `depends_on` and `condition: service_healthy`. PostgreSQL 18 images keep data
  under `/var/lib/postgresql`: mount the volume there, not at `.../data` as for 17 and older.
- Payments: Stripe Checkout in test mode, iDEAL included (EUR only). /forge-build has the details.
- **Rules the database enforces.** Unique numbers: a unique index. Bookings that must not overlap:
  a unique index on the start time is not enough, bookings of different lengths still overlap.
  Tried on `mariadb:11.8` and `postgres:18-alpine`; each profile's Database bullet says where it goes:

  ```sql
  -- MariaDB (no exclusion constraints, no partial indexes): an application-time period. `active` is
  -- 1 while the booking counts, NULL once cancelled. One active row per user: unique (user_id, active).
  alter table bookings add period for slot (starts_at, ends_at);
  alter table bookings add unique bookings_no_overlap (stylist_id, active, slot without overlaps);
  -- PostgreSQL: an exclusion constraint, and a partial unique index.
  create extension if not exists btree_gist;
  alter table bookings add constraint bookings_no_overlap exclude using gist
    (stylist_id with =, tstzrange(starts_at, ends_at) with &&) where (status <> 'cancelled');
  create unique index subscriptions_one_active on subscriptions (user_id) where status = 'active';
  ```

  The losing request gets a duplicate-key error: catch it and say the slot was just taken.

## laravel: PHP + MariaDB (Laravel)

- **Pick it when** the app is mostly pages, forms and accounts: bookings, shops, a SaaS with
  subscriptions. The default when the user has no preference.
- **Versions** (the latest Laravel major, each with two years of security fixes; the newest PHP it
  supports; LTS databases): Laravel 13.38 (fixes until March 2028), PHP 8.5 `php:8.5-fpm-alpine`,
  MariaDB 11.8 LTS `mariadb:11.8` (until June 2028), nginx 1.30
  `nginxinc/nginx-unprivileged:1.30-alpine`, Node 24 LTS `node:24-alpine` in the build stage only.
- **Start**: `laravel new app` (the installer offers the starter kits), or
  `composer create-project laravel/laravel app` for a bare app. Set `DB_CONNECTION=mariadb`: the
  skeleton defaults to SQLite. Both come with Tailwind CSS 4. Health URL: `/up` (built in).
- **Folder layout**: `app/Models`, `app/Http/Controllers`, `app/Policies` (one policy per model a user
  owns), `app/Jobs`, `app/Mail`, `database/migrations`, `routes/web.php` (`routes/api.php` only with
  an API), `resources/views` (Blade, Livewire) or `resources/js` (Inertia), `tests/Feature`,
  `tests/Unit`, `e2e/`.
- **Compose**: `app` (php-fpm), `web` (nginx: serves `public/`, passes PHP to `app`), `db` (mariadb),
  `mailpit` (dev). Optional, same image as `app`: `worker` (`php artisan queue:work`) and `scheduler`
  (`php artisan schedule:work`). Queue, cache and sessions use the database driver: no Redis.
- **Auth**: an official starter kit (Livewire, React, Vue or Svelte), all built on Laravel Fortify
  1.x: registration, login, email verification, password reset, two-factor, passkeys. Pick Laravel's
  built-in authentication, not WorkOS AuthKit (a hosted service outside the compose stack). Own front
  end: Fortify alone. API tokens or an SPA: Sanctum (`php artisan install:api`). Not Breeze (old).
- **Database**: Laravel migrations on MariaDB. Each foreign key gets a decided rule:
  `->cascadeOnDelete()`, `->restrictOnDelete()` or `->nullOnDelete()`. The MariaDB rules above go
  in the migration as `DB::statement()` calls after `Schema::create()`; one active row per user is
  `$table->unique(['user_id', 'active'])` on a nullable `active` column. Policies plus queries
  through the owner (`$request->user()->invoices()`) for data access.
- **Tests**: PHPUnit 12 (the skeleton's default) or Pest 5 (needs PHP 8.4+), `php artisan test`,
  `RefreshDatabase`; Playwright end to end. The skeleton's `phpunit.xml` uses SQLite in memory, which
  lacks the MariaDB rules: set `DB_CONNECTION` to `mariadb` and `DB_DATABASE` to `testing` there
  with `force="true"`, run `php artisan config:clear` first, and create the database with a `.sql`
  file in the db service's `/docker-entrypoint-initdb.d` (it runs when the volume is new):
  `CREATE DATABASE testing; GRANT ALL ON testing.* TO 'app'@'%';` (`app` is the `DB_USERNAME`).
- **Stripe**: `stripe/stripe-php` 22, or Laravel Cashier 16 (a separate package) for subscriptions.
  With Cashier, do not require stripe-php yourself (Cashier 16 brings stripe-php 21 or older) and set
  `CASHIER_CURRENCY=eur` (its default is usd). `.env` names, Cashier's, with or without it:
  `STRIPE_KEY`, `STRIPE_SECRET`, `STRIPE_WEBHOOK_SECRET`.
- **Email**: `MAIL_MAILER=smtp`, `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`,
  `MAIL_SCHEME`, `MAIL_FROM_ADDRESS`, `MAIL_FROM_NAME` (dev: `mailpit`, 1025). Queue it (`ShouldQueue`).
- **Keep on**: CSRF protection (the `PreventRequestForgery` middleware in the `web` group; exclude
  only the Stripe webhook route), Blade escaping `{{ }}`, query bindings, `Hash::make`, encrypted
  HttpOnly session cookies, Fortify's login rate limit, validation on every input. Production:
  `APP_ENV=production`, `APP_DEBUG=false`, `SESSION_SECURE_COOKIE=true`, `trustProxies` set in
  `bootstrap/app.php` for the user's reverse proxy.

**Five classic mistakes**
1. Mass assignment: `$guarded = []` with `create($request->all())`. Use `$fillable` and
   `$request->validated()`.
2. Route model binding without a check: `/invoices/{invoice}` shows anyone's invoice. A policy per
   model and `Gate::authorize()` in every action, or query through the user.
3. `APP_DEBUG=true` in production: the error page shows environment details.
4. User input in `DB::raw()`, `whereRaw()` or `{!! !!}`. Use bindings and `{{ }}`.
5. N+1 queries. Eager load with `with()`; `Model::preventLazyLoading(! app()->isProduction())`.

## django: Python + Postgres or MariaDB (Django)

- **Pick it when** the app is admin-heavy or data-heavy, or needs Python libraries (data work, PDFs,
  machine learning). The Django admin is a free back office.
- **Versions** (the latest Django feature release, or the LTS when a package you need lags behind;
  the newest Python Django lists): Django 6.1.2 (until December 2027) or 5.2.18 LTS (until April
  2028), Python 3.14 `python:3.14-slim`, PostgreSQL 18 `postgres:18-alpine` (MariaDB alternative:
  11.8 LTS `mariadb:11.8`), gunicorn 26, WhiteNoise 6.12, psycopg 3.3. On PyPI, pytest-django 4.14,
  WhiteNoise 6.12 and django-tasks-db 0.13 (marked beta) list Django only up to 6.0: run the suite
  on 6.1 once before you rely on them, or pick 5.2 LTS.
- **Start**: `django-admin startproject config .`, one app per area (`python manage.py startapp
  billing`). Create a custom user model before the first `migrate`. Health URL: `/healthz` (a
  tiny view). Styling: plain CSS, Tailwind only when the user asks for it.
- **Folder layout**: `manage.py`, `requirements.txt` (pinned), `config/settings.py` (every secret and
  host from environment variables), `config/urls.py`, per app `models.py`, `views.py`, `urls.py`,
  `forms.py`, `admin.py`, `tests/`; `templates/`, `static/`, `public/` (files served at the site
  root through `WHITENOISE_ROOT`), `e2e/`.
- **Compose**: `app` (gunicorn; WhiteNoise serves static files, so no nginx), `db` (postgres),
  `mailpit` (dev). Optional, same image: `worker` (`python manage.py db_worker`, see jobs).
- **Auth**: `django.contrib.auth` (login, logout, password reset views built in). Social login, email
  verification flows or MFA: django-allauth 65.
- **Database**: Django migrations, PostgreSQL by default through `psycopg[binary]` 3; MariaDB through
  `mysqlclient` 2.3 (needs the MariaDB client headers in the image). A decided `on_delete` on every
  `ForeignKey`, `Meta.indexes` for what you filter and sort on, `USE_TZ = True` (the default). The
  rules above: PostgreSQL, `ExclusionConstraint` (with `BtreeGistExtension()` in the migration) and
  `UniqueConstraint(condition=...)`; MariaDB ignores `condition`, so the shared SQL in `RunSQL` and a
  plain `UniqueConstraint` on `user` and a nullable `active`.
- **Jobs**: the built-in tasks framework (`django.tasks`, since 6.0) ships only development
  backends. Add `django-tasks-db` 0.13 (its `DatabaseBackend` keeps jobs in the same database) and
  run `python manage.py db_worker`. No Redis, no Celery.
- **Tests**: pytest 9 with pytest-django 4.14 (`manage.py test` is the fallback), on the same
  database engine as production. Playwright end to end.
- **Stripe**: `stripe` (stripe-python) 16. `.env` names: `STRIPE_PUBLISHABLE_KEY`,
  `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`.
- **Email**: SMTP from `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, set in
  Django 6.1's new `MAILERS` setting (`smtp.EmailBackend` with `OPTIONS`); old `EMAIL_*` settings warn.
- **Keep on**: `SecurityMiddleware`, `CsrfViewMiddleware`, `XFrameOptionsMiddleware`, template
  auto-escaping, ORM parameters, PBKDF2 hashing and the password validators; add the built-in CSP
  middleware (`ContentSecurityPolicyMiddleware` with `SECURE_CSP`, since 6.0). Production:
  `DEBUG = False`, `SECRET_KEY` and `ALLOWED_HOSTS` from the environment, `SESSION_COOKIE_SECURE`,
  `CSRF_COOKIE_SECURE`, `CSRF_TRUSTED_ORIGINS` and `SECURE_PROXY_SSL_HEADER` for the user's reverse
  proxy, and `python manage.py check --deploy` without warnings.

**Five classic mistakes**
1. `DEBUG = True`, a hard-coded `SECRET_KEY` or `ALLOWED_HOSTS = ["*"]` in production.
2. Queries not scoped to the user: `Invoice.objects.get(pk=pk)` shows anyone's invoice. Use
   `get_object_or_404(Invoice, pk=pk, owner=request.user)`.
3. Raw SQL built with f-strings or `%`, `.extra()`, or `mark_safe` and `|safe` on user input.
4. No custom user model at the start: changing it later is a painful migration.
5. N+1 queries in lists and the admin. Use `select_related`, `prefetch_related`,
   `list_select_related`.

## next: Node/TypeScript + Postgres (Next.js, self-hosted)

- **Pick it when** the UI is very interactive with a lot of client state, or the team works in React
  and TypeScript. It runs as a plain Node server in a container.
- **Versions** (the latest Next.js major on a Node LTS release): Next.js 16.4.3 with React 19 and
  the App Router, Node 24 LTS `node:24-alpine` (until April 2028, the tag forge-pack uses; Node 26
  becomes LTS on 28 October 2026: move the templates and the plan to it together), PostgreSQL 18
  `postgres:18-alpine`, Drizzle ORM 0.45 with drizzle-kit 0.31 and the `pg` driver 8, Better Auth
  1.7, zod 4 for input validation.
- **Start**: `npx create-next-app@latest app` (TypeScript, App Router, Tailwind CSS 4). In
  `next.config.ts`: `output: "standalone"` and `poweredByHeader: false`. The standalone build
  leaves out `public/` and `.next/static/`: the Dockerfile copies them in. Health URL:
  `/api/health` (`app/api/health/route.ts`).
- **Folder layout**: `app/` (routes: `page.tsx`, `layout.tsx`, `route.ts` for API, `actions.ts` for
  Server Actions), `lib/db/schema.ts` (Drizzle tables), `lib/db/index.ts` (connection), `lib/dal.ts`
  (data access layer: every query checks the session and the owner), `lib/auth.ts` (Better Auth),
  `drizzle/` (generated SQL migrations, committed), `proxy.ts` (optional, redirects only; Next 16
  renamed `middleware.ts` to `proxy.ts`), `tests/` (Vitest), `e2e/`.
- **Compose**: `app` (`node server.js` from the standalone build), `db` (postgres), `mailpit` (dev).
  Optional, same image: `worker` running a job script with pg-boss 12 (jobs stored in Postgres).
- **Auth**: Better Auth with `@better-auth/drizzle-adapter`: email and password, verification, social
  login, sessions in the database. Auth.js now recommends Better Auth; keep it only where it is in use.
- **Database**: Drizzle schema in TypeScript; `npx drizzle-kit generate` writes SQL to `drizzle/`;
  `npx auth@latest generate` (the Better Auth CLI) adds its tables; the PostgreSQL rules above go in
  a custom migration (`npx drizzle-kit generate --custom`). drizzle-kit is a dev tool: in the
  container, a small script runs `migrate()` from `drizzle-orm/node-postgres/migrator` before the
  server starts. Times: `timestamp({ withTimezone: true })`; money: `integer` cents.
- **Tests**: Vitest 5 for logic and the data access layer (against a test database), Playwright end
  to end.
- **Stripe**: `stripe` (stripe-node) 23 in route handlers. The webhook route reads the raw body with
  `await request.text()` before it verifies the signature. `.env` names: `STRIPE_SECRET_KEY`,
  `STRIPE_WEBHOOK_SECRET`.
- **Email**: nodemailer over SMTP from `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`,
  `MAIL_FROM`.
- **Keep on**: React's escaping; Server Actions accept only POST and compare Origin with Host (list
  extra origins in `experimental.serverActions.allowedOrigins` only if the user's proxy changes the
  host); variables without the `NEXT_PUBLIC_` prefix stay on the server; `import "server-only"` in
  every module that touches the database or secrets; Better Auth's HttpOnly SameSite cookies and
  `trustedOrigins`; security headers (CSP, frame-ancestors) in `headers()` in `next.config.ts`.

**Five classic mistakes**
1. A secret in a `NEXT_PUBLIC_` variable: it is copied into the JavaScript every visitor gets.
2. Auth checked only in `proxy.ts` or a layout. Server Actions and route handlers are public POST
   endpoints: check session and owner inside each one (a middleware-only check was bypassed in
   2025, CVE-2025-29927).
3. Whole database rows passed to client components (password hashes, other people's emails).
   Return only the fields a screen needs from the data access layer.
4. SQL built from strings with `sql.raw()`. Use the query builder or the `sql` template tag, which
   sends values as parameters.
5. Personal data in a shared cache (`"use cache"`, cached fetches, static pages): one user sees
   another's data. Keep per-user pages dynamic.

## static: static site or SPA (Vite + nginx)

- **Pick it when** there is no server logic of its own: landing pages, docs, portfolios, or a
  single-page app on top of an API that already exists.
- **Versions** (the latest Vite major, a Node LTS release to build, nginx stable to serve): Vite
  8.3.5, Node 24 LTS `node:24-alpine` to build, nginx 1.30 `nginxinc/nginx-unprivileged:1.30-alpine`
  (non-root), Vitest 5, Tailwind CSS 4.3 (`@tailwindcss/vite`).
- **Start**: `npm create vite@latest app` with a template (`vanilla-ts`, `react-ts`, `vue-ts`,
  `svelte-ts`; write the one you pick in plan.md). Plain pages: `vanilla-ts` with one `.html` file per
  page (Vite multi-page build). Health URL: `/`.
- **Folder layout**: `index.html`, `src/`, `public/` (copied as-is to `dist/`: icons, `robots.txt`,
  manifest, `sw.js`), `vite.config.ts`, `tests/` (Vitest), `e2e/`, `nginx.conf`.
- **Compose**: one service, `web`: nginx serving `dist/`, built with Node in the first stage. SPA:
  unknown paths fall back to `index.html` (`try_files $uri $uri/ /index.html;`). Hashed files in
  `/assets/` get a long cache; `index.html` gets `Cache-Control: no-cache`.
- **Auth**: none. Accounts are the API's job (an HttpOnly session cookie set by the API). No API yet
  and it needs accounts: this is not a static app; pick laravel, django or next.
- **Database**: none. **Email**: none (a contact form needs a server: pick another profile).
- **Tests**: Vitest 5 for logic and components; Playwright against the nginx container.
- **Stripe**: a secret key never lives in a browser bundle, so Stripe Payment Links (made in the
  Dashboard, test mode), fulfilled by hand. Reacting to a payment needs a webhook: a server profile.
- **Keep on**: the CSP, `X-Content-Type-Options`, `Referrer-Policy` and `frame-ancestors` headers in
  forge-pack's nginx.conf; React, Vue and Svelte escape text by default; no source maps in the
  production build unless the user wants them.

**Five classic mistakes**
1. API keys in `VITE_` variables: every `VITE_` variable ends up in the JavaScript anyone can read.
2. Access checks only in the browser (hidden buttons, route guards). The API checks every request.
3. Tokens in `localStorage`, where any injected script can read them. Use an HttpOnly cookie.
4. No SPA fallback (a refresh on `/settings` gives 404) or a long cache on `index.html` (people stay
   on an old version).
5. `innerHTML`, `v-html`, `{@html}` or `dangerouslySetInnerHTML` with user or API content.

## PWA toggle (any profile)

`PWA: yes` in plan.md adds the parts below. Installing needs HTTPS (localhost counts in dev).

- **Manifest** `manifest.webmanifest`: `name`, `short_name`, `start_url: "/"`, `scope: "/"`,
  `display: "standalone"`, `background_color`, `theme_color`, `icons`. Every page links it
  (`<link rel="manifest">`) with `<meta name="theme-color">` and `<link rel="apple-touch-icon">`.
- **Icons**, the user's own: 192x192 and 512x512 PNG (`"purpose": "any"`), a 512x512
  `"purpose": "maskable"` with the logo inside the middle 80%, and a 180x180 apple-touch-icon.
- **Service worker** at the site root (`/sw.js`), so its scope is the whole app, served with
  `Cache-Control: no-cache` so updates arrive.
- **Offline page** `offline.html`: plain, no personal data, cached when the worker installs.
- **Caching**: pages (HTML) network first, the offline page when the network fails. Hashed static
  assets cache first. Never cached: API responses, pages a logged-in user saw, POSTs and other
  non-GET requests, other domains (Stripe). Those go straight to the network. Pages for logged-in
  users also carry `Cache-Control: no-store` or `private, no-cache` so the browser's own cache does
  not keep them (Laravel and dynamic Next.js pages do this by default; Django: `@never_cache`).
- **Leaving the app to pay**: after Stripe Checkout or the bank app, the customer often lands in the
  normal browser, and on iOS that shares no cookies or storage with the installed app. So the return
  page works without the app's session: it finds the order by a random token in the URL and shows
  only its status ("paid" or "waiting for your bank"). Put this case in the test plan.
- **Updates**: a new worker waits. The page shows "A new version is available" with a button that
  posts `SKIP_WAITING` to `registration.waiting`, then reloads once on `controllerchange`. Bump
  `VERSION` in sw.js with every release; the old cache is deleted on activate.

| profile | manifest, sw.js, offline.html, icons | hashed assets |
| --- | --- | --- |
| laravel | `public/` | `/build/assets/` |
| django | `public/`, served at the root with `WHITENOISE_ROOT` | `/static/` (use WhiteNoise's `CompressedManifestStaticFilesStorage`) |
| next | `public/` (or the manifest as `app/manifest.ts`) | `/_next/static/` |
| static | `public/` | `/assets/` |

A minimal `sw.js` that follows these rules. Set `ASSETS` to the profile's folder above:

```js
const VERSION = "v1", CACHE = "app-" + VERSION; // bump VERSION with every release
const OFFLINE = "/offline.html", ASSETS = "/build/assets/";
self.addEventListener("install", (e) => e.waitUntil(caches.open(CACHE).then((c) => c.add(OFFLINE))));
self.addEventListener("activate", (e) => e.waitUntil(caches.keys().then((keys) =>
  Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))));
self.addEventListener("message", (e) => { if (e.data === "SKIP_WAITING") self.skipWaiting(); });
self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return; // network only
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).catch(() => caches.match(OFFLINE)));
  } else if (url.pathname.startsWith(ASSETS)) {
    e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
      return res;
    })));
  } // anything else is not handled here: the browser fetches it and nothing is stored
});
```

Plugins can generate a worker instead: vite-plugin-pwa 2.0 (static, and Laravel's Vite build) and
Serwist 9.5 (Next.js). Check what they generate against the caching rules above.
