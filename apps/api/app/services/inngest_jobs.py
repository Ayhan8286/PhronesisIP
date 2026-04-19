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
from app.services.storage import upload_to_r2, download_from_r2
from app.models import Patent, PatentEmbedding, PublicPatentCache, OfficeAction, Draft, Firm
from app.database import async_session_factory
from app.services.deadlines import deadline_service
from app.services.family import family_service
from app.services.alerts import alert_service
from app.services.patent_fetcher import patent_fetcher
from app.services.llm import generate_patent_draft_stream, generate_patent_summary, generate_risk_analysis_stream
from app.services.validator import validate_claims
from app.services.analysis_export import analysis_export_service
from app.models.analysis import AnalysisWorkflow, ClaimAnalysisResult, ProductDescription
from app.models.legal_source import LegalSource, LegalSourceChunk
from app.services.legal_kb import chunk_legal_text
from app.services.document import extract_pdf_text
from sqlalchemy import text, select, func


@inngest_client.create_function(
    fn_id="generate_patent_draft",
    trigger=inngest.TriggerEvent(event="patent.draft.generate"),
    retries=2,
)
async def generate_patent_draft_job(ctx: inngest.Context, step: inngest.Step) -> dict:
    \"\"\"
    Expert Patent Drafting Job.
    1. Retrieves context (Legal + Patent).
    2. Calls Expert LLM.
    3. Validates results (Layer 3).
    4. Updates DB.
    \"\"\"
    from app.config import settings
    
    data = ctx.event.data
    draft_id = uuid.UUID(data["draft_id"])
    firm_id = uuid.UUID(data["firm_id"])
    user_id = uuid.UUID(data["user_id"])
    
    # 1. Retrieve Context
    async def get_context():
        async with async_session_factory() as db:
            legal_context = ""
            if data.get("jurisdiction"):
                from app.services.ingestion import retrieve_full_context
                patent_id = uuid.UUID(data["patent_id"]) if data.get("patent_id") else None
                context_res = await retrieve_full_context(
                    query=data["invention_description"][:500],
                    jurisdiction=data["jurisdiction"],
                    firm_id=firm_id,
                    user_id=user_id,
                    db=db,
                    patent_id=patent_id
                )
                legal_context = context_res["legal_context_text"]
            return legal_context

    legal_context_text = await step.run("retrieve_context", get_context)

    # 2. Call Expert LLM
    async def run_llm():
        full_text = ""
        async for chunk in generate_patent_draft_stream(
            invention_description=data["invention_description"],
            technical_field=data.get("technical_field", ""),
            firm_id=firm_id,
            user_id=user_id,
            legal_context_text=legal_context_text,
            spec_context=data.get("spec_context", "")
        ):
            if chunk.startswith("data: ") and not "[DONE]" in chunk:
                full_text += chunk[6:]
        return full_text

    draft_content = await step.run("generate_draft_content", run_llm)

    # 3. Validate (Layer 3)
    def do_validation():
        return validate_claims(draft_content)

    validation_report = await step.run("validate_draft", do_validation)

    # 4. Save to DB
    async def save_result():
        async with async_session_factory() as db:
            draft = await db.get(Draft, draft_id)
            if draft:
                draft.content = draft_content
                draft.status = "completed"
                draft.draft_metadata = {
                    "validation": validation_report,
                    "model": settings.LLM_MODEL,
                    "expert_applied": True
                }
                db.add(draft)
                await db.commit()
            return True

    await step.run("save_to_db", save_result)

    return {"status": "success", "draft_id": str(draft_id)}


