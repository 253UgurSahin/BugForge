# Checks by reading the code

Step 8 of `/forge-check secure` (`../forge-check/steps/secure.md`) walks this file by reading the code
and the settings; its Step 6 uses "The running app". What runs depends on the secure level on record
(`python3 ../forge/level.py get secure`):

| from level | what | where in this file |
| --- | --- | --- |
| 3 | the framework checks, for each stack the project uses | Laravel, Django, Next.js, Static site, Stripe |
| 4 | the container checks; the path lists and sessions for probe.py and authz.py | Containers, The running app |
| 5 | the review: a threat model per entry point, the access matrix, abuse and rate-limit cases, the licence review, an attack story per finding | Level 5 |

Each failed check is a finding in the plain format. Default severity in brackets. Say in the report
which stacks you skipped and why, and leave out what is above the level on record.

## Framework checks (level 3)

**Laravel**
- `APP_DEBUG=false` in production (high). What counts is the production value: `.env.example` only
  when it is the production template (a forge-built app, a Dockerfile or deploy script that copies
  it), else the deploy settings. Unknown: a question under "Not checked", not a finding. `php
  artisan about` shows this machine only, where debug on is no finding (Step 6).
- `APP_KEY` is set in `.env`. Check that it is set, never print it (high).
- CSRF protection is on for web routes, with no broad exceptions (high): Laravel 11 and up keep the
  exceptions in `bootstrap/app.php` (`validateCsrfTokens(except: [...])`), older ones in
  `app/Http/Middleware/VerifyCsrfToken.php`.
- Each route group or controller for one role (admin, staff) has its gate: a `can:` or role
  middleware, a policy, or a `Gate::define` the controller checks. Read `routes/web.php` and the
  controllers; a role's page any signed-in user can open is high.
- Models that take request data set `$fillable` or a non-empty `$guarded` (high).

**Django**
- `python manage.py check --deploy` with production settings: each warning (medium).
- `DEBUG = False` in production (high). `SECRET_KEY` read from the environment (high).
- `ALLOWED_HOSTS` lists the real hosts (medium).

**Next.js**
- No secret in any `NEXT_PUBLIC_` variable: those are sent to every browser (high).
- Auth is checked on the server inside each route handler and server action,
  not only in middleware. Middleware alone has been bypassed before (high).
- Server actions are protected against forged posts by Next.js's own Origin check, so their
  forms need no hidden CSRF field. The `allowedOrigins` of `serverActions` in `next.config.*`
  lists only the app's own hosts (high when it lists another host). A `route.ts` that changes
  data on a POST with a cookie session has no such check: SameSite cookies or a token (medium).

**Static site or SPA**
- A strict Content-Security-Policy, without `unsafe-inline` or `unsafe-eval` (headers.py rates it).
- No secrets in the bundle: build it, then run `secretscan.py` on the build folder itself
  (for example `dist`), because the normal walk skips build folders.

**Stripe**
- Test mode only: `sk_test_` and `pk_test_` keys. Live keys are the user's job (critical).
- Webhooks verify the `Stripe-Signature` header with the webhook secret (high).
- Card data never touches the server or database: use Stripe Checkout or Elements (critical).
- Prices and amounts are computed on the server, never taken from the browser (critical).

## Containers (level 4)

Run `python3 ../forge-build/packcheck.py .` when there is a Dockerfile, then read for what it cannot see:

- Runs as a non-root user: a `USER` line in the Dockerfile (medium). Base image pinned, not `latest` (low).
- No secrets baked into the image: no `.env` or other file of secrets (`.env.local`, `auth.json`, `.npmrc`) copied in, no secret in `ENV` or `ARG` (critical).
- `.dockerignore` excludes `.env`, `.git`, `forge-work/` and the other files of secrets in the project (high).

No Dockerfile: "does not apply: the project has no container setup" under "Not checked".

## The running app (level 4)

What Step 6 of the secure steps needs, all in `forge-work/security/`, nothing in the app.

