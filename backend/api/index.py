"""
Vercel Serverless Function Handler for FastAPI
"""
from app.main import app

# Vercel expects a handler function
handler = app
