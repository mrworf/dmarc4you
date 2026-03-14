"""ASGI app: mount versioned API routes and static frontend."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.api.v1 import router as v1_router

app = FastAPI(title="DMARC Analyzer")
app.include_router(v1_router)

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
