"""Few-shot examples management endpoints — backed by Supabase."""

import re

from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.services.supabase_client import get_supabase
from backend.services.storage_helpers import upload_file, download_file, delete_files

router = APIRouter()


def _get_prefix(filename: str) -> str | None:
    match = re.match(r"^(\d+)\.?\s*", filename)
    return match.group(1) if match else None


def _get_examples() -> list[dict]:
    """Query examples + example_files tables and group by prefix."""
    sb = get_supabase()
    examples = sb.table("examples").select("prefix, display_name, created_at").order("prefix").execute()
    if not examples.data:
        return []

    result = []
    for ex in examples.data:
        files_result = (sb.table("example_files")
                        .select("filename, file_type, size_bytes")
                        .eq("prefix", ex["prefix"])
                        .execute())
        files = [
            {"name": f["filename"], "size": f.get("size_bytes", 0), "type": f.get("file_type", "")}
            for f in files_result.data
        ]
        result.append({
            "prefix": ex["prefix"],
            "display_name": ex["display_name"],
            "files": files,
        })
    return result


@router.get("/")
async def list_examples():
    return _get_examples()


@router.get("/{prefix}/md-preview")
async def get_md_preview(prefix: str):
    """Get first 3000 chars of the markdown file for an example."""
    sb = get_supabase()
    files = (sb.table("example_files")
             .select("storage_path, filename")
             .eq("prefix", prefix)
             .like("filename", "%.md")
             .limit(1)
             .execute())
    if not files.data:
        raise HTTPException(404, "No markdown file found for this example")

    data = download_file("examples", files.data[0]["storage_path"])
    content = data.decode("utf-8")
    return {"content": content[:3000]}


@router.post("/")
async def upload_example(
    md_file: UploadFile = File(...),
    pdf_file: UploadFile = File(...),
    xlsx_file: UploadFile = File(default=None),
):
    """Upload a new example pair (MD + PDF + optional XLSX)."""
    md_prefix = _get_prefix(md_file.filename)
    pdf_prefix = _get_prefix(pdf_file.filename)

    if not md_prefix or not pdf_prefix:
        raise HTTPException(400, "Files must start with a numeric prefix (e.g., '34. Company Name')")
    if md_prefix != pdf_prefix:
        raise HTTPException(400, f"Prefix mismatch: MD={md_prefix}, PDF={pdf_prefix}")

    sb = get_supabase()

    # Check for existing
    existing = sb.table("examples").select("prefix").eq("prefix", md_prefix).limit(1).execute()
    if existing.data:
        raise HTTPException(400, f"Example with prefix {md_prefix} already exists")

    # Determine display name
    display = re.sub(r"^\d+\.?\s*", "", md_file.filename.rsplit(".", 1)[0])
    display = re.sub(r"[_.-]", " ", display).strip() or f"Example {md_prefix}"

    # Insert example row
    sb.table("examples").insert({
        "prefix": md_prefix,
        "display_name": display,
    }).execute()

    # Upload files and insert file rows
    files_to_upload = [(md_file, md_file.filename)]
    files_to_upload.append((pdf_file, pdf_file.filename))
    if xlsx_file and xlsx_file.filename:
        files_to_upload.append((xlsx_file, xlsx_file.filename))

    for upload, filename in files_to_upload:
        content = await upload.read()
        storage_path = f"{md_prefix}/{filename}"
        upload_file("examples", storage_path, content)

        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        sb.table("example_files").insert({
            "prefix": md_prefix,
            "filename": filename,
            "file_type": f".{suffix}" if suffix else "",
            "size_bytes": len(content),
            "storage_path": storage_path,
        }).execute()

    return {"prefix": md_prefix}


@router.delete("/{prefix}")
async def delete_example(prefix: str):
    """Delete all files for an example prefix."""
    sb = get_supabase()

    # Get storage paths to delete
    files = sb.table("example_files").select("storage_path").eq("prefix", prefix).execute()
    if not files.data:
        raise HTTPException(404, "No files found for this prefix")

    paths = [f["storage_path"] for f in files.data]
    delete_files("examples", paths)

    # CASCADE deletes example_files rows
    sb.table("examples").delete().eq("prefix", prefix).execute()

    return {"success": True, "deleted_count": len(paths)}
