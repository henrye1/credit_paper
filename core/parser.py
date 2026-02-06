"""Stage 1: Parse Excel files to Markdown using LlamaParse."""

import asyncio
import traceback
from pathlib import Path

import nest_asyncio
nest_asyncio.apply()

from config.settings import LLAMACLOUD_API_KEY, SUPPORTED_PARSE_EXTENSIONS


def initialize_parser(api_key: str = None):
    """Initialize and return a LlamaParse parser instance."""
    from llama_parse import LlamaParse
    key = api_key or LLAMACLOUD_API_KEY
    if not key:
        raise ValueError("LLAMACLOUD_API_KEY not configured. Set it in .env or pass directly.")
    return LlamaParse(api_key=key, result_type="markdown", verbose=True)


async def _parse_file(parser, file_path: Path) -> str:
    """Parse a single file using LlamaParse. Returns markdown text or raises."""
    documents = await parser.aload_data(str(file_path))
    if documents and len(documents) > 0 and hasattr(documents[0], 'text') and documents[0].text:
        return documents[0].text
    raise RuntimeError(f"Could not extract text from {file_path.name}")


def parse_excel_to_markdown(file_path: Path, api_key: str = None,
                            log_callback=None) -> Path:
    """Parse an Excel file to Markdown and save alongside the original.

    Returns the path to the generated .md file.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    parser = initialize_parser(api_key)
    output_path = file_path.parent / (file_path.stem + ".md")

    log(f"Parsing {file_path.name} with LlamaParse...")

    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        markdown_text = loop.run_until_complete(_parse_file(parser, file_path))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)
        log(f"Successfully parsed {file_path.name} -> {output_path.name}")
        return output_path
    except Exception as e:
        log(f"Error parsing {file_path.name}: {e}")
        raise


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
