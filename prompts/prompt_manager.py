"""Prompt management system with CRUD operations and version history."""

import yaml
import shutil
from pathlib import Path
from datetime import datetime
from difflib import unified_diff

from config.settings import PROMPTS_CURRENT_DIR, PROMPTS_HISTORY_DIR


def load_prompt(prompt_name: str) -> dict:
    """Load a prompt YAML file and return its contents as a dict."""
    filepath = PROMPTS_CURRENT_DIR / f"{prompt_name}.yaml"
    if not filepath.exists():
        return {"metadata": {"name": prompt_name, "description": ""}, "sections": {}}
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_prompt(prompt_name: str, data: dict) -> str:
    """Save prompt data to YAML and create a timestamped version in history.
    Returns the timestamp string of the saved version."""
    filepath = PROMPTS_CURRENT_DIR / f"{prompt_name}.yaml"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save current version
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)

    # Save timestamped copy to history
    history_dir = PROMPTS_HISTORY_DIR / prompt_name
    history_dir.mkdir(parents=True, exist_ok=True)
    history_filepath = history_dir / f"{prompt_name}_{timestamp}.yaml"
    shutil.copy2(filepath, history_filepath)

    return timestamp


def get_version_history(prompt_name: str) -> list[dict]:
    """List all historical versions for a prompt, newest first.
    Returns list of dicts with 'timestamp', 'filename', 'path'."""
    history_dir = PROMPTS_HISTORY_DIR / prompt_name
    if not history_dir.exists():
        return []

    versions = []
    for f in sorted(history_dir.glob(f"{prompt_name}_*.yaml"), reverse=True):
        # Extract timestamp from filename: prompt_name_YYYYMMDD_HHMMSS.yaml
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


def load_version(prompt_name: str, timestamp: str) -> dict:
    """Load a specific historical version of a prompt."""
    history_dir = PROMPTS_HISTORY_DIR / prompt_name
    filepath = history_dir / f"{prompt_name}_{timestamp}.yaml"
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def revert_to_version(prompt_name: str, timestamp: str) -> str:
    """Restore a historical version as the current version.
    Creates a new history entry for the revert action.
    Returns the new timestamp."""
    old_data = load_version(prompt_name, timestamp)
    if not old_data:
        raise ValueError(f"Version {timestamp} not found for prompt {prompt_name}")
    return save_prompt(prompt_name, old_data)


def diff_versions(prompt_name: str, ts1: str, ts2: str) -> dict:
    """Compare two versions section by section.
    Returns dict with section keys and their diff status."""
    v1 = load_version(prompt_name, ts1)
    v2 = load_version(prompt_name, ts2)

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


def assemble_prompt_text(prompt_name: str) -> str:
    """Concatenate all sections of a prompt into a single text block."""
    data = load_prompt(prompt_name)
    sections = data.get("sections", {})
    parts = []
    for key, section in sections.items():
        title = section.get("title", key)
        content = section.get("content", "")
        parts.append(f"**{title}**\n\n{content}")
    return "\n\n".join(parts)


def get_section_titles(prompt_name: str) -> list[tuple[str, str]]:
    """Return list of (section_key, section_title) pairs for a prompt."""
    data = load_prompt(prompt_name)
    sections = data.get("sections", {})
    return [(key, sec.get("title", key)) for key, sec in sections.items()]
