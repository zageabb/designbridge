from __future__ import annotations

from typing import Any

from .models import DesignBridgeDocument, DesignNode


def _index_nodes(document: DesignBridgeDocument) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    def walk(node: DesignNode, scope: str) -> None:
        result[node.id] = {
            "scope": scope,
            "node": node.model_dump(mode="json", exclude_none=True),
        }
        for child in node.children:
            walk(child, scope)

    for component in document.components:
        walk(component, "component")
    for page in document.pages:
        for node in page.children:
            walk(node, f"page:{page.id}")
    return result


def _property_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    ignored = {"children"}
    keys = (set(before) | set(after)) - ignored
    changed: dict[str, dict[str, Any]] = {}
    for key in sorted(keys):
        old = before.get(key)
        new = after.get(key)
        if old != new:
            changed[key] = {"before": old, "after": new}
    return changed


def compare_documents(
    before: DesignBridgeDocument,
    after: DesignBridgeDocument,
) -> dict[str, Any]:
    before_nodes = _index_nodes(before)
    after_nodes = _index_nodes(after)

    added = []
    removed = []
    changed = []

    for node_id in sorted(after_nodes.keys() - before_nodes.keys()):
        entry = after_nodes[node_id]
        added.append({
            "node_id": node_id,
            "name": entry["node"].get("name"),
            "type": entry["node"].get("type"),
            "scope": entry["scope"],
        })

    for node_id in sorted(before_nodes.keys() - after_nodes.keys()):
        entry = before_nodes[node_id]
        removed.append({
            "node_id": node_id,
            "name": entry["node"].get("name"),
            "type": entry["node"].get("type"),
            "scope": entry["scope"],
        })

    for node_id in sorted(before_nodes.keys() & after_nodes.keys()):
        left = before_nodes[node_id]
        right = after_nodes[node_id]
        properties = _property_diff(left["node"], right["node"])
        if left["scope"] != right["scope"]:
            properties["scope"] = {
                "before": left["scope"],
                "after": right["scope"],
            }
        if properties:
            changed.append({
                "node_id": node_id,
                "name": right["node"].get("name") or left["node"].get("name"),
                "type": right["node"].get("type") or left["node"].get("type"),
                "properties": properties,
            })

    token_changes: dict[str, Any] = {}
    before_tokens = before.tokens.model_dump(mode="json")
    after_tokens = after.tokens.model_dump(mode="json")
    for section in sorted(set(before_tokens) | set(after_tokens)):
        if before_tokens.get(section) != after_tokens.get(section):
            token_changes[section] = {
                "before": before_tokens.get(section),
                "after": after_tokens.get(section),
            }

    summary = {
        "added": len(added),
        "removed": len(removed),
        "changed": len(changed),
        "token_sections_changed": len(token_changes),
    }

    return {
        "summary": summary,
        "added": added,
        "removed": removed,
        "changed": changed,
        "tokens": token_changes,
    }
