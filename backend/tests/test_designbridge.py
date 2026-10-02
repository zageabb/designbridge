import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models import DesignBridgeDocument


def _revision_token(client: TestClient, revision: int = 1) -> str:
    response = client.get(f"/api/projects/demo?revision={revision}")
    assert response.status_code == 200
    return response.json()["revision_token"]


VALID = {
    "format": "designbridge",
    "version": "0.1",
    "document": {"id": "demo", "name": "Demo"},
    "tokens": {
        "colors": {"surface": {"value": "#ffffff"}},
        "spacing": {"md": 16},
    },
    "components": [
        {
            "id": "card",
            "type": "component",
            "name": "Card",
            "width": 240,
            "height": 120,
            "fill_token": "surface",
            "children": [
                {
                    "id": "card-label",
                    "type": "text",
                    "name": "Label",
                    "text": "Card",
                }
            ],
        }
    ],
    "pages": [
        {
            "id": "page",
            "name": "Page",
            "children": [
                {
                    "id": "frame",
                    "type": "frame",
                    "name": "Frame",
                    "width": 800,
                    "height": 600,
                    "children": [
                        {
                            "id": "title",
                            "type": "text",
                            "name": "Title",
                            "text": "Hello",
                        },
                        {
                            "id": "card-instance",
                            "type": "instance",
                            "name": "Card instance",
                            "component_id": "card",
                        },
                    ],
                }
            ],
        }
    ],
}


def test_valid_document():
    document = DesignBridgeDocument.model_validate(VALID)
    assert document.document.id == "demo"
    assert document.components[0].fill_token == "surface"
    assert document.pages[0].children[0].children[1].component_id == "card"


def test_text_requires_text_value():
    invalid = {**VALID}
    invalid["pages"] = [
        {
            "id": "page",
            "name": "Page",
            "children": [{"id": "text", "type": "text", "name": "Broken"}],
        }
    ]
    with pytest.raises(ValidationError):
        DesignBridgeDocument.model_validate(invalid)


def test_instance_requires_known_component():
    invalid = {**VALID}
    invalid["pages"] = [
        {
            "id": "page",
            "name": "Page",
            "children": [
                {
                    "id": "bad-instance",
                    "type": "instance",
                    "name": "Bad",
                    "component_id": "missing",
                }
            ],
        }
    ]
    with pytest.raises(ValidationError):
        DesignBridgeDocument.model_validate(invalid)


def test_duplicate_node_ids_are_rejected():
    invalid = {**VALID}
    invalid["pages"] = [
        {
            "id": "page",
            "name": "Page",
            "children": [
                {"id": "duplicate", "type": "text", "name": "A", "text": "A"},
                {"id": "duplicate", "type": "text", "name": "B", "text": "B"},
            ],
        }
    ]
    with pytest.raises(ValidationError):
        DesignBridgeDocument.model_validate(invalid)


def test_validate_endpoint():
    client = TestClient(app)
    response = client.post("/api/validate", json=VALID)
    assert response.status_code == 200
    assert response.json() == {"valid": True, "document_id": "demo", "pages": 1}


def test_apply_update_node_operation():
    client = TestClient(app)
    payload = {
        "document": VALID,
        "batch": {
            "description": "Rename title",
            "operations": [
                {
                    "action": "update_node",
                    "node_id": "title",
                    "changes": {"text": "Updated title", "name": "Updated title"},
                }
            ],
        },
    }
    response = client.post("/api/operations/apply", json=payload)
    assert response.status_code == 200
    body = response.json()
    title = body["document"]["pages"][0]["children"][0]["children"][0]
    assert title["text"] == "Updated title"
    assert body["changes"][0]["target"] == "title"


def test_apply_add_and_remove_node_operations():
    client = TestClient(app)
    payload = {
        "document": VALID,
        "batch": {
            "operations": [
                {
                    "action": "add_node",
                    "parent_id": "frame",
                    "index": 1,
                    "node": {
                        "id": "subtitle",
                        "type": "text",
                        "name": "Subtitle",
                        "text": "Added",
                    },
                },
                {
                    "action": "remove_node",
                    "node_id": "card-instance",
                },
            ]
        },
    }
    response = client.post("/api/operations/apply", json=payload)
    assert response.status_code == 200
    children = response.json()["document"]["pages"][0]["children"][0]["children"]
    assert [node["id"] for node in children] == ["title", "subtitle"]


