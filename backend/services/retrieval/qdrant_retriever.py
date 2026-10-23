"""Qdrant-backed retriever (role B, owner: Zainab). Plain Python, no Django imports."""

import asyncio
import os

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sentence_transformers import SentenceTransformer

from ..types import Passage


class QdrantRetriever:
    """Retriever over the chunks in Qdrant."""

    def __init__(
        self,
        collection_name: str = "sahkar_saathi_chunks",
        model: SentenceTransformer | None = None,
        client: QdrantClient | None = None,
    ):
        self.collection_name = collection_name
        self._model = model
        self._client = client

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            model_name = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
            self._model = SentenceTransformer(model_name)
        return self._model

    @model.setter
    def model(self, value: SentenceTransformer) -> None:
        self._model = value

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
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

        # 3. Perform similarity search in Qdrant using query_points (offload I/O call to thread)
        response = await asyncio.to_thread(
            self.client.query_points,
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
        )
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
