from pathlib import Path
import numpy as np
import soundfile as sf
from kokoro import KPipeline


class KokoroTTS:
    def __init__(self, voice: str = "af_heart", lang_code: str = "a", speed: float = 1.0):
        self.pipeline = KPipeline(lang_code=lang_code)
        self.voice = voice
        self.speed = speed

    def synthesize(self, text: str, output_path: Path) -> float:
        chunks = []
        for _graphemes, _phonemes, audio in self.pipeline(
            text, voice=self.voice, speed=self.speed
        ):
            if audio is not None:
                chunks.append(np.asarray(audio, dtype=np.float32).reshape(-1))
        if not chunks:
            raise RuntimeError("Kokoro returned no audio for narration.")
        audio = np.concatenate(chunks)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), audio, 24000)
        return len(audio) / 24000
