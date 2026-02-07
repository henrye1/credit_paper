"""Page 5: Settings - API keys, model configuration, paths."""

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from config.settings import (GOOGLE_API_KEY, LLAMACLOUD_API_KEY, FIRECRAWL_API_KEY,
                              MODELS, PROJECT_ROOT as PROJ_ROOT)

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
st.title("Settings")
st.markdown("Configure API keys, models, and paths.")

env_path = PROJ_ROOT / ".env"

# --- Load current .env values ---
def load_env_values():
    """Load current values from .env file."""
    values = {"GOOGLE_API_KEY": "", "LLAMACLOUD_API_KEY": "", "FIRECRAWL_API_KEY": ""}
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key in values:
                    values[key] = val
    return values


def mask_key(key: str) -> str:
    """Show first 4 and last 4 characters of a key."""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


st.markdown("---")

# --- API Keys ---
st.subheader("API Keys")
st.markdown("Keys are stored in `.env` file in the project root. "
            "Changes take effect on next app restart.")

current = load_env_values()

col_k1, col_k2 = st.columns([3, 1])

with col_k1:
    google_key = st.text_input(
        "Google API Key (Gemini)",
        value=current["GOOGLE_API_KEY"],
        type="password",
        key="google_key_input",
    )
    llama_key = st.text_input(
        "LlamaCloud API Key (LlamaParse)",
        value=current["LLAMACLOUD_API_KEY"],
        type="password",
        key="llama_key_input",
    )
    firecrawl_key = st.text_input(
        "Firecrawl API Key",
        value=current["FIRECRAWL_API_KEY"],
        type="password",
        key="firecrawl_key_input",
    )

with col_k2:
    st.markdown("**Status**")
    st.markdown(f"{'Configured' if current['GOOGLE_API_KEY'] else 'Not set'}")
    st.markdown(f"{'Configured' if current['LLAMACLOUD_API_KEY'] else 'Not set'}")
    st.markdown(f"{'Configured' if current['FIRECRAWL_API_KEY'] else 'Not set'}")

if st.button("Save API Keys", type="primary"):
    env_content = f"""# Google Generative AI API Key (for Gemini models)
GOOGLE_API_KEY={google_key}

# LlamaCloud API Key (for LlamaParse document parsing)
LLAMACLOUD_API_KEY={llama_key}

# Firecrawl API Key (for web scraping company descriptions)
FIRECRAWL_API_KEY={firecrawl_key}
"""
    env_path.write_text(env_content, encoding='utf-8')
    st.success("API keys saved to .env. Restart the app for changes to take effect.")

st.markdown("---")

# --- Model Configuration ---
st.subheader("Model Configuration")
st.markdown("Default models used for each pipeline stage. "
            "These can also be overridden per-run on the Run Assessment page.")

col_m1, col_m2 = st.columns(2)

with col_m1:
    st.text_input("Report Generation Model", value=MODELS["report_generation"],
                  disabled=True, key="model_report")
    st.text_input("Audit Review Model", value=MODELS["audit_review"],
                  disabled=True, key="model_audit")

with col_m2:
    st.text_input("Comparison Model", value=MODELS["comparison"],
                  disabled=True, key="model_comparison")
    st.text_input("Business Description Model", value=MODELS["business_description"],
                  disabled=True, key="model_desc")

st.caption("To change default models, edit `config/settings.py`.")

st.markdown("---")

# --- Directory Paths ---
st.subheader("Directory Paths")

from config.settings import (REPORT_INPUTS_DIR, FS_LEARNING_INPUTS_DIR,
                              REPORT_OUTPUT_DIR, AUDIT_LLM_INPUT_DIR,
                              AUDIT_LLM_OUTPUT_DIR, EVAL_INPUT_DIR,
                              EVAL_OUTPUT_DIR, CONVERTED_REPORTS_DIR)

paths = {
    "Report Inputs": REPORT_INPUTS_DIR,
    "Learning Examples": FS_LEARNING_INPUTS_DIR,
    "Report Output": REPORT_OUTPUT_DIR,
    "Audit LLM Input": AUDIT_LLM_INPUT_DIR,
    "Audit LLM Output": AUDIT_LLM_OUTPUT_DIR,
    "Eval Input": EVAL_INPUT_DIR,
    "Eval Output": EVAL_OUTPUT_DIR,
    "Converted Reports": CONVERTED_REPORTS_DIR,
}

for label, path in paths.items():
    col_p1, col_p2, col_p3 = st.columns([2, 4, 1])
    with col_p1:
        st.text(label)
    with col_p2:
        st.text(str(path))
    with col_p3:
        file_count = len(list(path.iterdir())) if path.exists() else 0
        st.text(f"{file_count} files")

st.caption("Paths are configured in `config/settings.py`.")
