"""Page 1: Quick Assessment - Upload files and generate a report in one click."""

import sys
import shutil
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from config.settings import (REPORT_OUTPUT_DIR, MODELS, REPORT_INPUTS_DIR,
                              ASSESSMENTS_DIR, SUPPORTED_PARSE_EXTENSIONS)

st.set_page_config(page_title="Quick Assessment", page_icon="⚡", layout="wide")
st.title("Quick Assessment")
st.markdown("Upload your Excel ratio file and AFS PDFs, then generate a complete "
            "financial condition assessment report in one click.")

# --- Session state initialisation ---
if "current_report_path" not in st.session_state:
    st.session_state.current_report_path = None
if "current_report_name" not in st.session_state:
    st.session_state.current_report_name = None

st.markdown("---")

# --- File Upload ---
st.subheader("1. Upload Files")

col_up1, col_up2 = st.columns(2)

with col_up1:
    st.markdown("**Financial Ratio File (.xlsx / .xlsm)** *required*")
    ratio_file = st.file_uploader("Upload Excel ratio file", type=["xlsx", "xlsm"],
                                   key="quick_ratio")

with col_up2:
    st.markdown("**Audited Financial Statements (.pdf)** *required*")
    pdf_files = st.file_uploader("Upload AFS PDFs", type=["pdf"],
                                  accept_multiple_files=True, key="quick_pdfs")

st.markdown("---")

# --- Configuration ---
st.subheader("2. Configuration")

col_cfg1, col_cfg2 = st.columns(2)

with col_cfg1:
    model_choice = st.selectbox("Report Generation Model", [
        "gemini-2.5-flash",
        "gemini-2.5-pro (requires billing)",
    ], index=0)
    # Strip the hint suffix if user selects the pro option
    if model_choice.startswith("gemini-2.5-pro"):
        model_choice = "gemini-2.5-pro"

with col_cfg2:
    skip_biz_desc = st.checkbox(
        "Skip business description extraction",
        value=False,
        help="If checked, the report will be generated without a web-scraped business description."
    )

st.markdown("---")

# --- Generate ---
st.subheader("3. Generate Report")

can_run = ratio_file is not None and len(pdf_files) > 0
if not can_run:
    st.info("Upload at least one Excel ratio file and one PDF to proceed.")

