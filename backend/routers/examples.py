"""Few-shot examples management endpoints."""

import re
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from config.settings import FS_LEARNING_INPUTS_DIR

router = APIRouter()


def _get_prefix(filename: str) -> str | None:
    match = re.match(r"^(\d+)\.?\s*", filename)
    return match.group(1) if match else None


def _get_examples() -> list[dict]:
    """Scan learning inputs and group by numeric prefix."""
    if not FS_LEARNING_INPUTS_DIR.exists():
        return []

    files_by_prefix: dict[str, list[dict]] = {}
    for f in sorted(FS_LEARNING_INPUTS_DIR.iterdir()):
        if not f.is_file():
            continue
        prefix = _get_prefix(f.name)
        if not prefix:
            continue
        if prefix not in files_by_prefix:
            files_by_prefix[prefix] = []
        files_by_prefix[prefix].append({
            "name": f.name,
            "size": f.stat().st_size,
            "type": f.suffix.lower(),
        })

    result = []
    for prefix, files in sorted(files_by_prefix.items()):
        # Extract display name from first file
        first = files[0]["name"]
        display = re.sub(r"^\d+\.?\s*", "", Path(first).stem)
        display = re.sub(r"[_.-]", " ", display).strip() or f"Example {prefix}"
        result.append({
            "prefix": prefix,
            "display_name": display,
            "files": files,
        })
    return result


@router.get("/")
async def list_examples():
    return _get_examples()


@router.get("/{prefix}/md-preview")
async def get_md_preview(prefix: str):
    """Get first 3000 chars of the markdown file for an example."""
    md_files = list(FS_LEARNING_INPUTS_DIR.glob(f"{prefix}*.md"))
    if not md_files:
        raise HTTPException(404, "No markdown file found for this example")
    content = md_files[0].read_text(encoding="utf-8")
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

    # Check for existing files with same prefix
    existing = list(FS_LEARNING_INPUTS_DIR.glob(f"{md_prefix}*"))
    if existing:
        raise HTTPException(400, f"Example with prefix {md_prefix} already exists")

    # Save files
    dest_dir = FS_LEARNING_INPUTS_DIR
    (dest_dir / md_file.filename).write_bytes(await md_file.read())
    (dest_dir / pdf_file.filename).write_bytes(await pdf_file.read())
    if xlsx_file and xlsx_file.filename:
        (dest_dir / xlsx_file.filename).write_bytes(await xlsx_file.read())

    return {"prefix": md_prefix}


@router.delete("/{prefix}")
async def delete_example(prefix: str):
    """Delete all files for an example prefix."""
    files = list(FS_LEARNING_INPUTS_DIR.glob(f"{prefix}*"))
    if not files:
        raise HTTPException(404, "No files found for this prefix")
    for f in files:
        f.unlink()
    return {"success": True, "deleted_count": len(files)}
