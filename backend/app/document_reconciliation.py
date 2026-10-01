from __future__ import annotations

from collections import Counter
from typing import Any

from .models import DesignBridgeDocument
from .penpot_sync import PenpotShapeSnapshot
from .three_way import three_way_review


def _expected_locations(document: DesignBridgeDocument) -> dict[str, dict[str, str]]:
    expected: dict[str, dict[str, str]] = {}

    def walk(node, scope: str, page_id: str, page_name: str) -> None:
        expected[node.id] = {
            "scope": scope,
            "page_id": page_id,
            "page_name": page_name,
            "name": node.name,
            "type": node.type,
        }
        for child in node.children:
            walk(child, scope, page_id, page_name)

    for component in document.components:
        walk(component, "component", "__components__", "Design System")
    for page in document.pages:
        for node in page.children:
            walk(node, f"page:{page.id}", page.id, page.name)
    return expected


def reconcile_document(
    base: DesignBridgeDocument,
    latest: DesignBridgeDocument,
    raw_snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = _expected_locations(latest)
    linked = [item for item in raw_snapshots if item.get("designbridge_id")]
    ids = [str(item["designbridge_id"]) for item in linked]
    counts = Counter(ids)

    duplicate_ids = sorted(node_id for node_id, count in counts.items() if count > 1)
    linked_ids = set(ids)
    expected_ids = set(expected)
    missing_ids = sorted(expected_ids - linked_ids)
    unknown_ids = sorted(linked_ids - expected_ids)

    pages: dict[str, dict[str, Any]] = {}
    for node_id, meta in expected.items():
        key = meta["page_id"]
        page = pages.setdefault(
            key,
            {
                "page_id": key,
                "page_name": meta["page_name"],
                "expected": 0,
                "linked": 0,
                "missing": [],
            },
        )
        page["expected"] += 1
        if node_id in linked_ids:
            page["linked"] += 1
        else:
            page["missing"].append(node_id)

    snapshots = [
        PenpotShapeSnapshot.model_validate(item)
        for item in linked
        if item.get("designbridge_id") in expected
    ]
    review = three_way_review(base, latest, snapshots) if snapshots else {
        "summary": {
            "nodes_reviewed": 0,
            "nodes_with_conflicts": 0,
            "conflict_properties": 0,
            "local_only_properties": 0,
            "remote_only_properties": 0,
            "same_change_properties": 0,
        },
        "nodes": [],
    }

    for item in linked:
        node_id = str(item.get("designbridge_id"))
        meta = expected.get(node_id)
        if not meta:
            continue
        canonical_page_id = str(item.get("designbridge_page_id") or "")
        actual_page_name = str(item.get("page_name") or "")
        location_matches = (
            canonical_page_id == meta["page_id"]
            if canonical_page_id
            else actual_page_name == meta["page_name"]
        )
        if not location_matches:
            review.setdefault("location_mismatches", []).append(
                {
                    "node_id": node_id,
                    "expected_page_id": meta["page_id"],
                    "expected_page_name": meta["page_name"],
                    "actual_page_id": item.get("page_id"),
                    "actual_page_name": item.get("page_name"),
                    "actual_designbridge_page_id": item.get("designbridge_page_id"),
                }
            )

    page_rows = sorted(pages.values(), key=lambda item: (item["page_name"], item["page_id"]))
    for page in page_rows:
        page["coverage_percent"] = (
            round((page["linked"] / page["expected"]) * 100, 1)
            if page["expected"]
            else 100.0
        )

    expected_count = len(expected_ids)
    linked_expected_count = len(expected_ids & linked_ids)
    return {
        "summary": {
            "expected_nodes": expected_count,
            "linked_nodes": linked_expected_count,
            "missing_nodes": len(missing_ids),
            "unknown_linked_nodes": len(unknown_ids),
            "duplicate_link_ids": len(duplicate_ids),
            "coverage_percent": (
                round((linked_expected_count / expected_count) * 100, 1)
                if expected_count
                else 100.0
            ),
            "pages": len(page_rows),
            "pages_incomplete": sum(bool(page["missing"]) for page in page_rows),
        },
        "pages": page_rows,
        "missing_node_ids": missing_ids,
        "unknown_linked_node_ids": unknown_ids,
        "duplicate_link_ids": duplicate_ids,
        "review": review,
    }
