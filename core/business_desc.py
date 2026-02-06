"""Stage 2: Extract company business descriptions via web scraping + LLM synthesis."""

import os
import re
import json
import time
from pathlib import Path

import requests
import pandas as pd

from config.settings import FIRECRAWL_API_KEY, GOOGLE_API_KEY, MODELS


def extract_company_name_from_excel(excel_filepath: Path) -> str:
    """Extract company name from the first few rows of an Excel file."""
    try:
        df = pd.read_excel(excel_filepath, header=None, nrows=10, engine='openpyxl')
        for _, row in df.iterrows():
            if row.empty:
                continue
            first_cell = str(row.iloc[0]).strip()
            if first_cell and 3 < len(first_cell) < 100:
                if first_cell.lower().startswith("type") or \
                   first_cell.lower().startswith("debt seniority"):
                    continue
                # Clean the name
                name = re.sub(r"\|.*$", "", first_cell).strip()
                name = re.sub(r";;;+.*$", "", name).strip()
                name = re.sub(r"\s{2,}", " ", name).strip()
                name = re.sub(r"\s*\((Pty|PTY)\)\s*(Ltd|LTD)\.?$", "", name, flags=re.IGNORECASE).strip()
                name = re.sub(r"\s*(Pty|PTY)\s*(Ltd|LTD)\.?$", "", name, flags=re.IGNORECASE).strip()
                name = re.sub(r"\s*Ltd\.?$", "", name, flags=re.IGNORECASE).strip()
                name_match = re.match(r"([\w\s\.\(\)-]+)", name)
                if name_match:
                    name = name_match.group(1).strip()
                name_for_search = re.sub(r"^\d+\s*\.?\s*", "", name).strip()
                if len(name_for_search.split()) > 1 and len(name_for_search.split()) < 10:
                    return name_for_search
    except Exception:
        pass

    # Fallback: clean filename
    stem = excel_filepath.stem
    name = re.sub(r"^\d+\s*\.?\s*", "", stem).strip()
    name = re.sub(r"\s*\((Pty|PTY)\)\s*(Ltd|LTD)\.?$", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"\s*(Pty|PTY)\s*(Ltd|LTD)\.?$", "", name, flags=re.IGNORECASE).strip()
    return name if name else "Unknown_Company"


