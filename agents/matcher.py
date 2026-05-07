"""
matcher.py — queries Qdrant for the most similar startup failures
Returns top 15 postmortems ranked by semantic similarity
"""

import os
import logging
from dotenv import load_dotenv
from ingestion.embedder import search_similar, get_qdrant_client, get_collection_stats

load_dotenv()
logger = logging.getLogger(__name__)


async def retrieve_similar_failures(startup_profile: dict, top_k: int = 15) -> list[dict]:
    """
    Find the most similar failed startups to the given profile.

    Strategy:
    1. Search with query_text (broad semantic match)
    2. If fewer than 5 results, do a second search without type filter
    3. Deduplicate by source_url
    4. Return top_k results sorted by score
    """
    query_text = startup_profile.get("query_text", "")
    startup_type = startup_profile.get("type", "")

    if not query_text:
        # Fallback: build query from components
        parts = [
            startup_profile.get("type", ""),
            startup_profile.get("stage", ""),
            startup_profile.get("description", ""),
            startup_profile.get("biggest_worry", ""),
        ]
        query_text = " ".join([p for p in parts if p])

    logger.info(f"Searching for: {query_text[:80]}...")

    client = get_qdrant_client()

    # First pass: type-filtered search for better precision
    results = search_similar(
        query_text=query_text,
        top_k=top_k,
        client=client,
        startup_type_filter=startup_type if startup_type != "Other" else None,
    )

    # Second pass: unfiltered search if we don't have enough
    if len(results) < 8:
        logger.info(f"Only {len(results)} type-filtered results, doing broad search...")
        broad_results = search_similar(
            query_text=query_text,
            top_k=top_k,
            client=client,
            startup_type_filter=None,
        )
        # Merge and deduplicate by URL
        seen_urls = {r["source_url"] for r in results}
        for r in broad_results:
            if r["source_url"] not in seen_urls:
                results.append(r)
                seen_urls.add(r["source_url"])

    # Sort by score descending, take top_k
    results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
    results = results[:top_k]

    logger.info(f"Retrieved {len(results)} similar failures")

    # Log top 3 for debugging
    for i, r in enumerate(results[:3]):
        logger.info(
            f"  [{i+1}] {r.get('startup_name', '?')} | "
            f"{r.get('primary_failure_cause', '?')} | "
            f"score={r.get('similarity_score', 0):.2f}"
        )

    return results


def get_db_stats() -> dict:
    """Get current database statistics."""
    client = get_qdrant_client()
    return get_collection_stats(client)
