"""Stage 4: LLM Audit Review of generated financial reports."""

import re
from pathlib import Path

import docx

from config.settings import MODELS, REPORT_OUTPUT_DIR, AUDIT_LLM_INPUT_DIR, AUDIT_LLM_OUTPUT_DIR
from core.gemini_client import GeminiClient, clean_html_response, safe_filename
from core.prompt_builder import build_audit_prompt


def _read_html(filepath: Path) -> str:
    """Read HTML file content."""
    return filepath.read_text(encoding='utf-8')


def _extract_text_from_docx(filepath: Path) -> str:
    """Extract plain text from a DOCX file."""
    doc = docx.Document(filepath)
    return '\n\n'.join(para.text for para in doc.paragraphs)


def _find_latest(directory: Path, pattern: str) -> Path:
    """Find the most recently modified file matching a glob pattern."""
    files = list(directory.glob(pattern))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def audit_report(report_path: Path = None,
                 context_docx_path: Path = None,
                 output_dir: Path = None,
                 api_key: str = None,
                 model: str = None,
                 log_callback=None) -> dict:
    """Run LLM audit review on a generated HTML report.

    Returns dict with keys: 'success', 'output_path', 'message'.
    """
    out_dir = output_dir or AUDIT_LLM_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    model_name = model or MODELS["audit_review"]

    def log(msg):
        if log_callback:
            log_callback(msg)

    # Find report to audit
    if not report_path:
        report_path = _find_latest(AUDIT_LLM_INPUT_DIR, '*.html')
        if not report_path:
            report_path = _find_latest(REPORT_OUTPUT_DIR, '*.html')
    if not report_path or not report_path.exists():
        return {"success": False, "message": "No HTML report found to audit."}

    # Find context DOCX
    if not context_docx_path:
        context_docx_path = _find_latest(AUDIT_LLM_INPUT_DIR, '*.docx')
    if not context_docx_path or not context_docx_path.exists():
        return {"success": False, "message": "No DOCX context file found for audit."}

    log(f"Auditing: {report_path.name}")
    log(f"Context: {context_docx_path.name}")

    html_content = _read_html(report_path)
    risk_research = _extract_text_from_docx(context_docx_path)

    if not html_content:
        return {"success": False, "message": f"Failed to read HTML: {report_path.name}"}
    if not risk_research:
        return {"success": False, "message": f"Failed to read DOCX: {context_docx_path.name}"}

    # Build prompt from YAML sections
    prompt_contents = build_audit_prompt(
        html_report_content=html_content,
        llm_risk_research_text=risk_research,
        report_filename=report_path.name,
    )

    try:
        client = GeminiClient(api_key)
        log(f"Sending audit request to Gemini ({model_name})...")
        audit_html = client.generate_content(
            model=model_name,
            contents=prompt_contents,
            temperature=0.2,
        )

        cleaned_html = clean_html_response(audit_html)

        # Save audit report
        stem = safe_filename(report_path.stem)
        filename = f"Audit_Review_of_{stem}.html"
        output_path = out_dir / filename
        output_path.write_text(cleaned_html, encoding='utf-8')
        log(f"Audit review saved to: {output_path}")

        return {
            "success": True,
            "output_path": output_path,
            "message": f"Audit review generated: {filename}",
        }

    except Exception as e:
        return {"success": False, "message": f"Audit error: {e}"}
