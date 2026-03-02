"""Factory for dense embedding models.

Self-contained implementation supporting Ollama and OpenAI providers.
"""

from __future__ import annotations

from typing import Optional, Tuple


def build_dense_embeddings(
    *,
    provider: str,
    model: str,
    vector_size: int,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Tuple[object, int]:
    """Build a dense embedding object and return (embedding, vector_size).

    Args:
        provider: "ollama" or "openai".
        model: Model name (e.g., "qwen3-embedding:0.6b").
        vector_size: Expected vector dimensions.
        base_url: API base URL (optional, uses defaults).
        api_key: API key (optional for Ollama).

    Returns:
        (embedding_object, vector_size)
    """
    provider = provider.lower().strip()

    if provider == "ollama":
        from langchain_community.embeddings import OllamaEmbeddings

        embedding = OllamaEmbeddings(
            model=model,
            base_url=base_url or "http://localhost:11434",
        )
        return embedding, vector_size

    elif provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        kwargs = {"model": model}
        if base_url:
            kwargs["openai_api_base"] = base_url
        if api_key:
            kwargs["openai_api_key"] = api_key
        embedding = OpenAIEmbeddings(**kwargs)
        return embedding, vector_size

    else:
        raise ValueError(
            f"Provider '{provider}' not supported. Use 'ollama' or 'openai'."
        )
