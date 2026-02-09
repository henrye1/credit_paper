"""Page 1: Quick Assessment - Upload, generate, review, and approve a report."""

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

# ──────────────────────────────────────────────────────────────────────────────
# Session state initialisation
# ──────────────────────────────────────────────────────────────────────────────
_DEFAULTS = {
    "current_report_path": None,
    "current_report_name": None,
    "assessment_complete": False,
    # Review mode state
    "review_mode": False,
    "parsed_report": None,
    "selected_review_section": 0,
    "section_chat_histories": {},
    "ai_pending_html": {},
    "review_model_choice": "gemini-2.5-flash",
}
for key, default in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ──────────────────────────────────────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────────────────────────────────────

def _archive_current():
    """Archive the current working files + report to assessments folder."""
    work_dir = REPORT_INPUTS_DIR
    html_reports = sorted(REPORT_OUTPUT_DIR.glob('*.html'),
                          key=lambda p: p.stat().st_mtime, reverse=True)
    if not html_reports:
        return None

    report_path = html_reports[0]

    excel_files = [f for f in work_dir.iterdir()
                   if f.is_file() and f.suffix.lower() in ['.xlsx', '.xlsm']]
    company_stem = excel_files[0].stem if excel_files else "Assessment"

    safe_name = "".join(c for c in company_stem if c.isalnum() or c == ' ').strip()
    safe_name = safe_name[:30].strip()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    assessment_dir = ASSESSMENTS_DIR / f"{safe_name}_{timestamp}"
    assessment_dir.mkdir(parents=True, exist_ok=True)

    inputs_subdir = assessment_dir / "inputs"
    inputs_subdir.mkdir(exist_ok=True)
    for f in work_dir.iterdir():
        if f.is_file():
            dest_name = f.name
            if len(dest_name) > 60:
                dest_name = f.stem[:50] + f.suffix
            shutil.copy2(str(f), str(inputs_subdir / dest_name))

    report_dest_name = report_path.name
    if len(report_dest_name) > 80:
        report_dest_name = report_path.stem[:70] + report_path.suffix
    report_dest = assessment_dir / report_dest_name
    shutil.copy2(str(report_path), str(report_dest))

    return assessment_dir.name


def _clean_working_dir():
    """Remove all working files from report_inputs."""
    for old_file in REPORT_INPUTS_DIR.iterdir():
        if old_file.is_file() and old_file.suffix.lower() in ['.xlsx', '.xlsm', '.pdf', '.md', '.txt']:
            old_file.unlink()


def _reset_all_state():
    """Reset all session state to defaults."""
    for key, default in _DEFAULTS.items():
        st.session_state[key] = default


def _start_new_assessment():
    """Archive current run, clean working dir, reset session state."""
    if st.session_state.current_report_path:
        _archive_current()
    _clean_working_dir()
    _reset_all_state()


def _discard_current_assessment():
    """Discard the current assessment: delete its archive and reset."""
    report_path = st.session_state.get("current_report_path")
    if report_path:
        archive_dir = Path(report_path).parent
        if archive_dir.exists() and str(ASSESSMENTS_DIR) in str(archive_dir):
            shutil.rmtree(str(archive_dir), ignore_errors=True)
    _clean_working_dir()
    _reset_all_state()


def _advance_to_next_unapproved():
    """Move selection to the next unapproved section."""
    sections = st.session_state.parsed_report["sections"]
    current = st.session_state.selected_review_section
    for offset in range(1, len(sections) + 1):
        candidate = (current + offset) % len(sections)
        if sections[candidate]["status"] != "approved":
            st.session_state.selected_review_section = candidate
            return


def _finalize_report():
    """Reassemble sections into final HTML, save, archive, transition to completed."""
    from core.report_sections import reassemble_report_html

    parsed = st.session_state.parsed_report
    final_html = reassemble_report_html(parsed)

    html_reports = sorted(REPORT_OUTPUT_DIR.glob('*.html'),
                          key=lambda p: p.stat().st_mtime, reverse=True)
    if html_reports:
        output_path = html_reports[0]
        output_path.write_text(final_html, encoding='utf-8')

    archive_name = _archive_current()
    if archive_name:
        archived_html = list((ASSESSMENTS_DIR / archive_name).glob('*.html'))
        if archived_html and html_reports:
            st.session_state.current_report_path = str(archived_html[0])
            st.session_state.current_report_name = html_reports[0].name

    st.session_state.assessment_complete = True
    st.session_state.review_mode = False
    st.session_state.parsed_report = None
    st.session_state.section_chat_histories = {}
    st.session_state.ai_pending_html = {}


