# forge-test reference: the walk, the edge cases, the budget and the screenshots

Detail for `../forge-test/SKILL.md`. The walk and the edge cases are active tests: only the user's
own app, after `../forge-secure/scope.py` exits 0 for the base URL.

## The edge list

Go down this list for every flow in Step 1 and keep the cases that apply:

- empty input; very long input (a 60 character name, a 300 character text); emoji and accents;
  wrong input for the field (letters in a number, "abc" as an email);
- text that looks like HTML or SQL: it comes back as plain text and never runs;
- double click on submit (one record); two tabs at once;
- back button mid-flow; refresh mid-flow; slow network; offline; expired session;
- a second user's data (must be invisible: 403 or 404; no accounts: a second browser sees none);
- time zones and daylight saving; mobile width (390px); keyboard only; screen reader labels.

`../forge-test/edge.example.spec.ts` has a helper for each of the form cases and one worked form.
Copy it to `e2e/edge.spec.ts`, change `FORM`, and add one `describe` per form. A case that fails
leaves `forge-work/test/evidence/<case>.png`: name it on the bug's `evidence:` line.

| helper | what it does |
| --- | --- |
| `withEvidence(page, caseId, steps)` | runs the case; on failure saves the screenshot, then fails |
| `expectRejected(page, field)` | the field is marked invalid or an alert with text shows |
| `expectShownAsText(page, text)` | the text shows letter for letter, made no element, ran nothing |
| `doubleClick(page, button)` | a real double click on the same spot |
| `slowNetwork(page, ms)` | every request waits first; returns a function that undoes it |
| `expireSession(page)` | clears the cookies, as after a time-out |
| `watchForCrashes(page)` | collects 5xx answers and uncaught script errors |
| `LONG(300)`, `ACCENTS`, `HTML_TEXT`, `SQL_TEXT` | the values to type |

## Severity for a bug

| severity | for a bug (rules.md section 8) |
| --- | --- |
| critical | data loss, another user's data visible, a security hole, money wrong, a legal problem (a tracker that loads before consent) |
| high | a core flow or feature broken, no workaround |
| medium | broken with a workaround, or visibly wrong |
| low | cosmetic |

## PWA and offline

- `PWA: yes`: install, the offline page styled offline (its `/offline.css` comes from the worker's
  cache), and no signed-in page from the cache after logging out.
- When plan.md says a static app works offline (profiles.md, "Working offline"), its pages open
  offline after one online visit.

Both have a test in `../forge-test/e2e.example.spec.ts`.

## Seed data

Improve mode without a seeder: write one in `forge-work/` (out of git), or after the user's go
commit one as `test: add a seed command`, with fake `@example.test` users sharing `SEED_PASSWORD`,
a record per edge case (a draft, a past item, a nearly full one), on a database that may be emptied
(unsure: ask). No accounts, data in the browser: no seeder or `E2E_PASSWORD`, each test seeds its
own data (see the last group of `../forge-test/e2e.example.spec.ts`).

Seed and unit tests run on the host and reach the database on the override's port ("Where things
run" in `../forge-build/SKILL.md`): `127.0.0.1:3307` (MariaDB) or `127.0.0.1:5433` (PostgreSQL).
next: the unit tests use `TEST_DATABASE_URL=postgres://app:<DB_PASSWORD>@127.0.0.1:5433/app_test`,
made once by `docker compose exec db createdb -U app app_test`; the tests migrate it and refuse a
name without `_test`.

Improve mode, after the fix loop: update improve.md: "Tests after", and per fixed bug a line under
"Found on the way": `B001 fixed in d8a76ff, see bugs.md`.

## Rate limits

The app's rate limits count every spec and every page of the walk, all from one address. Never
loosen them for tests. Clear the counters between runs: laravel `docker compose exec app php
artisan cache:clear`, django its limiter's store (django-axes: `manage.py axes_reset`), next
`docker compose restart app` (Better Auth counts in memory by default). The walk signs nobody in:
it reuses the cookies the setup project saved.

## routes.json

`forge-work/test/routes.json` is the list of pages the walk opens. Write it yourself, without
asking: one entry per screen of recon.md or plan.md (the same names, `S03-dashboard`); improve
mode: one per route in the app's router. Fill in the ids of seed records (`/items/1`).

```json
[
  { "name": "S01-home", "path": "/", "as": null },
  { "name": "S03-dashboard", "path": "/dashboard", "as": "alice" }
]
```

- `name`: letters, digits, `-` and `_`; each name once. It is part of the screenshot's name.
- `path`: starts with one `/`.
- `as`: `null` for a visitor, or a seed user whose cookies the setup project saved in
  `e2e/.auth/<as>.json`. Walk a page as the user who may see it; a page only an admin may open
  gets `"as": "admin"` and a third saved sign-in.
- Not a route: a dialog, a tab or a step with no URL of its own (a flow spec covers it), and pages
  on other hosts (Stripe Checkout).

## What the walk records

`e2e/walk.spec.ts` (from `../forge-test/walk.example.spec.ts`) opens each route at 390, 768 and
1440 px wide, in the light and the dark colour scheme, each in a fresh browser context (an empty
cache). It fails only when a page cannot be loaded or routes.json cannot be read. It writes
`forge-work/test/walk.json` after every page:

```json
{ "version": 1, "base_url": "http://localhost:8080", "round": "r1", "written": "2026-01-01T10:00:00Z",
  "widths": [390, 768, 1440], "schemes": ["light", "dark"],
  "routes": [{ "name": "S01-home", "path": "/", "as": null }],
  "results": [{ "route": "S01-home", "path": "/", "as": null, "width": 390, "scheme": "light" }] }
```

