"""Prompt management system with set-aware CRUD, versioning — backed by Supabase."""

import hashlib
import json
from datetime import datetime
from difflib import unified_diff

from config.settings import DEFAULT_PROMPT_SET, PROMPT_FILES
from backend.services.supabase_client import get_supabase


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_set(prompt_set: str | None) -> str:
    """Resolve None to the default set."""
    if prompt_set:
        return prompt_set
    sb = get_supabase()
    row = sb.table("prompt_sets").select("slug").eq("is_default", True).limit(1).execute()
    if row.data:
        return row.data[0]["slug"]
    return DEFAULT_PROMPT_SET


def _validate_set_exists(prompt_set: str) -> None:
    sb = get_supabase()
    row = sb.table("prompt_sets").select("slug").eq("slug", prompt_set).limit(1).execute()
    if not row.data:
        raise ValueError(f"Prompt set '{prompt_set}' not found")


# ──────────────────────────────────────────────────────────────────────────────
# Prompt set management
# ──────────────────────────────────────────────────────────────────────────────

def list_prompt_sets() -> list[dict]:
    """List all prompt sets with metadata."""
    sb = get_supabase()
    rows = sb.table("prompt_sets").select("*").order("created_at").execute()
    return [
        {
            "slug": r["slug"],
            "display_name": r["display_name"],
            "description": r.get("description", ""),
            "created_at": r.get("created_at"),
            "cloned_from": r.get("cloned_from"),
            "is_default": r.get("is_default", False),
        }
        for r in rows.data
    ]


def get_prompt_set_info(prompt_set: str) -> dict:
    """Return metadata for a single set."""
    sb = get_supabase()
    row = sb.table("prompt_sets").select("*").eq("slug", prompt_set).limit(1).execute()
    if not row.data:
        raise ValueError(f"Prompt set '{prompt_set}' not found")
    r = row.data[0]
    return {
        "slug": r["slug"],
        "display_name": r["display_name"],
        "description": r.get("description", ""),
        "created_at": r.get("created_at"),
        "cloned_from": r.get("cloned_from"),
        "is_default": r.get("is_default", False),
    }


def create_prompt_set(slug: str, display_name: str, description: str = "") -> dict:
    """Create a new prompt set with blank prompts."""
    sb = get_supabase()

    # Check if exists
    existing = sb.table("prompt_sets").select("slug").eq("slug", slug).limit(1).execute()
    if existing.data:
        raise ValueError(f"Prompt set '{slug}' already exists")

    entry = {
        "slug": slug,
        "display_name": display_name,
        "description": description,
        "is_default": False,
        "cloned_from": None,
    }
    sb.table("prompt_sets").insert(entry).execute()

    # Create blank prompts for each known prompt type
    for key in PROMPT_FILES:
        sb.table("prompts").insert({
            "prompt_set": slug,
            "prompt_name": key,
            "metadata": {"name": key, "description": ""},
            "sections": {},
        }).execute()

    return {"slug": slug, "display_name": display_name, "description": description,
            "is_default": False, "cloned_from": None}


def clone_prompt_set(source_set: str, new_slug: str, new_display_name: str,
                     new_description: str = "") -> dict:
    """Clone all current prompts from source into a new set."""
    sb = get_supabase()

    _validate_set_exists(source_set)

    existing = sb.table("prompt_sets").select("slug").eq("slug", new_slug).limit(1).execute()
    if existing.data:
        raise ValueError(f"Prompt set '{new_slug}' already exists")

    sb.table("prompt_sets").insert({
        "slug": new_slug,
        "display_name": new_display_name,
        "description": new_description,
        "is_default": False,
        "cloned_from": source_set,
    }).execute()

    # Copy prompts from source
    source_prompts = (sb.table("prompts")
                      .select("prompt_name, metadata, sections")
                      .eq("prompt_set", source_set)
                      .execute())
    for p in source_prompts.data:
        sb.table("prompts").insert({
            "prompt_set": new_slug,
            "prompt_name": p["prompt_name"],
            "metadata": p["metadata"],
            "sections": p["sections"],
        }).execute()

    return {"slug": new_slug, "display_name": new_display_name,
            "description": new_description, "is_default": False,
            "cloned_from": source_set}


