"""
agents/llm.py — LLM provider abstraction

Waterfall (tried in order):
  1. Ollama local (llama3.2) — unlimited, 10s timeout
  2. OpenRouter meta-llama/llama-3.3-70b-instruct:free — on Ollama failure
  3. OpenRouter google/gemma-3-12b-it:free            — on 429 from fallback 1

Set LLM_PROVIDER=ollama in .env (default).
"""

import asyncio
import os
import re
import logging
from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APITimeoutError
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

# Ollama
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT  = 90  # seconds — synthesis prompts are long

# OpenRouter
OR_PRIMARY  = "meta-llama/llama-3.3-70b-instruct:free"
OR_FALLBACK = "google/gemma-2-9b-it:free"

_ollama_client:     AsyncOpenAI | None = None
_openrouter_client: AsyncOpenAI | None = None


def _get_ollama() -> AsyncOpenAI:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = AsyncOpenAI(
            base_url=f"{OLLAMA_BASE_URL}/v1",
            api_key="ollama",
            timeout=OLLAMA_TIMEOUT,
        )
    return _ollama_client


def _get_openrouter() -> AsyncOpenAI:
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
    return _openrouter_client


def _build_messages(prompt: str, system: str) -> list[dict]:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return msgs


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks emitted by qwen3 and similar reasoning models."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


async def _call(
    client: AsyncOpenAI, model: str, messages: list[dict],
    max_tokens: int, json_mode: bool = False
) -> str:
    kwargs: dict = dict(model=model, max_tokens=max_tokens, messages=messages)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = await client.chat.completions.create(**kwargs)
    return _strip_thinking(response.choices[0].message.content or "")


async def _call_openrouter(
    messages: list[dict], max_tokens: int, json_mode: bool = False
) -> str:
    """Try OR_PRIMARY, fall back to OR_FALLBACK on 429."""
    client = _get_openrouter()
    try:
        text = await _call(client, OR_PRIMARY, messages, max_tokens, json_mode)
        logger.debug(f"OpenRouter primary ({OR_PRIMARY}): {len(text)} chars")
        return text
    except RateLimitError:
        logger.warning(f"429 on {OR_PRIMARY} — trying {OR_FALLBACK}")
        text = await _call(client, OR_FALLBACK, messages, max_tokens, json_mode)
        logger.debug(f"OpenRouter fallback ({OR_FALLBACK}): {len(text)} chars")
        return text


async def call_llm(
    prompt: str, system: str = "", max_tokens: int = 1000, json_mode: bool = False
) -> str:
    """
    Waterfall: Ollama (10s timeout) → OpenRouter primary → OpenRouter fallback.

    Args:
        prompt: User message
        system: Optional system prompt
        max_tokens: Max tokens to generate
        json_mode: Request JSON output

    Returns:
        Response text, stripped of whitespace
    """
    messages = _build_messages(prompt, system)

    # Step 1 — Ollama (local, unlimited)
    try:
        text = await _call(_get_ollama(), OLLAMA_MODEL, messages, max_tokens, json_mode)
        logger.debug(f"Ollama ({OLLAMA_MODEL}): {len(text)} chars")
        return text
    except (APIConnectionError, APITimeoutError, asyncio.TimeoutError) as e:
        logger.warning(f"Ollama unavailable ({type(e).__name__}) — falling back to OpenRouter")
    except Exception as e:
        logger.warning(f"Ollama error ({e}) — falling back to OpenRouter")

    # Step 2+3 — OpenRouter
    return await _call_openrouter(messages, max_tokens, json_mode)
