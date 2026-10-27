# Test plan: {{app name}}

Build: {{commit}}  Date: {{YYYY-MM-DD}}  Profile: {{laravel | django | next | static}}  PWA: {{yes | no}}
Runs against: {{http://localhost:8080}}, the local compose stack with seed data. scope.py: exit {{0}}

## How to run

- Unit and integration tests, on the host (forge-test Step 2): `{{php artisan test | pytest | npx vitest run}}`
- End to end: `cd e2e && FORGE_BASE_URL=http://localhost:8080 E2E_PASSWORD=<the seed password> npx playwright test`.
  Without `E2E_PASSWORD` every signed-in test is skipped: Playwright still exits 0, so read the
  skipped count and write each skip in the result column.

## Cases

| case | flow | type | steps | expected | auto | result |
| --- | --- | --- | --- | --- | --- | --- |
| F01-H1 | guest books a meeting | happy | open /u/demo/30min, pick tomorrow 10:00, fill in the form, confirm | confirmation screen, booking on the host's dashboard, email to both in Mailpit | e2e | |
| F01-E1 | | edge: slot taken while the guest fills in the form | | clear message, pick another slot, no double booking | e2e | |
| F01-E2 | | edge: guest in another time zone | | times shown in the guest's zone, stored in UTC | e2e | |
| F01-E3 | | edge: a second user opens the first user's booking | | 403 or 404, never the data | e2e | |
| F01-N1 | | negative: card declined (4000 0000 0000 0002) | | error shown, no booking created | manual | |
| F01-N2 | | negative: iDEAL test payment, Fail | | order stays unpaid, plain message, no email | manual | |

auto: `e2e` (a Playwright spec), `unit` (the profile's test runner) or `manual` (by hand or with a
browser tool). result: `pass`, `fail B003` (the bug in bugs.md) or `skipped: why`.

## Not tested

- {{what, and why: for example "sign in with Google: needs the user's own test account"}}

## Result

Cases: {{n}} run, {{n}} passed, {{n}} failed, {{n}} skipped.
Bugs (the counts `../forge-test/bugs.py` prints): {{n}} critical, {{n}} high, {{n}} medium, {{n}} low;
{{n}} open, {{n}} fixed, {{n}} wontfix.
`python3 ../forge-test/bugs.py forge-work/bugs.md`: exit {{0}}.
