"""
Legal Knowledge Base API router.

Manages legal source documents (MPEP, statutes, firm policies) that ground
the AI's responses. Supports upload, activation, preview, and jurisdiction status.

Auth:
- System admins can upload/manage global sources (firm_id = NULL)
- Firm admins can upload/manage firm-specific sources
- All authenticated users can read sources and jurisdiction status
"""

import uuid
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_active_firm_user, get_system_admin, CurrentUser, get_current_user
from app.models.legal_source import LegalSource, LegalSourceChunk
import inngest
from app.services.storage import upload_to_r2
from app.services.inngest_client import inngest_client
from app.schemas.legal_source import (
    LegalSourceResponse,
    LegalSourceUpdate,
    LegalSourceChunkResponse,
    JurisdictionStatus,
    JurisdictionListItem,
)
from app.services.legal_kb import (
    ingest_legal_source,
    get_jurisdiction_status,
    list_available_jurisdictions,
)

router = APIRouter()


# ── Legal Sources CRUD ──────────────────────────────────────────────────────

def _enrich_stale_flag(source: LegalSource) -> dict:
    """Add is_stale flag to a source response."""
    data = {
        "id": source.id,
        "firm_id": source.firm_id,
        "jurisdiction": source.jurisdiction,
        "doc_type": source.doc_type,
        "title": source.title,
        "version": source.version,
        "is_active": source.is_active,
        "chunk_count": source.chunk_count,
        "source_updated_at": source.source_updated_at,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
        "is_stale": False,
    }
    if source.source_updated_at:
        age = datetime.now(source.source_updated_at.tzinfo) - source.source_updated_at
        data["is_stale"] = age > timedelta(days=365)
    return data


