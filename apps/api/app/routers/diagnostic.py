
import os
import uuid
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.auth import get_current_user, CurrentUser

router = APIRouter()

@router.get("/check")
async def diagnostic_check(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Performs a system-wide diagnostic check.
    Returns masked environment info and DB connectivity status.
    Requires authentication to prevent public info leak.
    """
    results = {
        "status": "checking",
        "user_context": {
            "firm_id": str(user.firm_id),
            "role": user.role,
        },
        "environment": {
            "APP_ENV": settings.APP_ENV,
            "DEBUG": settings.DEBUG,
            "CLERK_JWKS_URL_SET": bool(settings.CLERK_JWKS_URL),
            "CLERK_ISSUER_SET": bool(settings.CLERK_ISSUER),
            "CLERK_SECRET_SET": bool(settings.CLERK_SECRET_KEY),
            "DATABASE_URL_SET": bool(settings.DATABASE_URL),
            "GOOGLE_API_KEY_SET": bool(settings.GOOGLE_API_KEY),
        },
        "database": {
            "ping": "failed",
            "rls_check": "failed",
        }
    }

    try:
        # 1. Ping database
        await db.execute(text("SELECT 1"))
        results["database"]["ping"] = "ok"

        # 2. Check RLS context
        # Try to read the setting. With our fix in 003_safe_rls.sql, 
        # this should return NULL instead of crashing if missing.
        rls_result = await db.execute(text("SELECT current_setting('app.current_firm_id', true)"))
        val = rls_result.scalar()
        results["database"]["rls_check"] = f"ok (current_val: {val})"
        
        results["status"] = "ok"
    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)

    return results
