import pdfplumber
from pathlib import Path

_TRUNCATION_MARKER = "\n[... text truncated at {limit} characters to optimize analysis ...]"


def extract_text_from_pdf(path: str, max_chars: int | None = 25000) -> tuple[str, bool]:
    """
    Extract all text from a PDF file, page by page.
    Returns (text, was_truncated).
    If max_chars is None, returns the full text with no limit.
    If the extracted text exceeds max_chars, truncates at the last paragraph
    boundary before the limit and appends a truncation marker.
    Raises FileNotFoundError if the path does not exist.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    pages_text = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                pages_text.append(page_text)

    full_text = "\n".join(pages_text)

    if max_chars is None or len(full_text) <= max_chars:
        return full_text, False

    # Truncate at last paragraph boundary before max_chars
    cut = full_text.rfind("\n\n", 0, max_chars)
    if cut == -1:
        cut = full_text.rfind("\n", 0, max_chars)
    if cut == -1:
        cut = max_chars

    truncated = full_text[:cut].rstrip() + _TRUNCATION_MARKER.format(limit=max_chars)
    return truncated, True