Each result also has:

| field | what it holds |
| --- | --- |
| `loaded`, `error`, `skipped` | whether the page opened; why not; why it was skipped (no saved sign-in) |
| `incomplete` | the checks that could not run on this page (`axe: ...`, `layout: ...`) |
| `status`, `redirected_to` | the page's HTTP status; the path it landed on when that is another one |
| `screenshot` | `forge-work/test/shots/<round>/<name>-<width>-<scheme>.png`, the full page |
| `console_errors`, `page_errors` | console lines of the type error; uncaught script errors |
| `failed_requests` | requests with no answer: `url`, `method`, `type`, `same_origin`, `error` |
| `bad_responses` | answers of 400 and up (not the page itself): the same fields, `status`, `own_asset` |
| `broken_links`, `links_checked` | same-origin links that answer 404, 410 or 5xx: `url`, `status`, `text` |
| `axe` | WCAG 2.0, 2.1 and 2.2 A and AA violations: `id`, `impact`, `help`, `help_url`, `nodes`, `targets` |
| `overflow_px` | how many pixels the page is wider than the screen (0 is right) |
| `clipped` | elements whose own text is cut off with no ellipsis: `element`, `direction` |
| `overlaps` | a control whose centre lies under another control: `element`, `covered_by` |
| `small_targets` | controls under 24 by 24 px (links in a sentence and labelled boxes do not count) |
| `perf` | `lcp_ms`, `cls`, `ttfb_ms`, `load_ms`, `requests`, `transfer_bytes` |

Every link is asked for once per run with a GET, as the route's user. Links that could change
something (their address holds log out, delete, remove, cancel, export, download ...) are never
followed. Query strings are cut from every address written down, because they can hold a token.
At most 25 entries of one kind per page. CLS is the sum of all layout shifts while loading.

## What walkcheck.py makes of it

`python3 ../forge-test/walkcheck.py forge-work/test/walk.json` groups one problem seen at several
widths or schemes into one finding (a broken link: one for all routes) and gives it a severity:

| severity | findings |
| --- | --- |
| high | the page answers 4xx or 5xx; an uncaught script error; a 5xx answer or link; an axe violation with the impact critical; a speed or size value over twice its budget |
| medium | a console error; a failed request or a 4xx from the app itself; a 404 link; an axe violation with the impact serious; sideways scrolling; cut-off text; a covered control; a redirect; a value over its budget |
| low | a failed request or 4xx from another host; other axe violations; tap targets under 24 px; too many requests |

It never says critical: whether a finding leaks data or loses it is for you to judge. Raise the
severity in bugs.md when it does, and say why. Never lower one to get through.

Exit 2 means the walk is incomplete: a page has no result, was skipped, did not load, or one of
its checks could not run. Fix the cause and walk again. A route that cannot be walked (no seed
password) comes out of routes.json and goes under "Not tested" in test-plan.md, after asking.

`--bugs` prints the findings at or above `--fail-on` as blocks for bugs.md. `--known
forge-work/bugs.md` leaves out the ones whose title is in bugs.md already and numbers on from its
last bug; `--build` fills in the commit. Paste the blocks above `## To check`, as UTF-8.

## The budget

Per page, on a first load (an empty cache), on the local stack:

| key | limit | what it is |
| --- | --- | --- |
| `lcp_ms` | 2500 | Largest Contentful Paint: when the biggest thing on the screen was drawn |
| `cls` | 0.1 | Cumulative Layout Shift: how much the page jumped while loading |
| `ttfb_ms` | 800 | time to first byte: how long the server took to start answering |
| `load_ms` | 4000 | until the load event: everything the page asked for is in |
| `transfer_bytes` | 1500000 | bytes sent over the network for the page (1.5 MB) |
| `requests` | 60 | requests the page made |

Over the limit is medium, over twice the limit high (`requests`: always low). A measurement the
browser did not give (`null`) is not judged. The local stack is faster than a real server, so a
page over budget here is over budget everywhere. To change a limit, write
`forge-work/test/budget.json` with only the keys that differ, such as `{"lcp_ms": 3000}`, and run
walkcheck.py with `--budget forge-work/test/budget.json`. A looser budget is the user's call: ask,
and write their words in test-plan.md under "Not tested".

## Rounds of screenshots

`FORGE_ROUND` names the folder of a walk's screenshots: `r1` for the first walk (the baseline),
`r2` after the first round of fixes, and so on. walk.json is always the last walk.

`python3 ../forge-test/shotcheck.py forge-work/test/shots/r1 forge-work/test/shots/r2` compares
the shots with the same name through `../forge-diff/imgdiff.py`. A pair under `--min` (default 90)
is CHANGED, with where on the screen; a shot only one round has is MISSING or NEW. Exit 0: nothing
changed; 1: something did; 2: could not compare (a folder is missing: the first round has nothing
to compare with). imgdiff looks at layout, not colour: a colour-only change is not seen here, but
axe's contrast check in the walk sees the ones that matter.

After the first walk, open the phone (390) and the dark shots yourself: no script sees a page that
is merely ugly, or dark text on a dark background that axe could not measure.

A change is not always a bug. Open both PNGs of each changed shot: the fix itself (the button that
was cut off now fits) gets a line in test-plan.md; anything the fix was not meant to touch is a
new bug, with both files on its `evidence:` line. `forge-work/` stays out of git and out of the
image, so the shots do too.
