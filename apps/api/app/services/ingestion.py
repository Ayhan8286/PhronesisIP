"""
Document ingestion pipeline + RAG context retrieval.

PHASE 1 — Ingestion (when attorney uploads a patent PDF):
  PDF → extract text → claim-aware chunking → Voyage AI embeddings → pgvector storage

PHASE 2 — Retrieval (when attorney asks a question):
  Query → embed → pgvector cosine similarity → top-K chunks returned

This module handles both phases. Phase 3 (generation) is in llm.py.
"""

import uuid
from typing import Optional, List, TypedDict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.document import extract_pdf_text
from app.services.embeddings import (
    chunk_patent_text,
    chunk_text,
    generate_document_embeddings,
    generate_query_embedding,
    ChunkedSegment,
)
from app.services.llm import generate_patent_summary
from app.models import Patent, PatentClaim, PatentEmbedding
from app.utils.logging import get_base_logger

logger = get_base_logger(__name__)

from app.utils.logging import get_base_logger

logger = get_base_logger(__name__)


# ── Types ───────────────────────────────────────────────────────────────────

class RetrievedChunk(TypedDict):
    chunk_text: str
    section_type: str
    page_number: int
    patent_id: str
    patent_title: str
    score: float


# ── PHASE 1: Ingestion ─────────────────────────────────────────────────────

