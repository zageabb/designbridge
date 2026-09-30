# DesignBridge

**Local AI design workspace bridging ChatGPT/local LLMs, Penpot, developer handoff and later Figma/code export.**

DesignBridge uses a canonical, portable JSON design model as the contract between AI-generated designs and visual design tools. The first target is Penpot: designs can be generated as DesignBridge JSON, validated, previewed locally, and imported by a Penpot plugin as editable native design objects.

## Core principles

- **JSON-first** — AI produces a stable DesignBridge document, not raw Penpot internals.
- **Deterministic adapters** — application code translates validated JSON into Penpot/Figma/code outputs.
- **Developer-grade structure** — named layers, components, instances, layout semantics and design tokens are retained.
- **Local-first** — local Ollama support is a first-class path.
- **Portable** — designs are not tied to local database IDs.
- **Reviewable** — design changes can be represented as structured operations and eventually diffed/undone.

## Initial architecture

```text
ChatGPT / Ollama
      |
      v
DesignBridge JSON
      |
      +--> validation
      +--> local preview
      +--> Penpot plugin import
      +--> React/HTML adapter (later)
      +--> Figma adapter (later)
```

Development starts in small verified milestones. The first milestone proves the canonical JSON model, local preview/API and native Penpot import path.
