"""Report browsing and download endpoints."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config.settings import REPORT_OUTPUT_DIR

router = APIRouter()


@router.get("/")
async def list_reports():
    """List all generated reports."""
    if not REPORT_OUTPUT_DIR.exists():
        return []
    reports = sorted(
        REPORT_OUTPUT_DIR.glob("*.html"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [
        {
            "name": r.name,
            "size": r.stat().st_size,
            "modified": r.stat().st_mtime,
        }
        for r in reports
    ]


@router.get("/{filename}/preview")
async def preview_report(filename: str):
    """Get HTML content of a report for preview."""
    path = REPORT_OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Report not found")
    content = path.read_text(encoding="utf-8")
    return {"html": content}


@router.get("/{filename}/download")
async def download_report(filename: str):
    """Download a report file."""
    path = REPORT_OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Report not found")
    return FileResponse(path, filename=filename, media_type="text/html")
