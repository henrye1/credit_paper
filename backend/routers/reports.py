"""Report browsing and download endpoints — backed by Supabase."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.services.supabase_client import get_supabase
from backend.services.storage_helpers import download_file

router = APIRouter()


@router.get("/")
async def list_reports():
    """List all reports from the database."""
    sb = get_supabase()
    rows = (sb.table("reports")
            .select("filename, company_name, size_bytes, report_type, created_at")
            .order("created_at", desc=True)
            .execute())
    return [
        {
            "name": r["filename"],
            "size": r.get("size_bytes", 0),
            "report_type": r.get("report_type", "generated"),
            "company_name": r.get("company_name"),
            "created_at": r.get("created_at"),
        }
        for r in rows.data
    ]


@router.get("/{filename}/preview")
async def preview_report(filename: str):
    """Get HTML content of a report for preview."""
    sb = get_supabase()
    row = sb.table("reports").select("storage_path").eq("filename", filename).limit(1).execute()
    if not row.data:
        raise HTTPException(404, "Report not found")

    data = download_file("reports", row.data[0]["storage_path"])
    html = data.decode("utf-8")
    return {"html": html}


@router.get("/{filename}/download")
async def download_report(filename: str):
    """Download a report file."""
    sb = get_supabase()
    row = sb.table("reports").select("storage_path").eq("filename", filename).limit(1).execute()
    if not row.data:
        raise HTTPException(404, "Report not found")

    data = download_file("reports", row.data[0]["storage_path"])
    return Response(
        content=data,
        media_type="text/html",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
