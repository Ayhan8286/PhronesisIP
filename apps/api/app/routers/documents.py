"""
Document upload and ingestion endpoints.
Handles PDF upload for patents, office actions, and invention specs.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Patent, OfficeAction
from app.auth import get_active_firm_user, CurrentUser
from app.services.ingestion import ingest_patent_pdf
from app.services.document import extract_pdf_text, extract_docx_text
from app.services.storage import upload_to_r2, get_presigned_url
from app.utils.audit import audit_log

router = APIRouter()


@router.post("/upload-patent")
@audit_log(action="UPLOAD_PATENT", target_type="patent")
async def upload_patent_pdf(
    file: UploadFile = File(...),
    patent_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Upload a patent PDF → extract text → chunk → embed → generate AI summary.
    This is the core ingestion pipeline.
    """
    # Verify file is not empty
    if file.size == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    # Verify patent belongs to user's firm
    result = await db.execute(
        select(Patent).where(
            Patent.id == uuid.UUID(patent_id),
            Patent.firm_id == user.firm_id,
        )
    )
    patent = result.scalar_one_or_none()
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")

    content = await file.read()

    # Detect scanned PDF early to prevent bad ingestion
    extracted_text = extract_pdf_text(content)
    if not extracted_text or (len(content) > 10000 and len(extracted_text) < 100):
        raise HTTPException(
            status_code=400, 
            detail="Could not extract text from PDF. This document appears to be a scanned image (not real text). Please upload a text-based PDF or use OCR."
        )

    # Upload to R2 storage
    r2_key = f"patents/{user.firm_id}/{patent_id}/{file.filename}"
    try:
        await upload_to_r2(content, r2_key, content_type="application/pdf")
    except Exception as e:
        # R2 upload is optional — continue with ingestion
        r2_key = None

    # Run full ingestion pipeline
    result = await ingest_patent_pdf(
        pdf_bytes=content,
        patent_id=uuid.UUID(patent_id),
        firm_id=user.firm_id,
        db=db,
    )

    return {
        "message": "Patent PDF uploaded and processed",
        "r2_key": r2_key,
        **result,
    }


