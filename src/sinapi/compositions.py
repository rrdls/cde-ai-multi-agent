#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

HEADER_ANCHOR = "DESCRICAO DA CLASSE"

COST_FIELD_MAP = {
    "mao_de_obra": "CUSTO MAO DE OBRA",
    "material": "CUSTO MATERIAL",
    "equipamento": "CUSTO EQUIPAMENTO",
    "servicos_terceiros": "CUSTO SERVICOS TERCEIROS",
    "outros": "CUSTO OUTROS",
}

PERCENT_FIELD_MAP = {
    "mao_de_obra": "% MAO DE OBRA",
    "material": "% MATERIAL",
    "equipamento": "% EQUIPAMENTO",
    "servicos_terceiros": "% SERVICOS TERCEIROS",
    "outros": "% OUTROS",
}


def load_composition_frame(path: Path) -> pd.DataFrame:
    """Return the SINAPI analytic table as a cleaned dataframe."""
    df_raw = pd.read_excel(path, sheet_name=0, header=None)
    header_row_idx = _find_header_row(df_raw)
    header_row = df_raw.iloc[header_row_idx].tolist()
    deduplicated_header = _deduplicate_columns(header_row)

    df = df_raw.iloc[header_row_idx + 1 :].copy()
    df.columns = deduplicated_header

    df = df.rename(
        columns={
            "CUSTO TOTAL": "CUSTO TOTAL COMPOSICAO",
            "CUSTO TOTAL_1": "CUSTO TOTAL ITEM",
        }
    )

    df = df[df["CODIGO DA COMPOSICAO"].notna()].copy()
    df["CODIGO DA COMPOSICAO"] = df["CODIGO DA COMPOSICAO"].map(normalise_code)
    df["TIPO ITEM"] = df["TIPO ITEM"].map(normalise_text)

    return df


def inspect_workbook(path: Path, preview: int = 3) -> Dict[str, Any]:
    """
    Collect basic information about the workbook for planning purposes.

    Returns a dictionary so callers can decide como exibir os dados.
    """
    if not path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {path}")

    df = load_composition_frame(path)
    sheet_names = pd.ExcelFile(path).sheet_names

    summary: Dict[str, Any] = {
        "arquivo": path.name,
        "planilhas": sheet_names,
        "linhas_totais": len(df),
        "total_composicoes": int(df["CODIGO DA COMPOSICAO"].nunique()),
        "colunas": df.columns.tolist(),
        "preview": [],
    }

    for codigo, group in _iter_composition_groups(df, limit=preview):
        meta_row = _get_meta_row(group)
        descricao = (
            normalise_text(meta_row.get("DESCRICAO DA COMPOSICAO"))
            if meta_row is not None
            else None
        )
        total_itens = int(group["TIPO ITEM"].notna().sum())
        tipos_itens = sorted(
            {normalise_text(value) for value in group["TIPO ITEM"].dropna().unique()}
        )
        summary["preview"].append(
            {
                "codigo": codigo,
                "descricao": descricao,
                "total_itens": total_itens,
                "tipos_itens": tipos_itens,
            }
        )

    return summary


