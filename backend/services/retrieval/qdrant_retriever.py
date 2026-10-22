"""Qdrant-backed retriever (role B, owner: Zainab). Plain Python, no Django imports.

A skeleton: it satisfies the Retriever Protocol in services/types.py so the wiring in
config/services.py is final. Turning it on is one step, USE_STUB_RETRIEVER=false, once
search() is implemented.
"""

from ..types import Passage, ServiceNotReady


class QdrantRetriever:
    """Retriever over the chunks in Qdrant.

    ``search`` must return up to ``top_k`` ``Passage`` objects, best first:
    - filtered by ``state`` (the state's documents plus central ones; central only when
      ``state`` is None) and by ``language`` when given,
    - limited to one document when ``document_id`` is given,
    - only active documents (retired versions are never cited),
    - each with ``score`` on the same scale as ``SCORE_THRESHOLD`` (higher is better),
      because the answer service declines when the best score is below it.
    """

    async def search(
        self,
        query: str,
        *,
        state: str | None,
        language: str | None,
        top_k: int = 4,
        document_id: str | None = None,
    ) -> list[Passage]:
        raise ServiceNotReady("The retriever is not implemented yet (owner: Zainab).")