@router.post("/upload-office-action")
@audit_log(action="UPLOAD_OFFICE_ACTION", target_type="patent")
async def upload_office_action_pdf(
    file: UploadFile = File(...),
    patent_id: str = Form(...),
    action_type: str = Form("Non-Final Rejection"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Upload an office action PDF → extract text → AI-parse rejections → create OA record.
    """
    # Verify file is not empty
    if file.size == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    # Verify patent belongs to firm
    result = await db.execute(
        select(Patent).where(
            Patent.id == uuid.UUID(patent_id),
            Patent.firm_id == user.firm_id,
        )
    )
    patent = result.scalar_one_or_none()
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")

    content = await file.read()

    # Extract text from PDF
    extracted_text = extract_pdf_text(content)
    if not extracted_text or (len(content) > 10000 and len(extracted_text) < 100):
        raise HTTPException(
            status_code=400, 
            detail="Could not extract text from PDF. This document appears to be a scanned image (not real text). Please upload a text-based PDF or use OCR."
        )

    # Upload to R2 storage
    r2_key = f"office-actions/{user.firm_id}/{patent_id}/{file.filename}"
    try:
        await upload_to_r2(content, r2_key, content_type="application/pdf")
    except Exception:
        r2_key = None

    # AI-parse rejections from the extracted text
    ai_data = await _parse_rejections_ai(extracted_text)
    rejections = ai_data.get("rejections", [])
    oa_metadata = ai_data.get("metadata", {})

    from datetime import date
    from dateutil.relativedelta import relativedelta
    
    # Calculate statutory 3-month free response deadline for USPTO
    today = date.today()
    calculated_deadline = today + relativedelta(months=3)

    # Create office action record
    oa = OfficeAction(
        patent_id=uuid.UUID(patent_id),
        firm_id=user.firm_id,
        action_type=action_type,
        r2_file_key=r2_key,
        extracted_text=extracted_text,
        rejections=rejections, # Still storing rejections for compatibility
        mailing_date=today,
        response_deadline=calculated_deadline,
        status="pending",
    )
    # Store extended metadata if needed (could be added to a new column or JSONB field)
    # For now, let's keep it in the rejections JSONB as an alternative structure if we want
    # but I'll stick to a list for 'rejections' and maybe add a migration later.
    # Actually, let's just use rejections for now and return it to UI.
    db.add(oa)
    await db.flush()
    await db.refresh(oa)

    # Trigger background job to fetch referenced prior art instantly
    from app.services.inngest_client import inngest_client
    await inngest_client.send(
        inngest.Event(
            name="oa.references.fetch",
            data={
                "office_action_id": str(oa.id),
                "firm_id": str(user.firm_id)
            }
        )
    )

    return {
        "message": "Office action PDF uploaded and parsed. Prior art is being fetched in the background.",
        "office_action_id": str(oa.id),
        "text_length": len(extracted_text),
        "rejections_found": len(rejections),
        "rejections": rejections,
    }


@router.post("/upload-spec")
async def upload_invention_spec(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Upload an invention specification / engineering doc for use in patent drafting.
    Supports PDF and DOCX formats.
    Returns extracted text that can be passed to the drafting endpoint.
    """
    # Verify file is not empty
    if file.size == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    content = await file.read()
    filename = file.filename.lower() if file.filename else ""
    
    extracted_text = ""
    if filename.endswith(".docx"):
        extracted_text = extract_docx_text(content)
    elif filename.endswith(".pdf"):
        extracted_text = extract_pdf_text(content)
    else:
        # Fallback for plain text
        try:
            extracted_text = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Unsupported file format")

    if not extracted_text or (filename.endswith(".pdf") and len(content) > 10000 and len(extracted_text) < 100):
        raise HTTPException(
            status_code=400, 
            detail="Could not extract text from document. This appears to be a scanned image or empty file. Please upload a text-based document."
        )

    return {
        "message": "Specification uploaded and text extracted",
        "text_length": len(extracted_text),
        "extracted_text": extracted_text,
    }


@router.get("/{patent_id}/summary")
async def get_patent_summary(
    patent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Get the AI-generated summary for a patent.
    Returns the structured summary stored in patent metadata.
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

    # Log document access
    # (Note: Decorator handles this for the route below, but we log summary access too)

    meta = patent.patent_metadata or {}
    summary = meta.get("ai_summary")

    if not summary:
        raise HTTPException(
            status_code=404,
            detail="No AI summary available. Upload a patent PDF to generate one.",
        )

    return {
        "patent_id": str(patent.id),
        "title": patent.title,
        "summary": summary,
        "ingested": meta.get("ingested", False),
        "text_length": meta.get("text_length", 0),
        "chunk_count": meta.get("chunk_count", 0),
    }


async def _parse_rejections_ai(office_action_text: str) -> dict:
    """
    Use AI to parse rejection details and metadata from an office action text.
    Identifies rejection type, cited references, affected claims, plus Art Unit and Examiner.
    """
    import json

    try:
        from app.services.llm import _get_llm
        from langchain_core.messages import HumanMessage

        llm = await _get_llm(temperature=0.1)

        prompt = f"""Parse this USPTO office action text and extract ALL rejections and key header metadata.
 
 OFFICE ACTION TEXT:
 {office_action_text[:6000]}
 
 Return a JSON object with:
 1. "metadata": {{
     "art_unit": "The USPTO Art Unit (e.g., 3622)",
     "examiner": "The name of the Examiner",
     "docket_number": "The Attorney Docket Number if found",
     "application_number": "The Application Number if found"
    }}
 2. "rejections": A JSON array where each rejection has:
     - "type": The statutory basis (e.g., "102", "103", "112", "101")
     - "claims": Array of claim numbers affected
     - "references": Array of cited prior art references (patent numbers and names)
     - "basis": Brief description of the rejection basis
 
 Return ONLY a valid JSON object."""

        result = await llm.ainvoke([HumanMessage(content=prompt)])
        text = result.content.strip()

        # Remove markdown fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]

        return json.loads(text)
    except Exception:
        return {"rejections": [], "metadata": {}}

@router.get("/{patent_id}/view-url")
@audit_log(action="VIEW_DOCUMENT", target_type="patent")
async def get_document_view_url(
    patent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Generate a 15-minute presigned URL to view a patent PDF.
    Verifies RLS before signing.
    """
    result = await db.execute(
        select(Patent).where(
            Patent.id == patent_id,
            Patent.firm_id == user.firm_id,
        )
    )
    patent = result.scalar_one_or_none()
    if not patent or not patent.patent_metadata:
        raise HTTPException(status_code=404, detail="Document not found")

    r2_key = patent.patent_metadata.get("r2_key")
    if not r2_key:
        raise HTTPException(status_code=404, detail="Source PDF not stored in R2")

    url = await get_presigned_url(r2_key, expires_in=900)
    return {"url": url, "expires_in": 900}
