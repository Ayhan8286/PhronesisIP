"""
Optimized local processing for the 2100-page MPEP.
Uses local sentence-transformers for zero cost and zero rate limits.

Usage:
1. Ensure mpep-2100.pdf is in the current directory.
2. Run: python scripts/index_mpep_local.py
"""

import asyncio
import os
import sys
import uuid
import pdfplumber
import torch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sentence_transformers import SentenceTransformer

# Add the app directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.models.legal_source import LegalSource, LegalSourceChunk

# Configuration
PDF_PATH = "mpep-2100.pdf"
JURISDICTION = "USPTO"
TITLE = "MPEP Chapter 2100"
VERSION = "9th Edition, Rev. 07.2022"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# Initialize engine
engine = create_async_engine(settings.DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = ' '.join(words[i : i + size])
        chunks.append(chunk)
        i += size - overlap
    return chunks


async def process_mpep():
    if not os.path.exists(PDF_PATH):
        print(f"Error: {PDF_PATH} not found. Please place the PDF in the directory.")
        return

    print("Loading embedding model...")
    model = SentenceTransformer(settings.EMBEDDING_MODEL, device="cpu")

    async with AsyncSessionLocal() as session:
        # 1. Create LegalSource record
        new_source = LegalSource(
            id=uuid.uuid4(),
            title=TITLE,
            version=VERSION,
            jurisdiction=JURISDICTION,
            doc_type="guideline",
            status="processing",
            firm_id=None # Global source
        )
        session.add(new_source)
        await session.commit()
        
        source_id = new_source.id
        print(f"Created LegalSource record: {source_id}")

        all_chunks = []
        
        print(f"Extracting text from {PDF_PATH}...")
        with pdfplumber.open(PDF_PATH) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if not text or len(text.strip()) < 50:
                    continue
                
                # Split page into chunks
                page_chunks = chunk_text(text)
                for j, chunk_text_val in enumerate(page_chunks):
                    all_chunks.append({
                        "text": chunk_text_val,
                        "page": i + 1,
                        "index": len(all_chunks)
                    })
                
                if (i + 1) % 100 == 0:
                    print(f"  Processed {i + 1}/{len(pdf.pages)} pages...")

        print(f"Total chunks to embed: {len(all_chunks)}")
        
        # 2. Embed and Store
        batch_size = 32
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i : i + batch_size]
            texts = [c["text"] for c in batch]
            
            # Local inference
            embeddings = model.encode(texts, normalize_embeddings=True)
            
            for chunk_data, emb in zip(batch, embeddings):
                new_chunk = LegalSourceChunk(
                    source_id=source_id,
                    chunk_text=chunk_data["text"],
                    chunk_index=chunk_data["index"],
                    page_number=chunk_data["page"],
                    firm_id=None,
                    embedding=emb.tolist()
                )
                session.add(new_chunk)
            
            await session.commit()
            print(f"  Embedded and stored chunks {i} to {min(i + batch_size, len(all_chunks))}...")

        # 3. Finalize
        new_source.status = "active"
        new_source.chunk_count = len(all_chunks)
        await session.commit()
        
    print(f"\nSuccess! '{TITLE}' is now fully indexed and ready for strict RAG.")


if __name__ == "__main__":
    asyncio.run(process_mpep())
    asyncio.run(engine.dispose())
