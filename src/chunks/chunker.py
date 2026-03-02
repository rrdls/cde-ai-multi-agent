from __future__ import annotations

"""
Extração de chunks a partir de PDFs e CSVs.

PDFs: converte PDF → markdown (via docling) → parágrafos → janelas deslizantes → JSONL.
CSVs: cada linha não-vazia do CSV vira um chunk.

Dependências externas: docling
"""

import csv
import json
import re
import time
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

# ---------------------------------------------------------------------------
# PDF → Markdown
# ---------------------------------------------------------------------------

PAGE_BREAK_MARKER = "<<<PAGE_BREAK>>>"


def _build_converter() -> DocumentConverter:
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=PdfPipelineOptions(
                    do_ocr=False,
                    enable_image_extraction=False,
                    do_table_structure=False,
                )
            )
        }
    )


_converter: DocumentConverter | None = None


def pdf_to_markdown(pdf_path: Path, *, output_dir: Optional[Path] = None) -> str:
    """Converte um PDF em markdown usando docling. Opcionalmente salva em disco."""
    global _converter
    if _converter is None:
        _converter = _build_converter()

    print(f"Convertendo: {pdf_path.name}")
    result = _converter.convert(str(pdf_path))
    markdown = result.document.export_to_markdown(
        page_break_placeholder=PAGE_BREAK_MARKER
    )

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", pdf_path.stem).strip("_") or "document"
        md_path = output_dir / f"{slug}.md"
        md_path.write_text(markdown, encoding="utf-8")
        print(f"Markdown salvo em {md_path}")

    return markdown


# ---------------------------------------------------------------------------
# Markdown → Parágrafos
# ---------------------------------------------------------------------------


def _is_separator_line(line: str) -> bool:
    """Detecta linhas de separador de tabela Markdown (---|---)."""
    trimmed = line.strip()
    return bool(trimmed) and all(ch in "-|: " for ch in trimmed)


def _normalize_cell(cell: str) -> str:
    text = cell.strip().strip('"').strip("'")
    return " ".join(text.split())


def _split_table_lines(markdown_string: str) -> Iterable[List[str]]:
    for raw_line in markdown_string.strip().splitlines():
        if not raw_line.strip():
            continue
        if _is_separator_line(raw_line):
            continue
        cells = [_normalize_cell(cell) for cell in raw_line.strip().strip("|").split("|")]
        if not any(cells):
            continue
        yield cells


def markdown_table_to_records(markdown_string: str) -> List[str]:
    """Converte uma tabela Markdown em uma lista de linhas limpas, uma por registro."""
    lines = list(_split_table_lines(markdown_string))
    if not lines:
        return []

    header = " | ".join(lines[0])
    seen: set[str] = set()
    records: List[str] = []

    for cells in lines[1:]:
        row_text = " | ".join(c for c in cells if c)
        if not row_text:
            continue
        normalized = " ".join(row_text.split())
        if normalized == header or normalized in seen:
            continue
        seen.add(normalized)
        records.append(row_text)

    return records


def split_paragraphs(content: str) -> List[Tuple[str, bool]]:
    """
    Divide o markdown em parágrafos, tratando tabelas como linhas individuais.
    Retorna tuplas (texto, is_table_row).
    """
    raw_blocks = [part for part in content.strip().split("\n\n") if part.strip()]
    paragraphs: List[Tuple[str, bool]] = []

    for block in raw_blocks:
        lines = block.splitlines()
        if lines and lines[0].lstrip().startswith("|") and len(lines) > 2:
            paragraphs.extend((row, True) for row in markdown_table_to_records(block))
        elif lines and lines[0].lstrip().startswith("|") and lines[0].lstrip().endswith("|"):
            for item in block.split("\n"):
                if _is_separator_line(item):
                    continue
                paragraphs.append((item.strip(), True))
        else:
            paragraphs.append((block.strip(), False))

    return paragraphs


# ---------------------------------------------------------------------------
# Sliding Window
# ---------------------------------------------------------------------------


def build_sliding_windows_with_pages(
    paragraphs_with_pages: list[tuple[str, int, bool]], window_size: int = 1
) -> list[tuple[str, int]]:
    """
    Cria janelas deslizantes mantendo a página do primeiro parágrafo.
    Linhas de tabela (is_table_row=True) viram janelas isoladas.
    """
    if window_size <= 0:
        raise ValueError("window_size deve ser positivo")
    if not paragraphs_with_pages:
        return []

    windows: list[tuple[str, int]] = []

    def _flush_buffer(buffer: list[tuple[str, int]]) -> None:
        if not buffer:
            return
        if len(buffer) <= window_size:
            windows.append(("\n\n".join(p for p, _ in buffer), buffer[0][1]))
            return
        for start in range(len(buffer) - window_size + 1):
            window = buffer[start : start + window_size]
            windows.append(("\n\n".join(p for p, _ in window), window[0][1]))

    buffer: list[tuple[str, int]] = []
    for paragraph, page_no, is_table_row in paragraphs_with_pages:
        if is_table_row:
            _flush_buffer(buffer)
            buffer = []
            windows.append((paragraph, page_no))
        else:
            buffer.append((paragraph, page_no))

    _flush_buffer(buffer)
    return windows


