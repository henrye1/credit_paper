"""Page 1: Run Assessment Pipeline."""

import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from config.settings import (REPORT_INPUTS_DIR, FS_LEARNING_INPUTS_DIR,
                              REPORT_OUTPUT_DIR, AUDIT_LLM_INPUT_DIR,
                              EVAL_INPUT_DIR, MODELS)

st.set_page_config(page_title="Run Assessment", page_icon="▶️", layout="wide")
st.title("Run Assessment")
st.markdown("Upload input files, configure the pipeline, and generate reports.")

# --- File Upload Section ---
st.subheader("1. Input Files")

col_upload1, col_upload2 = st.columns(2)

with col_upload1:
    st.markdown("**Financial Ratio File (.xlsx)**")
    ratio_file = st.file_uploader("Upload Excel ratio file", type=["xlsx"],
                                   key="ratio_upload")
    if ratio_file:
        dest = REPORT_INPUTS_DIR / ratio_file.name
        dest.write_bytes(ratio_file.getvalue())
        st.success(f"Saved: {ratio_file.name}")

    st.markdown("**Audited Financial Statements (.pdf)**")
    pdf_files = st.file_uploader("Upload AFS PDFs", type=["pdf"],
                                  accept_multiple_files=True, key="pdf_upload")
    for pdf in pdf_files:
        dest = REPORT_INPUTS_DIR / pdf.name
        dest.write_bytes(pdf.getvalue())
    if pdf_files:
        st.success(f"Saved {len(pdf_files)} PDF file(s)")

with col_upload2:
    st.markdown("**Business Description (.txt)** *(optional)*")
    desc_file = st.file_uploader("Upload business description", type=["txt"],
                                  key="desc_upload")
    if desc_file:
        dest = REPORT_INPUTS_DIR / "company_business_description.txt"
        dest.write_bytes(desc_file.getvalue())
        st.success("Saved business description")

    st.markdown("**Audit Context (.docx)** *(for Stage 4)*")
    audit_ctx = st.file_uploader("Upload LLM risks research DOCX", type=["docx"],
                                  key="audit_ctx_upload")
    if audit_ctx:
        dest = AUDIT_LLM_INPUT_DIR / audit_ctx.name
        dest.write_bytes(audit_ctx.getvalue())
        st.success(f"Saved: {audit_ctx.name}")

# Show current input files
with st.expander("Current files in report_inputs/"):
    files = list(REPORT_INPUTS_DIR.iterdir())
    if files:
        for f in sorted(files):
            st.text(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB)")
    else:
        st.info("No files yet.")

st.markdown("---")

# --- Pipeline Configuration ---
st.subheader("2. Pipeline Configuration")

col_cfg1, col_cfg2 = st.columns(2)

with col_cfg1:
    stages = st.multiselect(
        "Select stages to run",
        options=[
            "1. Parse Excel to Markdown",
            "2. Extract Business Description",
            "3. Generate Financial Report",
            "4. Audit LLM Review",
            "5. Compare Human vs LLM",
            "6. Convert to DOCX/JSON",
        ],
        default=["3. Generate Financial Report"],
    )

with col_cfg2:
    model_report = st.selectbox("Report Model", [
        "gemini-2.5-pro",
        "gemini-2.5-flash-preview-05-20",
    ], index=0)
    model_audit = st.selectbox("Audit Model", [
        "gemini-2.5-flash-preview-04-17-thinking",
        "gemini-2.5-flash-preview-05-20",
    ], index=0)

# Show few-shot examples
with st.expander("Few-Shot Learning Examples"):
    example_mds = sorted(FS_LEARNING_INPUTS_DIR.glob('*.md'))
    if example_mds:
        for md in example_mds:
            st.text(f"  {md.name}")
    else:
        st.info("No examples loaded. Go to Examples Manager to add some.")

st.markdown("---")

# --- Run Pipeline ---
st.subheader("3. Run")

