# 0006. The release check runs locally, without GitHub Actions

Status: accepted (2026-11-24, the owner's choice)

## Context
The owner does not want GitHub Actions for this repository.

## Decision
There is no CI workflow. Before every push to `main`, three commands run from the repository root:
the test suite, the repository's own secret scan and the plugin directory validation (README, Tests).

## Consequences
No CI minutes are used. Whoever pushes to `main` runs the checks; Windows and macOS are checked only
where someone runs the suite there.
