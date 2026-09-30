# DesignBridge Architecture

## Goal

DesignBridge provides a stable design contract between conversational AI and visual/product-development tools. Penpot is the first visual editor, but Penpot's internal representation is deliberately not the source of truth.

## Core flow

```text
ChatGPT / Ollama
      |
      v
DesignBridge document (portable JSON)
      |
      +-- Pydantic validation
      +-- browser preview
      +-- structured change operations (next)
      |
      +-- Penpot adapter/plugin
      +-- React/HTML adapter (later)
      +-- Figma adapter (later)
```

## Why a canonical model

The canonical model follows the proven local-app pattern used elsewhere in this account: AI proposes structured data; deterministic code validates and materialises the final artifact.

This prevents:

- model output being coupled to a particular Penpot release;
- arbitrary AI code from mutating a design file;
- export paths becoming dependent on SQLite row IDs;
- a future Figma or code exporter needing to reverse-engineer Penpot data.

## v0.1 document model

The initial model supports:

- document identity;
- pages;
- frames;
- rectangles;
- text;
- component and instance placeholders;
- horizontal/vertical layout intent;
- fill, position and dimensions;
- design-token storage;
- assets and metadata extension points.

The v0.1 schema is intentionally small. New node semantics should be added only when they can be mapped cleanly to Penpot and later to developer-grade Figma/code outputs.

## Stable identity

Every page/node has a portable string ID. The Penpot adapter stores the originating ID as plugin data so future round-trip updates can find and modify the same object rather than regenerating an entire page.

## Penpot adapter

The first plugin uses the official Penpot plugin API and creates native:

- pages;
- boards;
- flex layouts;
- text nodes;
- rectangles.

The adapter is deterministic. The AI produces DesignBridge JSON; it does not produce raw Penpot API calls.

## Next architectural slices

1. JSON Schema export and stronger semantic validation.
2. Layout-aware browser preview rather than position-only preview.
3. Design operations/diffs and undoable revisions.
4. Component creation and native component instances in Penpot.
5. Design tokens -> Penpot token/library mapping.
6. Ollama/ChatGPT-facing design tools.
7. Read-back from Penpot using stored DesignBridge IDs.
8. Direct local push service.
9. Figma adapter and developer-handoff acceptance suite.
10. React/HTML generation from the same canonical model.
