from app.document_reconciliation import reconcile_document
from app.models import DesignBridgeDocument

from test_designbridge import VALID


def _snapshot(node_id: str, *, page_id: str, page_name: str, **values):
    return {
        "designbridge_id": node_id,
        "designbridge_page_id": page_id,
        "page_id": "penpot-" + page_id,
        "page_name": page_name,
        **values,
    }


def test_document_reconciliation_reports_full_coverage():
    document = DesignBridgeDocument.model_validate(VALID)
    snapshots = [
        _snapshot("card", page_id="__components__", page_name="Design System", name="Card"),
        _snapshot("card-label", page_id="__components__", page_name="Design System", name="Label", text="Card"),
        _snapshot("frame", page_id="page", page_name="Page", name="Frame"),
        _snapshot("title", page_id="page", page_name="Page", name="Title", text="Hello"),
        _snapshot("card-instance", page_id="page", page_name="Page", name="Card instance"),
    ]

    result = reconcile_document(document, document, snapshots)

    assert result["summary"]["expected_nodes"] == 5
    assert result["summary"]["linked_nodes"] == 5
    assert result["summary"]["missing_nodes"] == 0
    assert result["summary"]["coverage_percent"] == 100.0
    assert result["summary"]["pages_incomplete"] == 0


def test_document_reconciliation_reports_missing_unknown_and_duplicates():
    document = DesignBridgeDocument.model_validate(VALID)
    snapshots = [
        _snapshot("title", page_id="page", page_name="Page", name="Title", text="Hello"),
        _snapshot("title", page_id="page", page_name="Page", name="Title duplicate", text="Hello"),
        _snapshot("unknown", page_id="page", page_name="Page", name="Unknown"),
    ]

    result = reconcile_document(document, document, snapshots)

    assert result["summary"]["linked_nodes"] == 1
    assert result["summary"]["missing_nodes"] == 4
    assert result["unknown_linked_node_ids"] == ["unknown"]
    assert result["duplicate_link_ids"] == ["title"]


def test_document_reconciliation_reports_page_location_mismatch():
    document = DesignBridgeDocument.model_validate(VALID)
    snapshots = [
        _snapshot(
            "title",
            page_id="wrong-page",
            page_name="Wrong",
            name="Title",
            text="Hello",
        )
    ]

    result = reconcile_document(document, document, snapshots)

    mismatches = result["review"]["location_mismatches"]
    assert mismatches[0]["node_id"] == "title"
    assert mismatches[0]["expected_page_id"] == "page"
    assert mismatches[0]["actual_designbridge_page_id"] == "wrong-page"


def test_document_reconciliation_includes_document_wide_conflicts():
    base = DesignBridgeDocument.model_validate(VALID)
    latest = base.model_copy(deep=True)
    latest.pages[0].children[0].children[0].text = "Remote title"

    snapshots = [
        _snapshot(
            "title",
            page_id="page",
            page_name="Page",
            name="Title",
            text="Local title",
        )
    ]

    result = reconcile_document(base, latest, snapshots)

    assert result["review"]["summary"]["conflict_properties"] == 1
    assert result["review"]["nodes"][0]["node_id"] == "title"
