# Stack profiles

The one reference for the four stack profiles and the PWA toggle, used by `/forge-plan`, `/forge-build`
(build and pack), `/forge-check` and `/forge-design`. Everything runs in the user's own compose stack.

**Versions checked 27 October 2026** (stable or LTS, and the image tags of `/forge-build pack`), three
0.187 on 10 November 2026. Recheck after three months: `npm view next version`, `npm view three
version`, `pip index versions django`, `composer show -a laravel/framework`.

## How to pick a profile

Ask only what the user has not already told you, one question at a time:

1. Is there an existing codebase? Use the profile `python3 ../forge-check/detect.py .` names: forge
   does not move an app to another stack. It names `none` (Rails, Flask, ...): stop and tell the user.
2. Does whoever maintains it know PHP, Python or TypeScript already? Prefer that one.
3. Does it need accounts, a database, payments or emails? If not: static.
4. Should people install it on their phone or use it offline? Then `PWA: yes`. Offline, the server
   profiles show an offline page; only a static app keeps working (PWA toggle, "Working offline").
   A native app-store app is outside forge: offer a PWA instead.

| kind of app | default | why |
| --- | --- | --- |
| landing page, docs, portfolio, brochure site | static | nothing to run but nginx |
| front end for an API that already exists | static | the API owns accounts and data |
| accounts and forms: bookings, a shop, a SaaS with payments | laravel | auth, queues and mail built in; Stripe through Cashier |
| no accounts, shared by link: polls, sign-up sheets, guest forms | laravel, bare skeleton | a database without logins |
| admin-heavy or data-heavy, or needs Python libraries (data, PDF, ML) | django | the admin and the Python ecosystem |
| very interactive UI with a lot of client state, a React team | next | React on server and client in one app |

No preference and no clear row: laravel. Write the reason in plan.md either way.

## Shared by all profiles

- One app, no microservices. Secrets only in `.env` (git-ignored); `.env.example` lists every name
  with a fake value. TLS and the public domain belong to the user's own reverse proxy.
- End-to-end tests: Playwright (`@playwright/test` 1.64) against the running compose stack.
- **3D scenes**, look level 4 and 5 only (1 to 3 add no library; level 3 depth is the kit's `depth.js`): `three`
  0.187 from npm, never a CDN, and the kit's files copied into the app (`../forge-design/scenes/lazy.js`,
  `stage.js`, `glsl.js`, the scene). Three loads on the client only, on the screens with a scene, when near
  (`lazyScene`), with a poster for no WebGL and reduced motion. Files and mount: `../forge-design/scenes.md`.

## Shared by the server profiles (laravel, django, next)

- One database. Uploaded files live in a named volume. Times stored in UTC. Money as integer cents
  plus a currency code (`EUR`). Payments: Stripe Checkout in test mode, iDEAL included.
- Dev and prod compose have the same shape. Dev adds `mailpit` (`axllent/mailpit:v1.32`, SMTP on
  port 1025, web inbox on 8025); prod sends mail through the user's own SMTP provider from `.env`.
- Database service: named volume, healthcheck, no published port (or `127.0.0.1` only); the app
  waits for it with `depends_on` and `condition: service_healthy`. PostgreSQL 18 images keep data
  under `/var/lib/postgresql`: mount the volume there, not at `.../data` as for 17 and older.
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

- **Versions** (the latest major, two years of security fixes): Laravel 13.38 (until March 2028),
  PHP 8.5 `php:8.5-fpm-alpine`, MariaDB 11.8 LTS `mariadb:11.8` (until June 2028), nginx 1.30
  `nginxinc/nginx-unprivileged:1.30-alpine`, Node 24 LTS `node:24-alpine` in the build stage only.
- **Start**: `laravel new app` (the installer offers the starter kits), or for a bare app (no
  accounts) `composer create-project laravel/laravel app`. Set `DB_CONNECTION=mariadb`: the
  skeleton defaults to SQLite. Both come with Tailwind CSS 4. Health URL: `/up` (built in).
