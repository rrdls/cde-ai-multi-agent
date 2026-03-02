import unicodedata
from math import sqrt
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
from uuid import uuid4

from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client import models
from qdrant_client.http.models import Distance, SparseVectorParams, VectorParams

if __package__:
    from .composition_documents import build_composition_documents
    from .compositions import export_workbook
    from .embeddings_factory import build_dense_embeddings
else:
    from composition_documents import build_composition_documents
    from compositions import export_workbook
    from embeddings_factory import build_dense_embeddings

from langchain_core.documents import Document


# ---------------------------------------------------------------------------
# Text normalization (ASCII folding)
# ---------------------------------------------------------------------------


def ascii_fold(text: str) -> str:
    """Remove diacríticos via NFKD decomposition (ex: SIFÃO → SIFAO).

    Aplicado ao texto antes de gerar sparse vectors (BM25), garantindo
    que termos com e sem acento produzam os mesmos tokens.
    """
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Deduplication (ported from mestrado-code/src/agentic/search_state.py)
# ---------------------------------------------------------------------------


def _extract_code(metadata: Dict[str, Any]) -> Optional[str]:
    """Extract and normalize the SINAPI code from document metadata."""
    codigo = metadata.get("codigo")
    if codigo is None:
        return None
    text = str(codigo).strip()
    return text or None


def deduplicate_documents(
    documents: Sequence[Document],
    limit: int,
    seen_codes: Optional[Set[str]] = None,
) -> Tuple[List[Document], int]:
    """Remove duplicatas usando o campo 'codigo' como chave.

    Args:
        documents: Lista de documentos retornados pela busca.
        limit:     Quantidade maxima de documentos unicos a retornar.
        seen_codes: Set externo de codigos ja vistos (atualizado in-place).
                    Permite dedup cross-search em pipelines agentic.

    Returns:
        (unique_documents, duplicates_count)
    """
    if limit <= 0:
        return [], 0

    working_seen = seen_codes if seen_codes is not None else set()
    unique: List[Document] = []
    duplicates = 0

    for document in documents:
        metadata: Dict[str, Any] = document.metadata or {}
        codigo = _extract_code(metadata)

        if codigo and codigo in working_seen:
            duplicates += 1
            continue

        unique.append(document)
        if codigo:
            working_seen.add(codigo)

        if len(unique) >= limit:
            break

    return unique, duplicates


