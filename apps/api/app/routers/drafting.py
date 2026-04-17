"""
Patent application drafting with AI assistance.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Draft, Patent
from app.schemas import (
    DraftCreate, DraftUpdate, DraftResponse, DraftGenerationRequest,
)
from app.auth import get_active_firm_user, CurrentUser
from app.services.llm import generate_patent_draft_stream

router = APIRouter()


@router.get("/", response_model=list[DraftResponse])
async def list_drafts(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """List all drafts for the current user's firm."""
    result = await db.execute(
        select(Draft)
        .where(Draft.firm_id == user.firm_id)
        .order_by(Draft.updated_at.desc())
    )
    drafts = result.scalars().all()
    return [DraftResponse.model_validate(d) for d in drafts]


@router.get("/{draft_id}", response_model=DraftResponse)
async def get_draft(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Get a single draft."""
    result = await db.execute(
        select(Draft).where(
            Draft.id == draft_id,
            Draft.firm_id == user.firm_id,
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return DraftResponse.model_validate(draft)


@router.post("/", response_model=DraftResponse, status_code=201)
async def create_draft(
    data: DraftCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Create a new draft manually."""
    draft = Draft(
        firm_id=user.firm_id,
        created_by=user.id,
        **data.model_dump(),
    )
    db.add(draft)
    await db.flush()
    await db.refresh(draft)
    return DraftResponse.model_validate(draft)


@router.patch("/{draft_id}", response_model=DraftResponse)
async def update_draft(
    draft_id: uuid.UUID,
    data: DraftUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Update draft content or status."""
    result = await db.execute(
        select(Draft).where(
            Draft.id == draft_id,
            Draft.firm_id == user.firm_id,
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(draft, field, value)

    await db.flush()
    await db.refresh(draft)
    return DraftResponse.model_validate(draft)


@router.post("/generate")
async def generate_draft(
    data: DraftGenerationRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    AI-generate a patent application draft.
    Returns a streamed response for real-time display.

    When jurisdiction is provided, enables STRICT LEGAL RAG:
    - Retrieves relevant legal authority from the Legal Knowledge Base
    - Forbids the LLM from using general training knowledge
    - Enforces [Source: ...] citations on every legal claim
    - Sends [SOURCES] metadata event for the UI trust panel
    """
    # Handle both field names from frontend
    description = data.invention_description or data.description or ""
    if not description.strip():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invention description is required")

    # Strict RAG: perform dual retrieval when jurisdiction is specified
    legal_context_text = None
    patent_context_text = None
    sources_metadata = None
    firm_name = "the firm"

    if data.jurisdiction:
        from app.services.ingestion import retrieve_full_context
        from app.models import Firm

        # Get firm name for the prompt
        firm_result = await db.execute(
            select(Firm.name).where(Firm.id == user.firm_id)
        )
        firm_row = firm_result.first()
        if firm_row:
            firm_name = firm_row.name

        patent_id = uuid.UUID(data.patent_id) if data.patent_id else None

        context = await retrieve_full_context(
            query=description[:500],  # Use first 500 chars as query
            jurisdiction=data.jurisdiction,
            firm_id=user.firm_id,
            user_id=user.id,
            db=db,
            patent_id=patent_id,
        )

        legal_context_text = context["legal_context_text"]
        patent_context_text = context["patent_context_text"]
        sources_metadata = {
            "sources_used": context["sources_used"],
            "has_legal_authority": context["has_legal_authority"],
            "jurisdiction": context["jurisdiction"],
        }

    import json as json_lib
    from app.services.citation_validator import validate_citations

    async def wrapped_stream():
        full_response_parts = []

        async for chunk in generate_patent_draft_stream(
            invention_description=description,
            technical_field=data.technical_field,
            prior_art_context=data.prior_art_context,
            claim_style=data.claim_style,
            spec_context=data.spec_context,
            firm_id=user.firm_id,
            user_id=user.id,
            jurisdiction=data.jurisdiction,
            legal_context_text=legal_context_text,
            patent_context_text=patent_context_text,
            firm_name=firm_name,
        ):
            # Collect full response for citation validation
            if chunk.startswith("data: ") and chunk.strip() not in ("data: [DONE]",):
                full_response_parts.append(chunk[6:].strip())
            yield chunk

        # After stream completes, send citation validation + sources metadata
        if data.jurisdiction and sources_metadata:
            full_text = "".join(full_response_parts)
            validation = validate_citations(
                full_text,
                sources_metadata.get("sources_used", []),
            )
            sources_event = {
                **sources_metadata,
                "citation_validation": dict(validation),
            }
            yield f"data: [SOURCES]{json_lib.dumps(sources_event)}\n\n"

    return StreamingResponse(
        wrapped_stream(),
        media_type="text/event-stream",
    )


@router.delete("/{draft_id}", status_code=204)
async def delete_draft(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Delete a draft."""
    result = await db.execute(
        select(Draft).where(
            Draft.id == draft_id,
            Draft.firm_id == user.firm_id,
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    await db.delete(draft)
