"""LangChain ChatDeepSeek wrapper with structured output."""

import logging
import os
from typing import Optional

import httpx
from langchain_deepseek import ChatDeepSeek

from app.config import Settings

logger = logging.getLogger(__name__)

settings = Settings()


def _proxy_url() -> str | None:
    proxy = (
        os.getenv("HTTPS_PROXY")
        or os.getenv("https_proxy")
        or os.getenv("ALL_PROXY")
        or os.getenv("all_proxy")
        or os.getenv("HTTP_PROXY")
        or os.getenv("http_proxy")
    )
    if proxy and proxy.startswith("socks://"):
        return "socks5://" + proxy[len("socks://"):]
    return proxy


def _http_clients() -> dict:
    proxy = _proxy_url()
    return {
        "http_client": httpx.Client(proxy=proxy, trust_env=False),
        "http_async_client": httpx.AsyncClient(proxy=proxy, trust_env=False),
    }


# Primary DeepSeek model.
llm: Optional[ChatDeepSeek] = None

# Fallback DeepSeek model for retries.
llm_fallback: Optional[ChatDeepSeek] = None


def get_llm(temperature: float = 0.1, max_tokens: int = 2000) -> ChatDeepSeek:
    """Get the primary DeepSeek LLM instance."""
    global llm
    if llm is None:
        llm = ChatDeepSeek(
            api_key=settings.DEEPSEEK_API_KEY.get_secret_value(),
            model=settings.DEEPSEEK_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=30,
            max_retries=2,
            http_socket_options=(),
            **_http_clients(),
        )
    return llm


def get_llm_fallback() -> ChatDeepSeek:
    """Get the fallback DeepSeek LLM instance."""
    global llm_fallback
    if llm_fallback is None:
        llm_fallback = ChatDeepSeek(
            api_key=settings.DEEPSEEK_API_KEY.get_secret_value(),
            model=settings.DEEPSEEK_FALLBACK_MODEL,
            temperature=0.1,
            max_tokens=2000,
            timeout=30,
            max_retries=1,
            http_socket_options=(),
            **_http_clients(),
        )
    return llm_fallback


async def invoke_structured(prompt: str, max_retries: int = 2) -> str:
    """Invoke DeepSeek with JSON output, retrying on failure."""
    from app.core.errors import AIGenerationFailedError

    last_error = None

    for attempt in range(max_retries + 1):
        try:
            client = get_llm() if attempt == 0 else get_llm_fallback()
            response = await client.ainvoke(
                prompt,
                response_format={"type": "json_object"},
            )
            # Token usage accounting (P2 成本记录) — best-effort, never fails.
            usage = getattr(response, "usage_metadata", None) or {}
            if usage:
                logger.info(
                    "llm_usage model=%s attempt=%d input_tokens=%s "
                    "output_tokens=%s total_tokens=%s",
                    getattr(client, "model_name", "deepseek"),
                    attempt,
                    usage.get("input_tokens"),
                    usage.get("output_tokens"),
                    usage.get("total_tokens"),
                )
            return response.content
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                import asyncio
                await asyncio.sleep(1 * (attempt + 1))

    raise AIGenerationFailedError(
        f"LLM generation failed after {max_retries + 1} attempts: {last_error}"
    )
