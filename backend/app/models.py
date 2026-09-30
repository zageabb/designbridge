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
    component_id: str | None = None
    layout: Layout | None = None
    children: list["DesignNode"] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_node_semantics(self) -> "DesignNode":
        if self.type == "text" and self.text is None:
            raise ValueError("text nodes require a text value")
        if self.type == "instance" and not self.component_id:
            raise ValueError("instance nodes require component_id")
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
    tokens: dict = Field(default_factory=dict)
    components: list[DesignNode] = Field(default_factory=list)
    assets: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
