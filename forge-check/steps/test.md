# forge-check: test

A part of `/forge-check`: the ground rules, the levels and "show the result" are in its `SKILL.md`
and `../forge/rules.md` (sections 9 and 10). Read rules.md once per session; `../forge/levels.md`
only when what level.py prints is unclear. Detail is in `../forge-check/walk.md`.

Reads the flows in `forge-work/recon.md` (idea mode: plan.md; improve mode: the app and improve.md).
Writes `forge-work/test-plan.md` and `bugs.md`, specs in `e2e/`, unit tests next to the code, the
walk's record and screenshots in `forge-work/test/`. Run on its own in the user's app (no
`forge-work/state.json`, as with "test mijn app" in their folder): treat it as improve mode without
improve.md. List the flows yourself (Step 1), use the app as it already runs ("An app that already
runs" in walk.md), and skip the improve.md steps.

## Test your own app, nothing else

- Testing is active: only the user's own app, the local compose stack or a host scope.py allows.
  Run `python3 ../forge-check/scope.py <base url>` before the first e2e run; any exit but 0: stop
  and ask. Never load test, fuzz or script anyone else's site (the original by hand is fine).
- Test data is fake: seed users such as `alice@example.test` or the app's demo accounts, passwords
  from the environment, Stripe test mode and Mailpit where the app has them. Never the user's real
  accounts, real cards or live keys.

## On your own

Without asking, up to the checkpoint in Next: write the plan and routes.json, set up `e2e/`, start
what does not run yet, run every test the level asks for, file each bug you reproduced, fix it (at
most 3 tries per bug), test again and show the fixes. Stop and ask only for: the level; a
`[wontfix]`, a looser budget or a route left out of the walk; a fix bigger than it looked or a bug
open after 3 tries; a missing seed or demo password; a seed command that empties a database, or
the app's own tests when `testdb.py` exits 1 (Step 2.6); what scope.py does not allow. Never wait
mid-run for more: what only the user can do goes into the checkpoint.

## The level

1. "Levels" in SKILL.md: `python3 ../forge/level.py get test`; a level in the request is recorded
   at once with `set test N --said '<their words>'`; none: the ONE question, "How far should I go
   with testing?" (Dutch: "Hoe ver moet ik gaan met testen?"), with the lines of `show test` (Dutch:
   `show test --nl`) and no gallery line. Asked in auto mode too.
2. **The floor.** Inside a `/forge` project (`forge-work/state.json` is there) testing never runs
   below level 2: level 1 is for a test on its own. `set` raises level 1 to 2 and prints a note:
   tell the user. `get` refuses level 1 on record there and prints the command that records it again.
3. Then do exactly what that level asks (the table in SKILL.md): every row up to it, nothing above
   it. What a higher level would add goes under "Not tested" in test-plan.md as `above level <N>:
   ...`, with the level on record as N. The steps per level, and what the gate asks for:

| level | steps (each level includes the ones below it) | the gate asks for |
| --- | --- | --- |
| 1 Quick | 0, 1, 2 (no unit tests), 3 (the smoke spec), 5, 6, 7 | nothing more |
| 2 Basic | + unit tests, a spec per flow, 4 | nothing more |
| 3 Standard | + edge and negative cases, the second user, the walk | `forge-work/test/walk.json` |
| 4 Thorough | + edge.spec.ts, PWA, keyboard, round r2, shotcheck.py | `**/edge.spec.*`, `forge-work/test/shots/r1/*.png` and `r2/*.png` |
| 5 Exhaustive | + "Level 5" in walk.md | nothing more |

## Step 0: say what comes

Once the level is on record, tell the user in 3 lines, in their language: the steps, about how
many pages the walk will open (level 3 and up: routes times 3 widths times light and dark), and
about how long it takes. In the same message, ask for what only the user has: a demo password the
app does not document, and a test account per other role (walk.md, "routes.json"), each put in the
git-ignored `.env` (Step 2.5), never in the chat. After each step, one line with what it found
(cases passed and failed, bugs filed). Never work in silence for long (rules.md section 9).

## Step 1: the plan

Copy `../forge-check/test-plan.md` to `forge-work/test-plan.md`, its `Level:` line the level on
record. Improve mode: list the app's main flows yourself (F01, F02...), a case for every fix in
improve.md. Number every case (F01-H1 happy, F01-E3 edge, F01-N2 negative), mark it `e2e`, `unit`
or `manual`. What goes in, per level:

- **Level 1**: `F00-H1` the app starts (the health URL of the profile in `../forge-plan/profiles.md`,
  or the home page when the app has none: write which; the home page opens with no console error)
  and `F01-H1` the main flow once, with what the user should see at the end. That is all.
