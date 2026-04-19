"""
Authentication middleware: verifies local JWTs and extracts user context.
"""

import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Union

from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Header
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate a hash for a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a new JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


@dataclass
class CurrentUser:
    """Authenticated user context."""
    id: uuid.UUID
    email: str
    role: str
    is_system_admin: bool = False
    firm_id: Optional[uuid.UUID] = None


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    authorization: Optional[str] = Header(None),
) -> CurrentUser:
    """
    FastAPI dependency: extracts and validates the local JWT.
    Supports both Authorization header and OAuth2 form token.
    """
    # 1. Handle fallback from header if OAuth2 scheme didn't pick it up
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        # Decode and verify the JWT
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        user_id_str = payload.get("sub")
        email = payload.get("email")
        role = payload.get("role", "attorney")
        firm_id_str = payload.get("firm_id")
        is_admin = payload.get("is_admin", False)

        if user_id_str is None:
            raise HTTPException(status_code=401, detail="Invalid token: missing sub")

        return CurrentUser(
            id=uuid.UUID(user_id_str),
            email=email or "admin@phronesis.ip",
            role=role,
            is_system_admin=is_admin,
            firm_id=uuid.UUID(firm_id_str) if firm_id_str else None
        )

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Authentication failed")


async def get_active_firm_user(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Strict dependency for routes that REQUIRE a firm context."""
    if not user.firm_id:
        # For this internal tool, we default to the static internal firm
        user.firm_id = uuid.UUID(settings.STATIC_FIRM_ID)
    return user


async def get_system_admin(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Strict dependency for routes that REQUIRE administrative rights."""
    if not user.is_system_admin:
        raise HTTPException(status_code=403, detail="Forbidden: Administrative access required")
    return user


def get_dev_user() -> CurrentUser:
    """Returns the static admin user for development."""
    return CurrentUser(
        id=uuid.UUID(settings.STATIC_USER_ID),
        email="admin@phronesis.ip",
        role="admin",
        is_system_admin=True,
        firm_id=uuid.UUID(settings.STATIC_FIRM_ID),
    )
