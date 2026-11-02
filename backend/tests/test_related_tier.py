"""The related-answer tier: between a confident answer and a decline. Off by default.

The LLM is faked by replacing services.answer.generate; the retriever is scripted. No
network, no model, no Qdrant.
"""

import asyncio
import io
import json

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.chat import api as chat_api
from apps.chat.models import Message
from apps.knowledge.management.commands import eval_retrieval as eval_module
from apps.knowledge.management.commands.eval_retrieval import answer_tier
from config import services
from services import answer as answer_module
from services.answer import (
    DECLINE_TEXT,
    RELATED_LEAD_TEXT,
    GroundedAnswerService,
    build_related_text,
    shorten_at_sentence,
)
from services.types import Answer, Passage

from .test_eval_tools import FakeRetriever, question, write_questions

MAIN = 0.82
RELATED = 0.75
LONG = (
    "A member may complain to the Cooperative Ombudsman about deposits. "
    "The complaint is filed in Form VI under rule 30H(2). "
    "The Ombudsman decides it within three months of receiving all the documents needed. "
    "An appeal lies to the Appellate Authority within one month of the decision. "
    "The society must comply with the decision within the time the Ombudsman sets."
)


def passage(n: int, score: float, text: str = LONG, page: int | None = 4) -> Passage:
    return Passage(
        chunk_id=f"c{n}",
        text=text,
        document_id=f"DOC-{n}",
        document_title=f"Document {n}",
        publisher="P",
        source_url=None,
        published_date="2026-01-01",
        page=page,
        score=score,
        state=None,
    )


class ScriptedRetriever:
    def __init__(self, *passages: Passage):
        self.passages = list(passages)

    async def search(self, query, *, state, language, top_k=4, document_id=None):
        return self.passages[:top_k]


@pytest.fixture
def llm(monkeypatch):
    """Records every LLM call; replies with a valid answer citing passage 1."""
    calls: list[str] = []

    async def fake_generate(system, user, json_mode=True, temperature=0.0):
        calls.append(user)
        return json.dumps(
            {"status": "answered", "answer_text": "File a complaint.", "cited_ids": [1]}
        )

    monkeypatch.setattr(answer_module, "generate", fake_generate)
    return calls


def service(*passages, related=RELATED, by_lang=None, **kwargs) -> GroundedAnswerService:
    return GroundedAnswerService(
        ScriptedRetriever(*passages),
        min_score=MAIN,
        related_min_score=related,
        related_min_score_by_lang=by_lang,
        **kwargs,
    )


def ask(svc, language="en") -> Answer:
    return asyncio.run(svc.ask("How do I complain?", language=language, state=None))


# --- The tiers ------------------------------------------------------------------------


def test_above_the_main_threshold_is_the_normal_answer(llm):
    answer = ask(service(passage(1, 0.90), passage(2, 0.78)))
    assert len(llm) == 1
    assert answer.status == "answered" and answer.confidence == "high"
    assert answer.text == "File a complaint."


def test_between_the_thresholds_is_a_related_answer_without_the_llm(llm):
    answer = ask(service(passage(1, 0.80), passage(2, 0.77), passage(3, 0.76)))
    assert llm == []  # the LLM is never called
    assert answer.status == "answered" and answer.confidence == "related"
    assert answer.top_score == 0.80 and answer.model == "" and answer.contact is None
    assert [c.chunk_id for c in answer.citations] == ["c1", "c2"]  # RELATED_MAX_PASSAGES=2
    assert answer.text.startswith(RELATED_LEAD_TEXT["en"])
    assert "(Document 1, p. 4)" in answer.text and "(Document 2, p. 4)" in answer.text
    assert "Document 3" not in answer.text


def test_a_related_answer_quotes_only_passages_above_the_related_threshold(llm):
    answer = ask(service(passage(1, 0.79), passage(2, 0.40)))
    assert [c.chunk_id for c in answer.citations] == ["c1"]
    assert "Document 2" not in answer.text


def test_below_the_related_threshold_is_declined(llm):
    answer = ask(service(passage(1, 0.70)))
    assert llm == []
    assert answer.status == "declined" and answer.text == DECLINE_TEXT["en"]
    assert answer.citations == [] and answer.top_score == 0.70 and answer.confidence == "high"


def test_no_passages_at_all_is_declined(llm):
    assert ask(service()).status == "declined"


