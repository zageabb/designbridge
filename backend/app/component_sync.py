from __future__ import annotations

from typing import Any

from .models import DesignBridgeDocument, DesignNode
from .operations import DesignOperation
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


def _safe_definition_values(node: DesignNode, snapshot: PenpotShapeSnapshot) -> dict[str, Any]:
    provided = snapshot.model_fields_set
    values: dict[str, Any] = {}
    if "name" in provided and snapshot.name is not None and snapshot.name != node.name:
        values["name"] = snapshot.name
    if (
        node.type == "text"
        and "text" in provided
        and snapshot.text is not None
        and snapshot.text != node.text
    ):
        values["text"] = snapshot.text
    if (
        node.fill_token is None
        and "fill" in provided
        and snapshot.fill is not None
        and snapshot.fill != node.fill
    ):
        values["fill"] = snapshot.fill
    return values


def component_definition_report(
    document: DesignBridgeDocument,
    raw_snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    components = {node.id: node for node in document.components}
    component_children = {
        component_id: _component_children(component)
        for component_id, component in components.items()
    }
    snapshots = [
        PenpotShapeSnapshot.model_validate(item)
        for item in raw_snapshots
        if item.get("designbridge_id")
    ]

    main_roots: dict[str, PenpotShapeSnapshot] = {}
    main_members: dict[str, dict[str, PenpotShapeSnapshot]] = {}
    for snapshot in snapshots:
        if snapshot.component_role == "main_root":
            component_id = snapshot.component_id or snapshot.designbridge_id
            main_roots[component_id] = snapshot
        elif snapshot.component_role == "main_member" and snapshot.component_id:
            main_members.setdefault(snapshot.component_id, {})[
                snapshot.designbridge_id
            ] = snapshot

    rows: list[dict[str, Any]] = []
    missing_components: list[str] = []
    changed_components: list[str] = []

    for component_id, component in sorted(components.items()):
        root = main_roots.get(component_id)
        if root is None:
            missing_components.append(component_id)
            rows.append({
                "component_id": component_id,
                "name": component.name,
                "status": "missing",
                "root_changes": {},
                "child_changes": {},
                "protected_instance_overrides": {},
            })
            continue

        root_changes = _safe_definition_values(component, root)
        child_changes: dict[str, dict[str, Any]] = {}
        for child_id, child in component_children[component_id].items():
            snapshot = main_members.get(component_id, {}).get(child_id)
            if snapshot is None:
                continue
            values = _safe_definition_values(child, snapshot)
            if values:
                child_changes[child_id] = values

        protected: dict[str, dict[str, list[str]]] = {}
        for node_id, node in _node_index(document).items():
            if node.type != "instance" or node.component_id != component_id:
                continue
            for child_id, overrides in node.overrides.items():
                for property_name in overrides:
                    protected.setdefault(node_id, {}).setdefault(child_id, []).append(
                        property_name
                    )

        status = "changed" if root_changes or child_changes else "in_sync"
        if status == "changed":
            changed_components.append(component_id)

        rows.append({
            "component_id": component_id,
            "name": component.name,
            "status": status,
            "root_changes": root_changes,
            "child_changes": child_changes,
            "protected_instance_overrides": protected,
        })

    return {
        "summary": {
            "components": len(components),
            "in_sync": sum(item["status"] == "in_sync" for item in rows),
            "changed": len(changed_components),
            "missing": len(missing_components),
        },
        "components": rows,
        "changed_component_ids": changed_components,
        "missing_component_ids": missing_components,
    }


def component_definition_operations(
    document: DesignBridgeDocument,
    raw_snapshots: list[dict[str, Any]],
    component_ids: list[str],
) -> list[DesignOperation]:
    report = component_definition_report(document, raw_snapshots)
    by_id = {item["component_id"]: item for item in report["components"]}
    requested = list(dict.fromkeys(component_ids))
    if not requested:
        raise ValueError("at least one component_id is required")

    operations: list[DesignOperation] = []
    for component_id in requested:
        item = by_id.get(component_id)
        if item is None:
            raise ValueError(f"unknown component_id: {component_id}")
        if item["status"] == "missing":
            raise ValueError(f"component {component_id} main definition is missing in Penpot")
        if item["root_changes"]:
            operations.append(
                DesignOperation(
                    action="update_node",
                    node_id=component_id,
                    changes=item["root_changes"],
                )
            )
        for child_id, changes in item["child_changes"].items():
            operations.append(
                DesignOperation(
                    action="update_node",
                    node_id=child_id,
                    changes=changes,
                )
            )
    return operations


def _variant_slot_index(component: DesignNode) -> dict[str, DesignNode]:
    slots: dict[str, DesignNode] = {}

    def walk(node: DesignNode) -> None:
        if node.variant_slot:
            slots[node.variant_slot] = node
        for child in node.children:
            walk(child)

    for child in component.children:
        walk(child)
    return slots


def variant_family_report(document: DesignBridgeDocument) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for component in document.components:
        if not component.variant_group:
            continue
        groups.setdefault(component.variant_group, []).append({
            "component_id": component.id,
            "name": component.name,
            "properties": component.variant_properties,
            "slots": sorted(_variant_slot_index(component)),
        })

    instances: list[dict[str, Any]] = []
    for node_id, node in _node_index(document).items():
        if node.type != "instance":
            continue
        component = next(
            (item for item in document.components if item.id == node.component_id),
            None,
        )
        if component is None or not component.variant_group:
            continue
        instances.append({
            "instance_id": node_id,
            "component_id": node.component_id,
            "variant_group": component.variant_group,
            "variant_properties": component.variant_properties,
            "overrides": node.overrides,
        })

    return {
        "summary": {
            "variant_groups": len(groups),
            "variant_components": sum(len(items) for items in groups.values()),
            "variant_instances": len(instances),
        },
        "groups": [
            {
                "variant_group": group_id,
                "components": sorted(items, key=lambda item: item["component_id"]),
            }
            for group_id, items in sorted(groups.items())
        ],
        "instances": sorted(instances, key=lambda item: item["instance_id"]),
    }


def plan_variant_switch(
    document: DesignBridgeDocument,
    instance_id: str,
    target_component_id: str,
) -> dict[str, Any]:
    nodes = _node_index(document)
    instance = nodes.get(instance_id)
    if instance is None or instance.type != "instance":
        raise ValueError(f"unknown instance_id: {instance_id}")

    components = {item.id: item for item in document.components}
    source = components.get(instance.component_id or "")
    target = components.get(target_component_id)
    if source is None or target is None:
        raise ValueError("source or target component not found")
    if not source.variant_group or source.variant_group != target.variant_group:
        raise ValueError("variant switch requires source and target in the same variant_group")
    if source.id == target.id:
        raise ValueError("target component is already active")

    source_children = _component_children(source)
    source_slots = _variant_slot_index(source)
    target_slots = _variant_slot_index(target)
    source_slot_by_id = {
        node.id: slot for slot, node in source_slots.items()
    }

    issues: list[dict[str, Any]] = []
    remapped: dict[str, dict[str, Any]] = {}

    for child_id, values in instance.overrides.items():
        source_child = source_children.get(child_id)
        slot = source_slot_by_id.get(child_id)
        if source_child is None:
            issues.append({
                "child_id": child_id,
                "reason": "override source child does not exist in source component",
            })
            continue
        if not slot:
            issues.append({
                "child_id": child_id,
                "reason": "override source child has no variant_slot",
            })
            continue
        target_child = target_slots.get(slot)
        if target_child is None:
            issues.append({
                "child_id": child_id,
                "variant_slot": slot,
                "reason": "target variant is missing the override slot",
            })
            continue
        if source_child.type != target_child.type:
            issues.append({
                "child_id": child_id,
                "variant_slot": slot,
                "reason": f"slot type mismatch: {source_child.type} -> {target_child.type}",
            })
            continue

        supported_values: dict[str, Any] = {}
        for property_name, value in values.items():
            if property_name == "text" and target_child.type != "text":
                issues.append({
                    "child_id": child_id,
                    "variant_slot": slot,
                    "property": property_name,
                    "reason": "target slot does not support text override",
                })
                continue
            if property_name == "fill" and target_child.fill_token is not None:
                issues.append({
                    "child_id": child_id,
                    "variant_slot": slot,
                    "property": property_name,
                    "reason": "target slot is token-bound and cannot accept direct fill override",
                })
                continue
            supported_values[property_name] = value

        if supported_values:
            remapped[target_child.id] = supported_values

    return {
        "instance_id": instance_id,
        "source_component_id": source.id,
        "target_component_id": target.id,
        "variant_group": source.variant_group,
        "source_properties": source.variant_properties,
        "target_properties": target.variant_properties,
        "compatible": not issues,
        "issues": issues,
        "remapped_overrides": remapped,
    }


def variant_switch_operation(
    document: DesignBridgeDocument,
    instance_id: str,
    target_component_id: str,
) -> tuple[DesignOperation, dict[str, Any]]:
    plan = plan_variant_switch(document, instance_id, target_component_id)
    if not plan["compatible"]:
        raise ValueError(
            "variant switch is incompatible: "
            + "; ".join(item["reason"] for item in plan["issues"])
        )
    return (
        DesignOperation(
            action="update_node",
            node_id=instance_id,
            changes={
                "component_id": target_component_id,
                "variant_group": plan["variant_group"],
                "overrides": plan["remapped_overrides"],
            },
        ),
        plan,
    )


def native_variant_mapping_report(
    document: DesignBridgeDocument,
    native_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    canonical = variant_family_report(document)
    canonical_groups = {
        item["variant_group"]: item
        for item in canonical["groups"]
    }

    native_by_group: dict[str, list[dict[str, Any]]] = {}
    for raw in native_groups:
        group_id = str(raw.get("designbridge_variant_group") or "").strip()
        if not group_id:
            continue
        native_by_group.setdefault(group_id, []).append(raw)

    rows: list[dict[str, Any]] = []
    for group_id, group in sorted(canonical_groups.items()):
        candidates = native_by_group.get(group_id, [])
        expected_components = {
            item["component_id"]: item
            for item in group["components"]
        }
        expected_property_names = sorted({
            key
            for item in group["components"]
            for key in item.get("properties", {})
        })

        if not candidates:
            rows.append({
                "variant_group": group_id,
                "status": "absent",
                "native_variant_id": None,
                "property_names": [],
                "issues": ["no tagged Penpot native variant family found"],
            })
            continue

        if len(candidates) > 1:
            rows.append({
                "variant_group": group_id,
                "status": "ambiguous",
                "native_variant_id": None,
                "property_names": [],
                "issues": ["multiple Penpot native variant families claim this DesignBridge group"],
            })
            continue

        native = candidates[0]
        native_components = {
            str(item.get("designbridge_component_id") or ""): item
            for item in native.get("components", [])
            if item.get("designbridge_component_id")
        }
        native_property_names = [str(item) for item in native.get("property_names", [])]

        issues: list[str] = []
        missing = sorted(set(expected_components) - set(native_components))
        unknown = sorted(set(native_components) - set(expected_components))
        if missing:
            issues.append("missing canonical components: " + ", ".join(missing))
        if unknown:
            issues.append("unknown tagged components: " + ", ".join(unknown))

        if sorted(native_property_names) != expected_property_names:
            issues.append(
                "property names differ: canonical "
                + repr(expected_property_names)
                + " vs Penpot "
                + repr(sorted(native_property_names))
            )

        property_mismatches: list[dict[str, Any]] = []
        for component_id, expected in expected_components.items():
            native_component = native_components.get(component_id)
            if native_component is None:
                continue
            actual = {
                str(key): str(value)
                for key, value in dict(native_component.get("variant_props") or {}).items()
            }
            expected_props = {
                str(key): str(value)
                for key, value in dict(expected.get("properties") or {}).items()
            }
            if actual != expected_props:
                property_mismatches.append({
                    "component_id": component_id,
                    "canonical": expected_props,
                    "penpot": actual,
                })

        if property_mismatches:
            issues.append("one or more component variant property values differ")

        rows.append({
            "variant_group": group_id,
            "status": "in_sync" if not issues else "mismatch",
            "native_variant_id": native.get("native_variant_id"),
            "library_id": native.get("library_id"),
            "property_names": native_property_names,
            "issues": issues,
            "property_mismatches": property_mismatches,
            "component_ids": sorted(native_components),
        })

    return {
        "summary": {
            "canonical_groups": len(canonical_groups),
            "native_mapped": sum(item["status"] == "in_sync" for item in rows),
            "absent": sum(item["status"] == "absent" for item in rows),
            "mismatch": sum(item["status"] == "mismatch" for item in rows),
            "ambiguous": sum(item["status"] == "ambiguous" for item in rows),
        },
        "groups": rows,
    }


def plan_variant_switch_with_native(
    document: DesignBridgeDocument,
    instance_id: str,
    target_component_id: str,
    native_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    plan = plan_variant_switch(document, instance_id, target_component_id)
    report = native_variant_mapping_report(document, native_groups)
    mapping = next(
        (
            item
            for item in report["groups"]
            if item["variant_group"] == plan["variant_group"]
        ),
        None,
    )

    strategy: dict[str, Any] = {
        "kind": "component_swap",
        "reason": "no verified native Penpot variant mapping",
    }

    if mapping and mapping["status"] == "in_sync":
        property_names = mapping["property_names"]
        source_props = {
            str(key): str(value)
            for key, value in plan["source_properties"].items()
        }
        target_props = {
            str(key): str(value)
            for key, value in plan["target_properties"].items()
        }
        steps = [
            {
                "position": position,
                "property": property_name,
                "value": target_props[property_name],
            }
            for position, property_name in enumerate(property_names)
            if source_props.get(property_name) != target_props.get(property_name)
        ]
        strategy = {
            "kind": "native_variant",
            "native_variant_id": mapping["native_variant_id"],
            "library_id": mapping.get("library_id"),
            "steps": steps,
        }

    return {
        **plan,
        "switch_strategy": strategy,
        "native_mapping": mapping,
    }
