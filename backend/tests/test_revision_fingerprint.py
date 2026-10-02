import json
import sqlite3

from fastapi.testclient import TestClient

from app.models import DesignBridgeDocument
from app.storage import DesignStore
from test_designbridge import VALID


def test_revision_token_is_deterministic_and_persisted(tmp_path):
    store = DesignStore(tmp_path / "tokens.db")
    document = DesignBridgeDocument.model_validate(VALID)

    expected = DesignStore.revision_token(document)
    saved = store.save(document, description="initial")
    loaded = store.load("demo")
    history = store.history("demo")

    assert len(expected) == 64
    assert saved["revision_token"] == expected
    assert loaded["revision_token"] == expected
    assert history[0]["revision_token"] == expected


def test_legacy_revision_rows_are_backfilled_with_tokens(tmp_path):
    path = tmp_path / "legacy.db"
    document = DesignBridgeDocument.model_validate(VALID)
    encoded = json.dumps(
        document.model_dump(mode="json", exclude_none=True),
        separators=(",", ":"),
    )

    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                current_revision INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE revisions (
                project_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                document_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (project_id, revision)
            );
            """
        )
        db.execute(
            """
            INSERT INTO projects
                (id, name, current_revision, created_at, updated_at)
            VALUES ('demo', 'Demo', 1, 'now', 'now')
            """
        )
        db.execute(
            """
            INSERT INTO revisions
                (project_id, revision, description, document_json, created_at)
            VALUES ('demo', 1, 'legacy', ?, 'now')
            """,
            (encoded,),
        )

    store = DesignStore(path)
    loaded = store.load("demo")

    assert loaded["revision_token"] == DesignStore.revision_token(document)
    with sqlite3.connect(path) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(revisions)")}
        persisted = db.execute(
            "SELECT revision_token FROM revisions WHERE project_id='demo' AND revision=1"
        ).fetchone()[0]

    assert "revision_token" in columns
    assert persisted == loaded["revision_token"]


def test_reused_revision_number_gets_different_content_token(tmp_path):
    store = DesignStore(tmp_path / "reuse.db")
    a = DesignBridgeDocument.model_validate(VALID)
    first = store.save(a, description="A")

    b = a.model_copy(deep=True)
    b.pages[0].children[0].children[0].text = "B"
    second = store.save(b, description="B")

    store.undo("demo")

    c = a.model_copy(deep=True)
    c.pages[0].children[0].children[0].text = "C"
    replacement = store.save(c, description="C")

    assert first["revision"] == 1
    assert second["revision"] == 2
    assert replacement["revision"] == 2
    assert replacement["revision_token"] != second["revision_token"]


def test_status_detects_same_revision_number_with_different_token(monkeypatch, tmp_path):
    from app import main as main_module

    store = DesignStore(tmp_path / "status-diverged.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)

    a = DesignBridgeDocument.model_validate(VALID)
    store.save(a, description="A")

    b = a.model_copy(deep=True)
    b.pages[0].children[0].children[0].text = "B"
    old_revision_two = store.save(b, description="B")

    store.undo("demo")
    c = a.model_copy(deep=True)
    c.pages[0].children[0].children[0].text = "C"
    replacement = store.save(c, description="C")

    response = client.get(
        "/api/penpot/projects/demo/status"
        f"?local_revision=2&local_revision_token={old_revision_two['revision_token']}"
    )
    assert response.status_code == 200
    body = response.json()

    assert replacement["revision"] == 2
    assert body["state"] == "diverged"
    assert body["current_revision"] == 2
    assert body["current_revision_token"] == replacement["revision_token"]


def test_status_marks_matching_number_without_token_unverified(monkeypatch, tmp_path):
    from app import main as main_module

    store = DesignStore(tmp_path / "status-unverified.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)
    saved = store.save(DesignBridgeDocument.model_validate(VALID), description="initial")

    response = client.get("/api/penpot/projects/demo/status?local_revision=1")
    assert response.status_code == 200
    body = response.json()

    assert saved["revision"] == 1
    assert body["state"] == "unverified"
    assert body["current_revision_token"] == saved["revision_token"]


def test_penpot_write_requires_matching_revision_token(monkeypatch, tmp_path):
    from app import main as main_module

    store = DesignStore(tmp_path / "write-token.db")
    monkeypatch.setattr(main_module, "STORE", store)
    client = TestClient(main_module.app)
    saved = store.save(DesignBridgeDocument.model_validate(VALID), description="initial")

    selection = [
        {
            "designbridge_id": "title",
            "type": "text",
            "name": "Title",
            "text": "Changed",
        }
    ]

    missing = client.post(
        "/api/penpot/projects/demo/selection",
        json={"expected_revision": 1, "selection": selection},
    )
    assert missing.status_code == 422

    diverged = client.post(
        "/api/penpot/projects/demo/selection",
        json={
            "expected_revision": 1,
            "expected_revision_token": "0" * 64,
            "selection": selection,
        },
    )
    assert diverged.status_code == 409
    assert diverged.json()["detail"]["code"] == "revision_diverged"

    valid = client.post(
        "/api/penpot/projects/demo/selection",
        json={
            "expected_revision": 1,
            "expected_revision_token": saved["revision_token"],
            "selection": selection,
        },
    )
    assert valid.status_code == 200
    assert valid.json()["revision"] == 2
    assert len(valid.json()["revision_token"]) == 64
