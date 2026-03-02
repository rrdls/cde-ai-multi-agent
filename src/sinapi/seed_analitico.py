from __future__ import annotations

"""
Seed do Qdrant a partir do orçamento analítico (ANALITICO.csv).

Indexa apenas composições não-SINAPI (Próprio/CPU, CPOS/CDHU, etc.)
com seus sub-componentes (Composição Auxiliar + Insumo).
Append-only — nunca recria a coleção.
"""

import argparse
import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from langchain_core.documents import Document

try:
    from src.sinapi.qdrant_simple import QdrantSinapi, ascii_fold
except ImportError:
    from qdrant_simple import QdrantSinapi, ascii_fold


# ---------------------------------------------------------------------------
# 1. CSV Parser
# ---------------------------------------------------------------------------

AnaliticoRecord = Dict[str, Any]

# Regex for section header items like " 1 ", " 1.1 ", " 1.1.1 ", " 2.16 "
_SECTION_RE = re.compile(r"^\d+(\.\d+)*$")

# Number format in the CSV uses Brazilian notation: "1,346.87" or "1.0000000"
_COMMA_NUMBER_RE = re.compile(r"^[\d,.]+$")


def _parse_number(value: str) -> Optional[float]:
    """Parse a number from the CSV. Handles '1,346.87' and '1.0000000'."""
    value = value.strip().replace('"', '')
    if not value:
        return None
    # Remove grouping commas (Brazilian: "1,346.87" -> "1346.87")
    # But be careful: quantities use dot as decimal (e.g. "1.0000000")
    try:
        # If there's a comma followed by exactly 2 digits at the end, it's
        # decimal comma (rare in this CSV, but handle it)
        cleaned = value.replace(",", "")
        return float(cleaned)
    except ValueError:
        return None


def parse_analitico_csv(csv_path: Path) -> List[AnaliticoRecord]:
    """Parse ANALITICO.csv and return a list of composition records with
    their sub-components (Composição Auxiliar / Insumo).

    The CSV is hierarchical:
    - Section headers (col[1] matches "1", "1.1", "1.1.1", etc.)
    - "Composição" rows define the main composition
    - "Composição Auxiliar" rows are sub-compositions
    - "Insumo" rows are input materials
    - Summary rows (MO, BDI, etc.) are ignored

    Only the first ~14 lines are file headers and are skipped.
    """
    records: List[AnaliticoRecord] = []
    secao: Optional[str] = None
    subsecao: Optional[str] = None
    current_record: Optional[AnaliticoRecord] = None

    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)

        for i, row in enumerate(reader):
            if i < 14:  # skip file headers
                continue
            if len(row) < 5:
                continue

            col1 = row[1].strip() if len(row) > 1 else ""
            col2 = row[2].strip() if len(row) > 2 else ""
            col3 = row[3].strip() if len(row) > 3 else ""
            col4 = row[4].strip() if len(row) > 4 else ""
            col5 = row[5].strip() if len(row) > 5 else ""
            col7 = row[7].strip() if len(row) > 7 else ""
            col8 = row[8].strip() if len(row) > 8 else ""
            col9 = row[9].strip() if len(row) > 9 else ""
            col10 = row[10].strip() if len(row) > 10 else ""

            # --- Section header line (e.g. " 1 ", " 1.1 ", " 2.16 ") ---
            if _SECTION_RE.match(col1):
                depth = col1.count(".")
                desc = col4
                if depth == 0:
                    # Top-level section (e.g. "SERVIÇOS PRELIMINARES E INDIRETOS")
                    secao = desc
                    subsecao = None
                elif depth == 1:
                    # Sub-section (e.g. "CANTEIRO DE OBRAS")
                    subsecao = desc
                # depth >= 2 is an item header (e.g. "1.1.1")
                # -> the next "Composição" line defines the composition
                continue

            # --- Composição (top-level composition) ---
            if col1 == "Composição":
                # Flush previous record
                if current_record is not None:
                    records.append(current_record)

                current_record = {
                    "codigo": col2,
                    "banco": col3,
                    "descricao": col4,
                    "tipo": col5,
                    "unidade": col7,
                    "quantidade": _parse_number(col8),
                    "valor_unitario": _parse_number(col9),
                    "valor_total": _parse_number(col10),
                    "secao": secao,
                    "subsecao": subsecao,
                    "componentes": {
                        "composicoes": [],
                        "insumos": [],
                        "outros": [],
                    },
                }
                continue

            # --- Composição Auxiliar (sub-composition) ---
            if col1 == "Composição Auxiliar" and current_record is not None:
                current_record["componentes"]["composicoes"].append({
                    "codigo": col2,
                    "banco": col3,
                    "descricao": col4,
                    "tipo": col5,
                    "unidade": col7,
                    "quantidade": _parse_number(col8),
                    "valor_unitario": _parse_number(col9),
                    "valor_total": _parse_number(col10),
                })
                continue

            # --- Insumo ---
            if col1 == "Insumo" and current_record is not None:
                current_record["componentes"]["insumos"].append({
                    "codigo": col2,
                    "banco": col3,
                    "descricao": col4,
                    "tipo": col5,
                    "unidade": col7,
                    "quantidade": _parse_number(col8),
                    "valor_unitario": _parse_number(col9),
                    "valor_total": _parse_number(col10),
                })
                continue

            # All other lines (summary, BDI, empty) are ignored

        # Flush last record
        if current_record is not None:
            records.append(current_record)

    return records


