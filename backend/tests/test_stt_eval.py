"""services/speech/eval_stt.py: normalize, error_rate and run_evals. Pure Python; the provider
is a fake, so there is no model, no audio decoder and no network."""

import asyncio

import pytest

from services.speech.eval_stt import _accepts, error_rate, normalize, run_evals
from services.speech.whisper_provider import WhisperSpeechProvider
from services.types import Transcript

# --- normalize ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Hello,   WORLD!!  ", "hello world"),
        ("फसल बीमा कब? ।", "फसल बीमा कब"),
        ("पहला वाक्य। दूसरा वाक्य॥", "पहला वाक्य दूसरा वाक्य"),
        ("பயிர் காப்பீடு எப்போது?", "பயிர் காப்பீடு எப்போது"),
        ("multi-state society", "multi state society"),
        ("Don't stop; it’s fine.", "dont stop its fine"),
        ("a\tb\nc", "a b c"),
        ("", ""),
        ("?! । ,", ""),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_normalize_keeps_combining_marks_and_digits():
    for word in ("कि", "की", "क्या", "பயிர்", "கூட்டுறவு", "बीमा१२"):
        assert normalize(word) == word, "a letter, vowel sign, virama or digit was removed"
    assert normalize("कि") != normalize("क")


def test_normalize_gives_one_spelling_for_a_nukta_letter():
    assert normalize("क़") == normalize("क़")  # precomposed and decomposed क़


def test_normalize_is_idempotent():
    once = normalize("When should it be reported?  फसल बीमा कब? ।")
    assert normalize(once) == once


# --- error_rate -----------------------------------------------------------------------


def test_word_error_rate_is_the_default_mode():
    assert error_rate("a b c", "a x c") == pytest.approx(1 / 3)


def test_insertions_and_deletions_count():
    assert error_rate("a b c d", "a b c") == pytest.approx(1 / 4)  # one deletion
    assert error_rate("a b c", "a b c d") == pytest.approx(1 / 3)  # one insertion
    assert error_rate("a", "a b c") == pytest.approx(2.0), "more errors than reference words"


def test_the_rate_ignores_case_and_punctuation():
    assert error_rate("When should it be reported?", "when should it be reported") == 0.0
    assert error_rate("फसल बीमा कब? ।", "फसल बीमा कब") == 0.0


def test_hindi_and_tamil_word_errors():
    assert error_rate("फसल बीमा कब", "फसल बीमा कहाँ") == pytest.approx(1 / 3)
    assert error_rate("பயிர் காப்பீடு எப்போது", "பயிர் காப்பீடு எப்போது") == 0.0
    assert error_rate("பயிர் காப்பீடு எப்போது", "பயிர் காப்பீடு") == pytest.approx(1 / 3)


def test_character_error_rate():
    assert error_rate("ab cd", "abcd", "char") == 0.0
    assert error_rate("abcd", "abxd", "char") == pytest.approx(1 / 4)
    assert 0.0 < error_rate("फसल बीमा कब", "फसल बीमा कहाँ", "char") < 1.0


def test_an_empty_reference():
    assert error_rate("", "", "word") == 0.0
    assert error_rate("", "something", "word") == 1.0
    assert error_rate("?!", "", "char") == 0.0, "a reference that is only punctuation is empty"
    assert error_rate("", "x y z", "char") == 1.0


def test_an_empty_hypothesis_is_a_complete_miss():
    assert error_rate("a b c", "", "word") == 1.0


def test_an_unknown_mode_is_an_error():
    with pytest.raises(ValueError, match="word"):
        error_rate("a", "a", "sentence")


# --- run_evals ------------------------------------------------------------------------


class PlainProvider:
    """Like WhisperSpeechProvider: no use_vocabulary_hint argument."""

    def __init__(self, text):
        self.text = text
        self.calls = []

    async def transcribe(self, audio, *, content_type, language_hint):
        self.calls.append({"audio": audio, "content_type": content_type, "hint": language_hint})
        return Transcript(text=self.text, language=language_hint or "en", confidence=0.9)


class HintProvider:
    """A provider that does take use_vocabulary_hint."""

    def __init__(self, text):
        self.text = text
        self.hints = []

    async def transcribe(self, audio, *, content_type, language_hint, use_vocabulary_hint):
        self.hints.append(use_vocabulary_hint)
        return Transcript(text=self.text, language=language_hint, confidence=0.5)


def clip(tmp_path, name="clip.m4a"):
    path = tmp_path / name
    path.write_bytes(b"not-real-audio")
    return path


def test_run_evals_prints_the_error_rates(tmp_path, capsys):
    provider = PlainProvider("a x c")
    asyncio.run(run_evals([(clip(tmp_path), "a b c", "en")], provider))
    out = capsys.readouterr().out
    assert "File: clip.m4a | Language: en | Confidence: 0.90" in out
    assert "Ground Truth: a b c" in out
    assert "Word error rate: 33.3% | Character error rate: 33.3%" in out
    assert provider.calls == [
        {"audio": b"not-real-audio", "content_type": "audio/m4a", "hint": "en"}
    ]


def test_run_evals_scores_hindi(tmp_path, capsys):
    provider = PlainProvider("फसल बीमा कब")
    asyncio.run(run_evals([(clip(tmp_path), "फसल बीमा कब? ।", "hi")], provider))
    assert "Word error rate: 0.0% | Character error rate: 0.0%" in capsys.readouterr().out


def test_run_evals_passes_the_hint_only_to_providers_that_take_it(tmp_path):
    taking = HintProvider("a")
    asyncio.run(run_evals([(clip(tmp_path), "a", "en")], taking))
    assert taking.hints == [True], "the original call is unchanged for such providers"

    # PlainProvider.transcribe would raise TypeError if the hint were passed to it.
    plain = PlainProvider("a")
    asyncio.run(run_evals([(clip(tmp_path), "a", "en")], plain))
    assert len(plain.calls) == 1


def test_the_real_provider_does_not_take_the_hint():
    """The reason run_evals checks: passing it to WhisperSpeechProvider would be a TypeError."""
    assert _accepts(WhisperSpeechProvider().transcribe, "use_vocabulary_hint") is False
    assert _accepts(WhisperSpeechProvider().transcribe, "language_hint") is True


def test_run_evals_without_a_ground_truth_prints_no_rate(tmp_path, capsys):
    cases = [(clip(tmp_path), "", "en"), (clip(tmp_path, "b.m4a"), None, "en")]
    asyncio.run(run_evals(cases, PlainProvider("x")))
    out = capsys.readouterr().out
    assert out.count("File: ") == 2 and "error rate" not in out


def test_run_evals_skips_a_missing_file(tmp_path, capsys):
    provider = PlainProvider("x")
    asyncio.run(run_evals([(tmp_path / "gone.m4a", "a", "en")], provider))
    out = capsys.readouterr().out
    assert "Skipping" in out and "(File not found)" in out
    assert provider.calls == [], "nothing is transcribed for a missing file"


def test_run_evals_writes_nothing(tmp_path):
    audio = clip(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    asyncio.run(run_evals([(audio, "a b", "en")], PlainProvider("a b")))
    assert sorted(p.name for p in tmp_path.iterdir()) == before
