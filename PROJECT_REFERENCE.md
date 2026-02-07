# Credit Paper Assessment Agent - Project Reference

## 1. Overview

The Credit Paper Assessment Agent is a Streamlit-based application that automates the generation of **SARB (South African Reserve Bank) Financial Condition Assessment Reports** for supplier evaluations. It uses Google Gemini LLMs to analyse uploaded financial data and produce formal HTML reports in the style of BDO financial assessments.

The application serves two distinct purposes:
- **Production use**: Quick, one-click report generation from uploaded financial files.
- **Framework development**: A full pipeline for iteratively refining the LLM prompts using few-shot examples, audit reviews, and human-vs-LLM comparisons.

---

## 2. Architecture

### 2.1 Technology Stack

| Component | Technology |
|---|---|
| Frontend / UI | Streamlit (Python) |
| LLM Provider | Google Gemini API (`google-genai`) |
| Document Parsing | LlamaParse (`llama-parse`) via LlamaCloud API |
| Web Scraping | Firecrawl API |
| Document Conversion | `python-docx`, `beautifulsoup4` |
| Data Handling | `pandas`, `openpyxl` |
| Configuration | `.env` file via `python-dotenv`, YAML prompt files |

### 2.2 Project Structure

```
credit_paper/
|-- app.py                          # Main Streamlit entry point (dashboard)
|-- requirements.txt                # Python dependencies
|-- .env                            # API keys (not committed)
|-- .env.example                    # Template for .env
|-- config/
|   |-- __init__.py
|   |-- settings.py                 # Centralised configuration constants
|-- core/
|   |-- __init__.py
|   |-- gemini_client.py            # Gemini API wrapper with retry logic
|   |-- parser.py                   # Stage 1: Excel to Markdown via LlamaParse
|   |-- business_desc.py            # Stage 2: Web scrape + LLM business description
|   |-- prompt_builder.py           # Assembles prompts from YAML sections
|   |-- report_generator.py         # Stage 3: Financial report generation
|   |-- auditor.py                  # Stage 4: LLM audit review
|   |-- comparator.py               # Stage 5: Human vs LLM comparison
|   |-- converter.py                # Stage 6: HTML to JSON/DOCX conversion
|-- prompts/
|   |-- __init__.py
|   |-- prompt_manager.py           # CRUD + versioning for YAML prompts
|   |-- current/                    # Active prompt YAML files
|   |   |-- report_instructions.yaml
|   |   |-- audit_criteria.yaml
|   |   |-- fin_condition_assessment_synthesis.yaml
|   |   |-- financial_health_diagnostics.yaml
|   |-- history/                    # Timestamped prompt versions
|-- pages/
|   |-- 1_Quick_Assessment.py       # Production: one-click report generation
|   |-- 2_Run_Assessment.py         # Development: full 6-stage pipeline
|   |-- 3_Prompt_Editor.py          # Edit prompt sections with versioning
|   |-- 4_Examples_Manager.py       # Manage few-shot learning example pairs
|   |-- 5_Version_History.py        # Browse, compare, revert prompt versions
|   |-- 6_Settings.py               # API keys, model config, directory paths
|-- data/
|   |-- report_inputs/              # Target company Excel + PDF files
|   |-- fs_learning_inputs/         # Few-shot example pairs (MD + PDF)
|   |-- report_output/              # Generated HTML reports
|   |-- audit_llm_input/            # Audit context DOCX files
|   |-- audit_llm_output/           # Audit review HTML reports
|   |-- eval_input/                 # Human-created reports for comparison
|   |-- eval_output/                # Comparison HTML reports
|   |-- converted_reports/          # JSON and DOCX conversions
```

---

## 3. Configuration

### 3.1 Environment Variables (`.env`)

| Variable | Purpose | Used By |
|---|---|---|
| `GOOGLE_API_KEY` | Google Gemini API access | `gemini_client.py`, `business_desc.py` |
| `LLAMACLOUD_API_KEY` | LlamaCloud / LlamaParse document parsing | `parser.py` |
| `FIRECRAWL_API_KEY` | Firecrawl web scraping for business descriptions | `business_desc.py` |

### 3.2 Model Configuration (`config/settings.py`)

| Task | Default Model |
|---|---|
| Report Generation | `gemini-2.5-pro` |
| Audit Review | `gemini-2.5-flash-preview-04-17-thinking` |
| Comparison | `gemini-2.5-flash-preview-05-20` |
| Business Description | `gemini-2.5-flash-preview-05-20` |

### 3.3 Processing Constants