if st.button("Run Pipeline", type="primary", use_container_width=True):
    log_area = st.empty()
    logs = []

    def log(msg):
        logs.append(msg)
        log_area.code("\n".join(logs), language="text")

    progress = st.progress(0)
    total_stages = len(stages)
    completed = 0

    # Stage 1: Parse
    if "1. Parse Excel to Markdown" in stages:
        with st.status("Stage 1: Parsing Excel files...", expanded=True):
            try:
                from core.parser import parse_all_in_directories
                results = parse_all_in_directories(
                    [REPORT_INPUTS_DIR, FS_LEARNING_INPUTS_DIR],
                    log_callback=log
                )
                log(f"Parsed {len(results)} file(s)")
                st.success(f"Stage 1 complete: {len(results)} file(s) parsed")
            except Exception as e:
                st.error(f"Stage 1 failed: {e}")
                log(f"ERROR: {e}")
        completed += 1
        progress.progress(completed / total_stages)

    # Stage 2: Business Description
    if "2. Extract Business Description" in stages:
        with st.status("Stage 2: Extracting business description...", expanded=True):
            try:
                from core.business_desc import extract_business_description
                desc = extract_business_description(REPORT_INPUTS_DIR, log_callback=log)
                log(f"Description: {desc[:100]}...")
                st.success("Stage 2 complete")
            except Exception as e:
                st.error(f"Stage 2 failed: {e}")
                log(f"ERROR: {e}")
        completed += 1
        progress.progress(completed / total_stages)

    # Stage 3: Generate Report
    if "3. Generate Financial Report" in stages:
        with st.status("Stage 3: Generating financial report...", expanded=True):
            try:
                from core.report_generator import generate_report
                result = generate_report(model=model_report, log_callback=log)
                if result["success"]:
                    st.success(result["message"])
                else:
                    st.error(result["message"])
            except Exception as e:
                st.error(f"Stage 3 failed: {e}")
                log(f"ERROR: {e}")
        completed += 1
        progress.progress(completed / total_stages)

    # Stage 4: Audit
    if "4. Audit LLM Review" in stages:
        with st.status("Stage 4: Running audit review...", expanded=True):
            try:
                from core.auditor import audit_report
                result = audit_report(model=model_audit, log_callback=log)
                if result["success"]:
                    st.success(result["message"])
                else:
                    st.error(result["message"])
            except Exception as e:
                st.error(f"Stage 4 failed: {e}")
                log(f"ERROR: {e}")
        completed += 1
        progress.progress(completed / total_stages)

    # Stage 5: Compare
    if "5. Compare Human vs LLM" in stages:
        with st.status("Stage 5: Comparing reports...", expanded=True):
            try:
                from core.comparator import compare_reports
                result = compare_reports(model=model_report, log_callback=log)
                if result["success"]:
                    st.success(result["message"])
                else:
                    st.error(result["message"])
            except Exception as e:
                st.error(f"Stage 5 failed: {e}")
                log(f"ERROR: {e}")
        completed += 1
        progress.progress(completed / total_stages)

    # Stage 6: Convert
    if "6. Convert to DOCX/JSON" in stages:
        with st.status("Stage 6: Converting reports...", expanded=True):
            try:
                from core.converter import convert_all_reports
                result = convert_all_reports(log_callback=log)
                log(f"Converted: {len(result['json_files'])} JSON, {len(result['docx_files'])} DOCX")
                st.success("Stage 6 complete")
            except Exception as e:
                st.error(f"Stage 6 failed: {e}")
                log(f"ERROR: {e}")
        completed += 1
        progress.progress(completed / total_stages)

    progress.progress(1.0)
    st.balloons()

st.markdown("---")

# --- View Output ---
st.subheader("4. Output Reports")

html_reports = sorted(REPORT_OUTPUT_DIR.glob('*.html'), key=lambda p: p.stat().st_mtime, reverse=True)
if html_reports:
    selected_report = st.selectbox("Select report to view",
                                    [r.name for r in html_reports])
    report_path = REPORT_OUTPUT_DIR / selected_report

    col_view1, col_view2 = st.columns([3, 1])
    with col_view2:
        content = report_path.read_text(encoding='utf-8')
        st.download_button("Download HTML", content, file_name=selected_report,
                          mime="text/html")

    with st.expander("Preview Report", expanded=True):
        st.components.v1.html(content, height=800, scrolling=True)
else:
    st.info("No reports generated yet. Run the pipeline above.")