# ---------------------------------------------------------------------------
# Pipeline: PDF → Chunks
# ---------------------------------------------------------------------------


def _slugify(pdf_path: Path) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", pdf_path.stem).strip("-").lower()
    return slug or "pdf"


def _clean_text_artifacts(text: str) -> str:
    """Remove sequências longas de pontos (ex: sumários)."""
    return re.sub(r"\.{3,}", " ", text)


_IMAGE_PLACEHOLDER_RE = re.compile(
    r"^(\s*<!--\s*image\s*-->\s*)+$", re.IGNORECASE
)


def _is_image_only(text: str) -> bool:
    """Retorna True se o texto contém apenas placeholders de imagem do Docling."""
    return bool(_IMAGE_PLACEHOLDER_RE.match(text.strip()))


def chunk_pdf_to_records(
    pdf_path: Path,
    *,
    window_size: int = 1,
    markdown_output_dir: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Converte um PDF em chunks (sliding window) prontos para persistência."""
    markdown_text = pdf_to_markdown(pdf_path, output_dir=markdown_output_dir)
    pages = [page for page in markdown_text.split(PAGE_BREAK_MARKER) if page.strip()]
    slug = _slugify(pdf_path)

    paragraphs_with_pages: list[tuple[str, int, bool]] = []
    for page_no, page_text in enumerate(pages, start=1):
        paragraphs = split_paragraphs(page_text)
        paragraphs_with_pages.extend(
            (paragraph, page_no, is_table_row) for paragraph, is_table_row in paragraphs
        )

    chunk_bodies = build_sliding_windows_with_pages(paragraphs_with_pages, window_size=window_size)
    if not chunk_bodies:
        return []

    records: list[dict[str, Any]] = []
    idx = 0
    for text, page_no in chunk_bodies:
        text = _clean_text_artifacts(text)
        if _is_image_only(text):
            continue
        idx += 1
        records.append(
            {
                "chunk_id": f"{slug}-chunk-{idx:04d}",
                "source_path": str(pdf_path),
                "source_name": pdf_path.name,
                "source_type": "pdf",
                "text": text,
                "page": page_no,
            }
        )

    return records


# ---------------------------------------------------------------------------
# CSV chunking
# ---------------------------------------------------------------------------


def chunk_csv_to_records(csv_path: Path) -> list[dict[str, Any]]:
    """Converte um CSV em chunks: cada linha não-vazia vira um chunk.

    O texto de cada chunk é a concatenação das células não-vazias,
    separadas por ', '. Nenhuma filtragem de headers é feita.
    """
    slug = _slugify(csv_path)
    records: list[dict[str, Any]] = []
    idx = 0

    with csv_path.open(encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            cells = [c.strip() for c in row if c.strip()]
            if not cells:
                continue
            idx += 1
            text = ", ".join(cells)
            records.append(
                {
                    "chunk_id": f"{slug}-csv-chunk-{idx:04d}",
                    "source_path": str(csv_path),
                    "source_name": csv_path.name,
                    "source_type": "csv",
                    "text": text,
                    "page": None,
                }
            )

    return records


# ---------------------------------------------------------------------------
# Batch extraction
# ---------------------------------------------------------------------------


class Timer:
    def __init__(self) -> None:
        self._start: float | None = None
        self._end: float | None = None

    def start(self) -> None:
        self._start = time.perf_counter()

    def stop(self) -> None:
        self._end = time.perf_counter()

    @property
    def elapsed_minutes(self) -> float:
        if self._start is None:
            return 0.0
        end = self._end if self._end is not None else time.perf_counter()
        return (end - self._start) / 60


def extract_all(
    pdf_root: Path,
    output_dir: Path,
    *,
    csv_root: Optional[Path] = None,
    overwrite: bool = False,
    window_size: int = 1,
    markdown_output_dir: Optional[Path] = None,
) -> None:
    """Itera PDFs (e CSVs se csv_root fornecido) e salva JSONL com chunks."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_jsonls: list[Path] = []

    # --- PDFs ---
    pdf_files = sorted(pdf_root.rglob("*.pdf"))
    if not pdf_files:
        print(f"Nenhum PDF encontrado em {pdf_root}")
    
    for pdf_path in pdf_files:
        timer = Timer()
        timer.start()
        slug = _slugify(pdf_path)
        target_file = output_dir / f"{slug}.jsonl"

        if target_file.exists() and not overwrite:
            print(f"[skip] {pdf_path.name} já existe em {target_file}")
            generated_jsonls.append(target_file)
            continue

        try:
            records = chunk_pdf_to_records(
                pdf_path,
                window_size=window_size,
                markdown_output_dir=markdown_output_dir,
            )
        except Exception as e:
            print(f"[erro] Falha ao processar {pdf_path.name}: {e}")
            continue

        if not records:
            print(f"[aviso] Nenhum chunk gerado para {pdf_path.name}")
            continue

        with target_file.open("w", encoding="utf-8") as f:
            for record in records:
                json.dump(record, f, ensure_ascii=False)
                f.write("\n")

        timer.stop()
        print(f"[ok] {len(records)} chunks (pdf) salvos em {target_file}")
        generated_jsonls.append(target_file)

        metrics_path = output_dir / f"{slug}_metrics.json"
        metrics_payload = {
            "source_name": pdf_path.name,
            "source_path": str(pdf_path),
            "source_type": "pdf",
            "window_size": window_size,
            "chunks_total": len(records),
            "elapsed_minutes": timer.elapsed_minutes,
        }
        with metrics_path.open("w", encoding="utf-8") as f:
            json.dump(metrics_payload, f, ensure_ascii=False, indent=2)

    # --- CSVs ---
    if csv_root and csv_root.exists():
        csv_files = sorted(csv_root.rglob("*.csv"))
        if not csv_files:
            print(f"Nenhum CSV encontrado em {csv_root}")

        for csv_file in csv_files:
            slug = _slugify(csv_file)
            target_file = output_dir / f"{slug}.jsonl"

            if target_file.exists() and not overwrite:
                print(f"[skip] {csv_file.name} já existe em {target_file}")
                generated_jsonls.append(target_file)
                continue

            records = chunk_csv_to_records(csv_file)

            if not records:
                print(f"[aviso] Nenhum chunk gerado para {csv_file.name}")
                continue

            with target_file.open("w", encoding="utf-8") as f:
                for record in records:
                    json.dump(record, f, ensure_ascii=False)
                    f.write("\n")

            print(f"[ok] {len(records)} chunks (csv) salvos em {target_file}")
            generated_jsonls.append(target_file)

    # --- Concatenar JSONL unificado (PDFs primeiro, depois CSVs) ---
    if len(generated_jsonls) > 1:
        project_slug = output_dir.parent.name
        unified_path = output_dir / f"{project_slug}-all.jsonl"

        total = 0
        with unified_path.open("w", encoding="utf-8") as out:
            for jl in generated_jsonls:
                with jl.open(encoding="utf-8") as inp:
                    for line in inp:
                        out.write(line)
                        total += 1

        print(f"[ok] {total} chunks unificados em {unified_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    _project_root = Path(__file__).resolve().parent.parent.parent

    parser = argparse.ArgumentParser(description="Extrai chunks de PDFs e CSVs")
    parser.add_argument("pdf_root", nargs="?", type=Path, default=None, help="Diretório raiz com PDFs (sobrescreve --project)")
    parser.add_argument("--project", "-p", type=str, default=None, help="Nome do projeto (ex: ubs-porte-1). Define pdf_root e output automaticamente.")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Diretório de saída (sobrescreve --project)")
    parser.add_argument("--markdown-dir", type=Path, default=None, help="Salvar markdown convertido")
    parser.add_argument("--window-size", "-w", type=int, default=1)
    parser.add_argument("--no-csv", action="store_true", help="Não processar CSVs")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    # Resolve paths from --project or explicit arguments
    csv_root = None
    if args.project:
        project_dir = _project_root / "data" / args.project
        pdf_root = args.pdf_root or project_dir / "pdfs"
        output = args.output or project_dir / "chunks"
        if args.markdown_dir is None:
            args.markdown_dir = project_dir / "markdown"
        if not args.no_csv:
            csv_root = project_dir / "csv"
    else:
        pdf_root = args.pdf_root or _project_root / "data" / "pdfs"
        output = args.output or _project_root / "data" / "chunks"

    timer = Timer()
    timer.start()

    print(f"Projeto: {args.project or '(nenhum)'}")
    print(f"Origem PDFs: {pdf_root}")
    print(f"Origem CSVs: {csv_root or '(desabilitado)'}")
    print(f"Destino: {output}")
    print(f"Window size: {args.window_size}")

    extract_all(
        pdf_root,
        output,
        csv_root=csv_root,
        overwrite=args.overwrite,
        window_size=args.window_size,
        markdown_output_dir=args.markdown_dir,
    )

    timer.stop()
    print(f"Tempo total: {timer.elapsed_minutes:.2f} minutos")


if __name__ == "__main__":
    main()
