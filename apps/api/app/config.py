"""
Application configuration loaded from environment variables.
"""

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings
from typing import List, Any, Optional
import json


class Settings(BaseSettings):
    """Application settings with sensible defaults for development."""

    # --- Application ---
    APP_ENV: str = "production"
    DEBUG: bool = False

    # --- Database (Neon PostgreSQL) ---
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/patentiq"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_database_url(cls, v: Any) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and "+asyncpg" not in v:
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    # --- Auth (Clerk) ---
    CLERK_SECRET_KEY: str = ""
    CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_JWKS_URL: str = ""
    CLERK_ISSUER: str = ""
    
    # --- Auth (Custom JWT replaces Clerk) ---
    JWT_SECRET: str = "super-secret-key-for-internal-tool"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week
    ADMIN_PASSWORD_HASH: str = "" # Set via env (bcrypt)
    STATIC_FIRM_ID: str = "a17772ca-86b5-4aa3-ae04-d7e8d7dc8ee7"
    STATIC_USER_ID: str = "00000000-0000-0000-0000-000000000001"

    # --- AI / Embeddings ---
    EMBEDDING_PROVIDER: str = "local"
    JINA_API_KEY: str = ""
    EMBEDDING_MODEL: str = "jina-embeddings-v3"
    LOCAL_EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_QUERY_PREFIX: str = "Represent this sentence for searching relevant passages: "
    EMBEDDING_DIM: int = 1024

    # --- LLM (xAI/Groq) ---
    XAI_API_KEY: str = ""
    XAI_BASE_URL: str = "https://api.x.ai/v1"
    GROQ_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    LLM_PROVIDER: str = "xai"
    LLM_MODEL: str = "grok-4.20-reasoning"

    # --- Storage (Cloudflare R2) ---
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "patentiq-docs"
    R2_ENDPOINT_URL: str = ""  # https://<account_id>.r2.cloudflarestorage.com
    R2_PUBLIC_URL: str = ""  # Custom domain or R2.dev URL

    # --- CORS ---
    CORS_ORIGINS: Any = []

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            # Fallback to comma-separated
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_env(self):
        if self.APP_ENV == "production":
            missing = [
                name
                for name in [
                    "DATABASE_URL",
                    "ADMIN_PASSWORD_HASH",
                ]
                if not getattr(self, name)
            ]
            if self.LLM_PROVIDER == "xai" and not self.XAI_API_KEY:
                missing.append("XAI_API_KEY")
            if self.LLM_PROVIDER == "groq" and not self.GROQ_API_KEY:
                missing.append("GROQ_API_KEY")
            if missing:
                raise ValueError(
                    "Missing required production environment variables: "
                    + ", ".join(missing)
                )
        return self

    # --- Background Jobs ---
    WORKER_CONCURRENCY: int = 4
    INNGEST_SIGNING_KEY: Optional[str] = None
    INNGEST_EVENT_KEY: Optional[str] = None

    # --- Redis Cache (Upstash / local) ---
    REDIS_URL: str = ""  # e.g. rediss://default:xxx@xxx.upstash.io:6379
    # --- Monitoring ---
    SENTRY_DSN: str = ""
    CACHE_TTL_HOURS: int = 48  # Cache AI responses for 48 hours

    # EPO
    EPO_CLIENT_ID: Optional[str] = None
    EPO_CLIENT_SECRET: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
