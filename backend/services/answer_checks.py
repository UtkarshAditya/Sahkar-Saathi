"""Cheap checks on a generated answer (role C). Plain Python, no Django imports."""

import re
import unicodedata


def normalize_text(text: str) -> str:
    """Lower-case, drop punctuation and symbols, tidy spaces.

    Combining marks (Hindi and Tamil vowel signs) are kept, so words stay intact.
    """
    text = unicodedata.normalize("NFC", text).lower()
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith(("P", "S")))
    return " ".join(text.split())


def _longest_shared_run(a: list[str], b: list[str]) -> int:
    """Length of the longest run of words that appears, in order, in both lists."""
    best = 0
    previous = [0] * (len(b) + 1)
    for x in a:
        current = [0]
        for j, y in enumerate(b, start=1):
            current.append(previous[j - 1] + 1 if x == y else 0)
            best = max(best, current[j])
        previous = current
    return best


def repeats_question(
    question: str, answer: str, min_words: int = 4, min_fraction: float = 0.8
) -> bool:
    """True if the answer copies most of the question word for word.

    Small models sometimes echo the question back as the "answer". A real answer may
    reuse a few of the question's words, but it rarely contains most of the question
    as one unbroken run. Very short questions are never flagged, because a short
    question can appear inside a perfectly good answer.

    Limit: this catches copying, not other kinds of empty or wrong answers.
    """
    q_words = normalize_text(question).split()
    if len(q_words) < min_words:
        return False
    a_words = normalize_text(answer).split()
    return _longest_shared_run(q_words, a_words) >= min_fraction * len(q_words)


def numbers_in(text: str) -> set[str]:
    """Every run of digits in the text, as plain 0-9 digits (Hindi and Tamil digits included)."""
    ascii_text = "".join(str(unicodedata.decimal(ch)) if ch.isdecimal() else ch for ch in text)
    return set(re.findall(r"\d+", ascii_text))


def unsupported_numbers(answer: str, sources: list[str], question: str = "") -> set[str]:
    """Numbers that appear in the answer but in none of the sources (or the question).

    The prompt tells the model to copy numbers, dates and deadlines exactly. This checks
    it did. It catches an invented or altered number. It does not catch a real number
    applied to the wrong situation.
    """
    allowed: set[str] = numbers_in(question)
    for source in sources:
        allowed |= numbers_in(source)
    return numbers_in(answer) - allowed
