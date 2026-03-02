# SINAPI Qdrant

Índice vetorial híbrido (dense + sparse) das composições SINAPI, armazenado no Qdrant.

## Objetivo

Fornecer busca semântica e lexical sobre as ~4.000 composições do catálogo SINAPI, servindo como backend de retrieval para os pipelines `chain/` e `sinapi_agent/`.

## Arquitetura

### Busca Híbrida

A coleção Qdrant armazena dois tipos de vetores para cada composição:

```
Composição SINAPI (ex: "SIFÃO FLEXÍVEL EM PVC 1 X 1.1/2")
    │
    ├── Dense Vector (1024 dims)
    │   Modelo: qwen3-embedding:0.6b (Ollama)
    │   Captura: similaridade semântica
    │
    └── Sparse Vector (BM25)
        Modelo: Qdrant/bm25 (FastEmbed)
        Captura: correspondência lexical (palavras-chave)
```

Modos de busca disponíveis:

| Modo | Usa | Melhor para |
|---|---|---|
| `dense` | Apenas embedding denso | Busca por sinônimos e conceitos |
| `sparse` | Apenas BM25 | Busca exata por termos técnicos |
| `hybrid` | Dense + Sparse (RRF) | Uso geral (default) |

### Pré-processamento: ASCII Folding

Antes de gerar os sparse vectors, o texto passa por **ASCII folding** (`unicodedata.normalize('NFKD')`) que remove diacríticos:

```
"SIFÃO"    → "SIFAO"
"VÁLVULA"  → "VALVULA"
"INSPEÇÃO" → "INSPECAO"
```

Isso é necessário porque o tokenizer BM25 do FastEmbed é sensível a acentos: sem folding, a query `"SIFAO"` não encontra documentos indexados como `"SIFÃO"`.

O folding é aplicado em dois pontos:
1. **Ingestão**: `add_compositions()` aplica `ascii_fold()` no `page_content` antes de indexar
2. **Query**: `similarity_search()` aplica `ascii_fold()` na query antes de buscar

A função `ascii_fold()` é exportada pelo módulo para uso externo.

## Estrutura

```
src/sinapi/
├── README.md                # Este arquivo
├── qdrant_simple.py         # QdrantSinapi: busca, indexação, deduplicação
├── composition_documents.py # Parser: Excel → LangChain Documents
├── compositions.py          # Leitor do workbook SINAPI (.xlsx)
├── embeddings_factory.py    # Factory de embeddings densos (Ollama, OpenAI, etc.)
├── seed_qdrant.py           # Script de seed: cria coleção e indexa composições SINAPI (Excel)
├── seed_analitico.py        # Script de seed: append de composições não-SINAPI (CSV analítico)
├── playground.py            # REPL interativo para testes de busca
├── docker-compose.yml       # Qdrant local (porta 6333)
├── docs/                    # Workbook SINAPI (.xlsx)
├── qdrant_data/             # Dados persistidos do Qdrant
└── qdrant_config/           # Configuração do Qdrant
```

## Uso

### 1. Subir o Qdrant

```bash
cd src/sinapi
docker-compose up -d
```

### 2. Indexar composições SINAPI (Excel)

```bash
python -m src.sinapi.seed_qdrant
```

Isso recria a coleção e indexa todas as composições do workbook SINAPI com ASCII folding.

### 3. Indexar composições não-SINAPI (CSV analítico)

```bash
# Indexar composições de orçamento analítico (Próprio/CPU, CPOS/CDHU, etc.)
python -m src.sinapi.seed_analitico

# Apenas listar o que seria indexado, sem inserir
python -m src.sinapi.seed_analitico --dry-run

# CSV e coleção customizados
python -m src.sinapi.seed_analitico --csv data/ubs-porte-1/planilha/ANALITICO.csv --collection sinapi
```

Este script é **append-only**: não recria a coleção, apenas adiciona composições cujo campo `banco` não seja `"SINAPI"`. O parser CSV lê a hierarquia do orçamento analítico (seção → subseção → composição → composição auxiliar → insumo) e gera documentos com metadata compatível com o seed SINAPI, acrescidos de campos extras (`banco`, `secao`, `subsecao`, `fonte`).

### 4. Buscar composições

```python
from src.sinapi.qdrant_simple import QdrantSinapi

sinapi = QdrantSinapi(
    dense_provider="ollama",
    dense_model="qwen3-embedding:0.6b",
    dense_size=1024,
)

# Busca híbrida (default)
results = sinapi.similarity_search("registro de pressão", k=3)

# Busca apenas lexical
results = sinapi.similarity_search("sifão PVC", mode="sparse")

# Com filtro de metadata
results = sinapi.similarity_search(
    "tubo PVC",
    metadata_filters=[("tipo", "COMPOSICAO")],
)
```

### 5. Playground interativo

```bash
cd src/sinapi
python playground.py
```

## API Principal (`QdrantSinapi`)

| Método | Descrição |
|---|---|
| `create_collection()` | Cria coleção híbrida (dense + sparse) |
| `add_compositions(path)` | Indexa composições com ASCII folding |
| `similarity_search(query, k, mode)` | Busca com deduplicação por código |
| `semantic_similarity(a, b)` | Cosseno entre embeddings densos |
| `sparse_similarity(a, b)` | Cosseno entre embeddings BM25 |
| `hybrid_similarity(a, b, alpha)` | Combinação ponderada (dense + sparse) |
| `embed_text(text)` | Gera embedding denso para um texto |
| `list_distinct_metadata(field)` | Lista valores únicos de metadata |

Função utilitária exportada:

| Função | Descrição |
|---|---|
| `ascii_fold(text)` | Remove diacríticos via NFKD (ex: SIFÃO → SIFAO) |
| `deduplicate_documents(docs, limit)` | Remove duplicatas por código SINAPI |

## Dependências

- `langchain-qdrant` (QdrantVectorStore, FastEmbedSparse)
- `langchain-core` (Document)
- `qdrant-client` (QdrantClient, models)
- `openpyxl` (leitor Excel)
- Docker (Qdrant server)
