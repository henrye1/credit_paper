"""One-time migration: seed Supabase with existing YAML prompts + registry.

Run from project root:
    python scripts/seed_supabase.py

Prerequisites:
    - SUPABASE_URL and SUPABASE_SERVICE_KEY set in .env
    - Tables created via scripts/create_tables.sql
    - Storage buckets created: assessment-files, reports, examples
"""

import json
import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import yaml
from backend.services.supabase_client import get_supabase


def main():
    sb = get_supabase()
    print("Connected to Supabase.")

    # --- Read local registry ---
    registry_path = PROJECT_ROOT / "prompts" / "sets" / "_registry.json"
    if not registry_path.exists():
        print("No _registry.json found. Nothing to migrate.")
        return

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    default_set = registry.get("default_set", "bdo_sme")
    sets_info = registry.get("sets", {})

    # --- Seed prompt_sets ---
    for slug, info in sets_info.items():
        existing = sb.table("prompt_sets").select("slug").eq("slug", slug).limit(1).execute()
        if existing.data:
            print(f"  Prompt set '{slug}' already exists, skipping.")
            continue

        sb.table("prompt_sets").insert({
            "slug": slug,
            "display_name": info.get("display_name", slug),
            "description": info.get("description", ""),
            "is_default": slug == default_set,
            "cloned_from": info.get("cloned_from"),
        }).execute()
        print(f"  Created prompt set: {slug}")

    # --- Seed prompts (current YAML files) ---
    sets_dir = PROJECT_ROOT / "prompts" / "sets"
    for slug in sets_info:
        current_dir = sets_dir / slug / "current"
        if not current_dir.exists():
            print(f"  No current/ dir for set '{slug}', skipping prompts.")
            continue

        for yaml_file in current_dir.glob("*.yaml"):
            prompt_name = yaml_file.stem
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            metadata = data.get("metadata", {"name": prompt_name, "description": ""})
            sections = data.get("sections", {})

            # Check if already exists
            existing = (sb.table("prompts")
                        .select("id")
                        .eq("prompt_set", slug)
                        .eq("prompt_name", prompt_name)
                        .limit(1)
                        .execute())
            if existing.data:
                print(f"    Prompt '{slug}/{prompt_name}' already exists, skipping.")
                continue

            sb.table("prompts").insert({
                "prompt_set": slug,
                "prompt_name": prompt_name,
                "metadata": metadata,
                "sections": sections,
            }).execute()
            print(f"    Seeded prompt: {slug}/{prompt_name}")

    # --- Seed prompt versions (history YAML files) ---
    for slug in sets_info:
        history_dir = sets_dir / slug / "history"
        if not history_dir.exists():
            continue

        for prompt_dir in history_dir.iterdir():
            if not prompt_dir.is_dir():
                continue
            prompt_name = prompt_dir.name

            for yaml_file in sorted(prompt_dir.glob(f"{prompt_name}_*.yaml")):
                ts_part = yaml_file.stem.replace(f"{prompt_name}_", "")
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}

                existing = (sb.table("prompt_versions")
                            .select("id")
                            .eq("prompt_set", slug)
                            .eq("prompt_name", prompt_name)
                            .eq("timestamp", ts_part)
                            .limit(1)
                            .execute())
                if existing.data:
                    continue

                sb.table("prompt_versions").insert({
                    "prompt_set": slug,
                    "prompt_name": prompt_name,
                    "timestamp": ts_part,
                    "metadata": data.get("metadata", {}),
                    "sections": data.get("sections", {}),
                }).execute()
                print(f"    Seeded version: {slug}/{prompt_name} @ {ts_part}")

    print("\nSeed complete!")


if __name__ == "__main__":
    main()
