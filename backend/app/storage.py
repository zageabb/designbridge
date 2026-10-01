from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import DesignBridgeDocument


class DesignStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    current_revision INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS revisions (
                    project_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    document_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, revision),
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def save(
        self,
        document: DesignBridgeDocument,
        *,
        description: str = "",
    ) -> dict[str, Any]:
        project_id = document.document.id
        now = self._now()
        encoded = json.dumps(
            document.model_dump(mode="json", exclude_none=True),
            separators=(",", ":"),
        )
        with self._connect() as db:
            row = db.execute(
                "SELECT current_revision FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()

            if row is None:
                revision = 1
                db.execute(
                    """
                    INSERT INTO projects (id, name, current_revision, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (project_id, document.document.name, revision, now, now),
                )
            else:
                current = int(row["current_revision"])
                db.execute(
                    "DELETE FROM revisions WHERE project_id = ? AND revision > ?",
                    (project_id, current),
                )
                revision = current + 1
                db.execute(
                    """
                    UPDATE projects
                    SET name = ?, current_revision = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (document.document.name, revision, now, project_id),
                )

            db.execute(
                """
                INSERT INTO revisions
                    (project_id, revision, description, document_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, revision, description, encoded, now),
            )

        return {
            "project_id": project_id,
            "revision": revision,
            "description": description,
        }

    def list_projects(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT id, name, current_revision, created_at, updated_at
                FROM projects
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def history(self, project_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT revision, description, created_at
                FROM revisions
                WHERE project_id = ?
                ORDER BY revision DESC
                """,
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def load(self, project_id: str, revision: int | None = None) -> dict[str, Any]:
        with self._connect() as db:
            project = db.execute(
                "SELECT current_revision FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise KeyError(project_id)
            target = revision or int(project["current_revision"])
            row = db.execute(
                """
                SELECT revision, description, document_json, created_at
                FROM revisions
                WHERE project_id = ? AND revision = ?
                """,
                (project_id, target),
            ).fetchone()
            if row is None:
                raise KeyError(f"{project_id}@{target}")

        document = DesignBridgeDocument.model_validate_json(row["document_json"])
        return {
            "revision": int(row["revision"]),
            "description": row["description"],
            "created_at": row["created_at"],
            "document": document,
        }

    def _step(self, project_id: str, delta: int) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT current_revision FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if row is None:
                raise KeyError(project_id)
            current = int(row["current_revision"])
            target = current + delta
            exists = db.execute(
                """
                SELECT 1 FROM revisions
                WHERE project_id = ? AND revision = ?
                """,
                (project_id, target),
            ).fetchone()
            if not exists:
                raise ValueError("no revision available")
            db.execute(
                "UPDATE projects SET current_revision = ?, updated_at = ? WHERE id = ?",
                (target, self._now(), project_id),
            )
        return self.load(project_id, target)

    def undo(self, project_id: str) -> dict[str, Any]:
        return self._step(project_id, -1)

    def redo(self, project_id: str) -> dict[str, Any]:
        return self._step(project_id, 1)