if st.button("Generate Report", type="primary", use_container_width=True, disabled=not can_run):
    # Clear previous session report
    st.session_state.current_report_path = None
    st.session_state.current_report_name = None

    log_area = st.empty()
    logs = []

    def log(msg):
        logs.append(msg)
        log_area.code("\n".join(logs), language="text")

    progress = st.progress(0)

    # Clean the working directory of previous files (preserve cached business descriptions)
    work_dir = REPORT_INPUTS_DIR
    for old_file in work_dir.iterdir():
        if old_file.is_file() and old_file.suffix.lower() in ['.xlsx', '.xlsm', '.pdf', '.md']:
            old_file.unlink()

    # Save uploaded files
    log("Saving uploaded files...")
    ratio_dest = work_dir / ratio_file.name
    ratio_dest.write_bytes(ratio_file.getvalue())
    log(f"  Saved: {ratio_file.name}")

    for pdf in pdf_files:
        pdf_dest = work_dir / pdf.name
        pdf_dest.write_bytes(pdf.getvalue())
        log(f"  Saved: {pdf.name}")

    progress.progress(0.10)

    # --- Stage 1: Parse Excel to Markdown ---
    with st.status("Parsing Excel file...", expanded=True):
        try:
            from core.parser import parse_excel_to_markdown
            md_path = parse_excel_to_markdown(ratio_dest, log_callback=log)
            log(f"Parsed -> {md_path.name}")
            st.success("Excel parsed to Markdown")
        except Exception as e:
            st.error(f"Parsing failed: {e}")
            log(f"ERROR: {e}")
            st.stop()

    progress.progress(0.30)

    # --- Stage 2: Extract Business Description ---
    if not skip_biz_desc:
        with st.status("Extracting business description...", expanded=True):
            try:
                from core.business_desc import extract_business_description
                desc = extract_business_description(work_dir, log_callback=log)
                log(f"Description: {desc[:100]}...")
                st.success("Business description extracted")
            except Exception as e:
                log(f"Warning: Business description extraction failed: {e}")
                log("Continuing without business description...")
                st.warning(f"Business description extraction failed: {e}. Continuing without it.")
    else:
        log("Skipping business description extraction (user opted out).")

    progress.progress(0.50)

    # --- Stage 3: Generate Report ---
    with st.status("Generating financial condition report...", expanded=True):
        try:
            from core.report_generator import generate_report
            result = generate_report(model=model_choice, log_callback=log)
            if result["success"]:
                st.success(result["message"])
                log(f"Report generated: {result.get('output_path', '')}")
            else:
                st.error(result["message"])
                log(f"ERROR: {result['message']}")
                st.stop()
        except Exception as e:
            st.error(f"Report generation failed: {e}")
            log(f"ERROR: {e}")
            st.stop()

    progress.progress(0.85)

    # --- Stage 4: Archive the assessment ---
    with st.status("Archiving assessment...", expanded=False):
        try:
            # Find the generated report
            html_reports = sorted(REPORT_OUTPUT_DIR.glob('*.html'),
                                  key=lambda p: p.stat().st_mtime, reverse=True)
            if html_reports:
                report_path = html_reports[0]

                # Create assessment folder: CompanyName_YYYYMMDD_HHMMSS
                company_stem = ratio_file.name.rsplit('.', 1)[0]
                # Clean the name for use as a folder name
                safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in company_stem).strip()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                assessment_dir = ASSESSMENTS_DIR / f"{safe_name}_{timestamp}"
                assessment_dir.mkdir(parents=True, exist_ok=True)

                # Copy inputs (Excel, PDFs, markdown, business description)
                inputs_subdir = assessment_dir / "inputs"
                inputs_subdir.mkdir(exist_ok=True)
                for f in work_dir.iterdir():
                    if f.is_file():
                        shutil.copy2(f, inputs_subdir / f.name)

                # Copy generated report
                report_dest = assessment_dir / report_path.name
                shutil.copy2(report_path, report_dest)

                # Store in session state for immediate preview
                st.session_state.current_report_path = str(report_dest)
                st.session_state.current_report_name = report_path.name

                log(f"Assessment archived to: {assessment_dir.name}/")
                st.success(f"Assessment saved to: {assessment_dir.name}/")
            else:
                log("Warning: No HTML report found to archive.")
        except Exception as e:
            log(f"Warning: Archiving failed: {e}")

    progress.progress(1.0)
    st.balloons()

st.markdown("---")

# --- Current Report Preview ---
st.subheader("4. Current Report")

if st.session_state.current_report_path and Path(st.session_state.current_report_path).exists():
    report_path = Path(st.session_state.current_report_path)
    content = report_path.read_text(encoding='utf-8')

    col_dl1, col_dl2 = st.columns([3, 1])
    with col_dl2:
        st.download_button("Download HTML", content,
                          file_name=st.session_state.current_report_name,
                          mime="text/html")

    with st.expander("Preview Report", expanded=True):
        st.components.v1.html(content, height=800, scrolling=True)
else:
    st.info("No report for current session. Upload files and click Generate above.")

st.markdown("---")

# --- Past Assessments ---
st.subheader("5. Past Assessments")

assessment_dirs = sorted(
    [d for d in ASSESSMENTS_DIR.iterdir() if d.is_dir()],
    key=lambda d: d.stat().st_mtime, reverse=True
)

if assessment_dirs:
    selected_name = st.selectbox(
        "Select a past assessment",
        [d.name for d in assessment_dirs],
        key="past_assessment"
    )
    selected_dir = ASSESSMENTS_DIR / selected_name

    # Find the HTML report in this assessment
    past_reports = list(selected_dir.glob('*.html'))
    if past_reports:
        past_report = past_reports[0]
        past_content = past_report.read_text(encoding='utf-8')

        col_p1, col_p2 = st.columns([3, 1])
        with col_p2:
            st.download_button("Download", past_content,
                              file_name=past_report.name,
                              mime="text/html", key="past_dl")

        # Show input files in this assessment
        inputs_dir = selected_dir / "inputs"
        if inputs_dir.exists():
            input_files = [f.name for f in inputs_dir.iterdir() if f.is_file()]
            if input_files:
                st.caption(f"Input files: {', '.join(input_files)}")

        with st.expander("Preview Past Report", expanded=False):
            st.components.v1.html(past_content, height=800, scrolling=True)
    else:
        st.warning("No HTML report found in this assessment folder.")
else:
    st.info("No past assessments yet.")
