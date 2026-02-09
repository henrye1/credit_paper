"""Page 2: Prompt Editor - Edit prompt sections independently."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from prompts.prompt_manager import (load_prompt, save_prompt, assemble_prompt_text,
                                     get_section_titles)
from config.settings import PROMPT_FILES

st.set_page_config(page_title="Prompt Editor", page_icon="✏️", layout="wide")
st.title("Prompt Editor")
st.markdown("Edit prompt sections independently. Changes are versioned automatically on save.")

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

# Load prompt data
prompt_data = load_prompt(selected_prompt)
sections = prompt_data.get("sections", {})

if not sections:
    st.warning(f"No sections found for '{selected_prompt}'. "
               "The YAML file may not exist yet or is empty.")
    st.stop()

# --- Initialize session state for edits ---
state_key = f"edits_{selected_prompt}"
if state_key not in st.session_state:
    st.session_state[state_key] = {}

st.markdown("---")

# --- Section Editor ---
col_list, col_editor = st.columns([1, 3])

# Section list
with col_list:
    st.markdown("### Sections")
    section_keys = list(sections.keys())
    section_labels = [sections[k].get("title", k) for k in section_keys]

    if "selected_section_idx" not in st.session_state:
        st.session_state.selected_section_idx = 0

    for i, (key, label) in enumerate(zip(section_keys, section_labels)):
        modified = key in st.session_state[state_key]
        marker = " *" if modified else ""
        if st.button(f"{label}{marker}", key=f"sec_btn_{key}",
                     use_container_width=True,
                     type="primary" if i == st.session_state.selected_section_idx else "secondary"):
            st.session_state.selected_section_idx = i

# Editor panel
with col_editor:
    idx = st.session_state.selected_section_idx
    if idx >= len(section_keys):
        idx = 0
    current_key = section_keys[idx]
    current_section = sections[current_key]

    # Get current values (from edits or original)
    edits = st.session_state[state_key].get(current_key, {})
    current_title = edits.get("title", current_section.get("title", current_key))
    current_desc = edits.get("description", current_section.get("description", ""))
    current_content = edits.get("content", current_section.get("content", ""))

    st.markdown(f"### Editing: {current_title}")

    new_title = st.text_input("Section Title", value=current_title, key=f"title_{current_key}")
    new_desc = st.text_input("Description", value=current_desc, key=f"desc_{current_key}")
    new_content = st.text_area("Content", value=current_content, height=500,
                                key=f"content_{current_key}")

    # Track changes
    original_title = current_section.get("title", current_key)
    original_desc = current_section.get("description", "")
    original_content = current_section.get("content", "")

    has_changes = (new_title != original_title or
                   new_desc != original_desc or
                   new_content != original_content)

    if has_changes:
        st.session_state[state_key][current_key] = {
            "title": new_title,
            "description": new_desc,
            "content": new_content,
        }
    elif current_key in st.session_state[state_key]:
        del st.session_state[state_key][current_key]

    # Action buttons
    col_save, col_discard, col_info = st.columns([1, 1, 2])

    with col_save:
        total_changes = len(st.session_state[state_key])
        if st.button(f"Save All Changes ({total_changes})", type="primary",
                     disabled=total_changes == 0):
            # Apply all edits to prompt data
            for edit_key, edit_vals in st.session_state[state_key].items():
                if edit_key in prompt_data["sections"]:
                    prompt_data["sections"][edit_key]["title"] = edit_vals["title"]
                    prompt_data["sections"][edit_key]["description"] = edit_vals["description"]
                    prompt_data["sections"][edit_key]["content"] = edit_vals["content"]

            timestamp = save_prompt(selected_prompt, prompt_data)
            st.session_state[state_key] = {}
            st.success(f"Saved! Version: {timestamp}")
            st.rerun()

    with col_discard:
        if st.button("Discard All Changes", disabled=total_changes == 0):
            st.session_state[state_key] = {}
            st.rerun()

    with col_info:
        if total_changes > 0:
            st.info(f"{total_changes} section(s) modified (unsaved)")

st.markdown("---")

# --- Assembled Prompt Preview ---
with st.expander("Preview Assembled Prompt"):
    full_text = assemble_prompt_text(selected_prompt)
    st.text_area("Full prompt text (read-only)", value=full_text, height=400,
                 disabled=True, key="preview_text")
    st.caption(f"Total characters: {len(full_text):,}")
