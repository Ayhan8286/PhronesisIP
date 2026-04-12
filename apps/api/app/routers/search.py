"""
Semantic + keyword hybrid search across local patents AND external USPTO search.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Patent
from app.schemas import SemanticSearchRequest, SearchResponse, SearchResultItem
from app.auth import get_current_user, get_active_firm_user, CurrentUser
from app.services.embeddings import generate_query_embedding
from app.services.patent_search import search_patents_external, fetch_patent_detail, search_google_patents
from app.services.ingestion import ingest_patent_from_external

router = APIRouter()


@router.post("/", response_model=SearchResponse)
async def search_patents(
    data: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_active_firm_user),
):
    """
    Hybrid search: combines semantic (pgvector), keyword (ts_vector) search
    across LOCAL portfolio patents.
    """
    results = []

    if data.search_type in ("semantic", "hybrid"):
        try:
            query_embedding = await generate_query_embedding(data.query)

            semantic_sql = text("""
                SELECT
                    p.id as patent_id,
                    p.title,
                    p.application_number,
                    p.status,
                    pe.chunk_text as matched_text,
                    pe.section_type,
                    pe.page_number,
                    (pe.embedding <#> :query_embedding::vector) * -1 as score
                FROM patent_embeddings pe
                JOIN patents p ON pe.patent_id = p.id
                WHERE pe.firm_id = :firm_id
                ORDER BY pe.embedding <#> :query_embedding::vector ASC
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
                # Add highlighting block indicating the exact section and page for the Frontend
                location_tag = f"[{row.section_type.upper()} - Page {row.page_number}]" if row.page_number else f"[{row.section_type.upper()}]"
                results.append(
                    SearchResultItem(
                        patent_id=row.patent_id,
                        title=row.title,
                        application_number=row.application_number,
                        score=float(row.score),
                        matched_text=f"{location_tag} {row.matched_text[:400]}...",
                        status=row.status,
                    )
                )
        except Exception:
            pass  # Fall through to keyword search

    if data.search_type in ("keyword", "hybrid") and not results:
        keyword_sql = text("""
            SELECT
                p.id as patent_id,
                p.title,
                p.application_number,
                p.status,
                LEFT(p.abstract, 300) as matched_text,
                ts_rank(
                    to_tsvector('english', COALESCE(p.title, '') || ' ' || COALESCE(p.abstract, '')),
                    plainto_tsquery('english', :query)
                ) as score
            FROM patents p
            WHERE p.firm_id = :firm_id
            AND to_tsvector('english', COALESCE(p.title, '') || ' ' || COALESCE(p.abstract, ''))
                @@ plainto_tsquery('english', :query)
            ORDER BY score DESC
            LIMIT :top_k
        """)

        keyword_results = await db.execute(
            keyword_sql,
            {
                "query": data.query,
                "firm_id": str(user.firm_id),
                "top_k": data.top_k,
            },
        )
        for row in keyword_results.all():
            results.append(
                SearchResultItem(
                    patent_id=row.patent_id,
                    title=row.title,
                    application_number=row.application_number,
                    score=float(row.score),
                    matched_text=row.matched_text or "",
                    status=row.status,
                )
            )

    # Deduplicate and sort
    seen = set()
    unique_results = []
    for r in sorted(results, key=lambda x: x.score, reverse=True):
        if r.patent_id not in seen:
            seen.add(r.patent_id)
            unique_results.append(r)

    return SearchResponse(
        results=unique_results[: data.top_k],
        query=data.query,
        total=len(unique_results),
    )


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
    Search USPTO PatentsView API for patents.
    Returns real patent data from the US patent office.
    """
    effective_query = data.query or ""
    if not effective_query and not data.patent_number and not data.assignee:
        raise HTTPException(status_code=400, detail="Provide a query, patent number, or assignee")

    try:
        results = await search_patents_external(
            query=effective_query,
            assignee=data.assignee,
            patent_number=data.patent_number,
            max_results=data.max_results,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"External patent search failed: {str(e)}",
        )

    return results


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
