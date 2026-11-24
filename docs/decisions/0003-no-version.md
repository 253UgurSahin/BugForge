# 0003. No version: every push to main is a release

Status: accepted (found in the code, 2026-11-24)

## Context
With a fixed `version` in `plugin.json`, Claude Code gives users nothing new until the number is raised,
and a forgotten bump strands fixes.

## Decision
`plugin/.claude-plugin/plugin.json` has no `version`; Claude Code uses the commit. `tests/test_repo.py`
keeps it that way.

## Consequences
Users get each push to `main` with `/plugin marketplace update`. The plugin directory shows a warning
for the missing version, which is accepted.
