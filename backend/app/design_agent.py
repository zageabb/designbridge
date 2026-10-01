from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .models import DesignBridgeDocument
from .operations import OperationBatch


SYSTEM_PROMPT = """You are the DesignBridge design editor.
Return ONLY one JSON object matching this shape:
{
  "description": "short summary",
  "operations": [
    {
      "action": "update_node|add_node|remove_node|move_node|set_color_token|set_spacing_token",
      "...": "fields required for that operation"
    }
  ]
}

Rules:
- Modify the supplied document with the smallest sensible set of operations.
- Reuse existing node IDs when editing.
- New node IDs must be concise, stable, lowercase kebab-case and unique.
- Never invent a component_id that is not declared in document.components.
- Prefer layout changes over absolute x/y changes when a parent has layout.
- Do not return markdown or commentary.
"""


def build_design_prompt(document: DesignBridgeDocument, instruction: str, selection_ids: list[str] | None = None) -> str:
    compact = document.model_dump(mode="json", exclude_none=True)
    return (
        SYSTEM_PROMPT
        + "\nUSER INSTRUCTION:\n"
        + instruction.strip()
        + "\nSELECTED DESIGNBRIDGE IDS:\n"
        + json.dumps(selection_ids or [])
        + "\nCURRENT DOCUMENT:\n"
        + json.dumps(compact, separators=(",", ":"))
    )


def parse_operation_batch(raw: str) -> OperationBatch:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    data = json.loads(text)
    return OperationBatch.model_validate(data)


async def propose_operations(
    document: DesignBridgeDocument,
    instruction: str,
    *,
    base_url: str | None = None,
    model: str | None = None,
    selection_ids: list[str] | None = None,
) -> OperationBatch:
    ollama_url = (
        base_url
        or os.getenv("DESIGNBRIDGE_OLLAMA_URL")
        or "http://127.0.0.1:11434"
    ).rstrip("/")
    ollama_model = (
        model
        or os.getenv("DESIGNBRIDGE_OLLAMA_MODEL")
        or "qwen3:14b"
    )

    payload: dict[str, Any] = {
        "model": ollama_model,
        "prompt": build_design_prompt(document, instruction, selection_ids),
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }

    timeout = httpx.Timeout(120.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{ollama_url}/api/generate", json=payload)
        response.raise_for_status()
        body = response.json()

    raw = body.get("response")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Ollama returned an empty design-operation response")
    return parse_operation_batch(raw)
