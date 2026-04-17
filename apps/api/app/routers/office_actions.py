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


@router.post("/{oa_id}/generate-response")
async def generate_oa_response(
    oa_id: uuid.UUID,
    data: OAResponseGenerationRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    AI-generate a response to an office action.
    Loads the patent's actual claims for claim-by-claim arguments.
    Streams the response for real-time display.

    When jurisdiction is provided, enables STRICT LEGAL RAG:
    - Retrieves relevant MPEP/statute/rule sections from the Legal Knowledge Base
    - Forbids the LLM from using general training knowledge
    - Enforces [Source: ...] citations on every legal claim
    - Sends [SOURCES] metadata event for the UI trust panel
    """
    # Get the office action with patent
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

    # Load the patent's claims from DB
    claims_result = await db.execute(
        select(PatentClaim)
        .where(PatentClaim.patent_id == action.patent_id)
        .order_by(PatentClaim.claim_number)
    )
    claims = claims_result.scalars().all()
    claims_data = [
        {
            "claim_number": c.claim_number,
            "claim_text": c.claim_text,
            "is_independent": c.is_independent,
        }
        for c in claims
    ]

    # Load fetched cited references (prior art)
    from app.models import PriorArtReference
    refs_result = await db.execute(
        select(PriorArtReference)
        .where(PriorArtReference.patent_id == action.patent_id, PriorArtReference.cited_by_examiner == True)
    )
    cited_refs = refs_result.scalars().all()
    prior_art_context = ""
    for r in cited_refs:
        prior_art_context += f"Reference: {r.reference_number} ({r.reference_title})\nAbstract: {r.reference_abstract}\n\n"

    # Strict RAG: dual retrieval when jurisdiction is specified
    legal_context_text = None
    patent_context_text = None
    sources_metadata = None
    firm_name = "the firm"

    if data.jurisdiction:
        from app.services.ingestion import retrieve_full_context
        from app.models import Firm

        firm_result = await db.execute(
            select(Firm.name).where(Firm.id == user.firm_id)
        )
        firm_row = firm_result.first()
        if firm_row:
            firm_name = firm_row.name

        context = await retrieve_full_context(
            query=f"{action.patent.title} office action response {action.extracted_text[:300]}",
            jurisdiction=data.jurisdiction,
            firm_id=user.firm_id,
            user_id=user.id,
            db=db,
            patent_id=action.patent_id,
        )

        legal_context_text = context["legal_context_text"]
        patent_context_text = context["patent_context_text"]
        sources_metadata = {
            "sources_used": context["sources_used"],
            "has_legal_authority": context["has_legal_authority"],
            "jurisdiction": context["jurisdiction"],
        }

    # Concurrency Control (Semaphore)
    from app.services.cache import cache_service
    if not await cache_service.acquire_llm_semaphore(limit=10):
        raise HTTPException(
            status_code=429,
            detail="System is currently generating responses for other attorneys. Please try again in 30 seconds."
        )

    import json as json_lib
    from app.services.citation_validator import validate_citations

    async def wrapped_stream():
        full_response_parts = []
        try:
            async for chunk in generate_oa_response_stream(
                office_action_text=action.extracted_text,
                patent_title=action.patent.title,
                patent_claims=claims_data,
                firm_id=user.firm_id,
                user_id=user.id,
                response_strategy=data.response_strategy,
                additional_context=data.additional_context,
                prior_art_context=prior_art_context if prior_art_context else None,
                jurisdiction=data.jurisdiction,
                legal_context_text=legal_context_text,
                patent_context_text=patent_context_text,
                firm_name=firm_name,
            ):
                if chunk.startswith("data: ") and chunk.strip() not in ("data: [DONE]",):
                    full_response_parts.append(chunk[6:].strip())
                yield chunk

            # Send citation validation + sources metadata
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
        finally:
            await cache_service.release_llm_semaphore()

    return StreamingResponse(
        wrapped_stream(),
        media_type="text/event-stream",
    )

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
