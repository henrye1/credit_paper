"""Helpers for Supabase Storage: upload, download, delete, temp file contexts."""

import tempfile
from contextlib import contextmanager
from pathlib import Path

from backend.services.supabase_client import get_supabase


def upload_file(bucket: str, storage_path: str, data: bytes,
                content_type: str = "application/octet-stream") -> str:
    """Upload bytes to a Supabase Storage bucket. Returns the storage_path."""
    sb = get_supabase()
    sb.storage.from_(bucket).upload(
        path=storage_path,
        file=data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return storage_path


def download_file(bucket: str, storage_path: str) -> bytes:
    """Download a file from Supabase Storage, returning raw bytes."""
    sb = get_supabase()
    return sb.storage.from_(bucket).download(storage_path)


def delete_file(bucket: str, storage_path: str) -> None:
    """Delete a single file from a Supabase Storage bucket."""
    sb = get_supabase()
    sb.storage.from_(bucket).remove([storage_path])


def delete_files(bucket: str, storage_paths: list[str]) -> None:
    """Delete multiple files from a Supabase Storage bucket."""
    if not storage_paths:
        return
    sb = get_supabase()
    sb.storage.from_(bucket).remove(storage_paths)


def list_files(bucket: str, folder: str) -> list[dict]:
    """List files in a storage folder."""
    sb = get_supabase()
    return sb.storage.from_(bucket).list(folder)


@contextmanager
def temp_file_from_storage(bucket: str, storage_path: str, suffix: str = ""):
    """Download a file from storage into a temp file; clean up on exit.

    Usage:
        with temp_file_from_storage("examples", "1/file.md", suffix=".md") as path:
            content = path.read_text()
    """
    data = download_file(bucket, storage_path)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(data)
        tmp.flush()
        tmp.close()
        yield Path(tmp.name)
    finally:
        Path(tmp.name).unlink(missing_ok=True)


@contextmanager
def temp_dir():
    """Provide a temporary directory that is cleaned up on exit.

    Usage:
        with temp_dir() as td:
            (td / "file.txt").write_text("hello")
    """
    import shutil
    d = Path(tempfile.mkdtemp())
    try:
        yield d
    finally:
        shutil.rmtree(str(d), ignore_errors=True)