async def ingest_patent_pdf(
    pdf_bytes: bytes,
    patent_id: uuid.UUID,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """
    Full ingestion pipeline for a patent PDF:
    1. Extract raw text via pdfplumber/PyMuPDF
    2. Claim-aware chunking (claims never split, 500-token window for prose)
    3. Generate embeddings via Voyage AI voyage-law-2
    4. Store embeddings + metadata in pgvector
    5. Generate AI summary
    6. Return stats

    ~80,000 words (115 pages) → ~160 chunks → ~160 Voyage API calls (batched)
    """
    # Step 1: Extract text
    full_text = extract_pdf_text(pdf_bytes)
    if not full_text:
        return {"error": "Could not extract text from PDF", "text_length": 0}

    # Step 2: Claim-aware chunking
    chunks: List[ChunkedSegment] = chunk_patent_text(
        full_text, max_tokens=500, overlap=50
    )

    # Step 3: Generate embeddings (batched, 64 at a time)
    chunk_texts = [c["text"] for c in chunks]
    embeddings = await generate_document_embeddings(chunk_texts, firm_id=firm_id, user_id=user_id)

    # Step 4: Delete old embeddings, insert new with metadata
    await db.execute(
        text("DELETE FROM patent_embeddings WHERE patent_id = :pid"),
        {"pid": str(patent_id)},
    )

    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        await db.execute(
            text("""
                INSERT INTO patent_embeddings
                    (id, patent_id, chunk_index, chunk_text, embedding,
                     page_number, section_type, firm_id)
                VALUES
                    (:id, :patent_id, :chunk_index, :chunk_text, :embedding::vector,
                     :page_number, :section_type, :firm_id)
            """),
            {
                "id": str(uuid.uuid4()),
                "patent_id": str(patent_id),
                "chunk_index": i,
                "chunk_text": chunk["text"],
                "embedding": str(embedding),
                "page_number": chunk.get("page_number", 1),
                "section_type": chunk.get("section_type", "description"),
                "firm_id": str(firm_id),
            },
        )

    # Step 5: Generate AI summary
    summary = await generate_patent_summary(full_text, firm_id=firm_id, user_id=user_id)

    # Step 6: Update patent record
    patent = await db.get(Patent, patent_id)
    if patent:
        if not patent.abstract and full_text:
            paragraphs = [p.strip() for p in full_text.split("\n\n") if len(p.strip()) > 100]
            if paragraphs:
                patent.abstract = paragraphs[0][:2000]

        existing_meta = patent.patent_metadata or {}
        existing_meta["ai_summary"] = summary
        existing_meta["text_length"] = len(full_text)
        existing_meta["chunk_count"] = len(chunks)
        existing_meta["ingested"] = True
        existing_meta["section_breakdown"] = _count_sections(chunks)
        patent.patent_metadata = existing_meta

    await db.flush()

    return {
        "text_length": len(full_text),
        "chunks": len(chunks),
        "embeddings_stored": len(embeddings),
        "section_breakdown": _count_sections(chunks),
        "summary": summary,
    }


def _count_sections(chunks: List[ChunkedSegment]) -> dict:
    """Count chunks per section type."""
    counts = {}
    for c in chunks:
        st = c.get("section_type", "description")
        counts[st] = counts.get(st, 0) + 1
    return counts


# ── PHASE 2: RAG Context Retrieval ──────────────────────────────────────────

async def retrieve_context(
    query: str,
    firm_id: uuid.UUID,
    db: AsyncSession,
    top_k: int = 15,
    section_filter: Optional[str] = None,
    patent_id_filter: Optional[uuid.UUID] = None,
) -> List[RetrievedChunk]:
    """
    RAG retrieval: find the top-K most relevant patent chunks for a query.

    1. Embed the query via Voyage AI (same model, input_type="query")
    2. pgvector cosine similarity against all firm's chunks
    3. Return top-K chunks with text + metadata

    Uses the HNSW index — returns results in ~50ms even across millions of vectors.
    """
    # Step 6 from the architecture: embed the attorney's query
    query_embedding = await generate_query_embedding(query)

    # Step 7: pgvector nearest neighbors
    filters = ["pe.firm_id = :firm_id"]
    params = {
        "query_embedding": str(query_embedding),
        "firm_id": str(firm_id),
        "top_k": top_k,
    }

    if section_filter:
        filters.append("pe.section_type = :section_filter")
        params["section_filter"] = section_filter

    if patent_id_filter:
        filters.append("pe.patent_id = :patent_id_filter")
        params["patent_id_filter"] = str(patent_id_filter)

    where_clause = " AND ".join(filters)

    sql = text(f"""
        SELECT
            pe.chunk_text,
            pe.section_type,
            pe.page_number,
            pe.patent_id,
            p.title as patent_title,
            1 - (pe.embedding <=> :query_embedding::vector) as score
        FROM patent_embeddings pe
        JOIN patents p ON pe.patent_id = p.id
        WHERE {where_clause}
        ORDER BY pe.embedding <=> :query_embedding::vector
        LIMIT :top_k
    """)

    result = await db.execute(sql, params)

    # Step 8: Return the actual text of the top chunks
    return [
        RetrievedChunk(
            chunk_text=row.chunk_text,
            section_type=row.section_type or "description",
            page_number=row.page_number or 0,
            patent_id=str(row.patent_id),
            patent_title=row.patent_title or "",
            score=float(row.score) if row.score else 0.0,
        )
        for row in result.all()
    ]


def format_context_for_llm(chunks: List[RetrievedChunk]) -> str:
    """
    Format retrieved chunks into a context block for Claude/Gemini.
    Each chunk is labeled with source patent, page, and section.

    This is what goes into the RAG prompt — Claude answers ONLY from this text.
    """
    if not chunks:
        return "No relevant patent context found in the portfolio."

    lines = ["RETRIEVED PATENT CONTEXT (from your portfolio, ranked by relevance):\n"]

    for i, chunk in enumerate(chunks, 1):
        source = f"[{chunk['patent_title']}]" if chunk.get("patent_title") else ""
        page = f"p.{chunk['page_number']}" if chunk.get("page_number") else ""
        section = chunk.get("section_type", "").replace("_", " ").title()
        meta = " | ".join(filter(None, [source, section, page]))

        lines.append(f"--- Chunk {i} ({meta}) [score: {chunk['score']:.2f}] ---")
        lines.append(chunk["chunk_text"])
        lines.append("")

    return "\n".join(lines)


# ── Patent Import (from external search) ────────────────────────────────────

async def ingest_patent_from_external(
    patent_data: dict,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Patent:
    """
    Import a patent from external source (Google Patents / USPTO ODP).
    Creates patent record + claims + generates embeddings from abstract.
    """
    # Check if already exists
    existing = await db.execute(
        text("SELECT id FROM patents WHERE firm_id = :fid AND patent_number = :pn"),
        {"fid": str(firm_id), "pn": patent_data.get("patent_number", "")},
    )
    if existing.first():
        raise ValueError("Patent already exists in your portfolio")

    # Create patent record
    patent = Patent(
        firm_id=firm_id,
        application_number=patent_data.get("patent_number", "").replace("US ", ""),
        patent_number=patent_data.get("patent_number", ""),
        title=patent_data.get("title", "Untitled"),
        abstract=patent_data.get("abstract", ""),
        status="granted" if patent_data.get("grant_date") else "pending",
        grant_date=patent_data.get("grant_date") if patent_data.get("grant_date") else None,
        inventors=patent_data.get("inventors", []),
        assignee=patent_data.get("assignee", ""),
        patent_metadata={
            "source": patent_data.get("source", "external"),
            "import_date": str(uuid.uuid4())[:10],
            "num_claims": patent_data.get("num_claims", 0),
        },
    )
    db.add(patent)
    await db.flush()
    await db.refresh(patent)

    # Import claims
    for claim_data in patent_data.get("claims", []):
        claim = PatentClaim(
            patent_id=patent.id,
            claim_number=claim_data.get("number", 0),
            claim_text=claim_data.get("text", ""),
            is_independent=claim_data.get("is_independent", False),
        )
        db.add(claim)

    # Generate embeddings from abstract + claims (with metadata)
    texts_to_embed = []
    chunk_metadata = []

    if patent_data.get("abstract"):
        texts_to_embed.append(patent_data["abstract"])
        chunk_metadata.append({"section_type": "abstract", "page_number": 1})

    for c in patent_data.get("claims", []):
        if c.get("text"):
            texts_to_embed.append(c["text"])
            chunk_metadata.append({"section_type": "claims", "page_number": 0})

    if texts_to_embed:
        try:
            embeddings = await generate_document_embeddings(texts_to_embed, firm_id=firm_id, user_id=user_id, workflow="import")
            for i, (txt, emb) in enumerate(zip(texts_to_embed, embeddings)):
                meta = chunk_metadata[i] if i < len(chunk_metadata) else {}
                await db.execute(
                    text("""
                        INSERT INTO patent_embeddings
                            (id, patent_id, chunk_index, chunk_text, embedding,
                             page_number, section_type, firm_id)
                        VALUES
                            (:id, :patent_id, :chunk_index, :chunk_text, :embedding::vector,
                             :page_number, :section_type, :firm_id)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "patent_id": str(patent.id),
                        "chunk_index": i,
                        "chunk_text": txt[:2000],
                        "embedding": str(emb),
                        "page_number": meta.get("page_number", 0),
                        "section_type": meta.get("section_type", "description"),
                        "firm_id": str(firm_id),
                    },
                )
        except Exception as e:
            logger.warning("Embedding generation failed", exc_info=True)

    await db.flush()
    return patent