def rename_prompt_set(prompt_set: str, new_display_name: str = None,
                      new_description: str = None) -> dict:
    """Update display name and/or description of a set."""
    _validate_set_exists(prompt_set)
    sb = get_supabase()
    updates = {}
    if new_display_name is not None:
        updates["display_name"] = new_display_name
    if new_description is not None:
        updates["description"] = new_description
    if updates:
        sb.table("prompt_sets").update(updates).eq("slug", prompt_set).execute()
    return get_prompt_set_info(prompt_set)


def delete_prompt_set(prompt_set: str) -> None:
    """Delete a prompt set. Cannot delete the default or only remaining set."""
    sb = get_supabase()
    info = get_prompt_set_info(prompt_set)
    if info.get("is_default"):
        raise ValueError("Cannot delete the default prompt set")

    all_sets = sb.table("prompt_sets").select("slug").execute()
    if len(all_sets.data) <= 1:
        raise ValueError("Cannot delete the only remaining prompt set")

    # CASCADE will handle prompts rows
    sb.table("prompt_sets").delete().eq("slug", prompt_set).execute()


def set_default_prompt_set(prompt_set: str) -> None:
    """Set a prompt set as the default."""
    _validate_set_exists(prompt_set)
    sb = get_supabase()
    # Clear existing default
    sb.table("prompt_sets").update({"is_default": False}).eq("is_default", True).execute()
    # Set new default
    sb.table("prompt_sets").update({"is_default": True}).eq("slug", prompt_set).execute()


def get_prompt_set_checksums(prompt_set: str = None) -> dict[str, str]:
    """Compute MD5 checksums for all prompts in a set."""
    prompt_set = _resolve_set(prompt_set)
    sb = get_supabase()
    rows = (sb.table("prompts")
            .select("prompt_name, sections")
            .eq("prompt_set", prompt_set)
            .execute())
    checksums = {}
    for r in rows.data:
        content = json.dumps(r["sections"], sort_keys=True).encode("utf-8")
        checksums[r["prompt_name"]] = hashlib.md5(content).hexdigest()
    return checksums


# ──────────────────────────────────────────────────────────────────────────────
# Prompt CRUD (set-aware)
# ──────────────────────────────────────────────────────────────────────────────

def load_prompt(prompt_name: str, prompt_set: str = None) -> dict:
    """Load a prompt from the specified (or default) set.

    Returns dict with 'metadata' and 'sections' keys (same shape as old YAML).
    """
    prompt_set = _resolve_set(prompt_set)
    sb = get_supabase()
    row = (sb.table("prompts")
           .select("metadata, sections")
           .eq("prompt_set", prompt_set)
           .eq("prompt_name", prompt_name)
           .limit(1)
           .execute())
    if not row.data:
        return {"metadata": {"name": prompt_name, "description": ""}, "sections": {}}
    r = row.data[0]
    return {
        "metadata": r.get("metadata") or {"name": prompt_name, "description": ""},
        "sections": r.get("sections") or {},
    }


def save_prompt(prompt_name: str, data: dict, prompt_set: str = None) -> str:
    """Save prompt data and create a timestamped version. Returns timestamp."""
    prompt_set = _resolve_set(prompt_set)
    sb = get_supabase()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    metadata = data.get("metadata", {"name": prompt_name, "description": ""})
    sections = data.get("sections", {})

    # Upsert current prompt
    sb.table("prompts").upsert({
        "prompt_set": prompt_set,
        "prompt_name": prompt_name,
        "metadata": metadata,
        "sections": sections,
        "updated_at": datetime.now().isoformat(),
    }, on_conflict="prompt_set,prompt_name").execute()

    # Insert history version
    sb.table("prompt_versions").insert({
        "prompt_set": prompt_set,
        "prompt_name": prompt_name,
        "timestamp": timestamp,
        "metadata": metadata,
        "sections": sections,
    }).execute()

    return timestamp


