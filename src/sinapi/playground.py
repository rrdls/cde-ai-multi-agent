"""
Playground para testar retrievals no Qdrant (SINAPI).

Uso:
    python -m playground
    python -m playground --query "alvenaria de vedação" --mode hybrid --k 5
"""

import argparse
import json
from pathlib import Path

from qdrant_simple import QdrantSinapi


def get_sinapi(
    *,
    collection_name: str = "sinapi",
    qdrant_url: str = "http://localhost:6333",
    provider: str = "ollama",
    model: str = "qwen3-embedding:0.6b",
    vector_size: int = 1024,
) -> QdrantSinapi:
    return QdrantSinapi(
        dense_provider=provider,
        dense_model=model,
        dense_size=vector_size,
        collection_name=collection_name,
        qdrant_url=qdrant_url,
    )


def print_results(results, mode: str, query: str) -> None:
    print(f"\n{'='*80}")
    print(f"  Mode: {mode.upper()}  |  Query: \"{query}\"  |  {len(results)} resultados")
    print(f"{'='*80}")
    for i, doc in enumerate(results, 1):
        meta = doc.metadata or {}
        codigo = meta.get("codigo", "?")
        tipo = meta.get("tipo", "")
        custo = meta.get("custo_total", "")
        print(f"\n  [{i}] COD: {codigo}  |  Tipo: {tipo}  |  Custo: {custo}")
        print(f"      {doc.page_content.strip()}")
    print()


def run_search(sinapi: QdrantSinapi, query: str, mode: str, k: int) -> list:
    results = sinapi.similarity_search(query=query, k=k, mode=mode)
    print_results(results, mode, query)
    return results


def compare_modes(sinapi: QdrantSinapi, query: str, k: int = 3) -> None:
    """Roda a mesma query nos 3 modos para comparação."""
    for mode in ("sparse", "dense", "hybrid"):
        run_search(sinapi, query, mode, k)


def interactive(sinapi: QdrantSinapi, default_mode: str = "hybrid", default_k: int = 5) -> None:
    """Modo interativo: digite queries e veja resultados em tempo real."""
    print("\n🔍 Modo interativo (digite 'exit' para sair, 'compare' para comparar modos)")
    print(f"   Defaults: mode={default_mode}, k={default_k}\n")

    while True:
        raw = input("Query> ").strip()
        if not raw or raw.lower() == "exit":
            break

        if raw.lower() == "compare":
            q = input("  Query para comparar> ").strip()
            if q:
                compare_modes(sinapi, q, default_k)
            continue

        # Permite trocar mode/k inline: "alvenaria --mode sparse --k 10"
        parts = raw.split(" --")
        query = parts[0].strip()
        mode = default_mode
        k = default_k
        for part in parts[1:]:
            if part.startswith("mode "):
                mode = part.split()[1]
            elif part.startswith("k "):
                k = int(part.split()[1])

        run_search(sinapi, query, mode, k)


def main() -> None:
    parser = argparse.ArgumentParser(description="Playground SINAPI Qdrant")
    parser.add_argument("--query", "-q", type=str, default=None, help="Query de busca")
    parser.add_argument("--mode", "-m", type=str, default="hybrid", choices=["sparse", "dense", "hybrid"])
    parser.add_argument("--k", type=int, default=5, help="Número de resultados")
    parser.add_argument("--compare", action="store_true", help="Compara os 3 modos")
    parser.add_argument("--collection", type=str, default="sinapi")
    parser.add_argument("--provider", type=str, default="ollama")
    parser.add_argument("--model", type=str, default="qwen3-embedding:0.6b")
    parser.add_argument("--vector-size", type=int, default=1024)
    args = parser.parse_args()

    sinapi = get_sinapi(
        collection_name=args.collection,
        provider=args.provider,
        model=args.model,
        vector_size=args.vector_size,
    )

    if args.query and args.compare:
        compare_modes(sinapi, args.query, args.k)
    elif args.query:
        run_search(sinapi, args.query, args.mode, args.k)
    else:
        interactive(sinapi, args.mode, args.k)


if __name__ == "__main__":
    main()
