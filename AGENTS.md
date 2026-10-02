# AGENTS.md — DesignBridge agent operating instructions

This file is the operational contract for AI/coding agents working on DesignBridge.

Read this file and `DEVELOPMENT.md` before making changes.

---

## Mission

Build DesignBridge as a reliable local-first bridge between AI-generated design intent and editable design tools.

Canonical rule:

> AI proposes structured DesignBridge intent. Deterministic code validates and applies it.

Do not turn DesignBridge into an opaque LLM-driven design mutator.

---

## Source of truth

The canonical DesignBridge document is the source of truth.

Current primary visual editor:

- Penpot.

Future adapters:

- Figma.
- React/HTML.

Penpot state may be read, compared, reconciled, and updated, but the plugin must preserve native design semantics where possible.

---

## Architecture rules

Always preserve these boundaries:

1. Canonical schema lives in `backend/app/models.py`.
2. Deterministic operations live in `backend/app/operations.py`.
3. Penpot snapshot comparison lives in `backend/app/penpot_sync.py`.
4. revision-level comparison lives in `backend/app/revision_diff.py`.
5. three-way conflict handling lives in `backend/app/three_way.py`.
6. whole-document coverage/link integrity lives in `backend/app/document_reconciliation.py`.
7. component/instance/definition/variant behavior lives in `backend/app/component_sync.py`.
8. HTTP orchestration lives in `backend/app/main.py`.
9. Penpot mutations live in `penpot-plugin/public/plugin.js`.
10. Penpot user-facing controls live in `penpot-plugin/public/index.html`.

Avoid placing business rules only in the UI.

---

## Non-negotiable synchronization rules

- Never silently overwrite newer canonical state.
- Pushes from Penpot must validate expected revision.
- Partial pulls/reconciliation must not advance the stored Penpot revision to a newer DesignBridge revision unless the full outstanding state is reconciled.
- Unsupported structural changes must be surfaced, not guessed.
- Unknown DesignBridge IDs must not be created implicitly from Penpot.
- Component copies must remain component copies.
- Do not detach/recreate components merely to simplify implementation.
- Component main changes and instance overrides are separate state layers.
- Existing instance overrides must survive compatible definition changes.
- Variant switching must be planned/validated before mutation.
- Incompatible variant switches must be blocked before Penpot is changed.
- If a multi-step Penpot/canonical mutation cannot complete, prefer rollback or leave the canonical state unchanged.
- Preserve manual JSON import/export fallback while direct sync is still evolving.

---

## Current release state

Merged into `main` through:

```text
v0.16
main commit: 07c24f5c2e8b7737b578c2c7cfaed63bfa0e551a
```

Current active milestone:

```text
v0.17 — component variants and safe switching
branch: feature/v0.17-component-variants
PR: #17
branch head when documented: af97201f078f81002f8743361b9b292ebb79be59
```

v0.17 includes:

- canonical `variant_group`.
- canonical `variant_properties`.
- stable child `variant_slot`.
- variant family reporting.
- safe override remapping.
- compatibility planning.
- guarded Penpot native component swap.
- canonical commit after Penpot succeeds.
- rollback attempt on final commit race.
- revision-safe advancement.

Before any further work, check the actual current branch, PR head, and CI status. Do not assume these values are still current.

---

## Completed capability summary

### Core

- canonical document model.
- validation.
- deterministic operations.
- local Ollama operation proposal.
- project persistence.
- revisions.
- undo/redo.
- history.

### Penpot sync

- direct local API sync.
- selection snapshots.
- name/position/size/text/direct-fill sync.
- flex direction/gap/padding/alignment sync.
- revision state.
- stale-push blocking.
- passive polling.
- revision diffs.
- selective pull.
- three-way review.
- property-level resolution.
- whole-document reconciliation.

### Components

- native component creation.
- instance creation.
- component relationship discovery.
- detached/swapped instance detection.
- safe instance overrides.
- safe override capture.
- canonical override reapplication.
- main definition review.
- main definition capture.
- main-only canonical pull.
- protected instance overrides.

### Variants

- canonical variant families.
- variant properties.
- variant slots.
- compatibility planning.
- override remapping.
- guarded switching.

---

## Current known architectural risk

Numeric revision alone is not a durable identity.

Scenario:

1. A is revision 1.
2. B is revision 2.
3. Penpot stores revision 2.
4. server undo returns to revision 1.
5. C is saved and reuses revision 2.
6. stale Penpot still says revision 2.

