"""End-to-end smoke test: real FFmpeg, stubbed speech synthesis.

This is the test that would have caught the missing ``work/clips`` directory,
the ``-shortest`` truncation and the concat timestamp corruption, none of
which unit tests can see.

Skipped automatically when FFmpeg is unavailable.
"""

from __future__ import annotations

import io
import shutil
import wave
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import scripts.run_pipeline as pipeline_module
from scripts.run_pipeline import main

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)

NARRATION = """\
[PAGE 001]
[PANEL 001]
CROP: 0.00,0.00,1.00,0.50
NARRATION: The first panel has a short line.

[PANEL 002]
CROP: 0.00,0.50,1.00,0.50
NARRATION: The second panel has a noticeably longer line of narration text.
"""


def _make_cbz(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for index, color in enumerate(["white", "gray"], start=1):
            buffer = io.BytesIO()
            Image.new("RGB", (400, 600), color).save(buffer, format="JPEG")
            archive.writestr(f"page{index}.jpg", buffer.getvalue())
    return path


class StubTTS:
    """Deterministic stand-in for Kokoro: one second per ~10 words."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def synthesize(self, text: str, output_path: Path) -> float:
        seconds = max(0.8, len(text.split()) / 10)
        frames_count = int(24000 * seconds)
        samples = np.zeros(frames_count, dtype=np.int16)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "w") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(24000)
            handle.writeframes(samples.tobytes())
        return seconds


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A throwaway project root with input/, config and a stubbed TTS."""

    root = tmp_path / "project"
    (root / "input").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "config.yaml").write_text(
        "voice:\n  voice: af_heart\nvideo:\n"
        "  width: 360\n  height: 640\n  fps: 30\n  tail_seconds: 0.35\n"
        "  output_filename: narrated-manhwa.mp4\n",
        encoding="utf-8",
    )
    _make_cbz(root / "input" / "chapter.cbz")
    (root / "input" / "chapter.txt").write_text(NARRATION, encoding="utf-8")
    (root / "input" / "README.txt").write_text("housekeeping", encoding="utf-8")

    monkeypatch.setattr(pipeline_module, "ROOT", root)

    import src.tts_engine as tts_module

    monkeypatch.setattr(tts_module, "KokoroTTS", StubTTS)
    return root


def _decoded_seconds(path: Path, stream: str = "v:0") -> float:
    """Seconds of ``stream`` that FFmpeg can actually decode.

    Uses ffmpeg itself rather than ffprobe so the test only depends on one
    binary being present in every environment that runs the pipeline.
    """

    import re
    import subprocess

    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-map", f"0:{stream}",
         "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    stamps = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if not stamps:
        return 0.0
    hours, minutes, seconds = stamps[-1]
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def test_pipeline_renders_a_video(project, monkeypatch, capsys):
    exit_code = main(["--config", str(project / "config.yaml"),
                      "--input-dir", str(project / "input")])

    assert exit_code == 0, capsys.readouterr().out
    video = project / "output" / "narrated-manhwa.mp4"
    assert video.exists(), "pipeline reported success but wrote no MP4"
    assert video.stat().st_size > 1000

    # The log must exist for the CI artifact upload to find something.
    assert (project / "output" / "pipeline.log").read_text(encoding="utf-8")


def test_rendered_video_keeps_the_full_tail_duration(project, capsys):
    """-shortest used to end each clip at the end of the audio stream."""
    assert main(["--config", str(project / "config.yaml"),
                 "--input-dir", str(project / "input")]) == 0, capsys.readouterr().out

    video = project / "output" / "narrated-manhwa.mp4"
    duration = _decoded_seconds(video)

    # Stub audio is max(0.8, words/10): 6 words and 11 words in the fixture.
    expected = (0.8 + 0.35) + (1.1 + 0.35)
    assert duration == pytest.approx(expected, abs=0.30), (
        f"video is {duration:.2f}s, expected about {expected:.2f}s "
        "(a shorter value means tail_seconds is being truncated again)"
    )


def test_video_streams_have_matching_lengths(project, capsys):
    """Mismatched stream lengths desynchronise every clip after the first."""
    assert main(["--input-dir", str(project / "input"),
                 "--config", str(project / "config.yaml")]) == 0

    video = project / "output" / "narrated-manhwa.mp4"
    video_seconds = _decoded_seconds(video, "v:0")
    audio_seconds = _decoded_seconds(video, "a:0")

    assert video_seconds > 0 and audio_seconds > 0
    assert video_seconds == pytest.approx(audio_seconds, abs=0.10), (
        f"video {video_seconds:.2f}s vs audio {audio_seconds:.2f}s: "
        "mismatched stream lengths desynchronise later clips"
    )


def test_validate_mode_does_not_render(project):
    assert main(["--validate", "--input-dir", str(project / "input"),
                 "--config", str(project / "config.yaml")]) == 0
    assert not (project / "output" / "narrated-manhwa.mp4").exists()


def test_missing_input_returns_error_exit_code(project, capsys):
    (project / "input" / "chapter.cbz").unlink()
    assert main(["--input-dir", str(project / "input"),
                 "--config", str(project / "config.yaml")]) == 1
    assert "exactly one" in capsys.readouterr().out.lower()


def test_page_number_beyond_archive_is_reported(project, capsys):
    (project / "input" / "chapter.txt").write_text(
        "[PAGE 005]\n[PANEL 001]\nCROP: 0,0,1,1\nNARRATION: Out of range.\n",
        encoding="utf-8",
    )
    assert main(["--input-dir", str(project / "input"),
                 "--config", str(project / "config.yaml")]) == 1
    assert "page 5" in capsys.readouterr().out.lower()
