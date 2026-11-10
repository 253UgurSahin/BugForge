# Framework checks

forge-secure's Step 8 walks these for each stack the project uses, by reading the code and the
settings. Each failed check is a finding in the plain format. Default severity in brackets.

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

**Containers**
- Runs as a non-root user: a `USER` line in the Dockerfile (medium). Base image pinned, not `latest` (low).
- No secrets baked into the image: no `.env` or other file of secrets (`.env.local`, `auth.json`, `.npmrc`) copied in, no secret in `ENV` or `ARG` (critical).
- `.dockerignore` excludes `.env`, `.git`, `forge-work/` and the other files of secrets in the project (high).

**Stripe**
- Test mode only: `sk_test_` and `pk_test_` keys. Live keys are the user's job (critical).
- Webhooks verify the `Stripe-Signature` header with the webhook secret (high).
- Card data never touches the server or database: use Stripe Checkout or Elements (critical).
- Prices and amounts are computed on the server, never taken from the browser (critical).

