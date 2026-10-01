from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import ValidationError

from .design_agent import propose_operations
from .models import DesignBridgeDocument
from .operations import OperationBatch, apply_operations
from .storage import DesignStore

app = FastAPI(title="DesignBridge API", version="0.4.0")
ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT / "web"
DATA_ROOT = ROOT / "data"
STORE = DesignStore(DATA_ROOT / "designbridge.db")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "designbridge", "version": "0.4.0"}


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
