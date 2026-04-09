"""
Application configuration loaded from environment variables.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings with sensible defaults for development."""

    # --- Application ---
    APP_ENV: str = "development"
    DEBUG: bool = True

    # --- Database (Neon PostgreSQL) ---
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/patentiq"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    # --- Auth (Clerk) ---
    CLERK_SECRET_KEY: str = ""
    CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_JWKS_URL: str = "https://api.clerk.com/v1/jwks"
    CLERK_ISSUER: str = ""

    # --- AI / Embeddings ---
    VOYAGE_API_KEY: str = ""
    VOYAGE_MODEL: str = "voyage-law-2"
    VOYAGE_EMBEDDING_DIM: int = 1024

    # --- LLM ---
    GOOGLE_API_KEY: str = ""  # Gemini
    ANTHROPIC_API_KEY: str = ""  # Claude (production)
    LLM_PROVIDER: str = "gemini"  # "gemini" or "claude"
    LLM_MODEL: str = "gemini-2.5-flash"

    # --- Storage (Cloudflare R2) ---
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "patentiq-docs"
    R2_ENDPOINT_URL: str = ""  # https://<account_id>.r2.cloudflarestorage.com
    R2_PUBLIC_URL: str = ""  # Custom domain or R2.dev URL

    # --- CORS ---
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]

    # --- Background Jobs ---
    WORKER_CONCURRENCY: int = 4

    # --- Redis Cache (Upstash / local) ---
    REDIS_URL: str = ""  # e.g. rediss://default:xxx@xxx.upstash.io:6379
    CACHE_TTL_HOURS: int = 48  # Cache AI responses for 48 hours

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
