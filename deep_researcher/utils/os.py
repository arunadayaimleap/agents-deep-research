import os
import sys
from typing import Optional

def get_env_with_prefix(base_name: str, prefix: str = "DR_", default: Optional[str] = None) -> Optional[str]:
    """
    Retrieves an environment variable, checking for a prefixed version first.

    Args:
        base_name: The base name of the environment variable (e.g., "OPENAI_API_KEY").
        prefix: The prefix to check for (e.g., "DR_"). Defaults to "DR_".
        default: The default value to return if neither the prefixed nor the
                 base variable is found.

    Returns:
        The value of the environment variable, or the default value, or None.
    """
    prefixed_name = f"{prefix}{base_name}"
    value = os.getenv(prefixed_name)
    if value is not None:
        return value
    return os.getenv(base_name, default)


def exit_if_cli_search_keys_missing() -> None:
    """Exit if env keys do not match ``SEARCH_PROVIDER`` (default ``jina``). Used by CLI runners."""
    sp = (get_env_with_prefix("SEARCH_PROVIDER", default="jina") or "jina").strip().lower()
    if sp in ("brightdata", "serper", "searchxng"):
        sp = "jina"
    exa = get_env_with_prefix("EXA_API_KEY")
    jina = get_env_with_prefix("JINA_API_KEY")
    if sp == "exa":
        if not exa:
            print("Error: Set EXA_API_KEY in .env (SEARCH_PROVIDER=exa)", file=sys.stderr)
            sys.exit(1)
    elif sp == "openai":
        if not exa:
            print(
                "Error: Set EXA_API_KEY in .env (crawl and thin search hits use Exa get_contents)",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        if not jina:
            print("Error: Set JINA_API_KEY in .env (SEARCH_PROVIDER=jina)", file=sys.stderr)
            sys.exit(1)
        if not exa:
            print(
                "Error: Set EXA_API_KEY in .env (page extraction via Exa get_contents)",
                file=sys.stderr,
            )
            sys.exit(1)
