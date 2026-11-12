# SS1 Progress and SS2 Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Continue emmkay's SS1 decomp in MatyMeatBoy/SS1Decomp with honest SS2-style progress and actionable cross-game matching candidates.

**Architecture:** Preserve the upstream build and legacy progress interface. Add isolated ROM-free ELF/map metadata generation and a presentation layer adapted from SS2. Independently validate any imported SS2 source against SS1.

**Tech Stack:** Python standard library, GNU ARM binutils, agbcc/old_agbcc, Make, SVG and GitHub Actions.

**Spec:** docs/superpowers/specs/2026-11-12-progress-and-ss2-reuse-design.md

## Global Constraints

- Preserve upstream history, credits, ROM profile AHUE and SHA1 `14723ead8634959b4fad027d9618c0860b82ea67`.
- Author new commits as MatyMeatBoy. Keep public repository prose in English.
- No ROM or extracted game assets in Git. Metadata-only inputs must not overwrite real build inputs or objects.
- Preserve `make progress`, its JSON fields and the ordinary `make compare` gate.
- No matching credit for cross-game resemblance, drafts or metadata-only builds.

## Review Focus

- Missing or incorrect ROM must never produce a successful match status.
- Header bytes, empty modules and duplicate aliases must not inflate code or function totals.
- Early MultiSio and library ownership must remain distinct from game code.
- Unknown incbin directives must fail safely rather than silently generating incorrect layouts.
- SS2 structs, coordinate scales, callbacks and constants require independent SS1 evidence.

### Task 1: Preserve provenance and establish baseline

- [x] Fork upstream under the requested account/name and configure author identity.
- [x] Reply to the owner's permission with the requested thanks and credit commitment.
- [x] Record credits and pinned upstream source revision.
- [ ] Verify the owner's ROM and reproduce `make compare` before claiming a matching baseline.

### Task 2: Reproducible metadata-only layout

- [ ] Add `tools/scripts/metadata_build.py` with isolated outputs and strict incbin guards.
- [ ] Add meaningful tests in `tests/test_metadata_build.py`.
- [ ] Compile/link all code with the original flags; verify expected code/data boundaries.

### Task 3: SS2-style presentation

- [ ] Add inventory/report rendering in `tools/scripts/progress_visuals.py`.
- [ ] Adapt SS2 badge/treemap rendering with attribution, using SS1 metrics.
- [ ] Add README code/names/data views, explicit verification status and generation commands.
- [ ] Add ROM-free CI generation and preserve the legacy `make progress` interface.
- [ ] Check numeric partitions, XML output and absence of game assets in staged files.

### Task 4: Initial SS2 transfer cohort

- [x] Compare historical SS1/SS2 candidates against current linked source.
- [ ] Preserve the reviewed candidate manifest and missing-draft recovery notes.
- [ ] Adapt a selected candidate in an isolated checkout when its inputs and ROM gate are available.
- [ ] Credit a gain only after the full ROM check; preserve nonmatching attempts as scratch drafts.

### Task 5: Review and delivery

- [ ] Independently review generator, metrics, attribution and candidate evidence.
- [ ] Run required checks and `make compare` when its required ROM is available.
- [ ] Publish the finished setup in a reviewable PR, with exact validation and any remaining blockers.
