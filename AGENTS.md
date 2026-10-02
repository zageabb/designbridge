# AGENTS.md

## Project

Repository: `zageabb/designbridge`

This file is the persistent working agreement for ChatGPT, Codex, Olladex and other coding agents operating on this repository.

## Start here

Before changing code:

1. Read this file.
2. Read `DEVELOPMENT.md`.
3. Read the repository README and relevant DesignBridge documentation.
4. Read TODO, roadmap, phase, audit, release, revision, design and development notes when present.
5. Inspect the existing implementation before proposing replacement architecture.
6. Identify the current DEV item, dependencies, branch ownership and integration state.
7. Continue the highest-priority incomplete item unless the user explicitly asks for something else.

Repository state is authoritative. Do not rely on chat history when Git, code, tests, CI or `DEVELOPMENT.md` provide a more current answer.

## Current DesignBridge development state

Merged runtime capability is verified through v0.18.

Current active item:

- DEV-019 — native Penpot variant integration.
- Branch: `feature/v0.19-native-penpot-variants`.
- Goal: discover/map Penpot-native variant families and use native `switchVariant(...)` when the canonical DesignBridge family maps safely.
- Keep the existing guarded `swapComponent(...)` path as fallback for ordinary grouped components or mismatched native metadata.
- Compatibility planning and revision fingerprint protection remain mandatory before any switch.

DEV-018 evidence:

- PR #19 passed CI run #218.
- Merged to `main` as `ba66a3f1ed41dc6fd4db1a0f2fa7f7a04d743c63`.
- Post-merge verification confirmed revision-token storage, `diverged` status, and token-required writes on `main`.

DEV-019 integration evidence so far:

- PR #20 is open.
- CI run #233 passed on the implementation head.
- Pre-merge review found no blocker.
- Merge and post-merge verification are still required before COMPLETE.

Do not automatically convert existing component sets into native VariantContainers until discovery/mapping behavior is proven safe.

## Development rules

- Preserve the existing architecture, UI conventions and working behaviour unless the requested change requires otherwise.
- Prefer extending existing modules over rewriting working code.
- Keep modules focused and independently testable; avoid unnecessary monolithic files.
- Maintain backwards compatibility where practical.
- Keep business logic separate from UI, storage, integration and transport layers.
- Do not hard-code passwords, tokens, API keys, server addresses, ports or environment-specific paths when configuration can be used.
- Put secrets in environment/configuration mechanisms and never commit production secrets.
- Keep configuration explicit and documented.
- Update README/docs/DEVELOPMENT when implementation changes make them inaccurate.
- Clearly mark scaffolds, placeholders, limitations and unfinished features.
- Stay within the current objective. Record unrelated improvements as follow-up DEV items rather than silently expanding scope.

## Revision fingerprint rules

Revision number alone is not a valid synchronization identity.

- Every stored revision must have a deterministic SHA-256 `revision_token` derived from canonical sorted DesignBridge JSON.
- Legacy databases must be migrated/backfilled without losing revision history.
- Penpot stores the token as plugin data alongside the numeric revision.
- Mutating Penpot requests must provide `expected_revision` and `expected_revision_token`.
- Base-sensitive reconciliation must provide `from_revision` and `from_revision_token`.
- Numeric match + token match = `in_sync`.
- Numeric match + token mismatch = `diverged`.
- Numeric match + no token = `unverified`.
- Do not silently accept missing tokens for writes.
- Do not derive trust from a revision number after undo/history truncation.
- New sync features must preserve revision-token checks.

## DesignBridge-specific principles

- Preserve round-trip fidelity and revision traceability.
- Prefer deterministic transforms and explicit conflict handling over silent mutation.
- Keep Penpot/Figma/design-document interchange reviewable and reversible where practical.
- Treat revision IDs, document identity, component identity and property-resolution rules as data-integrity concerns.
- Do not silently discard unsupported properties, components, layouts or revision metadata.
- Prefer explicit reconciliation states when source and target design documents diverge.
- Keep developer-facing exports usable as real implementation artefacts rather than presentation-only approximations.

## Native Penpot variant rules

- Native Penpot variant discovery is read-only and must not switch pages or restructure the file.
- A native family is safe only when its tagged DesignBridge group, component membership, property names, and per-component property values match canonical data.
- Native property order comes from Penpot `Variants.properties`; do not sort it before creating `switchVariant(position, value)` steps.
- If native mapping is absent, mismatched, or ambiguous, use the existing guarded `swapComponent` fallback.
- Do not silently switch from an approved native strategy to fallback after mutation begins; fail and leave canonical state unchanged.
- After native switching, verify the resulting library component's DesignBridge ID equals the approved target before canonical commit.
- Reapply only the already-approved remapped overrides.
- Keep revision fingerprint checks mandatory for planning and commit.
- Automatic VariantContainer creation/restructuring is not part of DEV-019.

## Reuse before duplication

Before building a capability from scratch, inspect relevant existing repositories and reuse proven patterns or modules where appropriate, especially:

- `context-studio`
- `general-search`
- `tender_designer`
- `should-cost-intelligence`
- `should-cost-price-estimator`
- `system-knowledge-designer`
- `olladex`
- `AI_Spreadsheet`

