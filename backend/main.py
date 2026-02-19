"""FastAPI backend for the Credit Paper Assessment application."""

import os
import sys
from pathlib import Path

# Ensure project root is importable (for core/, config/, prompts/)
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.routers import assessment, prompts, prompt_sets, examples, settings, reports, pipeline

FRONTEND_DIR = PROJECT_ROOT / "frontend" / "dist"

app = FastAPI(title="Credit Paper Assessment", version="1.0.0")

# CORS: allow dev servers + production origin from ALLOWED_ORIGINS env var
_origins = ["*"]
_extra = os.getenv("ALLOWED_ORIGINS", "")
if _extra:
    _origins.extend([o.strip() for o in _extra.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# SPA fallback middleware: serve index.html for non-API 404s
class SPAFallbackMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        # If the API returns 404 and it's NOT an /api/ request, serve the SPA
        if (
            response.status_code == 404
            and request.method == "GET"
            and not request.url.path.startswith("/api/")
            and not request.url.path.startswith("/assets/")
        ):
            index = FRONTEND_DIR / "index.html"
            if index.exists():
                return FileResponse(index)
        return response


if FRONTEND_DIR.exists():
    app.add_middleware(SPAFallbackMiddleware)


# API routers
app.include_router(assessment.router, prefix="/api/assessment", tags=["assessment"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])
app.include_router(prompts.router, prefix="/api/prompts", tags=["prompts"])
app.include_router(prompt_sets.router, prefix="/api/prompt-sets", tags=["prompt-sets"])
app.include_router(examples.router, prefix="/api/examples", tags=["examples"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])

# Serve React static assets (JS, CSS, images)
if FRONTEND_DIR.exists() and (FRONTEND_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