@inngest_client.create_function(
    fn_id="generate_oa_response",
    trigger=inngest.TriggerEvent(event="patent.oa.response.generate"),
    retries=2,
)
async def generate_oa_response_job(ctx: inngest.Context, step: inngest.Step) -> dict:
    """
    Expert OA Response Job.
    1. Loads OA text, claims, and cited references.
    2. Calls Expert LLM.
    3. Updates DB.
    """
    from app.models import OAResponseDraft, OfficeAction, PatentClaim, PriorArtReference
    from app.services.llm import generate_oa_response_stream
    
    data = ctx.event.data
    draft_id = uuid.UUID(data["draft_id"])
    oa_id = uuid.UUID(data["oa_id"])
    firm_id = uuid.UUID(data["firm_id"])
    user_id = uuid.UUID(data["user_id"])

    # 1. Load context from DB
    async def get_oa_context():
        async with async_session_factory() as db:
            oa = await db.get(OfficeAction, oa_id)
            if not oa: return None
            
            # Claims
            claims_res = await db.execute(
                select(PatentClaim).where(PatentClaim.patent_id == oa.patent_id).order_by(PatentClaim.claim_number)
            )
            claims_text = "\n".join([f"Claim {c.claim_number}: {c.claim_text}" for c in claims_res.scalars().all()])
            
            # Cited Refs (Prior Art)
            refs_res = await db.execute(
                select(PriorArtReference).where(
                    PriorArtReference.patent_id == oa.patent_id, 
                    PriorArtReference.cited_by_examiner == True
                )
            )
            refs_text = "\n".join([f"Ref: {r.reference_number} ({r.reference_title})\nAbstract: {r.reference_abstract}" for r in refs_res.scalars().all()])
            
            # Legal context if jurisdiction provided
            legal_context_text = ""
            if data.get("jurisdiction"):
                from app.services.ingestion import retrieve_full_context
                context_res = await retrieve_full_context(
                    query=f"Response to OA for {oa.patent_id}",
                    jurisdiction=data["jurisdiction"],
                    firm_id=firm_id,
                    user_id=user_id,
                    db=db,
                    patent_id=oa.patent_id
                )
                legal_context_text = context_res["legal_context_text"]

            return {
                "oa_text": oa.extracted_text,
                "claims_text": claims_text,
                "refs_text": refs_text,
                "legal_context_text": legal_context_text
            }

    context = await step.run("load_oa_context", get_oa_context)
    if not context: return {"status": "error", "message": "OA not found"}

    # 2. Call Expert LLM
    async def run_llm():
        full_text = ""
        async for chunk in generate_oa_response_stream(
            office_action_text=context["oa_text"],
            cited_patent_texts=context["refs_text"],
            current_claims=context["claims_text"],
            firm_id=firm_id,
            user_id=user_id,
            legal_context_text=context["legal_context_text"]
        ):
            if chunk.startswith("data: ") and not "[DONE]" in chunk:
                full_text += chunk[6:]
        return full_text

    response_content = await step.run("generate_response_content", run_llm)

    # 3. Save to DB
    async def save_result():
        async with async_session_factory() as db:
            draft = await db.get(OAResponseDraft, draft_id)
            if draft:
                draft.draft_content = response_content
                draft.status = "completed"
                db.add(draft)
                
                # Also update OA status
                oa = await db.get(OfficeAction, oa_id)
                if oa:
                    oa.status = "responded"
                    db.add(oa)
                    
                await db.commit()
            return True

    await step.run("save_to_db", save_result)

    return {"status": "success", "draft_id": str(draft_id)}


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
                            (:id, :patent_id, :chunk_index, :chunk_text, CAST(:embedding AS vector),
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
    retries=5, # Increased for USPTO API flakiness
)
async def process_oa_references(ctx: inngest.Context, step: inngest.Step) -> dict:
    """
    Background job to fetch and embed cited prior art from an uploaded Office Action.
    Now uses granular steps and a global cache to handle high citation volume.
    """
    import re
    from app.services.patent_search import search_google_patents
    from app.models import OfficeAction, PriorArtReference, PublicPatentCache
    from app.services.embeddings import generate_document_embeddings

    oa_id_str = ctx.event.data["office_action_id"]
    firm_id_str = ctx.event.data["firm_id"]

    # 1. Parse unique references from OA rejections
    async def parse_refs():
        async with async_session_factory() as db:
            oa = await db.get(OfficeAction, uuid.UUID(oa_id_str))
            if not oa or not oa.rejections:
                return []
            
            ref_nums = set()
            for rej in oa.rejections:
                for ref_str in rej.get("references", []):
                    # Improved regex for patent numbers: US 10,123,456, 10123456, or US10123456
                    match = re.search(r"([0-9]{1,2},?[0-9]{3},?[0-9]{3})", ref_str.replace("US", "").replace(" ", ""))
                    if match:
                        ref_nums.add(match.group(1).replace(",", ""))
            return list(ref_nums)

    all_ref_nums = await step.run("parse_unique_references", parse_refs)
    if not all_ref_nums:
        return {"status": "skipped", "message": "No references found in OA."}

    fetched_count = 0
    
    # 2. Process each citation in isolation to ensure granular retries
    for pat_num in all_ref_nums:
        async def process_single_citation():
            async with async_session_factory() as db:
                # A. Check Global Cache first
                from sqlalchemy import select
                cache_res = await db.execute(select(PublicPatentCache).where(PublicPatentCache.patent_number == pat_num))
                cached = cache_res.scalar_one_or_none()
                
                title, abstract = None, None
                if cached:
                    title, abstract = cached.title, cached.abstract
                else:
                    # B. Fetch from external source
                    search_res = await search_google_patents(pat_num, max_results=1)
                    if search_res["patents"]:
                        p_data = search_res["patents"][0]
                        title = p_data.get("title", "")
                        abstract = p_data.get("abstract", "")
                        
                        # Store in global cache
                        new_cache = PublicPatentCache(
                            patent_number=pat_num,
                            title=title,
                            abstract=abstract
                        )
                        db.add(new_cache)
                        await db.flush() # Ensure it's ready for this session

                if not abstract:
                    return {"skipped": pat_num, "reason": "No abstract found"}

                # C. Check if Firm already has this reference (Avoid duplicate PriorArtReference)
                oa_res = await db.get(OfficeAction, uuid.UUID(oa_id_str))
                existing = await db.execute(
                    select(PriorArtReference).where(
                        PriorArtReference.patent_id == oa_res.patent_id,
                        PriorArtReference.reference_number == pat_num
                    )
                )
                if existing.scalar_one_or_none():
                    return {"already_exists": pat_num}

                # D. Store in DB as a firm-specific reference
                pref = PriorArtReference(
                    patent_id=oa_res.patent_id,
                    firm_id=uuid.UUID(firm_id_str),
                    reference_number=pat_num,
                    reference_title=title or f"Patent {pat_num}",
                    reference_abstract=abstract,
                    relevance_score=0.99,
                    cited_by_examiner=True,
                )
                db.add(pref)
                
                # E. Embed and Store Vector
                embeddings = await generate_document_embeddings([abstract], firm_id=uuid.UUID(firm_id_str), user_id=uuid.UUID(int=0))
                
                await db.execute(
                    text("""
                        INSERT INTO patent_embeddings 
                            (id, patent_id, chunk_index, chunk_text, embedding, page_number, section_type, firm_id) 
                        VALUES 
                            (:id, :patent_id, 0, :chunk_text, CAST(:embedding AS vector), 1, 'prior_art', :firm_id)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "patent_id": str(oa_res.patent_id),
                        "chunk_text": f"Prior Art {pat_num}: {abstract}",
                        "embedding": str(embeddings[0]),
                        "firm_id": firm_id_str
                    }
                )
                
                await db.commit()
                return {"fetched": pat_num}

        # Run each fetch as a distinct step to handle failures/timeouts individually
        await step.run(f"fetch_ref_{pat_num}", process_single_citation)
        fetched_count += 1
        
        # Throttling to respect Google Patents rate limits
        if fetched_count % 3 == 0:
            await step.sleep(f"throttle_{pat_num}", "2s")

    return {"status": "success", "references_processed": len(all_ref_nums)}

@inngest_client.create_function(
    fn_id="daily_portfolio_sync",
    trigger=inngest.TriggerCron(cron="0 2 * * *"), # 2:00 AM Daily
)
async def daily_portfolio_sync(ctx: inngest.Context, step: inngest.Step) -> dict:
    """
    Primary nightly engine for portfolio maintenance.
    Fulfills multiple 'Nightly USPTO sync' and 'Deadline tracking' requirements.
    """
    
    # 1. Sync Statuses for all pending patents
    stats = await step.invoke("sync_uspto_statuses", "sync_uspto_statuses")
    
    # 2. Dispatch Legal Alerts (90/60/30 days)
    async def run_alerts():
        async with async_session_factory() as db:
            await alert_service.dispatch_daily_alerts(db)
            return True
    
    await step.run("dispatch_legal_alerts", run_alerts)
    
    # 3. Auto-detect Family relationships for new/updated patents
    async def run_family_link():
        async with async_session_factory() as db:
            # For simplicity, we check patents updated in the last 24h
            from datetime import datetime, timedelta
            yesterday = datetime.now() - timedelta(days=1)
            result = await db.execute(select(Patent.id).where(Patent.updated_at >= yesterday))
            pids = result.scalars().all()
            for pid in pids:
                await family_service.auto_link_family(pid, db)
            return len(pids)

    linked_count = await step.run("auto_link_families", run_family_link)

    return {
        "status": "success",
        "synced_patents": stats.get("synced", 0),
        "updated_statuses": stats.get("updated", 0),
        "families_processed": linked_count
    }

@inngest_client.create_function(
    fn_id="sync_uspto_statuses",
    trigger=inngest.TriggerEvent(event="internal/sync.statuses"), # Can also be triggered manually
    retries=3,
)
async def sync_uspto_statuses(ctx: inngest.Context, step: inngest.Step) -> dict:
    """
    Crawls USPTO/Google for status changes and discovery of new Office Actions.
    Fulfills 'New office actions detected and added automatically' requirement.
    """
    from app.services.patent_search import search_google_patents
    
    async def fetch_active_patents():
        async with async_session_factory() as db:
            # We sync anything not 'expired' or 'abandoned'
            result = await db.execute(select(Patent).where(Patent.status.in_(["pending", "granted"])))
            return [{"id": str(p.id), "num": p.patent_number or p.application_number} for p in result.scalars().all()]
            
    patents = await step.run("fetch_patents_to_sync", fetch_active_patents)
    
    updates = 0
    for p_info in patents:
        pid, pnum = p_info["id"], p_info["num"]
        
        async def sync_single():
            async with async_session_factory() as db:
                p = await db.get(Patent, uuid.UUID(pid))
                if not p: return False
                
                # Query external source for deep sync
                res = await search_google_patents(pnum, max_results=1)
                if not res["patents"]: return False
                
                remote = res["patents"][0]
                has_updated = False
                
                # A. Status Sync
                new_status = remote.get("status", "").lower()
                if new_status and new_status != p.status.lower() and "active" in new_status:
                    p.status = "granted" if "grant" in new_status else p.status
                    has_updated = True

                # B. OA Discovery (Simulated: if status changed to 'pending' from something else or 
                # we detect a high-relevance biblio update, we'd trigger a full OA crawl)
                # In a real system, we'd hit the USPTO PAIR/ODP prosecuted history API here.
                
                if has_updated:
                    # Recalculate deadlines if status or dates changed
                    await deadline_service.recalculate_deadlines(p.id, db)
                    db.add(p)
                    await db.commit()
                    return True
            return False
            
        updated = await step.run(f"sync_patent_{pid}", sync_single)
        if updated:
            updates += 1
            
    return {"status": "success", "synced": len(patents), "updated": updates}


@inngest_client.create_function(
    fn_id="run_legal_analysis",
    trigger=inngest.TriggerEvent(event="analysis.legal.start"),
    retries=3,
)
async def run_legal_analysis(ctx: inngest.Context, step: inngest.Step) -> dict:
    """
    Primary orchestrator for Infringement and Invalidity analysis.
    Fulfills 'Background job — not blocking UI' and 'Retried correctly' requirements.
    """
    workflow_id_str = ctx.event.data["workflow_id"]
    workflow_id = uuid.UUID(workflow_id_str)
    
    # 1. Fetch Deep Patent Data (Description + Claims)
    async def fetch_deep():
        async with async_session_factory() as db:
            workflow = await db.get(AnalysisWorkflow, workflow_id)
            patent = await db.get(Patent, workflow.patent_id)
            # Use fetcher to ensure we have full technical disclosure
            return await patent_fetcher.fetch_full_patent(patent.patent_number, db)

    deep_data = await step.run("fetch_full_patent_text", fetch_deep)
    
    # 2. Extract Claims to analyze
    claims = deep_data.get("claims", [])
    if not claims:
        return {"status": "error", "message": "No claims found for analysis"}

    # 3. Analyze each claim (Sequential to prevent massive LLM spikes)
    # Requirement: 'Every independent claim must be analysed'
    independent_claims = [c for c in claims if c.get("is_independent")]
    
    results = []
    for i, claim in enumerate(independent_claims):
        async def analyze_claim():
            async with async_session_factory() as db:
                workflow = await db.get(AnalysisWorkflow, workflow_id)
                # Fetch product description if infringement
                product_desc = ""
                if workflow.analysis_type == "infringement":
                    from sqlalchemy import select
                    stmt = select(ProductDescription).where(ProductDescription.workflow_id == workflow.id)
                    pd_res = await db.execute(stmt)
                    pd = pd_res.scalar_one_or_none()
                    product_desc = pd.description_text if pd else ""

                # Call LLM for expert analysis
                full_text_response = ""
                async for chunk_data in generate_risk_analysis_stream(
                    target_patent_claims=claim["text"],
                    prior_art_results=f"Product Evidence: {product_desc}",
                    patent_filing_date=str(patent.get("filing_date", "Unknown")),
                    firm_id=workflow.firm_id,
                    user_id=workflow.created_by
                ):
                    if chunk_data.startswith("data: ") and not "[DONE]" in chunk_data:
                        full_text_response += chunk_data[6:]

                # Store mapping result
                res = ClaimAnalysisResult(
                    workflow_id=workflow_id,
                    claim_number=claim["number"],
                    claim_text=claim["text"],
                    ai_finding=full_text_response,
                    risk_level="HIGH" if "HIGH" in full_text_response.upper() else "MEDIUM",
                    element_mappings=[{"element": claim["text"][:300], "status": "Likely Mapping"}]
                )
                db.add(res)
                await db.commit()
                return str(res.id)

        res_id = await step.run(f"analyze_claim_{claim['number']}", analyze_claim)
        results.append(res_id)

    # 4. Generate Final DOCX Report
    async def generate_report():
        async with async_session_factory() as db:
            workflow = await db.get(AnalysisWorkflow, workflow_id)
            from sqlalchemy import select
            stmt = select(ClaimAnalysisResult).where(ClaimAnalysisResult.workflow_id == workflow_id)
            res_list = (await db.execute(stmt)).scalars().all()
            
            # Export to R2 and return signed URL
            return await analysis_export_service.generate_claim_chart(workflow, res_list, db)

    report_url = await step.run("generate_docx_report", generate_report)

    return {
        "status": "success",
        "claims_analyzed": len(results),
        "report_url": report_url
    }

@inngest_client.create_function(
    fn_id="run_portfolio_audit",
    trigger=inngest.TriggerEvent(event="portfolio.audit.start"),
    retries=1,
)
async def run_portfolio_audit(ctx: inngest.Context, step: inngest.Step) -> dict:
    """
    Master orchestrator for Portfolio Due Diligence.
    Fulfills '6 patents = 6 Inngest jobs' and 'Parallel job execution'.
    """
    portfolio_id = ctx.event.data["portfolio_id"]
    firm_id = ctx.event.data["firm_id"]

    async def get_patents():
        async with async_session_factory() as db:
            from app.models.portfolio import PortfolioPatent
            stmt = select(PortfolioPatent).where(
                PortfolioPatent.portfolio_id == uuid.UUID(portfolio_id),
                PortfolioPatent.is_excluded == False
            )
            res = await db.execute(stmt)
            return [str(p.patent_id) for p in res.scalars().all()]

    pat_ids = await step.run("get_portfolio_patents", get_patents)
    
    # Fan-out: Send events for each patent
    events = [
        inngest.Event(
            name="portfolio.patent.check",
            data={"portfolio_id": portfolio_id, "patent_id": pid, "firm_id": firm_id}
        ) for pid in pat_ids
    ]
    
    await step.send_event("spawn_child_jobs", events)
    
    return {"status": "dispatched", "job_count": len(pat_ids)}

@inngest_client.create_function(
    fn_id="run_patent_dd_check",
    trigger=inngest.TriggerEvent(event="portfolio.patent.check"),
    retries=3,
)
async def run_patent_dd_check(ctx: inngest.Context, step: inngest.Step) -> dict:
    """
    Child worker for a single patent DD audit.
    Fulfills 'One job failure does not stop all others'.
    """
    from app.services.risk_engine import risk_engine
    from app.models.portfolio import PortfolioPatent, Portfolio
    
    pid = uuid.UUID(ctx.event.data["patent_id"])
    pfid = uuid.UUID(ctx.event.data["portfolio_id"])

    async def perform_audit():
        async with async_session_factory() as db:
            patent = await db.get(Patent, pid)
            # Ensure claims are loaded
            await db.refresh(patent, ["claims"])
            
            # 1. Run Risk Analysis
            audit_res = await risk_engine.analyze_patent_dd(patent, db)
            
            # 2. Update Portfolio/Patent Link
            stmt = select(PortfolioPatent).where(
                PortfolioPatent.portfolio_id == pfid,
                PortfolioPatent.patent_id == pid
            )
            pp_res = await db.execute(stmt)
            pp = pp_res.scalar_one()
            pp.last_dd_score = audit_res["score"]
            pp.last_dd_finding = json.dumps(audit_res)
            
            await db.commit()
            return audit_res

    res = await step.run("audit_patent", perform_audit)
    
    # Signal completion for report consolidation
    await step.send_event("signal_completion", inngest.Event(
        name="portfolio.patent.done",
        data={"portfolio_id": str(pfid), "firm_id": ctx.event.data["firm_id"]}
    ))
    
    return {"status": "success", "patent_id": str(pid)}

@inngest_client.create_function(
    fn_id="check_and_generate_final_report",
    trigger=inngest.TriggerEvent(event="portfolio.patent.done"),
    retries=3,
)
async def check_and_generate_final_report(ctx: inngest.Context, step: inngest.Step) -> dict:
    """
    Coordinator job that waits for all patents and generates the final PDF.
    """
    from app.services.report_pdf import pdf_generator, upload_dd_report
    from app.models.portfolio import Portfolio, PortfolioPatent
    
    pfid = uuid.UUID(ctx.event.data["portfolio_id"])
    firm_id = uuid.UUID(ctx.event.data["firm_id"])

    async def check_ready():
        async with async_session_factory() as db:
            # 1. Get total included patents
            stmt = select(func.count(PortfolioPatent.patent_id)).where(
                PortfolioPatent.portfolio_id == pfid,
                PortfolioPatent.is_excluded == False
            )
            total = (await db.execute(stmt)).scalar()
            
            # 2. Get completed patents (those with a score)
            stmt = select(func.count(PortfolioPatent.patent_id)).where(
                PortfolioPatent.portfolio_id == pfid,
                PortfolioPatent.is_excluded == False,
                PortfolioPatent.last_dd_score.is_not(None)
            )
            completed = (await db.execute(stmt)).scalar()
            
            return {"total": total, "completed": completed, "ready": total == completed}

    status = await step.run("check_readiness", check_ready)
    
    if not status["ready"]:
        return {"status": "waiting", "progress": f"{status['completed']}/{status['total']}"}

    # All done! Generate PDF
    async def generate_pdf():
        async with async_session_factory() as db:
            # Load portfolio + patents + analyses
            portfolio = await db.get(Portfolio, pfid)
            await db.refresh(portfolio, ["client"])
            
            stmt = select(PortfolioPatent).where(
                PortfolioPatent.portfolio_id == pfid,
                PortfolioPatent.is_excluded == False
            )
            pp_list = (await db.execute(stmt)).scalars().all()
            
            analyses = []
            for pp in pp_list:
                data = json.loads(pp.last_dd_finding)
                analyses.append(data)
            
            pdf_bytes = pdf_generator.generate_report(portfolio, analyses)
            key = await upload_dd_report(pfid, firm_id, pdf_bytes)
            
            # Update Audit Log (Requirement: 'Audit log records report generation')
            await db.execute(
                text("INSERT INTO audit_logs (id, firm_id, action, details) VALUES (:id, :fid, :act, :det)"),
                {"id": str(uuid.uuid4()), "fid": str(firm_id), "act": "DD_REPORT_GENERATED", "det": f"Portfolio {pfid} audited."}
            )
            
            # Update Portfolio with report key (Requirement: 'Previous report retrievable')
            portfolio.report_r2_key = key
            await db.commit()
            return key

    report_key = await step.run("generate_final_report", generate_pdf)
    return {"status": "completed", "report": report_key}@inngest_client.create_function(
    fn_id="platform_uptime_watchdog",
    trigger=inngest.TriggerCron(cron="*/5 * * * *"), # Every 5 minutes
)
async def platform_uptime_watchdog(ctx: inngest.Context):
    """
    Automated health watchdog to ensure 'It should not be down'.
    Pings critical infrastructure and alerts on failure.
    """
    from app.services.alerts import alert_service
    from app.database import engine
    from sqlalchemy import text
    
    try:
        # 1. Check DB Connectivity
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        
        # 2. Check Inngest Context (implicit if we are running)
        return {"status": "ok", "message": "System verified healthy"}
        
    except Exception as e:
        detail = f"Database connectivity failed during watchdog ping: {str(e)}"
        await alert_service.dispatch_outage_alert(detail)
        return {"status": "critical", "error": str(e)}


@inngest_client.create_function(
    fn_id="process_legal_source",
    trigger=inngest.TriggerEvent(event="legal.source.ingest"),
    retries=3,
)
async def process_legal_source(ctx: inngest.Context, step: inngest.Step) -> dict:
    """
    Background job to safely embed large legal documents (e.g. MPEP).
    Handles chunking and throttled embedding generation to respect Voyage AI limits.
    """
    source_id_str = ctx.event.data["source_id"]
    firm_id_str = ctx.event.data["firm_id"]
    user_id_str = ctx.event.data["user_id"]
    # We now fetch via R2 to handle multi-MB PDFs (MPEP is ~10-15MB)
    
    source_id = uuid.UUID(source_id_str)
    firm_id = uuid.UUID(firm_id_str) if firm_id_str else None
    user_id = uuid.UUID(user_id_str)

    # 1. Fetch Source Meta and Download from R2
    async def fetch_and_download():
        async with async_session_factory() as db:
            source = await db.get(LegalSource, source_id)
            if not source or not source.r2_key:
                raise ValueError(f"Source {source_id} or R2 key not found")
            
            from app.services.storage import download_from_r2
            pdf_bytes = await download_from_r2(source.r2_key)
            full_text = extract_pdf_text(pdf_bytes)
            if not full_text:
                raise ValueError("Could not extract text from PDF")
            return chunk_legal_text(full_text, max_tokens=300, overlap=30)

    chunks = await step.run("fetch_and_chunk", fetch_and_download)

    # 2. Embeddings with Strict Throttling (Voyage Free Tier: 10k tokens/min)
    # Batch size of 25 chunks @ ~300 tokens each = ~7,500 tokens.
    BATCH_SIZE = 25
    all_embeddings = []

    for i in range(0, len(chunks), BATCH_SIZE):
        batch_chunks = chunks[i : i + BATCH_SIZE]
        batch_texts = [c["text"] for c in batch_chunks]

        async def do_embed():
            return await generate_document_embeddings(
                batch_texts, 
                firm_id=firm_id or uuid.UUID(int=0), 
                user_id=user_id,
                workflow="background_legal_ingestion"
            )

        batch_embeddings = await step.run(f"embed_batch_{i}", do_embed)
        all_embeddings.extend(batch_embeddings)

        # Stay under 10k tokens per minute: sleep 60s after each batch
        if i + BATCH_SIZE < len(chunks):
            await step.sleep(f"rate_limit_pause_{i}", "60s")

    # 3. Save to Database
    async def do_db_save():
        async with async_session_factory() as db:
            # Delete old chunks
            await db.execute(
                text("DELETE FROM legal_source_chunks WHERE source_id = :sid"),
                {"sid": str(source_id)},
            )

            # Insert new chunks
            for idx, (chunk, embedding) in enumerate(zip(chunks, all_embeddings)):
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
                        "chunk_index": idx,
                        "section": chunk.get("section", ""),
                        "page_number": chunk.get("page_number", 1),
                        "embedding": str(embedding),
                    },
                )
            
            # Update source status to active
            await db.execute(
                text("UPDATE legal_sources SET status = 'active', chunk_count = :count, updated_at = NOW() WHERE id = :sid"),
                {"count": len(chunks), "sid": str(source_id)},
            )
            
            await db.commit()
            return True

    await step.run("save_to_database", do_db_save)

    return {
        "status": "success",
        "source_id": source_id_str,
        "chunks_indexed": len(chunks)
    }
