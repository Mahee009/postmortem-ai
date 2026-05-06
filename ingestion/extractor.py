"""
extractor.py — uses the configured LLM to extract structured data from raw postmortem text
Turns messy blog posts into clean PostMortem objects
"""

import json
import re
import logging
import asyncio
import uuid
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential
from agents.llm import call_llm

load_dotenv()
logger = logging.getLogger(__name__)

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

    @model_validator(mode="before")
    @classmethod
    def coerce_nulls(cls, values):
        str_fields = [
            "startup_name", "startup_type", "stage_at_failure", "funding",
            "primary_failure_cause", "decision_point",
            "what_they_would_do_differently", "raw_summary",
        ]
        for f in str_fields:
            v = values.get(f)
            if v is None:
                values[f] = ""
            elif isinstance(v, list):
                # Model returned a list where a string was expected — take first element
                values[f] = str(v[0]) if v else ""
        return values

    @field_validator("team_size", "months_alive", mode="before")
    @classmethod
    def coerce_int(cls, v):
        if v is None or v == "" or str(v).lower() in ("null", "unknown", "n/a"):
            return None
        try:
            # Handle ranges like "3-5" → take the first number
            return int(str(v).split("-")[0].strip())
        except (ValueError, TypeError):
            return None

    @field_validator("secondary_causes", "warning_signs_missed", mode="before")
    @classmethod
    def coerce_list(cls, v):
        if isinstance(v, list):
            return [str(i) for i in v]
        if isinstance(v, str) and v:
            return [v]
        return []


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


def _extract_json(raw: str) -> str:
    """Pull the first {...} block out of a model response and clean it up."""
    # Strip markdown fences
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    # Grab the outermost { ... }
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    # Remove trailing commas before } or ] (common llama3.2 quirk)
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    return raw.strip()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def extract_postmortem(page: dict) -> Optional[PostMortem]:
    """Extract structured postmortem from a scraped page."""
    text = page.get("content", "")
    url = page.get("url", "")

    if len(text) < 300:
        return None

    text = text[:4000]

    prompt = EXTRACTION_PROMPT.format(
        text=text,
        url=url,
        startup_types=", ".join(STARTUP_TYPES),
        failure_taxonomy=", ".join(FAILURE_TAXONOMY)
    )

    try:
        raw = await call_llm(prompt, max_tokens=1000, json_mode=True)
        raw = _extract_json(raw)
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
    except ValidationError as e:
        logger.debug(f"Validation failed for {url} — not a postmortem page")
        return None
    except Exception as e:
        logger.error(f"Extraction error for {url}: {e}")
        raise


async def extract_all(pages: list[dict], delay_seconds: float = 4.0) -> list[PostMortem]:
    """Extract structured data from all pages sequentially with rate-limit-safe delays.

    OpenRouter free tier: 20 req/min, 50 req/day.
    At 4s delay we stay under 20/min (15 req/min max).
    """
    postmortems = []
    total = len(pages)

    for i, page in enumerate(pages):
        logger.info(f"Extracting [{i+1}/{total}]: {page.get('url', '')[:60]}")
        try:
            result = await extract_postmortem(page)
            if isinstance(result, PostMortem):
                postmortems.append(result)
        except Exception as e:
            logger.error(f"Skipping page after retries: {e}")

        if i < total - 1:
            await asyncio.sleep(delay_seconds)

    logger.info(f"Extracted {len(postmortems)} valid postmortems from {total} pages")
    return postmortems
