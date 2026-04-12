"""
LLM service: handles AI generation for all workflows.
Supports Gemini (dev) and Claude (production) via LangChain.
Produces STRUCTURED legal documents, not just free text.

Includes:
- Redis caching (48h TTL) — same query = instant response, no API cost
- RAG context injection — Claude answers from retrieved pgvector chunks
"""

import json
import uuid
import logging
from typing import AsyncGenerator, Optional, List

from app.config import settings
from app.services.cache import cache_service


async def _get_llm(temperature: float = 0.3):
    """Get the configured LLM instance."""
    if settings.LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=temperature,
            streaming=True,
        )
    else:
        from langchain_community.chat_models import ChatAnthropic

        return ChatAnthropic(
            model=settings.LLM_MODEL,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            temperature=temperature,
            streaming=True,
        )


# ---------------------------------------------------------------------------
# Patent Summary (auto-generated after PDF upload)
# ---------------------------------------------------------------------------

async def generate_patent_summary(full_text: str, firm_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    """
    Generate a structured patent summary from full text.
    Returns a dict with core_invention, claims_breakdown, weaknesses, etc.
    """
    llm = await _get_llm(temperature=0.2)

    prompt = f"""You are a senior patent attorney. Analyze this patent and produce a structured summary.

PATENT TEXT (truncated to key sections):
{full_text[:15000]}

Return your analysis in this EXACT JSON format:
{{
    "core_invention": "One paragraph describing the core inventive concept",
    "technical_field": "The technical field this patent covers",
    "independent_claims_count": <number>,
    "dependent_claims_count": <number>,
    "claims_breakdown": [
        {{
            "claim_number": 1,
            "type": "independent",
            "summary": "Brief summary of what this claim covers",
            "key_elements": ["element 1", "element 2"],
            "breadth": "broad|medium|narrow"
        }}
    ],
    "weaknesses": [
        {{
            "claim_number": 1,
            "issue": "Description of the weakness",
            "severity": "high|medium|low",
            "exploitation_angle": "How an opponent could attack this"
        }}
    ],
    "strongest_claim": {{
        "claim_number": 9,
        "reason": "Why this claim is the strongest"
    }},
    "prior_art_vulnerability": "high|medium|low",
    "overall_quality_score": 75
}}

Return ONLY valid JSON, no markdown formatting."""

    # 1. Try cache
    cached = await cache_service.get_llm_response(prompt)
    if cached:
        try:
            return json.loads(cached)
        except:
            pass

    # 2. Call API
    from langchain_core.messages import HumanMessage
    result = await llm.ainvoke([HumanMessage(content=prompt)])
    content = result.content
    
    # 3. Log cost & usage
    from app.services.usage import track_ai_generation_usage
    await track_ai_generation_usage(
        result=result,
        firm_id=firm_id,
        user_id=user_id,
        workflow_type="patent_summary"
    )

    # 4. Cache and return
    await cache_service.set_llm_response(prompt, content)
    
    try:
        # Try to parse JSON from response
        text = content.strip()
        # Remove markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        return {
            "core_invention": result.content[:500],
            "raw_analysis": result.content,
            "parse_error": True,
        }


# ---------------------------------------------------------------------------
# Patent Application Drafting (Streaming)
# ---------------------------------------------------------------------------

PATENT_DRAFT_SYSTEM_PROMPT = """You are an expert patent attorney assistant specializing in drafting
patent applications for the United States Patent and Trademark Office (USPTO).

Your drafts must follow the standard USPTO format:
1. Title of the Invention
2. Cross-Reference to Related Applications (if applicable)
3. Field of the Invention
4. Background of the Invention
5. Summary of the Invention
6. Brief Description of the Drawings
7. Detailed Description of the Preferred Embodiments
8. Claims (independent and dependent)
9. Abstract of the Disclosure

Guidelines:
- Use precise, technical language appropriate for patent prosecution
- Claims should be as broad as reasonably possible while being novel over prior art
- Independent claims should stand alone; dependent claims should add specific limitations
- Use proper antecedent basis throughout
- Include at least 3 independent claims and 10+ dependent claims
- The specification must enable a person skilled in the art to practice the invention
- LEGAL SAFETY: NEVER concede that any claim features are already known in the prior art or that the invention is obvious. Maintain a strategically novel and non-obvious stance throughout.
"""