@router.get("/sources", response_model=List[LegalSourceResponse])
async def list_legal_sources(
    jurisdiction: Optional[str] = Query(None, description="Filter by jurisdiction"),
    include_inactive: bool = Query(False, description="Include deactivated sources"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    List all legal sources accessible to the current firm.
    Shows both global sources (firm_id IS NULL) and firm-specific sources.
    """
    query = select(LegalSource).where(
        (LegalSource.firm_id == user.firm_id) | (LegalSource.firm_id.is_(None))
    )

    if jurisdiction:
        query = query.where(LegalSource.jurisdiction == jurisdiction)

    if not include_inactive:
        query = query.where(LegalSource.is_active == True)

    query = query.order_by(LegalSource.jurisdiction, LegalSource.title)
    result = await db.execute(query)
    sources = result.scalars().all()

    return [_enrich_stale_flag(s) for s in sources]


@router.post("/sources", status_code=201)
async def upload_legal_source(
    file: UploadFile = File(...),
    jurisdiction: str = Form(...),
    doc_type: str = Form(...),
    title: str = Form(...),
    version: Optional[str] = Form(None),
    source_updated_at: Optional[str] = Form(None),
    is_global: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Upload a new legal source document (PDF).

    - Global sources (is_global=true) require system admin permissions.
    - Firm-specific sources are scoped to the uploading firm.

    The PDF is extracted, chunked into 300-token sections, embedded via
    Voyage AI, and stored in legal_source_chunks for strict RAG retrieval.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Validate jurisdiction
    valid_jurisdictions = {"USPTO", "EPO", "JPO", "CNIPA", "IP_AUSTRALIA", "WIPO", "firm"}
    if jurisdiction not in valid_jurisdictions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid jurisdiction. Must be one of: {', '.join(sorted(valid_jurisdictions))}"
        )

    # Validate doc_type
    valid_doc_types = {"statute", "rule", "guideline", "firm_policy", "case_law"}
    if doc_type not in valid_doc_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid doc_type. Must be one of: {', '.join(sorted(valid_doc_types))}"
        )

    # Determine firm_id scope
    firm_id = None if is_global else user.firm_id

    # Parse source_updated_at if provided
    parsed_date = None
    if source_updated_at:
        try:
            parsed_date = datetime.fromisoformat(source_updated_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format for source_updated_at")

    # Safely verify user exists to prevent FK violation (500 error)
    from sqlalchemy import text
    try:
        user_check = await db.execute(text("SELECT id FROM users WHERE id = :uid"), {"uid": str(user.id)})
        db_user_id = user.id if user_check.scalar_one_or_none() else None
    except Exception:
        db_user_id = None

    # Safely verify firm exists
    db_firm_id = None
    if firm_id:
        try:
            firm_check = await db.execute(text("SELECT id FROM firms WHERE id = :fid"), {"fid": str(firm_id)})
            db_firm_id = firm_id if firm_check.scalar_one_or_none() else None
        except Exception:
            db_firm_id = None

    # Create the source record
    source = LegalSource(
        firm_id=db_firm_id,
        jurisdiction=jurisdiction,
        doc_type=doc_type,
        title=title,
        version=version,
        source_updated_at=parsed_date,
        uploaded_by=db_user_id,
        is_active=False,  # Start inactive until processing completes
        status="processing",
    )
    
    try:
        db.add(source)
        await db.flush()
        await db.refresh(source)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database constraint error: {str(e)}")

    try:
        # Step 1: Upload PDF to R2 Storage (Handles multi-MB files like MPEP)
        pdf_bytes = await file.read()
        r2_key = f"legal_sources/{source.id}.pdf"
        await upload_to_r2(pdf_bytes, r2_key)
        
        # Step 2: Update source with R2 key
        source.r2_key = r2_key
        db.add(source)
        await db.commit()

        # Step 3: Dispatch Throttled Ingestion Job (Non-blocking)
        # This allows the API to return immediately while the background job 
        # manages Voyage AI rate limits (10k tokens/min).
        await inngest_client.send(
            inngest.Event(
                name="legal.source.ingest",
                data={
                    "source_id": str(source.id),
                    "firm_id": str(db_firm_id) if db_firm_id else None,
                    "user_id": str(user.id),
                },
            )
        )

    except Exception as e:
        # Cleanup on failure
        await db.rollback()
        try:
             await db.execute(text("DELETE FROM legal_sources WHERE id = :sid"), {"sid": str(source.id)})
             await db.commit()
        except:
             pass
        raise HTTPException(status_code=500, detail=f"Failed to initiate background ingestion: {str(e)}")

    return {
        "message": "Legal source upload accepted. Processing started in the background (MPEP large files take ~15-20m).",
        "source_id": str(source.id),
        "title": title,
        "jurisdiction": jurisdiction,
        "status": "processing"
    }


@router.get("/sources/{source_id}", response_model=LegalSourceResponse)
async def get_legal_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get details of a specific legal source."""
    result = await db.execute(
        select(LegalSource).where(
            LegalSource.id == source_id,
            (LegalSource.firm_id == user.firm_id) | (LegalSource.firm_id.is_(None)),
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Legal source not found")

    return _enrich_stale_flag(source)


@router.patch("/sources/{source_id}", response_model=LegalSourceResponse)
async def update_legal_source(
    source_id: uuid.UUID,
    data: LegalSourceUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Update a legal source (toggle active/inactive, update metadata).
    Only the firm that uploaded it (or system admin for global) can modify.
    """
    result = await db.execute(
        select(LegalSource).where(
            LegalSource.id == source_id,
            (LegalSource.firm_id == user.firm_id) | (LegalSource.firm_id.is_(None)),
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Legal source not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(source, field, value)

    await db.flush()
    await db.refresh(source)
    return _enrich_stale_flag(source)


@router.delete("/sources/{source_id}", status_code=204)
async def delete_legal_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Delete a legal source and all its chunks.
    Only the firm that uploaded it can delete firm-specific sources.
    """
    result = await db.execute(
        select(LegalSource).where(
            LegalSource.id == source_id,
            LegalSource.firm_id == user.firm_id,  # Can't delete global sources via this endpoint
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Legal source not found or not authorized to delete")

    await db.delete(source)  # CASCADE deletes chunks


@router.get(
    "/sources/{source_id}/chunks",
    response_model=List[LegalSourceChunkResponse],
)
async def preview_source_chunks(
    source_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Preview the chunked content of a legal source.
    Attorneys can click a source in the trust panel to see the exact text.
    """
    # Verify access
    source_check = await db.execute(
        select(LegalSource.id).where(
            LegalSource.id == source_id,
            (LegalSource.firm_id == user.firm_id) | (LegalSource.firm_id.is_(None)),
        )
    )
    if not source_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Legal source not found")

    offset = (page - 1) * page_size
    result = await db.execute(
        select(LegalSourceChunk)
        .where(LegalSourceChunk.source_id == source_id)
        .order_by(LegalSourceChunk.chunk_index)
        .offset(offset)
        .limit(page_size)
    )
    chunks = result.scalars().all()

    return [
        LegalSourceChunkResponse(
            id=c.id,
            chunk_text=c.chunk_text,
            section=c.section,
            page_number=c.page_number,
            chunk_index=c.chunk_index,
        )
        for c in chunks
    ]


# ── Jurisdiction Status ─────────────────────────────────────────────────────

@router.get("/jurisdictions", response_model=List[JurisdictionListItem])
async def list_jurisdictions(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    List all jurisdictions that have at least one active legal source.
    Used by the JurisdictionSelector component to populate the dropdown.
    """
    jurisdictions = await list_available_jurisdictions(user.firm_id, db)
    return jurisdictions


@router.get("/jurisdictions/{code}/status", response_model=JurisdictionStatus)
async def get_jurisdiction_status_endpoint(
    code: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Check if a jurisdiction has adequate legal sources for strict RAG.
    Shows source count, chunk count, and staleness warnings.
    """
    status = await get_jurisdiction_status(code, user.firm_id, db)
    return status
