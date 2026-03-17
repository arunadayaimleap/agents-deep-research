"""Extract Indian legal case citations from judgment text using regex patterns."""

import re
from typing import List

from ..models import Citation


# Indian citation patterns (SCC, AIR, SCR, etc.)
# (YYYY) X SCC XXX - Supreme Court Cases
# (YYYY) X SCC (Cri) XXX - Criminal
# (YYYY) X SCC (L&S) XXX - Labour & Services
# AIR YYYY SC XXXX - All India Reporter Supreme Court
# AIR YYYY SC 1234 or AIR 1996 SC 1393
# YYYY SCC (Cri) XXX
# Also: SCR, Scale, JT, etc.

SCC_PATTERN = re.compile(
    r"\((\d{4})\)\s+(\d+)\s+SCC\s+(?:\([A-Za-z\s&]+\)\s+)?(\d+)",
    re.IGNORECASE,
)
AIR_SC_PATTERN = re.compile(
    r"AIR\s+(\d{4})\s+(?:SC|Supreme\s*Court)\s+(\d+)",
    re.IGNORECASE,
)
AIR_HC_PATTERN = re.compile(
    r"AIR\s+(\d{4})\s+(?:HC|(?:Cal|Bom|Mad|Del|All)\s*HC)\s+(\d+)",
    re.IGNORECASE,
)
def extract_citations(text: str, include_paragraph_numbers: bool = False) -> List[Citation]:
    """
    Detect all case citations in judgment text using regex patterns.

    Supports:
    - (YYYY) X SCC XXX and (YYYY) X SCC (Cri) XXX
    - AIR YYYY SC XXXX
    - AIR YYYY [High Court] XXXX

    Returns list of Citation objects. Paragraph numbers are optional
    (requires paragraph-split text and matching).
    """
    seen: set[str] = set()
    citations: List[Citation] = []

    # SCC
    for m in SCC_PATTERN.finditer(text):
        citation_text = m.group(0).strip()
        if citation_text in seen:
            continue
        seen.add(citation_text)
        citations.append(Citation(citation_text=citation_text, paragraph=None))

    # Standalone AIR SC
    for m in AIR_SC_PATTERN.finditer(text):
        citation_text = m.group(0).strip()
        if citation_text in seen:
            continue
        seen.add(citation_text)
        citations.append(Citation(citation_text=citation_text, paragraph=None))

    # Standalone AIR HC
    for m in AIR_HC_PATTERN.finditer(text):
        citation_text = m.group(0).strip()
        if citation_text in seen:
            continue
        seen.add(citation_text)
        citations.append(Citation(citation_text=citation_text, paragraph=None))

    return citations
