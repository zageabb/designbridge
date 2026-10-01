from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import ValidationError

from .design_agent import propose_operations
from .models import DesignBridgeDocument
from .operations import OperationBatch, apply_operations
from .penpot_sync import PenpotShapeSnapshot, compare_penpot_snapshot
from .revision_diff import compare_documents, selective_pull_plan
from .storage import DesignStore

app = FastAPI(title="DesignBridge API", version="0.11.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4400",
        "http://127.0.0.1:4400",
        "https://design.penpot.app",
        "https://penpot.app",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT / "web"
DATA_ROOT = ROOT / "data"
STORE = DesignStore(DATA_ROOT / "designbridge.db")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "designbridge", "version": "0.11.0"}


@app.post("/api/validate")
def validate_design(document: DesignBridgeDocument) -> dict:
    return {
        "valid": True,
        "document_id": document.document.id,
        "pages": len(document.pages),
    }


@app.post("/api/normalize")
def normalize_design(payload: dict) -> dict:
    try:
        document = DesignBridgeDocument.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    return document.model_dump(mode="json", exclude_none=True)


@app.post("/api/operations/apply")
def apply_design_operations(payload: dict) -> dict:
    try:
        document = DesignBridgeDocument.model_validate(payload["document"])
        batch = OperationBatch.model_validate(payload["batch"])
        result = apply_operations(document, batch)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"missing field: {exc.args[0]}") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.model_dump(mode="json", exclude_none=True)


@app.post("/api/operations/propose")
async def propose_design_operations(payload: dict) -> dict:
    try:
        document = DesignBridgeDocument.model_validate(payload["document"])
        instruction = str(payload["instruction"]).strip()
        if not instruction:
            raise ValueError("instruction is required")
        batch = await propose_operations(
            document,
            instruction,
            base_url=payload.get("ollama_url"),
            model=payload.get("model"),
            selection_ids=[str(item) for item in payload.get("selection_ids", [])],
        )
        preview = apply_operations(document, batch)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"missing field: {exc.args[0]}") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"design model request failed: {exc}") from exc

    return {
        "batch": batch.model_dump(mode="json", exclude_none=True),
        "preview": preview.model_dump(mode="json", exclude_none=True),
    }


@app.post("/api/penpot/compare")
def compare_penpot(payload: dict) -> dict:
    try:
        document = DesignBridgeDocument.model_validate(payload["document"])
        snapshots = [
            PenpotShapeSnapshot.model_validate(item)
            for item in payload.get("selection", [])
            if item.get("designbridge_id")
        ]
        if not snapshots:
            raise ValueError("no DesignBridge-linked Penpot shapes supplied")
        batch = compare_penpot_snapshot(document, snapshots)
        preview = apply_operations(document, batch)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"missing field: {exc.args[0]}") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "batch": batch.model_dump(mode="json", exclude_none=True),
        "preview": preview.model_dump(mode="json", exclude_none=True),
    }


@app.get("/api/penpot/projects/{project_id}/current")
def penpot_current_project(project_id: str) -> dict:
    try:
        result = STORE.load(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="project not found")
    return {
        "project_id": project_id,
        "revision": result["revision"],
        "description": result["description"],
        "created_at": result["created_at"],
        "document": result["document"].model_dump(mode="json", exclude_none=True),
    }


@app.get("/api/penpot/projects/{project_id}/status")
def penpot_project_status(project_id: str, local_revision: int | None = None) -> dict:
    try:
        current = STORE.load(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="project not found")

    current_revision = int(current["revision"])
    if local_revision is None:
        state = "unknown"
    elif local_revision == current_revision:
        state = "in_sync"
    elif local_revision < current_revision:
        state = "behind"
    else:
        state = "ahead"

    return {
        "project_id": project_id,
        "local_revision": local_revision,
        "current_revision": current_revision,
        "state": state,
        "updated_at": current["created_at"],
        "description": current["description"],
    }


