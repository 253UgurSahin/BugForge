# 0004. Scripts share code through _ helpers

Status: accepted (found in the code, 2026-11-24)

## Context
Every script stood alone and might not import another, so 21 blocks were copied between scripts and
could drift apart (craft.md CR-G1).

## Decision
The scripts of a folder share code through `_*.py` helpers next to them. A script still never imports
another script. Two scripts of forge-design reach forge-check's helpers through one `sys.path` entry.

## Consequences
One copy of each shared rule. A script runs when Python puts its own folder on `sys.path`, as
`python3 path/script.py` does; with `-I`, `-P` or `PYTHONSAFEPATH` it does not.
