"""Prompt management system with set-aware CRUD, versioning, and migration."""

import hashlib
import json
import shutil
import yaml
from pathlib import Path
from datetime import datetime
from difflib import unified_diff

from config.settings import (
    PROMPT_SETS_DIR, PROMPT_REGISTRY_FILE, DEFAULT_PROMPT_SET,
    PROMPTS_CURRENT_DIR, PROMPTS_HISTORY_DIR, PROMPT_FILES,
)


# ──────────────────────────────────────────────────────────────────────────────
# Registry helpers
# ──────────────────────────────────────────────────────────────────────────────

def _load_registry() -> dict:
    if PROMPT_REGISTRY_FILE.exists():
        return json.loads(PROMPT_REGISTRY_FILE.read_text(encoding="utf-8"))
    return {"sets": {}, "default_set": DEFAULT_PROMPT_SET}


def _save_registry(registry: dict) -> None:
    PROMPT_REGISTRY_FILE.write_text(
        json.dumps(registry, indent=2, default=str), encoding="utf-8"
    )


def _resolve_set(prompt_set: str | None) -> str:
    """Resolve None to the default set."""
    if prompt_set:
        return prompt_set
    return _load_registry().get("default_set", DEFAULT_PROMPT_SET)


def _set_current_dir(prompt_set: str) -> Path:
    return PROMPT_SETS_DIR / prompt_set / "current"


def _set_history_dir(prompt_set: str) -> Path:
    return PROMPT_SETS_DIR / prompt_set / "history"


def _validate_set_exists(prompt_set: str) -> None:
    registry = _load_registry()
    if prompt_set not in registry["sets"]:
        raise ValueError(f"Prompt set '{prompt_set}' not found")


# ──────────────────────────────────────────────────────────────────────────────
# One-time migration from flat prompts/current/ to prompts/sets/
# ──────────────────────────────────────────────────────────────────────────────

def _migrate_to_prompt_sets() -> None:
    """Auto-migrate from legacy prompts/current/ into prompts/sets/bdo_sme/."""
    if PROMPT_REGISTRY_FILE.exists():
        return  # already migrated

    if not PROMPTS_CURRENT_DIR.exists():
        # Fresh install — create default set with empty structure
        _create_set_dirs(DEFAULT_PROMPT_SET)
        _save_registry({
            "sets": {
                DEFAULT_PROMPT_SET: {
                    "display_name": "BDO SME",
                    "description": "BDO supplier assessment prompts for SMEs",
                    "created_at": datetime.now().isoformat(),
                    "cloned_from": None,
                }
            },
            "default_set": DEFAULT_PROMPT_SET,
        })
        return

    # Migrate existing files
    target_current = _set_current_dir(DEFAULT_PROMPT_SET)
    target_current.mkdir(parents=True, exist_ok=True)
    target_history = _set_history_dir(DEFAULT_PROMPT_SET)
    target_history.mkdir(parents=True, exist_ok=True)

    # Copy YAML files
    for yaml_file in PROMPTS_CURRENT_DIR.glob("*.yaml"):
        shutil.copy2(str(yaml_file), str(target_current / yaml_file.name))

    # Move history subdirectories
    if PROMPTS_HISTORY_DIR.exists():
        for subdir in PROMPTS_HISTORY_DIR.iterdir():
            if subdir.is_dir():
                dest = target_history / subdir.name
                if not dest.exists():
                    shutil.copytree(str(subdir), str(dest))

    _save_registry({
        "sets": {
            DEFAULT_PROMPT_SET: {
                "display_name": "BDO SME",
                "description": "BDO supplier assessment prompts for SMEs",
                "created_at": datetime.now().isoformat(),
                "cloned_from": None,
            }
        },
        "default_set": DEFAULT_PROMPT_SET,
    })


def _create_set_dirs(slug: str) -> None:
    """Create the directory structure for a prompt set."""
    (_set_current_dir(slug)).mkdir(parents=True, exist_ok=True)
    (_set_history_dir(slug)).mkdir(parents=True, exist_ok=True)


# Run migration on import
_migrate_to_prompt_sets()


# ──────────────────────────────────────────────────────────────────────────────
# Prompt set management
# ──────────────────────────────────────────────────────────────────────────────

def list_prompt_sets() -> list[dict]:
    """List all prompt sets with metadata."""
    registry = _load_registry()
    default = registry.get("default_set", DEFAULT_PROMPT_SET)
    result = []
    for slug, info in registry.get("sets", {}).items():
        result.append({
            "slug": slug,
            "display_name": info.get("display_name", slug),
            "description": info.get("description", ""),
            "created_at": info.get("created_at"),
            "cloned_from": info.get("cloned_from"),
            "is_default": slug == default,
        })
    return result


def get_prompt_set_info(prompt_set: str) -> dict:
    """Return metadata for a single set."""
    registry = _load_registry()
    info = registry["sets"].get(prompt_set)
    if not info:
        raise ValueError(f"Prompt set '{prompt_set}' not found")
    return {
        "slug": prompt_set,
        **info,
        "is_default": prompt_set == registry.get("default_set"),
    }


def create_prompt_set(slug: str, display_name: str, description: str = "") -> dict:
    """Create a new prompt set with blank YAML files."""
    registry = _load_registry()
    if slug in registry["sets"]:
        raise ValueError(f"Prompt set '{slug}' already exists")

    _create_set_dirs(slug)

    # Create blank YAML files with structure matching PROMPT_FILES
    for key, filename in PROMPT_FILES.items():
        blank = {
            "metadata": {"name": key, "description": ""},
            "sections": {},
        }
        filepath = _set_current_dir(slug) / filename
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(blank, f, default_flow_style=False, allow_unicode=True,
                      sort_keys=False, width=120)

    entry = {
        "display_name": display_name,
        "description": description,
        "created_at": datetime.now().isoformat(),
        "cloned_from": None,
    }
    registry["sets"][slug] = entry
    _save_registry(registry)
    return {"slug": slug, **entry}


