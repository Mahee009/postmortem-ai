"""
extractor.py — uses Claude to extract structured data from raw postmortem text
Turns messy blog posts into clean PostMortem objects
"""

import os
import json
import logging
import asyncio
import uuid
from typing import Optional
from pydantic import BaseModel, Field
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()
logger = logging.getLogger(__name__)
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

FAILURE_TAXONOMY = [
    "no_market_need", "ran_out_of_cash", "team_issues", "competition",
    "wrong_pricing", "poor_product", "bad_timing", "regulatory",
    "pivot_failed", "scaling_too_fast", "customer_acquisition",
    "founder_burnout", "monetization_failed", "distribution_failed"
]

STARTUP_TYPES = [
    "B2B SaaS", "B2C App", "Marketplace", "E-commerce", "Hardware",
    "Developer Tools", "Fintech", "Healthtech", "Edtech", "Consumer Social",
    "Enterprise Software", "API/Infrastructure", "Other"
]


class PostMortem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_url: str = ""
    startup_name: str = ""
    startup_type: str = ""
    stage_at_failure: str = ""
    team_size: Optional[int] = None
    months_alive: Optional[int] = None
    funding: str = "unknown"
    primary_failure_cause: str = ""
    secondary_causes: list[str] = []
    warning_signs_missed: list[str] = []
    decision_point: str = ""
    what_they_would_do_differently: str = ""
    raw_summary: str = ""
    is_valid_postmortem: bool = False


EXTRACTION_PROMPT = """You are extracting structured data from a startup failure story or postmortem.

Analyze this text and extract the information. If this is NOT actually a startup failure story (e.g. it's a list, ad, unrelated content), set is_valid_postmortem to false.

Text to analyze:
---
{text}
---

Source URL: {url}

Extract and return a JSON object with EXACTLY these fields:
{{
  "startup_name": "Name of the startup (or 'Unknown')",
  "startup_type": "One of: {startup_types}",
  "stage_at_failure": "One of: pre-product | pre-revenue | early-revenue | growth | Series A+",
  "team_size": null or integer,
  "months_alive": null or integer (how many months the startup ran),
  "funding": "One of: bootstrapped | pre-seed | seed | Series A | Series B+ | unknown",
  "primary_failure_cause": "One of: {failure_taxonomy}",
  "secondary_causes": ["cause1", "cause2"] (from the same taxonomy, 0-3 items),
  "warning_signs_missed": ["sign1", "sign2"] (specific things they could have caught early, 2-4 items),
  "decision_point": "The ONE specific moment or decision that, if different, might have changed everything. One sentence.",
  "what_they_would_do_differently": "What the founder said they'd do differently. One sentence.",
  "raw_summary": "2-3 sentence plain English summary of what happened and why it failed.",
  "is_valid_postmortem": true or false
}}

Return ONLY the JSON object, no other text."""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def extract_postmortem(page: dict) -> Optional[PostMortem]:
    """Extract structured postmortem from a scraped page."""
    text = page.get("content", "")
    url = page.get("url", "")

    # Skip very short pages
    if len(text) < 300:
        return None

    # Truncate very long pages to avoid token limits
    text = text[:8000]

    prompt = EXTRACTION_PROMPT.format(
        text=text,
        url=url,
        startup_types=", ".join(STARTUP_TYPES),
        failure_taxonomy=", ".join(FAILURE_TAXONOMY)
    )

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()

        # Clean up if model wrapped in ```json
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)
        postmortem = PostMortem(**data, source_url=url)

        if not postmortem.is_valid_postmortem:
            logger.debug(f"Skipping non-postmortem page: {url}")
            return None

        logger.info(f"✓ Extracted: {postmortem.startup_name} ({postmortem.primary_failure_cause})")
        return postmortem

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error for {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Extraction error for {url}: {e}")
        raise


async def extract_all(pages: list[dict], batch_size: int = 5) -> list[PostMortem]:
    """Extract structured data from all pages, in batches."""
    postmortems = []
    total = len(pages)

    for i in range(0, total, batch_size):
        batch = pages[i:i + batch_size]
        logger.info(f"Extracting batch {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}")

        tasks = [extract_postmortem(page) for page in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, PostMortem):
                postmortems.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Batch error: {result}")

        # Rate limiting
        await asyncio.sleep(1)

    valid = [p for p in postmortems if p.is_valid_postmortem]
    logger.info(f"Extracted {len(valid)} valid postmortems from {total} pages")
    return valid


if __name__ == "__main__":
    import sys

    # Test on a single page
    test_page = {
        "url": "https://example.com/test",
        "content": """
        We built a SaaS tool for restaurant inventory management.
        After 18 months and $200K raised, we shut down last month.
        The core problem: restaurants didn't actually want software - they wanted someone to
        solve their problem, not a tool that required behavior change.
        We had 50 beta users but only 3 paying customers after 6 months of trying to convert.
        If I could do it over, I would have charged from day one to validate real willingness to pay.
        """
    }

    result = asyncio.run(extract_postmortem(test_page))
    if result:
        print(json.dumps(result.model_dump(), indent=2))
