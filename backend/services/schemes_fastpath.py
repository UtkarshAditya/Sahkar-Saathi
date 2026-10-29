"""Answer common PMFBY questions straight from verified facts (role C).

Plain Python, no Django imports. It reads schemes.yaml (see data/schemes.pmfby.draft.yaml
for the layout) and answers only from facts marked `verified: true` that have a real
source URL and date. A question it cannot match goes on to the normal answer service.

Use it by wrapping the real service where the services are created:

    service = FastPathAnswerService(GroundedAnswerService(...), SchemeFastPath.from_file(path))
"""

import logging
from pathlib import Path

import yaml

from .answer_checks import normalize_text
from .types import Answer, Passage

logger = logging.getLogger(__name__)

# A question matches when it has a word from EACH group below. Words are matched inside the
# normalized question, so word endings do not matter. Whisper sometimes spells "crop" in
# Tamil as பையிர், so both spellings are listed. Add words here as you see real questions.
_CROP_OR_INSURANCE = (
    "crop", "pmfby", "insurance", "fasal bima",
    "फसल", "बीमा", "पीएमएफबीवाई",
    "பயிர்", "பையிர்", "காப்பீடு",
)  # fmt: skip
_LOSS = (
    "loss", "damage", "destroyed", "ruined",
    "नुकसान", "खराब", "बर्बाद",
    "இழப்", "சேதம்", "பாதிப்",
)  # fmt: skip
_REPORT = (
    "report", "intimate", "inform", "notify", "claim", "deadline", "within", "when",
    "what should i do", "what to do",
    "सूचना", "सूचित", "बताना", "दावा", "कब", "क्या करना",
    "தெரிவி", "எப்போது", "புகார்", "என்ன செய்ய",
)  # fmt: skip

FACT_ID = "loss-report-window"


def _usable(value) -> bool:
    return value is not None and str(value).strip() not in ("", "TODO")


def load_verified_facts(path: str | Path) -> list[dict]:
    """Return the verified, sourced facts from schemes.yaml, each with its scheme attached."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    entries = data.get("schemes", []) if isinstance(data, dict) else data
    facts = []
    for entry in entries:
        for fact in entry.get("facts") or []:
            if (
                fact.get("verified") is True
                and _usable(fact.get("source_url"))
                and _usable(fact.get("as_of"))
            ):
                facts.append({**fact, "_scheme": entry})
            else:
                logger.info("Fast path skips unverified fact %s", fact.get("id"))
    return facts


class SchemeFastPath:
    """Matches a question to a verified fact and builds the answer from it."""

    def __init__(self, facts: list[dict], fallback_to_english: bool = True) -> None:
        self.facts = {f["id"]: f for f in facts}
        # If there is no reviewed text in the user's language, answer in English
        # (a verified English fact beats a decline). Set False to fall through instead.
        self.fallback_to_english = fallback_to_english

    @classmethod
    def from_file(cls, path: str | Path, **kwargs) -> "SchemeFastPath":
        return cls(load_verified_facts(path), **kwargs)

    @staticmethod
    def matches(question: str) -> bool:
        q = normalize_text(question)
        return all(
            any(word in q for word in group) for group in (_CROP_OR_INSURANCE, _LOSS, _REPORT)
        )

    def _text_for(self, fact: dict, language: str) -> tuple[str, str] | None:
        """Return (text, language of that text), or None if there is nothing safe to say."""
        texts = fact.get("answer") or {}
        reviewed = fact.get("answer_reviewed") or {}
        if language == "en" and texts.get("en"):
            return texts["en"], "en"
        if language != "en" and texts.get(language) and reviewed.get(language) is True:
            return texts[language], language
        if self.fallback_to_english and texts.get("en"):
            return texts["en"], "en"
        return None

    def answer(self, question: str, language: str) -> Answer | None:
        fact = self.facts.get(FACT_ID)
        if fact is None or not self.matches(question):
            return None
        chosen = self._text_for(fact, language)
        if chosen is None:
            return None
        text, text_language = chosen
        scheme = fact["_scheme"]
        source = Passage(
            chunk_id=f"schemes:{scheme.get('slug', 'scheme')}:{fact['id']}",
            text=str(fact.get("value", "")).strip(),
            document_id=f"schemes.yaml:{scheme.get('slug', 'scheme')}",
            document_title=f"{scheme.get('title', 'Scheme')} (verified fact)",
            publisher=str(fact.get("publisher", "Government of India")),
            source_url=str(fact["source_url"]),
            published_date=str(fact["as_of"]),
            page=fact.get("page") if isinstance(fact.get("page"), int) else None,
            score=1.0,
            state=None,
            section=fact["id"],
        )
        return Answer(
            text=text.strip(),
            status="answered",
            language=text_language,
            citations=[source],
            model="schemes.yaml",
            top_score=1.0,
        )


class FastPathAnswerService:
    """Tries the fast path first, then hands everything else to the real answer service."""

    def __init__(self, inner, fast_path: SchemeFastPath) -> None:
        self.inner = inner
        self.fast_path = fast_path

    async def ask(
        self, text: str, *, language: str, state: str | None, document_id: str | None = None
    ) -> Answer:
        # "Ask about this document" must stay limited to that document, so skip the fast path.
        if document_id is None:
            result = self.fast_path.answer(text, language)
            if result is not None:
                return result
        return await self.inner.ask(text, language=language, state=state, document_id=document_id)
