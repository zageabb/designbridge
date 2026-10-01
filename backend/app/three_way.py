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
    provided = snapshot.model_fields_set
    props: dict[str, Any] = {}
    if "name" in provided:
        props["name"] = snapshot.name
    if base.x is not None and "x" in provided:
        props["x"] = snapshot.x
    if base.y is not None and "y" in provided:
        props["y"] = snapshot.y
    if base.width is not None and "width" in provided:
        props["width"] = snapshot.width
    if base.height is not None and "height" in provided:
        props["height"] = snapshot.height
    if base.type == "text" and "text" in provided:
        props["text"] = snapshot.text
    if base.fill_token is None and "fill" in provided:
        props["fill"] = snapshot.fill
    if base.layout is not None:
        layout_fields = {
            "layout_direction",
            "layout_gap",
            "layout_padding",
            "layout_align",
        }
        if provided & layout_fields:
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

        for key in sorted(set(base_props) | set(latest_props)):
            base_value = base_props.get(key)
            has_local = key in local_props
            local_value = local_props.get(key, base_value)
            latest_value = latest_props.get(key)

            local_changed = has_local and local_value != base_value
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


def resolution_plan(
    base: DesignBridgeDocument,
    latest: DesignBridgeDocument,
    snapshots: list[PenpotShapeSnapshot],
    resolutions: list[dict[str, str]],
) -> dict[str, Any]:
    review = three_way_review(base, latest, snapshots)
    review_by_node = {item["node_id"]: item for item in review["nodes"]}

    requested: dict[tuple[str, str], str] = {}
    for item in resolutions:
        node_id = str(item.get("node_id") or "").strip()
        property_name = str(item.get("property") or "").strip()
        choice = str(item.get("choice") or "").strip()
        if not node_id or not property_name or choice not in {"local", "remote"}:
            raise ValueError("each resolution requires node_id, property, and choice local|remote")
        requested[(node_id, property_name)] = choice

    required: set[tuple[str, str]] = set()
    for node in review["nodes"]:
        for property_name, detail in node["properties"].items():
            if detail["classification"] in {"conflict", "local_only", "remote_only"}:
                required.add((node["node_id"], property_name))

    unknown = sorted(set(requested) - required)
    if unknown:
        raise ValueError(
            "resolution does not match an outstanding property: "
            + ", ".join(f"{node}.{prop}" for node, prop in unknown)
        )

    remote_updates: list[dict[str, Any]] = []
    local_changes: dict[str, dict[str, Any]] = {}

    for (node_id, property_name), choice in requested.items():
        detail = review_by_node[node_id]["properties"][property_name]
        if choice == "remote":
            remote_updates.append({
                "node_id": node_id,
                "property": property_name,
                "value": detail["latest"],
            })
        else:
            local_changes.setdefault(node_id, {})[property_name] = detail["local"]

    unresolved = sorted(required - set(requested))
    return {
        "review": review,
        "remote_updates": remote_updates,
        "local_changes": local_changes,
        "resolved": [
            {"node_id": node, "property": prop, "choice": choice}
            for (node, prop), choice in sorted(requested.items())
        ],
        "unresolved": [
            {"node_id": node, "property": prop}
            for node, prop in unresolved
        ],
        "complete": not unresolved,
    }
