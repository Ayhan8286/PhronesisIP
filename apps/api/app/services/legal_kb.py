"""
Legal Knowledge Base service.

Handles:
- Ingesting legal source documents (MPEP, statutes, firm policies)
- Chunking into 300-token sections with legal section extraction
- Embedding via Voyage AI voyage-law-2
- Retrieval of relevant legal authority for strict RAG

This is the legal counterpart to the patent ingestion pipeline in ingestion.py.
"""

import re
import uuid
from typing import Optional, List, TypedDict
from datetime import datetime, timedelta

from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.document import extract_pdf_text
from app.services.embeddings import (
    chunk_text,
    generate_document_embeddings,
    generate_query_embedding,
)
from app.models.legal_source import LegalSource, LegalSourceChunk
from app.utils.logging import get_base_logger

logger = get_base_logger(__name__)


# ── Types ───────────────────────────────────────────────────────────────────

class LegalChunk(TypedDict):
    chunk_text: str
    section: str
    page_number: int
    source_title: str
    source_jurisdiction: str
    source_doc_type: str
    score: float


class LegalSourceInfo(TypedDict):
    """Metadata about a legal source used in generation, for the UI trust panel."""
    source_id: str
    title: str
    section: str
    jurisdiction: str
    doc_type: str
    score: float


# ── Legal Section Extraction ────────────────────────────────────────────────

# Regex patterns to detect legal section references in chunked text
_SECTION_PATTERNS = [
    # US statutes: "35 U.S.C. § 112", "35 USC §112"
    re.compile(r'(35\s*U\.?S\.?C\.?\s*§\s*\d+[\w.]*)', re.IGNORECASE),
    # CFR rules: "37 C.F.R. § 1.75"
    re.compile(r'(37\s*C\.?F\.?R\.?\s*§\s*[\d.]+)', re.IGNORECASE),
    # MPEP sections: "MPEP § 2111", "MPEP 2111.01"
    re.compile(r'(MPEP\s*§?\s*[\d.]+)', re.IGNORECASE),
    # EPO rules: "Rule 43 EPC", "Article 52 EPC"
    re.compile(r'((?:Rule|Article|Art\.?)\s*\d+[a-z]?\s*(?:EPC|PCT))', re.IGNORECASE),
    # Generic section: "Section 112", "§ 112"
    re.compile(r'((?:Section|§)\s*[\d.]+)', re.IGNORECASE),
    # Chapter headers: "Chapter 2100"
    re.compile(r'(Chapter\s*\d+)', re.IGNORECASE),
]


def extract_section_reference(chunk_text: str) -> Optional[str]:
    """
    Extract the most specific legal section reference from a chunk of text.
    Returns the first match, prioritizing more specific patterns (USC, CFR, MPEP).
    """
    for pattern in _SECTION_PATTERNS:
        match = pattern.search(chunk_text)
        if match:
            return match.group(1).strip()
    return None


# ── Legal-Aware Chunking ───────────────────────────────────────────────────

