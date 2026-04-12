import uuid
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.portfolio import Client, Portfolio, PortfolioPatent
from app.models.patent import Patent
from app.auth import get_active_firm_user, CurrentUser
from app.services.inngest_client import inngest_client
from app.services.storage import get_presigned_url

router = APIRouter()

@router.get("/clients")
async def get_clients(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    List all clients for the firm with their patent counts.
    Fulfills 'Dropdown shows all firm clients with patent counts'.
    """
    # Count patents per client
    stmt = (
        select(Client.id, Client.name, func.count(Patent.id).label("patent_count"))
        .outerjoin(Patent, Patent.client_id == Client.id)
        .where(Client.firm_id == user.firm_id)
        .group_by(Client.id, Client.name)
    )
    result = await db.execute(stmt)
    clients = []
    for row in result:
        clients.append({
            "id": row.id,
            "name": row.name,
            "patent_count": row.patent_count
        })
    return clients

@router.post("/audit", status_code=201)
async def trigger_portfolio_audit(
    client_id: uuid.UUID,
    portfolio_name: str,
    excluded_patent_ids: List[uuid.UUID] = Query([]),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Trigger a full Due Diligence audit for a client portfolio.
    Fulfills 'Parallel job execution spawned' and 'Paralegal cannot generate report'.
    """
    # 1. Role Restriction (Requirement: 'Paralegal cannot generate due diligence report')
    if user.role == "paralegal":
        raise HTTPException(status_code=403, detail="Paralegals are not authorized to trigger due diligence audits.")

    # 2. Create Portfolio Record
    portfolio = Portfolio(
        firm_id=user.firm_id,
        client_id=client_id,
        name=portfolio_name,
        status="active"
    )
    db.add(portfolio)
    await db.flush()

    # 3. Associate all client patents
    stmt = select(Patent.id).where(Patent.client_id == client_id, Patent.firm_id == user.firm_id)
    patents = (await db.execute(stmt)).scalars().all()
    
    if not patents:
        raise HTTPException(status_code=400, detail="This client has no patents to analyze.")

    for pid in patents:
        pp = PortfolioPatent(
            portfolio_id=portfolio.id,
            patent_id=pid,
            is_excluded=pid in excluded_patent_ids
        )
        db.add(pp)

    await db.commit()

    # 4. Trigger Master Inngest Job
    import inngest
    await inngest_client.send(
        inngest.Event(
            name="portfolio.audit.start",
            data={
                "portfolio_id": str(portfolio.id),
                "firm_id": str(user.firm_id)
            }
        )
    )

    return {"portfolio_id": portfolio.id, "status": "dispatched"}


@router.get("/{portfolio_id}")
async def get_portfolio_status(
    portfolio_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Check progress of a portfolio audit.
    Fulfills 'Progress shown in real time — 4 of 6 patents analysed'.
    """
    # 1. Get Totals
    stmt = select(func.count(PortfolioPatent.patent_id)).where(
        PortfolioPatent.portfolio_id == portfolio_id,
        PortfolioPatent.is_excluded == False
    )
    total = (await db.execute(stmt)).scalar()
    
    # 2. Get Completed
    stmt = select(func.count(PortfolioPatent.patent_id)).where(
        PortfolioPatent.portfolio_id == portfolio_id,
        PortfolioPatent.is_excluded == False,
        PortfolioPatent.last_dd_score.is_not(None)
    )
    completed = (await db.execute(stmt)).scalar()

    # 3. Get Report Link if exists
    stmt = select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.firm_id == user.firm_id)
    portfolio = (await db.execute(stmt)).scalar_one_or_none()
    
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    report_url = None
    if portfolio.report_r2_key:
        report_url = await get_presigned_url(portfolio.report_r2_key, expires_in=86400) # 24 Hours

    return {
        "id": portfolio_id,
        "name": portfolio.name,
        "progress": f"{completed} of {total} patents analyzed",
        "is_complete": completed == total if total > 0 else False,
        "report_url": report_url
    }

@router.get("/{portfolio_id}/report")
async def get_due_diligence_report(
    portfolio_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Get the 24h signed URL for the PDF report.
    Fulfills 'Download link expires after 24 hours' and 'Previous report retrievable'.
    """
    portfolio = await db.get(Portfolio, portfolio_id)
    if not portfolio or not portfolio.firm_id == user.firm_id:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    if not portfolio.report_r2_key:
        raise HTTPException(status_code=404, detail="Report not yet generated for this portfolio.")

    url = await get_presigned_url(portfolio.report_r2_key, expires_in=86400) # 24 Hours
    return {"download_url": url}
