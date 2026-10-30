"""Warm-up (role C): load the models before the first real request.

The first LLM call after Ollama loads a model can take 25 seconds or more, and Whisper
loads its model on first use. Call warm_up_all() once when the app starts, or run it by hand:

    python -m services.warmup

Settings (environment variables):
    LLM_KEEP_ALIVE  how long Ollama keeps the model in memory, default 24h
"""

import asyncio
import http.client
import json
import logging
import os
from urllib.parse import urlparse

from . import llm
from .speech.whisper_provider import warm_up as warm_up_whisper

logger = logging.getLogger(__name__)


def _native_endpoint() -> tuple[str, str, int | None, str]:
    """Turn the OpenAI-style base URL into Ollama's own /api/generate address."""
    parsed = urlparse(llm.base_url())
    path = parsed.path.rstrip("/")
    path = path.removesuffix("/v1")
    return parsed.scheme, parsed.hostname or "localhost", parsed.port, path + "/api/generate"


def _load_llm_sync() -> None:
    """Ask Ollama to load the model and keep it loaded. An empty prompt only loads it."""
    scheme, host, port, path = _native_endpoint()
    connection_class = (
        http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
    )
    connection = connection_class(host, port, timeout=llm._timeout())
    try:
        body = json.dumps(
            {
                "model": llm.model_name(),
                "prompt": "",
                "stream": False,
                "keep_alive": os.getenv("LLM_KEEP_ALIVE", "24h"),
            }
        )
        connection.request("POST", path, body, {"Content-Type": "application/json"})
        response = connection.getresponse()
        response.read()
        if response.status >= 400:
            raise RuntimeError(f"Ollama answered HTTP {response.status}")
    finally:
        connection.close()


def load_llm() -> None:
    """Load the model into Ollama and keep it there (blocking; raises if Ollama is down).

    What `manage.py warm_models` calls; warm_up_all() runs it in a thread."""
    _load_llm_sync()


async def warm_up_all(languages=("en", "hi", "ta")) -> dict[str, bool]:
    """Warm up the LLM and Whisper. Never raises: a failure is logged and reported."""
    results = {}
    try:
        await asyncio.to_thread(_load_llm_sync)
        results["llm"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM warm-up failed (%s). The first request will be slow.", exc)
        results["llm"] = False
    try:
        await warm_up_whisper(languages)
        results["whisper"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Whisper warm-up failed (%s). The first transcription will be slow.", exc)
        results["whisper"] = False
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(warm_up_all()))
