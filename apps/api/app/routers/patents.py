"""
Patent CRUD operations.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Patent, PatentClaim
from app.schemas import (
    PatentCreate, PatentUpdate, PatentResponse, PatentListResponse,
    ClaimCreate, ClaimResponse,
)
from app.auth import get_active_firm_user, CurrentUser

router = APIRouter()


@router.get("/", response_model=PatentListResponse)
async def list_patents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """List patents for the current firm with pagination and filtering."""
    query = select(Patent).where(Patent.firm_id == user.firm_id)

    if status:
        query = query.where(Patent.status == status)
    if search:
        query = query.where(
            Patent.title.ilike(f"%{search}%")
            | Patent.application_number.ilike(f"%{search}%")
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Patent.updated_at.desc())

    result = await db.execute(query)
    patents = result.scalars().all()

    return PatentListResponse(
        patents=[PatentResponse.model_validate(p) for p in patents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{patent_id}", response_model=PatentResponse)
async def get_patent(
    patent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Get a single patent by ID."""
    result = await db.execute(
        select(Patent).where(
            Patent.id == patent_id,
            Patent.firm_id == user.firm_id,
        )
    )
    patent = result.scalar_one_or_none()
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")
    return PatentResponse.model_validate(patent)


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
    """Delete a patent and all related data."""
    result = await db.execute(
        select(Patent).where(
            Patent.id == patent_id,
            Patent.firm_id == user.firm_id,
        )
    )
    patent = result.scalar_one_or_none()
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")

    await db.delete(patent)


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
