"""
scraper.py — fetches raw postmortem content from sources
Primary: Firecrawl for clean text extraction
Fallback: Jina.ai reader (https://r.jina.ai/{url}) — no API key required
"""

import os
import json
import logging
import asyncio
from typing import Optional
from dotenv import load_dotenv
import httpx
from firecrawl import FirecrawlApp
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))


def scrape_with_jina(url: str) -> Optional[dict]:
    """Fallback scraper using Jina.ai reader — no API key required."""
    try:
        logger.info(f"Jina fallback: {url}")
        resp = httpx.get(f"https://r.jina.ai/{url}", timeout=30, follow_redirects=True)
        resp.raise_for_status()
        content = resp.text
        if len(content) < 300:
            return None
        return {"url": url, "content": content, "title": "", "description": ""}
    except Exception as e:
        logger.error(f"Jina scrape failed for {url}: {e}")
        return None


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
def scrape_url(url: str) -> Optional[dict]:
    """Scrape a single URL — tries Firecrawl first, falls back to Jina."""
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
        # Firecrawl returned nothing — try Jina
        return scrape_with_jina(url)
    except Exception as e:
        logger.warning(f"Firecrawl failed for {url}: {e} — trying Jina")
        return scrape_with_jina(url)


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
    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "raw_scraped.json")
    with open(output_path, "w") as f:
        json.dump(pages, f, indent=2)
    logger.info(f"Saved {len(pages)} pages to {output_path}")
