"""Assessment pipeline orchestration — Supabase-backed state + storage."""

import json
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

from backend.services.supabase_client import get_supabase
from backend.services.storage_helpers import (
    upload_file, download_file, delete_files, list_files, temp_dir,
)
from backend.services.log_manager import create_log_queue, push_log


# In-memory cache for active sessions (avoids round-trips during generation)
_assessments: dict[str, dict] = {}

# Columns to persist in the assessments table
_DB_COLUMNS = [
    "id", "phase", "model_choice", "skip_biz_desc",
    "head_html", "sections", "pending_ai_proposals", "chat_histories",
    "report_filename", "report_name", "company_name", "prompt_set",
    "created_at", "generated_at", "finalized_at",
    "prompt_checksums", "input_files", "sections_modified",
    "sections_unmodified", "changes",
]


def save_state(assessment_id: str):
    """Persist assessment state to Supabase."""
    state = _assessments.get(assessment_id)
    if not state:
        return
    sb = get_supabase()
    row = {"id": assessment_id}
    for col in _DB_COLUMNS:
        if col == "id":
            continue
        val = state.get(col if col != "id" else "assessment_id")
        # Map internal key names to DB columns
        if col == "id":
            val = assessment_id
        else:
            val = state.get(col)
        if val is not None:
            row[col] = val
    sb.table("assessments").upsert(row, on_conflict="id").execute()


def load_state(assessment_id: str) -> dict | None:
    """Load assessment state from cache or Supabase."""
    if assessment_id in _assessments:
        return _assessments[assessment_id]
    sb = get_supabase()
    result = sb.table("assessments").select("*").eq("id", assessment_id).limit(1).execute()
    if not result.data:
        return None
    row = result.data[0]
    state = {
        "assessment_id": row["id"],
        "phase": row.get("phase", "generating"),
        "model_choice": row.get("model_choice"),
        "skip_biz_desc": row.get("skip_biz_desc", False),
        "head_html": row.get("head_html", ""),
        "sections": row.get("sections") or [],
        "pending_ai_proposals": row.get("pending_ai_proposals") or {},
        "chat_histories": row.get("chat_histories") or {},
        "report_filename": row.get("report_filename"),
        "report_name": row.get("report_name"),
        "company_name": row.get("company_name"),
        "prompt_set": row.get("prompt_set"),
        "created_at": row.get("created_at"),
        "generated_at": row.get("generated_at"),
        "finalized_at": row.get("finalized_at"),
        "prompt_checksums": row.get("prompt_checksums"),
        "input_files": row.get("input_files") or [],
        "sections_modified": row.get("sections_modified"),
        "sections_unmodified": row.get("sections_unmodified"),
        "changes": row.get("changes"),
    }
    _assessments[assessment_id] = state
    return state


def get_state(assessment_id: str) -> dict | None:
    return _assessments.get(assessment_id) or load_state(assessment_id)


def create_assessment(ratio_filename: str, model: str, skip_biz_desc: bool,
                      report_name: str = "", prompt_set: str = None) -> str:
    """Create a new assessment and return its ID."""
    stem = Path(ratio_filename).stem
    safe_name = "".join(c for c in stem if c.isalnum() or c == " ").strip()[:30].strip()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    assessment_id = f"{safe_name}_{timestamp}"

    _assessments[assessment_id] = {
        "assessment_id": assessment_id,
        "phase": "generating",
        "model_choice": model,
        "skip_biz_desc": skip_biz_desc,
        "head_html": "",
        "sections": [],
        "pending_ai_proposals": {},
        "chat_histories": {},
        "report_filename": None,
        "report_name": report_name or None,
        "company_name": None,
        "prompt_set": prompt_set,
        "created_at": datetime.now().isoformat(),
        "generated_at": None,
        "finalized_at": None,
    }
    save_state(assessment_id)
    return assessment_id


