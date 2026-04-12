from fastapi import APIRouter, Depends
from app.auth import get_active_firm_user, CurrentUser

router = APIRouter()

@router.get("/session")
async def get_session_status(user: CurrentUser = Depends(get_active_firm_user)):
    """
    Basic health check for the authenticated session.
    """
    return {
        "user_id": str(user.id),
        "firm_id": str(user.firm_id),
        "role": user.role,
        "status": "authenticated"
    }
