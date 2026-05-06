"""
classifier.py — turns a raw startup description into a structured profile
Uses the configured LLM to extract: type, stage, team, funding, biggest risk
"""

import json
import logging
from dotenv import load_dotenv
from agents.llm import call_llm

load_dotenv()
logger = logging.getLogger(__name__)

CLASSIFY_PROMPT = """You are a startup analyst. A founder just described their startup to you.

Your job: extract a structured profile from their description.

Founder's message:
---
{message}
---

Return ONLY a JSON object with these exact fields. Infer anything not explicitly stated from context:
{{
  "startup_name": "Their startup name if mentioned, or 'Unknown'",
  "description": "One sentence: what they build and for whom",
  "type": "Exactly one of: B2B SaaS | B2C App | Marketplace | E-commerce | Hardware | Developer Tools | Fintech | Healthtech | Edtech | Consumer Social | Enterprise Software | API/Infrastructure | Other",
  "stage": "Exactly one of: pre-product | pre-revenue | early-revenue | growth | Series A+",
  "months_in": "Integer. How many months they've been working on this. Guess if not stated.",
  "team_size": "Integer. Number of founders/employees. Guess if not stated.",
  "funding": "Exactly one of: bootstrapped | pre-seed | seed | Series A | Series B+",
  "revenue": "Exactly one of: $0 | <$1K MRR | $1K-$10K MRR | $10K+ MRR",
  "biggest_worry": "Their primary concern in one sentence. Use their words if they said it.",
  "target_customer": "Who they sell to. One phrase.",
  "business_model": "How they make (or plan to make) money. One sentence.",
  "query_text": "A 2-3 sentence summary optimized for finding similar failed startups. Include type, stage, business model, and main challenge."
}}

Rules:
- Return ONLY valid JSON. No markdown, no explanation.
- If something is truly unknown, make a reasonable inference based on context.
- query_text is the most important field — write it to maximize similarity search relevance."""


async def classify_startup(user_message: str) -> dict:
    """
    Classify a startup description into a structured profile.

    Args:
        user_message: Raw description from the founder

    Returns:
        Structured startup profile dict
    """
    logger.info("Classifying startup...")

    raw = await call_llm(CLASSIFY_PROMPT.format(message=user_message), max_tokens=800)

    # Clean up if model wrapped in ```json
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    profile = json.loads(raw)
    logger.info(f"Profile: {profile.get('type')} | {profile.get('stage')} | {profile.get('revenue')}")
    return profile
