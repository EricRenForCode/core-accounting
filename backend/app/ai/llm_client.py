"""LangChain ChatOpenAI wrapper for DeepSeek with structured output."""

from typing import Optional

import httpx
from langchain_openai import ChatOpenAI

from app.config import Settings

settings = Settings()


def _http_clients() -> dict:
    return {
        "http_client": httpx.Client(trust_env=False),
        "http_async_client": httpx.AsyncClient(trust_env=False),
    }


# Primary DeepSeek model.
llm: Optional[ChatOpenAI] = None

# Fallback DeepSeek model for retries.
llm_fallback: Optional[ChatOpenAI] = None


def get_llm(temperature: float = 0.1, max_tokens: int = 2000) -> ChatOpenAI:
    """Get the primary LLM instance.

    Creates a LangChain ChatOpenAI wrapper pointed at DeepSeek's
    OpenAI-compatible API. Uses low temperature for deterministic structured
    outputs.
    """
    global llm
    if llm is None:
        llm = ChatOpenAI(
            api_key=settings.DEEPSEEK_API_KEY.get_secret_value(),
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.DEEPSEEK_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=30,
            max_retries=2,
            **_http_clients(),
        )
    return llm


def get_llm_fallback() -> ChatOpenAI:
    """Get the fallback LLM instance (cheaper model for retries)."""
    global llm_fallback
    if llm_fallback is None:
        llm_fallback = ChatOpenAI(
            api_key=settings.DEEPSEEK_API_KEY.get_secret_value(),
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.DEEPSEEK_FALLBACK_MODEL,
            temperature=0.1,
            max_tokens=2000,
            timeout=30,
            max_retries=1,
            **_http_clients(),
        )
    return llm_fallback


async def invoke_structured(prompt: str, max_retries: int = 2) -> str:
    """Invoke the LLM with structured (JSON) output, retrying on failure.

    Args:
        prompt: The prompt to send.
        max_retries: Number of retries on failure.

    Returns:
        Raw LLM response string.

    Raises:
        AIGenerationFailedError: If all retries fail.
    """
    from app.core.errors import AIGenerationFailedError

    last_error = None

    for attempt in range(max_retries + 1):
        try:
            client = get_llm() if attempt == 0 else get_llm_fallback()
            # Use JSON mode for DeepSeek's OpenAI-compatible API.
            response = await client.ainvoke(
                prompt,
                response_format={"type": "json_object"},
            )
            return response.content
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                import asyncio
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff

    raise AIGenerationFailedError(
        f"LLM generation failed after {max_retries + 1} attempts: {last_error}"
    )
