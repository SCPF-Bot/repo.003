"""Tests for the Kokoro wrapper (no model download required)."""

from __future__ import annotations

import sys
from unittest import mock

import numpy as np
import pytest

import src.tts_engine as tts_module
from src.tts_engine import KokoroTTS, TTSError


class FakePipeline:
    """Stands in for ``kokoro.KPipeline``."""

    def __init__(self, chunks=None, lang_code: str = "a") -> None:
        self.chunks = chunks if chunks is not None else [np.zeros(24000, dtype=np.float32)]
        self.lang_code = lang_code
        self.calls: list[tuple[str, str, float]] = []

    def __call__(self, text, voice="af_heart", speed=1.0):
        self.calls.append((text, voice, speed))
        for chunk in self.chunks:
            yield "", "", chunk


@pytest.fixture
def fake_kokoro(monkeypatch):
    module = mock.MagicMock()
    module.KPipeline = FakePipeline
    monkeypatch.setitem(sys.modules, "kokoro", module)
    return module


def test_synthesize_writes_audio_and_returns_duration(fake_kokoro, tmp_path):
    engine = KokoroTTS(voice="af_heart", lang_code="a", speed=1.0)
    engine.pipeline = FakePipeline([np.zeros(24000, dtype=np.float32)])

    seconds = engine.synthesize("Hello there.", tmp_path / "out.wav")

    assert seconds == pytest.approx(1.0, abs=0.01)
    assert (tmp_path / "out.wav").exists()


def test_synthesize_concatenates_chunks(fake_kokoro, tmp_path):
    engine = KokoroTTS()
    engine.pipeline = FakePipeline(
        [np.zeros(12000, dtype=np.float32), np.zeros(12000, dtype=np.float32)]
    )
    assert engine.synthesize("Two chunks.", tmp_path / "out.wav") == pytest.approx(1.0, abs=0.01)


def test_synthesize_skips_none_chunks(fake_kokoro, tmp_path):
    engine = KokoroTTS()
    engine.pipeline = FakePipeline([None, np.zeros(24000, dtype=np.float32)])
    assert engine.synthesize("Sparse.", tmp_path / "out.wav") == pytest.approx(1.0, abs=0.01)


def test_synthesize_rejects_empty_audio(fake_kokoro, tmp_path):
    engine = KokoroTTS()
    engine.pipeline = FakePipeline([])
    with pytest.raises(TTSError, match="no audio"):
        engine.synthesize("Silence.", tmp_path / "out.wav")


def test_missing_kokoro_package_is_actionable(monkeypatch):
    monkeypatch.setitem(sys.modules, "kokoro", None)
    with pytest.raises(TTSError, match="pip install"):
        KokoroTTS()


def test_voice_and_speed_are_forwarded(fake_kokoro, tmp_path):
    engine = KokoroTTS(voice="bf_emma", lang_code="b", speed=1.5)
    engine.pipeline = FakePipeline()
    engine.synthesize("Hi.", tmp_path / "out.wav")

    text, voice, speed = engine.pipeline.calls[0]
    assert (text, voice, speed) == ("Hi.", "bf_emma", 1.5)


def test_sample_rate_is_the_kokoro_rate():
    assert tts_module.SAMPLE_RATE == 24000
