from __future__ import annotations

"""
Script de seed do Qdrant para composições SINAPI.

Todos os parâmetros de modelo/embedding são passados explicitamente
via argumentos de função. Sem fallback para variáveis de ambiente.
"""

from pathlib import Path

try:  # quando executado como `python -m src.sinapi.seed_qdrant`
    from src.sinapi.composition_documents import build_composition_documents
    from src.sinapi.compositions import export_workbook
    from src.sinapi.qdrant_simple import QdrantSinapi
except ImportError:  # pragma: no cover - fallback para PATH com raiz em src/
    from composition_documents import build_composition_documents
    from compositions import export_workbook
    from qdrant_simple import QdrantSinapi


def populate_qdrant(
    *,
    workbook_path: Path,
    dense_provider: str,
    dense_model: str,
    dense_vector_size: int,
    collection_name: str = "sinapi",
    qdrant_url: str = "http://localhost:6333",
    dense_base_url: str | None = None,
    dense_api_key: str | None = None,
    recreate_collection: bool = True,
) -> None:
    """Exporta o workbook, cria/recria coleção e indexa documentos."""
    sinapi = QdrantSinapi(
        collection_name=collection_name,
        qdrant_url=qdrant_url,
        dense_model=dense_model,
        dense_size=dense_vector_size,
        dense_provider=dense_provider,
        dense_base_url=dense_base_url,
        dense_api_key=dense_api_key,
    )

    print(f"Exportando workbook: {workbook_path}")
    payload = export_workbook(workbook_path)
    documents = build_composition_documents(payload)
    print(f"{len(documents)} documentos prontos para indexação.")

    if recreate_collection:
        print("Recriando coleção no Qdrant...")
        sinapi.create_collection()

    print("Indexando documentos (dense + sparse)...")
    sinapi.add_compositions(workbook_path, limit=None)
    print("Seed concluído.")


def main() -> None:
    _here = Path(__file__).resolve().parent
    workbook_path = _here / "docs" / "SINAPI_Custo_Ref_Composicoes_Analitico_AL_202412_Desonerado.xlsx"

    populate_qdrant(
        workbook_path=workbook_path,
        collection_name="sinapi",
        qdrant_url="http://localhost:6333",
        recreate_collection=True,
        dense_provider="ollama",
        dense_model="qwen3-embedding:0.6b",
        dense_vector_size=1024,
    )


if __name__ == "__main__":
    main()