def _firecrawl_search(company_name: str, api_key: str) -> list[str]:
    """Search for company URLs using Firecrawl."""
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {
        "query": f"official website and business overview for {company_name}",
        "pageOptions": {"includeMarkdown": False, "includeHtml": False}
    }
    try:
        response = requests.post("https://api.firecrawl.dev/v0/search",
                                 headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        if data.get('success') and 'data' in data:
            urls = []
            for item in data['data'][:2]:
                if isinstance(item, dict):
                    metadata = item.get('metadata', {})
                    url = metadata.get('url') or metadata.get('sourceURL')
                    if url and isinstance(url, str) and url.startswith('http'):
                        urls.append(url)
            return urls
    except Exception:
        pass
    return []


def _firecrawl_scrape(url: str, company_name: str, api_key: str) -> str:
    """Scrape and extract content from a URL using Firecrawl."""
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {
        "url": url,
        "pageOptions": {"onlyMainContent": True, "includeHtml": False},
        "llmExtractionOptions": {
            "mode": "markdown",
            "prompt": (
                f"From the content of this page about '{company_name}', extract detailed "
                "information about its core business activities, main products or services, "
                "and the primary industry it operates in."
            ),
        }
    }
    try:
        response = requests.post("https://api.firecrawl.dev/v0/scrape",
                                 headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        if data.get('success') and 'data' in data:
            return data['data'].get('llm_extraction') or data['data'].get('markdown') or None
        if data.get('success') and 'jobId' in data:
            return _poll_firecrawl_job(data['jobId'], api_key)
    except Exception:
        pass
    return None


def _poll_firecrawl_job(job_id: str, api_key: str) -> str:
    """Poll a Firecrawl job until completion."""
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    for _ in range(18):
        try:
            response = requests.get(f"https://api.firecrawl.dev/v0/scrape/{job_id}",
                                    headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data.get('status') == 'completed':
                result = data.get('data', {})
                return result.get('llm_extraction') or result.get('markdown')
            elif data.get('status') == 'failed':
                return None
        except Exception:
            pass
        time.sleep(10)
    return None


def _synthesize_with_gemini(company_name: str, extracted_text: str,
                            api_key: str = None) -> str:
    """Use Gemini to synthesize a concise business description."""
    from google import genai
    key = api_key or GOOGLE_API_KEY
    client = genai.Client(api_key=key)
    model = MODELS.get("business_description", "gemini-2.5-flash-preview-05-20")

    if len(extracted_text) > 70000:
        extracted_text = extracted_text[:70000]

    prompt = f"""You are an expert business analyst. Based *only* on the following text about the company "{company_name}", provide a concise business activity description.
Instructions:
1. Single paragraph, 5 to 8 sentences.
2. Summarize main activities, primary services or products, related companies if part of a group, BEE ownership and industry.
3. Focus on what the company *does*.
4. Use neutral, factual language.
5. Do not start with "This company..." - start directly with the description.
6. If insufficient information, respond with only "Insufficient information."

Extracted Text for "{company_name}":
---
{extracted_text}
---
Concise Business Activity Description:"""

    response = client.models.generate_content(model=model, contents=[prompt])
    text = ""
    if hasattr(response, 'text') and response.text:
        text = response.text.strip()
    if "insufficient information" in text.lower() or len(text) < 30:
        return None
    return text


def extract_business_description(inputs_dir: Path, api_key_google: str = None,
                                 api_key_firecrawl: str = None,
                                 log_callback=None) -> str:
    """Main orchestrator: find company, check existing description, fetch if needed.

    Returns the business description text.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    fc_key = api_key_firecrawl or FIRECRAWL_API_KEY
    g_key = api_key_google or GOOGLE_API_KEY
    desc_filepath = inputs_dir / "company_business_description.txt"

    # Find target Excel
    excel_files = sorted(list(inputs_dir.glob('*.xlsx')))
    if not excel_files:
        raise FileNotFoundError("No Excel (.xlsx) file found in inputs directory.")
    company_name = extract_company_name_from_excel(excel_files[0])
    log(f"Target company: {company_name}")

    # Check existing description
    start_delim = f"--- START COMPANY: {company_name} ---"
    end_delim = f"--- END COMPANY: {company_name} ---"

    if desc_filepath.exists():
        content = desc_filepath.read_text(encoding='utf-8')
        pattern = re.compile(
            rf"{re.escape(start_delim)}(.*?){re.escape(end_delim)}",
            re.DOTALL | re.IGNORECASE
        )
        match = pattern.search(content)
        if match:
            existing = match.group(1).strip()
            if len(existing) > 70 and "could not be automatically generated" not in existing:
                log(f"Existing description found for {company_name}. Skipping web update.")
                return existing

    # Fetch via web scraping
    log(f"Searching web for {company_name}...")
    urls = _firecrawl_search(company_name, fc_key)
    all_markdown = []
    for url in urls:
        md = _firecrawl_scrape(url, company_name, fc_key)
        if md:
            all_markdown.append(md)
        time.sleep(1)

    description = None
    if all_markdown:
        combined = "\n\n---\n\n".join(all_markdown)
        description = _synthesize_with_gemini(company_name, combined, g_key)

    if not description:
        description = f"Business description for {company_name} could not be automatically generated."
        log(f"Could not generate description for {company_name}.")

    # Write to file
    new_block = f"{start_delim}\n{description}\n{end_delim}\n"
    if desc_filepath.exists():
        content = desc_filepath.read_text(encoding='utf-8')
        pattern = re.compile(
            rf"{re.escape(start_delim)}.*?\n{re.escape(end_delim)}\n?",
            re.DOTALL | re.IGNORECASE
        )
        if pattern.search(content):
            updated = pattern.sub(new_block, content)
        else:
            updated = content.rstrip() + f"\n\n{new_block}"
    else:
        updated = new_block

    desc_filepath.write_text(updated, encoding='utf-8')
    log(f"Business description saved to {desc_filepath.name}")
    return description
