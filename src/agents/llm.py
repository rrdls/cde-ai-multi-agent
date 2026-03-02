"""LLM factory for the agent pipeline.

Uses OpenRouter (OpenAI-compatible API) for model access.
"""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_llm(
    temperature: float = 0,
    model: str | None = None,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance configured for OpenRouter.

    Args:
        temperature: Sampling temperature (0 = deterministic).
        model: Model name override. Defaults to MODEL_NAME from .env.
    """
    return ChatOpenAI(
        model=model or os.getenv("MODEL_NAME", "anthropic/claude-haiku-4.5"),
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=temperature,
    )
