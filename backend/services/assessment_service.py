"""Assessment pipeline orchestration — wraps core modules for async execution."""

import json
import shutil
import traceback
from datetime import datetime
from pathlib import Path

from config.settings import (
    REPORT_INPUTS_DIR, REPORT_OUTPUT_DIR, ASSESSMENTS_DIR,
)
from backend.services.log_manager import create_log_queue, push_log


# In-memory assessment state (also persisted to state.json)
_assessments: dict[str, dict] = {}


def _state_file(assessment_id: str) -> Path:
    return ASSESSMENTS_DIR / assessment_id / "state.json"


def _assessment_dir(assessment_id: str) -> Path:
    return ASSESSMENTS_DIR / assessment_id


def save_state(assessment_id: str):
    """Persist assessment state to JSON file."""
    state = _assessments.get(assessment_id)
    if not state:
        return
    path = _state_file(assessment_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write a copy without non-serializable fields
    serializable = {k: v for k, v in state.items() if k != "_queue"}
    path.write_text(json.dumps(serializable, indent=2, default=str), encoding="utf-8")


def load_state(assessment_id: str) -> dict | None:
    """Load assessment state from JSON file."""
    if assessment_id in _assessments:
        return _assessments[assessment_id]
    path = _state_file(assessment_id)
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
        _assessments[assessment_id] = state
        return state
    return None


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


def run_pipeline_sync(assessment_id: str):
    """Run the 3-stage Quick Assessment pipeline synchronously.

    This is executed in a thread pool by the router.
    Pushes log events to the SSE queue.
    """
    state = get_state(assessment_id)
    if not state:
        push_log(assessment_id, "error", "Assessment not found")
        return

    def log(msg: str):
        push_log(assessment_id, "log", msg)

    try:
        work_dir = REPORT_INPUTS_DIR

        # Stage 1: Parse Excel
        push_log(assessment_id, "stage", "Parsing Excel file...")
        from core.parser import parse_excel_to_markdown

        excel_files = [
            f for f in work_dir.iterdir()
            if f.is_file() and f.suffix.lower() in [".xlsx", ".xlsm"]
        ]
        if not excel_files:
            push_log(assessment_id, "error", "No Excel file found in working directory")
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

        log(f"Report generated: {result.get('output_path', '')}")
        state["company_name"] = result.get("company_name", "")
        state["generated_at"] = datetime.now().isoformat()

        # Stage 4: Parse into sections
        push_log(assessment_id, "stage", "Preparing review...")
        from core.report_sections import parse_report_to_sections

        html_reports = sorted(
            REPORT_OUTPUT_DIR.glob("*.html"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not html_reports:
            push_log(assessment_id, "error", "No HTML report found after generation")
            state["phase"] = "error"
            save_state(assessment_id)
            return

        report_path = html_reports[0]
        html_content = report_path.read_text(encoding="utf-8")
        parsed = parse_report_to_sections(html_content)

        if not parsed["sections"]:
            push_log(assessment_id, "error", "Could not parse report into sections")
            state["phase"] = "error"
            save_state(assessment_id)
            return

        log(f"Report parsed into {len(parsed['sections'])} sections.")

        # Save original AI-generated report before any human edits
        assess_dir = _assessment_dir(assessment_id)
        assess_dir.mkdir(parents=True, exist_ok=True)
        (assess_dir / "original_report.html").write_text(
            html_content, encoding="utf-8"
        )

        # Copy input files early so they're preserved even if user abandons
        _copy_inputs(assess_dir)

        state["phase"] = "review"
        state["head_html"] = parsed["head_html"]
        state["sections"] = parsed["sections"]
        state["report_filename"] = report_path.name
        state["pending_ai_proposals"] = {}
        state["chat_histories"] = {}
        save_state(assessment_id)

        push_log(assessment_id, "done", json.dumps({
            "assessment_id": assessment_id,
            "section_count": len(parsed["sections"]),
        }))

    except Exception as e:
        push_log(assessment_id, "error", f"Pipeline error: {e}\n{traceback.format_exc()}")
        state["phase"] = "error"
        save_state(assessment_id)


def _copy_inputs(assessment_dir: Path):
    """Copy current working input files to assessment inputs/ subdirectory."""
    inputs_subdir = assessment_dir / "inputs"
    inputs_subdir.mkdir(exist_ok=True)
    for f in REPORT_INPUTS_DIR.iterdir():
        if f.is_file():
            dest_name = f.name
            if len(dest_name) > 60:
                dest_name = f.stem[:50] + f.suffix
            dest = inputs_subdir / dest_name
            if not dest.exists():
                shutil.copy2(str(f), str(dest))


def _compute_changes(state: dict) -> dict:
    """Compute section-level change summary for the assessment.

    Returns a dict with per-section change info and an overall summary.
    Useful for monitoring quality and identifying prompt improvement areas.
    """
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

        # Determine edit type from chat histories
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
    """Archive the finalized assessment with full provenance for labelling.

    Saves:
      - inputs/              (Excel, PDFs, business desc, parsed markdown)
      - original_report.html (AI-generated, before human edits)
      - final_report.html    (human-reviewed, after edits + approval)
      - metadata.json        (model, timestamps, prompt versions, change stats)
      - changes.json         (per-section change summary)
      - state.json           (full state including original_html + html per section)
    """
    state = get_state(assessment_id)
    if not state:
        return {"success": False, "message": "Assessment not found"}

    assess_dir = _assessment_dir(assessment_id)
    assess_dir.mkdir(parents=True, exist_ok=True)

    # Ensure inputs are copied (may already be done during pipeline)
    _copy_inputs(assess_dir)

    # Save final human-reviewed report
    if final_html:
        (assess_dir / "final_report.html").write_text(final_html, encoding="utf-8")
    else:
        # Fallback: copy from report_output
        report_filename = state.get("report_filename")
        if report_filename:
            report_src = REPORT_OUTPUT_DIR / report_filename
            if report_src.exists():
                shutil.copy2(str(report_src), str(assess_dir / "final_report.html"))

    # If original_report.html wasn't saved during pipeline (legacy), save from original sections
    if not (assess_dir / "original_report.html").exists():
        from core.report_sections import reassemble_report_html
        original_sections = []
        for s in state.get("sections", []):
            original_sections.append({**s, "html": s.get("original_html", s["html"])})
        original_html = reassemble_report_html({
            "head_html": state.get("head_html", ""),
            "body_prefix": "",
            "sections": original_sections,
        })
        (assess_dir / "original_report.html").write_text(original_html, encoding="utf-8")

    # Compute and save section-level changes
    changes = _compute_changes(state)
    (assess_dir / "changes.json").write_text(
        json.dumps(changes, indent=2), encoding="utf-8"
    )

    # Record finalization timestamp
    state["finalized_at"] = datetime.now().isoformat()
    save_state(assessment_id)

    # Save metadata
    inputs_dir = assess_dir / "inputs"
    input_files = [f.name for f in inputs_dir.iterdir() if f.is_file()] if inputs_dir.exists() else []

    from prompts.prompt_manager import get_prompt_set_checksums

    metadata = {
        "assessment_id": assessment_id,
        "company_name": state.get("company_name", ""),
        "model": state.get("model_choice", ""),
        "prompt_set": state.get("prompt_set"),
        "created_at": state.get("created_at"),
        "generated_at": state.get("generated_at"),
        "finalized_at": state.get("finalized_at"),
        "prompt_checksums": get_prompt_set_checksums(state.get("prompt_set")),
        "input_files": input_files,
        "section_count": changes["summary"]["total_sections"],
        "sections_modified": changes["summary"]["sections_modified"],
        "sections_unmodified": changes["summary"]["sections_unmodified"],
    }
    (assess_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    return {
        "success": True,
        "report_path": str(assess_dir),
        "report_name": state.get("report_name") or state.get("report_filename"),
    }


def clean_working_dir():
    """Remove working files from report_inputs."""
    for f in REPORT_INPUTS_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in [".xlsx", ".xlsm", ".pdf", ".md", ".txt"]:
            f.unlink()


def list_past_assessments() -> list[dict]:
    """List all past assessments with metadata when available."""
    result = []
    if not ASSESSMENTS_DIR.exists():
        return result
    for d in sorted(ASSESSMENTS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue

        inputs_dir = d / "inputs"
        input_files = [f.name for f in inputs_dir.iterdir() if f.is_file()] if inputs_dir.exists() else []

        entry = {
            "name": d.name,
            "input_files": input_files,
            "has_state": (d / "state.json").exists(),
            "has_original": (d / "original_report.html").exists(),
            "has_final": (d / "final_report.html").exists(),
        }

        # Include metadata if available
        meta_path = d / "metadata.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                entry["company_name"] = meta.get("company_name")
                entry["model"] = meta.get("model")
                entry["finalized_at"] = meta.get("finalized_at")
                entry["section_count"] = meta.get("section_count")
                entry["sections_modified"] = meta.get("sections_modified")
            except (json.JSONDecodeError, OSError):
                pass

        # Determine report name from final or any HTML file
        if (d / "final_report.html").exists():
            entry["report_name"] = "final_report.html"
        else:
            html_files = list(d.glob("*.html"))
            entry["report_name"] = html_files[0].name if html_files else None

        result.append(entry)
    return result
