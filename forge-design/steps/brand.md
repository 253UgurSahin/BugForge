# The brand part of /forge-design

A part of `/forge-design`. The ground rules, the levels and "show the result" live in
`../forge-design/SKILL.md` and in `../forge/rules.md` (sections 9 and 10): read them first.

This part gives the app its own name, palette, logo brief and voice, and sweeps out the original's.
It ends when the user sees their app's new name and colours on their own screen, not when the files
are written. In `/forge` it runs after the tests (clone mode: after `/forge-check diff`), on the app
that `/forge-build` built and runs in containers.

Reads `plan.md`, `compare.md` (the angle, if there is one), `recon.md` and `design/` in `forge-work/`
(`brief.md`, `tokens.json`, `components.md`, `world.md`). Writes `forge-work/brand.md`,
`forge-work/brand.json`, new token values and the renamed app.

Brand has no level of its own (rules.md section 10): it adds no motion, and the look level stays as it is.

## Where the brand comes from

The user picked a concept on the board of the design part. The brand follows it:

- **The palette** starts from the colours of that concept: `## Colour` in `forge-work/design/brief.md`
  and the values in `forge-work/design/tokens.json`. Brand changes them only where Step 3 says.
- **The voice** starts from the brief's "How it should feel" and its "Never" words.
- **The name** says something about the angle in compare.md and fits the concept's world (world.md).
- **The user's own app**, or a redesign of it: keep the brand the user already likes, its name,
  colours, logo and tone. Change only what they asked for ("a new name", "rebrand"). No
  `forge-work/design/tokens.json` yet (brand on its own, without the design part): write it from the
  app's current colours as Steps 1 and 2 of `../forge-design/steps/design.md` say, so the palette
  has one home.

## Before you start: what the user looks at

Rules.md section 9, before the first change:

1. **What serves the local URL.** A new app from `/forge-build`: its containers, started from the
   project folder with `docker compose up -d --build --wait`, at the address RUN.md gives (usually
   http://localhost:8080). The user's own app: a dev server that reloads by itself, a built app or
   containers; from which folder and branch (`git branch --show-current`, `git worktree list`); and
   whether a service worker sits in front (`PWA: yes` in plan.md, or a `sw.js` in `public/`). Write
   it under `## How it runs`, the first section of brand.md. Cannot tell: ask one question, "How do
   you open the app, and at which address?"
2. **A work branch in that same folder**: `python3 ../forge/gitguard.py` must exit 0. Exit 1: `git
   switch -c forge/brand`, then run it again.
3. **Before shots** of every screen that shows the name or the colours (at least the home page, the
   sign-in page, the main screen and an error page), from that URL, into `forge-work/brand/shots/before`.
   The shots script is `forge-work/design/shots.mjs`; when it is not there, copy it once as section 1
   of `../forge-design/review.md` says. For example: `node forge-work/design/shots.mjs
   http://localhost:8080 forge-work/brand/shots/before / /login /dashboard`.
4. **Say what will happen**, in order: five names and their checks, the user's pick, the palette,
   the logo brief, the voice, the rename and sweep, the app showing it. Then one line per step.

## Step 1: the name

Ask first: does the app carry a name the user already has (their own business, a salon's booking page)?
Then keep it: no candidates, only the Step 2 checks they want, their own colours and logo in Steps 3 and 4.

Otherwise read the angle in compare.md, the plan and the concept in the brief. Write 20 candidates
across five styles: descriptive (Booklink), compound (Slotwise), invented (Calvo), metaphor (Harbor),
verb (Book). A few may come from the concept's world. Cut to 5:

- **Not confusingly similar** to the original or any other app in the same category, in sound, look
  or meaning. That is the test trademark offices use. No puns on their name, no misspelling of it.
- Short, spellable after hearing it once, no awkward meaning in Dutch, English, German or French.
- Says something about the angle, or at least does not fight it or the concept.

## Step 2: the checks, run, not assumed

For each of the 5, one row per check: the result and the date, or "to run". Never write "free" or
"available" for a check nobody ran. Public registers are fine to search (passive): do it when you
have a browser tool, otherwise give the user the list. Search variants and misspellings too.

| check | where | look for |
|---|---|---|
| EU trademark | EUIPO eSearch plus (euipo.europa.eu) | the same or a similar word in Nice classes 9 and 42 (software, SaaS), 35 for a shop |
| Benelux trademark | BOIP trademarks register (boip.int) | the same; it also shows EU and international marks valid in the Benelux |
| worldwide | WIPO Global Brand Database (branddb.wipo.int) | the same classes, in the countries the user sells in |
| US trademark | USPTO trademark search (tmsearch.uspto.gov), only when selling in the US | classes 9 and 42 |
| Dutch trade name | KvK search (kvk.nl/zoeken) | a business with the same or a similar handelsnaam in the same line of work |
| domains | a registrar's search, or `whois` (SIDN for .nl) | .nl, .com, .eu, .app |
| the web | a search for "name + category", GitHub, social handles | a product that already uses the name |

Screening only, not legal advice: before money goes into the name, a trademark attorney should run
a full search. Registering a domain or a trademark is the user's step; forge never buys anything.

Checkpoint: show the five with their check results and wait for the user to pick one. This stop
holds in auto mode: the app's name is the user's (rules.md section 7).

## Step 3: the palette

The token roles the design part set up keep their names; only values change, and only where they must:

- **Clone mode**: no role holds one of the original's colours (under `## Original brand colours` in
  components.md), and the accent is from another colour family than the original's: if theirs is
  blue, yours is not blue. Idea mode: the same for the closest competitor's colours.
- **The name or the logo** asks for a shift inside the concept's own colours (a warmer accent for a
  warm name). Never a colour family the concept did not have: the palette follows the concept.
