"""services/llm.py: settings read at call time, a lazy client, ProviderError on failure.
No network: the client is replaced by a fake."""

import asyncio
import importlib
import socket
import types

import openai
import pytest

from services import llm
from services.types import ProviderError


class FakeCompletions:
    def __init__(self, error: Exception | None = None):
        self.calls: list[dict] = []
        self.error = error

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        message = types.SimpleNamespace(content='{"ok": true}')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


@pytest.fixture
def fake_client(monkeypatch):
    completions = FakeCompletions()
    built: list[tuple] = []

    def client(url, api_key, timeout):
        built.append((url, api_key, timeout))
        return types.SimpleNamespace(chat=types.SimpleNamespace(completions=completions))

    monkeypatch.setattr(llm, "_client", client)
    return completions, built


@pytest.mark.parametrize("name", ["LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_TIMEOUT"])
def test_empty_settings_fall_back_to_the_defaults(monkeypatch, fake_client, name):
    completions, built = fake_client
    monkeypatch.setenv(name, "")
    asyncio.run(llm.generate("system", "user"))
    assert built[-1] == (llm.DEFAULT_BASE_URL, llm.DEFAULT_API_KEY, llm.DEFAULT_TIMEOUT)
    assert completions.calls[-1]["model"] == llm.DEFAULT_MODEL


def test_settings_are_read_at_call_time(monkeypatch, fake_client):
    completions, built = fake_client
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_TIMEOUT", "5")
    asyncio.run(llm.generate("system", "user"))
    assert built[-1] == ("http://llm.test/v1", "test-key", 5.0)
    assert completions.calls[-1]["model"] == "test-model"
    assert llm.model_name() == "test-model"


def test_json_mode_can_be_turned_off(monkeypatch, fake_client):
    completions, _ = fake_client
    asyncio.run(llm.generate("system", "user"))
    assert completions.calls[-1]["response_format"] == {"type": "json_object"}
    monkeypatch.setenv("LLM_JSON_MODE", "false")
    asyncio.run(llm.generate("system", "user"))
    assert "response_format" not in completions.calls[-1]


def test_importing_needs_no_network_and_no_key(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("importing services.llm opened a connection")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    module = importlib.reload(llm)
    assert module._client.cache_info().currsize == 0, "the client must be created lazily"


def test_a_provider_failure_becomes_provider_error(monkeypatch, fake_client):
    completions, _ = fake_client
    completions.error = openai.OpenAIError("connection refused")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    with pytest.raises(ProviderError, match="test-model"):
        asyncio.run(llm.generate("system", "user"))
