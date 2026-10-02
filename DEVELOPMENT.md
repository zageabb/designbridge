# Development Status

Last reviewed: 2026-10-02
Current development state: ACTIVE

## Purpose

This file is the repository-level source of truth for planned development and **evidence of completion**. It is intended to be readable by both the user and AI coding agents.

Existing project-specific roadmaps, version documents, release notes, design documents and implementation notes remain valid. They provide detail and history; this file provides the common cross-repository development, coordination and completion standard.

## Current objective

Continue reliable design round-tripping and Penpot/Figma-oriented design interchange with revision-aware evidence, safe synchronisation, reusable design-system behaviour and developer-usable output.

## Existing planning and evidence sources

- `README.md`
- `docs/V0.2_COMPONENTS_TOKENS.md`
- `docs/V0.3_DESIGN_OPERATIONS.md`
- `docs/V0.4_REVISIONS_ROUNDTRIP.md`
- `docs/V0.5_PENPOT_SYNC.md`
- `docs/V0.6_DIRECT_PENPOT_SYNC.md`
- `docs/V0.7_LAYOUT_SYNC.md`
- `docs/V0.8_CONFLICT_AWARE_SYNC.md`
- `docs/V0.9_REVISION_AWARENESS.md`
- `docs/V0.10_REVISION_DIFF.md`
- `docs/V0.11_SELECTIVE_PULL.md`
- `docs/V0.12_THREE_WAY_REVIEW.md`
- `docs/V0.13_PROPERTY_RESOLUTION.md`
- `docs/V0.14_DOCUMENT_RECONCILIATION.md`
- `docs/V0.15_COMPONENT_INSTANCES.md`
- `docs/V0.16_COMPONENT_DEFINITIONS.md`
- `docs/V0.17_COMPONENT_VARIANTS.md`
- `GitHub pull requests`
- `GitHub Actions`

## Status values

- 🔵 **PLANNED** — agreed or captured, not started.
- 🔨 **IN PROGRESS** — implementation has started but completion evidence is incomplete.
- 🚫 **BLOCKED** — cannot progress until a dependency, conflict or decision is resolved.
- ⏳ **AWAITING ACCEPTANCE** — development evidence is complete but an external/user/business acceptance step remains.
- ✅ **COMPLETE** — implementation and all applicable evidence checks have been verified.
- 💤 **DEFERRED** — intentionally postponed.

## Evidence standard

A development item MUST NOT be marked **COMPLETE** solely because an AI agent, developer, document, UI message or successful CI run says that it is complete.

Before using COMPLETE, verify all applicable evidence:

1. the requested implementation exists in the repository;
2. the expected files actually changed;
3. a non-empty diff or equivalent implementation evidence exists;
4. tests for the behaviour exist, or a reason for no test is recorded;
5. relevant tests pass;
6. build, lint, type-check, migration or other repository validation passes where applicable;
7. CI passes where CI exists;
8. commit and/or pull-request evidence is recorded;
9. the change is merged into the intended branch when merge is required;
10. post-merge verification confirms the expected change exists on the intended branch where appropriate;
11. user/business/external acceptance is recorded separately from development completion.

If required evidence is missing, use **IN PROGRESS**, **BLOCKED** or **AWAITING ACCEPTANCE** instead.

For coding work, any of the following are explicit evidence that the task is **not complete** when a code change was expected:

- empty final response;
- no write/edit operation;
- unchanged branch HEAD;
- empty branch diff;
- no requested validation;
- budget exhaustion before acceptance criteria are satisfied.

Green CI alone does not prove feature completion.

## Development ledger

### DEV-000 — Establish evidence-based development ledger

Status: ✅ COMPLETE  
Priority: High  
Owner/Agent: ChatGPT  
Branch: main  
Depends on: None  
Can run in parallel with: Repository development work that does not modify this process definition  
Integration status: integrated

Requirement:
Give the user and AI agents one persistent place to see planned work, completion state, parallel-development ownership and the evidence supporting completion.

Implementation:
- Added and standardised this `DEVELOPMENT.md`.
- Standardised `AGENTS.md` so AI agents must read and maintain this ledger.
- Added explicit parallel-development coordination metadata.
- Existing DesignBridge version/design documents remain in place as detailed historical and technical sources.

Evidence:
- Files: `DEVELOPMENT.md`, `AGENTS.md`
- Commit: recorded by GitHub history for this change.
- Tests: documentation/process change; no runtime test required.
- CI: not required to establish the ledger itself.
- Merged to intended branch: yes, `main`.
- User acceptance: requested directly on 2026-10-02.

Completion criteria:
- [x] Common status vocabulary defined.
- [x] Completion evidence rules defined.
- [x] False-completion rules defined.
- [x] Existing planning/evidence sources referenced.
- [x] Parallel-development metadata defined.
- [x] Integration status defined.
- [x] AI maintenance rule added.
- [x] Development completion separated from external/user acceptance.

