from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import ValidationError

from .models import DesignBridgeDocument
from .operations import OperationBatch, apply_operations

app = FastAPI(title="DesignBridge API", version="0.3.0")
ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT / "web"


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "designbridge", "version": "0.3.0"}


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


@app.get("/")
def index():
    return FileResponse(WEB_ROOT / "index.html")
