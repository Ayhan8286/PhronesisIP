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
if api_root not in sys.path:
    sys.path.append(api_root)

# Vercel's Python builder COMPULSIVELY needs 'app' to be defined at the top level
# without being hidden inside try/except blocks in some environments.
app = None

try:
    # Now that apps/api is in the path, 'app.main' should be findable
    from app.main import app as main_app
    app = main_app
except Exception as e:
    # Fallback to a diagnostic app if the real one fails to load
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

# Ensure app is never None for the builder
if app is None:
    from fastapi import FastAPI
    app = FastAPI()