| Constant | Default | Purpose |
|---|---|---|
| `GEMINI_UPLOAD_RETRIES` | 3 | Number of upload retry attempts |
| `GEMINI_UPLOAD_DELAY` | 20s | Delay between retries |
| `GEMINI_FILE_TIMEOUT` | 300s | Max wait for file to become ACTIVE |
| `FIRECRAWL_POLL_INTERVAL` | 10s | Polling interval for async scrape jobs |
| `FIRECRAWL_POLL_MAX_ATTEMPTS` | 18 | Max polling attempts |
| `SUPPORTED_PARSE_EXTENSIONS` | `.xlsx`, `.xlsm` | File types parsed by LlamaParse |

---

## 4. Application Pages

### 4.1 Dashboard (`app.py`)

The home page displays:
- **Metrics**: Input file count, few-shot example count, generated report count, prompt version count.
- **Quick Actions**: Navigation links to the main pages.
- **Recent Reports**: List of the 5 most recent HTML reports with download buttons.

### 4.2 Quick Assessment (`pages/1_Quick_Assessment.py`)

**Purpose**: Production-mode, one-click report generation.

**Workflow**:
1. Upload an Excel ratio file (`.xlsx` / `.xlsm`) and one or more AFS PDFs.
2. Choose a model and optionally skip business description extraction.
3. Click "Generate Report".
4. The pipeline automatically:
   - Parses the Excel file to Markdown via LlamaParse.
   - Extracts a business description via Firecrawl + Gemini (web scraping the company name).
   - Generates the full HTML Financial Condition Assessment Report using the refined prompts and any few-shot examples present in `fs_learning_inputs/`.
5. Download or preview the generated report.

### 4.3 Run Assessment / Dev Pipeline (`pages/2_Run_Assessment.py`)

**Purpose**: Framework development and refinement. Full 6-stage pipeline with granular control.

**Stages**:

| # | Stage | Description |
|---|---|---|
| 1 | Parse Excel to Markdown | Converts uploaded `.xlsx`/`.xlsm` files to Markdown via LlamaParse |
| 2 | Extract Business Description | Web scrapes company info via Firecrawl, synthesises with Gemini |
| 3 | Generate Financial Report | Builds a prompt from YAML sections + few-shot examples, calls Gemini to produce an HTML report |
| 4 | Audit LLM Review | A second LLM (auditor) reviews the generated report for hallucinations, bias, incoherence, PII, etc. Requires a DOCX file containing LLM risk research as context |
| 5 | Compare Human vs LLM | Uploads a human-written report and compares it section-by-section with the LLM report, using the AFS as ground truth |
| 6 | Convert to DOCX/JSON | Converts all HTML reports across output directories to structured JSON and DOCX |

**Stages 4-5** are specifically for evaluating and improving model output quality. They require additional input files (audit context DOCX, human-written report).

### 4.4 Prompt Editor (`pages/3_Prompt_Editor.py`)

**Purpose**: Edit individual sections of the 4 prompt YAML documents.

**Features**:
- Section-by-section editing with change tracking.
- Automatic versioning on save (timestamped copies in `prompts/history/`).
- Assembled prompt preview showing the full concatenated text.

**Prompt Documents**:
| Document | Purpose |
|---|---|
| `report_instructions` | Role definition, format rules, citation rules, few-shot preamble for report generation |
| `fin_condition_assessment_synthesis` | Primary guidance document for financial condition assessment structure |
| `financial_health_diagnostics` | Secondary guidance document for financial health diagnostic criteria |
| `audit_criteria` | Auditor role, 8 audit categories, output format for Stage 4 |

### 4.5 Examples Manager (`pages/4_Examples_Manager.py`)

**Purpose**: Manage few-shot learning example pairs used during report generation (Stage 3).

**How it works**:
- Examples are pairs of files with matching numeric prefixes (e.g., `34. Company Name.md` + `34. Company Name.pdf`).
- The Markdown file contains parsed financial ratios; the PDF is a completed BDO report.
- During report generation, these pairs are uploaded to Gemini as examples of the expected output style.
- Upload new pairs, preview Markdown content, or remove existing examples.

### 4.6 Version History (`pages/5_Version_History.py`)

**Purpose**: Browse, compare, and revert prompt versions.

**Features**:
- Timeline view of all saved versions for each prompt document.
- View any historical version's content.
- Revert to a previous version (creates a new version entry).
- Side-by-side diff comparison between any two versions.

### 4.7 Settings (`pages/6_Settings.py`)

**Purpose**: Configure API keys, view model configuration, and inspect directory paths.