- **Level 2**: the **happy path** of every flow: the steps, and what the user should see at the end;
  and the `unit` cases for the logic that matters: money in cents, dates, rules, permissions.
- **Level 3**: + **edge cases** that apply: go down "The edge list" in walk.md for every flow.
  **Negative cases**: wrong password, too many login attempts (on a throwaway account the spec signs
  up, never a seed or demo account: "Rate limits" in walk.md), permission denied, a deleted record;
  where the app has them, card `4000 0000 0000 0002` declined, **Fail** on the iDEAL test page, a
  webhook event sent twice. A second user opens the first user's data. And
  `forge-work/test/routes.json`: every screen with a URL of its own and who opens it (walk.md).
- **Level 4**: + the edge helpers' cases on every form, "PWA and offline" (`PWA: yes`, or a static
  app that works offline) and a keyboard-only case per flow (walk.md).
- **Level 5**: + the cases of "Level 5" in walk.md.

## Step 2: the branch, the app, test users and unit tests

1. **The branch.** Note the user's branch (`git branch --show-current`). Not a `forge/` branch:
   `git switch -c forge/test` in their folder (that name exists from an earlier run: `forge/test-2`,
   `-3` ...), so the server they run keeps showing the work (their uncommitted changes stay
   uncommitted). Commit only what you add or change, by name (`git add <paths>`), never `git add
   -A`; a file that holds their uncommitted changes: say so and ask.
2. **What serves the app** (rules.md section 9): compose, a dev server or a built app; from which
   folder and branch (`git worktree list`); a service worker? Cannot tell: ask "How do you open the
   app, and at which address?" Write it on the `Served:` line of test-plan.md, the commit at the top.
3. **Start nothing that runs already.** When the app answers on the user's address (for example
   `http://localhost:3000` from their `npm run dev`), use it as it is: never a second server next
   to it, never a restart of theirs. Only when nothing answers: `docker compose up -d --build --wait`
   with a compose file (normally `http://localhost:8080`), else the README's start command. Then
   open the health URL of the profile, or the home page when the app has none (write which).
4. **Dependencies.** Install only what is missing. Never `npm ci` (or anything that empties
   node_modules) in a folder whose dev server runs. A compose stack: "Seed data" in walk.md.
5. **Test users.** The app has demo accounts: use two of them with the same role (their emails in
   `e2e/helpers.ts`, their passwords as `E2E_PASSWORD` and `E2E_PASSWORD_2` in the git-ignored
   `.env` or, when the app documents them, `forge-work/test/e2e.env`: the e2e config reads both;
   another role: one account each, walk.md "routes.json"), and seed nothing unless the level needs a
   record they lack. Else the seeder or a new one ("Seed data" in walk.md). Ask before any seed
   command that empties a database.
6. **Unit tests**, level 2 and up: run the app's own (laravel `php artisan test`, django `pytest`,
   next and static `npx vitest run`, or package.json's `test` script); add one per `unit` case.
   Tests can empty the database they reach: first `python3 ../forge-check/testdb.py .`. Exit 0: a
   database of their own (or none), run them. Exit 1: ask the user as its line says (the database
   the tests can wipe, and how they get one of their own: set that up only with their go). No go:
   run only the test files that reach no database (Laravel: those on PHPUnit's own `TestCase`,
   often `tests/Unit`), each by its path; the rest go under "Not tested", with why.

## Step 3: end to end with Playwright

Improve mode, and the app already has Playwright (a `playwright.config.*`): add the specs to its
setup and use its command. Otherwise the specs go in `e2e/`, set up as the top of
`../forge-check/e2e.example.spec.ts` says, with the changes of "The e2e config" in walk.md (the
walk as a project of its own, so the suite never writes over walk.json). Start from that example:
the base URL from `FORGE_BASE_URL`, roles and labels as selectors (never CSS classes), a failure on
any console error, 5xx or broken asset. Its axe scan per screen (`expectAccessible`, WCAG 2.2 AA),
second-user check and double submit are level 3 cases: below level 3, leave them out.

Run from the project root, with the `Served:` address in full (the examples fall back to port
8080). The e2e config reads the passwords (Step 2.5): no command carries one. Every walk command,
r2 too, carries the theme choice of "Light and dark" in walk.md: `FORGE_INIT_SCRIPT=<file>` for an
app that keeps its own theme, `FORGE_SCHEMES=light` for an app with one, nothing otherwise:
- the suite: `cd e2e && FORGE_BASE_URL=<Served address> npx playwright test --project=chromium`
- the walk: `cd e2e && FORGE_BASE_URL=<Served address> [FORGE_INIT_SCRIPT=<file> | FORGE_SCHEMES=light] FORGE_ROUND=r1 npx playwright test --project=walk`

