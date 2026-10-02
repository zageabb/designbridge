# DesignBridge Development Guide

DesignBridge is a local-first bridge between AI-generated design intent and editable design tools.

Its core rule is:

> LLMs propose structured DesignBridge data and deterministic code validates, stores, synchronizes, and applies it.

The canonical DesignBridge model is the source of truth. Penpot is the primary editable visual surface today. Figma and React/HTML remain target adapters.

---

## Architecture

```text
                 DesignBridge
                     AI
                     │
               Design Model
                     │
       ┌─────────────┼─────────────┐
       ↓             ↓             ↓
    Penpot         Figma        React
   editing       handoff       output
```

Canonical mappings:

- Frame -> Penpot Board -> Figma Frame
- horizontal/vertical layout -> Penpot Flex -> Figma Auto Layout
- Component -> Penpot Component -> Figma Component
- Instance -> Penpot component copy -> Figma Instance
- Variant -> canonical variant family -> Penpot variant/component family -> Figma component variant
- color token -> Penpot token/color -> Figma Variable
- typography/spacing/radius -> token -> Style/Variable
- Text -> Text -> Text
- Vector -> SVG/path -> Vector
- Image -> Image -> Image
- Prototype -> interaction/prototype interaction

The canonical file format remains `format: designbridge`, schema `version: 0.1`. Application release numbers are independent from the schema version.

---

## Main project structure

Key areas:

- `backend/app/models.py` — canonical DesignBridge schema.
- `backend/app/operations.py` — deterministic design operations.
- `backend/app/storage.py` — SQLite project/revision persistence.
- `backend/app/penpot_sync.py` — supported Penpot snapshot -> canonical comparison.
- `backend/app/revision_diff.py` — revision diff and selective pull planning.
- `backend/app/three_way.py` — base/local/latest conflict review and property resolution.
- `backend/app/document_reconciliation.py` — whole-document coverage and link integrity.
- `backend/app/component_sync.py` — component, instance, definition, override, and variant logic.
- `backend/app/main.py` — FastAPI endpoints.
- `penpot-plugin/public/plugin.js` — Penpot-side runtime integration.
- `penpot-plugin/public/index.html` — Penpot plugin UI.
- `backend/tests/` — regression/API tests.
- `docs/` — milestone-specific documentation.

Local API default used by the Penpot plugin:

```text
http://127.0.0.1:5087
```

---

## Development history

### v0.1 — Initial bridge

Implemented:

- FastAPI backend.
- Pydantic canonical model.
- Static web UI.
- Penpot plugin.
- tests and CI.
- sample design.
- initial docs.

Merged main commit:

```text
090c41e824676f2a3e379fc74e5844abae4c5d31
```

### v0.2 — Typed tokens and Penpot components

Implemented:

- typed tokens.
- component/instance semantics.
- native Penpot components.
- local color mapping.
- preview/docs improvements.

Merged main commit:

```text
f76aafac144d0b6bf3ffff2f594a37337465a877
```

### v0.3 — Deterministic operation engine

Implemented operations:

- `update_node`
- `add_node`
- `remove_node`
- `move_node`
- `set_color_token`
- `set_spacing_token`

Added:

- local Ollama operation proposer.
- `POST /api/operations/apply`
- `POST /api/operations/propose`
- AI proposal UI.

Merged main commit:

```text
ea03df74661092830604ce50b137c6ab71438fe7
```

### v0.4 — Project/revision persistence

Implemented:

- SQLite projects.
- immutable revision history.
- load/save/history.
- undo/redo.
- selection-aware AI.
- Penpot selection snapshots.

Merged main commit:

```text
877b0bbbabae2a895563823db478fe99779421a4
```

### v0.5 — Safe Penpot -> DesignBridge sync

Added supported reverse-sync properties:

- name.
- x/y.
- width/height.
- text.
- direct fill where no fill token is bound.

Unknown IDs are ignored.

No supported differences raises:

```text
no supported Penpot changes detected
```

Merged main commit:

```text
da881ab631b65995d6e1882eb477a2c280651887
```

### v0.6 — Direct local sync

Added:

- CORS for localhost and Penpot cloud.
- `GET /api/penpot/projects/{project_id}/current`
- `POST /api/penpot/projects/{project_id}/selection`
- Penpot Test connection.
- Pull latest.
- Push selection.
- remembered local API URL.
- manual JSON fallback retained.

Merged main commit:

```text
b0839b6fada517f2c4ba2c907d544f188cb7ce97
```

### v0.7 — Semantic flex layout sync

Added Penpot <-> canonical sync for:

- layout direction.
- gap.
- padding.
- alignment.

