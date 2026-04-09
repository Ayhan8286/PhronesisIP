"""
Portfolio management: families, overview, and analytics.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Patent, PatentFamily, OfficeAction
from app.schemas import (
    PatentFamilyCreate, PatentFamilyResponse, PatentResponse,
)
from app.auth import get_current_user, CurrentUser

router = APIRouter()


# ---------------------------------------------------------------------------
# Portfolio Overview
# ---------------------------------------------------------------------------

@router.get("/overview")
async def portfolio_overview(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Get high-level portfolio statistics for the firm dashboard.
    """
    firm_id = user.firm_id

    # Patent counts by status
    status_counts = await db.execute(
        select(
            Patent.status,
            func.count(Patent.id).label("count"),
        )
        .where(Patent.firm_id == firm_id)
        .group_by(Patent.status)
    )
    statuses = {row.status: row.count for row in status_counts.all()}

    # Total patents
    total = sum(statuses.values())

    # Upcoming deadlines (office actions due in next 30 days)
    from datetime import date, timedelta

    deadline_cutoff = date.today() + timedelta(days=30)
    upcoming_deadlines = await db.execute(
        select(func.count(OfficeAction.id))
        .join(Patent, OfficeAction.patent_id == Patent.id)
        .where(
            Patent.firm_id == firm_id,
            OfficeAction.response_deadline <= deadline_cutoff,
            OfficeAction.status == "pending",
        )
    )
    urgent_deadlines = upcoming_deadlines.scalar() or 0

    # Family count
    family_count = await db.execute(
        select(func.count(PatentFamily.id)).where(PatentFamily.firm_id == firm_id)
    )

    return {
        "total_patents": total,
        "status_breakdown": statuses,
        "patent_families": family_count.scalar() or 0,
        "urgent_deadlines": urgent_deadlines,
        "deadline_window_days": 30,
    }


@router.get("/timeline")
async def portfolio_timeline(
    year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Filing timeline: patents grouped by filing month/year.
    """
    query = select(
        func.date_trunc("month", Patent.filing_date).label("month"),
        func.count(Patent.id).label("count"),
    ).where(
        Patent.firm_id == user.firm_id,
        Patent.filing_date.isnot(None),
    )

    if year:
        query = query.where(func.extract("year", Patent.filing_date) == year)

    query = query.group_by("month").order_by("month")
    result = await db.execute(query)

    return [
        {"month": str(row.month), "count": row.count}
        for row in result.all()
    ]


# ---------------------------------------------------------------------------
# Patent Families
# ---------------------------------------------------------------------------

@router.get("/families", response_model=list[PatentFamilyResponse])
async def list_families(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """List all patent families for the firm."""
    result = await db.execute(
        select(PatentFamily)
        .where(PatentFamily.firm_id == user.firm_id)
        .options(selectinload(PatentFamily.patents))
        .order_by(PatentFamily.family_name)
    )
    families = result.scalars().unique().all()
    return [PatentFamilyResponse.model_validate(f) for f in families]


@router.post("/families", response_model=PatentFamilyResponse, status_code=201)
async def create_family(
    data: PatentFamilyCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Create a new patent family."""
    family = PatentFamily(firm_id=user.firm_id, **data.model_dump())
    db.add(family)
    await db.flush()
    await db.refresh(family)
    return PatentFamilyResponse.model_validate(family)


@router.get("/families/{family_id}", response_model=PatentFamilyResponse)
async def get_family(
    family_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get a patent family with its patents."""
    result = await db.execute(
        select(PatentFamily)
        .where(
            PatentFamily.id == family_id,
            PatentFamily.firm_id == user.firm_id,
        )
        .options(selectinload(PatentFamily.patents))
    )
    family = result.scalar_one_or_none()
    if not family:
        raise HTTPException(status_code=404, detail="Patent family not found")
    return PatentFamilyResponse.model_validate(family)


@router.delete("/families/{family_id}", status_code=204)
async def delete_family(
    family_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Delete a patent family (does not delete the patents, just ungroups them)."""
    result = await db.execute(
        select(PatentFamily).where(
            PatentFamily.id == family_id,
            PatentFamily.firm_id == user.firm_id,
        )
    )
    family = result.scalar_one_or_none()
    if not family:
        raise HTTPException(status_code=404, detail="Patent family not found")

    # Unlink patents from this family
    patents_result = await db.execute(
        select(Patent).where(Patent.family_id == family_id)
    )
    for patent in patents_result.scalars().all():
        patent.family_id = None

    await db.delete(family)
