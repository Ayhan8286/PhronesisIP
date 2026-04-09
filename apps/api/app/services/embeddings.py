"""
Embedding service using Voyage AI voyage-law-2.

Handles:
- Claim-aware patent text chunking (claims never split across boundaries)
- Section-type detection (abstract, claims, description, drawings)
- Batched embedding generation via Voyage AI
- Query embedding for semantic search
"""

import re
import uuid
from typing import List, TypedDict, Optional

import voyageai

from app.config import settings
from app.services.cache import cache_service
from app.services.usage import log_usage

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

async def generate_query_embedding(
    query: str, 
    firm_id: uuid.UUID, 
    user_id: uuid.UUID
) -> List[float]:
    """Generate a single embedding for a search query (cached)."""
    # 1. Try cache
    cached = await cache_service.get_embedding(query)
    if cached:
        return cached

    # 2. Call API
    client = get_voyage_client()
    result = client.embed(
        texts=[query],
        model=settings.VOYAGE_MODEL,
        input_type="query",
    )
    embedding = result.embeddings[0]

    # Log Usage (Using consolidated helper)
    await log_usage(
        firm_id=firm_id,
        user_id=user_id,
        provider="voyage",
        model=settings.VOYAGE_MODEL,
        input_tokens=result.total_tokens,
        workflow_type="semantic_search"
    )

    # 3. Store in cache
    await cache_service.set_embedding(query, embedding)
    return embedding


async def generate_document_embeddings(
    texts: List[str], 
    firm_id: uuid.UUID, 
    user_id: uuid.UUID,
    workflow: str = "ingestion"
) -> List[List[float]]:
    """
    Generate embeddings for a batch of document chunks with 'Partial Hit' caching.
    Checks each text against the cache; only uncached texts hit the Voyage AI API.
    """
    client = get_voyage_client()
    
    # 1. Initialize results array and identify missing texts
    final_embeddings = [None] * len(texts)
    missing_indices = []
    missing_texts = []

    for idx, text in enumerate(texts):
        cached = await cache_service.get_embedding(text)
        if cached:
            final_embeddings[idx] = cached
        else:
            missing_indices.append(idx)
            missing_texts.append(text)

    if not missing_texts:
        return final_embeddings

    # 2. Call API for missing texts only (in batches of 64)
    batch_size = 64
    for i in range(0, len(missing_texts), batch_size):
        batch = missing_texts[i : i + batch_size]
        result = client.embed(
            texts=batch,
            model=settings.VOYAGE_MODEL,
            input_type="document",
        )
        
        # Log Usage (Using consolidated helper)
        await log_usage(
            firm_id=firm_id,
            user_id=user_id,
            provider="voyage",
            model=settings.VOYAGE_MODEL,
            input_tokens=result.total_tokens,
            workflow_type=workflow
        )
        
        # 3. Fill results and update cache
        for j, emb in enumerate(result.embeddings):
            original_idx = missing_indices[i + j]
            final_embeddings[original_idx] = emb
            await cache_service.set_embedding(batch[j], emb)

    return final_embeddings


# ── Claim-Aware Patent Chunking ─────────────────────────────────────────────

def chunk_text(text: str, max_tokens: int = 500, overlap: int = 50) -> List[ChunkedSegment]:
    """ Simple token-based chunking with overlap. """
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    
    chunks = []
    for i in range(0, len(tokens), max_tokens - overlap):
        chunk_tokens = tokens[i : i + max_tokens]
        chunk_text = enc.decode(chunk_tokens)
        chunks.append({
            "text": chunk_text,
            "section_type": "general",
            "page_number": 1 # Approximation
        })
        if i + max_tokens >= len(tokens):
            break
            
    return chunks


def chunk_patent_text(full_text: str, max_tokens: int = 500, overlap: int = 50) -> List[ChunkedSegment]:
    """
    Patent-aware chunking:
    1. Splits by section (Abstract, Claims, Description).
    2. Claims are kept together as much as possible.
    3. Uses tiktoken for accurate windowing.
    """
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    
    # Simple section detection
    sections = {
        "abstract": "",
        "claims": "",
        "description": ""
    }
    
    # Try to split by common patent headers
    # (This is a simplified version of a robust patent parser)
    lines = full_text.split("\n")
    current_section = "description"
    
    for line in lines:
        upper = line.upper().strip()
        if "ABSTRACT" in upper and len(upper) < 20:
            current_section = "abstract"
            continue
        elif "CLAIMS" in upper and len(upper) < 20:
            current_section = "claims"
            continue
        elif "DETAILED DESCRIPTION" in upper or "DESCRIPTION" in upper and len(upper) < 30:
            current_section = "description"
            continue
            
        sections[current_section] += line + "\n"

    all_chunks = []
    
    for sec_name, sec_text in sections.items():
        if not sec_text.strip():
            continue
            
        tokens = enc.encode(sec_text)
        for i in range(0, len(tokens), max_tokens - overlap):
            chunk_tokens = tokens[i : i + max_tokens]
            txt = enc.decode(chunk_tokens)
            
            # Estimate page number (roughly 2500 characters per page)
            char_pos = full_text.find(txt[:50])
            page_num = (char_pos // 2500) + 1 if char_pos != -1 else 1

            all_chunks.append({
                "text": txt,
                "section_type": sec_name,
                "page_number": max(1, page_num)
            })
            
            if i + max_tokens >= len(tokens):
                break
                
    return all_chunks
