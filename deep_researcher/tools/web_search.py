from typing import List, Optional, Union

from agents import function_tool
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from ..llm_config import LLMConfig
from .exa_tools import exa_get_urls_text_ordered, exa_search
from .jina_tools import jina_search

load_dotenv()
CONTENT_LENGTH_LIMIT = 10000  # Trim scraped content to this length to avoid large context / token limit issues


async def _raw_search_results(query: str, provider: str, max_results: int = 5) -> List[dict]:
    """SERP-style results as list of {url, title, description, text}; errors as [{'error': ...}]."""
    if provider == "exa":
        return await exa_search(query, max_results=max_results, include_ai_overview=True)
    return await jina_search(query, max_results=max_results)


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
    if config.search_provider not in ("jina", "exa", "openai"):
        raise ValueError(
            f"Search provider must be 'jina', 'exa', or 'openai'. Got: {config.search_provider}"
        )

    provider = config.search_provider

    @function_tool
    async def web_search(query: str) -> Union[List[ScrapeResult], str]:
        """Perform a web search (Jina or Exa per SEARCH_PROVIDER). Thin hits get full page text via Exa get_contents.

        Natural language queries are supported directly, including full questions.

        Args:
            query: The search query

        Returns:
            List of ScrapeResult objects with url, title, description, and text content.
        """
        try:
            print(f"\n[SEARCH] WebSearchAgent tool call — query: {query} (provider={provider})", flush=True)
            raw_results = await _raw_search_results(query, provider, max_results=5)
            print(f"[SEARCH] Raw results count: {len(raw_results) if raw_results else 0}", flush=True)

            if raw_results and "error" in raw_results[0]:
                error_msg = raw_results[0]["error"]
                print(f"[SEARCH] Error: {error_msg}", flush=True)
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

            text_by_url = {r.get("url", ""): (r.get("text") or "").strip() for r in raw_results if r.get("url")}

            snippets_with_content = [
                s
                for s in snippets
                if (text_by_url.get(s.url, "") and len(text_by_url.get(s.url, "")) > 20)
                or (s.description and len(s.description) > 20)
            ]
            urls_with_body = {s.url for s in snippets_with_content}
            snippets_without_content = [s for s in snippets if s.url not in urls_with_body]

            print(f"[SEARCH] URLs with usable text/snippet: {len(snippets_with_content)}", flush=True)
            print(f"[SEARCH] URLs needing /contents fetch: {len(snippets_without_content)}", flush=True)

            results: List[ScrapeResult] = []
            if snippets_with_content:
                print(f"[SEARCH] Using search result text/snippet for {len(snippets_with_content)} URLs", flush=True)
                for snippet in snippets_with_content:
                    body = text_by_url.get(snippet.url, "") or (snippet.description or "")
                    if len(body) > CONTENT_LENGTH_LIMIT:
                        body = body[:CONTENT_LENGTH_LIMIT] + f"\n\n[Truncated at {CONTENT_LENGTH_LIMIT}]"
                    desc = (snippet.description or body[:800])[:800]
                    results.append(
                        ScrapeResult(
                            url=snippet.url,
                            title=snippet.title,
                            description=desc,
                            text=body,
                        )
                    )

            if snippets_without_content:
                print(f"[SEARCH] Page extract (Exa get_contents) for {len(snippets_without_content)} URLs:", flush=True)
                for i, snippet in enumerate(snippets_without_content, 1):
                    print(f"  {i}. {snippet.url}", flush=True)
                crawled_results = await scrape_urls(snippets_without_content)
                results.extend(crawled_results)
                print(f"[SEARCH] Fetched results: {len(crawled_results)}", flush=True)

            print(f"[SEARCH] Final results: {len(results)}\n", flush=True)
            return results
        except Exception as e:
            error_msg = f"Sorry, I encountered an error while searching: {str(e)}"
            print(f"[SEARCH] Exception: {error_msg}\n", flush=True)
            return error_msg

    return web_search


# ------- PAGE EXTRACTION (Exa /contents) -------


async def scrape_urls(items: List[WebpageSnippet]) -> List[ScrapeResult]:
    """Fetch text for URLs using Exa get_contents."""
    filtered = [item for item in items if item.url]
    if not filtered:
        return []
    texts = await exa_get_urls_text_ordered([i.url for i in filtered], CONTENT_LENGTH_LIMIT)
    out: List[ScrapeResult] = []
    for item, text_content in zip(filtered, texts):
        if not is_valid_url(item.url):
            out.append(
                ScrapeResult(
                    url=item.url,
                    title=item.title,
                    description=item.description or "",
                    text="Error fetching content: URL contains restricted file extension",
                )
            )
            continue
        out.append(
            ScrapeResult(
                url=item.url,
                title=item.title,
                description=item.description or "",
                text=text_content,
            )
        )
    return out


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
