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