Numeric equality can incorrectly imply in_sync.

Preferred fix:

- deterministic canonical JSON.
- SHA-256 content/revision token.
- expose token from current/status/save/load.
- store token in Penpot plugin data.
- require expected token on mutating endpoints.
- status should return diverged/conflict when revision numbers match but tokens differ.

This should be prioritized before sync grows substantially more destructive.

---

## Variant rules

For canonical variants:

- components in a family share `variant_group`.
- each component has a unique `variant_properties` combination within the group.
- corresponding children across variants should use the same `variant_slot`.
- child node IDs remain globally unique.
- overrides are remapped by `variant_slot`, never by display name alone.
- text override can only map to a text child.
- direct fill override must not map to a token-bound target child.
- missing target slot makes the switch incompatible.
- switching to a component outside the source family is invalid.

Current Penpot behavior:

- grouped canonical variants are switched with native `swapComponent`.
- native Penpot VariantContainer integration is not yet automatic.
- future work may use native `switchVariant` when a Penpot-native family is detected.

---

## Component rules

Component definitions:

- only safe main properties currently synchronize: name, text, direct fill.
- structural main edits are not yet supported.
- only main roots/members receive canonical definition pulls.
- copy members must not be updated as standalone canonical nodes.

Instance overrides:

- currently safe: text, name, direct fill.
- stored on the canonical instance as:
  `overrides[component_child_id][property] = value`.
- instance overrides must remain intact when main definitions change.
- canonical overrides must be reapplied when an instance is created or refreshed.

---

## Whole-document reconciliation rules

Coverage calculations should:

- count canonical nodes expected in Penpot.
- ignore component copy members as standalone duplicates.
- report missing nodes.
- report unknown DesignBridge IDs.
- report duplicate standalone links.
- report page-location mismatches.
- include document-wide conflict summaries.

New imports should tag pages with canonical page IDs.

Older files without tags may fall back to page-name matching.

---

## Coding workflow

When continuing development:

1. inspect current PR/branch/CI.
2. if current milestone is green, merge with expected head SHA.
3. create a fresh branch from updated `main`.
4. implement the next coherent slice.
5. add regression tests at the same time.
6. update milestone docs.
7. update `DEVELOPMENT.md` and `AGENTS.md`.
8. open PR.
9. check CI.
10. inspect and fix failures directly.

Do not ask for confirmation for routine continuation if the user says “continue”.

---

## Testing expectations

Every new sync rule needs tests.

Minimum expectations:

- happy path.
- stale revision path for mutating APIs.
- missing/invalid input.
- no-op behavior.
- conflict/incompatibility behavior.
- preservation of unaffected canonical state.
- preservation of instance overrides where relevant.
- regression for any bug found in CI.

Keep tests deterministic.

Never “fix” CI by weakening a valid test unless the intended behavior has deliberately changed and is documented.

---

## API behavior conventions

Prefer:

- 200 for successful review/plan/no-op responses.
- 409 for revision conflicts.
- 422 for invalid user/design input or unsupported/incompatible operations.
- 404 for missing project/revision resources.

Mutation responses should make clear:

- whether anything changed.
- resulting revision.
- resulting canonical document where useful.
- planned/applied changes.
- conflict details where blocked.

---

## Penpot plugin behavior conventions

- Do not visibly switch pages just to inspect the file.
- Use document/page enumeration when possible.
- preserve current selection/page where possible.
- prefer plugin data for stable DesignBridge identity.
- use native component APIs instead of flattening.
- keep JSON fallback available.
- provide clear user-facing status for partial vs complete reconciliation.
- do not claim “in sync” after a partial update.

---

## Documentation maintenance

Every completed development slice must update:

- `DEVELOPMENT.md`
- `AGENTS.md`
- a milestone-specific document under `docs/` when the change is substantial.

Keep these files current with:

- merged versions.
- current active branch/PR.
- current architecture.
- new invariants.
- known risks.
- next milestone.

Future agents should be able to understand the project without reading prior chat history.

---

## Next likely work after v0.17

Preferred sequence:

1. finish and merge v0.17 when CI is green.
2. implement durable revision token/fingerprint unless explicitly deprioritized.
3. native Penpot VariantContainer discovery/mapping.
4. native `switchVariant(...)` path with component-swap fallback.
5. structural sync only after revision identity is hardened.
6. richer tokens/typography.
7. Figma adapter.
8. React/HTML output.

Do not skip revision identity hardening before adding substantially more destructive synchronization.
