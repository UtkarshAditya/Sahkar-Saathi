"""Qdrant-backed retriever (role B, owner: Zainab). Plain Python, no Django imports.
"""

import os
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from ..types import Passage


class QdrantRetriever:
    """Retriever over the chunks in Qdrant."""

    def __init__(self, collection_name: str = "sahkar_saathi_chunks"):
        self.collection_name = collection_name
        model_name = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
        self.model = SentenceTransformer(model_name)
        
        qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
        self.client = QdrantClient(url=qdrant_url)

    async def search(
        self,
        query: str,
        *,
        state: str | None,
        language: str | None,
        top_k: int = 4,
        document_id: str | None = None,
    ) -> list[Passage]:
        # 1. Encode query into a vector
        query_vector = self.model.encode(query).tolist()

        # 2. Build Qdrant filter conditions
        must_conditions = []

        # State filtering: state's documents plus central ones (state is None)
        if state:
            must_conditions.append(
                qdrant_models.Condition(
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

        # Language filtering if given
        if language:
            must_conditions.append(
                qdrant_models.FieldCondition(
                    key="language",
                    match=qdrant_models.MatchValue(value=language),
                )
            )

        # Document ID filtering if given ("Ask about this document")
        if document_id:
            must_conditions.append(
                qdrant_models.FieldCondition(
                    key="doc_id",
                    match=qdrant_models.MatchValue(value=document_id),
                )
            )

        query_filter = qdrant_models.Filter(must=must_conditions) if must_conditions else None

        # 3. Perform similarity search in Qdrant using query_points
        response = self.client.query_points(
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