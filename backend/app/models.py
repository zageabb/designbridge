from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


NodeType = Literal["frame", "rectangle", "text", "component", "instance"]


class Layout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: Literal["horizontal", "vertical"] = "vertical"
    gap: float = Field(default=0, ge=0)
    padding: float = Field(default=0, ge=0)
    align: Literal["start", "center", "end", "stretch"] = "start"


class ColorToken(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str
    description: str | None = None


class DimensionToken(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: float
    description: str | None = None


class DesignTokens(BaseModel):
    model_config = ConfigDict(extra="forbid")
    colors: dict[str, ColorToken | str] = Field(default_factory=dict)
    spacing: dict[str, DimensionToken | float] = Field(default_factory=dict)
    radius: dict[str, DimensionToken | float] = Field(default_factory=dict)
    typography: dict = Field(default_factory=dict)


class DesignNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: NodeType
    name: str = Field(min_length=1)
    x: float | None = None
    y: float | None = None
    width: float | None = Field(default=None, gt=0)
    height: float | None = Field(default=None, gt=0)
    text: str | None = None
    fill: str | None = None
    fill_token: str | None = None
    component_id: str | None = None
    overrides: dict[str, dict[str, str | float | bool | None]] = Field(default_factory=dict)
    layout: Layout | None = None
    children: list["DesignNode"] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_node_semantics(self) -> "DesignNode":
        if self.type == "text" and self.text is None:
            raise ValueError("text nodes require a text value")
        if self.type == "instance" and not self.component_id:
            raise ValueError("instance nodes require component_id")
        if self.type == "instance" and self.children:
            raise ValueError("instance nodes cannot contain children")
        if self.type != "instance" and self.overrides:
            raise ValueError("only instance nodes may define overrides")
        allowed_override_properties = {"text", "name", "fill"}
        for child_id, values in self.overrides.items():
            if not child_id:
                raise ValueError("instance override child IDs cannot be empty")
            unsupported = set(values) - allowed_override_properties
            if unsupported:
                raise ValueError(
                    "unsupported instance override properties: "
                    + ", ".join(sorted(unsupported))
                )
        return self


class DesignPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    children: list[DesignNode] = Field(default_factory=list)


class DesignDocumentInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class DesignBridgeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["designbridge"] = "designbridge"
    version: Literal["0.1"] = "0.1"
    document: DesignDocumentInfo
    pages: list[DesignPage] = Field(min_length=1)
    tokens: DesignTokens = Field(default_factory=DesignTokens)
    components: list[DesignNode] = Field(default_factory=list)
    assets: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> "DesignBridgeDocument":
        component_ids = {component.id for component in self.components}
        if len(component_ids) != len(self.components):
            raise ValueError("component IDs must be unique")

        seen: set[str] = set()

        def walk(node: DesignNode) -> None:
            if node.id in seen:
                raise ValueError(f"duplicate node id: {node.id}")
            seen.add(node.id)
            if node.type == "instance" and node.component_id not in component_ids:
                raise ValueError(f"unknown component_id: {node.component_id}")
            for child in node.children:
                walk(child)

        for component in self.components:
            if component.type != "component":
                raise ValueError("top-level components must use type 'component'")
            walk(component)
        for page in self.pages:
            for child in page.children:
                walk(child)
        return self
