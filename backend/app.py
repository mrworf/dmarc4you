"""ASGI app: serve versioned API routes for DMARCWatch."""

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from backend.api.errors import http_exception_handler, validation_exception_handler
from backend.api.v1 import router as v1_router
from backend.config import load_config

app = FastAPI(title="DMARCWatch")
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

_config = load_config()
app.state.config = _config
if _config.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(_config.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(v1_router)
