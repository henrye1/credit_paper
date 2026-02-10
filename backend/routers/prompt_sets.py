"""Prompt set management endpoints — CRUD for named prompt collections."""

from fastapi import APIRouter, HTTPException

from prompts.prompt_manager import (
    list_prompt_sets, get_prompt_set_info,
    create_prompt_set, clone_prompt_set, delete_prompt_set,
    rename_prompt_set, set_default_prompt_set,
)
from backend.schemas import (
    PromptSetInfo, PromptSetCreateRequest, PromptSetCloneRequest,
    PromptSetUpdateRequest, SetDefaultRequest,
)

router = APIRouter()


@router.get("/", response_model=list[PromptSetInfo])
async def list_sets():
    """List all prompt sets."""
    return list_prompt_sets()


@router.post("/", response_model=PromptSetInfo)
async def create_set(body: PromptSetCreateRequest):
    """Create a new empty prompt set."""
    try:
        result = create_prompt_set(body.slug, body.display_name, body.description)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/default")
async def set_default(body: SetDefaultRequest):
    """Set which prompt set is the default."""
    try:
        set_default_prompt_set(body.slug)
        return {"success": True, "default_set": body.slug}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{slug}", response_model=PromptSetInfo)
async def get_set(slug: str):
    """Get info for a single prompt set."""
    try:
        return get_prompt_set_info(slug)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.put("/{slug}", response_model=PromptSetInfo)
async def update_set(slug: str, body: PromptSetUpdateRequest):
    """Update display name and/or description."""
    try:
        result = rename_prompt_set(slug, body.display_name, body.description)
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/{slug}")
async def delete_set(slug: str):
    """Delete a prompt set."""
    try:
        delete_prompt_set(slug)
        return {"success": True}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{slug}/clone", response_model=PromptSetInfo)
async def clone_set(slug: str, body: PromptSetCloneRequest):
    """Clone an existing prompt set into a new one."""
    try:
        result = clone_prompt_set(slug, body.new_slug, body.new_display_name, body.new_description)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