def export_compositions_to_json(
    df: pd.DataFrame, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Transform the dataframe into structured JSON-ready objects."""
    payload: List[Dict[str, Any]] = []

    for codigo, group in _iter_composition_groups(df, limit=limit):
        meta_row = _get_meta_row(group)
        if meta_row is None:
            continue

        base_record = {
            "codigo": codigo,
            "descricao": normalise_text(meta_row.get("DESCRICAO DA COMPOSICAO")),
            "classe": f"{normalise_text(meta_row.get("SIGLA DA CLASSE"))} - {normalise_text(meta_row.get('DESCRICAO DA CLASSE'))}",
            "tipo": normalise_text(meta_row.get("DESCRICAO DO TIPO 1")),
            "unidade": normalise_text(meta_row.get("UNIDADE")),
        }

        componentes = {"composicoes": [], "insumos": []}
        for _, item_row in group[group["TIPO ITEM"].notna()].iterrows():
            item_payload = {
                "codigo": normalise_code(item_row.get("CODIGO ITEM")),
                "descricao": normalise_text(item_row.get("DESCRIÇÃO ITEM")),
                "unidade": normalise_text(item_row.get("UNIDADE ITEM")),
                "coeficiente": parse_decimal(item_row.get("COEFICIENTE")),
                "preco_unitario": parse_decimal(item_row.get("PRECO UNITARIO")),
                "custo_total": parse_decimal(item_row.get("CUSTO TOTAL ITEM")),
            }

            item_type = (item_row.get("TIPO ITEM") or "").strip().upper()
            if item_type == "COMPOSICAO":
                componentes["composicoes"].append(item_payload)
            elif item_type == "INSUMO":
                componentes["insumos"].append(item_payload)
            else:
                componentes.setdefault("outros", []).append(
                    {"tipo": item_type or None, **item_payload}
                )

        base_record["componentes"] = componentes
        base_record["custo_total"] = parse_decimal(
            meta_row.get("CUSTO TOTAL COMPOSICAO")
        )
        payload.append(base_record)

    return payload


def export_workbook(
    workbook_path: Path,
    *,
    limit: Optional[int] = None,
    output_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    High-level helper that parses the workbook and optionally writes a JSON file.
    """
    if not workbook_path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {workbook_path}")

    df = load_composition_frame(workbook_path)
    payload = export_compositions_to_json(df, limit=limit)

    if output_path is not None:
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return payload


def _iter_composition_groups(
    df: pd.DataFrame, limit: Optional[int] = None
) -> Iterable[tuple[str, pd.DataFrame]]:
    count = 0
    for codigo, group in df.groupby("CODIGO DA COMPOSICAO", sort=False):
        if codigo is None:
            continue
        yield codigo, group
        count += 1
        if limit is not None and count >= limit:
            break


def _get_meta_row(group: pd.DataFrame) -> Optional[pd.Series]:
    meta = group[group["TIPO ITEM"].isna()]
    if not meta.empty:
        return meta.iloc[0]
    return group.iloc[0] if not group.empty else None


def _pick_numeric_fields(
    row: pd.Series, mapping: Dict[str, str], prefix: str = ""
) -> Dict[str, Optional[float]]:
    values = {
        f"{prefix}{alias}": parse_decimal(row.get(source))
        for alias, source in mapping.items()
    }
    return {key: value for key, value in values.items() if value is not None}


def _find_header_row(df: pd.DataFrame) -> int:
    for idx, value in enumerate(df.iloc[:, 0]):
        if isinstance(value, str) and value.strip().upper() == HEADER_ANCHOR:
            return idx
    raise ValueError("Nao foi possivel localizar o cabecalho da planilha.")


def _deduplicate_columns(columns: List[str]) -> List[str]:
    seen: Dict[str, int] = {}
    result: List[str] = []
    for col in columns:
        col = col or ""
        if col not in seen:
            seen[col] = 0
            result.append(col)
        else:
            seen[col] += 1
            result.append(f"{col}_{seen[col]}")
    return result


def normalise_text(value: Any) -> Optional[str]:
    if isinstance(value, float) and pd.isna(value):
        return None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalise_code(value: Any) -> Optional[str]:
    text = normalise_text(value)
    if text is None:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    return text


def parse_decimal(value: Any) -> Optional[float]:
    if isinstance(value, float) and pd.isna(value):
        return None
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalised = text.replace(".", "").replace(",", ".")
    try:
        return float(normalised)
    except ValueError:
        return None


if __name__ == "__main__":
    """
    Pequeno exemplo de uso direto via chamada de função.
    Ajuste `exemplo_arquivo` para apontar para algum XLSX analítico do SINAPI.
    """
    exemplo_arquivo = Path("src/sinapi/docs/SINAPI_Custo_Ref_Composicoes_Analitico_AL_202412_Desonerado.xlsx")
    if not exemplo_arquivo.exists():
        print(
            f"Defina o caminho de um arquivo analitico antes de rodar. "
            f"Arquivo esperado: {exemplo_arquivo.resolve()}"
        )
    else:
        # resumo = inspect_workbook(exemplo_arquivo, preview=2)
        # print(json.dumps(resumo, ensure_ascii=False, indent=2))
        payload = export_workbook(exemplo_arquivo, output_path=Path("composicoes.json"))
        print(f"{len(payload)} composicoes exportadas para composicoes.json")
