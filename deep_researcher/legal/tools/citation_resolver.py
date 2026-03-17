"""Resolve citations to canonical case IDs (DB lookup + optional web fallback)."""

from typing import Awaitable, Callable, List, Optional

from ..models import Citation


async def resolve_citations(
    citations: List[Citation],
    source_case_id: Optional[str],
    db_lookup: Optional[object],
    config: Optional[object] = None,
    web_fallback: Optional[Callable[[str], Awaitable[Optional[str]]]] = None,
) -> List[Citation]:
    """
    Map citation strings to canonical case IDs.

    - db_lookup: object with .find_case_by_citation(citation_text) -> case_id or None
    - web_fallback: optional async function (citation_text) -> case_id or None; used when DB returns None
    """
    resolved = []
    for c in citations:
        case_id = None
        try:
            if db_lookup and hasattr(db_lookup, "find_case_by_citation"):
                case_id = db_lookup.find_case_by_citation(c.citation_text)
            if case_id is None and web_fallback:
                case_id = await web_fallback(c.citation_text)
        except Exception:
            pass
        if case_id:
            resolved.append(Citation(**{**c.model_dump(), "resolved_case_id": case_id}))
        else:
            resolved.append(c)
    return resolved
