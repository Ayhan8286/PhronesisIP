"""
Background job definitions using Inngest.
Handles bulk processing tasks that might timeout in a standard HTTP request,
such as embedding large patents or huge multi-patent portfolios.
"""

import inngest
import uuid
import json

from app.services.inngest_client import inngest_client
from app.services.embeddings import chunk_patent_text, generate_document_embeddings
from app.services.llm import generate_patent_summary
from app.models import Patent, PatentEmbedding
from app.database import async_session_factory
from sqlalchemy import text


@inngest_client.create_function(
    fn_id="process_large_patent",
    trigger=inngest.TriggerEvent(event="patent.ingest.async"),
    retries=3,
)
async def process_large_patent(ctx: inngest.Context, step: inngest.Step) -> dict:
    """
    Background job to safely embed large patents.
    Chunks text, then embeds in batches via Voyage AI with step.sleep() pauses
    to respect rate limits and prevent timeouts.
    """
    patent_id_str = ctx.event.data["patent_id"]
    firm_id_str = ctx.event.data["firm_id"]
    full_text = ctx.event.data["full_text"]

    patent_id = uuid.UUID(patent_id_str)
    firm_id = uuid.UUID(firm_id_str)

    # 1. Chunking (fast, done in memory)
    def do_chunking():
        return chunk_patent_text(full_text, max_tokens=500, overlap=50)

    chunks = await step.run("chunk_patent_text", do_chunking)

    # 2. Embeddings with Batching
    BATCH_SIZE = 64
    all_embeddings = []

    for i in range(0, len(chunks), BATCH_SIZE):
        batch_chunks = chunks[i: i + BATCH_SIZE]
        batch_texts = [c["text"] for c in batch_chunks]

        async def do_embed():
            # Using firm_id and assuming a system user_id for background tasks or passing it if available
            return await generate_document_embeddings(batch_texts, firm_id=firm_id, user_id=uuid.UUID(int=0)) # Placeholder system user

        # Inngest steps must be deterministic and retriable
        batch_embeddings = await step.run(f"embed_batch_{i}", do_embed)
        all_embeddings.extend(batch_embeddings)

        # Brief sleep between batches to avoid Voyage AI rate limit spikes
        # The user specification requested "embed 200 chunks, wait 10 seconds, embed 200 more"
        # We're doing 64 chunks at a time, so after 3 batches (~192 chunks), we sleep
        if i > 0 and (i // BATCH_SIZE) % 3 == 0:
            await step.sleep(f"rate_limit_sleep_{i}", "10s")

    # 3. Store to Database
    async def do_db_save():
        async with async_session_factory() as db:
            # Delete old embedded chunks
            await db.execute(
                text("DELETE FROM patent_embeddings WHERE patent_id = :pid"),
                {"pid": str(patent_id)},
            )

            # Insert new chunks
            for idx, (chunk, embedding) in enumerate(zip(chunks, all_embeddings)):
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
                        "chunk_index": idx,
                        "chunk_text": chunk["text"],
                        "embedding": str(embedding),
                        "page_number": chunk.get("page_number", 1),
                        "section_type": chunk.get("section_type", "description"),
                        "firm_id": str(firm_id),
                    },
                )
            await db.commit()
            return True

    await step.run("save_to_database", do_db_save)

    # 4. Generate AI Summary (Background)
    async def do_summary():
        return await generate_patent_summary(full_text, firm_id=firm_id, user_id=uuid.UUID(int=0))

    summary = await step.run("generate_summary", do_summary)

    # 5. Final DB Record Update
    async def do_final_update():
        async with async_session_factory() as db:
            patent = await db.get(Patent, patent_id)
            if patent:
                existing_meta = patent.patent_metadata or {}
                existing_meta["ai_summary"] = summary
                existing_meta["text_length"] = len(full_text)
                existing_meta["chunk_count"] = len(chunks)
                existing_meta["ingested"] = True
                
                # Cannot store dict directly via assignment if it's not detected as changed
                patent.patent_metadata = existing_meta
                
                # Also set abstract if missing
                if not patent.abstract and full_text:
                    paragraphs = [p.strip() for p in full_text.split("\n\n") if len(p.strip()) > 100]
                    if paragraphs:
                        patent.abstract = paragraphs[0][:2000]

                db.add(patent)
                await db.commit()
            return True

    await step.run("update_patent_record", do_final_update)

    return {
        "status": "success",
        "chunks_processed": len(chunks)
    }