Only applies where canonical layout already exists.

Merged main commit:

```text
5f145e81da06455aaf05e4679266cda3a6869b51
```

### v0.8 — Revision-aware conflict blocking

Added:

- status endpoint.
- states: unknown / in_sync / behind / ahead.
- push requires `expected_revision`.
- stale push returns HTTP 409 `revision_conflict`.
- Penpot stores DesignBridge document ID and revision.

Merged main commit:

```text
7a41a283195183122d0a45a50f5df09c1528c9c5
```

Known architectural caveat still outstanding:

Revision numbers can be reused after undo followed by a new save. Numeric revision alone is therefore not a fully durable revision identity.

Planned hardening:

- deterministic canonical JSON.
- SHA-256 revision token.
- plugin stores revision token.
- status/push/selective-pull/review validate both revision and token.
- same numeric revision with different content must become diverged/conflict, never in_sync.

### v0.9 — Passive revision awareness

Added:

- 30-second Penpot status polling.
- update available indicator.
- Review latest.
- latest description/revision state.
- no destructive auto-pull.

Merged main commit:

```text
afc478be6342f3c75db3d6cf7dd84fc1b0d365ad
```

### v0.10 — Canonical revision diffs

Added:

- node-level added/removed/changed diff.
- token section change reporting.
- `GET /api/penpot/projects/{project_id}/diff`
- Penpot diff rendering.

Merged main commit:

```text
2c9c4de1fe201ba37ed034a1e6f7a6be37da939a
```

### v0.11 — Safe selective pull

Added:

- `POST /api/penpot/projects/{project_id}/selective-pull`
- changed-node selection.
- selective Penpot updates.
- revision advancement only when all safe outstanding changes are reconciled.
- structural/token unsupported changes block full advancement.

Merged main commit:

```text
93c06a786a96eb91d753b38aa666a9c2bdf080cd
```

### v0.12 — Three-way conflict review

Added Base / Local / Latest comparison.

Classifications:

- conflict.
- same_change.
- local_only.
- remote_only.

Added:

```text
POST /api/penpot/projects/{project_id}/three-way-review
```

Penpot UI added:

- Check local conflicts.
- base/Penpot/DesignBridge value display.

Merged main commit:

```text
254500b21fc60c5224dae5e84905a8614fc7f497
```

### v0.13 — Property-level resolution

Added explicit per-property choices:

- Keep Penpot.
- Use DesignBridge.

Behavior:

- Keep Penpot writes local values into canonical DesignBridge.
- Use DesignBridge applies only that canonical property to Penpot.
- all outstanding properties must be resolved before reconciliation is complete.
- if every choice is remote, no redundant canonical revision is created.
- absent Penpot snapshot fields are not treated as null edits.

Merged main commit:

```text
bc934a1a033449cb7b0db3fe16f11ebac0df3e1d
```

### v0.14 — Whole-document reconciliation

Expanded review from current page to whole Penpot file.

Added:

- all-page linked-shape snapshotting.
- stable DesignBridge page IDs stored in Penpot plugin data.
- page-name fallback for older files.
- overall and per-page coverage.
- missing node reporting.
- unknown linked ID reporting.
- duplicate linked ID reporting.
- page-location mismatch reporting.
- document-wide three-way conflict counts.
- cross-page property updates.

Merged main commit:

```text
c342b31adeed850a1b30c453706fc8974e7d0d1e
```

### v0.15 — Component instance semantics and overrides

Added native Penpot component relationship awareness.

Detects:

- main roots.
- main members.
- copy roots.
- copy members.
- detached/basic shapes.
- wrong/swapped component links.

Canonical instance overrides added for safe properties:

- text.
- name.
- direct fill.

Added:

- Review components.
- Capture safe overrides.
- revision protection.
- canonical override reapplication into Penpot.
- copy members excluded from standalone duplicate-link coverage.

Merged main commit:

```text
ee8d58d83560533c6a061d3f18e50035ce0ea3dc
```

### v0.16 — Component definition synchronization

Added safe component-main synchronization.

Supported main-definition changes:

- name.
- text.
- direct fill when not token-bound.

Added:

- Review definitions.
- Capture Penpot definitions.
- Use DesignBridge definitions.
- main-root/main-member-only Penpot updates.
- protected instance override visibility.
- instance overrides preserved when component definitions change.
- component-only pulls do not falsely advance the whole Penpot revision.

Merged main commit:

```text
07c24f5c2e8b7737b578c2c7cfaed63bfa0e551a
```

### v0.17 — Component variants and safe switching

Current development branch:

```text
feature/v0.17-component-variants
```

