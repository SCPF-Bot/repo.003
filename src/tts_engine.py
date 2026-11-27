"""Kokoro-82M text-to-speech wrapper."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import soundfile as sf

LOGGER = logging.getLogger(__name__)

#: Kokoro always renders at this rate. Keep it in one place so duration
#: bookkeeping cannot drift from the file that is written.
SAMPLE_RATE = 24000


class TTSError(RuntimeError):
    """Raised when the speech engine cannot produce audio."""


class KokoroTTS:
    """Narrate text with Kokoro.

    ``KPipeline`` is imported lazily: importing ``kokoro`` pulls in Torch and
    Transformers, which costs several seconds and a few hundred megabytes.
    Validation-only runs should not pay that cost.
    """

    def __init__(
        self,
        voice: str = "af_heart",
        lang_code: str = "a",
        speed: float = 1.0,
    ) -> None:
        try:
            from kokoro import KPipeline
        except ImportError as exc:  # pragma: no cover - depends on the install
            raise TTSError(
                "The 'kokoro' package is not installed. Run "
                "`pip install -r requirements.txt` first."
            ) from exc

        self.voice = voice
        self.speed = float(speed)
        self.pipeline = KPipeline(lang_code=lang_code)
        LOGGER.info(
            "Kokoro ready (voice=%s, lang_code=%s, speed=%.2f)",
            self.voice,
            lang_code,
            self.speed,
        )

    def synthesize(self, text: str, output_path: Path) -> float:
        """Render ``text`` to ``output_path`` and return its duration in seconds."""

        chunks = [
            np.asarray(audio, dtype=np.float32).reshape(-1)
            for _graphemes, _phonemes, audio in self.pipeline(
                text, voice=self.voice, speed=self.speed
            )
            if audio is not None
        ]
        if not chunks:
            raise TTSError(f"Kokoro returned no audio for: {text[:80]!r}")

        audio = np.concatenate(chunks)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), audio, SAMPLE_RATE)

        # Measure what was actually written instead of assuming the model
        # honoured our requested rate; a mismatch here would desynchronise
        # every clip that follows.
        frames = sf.info(str(output_path)).frames
        if frames <= 0:
            raise TTSError(f"Kokoro wrote an empty audio file: {output_path}")
        return frames / SAMPLE_RATE
