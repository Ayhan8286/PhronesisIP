"""
Vercel serverless entry point for FastAPI.
This file maps the app instance to Vercel's runtime.
"""
import sys
import os
import traceback

# Add the current directory to the path so 'app.main' is found
sys.path.append(os.path.dirname(__file__))

try:
    from app.main import app
except Exception as e:
    # If the app fails to import (due to missing dependencies or config errors),
    # catch it here and return the error message so we can diagnose it.
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI()
    
    # Catch all route for debugging
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
    async def catch_all(path: str = None):
        return JSONResponse(
            status_code=500,
            content={
                "error": "FastAPI Startup Failure",
                "detail": str(e),
                "traceback": traceback.format_exc(),
                "sys_path": sys.path,
                "cwd": os.getcwd()
            }
        )

# Vercel's Python runtime expects a module-level variable that is the application
# We already have it as 'app' in app.main
