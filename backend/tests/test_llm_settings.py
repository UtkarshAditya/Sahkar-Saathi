"""Tests for the LLM wrapper's settings (role C). No Ollama needed: the client is faked.

Run from backend/:  python -m pytest tests/test_llm_settings.py -v
"""

import asyncio
import types

import pytest
from openai import OpenAIError

from services import llm
from services.types import ProviderError

SETTINGS = ("LLM_MAX_TOKENS", "LLM_TEMPERATURE", "LLM_JSON_MODE", "LLM_MODEL", "LLM_BASE_URL")


class _FakeClient:
    """Records what generate() sends, and returns a canned reply."""

    def __init__(self, error=None):
        self.sent = {}
        self._error = error
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        if self._error:
            raise self._error
        self.sent = kwargs
        message = types.SimpleNamespace(content='{"ok": true}')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


@pytest.fixture
def client(monkeypatch):
    for name in SETTINGS:
        monkeypatch.delenv(name, raising=False)
    fake = _FakeClient()
    monkeypatch.setattr(llm, "_client", lambda url, key, timeout: fake)
    return fake


def _generate(**kwargs):
    return asyncio.run(llm.generate("system", "user", **kwargs))


def test_defaults_send_temperature_zero_and_json_mode_but_no_token_cap(client):
    assert _generate() == '{"ok": true}'
    assert client.sent["temperature"] == 0.0
    assert client.sent["response_format"] == {"type": "json_object"}
    assert client.sent["model"] == llm.DEFAULT_MODEL
    assert "max_tokens" not in client.sent


def test_token_cap_is_sent_when_set(client, monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOKENS", "600")
    _generate()
    assert client.sent["max_tokens"] == 600


@pytest.mark.parametrize("value", ["", "0"])
def test_empty_or_zero_token_cap_is_not_sent(client, monkeypatch, value):
    monkeypatch.setenv("LLM_MAX_TOKENS", value)
    _generate()
    assert "max_tokens" not in client.sent


def test_temperature_modelfile_means_not_sent(client, monkeypatch):
    monkeypatch.setenv("LLM_TEMPERATURE", "modelfile")
    _generate()
    assert "temperature" not in client.sent


def test_temperature_setting_and_argument(client, monkeypatch):
    monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
    _generate()
    assert client.sent["temperature"] == 0.3
    _generate(temperature=0.7)
    assert client.sent["temperature"] == 0.7


def test_empty_temperature_uses_the_default(client, monkeypatch):
    monkeypatch.setenv("LLM_TEMPERATURE", "")
    _generate()
    assert client.sent["temperature"] == 0.0


def test_json_mode_off_by_argument_or_setting(client, monkeypatch):
    _generate(json_mode=False)
    assert "response_format" not in client.sent
    monkeypatch.setenv("LLM_JSON_MODE", "false")
    _generate()
    assert "response_format" not in client.sent


def test_max_tokens_argument_overrides(client, monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOKENS", "600")
    _generate(max_tokens=50)
    assert client.sent["max_tokens"] == 50


def test_model_name_follows_the_setting(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "sahkar-llama31")
    assert llm.model_name() == "sahkar-llama31"
    monkeypatch.setenv("LLM_MODEL", "")
    assert llm.model_name() == llm.DEFAULT_MODEL


def test_provider_failure_becomes_provider_error(monkeypatch):
    fake = _FakeClient(error=OpenAIError("connection refused"))
    monkeypatch.setattr(llm, "_client", lambda url, key, timeout: fake)
    with pytest.raises(ProviderError):
        _generate()
