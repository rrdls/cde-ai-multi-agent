"""Seed Qdrant 'specifications' collection from pre-chunked JSONL files.

Reads JSONL chunks from data/<project>/chunks/ and indexes them in Qdrant
with hybrid vectors (Qwen 0.6B dense + BM25 sparse).
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path
from typing import List
from uuid import uuid4

from langchain_core.documents import Document
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Distance, SparseVectorParams, VectorParams

# Add src/ to path
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from sinapi.embeddings_factory import build_dense_embeddings  # noqa: E402

COLLECTION_NAME = "specifications"
QDRANT_URL = "http://localhost:6333"
DENSE_SIZE = 1024


def ascii_fold(text: str) -> str:
    """Remove diacritics for BM25 tokenization."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def load_chunks_from_jsonl(jsonl_paths: List[Path]) -> List[Document]:
    """Load chunks from JSONL files into LangChain Documents."""
    documents = []
    for path in jsonl_paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                text = record.get("text", "").strip()
                if not text:
                    continue
                documents.append(
                    Document(
                        page_content=ascii_fold(text),
                        metadata={
                            "chunk_id": record.get("chunk_id", ""),
                            "source_name": record.get("source_name", ""),
                            "source_type": record.get("source_type", ""),
                            "page": record.get("page"),
                        },
                    )
                )
    return documents


def seed_specifications(project_dir: Path, overwrite: bool = False) -> int:
    """Index project chunks into Qdrant 'specifications' collection.

    Args:
        project_dir: Path to data/<project>/ containing chunks/ subdirectory.
        overwrite: If True, recreate the collection from scratch.

    Returns:
        Number of documents indexed.
    """
    chunks_dir = project_dir / "chunks"
    if not chunks_dir.exists():
        raise FileNotFoundError(f"Chunks directory not found: {chunks_dir}")

    jsonl_files = sorted(chunks_dir.glob("*.jsonl"))
    if not jsonl_files:
        raise FileNotFoundError(f"No JSONL files found in {chunks_dir}")

    print(f"Loading chunks from {len(jsonl_files)} JSONL files...")
    documents = load_chunks_from_jsonl(jsonl_files)
    print(f"Loaded {len(documents)} chunks")

    # Setup Qdrant
    client = QdrantClient(url=QDRANT_URL, prefer_grpc=False)

    if overwrite or not client.collection_exists(COLLECTION_NAME):
        print(f"Creating collection '{COLLECTION_NAME}'...")
        client.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                "dense": VectorParams(size=DENSE_SIZE, distance=Distance.COSINE)
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=False)
                )
            },
        )

    # Build embeddings
    dense_embeddings, _ = build_dense_embeddings(
        provider="ollama",
        model="qwen3-embedding:0.6b",
        vector_size=DENSE_SIZE,
    )
    sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")

    # Index documents
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=dense_embeddings,
        sparse_embedding=sparse_embeddings,
        retrieval_mode=RetrievalMode.HYBRID,
        vector_name="dense",
        sparse_vector_name="sparse",
    )

    ids = [str(uuid4()) for _ in documents]
    BATCH_SIZE = 50
    for i in range(0, len(documents), BATCH_SIZE):
        batch_docs = documents[i : i + BATCH_SIZE]
        batch_ids = ids[i : i + BATCH_SIZE]
        vector_store.add_documents(documents=batch_docs, ids=batch_ids)
        print(f"  Indexed {min(i + BATCH_SIZE, len(documents))}/{len(documents)}")

    print(f"Done! {len(documents)} chunks indexed in '{COLLECTION_NAME}'")
    return len(documents)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed Qdrant specifications collection from project chunks"
    )
    parser.add_argument(
        "--project", "-p",
        type=str,
        default="ubs-porte-1",
        help="Project name (directory under data/)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Recreate collection from scratch",
    )
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent.parent.parent / "data" / args.project
    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}")
        sys.exit(1)

    seed_specifications(project_dir, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
