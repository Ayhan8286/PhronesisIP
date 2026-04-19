"""
Auth router for the internal tool.
Provides a simple password-based login that returns a long-lived JWT.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional
import uuid

from app.auth import verify_password, create_access_token
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    firm_id: str


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible login. Verifies the password against ADMIN_PASSWORD_HASH.
    Returns a JWT if successful.
    """
    if not settings.ADMIN_PASSWORD_HASH:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: ADMIN_PASSWORD_HASH not set."
        )

    if not verify_password(form_data.password, settings.ADMIN_PASSWORD_HASH):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Use static IDs for the internal tool
    user_id = settings.STATIC_USER_ID
    firm_id = settings.STATIC_FIRM_ID

    access_token = create_access_token(
        data={
            "sub": user_id,
            "email": "admin@phronesis.ip",
            "role": "admin",
            "is_admin": True,
            "firm_id": firm_id
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user_id,
        "firm_id": firm_id
    }


@router.post("/login-json", response_model=TokenResponse)
async def login_json(request: LoginRequest):
    """
    JSON-based login for easy frontend integration.
    """
    if not settings.ADMIN_PASSWORD_HASH:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: ADMIN_PASSWORD_HASH not set."
        )

    if not verify_password(request.password, settings.ADMIN_PASSWORD_HASH):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )

    user_id = settings.STATIC_USER_ID
    firm_id = settings.STATIC_FIRM_ID

    access_token = create_access_token(
        data={
            "sub": user_id,
            "email": "admin@phronesis.ip",
            "role": "admin",
            "is_admin": True,
            "firm_id": firm_id
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user_id,
        "firm_id": firm_id
    }
