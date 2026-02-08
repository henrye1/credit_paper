"""Assessment pipeline orchestration — wraps core modules for async execution."""

import json
import shutil
import traceback
from datetime import datetime
from pathlib import Path

from config.settings import (
    REPORT_INPUTS_DIR, REPORT_OUTPUT_DIR, ASSESSMENTS_DIR
)
from backend.services.log_manager import create_log_queue, push_log


# In-memory assessment state (also persisted to state.json)
_assessments: dict[str, dict] = {}


def _state_file(assessment_id: str) -> Path:
    return ASSESSMENTS_DIR / assessment_id / "state.json"


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


def create_assessment(ratio_filename: str, model: str, skip_biz_desc: bool) -> str:
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
        "company_name": None,
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
            log_callback=log,
        )
        if not result["success"]:
            push_log(assessment_id, "error", result["message"])
            state["phase"] = "error"
            save_state(assessment_id)
            return

        log(f"Report generated: {result.get('output_path', '')}")
        state["company_name"] = result.get("company_name", "")

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


def archive_assessment(assessment_id: str) -> dict:
    """Archive the finalized assessment (inputs + report)."""
    state = get_state(assessment_id)
    if not state:
        return {"success": False, "message": "Assessment not found"}

    work_dir = REPORT_INPUTS_DIR
    assessment_dir = ASSESSMENTS_DIR / assessment_id
    assessment_dir.mkdir(parents=True, exist_ok=True)

    # Copy input files
    inputs_subdir = assessment_dir / "inputs"
    inputs_subdir.mkdir(exist_ok=True)
    for f in work_dir.iterdir():
        if f.is_file():
            dest_name = f.name
            if len(dest_name) > 60:
                dest_name = f.stem[:50] + f.suffix
            shutil.copy2(str(f), str(inputs_subdir / dest_name))

    # Copy/write the finalized report
    report_filename = state.get("report_filename")
    if report_filename:
        report_src = REPORT_OUTPUT_DIR / report_filename
        if report_src.exists():
            dest_name = report_filename
            if len(dest_name) > 80:
                dest_name = Path(report_filename).stem[:70] + Path(report_filename).suffix
            shutil.copy2(str(report_src), str(assessment_dir / dest_name))

    return {
        "success": True,
        "report_path": str(assessment_dir),
        "report_name": report_filename,
    }


def clean_working_dir():
    """Remove working files from report_inputs."""
    for f in REPORT_INPUTS_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in [".xlsx", ".xlsm", ".pdf", ".md", ".txt"]:
            f.unlink()


def list_past_assessments() -> list[dict]:
    """List all past assessments."""
    result = []
    if not ASSESSMENTS_DIR.exists():
        return result
    for d in sorted(ASSESSMENTS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        html_files = list(d.glob("*.html"))
        inputs_dir = d / "inputs"
        input_files = [f.name for f in inputs_dir.iterdir() if f.is_file()] if inputs_dir.exists() else []
        result.append({
            "name": d.name,
            "report_name": html_files[0].name if html_files else None,
            "input_files": input_files,
            "has_state": (d / "state.json").exists(),
        })
    return result
