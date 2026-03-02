# Chunks

Extração de chunks de texto a partir de **PDFs** e **CSVs** para uso nos pipelines de vinculação SINAPI.

## Objetivo

Transformar documentos brutos (projetos técnicos em PDF e listas de materiais em CSV) em fragmentos de texto normalizados (chunks), salvos em formato JSONL, prontos para indexação no Qdrant e processamento pelos pipelines Chain e Agent.

## Pipeline

```
PDF ──→ Markdown (docling) ──→ Parágrafos ──→ Sliding Windows ──→ JSONL
CSV ──→ Linha por linha ──────────────────────────────────────→ JSONL
```

### PDF: 4 estágios

| Estágio | Função | Descrição |
|---------|--------|-----------|
| **1. Conversão** | `pdf_to_markdown()` | Converte PDF para Markdown via docling (sem OCR, sem tabelas, sem imagens) |
| **2. Paragrafação** | `split_paragraphs()` | Divide o Markdown em parágrafos. Tabelas Markdown são decompostas em linhas individuais via `markdown_table_to_records()` |
| **3. Sliding Window** | `build_sliding_windows_with_pages()` | Agrupa parágrafos em janelas deslizantes de tamanho configurável (`--window-size`). Linhas de tabela viram chunks isolados (nunca agrupadas) |
| **4. Serialização** | `chunk_pdf_to_records()` | Gera registros com `chunk_id`, `source_path`, `source_name`, `source_type`, `text`, `page`. Remove artefatos (séries de pontos de sumários) e placeholders de imagem do docling |

### CSV: direto

Cada linha não vazia vira um chunk. As células são concatenadas com `, `. Formato de `chunk_id`: `{slug}-csv-chunk-{N:04d}`.

### Batch (`extract_all`)

Itera todos os PDFs (e CSVs se `--csv_root` fornecido) de um diretório, gerando:

- Um `.jsonl` por arquivo fonte
- Um `_metrics.json` por PDF (tempo de processamento, total de chunks, window_size)
- Um `{project}-all.jsonl` unificado (todos os chunks concatenados)

## Formato de Saída (JSONL)

Cada linha do JSONL contém:

```json
{
  "chunk_id": "ubs-porte-1-arq-chunk-0042",
  "source_path": "data/ubs-porte-1/pdfs/UBS PORTE 1 - ARQ.pdf",
  "source_name": "UBS PORTE 1 - ARQ.pdf",
  "source_type": "pdf",
  "text": "Alvenaria de vedação com blocos cerâmicos...",
  "page": 3
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `chunk_id` | `str` | Identificador único: `{slug}-chunk-{N:04d}` (PDF) ou `{slug}-csv-chunk-{N:04d}` (CSV) |
| `source_path` | `str` | Caminho absoluto do arquivo original |
| `source_name` | `str` | Nome do arquivo original |
| `source_type` | `str` | `"pdf"` ou `"csv"` |
| `text` | `str` | Conteúdo textual do chunk |
| `page` | `int\|null` | Número da página (PDFs) ou `null` (CSVs) |

## Uso

```bash
# Modo projeto (resolve caminhos automaticamente)
python -m src.chunks.chunker --project ubs-porte-1

# Caminhos explícitos
python -m src.chunks.chunker data/pdfs/ --output data/chunks/ --window-size 2

# Com CSVs
python -m src.chunks.chunker --project ubs-porte-1 --window-size 1

# Sem CSVs
python -m src.chunks.chunker --project ubs-porte-1 --no-csv

# Sobrescrever chunks existentes
python -m src.chunks.chunker --project ubs-porte-1 --overwrite
```

### Parâmetros CLI

| Parâmetro | Default | Descrição |
|-----------|---------|-----------|
| `pdf_root` | `data/pdfs/` | Diretório raiz com PDFs (posicional, opcional) |
| `--project`, `-p` | `None` | Nome do projeto. Define `pdf_root=data/{project}/pdfs`, `output=data/{project}/chunks`, `markdown-dir=data/{project}/markdown`, `csv_root=data/{project}/csv` |
| `--output`, `-o` | `data/chunks/` | Diretório de saída para JSONLs |
| `--markdown-dir` | `None` | Salvar Markdown intermediário convertido |
| `--window-size`, `-w` | `1` | Tamanho da janela deslizante (parágrafos por chunk) |
| `--no-csv` | `False` | Não processar CSVs |
| `--overwrite` | `False` | Sobrescrever JSONLs existentes |

### Modo `--project`

Quando `--project` é usado, os caminhos são derivados automaticamente:

```
data/{project}/
├── pdfs/           → pdf_root
├── csv/            → csv_root (se --no-csv não definido)
├── markdown/       → markdown_output_dir
└── chunks/         → output_dir
    ├── {slug}.jsonl
    ├── {slug}_metrics.json
    └── {project}-all.jsonl
```

## Estrutura

```
src/chunks/
├── README.md       # Este arquivo
└── chunker.py      # Pipeline completo: conversão, paragrafação, sliding window, serialização, CLI
```

## Dependências

- `docling` (conversão PDF → Markdown)
- Módulos padrão: `csv`, `json`, `re`, `time`, `pathlib`, `argparse`
