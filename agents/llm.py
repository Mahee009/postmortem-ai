"""
llm.py — production LLM client with auto-discovery of working free models
Never hardcodes model names. Fetches live free model list from OpenRouter.
Falls back to Ollama for local dev.
"""

import os
import re
import logging
import httpx
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Preferred models tried first when ranking the live free list
PREFERRED_MODEL_KEYWORDS = [
    "llama-3.3-70b",
    "gemma-4-27b",
    "gemma-4-31b",
    "qwen3",
    "nemotron-3-super",
    "tencent/hy3",
    "minimax",
]

_working_model_cache: str | None = None


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks emitted by reasoning models (qwen3 etc.)."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


async def _get_working_free_model() -> str:
    """Fetch the live free model list from OpenRouter and return the best one."""
    global _working_model_cache
    if _working_model_cache:
        return _working_model_cache

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    SKIP = {"ocr", "audio", "vision", "embed", "rerank", "speech", "lyria", "owl", "cobuddy"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            models = resp.json().get("data", [])

        free_models = [
            m["id"] for m in models
            if (m.get("pricing", {}).get("prompt") in ("0", 0))
            and not any(skip in m["id"] for skip in SKIP)
            and ("instruct" in m["id"] or any(k in m["id"] for k in PREFERRED_MODEL_KEYWORDS))
        ]

        # Prefer known-good models first, then append the rest
        ordered: list[str] = []
        for keyword in PREFERRED_MODEL_KEYWORDS:
            for m in free_models:
                if keyword in m and m not in ordered:
                    ordered.append(m)
        for m in free_models:
            if m not in ordered:
                ordered.append(m)

        if ordered:
            _working_model_cache = ordered[0]
            logger.info(f"Auto-selected free model: {_working_model_cache}")
            return _working_model_cache

    except Exception as e:
        logger.warning(f"Could not fetch model list: {e}")

    return "meta-llama/llama-3.3-70b-instruct:free"


def _ollama_reachable() -> bool:
    try:
        httpx.get("http://localhost:11434", timeout=2)
        return True
    except Exception:
        return False


async def call_llm(
    prompt: str,
    system: str = "",
    max_tokens: int = 2000,
    json_mode: bool = False,
) -> str:
    """
    Call the configured LLM and return the response text.

    LLM_PROVIDER=ollama      → Ollama (local, fast); falls back to OpenRouter if unreachable.
    LLM_PROVIDER=openrouter  → OpenRouter with auto-discovered free model; retries on failure.

    Args:
        prompt: User message text
        system: Optional system prompt
        max_tokens: Max tokens to generate
        json_mode: Ignored — included for backward compatibility
    """
    provider = os.getenv("LLM_PROVIDER", "openrouter")

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # Local dev — Ollama
    if provider == "ollama" and _ollama_reachable():
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        logger.info(f"Using Ollama: {model}")
        try:
            response = await client.chat.completions.create(
                model=model, messages=messages, max_tokens=max_tokens
            )
            return _strip_thinking(response.choices[0].message.content or "")
        except Exception as e:
            logger.warning(f"Ollama failed ({e}) — falling back to OpenRouter")

    # Production — auto-discover working free model
    model = await _get_working_free_model()
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )
    logger.info(f"Using OpenRouter: {model}")

    try:
        response = await client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens
        )
        return _strip_thinking(response.choices[0].message.content or "")

    except Exception as e:
        logger.error(f"LLM error with {model}: {e}")
        global _working_model_cache
        _working_model_cache = None

        # One retry with a freshly discovered model
        new_model = await _get_working_free_model()
        if new_model != model:
            logger.info(f"Retrying with: {new_model}")
            response = await client.chat.completions.create(
                model=new_model, messages=messages, max_tokens=max_tokens
            )
            return _strip_thinking(response.choices[0].message.content or "")
        raise
