"""
Embedding service with pluggable providers.

Preferred low-cost path:
- local open-source embeddings with BAAI/bge-m3

Backward-compatible fallback:
- Jina API
"""

import asyncio
import logging
import uuid
from functools import lru_cache
from typing import List, Optional, TypedDict

import httpx

from app.config import settings
from app.services.cache import cache_service
from app.services.usage import log_usage

logger = logging.getLogger(__name__)

JINA_API_URL = "https://api.jina.ai/v1/embeddings"


class ChunkedSegment(TypedDict):
    text: str
    section_type: str
    page_number: int


@lru_cache(maxsize=1)
def _get_local_embedding_model():
    from sentence_transformers import SentenceTransformer

    logger.info("Loading local embedding model: %s", settings.LOCAL_EMBEDDING_MODEL)
    return SentenceTransformer(settings.LOCAL_EMBEDDING_MODEL)


def _validate_embedding_size(embedding: List[float]) -> List[float]:
    if len(embedding) != settings.EMBEDDING_DIM:
        raise ValueError(
            f"Embedding dimension mismatch. Expected {settings.EMBEDDING_DIM}, got {len(embedding)}."
        )
    return embedding


async def _embed_local(inputs: List[str], is_query: bool) -> List[List[float]]:
    def _run() -> List[List[float]]:
        model = _get_local_embedding_model()
        texts = inputs
        if is_query and settings.EMBEDDING_QUERY_PREFIX:
            texts = [f"{settings.EMBEDDING_QUERY_PREFIX}{text}" for text in inputs]

        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [list(map(float, vector.tolist())) for vector in vectors]

    embeddings = await asyncio.to_thread(_run)
    return [_validate_embedding_size(embedding) for embedding in embeddings]


async def _embed_jina(
    inputs: List[str],
    *,
    task: str,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    workflow: str,
) -> List[List[float]]:
    if not settings.JINA_API_KEY:
        logger.error("JINA_API_KEY is not set.")
        return [[0.0] * settings.EMBEDDING_DIM for _ in inputs]

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            JINA_API_URL,
            headers={"Authorization": f"Bearer {settings.JINA_API_KEY}"},
            json={
                "model": settings.EMBEDDING_MODEL,
                "task": task,
                "input": inputs,
            },
        )
        response.raise_for_status()
        result = response.json()
        embeddings = [list(map(float, item["embedding"])) for item in result["data"]]

    await log_usage(
        firm_id=firm_id,
        user_id=user_id,
        provider="jina",
        model=settings.EMBEDDING_MODEL,
        input_tokens=result.get("usage", {}).get("total_tokens", 0),
        workflow_type=workflow,
    )
    return [_validate_embedding_size(embedding) for embedding in embeddings]


async def generate_query_embedding(
    query: str,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
) -> List[float]:
    """Generate an embedding for a search query."""
    cached = await cache_service.get_embedding(query)
    if cached:
        return cached

    provider = settings.EMBEDDING_PROVIDER.lower()
    try:
        if provider == "local":
            embedding = (await _embed_local([query], is_query=True))[0]
        elif provider == "jina":
            embedding = (
                await _embed_jina(
                    [query],
                    task="retrieval.query",
                    firm_id=firm_id,
                    user_id=user_id,
                    workflow="semantic_search",
                )
            )[0]
        else:
            raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER}")

        await cache_service.set_embedding(query, embedding)
        return embedding
    except Exception as exc:
        logger.error("Embedding error (query): %s", exc)
        return [0.0] * settings.EMBEDDING_DIM


async def generate_document_embeddings(
    texts: List[str],
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    workflow: str = "ingestion",
) -> List[List[float]]:
    """Generate embeddings for a batch of document chunks with cache reuse."""
    if not texts:
        return []

    final_embeddings: List[Optional[List[float]]] = [None] * len(texts)
    missing_indices = []
    missing_texts = []

    for idx, text in enumerate(texts):
        cached = await cache_service.get_embedding(text)
        if cached:
            final_embeddings[idx] = cached
        else:
            missing_indices.append(idx)
            missing_texts.append(text)

    if missing_texts:
        provider = settings.EMBEDDING_PROVIDER.lower()
        try:
            if provider == "local":
                generated = await _embed_local(missing_texts, is_query=False)
            elif provider == "jina":
                generated = await _embed_jina(
                    missing_texts,
                    task="retrieval.passage",
                    firm_id=firm_id,
                    user_id=user_id,
                    workflow=workflow,
                )
            else:
                raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER}")

            for idx, embedding in zip(missing_indices, generated):
                final_embeddings[idx] = embedding
                await cache_service.set_embedding(texts[idx], embedding)
        except Exception as exc:
            logger.error("Embedding error (batch): %s", exc)
            for idx in missing_indices:
                final_embeddings[idx] = [0.0] * settings.EMBEDDING_DIM

    return [embedding or [0.0] * settings.EMBEDDING_DIM for embedding in final_embeddings]


def chunk_text(full_text: str, max_tokens: int = 500, overlap: int = 50) -> List[str]:
    """Generic token-aware chunking helper."""
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(full_text)
    chunks = []
    step = max(1, max_tokens - overlap)

    for i in range(0, len(tokens), step):
        chunk_tokens = tokens[i : i + max_tokens]
        chunks.append(enc.decode(chunk_tokens))
        if i + max_tokens >= len(tokens):
            break

    return chunks


def chunk_patent_text(full_text: str, max_tokens: int = 500, overlap: int = 50) -> List[ChunkedSegment]:
    """Patent-aware chunking that preserves section labels."""
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    sections = {
        "abstract": "",
        "claims": "",
        "description": "",
    }

    lines = full_text.split("\n")
    current_section = "description"

    for line in lines:
        upper = line.upper().strip()
        if "ABSTRACT" in upper and len(upper) < 20:
            current_section = "abstract"
            continue
        if "CLAIMS" in upper and len(upper) < 20:
            current_section = "claims"
            continue
        if "DETAILED DESCRIPTION" in upper or ("DESCRIPTION" in upper and len(upper) < 30):
            current_section = "description"
            continue

        sections[current_section] += line + "\n"

    all_chunks: List[ChunkedSegment] = []
    step = max(1, max_tokens - overlap)

    for section_name, section_text in sections.items():
        if not section_text.strip():
            continue

        tokens = enc.encode(section_text)
        for i in range(0, len(tokens), step):
            chunk_tokens = tokens[i : i + max_tokens]
            text = enc.decode(chunk_tokens)
            char_pos = full_text.find(text[:50])
            page_num = (char_pos // 2500) + 1 if char_pos != -1 else 1

            all_chunks.append(
                {
                    "text": text,
                    "section_type": section_name,
                    "page_number": max(1, page_num),
                }
            )

            if i + max_tokens >= len(tokens):
                break

    return all_chunks
