"""
LLM service for generation workflows.

Supports:
- xAI Grok via the OpenAI-compatible API
- Groq as a backward-compatible fallback

The default configuration is now xAI so the only paid AI dependency can be Grok,
while retrieval can stay on open-source embeddings.
"""

import logging
import uuid
from typing import AsyncGenerator, Optional

from langchain_core.messages import HumanMessage

from app.config import settings
from app.services.cache import cache_service
from app.services.usage import log_usage

logger = logging.getLogger(__name__)


async def _get_llm(temperature: float = 0.3):
    """Return the configured chat model."""
    provider = (settings.LLM_PROVIDER or "xai").lower()

    if provider == "xai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.XAI_API_KEY,
            base_url=settings.XAI_BASE_URL,
            temperature=temperature,
            streaming=True,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=settings.LLM_MODEL,
            groq_api_key=settings.GROQ_API_KEY,
            temperature=temperature,
            streaming=True,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")


LEGAL_DISCLAIMER = (
    "\n\n---\n"
    "*Generated using provided legal sources only. "
    "This output requires attorney review before use. "
    "PhronesisIP provides AI assistance only. The reviewing attorney accepts "
    "professional responsibility for this filing.*"
)

PATENT_DRAFT_SYSTEM_PROMPT = """You are a senior USPTO patent prosecutor with 20 years of experience.
You are drafting a patent application under 35 U.S.C. § 111.

STRICT RULES — follow exactly:
1. TRANSITIONAL PHRASE: Always use "comprising" unless the client explicitly requests "consisting of". Comprising is open-ended and provides the broadest protection.
2. CLAIM STRUCTURE: Every independent claim must follow:
   "A [claim type] comprising: [element]; [element]; wherein..."
3. CLAIM TYPES: Draft three independent claims:
   - Apparatus/System claim ("A system comprising...")
   - Method claim ("A method comprising the steps of...")
   - CRM claim ("A non-transitory computer-readable medium...")
4. FORBIDDEN WORDS: Never use in claims:
   optionally, preferably, approximately, generally, such as, etc., means for, should, may, might
5. ANTECEDENT BASIS: Every element introduced with "a/an" must be referred to as "the [element]" thereafter.
6. DEPENDENT CLAIMS: Draft 5-10 dependent claims adding specific features.
7. SPECIFICATION: Use language like "in one embodiment" and "in another embodiment" and keep the disclosure broad.
8. CITE YOUR SOURCES: After each claim, note which MPEP section or 35 U.S.C. provision it satisfies.
9. FLAG ISSUES: If a claim element might face § 101 eligibility issues, add: [ATTORNEY REVIEW: § 101 risk]
"""

OA_RESPONSE_SYSTEM_PROMPT = """You are a senior USPTO patent prosecutor responding to an Office Action under 37 C.F.R. § 1.111.

REJECTION ANALYSIS RULES:
1. Identify EVERY ground of rejection.
2. For each § 102 rejection: find ONE missing element and state it clearly.
3. For each § 103 rejection: argue lack of motivation to combine, inoperability, or unexpected results.
4. NEVER admit prior art without explicit client approval.
5. NEVER say the invention "is similar to" the cited art.
6. Quote exact support locations from cited references whenever available.
7. Propose claim amendments only when argument alone is insufficient.
"""

INVALIDITY_ANALYSIS_SYSTEM_PROMPT = """You are a senior IP litigator building an invalidity case.

INVALIDITY ANALYSIS RULES:
1. Analyze EVERY independent claim separately.
2. For each claim element, search the prior art for explicit, implied, or combination disclosure.
3. Prior art must predate the filing date.
4. Generate a formal claim chart:
   Claim Element | Prior Art Reference | Location in Reference
5. For § 103 combinations: state the motivation to combine.
6. Flag claim elements with no prior art found.
7. Note confidence per element:
   [HIGH CONFIDENCE] [MEDIUM - attorney review] [LOW - weak art]
"""

PATENT_SUMMARY_SYSTEM_PROMPT = """You are an expert patent analyst.

Summarize the patent in plain, accurate language with these sections:
1. Title
2. Core invention
3. Novel technical ideas
4. Main independent claim themes
5. Commercial or litigation relevance

Stay grounded in the provided text. If a detail is unclear, say so.
"""


def build_grounded_prompt(system_rules: str, legal_chunks: str, context: str, user_input: str) -> str:
    return f"""{system_rules}

LEGAL CONTEXT FROM KNOWLEDGE BASE:
{legal_chunks}

BACKGROUND CONTEXT:
{context}

USER REQUEST / DISCLOSURE:
{user_input}
"""


