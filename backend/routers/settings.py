"""Settings endpoints — API keys, models, storage info."""

from fastapi import APIRouter

from config.settings import GOOGLE_API_KEY, FIRECRAWL_API_KEY, MODELS, PROJECT_ROOT
from backend.schemas import ApiKeysRequest, DirectoryInfo
from backend.services.supabase_client import get_supabase

router = APIRouter()


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


@router.get("/keys")
async def get_api_keys():
    return {
        "google_api_key": _mask_key(GOOGLE_API_KEY),
        "google_configured": bool(GOOGLE_API_KEY),
        "firecrawl_api_key": _mask_key(FIRECRAWL_API_KEY),
        "firecrawl_configured": bool(FIRECRAWL_API_KEY),
    }


@router.put("/keys")
async def update_api_keys(body: ApiKeysRequest):
    """Update API keys in .env file.

    Note: On Railway, env vars should be set via the dashboard instead.
    """
    env_path = PROJECT_ROOT / ".env"

    # Read existing .env
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    def update_line(lines: list[str], key: str, value: str) -> list[str]:
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}")
        return lines

    if body.google_api_key is not None:
        lines = update_line(lines, "GOOGLE_API_KEY", body.google_api_key)
    if body.firecrawl_api_key is not None:
        lines = update_line(lines, "FIRECRAWL_API_KEY", body.firecrawl_api_key)

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"success": True, "message": "API keys updated. Restart the server for changes to take effect."}


@router.get("/models")
async def get_models():
    return MODELS


@router.get("/directories")
async def get_directories() -> list[DirectoryInfo]:
    """Return counts of stored items from Supabase instead of local dirs."""
    sb = get_supabase()

    # Count reports by type
    type_counts = {}
    try:
        rows = sb.table("reports").select("report_type").execute()
        for r in rows.data:
            rt = r.get("report_type", "generated")
            type_counts[rt] = type_counts.get(rt, 0) + 1
    except Exception:
        pass

    # Count examples
    example_count = 0
    try:
        rows = sb.table("example_files").select("id").execute()
        example_count = len(rows.data)
    except Exception:
        pass

    # Count assessments
    assessment_count = 0
    try:
        rows = sb.table("assessments").select("id").execute()
        assessment_count = len(rows.data)
    except Exception:
        pass

    return [
        DirectoryInfo(label="Generated Reports", path="reports/generated", file_count=type_counts.get("generated", 0)),
        DirectoryInfo(label="Learning Examples", path="examples/", file_count=example_count),
        DirectoryInfo(label="Audit Output", path="reports/audit_output", file_count=type_counts.get("audit", 0)),
        DirectoryInfo(label="Comparison Output", path="reports/eval_output", file_count=type_counts.get("comparison", 0)),
        DirectoryInfo(label="Converted Reports", path="reports/converted", file_count=type_counts.get("converted", 0)),
        DirectoryInfo(label="Assessments", path="assessments", file_count=assessment_count),
    ]
