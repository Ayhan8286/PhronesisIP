"""
Prior art management and AI-powered risk/invalidity analysis.
Now with RAG: retrieves relevant chunks from pgvector before generating.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Patent, PatentClaim, PriorArtReference
from app.schemas import PriorArtCreate, PriorArtResponse
from app.auth import get_current_user, CurrentUser
from app.services.llm import (
    generate_risk_analysis_stream,
    analyze_prior_art_stream,
    generate_due_diligence_stream,
)
from app.services.ingestion import retrieve_context, format_context_for_llm

router = APIRouter()


@router.get("/{patent_id}", response_model=list[PriorArtResponse])
async def list_prior_art(
    patent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """List prior art references for a patent."""
    # Verify patent belongs to firm
    patent = await db.execute(
        select(Patent).where(Patent.id == patent_id, Patent.firm_id == user.firm_id)
    )
    if not patent.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patent not found")

    result = await db.execute(
        select(PriorArtReference)
        .where(PriorArtReference.patent_id == patent_id)
        .order_by(PriorArtReference.relevance_score.desc())
    )
    refs = result.scalars().all()
    return [PriorArtResponse.model_validate(r) for r in refs]


@router.post("/", response_model=PriorArtResponse, status_code=201)
async def add_prior_art(
    data: PriorArtCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Add a prior art reference to a patent."""
    patent = await db.execute(
        select(Patent).where(Patent.id == data.patent_id, Patent.firm_id == user.firm_id)
    )
    if not patent.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patent not found")

    ref = PriorArtReference(**data.model_dump())
    db.add(ref)
    await db.flush()
    await db.refresh(ref)
    return PriorArtResponse.model_validate(ref)


# ---------------------------------------------------------------------------
# Risk / Infringement Analysis (Structured Claim Charts)
# ---------------------------------------------------------------------------

class RiskAnalysisRequest(BaseModel):
    patent_id: uuid.UUID
    analysis_type: str = "invalidity"  # invalidity, infringement, freedom-to-operate
    product_description: Optional[str] = None  # Required for infringement analysis
    target_claims: Optional[list[int]] = None


@router.post("/risk-analysis")
async def run_risk_analysis(
    data: RiskAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Run AI-powered risk/invalidity/infringement analysis on a patent.
    Produces structured claim charts with element-by-element mapping.
    """
    # Load patent with claims and prior art
    result = await db.execute(
        select(Patent)
        .where(Patent.id == data.patent_id, Patent.firm_id == user.firm_id)
        .options(
            selectinload(Patent.claims),
            selectinload(Patent.prior_art_refs),
        )
    )
    patent = result.scalar_one_or_none()
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")

    claims_data = [
        {
            "claim_number": c.claim_number,
            "claim_text": c.claim_text,
            "is_independent": c.is_independent,
        }
        for c in sorted(patent.claims, key=lambda x: x.claim_number)
    ]

    prior_art_data = [
        {
            "reference_number": r.reference_number,
            "reference_title": r.reference_title,
            "reference_abstract": r.reference_abstract or "",
        }
        for r in patent.prior_art_refs
    ]

    if data.analysis_type == "infringement" and not data.product_description:
        raise HTTPException(
            status_code=400,
            detail="Product description is required for infringement analysis",
        )

    # RAG: retrieve relevant chunks from portfolio for context
    rag_query = f"{patent.title} {data.product_description or ''} {data.analysis_type}"
    try:
        retrieved_chunks = await retrieve_context(
            query=rag_query,
            firm_id=user.firm_id,
            db=db,
            top_k=15,
            patent_id_filter=data.patent_id,
        )
        rag_context = format_context_for_llm(retrieved_chunks)
    except Exception:
        rag_context = None

    return StreamingResponse(
        generate_risk_analysis_stream(
            patent_title=patent.title,
            claims=claims_data,
            prior_art=prior_art_data,
            analysis_type=data.analysis_type,
            product_description=data.product_description,
            target_claims=data.target_claims,
            rag_context=rag_context,
        ),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------------
# Prior Art Deep Analysis
# ---------------------------------------------------------------------------

class PriorArtAnalysisRequest(BaseModel):
    patent_id: uuid.UUID
    analysis_depth: str = "standard"
    include_npl: bool = False


@router.post("/analyze")
async def analyze_prior_art(
    data: PriorArtAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Run AI prior art analysis on a patent.
    Identifies vulnerabilities, recommends search strategies.
    """
    result = await db.execute(
        select(Patent)
        .where(Patent.id == data.patent_id, Patent.firm_id == user.firm_id)
        .options(selectinload(Patent.claims))
    )
    patent = result.scalar_one_or_none()
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")

    claims_data = [
        {
            "claim_number": c.claim_number,
            "claim_text": c.claim_text,
            "is_independent": c.is_independent,
        }
        for c in sorted(patent.claims, key=lambda x: x.claim_number)
    ]

    return StreamingResponse(
        analyze_prior_art_stream(
            patent_title=patent.title,
            patent_abstract=patent.abstract or "",
            claims=claims_data,
            analysis_depth=data.analysis_depth,
            include_npl=data.include_npl,
        ),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------------
# Due Diligence Report
# ---------------------------------------------------------------------------

class DueDiligenceRequest(BaseModel):
    patent_ids: Optional[list[uuid.UUID]] = None  # None = all patents
    context: Optional[str] = None


@router.post("/due-diligence")
async def generate_due_diligence(
    data: DueDiligenceRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Generate a comprehensive due diligence report for selected patents.
    Produces scored portfolio assessment with per-patent analysis.
    """
    if data.patent_ids:
        result = await db.execute(
            select(Patent)
            .where(Patent.id.in_(data.patent_ids), Patent.firm_id == user.firm_id)
            .options(selectinload(Patent.claims))
        )
    else:
        result = await db.execute(
            select(Patent)
            .where(Patent.firm_id == user.firm_id)
            .options(selectinload(Patent.claims))
        )

    patents = result.scalars().all()
    if not patents:
        raise HTTPException(status_code=404, detail="No patents found")

    patents_data = [
        {
            "patent_number": p.patent_number or p.application_number,
            "application_number": p.application_number,
            "title": p.title,
            "abstract": p.abstract or "",
            "status": p.status,
            "filing_date": str(p.filing_date) if p.filing_date else None,
            "grant_date": str(p.grant_date) if p.grant_date else None,
            "assignee": p.assignee or "",
            "claims": [
                {"number": c.claim_number, "text": c.claim_text, "is_independent": c.is_independent}
                for c in sorted(p.claims, key=lambda x: x.claim_number)
            ],
        }
        for p in patents
    ]

    return StreamingResponse(
        generate_due_diligence_stream(
            patents=patents_data,
            context=data.context,
        ),
        media_type="text/event-stream",
    )
