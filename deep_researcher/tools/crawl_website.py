import re
from typing import List, Set, Union
from urllib.parse import urlparse, urljoin

from agents import function_tool

from .exa_tools import exa_get_url_text
from .web_search import ScrapeResult, WebpageSnippet, scrape_urls


def extract_links_from_page(content: str, current_url: str, base_domain: str) -> tuple[List[str], List[str]]:
    """Extract same-domain links from page text: markdown [label](url) and bare http(s) URLs."""
    links: Set[str] = set()
    for match in re.finditer(r"\[([^\]]*)\]\(([^)]+)\)", content):
        link = urljoin(current_url, match.group(2).strip())
        if urlparse(link).netloc == base_domain and not link.lower().endswith(
            (".pdf", ".jpg", ".png")
        ):
            links.add(link.rstrip("/"))
    for match in re.finditer(r"https?://[^\s\)\]\"']+", content):
        link = match.group(0).rstrip(".,;:)")
        if urlparse(link).netloc == base_domain and not link.lower().endswith(
            (".pdf", ".jpg", ".png")
        ):
            links.add(link.rstrip("/"))
    return list(links), []


@function_tool
async def crawl_website(starting_url: str) -> Union[List[ScrapeResult], str]:
    """Crawls the pages of a website starting with the starting_url and then descending into the pages linked from there.
    Prioritizes links found in headers/navigation, then body links, then subsequent pages.

    Args:
        starting_url: Starting URL to scrape

    Returns:
        List of ScrapeResult objects which have the following fields:
            - url: The URL of the web page
            - title: The title of the web page
            - description: The description of the web page
            - text: The text content of the web page
    """
    if not starting_url:
        return "Empty URL provided"

    # Ensure URL has a protocol
    if not starting_url.startswith(("http://", "https://")):
        starting_url = "https://" + starting_url

    max_pages = 10
    base_domain = urlparse(starting_url).netloc

    # Initialize with starting URL
    queue: List[str] = [starting_url]
    next_level_queue: List[str] = []
    all_pages_to_scrape: Set[str] = {starting_url}

    # Breadth-first crawl using Exa /contents for page text
    while queue and len(all_pages_to_scrape) < max_pages:
        current_url = queue.pop(0)

        page_text = await exa_get_url_text(current_url, max_length=50000)
        if page_text and not page_text.startswith("Error"):
            nav_links, body_links = extract_links_from_page(page_text, current_url, base_domain)

            # Add unvisited nav links to current queue (higher priority)
            remaining_slots = max_pages - len(all_pages_to_scrape)
            for link in nav_links:
                link = link.rstrip("/")
                if link not in all_pages_to_scrape and remaining_slots > 0:
                    queue.append(link)
                    all_pages_to_scrape.add(link)
                    remaining_slots -= 1

            # Add unvisited body links to next level queue (lower priority)
            for link in body_links:
                link = link.rstrip("/")
                if link not in all_pages_to_scrape and remaining_slots > 0:
                    next_level_queue.append(link)
                    all_pages_to_scrape.add(link)
                    remaining_slots -= 1

        # If current queue is empty, add next level links
        if not queue:
            queue = next_level_queue
            next_level_queue = []

    # Convert set to list for final processing
    pages_to_scrape = list(all_pages_to_scrape)[:max_pages]
    pages_to_scrape = [WebpageSnippet(url=page, title="", description="") for page in pages_to_scrape]

    # Use scrape_urls to get the content for all discovered pages
    result = await scrape_urls(pages_to_scrape)
    return result
