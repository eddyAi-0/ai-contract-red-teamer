import pdfplumber
from pathlib import Path


def extract_text_from_pdf(path: str) -> str:
    """
    Extract all text from a PDF file, page by page.
    Returns a single string with pages separated by newlines.
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

    return "\n".join(pages_text)
