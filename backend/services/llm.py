"""LLM wrapper (role C). Plain Python, no Django imports.

Async, because the API handlers are async and a blocking call would freeze them.
Everything that can change is a setting (environment variable), read at call time, so
an empty value (Compose passes "" for unset variables) falls back to the default:

    LLM_BASE_URL   default http://localhost:11434/v1   (Ollama's OpenAI-compatible API)
    LLM_MODEL      default llama3.1:8b
    LLM_API_KEY    default "ollama" (Ollama ignores it; hosted providers need a real key)
    LLM_TIMEOUT    seconds, default 60
    LLM_JSON_MODE  default true; false stops sending response_format, for providers
                   that reject it (answer.py's parser still checks the JSON)

Importing this module needs no network and no key: the client is created on first use.
"""

import os
from functools import cache

from openai import AsyncOpenAI, OpenAIError

from .types import ProviderError

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_API_KEY = "ollama"
DEFAULT_TIMEOUT = 60.0


def base_url() -> str:
    return os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL


def model_name() -> str:
    return os.getenv("LLM_MODEL") or DEFAULT_MODEL


def _api_key() -> str:
    return os.getenv("LLM_API_KEY") or DEFAULT_API_KEY


def _timeout() -> float:
    return float(os.getenv("LLM_TIMEOUT") or DEFAULT_TIMEOUT)


def _json_mode_allowed() -> bool:
    value = os.getenv("LLM_JSON_MODE") or "true"
    return value.strip().lower() in {"1", "true", "yes", "on"}


@cache
def _client(url: str, api_key: str, timeout: float) -> AsyncOpenAI:
    # One client per configuration; it holds a connection pool, so reuse it.
    return AsyncOpenAI(base_url=url, api_key=api_key, timeout=timeout)


async def generate(system: str, user: str, json_mode: bool = True, temperature: float = 0.0) -> str:
    """Send one system + user prompt and return the model's raw text.

    temperature 0 keeps answers as repeatable as possible, which matters when
    we score the model on the 80-question set. Any provider failure (server not
    running, timeout, bad key, rate limit) is raised as ProviderError, which the
    API layer already knows how to turn into a clean error response.
    """
    url, model = base_url(), model_name()
    kwargs = {}
    if json_mode and _json_mode_allowed():
        # Asks the server for valid JSON. If a provider rejects this option,
        # set LLM_JSON_MODE=false and rely on the parser in answer.py.
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = await _client(url, _api_key(), _timeout()).chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **kwargs,
        )
    except OpenAIError as exc:
        raise ProviderError(f"LLM call failed ({model} at {url}): {exc}") from exc
    return response.choices[0].message.content or ""


if __name__ == "__main__":
    import asyncio

    async def _main() -> None:
        print(f"Model: {model_name()} at {base_url()}")
        print(await generate("You are a helpful assistant.", 'Reply with JSON: {"ok": true}'))

    asyncio.run(_main())
