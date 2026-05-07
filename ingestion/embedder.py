"""
embedder.py — embeds PostMortem objects and stores them in Qdrant
Uses sentence-transformers for local embeddings (no API key, works on Render)
"""

import os
import logging
from typing import Optional
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue,
    PayloadSchemaType,
)
from dotenv import load_dotenv
from .extractor import PostMortem

load_dotenv()
logger = logging.getLogger(__name__)

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "postmortems")
VECTOR_DIM = 384  # all-MiniLM-L6-v2 output dimension

_model = None


def get_embed_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> list[float]:
    return get_embed_model().encode(text, normalize_embeddings=True).tolist()


def get_qdrant_client() -> QdrantClient:
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key = os.getenv("QDRANT_API_KEY")
    if api_key:
        return QdrantClient(url=url, api_key=api_key)
    return QdrantClient(url=url)


def ensure_collection(client: QdrantClient):
    """Create collection if it doesn't exist. If vector dim changed, delete and recreate."""
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME in existing:
        existing_dim = client.get_collection(COLLECTION_NAME).config.params.vectors.size
        if existing_dim != VECTOR_DIM:
            logger.warning(
                f"Collection dim={existing_dim} != required dim={VECTOR_DIM}. "
                "Dropping and recreating — re-ingestion required."
            )
            client.delete_collection(COLLECTION_NAME)
            existing = []

    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")
    else:
        logger.info(f"Collection exists: {COLLECTION_NAME}")

    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="startup_type",
        field_schema=PayloadSchemaType.KEYWORD,
    )
    logger.info("Payload index ensured: startup_type")


def make_embedding_text(postmortem: PostMortem) -> str:
    parts = [
        postmortem.startup_type,
        postmortem.stage_at_failure,
        postmortem.primary_failure_cause,
        " ".join(postmortem.secondary_causes),
        postmortem.raw_summary,
        postmortem.decision_point,
    ]
    return " ".join([p for p in parts if p])


def upsert_postmortems(postmortems: list[PostMortem], client: Optional[QdrantClient] = None):
    """Upsert a list of PostMortem objects into Qdrant."""
    if client is None:
        client = get_qdrant_client()

    ensure_collection(client)

    points = []
    for pm in postmortems:
        text = make_embedding_text(pm)
        vector = embed_text(text)

        payload = pm.model_dump()
        payload.pop("id", None)

        points.append(PointStruct(
            id=pm.id,
            vector=vector,
            payload=payload,
        ))

    if not points:
        logger.warning("No points to upsert")
        return

    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        client.upsert(collection_name=COLLECTION_NAME, points=batch)
        logger.info(f"Upserted batch {i//batch_size + 1} ({len(batch)} points)")

    total = client.count(collection_name=COLLECTION_NAME).count
    logger.info(f"✓ Total postmortems in Qdrant: {total}")


def search_similar(
    query_text: str,
    top_k: int = 15,
    client: Optional[QdrantClient] = None,
    startup_type_filter: Optional[str] = None,
) -> list[dict]:
    """Search for similar postmortems given a startup description."""
    if client is None:
        client = get_qdrant_client()

    query_vector = embed_text(query_text)

    search_filter = None
    if startup_type_filter:
        search_filter = Filter(
            must=[FieldCondition(
                key="startup_type",
                match=MatchValue(value=startup_type_filter)
            )]
        )

    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
        query_filter=search_filter,
        with_payload=True,
        score_threshold=0.3,
    )

    return [
        {**hit.payload, "similarity_score": hit.score}
        for hit in results
    ]


def get_collection_stats(client: Optional[QdrantClient] = None) -> dict:
    if client is None:
        client = get_qdrant_client()
    count = client.count(collection_name=COLLECTION_NAME).count
    return {"total_postmortems": count, "collection": COLLECTION_NAME}


# Alias used by api/main.py
get_db_stats = get_collection_stats
