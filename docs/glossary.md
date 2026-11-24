# Glossary

The words BugForge uses, one meaning each.

| word | meaning | in the code |
| --- | --- | --- |
| skill | one folder of instructions Claude follows, started by a command such as `/forge-check` | `plugin/<skill>/SKILL.md` |
| part | a piece of a skill with its own steps, such as `audit` of forge-check | `plugin/<skill>/steps/<part>.md` |
| phase | one step of a `/forge` project, done by a skill or a part | `plugin/forge/phases.json` |
| mode | the kind of project: clone, idea or improve; it decides the phases | `modes` in `plugin/forge/phases.json` |
| gate | the script that records a phase only when its checks pass and the user gave the go | `plugin/forge/gate.py` |
| exit check | one thing a phase must leave behind, checked by the gate | `plugin/forge/phasecheck.json` |
| go | the user's own words that approve a phase, recorded as typed | `approved` in `forge-work/state.json` |
| auto mode | the user's request to run the phases without a stop after each; never for secure | `--auto` of `gate.py done` |
| level | how far a skill goes, 1 to 5, chosen by the user per domain | `plugin/forge/levels.json`, `level.py` |
| domain | what a level is for: look, header, dashboard, test or secure | `domains` in `levels.json` |
| finding | one problem a check found, with an ID, severity, where, why and fix | `forge-work/audit.md`, `bugs.md`, `security.md` |
| severity | how bad a finding is: critical, high, medium or low | each script's `SEVERITIES` |
| forge-work | the folder in the user's project for plans, reports and screenshots; never committed | `forge-work/` |
| scope | the hosts the user owns, where active tests may run | `forge-work/scope.json`, `scope.py` |
| clean-room | rebuilding what an app does without taking its code, assets, copy or brand | `plugin/forge/rules.md` |
| plain | clear for everyone and written professionally | `plugin/forge-design/plain.md` |
| code craft | how well code is made, by the rules of Clean Code, SOLID, GRASP and the patterns | `plugin/forge-check/craft.md` |
| scene kit | the 3D scenes the look uses from level 4 | `plugin/forge-design/scenes/` |
| helper | a `_*.py` module that scripts in its folder import; never run on its own | `plugin/forge-check/_walk.py` and others |
