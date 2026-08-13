---
title: "Persist TDD Cycle Evidence in apply-progress.md before strict-TDD verify; commit remediations before ledger settle"
date: 2026-08-13
category: workflow-issues
module: sdd-verify (hybrid routing, gentle-ai SDD)
problem_type: workflow_issue
component: development_workflow
severity: medium
applies_when:
  - "Running an SDD change with strict_tdd: true under hybrid routing"
  - "UI bundles are routed to frontend-dev while the orchestrator owns apply-progress.md merging"
  - "Merging lane results into apply-progress.md before verify launches"
  - "Settling a failed-to-passed verify pair whose remediation artifact is untracked"
root_cause: missing_workflow_step
resolution_type: workflow_improvement
related_components:
  - documentation
  - tooling
tags:
  - sdd
  - hybrid-routing
  - strict-tdd
  - tdd-evidence
  - verify-gate
  - gentle-ai
---

# Persist TDD Cycle Evidence in apply-progress.md before strict-TDD verify; commit remediations before ledger settle

## Context

This repo runs spec-driven SDD with `openspec/config.yaml` declaring `strict_tdd: true` (and `apply.tdd: true`). Under that contract, sdd-verify treats `apply-progress.md` with a TDD Cycle Evidence table as a first-class gate — every archived change in `openspec/changes/archive/` carries one. Change `r2-world-xp-island` (3 slices, PRs #55–#57) executed its UI bundles through the **frontend lane** (frontend-dev design/verify → frontend-apply implementation) per the hybrid routing recipe, and the orchestrator — who contractually owns "merging results into apply-progress" — never merged the lane results into the artifact. The first verify run FAILED even though every piece of code evidence was green: 6/6 requirements, 13/13 scenarios, pytest 574/574, node 133/133, pyright 0, smoke 81/81. The only missing piece was the strict-TDD evidence artifact.

A second, related wrinkle surfaced while closing the ledger: settling the failed→passed verify pair with `gentle-ai sdd-attempt settle` demands `--remediates-evidence-revision <failed-evidence-revision>` and then refuses a second time ("unmanaged remediation requires a changed correction candidate") when the remediation exists only as an untracked file — the git candidate identity is unchanged.

## Guidance

**Practice 1 — the orchestrator MUST persist `apply-progress.md` with truthful TDD Cycle Evidence BEFORE launching verify, merging lane results.** For hybrid-lane changes, collect from each lane: per-work-unit RED evidence (the actual failing assertion), GREEN evidence (focused test counts), triangulation coverage, safety-net baseline, and runtime harness results (smoke counts, screenshots), then write the artifact exactly as if a single apply session had produced it.

Table schema to reproduce (from the archived artifact):

`| Work unit | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |`

Required companion sections: **Completed Tasks** (per-work-unit checkboxes), **Work Unit Evidence** (focused test commands + exact results; runtime harness commands + exact results; visual verification; rollback boundary = revert the slice commit on its branch, no DB migration), **Deviations from Design**, **Issues Found**, **Verification** (full-suite counts).

RED rows must be **truthful and cross-checkable** — verify validates them by commit-parent inspection (Slice 1 parent lacked `worldStage`; Slice 2 parent retained the placeholder; Slice 3 parent lacked `renderWorld` wiring).

**Practice 2 — remediation of a ledger-tracked failed verify requires a CHANGED correction candidate.** A failed→passed settle demands `--remediates-evidence-revision <failed-evidence-revision>`, then refuses ("unmanaged remediation requires a changed correction candidate") when the remediation is an untracked file. The remediation must be **committed** (docs commit is enough) so the candidate changes; then the settle passes.

## Why This Matters

- The failure is **invisible in code evidence**: every suite green, yet verify FAILED on the missing artifact. It reads as a false-fail unless you know the strict-TDD contract.
- It **blocks the pipeline twice**: once at verify (process blocker, not code), once at settle (evidence-revision demand, then candidate-change demand).
- The candidate-change requirement expands the remediation's blast radius into git history: an uncommitted remediation cannot be settled; you must commit it, which also means the remediation docs ride the next PR's diff.
- Cost of missing it: full verify re-run + remediation artifact + docs commit + settle round-trip, plus the ledger's FAIL record persisting until the remediation commit lands.

## When to Apply

- Any `strict_tdd: true` SDD change before launching verify — the artifact is a gate, not a courtesy.
- Any hybrid-lane execution (frontend lane, multiple apply sessions, delegated applies) — the more lanes, the less likely any single writer emits the artifact; the orchestrator is the only place lane results converge.
- Any failed→passed verify settle on the ledger: commit the remediation docs BEFORE running settle with `--remediates-evidence-revision`.
- Also when a change's execution is split across sessions/transports (r1 precedent: delegated-apply transport failures → inline implementation → artifact still produced).

## Examples

**1. The first-run FAIL (artifact gap, all code green)** — verbatim from the remediated apply-progress.md "Issues Found":

> "Verify FAIL on first run (2026-08-13) — artifact, not code: all 6/6 requirements and 13/13 scenarios compliant (pytest 574/574, node 133/133, pyright 0, smoke 81/81) but the strict-TDD `apply-progress.md` TDD Cycle Evidence artifact was missing (frontend-lane results had not been merged)."

**2. A truthful row in the remediated TDD Cycle Evidence table** (Slice 3, verbatim):

```
| Slice 3 (live behavior) | tests/test_spa_gate.py app.js wiring pins | Integration (served assets) | ✅ gate suite green before | ✅ wiring pins failed — renderWorld/prevWorldStage/stageChanged wiring absent from app.js | ✅ gate suite green; full pytest 574, node 133, pyright 0, smoke 81 | ✅ stage-up confetti fires once; suppressed on equal/lower/failed/reduced-motion; "Sprout Isle" + 0 / 100 for fresh user; both themes | ➖ None needed |
```

**3. The ledger settle error sequence** (this session):

1. Failed→passed settle demanded `--remediates-evidence-revision <failed-evidence-revision>`.
2. Settle refused again: "unmanaged remediation requires a changed correction candidate" — the apply-progress.md/verify-report.md were untracked, so the git candidate identity was unchanged.
3. Docs commit `bd29724 docs(openspec): persist r2-world-xp-island TDD evidence and verify report` changed the candidate → settle passed.

**4. The commit trail** (what "changed candidate" looks like):

```
9a59fac feat(format): derive world island stages from total XP      ← slice 1 (RED world.test.mjs → TypeError)
1388fcf feat(world): static island markup, tokens, motion gate      ← slice 2
d865b26 feat(world): live island render, stage-up confetti, smoke   ← slice 3
bd29724 docs(openspec): persist r2-world-xp-island TDD evidence and verify report  ← remediation (candidate change)
ee966eb docs(openspec): sync r2-world-xp-island deltas into catalog specs
461e7e6 chore(openspec): archive r2-world-xp-island change
```

## Related

- Source artifacts: `openspec/changes/archive/2026-08-13-r2-world-xp-island/{apply-progress,verify-report,archive-report}.md`
- Prior precedent (same table schema + transport-failure remediation): `openspec/changes/archive/2026-08-10-r1-quests-xp/apply-progress.md`
- Earlier, weaker variant of the same artifact gap (WARNING, not FAIL): `openspec/changes/archive/2026-08-11-r2-achievements/verify-report.md` — Safety Net baselines missing from apply-progress
- Truthfulness variant (tasks.md is the source of truth): `openspec/changes/archive/2026-08-05-user-accounts-auth/archive-report.md`
- Contract: `openspec/config.yaml` (`strict_tdd: true`); canonical recipe: `/home/james/ai-workspace/workflow_optimisation/WORKFLOW.md` (hybrid lane); settle contract: `~/.config/opencode/skills/_shared/sdd-status-contract.md`
