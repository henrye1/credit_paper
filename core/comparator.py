"""Stage 5: Compare human-created and LLM-generated financial reports."""

import re
import time
from pathlib import Path

from config.settings import MODELS
from core.gemini_client import GeminiClient, clean_html_response, safe_filename
from core.prompt_builder import build_comparison_prompt


def compare_reports(human_report_path: Path = None,
                    llm_report_path: Path = None,
                    afs_path: Path = None,
                    output_dir: Path = None,
                    api_key: str = None,
                    model: str = None,
                    log_callback=None) -> dict:
    """Compare human and LLM financial reports.

    Returns dict with keys: 'success', 'html_content', 'output_path', 'message'.
    When output_dir is provided, also writes to disk.
    """
    model_name = model or MODELS["comparison"]

    def log(msg):
        if log_callback:
            log_callback(msg)

    if not human_report_path or not human_report_path.exists():
        return {"success": False, "message": "No human-created report provided."}
    if not llm_report_path or not llm_report_path.exists():
        return {"success": False, "message": "No LLM-generated HTML report provided."}
    if not afs_path or not afs_path.exists():
        return {"success": False, "message": "No audited financial statements PDF provided."}

    log(f"Human report: {human_report_path.name}")
    log(f"LLM report: {llm_report_path.name}")
    log(f"AFS: {afs_path.name}")

    llm_html_content = llm_report_path.read_text(encoding='utf-8')

    client = GeminiClient(api_key)

    try:
        # Upload files
        log("Uploading files to Gemini...")
        human_file = client.upload_file(human_report_path, "Human Report")
        afs_file = client.upload_file(afs_path, "Audited Financial Statements")

        if not human_file or not afs_file:
            return {"success": False, "message": "Failed to upload files to Gemini API."}

        time.sleep(5)

        # Build prompt
        prompt_parts = build_comparison_prompt(
            llm_report_content=llm_html_content,
            human_report_file_obj=human_file,
            audited_statements_file_obj=afs_file,
        )

        log(f"Sending comparison request to Gemini ({model_name})...")
        raw_html = client.generate_content(model=model_name, contents=prompt_parts)
        comparison_html = clean_html_response(raw_html)

        # Extract company name from LLM filename for output naming
        company_raw = re.match(r"^(.*?)(?:_Financial_Condition_Report)?\.html$",
                               llm_report_path.name)
        company_name = company_raw.group(1) if company_raw else llm_report_path.stem
        filename = f"{safe_filename(company_name)}_eval.html"

        output_path = None
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / filename
            output_path.write_text(comparison_html, encoding='utf-8')
            log(f"Comparison report saved to: {output_path}")

        return {
            "success": True,
            "html_content": comparison_html,
            "output_path": output_path,
            "filename": filename,
            "message": f"Comparison report generated: {filename}",
        }

    except Exception as e:
        return {"success": False, "message": f"Comparison error: {e}"}

    finally:
        client.cleanup_files()
