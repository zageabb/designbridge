from app.models import DesignBridgeDocument
from app.penpot_sync import PenpotShapeSnapshot, compare_penpot_snapshot

from test_designbridge import VALID


def test_compare_penpot_text_and_size_changes():
    document = DesignBridgeDocument.model_validate(VALID)
    batch = compare_penpot_snapshot(
        document,
        [
            PenpotShapeSnapshot(
                designbridge_id="title",
                penpot_id="shape-1",
                name="Title",
                type="text",
                text="Changed in Penpot",
                width=120,
                height=30,
            )
        ],
    )

    assert len(batch.operations) == 1
    operation = batch.operations[0]
    assert operation.action == "update_node"
    assert operation.node_id == "title"
    assert operation.changes["text"] == "Changed in Penpot"


def test_compare_penpot_direct_fill_change():
    payload = {
        **VALID,
        "pages": [
            {
                "id": "page",
                "name": "Page",
                "children": [
                    {
                        "id": "box",
                        "type": "rectangle",
                        "name": "Box",
                        "width": 100,
                        "height": 80,
                        "fill": "#ffffff",
                    }
                ],
            }
        ],
    }
    document = DesignBridgeDocument.model_validate(payload)
    batch = compare_penpot_snapshot(
        document,
        [
            PenpotShapeSnapshot(
                designbridge_id="box",
                type="rectangle",
                name="Box",
                width=100,
                height=80,
                fill="#123456",
            )
        ],
    )
    assert batch.operations[0].changes["fill"] == "#123456"


def test_compare_penpot_ignores_token_bound_fill():
    document = DesignBridgeDocument.model_validate(VALID)
    component = document.components[0]
    assert component.fill_token == "surface"

    try:
        compare_penpot_snapshot(
            document,
            [
                PenpotShapeSnapshot(
                    designbridge_id="card",
                    type="board",
                    name="Card",
                    width=240,
                    height=120,
                    fill="#123456",
                )
            ],
        )
    except ValueError as exc:
        assert "no supported Penpot changes" in str(exc)
    else:
        raise AssertionError("token-bound fill should not become a direct fill override")


def test_compare_penpot_skips_unknown_designbridge_id():
    document = DesignBridgeDocument.model_validate(VALID)
    try:
        compare_penpot_snapshot(
            document,
            [
                PenpotShapeSnapshot(
                    designbridge_id="missing",
                    type="rectangle",
                    name="Unknown",
                )
            ],
        )
    except ValueError as exc:
        assert "no supported Penpot changes" in str(exc)
    else:
        raise AssertionError("unknown IDs should not produce operations")


def test_compare_penpot_layout_changes():
    payload = {
        **VALID,
        "pages": [
            {
                "id": "page",
                "name": "Page",
                "children": [
                    {
                        "id": "layout-frame",
                        "type": "frame",
                        "name": "Layout Frame",
                        "layout": {
                            "direction": "vertical",
                            "gap": 16,
                            "padding": 24,
                            "align": "start",
                        },
                        "children": [],
                    }
                ],
            }
        ],
    }
    document = DesignBridgeDocument.model_validate(payload)
    batch = compare_penpot_snapshot(
        document,
        [
            PenpotShapeSnapshot(
                designbridge_id="layout-frame",
                type="board",
                name="Layout Frame",
                layout_direction="horizontal",
                layout_gap=8,
                layout_padding=12,
                layout_align="center",
            )
        ],
    )

    operation = batch.operations[0]
    assert operation.node_id == "layout-frame"
    assert operation.changes["layout"] == {
        "direction": "horizontal",
        "gap": 8,
        "padding": 12,
        "align": "center",
    }


def test_compare_penpot_layout_ignores_absent_snapshot_fields():
    payload = {
        **VALID,
        "pages": [
            {
                "id": "page",
                "name": "Page",
                "children": [
                    {
                        "id": "layout-frame",
                        "type": "frame",
                        "name": "Layout Frame",
                        "layout": {
                            "direction": "vertical",
                            "gap": 16,
                            "padding": 24,
                            "align": "start",
                        },
                        "children": [],
                    }
                ],
            }
        ],
    }
    document = DesignBridgeDocument.model_validate(payload)

    try:
        compare_penpot_snapshot(
            document,
            [
                PenpotShapeSnapshot(
                    designbridge_id="layout-frame",
                    type="board",
                    name="Layout Frame",
                )
            ],
        )
    except ValueError as exc:
        assert "no supported Penpot changes" in str(exc)
    else:
        raise AssertionError("missing layout snapshot fields should not create updates")
