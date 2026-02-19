"""Dev Pipeline endpoints — wraps the 6-stage Run Assessment workflow.

The pipeline operates on files already uploaded to Supabase Storage.
Each stage downloads needed files to temp dirs, processes, and uploads results.
"""

import asyncio
import json
import tempfile
import traceback
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse

from backend.schemas import PipelineRunResponse
from backend.services.supabase_client import get_supabase
from backend.services.storage_helpers import (
    upload_file as storage_upload,
    download_file as storage_download,
    list_files,
    temp_dir,
)
from backend.services.log_manager import create_log_queue, push_log, event_generator

router = APIRouter()


def _download_bucket_folder(bucket: str, folder: str, dest_dir: Path) -> list[Path]:
    """Download all files from a storage folder to a local directory."""
    files = list_files(bucket, folder)
    paths = []
    for f in files:
        name = f.get("name", "")
        if not name or name.endswith("/"):
            continue
        try:
            data = storage_download(bucket, f"{folder}/{name}")
            dest = dest_dir / name
            dest.write_bytes(data)
            paths.append(dest)
        except Exception:
            continue
    return paths


def _run_pipeline_sync(run_id: str, stages: list[str], model_report: str, model_audit: str,
                       input_file_paths: list[Path] = None):
    """Run selected stages of the dev pipeline synchronously."""
    def log(msg: str):
        push_log(run_id, "log", msg)

    sb = get_supabase()

    try:
        # Use provided input files or create empty work dir
        if input_file_paths:
            work_dir = input_file_paths[0].parent
        else:
            work_dir = Path(tempfile.mkdtemp(prefix="pipeline_"))

        # Stage 1: Parse Excel
        if "parse" in stages:
            push_log(run_id, "stage", "Stage 1: Parsing Excel files...")
            from core.parser import parse_all_in_directories
            results = parse_all_in_directories([work_dir], log_callback=log)
            log(f"Parsed {len(results)} file(s)")

        # Stage 2: Business Description
        if "business_desc" in stages:
            push_log(run_id, "stage", "Stage 2: Extracting business description...")
            from core.business_desc import extract_business_description
            try:
                desc = extract_business_description(work_dir, log_callback=log)
                log(f"Description: {desc[:100]}...")
            except Exception as e:
                log(f"Warning: {e}")

        # Stage 3: Generate Report
        if "generate" in stages:
            push_log(run_id, "stage", "Stage 3: Generating report...")
            from core.report_generator import generate_report
            result = generate_report(
                target_inputs_dir=work_dir,
                model=model_report,
                log_callback=log,
            )
            if result["success"]:
                html_content = result.get("html_content", "")
                filename = result.get("report_filename", "report.html")
                # Upload to storage + DB
                storage_upload("reports", f"generated/{filename}",
                               html_content.encode("utf-8"), "text/html")
                sb.table("reports").upsert({
                    "filename": filename,
                    "company_name": result.get("company_name", ""),
                    "storage_path": f"generated/{filename}",
                    "size_bytes": len(html_content.encode("utf-8")),
                    "report_type": "generated",
                }, on_conflict="filename").execute()
                # Write to work_dir so subsequent stages can pick it up
                (work_dir / filename).write_text(html_content, encoding="utf-8")
                log(f"Report: {result['message']}")
            else:
                log(f"Error: {result['message']}")

        # Stage 4: Audit Review
        if "audit" in stages:
            push_log(run_id, "stage", "Stage 4: Running audit review...")
            from core.auditor import audit_report

            # Find HTML and DOCX in work_dir
            html_files = sorted(work_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
            docx_files = sorted(work_dir.glob("*.docx"), key=lambda p: p.stat().st_mtime, reverse=True)

            if html_files and docx_files:
                result = audit_report(
                    report_path=html_files[0],
                    context_docx_path=docx_files[0],
                    model=model_audit,
                    log_callback=log,
                )
                if result["success"]:
                    audit_html = result.get("html_content", "")
                    audit_filename = result.get("filename", "audit.html")
                    storage_upload("reports", f"audit_output/{audit_filename}",
                                   audit_html.encode("utf-8"), "text/html")
                    sb.table("reports").upsert({
                        "filename": audit_filename,
                        "storage_path": f"audit_output/{audit_filename}",
                        "size_bytes": len(audit_html.encode("utf-8")),
                        "report_type": "audit",
                    }, on_conflict="filename").execute()
                    log(f"Audit: {result['message']}")
                else:
                    log(f"Error: {result['message']}")
            else:
                log("Skipping audit: need both HTML report and DOCX context in work dir")

        # Stage 5: Compare Reports
        if "compare" in stages:
            push_log(run_id, "stage", "Stage 5: Comparing reports...")
            from core.comparator import compare_reports

            html_files = sorted(work_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
            human_files = [f for f in work_dir.iterdir()
                           if f.suffix.lower() in [".pdf", ".docx"] and "eval" not in f.stem.lower()]
            afs_files = [f for f in work_dir.glob("*.pdf")]

            if html_files and human_files and afs_files:
                result = compare_reports(
                    human_report_path=human_files[0],
                    llm_report_path=html_files[0],
                    afs_path=afs_files[0],
                    model=model_report,
                    log_callback=log,
                )
                if result["success"]:
                    comp_html = result.get("html_content", "")
                    comp_filename = result.get("filename", "comparison.html")
                    storage_upload("reports", f"eval_output/{comp_filename}",
                                   comp_html.encode("utf-8"), "text/html")
                    sb.table("reports").upsert({
                        "filename": comp_filename,
                        "storage_path": f"eval_output/{comp_filename}",
                        "size_bytes": len(comp_html.encode("utf-8")),
                        "report_type": "comparison",
                    }, on_conflict="filename").execute()
                    log(f"Comparison: {result['message']}")
                else:
                    log(f"Error: {result['message']}")
            else:
                log("Skipping comparison: need HTML report, human report, and AFS PDF")

        # Stage 6: Convert
        if "convert" in stages:
            push_log(run_id, "stage", "Stage 6: Converting reports...")
            from core.converter import convert_all_reports

            html_files = list(work_dir.glob("*.html"))
            html_items = []
            for hf in html_files:
                html_items.append({
                    "html_content": hf.read_text(encoding="utf-8"),
                    "filename": hf.name,
                })

            result = convert_all_reports(html_items=html_items, log_callback=log)

            # Upload converted files
            for jf in result.get("json_files", []):
                fname = jf.get("filename", "report.json")
                storage_upload("reports", f"converted/{fname}",
                               jf["json_str"].encode("utf-8"), "application/json")
                sb.table("reports").upsert({
                    "filename": fname,
                    "storage_path": f"converted/{fname}",
                    "size_bytes": len(jf["json_str"].encode("utf-8")),
                    "report_type": "converted",
                }, on_conflict="filename").execute()

            for df in result.get("docx_files", []):
                fname = df.get("filename", "report.docx")
                storage_upload("reports", f"converted/{fname}",
                               df["docx_bytes"],
                               "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                sb.table("reports").upsert({
                    "filename": fname,
                    "storage_path": f"converted/{fname}",
                    "size_bytes": len(df["docx_bytes"]),
                    "report_type": "converted",
                }, on_conflict="filename").execute()

            log(f"Converted: {len(result.get('json_files', []))} JSON, "
                f"{len(result.get('docx_files', []))} DOCX")

        push_log(run_id, "done", json.dumps({"run_id": run_id, "status": "complete"}))

    except Exception as e:
        push_log(run_id, "error", f"Pipeline error: {e}\n{traceback.format_exc()}")
    finally:
        # Clean up temp work dir
        import shutil
        if work_dir and work_dir.exists() and str(work_dir).startswith(tempfile.gettempdir()):
            shutil.rmtree(str(work_dir), ignore_errors=True)


@router.post("/run", response_model=PipelineRunResponse)
async def run_pipeline(
    stages: str = Form(...),  # Comma-separated: "parse,business_desc,generate,audit,compare,convert"
    model_report: str = Form("gemini-2.5-flash"),
    model_audit: str = Form("gemini-2.5-flash"),
    files: list[UploadFile] = File(default=[]),
):
    """Start a dev pipeline run with selected stages.

    Files are uploaded directly in this request and saved to a temp dir.
    """
    run_id = f"pipeline_{uuid4().hex[:8]}"
    stage_list = [s.strip() for s in stages.split(",") if s.strip()]

    valid_stages = {"parse", "business_desc", "generate", "audit", "compare", "convert"}
    invalid = set(stage_list) - valid_stages
    if invalid:
        raise HTTPException(400, f"Invalid stages: {invalid}")

    # Save uploaded files to temp dir
    input_paths = []
    if files:
        work_dir = Path(tempfile.mkdtemp(prefix="pipeline_"))
        for f in files:
            if f.filename:
                dest = work_dir / f.filename
                dest.write_bytes(await f.read())
                input_paths.append(dest)

    create_log_queue(run_id)

    loop = asyncio.get_event_loop()
    asyncio.ensure_future(
        loop.run_in_executor(
            None, _run_pipeline_sync, run_id, stage_list,
            model_report, model_audit,
            input_paths if input_paths else None,
        )
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
