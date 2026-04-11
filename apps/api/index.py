"""
ULTRA-MINIMAL DIAGNOSTIC ENTRY POINT
This file has zero internal imports to isolate build/deployment issues.
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import sys
import os

app = FastAPI()

@app.get("/api/v1/health")
async def health():
    return {
        "status": "ULTRA-MINIMAL-OK",
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "files_in_cwd": os.listdir(os.getcwd()) if os.path.exists(os.getcwd()) else [],
        "env": {k: "SET" for k in os.environ.keys() if "KEY" in k or "SECRET" in k or "URL" in k}
    }

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def catch_all(path: str = None):
    return JSONResponse(
        status_code=200,
        content={
            "msg": "Isolation test active. Hit /api/v1/health for details.",
            "requested_path": path
        }
    )
