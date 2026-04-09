"""
IP Patent Intelligence Platform — FastAPI Backend
Main application entry point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.routers import patents, portfolio, drafting, office_actions, prior_art, search, documents
from app.auth import get_current_user, get_dev_user


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown events."""
    yield
    await engine.dispose()


app = FastAPI(
    title="PatentIQ API",
    description="AI-powered patent prosecution and portfolio intelligence platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Next.js frontend
if settings.APP_ENV == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# DEV MODE: bypass Clerk auth with a fake user
if settings.APP_ENV == "development":
    app.dependency_overrides[get_current_user] = get_dev_user


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "patentiq-api", "version": "1.0.0", "env": settings.APP_ENV}


# Register routers
app.include_router(patents.router, prefix="/api/v1/patents", tags=["Patents"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["Portfolio"])
app.include_router(drafting.router, prefix="/api/v1/drafting", tags=["Patent Drafting"])
app.include_router(
    office_actions.router, prefix="/api/v1/office-actions", tags=["Office Actions"]
)
app.include_router(prior_art.router, prefix="/api/v1/prior-art", tags=["Prior Art & Analysis"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])

# Register Inngest endpoint
import inngest.fast_api
from app.services.inngest_client import inngest_client
from app.services.inngest_jobs import process_large_patent, process_oa_references, sync_uspto_statuses

inngest.fast_api.serve(
    app,
    inngest_client,
    [process_large_patent, process_oa_references, sync_uspto_statuses],
    serve_path="/api/inngest"
)