- **Compose**: `app` (php-fpm), `web` (nginx: serves `public/`, passes PHP to `app`), `db` (mariadb),
  `mailpit` (dev). Optional, same image as `app`: `worker` (`php artisan queue:work`) and `scheduler`
  (`php artisan schedule:work`). Queue, cache and sessions use the database driver: no Redis.
- **Auth**: an official starter kit (Livewire, React, Vue or Svelte) with Laravel's built-in auth,
  not WorkOS AuthKit (hosted outside the stack); own front end: Fortify 1.x; API tokens or an SPA:
  Sanctum (`php artisan install:api`); not Breeze (old). The kits and `fortify:install` turn on
  public registration, profile updates, two-factor and passkeys: keep only what plan.md's Auth
  section names. Only staff log in: remove `Features::registration()` and `CreateNewUser`, make
  accounts with an artisan command, and test that GET and POST `/register` answer 404.
- **Database**: Laravel migrations on MariaDB; every foreign key gets a decided rule
  (`->cascadeOnDelete()`, `->restrictOnDelete()` or `->nullOnDelete()`). The MariaDB rules above go
  in the migration as `DB::statement()` after `Schema::create()`; one active row per user is
  `$table->unique(['user_id', 'active'])` on a nullable `active`. Data access: a policy per model a
  user owns (`app/Policies`) plus queries through the owner (`$request->user()->invoices()`).
- **Tests**: PHPUnit 12 (the skeleton's default) or Pest 5 (PHP 8.4+), `php artisan test`,
  `RefreshDatabase`; Playwright end to end. In `phpunit.xml`, with `force="true"`: `DB_CONNECTION`
  `mariadb` and `DB_DATABASE` `testing` (SQLite lacks the MariaDB rules), `LOG_CHANNEL` `null`
  (`.env.example` logs to stderr); then `php artisan config:clear`. A `.sql` file in the db
  service's `/docker-entrypoint-initdb.d` makes the database when the volume is new (`app` is the
  `DB_USERNAME`): `CREATE DATABASE testing; GRANT ALL ON testing.* TO 'app'@'%';`. CSS and JS are
  built in the image, not on the host: `$this->withoutVite()` in `setUp()` of `tests/TestCase.php`.
- **Stripe**: `stripe/stripe-php` 22, or Laravel Cashier 16 for subscriptions (then no stripe-php of
  your own, Cashier brings 21 or older, and `CASHIER_CURRENCY=eur`, its default is usd). `.env`
  names, Cashier's either way: `STRIPE_KEY`, `STRIPE_SECRET`, `STRIPE_WEBHOOK_SECRET`.
- **Email**: `MAIL_MAILER=smtp`, `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`,
  `MAIL_SCHEME`, `MAIL_FROM_ADDRESS`, `MAIL_FROM_NAME` (dev: `mailpit`, 1025). Queue it (`ShouldQueue`).
  Write Markdown mailables (`Content(markdown: ...)`), whose text part is decoded: a plain
  `Content(text: ...)` view with `{{ }}` sends names as `O&#039;Brien &amp; Zoe`.
- **Keep on**: CSRF (`PreventRequestForgery` in the `web` group; exclude only the Stripe webhook),
  Blade's `{{ }}`, query bindings, `Hash::make`, encrypted HttpOnly session cookies, Fortify's login
  rate limit, validation on every input. Production: `APP_ENV=production`, `APP_DEBUG=false`,
  `SESSION_SECURE_COOKIE=true`, `trustProxies` in `bootstrap/app.php` for the user's reverse proxy.
- **3D scene**: `npm install three` in the app root, next to Vite's `package.json`; the kit's files go
  in `resources/js/scenes/`. `resources/js/hero.js` calls `lazyScene(el, () => import("./scenes/form.js"))`,
  and `app.js` loads hero.js with `import()` only on a page with the container: Vite splits three off.