Current PR:

```text
#17 — DesignBridge v0.17 — component variants and safe switching
```

Current branch head at time of this document update:

```text
af97201f078f81002f8743361b9b292ebb79be59
```

Implemented:

- `variant_group` on component/instance nodes.
- `variant_properties` on components.
- `variant_slot` on component children.
- duplicate variant property combinations rejected.
- stable override remapping across variants by `variant_slot`.
- compatibility planning before switch.
- rejection when target variant lacks a required slot.
- rejection for incompatible type/property remapping.
- direct fill override blocked when target child is token-bound.
- variant family reporting.
- Penpot Review variants UI.
- native Penpot component swap.
- canonical commit only after Penpot swap succeeds.
- rollback attempt to original component if canonical commit loses a revision race.
- revision advancement only after successful canonical commit.

APIs:

```text
GET  /api/penpot/projects/{project_id}/variants
POST /api/penpot/projects/{project_id}/variant-switch-plan
POST /api/penpot/projects/{project_id}/commit-variant-switch
```

Current boundary:

v0.17 models variants canonically and switches compatible component definitions using Penpot component swapping.

It does not yet automatically create/restructure Penpot native VariantContainers.

Next likely milestone:

- native Penpot variant-container discovery.
- map native Penpot variant properties to `variant_group` / `variant_properties`.
- use Penpot native `switchVariant(...)` where available.
- retain component-swap fallback for grouped components that are not native Penpot variants.

---

## Safety and synchronization rules

These rules are architectural, not optional.

1. DesignBridge canonical data is the source of truth.
2. LLMs must not directly mutate Penpot internal JSON/state.
3. All mutations pass through deterministic operations or dedicated validated sync functions.
4. Stale Penpot writes must return 409 rather than silently overwrite newer DesignBridge state.
5. Partial reconciliation must never mark the whole file synchronized.
6. Component copies must not be flattened just to simplify sync.
7. Component main definition state and instance override state are separate.
8. Instance overrides must survive compatible component definition updates.
9. Variant switching must be compatibility-checked before mutation.
10. Structural/destructive operations must be explicitly supported before use.
11. Unsupported changes should be surfaced, not guessed.
12. Tests must cover every new sync or conflict rule before merge.

---

## Known backlog / unresolved items

High priority:

- durable revision SHA/token identity to prevent false in_sync after revision-number reuse.
- native Penpot VariantContainer integration.
- stronger multi-page update/result confirmation.
- graceful no-change push response instead of 422.
- configurable CORS for self-hosted Penpot.
- verify Penpot plugin permissions such as localStorage against current plugin docs.
- ensure run-local script and plugin API port remain aligned.

Structural sync backlog:

- add/remove nodes.
- reparenting.
- hierarchy changes.
- component child structural edits.
- richer layout structural sync.
- token-bound style reconciliation.
- typography token system.
- prototypes/interactions.
- assets/images/vectors.
- multi-page creation/deletion reconciliation.

Adapter backlog:

- Figma adapter.
- Figma Variables/styles.
- Figma component/variant mapping.
- React/HTML export.
- developer-friendly code generation.

Potential operation bug to keep regression coverage around:

- `move_node` target-index semantics when moving within the same container after removal.

---

## Autonomous continuation rule

When the user asks to continue development, operate under this rule:

> Continue autonomously until one of these happens:
> 1. the current objective is complete and verified;
> 2. a genuinely ambiguous product decision is required;
> 3. progress is blocked by something outside the repo;
> 4. continuing would risk destructive changes.
>
> Do not stop just because one implementation step has completed.

This means a coding agent should normally continue through implementation, tests, CI inspection, fixes, documentation updates, PR creation, and merge-readiness checks without pausing after each intermediate step. Stop only when one of the conditions above is actually reached.

---

## CI and branch workflow

Normal workflow:

1. start from current `main`.
2. create a fresh feature branch per milestone.
3. implement code + tests + docs together.
4. open PR.
5. run CI.
6. inspect/fix failures.
7. merge only when CI is green.
8. immediately create the next fresh feature branch for continued development.

Do not continue stacking unrelated milestones on an already merged feature branch.

GitHub CI currently runs backend tests and compile checks.

Before merge:

- check PR head SHA.
- ensure CI is completed and successful.
- merge using the expected head SHA.
- create the next branch from updated main.

---

## Documentation rule

Every meaningful development milestone must update both:

- `DEVELOPMENT.md`
- `AGENTS.md`

Milestone-specific details should also be added under `docs/`.

These root files are the authoritative quick-start context for future developers and coding agents. Do not rely on chat history to reconstruct project state.
