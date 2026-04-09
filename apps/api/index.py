"""
Vercel serverless entry point for FastAPI.
This file maps the app instance to Vercel's runtime.
"""
from app.main import app

# Vercel's Python runtime expects a module-level variable that is the application
# We already have it as 'app' in app.main