**Classic mistakes**
1. Mass assignment: `$guarded = []` with `create($request->all())`. Use `$fillable`, `validated()`.
2. Route model binding without a check: `/invoices/{invoice}` shows anyone's invoice. A policy per
   model and `Gate::authorize()` in every action, or query through the user.
3. `APP_DEBUG=true` in production: the error page shows environment details.
4. User input in `DB::raw()`, `whereRaw()` or `{!! !!}`. Use bindings and `{{ }}`.
5. N+1 queries. Eager load with `with()`; `Model::preventLazyLoading(! app()->isProduction())`.

## django: Python + Postgres or MariaDB (Django)

- **Versions** (the latest feature release, or the LTS when a package lags behind): Django 6.1.2
  (until December 2027) or 5.2.18 LTS (until April 2028), Python 3.14 `python:3.14-slim`, PostgreSQL
  18 `postgres:18-alpine` (MariaDB alternative: 11.8 LTS `mariadb:11.8`), gunicorn 26, WhiteNoise
  6.12, psycopg 3.3. On PyPI, pytest-django 4.14, WhiteNoise 6.12 and django-tasks-db 0.13 (beta)
  list Django only up to 6.0: run the suite on 6.1 once before you rely on them, or pick 5.2 LTS.
- **Start**: `django-admin startproject config .`, then one app per area:
  `python manage.py startapp billing`. Create a custom user model before the first `migrate`.
  Health URL: `/healthz` (a tiny view). Styling: plain CSS, Tailwind only when the user asks for it.
- **Folder layout**: `manage.py`, pinned `requirements.txt`, `config/settings.py` (secrets and hosts
  from the environment), per app `models.py`, `views.py`, `urls.py`, `forms.py`, `admin.py`,
  `tests/`; `templates/`, `static/`, `public/` (served at the root through `WHITENOISE_ROOT`), `e2e/`.
- **Compose**: `app` (gunicorn; WhiteNoise serves static files, so no nginx), `db` (postgres),
  `mailpit` (dev). Optional, same image: `worker` (`python manage.py db_worker`, see jobs).
- **Auth**: `django.contrib.auth` (login, logout, password reset built in); social login, email
  verification or MFA: django-allauth 65.
- **Database**: Django migrations; PostgreSQL through `psycopg[binary]` 3, MariaDB through `mysqlclient` 2.3
  (needs the client headers in the image). A decided `on_delete` on every `ForeignKey`, `Meta.indexes`
  for what you filter and sort on, `USE_TZ = True` (the default). The rules above, PostgreSQL:
  `ExclusionConstraint` (`BtreeGistExtension()` in the migration) and `UniqueConstraint(condition=...)`;
  MariaDB ignores `condition`: the shared SQL in `RunSQL`, a `UniqueConstraint` on `user` and a nullable `active`.
- **Jobs**: the built-in `django.tasks` (6.0+) ships only development backends: add `django-tasks-db`
  0.13 (jobs in the same database) and run `python manage.py db_worker`. No Redis, no Celery.
