"""PDF/CSV specification search tool for the Extraction Agent.

Provides RAG over project specifications stored in Qdrant "specifications" collection.
Uses same hybrid search pattern as SINAPI (Qwen 0.6B dense + BM25 sparse).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient

_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from sinapi.embeddings_factory import build_dense_embeddings  # noqa: E402

COLLECTION_NAME = "specifications"
QDRANT_URL = "http://localhost:6333"

_vector_store: Optional[QdrantVectorStore] = None


def _get_vector_store() -> QdrantVectorStore:
    global _vector_store
    if _vector_store is None:
        dense_embeddings, _ = build_dense_embeddings(
            provider="ollama",
            model="qwen3-embedding:0.6b",
            vector_size=1024,
        )
        sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")
        client = QdrantClient(url=QDRANT_URL, prefer_grpc=False)

        _vector_store = QdrantVectorStore(
            client=client,
            collection_name=COLLECTION_NAME,
            embedding=dense_embeddings,
            sparse_embedding=sparse_embeddings,
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name="dense",
            sparse_vector_name="sparse",
        )
    return _vector_store


def _run_search(query: str, k: int) -> str:
    store = _get_vector_store()
    from sinapi.qdrant_simple import ascii_fold
    results = store.similarity_search(query=ascii_fold(query), k=k)

    if not results:
        return "No matching documents found."

    lines = []
    for i, doc in enumerate(results, 1):
        meta = doc.metadata
        source = meta.get("source_name", "unknown")
        page = meta.get("page")
        page_str = f" (page {page})" if page else ""
        lines.append(
            f"--- Result {i} [{source}{page_str}] ---\n{doc.page_content}"
        )

    return "\n\n".join(lines)


@tool
def search_documents(query: str, k: int = 5) -> str:
    """Search project documents and general text files via RAG.
    
    Args:
        query: What to search for.
        k: Number of results.
    """
    return _run_search(query, k)


@tool
def search_specs(query: str, k: int = 5) -> str:
    """Search project technical specifications.
    
    Args:
        query: What to search for.
        k: Number of results.
    """
    return _run_search(query, k)


@tool
def search_specifications(query: str, k: int = 5) -> str:
    """Alternative search for project technical specifications and design details.
    
    Args:
        query: What to search for.
        k: Number of results.
    """
    return _run_search(query, k)