async def generate_patent_draft_stream(
    invention_description: str,
    technical_field: str,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    prior_art_context: Optional[str] = None,
    claim_style: str = "apparatus",
    spec_context: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream a patent application draft."""
    llm = await _get_llm()

    context_sections = ""
    if prior_art_context:
        context_sections += f"\n\nKnown Prior Art:\n{prior_art_context}"
    if spec_context:
        context_sections += f"\n\nEngineering Specification:\n{spec_context}"

    prompt = f"""{PATENT_DRAFT_SYSTEM_PROMPT}

Technical Field: {technical_field}
Claim Style: {claim_style}

Invention Description:
{invention_description}
{context_sections}

Please draft a complete patent application following the USPTO format above."""

    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [
        SystemMessage(content=PATENT_DRAFT_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    # 1. Try cache
    cached = await cache_service.get_llm_response(prompt)
    if cached:
        yield f"data: {cached}\n\n"
        yield "data: [DONE]\n\n"
        return

    # 2. Stream and collect
    full_response = []
    async for chunk in llm.astream(messages):
        if hasattr(chunk, "content") and chunk.content:
            full_response.append(chunk.content)
            yield f"data: {chunk.content}\n\n"

    # 3. Cache the result
    if full_response:
        await cache_service.set_llm_response(prompt, "".join(full_response))

    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Office Action Response (Streaming + Structured)
# ---------------------------------------------------------------------------

OA_RESPONSE_SYSTEM_PROMPT = """You are an expert patent prosecution attorney assistant.
You are helping draft a response to a USPTO Office Action.

Your response must:
1. Respectfully address each rejection and objection raised by the Examiner
2. Present clear, persuasive legal arguments citing relevant MPEP sections
3. If amending claims, show the amendments clearly
4. Distinguish the claimed invention from cited prior art references
5. Address each claim individually when rejections differ
6. Maintain proper tone — professional, not adversarial
7. Include a conclusion requesting allowance of all pending claims

Format the response as a formal Office Action Response with:
- Caption/Header with application number and art unit
- Remarks section addressing each rejection
- Claim amendments (if applicable)
- Conclusion requesting allowance
- LEGAL SAFETY: NEVER concede infringement, acknowledge validity of prior art for the purpose of anticipation/obviousness, or make any admissions that could be used against the applicant in litigation. Focus exclusively on distinguishing the technical features and legal arguments for non-obviousness.
"""


async def generate_oa_response_stream(
    office_action_text: str,
    patent_title: str,
    patent_claims: List[dict],
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    response_strategy: str = "argue",
    additional_context: Optional[str] = None,
    prior_art_context: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream an office action response."""
    llm = await _get_llm()

    claims_text = "\n".join(
        [f"Claim {c.get('claim_number', c.get('number', '?'))}: {c.get('claim_text', c.get('text', ''))}"
         for c in patent_claims]
    ) if patent_claims else "Claims not loaded."

    context_str = ""
    if prior_art_context:
        context_str += f"\n\nKNOWN CITED PRIOR ART:\n{prior_art_context}"
    if additional_context:
        context_str += f"\n\nATTORNEY INSTRUCTIONS/CONTEXT:\n{additional_context}"

    prompt = f"""Patent Title: {patent_title}

Response Strategy: {response_strategy}

Current Claims:
{claims_text}

Office Action Text:
{office_action_text[:8000]}
{context_str}

Please draft a comprehensive, formal response to this Office Action. Include:
1. A professional header
2. Address EACH rejection specifically with legal arguments
3. If strategy is "amend" or "both", propose specific claim amendments
4. Cite relevant MPEP sections and case law
5. End with a conclusion requesting allowance"""

    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [
        SystemMessage(content=OA_RESPONSE_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    full_response = []
    async for chunk in llm.astream(messages):
        if hasattr(chunk, "content") and chunk.content:
            full_response.append(chunk.content)
            yield f"data: {chunk.content}\n\n"

    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Infringement / Risk Analysis (Structured Claim Chart)
# ---------------------------------------------------------------------------

async def generate_risk_analysis_stream(
    patent_title: str,
    claims: List[dict],
    prior_art: List[dict],
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    analysis_type: str = "invalidity",
    product_description: Optional[str] = None,
    target_claims: Optional[List[int]] = None,
    rag_context: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream a structured risk/infringement/invalidity analysis.
    Produces element-by-element claim charts.
    Uses RAG context from pgvector when available.
    """
    llm = await _get_llm()

    claims_text = "\n".join(
        [f"Claim {c.get('claim_number', c.get('number', '?'))} ({'Independent' if c.get('is_independent') else 'Dependent'}): {c.get('claim_text', c.get('text', ''))}"
         for c in claims]
    ) if claims else "No claims available."

    pa_text = "\n".join(
        [f"- {p.get('reference_number', p.get('number', 'N/A'))}: {p.get('reference_title', p.get('title', 'Untitled'))} — {p.get('reference_abstract', p.get('abstract', 'No abstract'))[:300]}"
         for p in prior_art]
    ) if prior_art else "No prior art references loaded."

    target = f"Focus on claims: {target_claims}" if target_claims else "Analyze all independent claims"

    if analysis_type == "infringement" and product_description:
        specific_prompt = f"""
PRODUCT UNDER ANALYSIS:
{product_description}

Generate an INFRINGEMENT ANALYSIS with:

1. **EXECUTIVE SUMMARY** — Overall infringement risk (HIGH/MEDIUM/LOW) with confidence percentage

2. **CLAIM CHART** — For each independent claim, map EVERY element against the product:

| Claim Element | Product Feature | Reads On? | Risk Level | Notes |
|---|---|---|---|---|
| [exact claim language] | [corresponding product feature or "NOT FOUND"] | Yes/No/Partial | High/Medium/Low | [explanation] |

3. **RISK SCORES** — Per-claim risk assessment:
- Claim X: XX% infringement risk — [one-line rationale]

4. **DESIGN-AROUND OPTIONS** — For high-risk claims, suggest specific modifications to avoid infringement

5. **RECOMMENDED ACTIONS** — Ranked by priority
"""
    elif analysis_type == "invalidity":
        specific_prompt = f"""
Generate an INVALIDITY ANALYSIS with:

1. **EXECUTIVE SUMMARY** — Overall invalidity strength (STRONG/MODERATE/WEAK) with confidence percentage

2. **CLAIM CHARTS** — For each independent claim, map elements against prior art:

| Claim Element | Prior Art Reference | Disclosure Location | Anticipates? |
|---|---|---|---|
| [exact claim language] | [reference number + title] | [column/line or paragraph] | §102/§103/Neither |

3. **INVALIDITY SCORES** — Per-claim assessment:
- Claim X: XX% likely invalid — [one-line rationale]

4. **BEST COMBINATIONS** — For §103 (obviousness), which references to combine and why

5. **GAPS** — Elements NOT found in prior art (potential strengths of the patent)
"""
    else:  # freedom-to-operate
        specific_prompt = f"""
Generate a FREEDOM TO OPERATE analysis with:

1. **EXECUTIVE SUMMARY** — Overall FTO risk assessment

2. **BLOCKING PATENTS** — Which claims could block operations, with risk levels

3. **CLAIM CHARTS** — Element mapping for blocking claims

4. **RISK MITIGATION** — Design-around options, licensing recommendations

5. **FTO SCORE** — Overall freedom to operate score (0-100)
"""

    # Include RAG-retrieved context if available
    rag_section = ""
    if rag_context:
        rag_section = f"\n\nRETRIEVED PATENT CONTEXT (from pgvector semantic search):\n{rag_context}\n\nIMPORTANT: Base your analysis on the retrieved context above. Cite specific passages with page numbers when available."

    prompt = f"""Patent: {patent_title}
Analysis Type: {analysis_type.upper()}
{target}

CLAIMS UNDER ANALYSIS:
{claims_text}

PRIOR ART REFERENCES:
{pa_text}
{rag_section}

{specific_prompt}

Be thorough and precise. Use proper legal terminology. Cite specific claim elements by quoting them."""

    from langchain_core.messages import HumanMessage, SystemMessage

    system = f"You are an expert patent litigator and invalidity analyst conducting a {analysis_type} analysis. Produce a structured, court-ready report. When retrieved patent context is provided, cite it with page numbers."

    # 1. Try cache
    cached = await cache_service.get_llm_response(prompt)
    if cached:
        yield f"data: {cached}\n\n"
        yield "data: [DONE]\n\n"
        return

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ]

    # Stream and accumulate for caching
    full_response = []
    async for chunk in llm.astream(messages):
        if hasattr(chunk, "content") and chunk.content:
            full_response.append(chunk.content)
            yield f"data: {chunk.content}\n\n"

    # 3. Cache the result
    if full_response:
        await cache_service.set_llm_response(prompt, "".join(full_response))
    
    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Prior Art Analysis (Streaming)
# ---------------------------------------------------------------------------

async def analyze_prior_art_stream(
    patent_title: str,
    patent_abstract: str,
    claims: List[dict],
    analysis_depth: str = "standard",
    include_npl: bool = False,
) -> AsyncGenerator[str, None]:
    """Stream prior art analysis."""
    llm = await _get_llm()

    claims_text = "\n".join(
        [f"Claim {c.get('claim_number', c.get('number', '?'))}: {c.get('claim_text', c.get('text', ''))}"
         for c in claims]
    ) if claims else "No claims available."

    prompt = f"""Analyze the following patent for prior art considerations:

Title: {patent_title}
Abstract: {patent_abstract}

Claims:
{claims_text}

Analysis Depth: {analysis_depth}
Include Non-Patent Literature: {include_npl}

Generate a STRUCTURED prior art analysis:

1. **KEY NOVEL FEATURES** — What makes this patent unique
2. **CLAIM ELEMENT BREAKDOWN** — Each independent claim broken into individual elements
3. **PRIOR ART SEARCH STRATEGY** — Recommended search queries and CPC codes
4. **VULNERABILITY ASSESSMENT** — Which claims are most vulnerable and why
5. **RECOMMENDED SEARCH DATABASES** — USPTO, EPO, WIPO, Google Patents, IEEE, etc.
"""

    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [
        SystemMessage(content="You are an expert patent analyst specializing in prior art analysis. Produce a thorough, actionable report."),
        HumanMessage(content=prompt),
    ]

    async for chunk in llm.astream(messages):
        if hasattr(chunk, "content") and chunk.content:
            yield f"data: {chunk.content}\n\n"

    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Due Diligence Report (Streaming + Structured)
# ---------------------------------------------------------------------------

async def generate_due_diligence_stream(
    patents: List[dict],
    licenses: List[dict] = None,
    context: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Generate a comprehensive due diligence report for a patent portfolio.
    """
    llm = await _get_llm()

    patent_summaries = []
    for p in patents:
        claims_info = f", {len(p.get('claims', []))} claims" if p.get("claims") else ""
        patent_summaries.append(
            f"• {p.get('patent_number', p.get('application_number', 'N/A'))} — \"{p.get('title', 'Untitled')}\" "
            f"[Status: {p.get('status', 'unknown')}, Filed: {p.get('filing_date', 'N/A')}, "
            f"Granted: {p.get('grant_date', 'N/A')}{claims_info}]"
            f"\n  Abstract: {(p.get('abstract', '') or 'No abstract')[:200]}"
        )

    license_info = ""
    if licenses:
        license_info = "\n\nLICENSED PATENTS:\n" + "\n".join(
            [f"• {l.get('patent_number', 'N/A')} from {l.get('licensor', 'Unknown')} — expires {l.get('end_date', 'N/A')}"
             for l in licenses]
        )

    context_info = f"\n\nADDITIONAL CONTEXT:\n{context}" if context else ""

    prompt = f"""Generate a comprehensive IP DUE DILIGENCE REPORT for this patent portfolio.

PORTFOLIO ({len(patents)} patents):
{chr(10).join(patent_summaries)}
{license_info}
{context_info}

FORMAT YOUR REPORT AS:

# IP DUE DILIGENCE REPORT

## EXECUTIVE SUMMARY
- Overall portfolio quality score (0-100)
- Total patents analyzed
- Key strengths and weaknesses
- Bottom-line recommendation

## PATENT-BY-PATENT ANALYSIS
For EACH patent:
### [Patent Number] — [Title]
- **Quality Score:** XX/100
- **Claim Strength:** Strong/Moderate/Weak — [rationale]
- **Prior Art Risk:** High/Medium/Low — [rationale]
- **Remaining Life:** XX years (expires YYYY)
- **Market Relevance:** [assessment]
- **Recommendation:** [Hold/Divest/License/Strengthen]

## PORTFOLIO RISKS
- List specific risks with severity ratings
- License dependencies and expiration concerns
- Coverage gaps

## PORTFOLIO STRENGTHS
- Core defensible positions
- Cross-licensing opportunities
- Competitive advantages

## VALUATION FACTORS
- Revenue potential
- Litigation defensibility
- Strategic value

## RECOMMENDATIONS
Numbered, actionable recommendations ranked by priority
"""

    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [
        SystemMessage(content="You are a senior IP attorney conducting due diligence for a potential acquisition. Produce a thorough, honest, and actionable report. Assign realistic scores — don't inflate."),
        HumanMessage(content=prompt),
    ]

    full_response = []
    async for chunk in llm.astream(messages):
        if hasattr(chunk, "content") and chunk.content:
            full_response.append(chunk.content)
            yield f"data: {chunk.content}\n\n"

    yield "data: [DONE]\n\n"
