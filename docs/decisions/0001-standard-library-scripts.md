# 0001. Skills run standard-library Python scripts

Status: accepted (found in the code, 2026-11-24)

## Context
The skills must work on Linux, macOS and Windows, in a fresh Claude Code session and on claude.ai,
without installing anything first.

## Decision
Every check is a Python 3.9 script that uses only the standard library, with `--help`, `--json` and
exit codes 0 (clean), 1 (a finding at or above `--fail-on`) and 2 (could not run). `tests/test_repo.py`
enforces the library, the syntax, the line limit and a test file per script.

## Consequences
The scripts run anywhere Python runs, and their output can be read by Claude and by people. Parsers
for HTML, PNG and compose files are written by hand, so they are smaller than full libraries.