### DEV-017 — Component variants and safe switching

Status: ✅ COMPLETE  
Priority: High  
Owner/Agent: ChatGPT  
Branch: `feature/v0.17-component-variants-rebased`  
Depends on: v0.16 component definition synchronization  
Can run in parallel with: documentation/process work that does not modify component/variant sync code  
Integration status: verified on target branch

Requirement:
Represent component variant families canonically and allow safe Penpot instance switching without silently losing compatible instance overrides.

Implementation:
- Added canonical `variant_group`, `variant_properties`, and stable child `variant_slot`.
- Rejects duplicate variant property combinations inside one family.
- Added variant family reporting.
- Added compatibility planning before mutation.
- Remaps overrides across variants by `variant_slot`, never by display name.
- Rejects missing slots, incompatible types, and direct-fill remaps onto token-bound targets.
- Added Penpot **Review variants** UI.
- Uses Penpot native component swap semantics for compatible switches.
- Commits the canonical component switch only after Penpot succeeds.
- Attempts to swap Penpot back to the source component if the final canonical commit loses a revision race.
- Rebased the implementation onto current `main` after process/documentation work landed there.

Evidence:
- Original implementation CI: GitHub Actions run #174 passed on commit `af97201f078f81002f8743361b9b292ebb79be59`.
- Original PR: #17 (superseded after main diverged).
- Active replacement PR: #18.
- Rebased branch: `feature/v0.17-component-variants-rebased`.
- Files: `backend/app/models.py`, `backend/app/component_sync.py`, `backend/app/main.py`, `penpot-plugin/public/plugin.js`, `penpot-plugin/public/index.html`.
- Tests: `backend/tests/test_component_sync.py`, `backend/tests/test_designbridge.py`.
- Documentation: `docs/V0.17_COMPONENT_VARIANTS.md`.
- Rebased CI: GitHub Actions run #204 passed.
- Merged to intended branch: yes, `main`.
- Merge commit: `8113b9d482810fc1a7ed47051296ae740be3bc27`.
- Post-merge verification: `DEVELOPMENT.md` contains DEV-017 and `backend/app/models.py` contains `variant_slot` on `main`.
- User/business/external acceptance: separate from development completion.

Completion criteria:
- [x] Canonical variant families exist.
- [x] Stable cross-variant child mapping exists.
- [x] Compatible override remapping is implemented.
- [x] Incompatible switches are blocked before mutation.
- [x] Penpot switch precedes canonical commit.
- [x] Rollback is attempted on final revision race.
- [x] Material behavior is covered by tests.
- [x] Rebased branch CI passes.
- [x] PR is merged to `main`.
- [x] Post-merge verification is recorded.

Notes:
Native Penpot VariantContainer discovery and `switchVariant(...)` integration remain follow-up work. The current implementation uses safe component swaps for canonical variant families.

### DEV-018 — Durable revision fingerprints

Status: 🔨 IN PROGRESS  
Priority: Critical  
Owner/Agent: ChatGPT  
Branch: `feature/v0.18-revision-fingerprint`  
Depends on: DEV-017 integrated  
Can run in parallel with: non-sync documentation work only  
Integration status: implementation and regression tests in progress

Requirement:
Prevent reused numeric revision numbers from being mistaken for synchronized state after undo followed by a new divergent save.

Implementation:
- Added deterministic SHA-256 revision fingerprints derived from canonical sorted DesignBridge JSON.
- Added `revision_token` storage on revision rows.
- Added SQLite migration/backfill for legacy revision rows.
- `save`, `load`, and `history` expose revision tokens.
- Penpot current/status APIs expose fingerprints.
- Status distinguishes `in_sync`, `behind`, `ahead`, `unverified`, and `diverged`.
- Same numeric revision with a different token becomes `diverged`.
- Penpot stores `designbridge:revision-token` in plugin data.
- Penpot sync UI sends tokens on writes and base-revision reconciliation requests.
- Mutating Penpot APIs require both revision number and matching fingerprint.
- Base-sensitive reconciliation APIs require `from_revision_token`.
- Added regression coverage for legacy database backfill and reused revision numbers.

Evidence:
- Files: `backend/app/storage.py`, `backend/app/main.py`, `penpot-plugin/public/plugin.js`, `penpot-plugin/public/index.html`.
- Tests: `backend/tests/test_revision_fingerprint.py`, updates to `backend/tests/test_designbridge.py`.
- Branch commits include `59f9da5549ee3fa893345315f173487036bf0d88`, `c555885f046deff8ee28c058e8be9e7ac8db0f2f`, `511082958e3aa8e93f66bdb0cc2f49db72bd8b92`, `e830a940e884db24bf779a57a9cfedb9a8ab0514`, `46ac4bdcecbef300b7dbe5f5983b1866c195bb83`.
- CI: pending.
- PR: pending.
- Merged to intended branch: no.
- Post-merge verification: pending.

