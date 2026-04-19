import uuid
import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.office_action import OfficeAction
from app.models.patent import Patent
from app.auth import get_active_firm_user, CurrentUser
from app.services.export_docx import generate_office_action_response_docx
from app.services.service_report import service_report_generator
from pydantic import BaseModel, Field

router = APIRouter()

class ExportRequest(BaseModel):
    draft_text: str

@router.post("/office-action/{oa_id}")
async def export_oa_response(
    oa_id: uuid.UUID,
    data: ExportRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Generate and download a professional DOCX for an office action response.
    Requires the current JSON draft text.
    """
    # Fetch OA with Patent info for the header
    result = await db.execute(
        select(OfficeAction)
        .join(Patent, OfficeAction.patent_id == Patent.id)
        .where(OfficeAction.id == oa_id, OfficeAction.firm_id == user.firm_id)
        .options(selectinload(OfficeAction.patent))
    )
    oa = result.scalar_one_or_none()
    if not oa:
        raise HTTPException(status_code=404, detail="Office action not found")

    # Construct metadata for header
    metadata = {
        "applicant": oa.patent.assignee or "TBD",
        "application_number": oa.patent.application_number,
        "filing_date": oa.patent.filing_date.strftime("%Y-%m-%d") if oa.patent.filing_date else "TBD",
        "title": oa.patent.title,
        # Rejections field currently stores a list, but in future will store extracted metadata
        # For now, we use defaults or try to extract from OA
        "examiner": "TBD", 
        "art_unit": "TBD",
        "docket_number": "TBD"
    }

    # Generate DOCX
    docx_bytes = generate_office_action_response_docx(data.draft_text, metadata)

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename=Office_Action_Response_{oa.id}.docx"
        }
    )

# --- Service Mode Exports ---

class PriorArtExportRequest(BaseModel):
    client_name: str
    invention_title: str
    results: List[Dict[str, Any]]

@router.post("/prior-art")
async def export_prior_art_report(
    data: PriorArtExportRequest,
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Generate and download a premium branded Prior Art PDF report.
    """
    pdf_bytes = service_report_generator.generate_prior_art_report(
        client_name=data.client_name,
        invention_title=data.invention_title,
        results=data.results
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Prior_Art_Report_{datetime.datetime.now().strftime('%Y%m%d')}.pdf"
        }
    )

class PatentabilityExportRequest(BaseModel):
    client_name: str
    invention_title: str
    analysis: str
    claims: List[str]
    prior_art: List[Dict[str, Any]]

@router.post("/patentability")
async def export_patentability_report(
    data: PatentabilityExportRequest,
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Generate and download a premium branded Patentability PDF report.
    """
    # For now, we'll repurpose the prior art template or a similar one
    # In a real app, we'd have a specific method in service_report_generator
    # I'll add generate_patentability_report to the service soon.
    pdf_bytes = service_report_generator.generate_prior_art_report(
        client_name=data.client_name,
        invention_title=data.invention_title,
        results=data.prior_art
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Patentability_Report_{datetime.datetime.now().strftime('%Y%m%d')}.pdf"
        }
    )
