"""The score threshold is applied once, by the answer service, so a low top score is seen."""

import asyncio

import pytest

from config import services
from services.answer import DECLINE_TEXT, GroundedAnswerService
from services.retrieval.qdrant_retriever import QdrantRetriever
from services.types import Passage


def _passage(score: float) -> Passage:
    return Passage(
        chunk_id="c1",
        text="text",
        document_id="d1",
        document_title="Title",
        publisher="P",
        source_url=None,
        published_date="2026-01-01",
        page=1,
        score=score,
        state=None,
    )


class _WeakRetriever:
    async def search(self, query, *, state, language, top_k=4, document_id=None):
        return [_passage(0.5)]


def test_the_real_retriever_does_not_filter_by_score(settings):
    settings.USE_STUB_RETRIEVER = False
    services._retriever.cache_clear()
    try:
        retriever = services.get_retriever()
    finally:
        services._retriever.cache_clear()
    assert isinstance(retriever, QdrantRetriever)
    assert retriever.score_threshold is None and retriever.score_threshold_by_lang == {}


def test_the_per_language_thresholds_are_en_hi_ta_and_default_to_the_global_one():
    from django.conf import settings

    assert set(settings.SCORE_THRESHOLD_BY_LANG) == {"en", "hi", "ta"}


@pytest.mark.parametrize("language", ["en", "hi", "ta"])
def test_a_weak_best_hit_is_declined_in_the_question_language_with_the_real_score(language):
    service = GroundedAnswerService(
        _WeakRetriever(), min_score=0.3, min_score_by_lang={"en": 0.6, "hi": 0.6, "ta": 0.6}
    )
    answer = asyncio.run(service.ask("question", language=language, state=None))
    assert answer.status == "declined"
    assert answer.text == DECLINE_TEXT[language]
    assert answer.top_score == 0.5  # the decline reports the score, not None
