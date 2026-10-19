"""LLM wrapper (role C). Plain Python, no Django imports.

Async, because the API handlers are async and a blocking call would freeze them.
Everything that can change is a setting (environment variable):

    LLM_BASE_URL  default http://localhost:11434/v1   (Ollama's OpenAI-compatible API)
    LLM_MODEL     default llama3.1:8b
    LLM_API_KEY   default "ollama" (Ollama ignores it; hosted providers need a real key)
    LLM_TIMEOUT   seconds, default 60
"""
import os

from openai import AsyncOpenAI, OpenAIError

from .types import ProviderError

BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
API_KEY = os.getenv("LLM_API_KEY", "ollama")
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))

_client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=TIMEOUT)


async def generate(system: str, user: str, json_mode: bool = True, temperature: float = 0.0) -> str:
    """Send one system + user prompt and return the model's raw text.

    temperature 0 keeps answers as repeatable as possible, which matters when
    we score the model on the 80-question set. Any provider failure (server not
    running, timeout, bad key, rate limit) is raised as ProviderError, which the
    API layer already knows how to turn into a clean error response.
    """
    kwargs = {}
    if json_mode:
        # Asks the server for valid JSON. If a provider rejects this option,
        # call with json_mode=False and rely on the parser in answer.py.
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = await _client.chat.completions.create(
            model=MODEL,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **kwargs,
        )
    except OpenAIError as exc:
        raise ProviderError(f"LLM call failed ({MODEL} at {BASE_URL}): {exc}") from exc
    return response.choices[0].message.content or ""


if __name__ == "__main__":
    import asyncio

    async def _main() -> None:
        print(f"Model: {MODEL} at {BASE_URL}")
        print(await generate("You are a helpful assistant.", 'Reply with JSON: {"ok": true}'))

    asyncio.run(_main())