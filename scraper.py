"""
scraper.py — fetches raw postmortem content from sources
Uses Firecrawl for clean text extraction from any URL
"""

import os
import json
import logging
import asyncio
from typing import Optional
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def scrape_url(url: str) -> Optional[dict]:
    """Scrape a single URL and return clean markdown content."""
    try:
        logger.info(f"Scraping: {url}")
        result = app.scrape_url(
            url,
            params={
                "formats": ["markdown"],
                "onlyMainContent": True,
                "timeout": 30000,
            }
        )
        if result and result.get("markdown"):
            return {
                "url": url,
                "content": result["markdown"],
                "title": result.get("metadata", {}).get("title", ""),
                "description": result.get("metadata", {}).get("description", ""),
            }
        return None
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        raise


def crawl_site(url: str, limit: int = 50) -> list[dict]:
    """Crawl a site and return up to `limit` pages of postmortem content."""
    try:
        logger.info(f"Crawling site: {url} (limit={limit})")
        result = app.crawl_url(
            url,
            params={
                "limit": limit,
                "scrapeOptions": {
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                },
            },
            poll_interval=5,
        )
        pages = []
        for page in result.get("data", []):
            if page.get("markdown") and len(page["markdown"]) > 500:
                pages.append({
                    "url": page.get("metadata", {}).get("url", ""),
                    "content": page["markdown"],
                    "title": page.get("metadata", {}).get("title", ""),
                })
        logger.info(f"Got {len(pages)} pages from {url}")
        return pages
    except Exception as e:
        logger.error(f"Failed to crawl {url}: {e}")
        return []


def load_sources() -> dict:
    sources_path = os.path.join(os.path.dirname(__file__), "..", "data", "sources.json")
    with open(sources_path) as f:
        return json.load(f)


def scrape_all_sources() -> list[dict]:
    """Main entry point — scrape all configured sources."""
    sources = load_sources()
    all_pages = []

    for source in sources["sources"]:
        logger.info(f"\n=== Processing source: {source['name']} ===")

        if source["type"] == "curated":
            for url in source["urls"]:
                pages = crawl_site(url, limit=30)
                all_pages.extend(pages)

        elif source["type"] == "direct":
            for url in source["urls"]:
                page = scrape_url(url)
                if page:
                    all_pages.append(page)

    logger.info(f"\nTotal pages scraped: {len(all_pages)}")
    return all_pages


if __name__ == "__main__":
    pages = scrape_all_sources()
    # Save raw scraped data
    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "raw_scraped.json")
    with open(output_path, "w") as f:
        json.dump(pages, f, indent=2)
    logger.info(f"Saved {len(pages)} pages to {output_path}")
