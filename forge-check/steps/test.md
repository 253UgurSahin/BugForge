# forge-check: test

A part of `/forge-check`. The ground rules, the levels and "show the result" live in its
`SKILL.md` and in `../forge/rules.md` (section 9: show the result; section 10: levels; the tables
are in `../forge/levels.md`): read them first.

Reads the flows in `forge-work/recon.md` (idea mode: plan.md; improve mode: the app and improve.md).
Writes `forge-work/test-plan.md` and `bugs.md`, specs in `e2e/`, unit tests next to the code, and
the walk's record and screenshots in `forge-work/test/`. How deep it goes is the test level. Detail
is in `../forge-check/walk.md`.

## Test your own app, nothing else

- Testing is active: only the user's own app, the local compose stack or a host scope.py allows.
  Run `python3 ../forge-check/scope.py <base url>` before the first e2e run; any exit but 0: stop
  and ask. Never load test, fuzz or script anyone else's site (the original by hand is fine).
- Test data is fake: seed users such as `alice@example.test`, Stripe test mode, email into Mailpit,
  passwords from the environment. Never the user's real accounts, real cards or live keys.

## On your own

Without asking, up to the checkpoint in Next: write the plan and routes.json, set up `e2e/`, start
and seed the stack, run every test the level asks for, file each bug you reproduced, fix it (at
most 3 tries per bug), test again and show the fixes. Stop and ask only for: the level when none
is on record; a `[wontfix]`, a looser budget or a route left out of the walk; a fix bigger than it
looked or a bug still open after 3 tries; a missing seed password or a database that may not be
emptied; anything scope.py does not allow.

## The level

1. `python3 ../forge/level.py get test`. It prints the number and the name: test at that level.
2. A level in the user's request ("a quick test", "snel", "grondig", "level 4") is recorded at
   once: `python3 ../forge/level.py set test 4 --said '<their words>'`.
3. Exit 1 and no level in the request: ask the ONE question of `../forge/rules.md` section 10,
   "How far should I go with testing?" (Dutch: "Hoe ver moet ik gaan met testen?"), with the lines
   that `python3 ../forge/level.py show test` prints (in Dutch: `show test --nl`). Testing has no
   examples, so no gallery line. Record the answer with `set`, in the user's words. This question
   is asked in auto mode too.
4. Then do exactly what that level asks: every row up to it, nothing of the rows above it. What a
   higher level would add goes under "Not tested" in test-plan.md as `above level 2: ...`.

What each level adds (each level includes everything of the levels below it):

