"""
Model configuration for tests.

Loads project ``.env`` first, then uses ``FAST_MODEL_PROVIDER`` and ``FAST_MODEL`` for every
test LLM slot (reasoning / main / fast) so integration tests match your stack—typically
OpenRouter via ``OPENROUTER_API_KEY`` when ``FAST_MODEL_PROVIDER=openrouter``.

Override with env (or ``DR_FAST_MODEL`` / ``DR_FAST_MODEL_PROVIDER``).
"""

from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env", override=True)

from deep_researcher.utils.os import get_env_with_prefix

_fast_provider = get_env_with_prefix("FAST_MODEL_PROVIDER", default="openrouter") or "openrouter"
_fast_model = get_env_with_prefix("FAST_MODEL", default="openai/gpt-4o-mini") or "openai/gpt-4o-mini"

REASONING_MODEL_PROVIDER = _fast_provider
REASONING_MODEL = _fast_model

MAIN_MODEL_PROVIDER = _fast_provider
MAIN_MODEL = _fast_model

FAST_MODEL_PROVIDER = _fast_provider
FAST_MODEL = _fast_model

SEARCH_PROVIDER = get_env_with_prefix("SEARCH_PROVIDER", default="exa") or "exa"

# Parametrized provider smoke test (single entry = FAST stack from .env)
PROVIDERS_TO_TEST = {_fast_provider: _fast_model}
