"""Legal-specific agents (e.g. CourtSearchAgent for citation enrichment)."""

from .court_search_agent import init_court_search_agent

def init_legal_tool_agents(config):
    """Return dict of legal tool agents for iterative enrichment."""
    court_search = init_court_search_agent(config)
    return {
        "CourtSearchAgent": court_search,
    }

__all__ = ["init_legal_tool_agents", "init_court_search_agent"]
