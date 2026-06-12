"""
scripts/reindex.py — re-upload existing postmortems to a (new) Qdrant cluster.

Use this when the Qdrant cluster was deleted/recreated but you still have
data/extracted_postmortems.json. Skips scraping AND extraction entirely.

Run from the project root:
    python scripts/reindex.py
"""

import json
import logging
import os
import sys

# Add project root to path (same trick as ingest_all.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.extractor import PostMortem
from ingestion.embedder import upsert_postmortems, get_collection_stats, get_qdrant_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "extracted_postmortems.json",
)


def main():
    if not os.path.exists(DATA_PATH):
        logger.error(f"Data file not found: {DATA_PATH}")
        logger.error("Expected data/extracted_postmortems.json in the project root.")
        sys.exit(1)

    with open(DATA_PATH) as f:
        raw = json.load(f)
    logger.info(f"Loaded {len(raw)} postmortems from {DATA_PATH}")

    postmortems = []
    for item in raw:
        try:
            postmortems.append(PostMortem(**item))
        except Exception as e:
            logger.warning(f"Skipping one invalid record: {e}")

    logger.info(f"{len(postmortems)} valid postmortems ready to upload")

    # Connect (uses QDRANT_URL + QDRANT_API_KEY from .env)
    client = get_qdrant_client()
    logger.info(f"Connecting to Qdrant at {os.getenv('QDRANT_URL', 'http://localhost:6333')}")

    # Upload — this also creates the collection if it doesn't exist
    upsert_postmortems(postmortems, client=client)

    stats = get_collection_stats(client)
    logger.info("=" * 50)
    logger.info(f"DONE. Postmortems now in Qdrant: {stats['total_postmortems']}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()