def chunk_legal_text(
    full_text: str,
    max_tokens: int = 300,
    overlap: int = 30,
) -> List[dict]:
    """
    Chunk legal text into 300-token sections (shorter than patent chunks)
    because legal rules need precise citation boundaries.

    Also extracts legal section references for each chunk.
    """
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(full_text)

    chunks = []
    for i in range(0, len(tokens), max_tokens - overlap):
        chunk_tokens = tokens[i: i + max_tokens]
        chunk_str = enc.decode(chunk_tokens)

        # Estimate page number (~2500 chars per page)
        char_pos = full_text.find(chunk_str[:50])
        page_num = (char_pos // 2500) + 1 if char_pos != -1 else 1

        # Extract section reference
        section = extract_section_reference(chunk_str)

        chunks.append({
            "text": chunk_str,
            "section": section or "",
            "page_number": max(1, page_num),
        })

        if i + max_tokens >= len(tokens):
            break

    return chunks


# ── PHASE 1: Legal Source Ingestion ─────────────────────────────────────────

async def ingest_legal_source(
    pdf_bytes: bytes,
    source_id: uuid.UUID,
    firm_id: Optional[uuid.UUID],
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """
    Full ingestion pipeline for a legal source document:
    1. Extract raw text via pdfplumber
    2. Chunk into 300-token sections with legal section extraction
    3. Generate embeddings via Voyage AI voyage-law-2
    4. Store embeddings + metadata in legal_source_chunks
    5. Update chunk_count on the source record
    """
    # Step 1: Extract text
    full_text = extract_pdf_text(pdf_bytes)
    if not full_text:
        return {"error": "Could not extract text from PDF", "text_length": 0}

    # Step 2: Legal-aware chunking (300 tokens, shorter than patent 500)
    chunks = chunk_legal_text(full_text, max_tokens=300, overlap=30)

    if not chunks:
        return {"error": "No text chunks produced", "text_length": len(full_text)}

    # Step 3: Generate embeddings (batched via existing infrastructure)
    chunk_texts = [c["text"] for c in chunks]
    embeddings = await generate_document_embeddings(
        chunk_texts,
        firm_id=firm_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
        user_id=user_id,
        workflow="legal_kb_ingestion",
    )

    # Step 4: Delete old chunks for this source, insert new
    await db.execute(
        text("DELETE FROM legal_source_chunks WHERE source_id = :sid"),
        {"sid": str(source_id)},
    )

    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        await db.execute(
            text("""
                INSERT INTO legal_source_chunks
                    (id, source_id, firm_id, chunk_text, chunk_index,
                     section, page_number, embedding)
                VALUES
                    (:id, :source_id, :firm_id, :chunk_text, :chunk_index,
                     :section, :page_number, CAST(:embedding AS vector))
            """),
            {
                "id": str(uuid.uuid4()),
                "source_id": str(source_id),
                "firm_id": str(firm_id) if firm_id else None,
                "chunk_text": chunk["text"],
                "chunk_index": i,
                "section": chunk.get("section", ""),
                "page_number": chunk.get("page_number", 1),
                "embedding": str(embedding),
            },
        )

    # Step 5: Update chunk_count on the source record
    await db.execute(
        text("""
            UPDATE legal_sources
            SET chunk_count = :count, updated_at = NOW()
            WHERE id = :sid
        """),
        {"count": len(chunks), "sid": str(source_id)},
    )

    await db.flush()

    return {
        "text_length": len(full_text),
        "chunks": len(chunks),
        "embeddings_stored": len(embeddings),
        "sections_found": len([c for c in chunks if c.get("section")]),
    }


# ── PHASE 2: Legal Authority Retrieval ──────────────────────────────────────

async def retrieve_legal_context(
    query: str,
    jurisdiction: str,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    top_k: int = 8,
    similarity_threshold: float = 0.65,
) -> List[LegalChunk]:
    """
    Retrieve relevant legal authority chunks for a query.

    Searches legal_source_chunks filtered by:
    - Jurisdiction (exact match)
    - Active sources only
    - Firm scope: firm-specific + global (firm_id IS NULL)
    - Similarity threshold: 0.65 (slightly lower than patent at 0.70
      because legal language is more formulaic)

    Returns top-K chunks with full source metadata for citation.
    """
    # Embed the query
    query_embedding = await generate_query_embedding(
        query, firm_id=firm_id, user_id=user_id
    )

    sql = text("""
        SELECT
            lsc.chunk_text,
            lsc.section,
            lsc.page_number,
            ls.title AS source_title,
            ls.jurisdiction AS source_jurisdiction,
            ls.doc_type AS source_doc_type,
            ls.id AS source_id,
            1 - (lsc.embedding <=> CAST(:query_embedding AS vector)) AS score
        FROM legal_source_chunks lsc
        JOIN legal_sources ls ON lsc.source_id = ls.id
        WHERE ls.jurisdiction = :jurisdiction
          AND (ls.firm_id = :firm_id OR ls.firm_id IS NULL)
          AND ls.is_active = true
          AND 1 - (lsc.embedding <=> CAST(:query_embedding AS vector)) > :threshold
        ORDER BY lsc.embedding <=> CAST(:query_embedding AS vector)
        LIMIT :top_k
    """)

    result = await db.execute(sql, {
        "query_embedding": str(query_embedding),
        "jurisdiction": jurisdiction,
        "firm_id": str(firm_id),
        "threshold": similarity_threshold,
        "top_k": top_k,
    })

    return [
        LegalChunk(
            chunk_text=row.chunk_text,
            section=row.section or "",
            page_number=row.page_number or 0,
            source_title=row.source_title or "",
            source_jurisdiction=row.source_jurisdiction or "",
            source_doc_type=row.source_doc_type or "",
            score=float(row.score) if row.score else 0.0,
        )
        for row in result.all()
    ]


def format_legal_context_for_llm(chunks: List[LegalChunk]) -> str:
    """
    Format retrieved legal chunks into a context block for the LLM.
    Each chunk is labeled with citation-ready source information.
    """
    if not chunks:
        return ""

    lines = []
    for chunk in chunks:
        section_label = f" — {chunk['section']}" if chunk['section'] else ""
        lines.append(
            f"[LEGAL SOURCE: {chunk['source_title']}{section_label}]\n"
            f"{chunk['chunk_text']}"
        )

    return "\n\n".join(lines)


def get_sources_metadata(chunks: List[LegalChunk]) -> List[LegalSourceInfo]:
    """
    Extract unique source metadata from retrieved chunks.
    Used by the frontend trust panel to show which sources were used.
    """
    seen = set()
    sources = []

    for chunk in chunks:
        key = f"{chunk['source_title']}|{chunk['section']}"
        if key not in seen:
            seen.add(key)
            sources.append(LegalSourceInfo(
                source_id="",  # Not available from chunk query
                title=chunk["source_title"],
                section=chunk["section"],
                jurisdiction=chunk["source_jurisdiction"],
                doc_type=chunk["source_doc_type"],
                score=chunk["score"],
            ))

    return sources


# ── Jurisdiction Status ─────────────────────────────────────────────────────

async def get_jurisdiction_status(
    jurisdiction: str,
    firm_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """
    Check the status of legal sources for a specific jurisdiction.
    Returns source count, chunk count, and staleness warnings.
    """
    result = await db.execute(
        text("""
            SELECT
                COUNT(DISTINCT ls.id) AS source_count,
                COALESCE(SUM(ls.chunk_count), 0) AS total_chunks,
                MIN(ls.source_updated_at) AS oldest_source,
                MAX(ls.created_at) AS newest_upload
            FROM legal_sources ls
            WHERE ls.jurisdiction = :jurisdiction
              AND (ls.firm_id = :firm_id OR ls.firm_id IS NULL)
              AND ls.is_active = true
        """),
        {"jurisdiction": jurisdiction, "firm_id": str(firm_id)},
    )

    row = result.first()
    source_count = int(row.source_count) if row else 0
    total_chunks = int(row.total_chunks) if row else 0
    oldest_source = row.oldest_source if row else None

    # Check staleness (> 12 months since source_updated_at)
    is_stale = False
    if oldest_source and isinstance(oldest_source, datetime):
        is_stale = (datetime.now(oldest_source.tzinfo) - oldest_source) > timedelta(days=365)

    return {
        "jurisdiction": jurisdiction,
        "source_count": source_count,
        "total_chunks": total_chunks,
        "has_sources": source_count > 0,
        "is_stale": is_stale,
        "oldest_source_date": oldest_source.isoformat() if oldest_source else None,
    }


async def list_available_jurisdictions(
    firm_id: uuid.UUID,
    db: AsyncSession,
) -> List[dict]:
    """List all jurisdictions that have at least one active legal source."""
    result = await db.execute(
        text("""
            SELECT
                ls.jurisdiction,
                COUNT(DISTINCT ls.id) AS source_count,
                COALESCE(SUM(ls.chunk_count), 0) AS total_chunks
            FROM legal_sources ls
            WHERE (ls.firm_id = :firm_id OR ls.firm_id IS NULL)
              AND ls.is_active = true
            GROUP BY ls.jurisdiction
            ORDER BY source_count DESC
        """),
        {"firm_id": str(firm_id)},
    )

    return [
        {
            "jurisdiction": row.jurisdiction,
            "source_count": int(row.source_count),
            "total_chunks": int(row.total_chunks),
        }
        for row in result.all()
    ]
