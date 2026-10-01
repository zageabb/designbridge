from __future__ import annotations

from typing import Any

from .models import DesignBridgeDocument, DesignNode
from .penpot_sync import PenpotShapeSnapshot


SAFE_OVERRIDE_PROPERTIES = ("name", "text", "fill")


def _node_index(document: DesignBridgeDocument) -> dict[str, DesignNode]:
    nodes: dict[str, DesignNode] = {}

    def walk(node: DesignNode) -> None:
        nodes[node.id] = node
        for child in node.children:
            walk(child)

    for component in document.components:
        walk(component)
    for page in document.pages:
        for node in page.children:
            walk(node)
    return nodes


def _component_children(component: DesignNode) -> dict[str, DesignNode]:
    children: dict[str, DesignNode] = {}

    def walk(node: DesignNode) -> None:
        children[node.id] = node
        for child in node.children:
            walk(child)

    for child in component.children:
        walk(child)
    return children


def _safe_snapshot_overrides(
    component: DesignNode,
    members: list[PenpotShapeSnapshot],
) -> dict[str, dict[str, Any]]:
    children = _component_children(component)
    overrides: dict[str, dict[str, Any]] = {}

    for snapshot in members:
        child = children.get(snapshot.designbridge_id)
        if child is None:
            continue

        provided = snapshot.model_fields_set
        values: dict[str, Any] = {}

        if "name" in provided and snapshot.name is not None and snapshot.name != child.name:
            values["name"] = snapshot.name

        if (
            child.type == "text"
            and "text" in provided
            and snapshot.text is not None
            and snapshot.text != child.text
        ):
            values["text"] = snapshot.text

        if (
            child.fill_token is None
            and "fill" in provided
            and snapshot.fill is not None
            and snapshot.fill != child.fill
        ):
            values["fill"] = snapshot.fill

        if values:
            overrides[child.id] = values

    return overrides


def component_instance_report(
    document: DesignBridgeDocument,
    raw_snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes = _node_index(document)
    components = {node.id: node for node in document.components}
    expected_instances = {
        node_id: node
        for node_id, node in nodes.items()
        if node.type == "instance"
    }
    snapshots = [
        PenpotShapeSnapshot.model_validate(item)
        for item in raw_snapshots
        if item.get("designbridge_id")
    ]

    roots_by_id: dict[str, list[PenpotShapeSnapshot]] = {}
    members_by_root: dict[str, list[PenpotShapeSnapshot]] = {}

    for snapshot in snapshots:
        if snapshot.designbridge_type == "instance" or snapshot.component_role == "copy_root":
            roots_by_id.setdefault(snapshot.designbridge_id, []).append(snapshot)
        if (
            snapshot.component_role == "copy_member"
            and snapshot.component_root_designbridge_id
        ):
            members_by_root.setdefault(
                snapshot.component_root_designbridge_id, []
            ).append(snapshot)

    instances: list[dict[str, Any]] = []
    missing: list[str] = []
    detached: list[str] = []
    swapped: list[str] = []
    duplicate_roots: list[str] = []
    overrides_out_of_sync: list[str] = []

    for instance_id, instance in sorted(expected_instances.items()):
        roots = roots_by_id.get(instance_id, [])
        if not roots:
            missing.append(instance_id)
            instances.append({
                "instance_id": instance_id,
                "component_id": instance.component_id,
                "status": "missing",
                "canonical_overrides": instance.overrides,
                "discovered_overrides": {},
            })
            continue

        if len(roots) > 1:
            duplicate_roots.append(instance_id)

        root = roots[0]
        actual_component_id = root.component_id
        role = root.component_role or "basic"

        if role not in {"copy_root", "copy_member"}:
            status = "detached"
            detached.append(instance_id)
        elif actual_component_id and actual_component_id != instance.component_id:
            status = "swapped"
            swapped.append(instance_id)
        else:
            status = "linked"

        component = components.get(instance.component_id or "")
        discovered = (
            _safe_snapshot_overrides(
                component,
                members_by_root.get(instance_id, []),
            )
            if component is not None
            else {}
        )
        canonical = instance.overrides
        if discovered != canonical:
            overrides_out_of_sync.append(instance_id)

        instances.append({
            "instance_id": instance_id,
            "component_id": instance.component_id,
            "actual_component_id": actual_component_id,
            "component_role": role,
            "status": status,
            "canonical_overrides": canonical,
            "discovered_overrides": discovered,
            "overrides_match": discovered == canonical,
            "copy_members": len(members_by_root.get(instance_id, [])),
        })

    return {
        "summary": {
            "expected_instances": len(expected_instances),
            "linked_instances": sum(item["status"] == "linked" for item in instances),
            "missing_instances": len(missing),
            "detached_instances": len(detached),
            "swapped_instances": len(swapped),
            "duplicate_instance_roots": len(duplicate_roots),
            "overrides_out_of_sync": len(overrides_out_of_sync),
        },
        "instances": instances,
        "missing_instance_ids": missing,
        "detached_instance_ids": detached,
        "swapped_instance_ids": swapped,
        "duplicate_instance_root_ids": duplicate_roots,
        "overrides_out_of_sync_ids": overrides_out_of_sync,
    }


def instance_override_changes(
    document: DesignBridgeDocument,
    raw_snapshots: list[dict[str, Any]],
    instance_ids: list[str],
) -> dict[str, dict[str, dict[str, Any]]]:
    report = component_instance_report(document, raw_snapshots)
    by_id = {item["instance_id"]: item for item in report["instances"]}
    requested = list(dict.fromkeys(instance_ids))
    if not requested:
        raise ValueError("at least one instance_id is required")

    changes: dict[str, dict[str, dict[str, Any]]] = {}
    for instance_id in requested:
        item = by_id.get(instance_id)
        if item is None:
            raise ValueError(f"unknown instance_id: {instance_id}")
        if item["status"] != "linked":
            raise ValueError(
                f"instance {instance_id} is {item['status']} and cannot capture overrides"
            )
        changes[instance_id] = item["discovered_overrides"]
    return changes
