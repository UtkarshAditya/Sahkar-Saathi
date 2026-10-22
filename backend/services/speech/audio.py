"""Audio helpers (role C). Plain Python, no Django imports.

Browsers record WebM (Chrome, Firefox) or MP4 (Safari). Bhashini works best with
16 kHz mono WAV, so convert with ffmpeg first. Requires ffmpeg on the machine:
    macOS: brew install ffmpeg
"""

import asyncio
import subprocess
import tempfile
from pathlib import Path

from ..types import ProviderError


def _suffix_for(content_type: str | None) -> str:
    """Give ffmpeg a file extension hint; it also probes the content itself."""
    ct = (content_type or "").lower()
    for key, suffix in (
        ("webm", ".webm"),
        ("mp4", ".mp4"),
        ("m4a", ".m4a"),
        ("ogg", ".ogg"),
        ("wav", ".wav"),
        ("mpeg", ".mp3"),
    ):
        if key in ct:
            return suffix
    return ""


def _convert(audio: bytes, suffix: str) -> bytes:
    # Temp files, not pipes: MP4 from Safari often cannot be read from a pipe.
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / ("input" + suffix)
        dst = Path(tmp) / "output.wav"
        src.write_bytes(audio)
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1", "-f", "wav", str(dst)],
                check=True,
                capture_output=True,
                timeout=30,
            )
        except FileNotFoundError as exc:
            raise ProviderError("ffmpeg is not installed on this machine.") from exc
        except subprocess.TimeoutExpired as exc:
            raise ProviderError("Audio conversion timed out.") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode(errors="ignore")[-300:]
            raise ProviderError(f"ffmpeg could not convert the audio: {detail}") from exc
        return dst.read_bytes()


async def to_wav_16k_mono(audio: bytes, content_type: str | None = None) -> bytes:
    """Convert recorded audio to 16 kHz mono WAV bytes, without blocking the event loop."""
    if not audio:
        raise ProviderError("No audio received.")
    return await asyncio.to_thread(_convert, audio, _suffix_for(content_type))