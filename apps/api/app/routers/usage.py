import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit import UsageLog
from app.auth import get_active_firm_user, CurrentUser
from pydantic import BaseModel

router = APIRouter()

class FirmUsageStats(BaseModel):
    firm_id: uuid.UUID
    total_input_tokens: int
    total_output_tokens: int
    total_estimated_cost_usd: float
    workflow_counts: dict

@router.get("/stats", response_model=FirmUsageStats)
async def get_firm_usage_stats(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Get AI consumption statistics for the current firm.
    Allows for transparent billing and cost monitoring.
    """
    # Sum up totals
    result = await db.execute(
        select(
            func.sum(UsageLog.input_tokens).label("in_tk"),
            func.sum(UsageLog.output_tokens).label("out_tk"),
            func.sum(UsageLog.estimated_cost_usd).label("cost")
        ).where(UsageLog.firm_id == user.firm_id)
    )
    row = result.first()
    
    # Get counts per workflow
    workflow_res = await db.execute(
        select(UsageLog.workflow_type, func.count(UsageLog.id))
        .where(UsageLog.firm_id == user.firm_id)
        .group_by(UsageLog.workflow_type)
    )
    workflows = {row[0]: row[1] for row in workflow_res.all()}

    return {
        "firm_id": user.firm_id,
        "total_input_tokens": row.in_tk or 0,
        "total_output_tokens": row.out_tk or 0,
        "total_estimated_cost_usd": row.cost or 0.0,
        "workflow_counts": workflows
    }

@router.get("/history", response_model=List[dict])
async def get_usage_history(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Get the recent usage log entries for the firm."""
    result = await db.execute(
        select(UsageLog)
        .where(UsageLog.firm_id == user.firm_id)
        .order_by(UsageLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "user_id": str(log.user_id),
            "model": log.model,
            "tokens": log.input_tokens + log.output_tokens,
            "cost": log.estimated_cost_usd,
            "workflow": log.workflow_type,
            "created_at": log.created_at.isoformat()
        } for log in logs
    ]
