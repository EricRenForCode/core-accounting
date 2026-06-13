"""LangChain ChatOpenAI wrapper with primary/fallback model and structured output."""

from typing import Optional

from langchain_openai import ChatOpenAI

from app.config import Settings

settings = Settings()

# Primary model (e.g., gpt-4o)
llm: Optional[ChatOpenAI] = None

# Fallback model (e.g., gpt-4o-mini) for retries
llm_fallback: Optional[ChatOpenAI] = None


def get_llm(temperature: float = 0.1, max_tokens: int = 2000) -> ChatOpenAI:
    """Get the primary LLM instance.

    Creates a LangChain ChatOpenAI wrapper with the configured API key and model.
    Uses low temperature (0.1) for deterministic structured outputs.
    """
    global llm
    if llm is None:
        llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY.get_secret_value(),
            model=settings.AI_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=30,
            max_retries=2,
        )
    return llm


def get_llm_fallback() -> ChatOpenAI:
    """Get the fallback LLM instance (cheaper model for retries)."""
    global llm_fallback
    if llm_fallback is None:
        llm_fallback = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY.get_secret_value(),
            model=settings.AI_FALLBACK_MODEL,
            temperature=0.1,
            max_tokens=2000,
            timeout=30,
            max_retries=1,
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
    raise NotImplementedError(
        "invoke_structured:\n"
        "1. Call llm.ainvoke(prompt) with response_format={'type': 'json_object'}\n"
        "2. If timeout/error: retry with fallback model\n"
        "3. If all retries exhausted: raise AIGenerationFailedError\n"
        "4. Return response.content"
    )
