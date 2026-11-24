# 0005. A gate that records the user's own words

Status: accepted (found in the code, 2026-11-24)

## Context
A project of many phases must not run on past a point the user has not seen, and "done" must mean the
phase left what it promised.

## Decision
`gate.py` records a phase only when its exit checks pass, in order, with the user's words of go as
typed. Auto mode runs on only when the user asked for it; secure is never skipped and never auto.

## Consequences
Each phase ends at a checkpoint the user answers. The record in `forge-work/state.json` shows who
approved what and when.
