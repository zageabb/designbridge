import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models import DesignBridgeDocument


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
