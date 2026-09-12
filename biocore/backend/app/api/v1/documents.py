"""Serve generated PDFs by capability token (no session needed — the token is the
capability). Used for erasure certificates, 80G receipts, and muster reports."""
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.core.envelope import ApiError
from app.services import documents

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{category}/{token}")
def get_document(request: Request, category: str, token: str):
    fp = documents.path(category, token)
    if not fp:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "No such document.")
    return FileResponse(fp, media_type="application/pdf",
                        filename=f"{category[:-1]}-{token[:8]}.pdf")
