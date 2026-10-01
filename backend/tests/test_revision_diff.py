from app.models import DesignBridgeDocument
from app.revision_diff import compare_documents

from test_designbridge import VALID


def test_compare_documents_reports_changed_properties():
    before = DesignBridgeDocument.model_validate(VALID)
    after = before.model_copy(deep=True)
    title = after.pages[0].children[0].children[0]
    title.text = "Changed"
    title.name = "Changed title"

    diff = compare_documents(before, after)

    assert diff["summary"]["changed"] == 1
    change = diff["changed"][0]
    assert change["node_id"] == "title"
    assert set(change["properties"]) == {"name", "text"}


def test_compare_documents_reports_added_and_removed_nodes():
    before = DesignBridgeDocument.model_validate(VALID)
    after = before.model_copy(deep=True)
    frame = after.pages[0].children[0]
    frame.children = [frame.children[0]]
    frame.children.append(
        type(frame.children[0]).model_validate(
            {
                "id": "subtitle",
                "type": "text",
                "name": "Subtitle",
                "text": "New",
            }
        )
    )

    diff = compare_documents(before, after)

    assert diff["summary"]["added"] == 1
    assert diff["summary"]["removed"] == 1
    assert diff["added"][0]["node_id"] == "subtitle"
    assert diff["removed"][0]["node_id"] == "card-instance"


def test_compare_documents_reports_token_changes():
    before = DesignBridgeDocument.model_validate(VALID)
    after = before.model_copy(deep=True)
    after.tokens.colors["surface"] = "#eeeeee"

    diff = compare_documents(before, after)

    assert diff["summary"]["token_sections_changed"] == 1
    assert "colors" in diff["tokens"]


def test_selective_pull_plan_partial_does_not_advance():
    from app.revision_diff import selective_pull_plan

    before = DesignBridgeDocument.model_validate(VALID)
    after = before.model_copy(deep=True)
    after.pages[0].children[0].children[0].text = "Changed"
    after.pages[0].children[0].name = "Changed frame"

    plan = selective_pull_plan(before, after, ["title"])

    assert plan["selected_node_ids"] == ["title"]
    assert plan["remaining_changed_node_ids"] == ["frame"]
    assert plan["can_advance_revision"] is False


def test_selective_pull_plan_full_safe_change_can_advance():
    from app.revision_diff import selective_pull_plan

    before = DesignBridgeDocument.model_validate(VALID)
    after = before.model_copy(deep=True)
    after.pages[0].children[0].children[0].text = "Changed"

    plan = selective_pull_plan(before, after, ["title"])

    assert plan["remaining_changed_node_ids"] == []
    assert plan["can_advance_revision"] is True
    assert plan["selected"][0]["node"]["text"] == "Changed"


def test_selective_pull_plan_does_not_advance_with_structural_changes():
    from app.revision_diff import selective_pull_plan

    before = DesignBridgeDocument.model_validate(VALID)
    after = before.model_copy(deep=True)
    after.pages[0].children[0].children[0].text = "Changed"
    after.pages[0].children[0].children.append(
        type(after.pages[0].children[0].children[0]).model_validate(
            {
                "id": "subtitle",
                "type": "text",
                "name": "Subtitle",
                "text": "New",
            }
        )
    )

    plan = selective_pull_plan(before, after, ["title"])

    assert plan["can_advance_revision"] is False
    assert plan["diff"]["summary"]["added"] == 1
