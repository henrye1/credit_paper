"""Stage 1: Parse Excel/PDF files to Markdown.

Uses Docling (local, no API key needed) as the primary parser.
Falls back to pandas/openpyxl for Excel files if Docling fails.
"""

from pathlib import Path

from config.settings import SUPPORTED_PARSE_EXTENSIONS


# ---------------------------------------------------------------------------
# Docling backend (primary)
# ---------------------------------------------------------------------------

def _parse_with_docling(file_path: Path, log_callback=None) -> str:
    """Parse a file to Markdown using Docling (runs locally, no API key)."""
    from docling.document_converter import DocumentConverter

    def log(msg):
        if log_callback:
            log_callback(msg)

    log(f"Parsing {file_path.name} with Docling...")

    converter = DocumentConverter()
    result = converter.convert(str(file_path))
    markdown_text = result.document.export_to_markdown()

    if not markdown_text or not markdown_text.strip():
        raise RuntimeError(f"Docling returned empty output for {file_path.name}")

    return markdown_text


# ---------------------------------------------------------------------------
# pandas/openpyxl fallback (Excel only)
# ---------------------------------------------------------------------------

def _parse_with_pandas(file_path: Path, log_callback=None) -> str:
    """Parse an Excel file to Markdown using pandas + openpyxl (local, no API)."""
    import pandas as pd

    def log(msg):
        if log_callback:
            log_callback(msg)

    log(f"Using fallback parser (pandas/openpyxl) for {file_path.name}...")

    engine = 'openpyxl'
    xls = pd.ExcelFile(file_path, engine=engine)
    md_parts = []

    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name, header=None, engine=engine)

        if df.empty:
            continue

        md_parts.append(f"## {sheet_name}\n")

        # Try to detect a header row (first row with mostly non-null string values)
        header_row = 0
        first_row = df.iloc[0]
        non_null = first_row.dropna()
        if len(non_null) > 0 and all(isinstance(v, str) for v in non_null):
            header_row = 0
        else:
            header_row = None

        if header_row is not None:
            df.columns = [str(v) if pd.notna(v) else f"Col_{i}"
                          for i, v in enumerate(df.iloc[header_row])]
            df = df.iloc[header_row + 1:].reset_index(drop=True)

        # Convert to markdown table
        df = df.fillna("")
        df = df.astype(str)
        df = df.replace("nan", "")

        if df.empty or (df == "").all().all():
            continue

        headers = list(df.columns)
        md_parts.append("| " + " | ".join(headers) + " |")
        md_parts.append("| " + " | ".join(["---"] * len(headers)) + " |")

        for _, row in df.iterrows():
            values = [str(v).replace("|", "\\|") for v in row]
            md_parts.append("| " + " | ".join(values) + " |")

        md_parts.append("")

    return "\n".join(md_parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_excel_to_markdown(file_path: Path, api_key: str = None,
                            log_callback=None) -> Path:
    """Parse an Excel file to Markdown and save alongside the original.

    Returns the path to the generated .md file.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    output_path = file_path.parent / (file_path.stem + ".md")
    markdown_text = None

    # Try Docling first
    try:
        markdown_text = _parse_with_docling(file_path, log_callback)
    except Exception as e:
        log(f"Docling failed: {e}")
        log("Falling back to pandas parser...")

    # Fallback to pandas for Excel files
    if markdown_text is None and file_path.suffix.lower() in ['.xlsx', '.xlsm']:
        markdown_text = _parse_with_pandas(file_path, log_callback)

    if markdown_text is None:
        raise RuntimeError(f"All parsers failed for {file_path.name}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_text)
    log(f"Successfully parsed {file_path.name} -> {output_path.name}")
    return output_path


def parse_all_in_directories(directories: list[Path], api_key: str = None,
                             log_callback=None) -> list[Path]:
    """Parse all supported files in the given directories.

    Returns list of generated .md file paths.
    """
    results = []
    for input_dir in directories:
        if not input_dir.exists() or not input_dir.is_dir():
            continue
        for item in input_dir.iterdir():
            if item.is_file() and item.suffix.lower() in SUPPORTED_PARSE_EXTENSIONS:
                try:
                    md_path = parse_excel_to_markdown(item, api_key, log_callback)
                    results.append(md_path)
                except Exception:
                    continue
    return results
