"""Credit Paper Assessment Agent - Streamlit Application."""

import sys
from pathlib import Path

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from config.settings import (REPORT_INPUTS_DIR, FS_LEARNING_INPUTS_DIR,
                              REPORT_OUTPUT_DIR, PROMPTS_CURRENT_DIR)
from prompts.prompt_manager import get_version_history

st.set_page_config(
    page_title="Credit Paper Assessment Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Credit Paper Assessment Agent")
st.markdown("Generate, review, and refine SARB financial condition assessment reports.")

st.markdown("---")

# Dashboard statistics
col1, col2, col3, col4 = st.columns(4)

with col1:
    input_count = len(list(REPORT_INPUTS_DIR.glob('*.xlsx'))) + len(list(REPORT_INPUTS_DIR.glob('*.pdf')))
    st.metric("Input Files", input_count)

with col2:
    example_count = len(list(FS_LEARNING_INPUTS_DIR.glob('*.md')))
    st.metric("Few-Shot Examples", example_count)

with col3:
    report_count = len(list(REPORT_OUTPUT_DIR.glob('*.html')))
    st.metric("Generated Reports", report_count)

with col4:
    # Count total prompt versions across all prompt files
    total_versions = 0
    for yaml_file in PROMPTS_CURRENT_DIR.glob('*.yaml'):
        prompt_name = yaml_file.stem
        total_versions += len(get_version_history(prompt_name))
    st.metric("Prompt Versions", total_versions)

st.markdown("---")

# Quick navigation
st.subheader("Quick Actions")

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.markdown("### Run Assessment")
    st.markdown("Upload financial data and generate a credit assessment report.")
    st.page_link("pages/1_Run_Assessment.py", label="Go to Run Assessment", icon="▶️")

with col_b:
    st.markdown("### Edit Prompts")
    st.markdown("Modify prompt sections independently and track changes.")
    st.page_link("pages/2_Prompt_Editor.py", label="Go to Prompt Editor", icon="✏️")

with col_c:
    st.markdown("### Manage Examples")
    st.markdown("Add or remove few-shot learning examples for report generation.")
    st.page_link("pages/3_Examples_Manager.py", label="Go to Examples Manager", icon="📁")

st.markdown("---")

# Recent reports
st.subheader("Recent Reports")
html_reports = sorted(REPORT_OUTPUT_DIR.glob('*.html'), key=lambda p: p.stat().st_mtime, reverse=True)
if html_reports:
    for report in html_reports[:5]:
        col_r1, col_r2 = st.columns([4, 1])
        with col_r1:
            st.text(f"{report.name}")
        with col_r2:
            with open(report, "r", encoding="utf-8") as f:
                st.download_button(
                    "Download",
                    f.read(),
                    file_name=report.name,
                    mime="text/html",
                    key=f"dl_{report.name}"
                )
else:
    st.info("No reports generated yet. Go to Run Assessment to create your first report.")
