from pathlib import Path

from app.models import DesignBridgeDocument
from app.storage import DesignStore

from test_designbridge import VALID


def make_document(name: str = "Demo") -> DesignBridgeDocument:
    payload = {**VALID, "document": {"id": "demo", "name": name}}
    return DesignBridgeDocument.model_validate(payload)


def test_store_save_load_and_history(tmp_path: Path):
    store = DesignStore(tmp_path / "designbridge.db")
    first = store.save(make_document(), description="initial")
    second_doc = make_document()
    second_doc.pages[0].children[0].children[0].text = "Changed"
    second = store.save(second_doc, description="change title")

    assert first["revision"] == 1
    assert second["revision"] == 2
    assert store.load("demo")["document"].pages[0].children[0].children[0].text == "Changed"
    history = store.history("demo")
    assert [item["revision"] for item in history] == [2, 1]


def test_store_undo_and_redo(tmp_path: Path):
    store = DesignStore(tmp_path / "designbridge.db")
    store.save(make_document(), description="initial")
    changed = make_document()
    changed.pages[0].children[0].children[0].text = "Changed"
    store.save(changed, description="changed")

    undone = store.undo("demo")
    assert undone["revision"] == 1
    assert undone["document"].pages[0].children[0].children[0].text == "Hello"

    redone = store.redo("demo")
    assert redone["revision"] == 2
    assert redone["document"].pages[0].children[0].children[0].text == "Changed"


def test_save_after_undo_discards_redo_branch(tmp_path: Path):
    store = DesignStore(tmp_path / "designbridge.db")
    store.save(make_document(), description="initial")

    second = make_document()
    second.pages[0].children[0].children[0].text = "Second"
    store.save(second, description="second")

    third = make_document()
    third.pages[0].children[0].children[0].text = "Third"
    store.save(third, description="third")

    store.undo("demo")
    replacement = make_document()
    replacement.pages[0].children[0].children[0].text = "Replacement"
    saved = store.save(replacement, description="replacement")

    assert saved["revision"] == 3
    assert store.load("demo")["document"].pages[0].children[0].children[0].text == "Replacement"

    try:
        store.redo("demo")
    except ValueError:
        pass
    else:
        raise AssertionError("redo should be unavailable after a divergent save")
