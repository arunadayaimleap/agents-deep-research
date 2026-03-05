from pydantic import BaseModel, Field

class ToolAgentOutput(BaseModel):
    """Standard output for all tool agents"""
    output: str
    sources: list[str] = Field(default_factory=list)

from .search_agent import init_search_agent
from .crawl_agent import init_crawl_agent
from .page_fetch_agent import init_page_fetch_agent
from .brightdata_agent import init_brightdata_agent
from .serp_agent import init_serp_agent
from ...llm_config import LLMConfig
from ..baseclass import ResearchAgent

def init_tool_agents(config: LLMConfig) -> dict[str, ResearchAgent]:
    search_agent = init_search_agent(config)
    crawl_agent = init_crawl_agent(config)
    page_fetch_agent = init_page_fetch_agent(config)
    brightdata_agent = init_brightdata_agent(config)
    serp_agent = init_serp_agent(config)

    return {
        "WebSearchAgent": search_agent,
        "SiteCrawlerAgent": crawl_agent,
        "PageFetcherAgent": page_fetch_agent,
        "BrightDataFetcherAgent": brightdata_agent,
        "BrightDataSERPAgent": serp_agent,
    }

