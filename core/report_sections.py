"""Report section parsing, reassembly, and AI-assisted editing."""

import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag, NavigableString

from core.gemini_client import GeminiClient, clean_html_response
from config.settings import MODELS


# ──────────────────────────────────────────────────────────────────────────────
# Parsing & reassembly
# ──────────────────────────────────────────────────────────────────────────────

def parse_report_to_sections(html_content: str) -> dict:
    """Parse a generated HTML report into editable sections at h2 boundaries.

    Handles two report structures:
      - Flat: h2 tags are direct children of body or a container div
      - Paged: content is inside div.page wrappers, h2s inside pages

    Returns dict with keys:
        head_html: str - the <head> block (with styles)
        body_prefix: str - any wrapper HTML before the content (e.g. opening page divs)
        sections: list[dict] - each with id, title, html, status, original_html
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Extract head
    head_tag = soup.find('head')
    head_html = str(head_tag) if head_tag else ""

    # Collect ALL elements in document order by flattening page wrappers
    # This handles both flat and paged structures uniformly
    body = soup.body
    if not body:
        return {"head_html": head_html, "body_prefix": "", "sections": []}

    # Gather all content-level elements in order
    all_elements = []
    _collect_elements(body, all_elements)

    # Split at h2 boundaries
    sections = []
    current_parts = []
    current_h2 = None

    for el_html, el_tag in all_elements:
        is_h2 = isinstance(el_tag, Tag) and el_tag.name == 'h2'

        if is_h2:
            # Flush previous section
            if current_parts:
                _flush_section(sections, current_h2, current_parts)
                current_parts = []
            current_h2 = el_tag
            current_parts.append(el_html)
        else:
            current_parts.append(el_html)

    # Flush final section
    if current_parts:
        _flush_section(sections, current_h2, current_parts)

    return {
        "head_html": head_html,
        "body_prefix": "",
        "sections": sections,
    }


def _collect_elements(parent, result):
    """Recursively collect content elements, flattening page wrappers."""
    for child in parent.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                result.append((str(child), child))
            continue

        if not isinstance(child, Tag):
            continue

        # If it's a page wrapper div, recurse into it
        classes = child.get('class', [])
        if child.name == 'div' and 'page' in classes:
            _collect_elements(child, result)
        else:
            # It's a real content element - keep it
            result.append((str(child), child))


def _flush_section(sections, h2_tag, parts):
    """Create a section dict and append to sections list."""
    html = "\n".join(parts)
    if h2_tag is not None:
        section_id = h2_tag.get('id', f'section_{len(sections)}')
        title = h2_tag.get_text(strip=True)
    else:
        section_id = "__preamble__"
        title = "Cover Page"
    sections.append({
        "id": section_id,
        "title": title,
        "html": html,
        "status": "pending",
        "original_html": html,
    })


def reassemble_report_html(parsed: dict) -> str:
    """Rebuild the complete HTML document from parsed sections."""
    head_html = parsed["head_html"]
    sections_html = "\n".join(s["html"] for s in parsed["sections"])
    return (
        f'<!DOCTYPE html>\n<html lang="en">\n{head_html}\n'
        f'<body>\n{sections_html}\n</body>\n</html>'
    )


# ──────────────────────────────────────────────────────────────────────────────
# HTML ↔ readable text conversion
# ──────────────────────────────────────────────────────────────────────────────

def section_html_to_text(html: str) -> str:
    """Convert section HTML to human-readable text for editing.

    Headings → ## / ### / ####
    Paragraphs → plain text
    Lists → - bullet items
    Tables → markdown-style tables
    """
    soup = BeautifulSoup(html, 'html.parser')
    lines = []

    for tag in soup.find_all(True, recursive=False):
        _tag_to_lines(tag, lines)

    return "\n".join(lines).strip()


def _tag_to_lines(tag, lines):
    """Recursively convert a single tag to text lines."""
    if not isinstance(tag, Tag):
        return

    name = tag.name

    if name == 'h2':
        lines.append(f"## {tag.get_text(strip=True)}")
        lines.append("")
    elif name == 'h3':
        lines.append(f"### {tag.get_text(strip=True)}")
        lines.append("")
    elif name == 'h4':
        lines.append(f"#### {tag.get_text(strip=True)}")
        lines.append("")
    elif name == 'p':
        text = tag.get_text(strip=True)
        if text:
            # Preserve bold markers
            for strong in tag.find_all(['strong', 'b']):
                strong_text = strong.get_text(strip=True)
                if strong_text:
                    strong.replace_with(f"**{strong_text}**")
            text = tag.get_text(strip=True)
            lines.append(text)
            lines.append("")
    elif name in ('ul', 'ol'):
        for li in tag.find_all('li', recursive=False):
            lines.append(f"- {li.get_text(strip=True)}")
        lines.append("")
    elif name == 'table':
        _table_to_lines(tag, lines)
        lines.append("")
    elif name == 'div':
        # Recurse into div content (e.g. page-break divs, headers, etc.)
        for child in tag.find_all(True, recursive=False):
            _tag_to_lines(child, lines)
    # Skip other elements (style, script, etc.)


def _table_to_lines(table_tag, lines):
    """Convert HTML table to markdown-style table lines."""
    headers = []
    thead = table_tag.find('thead')
    if thead:
        tr = thead.find('tr')
        if tr:
            headers = [th.get_text(strip=True) for th in tr.find_all(['th', 'td'])]

    rows = []
    tbody = table_tag.find('tbody')
    source = tbody if tbody else table_tag
    for tr in source.find_all('tr'):
        cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
        if cells and cells != headers:
            rows.append(cells)

    # If no thead, use first row as header
    if not headers and rows:
        headers = rows.pop(0)

    if not headers and not rows:
        return

    col_count = max(len(headers), max((len(r) for r in rows), default=0))
    # Pad headers/rows to consistent column count
    headers = headers + [''] * (col_count - len(headers))

    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * col_count) + " |")
    for row in rows:
        row = row + [''] * (col_count - len(row))
        lines.append("| " + " | ".join(row) + " |")


def text_to_section_html(text: str, original_html: str = "") -> str:
    """Convert edited plain text back to section HTML.

    Handles: ## headings, - bullets, | tables |, **bold**, paragraphs.
    Preserves id/class from original section headings where possible.
    """
    # Extract heading attrs from original for preservation
    heading_attrs = {}
    if original_html:
        orig_soup = BeautifulSoup(original_html, 'html.parser')
        for h in orig_soup.find_all(['h2', 'h3', 'h4']):
            heading_attrs[h.get_text(strip=True)] = {
                'id': h.get('id', ''),
                'class': ' '.join(h.get('class', [])),
            }

    text_lines = text.strip().split('\n')
    html_parts = []
    in_list = False
    table_rows = []

    def flush_list():
        nonlocal in_list
        if in_list:
            html_parts.append('</ul>')
            in_list = False

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return
        # Find separator row to split headers from data
        sep_idx = None
        for i, row in enumerate(table_rows):
            if row is None:
                sep_idx = i
                break

        html_parts.append('<table>')
        if sep_idx is not None and sep_idx > 0:
            html_parts.append('<thead><tr>')
            for cell in table_rows[0]:
                html_parts.append(f'<th>{cell}</th>')
            html_parts.append('</tr></thead>')
            data = [r for r in table_rows[sep_idx + 1:] if r is not None]
        else:
            data = [r for r in table_rows if r is not None]

        if data:
            html_parts.append('<tbody>')
            for row in data:
                html_parts.append('<tr>')
                for cell in row:
                    html_parts.append(f'<td>{cell}</td>')
                html_parts.append('</tr>')
            html_parts.append('</tbody>')
        html_parts.append('</table>')
        table_rows.clear()

    for line in text_lines:
        stripped = line.strip()

        # Empty line
        if not stripped:
            if table_rows:
                flush_table()
            if in_list:
                flush_list()
            continue

        # Table row
        if stripped.startswith('|') and stripped.endswith('|'):
            if in_list:
                flush_list()
            cells = [c.strip() for c in stripped[1:-1].split('|')]
            # Detect separator row (all dashes)
            if all(re.match(r'^-+$', c.strip()) for c in cells if c.strip()):
                table_rows.append(None)
            else:
                table_rows.append(cells)
            continue
        elif table_rows:
            flush_table()

        # Headings
        if stripped.startswith('#### '):
            if in_list:
                flush_list()
            text_content = stripped[5:]
            attrs = heading_attrs.get(text_content, {})
            id_attr = f' id="{attrs["id"]}"' if attrs.get('id') else ''
            html_parts.append(f'<h4{id_attr}>{text_content}</h4>')
            continue
        if stripped.startswith('### '):
            if in_list:
                flush_list()
            text_content = stripped[4:]
            attrs = heading_attrs.get(text_content, {})
            id_attr = f' id="{attrs["id"]}"' if attrs.get('id') else ''
            html_parts.append(f'<h3{id_attr}>{text_content}</h3>')
            continue
        if stripped.startswith('## '):
            if in_list:
                flush_list()
            text_content = stripped[3:]
            attrs = heading_attrs.get(text_content, {})
            id_attr = f' id="{attrs["id"]}"' if attrs.get('id') else ''
            cls = f' class="{attrs["class"]}"' if attrs.get('class') else ''
            html_parts.append(f'<h2{cls}{id_attr}>{text_content}</h2>')
            continue

        # List items
        if stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            item_text = stripped[2:]
            html_parts.append(f'<li>{item_text}</li>')
            continue

        # Regular paragraph
        if in_list:
            flush_list()
        # Convert **bold** to <strong>
        para = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
        html_parts.append(f'<p>{para}</p>')

    # Flush remaining
    if table_rows:
        flush_table()
    if in_list:
        flush_list()

    return '\n'.join(html_parts)


# ──────────────────────────────────────────────────────────────────────────────
# AI-assisted section editing
# ──────────────────────────────────────────────────────────────────────────────

def generate_section_update(section_html: str,
                            instruction: str,
                            evidence_files: list = None,
                            full_report_context: str = None,
                            model: str = None,
                            api_key: str = None,
                            log_callback=None) -> dict:
    """Use Gemini to update a single report section based on analyst instructions.

    Returns dict with keys: success, updated_html, message.
    """
    model_name = model or MODELS.get("section_edit", MODELS["report_generation"])

    def log(msg):
        if log_callback:
            log_callback(msg)

    client = GeminiClient(api_key)

    try:
        # Upload evidence files
        file_objs = []
        if evidence_files:
            for fp in evidence_files:
                fp = Path(fp)
                if fp.exists():
                    obj = client.upload_file(fp, display_name=fp.name)
                    if obj:
                        file_objs.append(obj)

        # Build prompt contents
        contents = [
            "You are an expert financial analyst assistant helping to refine a "
            "Financial Condition Assessment Report. Your task is to update a single "
            "section of the report based on the analyst's instructions.\n\n"
            "CRITICAL RULES:\n"
            "1. Return ONLY the updated HTML for this section.\n"
            "2. Preserve the exact HTML tag structure: use the same h2, h3, h4, p, "
            "table, ul, ol tags with their existing CSS classes and id attributes.\n"
            "3. Do NOT include <!DOCTYPE>, <html>, <head>, <body>, or container <div> tags.\n"
            "4. Maintain the professional financial reporting tone.\n"
            "5. Keep all tables properly formatted with <thead>, <tbody>, <th>, <td>.\n"
            "6. If the instruction asks to add data from evidence files, integrate it "
            "naturally into the existing narrative.\n\n"
            "--- CURRENT SECTION HTML ---\n",
            section_html,
            "\n--- END CURRENT SECTION HTML ---\n",
        ]

        if full_report_context:
            contents.extend([
                "\n--- FULL REPORT CONTEXT (read-only, for reference) ---\n",
                full_report_context,
                "\n--- END FULL REPORT CONTEXT ---\n",
            ])

        if file_objs:
            contents.append("\n--- ADDITIONAL EVIDENCE FILES ---\n")
            contents.extend(file_objs)
            contents.append("\n--- END EVIDENCE FILES ---\n")

        contents.append(
            f"\n--- ANALYST INSTRUCTION ---\n{instruction}\n--- END INSTRUCTION ---\n"
            "\nNow return the updated section HTML."
        )

        log(f"Sending section update request to Gemini ({model_name})...")
        response = client.generate_content(model=model_name, contents=contents)
        cleaned = clean_html_response(response)

        return {
            "success": True,
            "updated_html": cleaned,
            "message": "Section updated successfully.",
        }

    except Exception as e:
        return {
            "success": False,
            "updated_html": "",
            "message": str(e),
        }

    finally:
        client.cleanup_files()