async def _log_llm_usage(
    result,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    workflow_type: str,
) -> None:
    usage = getattr(result, "usage_metadata", None) or {}
    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
    output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0

    if not input_tokens and not output_tokens:
        response_meta = getattr(result, "response_metadata", {}) or {}
        token_usage = response_meta.get("token_usage", {}) or {}
        input_tokens = token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0))
        output_tokens = token_usage.get("completion_tokens", token_usage.get("output_tokens", 0))

    if input_tokens or output_tokens:
        await log_usage(
            firm_id=firm_id,
            user_id=user_id,
            provider=settings.LLM_PROVIDER,
            model=settings.LLM_MODEL,
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            workflow_type=workflow_type,
        )


async def generate_patent_summary(
    full_text: str,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str:
    """Generate a concise patent summary."""
    llm = await _get_llm(temperature=0.1)
    prompt = build_grounded_prompt(
        system_rules=PATENT_SUMMARY_SYSTEM_PROMPT,
        legal_chunks="",
        context="",
        user_input=full_text[:20000],
    )

    cached = await cache_service.get_llm_response(prompt)
    if cached:
        return cached

    result = await llm.ainvoke([HumanMessage(content=prompt)])
    content = result.content if hasattr(result, "content") else str(result)
    content = content if isinstance(content, str) else "".join(content)

    await cache_service.set_llm_response(prompt, content)
    await _log_llm_usage(result, firm_id=firm_id, user_id=user_id, workflow_type="patent_summary")
    return content


async def _stream_response(
    prompt: str,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    workflow_type: str,
    temperature: float,
) -> AsyncGenerator[str, None]:
    llm = await _get_llm(temperature=temperature)

    cached = await cache_service.get_llm_response(prompt)
    if cached:
        yield f"data: {cached}\n\n"
        yield "data: [DONE]\n\n"
        return

    full_response = []
    async for chunk in llm.astream([HumanMessage(content=prompt)]):
        if hasattr(chunk, "content") and chunk.content:
            text = chunk.content if isinstance(chunk.content, str) else "".join(chunk.content)
            full_response.append(text)
            yield f"data: {text}\n\n"

    final_text = "".join(full_response)
    if final_text:
        await cache_service.set_llm_response(prompt, final_text)
        await log_usage(
            firm_id=firm_id,
            user_id=user_id,
            provider=settings.LLM_PROVIDER,
            model=settings.LLM_MODEL,
            input_tokens=0,
            output_tokens=0,
            workflow_type=workflow_type,
        )

    yield f"data: {LEGAL_DISCLAIMER}\n\n"
    yield "data: [DONE]\n\n"


async def generate_patent_draft_stream(
    invention_description: str,
    technical_field: str,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    legal_context_text: str = "",
    spec_context: str = "",
) -> AsyncGenerator[str, None]:
    prompt = build_grounded_prompt(
        system_rules=PATENT_DRAFT_SYSTEM_PROMPT,
        legal_chunks=legal_context_text,
        context=f"TECHNICAL FIELD:\n{technical_field}\n\n{spec_context}",
        user_input=invention_description,
    )
    async for chunk in _stream_response(prompt, firm_id, user_id, "patent_draft", 0.3):
        yield chunk


async def generate_oa_response_stream(
    office_action_text: str,
    cited_patent_texts: str,
    current_claims: str,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    legal_context_text: str = "",
) -> AsyncGenerator[str, None]:
    prompt = build_grounded_prompt(
        system_rules=OA_RESPONSE_SYSTEM_PROMPT,
        legal_chunks=legal_context_text,
        context=f"CITED REFERENCES:\n{cited_patent_texts}\n\nCURRENT CLAIMS:\n{current_claims}",
        user_input=office_action_text,
    )
    async for chunk in _stream_response(prompt, firm_id, user_id, "office_action_response", 0.2):
        yield chunk


async def generate_risk_analysis_stream(
    target_patent_claims: str,
    prior_art_results: str,
    patent_filing_date: str,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AsyncGenerator[str, None]:
    prompt = f"""{INVALIDITY_ANALYSIS_SYSTEM_PROMPT}

PATENT FILING DATE: {patent_filing_date}

TARGET PATENT CLAIMS:
{target_patent_claims}

PRIOR ART FOUND:
{prior_art_results}
"""
    async for chunk in _stream_response(prompt, firm_id, user_id, "risk_analysis", 0.1):
        yield chunk
