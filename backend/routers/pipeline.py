"""Dev Pipeline endpoints — wraps the 6-stage Run Assessment workflow."""

import asyncio
import json
import traceback
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse

from config.settings import (
    REPORT_INPUTS_DIR, FS_LEARNING_INPUTS_DIR, REPORT_OUTPUT_DIR,
    AUDIT_LLM_INPUT_DIR, AUDIT_LLM_OUTPUT_DIR, EVAL_INPUT_DIR, EVAL_OUTPUT_DIR,
)
from backend.schemas import PipelineRunResponse
from backend.services.log_manager import create_log_queue, push_log, event_generator

router = APIRouter()


def _run_pipeline_sync(run_id: str, stages: list[str], model_report: str, model_audit: str):
    """Run selected stages of the dev pipeline synchronously."""
    def log(msg: str):
        push_log(run_id, "log", msg)

    try:
        # Stage 1: Parse Excel
        if "parse" in stages:
            push_log(run_id, "stage", "Stage 1: Parsing Excel files...")
            from core.parser import parse_all_in_directories
            dirs = [REPORT_INPUTS_DIR, FS_LEARNING_INPUTS_DIR]
            results = parse_all_in_directories(dirs, log_callback=log)
            log(f"Parsed {len(results)} file(s)")

        # Stage 2: Business Description
        if "business_desc" in stages:
            push_log(run_id, "stage", "Stage 2: Extracting business description...")
            from core.business_desc import extract_business_description
            try:
                desc = extract_business_description(REPORT_INPUTS_DIR, log_callback=log)
                log(f"Description: {desc[:100]}...")
            except Exception as e:
                log(f"Warning: {e}")

        # Stage 3: Generate Report
        if "generate" in stages:
            push_log(run_id, "stage", "Stage 3: Generating report...")
            from core.report_generator import generate_report
            result = generate_report(model=model_report, log_callback=log)
            if result["success"]:
                log(f"Report: {result['message']}")
            else:
                log(f"Error: {result['message']}")

        # Stage 4: Audit Review
        if "audit" in stages:
            push_log(run_id, "stage", "Stage 4: Running audit review...")
            from core.auditor import audit_report
            result = audit_report(model=model_audit, log_callback=log)
            if result["success"]:
                log(f"Audit: {result['message']}")
            else:
                log(f"Error: {result['message']}")

        # Stage 5: Compare Reports
        if "compare" in stages:
            push_log(run_id, "stage", "Stage 5: Comparing reports...")
            from core.comparator import compare_reports
            result = compare_reports(model=model_report, log_callback=log)
            if result["success"]:
                log(f"Comparison: {result['message']}")
            else:
                log(f"Error: {result['message']}")

        # Stage 6: Convert
        if "convert" in stages:
            push_log(run_id, "stage", "Stage 6: Converting reports...")
            from core.converter import convert_all_reports
            result = convert_all_reports(log_callback=log)
            log(f"Converted: {len(result.get('json_files', []))} JSON, "
                f"{len(result.get('docx_files', []))} DOCX")

        push_log(run_id, "done", json.dumps({"run_id": run_id, "status": "complete"}))

    except Exception as e:
        push_log(run_id, "error", f"Pipeline error: {e}\n{traceback.format_exc()}")


@router.post("/run", response_model=PipelineRunResponse)
async def run_pipeline(
    stages: str = Form(...),  # Comma-separated: "parse,business_desc,generate,audit,compare,convert"
    model_report: str = Form("gemini-2.5-flash"),
    model_audit: str = Form("gemini-2.5-flash"),
):
    """Start a dev pipeline run with selected stages."""
    run_id = f"pipeline_{uuid4().hex[:8]}"
    stage_list = [s.strip() for s in stages.split(",") if s.strip()]

    valid_stages = {"parse", "business_desc", "generate", "audit", "compare", "convert"}
    invalid = set(stage_list) - valid_stages
    if invalid:
        raise HTTPException(400, f"Invalid stages: {invalid}")

    create_log_queue(run_id)

    loop = asyncio.get_event_loop()
    asyncio.ensure_future(
        loop.run_in_executor(None, _run_pipeline_sync, run_id, stage_list, model_report, model_audit)
    )

    return PipelineRunResponse(run_id=run_id)


@router.get("/{run_id}/logs")
async def stream_pipeline_logs(run_id: str):
    """SSE stream of pipeline logs."""
    return StreamingResponse(
        event_generator(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
