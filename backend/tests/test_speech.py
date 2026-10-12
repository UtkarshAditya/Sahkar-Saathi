import io
import json
import wave

from django.core.files.uploadedfile import SimpleUploadedFile

TRANSCRIBE = "/api/v1/speech/transcribe"
SYNTHESIZE = "/api/v1/speech/synthesize"


def upload(content=b"fake-webm-bytes", content_type="audio/webm;codecs=opus"):
    return SimpleUploadedFile("question.webm", content, content_type=content_type)


def test_transcribe_returns_transcript(client):
    res = client.post(TRANSCRIBE, {"audio": upload(), "language_hint": "hi"})
    assert res.status_code == 200
    body = res.json()
    assert body["text"]
    assert body["language"] == "hi"
    assert 0 <= body["confidence"] <= 1
    assert body["is_demo"] is True


def test_transcribe_rejects_non_audio(client):
    res = client.post(TRANSCRIBE, {"audio": upload(content_type="application/pdf")})
    assert res.status_code == 415
    assert res.json()["code"] == "unsupported_audio_type"


def test_transcribe_rejects_large_files(client, settings):
    settings.SPEECH_MAX_UPLOAD_BYTES = 10
    res = client.post(TRANSCRIBE, {"audio": upload(content=b"x" * 11)})
    assert res.status_code == 413
    assert res.json()["code"] == "audio_too_large"


def test_transcribe_rejects_empty_files(client):
    res = client.post(TRANSCRIBE, {"audio": upload(content=b"")})
    assert res.status_code == 400
    assert res.json()["code"] == "empty_audio"


def test_transcribe_rejects_unknown_language(client):
    res = client.post(TRANSCRIBE, {"audio": upload(), "language_hint": "xx"})
    assert res.status_code == 422


def test_transcribe_requires_audio(client):
    res = client.post(TRANSCRIBE, {"language_hint": "en"})
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"


def test_synthesize_returns_wav(client):
    res = client.post(
        SYNTHESIZE,
        data=json.dumps({"text": "Report the loss early.", "language": "en"}),
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res["Content-Type"] == "audio/wav"
    with wave.open(io.BytesIO(res.content)) as wav:
        assert wav.getframerate() == 16_000
        assert wav.getnchannels() == 1


def test_synthesize_validates_text(client):
    res = client.post(
        SYNTHESIZE, data=json.dumps({"text": "", "language": "en"}), content_type="application/json"
    )
    assert res.status_code == 422
    assert set(res.json()) == {"code", "message"}