def run_pipeline_sync(assessment_id: str, input_file_paths: list[Path]):
    """Run the 3-stage Quick Assessment pipeline synchronously.

    input_file_paths: list of local temp file paths (Excel + PDFs) already on disk.
    This is executed in a thread pool by the router.
    """
    state = get_state(assessment_id)
    if not state:
        push_log(assessment_id, "error", "Assessment not found")
        return

    def log(msg: str):
        push_log(assessment_id, "log", msg)

    try:
        # Identify file types from the temp paths
        excel_files = [p for p in input_file_paths if p.suffix.lower() in [".xlsx", ".xlsm"]]
        pdf_files = [p for p in input_file_paths if p.suffix.lower() == ".pdf"]
        work_dir = input_file_paths[0].parent if input_file_paths else Path(tempfile.gettempdir())

        # Stage 1: Parse Excel
        push_log(assessment_id, "stage", "Parsing Excel file...")
        from core.parser import parse_excel_to_markdown

        if not excel_files:
            push_log(assessment_id, "error", "No Excel file found in uploads")
            state["phase"] = "error"
            save_state(assessment_id)
            return

        md_path = parse_excel_to_markdown(excel_files[0], log_callback=log)
        log(f"Parsed -> {md_path.name}")

        # Stage 2: Business Description
        if not state.get("skip_biz_desc"):
            push_log(assessment_id, "stage", "Extracting business description...")
            try:
                from core.business_desc import extract_business_description
                desc = extract_business_description(work_dir, log_callback=log)
                log(f"Description: {desc[:100]}...")
            except Exception as e:
                log(f"Warning: Business description extraction failed: {e}")
                log("Continuing without business description.")
        else:
            log("Skipping business description extraction (user opted out).")

        # Stage 3: Generate Report
        push_log(assessment_id, "stage", "Generating financial condition report...")
        from core.report_generator import generate_report

        result = generate_report(
            target_inputs_dir=work_dir,
            model=state.get("model_choice", "gemini-2.5-flash"),
            report_name=state.get("report_name"),
            log_callback=log,
            prompt_set=state.get("prompt_set"),
        )
        if not result["success"]:
            push_log(assessment_id, "error", result["message"])
            state["phase"] = "error"
            save_state(assessment_id)
            return

        log(f"Report generated successfully")
        state["company_name"] = result.get("company_name", "")
        state["generated_at"] = datetime.now().isoformat()

        # Stage 4: Parse into sections
        push_log(assessment_id, "stage", "Preparing review...")
        html_content = result.get("html_content", "")
        report_filename = result.get("report_filename", "report.html")

        from core.report_sections import parse_report_to_sections
        parsed = parse_report_to_sections(html_content)

        if not parsed["sections"]:
            push_log(assessment_id, "error", "Could not parse report into sections")
            state["phase"] = "error"
            save_state(assessment_id)
            return

        log(f"Report parsed into {len(parsed['sections'])} sections.")

        # Upload original report to storage
        upload_file(
            "assessment-files",
            f"{assessment_id}/original_report.html",
            html_content.encode("utf-8"),
            "text/html",
        )

        # Upload input files to storage
        input_names = []
        for fp in input_file_paths:
            if fp.exists():
                storage_path = f"{assessment_id}/inputs/{fp.name}"
                upload_file("assessment-files", storage_path, fp.read_bytes())
                input_names.append(fp.name)

        state["phase"] = "review"
        state["head_html"] = parsed["head_html"]
        state["sections"] = parsed["sections"]
        state["report_filename"] = report_filename
        state["pending_ai_proposals"] = {}
        state["chat_histories"] = {}
        state["input_files"] = input_names
        save_state(assessment_id)

        push_log(assessment_id, "done", json.dumps({
            "assessment_id": assessment_id,
            "section_count": len(parsed["sections"]),
        }))

    except Exception as e:
        push_log(assessment_id, "error", f"Pipeline error: {e}\n{traceback.format_exc()}")
        state["phase"] = "error"
        save_state(assessment_id)


