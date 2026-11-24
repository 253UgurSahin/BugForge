# Architecture

How this was made: from the code at commit 9479de5 on `main`'s line (2026-11-24), by `/forge-docs`.
Read: every skill's `SKILL.md`, `plugin/forge/gate.py`, `phasecheck.py`, `level.py`, `phases.json`,
`levels.json`, the marketplace and plugin manifests and `tests/_load.py`. Run: `detect.py`,
`inventory.py`, `craftcheck.py` and the test suite.

## Context

BugForge is a Claude plugin: nine skills that Claude follows to research, plan, design, build, check,
improve, launch and document a web app on the user's own machine. The user talks to Claude; Claude
reads a skill's steps and runs its scripts in the user's project. Nothing runs on a BugForge server:
there is none. The skills reach outside services only where `plugin/README.md` lists them.

```mermaid
flowchart LR
  owner([App owner]) -->|asks, gives each go| claude[Claude Code or claude.ai]
  claude -->|reads steps, runs scripts| plugin[BugForge plugin]
  plugin -->|reads and writes| project[(The user's project and forge-work/)]
  plugin -->|starts, tests, screenshots| app[The user's app on localhost]
  plugin -->|named in plugin/README.md| outside[Sites the user names, registries, Stripe test mode]
```

## Logical view: layers and parts

Three layers, each calling only downward:

1. **Skills** (`plugin/<skill>/SKILL.md` and `steps/*.md`): what Claude does, in order, with the
   checkpoints where the user decides. Shared rules live in `plugin/forge/rules.md`.
2. **Scripts** (`plugin/<skill>/*.py`): standard-library Python 3.9, one job each, with `--json` and
   exit codes 0, 1 and 2. A script never imports another script; the scripts of one folder share code
   through `_*.py` helpers next to them.
3. **Data** (`*.json` next to the scripts): the rules, limits, words and patterns the scripts read,
   so a rule changes without changing code.

```mermaid
flowchart TB
  subgraph skills[Skills: what Claude follows]
    forge[forge: the orchestrator and the gate]
    research[forge-research] --- plan[forge-plan] --- design[forge-design] --- build[forge-build]
    check[forge-check] --- improve[forge-improve] --- launch[forge-launch] --- docs[forge-docs]
  end
  subgraph scripts[Scripts: one job each]
    gate[gate.py, phasecheck.py, level.py]
    checks[secretscan, codecheck, craftcheck, plaincheck, walkcheck ...]
    designs[theme, contrast, motioncount, changed ...]
  end
  subgraph data[Data the scripts read]
    tables[phases.json, levels.json, phasecheck.json, craft.json, plain.json ...]
  end
  skills --> scripts --> data
  forge --> gate
```

The orchestrator `/forge` runs the other skills as phases. Which phases a mode has is in
`plugin/forge/phases.json`:

| mode | phases, in order |
| --- | --- |
| clone | recon, compare, plan, design, build, dashboard, motion, test, diff, brand, launch, secure, pack |
| idea | compare, plan, design, build, dashboard, motion, test, brand, launch, secure, pack |
| improve | audit, inspect, improve, test, secure |

## Domain model

The concepts the skills and scripts share, in BugForge's own words (see `glossary.md`).

```mermaid
classDiagram
  Project "1" --> "1" State : forge-work/state.json
  Project "1" --> "0..5" Level : forge-work/levels.json
  State "1" --> "*" Phase : done or skipped
  Phase "1" --> "*" ExitCheck : phasecheck.json
  Phase "*" --> "1" Skill : runs a part of
  Skill "1" --> "*" Script : runs
  ExitCheck "*" --> "0..1" Script : doccheck, workcheck, lookcheck, level
  Finding "*" --> "1" Report : audit.md, bugs.md, security.md
  class Phase {
    name
    go words
    time
  }
  class Level {
    domain
    number 1 to 5
    user's words
  }
  class Finding {
    id
    severity
    where
    fix
  }
```

## Data view

BugForge has no database. Its data are files: what ships in the plugin, and what it writes into the
user's project under `forge-work/`, which is never committed (`gate.py init` writes a `.gitignore`
there).

