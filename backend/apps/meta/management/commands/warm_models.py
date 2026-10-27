"""Load the models before the server starts, so the first request is fast.

- USE_STUB_SPEECH=false: the Whisper model(s) for the supported languages: WHISPER_MODEL,
  or a WHISPER_MODEL_<LANG> override (for example WHISPER_MODEL_HI=medium).
- USE_STUB_RETRIEVER=false: the embedding model set by EMBEDDING_MODEL.

Both download into HF_HOME on first use. With every service on its stub there is nothing
to load.

Never fails: a missing network, a missing package or a bad model name prints a warning and
exits 0, and the model is then loaded on first use instead. The container entrypoint runs
this with a time limit (WARM_TIMEOUT) so start-up cannot hang.
"""

import time

from django.conf import settings
from django.core.management.base import BaseCommand


def _load_whisper() -> str:
    import asyncio

    from services.speech import whisper_provider

    languages = tuple(settings.SUPPORTED_LANGUAGES)
    # warm_up loads each distinct model these languages need (WHISPER_MODEL, or a
    # WHISPER_MODEL_<LANG> override) once.
    asyncio.run(whisper_provider.warm_up(languages))
    names = sorted({whisper_provider._model_name_for(language) for language in languages})
    return f"Whisper {'model' if len(names) == 1 else 'models'} " + ", ".join(
        repr(name) for name in names
    )


def _load_embedding_model() -> str:
    from sentence_transformers import SentenceTransformer

    SentenceTransformer(settings.EMBEDDING_MODEL)
    return f"embedding model '{settings.EMBEDDING_MODEL}'"


class Command(BaseCommand):
    help = "Load the Whisper and embedding models when their services are not stubs."

    def handle(self, *args, **options):
        # (what, load function, when it is first used instead)
        wanted = []
        if not settings.USE_STUB_SPEECH:
            wanted.append(("Whisper model", _load_whisper, "the first transcription"))
        if not settings.USE_STUB_RETRIEVER:
            wanted.append(("embedding model", _load_embedding_model, "the first question"))
        if not wanted:
            self.stdout.write("warm_models: speech and retrieval are stubs, nothing to warm.")
            return

        for what, load, fallback in wanted:
            started = time.perf_counter()
            try:
                loaded = load()
            except Exception as exc:  # never stop the container over a model download
                self.stdout.write(
                    self.style.WARNING(
                        f"warm_models: could not load the {what} ({exc.__class__.__name__}: "
                        f"{exc}). It will be loaded on {fallback} instead."
                    )
                )
                continue
            seconds = time.perf_counter() - started
            self.stdout.write(
                self.style.SUCCESS(f"warm_models: {loaded} loaded in {seconds:.1f} s.")
            )
