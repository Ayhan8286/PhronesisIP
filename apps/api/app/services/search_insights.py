import uuid
from typing import List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from app.services.llm import _get_llm

async def generate_search_insights(
    query: str,
    results: List[dict],
    firm_id: uuid.UUID,
    user_id: uuid.UUID
) -> str:
    """
    Generate a plain English explanation for why search results are relevant 
    to the attorney's query. Helps quickly identify threat level.
    """
    if not results:
        return "No relevant prior art found for this concept."

    llm = await _get_llm(temperature=0.2)
    
    # Format results for the LLM
    results_summary = ""
    for i, r in enumerate(results[:5]): # Only analyze top 5 for speed/cost
        results_summary += f"Result {i+1}: {r.get('title')} ({r.get('patent_number')})\n"
        results_summary += f"Snippet: {r.get('matched_text', r.get('abstract'))}\n\n"

    system_prompt = """You are a senior patent attorney assistant. 
Review the user's query and the top search results provided.
Explain in 2-3 concise paragraphs:
1. Which patent poses the highest threat to the novelty of the user's invention.
2. What specific claim features are covered vs. missing.
3. A strategic recommendation (e.g., 'Target claims towards feature X where prior art is weak').

Maintain a professional, objective tone. DO NOT hallucinate facts outside the provided snippets."""

    prompt = f"""ATTORNEY QUERY: {query}

TOP SEARCH RESULTS:
{results_summary}

Please provide the executive technical analysis:"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt)
    ]

    try:
        response = await llm.ainvoke(messages)
        return response.content
    except Exception as e:
        return f"Error generating insights: {str(e)}"