**Features**:
- Edit and save API keys to `.env` (requires app restart).
- View default models for each pipeline stage.
- View all data directory paths with file counts.

---

## 5. Core Modules

### 5.1 Gemini Client (`core/gemini_client.py`)

**Class `GeminiClient`**: Wraps the Google Gemini API with:
- **File upload** with retry logic (configurable retries and delay). Polls until file status is ACTIVE.
- **Content generation** with optional temperature control. Handles blocked prompts and empty responses.
- **File cleanup** to delete uploaded files from the API after use.

**Utility functions**:
- `clean_html_response(text)` - Strips markdown code fences from LLM HTML output.
- `safe_filename(name)` - Creates filesystem-safe filenames from company names.

### 5.2 Parser (`core/parser.py`)

**Stage 1**: Converts Excel files to Markdown using LlamaParse (LlamaCloud API).

- `parse_excel_to_markdown(file_path)` - Parses a single file, saves `.md` alongside the original.
- `parse_all_in_directories(directories)` - Batch parses all supported files across multiple directories.

Uses `nest_asyncio` to allow async LlamaParse calls within Streamlit's event loop.

### 5.3 Business Description (`core/business_desc.py`)

**Stage 2**: Extracts company business descriptions through a 3-step process:

1. **Company name extraction**: Reads the first rows of the Excel file to identify the company name.
2. **Web scraping**: Uses Firecrawl to search for the company and scrape its website.
3. **LLM synthesis**: Sends scraped content to Gemini to produce a concise 5-8 sentence business description.

Caches descriptions in `company_business_description.txt` with company-specific delimiters to avoid redundant scraping.

### 5.4 Prompt Builder (`core/prompt_builder.py`)

Assembles structured prompts from YAML sections for each pipeline stage:

- `build_report_prompt(...)` - Builds the Stage 3 prompt. Combines role definition, guidance documents, target company files (as Gemini file objects), few-shot examples, and generation instructions into a mixed list of strings and file objects.
- `build_audit_prompt(...)` - Builds the Stage 4 audit prompt with 8 evaluation categories.
- `build_comparison_prompt(...)` - Builds the Stage 5 comparison prompt.

### 5.5 Report Generator (`core/report_generator.py`)

**Stage 3**: Orchestrates report generation:

1. Discovers target files (`.md` ratios, `.pdf` AFS, business description `.txt`).
2. Uploads target files to Gemini API.
3. Uploads few-shot example pairs from `fs_learning_inputs/`.
4. Builds the prompt via `prompt_builder.build_report_prompt()`.
5. Calls Gemini and saves the cleaned HTML report.

### 5.6 Auditor (`core/auditor.py`)

**Stage 4**: Runs an LLM audit review on a generated report:

1. Finds the latest HTML report and a DOCX file containing LLM risk research.
2. Builds the audit prompt with 8 review categories (bias, hallucination, incoherence, verbosity, PII, chain-of-thought, formatting, other failures).
3. Calls Gemini and saves the audit review as HTML.

### 5.7 Comparator (`core/comparator.py`)

**Stage 5**: Compares a human-written report against the LLM-generated report:

1. Finds the human report (from `eval_input/`), LLM report (from `report_output/`), and AFS PDF (from `report_inputs/`).
2. Uploads the human report and AFS to Gemini.
3. Evaluates both reports on: validity of conclusions, depth of assessment, relevance of inputs, omissions/inconsistencies, and input data reference errors.
4. Saves the comparison as HTML.

### 5.8 Converter (`core/converter.py`)

**Stage 6**: Converts HTML reports to other formats:

- `convert_html_to_json(html_path)` - Parses HTML structure into a nested JSON document with sections, subsections, paragraphs, lists, and tables.
- `convert_html_to_docx(html_path)` - Converts HTML to a formatted Word document preserving headings, tables, lists, and styling.
- `convert_all_reports(html_dirs)` - Batch converts all HTML files across output directories.

### 5.9 Prompt Manager (`prompts/prompt_manager.py`)

Manages the 4 YAML prompt documents with full CRUD and version control:

- `load_prompt(name)` / `save_prompt(name, data)` - Read/write YAML files.
- `get_version_history(name)` - Lists all timestamped historical versions.
- `load_version(name, timestamp)` / `revert_to_version(name, timestamp)` - Access or restore historical versions.
- `diff_versions(name, ts1, ts2)` - Section-by-section unified diff between two versions.
- `assemble_prompt_text(name)` - Concatenates all sections into a single text block for use in prompts.

---

## 6. Data Flow

### 6.1 Quick Assessment (Production)

