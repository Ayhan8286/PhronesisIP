import uuid
import logging
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import UsageLog
from app.database import SessionLocal
from app.config import settings

logger = logging.getLogger(__name__)

# Standard Internal Pricing (USD per 1M tokens)
# Note: These can be moved to a remote config service for high-scale apps
PRICING = {
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 3.50, "output": 10.50},
    "claude-3-sonnet": {"input": 3.00, "output": 15.00},
    "voyage-law-2": {"input": 0.12, "output": 0.12}, # Symmetric for embeddings
}

async def log_usage(
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int = 0,
    workflow_type: str = "general",
) -> Optional[float]:
    """
    Log token usage and estimated USD cost to the database.
    Calculates cost based on the provider/model rates.
    """
    # Calculate costs
    model_rates = PRICING.get(model, {"input": 0, "output": 0})
    
    input_cost = (input_tokens / 1_000_000) * model_rates["input"]
    output_cost = (output_tokens / 1_000_000) * model_rates["output"]
    total_cost = input_cost + output_cost

    try:
        async with SessionLocal() as db:
            log = UsageLog(
                firm_id=firm_id,
                user_id=user_id,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=total_cost,
                workflow_type=workflow_type
            )
            db.add(log)
            await db.commit()
            
        logger.info(f"Usage logged for firm {firm_id}: {model} ({total_cost:.6f} USD)")
        return total_cost
    except Exception as e:
        logger.error(f"Failed to log usage: {e}")
        return None


async def track_ai_generation_usage(
    result: Any,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    workflow_type: str,
    provider: Optional[str] = None,
):
    """
    Helper to extract usage from a LangChain result and log it.
    Reduces boilerplate in AI services.
    """
    if not hasattr(result, "response_metadata"):
        return

    meta = result.response_metadata
    usage = meta.get("token_usage", {})
    
    if not usage:
        return

    # Extract tokens based on provider format (Gemini/Anthropic differ slightly)
    input_tokens = usage.get("prompt_token_count", usage.get("input_tokens", 0))
    output_tokens = usage.get("candidates_token_count", usage.get("output_tokens", 0))

    await log_usage(
        firm_id=firm_id,
        user_id=user_id,
        provider=provider or settings.LLM_PROVIDER,
        model=settings.LLM_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        workflow_type=workflow_type
    )
