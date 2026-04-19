"""
One-time migration script: re-embeds all existing text segments in the 
database using the new local BAAI/bge-large-en-v1.5 model.

Run this after updating the tech stack to ensure vector search works 
with the new 1024-dim embeddings.
"""

import asyncio
import os
import sys
import uuid
import torch
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sentence_transformers import SentenceTransformer

# Add the app directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.models.embeddings import PatentEmbedding, ClaimEmbedding
from app.models.legal_source import LegalSourceChunk
from app.models.patent import PatentClaim

# Initialize model
print("Loading local embedding model...")
model = SentenceTransformer(settings.EMBEDDING_MODEL, device="cpu")

# Initialize engine
engine = create_async_engine(settings.DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def migrate_patent_embeddings(session: AsyncSession):
    """Re-embed chunks in patent_embeddings table."""
    print("Processing patent_embeddings...")
    result = await session.execute(select(PatentEmbedding))
    chunks = result.scalars().all()
    
    if not chunks:
        print("  No patent chunks found.")
        return

    print(f"  Found {len(chunks)} patent chunks. Re-embedding...")
    
    batch_size = 32
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.chunk_text for c in batch]
        
        embeddings = model.encode(texts, normalize_embeddings=True)
        
        for chunk, emb in zip(batch, embeddings):
            # Since the table uses 'embedding' column (pgvector), 
            # we need to ensure the column exists and matches the new dimension.
            # IMPORTANT: You may need to run an Alembic migration first 
            # to resize the vector column to 1024 if it was 1536 (OpenAI) or 1024 (Voyage).
            # voyage-law-2 IS 1024 so we are good if coming from Voyage.
            await session.execute(
                update(PatentEmbedding)
                .where(PatentEmbedding.id == chunk.id)
                .values(embedding=emb.tolist())
            )
        
        await session.commit()
        print(f"    Processed {min(i + batch_size, len(chunks))}/{len(chunks)}")


async def migrate_claim_embeddings(session: AsyncSession):
    """Re-embed claims in claim_embeddings table."""
    print("Processing claim_embeddings...")
    # This assumes ClaimEmbedding table stores the text or we join with PatentClaim
    result = await session.execute(
        select(ClaimEmbedding, PatentClaim.claim_text)
        .join(PatentClaim, ClaimEmbedding.claim_id == PatentClaim.id)
    )
    rows = result.all()
    
    if not rows:
        print("  No claim embeddings found.")
        return

    print(f"  Found {len(rows)} claims. Re-embedding...")
    
    batch_size = 32
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        texts = [r.claim_text for r in batch]
        
        embeddings = model.encode(texts, normalize_embeddings=True)
        
        for (claim_emb, _), emb in zip(batch, embeddings):
            await session.execute(
                update(ClaimEmbedding)
                .where(ClaimEmbedding.id == claim_emb.id)
                .values(embedding=emb.tolist())
            )
        
        await session.commit()
        print(f"    Processed {min(i + batch_size, len(rows))}/{len(rows)}")


async def migrate_legal_source_chunks(session: AsyncSession):
    """Re-embed chunks in legal_source_chunks table."""
    print("Processing legal_source_chunks...")
    result = await session.execute(select(LegalSourceChunk))
    chunks = result.scalars().all()
    
    if not chunks:
        print("  No legal source chunks found.")
        return

    print(f"  Found {len(chunks)} legal chunks. Re-embedding...")
    
    batch_size = 32
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.chunk_text for c in batch]
        
        embeddings = model.encode(texts, normalize_embeddings=True)
        
        for chunk, emb in zip(batch, embeddings):
            await session.execute(
                update(LegalSourceChunk)
                .where(LegalSourceChunk.id == chunk.id)
                .values(embedding=emb.tolist())
            )
        
        await session.commit()
        print(f"    Processed {min(i + batch_size, len(chunks))}/{len(chunks)}")


async def main():
    async with AsyncSessionLocal() as session:
        try:
            await migrate_patent_embeddings(session)
            await migrate_claim_embeddings(session)
            await migrate_legal_source_chunks(session)
            print("\nMigration complete! All embeddings updated to BAAI/bge-large-en-v1.5.")
        except Exception as e:
            print(f"\nMigration failed: {e}")
            await session.rollback()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
