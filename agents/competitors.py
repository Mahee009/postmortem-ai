"""
competitors.py — finds real competitors for a startup profile
Uses Serper.dev for Google search (2500 free/mo, no CC required)
then uses the configured LLM to parse results into structured data
"""

import os
import re
import json
import logging
import httpx
from urllib.parse import urlparse
from dotenv import load_dotenv
from agents.llm import call_llm

load_dotenv()
logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"


def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


async def find_competitors(startup_profile: dict) -> list[dict]:
    """
    Search for real competitors using Serper.dev then parse with LLM.
    Returns list of: {name, domain, description, why_relevant, funding_stage}
    """
    api_key = os.getenv("SERPER_API_KEY", "")
    if not api_key:
        logger.warning("SERPER_API_KEY not set — skipping competitor lookup")
        return []

    startup_type = startup_profile.get("type", "")
    description = startup_profile.get("description", "")

    query = f"{startup_type} {description} competitors startups 2024 2025"

    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.post(
                SERPER_URL,
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": 10},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error(f"Serper search failed: {e}")
        return []

    organic = data.get("organic", [])[:8]
    if not organic:
        logger.warning("Serper returned no organic results")
        return []

    results_text = "\n".join(
        f"- Title: {r.get('title', '')}\n  Snippet: {r.get('snippet', '')}\n  URL: {r.get('link', '')}"
        for r in organic
    )

    prompt = f"""From these search results, identify 4-5 real competitor companies (not blog posts or listicles) for a {startup_type} startup described as: {description}

Search results:
{results_text}

Return ONLY a JSON array, no other text:
[
  {{
    "name": "Company Name",
    "url": "https://their-domain.com",
    "description": "One sentence what they do.",
    "why_relevant": "One sentence why they directly threaten this startup.",
    "stage": "Early | Seed | Series A | Series B+ | Public | Unknown"
  }}
]"""

    try:
        raw = await call_llm(prompt, max_tokens=900, json_mode=False)
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1:
            logger.error("LLM did not return a JSON array for competitors")
            return []
        raw = raw[start : end + 1]
        raw = re.sub(r",\s*([}\]])", r"\1", raw)
        parsed = json.loads(raw)
    except Exception as e:
        logger.error(f"Competitor LLM parse failed: {e}")
        return []

    competitors = []
    for c in parsed[:5]:
        if not isinstance(c, dict) or not c.get("name"):
            continue
        competitors.append({
            "name": c.get("name", ""),
            "domain": _domain_from_url(c.get("url", "")),
            "description": c.get("description", ""),
            "why_relevant": c.get("why_relevant", ""),
            "funding_stage": c.get("stage", "Unknown"),
        })

    logger.info(f"Found {len(competitors)} competitors for '{startup_type}'")
    return competitors