@inngest_client.create_function(
    fn_id="process_oa_references",
    trigger=inngest.TriggerEvent(event="oa.references.fetch"),
    retries=2,
)
async def process_oa_references(ctx: inngest.Context, step: inngest.Step) -> dict:
    """
    Background job to fetch and embed cited prior art from an uploaded Office Action.
    It scrapes Google Patents / USPTO for the full text of the cited reference,
    embeds it via Voyage AI, and saves to pgvector so Claude has full visibility 
    of the competitor's patent when drafting the response.
    """
    import re
    from app.services.patent_search import search_google_patents
    from app.models import OfficeAction, PriorArtReference
    
    oa_id_str = ctx.event.data["office_action_id"]
    firm_id_str = ctx.event.data["firm_id"]
    
    async def fetch_and_store_references():
        async with async_session_factory() as db:
            oa = await db.get(OfficeAction, uuid.UUID(oa_id_str))
            if not oa or not oa.rejections:
                return []
                
            fetched = []
            for rejection in oa.rejections:
                for ref_str in rejection.get("references", []):
                    # Extract roughly patent numbers like US8977255 or 8,977,255
                    match = re.search(r"(\b[0-9]{1,2},?[0-9]{3},?[0-9]{3}\b)", ref_str)
                    if match:
                        pat_num = match.group(1).replace(",", "")
                        # Fetch from Google Patents XHR
                        search_res = await search_google_patents(pat_num, max_results=1)
                        if search_res["patents"]:
                            p_data = search_res["patents"][0]
                            
                            # Embed the abstract mapping via Voyage AI
                            embeddings = await generate_document_embeddings([abstract_text], firm_id=uuid.UUID(firm_id_str), user_id=uuid.UUID(int=0)) if abstract_text else [[0.0]*1024]
                            
                            # Store in DB as a prior art reference
                            pref = PriorArtReference(
                                patent_id=oa.patent_id,
                                reference_number=p_data.get("patent_number", pat_num),
                                reference_title=p_data.get("title", ""),
                                reference_abstract=abstract_text,
                                relevance_score=0.99, # Highly relevant as examiner cited it
                                cited_by_examiner=True,
                                analysis_notes=f"Cited in {oa.action_type}",
                            )
                            db.add(pref)
                            fetched.append(p_data.get("patent_number"))
                            
                            # Insert the embedding for vector comparision
                            if abstract_text:
                                await db.execute(
                                    text("""
                                        INSERT INTO patent_embeddings 
                                            (id, patent_id, chunk_index, chunk_text, embedding, page_number, section_type, firm_id) 
                                        VALUES 
                                            (:id, :patent_id, 0, :chunk_text, :embedding::vector, 1, 'prior_art', :firm_id)
                                    """),
                                    {
                                        "id": str(uuid.uuid4()),
                                        "patent_id": str(oa.patent_id),
                                        "chunk_text": f"Prior Art {pat_num}: {abstract_text}",
                                        "embedding": str(embeddings[0]),
                                        "firm_id": firm_id_str
                                    }
                                )
            
            await db.commit()
            return fetched

    fetched_refs = await step.run("fetch_and_store_references", fetch_and_store_references)
    
    return {"status": "success", "fetched": fetched_refs}

@inngest_client.create_function(
    fn_id="sync_uspto_statuses",
    trigger=inngest.TriggerCron(cron="0 2 * * *"), # Runs every night at 2:00 AM
)
async def sync_uspto_statuses(ctx: inngest.Context, step: inngest.Step) -> dict:
    """
    Cron job to automatically sync pending patent statuses against the USPTO.
    Iterates through all 'pending' patents in the DB, queries external APIs,
    and updates their status and history if there are changes.
    """
    from app.services.patent_search import search_google_patents
    from sqlalchemy.future import select
    
    async def fetch_pending_patents():
        async with async_session_factory() as db:
            result = await db.execute(select(Patent).where(Patent.status == "pending"))
            return [str(p.id) for p in result.scalars().all()]
            
    patent_ids = await step.run("fetch_pending_patents", fetch_pending_patents)
    
    updates = 0
    for pid_str in patent_ids:
        async def sync_single_patent():
            async with async_session_factory() as db:
                p = await db.get(Patent, uuid.UUID(pid_str))
                if not p or not p.patent_number:
                    return False
                    
                # In production, we'd query USPTO API directly here. 
                # Since we lack an enterprise USPTO key, fallback to our Google Patents tool
                res = await search_google_patents(p.patent_number, max_results=1)
                if res["patents"]:
                    remote_status = res["patents"][0].get("status", "").lower()
                    if remote_status and remote_status != p.status.lower() and "active" in remote_status:
                        p.status = "granted"
                        db.add(p)
                        await db.commit()
                        return True
            return False
            
        updated = await step.run(f"sync_patent_{pid_str}", sync_single_patent)
        if updated:
            updates += 1
            
    return {"status": "success", "synced": len(patent_ids), "updated": updates}