def test_apply_move_node_operation():
    document = {
        **VALID,
        "pages": [
            {
                "id": "page",
                "name": "Page",
                "children": [
                    {
                        "id": "left",
                        "type": "frame",
                        "name": "Left",
                        "children": [
                            {"id": "moveme", "type": "text", "name": "Move", "text": "Move"}
                        ],
                    },
                    {
                        "id": "right",
                        "type": "frame",
                        "name": "Right",
                        "children": [],
                    },
                ],
            }
        ],
    }
    client = TestClient(app)
    response = client.post(
        "/api/operations/apply",
        json={
            "document": document,
            "batch": {
                "operations": [
                    {
                        "action": "move_node",
                        "node_id": "moveme",
                        "parent_id": "right",
                        "index": 0,
                    }
                ]
            },
        },
    )
    assert response.status_code == 200
    page = response.json()["document"]["pages"][0]
    assert page["children"][0]["children"] == []
    assert page["children"][1]["children"][0]["id"] == "moveme"


def test_apply_token_operation():
    client = TestClient(app)
    response = client.post(
        "/api/operations/apply",
        json={
            "document": VALID,
            "batch": {
                "operations": [
                    {
                        "action": "set_color_token",
                        "token_name": "accent",
                        "token_value": "#123456",
                    }
                ]
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["document"]["tokens"]["colors"]["accent"] == "#123456"


def test_operation_rejects_unknown_node():
    client = TestClient(app)
    response = client.post(
        "/api/operations/apply",
        json={
            "document": VALID,
            "batch": {
                "operations": [
                    {
                        "action": "update_node",
                        "node_id": "missing",
                        "changes": {"name": "Nope"},
                    }
                ]
            },
        },
    )
    assert response.status_code == 422


def test_project_save_load_undo_redo(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    monkeypatch.setattr(main_module, "STORE", DesignStore(tmp_path / "api.db"))
    client = TestClient(main_module.app)

    saved = client.post(
        "/api/projects/save",
        json={"document": VALID, "description": "initial"},
    )
    assert saved.status_code == 200
    assert saved.json()["revision"] == 1

    changed = {**VALID}
    changed["pages"] = [
        {
            **VALID["pages"][0],
            "children": [
                {
                    **VALID["pages"][0]["children"][0],
                    "children": [
                        {
                            **VALID["pages"][0]["children"][0]["children"][0],
                            "text": "Changed",
                        },
                        VALID["pages"][0]["children"][0]["children"][1],
                    ],
                }
            ],
        }
    ]
    second = client.post(
        "/api/projects/save",
        json={"document": changed, "description": "changed"},
    )
    assert second.status_code == 200
    assert second.json()["revision"] == 2

    history = client.get("/api/projects/demo/history")
    assert history.status_code == 200
    assert len(history.json()["history"]) == 2

    undo = client.post("/api/projects/demo/undo")
    assert undo.status_code == 200
    assert undo.json()["revision"] == 1

    redo = client.post("/api/projects/demo/redo")
    assert redo.status_code == 200
    assert redo.json()["revision"] == 2


def test_penpot_compare_endpoint():
    client = TestClient(app)
    response = client.post(
        "/api/penpot/compare",
        json={
            "document": VALID,
            "selection": [
                {
                    "penpot_id": "shape-1",
                    "designbridge_id": "title",
                    "designbridge_type": "text",
                    "name": "Title",
                    "type": "text",
                    "text": "Edited in Penpot",
                    "width": 120,
                    "height": 30,
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["batch"]["operations"][0]["node_id"] == "title"
    assert body["preview"]["document"]["pages"][0]["children"][0]["children"][0]["text"] == "Edited in Penpot"


def test_penpot_compare_rejects_unlinked_selection():
    client = TestClient(app)
    response = client.post(
        "/api/penpot/compare",
        json={
            "document": VALID,
            "selection": [{"penpot_id": "shape-1", "name": "Unlinked"}],
        },
    )
    assert response.status_code == 422


def test_direct_penpot_pull_and_push(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "direct-sync.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)

    save = client.post(
        "/api/projects/save",
        json={"document": VALID, "description": "initial"},
    )
    assert save.status_code == 200

    pull = client.get("/api/penpot/projects/demo/current")
    assert pull.status_code == 200
    assert pull.json()["revision"] == 1
    assert pull.json()["document"]["document"]["id"] == "demo"

    push = client.post(
        "/api/penpot/projects/demo/selection",
        json={
            "expected_revision": 1,
            "expected_revision_token": _revision_token(client, 1),
            "selection": [
                {
                    "penpot_id": "shape-1",
                    "designbridge_id": "title",
                    "designbridge_type": "text",
                    "name": "Title",
                    "type": "text",
                    "text": "Changed directly from Penpot",
                }
            ],
            "description": "Penpot direct sync test",
        },
    )
    assert push.status_code == 200
    body = push.json()
    assert body["revision"] == 2
    assert body["document"]["pages"][0]["children"][0]["children"][0]["text"] == "Changed directly from Penpot"

    latest = client.get("/api/penpot/projects/demo/current")
    assert latest.status_code == 200
    assert latest.json()["revision"] == 2


def test_direct_penpot_push_requires_linked_shape(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "direct-sync-empty.db")
    store.save(DesignBridgeDocument.model_validate(VALID), description="initial")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)

    response = client.post(
        "/api/penpot/projects/demo/selection",
        json={"expected_revision": 1,
            "expected_revision_token": _revision_token(client, 1), "selection": [{"penpot_id": "shape-1", "name": "Unlinked"}]},
    )
    assert response.status_code == 422


def test_penpot_status_and_revision_conflict(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "conflict-sync.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)

    first = client.post(
        "/api/projects/save",
        json={"document": VALID, "description": "initial"},
    )
    assert first.status_code == 200
    assert first.json()["revision"] == 1

    status = client.get("/api/penpot/projects/demo/status?local_revision=1")
    assert status.status_code == 200
    assert status.json()["state"] == "in_sync"
    assert status.json()["current_revision"] == 1

    changed = {**VALID}
    changed["pages"] = [
        {
            **VALID["pages"][0],
            "children": [
                {
                    **VALID["pages"][0]["children"][0],
                    "children": [
                        {
                            **VALID["pages"][0]["children"][0]["children"][0],
                            "text": "Changed elsewhere",
                        },
                        VALID["pages"][0]["children"][0]["children"][1],
                    ],
                }
            ],
        }
    ]
    second = client.post(
        "/api/projects/save",
        json={"document": changed, "description": "external change"},
    )
    assert second.status_code == 200
    assert second.json()["revision"] == 2

    behind = client.get("/api/penpot/projects/demo/status?local_revision=1")
    assert behind.status_code == 200
    assert behind.json()["state"] == "behind"
    assert behind.json()["current_revision"] == 2

    conflict = client.post(
        "/api/penpot/projects/demo/selection",
        json={
            "expected_revision": 1,
            "expected_revision_token": _revision_token(client, 1),
            "selection": [
                {
                    "penpot_id": "shape-1",
                    "designbridge_id": "title",
                    "designbridge_type": "text",
                    "name": "Title",
                    "type": "text",
                    "text": "Stale Penpot edit",
                }
            ],
        },
    )
    assert conflict.status_code == 409
    detail = conflict.json()["detail"]
    assert detail["code"] == "revision_conflict"
    assert detail["expected_revision"] == 1
    assert detail["current_revision"] == 2


def test_penpot_push_succeeds_with_matching_revision(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "matching-sync.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)

    save = client.post(
        "/api/projects/save",
        json={"document": VALID, "description": "initial"},
    )
    assert save.status_code == 200
    assert save.json()["revision"] == 1

    push = client.post(
        "/api/penpot/projects/demo/selection",
        json={
            "expected_revision": 1,
            "expected_revision_token": _revision_token(client, 1),
            "selection": [
                {
                    "penpot_id": "shape-1",
                    "designbridge_id": "title",
                    "designbridge_type": "text",
                    "name": "Title",
                    "type": "text",
                    "text": "Fresh Penpot edit",
                }
            ],
        },
    )
    assert push.status_code == 200
    assert push.json()["revision"] == 2


def test_penpot_current_and_status_include_revision_metadata(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "revision-awareness.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)

    saved = client.post(
        "/api/projects/save",
        json={"document": VALID, "description": "Review me"},
    )
    assert saved.status_code == 200

    current = client.get("/api/penpot/projects/demo/current")
    assert current.status_code == 200
    body = current.json()
    assert body["revision"] == 1
    assert body["description"] == "Review me"
    assert body["created_at"]

    status = client.get("/api/penpot/projects/demo/status?local_revision=0")
    assert status.status_code == 200
    state = status.json()
    assert state["state"] == "behind"
    assert state["description"] == "Review me"
    assert state["updated_at"]


def test_penpot_revision_diff_endpoint(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "revision-diff.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)

    first = client.post(
        "/api/projects/save",
        json={"document": VALID, "description": "initial"},
    )
    assert first.status_code == 200

    changed = {**VALID}
    changed["pages"] = [
        {
            **VALID["pages"][0],
            "children": [
                {
                    **VALID["pages"][0]["children"][0],
                    "children": [
                        {
                            **VALID["pages"][0]["children"][0]["children"][0],
                            "text": "Revision two",
                        },
                        VALID["pages"][0]["children"][0]["children"][1],
                    ],
                }
            ],
        }
    ]
    second = client.post(
        "/api/projects/save",
        json={"document": changed, "description": "change title"},
    )
    assert second.status_code == 200

    response = client.get("/api/penpot/projects/demo/diff?from_revision=1")
    assert response.status_code == 200
    body = response.json()
    assert body["from_revision"] == 1
    assert body["to_revision"] == 2
    assert body["diff"]["summary"]["changed"] == 1
    assert body["diff"]["changed"][0]["node_id"] == "title"
    assert "text" in body["diff"]["changed"][0]["properties"]


def test_penpot_selective_pull_endpoint(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "selective-pull.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)

    assert client.post(
        "/api/projects/save",
        json={"document": VALID, "description": "initial"},
    ).status_code == 200

    changed = DesignBridgeDocument.model_validate(VALID).model_copy(deep=True)
    changed.pages[0].children[0].children[0].text = "Latest title"
    changed.pages[0].children[0].name = "Latest frame"

    assert client.post(
        "/api/projects/save",
        json={
            "document": changed.model_dump(mode="json", exclude_none=True),
            "description": "two changes",
        },
    ).status_code == 200

    partial = client.post(
        "/api/penpot/projects/demo/selective-pull",
        json={"from_revision": 1,
            "from_revision_token": _revision_token(client, 1), "node_ids": ["title"]},
    )
    assert partial.status_code == 200
    body = partial.json()
    assert body["from_revision"] == 1
    assert body["to_revision"] == 2
    assert body["selected_node_ids"] == ["title"]
    assert body["remaining_changed_node_ids"] == ["frame"]
    assert body["can_advance_revision"] is False
    assert body["selected"][0]["node"]["text"] == "Latest title"

    full = client.post(
        "/api/penpot/projects/demo/selective-pull",
        json={"from_revision": 1,
            "from_revision_token": _revision_token(client, 1), "node_ids": ["frame", "title"]},
    )
    assert full.status_code == 200
    assert full.json()["can_advance_revision"] is True


def test_penpot_selective_pull_rejects_added_node(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "selective-pull-added.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)

    client.post("/api/projects/save", json={"document": VALID, "description": "initial"})
    changed = DesignBridgeDocument.model_validate(VALID).model_copy(deep=True)
    changed.pages[0].children[0].children.append(
        type(changed.pages[0].children[0].children[0]).model_validate(
            {"id": "new-label", "type": "text", "name": "New label", "text": "New"}
        )
    )
    client.post(
        "/api/projects/save",
        json={"document": changed.model_dump(mode="json", exclude_none=True), "description": "add node"},
    )

    response = client.post(
        "/api/penpot/projects/demo/selective-pull",
        json={"from_revision": 1,
            "from_revision_token": _revision_token(client, 1), "node_ids": ["new-label"]},
    )
    assert response.status_code == 422


def test_penpot_three_way_review_endpoint(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "three-way.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)

    assert client.post(
        "/api/projects/save",
        json={"document": VALID, "description": "initial"},
    ).status_code == 200

    changed = DesignBridgeDocument.model_validate(VALID).model_copy(deep=True)
    changed.pages[0].children[0].children[0].text = "Changed in DesignBridge"
    assert client.post(
        "/api/projects/save",
        json={
            "document": changed.model_dump(mode="json", exclude_none=True),
            "description": "remote title edit",
        },
    ).status_code == 200

    response = client.post(
        "/api/penpot/projects/demo/three-way-review",
        json={
            "from_revision": 1,
            "from_revision_token": _revision_token(client, 1),
            "snapshots": [
                {
                    "penpot_id": "shape-1",
                    "designbridge_id": "title",
                    "designbridge_type": "text",
                    "name": "Title",
                    "type": "text",
                    "text": "Changed in Penpot",
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["from_revision"] == 1
    assert body["to_revision"] == 2
    assert body["review"]["summary"]["conflict_properties"] == 1
    detail = body["review"]["nodes"][0]["properties"]["text"]
    assert detail["classification"] == "conflict"


def test_penpot_property_resolution_endpoint(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "property-resolution.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)

    assert client.post(
        "/api/projects/save",
        json={"document": VALID, "description": "initial"},
    ).status_code == 200

    changed = DesignBridgeDocument.model_validate(VALID).model_copy(deep=True)
    changed.pages[0].children[0].children[0].text = "Remote text"
    assert client.post(
        "/api/projects/save",
        json={
            "document": changed.model_dump(mode="json", exclude_none=True),
            "description": "remote edit",
        },
    ).status_code == 200

    response = client.post(
        "/api/penpot/projects/demo/resolve-properties",
        json={
            "from_revision": 1,
            "from_revision_token": _revision_token(client, 1),
            "snapshots": [
                {
                    "penpot_id": "shape-1",
                    "designbridge_id": "title",
                    "designbridge_type": "text",
                    "name": "Title",
                    "type": "text",
                    "text": "Local text",
                }
            ],
            "resolutions": [
                {"node_id": "title", "property": "text", "choice": "local"}
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["complete"] is True
    assert body["final_revision"] == 3
    assert body["local_changes"] == {"title": {"text": "Local text"}}
    assert body["document"]["pages"][0]["children"][0]["children"][0]["text"] == "Local text"


def test_penpot_property_resolution_remote_choice_does_not_create_revision(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "property-resolution-remote.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)

    client.post("/api/projects/save", json={"document": VALID, "description": "initial"})
    changed = DesignBridgeDocument.model_validate(VALID).model_copy(deep=True)
    changed.pages[0].children[0].children[0].text = "Remote text"
    client.post(
        "/api/projects/save",
        json={"document": changed.model_dump(mode="json", exclude_none=True), "description": "remote edit"},
    )

    response = client.post(
        "/api/penpot/projects/demo/resolve-properties",
        json={
            "from_revision": 1,
            "from_revision_token": _revision_token(client, 1),
            "snapshots": [
                {
                    "designbridge_id": "title",
                    "type": "text",
                    "name": "Title",
                    "text": "Local text",
                }
            ],
            "resolutions": [
                {"node_id": "title", "property": "text", "choice": "remote"}
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["final_revision"] == 2
    assert body["saved_revision"] is None
    assert body["remote_updates"] == [
        {"node_id": "title", "property": "text", "value": "Remote text"}
    ]


def test_penpot_document_reconciliation_endpoint(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "document-reconciliation.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)

    assert client.post(
        "/api/projects/save",
        json={"document": VALID, "description": "initial"},
    ).status_code == 200

    response = client.post(
        "/api/penpot/projects/demo/document-reconciliation",
        json={
            "from_revision": 1,
            "from_revision_token": _revision_token(client, 1),
            "snapshots": [
                {
                    "designbridge_id": "title",
                    "designbridge_page_id": "page",
                    "page_id": "penpot-page",
                    "page_name": "Page",
                    "name": "Title",
                    "type": "text",
                    "text": "Hello",
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["from_revision"] == 1
    assert body["to_revision"] == 1
    assert body["reconciliation"]["summary"]["expected_nodes"] == 5
    assert body["reconciliation"]["summary"]["linked_nodes"] == 1
    assert body["reconciliation"]["summary"]["missing_nodes"] == 4


def test_penpot_component_report_endpoint(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "component-report.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)
    client.post("/api/projects/save", json={"document": VALID, "description": "initial"})

    response = client.post(
        "/api/penpot/projects/demo/component-report",
        json={
            "snapshots": [
                {
                    "designbridge_id": "card-instance",
                    "designbridge_type": "instance",
                    "component_role": "copy_root",
                    "component_id": "card",
                    "component_root_designbridge_id": "card-instance",
                    "name": "Card instance",
                },
                {
                    "designbridge_id": "card-label",
                    "designbridge_type": "text",
                    "component_role": "copy_member",
                    "component_id": "card",
                    "component_root_designbridge_id": "card-instance",
                    "name": "Label",
                    "text": "Instance label",
                },
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["report"]["summary"]["linked_instances"] == 1
    assert body["report"]["summary"]["overrides_out_of_sync"] == 1


def test_penpot_capture_instance_overrides_endpoint(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "component-capture.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)
    client.post("/api/projects/save", json={"document": VALID, "description": "initial"})

    response = client.post(
        "/api/penpot/projects/demo/capture-instance-overrides",
        json={
            "expected_revision": 1,
            "expected_revision_token": _revision_token(client, 1),
            "instance_ids": ["card-instance"],
            "snapshots": [
                {
                    "designbridge_id": "card-instance",
                    "designbridge_type": "instance",
                    "component_role": "copy_root",
                    "component_id": "card",
                    "component_root_designbridge_id": "card-instance",
                    "name": "Card instance",
                },
                {
                    "designbridge_id": "card-label",
                    "designbridge_type": "text",
                    "component_role": "copy_member",
                    "component_id": "card",
                    "component_root_designbridge_id": "card-instance",
                    "name": "Label",
                    "text": "Instance label",
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["changed"] is True
    assert body["revision"] == 2
    instance = body["document"]["pages"][0]["children"][0]["children"][1]
    assert instance["overrides"] == {
        "card-label": {"text": "Instance label"}
    }


def test_penpot_capture_instance_overrides_blocks_stale_revision(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "component-stale.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)
    client.post("/api/projects/save", json={"document": VALID, "description": "initial"})

    response = client.post(
        "/api/penpot/projects/demo/capture-instance-overrides",
        json={
            "expected_revision": 0,
            "expected_revision_token": _revision_token(client, 1),
            "instance_ids": ["card-instance"],
            "snapshots": [],
        },
    )
    assert response.status_code == 409


def test_instance_overrides_are_validated():
    document = DesignBridgeDocument.model_validate(VALID).model_copy(deep=True)
    instance = document.pages[0].children[0].children[1]
    instance.overrides = {"card-label": {"text": "Instance text"}}
    validated = DesignBridgeDocument.model_validate(
        document.model_dump(mode="json", exclude_none=True)
    )
    assert validated.pages[0].children[0].children[1].overrides["card-label"]["text"] == "Instance text"


def test_non_instance_node_cannot_define_overrides():
    invalid = DesignBridgeDocument.model_validate(VALID).model_dump(mode="json", exclude_none=True)
    invalid["pages"][0]["children"][0]["overrides"] = {
        "title": {"text": "Nope"}
    }
    with pytest.raises(ValidationError):
        DesignBridgeDocument.model_validate(invalid)


def test_instance_override_rejects_unsupported_property():
    invalid = DesignBridgeDocument.model_validate(VALID).model_dump(mode="json", exclude_none=True)
    invalid["pages"][0]["children"][0]["children"][1]["overrides"] = {
        "card-label": {"width": 200}
    }
    with pytest.raises(ValidationError):
        DesignBridgeDocument.model_validate(invalid)


def test_penpot_component_definitions_endpoint(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "component-definitions.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)
    client.post("/api/projects/save", json={"document": VALID, "description": "initial"})

    response = client.post(
        "/api/penpot/projects/demo/component-definitions",
        json={
            "snapshots": [
                {
                    "designbridge_id": "card",
                    "designbridge_type": "component",
                    "component_role": "main_root",
                    "component_id": "card",
                    "name": "Card",
                },
                {
                    "designbridge_id": "card-label",
                    "designbridge_type": "text",
                    "component_role": "main_member",
                    "component_id": "card",
                    "name": "Label",
                    "text": "Changed main label",
                },
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["report"]["summary"]["changed"] == 1
    assert body["report"]["changed_component_ids"] == ["card"]


def test_penpot_capture_component_definitions_endpoint(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "component-definitions-capture.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)
    client.post("/api/projects/save", json={"document": VALID, "description": "initial"})

    response = client.post(
        "/api/penpot/projects/demo/capture-component-definitions",
        json={
            "expected_revision": 1,
            "expected_revision_token": _revision_token(client, 1),
            "component_ids": ["card"],
            "snapshots": [
                {
                    "designbridge_id": "card",
                    "designbridge_type": "component",
                    "component_role": "main_root",
                    "component_id": "card",
                    "name": "Renamed Card",
                },
                {
                    "designbridge_id": "card-label",
                    "designbridge_type": "text",
                    "component_role": "main_member",
                    "component_id": "card",
                    "name": "Label",
                    "text": "Changed main label",
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["changed"] is True
    assert body["revision"] == 2
    assert body["document"]["components"][0]["name"] == "Renamed Card"
    assert body["document"]["components"][0]["children"][0]["text"] == "Changed main label"


def test_penpot_capture_component_definitions_preserves_instance_overrides(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    document = DesignBridgeDocument.model_validate(VALID).model_copy(deep=True)
    document.pages[0].children[0].children[1].overrides = {
        "card-label": {"text": "Instance text"}
    }

    store = DesignStore(tmp_path / "component-definitions-overrides.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)
    client.post(
        "/api/projects/save",
        json={"document": document.model_dump(mode="json", exclude_none=True), "description": "initial"},
    )

    response = client.post(
        "/api/penpot/projects/demo/capture-component-definitions",
        json={
            "expected_revision": 1,
            "expected_revision_token": _revision_token(client, 1),
            "component_ids": ["card"],
            "snapshots": [
                {
                    "designbridge_id": "card",
                    "designbridge_type": "component",
                    "component_role": "main_root",
                    "component_id": "card",
                    "name": "Card",
                },
                {
                    "designbridge_id": "card-label",
                    "designbridge_type": "text",
                    "component_role": "main_member",
                    "component_id": "card",
                    "name": "Label",
                    "text": "Changed main label",
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    instance = body["document"]["pages"][0]["children"][0]["children"][1]
    assert instance["overrides"] == {
        "card-label": {"text": "Instance text"}
    }


def test_penpot_capture_component_definitions_blocks_stale_revision(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    store = DesignStore(tmp_path / "component-definitions-stale.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)
    client.post("/api/projects/save", json={"document": VALID, "description": "initial"})

    response = client.post(
        "/api/penpot/projects/demo/capture-component-definitions",
        json={
            "expected_revision": 0,
            "expected_revision_token": _revision_token(client, 1),
            "component_ids": ["card"],
            "snapshots": [],
        },
    )
    assert response.status_code == 409


def _variant_test_document():
    document = DesignBridgeDocument.model_validate(VALID).model_copy(deep=True)
    base_component = document.components[0]
    base_component.variant_group = "card-state"
    base_component.variant_properties = {"state": "default"}
    base_component.children[0].variant_slot = "label"

    active = type(base_component).model_validate(
        {
            "id": "card-active",
            "type": "component",
            "name": "Card Active",
            "variant_group": "card-state",
            "variant_properties": {"state": "active"},
            "children": [
                {
                    "id": "card-active-label",
                    "type": "text",
                    "name": "Label",
                    "text": "Active",
                    "variant_slot": "label",
                }
            ],
        }
    )
    document.components.append(active)
    return document


def test_variant_schema_rejects_duplicate_property_combination():
    document = _variant_test_document()
    duplicate = document.components[1].model_copy(deep=True)
    duplicate.id = "card-active-duplicate"
    duplicate.children[0].id = "card-active-duplicate-label"
    duplicate.variant_properties = {"state": "active"}
    document.components.append(duplicate)

    with pytest.raises(ValidationError):
        DesignBridgeDocument.model_validate(
            document.model_dump(mode="json", exclude_none=True)
        )


def test_penpot_variant_families_endpoint(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    document = _variant_test_document()
    store = DesignStore(tmp_path / "variants.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)
    client.post(
        "/api/projects/save",
        json={
            "document": document.model_dump(mode="json", exclude_none=True),
            "description": "variants",
        },
    )

    response = client.get("/api/penpot/projects/demo/variants")
    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 1
    assert body["variants"]["summary"]["variant_groups"] == 1
    assert body["variants"]["summary"]["variant_components"] == 2


def test_penpot_variant_switch_plan_endpoint(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    document = _variant_test_document()
    document.pages[0].children[0].children[1].overrides = {
        "card-label": {"text": "Custom"}
    }

    store = DesignStore(tmp_path / "variant-plan.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)
    client.post(
        "/api/projects/save",
        json={
            "document": document.model_dump(mode="json", exclude_none=True),
            "description": "variants",
        },
    )

    response = client.post(
        "/api/penpot/projects/demo/variant-switch-plan",
        json={
            "instance_id": "card-instance",
            "target_component_id": "card-active",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 1
    assert body["plan"]["compatible"] is True
    assert body["plan"]["remapped_overrides"] == {
        "card-active-label": {"text": "Custom"}
    }


def test_penpot_commit_variant_switch_endpoint(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    document = _variant_test_document()
    document.pages[0].children[0].children[1].overrides = {
        "card-label": {"text": "Custom"}
    }

    store = DesignStore(tmp_path / "variant-commit.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)
    client.post(
        "/api/projects/save",
        json={
            "document": document.model_dump(mode="json", exclude_none=True),
            "description": "variants",
        },
    )

    response = client.post(
        "/api/penpot/projects/demo/commit-variant-switch",
        json={
            "expected_revision": 1,
            "expected_revision_token": _revision_token(client, 1),
            "instance_id": "card-instance",
            "target_component_id": "card-active",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 2
    instance = body["document"]["pages"][0]["children"][0]["children"][1]
    assert instance["component_id"] == "card-active"
    assert instance["variant_group"] == "card-state"
    assert instance["overrides"] == {
        "card-active-label": {"text": "Custom"}
    }


def test_penpot_commit_variant_switch_blocks_stale_revision(monkeypatch, tmp_path):
    from app import main as main_module
    from app.storage import DesignStore

    document = _variant_test_document()
    store = DesignStore(tmp_path / "variant-stale.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)
    client.post(
        "/api/projects/save",
        json={
            "document": document.model_dump(mode="json", exclude_none=True),
            "description": "variants",
        },
    )

    response = client.post(
        "/api/penpot/projects/demo/commit-variant-switch",
        json={
            "expected_revision": 0,
            "expected_revision_token": _revision_token(client, 1),
            "instance_id": "card-instance",
            "target_component_id": "card-active",
        },
    )
    assert response.status_code == 409
