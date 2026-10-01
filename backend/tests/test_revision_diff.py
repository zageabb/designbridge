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
