#!/usr/bin/env python3
"""
Test Jina Reader and Search integration.

- JINA_API_KEY or DR_JINA_API_KEY must be set (same as production).
- Live calls need an active Jina plan; HTTP 402 means quota/billing, not a missing key.
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).resolve().parent
load_dotenv(_root / ".env", override=True)

from deep_researcher.utils.os import get_env_with_prefix


def _require_jina_key() -> None:
    if not get_env_with_prefix("JINA_API_KEY"):
        print(
            "Error: JINA_API_KEY or DR_JINA_API_KEY must be set in .env for Jina Search.",
            file=sys.stderr,
        )
        sys.exit(1)


async def _test_missing_key_guard() -> None:
    """No extra network semantics: jina_search must refuse when key is unset."""
    import deep_researcher.tools.jina_tools as jt

    old = jt.JINA_API_KEY
    try:
        jt.JINA_API_KEY = None
        out = await jt.jina_search("anything", max_results=1)
        assert len(out) == 1 and "error" in out[0], out
        assert "JINA_API_KEY required" in out[0]["error"]
        print("\n--- Missing-key guard: OK ---")
    finally:
        jt.JINA_API_KEY = old


async def test_reader():
    import deep_researcher.tools.jina_tools as jt

    print("\n--- Jina Reader (example.com) ---")
    result = await jt.read_url("https://example.com")
    print("Length:", len(result))
    print("Preview:", result[:200] + "..." if len(result) > 200 else result)
    if "402" in result or "401" in result:
        print(
            "(Reader returned billing/auth HTTP error - check Jina account/credits.)",
            flush=True,
        )
        return
    assert "example" in result.lower() or "Example" in result, "Expected example content"


async def test_search():
    _require_jina_key()
    import deep_researcher.tools.jina_tools as jt

    print("\n--- Jina Search (key present) ---")
    results = await jt.jina_search("Paris France capital", max_results=2)
    assert results, "Expected non-empty response list"
    if "error" in results[0]:
        err = results[0]["error"]
        print(f"Jina Search API error: {err}", file=sys.stderr)
        if "402" in err:
            print(
                "Hint: HTTP 402 = payment/quota. Add credits or upgrade at https://jina.ai",
                file=sys.stderr,
            )
            sys.exit(2)
        if "401" in err:
            print("Hint: Invalid or revoked API key.", file=sys.stderr)
            sys.exit(2)
        sys.exit(1)
    assert results[0].get("url") or results[0].get("text"), results[0]
    print("Results:", len(results))
    for i, r in enumerate(results[:2], 1):
        print(f"  {i}. {r.get('title', '')[:60]}")
        print(f"     URL: {r.get('url', '')[:70]}")
        print(f"     Content len: {len(r.get('text', ''))}")


async def main():
    key = get_env_with_prefix("JINA_API_KEY")
    print("JINA_API_KEY (or DR_):", "set" if key else "MISSING")

    await _test_missing_key_guard()
    await test_reader()
    await test_search()
    print("\n--- All Jina tests passed ---")


if __name__ == "__main__":
    asyncio.run(main())
