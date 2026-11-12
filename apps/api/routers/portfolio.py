from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status

from agent.handoffs import EvidenceItem
from apps.api.auth.security import AuthenticatedUser
from apps.api.context import AppContext
from apps.api.dependencies import get_context, get_current_user
from apps.api.portfolio_store import (
    delete_uploaded_evidence,
    list_uploaded_evidence,
    save_uploaded_evidence,
)
from rag.ingest.pipeline import IngestionPipeline

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".md", ".markdown", ".txt"}


def _suffix(filename: str) -> str:
    lowered = filename.lower()
    return next((suffix for suffix in ALLOWED_SUFFIXES if lowered.endswith(suffix)), "")


@router.get("", response_model=list[EvidenceItem])
async def list_portfolio(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> list[EvidenceItem]:
    return await list_uploaded_evidence(
        context.store,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
    )


@router.post("/upload", response_model=list[EvidenceItem])
async def upload_portfolio(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
    file: Annotated[UploadFile, File()],
    persona: Annotated[str, Form(min_length=2, max_length=100)],
    skills: Annotated[str, Form(max_length=1_000)] = "",
) -> list[EvidenceItem]:
    if context.store is None:
        raise HTTPException(status_code=503, detail="Portfolio store is unavailable")
    filename = file.filename or "portfolio.txt"
    suffix = _suffix(filename)
    if not suffix:
        raise HTTPException(status_code=415, detail="Upload a PDF, Markdown, or text file")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Portfolio file exceeds 5 MiB")
    pipeline = IngestionPipeline(tenant_id=user.tenant_id, persona=persona)
    metadata: dict[str, object] = {
        "skills": [item.strip() for item in skills.split(",") if item.strip()],
        "data_origin": "private_user_data_not_committed",
    }
    try:
        if suffix == ".pdf":
            items = pipeline.load_pdf_bytes(content, filename=filename, **metadata)
        else:
            items = pipeline.load_text(
                content.decode("utf-8"),
                filename=filename,
                skills=metadata["skills"],
                data_origin=metadata["data_origin"],
            )
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Portfolio file could not be parsed") from exc
    if not items:
        raise HTTPException(status_code=422, detail="Portfolio file contains no extractable text")
    return await save_uploaded_evidence(
        context.store,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        items=items,
    )


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio_item(
    evidence_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> Response:
    if context.store is None:
        raise HTTPException(status_code=503, detail="Portfolio store is unavailable")
    await delete_uploaded_evidence(
        context.store,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        evidence_id=evidence_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
