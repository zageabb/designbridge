from app.component_sync import component_instance_report, instance_override_changes
from app.models import DesignBridgeDocument

from test_designbridge import VALID


def _root(**extra):
    return {
        "designbridge_id": "card-instance",
        "designbridge_type": "instance",
        "component_role": "copy_root",
        "component_id": "card",
        "component_root_designbridge_id": "card-instance",
        "name": "Card instance",
        **extra,
    }


def _member(**extra):
    return {
        "designbridge_id": "card-label",
        "designbridge_type": "text",
        "component_role": "copy_member",
        "component_id": "card",
        "component_root_designbridge_id": "card-instance",
        "name": "Label",
        "text": "Card",
        **extra,
    }


def test_component_report_recognizes_linked_instance():
    document = DesignBridgeDocument.model_validate(VALID)

    report = component_instance_report(document, [_root(), _member()])

    assert report["summary"]["expected_instances"] == 1
    assert report["summary"]["linked_instances"] == 1
    assert report["summary"]["detached_instances"] == 0
    assert report["instances"][0]["status"] == "linked"
    assert report["instances"][0]["overrides_match"] is True


def test_component_report_detects_safe_text_override():
    document = DesignBridgeDocument.model_validate(VALID)

    report = component_instance_report(
        document,
        [_root(), _member(text="Instance label")],
    )

    instance = report["instances"][0]
    assert instance["discovered_overrides"] == {
        "card-label": {"text": "Instance label"}
    }
    assert instance["overrides_match"] is False
    assert report["overrides_out_of_sync_ids"] == ["card-instance"]


def test_component_report_detects_detached_and_swapped_instances():
    document = DesignBridgeDocument.model_validate(VALID)

    detached = component_instance_report(
        document,
        [{**_root(), "component_role": "basic", "component_id": None}],
    )
    assert detached["detached_instance_ids"] == ["card-instance"]

    swapped = component_instance_report(
        document,
        [{**_root(), "component_id": "other-component"}],
    )
    assert swapped["swapped_instance_ids"] == ["card-instance"]


def test_instance_override_changes_requires_linked_instance():
    document = DesignBridgeDocument.model_validate(VALID)

    changes = instance_override_changes(
        document,
        [_root(), _member(text="Instance label")],
        ["card-instance"],
    )
    assert changes == {
        "card-instance": {
            "card-label": {"text": "Instance label"}
        }
    }


def test_instance_override_changes_rejects_detached_instance():
    import pytest

    document = DesignBridgeDocument.model_validate(VALID)
    with pytest.raises(ValueError, match="detached"):
        instance_override_changes(
            document,
            [{**_root(), "component_role": "basic"}],
            ["card-instance"],
        )


def test_component_definition_report_detects_main_text_change():
    from app.component_sync import component_definition_report

    document = DesignBridgeDocument.model_validate(VALID)
    snapshots = [
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

    report = component_definition_report(document, snapshots)

    assert report["summary"]["changed"] == 1
    component = report["components"][0]
    assert component["component_id"] == "card"
    assert component["child_changes"] == {
        "card-label": {"text": "Changed main label"}
    }


def test_component_definition_report_preserves_instance_override_visibility():
    from app.component_sync import component_definition_report

    document = DesignBridgeDocument.model_validate(VALID).model_copy(deep=True)
    instance = document.pages[0].children[0].children[1]
    instance.overrides = {
        "card-label": {"text": "Instance-specific label"}
    }

    snapshots = [
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

    report = component_definition_report(document, snapshots)
    protected = report["components"][0]["protected_instance_overrides"]

    assert protected == {
        "card-instance": {
            "card-label": ["text"]
        }
    }


def test_component_definition_operations_only_touch_changed_main_nodes():
    from app.component_sync import component_definition_operations

    document = DesignBridgeDocument.model_validate(VALID)
    snapshots = [
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
    ]

    operations = component_definition_operations(
        document,
        snapshots,
        ["card"],
    )

    assert [operation.node_id for operation in operations] == ["card", "card-label"]
    assert operations[0].changes == {"name": "Renamed Card"}
    assert operations[1].changes == {"text": "Changed main label"}


def test_component_definition_operations_reject_missing_main():
    import pytest
    from app.component_sync import component_definition_operations

    document = DesignBridgeDocument.model_validate(VALID)
    with pytest.raises(ValueError, match="missing"):
        component_definition_operations(
            document,
            [],
            ["card"],
        )
