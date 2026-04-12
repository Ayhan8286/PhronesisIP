"""
Authentication middleware: verifies Clerk JWTs and extracts user context.
"""

import uuid
from dataclasses import dataclass
from typing import Optional

import jwt
import httpx
from fastapi import Depends, HTTPException, Header
from jwt import PyJWKClient

from app.config import settings


# Cache the JWKS client
_jwks_client: Optional[PyJWKClient] = None


def get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.CLERK_JWKS_URL)
    return _jwks_client


@dataclass
class CurrentUser:
    """Authenticated user context extracted from Clerk JWT."""
    id: uuid.UUID
    clerk_user_id: str
    firm_id: uuid.UUID
    clerk_org_id: str
    email: str
    role: str


async def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
) -> CurrentUser:
    """
    FastAPI dependency: extracts and validates Clerk JWT.
    Returns a CurrentUser with firm context for RLS.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        # Get the signing key from Clerk's JWKS endpoint
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode and verify the JWT
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.CLERK_ISSUER if settings.CLERK_ISSUER else None,
            options={
                "verify_iss": bool(settings.CLERK_ISSUER),
                "verify_aud": False,  # Clerk doesn't set audience by default
            },
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        # Catch JWKS fetch failures, network errors, etc.
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

    # Extract user info from claims
    clerk_user_id = payload.get("sub")
    clerk_org_id = payload.get("org_id")
    org_role = payload.get("org_role", "org:member")
    email = payload.get("email", "")

    # DIAGNOSTIC: Log the payload to see what's actually coming from Clerk
    print(f"DEBUG: Auth Payload - User: {clerk_user_id}, Org: {clerk_org_id}, Email: {email}")

    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Missing user ID in token")

    if not clerk_org_id:
        raise HTTPException(
            status_code=403,
            detail="No organization selected. Please select a firm.",
        )

    # Map Clerk org role to our roles
    role_map = {
        "org:admin": "admin",
        "org:member": "attorney",
        "org:viewer": "paralegal",
    }
    role = role_map.get(org_role, "attorney")

    # In production, lookup the user and firm IDs from the database
    # For now, use deterministic UUIDs derived from Clerk IDs
    user_id = uuid.uuid5(uuid.NAMESPACE_URL, f"user:{clerk_user_id}")
    firm_id = uuid.uuid5(uuid.NAMESPACE_URL, f"firm:{clerk_org_id}")

    return CurrentUser(
        id=user_id,
        clerk_user_id=clerk_user_id,
        firm_id=firm_id,
        clerk_org_id=clerk_org_id,
        email=email,
        role=role,
    )


# Development bypass for testing without Clerk
class DevUser(CurrentUser):
    """A test user for development without Clerk."""
    pass


def get_dev_user() -> CurrentUser:
    """Returns a fake user for development."""
    return CurrentUser(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        clerk_user_id="dev_user",
        firm_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        clerk_org_id="org_dev",
        email="dev@patentiq.com",
        role="admin",
    )
