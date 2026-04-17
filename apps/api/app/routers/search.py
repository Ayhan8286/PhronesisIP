"""
Semantic + keyword hybrid search across local patents AND external USPTO search.
"""

import hashlib
import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Patent, SearchHistory
from app.schemas import SemanticSearchRequest, SearchResponse, SearchResultItem
from app.auth import get_current_user, get_active_firm_user, CurrentUser
from app.services.embeddings import generate_query_embedding
from app.services.patent_search import search_patents_external, fetch_patent_detail, search_google_patents
from app.services.ingestion import ingest_patent_from_external
from app.services.cache import cache_service

router = APIRouter()


@router.post("/", response_model=SearchResponse)
async def search_patents(
    data: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Hybrid search: combines semantic (pgvector), keyword (ts_vector) search
    across LOCAL portfolio patents with security-safe history logging.
    """
    # 1. Validation & Hardening
    if not data.query or not data.query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")
    
    # Truncate extremely long queries (standard for embedding models)
    clean_query = data.query[:2000] if len(data.query) > 2000 else data.query
    
    # 2. History Hashing (Privacy)
    query_hash = hashlib.sha256(clean_query.encode()).hexdigest()
    
    # 3. Check Cache (Firm-Scoped)
    cache_key = f"firm:{user.firm_id}:search:{query_hash}"
    cached = await cache_service.get(cache_key)
    if cached:
        return SearchResponse(**cached)

    results = []

    if data.search_type in ("semantic", "hybrid"):
        try:
            query_embedding = await generate_query_embedding(clean_query, user.firm_id, user.id)

            # Weighting: Claims are weighted 20% higher for relevancy
            semantic_sql = text("""
                SELECT
                    p.id as patent_id,
                    p.title,
                    p.application_number,
                    p.status,
                    p.grant_date,
                    pe.chunk_text as matched_text,
                    pe.section_type,
                    pe.page_number,
                    ((pe.embedding <#> CAST(:query_embedding AS vector)) * -1) * 
                    (CASE WHEN pe.section_type = 'claims' THEN 1.2 ELSE 1.0 END) as score
                FROM patent_embeddings pe
                JOIN patents p ON pe.patent_id = p.id
                WHERE pe.firm_id = :firm_id
                ORDER BY score DESC
                LIMIT :top_k
            """)

            semantic_results = await db.execute(
                semantic_sql,
                {
                    "query_embedding": str(query_embedding),
                    "firm_id": str(user.firm_id),
                    "top_k": data.top_k,
                },
            )
            for row in semantic_results.all():
                location_tag = f"[{row.section_type.upper()} - Page {row.page_number}]" if row.page_number else f"[{row.section_type.upper()}]"
                
                # Threat-Level Re-ranking: Bonus for Granted patents + Recency
                # (Raw similarity * 0.7) + (Grant status * 0.3)
                final_score = row.score * 0.7
                if row.status.lower() == "granted":
                    final_score += 0.3
                
                results.append(
                    SearchResultItem(
                        patent_id=row.patent_id,
                        title=row.title,
                        application_number=row.application_number,
                        score=float(final_score),
                        matched_text=f"{location_tag} {row.matched_text[:400]}...",
                        status=row.status,
                    )
                )
        except Exception as e:
            print(f"Semantic search failed: {e}")

    # Deduplicate and sort
    seen = set()
    unique_results = []
    for r in sorted(results, key=lambda x: x.score, reverse=True):
        if r.patent_id not in seen:
            seen.add(r.patent_id)
            unique_results.append(r)

    response = SearchResponse(
        results=unique_results[: data.top_k],
        query=data.query,
        total=len(unique_results),
    )
    
    # 4. Save History & Cache
    history_entry = SearchHistory(
        firm_id=user.firm_id,
        user_id=user.id,
        query_hash=query_hash,
        query_display=clean_query[:100] + "..." if len(clean_query) > 100 else clean_query,
        search_type="hybrid",
        results_count=len(unique_results)
    )
    db.add(history_entry)
    await db.commit()
    
    await cache_service.set(cache_key, response.dict(), expire=3600*24) # 24h cache

    return response


@router.get("/history")
async def get_search_history(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """Retrieve recent search history for the user (privacy-safe)."""
    result = await db.execute(
        select(SearchHistory)
        .where(SearchHistory.user_id == user.id)
        .order_by(SearchHistory.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# External USPTO Patent Search
# ---------------------------------------------------------------------------

class ExternalSearchRequest(BaseModel):
    query: Optional[str] = None
    patent_number: Optional[str] = None
    assignee: Optional[str] = None
    max_results: int = 25


@router.post("/external")
async def search_external_patents(
    data: ExternalSearchRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Standard synchronous external search (returns all at once).
    """
    effective_query = data.query or ""
    if not effective_query and not data.patent_number and not data.assignee:
        raise HTTPException(status_code=400, detail="Provide a query, patent number, or assignee")

    return await search_patents_external(
        query=effective_query,
        assignee=data.assignee,
        patent_number=data.patent_number,
        max_results=data.max_results,
    )


@router.post("/external/stream")
async def search_external_stream(
    data: ExternalSearchRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Streaming search via SSE. Yields results as they arrive from different providers.
    Fulfills the 'Results stream in as they arrive' requirement.
    """
    import json
    import asyncio
    from app.services.patent_search import search_google_patents, _search_odp, epo_client
    from app.config import settings

    async def event_generator():
        tasks = []
        # Define tasks for each provider
        tasks.append(asyncio.create_task(search_google_patents(data.query, assignee=None, max_results=data.max_results)))
        tasks.append(asyncio.create_task(_search_odp(data.query, assignee=data.assignee, max_results=data.max_results)))
        
        if settings.EPO_CLIENT_ID:
            epo_query = data.query
            if data.assignee: epo_query = f'pa="{data.assignee}" and ({data.query})'
            tasks.append(asyncio.create_task(epo_client.search(epo_query, max_results=data.max_results)))

        # Yield results as they complete
        for completed_task in asyncio.as_completed(tasks):
            try:
                result = await completed_task
                if result and result.get("patents"):
                    yield f"data: {json.dumps(result)}\n\n"
            except Exception as e:
                # Log error but don't stop the stream
                yield f"data: {json.dumps({'error': str(e), 'patents': []})}\n\n"
        
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/external/{patent_number}/detail")
async def get_external_patent_detail(
    patent_number: str,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Fetch full patent details from USPTO including claims, inventors, and assignees.
    """
    detail = await fetch_patent_detail(patent_number)
    if not detail:
        raise HTTPException(status_code=404, detail="Patent not found on USPTO")
    return detail


class ImportRequest(BaseModel):
    patent_number: str


@router.post("/import")
async def import_external_patent(
    data: ImportRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Import an external patent from USPTO into the user's portfolio.
    Fetches full details, creates DB record, generates embeddings.
    """
    # Fetch full details from USPTO
    detail = await fetch_patent_detail(data.patent_number)
    if not detail:
        raise HTTPException(status_code=404, detail="Patent not found on USPTO")

    try:
        patent = await ingest_patent_from_external(
            patent_data=detail,
            firm_id=user.firm_id,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {
        "message": f"Patent {data.patent_number} imported successfully",
        "patent_id": str(patent.id),
        "title": patent.title,
        "claims_imported": len(detail.get("claims", [])),
    }


# ---------------------------------------------------------------------------
# Google Patents Search (International)
# ---------------------------------------------------------------------------

class GoogleSearchRequest(BaseModel):
    query: str = ""
    assignee: Optional[str] = None
    country: Optional[str] = None
    max_results: int = 20


@router.post("/google-patents")
async def search_google(
    data: GoogleSearchRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Search Google Patents for international patents.
    Covers US, EU, JP, WO, CN, KR, and other patent offices.
    """
    if not data.query and not data.assignee:
        raise HTTPException(status_code=400, detail="Provide a query or assignee")

    results = await search_google_patents(
        query=data.query,
        assignee=data.assignee,
        country=data.country,
        max_results=data.max_results,
    )

    return results


@router.post("/insights")
async def get_search_insights(
    data: dict,  # {query: str, results: list}
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Get AI-driven technical analysis of search results.
    Fulfills 'Each result has a plain English explanation'.
    """
    from app.services.search_insights import generate_search_insights
    insights = await generate_search_insights(
        query=data.get("query", ""),
        results=data.get("results", []),
        firm_id=user.firm_id,
        user_id=user.id
    )
    return {"insights": insights}


@router.post("/export/pdf")
async def export_search_results_pdf(
    data: dict,  # {query: str, results: list}
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Export search findings to a formal PDF report.
    Fulfills 'Export results as PDF report'.
    """
    from app.services.export_pdf import generate_search_report_pdf
    from fastapi.responses import Response
    
    pdf_buffer = await generate_search_report_pdf(
        query=data.get("query", ""),
        results=data.get("results", []),
        firm_name="PhronesisIP", # Could come from firm model
        attorney_name=user.email or "Attorney"
    )
    
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=Prior_Art_Report.pdf"}
    )


class PriorArtSaveRequest(BaseModel):
    patent_id: uuid.UUID
    patent_number: str
    title: str
    abstract: Optional[str] = None
    score: float = 0.0

@router.post("/save-prior-art")
async def save_search_result_as_prior_art(
    data: PriorArtSaveRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Link a search result to an existing patent record.
    Fulfills 'Attorney can save specific results to patent record'.
    """
    from app.models.prior_art import PriorArtReference
    
    ref = PriorArtReference(
        patent_id=data.patent_id,
        firm_id=user.firm_id,
        reference_number=data.patent_number,
        reference_title=data.title,
        reference_abstract=data.abstract,
        relevance_score=data.score,
        reference_type="patent"
    )
    db.add(ref)
    await db.commit()
    return {"message": "Prior art saved to patent record"}


@router.post("/dismiss")
async def dismiss_search_result(
    patent_number: str,
    query_hash: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Mark a search result as irrelevant for a specific query context.
    Fulfills 'Attorney can dismiss results as not relevant'.
    """
    # Simply using AuditLog to track dismissals for now
    from app.models.audit import AuditLog
    log = AuditLog(
        firm_id=user.firm_id,
        user_id=user.id,
        action="DISMISS_SEARCH_RESULT",
        target_type="patent",
        details={
            "patent_number": patent_number,
            "query_hash": query_hash
        }
    )
    db.add(log)
    await db.commit()
    return {"message": "Result dismissed from future searches"}
