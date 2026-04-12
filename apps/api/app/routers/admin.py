import uuid
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.database import get_db
from app.config import settings
from app.auth import get_system_admin, CurrentUser
from app.models.firm import Firm, User
from app.models.audit import UsageLog, AuditLog
from app.models.analysis import AnalysisWorkflow
from app.models.incident import SystemIncident
from app.services.inngest_client import inngest_client
import inngest

router = APIRouter()

@router.get("/health", response_model=Dict[str, Any])
async def get_global_health(
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = Depends(get_system_admin)
):
    """
    Comprehensive platform health diagnostic.
    Only accessible by PhronesisIP System Admins.
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": "unknown",
            "inngest_connection": "unknown",
            "storage_r2": "unknown",
        },
        "incidents_24h": 0
    }

    # 1. Database Ping
    try:
        await db.execute(text("SELECT 1"))
        health["services"]["database"] = "online"
    except Exception:
        health["services"]["database"] = "offline"
        health["status"] = "degraded"

    # 2. Check Recent Audit Failures (indicating potential systemic issues)
    # If 500 errors in AuditLog > threshold, mark degraded
    stmt = select(func.count(AuditLog.id)).where(
        AuditLog.action == "SYSTEM_ERROR",
        AuditLog.created_at >= datetime.now() - timedelta(hours=1)
    )
    error_count = (await db.execute(stmt)).scalar() or 0
    if error_count > 50:
        health["status"] = "unstable"
        health["incidents_24h"] = error_count

    return health

@router.get("/economics", response_model=Dict[str, Any])
async def get_platform_economics(
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = Depends(get_system_admin)
):
    """
    Aggregated AI consumption metrics across ALL firms.
    Allows for global cost monitoring and margin analysis.
    """
    # 1. Total Cumulative Cost
    totals_stmt = select(
        func.sum(UsageLog.estimated_cost_usd).label("total_cost"),
        func.sum(UsageLog.input_tokens).label("total_in"),
        func.sum(UsageLog.output_tokens).label("total_out")
    )
    totals_result = await db.execute(totals_stmt)
    totals = totals_result.first()

    # 2. Top 5 Firms by Usage (Last 30 Days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    top_firms_stmt = select(
        Firm.name,
        func.sum(UsageLog.estimated_cost_usd).label("cost")
    ).join(UsageLog, UsageLog.firm_id == Firm.id)\
     .where(UsageLog.created_at >= thirty_days_ago)\
     .group_by(Firm.name)\
     .order_by(text("cost DESC"))\
     .limit(5)
    
    top_firms = (await db.execute(top_firms_stmt)).all()

    # 3. Monthly Trend (last 7 days for chart)
    trend_stmt = select(
        func.date_trunc('day', UsageLog.created_at).label('day'),
        func.sum(UsageLog.estimated_cost_usd).label('cost')
    ).where(UsageLog.created_at >= datetime.now() - timedelta(days=7))\
     .group_by(text('day'))\
     .order_by(text('day ASC'))
    
    trend_results = (await db.execute(trend_stmt)).all()
    trend_data = [{"name": r.day.strftime("%a"), "cost": float(r.cost or 0)} for r in trend_results]

    return {
        "cumulative": {
            "cost_usd": float(totals.total_cost or 0.0),
            "tokens_in": int(totals.total_in or 0),
            "tokens_out": int(totals.total_out or 0),
        },
        "top_consumers_30d": [
            {"firm": f.name, "cost": float(f.cost or 0)} for f in top_firms
        ],
        "trend": trend_data
    }

@router.get("/analytics/usage", response_model=List[Dict[str, Any]])
async def get_usage_analytics(
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = Depends(get_system_admin)
):
    """Fetch top used features/actions from AuditLog."""
    stmt = select(
        AuditLog.action,
        func.count(AuditLog.id).label("count")
    ).group_by(AuditLog.action)\
     .order_by(text("count DESC"))\
     .limit(10)
    
    results = (await db.execute(stmt)).all()
    return [{"action": r.action, "count": r.count} for r in results]

@router.get("/analytics/errors", response_model=Dict[str, Any])
async def get_error_analytics(
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = Depends(get_system_admin)
):
    """Categorize and count recent incidents."""
    # Count by level
    stmt_level = select(
        SystemIncident.level,
        func.count(SystemIncident.id).label("count")
    ).group_by(SystemIncident.level)
    
    levels = (await db.execute(stmt_level)).all()
    
    # Count by source
    stmt_source = select(
        SystemIncident.source,
        func.count(SystemIncident.id).label("count")
    ).group_by(SystemIncident.source).limit(5)
    
    sources = (await db.execute(stmt_source)).all()
    
    return {
        "levels": {r.level: r.count for r in levels},
        "sources": [{"name": r.source, "count": r.count} for r in sources]
    }

@router.get("/monitoring/jobs", response_model=List[Dict[str, Any]])
async def get_job_telemetry(
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = Depends(get_system_admin)
):
    """
    Fetch global background job status.
    Identifies if parallel audits are failing at scale.
    """
    # Query AnalysisWorkflows for global failure patterns
    stmt = select(
        AnalysisWorkflow.analysis_type,
        func.count(AnalysisWorkflow.id).label("total"),
        func.sum(text("CASE WHEN status = 'failed' THEN 1 ELSE 0 END")).label("failed")
    ).group_by(AnalysisWorkflow.analysis_type)

    results = (await db.execute(stmt)).all()

    return [
        {
            "type": r.analysis_type,
            "total_runs": r.total,
            "failure_rate": (r.failed / r.total * 100) if r.total > 0 else 0
        } for r in results
    ]

@router.get("/analytics/growth", response_model=Dict[str, Any])
async def get_platform_growth(
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = Depends(get_system_admin)
):
    """Platform-level user and firm onboarding metrics."""
    firm_count = (await db.execute(select(func.count(Firm.id)))).scalar()
    user_count = (await db.execute(select(func.count(User.id)))).scalar()
    
    return {
        "total_firms": firm_count,
        "total_users": user_count,
        "active_last_24h": (await db.execute(
            select(func.count(func.distinct(UsageLog.user_id)))
            .where(UsageLog.created_at >= datetime.now() - timedelta(hours=24))
        )).scalar()
    }
@router.get("/incidents", response_model=List[Dict[str, Any]])
async def get_system_incidents(
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = Depends(get_system_admin)
):
    """
    Get the feed of recent platform incidents.
    Fulfills 'Admin dashboard alerts' and persistent notification history.
    """
    stmt = select(SystemIncident).order_by(SystemIncident.created_at.desc()).limit(50)
    incidents = (await db.execute(stmt)).scalars().all()
    
    return [
        {
            "id": str(i.id),
            "level": i.level,
            "source": i.source,
            "message": i.message,
            "details": i.details,
            "is_resolved": i.is_resolved,
            "created_at": i.created_at.isoformat()
        } for i in incidents
    ]

@router.get("/monitoring/failed-workflows", response_model=List[Dict[str, Any]])
async def get_failed_workflows(
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = Depends(get_system_admin)
):
    """List all workflows currently in 'error' status for manual intervention."""
    stmt = select(AnalysisWorkflow, Firm.name).join(Firm, AnalysisWorkflow.firm_id == Firm.id)\
          .where(AnalysisWorkflow.status == "error")\
          .order_by(AnalysisWorkflow.created_at.desc())
    
    results = (await db.execute(stmt)).all()
    
    return [
        {
            "id": str(w.id),
            "firm": firm_name,
            "type": w.analysis_type,
            "created_at": w.created_at.isoformat()
        } for w, firm_name in results
    ]

@router.post("/workflows/{workflow_id}/retry")
async def retry_failed_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = Depends(get_system_admin)
):
    """
    Manually re-trigger a failed analysis workflow.
    Fulfills 'all excess retry jobs' with full platform administration power.
    """
    stmt = select(AnalysisWorkflow).where(AnalysisWorkflow.id == workflow_id)
    workflow = (await db.execute(stmt)).scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Reset status
    workflow.status = "pending"
    await db.commit()
    
    # Re-trigger Inngest
    await inngest_client.send(
        inngest.Event(
            name="analysis.legal.start",
            data={
                "workflow_id": str(workflow.id),
                "firm_id": str(workflow.firm_id)
            }
        )
    )
    
    # Log the administrative action
    audit = AuditLog(
        firm_id=workflow.firm_id,
        user_id=admin.id,
        action="ADMIN_JOB_RETRY",
        target_type="analysis_workflow",
        target_id=workflow.id,
        details={"reason": "Manual administrative retry"}
    )
    db.add(audit)
    await db.commit()
    
    return {"status": "retrying", "workflow_id": str(workflow_id)}