Completion criteria:
- [x] Revision token is deterministic.
- [x] New revisions persist tokens.
- [x] Legacy revisions are backfilled.
- [x] Current/status APIs expose tokens.
- [x] Same-number/different-content state reports `diverged`.
- [x] Penpot persists revision tokens.
- [x] Penpot writes require matching revision identity.
- [x] Base-sensitive review/pull calls validate base token.
- [x] Regression tests cover revision-number reuse.
- [ ] CI passes.
- [ ] PR is merged to `main`.
- [ ] Post-merge verification is recorded.

Notes:
This milestone intentionally hardens identity before additional structural/destructive synchronization work.

## New development item template

Copy this section for every meaningful feature, bug fix, development idea or integration task.

### DEV-XXX — Short title

Status: 🔵 PLANNED  
Priority: Medium  
Owner/Agent:  
Branch:  
Depends on:  
Can run in parallel with:  
Integration status: not started

Requirement:
Describe what the user actually asked for and the intended outcome.

Implementation:
Record what was changed. Leave blank until implementation starts.

Evidence:
- Commit:
- PR:
- Files:
- Tests:
- Build/lint/type-check/validation:
- CI:
- Merged to intended branch:
- Post-merge verification:
- User/business/external acceptance:

Completion criteria:
- [ ] Implementation exists.
- [ ] Relevant files changed.
- [ ] Meaningful diff or equivalent implementation evidence exists.
- [ ] Tests added/updated, or reason recorded.
- [ ] Relevant tests pass.
- [ ] Build/lint/type-check/other validation passes where applicable.
- [ ] CI passes where applicable.
- [ ] Commit/PR evidence recorded.
- [ ] Merged where required.
- [ ] Post-merge verification completed where applicable.
- [ ] External/user acceptance separated from development completion.

Notes:
Record limitations, decisions, discovered follow-up work and integration considerations.

## Parallel development coordination

Use the coordination fields on every active DEV item when parallel work is possible.

- **Owner/Agent** — the person or AI agent currently responsible for the item.
- **Branch** — the working branch or worktree used for the item.
- **Depends on** — DEV items, decisions or external prerequisites that must complete first.
- **Can run in parallel with** — DEV items that are safe to develop concurrently without conflicting ownership or sequencing.
- **Integration status** — use values such as `not started`, `isolated`, `ready for integration`, `integration blocked`, `integrated`, or `verified on target branch`.

Before starting parallel work:

1. identify genuinely independent workstreams;
2. give each workstream a concrete DEV item and acceptance criteria;
3. record branch/worktree ownership;
4. record file/module/subsystem ownership where practical;
5. identify dependencies before spawning parallel work;
6. avoid assigning two active agents the same responsibility unless explicitly coordinated;
7. do not describe a sequential dependency chain as parallel work;
8. record who owns final integration;
9. independently verify each child workstream before integration;
10. verify the integrated result on the intended target branch.

If two DEV items touch the same subsystem or files, record the conflict explicitly and sequence or coordinate integration rather than assuming independence.

Parallel execution does not weaken the completion standard: every DEV item retains its own implementation, validation, CI, Git and acceptance evidence requirements.

## Autonomous continuation rule

When the user asks to continue development, operate under this rule:

> Continue autonomously until one of these happens:
> 1. the current objective is complete and verified;
> 2. a genuinely ambiguous product decision is required;
> 3. progress is blocked by something outside the repo;
> 4. continuing would risk destructive changes.
>
> Do not stop just because one implementation step has completed.

A coding agent should normally continue through implementation, tests, CI inspection, fixes, documentation updates, PR creation, merge-readiness, merge, and post-merge verification without pausing after each intermediate step.

## CI, acceptance and merge gates

Treat these as separate gates:

```text
Implementation evidence
        ↓
Local validation
        ↓
CI
        ↓
Acceptance verification
        ↓
Pre-merge review
        ↓
Merge
        ↓
Post-merge verification
        ↓
Development state update
```

Pre-merge review should check, where applicable:

- complete diff against the original requirement;
- no unintended debug or temporary files;
- no committed secrets;
- relevant tests/build/lint/type-check;
- migration/deployment implications;
- documentation accuracy;
- acceptance criteria.

Post-merge verification should confirm the expected change exists on the intended branch and record the resulting commit/merge evidence.

## Recovery and no-progress handling

If a development attempt makes no meaningful progress, do not convert activity into a COMPLETE status.

After repeated unsuccessful fixes to the same underlying problem, stop symptom-patching and inspect root cause, relevant history, current diff, tests and runtime evidence before another code change.

If budget/tool/runtime limits interrupt work, record:

- work completed;
- work remaining;
- blocker or reason for stopping;
- safest continuation point;
- recommended next action.

Preserve enough state in this file that another agent can continue without reconstructing the task from chat history.

## Maintenance rule

Update this file during the same development pass that changes implementation.

When documentation and repository evidence disagree, repository evidence wins. Reconcile this file rather than preserving an unsupported COMPLETE state.
