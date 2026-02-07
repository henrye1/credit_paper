"""Stage 2: Extract company business descriptions via web scraping + LLM synthesis."""

import os
import re
import json
import time
from pathlib import Path

import requests
import pandas as pd

from config.settings import FIRECRAWL_API_KEY, GOOGLE_API_KEY, MODELS


# ---------------------------------------------------------------------------
# Company identity extraction
# ---------------------------------------------------------------------------

def extract_company_info_from_pdf(pdf_path: Path, log_callback=None) -> dict:
    """Extract company name and registration number from a PDF using Docling.

    Returns dict with 'name', 'registration_number', 'raw_text' (first pages).
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    try:
        from docling.document_converter import DocumentConverter

        log(f"Extracting company info from PDF: {pdf_path.name}...")
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        full_text = result.document.export_to_markdown()

        if not full_text or not full_text.strip():
            return {}

        # Use only the first ~5000 chars (cover page + first few pages)
        front_text = full_text[:5000]

        info = {'raw_text': front_text}

        # Extract registration number patterns common in SA financial statements
        # Formats: 2001/012345/07, Registration number: 2001/012345/07, etc.
        reg_patterns = [
            r'[Rr]egistration\s*(?:[Nn]umber|[Nn]o\.?)\s*[:;]?\s*(\d{4}/\d{5,7}/\d{2})',
            r'[Cc]ompany\s*[Rr]eg(?:istration)?\.?\s*(?:[Nn]o\.?|[Nn]umber)\s*[:;]?\s*(\d{4}/\d{5,7}/\d{2})',
            r'[Rr]eg\.?\s*[Nn]o\.?\s*[:;]?\s*(\d{4}/\d{5,7}/\d{2})',
            r'(\d{4}/\d{5,7}/\d{2})',
        ]
        for pattern in reg_patterns:
            match = re.search(pattern, front_text)
            if match:
                info['registration_number'] = match.group(1)
                break

        # Extract company name - look for common patterns in SA AFS
        # Note: Docling OCR may strip/merge spaces, so patterns handle both
        name_patterns = [
            # Markdown heading: "## COMPANY NAME (PTY) LTD" or "## COMPANY(PTY)LTD"
            r'#{1,3}\s+([A-Z][A-Z\s&\'-]{1,50}\s*\(?(?:PTY|Pty|pty)\)?\s*(?:LTD|Ltd)\.?)',
            # "COMPANY NAME (Pty) Ltd" with normal spaces
            r'(?:^|\n)\s*([A-Z][A-Za-z\s&\'-]{2,50}\s*\((?:PTY|Pty|pty)\)\s*(?:LTD|Ltd)\.?)',
            # OCR-joined: "COMPANY(PTY)LTD" or "COMPANY(PTY) LTD"
            r'(?:^|\n)\s*([A-Z][A-Z\s&\'-]{2,50}\(?(?:PTY|Pty)\)?\s*(?:LTD|Ltd)\.?)',
            # After "Financial Statements of/for" (with possible OCR spacing)
            r'(?:[Ff]inancial\s*[Ss]tatements?\s*(?:of|for)\s*)([A-Z][A-Za-z\s&\'-]{2,60}(?:\(Pty\)\s*Ltd\.?|Limited)?)',
            # Proprietary Limited variant
            r'(?:^|\n)\s*([A-Z][A-Za-z\s&\'-]{2,50}(?:Proprietary\s+)?Limited)',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, front_text)
            if match:
                name = match.group(1).strip()
                # Clean up markdown artifacts and normalise spacing
                name = re.sub(r'[#*]+', '', name).strip()
                name = re.sub(r'\s+', ' ', name).strip()
                # Normalise (PTY)LTD -> (Pty) Ltd
                name = re.sub(r'\(PTY\)\s*LTD', '(Pty) Ltd', name, flags=re.IGNORECASE)
                name = re.sub(r'\(PTY\)', '(Pty)', name, flags=re.IGNORECASE)
                name = re.sub(r'LTD$', 'Ltd', name, flags=re.IGNORECASE)
                if len(name) > 5 and len(name) < 100:
                    info['name'] = name
                    break

        if 'name' in info:
            log(f"PDF company name: {info['name']}")
        if 'registration_number' in info:
            log(f"PDF registration number: {info['registration_number']}")

        return info

    except Exception as e:
        if log_callback:
            log(f"PDF extraction failed: {e}")
        return {}


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


def _clean_name_for_search(full_name: str) -> str:
    """Strip legal suffixes for web search while keeping the core name."""
    name = full_name
    name = re.sub(r"\s*\((Pty|PTY)\)\s*(Ltd|LTD)\.?", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"\s*(Proprietary\s+)?Limited$", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"\s*Ltd\.?$", "", name, flags=re.IGNORECASE).strip()
    return name.strip()


# ---------------------------------------------------------------------------
# Firecrawl web scraping
# ---------------------------------------------------------------------------

def _firecrawl_search(company_name: str, api_key: str,
                      registration_number: str = None) -> list[str]:
    """Search for company URLs using Firecrawl."""
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

    # Build a targeted search query
    search_name = _clean_name_for_search(company_name)
    query_parts = [search_name, "South Africa", "company"]
    if registration_number:
        query_parts.append(registration_number)
    query = " ".join(query_parts)

    payload = {
        "query": query,
        "pageOptions": {"includeMarkdown": False, "includeHtml": False}
    }
    try:
        response = requests.post("https://api.firecrawl.dev/v0/search",
                                 headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        if data.get('success') and 'data' in data:
            urls = []
            for item in data['data'][:3]:
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
        "formats": ["markdown"],
        "onlyMainContent": True,
    }
    try:
        response = requests.post("https://api.firecrawl.dev/v1/scrape",
                                 headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        if data.get('success') and 'data' in data:
            return data['data'].get('markdown') or None
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


# ---------------------------------------------------------------------------
# LLM synthesis
# ---------------------------------------------------------------------------

def _synthesize_with_gemini(company_name: str, extracted_text: str,
                            api_key: str = None) -> str:
    """Use Gemini to synthesize a concise business description."""
    from google import genai
    key = api_key or GOOGLE_API_KEY
    client = genai.Client(api_key=key)
    model = MODELS.get("business_description", "gemini-2.5-flash")

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


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def extract_business_description(inputs_dir: Path, api_key_google: str = None,
                                 api_key_firecrawl: str = None,
                                 log_callback=None) -> str:
    """Main orchestrator: find company, check existing description, fetch if needed.

    Extracts company name and registration number from the PDF AFS first,
    falls back to the Excel file for the company name.

    Returns the business description text.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    fc_key = api_key_firecrawl or FIRECRAWL_API_KEY
    g_key = api_key_google or GOOGLE_API_KEY
    desc_filepath = inputs_dir / "company_business_description.txt"

    # --- Step 1: Extract company identity from PDF AFS ---
    pdf_files = sorted(inputs_dir.glob('*.pdf'))
    pdf_info = {}
    if pdf_files:
        pdf_info = extract_company_info_from_pdf(pdf_files[0], log_callback)

    # --- Step 2: Determine company name (PDF > Excel > filename) ---
    company_name = pdf_info.get('name', '')
    registration_number = pdf_info.get('registration_number', '')

    if not company_name:
        # Fall back to Excel-based extraction
        excel_files = sorted(
            list(inputs_dir.glob('*.xlsx')) + list(inputs_dir.glob('*.xlsm'))
        )
        if not excel_files:
            raise FileNotFoundError("No Excel (.xlsx/.xlsm) file found in inputs directory.")
        company_name = extract_company_name_from_excel(excel_files[0])

    log(f"Target company: {company_name}")
    if registration_number:
        log(f"Registration number: {registration_number}")

    # --- Step 3: Check for existing cached description ---
    search_name = _clean_name_for_search(company_name)
    start_delim = f"--- START COMPANY: {search_name} ---"
    end_delim = f"--- END COMPANY: {search_name} ---"

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
                log(f"Existing description found for {search_name}. Skipping web update.")
                return existing

    # --- Step 4: Try to synthesize from PDF text directly ---
    pdf_raw = pdf_info.get('raw_text', '')
    description = None

    if pdf_raw and len(pdf_raw) > 200:
        log("Attempting to extract business description from PDF content...")
        try:
            description = _synthesize_with_gemini(company_name, pdf_raw, g_key)
            if description:
                log("Business description extracted from PDF AFS.")
        except Exception as e:
            log(f"Gemini synthesis from PDF failed: {e}")

    # --- Step 5: Fetch via web scraping if PDF didn't yield a description ---
    if not description:
        log(f"Searching web for {search_name} (South Africa)...")
        urls = _firecrawl_search(company_name, fc_key, registration_number)
        all_markdown = []
        for url in urls:
            log(f"  Scraping: {url[:80]}...")
            md = _firecrawl_scrape(url, company_name, fc_key)
            if md:
                all_markdown.append(md)
            time.sleep(1)

        if all_markdown:
            combined = "\n\n---\n\n".join(all_markdown)
            try:
                description = _synthesize_with_gemini(company_name, combined, g_key)
            except Exception as e:
                log(f"Gemini synthesis from web content failed: {e}")

    # --- Step 6: Final fallback ---
    if not description:
        description = f"Business description for {search_name} could not be automatically generated."
        log(f"Could not generate description for {search_name}.")

    # --- Step 7: Write to file ---
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
