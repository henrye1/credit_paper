"""Centralized configuration for the Credit Paper Assessment Agent."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Project Paths ---
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

REPORT_INPUTS_DIR = DATA_DIR / "report_inputs"
FS_LEARNING_INPUTS_DIR = DATA_DIR / "fs_learning_inputs"
REPORT_OUTPUT_DIR = DATA_DIR / "report_output"
AUDIT_LLM_INPUT_DIR = DATA_DIR / "audit_llm_input"
AUDIT_LLM_OUTPUT_DIR = DATA_DIR / "audit_llm_output"
EVAL_INPUT_DIR = DATA_DIR / "eval_input"
EVAL_OUTPUT_DIR = DATA_DIR / "eval_output"
CONVERTED_REPORTS_DIR = DATA_DIR / "converted_reports"
ASSESSMENTS_DIR = DATA_DIR / "assessments"

PROMPTS_DIR = PROJECT_ROOT / "prompts"
PROMPT_SETS_DIR = PROMPTS_DIR / "sets"
PROMPT_REGISTRY_FILE = PROMPT_SETS_DIR / "_registry.json"
DEFAULT_PROMPT_SET = "bdo_sme"

# Legacy paths (used for one-time migration to prompt sets)
PROMPTS_CURRENT_DIR = PROMPTS_DIR / "current"
PROMPTS_HISTORY_DIR = PROMPTS_DIR / "history"

# Ensure all data directories exist
for d in [REPORT_INPUTS_DIR, FS_LEARNING_INPUTS_DIR, REPORT_OUTPUT_DIR,
          AUDIT_LLM_INPUT_DIR, AUDIT_LLM_OUTPUT_DIR, EVAL_INPUT_DIR,
          EVAL_OUTPUT_DIR, CONVERTED_REPORTS_DIR, ASSESSMENTS_DIR,
          PROMPT_SETS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# --- API Keys ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
LLAMACLOUD_API_KEY = os.getenv("LLAMACLOUD_API_KEY", "")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")

# --- Model Configuration ---
MODELS = {
    "report_generation": "gemini-2.5-flash",
    "audit_review": "gemini-2.5-flash",
    "comparison": "gemini-2.5-flash",
    "business_description": "gemini-2.5-flash",
    "section_edit": "gemini-2.5-flash",
}

# --- Prompt File Names ---
PROMPT_FILES = {
    "fin_condition_assessment_synthesis": "fin_condition_assessment_synthesis.yaml",
    "financial_health_diagnostics": "financial_health_diagnostics.yaml",
    "report_instructions": "report_instructions.yaml",
    "audit_criteria": "audit_criteria.yaml",
}

# --- Processing Constants ---
GEMINI_UPLOAD_RETRIES = 3
GEMINI_UPLOAD_DELAY = 20
GEMINI_FILE_TIMEOUT = 300
FIRECRAWL_POLL_INTERVAL = 10
FIRECRAWL_POLL_MAX_ATTEMPTS = 18
SUPPORTED_PARSE_EXTENSIONS = [".xlsx", ".xlsm"]
