"""Answer common PMFBY questions straight from verified facts (role C).

Plain Python, no Django imports. It reads backend/data/schemes.yaml and answers only from
the PMFBY fact whose id is "loss" when that fact is no longer a placeholder: is_placeholder
is false and it has a real source_url and as_of date, the same rule apps/schemes enforces.
A question it cannot match, or a fact that is still a placeholder, goes on to the normal
answer service.

English comes from the fact's own `body`. Hindi and Tamil come from
services/data/fastpath_text.yaml and are shown only once a fluent reader has set
`reviewed: true`; until then the English text is used.

Use it by wrapping the real service where the services are created:

    service = FastPathAnswerService(GroundedAnswerService(...), SchemeFastPath.from_files(...))
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

SCHEME_SLUG = "pmfby"
FACT_ID = "loss"


def _usable(value) -> bool:
    return value is not None and str(value).strip() not in ("", "TODO", "None")


def load_verified_fact(path: str | Path, slug: str = SCHEME_SLUG, fact_id: str = FACT_ID):
    """Return the fact (with its scheme under "_scheme"), or None if it is not verified."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    entries = data.get("schemes", []) if isinstance(data, dict) else data
    for entry in entries:
        if entry.get("slug") != slug and entry.get("id") != slug:
            continue
        for fact in entry.get("facts") or []:
            if fact.get("id") != fact_id:
                continue
            if (
                fact.get("is_placeholder") is False
                and _usable(fact.get("source_url"))
                and _usable(fact.get("as_of"))
                and _usable(fact.get("body"))
            ):
                return {**fact, "_scheme": entry}
            logger.info("Fast path off: fact %s is still a placeholder or has no source", fact_id)
    return None


def load_translations(path: str | Path | None) -> dict:
    """Read fastpath_text.yaml: {fact id: {language: {text, reviewed}}}. Missing file is fine."""
    if path is None or not Path(path).exists():
        return {}
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


class SchemeFastPath:
    """Matches a question to the verified fact and builds the answer from it."""

    def __init__(self, fact: dict | None, translations: dict | None = None) -> None:
        self.fact = fact
        self.translations = translations or {}

    @classmethod
    def from_files(cls, schemes_path, translations_path=None) -> "SchemeFastPath":
        return cls(load_verified_fact(schemes_path), load_translations(translations_path))

    @property
    def active(self) -> bool:
        return self.fact is not None

    @staticmethod
    def matches(question: str) -> bool:
        q = normalize_text(question)
        groups = (_CROP_OR_INSURANCE, _LOSS, _REPORT)
        return all(any(word in q for word in group) for group in groups)

    def _text_for(self, language: str) -> tuple[str, str]:
        """The text to show and its language: reviewed translation, else the English body."""
        if language != "en":
            entry = (self.translations.get(FACT_ID) or {}).get(language) or {}
            if entry.get("reviewed") is True and _usable(entry.get("text")):
                return str(entry["text"]).strip(), language
        return " ".join(str(self.fact["body"]).split()), "en"

    def answer(self, question: str, language: str) -> Answer | None:
        if self.fact is None or not self.matches(question):
            return None
        text, text_language = self._text_for(language)
        scheme = self.fact["_scheme"]
        slug = scheme.get("slug") or scheme.get("id") or SCHEME_SLUG
        source = Passage(
            chunk_id=f"schemes:{slug}:{self.fact['id']}",
            text=" ".join(str(self.fact["body"]).split()),
            document_id=f"schemes.yaml:{slug}",
            document_title=f"{scheme.get('title', 'Scheme')} (verified fact)",
            publisher=str(self.fact.get("source_label") or "Government of India"),
            source_url=str(self.fact["source_url"]),
            published_date=str(self.fact["as_of"]),
            page=None,
            score=1.0,
            state=None,
        )
        return Answer(
            text=text,
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