- **Level 1, the smoke spec**: one file, `e2e/smoke.spec.ts`: the example's first test without its
  `expectAccessible` line (the home page loads with no console error) and the main flow once. Run
  it; it should take minutes, not an hour.
- **Level 2 and up**: one spec per flow (`e2e/f01-sign-in.spec.ts`, ...), its happy path; level 3
  adds the plan's edge, negative and second-user cases.
- **Level 3 and up, the walk**: copy `../forge-check/walk.example.spec.ts` to `e2e/walk.spec.ts`
  and, after the flow specs, run the walk command (a dev server: "The budget" in walk.md first). It
  writes `forge-work/test/walk.json` and the baseline shots in `forge-work/test/shots/r1/`. `python3
  ../forge-check/walkcheck.py forge-work/test/walk.json` judges it: errors, links, WCAG, layout,
  speed and size. Exit 2: the walk is incomplete, fix that.
- **Level 4 and up, the edge cases**: `e2e/edge.spec.ts` from `../forge-check/edge.example.spec.ts`
  (or beside the app's own specs), one group per form ("The edge list" in walk.md); a failing case
  leaves `forge-work/test/evidence/<case>.png`. PWA, offline, keyboard and the budget: walk.md.
- **Level 5**: the specs of "Level 5" in walk.md, and the suite run with `--repeat-each=3`.

The app's rate limits count every spec, all from one address; never loosen them for tests. Use new
emails and names in every run (`Date.now()`); clear the counters between runs ("Rate limits" in
walk.md). Commit the new tests before any fix: `python3 ../forge/gitguard.py` and `python3
../forge-check/secretscan.py .` must exit 0, then `git add` by name the specs, their config and
lockfile, the ignore lines and the unit tests, and one commit `test: add end-to-end and unit tests`.

## Step 4: the manual pass

Level 2 and up (level 1: these go under "Not tested"). What no spec reaches, do yourself with
Playwright or a browser tool, a screenshot of each step in `forge-work/test/manual/`. What needs the
user (a real OAuth account, a real inbox) goes into the checkpoint as a short checklist. Never wait
mid-run. Only what the app has:

- Level 2: the happy path parts: the email arrives in Mailpit, sign-in with an OAuth provider,
  Stripe Checkout and the iDEAL test page paid.
- Level 3: + the negative ones (a declined card, **Fail** on the iDEAL page) and visual glitches.
- Level 4: + the keyboard-only pass where no spec does it, and the screen reader labels.

## Step 5: report bugs

Create `forge-work/bugs.md` before anything else: `# Bugs`, a line `No bugs found.` and `## To
check`. Paste each bug above `## To check` (the first one replaces `No bugs found.`), with a heading
in exactly this form. `../forge-check/bugs.py` is strict: the only other `##` heading is `## To
check`, and `[high]` or `[open]` go in bug headings only. UTF-8.
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
that bugs.md does not have yet, numbered on from its last bug: paste them in (level 4 and up, also
the low `requests` ones, as "The budget" in walk.md says). Severity: "Severity for a bug" in
walk.md. Status: `open`, `fixed` or `wontfix`. Only what you reproduced; "might be an issue" goes
under `## To check`. No secret or real person's data in a bug. A must-have missing or half built is
no bug: `/forge-build`, then back here (say so at the checkpoint).

## Step 6: the fix loop

1. `python3 ../forge/gitguard.py` must exit 0: fixes are commits on the work branch, never on main.
   Say in two lines which bugs you will fix, in which order.
2. Critical and high first. Per bug: a fix that changes what a user sees first gets the "before"
   shots of its screens (Step 7.1), right before this fix, so no suite run of an earlier fix falls
   between its before and after. Write a test that fails (a walk finding: the walk is the test),
   fix the smallest thing that makes it pass, keep the test. Touch nothing unrelated. A test that
   reaches the database (RefreshDatabase) runs only where Step 2.6 allowed it; else make it an e2e
   spec against the running app, or one that touches no database, and say which.
3. Make the app show the fix (Step 7.2) and take its after shots (Step 7.3), then run the suite
   (Step 3's suite command, never the walk), then `python3 ../forge-check/secretscan.py .` (must
   exit 0), then `git add` the changed files by name and one commit: `fix(B001): booking accepts
   names with accents`.
4. Change the heading to `[fixed]` and fill in `fixed in:` with the commit. Tell the user in one
   line: the bug, and what is different now.
5. `python3 ../forge-check/bugs.py forge-work/bugs.md`. Exit 1: an open critical or high bug is
   left, back to 2. Exit 2: a line is not in the right form (the output names it). Repeat until it
   exits 0, then fix the medium bugs the same way, and low ones when the fix is small.
6. Level 3 and up: after each round of fixes, walk again as the next round (`FORGE_ROUND=r2`; a
   production build in a copy: move it to the work branch and rebuild it first, "The budget" in
   walk.md) and run walkcheck.py (new findings: Step 5). Level 4 and up: walk round r2 also when
   nothing was fixed, then `python3 ../forge-check/shotcheck.py forge-work/test/shots/r1
   forge-work/test/shots/r2`. A CHANGED shot is the fix or a new bug. Done: walkcheck.py exits 0
   (a walk of a dev server: its speed and size findings aside, "The budget" in walk.md; level 4:
   no speed or size finding left either, not even a low `requests` one).
7. Improve mode: a bug that is an audit or inspect finding the user did not pick stays open with
   `not picked: A016` under it; ask before fixing it. After the loop, update improve.md (walk.md).

Never lower a severity to get through. A bug is `[wontfix]` only when the user says so for that
bug: write their words under it. A fix that turns out bigger than it looked: stop and ask. A bug
that diff, brand, secure or pack sent here goes through this loop too, then back to that phase.

## Step 7: show what was fixed

For every fix that changes what a user sees (rules.md section 9); a fix nobody sees (an error now
caught in the server) has its test as proof.

1. **Before**, at the start of that bug's Step 6.2, never all at the first fix. Level 3 and up, a
   fixed screen that is a route of a walk of the `Served:` address and shows nothing the suite adds
   to (no list, count or date of records): its walk shots are the pair (r1 before, the next round
   after). Otherwise copy `../forge-design/shots.example.mjs` to `forge-work/design/shots.mjs`,
   then `node forge-work/design/shots.mjs <Served address> forge-work/test/fixes/B001/before /path
   ...` (the bug's own folder; signed in: `--state e2e/.auth/alice.json` before those paths), the
   whole page; `--viewport-only` only for a fix in the first screen.
2. **Make it show** (section 9). A dev server in your folder shows it already (never restart one
   you did not start); the compose stack: `docker compose up -d --build --wait`; a built app:
   rebuild and restart it (one the user started: ask first); a service worker that holds old
   files: bump its cache. Then load it.
3. **After, and proof.** Walk shots: `python3 ../forge-design/changed.py
   forge-work/test/shots/r1/<shot>.png forge-work/test/shots/r2/<shot>.png`. shots.mjs: the same
   command into `forge-work/test/fixes/B001/after` once the fix shows, before the suite of Step 6.3
   adds records (renew the state file first: a sign-in page is never shot as the screen), then
   changed.py on the two folders. Each fixed screen must say VISIBLE CHANGE. A fix in one small spot
   (a label, a colour, one button) can stay under the 2 percent bar on a whole page: then run
   changed.py again with `--json`; its `box` must sit on the fixed element in the after shot. Write
   its `percent` and `box` on the `Fixes you can see:` line of test-plan.md. No pixel changed, or a
   box elsewhere: find the reason of section 9, fix that, shoot again. Never lower `--min`, and
   never make a fix bigger to pass.
4. **Hand it over**, in plain words: the branch the fixes are on; the address that shows them now;
   per fix, where to click to see it; the paths of the before and after images; and how to go back
   (`git switch <their branch>`). A fix nobody sees: one line. Merging and deploying are theirs.

## Output

- `forge-work/test-plan.md` with every result and the totals, its `Level:` line and `Served:` line;
  `forge-work/bugs.md`, bugs.py exits 0. The specs in `e2e/`, new unit tests, one commit for the new
  tests and one per fixed bug; the before and after images of the fixes a user can see.
- Level 3 and up, `forge-work/test/`: routes.json, walk.json (walkcheck.py exits 0), the
  screenshots per round; level 4 and up, the edge spec and the rounds r1 and r2.
- `python3 ../forge/level.py check test --report forge-work/test-plan.md` exits 0. Exit 1 names
  what the level still asks for: do that work. Never change the level yourself.

## Next

Checkpoint, at most 5 lines, in the user's language and plain words: the level; the cases run,
passed, failed and skipped; the bugs by how bad, how many fixed, where to see them (Step 7.4); level
3 and up, "every page checked on phone, tablet and desktop, light and dark (or the one theme the
app has): N pages, N problems left, slowest page X (Y seconds)"; what is left open (a bug the user chose to leave), what was not
tested, the checklist of Step 4. Name the report, `forge-work/test-plan.md`, and the folder with the
before and after pictures. Wait for the user's go. Then `/forge-check diff` (clone mode),
`/forge-design brand` (idea mode) or `/forge-check secure` (improve mode), or back to `/forge` when
it runs the phases. On its own: stop after the checkpoint and offer `/forge-check secure`.
