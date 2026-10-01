from __future__ import annotations

from typing import Any

from .models import DesignBridgeDocument, DesignNode
from .penpot_sync import PenpotShapeSnapshot


def _index_nodes(document: DesignBridgeDocument) -> dict[str, DesignNode]:
    result: dict[str, DesignNode] = {}

    def walk(node: DesignNode) -> None:
        result[node.id] = node
        for child in node.children:
            walk(child)

    for component in document.components:
        walk(component)
    for page in document.pages:
        for node in page.children:
            walk(node)
    return result


def _canonical_properties(node: DesignNode) -> dict[str, Any]:
    props: dict[str, Any] = {
        "name": node.name,
        "x": node.x,
        "y": node.y,
        "width": node.width,
        "height": node.height,
    }
    if node.type == "text":
        props["text"] = node.text
    if node.fill_token is None:
        props["fill"] = node.fill
    if node.layout is not None:
        props["layout"] = node.layout.model_dump(mode="json")
    return props


def _snapshot_properties(snapshot: PenpotShapeSnapshot, base: DesignNode) -> dict[str, Any]:
    props: dict[str, Any] = {
        "name": snapshot.name,
        "x": snapshot.x if base.x is not None else None,
        "y": snapshot.y if base.y is not None else None,
        "width": snapshot.width if base.width is not None else None,
        "height": snapshot.height if base.height is not None else None,
    }
    if base.type == "text":
        props["text"] = snapshot.text
    if base.fill_token is None:
        props["fill"] = snapshot.fill
    if base.layout is not None:
        layout = base.layout.model_dump(mode="json")
        if snapshot.layout_direction in {"horizontal", "vertical"}:
            layout["direction"] = snapshot.layout_direction
        if snapshot.layout_gap is not None:
            layout["gap"] = snapshot.layout_gap
        if snapshot.layout_padding is not None:
            layout["padding"] = snapshot.layout_padding
        if snapshot.layout_align in {"start", "center", "end", "stretch"}:
            layout["align"] = snapshot.layout_align
        props["layout"] = layout
    return props


def three_way_review(
    base: DesignBridgeDocument,
    latest: DesignBridgeDocument,
    snapshots: list[PenpotShapeSnapshot],
) -> dict[str, Any]:
    base_nodes = _index_nodes(base)
    latest_nodes = _index_nodes(latest)
    reviews: list[dict[str, Any]] = []

    for snapshot in snapshots:
        node_id = snapshot.designbridge_id
        base_node = base_nodes.get(node_id)
        latest_node = latest_nodes.get(node_id)
        if base_node is None or latest_node is None:
            continue

        base_props = _canonical_properties(base_node)
        local_props = _snapshot_properties(snapshot, base_node)
        latest_props = _canonical_properties(latest_node)

        properties: dict[str, Any] = {}
        conflicts: list[str] = []
        local_only: list[str] = []
        remote_only: list[str] = []
        same_change: list[str] = []

        for key in sorted(set(base_props) | set(local_props) | set(latest_props)):
            base_value = base_props.get(key)
            local_value = local_props.get(key)
            latest_value = latest_props.get(key)

            local_changed = local_value != base_value
            remote_changed = latest_value != base_value
            conflict = local_changed and remote_changed and local_value != latest_value

            if not (local_changed or remote_changed):
                continue

            if conflict:
                classification = "conflict"
                conflicts.append(key)
            elif local_changed and remote_changed:
                classification = "same_change"
                same_change.append(key)
            elif local_changed:
                classification = "local_only"
                local_only.append(key)
            else:
                classification = "remote_only"
                remote_only.append(key)

            properties[key] = {
                "base": base_value,
                "local": local_value,
                "latest": latest_value,
                "local_changed": local_changed,
                "remote_changed": remote_changed,
                "conflict": conflict,
                "classification": classification,
            }

        if properties:
            reviews.append({
                "node_id": node_id,
                "name": latest_node.name,
                "properties": properties,
                "conflicts": conflicts,
                "local_only": local_only,
                "remote_only": remote_only,
                "same_change": same_change,
            })

    return {
        "summary": {
            "nodes_reviewed": len(reviews),
            "nodes_with_conflicts": sum(bool(item["conflicts"]) for item in reviews),
            "conflict_properties": sum(len(item["conflicts"]) for item in reviews),
            "local_only_properties": sum(len(item["local_only"]) for item in reviews),
            "remote_only_properties": sum(len(item["remote_only"]) for item in reviews),
            "same_change_properties": sum(len(item["same_change"]) for item in reviews),
        },
        "nodes": reviews,
    }