Reuse should preserve module boundaries and licensing/attribution requirements. Do not copy code blindly when a shared abstraction or adaptation is cleaner.

## Testing and quality

- Run the relevant automated tests before committing.
- Add or update tests for material behaviour changes.
- Run build, lint, type-check, migration or validation commands used by this repository when available.
- For synchronisation/round-trip work, test both forward behaviour and recovery/reconciliation paths where applicable.
- Do not claim a feature is complete if tests fail or only a scaffold exists.
- Fix regressions introduced by the change before moving on.
- Record validation evidence in the relevant `DEVELOPMENT.md` item.

## Git workflow

- Default branch is normally `main`; verify before acting.
- Do not force-push the default branch.
- Do not rewrite published history unless the user explicitly requests it.
- Keep commits focused and use clear commit messages.
- Do not push a change known to fail the repository's relevant tests/build unless the user explicitly requests a work-in-progress commit.
- For parallel development, use separate branches/worktrees for independent DEV items where practical.
- Record branch ownership and integration state in `DEVELOPMENT.md`.
- Do not treat creation of a branch or PR as evidence that implementation is complete.

## Parallel development

Before starting parallel work:

1. split only genuinely independent tasks;
2. assign each task a DEV item;
3. record Owner/Agent, Branch, Depends on, Can run in parallel with, and Integration status;
4. record file/module/subsystem ownership where practical;
5. check that another active agent does not already own the same area;
6. do not represent sequential dependencies as parallel execution;
7. preserve independent validation/evidence for every child task;
8. identify who owns integration;
9. verify the integrated result after merge.

If tasks overlap materially, coordinate or sequence them instead of creating competing edits.

## Deployment

Inspect the repository's actual deployment configuration before changing deployment behaviour.

- Preserve existing ports, volumes, environment variables, health checks and service names unless the requested change requires otherwise.
- Do not assume every target is Dockerised.
- Avoid introducing deployment-only dependencies into core application logic.
- Keep local development possible where the existing project supports it.

## Autonomous continuation rule

When the user asks to continue development, operate under this rule:

> Continue autonomously until one of these happens:
> 1. the current objective is complete and verified;
> 2. a genuinely ambiguous product decision is required;
> 3. progress is blocked by something outside the repo;
> 4. continuing would risk destructive changes.
>
> Do not stop just because one implementation step has completed.

Normally continue through implementation, tests, CI inspection, fixes, documentation/evidence updates, PR creation, merge-readiness, merge, and post-merge verification without pausing after intermediate steps.

## Agent behaviour

- Make the smallest coherent change that fully satisfies the current DEV item.
- Prefer implementation over speculative redesign.
- Use repository evidence as the source of truth.
- If documentation and code disagree, identify the mismatch and update the appropriate source.
- Do not invent completed work, test results, files, endpoints, integrations, CI status or merge state.
- When work spans phases, complete and verify the current dependency before starting dependent work.
- Do not stop merely because one implementation sub-step finished if the current DEV item remains incomplete.
- If two attempted fixes fail for the same underlying problem, perform root-cause analysis before another patch.
- Preserve enough state for another agent to resume safely.

## Development completion evidence

For every meaningful feature, bug fix, development idea or integration task:

- create or update its entry in `DEVELOPMENT.md`;
- keep PLANNED / IN PROGRESS / BLOCKED / AWAITING ACCEPTANCE / COMPLETE / DEFERRED truthful;
- record owner, branch, dependencies and integration status;
- record implementation files, tests, validation, CI and commit/PR evidence where applicable;
- separate development completion from user/business/external acceptance.

Never mark a coding task COMPLETE merely because an agent says it is complete.

Before marking COMPLETE, verify all applicable evidence:

- requested implementation exists;
- expected files changed;
- meaningful diff or equivalent implementation evidence exists;
- write/edit activity occurred where a code change was expected;
- branch HEAD changed where a code change was expected;
- relevant tests were added/updated or a no-test reason is recorded;
- relevant tests pass;
- build/lint/type-check/migration/other validation passes where applicable;
- CI passes where applicable;
- commit/PR evidence exists;
- merge/integration status is correct;
- post-merge verification is complete where applicable;
- acceptance criteria have been checked independently of CI;
- external/user acceptance is recorded separately.

An empty result, no write/edit action, unchanged branch HEAD, empty diff, missing requested validation, or budget exhaustion before acceptance criteria are satisfied means the task is **not complete**.

Green CI alone does not prove feature completion.

## CI and merge handling

Treat implementation, local validation, CI, acceptance, merge and post-merge verification as separate gates.

Before merge, review the complete diff against the DEV requirement and check for:

- unintended debug/temporary files;
- secrets;
- failing tests/build/lint/type-check;
- migration/deployment implications;
- stale documentation;
- unmet acceptance criteria.

After merge, verify the expected change exists on the intended target branch and record the resulting evidence in `DEVELOPMENT.md`.

## Recovery and interrupted work

If work is interrupted, blocked, budget-exhausted or otherwise incomplete, update `DEVELOPMENT.md` with:

- what was completed;
- what remains;
- the blocker;
- validation already performed;
- safest continuation point;
- next recommended action.

Do not turn partial work into COMPLETE for convenience.

When documentation conflicts with code, tests, Git history or CI, treat repository evidence as authoritative and reconcile the documentation.
