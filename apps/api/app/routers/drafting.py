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


@router.post("/generate", response_model=DraftResponse)
async def generate_draft(
    data: DraftGenerationRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    AI-generate a patent application draft via background job.
    Returns the Draft object immediately. The frontend should poll or listen for completion.
    """
    description = data.invention_description or data.description or ""
    if not description.strip():
        raise HTTPException(status_code=400, detail="Invention description is required")

    # 1. Create a Draft placeholder in 'processing' status
    draft = Draft(
        firm_id=user.firm_id,
        created_by=user.id,
        title=f"Draft: {data.technical_field or 'New Invention'}",
        content="# Generating Draft...\nPlease wait while our expert system prepares your application.",
        version=1,
        status="processing"
    )
    db.add(draft)
    await db.flush()
    await db.refresh(draft)

    # 2. Trigger Inngest Event
    from app.services.inngest_client import inngest_client
    import inngest

    # Prepare data for Inngest
    # We pass all IDs and parameters so the background job has full context
    await inngest_client.send(
        inngest.Event(
            name="patent.draft.generate",
            data={
                "draft_id": str(draft.id),
                "firm_id": str(user.firm_id),
                "user_id": str(user.id),
                "invention_description": description,
                "technical_field": data.technical_field,
                "prior_art_context": data.prior_art_context,
                "claim_style": data.claim_style,
                "spec_context": data.spec_context,
                "jurisdiction": data.jurisdiction,
                "patent_id": data.patent_id,
            }
        )
    )

    return DraftResponse.model_validate(draft)


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
