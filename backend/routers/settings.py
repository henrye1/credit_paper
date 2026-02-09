"""Settings endpoints — API keys, models, directories."""

from pathlib import Path

from fastapi import APIRouter

from config.settings import (
    GOOGLE_API_KEY, FIRECRAWL_API_KEY, MODELS,
    REPORT_INPUTS_DIR, FS_LEARNING_INPUTS_DIR, REPORT_OUTPUT_DIR,
    AUDIT_LLM_INPUT_DIR, AUDIT_LLM_OUTPUT_DIR, EVAL_INPUT_DIR,
    EVAL_OUTPUT_DIR, CONVERTED_REPORTS_DIR, ASSESSMENTS_DIR, PROJECT_ROOT,
)
from backend.schemas import ApiKeysRequest, DirectoryInfo

router = APIRouter()


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def _count_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for f in directory.iterdir() if f.is_file())


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
    """Update API keys in .env file."""
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
    dirs = [
        ("Report Inputs", REPORT_INPUTS_DIR),
        ("Learning Examples", FS_LEARNING_INPUTS_DIR),
        ("Report Output", REPORT_OUTPUT_DIR),
        ("Audit Input", AUDIT_LLM_INPUT_DIR),
        ("Audit Output", AUDIT_LLM_OUTPUT_DIR),
        ("Eval Input", EVAL_INPUT_DIR),
        ("Eval Output", EVAL_OUTPUT_DIR),
        ("Converted Reports", CONVERTED_REPORTS_DIR),
        ("Assessments", ASSESSMENTS_DIR),
    ]
    return [
        DirectoryInfo(label=label, path=str(d), file_count=_count_files(d))
        for label, d in dirs
    ]