- **The user's own colours**, which they like: keep them. Read them exactly off the before shots
  with `python3 ../forge-design/eyedropper.py forge-work/brand/shots/before/home-1440-light.png`
  (`--box x,y,w,h` for one area, `x,y` for one pixel), never by eye.

Note the old values under `## Palette` in brand.md and write the new palette in tokens.json. Run
`python3 ../forge-design/contrast.py forge-work/design/tokens.json` and fix the tokens until it exits 0
(exit 1 names the failing pair and the nearest colour that passes). Write the theme file again with
the `Command:` line under `## Theme` in components.md (`../forge-design/theme.py` writes it from
tokens.json), then put the new values in every other copy of the old ones: the icons, and with `PWA:
yes` the manifest's colours, the `theme-color` meta tag and `public/offline.css`, which repeats the
theme's colours. Then `python3 ../forge-design/sweep.py . --colors "<old value>,<old value>"`, with
each old value gone from tokens.json, must exit 0 (it skips forge-work/ and cannot read PNG files:
Step 4 draws the icons again). No value changed: say so under `## Palette`, and there is no old
colour to sweep for.

## Step 4: the logo brief

Not a logo but a brief for the user, a designer, or an image tool whose terms give the user the rights.
The user's own logo, which they like, stays: the brief then lists only the sizes that are missing.
- The idea in one line, tied to the name, the angle and the concept's shape and signature (the brief's
  `## Shape and depth` and `## Signature`).
- Mark type: wordmark, symbol plus wordmark, or monogram. Reads at 16px as a favicon, works as a square icon.
- Files: an SVG master; `favicon.ico` (32x32) and an SVG favicon; a 180x180 apple-touch-icon;
  with `PWA: yes` icons of 192x192 and 512x512 plus a maskable 512x512 with the mark inside the
  middle 80%; an Open Graph image of 1200x630.
- **Must not resemble the original's mark**: no shared shape, colour pair or letter trick (check side by side).
- A font in a wordmark has an open licence (SIL OFL) or one the user bought. Until the logo
  exists, a plain wordmark in the app's own font holds its place, and the favicon and app icons
  are the name's first letter in `on-accent` on `accent`, drawn as an SVG path: the build's placeholders go.

## Step 5: the voice

Three words for how it sounds, each with what it does not mean ("direct, not blunt"), taken from the
brief's "How it should feel" and "Never". Five do and don't pairs. Then rewrite the 10 most-seen strings
(sign up, the main button, the empty states, the confirmation, the main error, the welcome email
subject) in that voice, in every language the app has. All fresh, none echoing the original's
phrasing. The user's own app with a tone they like: write that tone down and rewrite only the strings
that fight it. In clone mode, list the runs of 4 or more words they share with the original:
`python3 ../forge-build/copycheck.py forge-work/brand.md --words 4`.

## Step 6: rename and sweep

1. Write `forge-work/brand.json` (below).
   - `avoid`: the original's product and company names (idea mode: the closest competitors, from
     compare.md or, if it was skipped, the best known), the working name (plan.md's title) unless the user
     keeps it, and what the scaffold shows ("Create Next App" and Vercel, Vite's "Vite + React", Laravel's
     Laracasts). Never a framework name: Laravel, Django, Next or Vite are in every config file. A working
     name that is a plain word for what the app holds (Notes, Bookings, Kapsalon) stays a word: rename it
     where it is the name (titles, manifest, emails), leave it out of `avoid`, say why in brand.md.
   - `domains`: the original's (idea mode: the competitors'). `colors`: the signature colours under
     `## Original brand colours` in components.md, never white, black or greys (every app has them).
   - `allow`: single words that hold a name and are fine, such as `linear-gradient` for an app
     called Linear. The sweep lists them; tell the user which ones you added.
2. Replace the name, colours and strings everywhere: the app name setting (laravel `APP_NAME` in
   `.env.example`, `config/app.php` and `.env`, that line changed by a script that never prints the file,
   like the one in Step 5 of `/forge-build pack`; django settings and `base.html`; next the root layout's
   `metadata`; static `index.html`), titles and meta tags, `package.json` or `composer.json`, email
   templates and the sender name, the manifest's `name` and `short_name`, error pages, the README and
   the expected texts in the e2e tests. Rename files and folders with the old name; fix imports.
