"""
OpenRouter server tools: web search and web fetch.

Docs:
- https://openrouter.ai/docs/guides/features/server-tools/web-search
- https://openrouter.ai/docs/guides/features/server-tools/web-fetch
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import aiohttp

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


def _api_key() -> str:
    key = os.getenv("DR_OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OPENROUTER_API_KEY is required for OpenRouter web search/fetch")
    return key


def _tool_model() -> str:
    return (
        os.getenv("DR_OPENROUTER_TOOL_MODEL")
        or os.getenv("OPENROUTER_TOOL_MODEL")
        or "google/gemini-2.5-flash"
    )


def _search_engine() -> str:
    return os.getenv("DR_OPENROUTER_SEARCH_ENGINE") or os.getenv("OPENROUTER_SEARCH_ENGINE") or "exa"


def _fetch_engine() -> str:
    return os.getenv("DR_OPENROUTER_FETCH_ENGINE") or os.getenv("OPENROUTER_FETCH_ENGINE") or "exa"


async def _chat_with_server_tools(
    user_message: str,
    tools: list[dict[str, Any]],
    *,
    timeout_s: int = 120,
) -> dict[str, Any]:
    payload = {
        "model": _tool_model(),
        "messages": [{"role": "user", "content": user_message}],
        "tools": tools,
    }
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://github.com/aimleap/agents-deep-research"),
        "X-Title": os.getenv("OPENROUTER_APP_TITLE", "agents-deep-research"),
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            OPENROUTER_CHAT_URL,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=timeout_s),
        ) as resp:
            body = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"OpenRouter API HTTP {resp.status}: {body[:500]}")
            return json.loads(body)


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return []
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)]
        except json.JSONDecodeError:
            pass
    return []


def _snippets_from_annotations(message: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for ann in message.get("annotations") or []:
        if not isinstance(ann, dict):
            continue
        if ann.get("type") == "url_citation":
            url_citation = ann.get("url_citation") or ann
            url = url_citation.get("url") or ann.get("url") or ""
            title = url_citation.get("title") or ann.get("title") or ""
            content = url_citation.get("content") or ann.get("content") or ""
            if url:
                out.append({"url": url, "title": title, "description": content[:500]})
    return out


async def openrouter_web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """
    Run OpenRouter ``openrouter:web_search`` and return url/title/description dicts.
    """
    print(f"\n[OPENROUTER:web_search] Query: {query}")
    user_message = (
        f"Search the web for: {query}\n\n"
        f"After searching, respond with ONLY a JSON array (no markdown prose) of up to {max_results} "
        f'objects: [{{"url":"...","title":"...","description":"..."}}]. '
        "Use real URLs from the search results."
    )
    tools = [
        {
            "type": "openrouter:web_search",
            "parameters": {
                "engine": _search_engine(),
                "max_results": max_results,
            },
        }
    ]
    data = await _chat_with_server_tools(user_message, tools)
    message = (data.get("choices") or [{}])[0].get("message") or {}
    content = message.get("content") or ""

    rows = _extract_json_array(content)
    if not rows:
        rows = _snippets_from_annotations(message)

    results: list[dict[str, str]] = []
    for row in rows[:max_results]:
        url = (row.get("url") or "").strip()
        if not url:
            continue
        results.append(
            {
                "url": url,
                "title": (row.get("title") or "").strip(),
                "description": (row.get("description") or row.get("snippet") or "").strip(),
            }
        )

    # If model returned prose only, preserve it as a single pseudo-result for downstream agents
    if not results and content.strip():
        results.append(
            {
                "url": "https://openrouter.ai/search",
                "title": f"Web search: {query}",
                "description": content.strip()[:2000],
            }
        )

    print(f"[OPENROUTER:web_search] Results: {len(results)}")
    return results


async def openrouter_web_fetch(url: str, max_content_chars: int = 10000) -> dict[str, str]:
    """
    Run OpenRouter ``openrouter:web_fetch`` for one URL.
    Returns dict with url, title, content (and optional error).
    """
    print(f"[OPENROUTER:web_fetch] URL: {url}")
    max_tokens = min(max(max_content_chars // 4, 2000), 100000)
    user_message = (
        f"Fetch this URL and return its main text content: {url}\n"
        "Reply with plain text only (no JSON), starting with the page title on the first line if known."
    )
    tools = [
        {
            "type": "openrouter:web_fetch",
            "parameters": {
                "engine": _fetch_engine(),
                "max_content_tokens": max_tokens,
                "max_uses": 3,
            },
        }
    ]
    data = await _chat_with_server_tools(user_message, tools, timeout_s=180)
    message = (data.get("choices") or [{}])[0].get("message") or {}
    content = (message.get("content") or "").strip()

    title = ""
    body = content
    if content:
        lines = content.split("\n", 1)
        if len(lines[0]) < 200:
            title = lines[0].strip()
            body = lines[1].strip() if len(lines) > 1 else content

    if len(body) > max_content_chars:
        body = body[:max_content_chars]

    print(f"[OPENROUTER:web_fetch] Retrieved {len(body)} chars")
    return {"url": url, "title": title, "content": body, "description": body[:500]}
