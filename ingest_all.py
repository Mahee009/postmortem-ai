"""
scripts/ingest_all.py — runs the full ingestion pipeline
Scrape → Extract → Embed → Store in Qdrant

Run this once to populate the database.
Takes 20-40 minutes for a full run.
"""

import asyncio
import json
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.scraper import scrape_all_sources
from ingestion.extractor import extract_all
from ingestion.embedder import upsert_postmortems, get_collection_stats, get_qdrant_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


async def run_ingestion(skip_scraping: bool = False):
    logger.info("=" * 60)
    logger.info("PostMortemAI — Full Ingestion Pipeline")
    logger.info("=" * 60)

    # Step 1: Scrape
    raw_path = os.path.join(DATA_DIR, "raw_scraped.json")

    if skip_scraping and os.path.exists(raw_path):
        logger.info("Loading existing scraped data (skip_scraping=True)...")
        with open(raw_path) as f:
            pages = json.load(f)
        logger.info(f"Loaded {len(pages)} cached pages")
    else:
        logger.info("\n[1/3] SCRAPING sources...")
        pages = scrape_all_sources()
        with open(raw_path, "w") as f:
            json.dump(pages, f, indent=2)
        logger.info(f"Scraped {len(pages)} pages → saved to {raw_path}")

    # Step 2: Extract structured data
    logger.info("\n[2/3] EXTRACTING structured postmortems...")
    postmortems = await extract_all(pages, batch_size=5)

    # Save extracted data
    extracted_path = os.path.join(DATA_DIR, "extracted_postmortems.json")
    with open(extracted_path, "w") as f:
        json.dump([p.model_dump() for p in postmortems], f, indent=2)
    logger.info(f"Extracted {len(postmortems)} postmortems → saved to {extracted_path}")

    # Step 3: Embed and store
    logger.info("\n[3/3] EMBEDDING and storing in Qdrant...")
    client = get_qdrant_client()
    upsert_postmortems(postmortems, client=client)

    # Final stats
    stats = get_collection_stats(client)
    logger.info("\n" + "=" * 60)
    logger.info(f"✓ INGESTION COMPLETE")
    logger.info(f"  Total postmortems in database: {stats['total_postmortems']}")
    logger.info("=" * 60)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-scraping", action="store_true",
                       help="Skip scraping and use cached raw data")
    args = parser.parse_args()

    asyncio.run(run_ingestion(skip_scraping=args.skip_scraping))


if __name__ == "__main__":
    main()