# ──────────────────────────────────────────────────────────────────────────────
# Past Assessments widget (shared)
# ──────────────────────────────────────────────────────────────────────────────

def _render_past_assessments(key_suffix=""):
    """Render the past assessments browser."""
    st.subheader("Past Assessments")
    assessment_dirs = sorted(
        [d for d in ASSESSMENTS_DIR.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime, reverse=True
    )
    if assessment_dirs:
        selected_name = st.selectbox(
            "Select a past assessment",
            [d.name for d in assessment_dirs],
            key=f"past_assessment{key_suffix}"
        )
        selected_dir = ASSESSMENTS_DIR / selected_name
        past_reports = list(selected_dir.glob('*.html'))
        if past_reports:
            past_report = past_reports[0]
            past_content = past_report.read_text(encoding='utf-8')
            col_p1, col_p2 = st.columns([3, 1])
            with col_p2:
                st.download_button("Download", past_content,
                                  file_name=past_report.name,
                                  mime="text/html", key=f"past_dl{key_suffix}")
            inputs_dir = selected_dir / "inputs"
            if inputs_dir.exists():
                input_files = [f.name for f in inputs_dir.iterdir() if f.is_file()]
                if input_files:
                    st.caption(f"Input files: {', '.join(input_files)}")
            with st.expander("Preview Past Report", expanded=False):
                st.components.v1.html(past_content, height=800, scrolling=True)
    else:
        st.info("No past assessments yet.")


# ──────────────────────────────────────────────────────────────────────────────
# STATE 3: Finalized / Completed view
# ──────────────────────────────────────────────────────────────────────────────

def _render_completed_view():
    report_path = Path(st.session_state.current_report_path)
    if not report_path.exists():
        st.error("Report file not found. Starting fresh.")
        _reset_all_state()
        st.rerun()
        return

    st.success(f"Assessment complete: {st.session_state.current_report_name}")
    content = report_path.read_text(encoding='utf-8')

    col_dl, col_keep, col_discard = st.columns([2, 1, 1])
    with col_dl:
        st.download_button("Download HTML Report", content,
                          file_name=st.session_state.current_report_name,
                          mime="text/html", use_container_width=True)
    with col_keep:
        if st.button("Save & New", type="primary", use_container_width=True,
                     help="Keep this report and start a new assessment"):
            _start_new_assessment()
            st.rerun()
    with col_discard:
        if st.button("Discard", type="secondary", use_container_width=True,
                     help="Delete this report and start over"):
            _discard_current_assessment()
            st.rerun()

    with st.expander("Preview Report", expanded=True):
        st.components.v1.html(content, height=800, scrolling=True)

    st.markdown("---")
    _render_past_assessments(key_suffix="_complete")


# ──────────────────────────────────────────────────────────────────────────────
# STATE 2: Review Mode
# ──────────────────────────────────────────────────────────────────────────────

def _render_review_mode():
    from core.report_sections import (section_html_to_text, text_to_section_html,
                                       reassemble_report_html, generate_section_update)

    sections = st.session_state.parsed_report["sections"]
    approved_count = sum(1 for s in sections if s["status"] == "approved")
    total_count = len(sections)

    # --- Header ---
    st.subheader("Review & Approve Report Sections")

    # Progress
    progress_pct = approved_count / total_count if total_count > 0 else 0
    st.progress(progress_pct)

    # Global actions
    col_progress, col_approve_all, col_finalize, col_discard_rev = st.columns([2, 1, 1, 1])
    with col_progress:
        st.caption(f"{approved_count} of {total_count} sections approved")
    with col_approve_all:
        remaining = total_count - approved_count
        if st.button(f"Approve All ({remaining})",
                     disabled=remaining == 0, type="secondary",
                     use_container_width=True):
            for s in sections:
                if s["status"] != "approved":
                    s["status"] = "approved"
            st.rerun()
    with col_finalize:
        if st.button("Finalize Report", type="primary",
                     disabled=approved_count < total_count,
                     use_container_width=True):
            _finalize_report()
            st.rerun()
    with col_discard_rev:
        if st.button("Discard", type="secondary", use_container_width=True):
            _reset_all_state()
            _clean_working_dir()
            st.rerun()

    st.markdown("---")

    # --- Section selector ---
    section_options = []
    for i, s in enumerate(sections):
        if s["status"] == "approved":
            icon = "\u2705"
        elif s["html"] != s["original_html"]:
            icon = "\u270E"
        else:
            icon = "\u25CB"
        section_options.append(f"{icon}  {s['title']}")

    col_sel, col_nav = st.columns([4, 1])
    with col_sel:
        selected_idx = st.selectbox(
            "Select section to review",
            range(len(sections)),
            index=st.session_state.selected_review_section,
            format_func=lambda i: section_options[i],
            key="section_selector"
        )
        if selected_idx != st.session_state.selected_review_section:
            st.session_state.selected_review_section = selected_idx
            st.rerun()

    with col_nav:
        col_prev, col_next = st.columns(2)
        with col_prev:
            if st.button("\u25C0 Prev", use_container_width=True,
                         disabled=selected_idx == 0):
                st.session_state.selected_review_section = selected_idx - 1
                st.rerun()
        with col_next:
            if st.button("Next \u25B6", use_container_width=True,
                         disabled=selected_idx >= len(sections) - 1):
                st.session_state.selected_review_section = selected_idx + 1
                st.rerun()

    idx = st.session_state.selected_review_section
    section = sections[idx]
    current_html = section["html"]

    # Status badge
    if section["status"] == "approved":
        st.success(f"**{section['title']}** — Approved")
    elif section["html"] != section["original_html"]:
        st.info(f"**{section['title']}** — Modified (needs approval)")
    else:
        st.warning(f"**{section['title']}** — Pending review")

    # --- Section preview ---
    head_html = st.session_state.parsed_report.get("head_html", "")
    preview_doc = (
        f'<!DOCTYPE html><html><head>{head_html}</head>'
        f'<body style="padding:20px;">{current_html}</body></html>'
    )
    st.components.v1.html(preview_doc, height=500, scrolling=True)

    # --- Approve / Reset buttons ---
    col_approve, col_reset = st.columns(2)
    with col_approve:
        approve_label = "Approve Section" if section["status"] != "approved" else "Already Approved"
        if st.button(approve_label, type="primary",
                     key=f"approve_{idx}", use_container_width=True,
                     disabled=section["status"] == "approved"):
            section["status"] = "approved"
            _advance_to_next_unapproved()
            st.rerun()
    with col_reset:
        can_reset = (section["html"] != section["original_html"]
                     or section["status"] != "pending")
        if st.button("Reset to Original", key=f"reset_{idx}",
                     use_container_width=True, disabled=not can_reset):
            section["html"] = section["original_html"]
            section["status"] = "pending"
            if idx in st.session_state.ai_pending_html:
                del st.session_state.ai_pending_html[idx]
            st.rerun()

    st.markdown("---")

    # --- Editing tools ---
    tab_edit, tab_ai = st.tabs(["Edit Content", "AI Update"])

    # ── TAB 1: Edit readable text ──
    with tab_edit:
        st.caption("Edit the section content below. Headings use ## / ### / #### markers. "
                   "Tables use | pipe | format. Use **bold** for emphasis.")

        current_text = section_html_to_text(current_html)
        edited_text = st.text_area(
            "Section content",
            value=current_text,
            height=400,
            key=f"edit_text_{idx}",
            label_visibility="collapsed",
        )

        has_changes = (edited_text != current_text)
        if has_changes:
            st.caption("You have unsaved changes.")

        col_apply, col_discard_edit = st.columns(2)
        with col_apply:
            if st.button("Apply Changes", type="primary",
                         key=f"apply_edit_{idx}",
                         use_container_width=True,
                         disabled=not has_changes):
                new_html = text_to_section_html(edited_text, section["original_html"])
                section["html"] = new_html
                if section["status"] == "approved":
                    section["status"] = "pending"
                st.rerun()
        with col_discard_edit:
            if st.button("Discard Changes", key=f"discard_edit_{idx}",
                         use_container_width=True, disabled=not has_changes):
                st.rerun()

    # ── TAB 2: AI-powered update ──
    with tab_ai:
        st.caption("Describe what you want changed. Optionally upload additional evidence "
                   "for the AI to reference.")

        evidence_files = st.file_uploader(
            "Additional evidence (optional)",
            type=["pdf", "docx", "txt", "xlsx"],
            accept_multiple_files=True,
            key=f"ai_evidence_{idx}"
        )

        instruction = st.text_area(
            "What should be updated?",
            placeholder="e.g., Update the profitability analysis to reflect the "
                        "Q4 2024 results from the attached PDF.",
            height=120,
            key=f"ai_instruction_{idx}",
            label_visibility="collapsed",
        )

        col_gen, col_ctx = st.columns([2, 1])
        with col_ctx:
            include_full_context = st.checkbox(
                "Include full report context",
                value=False,
                key=f"ai_context_{idx}",
                help="Sends the entire report to the AI for better coherence (slower)."
            )
        with col_gen:
            if st.button("Update with AI", type="primary",
                         key=f"ai_generate_{idx}",
                         use_container_width=True,
                         disabled=not instruction.strip()):
                with st.spinner("AI is updating the section..."):
                    temp_paths = []
                    if evidence_files:
                        for ef in evidence_files:
                            temp_path = REPORT_INPUTS_DIR / f"_temp_evidence_{ef.name}"
                            temp_path.write_bytes(ef.getvalue())
                            temp_paths.append(temp_path)

                    full_context = None
                    if include_full_context:
                        full_context = reassemble_report_html(
                            st.session_state.parsed_report
                        )

                    result = generate_section_update(
                        section_html=current_html,
                        instruction=instruction,
                        evidence_files=temp_paths if temp_paths else None,
                        full_report_context=full_context,
                        model=st.session_state.review_model_choice,
                    )

                    for tp in temp_paths:
                        if tp.exists():
                            tp.unlink()

                    if result["success"]:
                        st.session_state.ai_pending_html[idx] = result["updated_html"]
                        if idx not in st.session_state.section_chat_histories:
                            st.session_state.section_chat_histories[idx] = []
                        st.session_state.section_chat_histories[idx].append(
                            {"role": "user", "content": instruction}
                        )
                        st.session_state.section_chat_histories[idx].append(
                            {"role": "assistant",
                             "content": "Section updated. Review the proposed changes below."}
                        )
                        st.rerun()
                    else:
                        st.error(f"AI update failed: {result['message']}")

        # --- Pending AI proposal (governance gate) ---
        if idx in st.session_state.ai_pending_html:
            st.markdown("---")
            st.markdown("#### Proposed Changes")
            st.warning("Review the AI-generated update before accepting.")

            proposed_html = st.session_state.ai_pending_html[idx]
            preview_proposed = (
                f'<!DOCTYPE html><html><head>{head_html}</head>'
                f'<body style="padding:20px;">{proposed_html}</body></html>'
            )
            st.components.v1.html(preview_proposed, height=400, scrolling=True)

            col_accept, col_reject = st.columns(2)
            with col_accept:
                if st.button("Accept Changes", type="primary",
                             key=f"ai_accept_{idx}",
                             use_container_width=True):
                    section["html"] = proposed_html
                    if section["status"] == "approved":
                        section["status"] = "pending"
                    del st.session_state.ai_pending_html[idx]
                    st.rerun()
            with col_reject:
                if st.button("Reject Changes", key=f"ai_reject_{idx}",
                             use_container_width=True):
                    del st.session_state.ai_pending_html[idx]
                    st.rerun()

        # --- Chat history ---
        if idx in st.session_state.section_chat_histories:
            with st.expander("AI Conversation History", expanded=False):
                for msg in st.session_state.section_chat_histories[idx]:
                    with st.chat_message(msg["role"]):
                        st.write(msg["content"])


# ──────────────────────────────────────────────────────────────────────────────
# STATE 1: Upload & Generate
# ──────────────────────────────────────────────────────────────────────────────

def _render_upload_and_generate():
    st.markdown("Upload your Excel ratio file and AFS PDFs, then generate a complete "
                "financial condition assessment report.")

    st.markdown("---")

    # --- File Upload ---
    st.subheader("1. Upload Files")
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        st.markdown("**Financial Ratio File (.xlsx / .xlsm)** *required*")
        ratio_file = st.file_uploader("Upload Excel ratio file",
                                       type=["xlsx", "xlsm"],
                                       key="quick_ratio")
    with col_up2:
        st.markdown("**Audited Financial Statements (.pdf)** *required*")
        pdf_files = st.file_uploader("Upload AFS PDFs", type=["pdf"],
                                      accept_multiple_files=True,
                                      key="quick_pdfs")

    st.markdown("---")

    # --- Configuration ---
    st.subheader("2. Configuration")
    col_cfg1, col_cfg2 = st.columns(2)
    with col_cfg1:
        model_choice = st.selectbox("Report Generation Model", [
            "gemini-2.5-flash",
            "gemini-2.5-pro (requires billing)",
        ], index=0)
        if model_choice.startswith("gemini-2.5-pro"):
            model_choice = "gemini-2.5-pro"
    with col_cfg2:
        skip_biz_desc = st.checkbox(
            "Skip business description extraction",
            value=False,
            help="If checked, the report will be generated without a "
                 "web-scraped business description."
        )

    st.markdown("---")

    # --- Generate ---
    st.subheader("3. Generate Report")
    can_run = ratio_file is not None and len(pdf_files) > 0
    if not can_run:
        st.info("Upload at least one Excel ratio file and one PDF to proceed.")

    if st.button("Generate Report", type="primary", use_container_width=True,
                 disabled=not can_run):
        log_area = st.empty()
        logs = []

        def log(msg):
            logs.append(msg)
            log_area.code("\n".join(logs), language="text")

        progress = st.progress(0)

        # Clean working directory
        work_dir = REPORT_INPUTS_DIR
        for old_file in work_dir.iterdir():
            if old_file.is_file() and old_file.suffix.lower() in ['.xlsx', '.xlsm', '.pdf', '.md']:
                old_file.unlink()

        log("Saving uploaded files...")
        ratio_dest = work_dir / ratio_file.name
        ratio_dest.write_bytes(ratio_file.getvalue())
        log(f"  Saved: {ratio_file.name}")
        for pdf in pdf_files:
            pdf_dest = work_dir / pdf.name
            pdf_dest.write_bytes(pdf.getvalue())
            log(f"  Saved: {pdf.name}")
        progress.progress(0.10)

        # Stage 1: Parse Excel
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

        # Stage 2: Business Description
        if not skip_biz_desc:
            with st.status("Extracting business description...", expanded=True):
                try:
                    from core.business_desc import extract_business_description
                    desc = extract_business_description(work_dir, log_callback=log)
                    log(f"Description: {desc[:100]}...")
                    st.success("Business description extracted")
                except Exception as e:
                    log(f"Warning: Business description extraction failed: {e}")
                    st.warning(f"Business description extraction failed: {e}. "
                               "Continuing without it.")
        else:
            log("Skipping business description extraction (user opted out).")
        progress.progress(0.50)

        # Stage 3: Generate Report
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

        # Stage 4: Parse into sections → review mode
        with st.status("Preparing review...", expanded=False):
            try:
                from core.report_sections import parse_report_to_sections

                html_reports = sorted(REPORT_OUTPUT_DIR.glob('*.html'),
                                      key=lambda p: p.stat().st_mtime,
                                      reverse=True)
                if not html_reports:
                    st.error("No HTML report found after generation.")
                    st.stop()

                html_content = html_reports[0].read_text(encoding='utf-8')
                parsed = parse_report_to_sections(html_content)

                if not parsed["sections"]:
                    st.error("Could not parse report into sections.")
                    st.stop()

                log(f"Report parsed into {len(parsed['sections'])} sections.")

                st.session_state.parsed_report = parsed
                st.session_state.review_mode = True
                st.session_state.selected_review_section = 0
                st.session_state.section_chat_histories = {}
                st.session_state.ai_pending_html = {}
                st.session_state.review_model_choice = model_choice
                st.session_state.assessment_complete = False

                st.success("Report ready for review!")
            except Exception as e:
                st.error(f"Failed to prepare review: {e}")
                log(f"ERROR: {e}")
                import traceback
                log(traceback.format_exc())
                st.stop()

        progress.progress(1.0)
        st.balloons()
        st.rerun()

    # Past Assessments
    st.markdown("---")
    _render_past_assessments(key_suffix="_main")


# ──────────────────────────────────────────────────────────────────────────────
# Page Router
# ──────────────────────────────────────────────────────────────────────────────

col_title, col_new = st.columns([3, 1])
with col_title:
    st.markdown("### Quick Assessment")
with col_new:
    if st.button("New Report", type="secondary", use_container_width=True,
                 help="Save current assessment and start fresh"):
        _start_new_assessment()
        st.rerun()

if st.session_state.assessment_complete and st.session_state.current_report_path:
    _render_completed_view()
elif st.session_state.review_mode and st.session_state.parsed_report:
    _render_review_mode()
else:
    _render_upload_and_generate()
