"""Speech-to-text evaluation helpers (role C). Plain Python, no Django imports.

``normalize`` and ``error_rate`` score a transcript against a typed reference. ``run_evals``
transcribes recordings you already have and prints the error rate for each one. Nothing is
stored: no audio and no transcripts are written anywhere.
"""

import asyncio
import inspect
import unicodedata
from pathlib import Path

# Apostrophes are dropped, not turned into spaces, so "don't" stays one word.
_APOSTROPHES = {"'", "’", "ʼ"}


def normalize(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace, strip.

    Punctuation is any Unicode punctuation character, so it covers "?" and the Devanagari
    danda "।" alike. Letters, digits and combining marks (vowel signs, nukta, virama, pulli)
    are kept, so Hindi and Tamil words are never altered. The text is also put in a standard
    Unicode form (NFKC), so the same word typed in two ways compares equal.
    """
    text = unicodedata.normalize("NFKC", text).lower()
    kept = []
    for char in text:
        if char in _APOSTROPHES:
            continue
        kept.append(" " if unicodedata.category(char).startswith("P") else char)
    return " ".join("".join(kept).split())


def _edit_distance(a: list, b: list) -> int:
    """Smallest number of insertions, deletions and substitutions that turn a into b."""
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, start=1):
        current = [i]
        for j, y in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def error_rate(reference: str, hypothesis: str, mode: str = "word") -> float:
    """Error rate of ``hypothesis`` against ``reference``, on normalised text.

    ``mode="word"`` (the default) is the word error rate: word-level edit distance divided by
    the number of reference words. ``mode="char"`` is the character error rate: the same on
    characters, with spaces ignored (Unicode code points, so a Hindi or Tamil letter with its
    vowel sign counts as more than one character). 0.0 is a perfect match. The rate can exceed
    1.0 when the hypothesis has many extra words. An empty reference gives 0.0 if the
    hypothesis is empty too, and 1.0 otherwise, since there is nothing to divide by.
    """
    if mode == "word":
        ref, hyp = normalize(reference).split(), normalize(hypothesis).split()
    elif mode == "char":
        ref = list(normalize(reference).replace(" ", ""))
        hyp = list(normalize(hypothesis).replace(" ", ""))
    else:
        raise ValueError(f"mode must be 'word' or 'char', not {mode!r}")
    if not ref:
        return 0.0 if not hyp else 1.0
    return _edit_distance(ref, hyp) / len(ref)


def _accepts(function, name: str) -> bool:
    """Whether ``function`` can be called with the keyword argument ``name``."""
    try:
        parameters = inspect.signature(function).parameters
    except (TypeError, ValueError):
        return True  # cannot tell, so keep the original call
    return name in parameters or any(p.kind is p.VAR_KEYWORD for p in parameters.values())


async def run_evals(test_cases, provider):
    """Transcribe each ``(file_path, ground_truth_text, language)`` and print the result.

    When a ground truth is given, the word and character error rates are printed too.
    Recordings that are not found are skipped.
    """
    # WhisperSpeechProvider takes no such argument (WHISPER_USE_PROMPT switches its domain
    # prompt on instead), so only pass it to providers that accept it.
    extra = (
        {"use_vocabulary_hint": True}
        if _accepts(provider.transcribe, "use_vocabulary_hint")
        else {}
    )
    for file_path, gt_text, lang in test_cases:
        path = Path(file_path)
        if not await asyncio.to_thread(path.exists):
            print(f"Skipping {file_path} (File not found)")
            continue

        audio_bytes = await asyncio.to_thread(path.read_bytes)
        result = await provider.transcribe(
            audio_bytes, content_type="audio/m4a", language_hint=lang, **extra
        )
        print(
            f"\nFile: {path.name} | Language: {result.language} "
            f"| Confidence: {result.confidence:.2f}"
        )
        print(f"Ground Truth: {gt_text}")
        if gt_text:
            wer = error_rate(gt_text, result.text, "word")
            cer = error_rate(gt_text, result.text, "char")
            print(f"Word error rate: {wer:.1%} | Character error rate: {cer:.1%}")
