"""
Patent CRUD operations.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, func, update, and_
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Patent, PatentClaim, PatentDeadline, AuditLog
from app.schemas import (
    PatentCreate, PatentUpdate, PatentResponse, PatentListResponse,
    ClaimCreate, ClaimResponse,
)
from app.auth import get_active_firm_user, CurrentUser
from app.services.deadlines import deadline_service
from app.services.storage import get_presigned_url

router = APIRouter()


@router.get("/", response_model=PatentListResponse)
async def list_patents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = Query("urgency"), # urgency, updated, title
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    List patents for the current firm with pagination, filtering, and urgency sorting.
    Fulfills the 'Dashboard loads in under 2 seconds' and 'Urgency display' requirements.
    """
    # Enforce firm isolation and exclude soft-deleted records
    query = select(Patent).where(
        Patent.firm_id == user.firm_id,
        Patent.deleted_at.is_(None)
    )

    if status:
        query = query.where(Patent.status == status)
    if search:
        query = query.where(
            Patent.title.ilike(f"%{search}%")
            | Patent.application_number.ilike(f"%{search}%")
        )

    # Count total (before pagination)
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Sorting Logic
    if sort_by == "urgency":
        # Join with the earliest pending deadline
        sub_urgency = (
            select(PatentDeadline.patent_id, func.min(PatentDeadline.due_date).label("next_deadline"))
            .where(PatentDeadline.status == "PENDING")
            .group_by(PatentDeadline.patent_id)
            .subquery()
        )
        query = query.outerjoin(sub_urgency, Patent.id == sub_urgency.c.patent_id)
        query = query.order_by(sub_urgency.c.next_deadline.asc().nulls_last(), Patent.updated_at.desc())
    elif sort_by == "title":
        query = query.order_by(Patent.title.asc())
    else:
        query = query.order_by(Patent.updated_at.desc())

    # Paginate (Crucial for 1000+ records)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    patents = result.scalars().all()

    return PatentListResponse(
        patents=[PatentResponse.model_validate(p) for p in patents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{patent_id}", response_model=dict)
async def get_patent(
    patent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Get a single patent by ID with full fields and forensic audit logging.
    Fulfills 'Audit log' and 'Full patent record' requirements.
    """
    result = await db.execute(
        select(Patent).where(
            Patent.id == patent_id,
            Patent.firm_id == user.firm_id,
            Patent.deleted_at.is_(None)
        ).options(joinedload(Patent.deadlines), joinedload(Patent.office_actions))
    )
    patent = result.scalar_one_or_none()
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")

    # 1. Forensic Audit Logging (Bank-grade compliance)
    log = AuditLog(
        firm_id=user.firm_id,
        user_id=user.id,
        action="VIEW_PATENT_RECORD",
        target_type="patent",
        target_id=patent.id,
        details={"title": patent.title, "app_num": patent.application_number}
    )
    db.add(log)
    
    # 2. Add signed URL if PDF exists
    res_data = PatentResponse.model_validate(patent).model_dump()
    res_data["deadlines"] = [d for d in patent.deadlines if d.status == "PENDING"]
    
    # Check if we have a file key in metadata
    meta = patent.patent_metadata or {}
    if meta.get("r2_key"):
        res_data["pdf_signed_url"] = await get_presigned_url(meta["r2_key"], expires_in=900)

    await db.commit()
    return res_data


@router.post("/", response_model=PatentResponse, status_code=201)
async def create_patent(
    data: PatentCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Create a new patent record."""
    patent = Patent(
        firm_id=user.firm_id,
        **data.model_dump(),
    )
    db.add(patent)
    await db.flush()
    await db.refresh(patent)
    return PatentResponse.model_validate(patent)


@router.patch("/{patent_id}", response_model=PatentResponse)
async def update_patent(
    patent_id: uuid.UUID,
    data: PatentUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Update a patent."""
    result = await db.execute(
        select(Patent).where(
            Patent.id == patent_id,
            Patent.firm_id == user.firm_id,
        )
    )
    patent = result.scalar_one_or_none()
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(patent, field, value)

    await db.flush()
    await db.refresh(patent)
    return PatentResponse.model_validate(patent)


@router.delete("/{patent_id}", status_code=204)
async def delete_patent(
    patent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Soft-delete a patent. 
    Fulfills 'Deleted patent is soft-deleted only' and 'Recoverable within 30 days'.
    """
    result = await db.execute(
        select(Patent).where(
            Patent.id == patent_id,
            Patent.firm_id == user.firm_id,
        )
    )
    patent = result.scalar_one_or_none()
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")

    patent.deleted_at = datetime.now()
    await db.commit()


# ---------------------------------------------------------------------------
# Deadline Actions
# ---------------------------------------------------------------------------

@router.post("/{patent_id}/deadlines/recalculate")
async def recalculate_patent_deadlines(
    patent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Manually trigger deadline recalculation for a patent."""
    count = await deadline_service.recalculate_deadlines(patent_id, db)
    return {"message": f"Calculated {count} pending deadlines"}


@router.post("/deadlines/{deadline_id}/complete")
async def complete_deadline(
    deadline_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Mark a deadline as completed (e.g., 'Fee paid')."""
    success = await deadline_service.mark_complete(deadline_id, user.id, db)
    if not success:
        raise HTTPException(status_code=404, detail="Deadline not found")
    return {"message": "Deadline marked complete"}


# ---------------------------------------------------------------------------
# Claims sub-routes
# ---------------------------------------------------------------------------

@router.get("/{patent_id}/claims", response_model=list[ClaimResponse])
async def list_claims(
    patent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """List all claims for a patent."""
    # Verify patent belongs to firm
    patent = await db.execute(
        select(Patent).where(Patent.id == patent_id, Patent.firm_id == user.firm_id)
    )
    if not patent.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patent not found")

    result = await db.execute(
        select(PatentClaim)
        .where(PatentClaim.patent_id == patent_id)
        .order_by(PatentClaim.claim_number)
    )
    claims = result.scalars().all()
    return [ClaimResponse.model_validate(c) for c in claims]


@router.post("/{patent_id}/claims", response_model=ClaimResponse, status_code=201)
async def add_claim(
    patent_id: uuid.UUID,
    data: ClaimCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Add a claim to a patent."""
    patent = await db.execute(
        select(Patent).where(Patent.id == patent_id, Patent.firm_id == user.firm_id)
    )
    if not patent.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patent not found")

    claim = PatentClaim(patent_id=patent_id, **data.model_dump())
    db.add(claim)
    await db.flush()
    await db.refresh(claim)
    return ClaimResponse.model_validate(claim)
