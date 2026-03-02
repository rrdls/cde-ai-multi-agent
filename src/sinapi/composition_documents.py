from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from langchain_core.documents import Document

if __package__:
    from .compositions import export_workbook
else:
    from compositions import export_workbook



CompositionRecord = Dict[str, Any]


def build_composition_documents(records: Iterable[CompositionRecord]) -> List[Document]:
    """Convert exported compositions into LangChain Documents."""
    documents: List[Document] = []
    for record in records:
        content = _get_description(record)
        if content is None:
            continue

        metadata = _build_metadata(record)
        documents.append(Document(page_content=content, metadata=metadata))
    return documents


def _get_description(record: CompositionRecord) -> Optional[str]:
    descricao = record.get("descricao")
    if descricao is None:
        return None
    text = str(descricao).strip()
    return text or None


def _build_metadata(record: CompositionRecord) -> Dict[str, Any]:
    componentes = record.get("componentes") or {}
    composicoes = componentes.get("composicoes") or []
    insumos = componentes.get("insumos") or []
    outros = componentes.get("outros") or []

    return {
        "codigo": record.get("codigo"),
        "classe": record.get("classe"),
        "tipo": record.get("tipo"),
        "unidade": record.get("unidade"),
        "custo_total": record.get("custo_total"),
        "componentes": componentes,
        "componentes_totais": len(composicoes) + len(insumos) + len(outros),
        "componentes_composicoes": len(composicoes),
        "componentes_insumos": len(insumos),
        "componentes_outros": len(outros),
    }


if __name__ == "__main__":
    from pathlib import Path

    workbook_path = Path("src/sinapi/docs/SINAPI_Custo_Ref_Composicoes_Analitico_AL_202412_Desonerado.xlsx")
    payload = export_workbook(workbook_path, limit=5)
    documents = build_composition_documents(payload)

    
