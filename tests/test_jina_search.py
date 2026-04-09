"""Jina Search: key requirement (no live API needed for the guard test)."""

import pytest


@pytest.mark.asyncio
async def test_jina_search_requires_api_key():
    import deep_researcher.tools.jina_tools as jt

    old = jt.JINA_API_KEY
    try:
        jt.JINA_API_KEY = None
        out = await jt.jina_search("query", max_results=1)
        assert len(out) == 1
        assert "error" in out[0]
        assert "JINA_API_KEY required" in out[0]["error"]
    finally:
        jt.JINA_API_KEY = old
