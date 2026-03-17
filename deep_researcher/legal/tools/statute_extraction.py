"""Extract statutory references (IPC, CrPC, Constitution, etc.) from judgment text."""

import re
from typing import List

from ..models import StatuteReference


# Common Indian statutes and patterns
# Section 302 of the Indian Penal Code / IPC
# Section 154 of the Code of Criminal Procedure / CrPC
# Article 21 of the Constitution of India / Constitution

SECTION_PATTERN = re.compile(
    r"Section\s+(\d+[A-Za-z]?)\s+(?:of\s+the\s+)?([A-Za-z\s]+?)(?:\s*\.|,|\s*$)",
    re.IGNORECASE,
)
ARTICLE_PATTERN = re.compile(
    r"Article\s+(\d+[A-Za-z]?)\s+(?:of\s+the\s+)?(?:Constitution\s+of\s+India|Constitution)",
    re.IGNORECASE,
)
# Shorthand: "S. 302 IPC", "S. 154 CrPC"
SHORTHAND_SECTION = re.compile(
    r"(?:S\.|Sec\.|Section)\s+(\d+[A-Za-z]?)\s+(?:IPC|Indian\s+Penal\s+Code|CrPC|Code\s+of\s+Criminal\s+Procedure|CPC|Evidence\s+Act)",
    re.IGNORECASE,
)


def _normalize_statute_name(name: str) -> str:
    name = name.strip()
    if not name:
        return name
    # Map common shorthand to full name
    lower = name.lower()
    if "indian penal code" in lower or name.upper() == "IPC":
        return "Indian Penal Code"
    if "code of criminal procedure" in lower or "crpc" in lower:
        return "Code of Criminal Procedure"
    if "constitution" in lower:
        return "Constitution of India"
    if "evidence act" in lower:
        return "Indian Evidence Act"
    if "code of civil procedure" in lower or "cpc" in lower:
        return "Code of Civil Procedure"
    return name


def extract_statutes(text: str) -> List[StatuteReference]:
    """
    Detect statutory references in judgment text using regex.

    Supports:
    - Section XXX of the Indian Penal Code
    - Article XXX of the Constitution of India
    - S. 302 IPC, Section 154 CrPC
    """
    seen: set[tuple[str, str]] = set()
    refs: List[StatuteReference] = []

    for m in SECTION_PATTERN.finditer(text):
        section = m.group(1).strip()
        statute_raw = m.group(2).strip()
        statute = _normalize_statute_name(statute_raw)
        if not statute:
            statute = statute_raw
        key = (statute, section)
        if key in seen:
            continue
        seen.add(key)
        refs.append(StatuteReference(statute=statute, section=section, paragraph=None))

    for m in ARTICLE_PATTERN.finditer(text):
        section = m.group(1).strip()
        key = ("Constitution of India", section)
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            StatuteReference(statute="Constitution of India", section=section, paragraph=None)
        )

    for m in SHORTHAND_SECTION.finditer(text):
        section = m.group(1).strip()
        full_match = m.group(0)
        if "IPC" in full_match or "Indian Penal Code" in full_match:
            statute = "Indian Penal Code"
        elif "CrPC" in full_match or "Criminal Procedure" in full_match:
            statute = "Code of Criminal Procedure"
        elif "Evidence" in full_match:
            statute = "Indian Evidence Act"
        else:
            statute = "Code of Civil Procedure"
        key = (statute, section)
        if key in seen:
            continue
        seen.add(key)
        refs.append(StatuteReference(statute=statute, section=section, paragraph=None))

    return refs
