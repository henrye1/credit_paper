"""Page 3: Examples Manager - Manage few-shot learning examples."""

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from config.settings import FS_LEARNING_INPUTS_DIR

st.set_page_config(page_title="Examples Manager", page_icon="📁", layout="wide")
st.title("Examples Manager")
st.markdown("Manage few-shot learning example pairs (Markdown ratios + PDF reports) "
            "used during report generation.")

st.markdown("---")

# --- Current Examples ---
st.subheader("Current Examples")

md_files = sorted(FS_LEARNING_INPUTS_DIR.glob('*.md'))
pdf_files = sorted(FS_LEARNING_INPUTS_DIR.glob('*.pdf'))
xlsx_files = sorted(FS_LEARNING_INPUTS_DIR.glob('*.xlsx'))

# Build pairs by numeric prefix
import re

def get_prefix(filename):
    match = re.match(r"^(\d+)\.?\s*", filename)
    return match.group(1) if match else None

# Group files by prefix
all_files = list(FS_LEARNING_INPUTS_DIR.iterdir())
prefix_map = {}
for f in all_files:
    if f.is_file():
        prefix = get_prefix(f.name)
        if prefix:
            prefix_map.setdefault(prefix, []).append(f)

if prefix_map:
    for prefix in sorted(prefix_map.keys()):
        files = prefix_map[prefix]
        # Extract a display name from the first file
        display_name = re.sub(r"^\d+\.?\s*", "", files[0].stem)
        display_name = re.sub(r"[_.-]", " ", display_name).strip()

        with st.expander(f"Example {prefix}: {display_name}", expanded=False):
            col_files, col_actions = st.columns([3, 1])

            with col_files:
                for f in sorted(files, key=lambda x: x.suffix):
                    size_kb = f.stat().st_size / 1024
                    icon = {"md": "📝", ".pdf": "📄", ".xlsx": "📊"}.get(f.suffix, "📎")
                    st.text(f"  {icon} {f.name} ({size_kb:.1f} KB)")

                # Preview .md content
                md_in_group = [f for f in files if f.suffix == '.md']
                if md_in_group:
                    md_content = md_in_group[0].read_text(encoding='utf-8')
                    st.text_area("Markdown Preview", value=md_content[:3000],
                                height=200, disabled=True,
                                key=f"preview_{prefix}")

            with col_actions:
                if st.button("Remove", key=f"remove_{prefix}", type="secondary"):
                    for f in files:
                        f.unlink()
                    st.success(f"Removed example {prefix}")
                    st.rerun()
else:
    st.info("No examples loaded yet. Upload a pair below.")

st.markdown("---")

# --- Upload New Example ---
st.subheader("Upload New Example")

st.markdown("Upload a matched pair: a Markdown ratio file and a PDF report. "
            "Both filenames should start with the same numeric prefix (e.g., '34. Company Name').")

col_up1, col_up2 = st.columns(2)

with col_up1:
    new_md = st.file_uploader("Markdown Ratio File (.md)", type=["md"],
                               key="new_example_md")
    new_xlsx = st.file_uploader("Excel Ratio File (.xlsx) *(optional)*", type=["xlsx"],
                                 key="new_example_xlsx")

with col_up2:
    new_pdf = st.file_uploader("PDF Report File (.pdf)", type=["pdf"],
                                key="new_example_pdf")

if st.button("Add Example Pair", type="primary"):
    if not new_md or not new_pdf:
        st.error("Both a Markdown (.md) and PDF (.pdf) file are required.")
    else:
        # Validate matching prefixes
        md_prefix = get_prefix(new_md.name)
        pdf_prefix = get_prefix(new_pdf.name)

        if md_prefix and pdf_prefix and md_prefix == pdf_prefix:
            # Save files
            md_dest = FS_LEARNING_INPUTS_DIR / new_md.name
            md_dest.write_bytes(new_md.getvalue())

            pdf_dest = FS_LEARNING_INPUTS_DIR / new_pdf.name
            pdf_dest.write_bytes(new_pdf.getvalue())

            if new_xlsx:
                xlsx_dest = FS_LEARNING_INPUTS_DIR / new_xlsx.name
                xlsx_dest.write_bytes(new_xlsx.getvalue())

            st.success(f"Added example pair with prefix {md_prefix}")
            st.rerun()
        elif not md_prefix or not pdf_prefix:
            st.warning("Files should start with a numeric prefix (e.g., '34. Company Name'). "
                       "Saving anyway...")
            md_dest = FS_LEARNING_INPUTS_DIR / new_md.name
            md_dest.write_bytes(new_md.getvalue())
            pdf_dest = FS_LEARNING_INPUTS_DIR / new_pdf.name
            pdf_dest.write_bytes(new_pdf.getvalue())
            if new_xlsx:
                xlsx_dest = FS_LEARNING_INPUTS_DIR / new_xlsx.name
                xlsx_dest.write_bytes(new_xlsx.getvalue())
            st.success("Files saved.")
            st.rerun()
        else:
            st.error(f"Prefix mismatch: MD has '{md_prefix}', PDF has '{pdf_prefix}'. "
                     "They must match.")

st.markdown("---")

# --- Summary ---
st.subheader("Summary")
st.markdown(f"- **Total example pairs**: {len(prefix_map)}")
st.markdown(f"- **Location**: `{FS_LEARNING_INPUTS_DIR}`")