```
Excel (.xlsx/.xlsm) + PDFs
        |
        v
  [LlamaParse] --> .md ratios
        |
        v
  [Firecrawl + Gemini] --> business description .txt
        |
        v
  [Gemini API]
    + YAML prompts (report_instructions, guidance docs)
    + Few-shot examples (from fs_learning_inputs/)
    + Target .md + PDFs + business description
        |
        v
  HTML Financial Condition Report --> data/report_output/
```

### 6.2 Full Development Pipeline

```
                    Stage 1          Stage 2              Stage 3
Excel + PDFs  -->  [Parse]  -->  [Biz Desc]  -->  [Generate Report]  -->  HTML Report
                                                          |
                                                          |  Stage 4
                                              + DOCX risk research
                                                          |
                                                          v
                                                   [Audit Review]  -->  Audit HTML
                                                          |
                                                          |  Stage 5
                                              + Human report (eval_input/)
                                                          |
                                                          v
                                                   [Comparison]  -->  Eval HTML
                                                          |
                                                          |  Stage 6
                                                          v
                                                   [Convert]  -->  JSON + DOCX
```

---

## 7. Prompt System

The application uses a modular, versioned prompt system stored as YAML files.

### 7.1 Report Generation Prompt Structure

The Stage 3 prompt is assembled from multiple sources:

1. **Role & Context** (`report_instructions.yaml` > `role_definition`) - Defines the LLM as an expert BDO financial analyst producing a SARB supplier assessment.
2. **Guidance Documents** - Two full guidance documents loaded from their own YAML files:
   - `fin_condition_assessment_synthesis.yaml` - Structure for financial condition assessment.
   - `financial_health_diagnostics.yaml` - Diagnostic criteria for financial health.
3. **Target Company Inputs** - Business description text + uploaded Gemini file objects (Markdown ratios + AFS PDFs).
4. **Few-Shot Examples** - Paired Markdown + PDF files uploaded to Gemini as style examples.
5. **Generation Instructions** - Output format, section conclusion requirements, mandatory calculations (CFO, dividends), overall conclusion wording, citation rules.

### 7.2 Audit Prompt Structure

The Stage 4 prompt evaluates the generated report across 8 categories:
1. Bias
2. Hallucination / Fabrication
3. Incoherence / Lack of Logical Flow
4. Lack of Conciseness / Verbosity
5. Personally Identifiable Information (PII)
6. Chain of Thought Truthfulness
7. Formatting and Presentation (HTML)
8. Other LLM Failures

### 7.3 Version Control

Every save in the Prompt Editor creates a timestamped copy in `prompts/history/{prompt_name}/`. Users can view, diff, and revert to any previous version.

---

## 8. API Dependencies

| API | Endpoint | Purpose |
|---|---|---|
| Google Gemini | `generativelanguage.googleapis.com` | LLM content generation, file upload/processing |
| LlamaCloud | `api.cloud.llamaindex.ai` | Document parsing (Excel/PDF to Markdown) |
| Firecrawl | `api.firecrawl.dev` | Web search and scraping for business descriptions |

---

## 9. Running the Application

### 9.1 Prerequisites

- Python 3.10+
- API keys for Google Gemini, LlamaCloud, and Firecrawl

### 9.2 Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your API keys
```

### 9.3 Launch

```bash
streamlit run app.py
```

The application will open at `http://localhost:8501`.

---

## 10. File Format Requirements

### 10.1 Input Files

| File Type | Format | Purpose |
|---|---|---|
| Financial Ratios | `.xlsx` or `.xlsm` | Primary quantitative data. Company name is extracted from the first rows. |
| Audited Financial Statements | `.pdf` | Supporting documents for verification and additional calculations. |
| Business Description | `.txt` (auto-generated) | Company overview. Auto-generated via web scraping or can be manually provided. |
| Audit Context | `.docx` | LLM risk research document required for Stage 4 audit review. |
| Human Report | `.pdf` or `.docx` | Human-written report required for Stage 5 comparison. |

### 10.2 Few-Shot Examples

Example pairs must follow a numeric prefix convention:
- `34. Company Name.md` (parsed financial ratios)
- `34. Company Name.pdf` (completed BDO report)

The numeric prefix links the input-output pair. Both files must share the same prefix number.

### 10.3 Output Files

| Output | Format | Location |
|---|---|---|
| Financial Condition Report | `.html` | `data/report_output/` |
| Audit Review | `.html` | `data/audit_llm_output/` |
| Comparison Report | `.html` | `data/eval_output/` |
| Converted Reports | `.json`, `.docx` | `data/converted_reports/` |
