"""Assessment endpoints — wraps the Quick Assessment workflow."""

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

from config.settings import REPORT_INPUTS_DIR, REPORT_OUTPUT_DIR, ASSESSMENTS_DIR
from backend.schemas import (
    AssessmentStartResponse, AssessmentStatusResponse, SectionsResponse,
    SectionSchema, SectionUpdateRequest, AiUpdateResponse,
    AcceptAiRequest, FinalizeResponse,
)
from backend.services.assessment_service import (
    create_assessment, run_pipeline_sync, get_state, save_state,
    archive_assessment, clean_working_dir, list_past_assessments,
)
from backend.services.log_manager import create_log_queue, event_generator

router = APIRouter()


@router.post("/start", response_model=AssessmentStartResponse)
async def start_assessment(
    background_tasks: BackgroundTasks,
    ratio_file: UploadFile = File(...),
    pdf_files: list[UploadFile] = File(...),
    model: str = Form("gemini-2.5-flash"),
    skip_biz_desc: bool = Form(False),
    report_name: str = Form(""),
):
    """Upload files and start the generation pipeline."""
    # Clean working directory
    clean_working_dir()

    # Save uploaded files to working directory
    work_dir = REPORT_INPUTS_DIR
    ratio_dest = work_dir / ratio_file.filename
    ratio_dest.write_bytes(await ratio_file.read())

    for pdf in pdf_files:
        pdf_dest = work_dir / pdf.filename
        pdf_dest.write_bytes(await pdf.read())

    # Create assessment
    assessment_id = create_assessment(ratio_file.filename, model, skip_biz_desc, report_name)

    # Create log queue and start pipeline in background
    create_log_queue(assessment_id)

    loop = asyncio.get_event_loop()
    background_tasks.add_task(loop.run_in_executor, None, run_pipeline_sync, assessment_id)

    return AssessmentStartResponse(assessment_id=assessment_id)


