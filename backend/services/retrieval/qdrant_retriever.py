"""Qdrant-backed retriever (role B, owner: Zainab). Plain Python, no Django imports."""

import asyncio
import os

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qdrant_models
except ModuleNotFoundError as exc:
    _QDRANT_IMPORT_ERROR = exc

    class QdrantClient:  # type: ignore[no-redef]
        _missing_dependency = True

        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError(
                "qdrant-client is required to use QdrantRetriever."
            ) from _QDRANT_IMPORT_ERROR

    class _QdrantModelsFallback:
        class MatchValue:
            def __init__(self, *, value):
                self.value = value

        class FieldCondition:
            def __init__(self, *, key, match):
                self.key = key
                self.match = match

        class Filter:
            def __init__(self, *, must=None, should=None):
                self.must = must
                self.should = should

    qdrant_models = _QdrantModelsFallback()

try:
    from sentence_transformers import SentenceTransformer
except ModuleNotFoundError as exc:
    _SENTENCE_TRANSFORMERS_IMPORT_ERROR = exc

    class SentenceTransformer:  # type: ignore[no-redef]
        _missing_dependency = True

        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError(
                "sentence-transformers is required to use QdrantRetriever."
            ) from _SENTENCE_TRANSFORMERS_IMPORT_ERROR


from ..types import Passage, ServiceNotReady


class QdrantRetriever:
    """Retriever over the chunks in Qdrant."""

    def __init__(
        self,
        collection_name: str = "sahkar_saathi_chunks",
        model: SentenceTransformer | None = None,
        client: QdrantClient | None = None,
        score_threshold: float | None = None,
        score_threshold_by_lang: dict[str, float] | None = None,
    ):
        self.collection_name = collection_name
        self._model = model
        self._client = client
        self.score_threshold = score_threshold
        self.score_threshold_by_lang = score_threshold_by_lang or {}

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            if getattr(SentenceTransformer, "_missing_dependency", False) is True:
                raise ServiceNotReady(
                    "The retriever is unavailable. Set USE_STUB_RETRIEVER=true to use the stub."
                )
            model_name = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
            self._model = SentenceTransformer(model_name)
        return self._model

    @model.setter
    def model(self, value: SentenceTransformer) -> None:
        self._model = value

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            if getattr(QdrantClient, "_missing_dependency", False) is True:
                raise ServiceNotReady(
                    "The retriever is unavailable. Set USE_STUB_RETRIEVER=true to use the stub."
                )
            qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
            self._client = QdrantClient(url=qdrant_url)
        return self._client

    @client.setter
    def client(self, value: QdrantClient) -> None:
        self._client = value

    async def search(
        self,
        query: str,
        *,
        state: str | None,
        language: str | None = None,
        top_k: int = 4,
        document_id: str | None = None,
        score_threshold: float | None = None,
    ) -> list[Passage]:
        # 1. Prefix query with "query: " for multilingual-e5
        formatted_query = f"query: {query}"

        # Offload CPU-bound model encoding to thread
        raw_vector = await asyncio.to_thread(self.model.encode, formatted_query)
        query_vector = raw_vector.tolist() if hasattr(raw_vector, "tolist") else list(raw_vector)

        # 2. Build Qdrant filter conditions
        must_conditions = []

        # State filtering:
        # If state is provided: match state == user_state OR state == "central"
        # If state is None/empty: match state == "central"
        if state:
            must_conditions.append(
                qdrant_models.Filter(
                    should=[
                        qdrant_models.FieldCondition(
                            key="state",
                            match=qdrant_models.MatchValue(value=state),
                        ),
                        qdrant_models.FieldCondition(
                            key="state",
                            match=qdrant_models.MatchValue(value="central"),
                        ),
                    ]
                )
            )
        else:
            must_conditions.append(
                qdrant_models.FieldCondition(
                    key="state",
                    match=qdrant_models.MatchValue(value="central"),
                )
            )

        # Language filtering: Do NOT filter by language tag since the corpus is in English

        # Document ID filtering if given ("Ask about this document")
        if document_id:
            must_conditions.append(
                qdrant_models.FieldCondition(
                    key="doc_id",
                    match=qdrant_models.MatchValue(value=document_id),
                )
            )

        query_filter = qdrant_models.Filter(must=must_conditions) if must_conditions else None

        # Determine threshold by language if configured
        effective_threshold = score_threshold
        if effective_threshold is None and language and self.score_threshold_by_lang:
            effective_threshold = self.score_threshold_by_lang.get(language, self.score_threshold)
        elif effective_threshold is None:
            effective_threshold = self.score_threshold

        query_kwargs = {
            "collection_name": self.collection_name,
            "query": query_vector,
            "query_filter": query_filter,
            "limit": top_k,
        }
        if effective_threshold is not None:
            query_kwargs["score_threshold"] = effective_threshold

        # 3. Perform similarity search in Qdrant using query_points (offload I/O call to thread)
        try:
            response = await asyncio.to_thread(
                self.client.query_points,
                **query_kwargs,
            )
        except Exception as exc:
            raise ServiceNotReady(
                "The retriever is unavailable. Start Qdrant or set USE_STUB_RETRIEVER=true."
            ) from exc
        search_results = response.points

        # 4. Map Qdrant hits into Passage objects
        passages = []
        for hit in search_results:
            payload = hit.payload or {}
            passages.append(
                Passage(
                    chunk_id=str(hit.id),
                    text=payload.get("text", ""),
                    document_id=payload.get("doc_id", ""),
                    document_title=payload.get("document_title", "Unknown Title"),
                    publisher=payload.get("publisher", "Unknown Publisher"),
                    source_url=payload.get("source_url"),
                    published_date=payload.get("published_date"),
                    page=payload.get("page"),
                    score=float(hit.score),
                    state=payload.get("state"),
                )
            )

        return passages