def _compute_changes(state: dict) -> dict:
    """Compute section-level change summary for the assessment."""
    sections = state.get("sections", [])
    chat_histories = state.get("chat_histories", {})
    changes = []
    modified_count = 0

    for i, s in enumerate(sections):
        original = s.get("original_html", "")
        current = s.get("html", "")
        modified = original != current
        if modified:
            modified_count += 1

        has_ai_history = str(i) in chat_histories and len(chat_histories[str(i)]) > 0
        if modified and has_ai_history:
            edit_type = "ai_assisted"
        elif modified:
            edit_type = "manual"
        else:
            edit_type = "none"

        changes.append({
            "index": i,
            "id": s.get("id", ""),
            "title": s.get("title", ""),
            "modified": modified,
            "edit_type": edit_type,
        })

    return {
        "summary": {
            "total_sections": len(sections),
            "sections_modified": modified_count,
            "sections_unmodified": len(sections) - modified_count,
        },
        "sections": changes,
    }


def archive_assessment(assessment_id: str, final_html: str = None) -> dict:
    """Archive the finalized assessment with full provenance.

    Uploads final report to storage and writes metadata to the DB row.
    """
    state = get_state(assessment_id)
    if not state:
        return {"success": False, "message": "Assessment not found"}

    # Upload final report to storage
    if final_html:
        upload_file(
            "assessment-files",
            f"{assessment_id}/final_report.html",
            final_html.encode("utf-8"),
            "text/html",
        )

    # Compute changes
    changes = _compute_changes(state)

    state["finalized_at"] = datetime.now().isoformat()
    state["sections_modified"] = changes["summary"]["sections_modified"]
    state["sections_unmodified"] = changes["summary"]["sections_unmodified"]
    state["changes"] = changes

    from prompts.prompt_manager import get_prompt_set_checksums
    state["prompt_checksums"] = get_prompt_set_checksums(state.get("prompt_set"))

    save_state(assessment_id)

    return {
        "success": True,
        "report_path": assessment_id,
        "report_name": state.get("report_name") or state.get("report_filename"),
    }


def clean_working_dir():
    """No-op — temp files are managed by context managers now."""
    pass


def list_past_assessments() -> list[dict]:
    """List all past assessments from Supabase."""
    sb = get_supabase()
    rows = (sb.table("assessments")
            .select("id, phase, company_name, model_choice, report_filename, report_name, "
                    "created_at, finalized_at, input_files, sections_modified, "
                    "sections_unmodified, changes")
            .order("created_at", desc=True)
            .execute())

    result = []
    for r in rows.data:
        sections_data = r.get("changes", {})
        section_count = (sections_data.get("summary", {}).get("total_sections")
                         if sections_data else None)

        entry = {
            "name": r["id"],
            "input_files": r.get("input_files") or [],
            "has_state": True,
            "has_original": True,
            "has_final": r.get("phase") == "complete",
            "company_name": r.get("company_name"),
            "model": r.get("model_choice"),
            "finalized_at": r.get("finalized_at"),
            "section_count": section_count,
            "sections_modified": r.get("sections_modified"),
            "report_name": r.get("report_name") or r.get("report_filename"),
        }
        result.append(entry)
    return result


def delete_assessment(assessment_id: str):
    """Delete an assessment from DB and storage."""
    sb = get_supabase()

    # Delete storage files for this assessment
    try:
        files = list_files("assessment-files", assessment_id)
        if files:
            paths = [f"{assessment_id}/{f['name']}" for f in files if f.get("name")]
            delete_files("assessment-files", paths)
        # Also try inputs subfolder
        input_files = list_files("assessment-files", f"{assessment_id}/inputs")
        if input_files:
            paths = [f"{assessment_id}/inputs/{f['name']}" for f in input_files if f.get("name")]
            delete_files("assessment-files", paths)
    except Exception:
        pass  # Storage cleanup is best-effort

    # Delete DB row
    sb.table("assessments").delete().eq("id", assessment_id).execute()

    # Clear from cache
    _assessments.pop(assessment_id, None)
