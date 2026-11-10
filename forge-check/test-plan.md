# Test plan: {{app name}}

Build: {{commit}}  Date: {{YYYY-MM-DD}}  Profile: {{laravel | django | next | static}}  PWA: {{yes | no}}
Runs against: {{http://localhost:8080}}, the local compose stack with seed data. scope.py: exit {{0}}
Served: {{what serves the user's own address: the compose stack on http://localhost:8080, from this folder, branch forge/work; no service worker}}

Level: {{3 (Standard)}}

<!-- The Level line is the test level on record (`python3 ../forge/level.py get test`), on a line of
its own. `python3 ../forge/level.py check test --report forge-work/test-plan.md` must exit 0. -->

## How to run

- Unit and integration tests, on the host (Step 2 of the test part; level 2 and up): `{{php artisan test | pytest | npx vitest run}}`
- End to end, on the stack as it is now (after any change to the app, first
  `docker compose up -d --build --wait`), {{on the host | in Playwright's image (../forge-check/e2e.example.spec.ts)}}:
  `cd e2e && FORGE_BASE_URL=http://localhost:8080 E2E_PASSWORD=<the seed password> npx playwright test`.
  Without `E2E_PASSWORD` every signed-in test is skipped (an app without accounts has none):
  Playwright still exits 0, so read the skipped count and write each skip in the result column.
  Between two runs, reset the app's rate limits: `{{docker compose exec app php artisan cache:clear | docker compose restart app}}`.
- The walk, level 3 and up, after the flow specs (every route of `forge-work/test/routes.json` at 390, 768 and 1440 px,
  light and dark; see `../forge-check/walk.md`): `cd e2e && FORGE_BASE_URL=http://localhost:8080
  FORGE_ROUND={{r1}} npx playwright test walk`, then, from the project root,
  `python3 ../forge-check/walkcheck.py forge-work/test/walk.json`.
- Level 5: every spec three times, `npx playwright test --repeat-each=3`.

## Cases

| case | flow | type | steps | expected | auto | result |
| --- | --- | --- | --- | --- | --- | --- |
| F01-H1 | guest books a meeting | happy | open /u/demo/30min, pick tomorrow 10:00, fill in the form, confirm | confirmation screen, booking on the host's dashboard, email to both in Mailpit | e2e | |
| F01-E1 | | edge: slot taken while the guest fills in the form | | clear message, pick another slot, no double booking | e2e | |
| F01-E2 | | edge: guest in another time zone | | times shown in the guest's zone, stored in UTC | e2e | |
| F01-E3 | | edge: a second user opens the first user's booking | | 403 or 404, never the data | e2e | |
| F01-E4 | | edge: double click on Confirm | | one booking, no error message | e2e | |
| F01-N1 | | negative: card declined (4000 0000 0000 0002) | | error shown, no booking created | manual | |
| F01-N2 | | negative: iDEAL test payment, Fail | | order stays unpaid, plain message, no email | manual | |

auto: `e2e` (a Playwright spec), `unit` (the profile's test runner) or `manual` (by hand or with a
browser tool). result: `pass`, `fail B003` (the bug in bugs.md) or `skipped: why`.

## Not tested

- {{what and why, for example "Google sign-in: needs the user's own test account" or "above level 2: the walk, edge cases, the second-user check"}}

## Result

Cases: {{n}} run, {{n}} passed, {{n}} failed, {{n}} skipped.
Bugs (the counts `../forge-check/bugs.py` prints): {{n}} critical, {{n}} high, {{n}} medium, {{n}} low;
{{n}} open, {{n}} fixed, {{n}} wontfix.
`python3 ../forge-check/bugs.py forge-work/bugs.md`: exit {{0}}.
The walk (level 3 and up; below it: none), round {{r1}}: {{n}} routes, {{n}} pages; findings left: {{n}} high, {{n}} medium, {{n}} low.
Slowest page: {{S03-dashboard at 390 px, LCP 1800 ms}}; budget: {{the default | forge-work/test/budget.json}}.
Screenshots (level 4 and up): {{shotcheck.py r1 r2: 2 changed, both by the fix for B004 | below level 4: not compared}}.
`python3 ../forge-check/walkcheck.py forge-work/test/walk.json`: exit {{0}}.
Fixes you can see: {{2, before and after in forge-work/test/fixes/; changed.py: VISIBLE CHANGE | none: every fix is in the server}}.
