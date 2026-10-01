from __future__ import annotations

from math import isclose
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models import DesignBridgeDocument, DesignNode
from .operations import DesignOperation, OperationBatch


class PenpotShapeSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    penpot_id: str | None = None
    designbridge_id: str = Field(min_length=1)
    designbridge_type: str | None = None
    name: str | None = None
    type: str | None = None
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    text: str | None = None
    fill: str | None = None
    layout_direction: str | None = None
    layout_gap: float | None = None
    layout_padding: float | None = None
    layout_align: str | None = None
    component_role: str | None = None
    component_id: str | None = None
    component_root_designbridge_id: str | None = None


def _node_index(document: DesignBridgeDocument) -> dict[str, DesignNode]:
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


def _different(left: float | None, right: float | None, tolerance: float = 0.5) -> bool:
    if left is None or right is None:
        return False
    return not isclose(float(left), float(right), abs_tol=tolerance)


def compare_penpot_snapshot(
    document: DesignBridgeDocument,
    snapshots: list[PenpotShapeSnapshot],
) -> OperationBatch:
    nodes = _node_index(document)
    operations: list[DesignOperation] = []

    for snapshot in snapshots:
        node = nodes.get(snapshot.designbridge_id)
        if node is None:
            continue

        changes: dict[str, Any] = {}
        if snapshot.name is not None and snapshot.name != node.name:
            changes["name"] = snapshot.name

        if node.x is not None and _different(node.x, snapshot.x):
            changes["x"] = snapshot.x
        if node.y is not None and _different(node.y, snapshot.y):
            changes["y"] = snapshot.y
        if node.width is not None and _different(node.width, snapshot.width):
            changes["width"] = snapshot.width
        if node.height is not None and _different(node.height, snapshot.height):
            changes["height"] = snapshot.height

        if node.type == "text" and snapshot.text is not None and snapshot.text != node.text:
            changes["text"] = snapshot.text

        if (
            node.fill_token is None
            and snapshot.fill is not None
            and snapshot.fill != node.fill
        ):
            changes["fill"] = snapshot.fill

        if node.layout is not None:
            layout_changes = node.layout.model_dump(mode="json")
            changed_layout = False

            if snapshot.layout_direction in {"horizontal", "vertical"}:
                if snapshot.layout_direction != node.layout.direction:
                    layout_changes["direction"] = snapshot.layout_direction
                    changed_layout = True

            if snapshot.layout_gap is not None and _different(node.layout.gap, snapshot.layout_gap):
                layout_changes["gap"] = snapshot.layout_gap
                changed_layout = True

            if snapshot.layout_padding is not None and _different(node.layout.padding, snapshot.layout_padding):
                layout_changes["padding"] = snapshot.layout_padding
                changed_layout = True

            if snapshot.layout_align in {"start", "center", "end", "stretch"}:
                if snapshot.layout_align != node.layout.align:
                    layout_changes["align"] = snapshot.layout_align
                    changed_layout = True

            if changed_layout:
                changes["layout"] = layout_changes

        if changes:
            operations.append(
                DesignOperation(
                    action="update_node",
                    node_id=node.id,
                    changes=changes,
                )
            )

    if not operations:
        raise ValueError("no supported Penpot changes detected")

    return OperationBatch(
        description="Synchronize supported Penpot edits into DesignBridge",
        operations=operations,
    )
