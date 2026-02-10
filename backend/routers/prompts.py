"""Prompt management endpoints — wraps prompts/prompt_manager.py."""

from fastapi import APIRouter, HTTPException, Query

from config.settings import PROMPT_FILES
from prompts.prompt_manager import (
    load_prompt, save_prompt, get_version_history,
    load_version, revert_to_version, diff_versions, assemble_prompt_text,
)
from backend.schemas import PromptListItem, PromptSaveRequest, VersionListItem

router = APIRouter()

# Human-readable labels for prompt types
_LABELS = {
    "fin_condition_assessment_synthesis": "Financial Condition Assessment Synthesis",
    "financial_health_diagnostics": "Financial Health Diagnostics",
    "report_instructions": "Report Instructions",
    "audit_criteria": "Audit Criteria",
}


@router.get("/")
async def list_prompts(set: str = Query(None, alias="set")) -> list[PromptListItem]:
    """List all available prompt types."""
    result = []
    for key in PROMPT_FILES:
        data = load_prompt(key, prompt_set=set)
        section_count = len(data.get("sections", {})) if data else 0
        result.append(PromptListItem(
            name=key,
            label=_LABELS.get(key, key),
            section_count=section_count,
        ))
    return result


@router.get("/{name}")
async def get_prompt(name: str, set: str = Query(None, alias="set")):
    """Get a prompt's full data (metadata + sections)."""
    if name not in PROMPT_FILES:
        raise HTTPException(404, f"Prompt '{name}' not found")
    data = load_prompt(name, prompt_set=set)
    if not data:
        raise HTTPException(404, f"Could not load prompt '{name}'")
    return data


@router.put("/{name}")
async def update_prompt(name: str, body: PromptSaveRequest, set: str = Query(None, alias="set")):
    """Save updated sections (auto-creates version)."""
    if name not in PROMPT_FILES:
        raise HTTPException(404, f"Prompt '{name}' not found")

    current = load_prompt(name, prompt_set=set)
    if not current:
        raise HTTPException(404, f"Could not load prompt '{name}'")

    # Update sections
    for key, section in body.sections.items():
        if key in current.get("sections", {}):
            current["sections"][key]["title"] = section.title
            current["sections"][key]["description"] = section.description
            current["sections"][key]["content"] = section.content

    timestamp = save_prompt(name, current, prompt_set=set)
    return {"timestamp": timestamp}


@router.get("/{name}/preview")
async def get_prompt_preview(name: str, set: str = Query(None, alias="set")):
    """Get assembled prompt text."""
    if name not in PROMPT_FILES:
        raise HTTPException(404, f"Prompt '{name}' not found")
    text = assemble_prompt_text(name, prompt_set=set)
    return {"assembled_text": text}


@router.get("/{name}/versions")
async def get_versions(name: str, set: str = Query(None, alias="set")) -> list[VersionListItem]:
    """List all versions of a prompt."""
    if name not in PROMPT_FILES:
        raise HTTPException(404, f"Prompt '{name}' not found")
    versions = get_version_history(name, prompt_set=set)
    return [
        VersionListItem(
            timestamp=v["timestamp"],
            display_time=v.get("display_time", v["timestamp"]),
        )
        for v in versions
    ]


@router.get("/{name}/versions/{timestamp}")
async def get_version(name: str, timestamp: str, set: str = Query(None, alias="set")):
    """Get a specific version of a prompt."""
    if name not in PROMPT_FILES:
        raise HTTPException(404, f"Prompt '{name}' not found")
    data = load_version(name, timestamp, prompt_set=set)
    if not data:
        raise HTTPException(404, f"Version '{timestamp}' not found")
    return data


@router.post("/{name}/revert/{timestamp}")
async def revert_prompt(name: str, timestamp: str, set: str = Query(None, alias="set")):
    """Revert a prompt to a specific version."""
    if name not in PROMPT_FILES:
        raise HTTPException(404, f"Prompt '{name}' not found")
    new_ts = revert_to_version(name, timestamp, prompt_set=set)
    return {"new_timestamp": new_ts}


@router.get("/{name}/diff")
async def get_diff(name: str, ts1: str, ts2: str, set: str = Query(None, alias="set")):
    """Get a side-by-side diff between two versions."""
    if name not in PROMPT_FILES:
        raise HTTPException(404, f"Prompt '{name}' not found")
    result = diff_versions(name, ts1, ts2, prompt_set=set)
    return result
