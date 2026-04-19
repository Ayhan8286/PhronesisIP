"""
Office action management and AI response generation.
Full pipeline: upload PDF → parse rejections → fetch cited refs → generate response.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import OfficeAction, OAResponseDraft, Patent, PatentClaim
from app.schemas import (
    OfficeActionCreate, OfficeActionResponse,
    OAResponseDraftCreate, OAResponseDraftResponse,
    OAResponseGenerationRequest,
)
from app.auth import get_active_firm_user, CurrentUser
from app.services.llm import generate_oa_response_stream

router = APIRouter()


@router.get("/", response_model=list[OfficeActionResponse])
async def list_office_actions(
    patent_id: uuid.UUID | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """List office actions, optionally filtered by patent or status."""
    query = (
        select(OfficeAction)
        .join(Patent, OfficeAction.patent_id == Patent.id)
        .where(Patent.firm_id == user.firm_id)
    )
    if patent_id:
        query = query.where(OfficeAction.patent_id == patent_id)
    if status:
        query = query.where(OfficeAction.status == status)

    query = query.order_by(OfficeAction.response_deadline.asc())
    result = await db.execute(query)
    actions = result.scalars().all()
    return [OfficeActionResponse.model_validate(a) for a in actions]


@router.get("/{oa_id}", response_model=OfficeActionResponse)
async def get_office_action(
    oa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Get a single office action."""
    result = await db.execute(
        select(OfficeAction)
        .join(Patent, OfficeAction.patent_id == Patent.id)
        .where(OfficeAction.id == oa_id, Patent.firm_id == user.firm_id)
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Office action not found")
    return OfficeActionResponse.model_validate(action)


@router.post("/", response_model=OfficeActionResponse, status_code=201)
async def create_office_action(
    data: OfficeActionCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Create an office action record."""
    patent = await db.execute(
        select(Patent).where(
            Patent.id == data.patent_id, Patent.firm_id == user.firm_id
        )
    )
    if not patent.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patent not found")

    action = OfficeAction(**data.model_dump())
    db.add(action)
    await db.flush()
    await db.refresh(action)
    return OfficeActionResponse.model_validate(action)


# ---------------------------------------------------------------------------
# Response Drafts
# ---------------------------------------------------------------------------

@router.get("/{oa_id}/drafts", response_model=list[OAResponseDraftResponse])
async def list_response_drafts(
    oa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """List response drafts for an office action."""
    result = await db.execute(
        select(OAResponseDraft)
        .where(OAResponseDraft.office_action_id == oa_id)
        .order_by(OAResponseDraft.version.desc())
    )
    drafts = result.scalars().all()
    return [OAResponseDraftResponse.model_validate(d) for d in drafts]


@router.post("/{oa_id}/generate-response", response_model=OAResponseDraftResponse)
async def generate_oa_response(
    oa_id: uuid.UUID,
    data: OAResponseGenerationRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    AI-generate a response to an office action via background job.
    Returns the Draft object immediately. The frontend should poll or listen for completion.
    """
    # 1. Get the office action with patent
    result = await db.execute(
        select(OfficeAction)
        .join(Patent, OfficeAction.patent_id == Patent.id)
        .where(OfficeAction.id == oa_id, Patent.firm_id == user.firm_id)
        .options(selectinload(OfficeAction.patent))
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Office action not found")

    if not action.extracted_text:
        raise HTTPException(
            status_code=400,
            detail="No extracted text. Upload the office action PDF first.",
        )

    # 2. Get latest version number
    from sqlalchemy import func
    v_res = await db.execute(
        select(func.max(OAResponseDraft.version))
        .where(OAResponseDraft.office_action_id == oa_id)
    )
    max_v = v_res.scalar() or 0

    # 3. Create Draft placeholder
    draft = OAResponseDraft(
        office_action_id=oa_id,
        firm_id=user.firm_id,
        created_by=user.id,
        draft_content="# Analyzing Rejections...\nPlease wait while our expert prepares the legal response.",
        ai_model_used=settings.LLM_MODEL,
        version=max_v + 1,
        status="processing"
    )
    db.add(draft)
    await db.flush()
    await db.refresh(draft)

    # 4. Trigger Inngest Event
    from app.services.inngest_client import inngest_client
    import inngest

    await inngest_client.send(
        inngest.Event(
            name="patent.oa.response.generate",
            data={
                "draft_id": str(draft.id),
                "oa_id": str(oa_id),
                "firm_id": str(user.firm_id),
                "user_id": str(user.id),
                "response_strategy": data.response_strategy,
                "additional_context": data.additional_context,
                "jurisdiction": data.jurisdiction,
            }
        )
    )

    return OAResponseDraftResponse.model_validate(draft)

@router.post("/{oa_id}/drafts", response_model=OAResponseDraftResponse)
async def save_response_draft(
    oa_id: uuid.UUID,
    data: OAResponseDraftCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Save a new version of a response draft.
    Automatically updates the Office Action status to 'responded'.
    """
    # Verify OA exists and belongs to firm
    oa_res = await db.execute(
        select(OfficeAction).where(
            OfficeAction.id == oa_id, OfficeAction.firm_id == user.firm_id
        )
    )
    oa = oa_res.scalar_one_or_none()
    if not oa:
        raise HTTPException(status_code=404, detail="Office action not found")

    # Get latest version number
    v_res = await db.execute(
        select(func.max(OAResponseDraft.version))
        .where(OAResponseDraft.office_action_id == oa_id)
    )
    max_v = v_res.scalar() or 0

    draft = OAResponseDraft(
        office_action_id=oa_id,
        firm_id=user.firm_id,
        created_by=user.id,
        draft_content=data.draft_content,
        ai_model_used=data.ai_model_used or "gemini-2.0-flash",
        version=max_v + 1,
    )
    
    # Update OA status (UX Requirement)
    oa.status = "responded"
    
    db.add(draft)
    db.add(oa)
    await db.commit()
    await db.refresh(draft)
    return OAResponseDraftResponse.model_validate(draft)
