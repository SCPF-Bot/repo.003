"""Tests for frame composition and FFmpeg command construction."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
from PIL import Image

from src.config import VideoConfig
from src.errors import PipelineError
from src.video_maker import (
    DecodedPages,
    _concat_line,
    concatenate_clips,
    crop_panel,
    make_panel_frame,
    render_clip,
)


@pytest.fixture
def video() -> VideoConfig:
    return VideoConfig(width=360, height=640, fps=30)


def test_crop_panel_uses_full_page_for_full_crop():
    page = Image.new("RGB", (100, 200), "white")
    panel = crop_panel(page, (0.0, 0.0, 1.0, 1.0))
    assert panel.size == (100, 200)


def test_crop_panel_maps_normalized_coordinates():
    page = Image.new("RGB", (100, 200), "white")
    panel = crop_panel(page, (0.5, 0.5, 0.5, 0.5))
    assert panel.size == (50, 100)


def test_crop_panel_never_returns_zero_pixels():
    """Rounding used to produce a 0-width crop and a Pillow exception."""
    page = Image.new("RGB", (10, 10), "white")
    panel = crop_panel(page, (0.0, 0.0, 0.01, 0.01))
    assert panel.width >= 1 and panel.height >= 1


def test_crop_panel_rejects_absurd_pixel_counts():
    page = Image.new("RGB", (20000, 20000), "white")
    with pytest.raises(PipelineError, match="safety limit"):
        crop_panel(page, (0.0, 0.0, 1.0, 1.0))


def test_make_panel_frame_produces_configured_resolution(tmp_path, video):
    panel = Image.new("RGB", (300, 450), "navy")
    output = make_panel_frame(panel, tmp_path / "frame.png", video)

    with Image.open(output) as image:
        assert image.size == (video.width, video.height)
        assert image.format == "PNG"


def test_decoded_pages_reuses_the_same_image_and_can_close(tmp_path):
    first = tmp_path / "a.png"
    second = tmp_path / "b.png"
    Image.new("RGB", (10, 10), "white").save(first)
    Image.new("RGB", (10, 10), "black").save(second)

    cache = DecodedPages()
    one = cache.get(first)
    assert cache.get(first) is one
    assert cache.get(second) is not one
    cache.close()
    assert cache._image is None


def test_render_clip_omits_shortest_and_pads_audio(tmp_path, video):
    """-shortest truncated every clip; apad keeps audio and video equal length."""
    with mock.patch("src.video_maker.run_command") as run:
        run.return_value = mock.Mock()
        render_clip(
            tmp_path / "f.png", tmp_path / "a.wav", 2.5, tmp_path / "c.mp4", video
        )

    command = run.call_args.args[0]
    assert "-shortest" not in command
    assert "apad" in command
    assert "-fps_mode" in command
    assert "bt709" in command
    assert str(video.fps) in command


def test_concat_line_escapes_apostrophes():
    """A title like 'Ch. 1 - It's Over' used to corrupt the concat manifest."""
    line = _concat_line(Path("/tmp/it's here/clip.mp4"))
    assert line == "file '/tmp/it'\\''s here/clip.mp4'\n"


def test_concatenate_reencodes_audio_but_copies_video(tmp_path):
    with mock.patch("src.video_maker.run_command") as run:
        run.return_value = mock.Mock()
        concatenate_clips([tmp_path / "a.mp4"], tmp_path / "out.mp4", tmp_path)

    command = run.call_args.args[0]
    assert command[command.index("-c:v") + 1] == "copy"
    assert command[command.index("-c:a") + 1] == "aac"


def test_concatenate_requires_clips(tmp_path):
    with pytest.raises(PipelineError, match="No clips"):
        concatenate_clips([], tmp_path / "out.mp4", tmp_path)


def test_manifest_is_written_with_real_newlines(tmp_path):
    (tmp_path / "clip.mp4").write_bytes(b"x")
    with mock.patch("src.video_maker.run_command"):
        concatenate_clips([tmp_path / "clip.mp4"], tmp_path / "out.mp4", tmp_path)

    manifest = (tmp_path / "concat.txt").read_text(encoding="utf-8")
    assert manifest.startswith("file '")
    assert "\r" not in manifest