| level | name | Dutch | what is tested | steps | the gate asks for |
| --- | --- | --- | --- | --- | --- |
| 1 | Quick | Snel | the app starts, the main flow works once, no error in the browser console; minutes | 1, 2 (no unit tests), 3 (the smoke spec), 5, 6, 7 | nothing more |
| 2 | Basic | Basis | + one test per flow of the way it should go, unit tests for the logic that matters | + unit tests, a spec per flow, 4 | nothing more |
| 3 | Standard | Standaard | + edge cases and cases that must fail, the walk (every page at 3 widths, in light and dark: errors, links, accessibility, layout, speed), the check that a second user cannot reach the first one's data | + the walk | `forge-work/test/walk.json` |
| 4 | Thorough | Grondig | + the edge helpers on every form, the speed budget enforced, screenshots compared between rounds, offline and PWA, a pass with the keyboard only | + edge.spec.ts, round r2, shotcheck.py | `e2e/**/edge*.spec.*`, `forge-work/test/shots/r1/*.png` and `r2/*.png` |
| 5 | Exhaustive | Uitputtend | + every route in every state, hostile and oversized input on every field (the user's own app only), two tabs at once, time zones and summer time, a matrix of slow networks, each spec run three times to catch a test that fails only now and then | + "Level 5" in walk.md | nothing more |

## Step 1: the plan

Copy `../forge-check/test-plan.md` to `forge-work/test-plan.md` and fill in its `Level:` line with
the level on record. Improve mode has no recon.md: list the app's main flows yourself (F01, F02...)
and add a case for every fix in improve.md. Number every case (F01-H1 happy, F01-E3 edge, F01-N2
negative) and mark it `e2e`, `unit` or `manual`. What goes in, per level:

- **Level 1**: `F00-H1` the app starts (the health URL answers, the home page opens with no console
  error) and `F01-H1` the main flow once, with what the user should see at the end. That is all.
- **Level 2**: the **happy path** of every flow: the steps, and what the user should see at the end;
  and the `unit` cases for the logic that matters: money in cents, dates, rules, permissions.
- **Level 3**: + **edge cases** that apply: go down "The edge list" in walk.md for every flow.
  **Negative cases**: wrong password, too many login attempts, card `4000 0000 0000 0002` declined,
  **Fail** on the iDEAL test page, a webhook event sent twice, permission denied, a deleted record.
  A second user opens the first user's data. And `forge-work/test/routes.json`: every screen with a
  URL of its own and who opens it (walk.md).
- **Level 4**: + every form gets the cases of the edge helpers (walk.md); `PWA: yes`, or a static app
  that works offline: the cases under "PWA and offline" in walk.md; one keyboard-only case per flow.
- **Level 5**: + the cases of "Level 5" in walk.md: each route in each of its states, hostile and
  oversized input on every field, two tabs, time zones and summer time, the slow-network matrix.

## Step 2: the stack, seed data and unit tests

First, what the user looks at (`../forge/rules.md` section 9): find out what serves their local
address (the compose stack, a dev server that reloads by itself, or a built app), from which folder
and branch (`git branch --show-current`, `git worktree list`), and whether a service worker sits in
front. Cannot tell: ask "How do you open the app, and at which address?" Write it on the `Served:`
line of test-plan.md.

`docker compose up -d --build --wait`, then open the health URL from `../forge-plan/profiles.md` and
write the base URL (normally `http://localhost:8080`) and the commit at the top of test-plan.md.
Improve mode without a compose file: start the app the way its README says. The images have no dev
packages, so seed and unit tests run on the host (`composer install`, a venv with the dev
requirements, `npm ci`), on the override's database port ("Seed data" in walk.md).

Seed and unit tests: laravel `php artisan db:seed`, `php artisan test`; django `python manage.py
seed`, `pytest` (or `manage.py test`); next `npm run seed`, `npx vitest run`; static `npx vitest
run`. The seeder comes from `/forge-build` (see build-log.md or the README); its users' password,
`SEED_PASSWORD`, is Step 3's `E2E_PASSWORD`. No seeder (improve mode) or no accounts: "Seed data"
in walk.md. Level 1 seeds only what the main flow needs and runs no unit tests. Level 2 and up: run
the app's unit tests and add one for each case marked `unit`.

## Step 3: end to end with Playwright

Improve mode, and the app already has Playwright (a `playwright.config.*`): add the specs to its
setup and use its command. Otherwise the specs go in `e2e/`, set up as the top of
`../forge-check/e2e.example.spec.ts` says: its own package.json, ignore lines, a config whose setup
project signs the seed users in once, and Playwright's own image when the browser download fails.
Start from that example. It shows what every spec needs: the base URL from `FORGE_BASE_URL`, roles
and labels as selectors (never CSS classes), a failure on any console error, 5xx response or broken
asset, and an axe scan (WCAG 2.2 AA) on each screen. Its second-user check and double submit are
level 3 cases: leave them out below that.

- **Level 1, the smoke spec**: one file, `e2e/smoke.spec.ts`: the example's first test (the home
  page loads without errors) and the main flow once. Run it; it should take minutes, not an hour.
- **Level 2 and up**: one spec per flow (`e2e/f01-sign-in.spec.ts`, ...) with its happy path. Level
  3 adds the edge, negative and second-user cases of the plan to those specs.