**probe-paths.txt**, from the app's router, one GET path per line: Next.js, every `page.tsx` and
`route.ts` under `app/` (the folder path is the URL; leave out route groups like `(shop)`; fill
`[id]` with an id from a page) and every file under `pages/`; Laravel `php artisan route:list
--method=GET`; Django `urls.py`; the Express routers. Give each query parameter the code reads
(`searchParams`, `req.query`, `request.GET`) a harmless sample value: `/search?q=test`. Leave out
every path that changes something on a GET (log out, delete, approve, impersonate, verwijderen:
the words of `UNSAFE_LINK` in `../forge-check/walk.example.spec.ts`), here and in
private-paths.txt. Exit 2 because the run was cut short: raise `--max-requests` (up to 500) or put
the paths with input first.

**The two sessions**, user A and user B, the two accounts the user named (secure.md, "Say what
comes"). An app with no accounts at all has none: the `no accounts at all` line of Step 6, and
probe.py still runs. Never set up `e2e/` for this. First make sure git ignores what you write:
`git check-ignore -q forge-work/security/a.json`; when it does not, write `forge-work/.gitignore`
with the one line `*`, as gate.py does. Playwright: when the app has it (`node_modules/playwright`)
the script finds it; else install it in this folder only: `cd forge-work/security && npm init -y
&& npm i -D -E playwright && npx playwright install chromium`. Save this as
`forge-work/security/signin.mjs`, with the app's own labels and button name:

```js
// node --env-file=.env forge-work/security/signin.mjs <url> <sign-in path> <email> <VAR> <out> [page ...]
import { chromium } from 'playwright';
const [base, path, email, name, out, ...pages] = process.argv.slice(2);
if (!process.env[name]) { console.error(name + ' is not set in .env'); process.exit(2); }
const browser = await chromium.launch();
const page = await browser.newPage({ baseURL: base });
await page.goto(path);
await page.getByLabel(/e-?mail/i).fill(email);
await page.getByLabel(/password|wachtwoord/i).fill(process.env[name]);
await page.getByRole('button', { name: /sign in|log in|inloggen|aanmelden/i }).click();
await page.waitForURL((u) => u.pathname !== path, { timeout: 15000 });
await page.context().storageState({ path: out });
const origin = new URL(base).origin;
for (const p of pages) { // prints the same-origin links on A's own pages, never their content
  await page.goto(p);
  const links = await page.$$eval('a[href]', (as) => as.map((a) => a.href)); // absolute too: route() in Blade
  const own = links.map((href) => new URL(href)).filter((url) => url.origin === origin);
  console.log([...new Set(own.map((url) => url.pathname + url.search))].join('\n'));
}
await browser.close();
```

Run it once per user (Node 20.6 or newer), shortly before authz.py: an expired session for B
looks like a pass. Use the `.env` file git ignores: `node --env-file=.env
forge-work/security/signin.mjs <url> /login <email of A> E2E_PASSWORD forge-work/security/a.json
/bookings`, and for B with `E2E_PASSWORD_2` and `b.json` (an app forge built: `SEED_PASSWORD` for
both, with `alice@example.test` and `bob@example.test`). When `forge-work/test/e2e.env` exists (the
demo passwords the test part wrote there), put `--env-file=forge-work/test/e2e.env` before
`--env-file=.env`: Node reads both, and the later file wins, as in the e2e config. The session
files are never printed, never committed, and deleted once the report is written (sign in again
for a later run). Sign-in fails, or needs a code by email: the `no sessions` line of Step 6.

**private-paths.txt**, 3 to 10 paths of A's own records, read while signed in as A: the links the
script printed for A's list pages (A's bookings, invoices, profile, an API route with A's id), a
query with a token or signature in it left out.
Only pages with A's own data; no public page and no page every signed-in user sees the same, or
authz.py reports it as read by B.

## Level 5

The review an attacker would do, by reading the code. It writes two files next to the report,
`forge-work/security/threats.md` and `forge-work/security/access.md` (at level 5 the gate asks for
both); their findings go into security.md like any other, with their own X numbers.

### Threat model per entry point

List every way into the app from its routes and handlers: sign-up, login, logout, password reset,
email change, the session and "remember me", API tokens, invite links, payment and webhooks, file
upload, admin screens, search and export. Read auth, session, payment and upload first. For each,
a short block in threats.md:

- **who can reach it**: a visitor, any signed-in user, one role, another server (a webhook);
- **what it trusts**: which input, cookie, header or id it takes as given;
- **what could go wrong**: someone poses as another person, changes data that is not theirs, reads
  it, makes the app stop working, or gets more rights than they have;
- **what the code does about it**: the check, with file and line, or "nothing found";
- **result**: ok, or the finding ID.

### Access matrix

One row per route (from `php artisan route:list`, Django's `urls.py`, the `app/` folders and
`route.ts` files of Next.js, the Express routers), one column per role: visitor, signed-in user,
the owner of the record, another user, admin, and the app's own roles. Each cell holds what should
happen (allow, own only, deny) and what the code does (the guard you read, with file and line). A
cell where the two differ is a finding: critical when another user or a visitor reaches someone's
data, high for a page above the role. Write the table in access.md.

On the running app, where scope.py exits 0, check the "own only" and "deny" cells with authz.py:
one run per role, with that role's session as `--b`, the owner as `--a` and the owner's private
paths in `--urls`, its `--json` output saved as `forge-work/security/authz-<role>.json`. Sign each
role in with signin.mjs as A and B are, with its own variable (`E2E_PASSWORD_ADMIN`) and
`forge-work/security/<role>.json`. A role the user gave no account for (secure.md, "Say what
comes"): "not checked: no account for this role", named at the checkpoint, not asked halfway.

### Abuse and rate limits

For each entry point, what someone would repeat to do harm: guess passwords, send reset emails,
make accounts, try coupon or invite codes, upload large or many files, run an expensive search,
count ids upwards to read records one by one, replay a webhook. Read for a limit: Laravel's
`throttle` middleware or `RateLimiter`, django-axes or django-ratelimit, the auth library's rate
limit in Next.js, express-rate-limit, a size cap, a lock-out, a webhook id that is used only once.
No limit on login or password reset is high; elsewhere medium.

Only on the user's own running app (scope.py exits 0), one short burst may show the limit at work.
Sign up a throwaway account through the app's own sign-up (a new `@example.test` email), then try
at most 20 wrong passwords for it: it should end in a 429 or a lock-out. Never user A, user B or
another seed or demo account: a locked account stops their next sign-in, and the user may use it
themselves ("Rate limits" in `../forge-check/walk.md`). No sign-up in the app: no burst, and say so
under "Not checked". Never a load test, never a real person's account. Do it after the last
authz.py run, clear the counters afterwards as that section says, and name the throwaway account
under "What was checked".

### Secrets in the git history

Step 2 of the secure steps. A secret deleted from the code is still in old commits. Write each
commit's changes to its own file in a temporary folder outside the project, scan that folder, then
delete it. In bash (Git Bash on Windows):

```bash
T=$(mktemp -d)
for c in $(git rev-list --all --max-count=500); do
  git show --no-color --no-ext-diff --format=%H%n "$c" > "$T/$c.diff"
done
python3 ../forge-check/secretscan.py "$T"; rm -rf "$T"
```

Each hit names its file, so its commit, and secretscan masks the value. Never open, print, grep or
paste those files. Under "Not checked": the commits beyond the 500 (`git rev-list --all --count`
gives the total) and the diffs secretscan skipped as over 1 MB.

### Licences

From `forge-work/sbom.json` and supply.py's licence notes, and the fonts, icons and images the app
ships: list each GPL, AGPL, SSPL, unknown or missing licence, what it asks of the user (AGPL: share
the source with everyone who uses a hosted app, not only with those who download it) and whether
that fits the app's own `LICENSE` and the way the user means to offer it. Medium when it clashes,
low when it is only unknown. Not legal advice: the choice is the user's. A yarn, pnpm, bun or
Pipenv lockfile holds no licences, so its packages have none in the SBOM: read each one's licence
in `node_modules/<package>/package.json` (or the installed package's metadata) where it is there,
and call the rest unknown; never install anything for it.

### Attack stories

At level 5 each finding has a `story:` under `effort:`, a few plain sentences: who the attacker is,
what they do step by step, what they get, and what stops them once the fix is in. For example:

```text
story: A visitor signs up for a free account. On the page of their own invoice they change the 7
       in /invoices/7 to 8, and the app shows another customer's name, address and amount. A
       script that counts from 1 to 5,000 copies every invoice in a few minutes. With the owner
       check in InvoiceController@show, the 8 gives a 404.
```

Never invent what the code does not show. Where a step of the story is a guess, say so.
