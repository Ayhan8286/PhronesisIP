import functools
import uuid
import logging
from typing import Optional
from fastapi import Request
from app.database import SessionLocal
from app.models import AuditLog

logger = logging.getLogger(__name__)

def audit_log(action: str, target_type: Optional[str] = None):
    """
    Decorator to log high-sensitivity actions to the AuditLog table.
    Expects the decorated function to have 'user' (CurrentUser) and optionally 'patent_id' or 'id'.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Execute the function first
            response = await func(*args, **kwargs)
            
            # Extract context for logging
            user = kwargs.get("user")
            request: Optional[Request] = kwargs.get("request")
            target_id = kwargs.get("patent_id") or kwargs.get("id") or kwargs.get("office_action_id")
            
            if user:
                try:
                    async with SessionLocal() as db:
                        log = AuditLog(
                            firm_id=user.firm_id,
                            user_id=user.id,
                            action=action,
                            target_type=target_type,
                            target_id=uuid.UUID(str(target_id)) if target_id else None,
                            ip_address=request.client.host if request and request.client else None,
                            details={"status": "success"}
                        )
                        db.add(log)
                        await db.commit()
                except Exception as e:
                    logger.error(f"Failed to write audit log: {e}")
            
            return response
        return wrapper
    return decorator
