import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models import DesignBridgeDocument


VALID = {
    "format": "designbridge",
    "version": "0.1",
    "document": {"id": "demo", "name": "Demo"},
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
                        }
                    ],
                }
            ],
        }
    ],
}


def test_valid_document():
    document = DesignBridgeDocument.model_validate(VALID)
    assert document.document.id == "demo"
    assert document.pages[0].children[0].children[0].text == "Hello"


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


def test_validate_endpoint():
    client = TestClient(app)
    response = client.post("/api/validate", json=VALID)
    assert response.status_code == 200
    assert response.json() == {"valid": True, "document_id": "demo", "pages": 1}