- **Level 3 and up, the walk**: copy `../forge-check/walk.example.spec.ts` to `e2e/walk.spec.ts`;
  after the flow specs run `FORGE_ROUND=r1 npx playwright test walk`. It opens every route of
  routes.json at 390, 768 and 1440 px, light and dark, writes what it saw to
  `forge-work/test/walk.json` and a screenshot per page to `forge-work/test/shots/r1/` (the
  baseline), and fails only when a page cannot load. Then `python3 ../forge-check/walkcheck.py
  forge-work/test/walk.json` judges it: errors, failed requests, broken links, WCAG, layout faults,
  and speed and size against the budget (LCP 2500 ms, CLS 0.1, TTFB 800 ms, 1.5 MB). Exit 2: the
  walk is incomplete, fix that.
- **Level 4 and up, the edge cases**: copy `../forge-check/edge.example.spec.ts` to
  `e2e/edge.spec.ts`, one group per form, built from its helpers. A case that fails leaves
  `forge-work/test/evidence/<case>.png`. The PWA and offline tests and the keyboard pass are in
  walk.md; so is how the speed budget is enforced.
- **Level 5**: the specs of "Level 5" in walk.md, and every spec run three times:
  `npx playwright test --repeat-each=3`.

The app's rate limits count every spec, all from one address; never loosen them for tests. Use new
emails and names in every run (`Date.now()`); clear the counters between runs ("Rate limits" in
walk.md). Commit the new tests before any fix: `python3 ../forge/gitguard.py` and `python3
../forge-check/secretscan.py .` must exit 0, then one commit `test: add end-to-end and unit
tests` with the specs, their config and lockfile, the ignore lines and the unit tests.

## Step 4: the manual pass

Level 2 and up. What no spec can reach gets a manual pass: with a browser tool when there is one
(screenshot each step), otherwise as a checklist for the user. Wait for their answers.

- Level 2: the happy path parts: the email arrives in Mailpit, sign-in with a real OAuth provider,
  Stripe Checkout and the iDEAL test page paid.
- Level 3: + the negative ones (a declined card, **Fail** on the iDEAL page) and visual glitches.
- Level 4: + the keyboard-only pass where no spec does it, and the screen reader labels.

Level 1 has no manual pass: list these under "Not tested".

## Step 5: report bugs

Every bug gets a heading in `forge-work/bugs.md` in exactly the form below. `../forge-check/bugs.py`
reads it and is strict: the file starts with `# Bugs`, the only other `##` heading is `## To check`,
and `[high]` or `[open]` go in bug headings only. UTF-8, also with no bugs (a line "No bugs found.").
```markdown
# Bugs
## B001 [high] [open] Booking fails when the guest's name has an accent
case: F01-E4   screen: S03   build: 3f2a1c9   browser: Chromium, 390px wide
steps: open /u/demo/30min, pick 10:00, type the name "Zoë", confirm
expected: the confirmation screen
actual: a 500 error, nothing saved
evidence: e2e/f01-book.spec.ts "F01-E4", forge-work/test/evidence/F01-E4.png
fixed in: -
```
The walk's findings come in this form: `python3 ../forge-check/walkcheck.py forge-work/test/walk.json
--bugs --fail-on medium --known forge-work/bugs.md --build 3f2a1c9` prints a block per finding
that bugs.md does not have yet, numbered on from its last bug: paste them in. Severity: critical,
high, medium or low ("Severity for a bug" in walk.md). Status: `open`, `fixed` or `wontfix`. Only
report what you reproduced; "might be an issue" goes under `## To check`. Never paste a secret or
a real person's data into a bug. A must-have that is missing or half built is no bug: it goes to
`/forge-build`, then back here (say so at the checkpoint).

## Step 6: the fix loop

1. `python3 ../forge/gitguard.py` must exit 0: fixes are commits on the work branch, never on main.
   Say in two lines which bugs you will fix, in which order. Before the first fix that changes what
   a user sees, take the "before" shots of those screens from the `Served:` address (Step 7).
2. Critical and high first. Per bug: write a test that fails (a walk finding: the walk is the
   test), fix the smallest thing that makes it pass, keep the test. Touch nothing unrelated.
3. Rebuild the stack (Step 2), run the whole suite, then `python3 ../forge-check/secretscan.py .`
   (must exit 0), then one commit: `fix(B001): booking accepts names with accents`.
4. Change the heading to `[fixed]` and fill in `fixed in:` with the commit. Tell the user in one
   line: the bug, and what is different now.