@pytest.mark.parametrize("score", [0.95, 0.80, 0.70])
def test_with_the_tier_off_every_score_behaves_exactly_as_before(llm, score):
    passages = (passage(1, score), passage(2, score - 0.01))
    off = ask(service(*passages, related=None))
    before = ask(GroundedAnswerService(ScriptedRetriever(*passages), min_score=MAIN))
    assert off == before
    assert off.confidence == "high"
    if score < MAIN:
        assert off.status == "declined"


def test_per_language_related_thresholds(llm):
    svc = service(passage(1, 0.78), related=None, by_lang={"hi": 0.70, "ta": 0.79})
    assert ask(svc, "hi").confidence == "related"
    assert ask(svc, "ta").status == "declined"  # 0.78 is below ta's related threshold
    assert ask(svc, "en").status == "declined"  # no related threshold for en: tier off


@pytest.mark.parametrize("language", ["en", "hi", "ta"])
def test_the_lead_line_is_in_the_question_language(llm, language):
    answer = ask(service(passage(1, 0.80)), language)
    assert answer.text.startswith(RELATED_LEAD_TEXT[language])
    assert answer.language == language


def test_related_max_passages(llm):
    passages = [passage(n, 0.80 - n / 100) for n in range(1, 4)]
    answer = ask(service(*passages, related_max_passages=3))
    assert len(answer.citations) == 3


def test_the_fast_path_still_comes_first(llm):
    class FastPath:
        def answer(self, text, language):
            return Answer(text="fast", status="answered", language=language)

    answer = ask(service(passage(1, 0.80), fast_path=FastPath()))
    assert answer.text == "fast" and answer.confidence == "high"


# --- The related text -----------------------------------------------------------------


def test_passages_are_shortened_at_a_sentence_boundary_and_kept_verbatim():
    short = shorten_at_sentence(LONG)
    assert len(short) <= 300 and short.endswith(".")
    assert LONG.startswith(short)
    assert shorten_at_sentence("Short text.") == "Short text."


def test_a_passage_without_a_sentence_end_is_cut_at_a_word():
    text = "word " * 100
    short = shorten_at_sentence(text)
    assert short.endswith("…") and len(short) <= 301 and "wor…" not in short


def test_a_passage_without_a_page_is_attributed_to_its_title_only():
    text = build_related_text([passage(1, 0.8, "A web page sentence.", page=None)], "en")
    assert text.endswith("“A web page sentence.” (Document 1)")


# --- Settings and wiring --------------------------------------------------------------


def test_the_tier_is_off_by_default():
    assert settings.SCORE_THRESHOLD_RELATED is None
    assert settings.SCORE_THRESHOLD_RELATED_BY_LANG == {}
    assert settings.RELATED_MAX_PASSAGES == 2


def test_the_settings_reach_the_answer_service(settings, tmp_path):
    settings.USE_STUB_ANSWER = False
    settings.USE_STUB_RETRIEVER = True
    settings.CONTENT_DIR = tmp_path  # no fast path: get_answer_service returns the service
    settings.SCORE_THRESHOLD_RELATED = 0.7
    settings.SCORE_THRESHOLD_RELATED_BY_LANG = {"en": 0.7, "hi": 0.65, "ta": 0.7}
    settings.RELATED_MAX_PASSAGES = 3
    services._answer_service.cache_clear()
    try:
        svc = services.get_answer_service()
    finally:
        services._answer_service.cache_clear()
    svc = getattr(svc, "inner", svc)
    assert isinstance(svc, GroundedAnswerService)
    assert svc.related_min_score == 0.7 and svc.related_min_score_by_lang["hi"] == 0.65
    assert svc.related_max_passages == 3
    assert svc.min_score == settings.SCORE_THRESHOLD  # the main thresholds are unchanged


# --- The API --------------------------------------------------------------------------


def related_answer() -> Answer:
    return Answer(
        text="I could not find an exact answer...",
        status="answered",
        language="en",
        citations=[passage(1, 0.8)],
        top_score=0.8,
        confidence="related",
    )


def test_normalise_keeps_related_citations_and_strips_declined_ones():
    kept = chat_api._normalise(related_answer())
    assert kept.confidence == "related" and len(kept.citations) == 1 and kept.contact is None

    declined = related_answer()
    declined.status = "declined"
    declined = chat_api._normalise(declined)
    assert declined.citations == [] and declined.contact is not None
    assert declined.confidence == "high"


def test_the_api_returns_and_stores_the_confidence(client, monkeypatch):
    class Service:
        async def ask(self, text, *, language, state, document_id=None):
            return related_answer()

    monkeypatch.setattr(chat_api, "get_answer_service", lambda: Service())
    res = client.post(
        "/api/v1/chat/ask",
        data=json.dumps({"text": "How do I complain?"}),
        content_type="application/json",
    )
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["status"] == "answered" and body["confidence"] == "related"
    assert [c["id"] for c in body["citations"]] == ["c1"] and body["contact"] is None
    assert body["citations"][0]["fetched_at"] is None
    message = Message.objects.get(pk=body["message_id"])
    assert message.confidence == "related" and message.citations.count() == 1


