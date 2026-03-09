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
        Returns search results with snippets. Only crawls URLs if snippets are missing.

        Args:
            query: The search query

        Returns:
            List of ScrapeResult objects with url, title, description, and text content.
        """
        try:
            print(f"\n[SEARCH] Query: {query}")
            raw_results = await brightdata_search(query, max_results=5, include_ai_overview=True)
            print(f"[SEARCH] Raw results count: {len(raw_results) if raw_results else 0}")
            
            if raw_results and "error" in raw_results[0]:
                error_msg = raw_results[0]["error"]
                print(f"[SEARCH] Error: {error_msg}")
                return error_msg

            snippets = [
                WebpageSnippet(
                    url=r.get("url", ""),
                    title=r.get("title", ""),
                    description=r.get("description", ""),
                )
                for r in raw_results
                if r.get("url")
            ]
            
            # Check if snippets have good descriptions
            snippets_with_content = [s for s in snippets if s.description and len(s.description) > 20]
            snippets_without_content = [s for s in snippets if not s.description or len(s.description) <= 20]
            
            print(f"[SEARCH] URLs with snippets: {len(snippets_with_content)}")
            print(f"[SEARCH] URLs without snippets (need crawl): {len(snippets_without_content)}")
            
            # Convert snippet-only results (no crawl needed)
            results = []
            if snippets_with_content:
                print(f"[SEARCH] Using snippets from {len(snippets_with_content)} URLs (no crawl needed)")
                for snippet in snippets_with_content:
                    results.append(ScrapeResult(
                        url=snippet.url,
                        title=snippet.title,
                        description=snippet.description,
                        text=snippet.description,  # Use description as text if we have it
                    ))
            
            # Only crawl URLs without good snippets
            if snippets_without_content:
                print(f"[SEARCH] Crawling {len(snippets_without_content)} URLs for missing content:")
                for i, snippet in enumerate(snippets_without_content, 1):
                    print(f"  {i}. {snippet.url}")
                crawled_results = await scrape_urls(snippets_without_content)
                results.extend(crawled_results)
                print(f"[SEARCH] Crawled results: {len(crawled_results)}")
            
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
            
            print(f"[SEARCH] Final results: {len(results)}\n")
            return results
        except Exception as e:
            error_msg = f"Sorry, I encountered an error while searching: {str(e)}"
            print(f"[SEARCH] Exception: {error_msg}\n")
            return error_msg

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