# ---------------------------------------------------------------------------
# 2. Document builder
# ---------------------------------------------------------------------------


def build_analitico_documents(
    records: List[AnaliticoRecord],
) -> List[Document]:
    """Build LangChain Documents following the same metadata schema as the
    existing SINAPI seed (composition_documents.py).

    Enriched with real component data from ANALITICO.csv.
    Extra fields (banco, secao, subsecao, fonte) are added.
    """
    documents: List[Document] = []

    for rec in records:
        descricao = rec.get("descricao", "")
        if not descricao:
            continue

        page_content = ascii_fold(descricao)

        componentes = rec.get("componentes", {})
        n_comp = len(componentes.get("composicoes", []))
        n_ins = len(componentes.get("insumos", []))
        n_outros = len(componentes.get("outros", []))

        metadata = {
            # --- same schema as SINAPI seed ---
            "codigo": rec["codigo"],
            "classe": rec.get("tipo"),  # e.g. "CANT - CANTEIRO DE OBRAS"
            "tipo": None,
            "unidade": rec.get("unidade"),
            "custo_total": rec.get("valor_total"),
            "componentes": componentes,
            "componentes_totais": n_comp + n_ins + n_outros,
            "componentes_composicoes": n_comp,
            "componentes_insumos": n_ins,
            "componentes_outros": n_outros,
            # --- extra fields ---
            "banco": rec.get("banco"),
            "secao": rec.get("secao"),
            "subsecao": rec.get("subsecao"),
            "fonte": "analitico_csv",
        }

        documents.append(Document(page_content=page_content, metadata=metadata))

    return documents


# ---------------------------------------------------------------------------
# 3. Seed logic
# ---------------------------------------------------------------------------


def seed_analitico(
    *,
    csv_path: Path,
    dense_provider: str,
    dense_model: str,
    dense_vector_size: int,
    collection_name: str = "sinapi",
    qdrant_url: str = "http://localhost:6333",
    dense_base_url: str | None = None,
    dense_api_key: str | None = None,
    dry_run: bool = False,
) -> None:
    """Parse ANALITICO.csv, filter out SINAPI top-level compositions,
    and append non-SINAPI compositions to Qdrant."""

    # Parse CSV
    print(f"Parsing CSV: {csv_path}")
    all_records = parse_analitico_csv(csv_path)
    print(f"  Total de composições no CSV: {len(all_records)}")

    # Filter: keep only non-SINAPI top-level compositions
    to_index = [r for r in all_records if r["banco"] != "SINAPI"]
    sinapi_skipped = [r for r in all_records if r["banco"] == "SINAPI"]

    print(f"  Non-SINAPI (a indexar): {len(to_index)}")
    print(f"  SINAPI top-level (ignorados): {len(sinapi_skipped)}")

    if dry_run:
        print("\n--- DRY RUN (nada será indexado) ---")
        for rec in to_index:
            comp = rec.get("componentes", {})
            n_c = len(comp.get("composicoes", []))
            n_i = len(comp.get("insumos", []))
            print(
                f"  [{rec['banco']:>10}] {rec['codigo']:>10}  "
                f"comp={n_c} ins={n_i}  "
                f"{rec['descricao'][:70]}"
            )
        print(f"\nSINAPI top-level ignorados ({len(sinapi_skipped)}):")
        for rec in sinapi_skipped:
            print(f"  {rec['codigo']:>10}  {rec['descricao'][:70]}")
        return

    if not to_index:
        print("Nenhum documento novo para indexar.")
        return

    # Initialize QdrantSinapi
    sinapi_client = QdrantSinapi(
        collection_name=collection_name,
        qdrant_url=qdrant_url,
        dense_model=dense_model,
        dense_size=dense_vector_size,
        dense_provider=dense_provider,
        dense_base_url=dense_base_url,
        dense_api_key=dense_api_key,
    )

    # Build documents
    documents = build_analitico_documents(to_index)
    print(f"{len(documents)} documentos prontos para indexação.")

    # Index (append only, no collection recreation)
    from langchain_qdrant import QdrantVectorStore, RetrievalMode

    vector_store = QdrantVectorStore(
        client=sinapi_client.client,
        collection_name=collection_name,
        embedding=sinapi_client.dense_embeddings,
        sparse_embedding=sinapi_client.sparse_embeddings,
        retrieval_mode=RetrievalMode.HYBRID,
        vector_name="dense",
        sparse_vector_name="sparse",
    )

    ids = [str(uuid4()) for _ in documents]
    vector_store.add_documents(documents=documents, ids=ids)
    print(f"{len(documents)} documentos indexados com sucesso (append).")


# ---------------------------------------------------------------------------
# 4. CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed Qdrant com composições do orçamento analítico (CSV)."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent
        / "data"
        / "ubs-porte-1"
        / "planilha"
        / "ANALITICO.csv",
        help="Caminho para o ANALITICO.csv",
    )
    parser.add_argument(
        "--collection", default="sinapi", help="Nome da coleção no Qdrant"
    )
    parser.add_argument(
        "--qdrant-url", default="http://localhost:6333", help="URL do Qdrant"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas listar o que seria indexado, sem de fato inserir",
    )
    args = parser.parse_args()

    seed_analitico(
        csv_path=args.csv,
        collection_name=args.collection,
        qdrant_url=args.qdrant_url,
        dry_run=args.dry_run,
        dense_provider="ollama",
        dense_model="qwen3-embedding:0.6b",
        dense_vector_size=1024,
    )


if __name__ == "__main__":
    main()