class QdrantSinapi:
    def __init__(
        self,
        *,
        dense_provider: str,
        dense_model: str,
        dense_size: int,
        collection_name: str = "composicao",
        qdrant_url: str = "http://localhost:6333",
        dense_base_url: Optional[str] = None,
        dense_api_key: Optional[str] = None,
        dense_embeddings=None,
    ):
        self.collection_name = collection_name
        self.qdrant_url = qdrant_url
        self.dense_model = dense_model

        # embeddings denso e esparso
        if dense_embeddings is not None:
            self.dense_embeddings = dense_embeddings
            self.dense_size = dense_size
        else:
            embedding_obj, size = build_dense_embeddings(
                provider=dense_provider,
                model=dense_model,
                vector_size=dense_size,
                base_url=dense_base_url,
                api_key=dense_api_key,
            )
            self.dense_embeddings = embedding_obj
            self.dense_size = size

        self.sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")

        self.client = QdrantClient(url=qdrant_url, prefer_grpc=False)

    def _load_composition_documents(
        self, workbook_path: Path, limit: Optional[int] = None
    ):
        payload = export_workbook(workbook_path, limit=limit)
        documents = build_composition_documents(payload)
        if not documents:
            raise ValueError("Nenhuma descrição disponível para gerar embeddings.")
        return documents

    def create_collection(self):
        """Cria uma coleção híbrida (densa + esparsa)"""
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config={
                "dense": VectorParams(size=self.dense_size, distance=Distance.COSINE)
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=False)
                )
            },
        )

    def _build_vector_store(self, retrieval_mode: RetrievalMode):
        """Cria um VectorStore configurado com o modo desejado"""
        return QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.dense_embeddings,
            sparse_embedding=self.sparse_embeddings,
            retrieval_mode=retrieval_mode,
            vector_name="dense",
            sparse_vector_name="sparse",
        )

    def add_compositions(self, workbook_path: Path, limit: Optional[int] = None):
        """Indexa tudo uma única vez (dense + sparse)"""
        documents = self._load_composition_documents(workbook_path, limit)
        # ASCII folding: normaliza o page_content para que o BM25 tokenize
        # sem acentos (ex: SIFÃO → SIFAO), garantindo match accent-insensitive.
        for doc in documents:
            doc.page_content = ascii_fold(doc.page_content)
        vector_store = self._build_vector_store(RetrievalMode.HYBRID)
        ids = [str(uuid4()) for _ in documents]
        vector_store.add_documents(documents=documents, ids=ids)
        print(f"{len(documents)} documentos indexados com sucesso.")

    def _build_metadata_filter(
        self,
        filters: Optional[Sequence[Union[Tuple[str, str], dict]]],
    ) -> Optional[models.Filter]:
        """Converte uma lista de pares key/value em Filter must+MatchValue."""
        if not filters:
            return None

        conditions = []
        for item in filters:
            if isinstance(item, dict):
                key = item.get("key")
                value = item.get("value")
            else:
                try:
                    key, value = item
                except ValueError:
                    continue

            if not key or value is None:
                continue

            conditions.append(
                models.FieldCondition(
                    key=self._normalize_metadata_key(key),
                    match=models.MatchValue(value=value),
                )
            )

        if not conditions:
            return None
        return models.Filter(must=conditions)

    @staticmethod
    def _normalize_metadata_key(key: str) -> str:
        """Garante que filtros façam referência ao namespace `metadata.*`."""
        clean_key = (key or "").strip()
        if not clean_key or clean_key.startswith("metadata."):
            return clean_key
        return f"metadata.{clean_key}"

    @staticmethod
    def _extract_payload_value(payload: dict, field: str):
        """Busca o valor em caminhos diretos ou dentro de `metadata.*`."""
        if not field:
            return None

        direct_path = field.split(".") if "." in field else [field]
        candidate_paths = [direct_path]

        if direct_path[0] != "metadata":
            candidate_paths.append(["metadata", *direct_path])

        for path in candidate_paths:
            current = payload
            for part in path:
                if not isinstance(current, dict):
                    current = None
                    break
                current = current.get(part)
                if current is None:
                    break
            if current is not None:
                return current
        return None

    @staticmethod
    def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
        """Calcula similaridade de cosseno entre dois vetores densos."""
        if len(vec_a) != len(vec_b):
            raise ValueError("Os vetores precisam ter o mesmo tamanho para comparar.")

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sqrt(sum(a * a for a in vec_a))
        norm_b = sqrt(sum(b * b for b in vec_b))
        denom = norm_a * norm_b
        if denom == 0:
            return 0.0
        return dot_product / denom

    @staticmethod
    def _sparse_vector_to_dict(vector: object) -> dict:
        """Normaliza o formato do vetor esparso (FastEmbed retorna attrs)."""
        if vector is None:
            return {}
        if isinstance(vector, dict):
            return {int(k): float(v) for k, v in vector.items()}
        indices = getattr(vector, "indices", None)
        values = getattr(vector, "values", None)
        if indices is not None and values is not None:
            return {int(i): float(v) for i, v in zip(indices, values)}
        # fallback: tenta tratar como tupla/lista de pares
        try:
            return {int(i): float(v) for i, v in vector}
        except Exception:
            return {}

    def _sparse_cosine(self, vec_a: object, vec_b: object) -> float:
        """Calcula similaridade de cosseno entre vetores esparsos (dict idx->peso)."""
        a = self._sparse_vector_to_dict(vec_a)
        b = self._sparse_vector_to_dict(vec_b)
        if not a or not b:
            return 0.0

        dot = sum(weight * b.get(idx, 0.0) for idx, weight in a.items())
        norm_a = sqrt(sum(weight * weight for weight in a.values()))
        norm_b = sqrt(sum(weight * weight for weight in b.values()))
        denom = norm_a * norm_b
        if denom == 0:
            return 0.0
        return dot / denom

    def embed_text(self, text: str) -> List[float]:
        """Gera embedding denso usando a config atual (mesmo modelo da coleção)."""
        if not text or not text.strip():
            raise ValueError("Forneça um texto não vazio para gerar embedding.")
        vector = self.dense_embeddings.embed_query(text.strip())
        return list(vector)

    def semantic_similarity(self, text_a: str, text_b: str) -> float:
        """Retorna a similaridade de cosseno entre dois textos sem usar o Qdrant."""
        vec_a = self.embed_text(text_a)
        vec_b = self.embed_text(text_b)
        return self._cosine_similarity(vec_a, vec_b)

    def sparse_similarity(self, text_a: str, text_b: str) -> float:
        """Similaridade lexical (BM25/FastEmbed) sem tocar o Qdrant."""
        if not text_a or not text_b:
            raise ValueError("Forneça textos não vazios para comparar.")
        sparse_a = self.sparse_embeddings.embed_query(ascii_fold(text_a.strip()))
        sparse_b = self.sparse_embeddings.embed_query(ascii_fold(text_b.strip()))
        return self._sparse_cosine(sparse_a, sparse_b)

    def hybrid_similarity(self, text_a: str, text_b: str, alpha: float = 0.5) -> float:
        """
        Combina similaridades densa e esparsa.

        alpha=1 usa apenas denso; alpha=0 apenas lexical; valores intermediários
        mimetizam o balanceamento híbrido padrão (soma ponderada).
        """
        if not 0 <= alpha <= 1:
            raise ValueError("alpha deve estar entre 0 e 1.")
        dense = self.semantic_similarity(text_a, text_b)
        sparse = self.sparse_similarity(text_a, text_b)
        return alpha * dense + (1 - alpha) * sparse

    def similarity_search(
        self,
        query: str,
        k: int = 3,
        mode: str = "hybrid",
        metadata_filters: Optional[Sequence[Union[Tuple[str, str], dict]]] = None,
        deduplicate: bool = True,
        seen_codes: Optional[Set[str]] = None,
    ):
        """Busca com o modo desejado: dense | sparse | hybrid.

        Args:
            deduplicate: Remove duplicatas por código SINAPI. Busca 2*k
                         candidatos e retorna até k únicos.
            seen_codes:  Set externo de códigos já vistos (para dedup
                         cross-search em pipelines agentic). Se fornecido,
                         é atualizado in-place com os novos códigos.
        """
        retrieval_map = {
            "dense": RetrievalMode.DENSE,
            "sparse": RetrievalMode.SPARSE,
            "hybrid": RetrievalMode.HYBRID,
        }

        mode_enum = retrieval_map.get(mode.lower())
        if mode_enum is None:
            raise ValueError("Modo inválido. Use: dense, sparse ou hybrid.")

        vector_store = self._build_vector_store(mode_enum)
        filter_object = self._build_metadata_filter(metadata_filters)

        fetch_k = k * 2 if deduplicate else k
        # ASCII folding na query para match accent-insensitive no BM25
        folded_query = ascii_fold(query)
        results = vector_store.similarity_search(
            query=folded_query,
            k=fetch_k,
            filter=filter_object,
        )

        if deduplicate:
            results, _ = deduplicate_documents(
                results, limit=k, seen_codes=seen_codes
            )

        return results

    def list_distinct_metadata(
        self, field: str, *, limit: Optional[int] = None, page_size: int = 128
    ) -> List[str]:
        """Percorre a coleção e retorna valores distintos de um campo de metadata."""
        seen: Set[str] = set()
        collected: List[str] = []
        offset = None

        while True:
            records, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=page_size,
                with_payload=True,
                with_vectors=False,
                offset=offset,
            )

            for record in records:
                payload = record.payload or {}
                value = self._extract_payload_value(payload, field)
                if not value:
                    continue
                text_value = str(value).strip()
                if not text_value or text_value in seen:
                    continue
                seen.add(text_value)
                collected.append(text_value)
                if limit is not None and len(collected) >= limit:
                    return sorted(collected)

            if offset is None:
                break

        return sorted(collected)


if __name__ == "__main__":
    workbook_path = Path(
        "docs/SINAPI_Custo_Ref_Composicoes_Analitico_AL_202412_Desonerado.xlsx"
    )
    sinapi = QdrantSinapi(
        dense_provider="ollama",
        dense_model="qwen3-embedding:0.6b",
        dense_size=1024,
    )
    # sinapi.create_collection()
    # sinapi.add_compositions(workbook_path)

    sinapi.similarity_search(
        "alvenaria",
        mode="dense",
    )
