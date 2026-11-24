# 0002. The plugin is the plugin/ folder only

Status: accepted (found in the code, 2026-11-24)

## Context
With the whole repository as the plugin, an install and the plugin directory's scan held the gallery
(minified three.js) and the tests (a web shell fixture, fake secrets), which no skill runs.

## Decision
The nine skill folders, `plugin.json`, a README, the LICENSE and the icon live in `plugin/`; the
marketplace's source is `./plugin`. `tests/test_repo.py` keeps anything else out.

## Consequences
An install holds only what the skills run, and the directory scans only that. Commands run from the
repository root name `plugin/` in their paths.
