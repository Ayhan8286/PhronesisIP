"""
IP Patent Intelligence Platform — FastAPI Backend
Main application entry point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.routers import (
    patents, portfolio, drafting, office_actions, 
    prior_art, search, documents, diagnostic
)
from app.auth import get_current_user, get_dev_user

import sentry_sdk

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        traces_sample_rate=1.0 if settings.APP_ENV == "development" else 0.1,
    )


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


from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# --- Exception Handling for Debugging ---

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    # Do not catch Starlette/FastAPI HTTPExceptions (let them pass through)
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        raise exc

    import logging
    import traceback
    error_msg = str(exc)
    error_type = type(exc).__name__
    
    # In production, log the exception for diagnostics
    if settings.APP_ENV != "development":
        logging.error("Unhandled exception in FastAPI", exc_info=exc)

    # In development, print full traceback
    if settings.APP_ENV == "development":
        traceback.print_exc()

    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Internal Server Error: {error_msg}",
            "type": error_type,
            "msg": "Check your Vercel Environment Variables or DB connection.",
            "path": request.url.path
        },
    )

@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy", "service": "patentiq-api", "version": "1.0.1", "env": settings.APP_ENV}


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

if settings.APP_ENV == "development":
    app.include_router(diagnostic.router, prefix="/api/v1/diagnostic", tags=["Diagnostic"])

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