def test_a_normal_answer_is_high_confidence(client):
    res = client.post(
        "/api/v1/chat/ask",
        data=json.dumps({"text": "How do I complain?"}),
        content_type="application/json",
    )
    assert res.json()["confidence"] == "high"


def test_the_schema_requires_confidence_high_or_related():
    schema = json.loads((settings.BASE_DIR / "openapi.json").read_text(encoding="utf-8"))
    ask_out = schema["components"]["schemas"]["AskOut"]
    assert "confidence" in ask_out["required"]
    assert ask_out["properties"]["confidence"]["enum"] == ["high", "related"]
    citation = schema["components"]["schemas"]["CitationOut"]["properties"]
    assert "fetched_at" in citation


def test_messages_default_to_high_confidence():
    from apps.chat.models import Conversation

    message = Message.objects.create(
        conversation=Conversation.objects.create(), language="en", status="answered", latency_ms=1
    )
    assert message.confidence == "high"


def test_no_migration_is_missing():
    call_command("makemigrations", "--check", "--dry-run", stdout=io.StringIO())


def test_the_quality_summary_counts_answers_per_tier(client):
    from apps.chat.models import Conversation

    conversation = Conversation.objects.create()
    for status, confidence, needs_state in (
        ("answered", "high", False),
        ("answered", "high", False),
        ("partial", "high", False),
        ("answered", "related", False),
        ("declined", "high", False),
        ("answered", "high", True),  # a state prompt: in the total only
    ):
        Message.objects.create(
            conversation=conversation,
            language="en",
            status=status,
            confidence=confidence,
            needs_state=needs_state,
            latency_ms=1,
        )
    user = get_user_model().objects.create_user("staff", password="pw-for-tests", is_staff=True)
    client.force_login(user)
    tiers = client.get("/api/v1/eval/latest").json()["answer_tiers"]
    assert tiers == {"confident": 3, "related": 1, "declined": 1, "total": 6}


# --- eval_retrieval tier report -------------------------------------------------------


def test_answer_tier_matches_the_answer_service():
    assert answer_tier(0.9, 0.82, 0.75) == "confident"
    assert answer_tier(0.82, 0.82, 0.75) == "confident"
    assert answer_tier(0.75, 0.82, 0.75) == "related"
    assert answer_tier(0.74, 0.82, 0.75) == "decline"
    assert answer_tier(0.80, 0.82, None) == "decline"
    assert answer_tier(None, 0.82, 0.75) == "decline"


def run_eval(monkeypatch, tmp_path, *args) -> str:
    questions = [
        question("in-confident", True),
        question("in-related", True),
        question("in-declined", True),
        question("out-declined", False),
        question("out-related", False),
    ]
    script = {
        "in-confident": (0.90, "DOC-A"),
        "in-related": (0.78, "DOC-A"),
        "in-declined": (0.60, "DOC-A"),
        "out-declined": (0.50, "DOC-B"),
        "out-related": (0.76, "DOC-B"),
    }
    fake = FakeRetriever(script, questions)
    monkeypatch.setattr(eval_module, "get_retriever", lambda: fake)
    monkeypatch.setattr(settings, "SCORE_THRESHOLD_BY_LANG", {"en": MAIN, "hi": MAIN, "ta": MAIN})
    out = io.StringIO()
    path = write_questions(tmp_path, questions)
    call_command("eval_retrieval", "--questions", str(path), *args, stdout=out)
    return out.getvalue()


def test_eval_retrieval_reports_the_tiers_for_a_related_threshold(monkeypatch, tmp_path):
    out = run_eval(monkeypatch, tmp_path, "--related-threshold", "0.75")
    report = out[out.index("Answer tiers") :]
    assert "  confident  1" in report
    assert "  related    2" in report
    assert "  decline    2" in report
    assert "In-scope questions that would still decline (1): in-declined" in report
    assert "Out-of-scope questions that would wrongly get an answer (1): out-related (related)" in (
        report
    )


def test_eval_retrieval_says_when_the_tier_is_off(monkeypatch, tmp_path):
    out = run_eval(monkeypatch, tmp_path)
    assert "the related tier is off" in out
    assert "SUGGESTED SCORE_THRESHOLD" in out  # the existing suggestion is still printed
