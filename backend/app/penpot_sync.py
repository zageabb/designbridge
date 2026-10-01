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