@router.get("/{assessment_id}/logs")
async def stream_logs(assessment_id: str):
    """SSE stream of generation logs."""
    return StreamingResponse(
        event_generator(assessment_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{assessment_id}/status", response_model=AssessmentStatusResponse)
async def get_status(assessment_id: str):
    """Get current assessment status."""
    state = get_state(assessment_id)
    if not state:
        raise HTTPException(404, "Assessment not found")

    sections = state.get("sections", [])
    approved = sum(1 for s in sections if s.get("status") == "approved")

    return AssessmentStatusResponse(
        assessment_id=assessment_id,
        phase=state["phase"],
        section_count=len(sections),
        approved_count=approved,
    )


@router.get("/{assessment_id}/sections", response_model=SectionsResponse)
async def get_sections(assessment_id: str):
    """Get parsed sections for review."""
    state = get_state(assessment_id)
    if not state:
        raise HTTPException(404, "Assessment not found")
    if state["phase"] not in ("review", "complete"):
        raise HTTPException(400, f"Assessment is in '{state['phase']}' phase, not review")

    return SectionsResponse(
        head_html=state.get("head_html", ""),
        sections=[
            SectionSchema(
                id=s["id"],
                title=s["title"],
                html=s["html"],
                original_html=s["original_html"],
                status=s.get("status", "pending"),
            )
            for s in state["sections"]
        ],
    )


@router.put("/{assessment_id}/sections/{section_idx}")
async def update_section(assessment_id: str, section_idx: int, body: SectionUpdateRequest):
    """Apply a manual edit to a section (HTML from TipTap editor)."""
    state = get_state(assessment_id)
    if not state:
        raise HTTPException(404, "Assessment not found")
    sections = state.get("sections", [])
    if section_idx < 0 or section_idx >= len(sections):
        raise HTTPException(400, "Invalid section index")

    sections[section_idx]["html"] = body.html
    if sections[section_idx]["status"] == "approved":
        sections[section_idx]["status"] = "pending"
    save_state(assessment_id)
    return {"success": True}


@router.put("/{assessment_id}/sections/{section_idx}/approve")
async def approve_section(assessment_id: str, section_idx: int):
    """Approve a section."""
    state = get_state(assessment_id)
    if not state:
        raise HTTPException(404, "Assessment not found")
    sections = state.get("sections", [])
    if section_idx < 0 or section_idx >= len(sections):
        raise HTTPException(400, "Invalid section index")

    sections[section_idx]["status"] = "approved"
    save_state(assessment_id)
    return {"success": True, "status": "approved"}


@router.put("/{assessment_id}/sections/{section_idx}/reset")
async def reset_section(assessment_id: str, section_idx: int):
    """Reset a section to its original HTML."""
    state = get_state(assessment_id)
    if not state:
        raise HTTPException(404, "Assessment not found")
    sections = state.get("sections", [])
    if section_idx < 0 or section_idx >= len(sections):
        raise HTTPException(400, "Invalid section index")

    sections[section_idx]["html"] = sections[section_idx]["original_html"]
    sections[section_idx]["status"] = "pending"
    # Clear pending AI proposal for this section
    state.get("pending_ai_proposals", {}).pop(str(section_idx), None)
    save_state(assessment_id)
    return {"success": True}


@router.post("/{assessment_id}/sections/{section_idx}/ai-update", response_model=AiUpdateResponse)
async def ai_update_section(
    assessment_id: str,
    section_idx: int,
    instruction: str = Form(...),
    include_context: bool = Form(False),
    evidence_files: list[UploadFile] = File(default=[]),
):
    """Request AI update for a section. Returns proposed HTML (governance gate)."""
    state = get_state(assessment_id)
    if not state:
        raise HTTPException(404, "Assessment not found")
    sections = state.get("sections", [])
    if section_idx < 0 or section_idx >= len(sections):
        raise HTTPException(400, "Invalid section index")

    section = sections[section_idx]

    # Save evidence files temporarily
    temp_paths = []
    for ef in evidence_files:
        if ef.filename:
            temp_path = REPORT_INPUTS_DIR / f"_temp_evidence_{ef.filename}"
            temp_path.write_bytes(await ef.read())
            temp_paths.append(temp_path)

    # Build full report context if requested
    full_context = None
    if include_context:
        from core.report_sections import reassemble_report_html
        full_context = reassemble_report_html({
            "head_html": state.get("head_html", ""),
            "body_prefix": "",
            "sections": sections,
        })

    # Run AI update in thread pool (sync Gemini call)
    loop = asyncio.get_event_loop()
    from core.report_sections import generate_section_update

    result = await loop.run_in_executor(
        None,
        lambda: generate_section_update(
            section_html=section["html"],
            instruction=instruction,
            evidence_files=temp_paths if temp_paths else None,
            full_report_context=full_context,
            model=state.get("model_choice", "gemini-2.5-flash"),
        ),
    )

    # Cleanup temp files
    for tp in temp_paths:
        if tp.exists():
            tp.unlink()

    if result["success"]:
        # Store pending proposal
        if "pending_ai_proposals" not in state:
            state["pending_ai_proposals"] = {}
        state["pending_ai_proposals"][str(section_idx)] = result["updated_html"]

        # Track chat history
        if "chat_histories" not in state:
            state["chat_histories"] = {}
        key = str(section_idx)
        if key not in state["chat_histories"]:
            state["chat_histories"][key] = []
        state["chat_histories"][key].append({"role": "user", "content": instruction})
        state["chat_histories"][key].append({
            "role": "assistant",
            "content": "Section updated. Review the proposed changes."
        })
        save_state(assessment_id)

    return AiUpdateResponse(
        success=result["success"],
        proposed_html=result.get("updated_html", ""),
        message=result.get("message", ""),
    )


@router.put("/{assessment_id}/sections/{section_idx}/accept-ai")
async def accept_ai_update(assessment_id: str, section_idx: int, body: AcceptAiRequest):
    """Accept the AI-proposed update for a section."""
    state = get_state(assessment_id)
    if not state:
        raise HTTPException(404, "Assessment not found")
    sections = state.get("sections", [])
    if section_idx < 0 or section_idx >= len(sections):
        raise HTTPException(400, "Invalid section index")

    sections[section_idx]["html"] = body.proposed_html
    if sections[section_idx]["status"] == "approved":
        sections[section_idx]["status"] = "pending"

    # Clear pending proposal
    state.get("pending_ai_proposals", {}).pop(str(section_idx), None)
    save_state(assessment_id)
    return {"success": True}


@router.put("/{assessment_id}/approve-all")
async def approve_all_sections(assessment_id: str):
    """Approve all remaining sections."""
    state = get_state(assessment_id)
    if not state:
        raise HTTPException(404, "Assessment not found")

    for s in state.get("sections", []):
        if s["status"] != "approved":
            s["status"] = "approved"
    save_state(assessment_id)
    return {"success": True}


@router.post("/{assessment_id}/finalize", response_model=FinalizeResponse)
async def finalize_assessment(assessment_id: str):
    """Reassemble sections into final HTML, save, and archive."""
    state = get_state(assessment_id)
    if not state:
        raise HTTPException(404, "Assessment not found")

    sections = state.get("sections", [])
    unapproved = [s for s in sections if s["status"] != "approved"]
    if unapproved:
        raise HTTPException(400, f"{len(unapproved)} sections still need approval")

    # Reassemble HTML
    from core.report_sections import reassemble_report_html

    final_html = reassemble_report_html({
        "head_html": state.get("head_html", ""),
        "body_prefix": "",
        "sections": sections,
    })

    # Write back to report_output
    report_filename = state.get("report_filename")
    if report_filename:
        output_path = REPORT_OUTPUT_DIR / report_filename
        output_path.write_text(final_html, encoding="utf-8")

    # Archive
    result = archive_assessment(assessment_id)

    # Update state
    state["phase"] = "complete"
    save_state(assessment_id)

    # Clean working dir
    clean_working_dir()

    return FinalizeResponse(
        success=result["success"],
        report_path=result.get("report_path"),
        report_name=result.get("report_name"),
        message="Report finalized and archived.",
    )


@router.delete("/{assessment_id}")
async def discard_assessment(assessment_id: str):
    """Discard an assessment."""
    state = get_state(assessment_id)
    if state:
        import shutil
        assessment_dir = ASSESSMENTS_DIR / assessment_id
        if assessment_dir.exists():
            shutil.rmtree(str(assessment_dir), ignore_errors=True)
        from backend.services.assessment_service import _assessments
        _assessments.pop(assessment_id, None)

    clean_working_dir()
    return {"success": True}


@router.get("/past")
async def get_past_assessments():
    """List all past assessments."""
    return list_past_assessments()


@router.get("/past/{name}/report")
async def get_past_report(name: str):
    """Get a past assessment's HTML report content."""
    assessment_dir = ASSESSMENTS_DIR / name
    if not assessment_dir.exists():
        raise HTTPException(404, "Assessment not found")

    html_files = list(assessment_dir.glob("*.html"))
    if not html_files:
        raise HTTPException(404, "No report found in assessment")

    content = html_files[0].read_text(encoding="utf-8")
    return {"html": content, "filename": html_files[0].name}