@app.get("/api/penpot/projects/{project_id}/diff")
def penpot_project_diff(
    project_id: str,
    from_revision: int,
    to_revision: int | None = None,
) -> dict:
    try:
        before = STORE.load(project_id, from_revision)
        after = STORE.load(project_id, to_revision)
    except KeyError:
        raise HTTPException(status_code=404, detail="project or revision not found")

    return {
        "project_id": project_id,
        "from_revision": before["revision"],
        "to_revision": after["revision"],
        "from_description": before["description"],
        "to_description": after["description"],
        "diff": compare_documents(before["document"], after["document"]),
    }


@app.post("/api/penpot/projects/{project_id}/selective-pull")
def penpot_selective_pull(project_id: str, payload: dict) -> dict:
    try:
        from_revision = int(payload["from_revision"])
        node_ids = [str(item) for item in payload.get("node_ids", [])]
        before = STORE.load(project_id, from_revision)
        after = STORE.load(project_id)
        plan = selective_pull_plan(before["document"], after["document"], node_ids)
    except KeyError as exc:
        if exc.args and exc.args[0] == "from_revision":
            raise HTTPException(status_code=422, detail="from_revision is required") from exc
        raise HTTPException(status_code=404, detail="project or revision not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "project_id": project_id,
        "from_revision": before["revision"],
        "to_revision": after["revision"],
        **plan,
    }


@app.post("/api/penpot/projects/{project_id}/selection")
def penpot_sync_selection(project_id: str, payload: dict) -> dict:
    try:
        current = STORE.load(project_id)
        expected_revision = payload.get("expected_revision")
        if expected_revision is None:
            raise ValueError("expected_revision is required")
        if int(expected_revision) != int(current["revision"]):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "revision_conflict",
                    "message": "Penpot is based on an older DesignBridge revision",
                    "expected_revision": int(expected_revision),
                    "current_revision": int(current["revision"]),
                },
            )
        document = current["document"]
        snapshots = [
            PenpotShapeSnapshot.model_validate(item)
            for item in payload.get("selection", [])
            if item.get("designbridge_id")
        ]
        if not snapshots:
            raise ValueError("no DesignBridge-linked Penpot shapes supplied")
        batch = compare_penpot_snapshot(document, snapshots)
        preview = apply_operations(document, batch)
        saved = STORE.save(
            preview.document,
            description=str(payload.get("description") or "Penpot selection sync"),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="project not found")
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "project_id": project_id,
        "revision": saved["revision"],
        "batch": batch.model_dump(mode="json", exclude_none=True),
        "document": preview.document.model_dump(mode="json", exclude_none=True),
        "changes": preview.changes,
    }


@app.get("/api/projects")
def list_projects() -> dict:
    return {"projects": STORE.list_projects()}


@app.post("/api/projects/save")
def save_project(payload: dict) -> dict:
    try:
        document = DesignBridgeDocument.model_validate(payload["document"])
        description = str(payload.get("description") or "").strip()
        return STORE.save(document, description=description)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"missing field: {exc.args[0]}") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@app.get("/api/projects/{project_id}")
def load_project(project_id: str, revision: int | None = None) -> dict:
    try:
        result = STORE.load(project_id, revision)
    except KeyError:
        raise HTTPException(status_code=404, detail="project or revision not found")
    return {
        **{key: value for key, value in result.items() if key != "document"},
        "document": result["document"].model_dump(mode="json", exclude_none=True),
    }


@app.get("/api/projects/{project_id}/history")
def project_history(project_id: str) -> dict:
    return {"history": STORE.history(project_id)}


@app.post("/api/projects/{project_id}/undo")
def undo_project(project_id: str) -> dict:
    try:
        result = STORE.undo(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="project not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        **{key: value for key, value in result.items() if key != "document"},
        "document": result["document"].model_dump(mode="json", exclude_none=True),
    }


@app.post("/api/projects/{project_id}/redo")
def redo_project(project_id: str) -> dict:
    try:
        result = STORE.redo(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="project not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        **{key: value for key, value in result.items() if key != "document"},
        "document": result["document"].model_dump(mode="json", exclude_none=True),
    }


@app.get("/")
def index():
    return FileResponse(WEB_ROOT / "index.html")
