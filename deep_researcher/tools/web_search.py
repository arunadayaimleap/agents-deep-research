import asyncio
from typing import List, Optional, Union

from agents import function_tool
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from ..llm_config import LLMConfig
from .jina_tools import jina_search, read_url

load_dotenv()
CONTENT_LENGTH_LIMIT = 10000  # Trim scraped content to this length to avoid large context / token limit issues

# ------- DEFINE TYPES -------


class ScrapeResult(BaseModel):
    url: str = Field(description="The URL of the webpage")
    text: str = Field(description="The full text content of the webpage")
    title: str = Field(description="The title of the webpage")
    description: str = Field(description="A short description of the webpage")


class WebpageSnippet(BaseModel):
    url: str = Field(description="The URL of the webpage")
    title: str = Field(description="The title of the webpage")
    description: Optional[str] = Field(description="A short description of the webpage")


# ------- DEFINE TOOL -------


def create_web_search_tool(config: LLMConfig) -> function_tool:
    if config.search_provider != "jina" and config.search_provider != "openai":
        raise ValueError(f"Search provider must be 'jina' or 'openai'. Got: {config.search_provider}")

    @function_tool
    async def web_search(query: str) -> Union[List[ScrapeResult], str]:
        """Perform a web search for a given query using Jina Search. Returns URLs with titles, descriptions, and full text content.

        Args:
            query: The search query

        Returns:
            List of ScrapeResult objects with url, title, description, and text content.
        """
        try:
            raw_results = await jina_search(query, max_results=5, max_content_length=CONTENT_LENGTH_LIMIT)
            if raw_results and "error" in raw_results[0]:
                return raw_results[0]["error"]
            return [
                ScrapeResult(
                    url=r.get("url", ""),
                    title=r.get("title", ""),
                    description=r.get("description", ""),
                    text=r.get("text", "")[:CONTENT_LENGTH_LIMIT],
                )
                for r in raw_results
            ]
        except Exception as e:
            return f"Sorry, I encountered an error while searching: {str(e)}"

    return web_search


# ------- PAGE EXTRACTION (Jina Reader) -------

async def scrape_urls(items: List[WebpageSnippet]) -> List[ScrapeResult]:
    """Fetch text content from URLs using Jina Reader."""
    tasks = [fetch_and_process_url(item) for item in items if item.url]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, ScrapeResult)]


async def fetch_and_process_url(item: WebpageSnippet) -> ScrapeResult:
    """Fetch URL content using Jina Reader (page extractor API)."""
    if not is_valid_url(item.url):
        return ScrapeResult(
            url=item.url,
            title=item.title,
            description=item.description,
            text="Error fetching content: URL contains restricted file extension",
        )
    try:
        text_content = await read_url(item.url, max_length=CONTENT_LENGTH_LIMIT)
        return ScrapeResult(
            url=item.url,
            title=item.title,
            description=item.description,
            text=text_content,
        )
    except Exception as e:
        return ScrapeResult(
            url=item.url,
            title=item.title,
            description=item.description,
            text=f"Error fetching content: {str(e)}",
        )


def is_valid_url(url: str) -> bool:
    """Check that a URL does not contain restricted file extensions."""
    if any(
        ext in url
        for ext in [
            ".pdf",
            ".doc",
            ".xls",
            ".ppt",
            ".zip",
            ".rar",
            ".7z",
            ".txt",
            ".js",
            ".xml",
            ".css",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".ico",
            ".svg",
            ".webp",
            ".mp3",
            ".mp4",
            ".avi",
            ".mov",
            ".wmv",
            ".flv",
            ".wma",
            ".wav",
            ".m4a",
            ".m4v",
            ".m4b",
            ".m4p",
            ".m4u",
        ]
    ):
        return False
    return True
