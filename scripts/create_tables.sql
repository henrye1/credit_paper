-- Supabase DDL for Credit Paper Assessment Agent
-- Run this in the Supabase SQL editor to create all tables and indexes.

-- ─────────────────────────────────────────────────────────
-- Assessments
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY,
    phase TEXT NOT NULL DEFAULT 'generating',
    model_choice TEXT,
    skip_biz_desc BOOLEAN DEFAULT FALSE,
    head_html TEXT DEFAULT '',
    sections JSONB DEFAULT '[]'::jsonb,
    pending_ai_proposals JSONB DEFAULT '{}'::jsonb,
    chat_histories JSONB DEFAULT '{}'::jsonb,
    report_filename TEXT,
    report_name TEXT,
    company_name TEXT,
    prompt_set TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    generated_at TIMESTAMPTZ,
    finalized_at TIMESTAMPTZ,
    prompt_checksums JSONB,
    input_files TEXT[],
    sections_modified INT,
    sections_unmodified INT,
    changes JSONB
);

CREATE INDEX IF NOT EXISTS idx_assessments_phase ON assessments(phase);
CREATE INDEX IF NOT EXISTS idx_assessments_created ON assessments(created_at DESC);

-- ─────────────────────────────────────────────────────────
-- Prompt sets
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prompt_sets (
    slug TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    description TEXT DEFAULT '',
    is_default BOOLEAN DEFAULT FALSE,
    cloned_from TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────────────────────
-- Prompts (current versions)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prompts (
    id SERIAL PRIMARY KEY,
    prompt_set TEXT NOT NULL REFERENCES prompt_sets(slug) ON DELETE CASCADE,
    prompt_name TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    sections JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(prompt_set, prompt_name)
);

CREATE INDEX IF NOT EXISTS idx_prompts_set ON prompts(prompt_set);

-- ─────────────────────────────────────────────────────────
-- Prompt versions (history)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prompt_versions (
    id SERIAL PRIMARY KEY,
    prompt_set TEXT NOT NULL,
    prompt_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    sections JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(prompt_set, prompt_name, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_prompt_versions_lookup
    ON prompt_versions(prompt_set, prompt_name, created_at DESC);

-- ─────────────────────────────────────────────────────────
-- Few-shot examples
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS examples (
    prefix TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS example_files (
    id SERIAL PRIMARY KEY,
    prefix TEXT NOT NULL REFERENCES examples(prefix) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_type TEXT,
    size_bytes INT,
    storage_path TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_example_files_prefix ON example_files(prefix);

-- ─────────────────────────────────────────────────────────
-- Reports
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    filename TEXT UNIQUE NOT NULL,
    company_name TEXT,
    storage_path TEXT NOT NULL,
    size_bytes INT,
    report_type TEXT NOT NULL DEFAULT 'generated',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reports_type ON reports(report_type);
CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at DESC);
