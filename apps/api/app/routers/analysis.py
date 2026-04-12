import uuid
import inngest
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.analysis import AnalysisWorkflow, ProductDescription, ClaimAnalysisResult
from app.models.patent import Patent
from app.auth import get_active_firm_user, CurrentUser
from app.services.inngest_client import inngest_client
from app.services.storage import get_presigned_url

router = APIRouter()

@router.post("/", status_code=201)
async def start_legal_analysis(
    patent_id: uuid.UUID,
    analysis_type: str = Query(..., regex="^(infringement|invalidity|fto)$"),
    product_description: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Start a new legal analysis workflow.
    Fulfills 'Product description form accepts plain English' and 'Inngest orchestration'.
    """
    # 1. Create Workflow Record
    workflow = AnalysisWorkflow(
        firm_id=user.firm_id,
        created_by=user.id,
        patent_id=patent_id,
        analysis_type=analysis_type,
        status="pending"
    )
    db.add(workflow)
    await db.flush()

    # 2. Save Product Description if provided
    if product_description:
        pd = ProductDescription(
            workflow_id=workflow.id,
            firm_id=user.firm_id,
            description_text=product_description
        )
        db.add(pd)

    await db.commit()

    # 3. Trigger Inngest Background Job
    await inngest_client.send(
        inngest.Event(
            name="analysis.legal.start",
            data={
                "workflow_id": str(workflow.id),
                "firm_id": str(user.firm_id)
            }
        )
    )

    return {"workflow_id": workflow.id, "status": "pending"}


@router.get("/{analysis_id}")
async def get_analysis_status(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Check the status and results of an analysis.
    Fulfills 'Analysis ID in URL — Firm B attorney must get 404' (Enforced via firm_id check).
    """
    stmt = select(AnalysisWorkflow).where(
        AnalysisWorkflow.id == analysis_id,
        AnalysisWorkflow.firm_id == user.firm_id
    )
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Analysis not found")

    res_data = {
        "id": workflow.id,
        "status": workflow.status,
        "type": workflow.analysis_type,
        "created_at": workflow.created_at,
        "cost_usd": workflow.cost_usd,
        "report_url": None
    }
    
    if workflow.status == "completed" and workflow.report_r2_key:
        res_data["report_url"] = await get_presigned_url(workflow.report_r2_key, expires_in=900)

    # Include claim-level summaries if available
    stmt = select(ClaimAnalysisResult).where(ClaimAnalysisResult.workflow_id == workflow.id)
    claim_res = (await db.execute(stmt)).scalars().all()
    res_data["claims"] = [
        {
            "num": c.claim_number,
            "risk": c.risk_level,
            "ai_finding": c.ai_finding[:200] + "..."
        } for c in claim_res
    ]

    return res_data

@router.get("/{analysis_id}/report")
async def get_analysis_report(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Get a fresh signed URL for the DOCX report."""
    stmt = select(AnalysisWorkflow).where(
        AnalysisWorkflow.id == analysis_id,
        AnalysisWorkflow.firm_id == user.firm_id
    )
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()
    
    if not workflow or not workflow.report_r2_key:
        raise HTTPException(status_code=404, detail="Report not ready")

    url = await get_presigned_url(workflow.report_r2_key, expires_in=900)
    return {"download_url": url}

