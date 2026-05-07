import os
import re
import logging
import httpx
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks from reasoning models."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _ollama_reachable() -> bool:
    try:
        httpx.get("http://localhost:11434", timeout=2)
        return True
    except Exception:
        return False


async def call_llm(prompt_or_messages, system: str = "", max_tokens: int = 2000, **kwargs) -> str:
    # Accept either a plain string prompt (existing callers) or a messages list
    if isinstance(prompt_or_messages, str):
        messages = [{"role": "user", "content": prompt_or_messages}]
    else:
        messages = prompt_or_messages

    provider = os.getenv("LLM_PROVIDER", "huggingface")

    # Local dev — Ollama
    if provider == "ollama" and _ollama_reachable():
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        logger.info(f"Using Ollama: {model}")

    # Production — HuggingFace router (free, auto-failover, no rate limit hunting)
    else:
        client = AsyncOpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=os.getenv("HF_TOKEN", "")
        )
        # :fastest = auto-selects fastest available free provider
        model = "meta-llama/Llama-3.3-70B-Instruct:fastest"
        logger.info(f"Using HuggingFace router: {model}")

    all_messages = []
    if system:
        all_messages.append({"role": "system", "content": system})
    all_messages.extend(messages)

    response = await client.chat.completions.create(
        model=model,
        messages=all_messages,
        max_tokens=max_tokens,
    )
    return _strip_thinking(response.choices[0].message.content or "")
