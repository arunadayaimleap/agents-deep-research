"""
Exa (https://exa.ai) — page contents via official exa-py SDK (get_contents / supplemental search).

When ``SEARCH_PROVIDER=exa``, ``exa_search`` is also used for web search; with ``SEARCH_PROVIDER=jina``,
Jina handles search and Exa is used for URL text extraction only.

Uses EXA_API_KEY from the environment (Exa(api_key=None) reads it).
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

from ..utils.os import get_env_with_prefix

try:
    from exa_py import Exa
except ImportError:
    Exa = None  # type: ignore[misc, assignment]

EXA_TEXT_PER_RESULT = min(int(os.getenv("EXA_SEARCH_TEXT_MAX_CHARS", "12000")), 50000)
EXA_CONTENTS_MAX_CHARS = min(int(os.getenv("EXA_CONTENTS_MAX_CHARS", "20000")), 100000)


def _exa_client() -> Any:
    if Exa is None:
        raise RuntimeError("exa-py is not installed. pip install exa-py")
    key = get_env_with_prefix("EXA_API_KEY")
    return Exa(api_key=key) if key else Exa(api_key=None)


def _result_to_dict(r: Any) -> Dict[str, Any]:
    url = getattr(r, "url", None) or ""
    title = getattr(r, "title", None) or ""
    text = getattr(r, "text", None) or ""
    highlights = getattr(r, "highlights", None)
    desc = ""
    if text and str(text).strip():
        desc = str(text).strip()[:800]
    elif highlights:
        if isinstance(highlights, str):
            desc = highlights[:800]
        elif isinstance(highlights, list):
            desc = " ".join(str(h) for h in highlights)[:800]
    return {
        "url": url,
        "title": title,
        "description": desc,
        "text": str(text)[:EXA_TEXT_PER_RESULT] if text else "",
    }


async def exa_search(
    query: str,
    max_results: int = 5,
    include_ai_overview: bool = True,
) -> List[dict]:
    """
    Neural/auto search with full text snippets (Exa search + contents).
    Mirrors legacy shape: list of {url, title, description, text?}; errors as [{"error": ...}].
    """
    _ = include_ai_overview  # Exa auto search has no separate AI overview block
    query = (query or "").strip()
    if not query:
        return [{"error": "Empty search query"}]

    def _run() -> List[dict]:
        try:
            exa = _exa_client()
            resp = exa.search(
                query,
                type="auto",
                num_results=max(1, min(max_results, 25)),
                contents={"text": {"max_characters": EXA_TEXT_PER_RESULT}},
            )
        except Exception as e:
            return [{"error": f"Exa search failed: {e!s}"}]

        rows: List[dict] = []
        for r in getattr(resp, "results", None) or []:
            rows.append(_result_to_dict(r))
        return rows if rows else [{"error": "Exa returned no results"}]

    return await asyncio.to_thread(_run)


async def exa_get_url_text(url: str, max_length: int = 10000) -> str:
    """Single URL → plain text via Exa /contents."""
    url = (url or "").strip()
    if not url:
        return "Error: empty URL"

    def _run() -> str:
        try:
            exa = _exa_client()
            cap = min(max(max_length, 500), EXA_CONTENTS_MAX_CHARS)
            resp = exa.get_contents(urls=[url], text={"max_characters": cap})
            results = getattr(resp, "results", None) or []
            if not results:
                return f"Error: No content returned for {url}"
            t = getattr(results[0], "text", None) or ""
            t = str(t).strip()
            if not t:
                return f"Error: Empty text for {url}"
            if len(t) > max_length:
                t = t[:max_length] + f"\n\n[Content truncated at {max_length} characters]"
            return t
        except Exception as e:
            return f"Error: Exa get_contents failed for {url}: {e!s}"

    return await asyncio.to_thread(_run)


async def exa_get_urls_text_ordered(urls: List[str], max_length: int) -> List[str]:
    """Batch /contents; returns texts in the same order as urls (missing → error string)."""
    urls = [u.strip() for u in urls if u and u.strip()]
    if not urls:
        return []

    def _run() -> List[str]:
        try:
            exa = _exa_client()
            cap = min(max(max_length, 500), EXA_CONTENTS_MAX_CHARS)
            resp = exa.get_contents(urls=urls, text={"max_characters": cap})
            def _norm(u: str) -> str:
                return u.strip().rstrip("/")

            by_url: Dict[str, str] = {}
            for r in getattr(resp, "results", None) or []:
                u = getattr(r, "url", None) or ""
                t = getattr(r, "text", None) or ""
                if u:
                    by_url[_norm(str(u))] = str(t)
            out: List[str] = []
            for u in urls:
                t = by_url.get(_norm(u), "")
                t = (t or "").strip()
                if not t:
                    out.append(f"Error: No content returned for {u}")
                elif len(t) > max_length:
                    out.append(t[:max_length] + f"\n\n[Truncated at {max_length}]")
                else:
                    out.append(t)
            return out
        except Exception as e:
            return [f"Error: Exa get_contents batch failed: {e!s}"] * len(urls)

    return await asyncio.to_thread(_run)
