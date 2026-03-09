import asyncio
from typing import List, Optional, Union

from agents import function_tool
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from ..llm_config import LLMConfig
from .brightdata_tools import brightdata_search, brightdata_unlock_url

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
    if config.search_provider not in ("brightdata", "openai"):
        raise ValueError(
            f"Search provider must be 'brightdata' or 'openai'. Got: {config.search_provider}"
        )

    @function_tool
    async def web_search(query: str) -> Union[List[ScrapeResult], str]:
        """Perform a web search for a given query using Bright Data SERP API.

        Natural language queries are supported directly, including full questions.
        Top result URLs are then fetched with Bright Data Unlocker for anti-bot bypass and markdown content.

        Args:
            query: The search query

        Returns:
            List of ScrapeResult objects with url, title, description, and text content.
        """
        try:
            raw_results = await brightdata_search(query, max_results=5, include_ai_overview=True)
            if raw_results and "error" in raw_results[0]:
                return raw_results[0]["error"]

            snippets = [
                WebpageSnippet(
                    url=r.get("url", ""),
                    title=r.get("title", ""),
                    description=r.get("description", ""),
                )
                for r in raw_results
                if r.get("url")
            ]

            results = await scrape_urls(snippets)

            # If the AI overview had no URL, preserve it as a text-only result.
            if raw_results and raw_results[0].get("title", "").startswith("Google AI Overview:") and not raw_results[0].get("url"):
                results.insert(
                    0,
                    ScrapeResult(
                        url="https://www.google.com/search",
                        title=raw_results[0].get("title", "Google AI Overview"),
                        description=raw_results[0].get("description", ""),
                        text=(raw_results[0].get("text", "") or "")[:CONTENT_LENGTH_LIMIT],
                    ),
                )
            return results
        except Exception as e:
            return f"Sorry, I encountered an error while searching: {str(e)}"

    return web_search


# ------- PAGE EXTRACTION (Bright Data Unlocker) -------

async def scrape_urls(items: List[WebpageSnippet]) -> List[ScrapeResult]:
    """Fetch text content from URLs using Bright Data Unlocker API."""
    tasks = [fetch_and_process_url(item) for item in items if item.url]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, ScrapeResult)]


async def fetch_and_process_url(item: WebpageSnippet) -> ScrapeResult:
    """Fetch URL content using Bright Data Unlocker (anti-bot bypass + markdown extraction)."""
    if not is_valid_url(item.url):
        return ScrapeResult(
            url=item.url,
            title=item.title,
            description=item.description,
            text="Error fetching content: URL contains restricted file extension",
        )
    try:
        text_content = await brightdata_unlock_url(item.url, max_length=CONTENT_LENGTH_LIMIT, data_format="markdown")
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