3. From the project root: `python3 ../forge-design/sweep.py . --config forge-work/brand.json`. Exit 1:
   leftovers by place; fix them and run it again until it exits 0. Exit 2: brand.json or the path is
   wrong (the error says what), or the sweep is INCOMPLETE (a file not read, no text file found). A
   mention that must stay (an "Import from Calendly" button) gets `forge:allow` on its line, only with
   the user's OK for that line. If it flags your new name, that name holds the old one: back to Step 1.
4. Rebuild what serves the URL, now and after every later change: containers with `docker compose up
   -d --build --wait`, a built app with its own build and start; a dev server reloads by itself. The
   sweep cannot read images: check by eye the favicon and app icons (the logo or Step 4's letter, no
   shape of the original's mark), the OG image, README screenshots, the emails as they render, and the
   title in the browser tab.
5. Run the unit and e2e tests as `forge-work/test-plan.md` says until green (a rename breaks imports
   and expected texts). A failure the rename did not cause is a bug: it goes into `forge-work/bugs.md`
   and the fix loop of `/forge-check test`, a failing test first; a missing or partial must-have goes
   back to `/forge-build`.
6. `python3 ../forge-check/secretscan.py .`, `python3 ../forge/gitguard.py` and, in clone mode,
   `python3 ../forge-build/copycheck.py` must exit 0 (gitguard exit 1: `git switch -c forge/brand`; a run
   the user OKs goes in `forge-work/copy-allow.txt`). Then commit: `brand: rename to <name>, new palette`.

## Show the result

Rules.md section 9, after Step 6. The user must see their own name and colours on their local app.

1. **Make it show.** Say which branch the work is on. Containers or a built app were rebuilt in Step
   6.4; a worktree or copy: start the app from your folder on a free port and give that address, or
   give the one command that switches their folder to the branch. A service worker keeps the old
   icons, colours and `offline.css`: raise its version (`const VERSION = "v1"` to `"v2"` in
   `public/sw.js`, made from `../forge-plan/sw.example.js`), rebuild, and reload twice. Then load the
   URL yourself and check the title in the tab.
2. **After shots and proof.** The same command, paths and flags as the before shots, into
   `forge-work/brand/shots/after`. Then `python3 ../forge-design/changed.py forge-work/brand/shots/before
   forge-work/brand/shots/after` must exit 0 (VISIBLE CHANGE). Exit 1: find which reason of rules.md
   section 9 it is (another branch or folder, not rebuilt, a cache), fix it, shoot again. Only the
   name changed and the user's colours stayed: the change can be under the 2 percent bar, so compare
   `--viewport-only` shots of the screens where the name is largest; never lower `--min`. Exit 2 is
   never a pass. Results under `## Proof` in brand.md. Nothing new moves here: no frames, no clip.
3. **Hand it over** in plain words: the branch; the address that shows the new name and colours now;
   where to look first (the tab title, the header, the sign-in page, then the favicon, which a browser
   keeps for a while: a new private window shows the new one); the paths of the before and after
   images; and how to go back (`git switch <their branch>`). Merging and deploying stay their step.

## Output

`forge-work/brand.json` and `forge-work/brand.md`, as below. The gate checks the name and avoid list in
brand.json, a line of text under each of brand.md's five ## headings (Name checks, Palette, Logo brief,
Voice, Sweep), that contrast.py, the sweep and, in clone mode, the copy check exit 0, and that the app
carries the name. `## How it runs` and `## Proof` hold rule 9's lines.

```json
{"name": "Slotwise", "avoid": ["Calendly", "Calendly LLC"], "domains": ["calendly.com"],
 "colors": ["#006bff"], "allow": []}
```

```markdown
# Brand
Date: YYYY-MM-DD
Name: Slotwise (picked by the user on YYYY-MM-DD)
## How it runs
Containers from this folder (docker compose), http://localhost:8080, branch forge/brand. Service worker: none.
## Name checks (screening, not legal advice)
| check | Slotwise | Harbor |
|---|---|---|
| EUIPO, classes 9 and 42 | nothing similar (YYYY-MM-DD) | to run |
## Palette
accent #0f7b6c (was #2f6fde), from concept B. contrast.py exit 0. The original's colours are in brand.json.
## Logo brief
## Voice and the strings rewritten
## Sweep
sweep.py exit 0 on YYYY-MM-DD. forge:allow lines: none. Checked by eye: favicon, icons, OG image, emails.
## Proof
changed.py forge-work/brand/shots/before forge-work/brand/shots/after: VISIBLE CHANGE on 8 of 8 pairs.
```

## Next

Checkpoint: tell the user in at most 5 plain lines the name and which checks are still to run, the
palette and the contrast result, the sweep and test results, where to look on their own screen (the
address and the before and after images), and that the checks are not legal advice. Wait for the
user's go. Then `/forge-launch`, or back to `/forge` or `/forge-improve` when the run started there.
