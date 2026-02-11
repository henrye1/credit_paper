# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Credit Paper Assessment Agent — a full-stack app for generating SARB (South African Reserve Bank) Financial Condition Assessment Reports for supplier evaluations. Uses Google Gemini LLMs to analyse uploaded financial data (Excel ratios + PDF AFS) and produce formal HTML reports in the style of BDO financial assessments.

## Commands

### Development (two terminals)

```bash
# Backend — FastAPI with hot reload
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Frontend — Vite dev server (proxies /api → localhost:8000)
cd frontend
npm install
npm run dev
```

### Production (single command)

```bash
python start.py   # builds frontend, starts uvicorn on port 8000
```

### Frontend lint

```bash
cd frontend && npm run lint
```

### Legacy Streamlit UI

```bash
streamlit run app.py
```

### No automated test suite exists yet.

## Architecture

### Two frontends

- **React SPA** (`frontend/`) — primary UI. Vite + TypeScript + Tailwind + Zustand + TipTap editor. Built to `frontend/dist/` and served by FastAPI in production.
- **Streamlit** (`app.py` + `pages/`) — legacy UI, still maintained.

### Backend (`backend/`)

FastAPI app in `backend/main.py`. Routers in `backend/routers/`, services in `backend/services/`.

- `assessment.py` — Quick Assessment: upload → generate → review sections → approve → finalize
- `pipeline.py` — Full 6-stage development pipeline
- `prompts.py` / `prompt_sets.py` — Prompt CRUD with versioning and multi-set management
- `examples.py` — Few-shot learning example pair management
- `assessment_service.py` — In-memory + file-backed state (`data/assessments/{id}/state.json`)
- `log_manager.py` — SSE streaming via asyncio queues

All API routes are under `/api/`. SPA fallback middleware returns `index.html` for non-API 404s.

### Core processing (`core/`)

Each module corresponds to a pipeline stage:

| Module | Stage | Function |
|---|---|---|
| `parser.py` | 1 | Excel/PDF → Markdown (Docling with LlamaParse fallback) |
| `business_desc.py` | 2 | Company web scrape (Firecrawl) → Gemini business description |
| `report_generator.py` | 3 | Full report generation (prompts + few-shot examples → Gemini) |
| `auditor.py` | 4 | LLM audit review of generated report (8 categories) |
| `comparator.py` | 5 | Human vs LLM report comparison |
| `converter.py` | 6 | HTML → JSON/DOCX conversion |

Supporting modules: `gemini_client.py` (API wrapper with retry/upload/cleanup), `prompt_builder.py` (assembles YAML sections into prompts), `report_sections.py` (HTML section parsing, editing, reassembly).

### Prompt system (`prompts/`)

- YAML files with named sections (role, guidance, instructions)
- Multi-set architecture: `prompts/sets/{slug}/current/*.yaml` with `_registry.json` tracking default
- Auto-versioning on save (timestamped copies in `history/`)
- `prompt_manager.py` handles CRUD, versioning, set-aware resolution
- 4 prompt documents: `report_instructions`, `fin_condition_assessment_synthesis`, `financial_health_diagnostics`, `audit_criteria`

### Configuration (`config/settings.py`)

Central config: paths, API keys (from `.env`), model names, processing constants. All models default to `gemini-2.5-flash`. Directories auto-created on import.

### Frontend state (`frontend/src/`)

- Zustand store in `store/assessmentStore.ts` — sections, status, UI phase
- React Query for API calls (`api/`)
- SSE log streaming via `hooks/useSSELogs.ts`
- TipTap rich text editor for section editing (`components/report/SectionEditor.tsx`)
- Pages: Dashboard, QuickAssessment, Pipeline, PromptEditor, Examples, VersionHistory, Settings

## Key Patterns

- **Few-shot examples** require matching numeric prefixes: `34. Company Name.md` + `34. Company Name.pdf` in `data/fs_learning_inputs/`
- **Excel formula resolution**: `.xlsm` files opened twice (formulas + cached values), resolved into temp `.xlsx` before parsing
- **Gemini file lifecycle**: upload with 3 retries → poll until ACTIVE (300s timeout) → use → delete
- **HTML is source of truth** for reports: sections parsed at heading boundaries, reassembled after editing
- **Async pipeline in sync context**: uses `asyncio.run_in_executor()` to run blocking core modules

## Environment Variables (`.env`)

```
GOOGLE_API_KEY=      # Google Gemini API
LLAMACLOUD_API_KEY=  # LlamaParse document parsing
FIRECRAWL_API_KEY=   # Web scraping for business descriptions
```

## Data Directories (`data/`)

| Directory | Purpose |
|---|---|
| `report_inputs/` | Upload target (Excel + PDFs) |
| `fs_learning_inputs/` | Few-shot example pairs |
| `report_output/` | Generated HTML reports |
| `audit_llm_input/` | Audit context DOCX files |
| `audit_llm_output/` | Audit review HTML |
| `eval_input/` | Human reports for comparison |
| `eval_output/` | Comparison HTML |
| `converted_reports/` | JSON + DOCX conversions |
| `assessments/` | Archived assessment state |
