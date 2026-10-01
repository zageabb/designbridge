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


def node_snapshots(
    document: DesignBridgeDocument,
    node_ids: list[str],
) -> list[dict[str, Any]]:
    indexed = _index_nodes(document)
    snapshots: list[dict[str, Any]] = []
    for node_id in node_ids:
        entry = indexed.get(node_id)
        if entry is None:
            raise ValueError(f"unknown node_id: {node_id}")
        snapshots.append({
            "node_id": node_id,
            "scope": entry["scope"],
            "node": entry["node"],
        })
    return snapshots


def selective_pull_plan(
    before: DesignBridgeDocument,
    after: DesignBridgeDocument,
    node_ids: list[str],
) -> dict[str, Any]:
    diff = compare_documents(before, after)
    changed_by_id = {item["node_id"]: item for item in diff["changed"]}
    requested = list(dict.fromkeys(node_ids))

    if not requested:
        raise ValueError("at least one node_id is required")

    unsupported_requested = [
        node_id for node_id in requested
        if node_id not in changed_by_id
    ]
    if unsupported_requested:
        raise ValueError(
            "selective pull only supports changed existing nodes: "
            + ", ".join(unsupported_requested)
        )

    structural_requested = [
        node_id for node_id in requested
        if "scope" in changed_by_id[node_id]["properties"]
    ]
    if structural_requested:
        raise ValueError(
            "scope changes require a full pull: " + ", ".join(structural_requested)
        )

    selected = node_snapshots(after, requested)
    all_changed_ids = set(changed_by_id)
    selected_ids = set(requested)
    has_unsupported_outstanding = bool(
        diff["added"] or diff["removed"] or diff["tokens"]
        or any("scope" in item["properties"] for item in diff["changed"])
    )
    can_advance_revision = (
        not has_unsupported_outstanding
        and selected_ids == all_changed_ids
    )

    return {
        "selected": selected,
        "selected_node_ids": requested,
        "remaining_changed_node_ids": sorted(all_changed_ids - selected_ids),
        "can_advance_revision": can_advance_revision,
        "diff": diff,
    }
