"""
Vercel serverless entry point for FastAPI.
This file maps the app instance to Vercel's runtime.
"""
import sys
import os
import traceback

# Vercel executes from the project root. 
# We add apps/api to the path so internal imports like 'from app.main' work.
project_root = os.getcwd()
api_root = os.path.join(project_root, "apps", "api")
sys.path.append(api_root)

try:
    # Now that apps/api is in the path, 'app.main' should be findable
    from app.main import app
except Exception as e:
    # Catch any remaining startup errors
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI()
    
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
    async def catch_all(path: str = None):
        return JSONResponse(
            status_code=500,
            content={
                "error": "FastAPI Startup Failure",
                "detail": str(e),
                "traceback": traceback.format_exc(),
                "sys_path": sys.path,
                "cwd": os.getcwd(),
                "api_root": api_root
            }
        )

# Vercel's Python runtime expects a module-level variable that is the application
# We already have it as 'app' in app.main
