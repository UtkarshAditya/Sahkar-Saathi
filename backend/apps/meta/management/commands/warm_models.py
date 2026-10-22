"""Load the speech-to-text model before the server starts, so the first request is fast.

With USE_STUB_SPEECH=false this loads (and on first run downloads, into HF_HOME) the
Whisper model set by WHISPER_MODEL. With the stub on there is nothing to load.

Never fails: a missing network or model prints a warning and exits 0, and the model is
then loaded on the first transcription instead. The container entrypoint runs this with
a time limit (WARM_TIMEOUT) so start-up cannot hang.
"""

import time

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Load the Whisper model when real speech-to-text is on (USE_STUB_SPEECH=false)."

    def handle(self, *args, **options):
        if settings.USE_STUB_SPEECH:
            self.stdout.write("warm_models: speech is the stub, nothing to warm.")
            return
        started = time.perf_counter()
        try:
            from services.speech import whisper_provider

            whisper_provider._get_model()
        except Exception as exc:  # never stop the container over a model download
            self.stdout.write(
                self.style.WARNING(
                    f"warm_models: could not load the Whisper model ({exc.__class__.__name__}: "
                    f"{exc}). It will be loaded on the first transcription instead."
                )
            )
            return
        seconds = time.perf_counter() - started
        self.stdout.write(
            self.style.SUCCESS(
                f"warm_models: Whisper model '{whisper_provider.MODEL_SIZE}' loaded "
                f"in {seconds:.1f} s."
            )
        )