5. `python3 ../forge-check/bugs.py forge-work/bugs.md`. Exit 1: an open critical or high bug is
   left, back to 2. Exit 2: a line is not in the right form (the output names it). Repeat until it
   exits 0, then fix the medium bugs the same way, and low ones when the fix is small.
6. Level 3 and up: after each round of fixes, walk again as the next round (`FORGE_ROUND=r2`) and
   run walkcheck.py (new findings: Step 5). Level 4 and up: walk round r2 also when nothing was
   fixed, then `python3 ../forge-check/shotcheck.py forge-work/test/shots/r1
   forge-work/test/shots/r2`. A CHANGED shot is the fix or a new bug. Done: walkcheck.py exits 0
   (level 4: no speed or size finding left either, "The budget" in walk.md).
7. Improve mode: a bug that is an audit or inspect finding the user did not pick stays open with
   `not picked: A016` under it; ask before fixing it. After the loop, update improve.md (walk.md).

Never lower a severity to get through. A bug is `[wontfix]` only when the user says so for that
bug: write their words under it. A fix that turns out bigger than it looked: stop and ask. A bug
that diff, brand, secure or pack sent here goes through this loop too, then back to that phase.

## Step 7: show what was fixed

A fix the user cannot see has not happened (`../forge/rules.md` section 9). Do this for every fix
that changes what a user sees; a fix nobody sees (an error now caught in the server) has its test
as proof, and the hand-over names it in one line.

1. **Before**, in Step 6.1: copy `../forge-design/shots.example.mjs` to `forge-work/design/shots.mjs`
   when it is not there yet, then `node forge-work/design/shots.mjs <Served address>
   forge-work/test/fixes/before --viewport-only /path ...` with the paths of the screens the fixes
   touch (`--state e2e/.auth/alice.json` for signed-in ones).
2. **Make it show.** The compose stack: `docker compose up -d --build --wait`. A dev server in the
   folder you worked in: it shows the work already. A built app: rebuild and restart it. Another
   folder, branch or worktree: start the app from yours on a free port and give that address, or
   give the one command that switches their folder to the work branch. A service worker that holds
   old files: bump its cache. Then load the address yourself.
3. **After, and proof.** The same command into `forge-work/test/fixes/after`, then `python3
   ../forge-design/changed.py forge-work/test/fixes/before forge-work/test/fixes/after`. Each fixed
   screen must say VISIBLE CHANGE. NO VISIBLE CHANGE: find which reason of section 9 it is (another
   branch, no rebuild, a cache, the fix sits on a path the shots did not take), fix that, shoot again.
4. **Hand it over**, in plain words: the branch the fixes are on; the address that shows them now;
   per fix, where to click to see it; the paths of the before and after images; and how to go back
   (`git switch <their branch>`). Merging and deploying stay the user's step.

## Output

- `forge-work/test-plan.md` with every result and the totals, its `Level:` line and `Served:` line;
  `forge-work/bugs.md`, bugs.py exits 0.
- The specs in `e2e/`, new unit tests, one commit for the new tests and one per fixed bug.
- Level 3 and up, `forge-work/test/`: routes.json, walk.json (walkcheck.py exits 0), the
  screenshots per round; level 4 and up, `e2e/edge.spec.ts` and the rounds r1 and r2.
- `forge-work/test/fixes/before` and `after` for the fixes a user can see.
- `python3 ../forge/level.py check test --report forge-work/test-plan.md` exits 0. Exit 1 names
  what the level still asks for: do that work. Never change the level yourself.

## Next

Checkpoint, at most 5 plain lines: the level; cases run, passed, failed and skipped; bugs per
severity and how many are fixed, and where to look to see the fixes (Step 7.4); the walk at level 3
and up (pages, findings left, the slowest page, shots that changed); what is left open, each
critical or high bug the user accepted as wontfix (bugs.py lists them), and what was not tested.
Wait for the user's go. Then `/forge-check diff` (clone mode), `/forge-design brand` (idea mode)
or `/forge-check secure` (improve mode), or back to `/forge` when it runs the phases.