def get_version_history(prompt_name: str, prompt_set: str = None) -> list[dict]:
    """List all historical versions for a prompt, newest first."""
    prompt_set = _resolve_set(prompt_set)
    sb = get_supabase()
    rows = (sb.table("prompt_versions")
            .select("timestamp, created_at")
            .eq("prompt_set", prompt_set)
            .eq("prompt_name", prompt_name)
            .order("created_at", desc=True)
            .execute())

    versions = []
    for r in rows.data:
        ts = r["timestamp"]
        try:
            dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
            display_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            display_time = ts
        versions.append({
            "timestamp": ts,
            "display_time": display_time,
            "filename": f"{prompt_name}_{ts}.yaml",
        })
    return versions


def load_version(prompt_name: str, timestamp: str, prompt_set: str = None) -> dict:
    """Load a specific historical version of a prompt."""
    prompt_set = _resolve_set(prompt_set)
    sb = get_supabase()
    row = (sb.table("prompt_versions")
           .select("metadata, sections")
           .eq("prompt_set", prompt_set)
           .eq("prompt_name", prompt_name)
           .eq("timestamp", timestamp)
           .limit(1)
           .execute())
    if not row.data:
        return {}
    r = row.data[0]
    return {
        "metadata": r.get("metadata", {}),
        "sections": r.get("sections", {}),
    }


def revert_to_version(prompt_name: str, timestamp: str, prompt_set: str = None) -> str:
    """Restore a historical version as current. Creates new history entry."""
    prompt_set = _resolve_set(prompt_set)
    old_data = load_version(prompt_name, timestamp, prompt_set)
    if not old_data:
        raise ValueError(f"Version {timestamp} not found for prompt {prompt_name}")
    return save_prompt(prompt_name, old_data, prompt_set)


def diff_versions(prompt_name: str, ts1: str, ts2: str, prompt_set: str = None) -> dict:
    """Compare two versions section by section."""
    prompt_set = _resolve_set(prompt_set)
    v1 = load_version(prompt_name, ts1, prompt_set)
    v2 = load_version(prompt_name, ts2, prompt_set)

    s1 = v1.get("sections", {})
    s2 = v2.get("sections", {})
    all_keys = set(list(s1.keys()) + list(s2.keys()))
    diffs = {}

    for key in sorted(all_keys):
        sec1 = s1.get(key, {})
        sec2 = s2.get(key, {})
        content1 = sec1.get("content", "")
        content2 = sec2.get("content", "")

        if content1 == content2:
            diffs[key] = {"status": "unchanged", "diff": ""}
        elif key not in s1:
            diffs[key] = {"status": "added", "diff": content2}
        elif key not in s2:
            diffs[key] = {"status": "removed", "diff": content1}
        else:
            diff_lines = list(unified_diff(
                content1.splitlines(keepends=True),
                content2.splitlines(keepends=True),
                fromfile=f"v1 ({ts1})",
                tofile=f"v2 ({ts2})",
                lineterm=""
            ))
            diffs[key] = {"status": "changed", "diff": "\n".join(diff_lines)}

    return diffs


def assemble_prompt_text(prompt_name: str, prompt_set: str = None) -> str:
    """Concatenate all sections of a prompt into a single text block."""
    data = load_prompt(prompt_name, prompt_set)
    sections = data.get("sections", {})
    parts = []
    for key, section in sections.items():
        title = section.get("title", key)
        content = section.get("content", "")
        parts.append(f"**{title}**\n\n{content}")
    return "\n\n".join(parts)


def get_section_titles(prompt_name: str, prompt_set: str = None) -> list[tuple[str, str]]:
    """Return list of (section_key, section_title) pairs for a prompt."""
    data = load_prompt(prompt_name, prompt_set)
    sections = data.get("sections", {})
    return [(key, sec.get("title", key)) for key, sec in sections.items()]