def clone_prompt_set(source_set: str, new_slug: str, new_display_name: str,
                     new_description: str = "") -> dict:
    """Clone all current prompt files from source into a new set."""
    registry = _load_registry()
    if source_set not in registry["sets"]:
        raise ValueError(f"Source set '{source_set}' not found")
    if new_slug in registry["sets"]:
        raise ValueError(f"Prompt set '{new_slug}' already exists")

    _create_set_dirs(new_slug)

    # Copy current YAML files
    src_dir = _set_current_dir(source_set)
    dst_dir = _set_current_dir(new_slug)
    for yaml_file in src_dir.glob("*.yaml"):
        shutil.copy2(str(yaml_file), str(dst_dir / yaml_file.name))

    entry = {
        "display_name": new_display_name,
        "description": new_description,
        "created_at": datetime.now().isoformat(),
        "cloned_from": source_set,
    }
    registry["sets"][new_slug] = entry
    _save_registry(registry)
    return {"slug": new_slug, **entry}


def rename_prompt_set(prompt_set: str, new_display_name: str = None,
                      new_description: str = None) -> dict:
    """Update display name and/or description of a set."""
    registry = _load_registry()
    if prompt_set not in registry["sets"]:
        raise ValueError(f"Prompt set '{prompt_set}' not found")
    if new_display_name is not None:
        registry["sets"][prompt_set]["display_name"] = new_display_name
    if new_description is not None:
        registry["sets"][prompt_set]["description"] = new_description
    _save_registry(registry)
    return {"slug": prompt_set, **registry["sets"][prompt_set]}


def delete_prompt_set(prompt_set: str) -> None:
    """Delete a prompt set. Cannot delete the default or only remaining set."""
    registry = _load_registry()
    if prompt_set not in registry["sets"]:
        raise ValueError(f"Prompt set '{prompt_set}' not found")
    if prompt_set == registry.get("default_set"):
        raise ValueError("Cannot delete the default prompt set")
    if len(registry["sets"]) <= 1:
        raise ValueError("Cannot delete the only remaining prompt set")

    # Remove directory
    set_dir = PROMPT_SETS_DIR / prompt_set
    if set_dir.exists():
        shutil.rmtree(str(set_dir), ignore_errors=True)

    del registry["sets"][prompt_set]
    _save_registry(registry)


def set_default_prompt_set(prompt_set: str) -> None:
    """Set a prompt set as the default."""
    registry = _load_registry()
    if prompt_set not in registry["sets"]:
        raise ValueError(f"Prompt set '{prompt_set}' not found")
    registry["default_set"] = prompt_set
    _save_registry(registry)


def get_prompt_set_checksums(prompt_set: str = None) -> dict[str, str]:
    """Compute MD5 checksums for all YAML files in a prompt set."""
    prompt_set = _resolve_set(prompt_set)
    current_dir = _set_current_dir(prompt_set)
    checksums = {}
    for key, filename in PROMPT_FILES.items():
        path = current_dir / filename
        if path.exists():
            checksums[key] = hashlib.md5(path.read_bytes()).hexdigest()
    return checksums


# ──────────────────────────────────────────────────────────────────────────────
# Prompt CRUD (set-aware versions of original functions)
# ──────────────────────────────────────────────────────────────────────────────

def load_prompt(prompt_name: str, prompt_set: str = None) -> dict:
    """Load a prompt YAML file from the specified (or default) set."""
    prompt_set = _resolve_set(prompt_set)
    filepath = _set_current_dir(prompt_set) / f"{prompt_name}.yaml"
    if not filepath.exists():
        return {"metadata": {"name": prompt_name, "description": ""}, "sections": {}}
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_prompt(prompt_name: str, data: dict, prompt_set: str = None) -> str:
    """Save prompt data to YAML and create a timestamped version in history.
    Returns the timestamp string."""
    prompt_set = _resolve_set(prompt_set)
    filepath = _set_current_dir(prompt_set) / f"{prompt_name}.yaml"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True,
                  sort_keys=False, width=120)

    history_dir = _set_history_dir(prompt_set) / prompt_name
    history_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(filepath), str(history_dir / f"{prompt_name}_{timestamp}.yaml"))

    return timestamp


def get_version_history(prompt_name: str, prompt_set: str = None) -> list[dict]:
    """List all historical versions for a prompt, newest first."""
    prompt_set = _resolve_set(prompt_set)
    history_dir = _set_history_dir(prompt_set) / prompt_name
    if not history_dir.exists():
        return []

    versions = []
    for f in sorted(history_dir.glob(f"{prompt_name}_*.yaml"), reverse=True):
        ts_part = f.stem.replace(f"{prompt_name}_", "")
        try:
            dt = datetime.strptime(ts_part, "%Y%m%d_%H%M%S")
            versions.append({
                "timestamp": ts_part,
                "display_time": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "filename": f.name,
                "path": f,
            })
        except ValueError:
            continue
    return versions


def load_version(prompt_name: str, timestamp: str, prompt_set: str = None) -> dict:
    """Load a specific historical version of a prompt."""
    prompt_set = _resolve_set(prompt_set)
    filepath = _set_history_dir(prompt_set) / prompt_name / f"{prompt_name}_{timestamp}.yaml"
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


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
