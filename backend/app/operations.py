from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import DesignBridgeDocument, DesignNode

OperationType = Literal[
    "update_node",
    "add_node",
    "remove_node",
    "move_node",
    "set_color_token",
    "set_spacing_token",
]


class DesignOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: OperationType
    node_id: str | None = None
    parent_id: str | None = None
    page_id: str | None = None
    index: int | None = Field(default=None, ge=0)
    changes: dict[str, Any] = Field(default_factory=dict)
    node: DesignNode | None = None
    token_name: str | None = None
    token_value: Any | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "DesignOperation":
        if self.action in {"update_node", "remove_node", "move_node"} and not self.node_id:
            raise ValueError(f"{self.action} requires node_id")
        if self.action == "update_node" and not self.changes:
            raise ValueError("update_node requires changes")
        if self.action == "add_node" and self.node is None:
            raise ValueError("add_node requires node")
        if self.action in {"set_color_token", "set_spacing_token"}:
            if not self.token_name:
                raise ValueError(f"{self.action} requires token_name")
            if self.token_value is None:
                raise ValueError(f"{self.action} requires token_value")
        return self


class OperationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = ""
    operations: list[DesignOperation] = Field(min_length=1)


class AppliedChange(BaseModel):
    action: OperationType
    target: str
    before: Any | None = None
    after: Any | None = None


class OperationResult(BaseModel):
    document: DesignBridgeDocument
    changes: list[AppliedChange]


class _NodeRef:
    def __init__(self, node: DesignNode, container: list[DesignNode], index: int):
        self.node = node
        self.container = container
        self.index = index


def _walk(container: list[DesignNode]):
    for index, node in enumerate(container):
        yield _NodeRef(node, container, index)
        yield from _walk(node.children)


def _find_node(document: DesignBridgeDocument, node_id: str) -> _NodeRef | None:
    for ref in _walk(document.components):
        if ref.node.id == node_id:
            return ref
    for page in document.pages:
        for ref in _walk(page.children):
            if ref.node.id == node_id:
                return ref
    return None


def _target_container(
    document: DesignBridgeDocument,
    parent_id: str | None,
    page_id: str | None,
) -> list[DesignNode]:
    if parent_id:
        parent = _find_node(document, parent_id)
        if not parent:
            raise ValueError(f"unknown parent_id: {parent_id}")
        if parent.node.type == "instance":
            raise ValueError("cannot add children to an instance")
        return parent.node.children
    if page_id:
        for page in document.pages:
            if page.id == page_id:
                return page.children
        raise ValueError(f"unknown page_id: {page_id}")
    raise ValueError("parent_id or page_id is required")


def _insert(container: list[DesignNode], node: DesignNode, index: int | None) -> None:
    if index is None or index >= len(container):
        container.append(node)
    else:
        container.insert(index, node)


def apply_operations(source: DesignBridgeDocument, batch: OperationBatch) -> OperationResult:
    document = source.model_copy(deep=True)
    changes: list[AppliedChange] = []

    for operation in batch.operations:
        if operation.action == "update_node":
            ref = _find_node(document, operation.node_id or "")
            if not ref:
                raise ValueError(f"unknown node_id: {operation.node_id}")
            before = ref.node.model_dump(mode="json", exclude_none=True)
            updated = ref.node.model_copy(update=deepcopy(operation.changes))
            updated = DesignNode.model_validate(
                updated.model_dump(mode="json", exclude_none=True)
            )
            ref.container[ref.index] = updated
            changes.append(
                AppliedChange(
                    action=operation.action,
                    target=operation.node_id or "",
                    before=before,
                    after=updated.model_dump(mode="json", exclude_none=True),
                )
            )

        elif operation.action == "add_node":
            if operation.node is None:
                raise ValueError("add_node requires node")
            if _find_node(document, operation.node.id):
                raise ValueError(f"duplicate node id: {operation.node.id}")
            container = _target_container(
                document, operation.parent_id, operation.page_id
            )
            node = operation.node.model_copy(deep=True)
            _insert(container, node, operation.index)
            changes.append(
                AppliedChange(
                    action=operation.action,
                    target=node.id,
                    after=node.model_dump(mode="json", exclude_none=True),
                )
            )

        elif operation.action == "remove_node":
            ref = _find_node(document, operation.node_id or "")
            if not ref:
                raise ValueError(f"unknown node_id: {operation.node_id}")
            before = ref.node.model_dump(mode="json", exclude_none=True)
            del ref.container[ref.index]
            changes.append(
                AppliedChange(
                    action=operation.action,
                    target=operation.node_id or "",
                    before=before,
                )
            )

        elif operation.action == "move_node":
            ref = _find_node(document, operation.node_id or "")
            if not ref:
                raise ValueError(f"unknown node_id: {operation.node_id}")
            node = ref.node
            old_index = ref.index
            del ref.container[ref.index]
            target = _target_container(
                document, operation.parent_id, operation.page_id
            )
            _insert(target, node, operation.index)
            changes.append(
                AppliedChange(
                    action=operation.action,
                    target=operation.node_id or "",
                    before={"index": old_index},
                    after={"index": operation.index},
                )
            )

        elif operation.action == "set_color_token":
            name = operation.token_name or ""
            before = document.tokens.colors.get(name)
            document.tokens.colors[name] = operation.token_value
            changes.append(
                AppliedChange(
                    action=operation.action,
                    target=name,
                    before=before,
                    after=operation.token_value,
                )
            )

        elif operation.action == "set_spacing_token":
            name = operation.token_name or ""
            before = document.tokens.spacing.get(name)
            document.tokens.spacing[name] = operation.token_value
            changes.append(
                AppliedChange(
                    action=operation.action,
                    target=name,
                    before=before,
                    after=operation.token_value,
                )
            )

    validated = DesignBridgeDocument.model_validate(
        document.model_dump(mode="json", exclude_none=True)
    )
    return OperationResult(document=validated, changes=changes)
