"""
Embedding service using Voyage AI voyage-law-2.

Handles:
- Claim-aware patent text chunking (claims never split across boundaries)
- Section-type detection (abstract, claims, description, drawings)
- Batched embedding generation via Voyage AI
- Query embedding for semantic search
"""

import re
from typing import List, TypedDict

import voyageai

from app.config import settings

_client = None


def get_voyage_client():
    global _client
    if _client is None:
        _client = voyageai.Client(api_key=settings.VOYAGE_API_KEY)
    return _client


# ── Types ───────────────────────────────────────────────────────────────────

class ChunkedSegment(TypedDict):
    text: str
    section_type: str  # abstract, claims, description, drawings_description
    page_number: int   # estimated page based on character position


# ── Embedding Generation ────────────────────────────────────────────────────

async def generate_query_embedding(query: str) -> List[float]:
    """Generate a single embedding for a search query."""
    client = get_voyage_client()
    result = client.embed(
        texts=[query],
        model=settings.VOYAGE_MODEL,
        input_type="query",
    )
    return result.embeddings[0]


async def generate_document_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a batch of document chunks.
    Respects Voyage AI rate limits — batches of 64.
    """
    client = get_voyage_client()

    all_embeddings = []
    batch_size = 64  # Voyage supports up to 128, 64 is safe

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        result = client.embed(
            texts=batch,
            model=settings.VOYAGE_MODEL,
            input_type="document",
        )
        all_embeddings.extend(result.embeddings)

    return all_embeddings


# ── Claim-Aware Patent Chunking ─────────────────────────────────────────────

# Characters per page estimate (patent PDFs are dense)
CHARS_PER_PAGE = 3500

# Regex patterns for detecting patent sections
_CLAIMS_HEADER = re.compile(
    r"(?:^|\n\n)\s*(?:CLAIMS?|What is claimed is:?|I(?:/We)? claim:?)\s*\n",
    re.IGNORECASE,
)
_CLAIM_START = re.compile(
    r"(?:^|\n)\s*(\d{1,3})\.\s+",
)
_ABSTRACT_HEADER = re.compile(
    r"(?:^|\n\n)\s*(?:ABSTRACT(?:\s+OF\s+THE\s+DISCLOSURE)?)\s*\n",
    re.IGNORECASE,
)
_DESCRIPTION_HEADER = re.compile(
    r"(?:^|\n\n)\s*(?:DETAILED\s+DESCRIPTION|DESCRIPTION\s+OF\s+(?:THE\s+)?(?:PREFERRED\s+)?EMBODIMENTS?|SPECIFICATION)\s*\n",
    re.IGNORECASE,
)
_DRAWINGS_HEADER = re.compile(
    r"(?:^|\n\n)\s*(?:BRIEF\s+DESCRIPTION\s+OF\s+(?:THE\s+)?DRAWINGS?)\s*\n",
    re.IGNORECASE,
)


def _estimate_page(char_offset: int) -> int:
    """Estimate page number from character offset in full text."""
    return max(1, (char_offset // CHARS_PER_PAGE) + 1)


def _split_into_sections(full_text: str) -> List[dict]:
    """
    Split patent full text into labeled sections.
    Returns list of {"text": str, "section_type": str, "start_offset": int}.
    """
    sections = []
    text_lower = full_text

    # Find section boundaries
    boundaries = []

    for pattern, section_type in [
        (_ABSTRACT_HEADER, "abstract"),
        (_DRAWINGS_HEADER, "drawings_description"),
        (_DESCRIPTION_HEADER, "description"),
        (_CLAIMS_HEADER, "claims"),
    ]:
        for match in pattern.finditer(full_text):
            boundaries.append((match.start(), section_type, match.end()))

    # Sort by position
    boundaries.sort(key=lambda x: x[0])

    if not boundaries:
        # No sections detected — treat entire text as description
        return [{"text": full_text, "section_type": "description", "start_offset": 0}]

    # Text before first detected section
    if boundaries[0][0] > 100:
        sections.append({
            "text": full_text[: boundaries[0][0]].strip(),
            "section_type": "description",
            "start_offset": 0,
        })

    # Each section runs from its header to the next section's header
    for i, (start, section_type, content_start) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(full_text)
        section_text = full_text[content_start:end].strip()
        if section_text:
            sections.append({
                "text": section_text,
                "section_type": section_type,
                "start_offset": content_start,
            })

    return sections


def _chunk_claims(claims_text: str, start_offset: int) -> List[ChunkedSegment]:
    """
    Split claims section into individual claim chunks.
    Each claim gets its own chunk — NEVER split a claim across boundaries.
    """
    chunks: List[ChunkedSegment] = []

    # Find individual claim boundaries
    claim_starts = list(_CLAIM_START.finditer(claims_text))

    if not claim_starts:
        # Can't parse individual claims — return as single chunk
        return [{
            "text": claims_text.strip(),
            "section_type": "claims",
            "page_number": _estimate_page(start_offset),
        }]

    for i, match in enumerate(claim_starts):
        claim_end = claim_starts[i + 1].start() if i + 1 < len(claim_starts) else len(claims_text)
        claim_text = claims_text[match.start():claim_end].strip()

        if claim_text:
            chunks.append({
                "text": claim_text,
                "section_type": "claims",
                "page_number": _estimate_page(start_offset + match.start()),
            })

    return chunks


def _chunk_prose(
    text: str,
    section_type: str,
    start_offset: int,
    max_tokens: int = 500,
    overlap: int = 50,
) -> List[ChunkedSegment]:
    """
    Chunk prose text (description, abstract, drawings) with overlap.
    500 tokens ≈ 500 words. 50-token overlap prevents sentence loss at boundaries.
    """
    words = text.split()
    chunks: List[ChunkedSegment] = []
    start = 0

    while start < len(words):
        end = min(start + max_tokens, len(words))
        chunk_text = " ".join(words[start:end])

        # Estimate character offset for page number
        chars_before = len(" ".join(words[:start]))
        page = _estimate_page(start_offset + chars_before)

        chunks.append({
            "text": chunk_text,
            "section_type": section_type,
            "page_number": page,
        })

        # Advance with overlap
        start = end - overlap
        if start >= len(words):
            break

    return chunks


def chunk_patent_text(
    full_text: str,
    max_tokens: int = 500,
    overlap: int = 50,
) -> List[ChunkedSegment]:
    """
    Production patent chunking:
    1. Split text into sections (abstract, description, claims, drawings)
    2. Claims → individual chunks (never split across boundaries)
    3. Prose → 500-token windows with 50-token overlap
    4. Each chunk tagged with section_type and estimated page_number

    Returns list of ChunkedSegment dicts.
    """
    if not full_text or not full_text.strip():
        return []

    sections = _split_into_sections(full_text)
    all_chunks: List[ChunkedSegment] = []

    for section in sections:
        if section["section_type"] == "claims":
            # Claims get individual chunks — never split
            claim_chunks = _chunk_claims(section["text"], section["start_offset"])
            all_chunks.extend(claim_chunks)
        elif section["section_type"] == "abstract":
            # Abstract is usually < 500 tokens — keep as single chunk
            all_chunks.append({
                "text": section["text"],
                "section_type": "abstract",
                "page_number": _estimate_page(section["start_offset"]),
            })
        else:
            # Description / drawings — window chunking
            prose_chunks = _chunk_prose(
                section["text"],
                section["section_type"],
                section["start_offset"],
                max_tokens=max_tokens,
                overlap=overlap,
            )
            all_chunks.extend(prose_chunks)

    return all_chunks if all_chunks else [{
        "text": full_text[:2000],
        "section_type": "description",
        "page_number": 1,
    }]


# ── Legacy compat (simple word chunking for non-patent text) ────────────────

def chunk_text(text: str, max_tokens: int = 512, overlap: int = 50) -> List[str]:
    """
    Simple word-based chunking for non-patent text (specs, OA docs).
    Returns plain text strings (no metadata).
    """
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + max_tokens
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap

    return chunks if chunks else [text]
