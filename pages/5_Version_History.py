"""Page 4: Version History - Browse, compare, and revert prompt versions."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from prompts.prompt_manager import (get_version_history, load_version,
                                     revert_to_version, diff_versions, load_prompt)
from config.settings import PROMPT_FILES

st.set_page_config(page_title="Version History", page_icon="📜", layout="wide")
st.title("Version History")
st.markdown("Browse, compare, and revert to previous versions of your prompts.")

# --- Prompt Selection ---
prompt_names = list(PROMPT_FILES.keys())
prompt_labels = {
    "fin_condition_assessment_synthesis": "Financial Condition Assessment Synthesis",
    "financial_health_diagnostics": "Financial Health Diagnostics",
    "report_instructions": "Report Generation Instructions",
    "audit_criteria": "Audit LLM Criteria",
}

selected_prompt = st.selectbox(
    "Select Prompt Document",
    prompt_names,
    format_func=lambda x: prompt_labels.get(x, x),
)

st.markdown("---")

# --- Version List ---
versions = get_version_history(selected_prompt)

if not versions:
    st.info(f"No version history for '{prompt_labels.get(selected_prompt, selected_prompt)}'. "
            "Save changes in the Prompt Editor to create versions.")
    st.stop()

st.subheader(f"Versions ({len(versions)} total)")

# Version timeline
for i, v in enumerate(versions):
    col_ts, col_actions = st.columns([3, 2])
    with col_ts:
        label = "Latest" if i == 0 else ""
        st.text(f"  {v['display_time']}  {label}")
    with col_actions:
        col_view, col_revert = st.columns(2)
        with col_view:
            if st.button("View", key=f"view_{v['timestamp']}"):
                st.session_state[f"viewing_{selected_prompt}"] = v['timestamp']
        with col_revert:
            if i > 0:  # Don't revert to already-current version
                if st.button("Revert", key=f"revert_{v['timestamp']}"):
                    new_ts = revert_to_version(selected_prompt, v['timestamp'])
                    st.success(f"Reverted to {v['display_time']}. New version: {new_ts}")
                    st.rerun()

st.markdown("---")

# --- View Selected Version ---
viewing_key = f"viewing_{selected_prompt}"
if viewing_key in st.session_state:
    ts = st.session_state[viewing_key]
    matching = [v for v in versions if v['timestamp'] == ts]
    if matching:
        v = matching[0]
        st.subheader(f"Viewing Version: {v['display_time']}")

        version_data = load_version(selected_prompt, ts)
        sections = version_data.get("sections", {})

        for key, sec in sections.items():
            with st.expander(sec.get("title", key)):
                st.text_area(
                    "Content",
                    value=sec.get("content", ""),
                    height=200,
                    disabled=True,
                    key=f"view_content_{ts}_{key}",
                )

        st.markdown("---")

# --- Compare Versions ---
st.subheader("Compare Two Versions")

if len(versions) >= 2:
    col_v1, col_v2 = st.columns(2)

    version_options = [(v['timestamp'], v['display_time']) for v in versions]

    with col_v1:
        v1_idx = st.selectbox("Version A (older)", range(len(version_options)),
                               format_func=lambda i: version_options[i][1],
                               index=min(1, len(version_options) - 1),
                               key="compare_v1")
    with col_v2:
        v2_idx = st.selectbox("Version B (newer)", range(len(version_options)),
                               format_func=lambda i: version_options[i][1],
                               index=0,
                               key="compare_v2")

    if st.button("Compare"):
        ts1 = version_options[v1_idx][0]
        ts2 = version_options[v2_idx][0]

        diffs = diff_versions(selected_prompt, ts1, ts2)

        if not diffs:
            st.info("No sections to compare.")
        else:
            changed_count = sum(1 for d in diffs.values() if d['status'] != 'unchanged')
            st.markdown(f"**{changed_count}** section(s) changed between versions.")

            for key, diff_info in diffs.items():
                status = diff_info['status']
                if status == 'unchanged':
                    continue

                icon = {"changed": "🔄", "added": "➕", "removed": "➖"}.get(status, "")
                st.markdown(f"#### {icon} {key} ({status})")

                if diff_info['diff']:
                    st.code(diff_info['diff'], language="diff")
else:
    st.info("Need at least 2 versions to compare. Make changes in the Prompt Editor.")
