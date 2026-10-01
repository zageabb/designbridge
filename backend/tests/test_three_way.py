from app.models import DesignBridgeDocument
from app.penpot_sync import PenpotShapeSnapshot
from app.three_way import three_way_review

from test_designbridge import VALID


def test_three_way_detects_true_property_conflict():
    base = DesignBridgeDocument.model_validate(VALID)
    latest = base.model_copy(deep=True)
    latest.pages[0].children[0].children[0].text = "Changed in DesignBridge"

    review = three_way_review(
        base,
        latest,
        [
            PenpotShapeSnapshot(
                designbridge_id="title",
                type="text",
                name="Title",
                text="Changed in Penpot",
            )
        ],
    )

    assert review["summary"]["conflict_properties"] == 1
    node = review["nodes"][0]
    assert node["node_id"] == "title"
    assert node["properties"]["text"]["classification"] == "conflict"
    assert node["properties"]["text"]["base"] == "Hello"
    assert node["properties"]["text"]["local"] == "Changed in Penpot"
    assert node["properties"]["text"]["latest"] == "Changed in DesignBridge"


def test_three_way_classifies_remote_only_change():
    base = DesignBridgeDocument.model_validate(VALID)
    latest = base.model_copy(deep=True)
    latest.pages[0].children[0].children[0].text = "Changed in DesignBridge"

    review = three_way_review(
        base,
        latest,
        [
            PenpotShapeSnapshot(
                designbridge_id="title",
                type="text",
                name="Title",
                text="Hello",
            )
        ],
    )

    assert review["summary"]["conflict_properties"] == 0
    assert review["summary"]["remote_only_properties"] == 1
    assert review["nodes"][0]["properties"]["text"]["classification"] == "remote_only"


def test_three_way_classifies_local_only_change():
    base = DesignBridgeDocument.model_validate(VALID)
    latest = base.model_copy(deep=True)

    review = three_way_review(
        base,
        latest,
        [
            PenpotShapeSnapshot(
                designbridge_id="title",
                type="text",
                name="Title",
                text="Changed in Penpot",
            )
        ],
    )

    assert review["summary"]["local_only_properties"] == 1
    assert review["nodes"][0]["properties"]["text"]["classification"] == "local_only"


def test_three_way_same_change_is_not_conflict():
    base = DesignBridgeDocument.model_validate(VALID)
    latest = base.model_copy(deep=True)
    latest.pages[0].children[0].children[0].text = "Same change"

    review = three_way_review(
        base,
        latest,
        [
            PenpotShapeSnapshot(
                designbridge_id="title",
                type="text",
                name="Title",
                text="Same change",
            )
        ],
    )

    assert review["summary"]["conflict_properties"] == 0
    assert review["summary"]["same_change_properties"] == 1


def test_resolution_plan_requires_all_outstanding_properties():
    from app.three_way import resolution_plan

    base = DesignBridgeDocument.model_validate(VALID)
    latest = base.model_copy(deep=True)
    latest.pages[0].children[0].children[0].text = "Remote"

    snapshots = [
        PenpotShapeSnapshot(
            designbridge_id="title",
            type="text",
            name="Title",
            text="Local",
        )
    ]

    plan = resolution_plan(base, latest, snapshots, [])
    assert plan["complete"] is False
    assert plan["unresolved"] == [{"node_id": "title", "property": "text"}]


def test_resolution_plan_separates_local_and_remote_choices():
    from app.three_way import resolution_plan

    base = DesignBridgeDocument.model_validate(VALID)
    latest = base.model_copy(deep=True)
    latest.pages[0].children[0].children[0].text = "Remote"
    latest.pages[0].children[0].name = "Remote frame"

    snapshots = [
        PenpotShapeSnapshot(
            designbridge_id="title",
            type="text",
            name="Title",
            text="Local",
        ),
        PenpotShapeSnapshot(
            designbridge_id="frame",
            type="board",
            name="Frame",
        ),
    ]

    plan = resolution_plan(
        base,
        latest,
        snapshots,
        [
            {"node_id": "title", "property": "text", "choice": "local"},
            {"node_id": "frame", "property": "name", "choice": "remote"},
        ],
    )

    assert plan["complete"] is True
    assert plan["local_changes"] == {"title": {"text": "Local"}}
    assert plan["remote_updates"] == [
        {"node_id": "frame", "property": "name", "value": "Remote frame"}
    ]
