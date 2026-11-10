# Checks by reading the code

Step 8 of `/forge-check secure` (`../forge-check/steps/secure.md`) walks this file by reading the code
and the settings. What runs depends on the secure level on record (`python3 ../forge/level.py get
secure`):

| from level | what | where in this file |
| --- | --- | --- |
| 3 | the framework checks, for each stack the project uses | Laravel, Django, Next.js, Static site, Stripe |
| 4 | the container checks | Containers |
| 5 | the review: a threat model per entry point, the access matrix, abuse and rate-limit cases, the licence review, an attack story per finding | Level 5 |

Each failed check is a finding in the plain format. Default severity in brackets. Say in the report
which stacks you skipped and why, and leave out what is above the level on record.

## Framework checks (level 3)

**Laravel**
- `APP_DEBUG=false` in production and in `.env.example`; `php artisan about` shows it (high).
- `APP_KEY` is set in `.env`. Check that it is set, never print it (high).
- CSRF protection is on for web routes, with no broad exceptions (high).
- Models that take request data set `$fillable` or a non-empty `$guarded` (high).

**Django**
- `python manage.py check --deploy` with production settings: each warning (medium).
- `DEBUG = False` in production (high). `SECRET_KEY` read from the environment (high).
- `ALLOWED_HOSTS` lists the real hosts (medium).

**Next.js**
- No secret in any `NEXT_PUBLIC_` variable: those are sent to every browser (high).
- Auth is checked on the server inside each route handler and server action,
  not only in middleware. Middleware alone has been bypassed before (high).

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

## Level 5

The review an attacker would do, by reading the code. It writes two files next to the report,
`forge-work/security/threats.md` and `forge-work/security/access.md`; their findings go into
security.md like any other, with their own X numbers.

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
paths in `--urls`, its `--json` output saved as `forge-work/security/authz-<role>.json`. A role
with no seed account: "not checked: no account for this role", and ask the user for one.

### Abuse and rate limits

For each entry point, what someone would repeat to do harm: guess passwords, send reset emails,
make accounts, try coupon or invite codes, upload large or many files, run an expensive search,
count ids upwards to read records one by one, replay a webhook. Read for a limit: Laravel's
`throttle` middleware or `RateLimiter`, django-axes or django-ratelimit, the auth library's rate
limit in Next.js, express-rate-limit, a size cap, a lock-out, a webhook id that is used only once.
No limit on login or password reset is high; elsewhere medium.

Only on the user's own running app (scope.py exits 0) and only with a seed account, one short
burst may show the limit at work: at most 20 wrong passwords for `alice@example.test`, which should
end in a 429 or a lock-out. Never a load test, never a real person's account. Clear the counters
afterwards ("Rate limits" in `../forge-check/walk.md`).

### Licences

From `forge-work/sbom.json` and supply.py's licence notes, and the fonts, icons and images the app
ships: list each GPL, AGPL, SSPL, unknown or missing licence, what it asks of the user (AGPL: share
the source with everyone who uses a hosted app, not only with those who download it) and whether
that fits the app's own `LICENSE` and the way the user means to offer it. Medium when it clashes,
low when it is only unknown. Not legal advice: the choice is the user's.

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
