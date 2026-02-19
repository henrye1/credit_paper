"""Stage 3: Financial Condition Report generation using Gemini."""

import re
import tempfile
from pathlib import Path

from config.settings import MODELS
from core.gemini_client import GeminiClient, clean_html_response, safe_filename
from core.prompt_builder import build_report_prompt


def _get_numeric_prefix(filename: str) -> str:
    """Extract leading number from filename for matching file pairs."""
    match = re.match(r"^(\d+)\.?\s*", Path(filename).name)
    return match.group(1) if match else None


def _extract_company_name(md_filepath: Path) -> str:
    """Extract clean company name from markdown filename."""
    name = md_filepath.stem
    name = re.sub(r"^\d+\.?\s*", "", name)
    name = re.sub(r"[_.-]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name if name else "Unknown_Company"


def _extract_text_from_file(filepath: Path) -> str:
    """Extract plain text from DOCX or TXT files."""
    if filepath.suffix == '.docx':
        import docx
        doc = docx.Document(filepath)
        return '\n'.join(para.text for para in doc.paragraphs)
    elif filepath.suffix == '.txt':
        return filepath.read_text(encoding='utf-8')
    return ""


def _download_examples_to_tempdir(tmp_dir: Path) -> Path:
    """Download few-shot example files from Supabase storage to a temp dir.

    Returns the temp dir path. Files are named {prefix}. {display_name}.{ext}.
    """
    from backend.services.supabase_client import get_supabase
    from backend.services.storage_helpers import download_file

    sb = get_supabase()
    examples = sb.table("examples").select("prefix, display_name").execute()
    if not examples.data:
        return tmp_dir

    for ex in examples.data:
        prefix = ex["prefix"]
        files_result = (sb.table("example_files")
                        .select("filename, storage_path")
                        .eq("prefix", prefix)
                        .execute())
        for f in files_result.data:
            try:
                data = download_file("examples", f["storage_path"])
                dest = tmp_dir / f["filename"]
                dest.write_bytes(data)
            except Exception:
                continue

    return tmp_dir


def generate_report(target_inputs_dir: Path = None,
                    learning_inputs_dir: Path = None,
                    output_dir: Path = None,
                    api_key: str = None,
                    model: str = None,
                    report_name: str = None,
                    log_callback=None,
                    prompt_set: str = None) -> dict:
    """Generate a Financial Condition Assessment Report.

    Returns dict with keys: 'success', 'html_content', 'report_filename',
    'company_name', 'message'.
    """
    target_dir = target_inputs_dir
    if not target_dir:
        raise ValueError("target_inputs_dir is required")

    model_name = model or MODELS["report_generation"]

    def log(msg):
        if log_callback:
            log_callback(msg)

    client = GeminiClient(api_key)

    try:
        # --- File Discovery ---
        target_md_paths = list(target_dir.glob('*.md'))
        target_pdf_paths = list(target_dir.glob('*.pdf'))
        business_desc_path = target_dir / 'company_business_description.txt'

        if not target_md_paths:
            return {"success": False, "message": "No markdown ratio file found in inputs."}
        if len(target_md_paths) > 1:
            return {"success": False, "message": "Multiple markdown files found. Provide only one."}

        target_md_path = target_md_paths[0]
        company_name = _extract_company_name(target_md_path)
        log(f"Target company: {company_name}")

        # Read business description
        business_desc = ""
        if business_desc_path.exists():
            business_desc = _extract_text_from_file(business_desc_path)
        if not business_desc:
            log("Warning: No business description found. Proceeding without it.")
            business_desc = f"No business description available for {company_name}."

        # --- Upload target files ---
        log("Uploading target files to Gemini...")
        target_md_obj = client.upload_file(target_md_path, f"Target Ratio ({company_name})")
        if not target_md_obj:
            return {"success": False, "message": "Failed to upload target markdown file."}

        target_pdf_objs = []
        for pdf_path in target_pdf_paths:
            obj = client.upload_file(pdf_path, f"Target AFS PDF ({company_name})")
            if obj:
                target_pdf_objs.append(obj)

        # --- Download and upload learning examples ---
        example_files = []
        if learning_inputs_dir:
            learning_dir = learning_inputs_dir
        else:
            # Download examples from Supabase
            learning_dir = Path(tempfile.mkdtemp(prefix="examples_"))
            _download_examples_to_tempdir(learning_dir)

        if learning_dir.exists():
            learning_md_paths = sorted(list(learning_dir.glob('*.md')))
            learning_pdf_map = {
                _get_numeric_prefix(p.name): p
                for p in learning_dir.glob('*.pdf')
                if _get_numeric_prefix(p.name)
            }

            for md_path in learning_md_paths:
                prefix = _get_numeric_prefix(md_path.name)
                if prefix and prefix in learning_pdf_map:
                    pdf_path = learning_pdf_map[prefix]
                    ex_name = _extract_company_name(md_path)
                    log(f"Uploading example pair: {md_path.name} + {pdf_path.name}")
                    md_obj = client.upload_file(md_path, f"Example MD ({ex_name})")
                    pdf_obj = client.upload_file(pdf_path, f"Example PDF ({ex_name})")
                    if md_obj and pdf_obj:
                        example_files.append({
                            'md_file_obj': md_obj,
                            'pdf_file_obj': pdf_obj,
                            'name': ex_name,
                        })

        # --- Build prompt and call API ---
        log("Building prompt from YAML sections...")
        if prompt_set:
            log(f"Using prompt set: {prompt_set}")
        prompt_contents = build_report_prompt(
            company_name=company_name,
            business_desc_content=business_desc,
            target_md_file_obj=target_md_obj,
            target_pdf_file_objs=target_pdf_objs,
            example_files_info=example_files,
            prompt_set=prompt_set,
        )

        log(f"Sending request to Gemini ({model_name})...")
        html_report = client.generate_content(model=model_name, contents=prompt_contents)
        cleaned_html = clean_html_response(html_report)

        # --- Determine filename ---
        if report_name:
            filename = f"{safe_filename(report_name)}.html"
        else:
            filename = f"{safe_filename(company_name)}_Financial_Condition_Report.html"

        # Write to output_dir if provided (for pipeline/legacy use)
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / filename
            output_path.write_text(cleaned_html, encoding='utf-8')
            log(f"Report saved to: {output_path}")

        return {
            "success": True,
            "html_content": cleaned_html,
            "report_filename": filename,
            "company_name": company_name,
            "message": f"Report generated successfully: {filename}",
        }

    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}

    finally:
        client.cleanup_files()
        # Clean up temp examples dir if we created one
        if not learning_inputs_dir and learning_dir and learning_dir.exists():
            import shutil
            shutil.rmtree(str(learning_dir), ignore_errors=True)
