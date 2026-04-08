"""Extract text from PDF, Word, and URL for judgment processing."""

import asyncio
from pathlib import Path
from typing import Optional

# Optional deps - fail gracefully if not installed
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from docx import Document as DocxDocument
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


def extract_text_from_pdf(path: str) -> str:
    """
    Extract text from a PDF file using pdfplumber.

    Requires: pip install pdfplumber
    """
    if not HAS_PDFPLUMBER:
        raise RuntimeError(
            "PDF extraction requires pdfplumber. Install with: pip install pdfplumber"
        )
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            block = page.extract_text()
            if block:
                text_parts.append(block)
    return "\n\n".join(text_parts) if text_parts else ""


def extract_text_from_docx(path: str) -> str:
    """
    Extract text from a Word document.

    Requires: pip install python-docx
    """
    if not HAS_DOCX:
        raise RuntimeError(
            "DOCX extraction requires python-docx. Install with: pip install python-docx"
        )
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"DOCX not found: {path}")
    doc = DocxDocument(path)
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


async def extract_text_from_url(url: str) -> str:
    """
    Fetch page HTML-derived text from a URL via Exa get_contents.

    Call from async context.
    """
    from .exa_tools import exa_get_url_text

    return await exa_get_url_text(url, max_length=500000)


async def extract_text(
    *,
    text: Optional[str] = None,
    pdf_path: Optional[str] = None,
    url: Optional[str] = None,
    docx_path: Optional[str] = None,
) -> str:
    """
    Extract judgment text from one of the supported sources.
    Exactly one of text, pdf_path, url, docx_path must be provided.
    """
    provided = sum(1 for x in (text, pdf_path, url, docx_path) if x is not None)
    if provided != 1:
        raise ValueError(
            "Exactly one of text, pdf_path, url, docx_path must be provided"
        )
    if text is not None:
        return text.strip()
    if pdf_path is not None:
        return extract_text_from_pdf(pdf_path)
    if docx_path is not None:
        return extract_text_from_docx(docx_path)
    if url is not None:
        return await extract_text_from_url(url)
    raise AssertionError("Unreachable")