| file | written by | holds |
| --- | --- | --- |
| `forge-work/state.json` | only `gate.py` | the mode, each phase done (with the user's words of go and the time) or skipped (with the reason) |
| `forge-work/levels.json` | only `level.py` | the level per domain (look, header, dashboard, test, secure) with the user's words |
| `forge-work/plan.md`, `recon.md`, `compare.md` | research and plan | what to build and why |
| `forge-work/design/` | forge-design | brief, tokens, concepts, shots, review |
| `forge-work/bugs.md`, `audit.md`, `security.md`, `improve.md` | forge-check and forge-improve | findings with IDs, severity, where and fix |

## Main flows

### A phase of /forge, with the gate

Claude does a phase's steps, the gate runs its exit checks, the user gives the go in their own words,
and only then does the gate record the phase.

```mermaid
sequenceDiagram
  actor U as Owner
  participant C as Claude
  participant G as gate.py
  participant P as phasecheck.py
  participant T as doccheck, workcheck, lookcheck, level.py
  C->>C: follow the phase's steps (a skill or a part)
  C->>G: check <phase>
  G->>P: <phase> (subprocess)
  P->>T: each check, with --json
  T-->>P: ok or not, per line
  P-->>G: exit 0 when every check passes
  G-->>C: the result
  C->>U: the checkpoint and one line with the gate's result
  U-->>C: "ja, ga door"
  C->>G: done <phase> --approved "ja, ga door"
  G->>G: refuse if a check fails, the words are missing or an earlier phase is open
  G-->>C: recorded in forge-work/state.json
```

### An audit of the user's code

```mermaid
sequenceDiagram
  actor U as Owner
  participant C as Claude
  participant S as detect, inventory, secretscan, codecheck, deps, trackers, craftcheck
  participant R as forge-work/audit.md
  U->>C: "audit my code"
  C->>S: run each scanner on the project (read only)
  S-->>C: findings with file and line, exit codes
  C->>C: read each place, then the code with craft.md
  C->>R: findings A001..., sorted by severity, with a verdict
  C-->>U: the verdict, the top 3, what was not checked
```

## Deployment view

BugForge is not deployed; it is installed. The repository is a Claude Code marketplace whose one
plugin is the `plugin/` folder; the directory listing reads the same folder.

```mermaid
flowchart LR
  repo[(GitHub: 253UgurSahin/BugForge, branch main)]
  repo -->|.claude-plugin/marketplace.json, source ./plugin| cc[Claude Code: /plugin install bugforge@bugforge]
  repo -->|plugin path: plugin| dir[Claude plugin directory listing]
  repo -->|git archive per skill folder| zips[claude.ai: one zip per skill, all nine]
  cc --> machine[The user's machine: skills and scripts run there]
  zips --> machine
```

Every push to `main` is a release (no `version` in `plugin.json`); the release check runs locally
(README, "Tests").

## States

A phase in `forge-work/state.json`: only done and skipped are written; a passing check alone records
nothing, so the gate runs the checks again at `done`.

```mermaid
stateDiagram-v2
  [*] --> Open
  Open --> Done: done --approved with the user's words, when every exit check passes
  Open --> Done: done --auto in auto mode (never secure)
  Open --> Skipped: skip --reason (optional phases only; never secure)
  Done --> [*]
  Skipped --> [*]
```

## Decisions

- [0001. Skills run standard-library Python scripts](decisions/0001-standard-library-scripts.md)
- [0002. The plugin is the plugin/ folder only](decisions/0002-plugin-folder-only.md)
- [0003. No version: every push to main is a release](decisions/0003-no-version.md)
- [0004. Scripts share code through _ helpers](decisions/0004-shared-helpers.md)
- [0005. A gate that records the user's own words](decisions/0005-gate-with-the-users-words.md)
- [0006. The release check runs locally, without GitHub Actions](decisions/0006-local-release-check.md)

## Quality notes

- 1,952 tests in `tests/` cover every script and the repository's conventions (`tests/test_repo.py`).
  Without Node, the scene kit and screenshot tests are skipped.
- `python3 plugin/forge-check/craftcheck.py plugin` finds no duplicated code, swallowed errors or
  commented-out code. It still lists functions with four or more arguments and some long script
  functions; they get smaller as the code is touched.
- Two false positives that this documentation run found in BugForge's own scanners: `detect.py`
  names a "Django test runner" because a test fixture holds that text, and `inventory.py` lists
  itself as generated because its own pattern holds the words it looks for.
