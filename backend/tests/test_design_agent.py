from app.design_agent import build_design_prompt, parse_operation_batch
from app.models import DesignBridgeDocument

from test_designbridge import VALID


def test_parse_operation_batch_from_plain_json():
    batch = parse_operation_batch(
        '{"description":"change title","operations":[{"action":"update_node","node_id":"title","changes":{"text":"New"}}]}'
    )
    assert batch.description == "change title"
    assert batch.operations[0].node_id == "title"


def test_parse_operation_batch_from_fenced_json():
    raw = """```json
{"description":"change title","operations":[{"action":"update_node","node_id":"title","changes":{"text":"New"}}]}
```"""
    batch = parse_operation_batch(raw)
    assert batch.operations[0].action == "update_node"


def test_design_prompt_contains_instruction_and_document():
    document = DesignBridgeDocument.model_validate(VALID)
    prompt = build_design_prompt(document, "Make the title shorter")
    assert "Make the title shorter" in prompt
    assert '"id":"title"' in prompt
    assert "Return ONLY one JSON object" in prompt