- **Tests**: pytest 9 with pytest-django 4.14 on the production database engine; Playwright end to end.
- **Stripe**: stripe-python 16. `.env`: `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`.
- **Email**: SMTP from `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, set in
  Django 6.1's new `MAILERS` setting (`smtp.EmailBackend` with `OPTIONS`); old `EMAIL_*` settings warn.
- **Keep on**: `SecurityMiddleware`, `CsrfViewMiddleware`, `XFrameOptionsMiddleware`, template
  auto-escaping, ORM parameters, PBKDF2 hashing, the password validators, and the built-in CSP
  middleware (`ContentSecurityPolicyMiddleware` with `SECURE_CSP`, 6.0+). Production: `DEBUG = False`,
  `SECRET_KEY` and `ALLOWED_HOSTS` from the environment, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
  `CSRF_TRUSTED_ORIGINS`, `SECURE_PROXY_SSL_HEADER`, and `manage.py check --deploy` without warnings.
- **3D scene**: no bundler. `npm install three` at the root; an npm script copies `three.module.js`,
  `three.core.js` and the LICENSE to `static/vendor/three/` (committed: the image needs no Node); the kit
  goes in `static/js/scenes/`. An inline import map points `three` there (its hash in `SECURE_CSP`); a
  module script loads `static/js/hero.js`, whose `lazyScene` loads the scene when it is near.

**Classic mistakes**
1. `DEBUG = True`, a hard-coded `SECRET_KEY` or `ALLOWED_HOSTS = ["*"]` in production. Fixing it in
   an existing app: what hangs on `if not DEBUG` (`SECURE_SSL_REDIRECT`) then hits the tests and
   runserver too, so give the redirect its own switch or leave it to the proxy; static files need
   collectstatic and WhiteNoise; dev and tests need `DJANGO_DEBUG=true` or a dev `SECRET_KEY` (README).
2. Queries not scoped to the user: `Invoice.objects.get(pk=pk)` shows anyone's invoice. Use
   `get_object_or_404(Invoice, pk=pk, owner=request.user)`.
3. Raw SQL built with f-strings or `%`, `.extra()`, or `mark_safe` and `|safe` on user input.
4. No custom user model at the start: changing it later is a painful migration.
5. N+1 queries in lists and the admin: `select_related`, `prefetch_related`, `list_select_related`.
6. `@csrf_exempt` on a view that a logged-in form posts to. Only a signed webhook may skip CSRF.
7. `datetime.now()` or `utcnow()` instead of `django.utils.timezone.now()` while `USE_TZ` is on.
8. A field looked up on every request (ticket codes, tokens, slugs, emails) without `db_index`,
   `unique` or a `Meta.indexes` entry: check each `.filter(field=...)` in the views against the models.

## next: Node/TypeScript + Postgres (Next.js, self-hosted)

- **Versions**: Next.js 16.4.3 with React 19 and the App Router, Node 24 LTS `node:24-alpine`
  (maintenance LTS until 30 April 2028, the tag the pack templates use), PostgreSQL 18
  `postgres:18-alpine`, Drizzle ORM 0.45 (drizzle-kit 0.31, `pg` 8), Better Auth 1.7, zod 4.
- **Start**: `npx create-next-app@latest app` (TypeScript, App Router, Tailwind CSS 4), then
  `npm i -D @types/node@24 vitest@5` (the image's Node; the scaffold's `@types/node` 20 blocks
  Vitest 5). `next.config.ts`: `output: "standalone"`, `poweredByHeader: false`, and with logins delete
  `cacheComponents` and `partialPrefetching` (the scaffold turns them on; every page then streams a
  200 shell first, so another user's record answers 200, not 404). The Dockerfile copies `public/`
  and `.next/static/` into the standalone build. Health URL: `/api/health` (`app/api/health/route.ts`).
- **Folder layout**: `app/` (routes, `actions.ts` for Server Actions), `lib/db/schema.ts` (Drizzle
  tables), `lib/db/index.ts` (connection), `lib/dal.ts` (data access layer: every query checks the
  session and the owner), `lib/auth.ts` (Better Auth), `lib/auth-client.ts`, `drizzle/` (generated
  SQL, committed), `proxy.ts` (optional, redirects only; was `middleware.ts`), `tests/`, `e2e/`.
- **Compose**: `app` (`node server.js` from the standalone build), `db` (postgres), `mailpit` (dev).
  Optional, same image: `worker` running a job script with pg-boss 12 (jobs stored in Postgres).
- **Auth**: Better Auth with `drizzleAdapter` from `better-auth/adapters/drizzle` (no extra package),
  sessions in the database. Sign up, log in, log out, password reset and account deletion go from
  the browser to `/api/auth/*` through `createAuthClient` (`better-auth/react`); on the server use
  only `auth.api.getSession({ headers: await headers() })`. Account deletion: set
  `user: { deleteUser: { enabled: true } }`; app tables reference `user.id` with `onDelete: "cascade"`.
  Behind a reverse proxy, set Better Auth's `advanced.ipAddress`, or all visitors share one rate limit.
- **Database**: Drizzle schema in TypeScript; `npx drizzle-kit generate` writes SQL to `drizzle/`,
  which `migrate()` in `instrumentation.ts` runs when the server starts (`/forge-build pack` adds it). The
  PostgreSQL rules above go in a custom migration (`npx drizzle-kit generate --custom`). Times:
  `timestamp({ withTimezone: true })`; money: `integer` cents. Better Auth's tables: comment out
  `import "server-only"` in the modules lib/auth.ts imports (its CLI refuses it), run its CLI at the
  installed better-auth version, add the time zone the CLI leaves out, and put the imports back:
  ```sh
  npx auth@<better-auth version> generate --config lib/auth.ts --output lib/db/auth-schema.ts --yes
  perl -pi -e 's/timestamp\("(\w+)"\)/timestamp("$1", { withTimezone: true })/g' lib/db/auth-schema.ts
  ```
- **Tests**: Vitest 5 for logic and the data access layer (on a test database); Playwright end to end.
  Log in once per seed user in a setup project and reuse `storageState`, or the sign-in rate limit
  fails e2e runs with 429 (never raise the limit for tests). React 19 empties uncontrolled inputs
  after a form action: return the typed values with an error and test that they stay.
- **Stripe**: `stripe` (stripe-node) 23 in route handlers; the webhook verifies the signature on
  `await request.text()` (the raw body). `.env`: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`.
- **Email**: nodemailer over SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`.
- **Keep on**: React's escaping; Server Actions accept only POST and compare Origin with Host (extra
  origins in `experimental.serverActions.allowedOrigins` only if the proxy changes the host); only
  `NEXT_PUBLIC_` variables reach the browser; `import "server-only"` in every module with database or
  secrets; Better Auth's HttpOnly cookies, `trustedOrigins` and rate limit; CSP in `next.config.ts`.
- **3D scene**: `npm install three` in the app; the kit's files go in `lib/scenes/`. A client component
  (`"use client"`) runs `lazyScene(ref.current, () => import("@/lib/scenes/form.js"))` in `useEffect`,
  `destroy()` on unmount. Load it with `dynamic(..., { ssr: false })` from a client component: no SSR.

**Classic mistakes**
1. A secret in a `NEXT_PUBLIC_` variable: it is copied into the JavaScript every visitor gets.
2. Auth checked only in `proxy.ts` or a layout. Server Actions and route handlers are public POST
   endpoints: check session and owner in each one (middleware-only checks fell to CVE-2025-29927).
3. Whole database rows passed to client components (password hashes, other people's emails).
   Return only the fields a screen needs from the data access layer.
4. SQL built from strings with `sql.raw()`. Use the query builder or the `sql` template tag.
5. Personal data in a shared cache (`"use cache"`, static pages): one user sees another's data.
6. Sign-in, sign-up, password reset or account deletion through `auth.api.*` in a Server Action: it
   skips the rate limit and origin check, which run only on `/api/auth/*` (passwords can be guessed).

## static: static site or SPA (Vite + nginx)

- **Versions**: Vite 8.3.5, Node 24 LTS `node:24-alpine` to build, nginx 1.30 (non-root)
  `nginxinc/nginx-unprivileged:1.30-alpine`, Vitest 5, Tailwind CSS 4.3 (`@tailwindcss/vite`).
- **Start**: `npm create vite@latest app` with a template (`vanilla-ts`, `react-ts`, `vue-ts` or
  `svelte-ts`, named in plan.md). Plain pages: `vanilla-ts`, one `.html` per page. Health URL: `/`.
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
  the pack templates' nginx.conf; the framework's escaping; no source maps in production unless asked for.
- **3D scene**: `npm install three` in the app; the kit's files go in `src/scenes/`. Through Vite:
  `src/main.ts` calls `lazyScene(el, () => import("./scenes/form.js"))` on a page with the container,
  and Vite splits three off into `/assets/`. A plain page outside Vite: an import map, as for django.

**Classic mistakes**
1. API keys in `VITE_` variables: every `VITE_` variable ends up in the JavaScript anyone can read.
2. Access checks only in the browser (hidden buttons, route guards). The API checks every request.
3. Tokens in `localStorage`, where any injected script can read them. Use an HttpOnly cookie.
4. No SPA fallback (a refresh on `/settings` gives 404), or a long cache on `index.html` (old versions stay).
5. `innerHTML`, `v-html`, `{@html}` or `dangerouslySetInnerHTML` with user or API content.

## PWA toggle (any profile)

`PWA: yes` in plan.md adds the parts below. Installing needs HTTPS (localhost counts in dev).

- **Manifest** `manifest.webmanifest`: `name`, `short_name`, `start_url: "/"`, `scope: "/"`,
  `display: "standalone"`, `background_color`, `theme_color`, `icons`. Every page links it
  (`<link rel="manifest">`) with `<meta name="theme-color">` and `<link rel="apple-touch-icon">`.
- **Icons**, the user's own: 192x192 and 512x512 PNG (`"purpose": "any"`), a 512x512
  `"purpose": "maskable"` with the logo inside the middle 80%, and a 180x180 apple-touch-icon.
- **Service worker** at the site root (`/sw.js`), so its scope is the whole app, served with
  `Cache-Control: no-cache` so updates arrive. **Offline page** `offline.html`: plain, no personal
  data, stored with its CSS when the worker installs. The CSP blocks inline styles, so it links
  `/offline.css` from the root, with system fonts and the theme's colours (change them with it).
- **Where**: these files go in `public/` (django: served at the root with `WHITENOISE_ROOT`; next:
  or the manifest as `app/manifest.ts`). Hashed assets are under `/build/assets/` (laravel),
  `/static/` (django, WhiteNoise's `CompressedManifestStaticFilesStorage`), `/_next/static/` (next), `/assets/` (static).
- **Caching**: pages (HTML) network first, the offline page when the network fails. Hashed static
  assets cache first. Never cached: API responses, pages a logged-in user saw, POSTs and other
  non-GET requests, other domains (Stripe): those go straight to the network. Pages for logged-in
  users also carry `Cache-Control: no-store` or `private, no-cache` against the browser's own cache
  (Laravel and dynamic Next.js pages do this by default; Django: `@never_cache`).
- **Working offline**, static only and when plan.md says so: its built pages hold no personal data
  and are the same for every visitor, so the worker may store them too. It precaches the pages and
  their hashed assets on install and answers them cache first; updates work as below. Only a
  generated worker (vite-plugin-pwa, below) knows the hashed names. API responses still go to the network.
- **Leaving the app to pay**: after Stripe Checkout or the bank app, the customer often lands in the
  normal browser, and on iOS that shares no cookies or storage with the installed app. So the return
  page works without the app's session: it finds the order by a random token in the URL and shows
  only its status ("paid" or "waiting for your bank"). Put this case in the test plan.
- **Updates**: a new worker waits. The page shows "A new version is available" with a button that
  posts `SKIP_WAITING` to `registration.waiting`, then reloads once on `controllerchange`. Bump
  `VERSION` in sw.js with every release; the old cache is deleted on activate.

A minimal worker that follows these rules is `../forge-plan/sw.example.js`: copy it to
`public/sw.js` and set its `ASSETS` to the profile's hashed assets path. Plugins can generate one
instead: vite-plugin-pwa 2.0 (static, and Laravel's Vite build) and Serwist 9.5 (Next.js). Check
what they generate against the caching rules above.
