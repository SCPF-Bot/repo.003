"""Tests for config.yaml loading and validation."""

from __future__ import annotations

import pytest

from src.config import load_settings
from src.errors import PipelineError

MINIMAL = "voice:\n  voice: af_heart\nvideo:\n  output_filename: out.mp4\n"


def write(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_defaults(tmp_path):
    settings = load_settings(write(tmp_path, MINIMAL))
    assert settings.voice.voice == "af_heart"
    assert settings.video.width == 1080
    assert settings.video.height == 1920
    assert settings.video.fps == 30


def test_repository_config_is_valid():
    from pathlib import Path

    settings = load_settings(Path(__file__).resolve().parents[1] / "config.yaml")
    assert settings.video.output_filename.endswith(".mp4")


def test_values_override_defaults(tmp_path):
    settings = load_settings(
        write(
            tmp_path,
            "voice:\n  speed: 1.25\nvideo:\n  width: 720\n  height: 1280\n  fps: 24\n",
        )
    )
    assert settings.voice.speed == 1.25
    assert (settings.video.width, settings.video.height, settings.video.fps) == (720, 1280, 24)


def test_odd_dimensions_are_rejected(tmp_path):
    with pytest.raises(PipelineError, match="even numbers"):
        load_settings(write(tmp_path, "video:\n  width: 1081\n"))


def test_non_mp4_output_is_rejected(tmp_path):
    with pytest.raises(PipelineError, match=r"must end with '.mp4'"):
        load_settings(write(tmp_path, "video:\n  output_filename: out.mkv\n"))


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("video:\n  width: abc\n", "must be an integer"),
        ("video:\n  width: -4\n", "greater than zero"),
        ("voice:\n  speed: 9\n", "between"),
        ("video:\n  background_darken: 2\n", "between"),
        ("video:\n  tail_seconds: -1\n", "between"),
    ],
)
def test_invalid_values_are_rejected(tmp_path, body, message):
    with pytest.raises(PipelineError, match=message):
        load_settings(write(tmp_path, body))


def test_broken_yaml_is_reported(tmp_path):
    with pytest.raises(PipelineError, match="not valid YAML"):
        load_settings(write(tmp_path, "video: [oops\n"))


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(PipelineError, match="Missing configuration"):
        load_settings(tmp_path / "absent.yaml")


def test_wrong_section_type_is_reported(tmp_path):
    with pytest.raises(PipelineError, match="must be a mapping"):
        load_settings(write(tmp_path, "video: just-a-string\n"))


def test_empty_config_uses_defaults(tmp_path):
    settings = load_settings(write(tmp_path, ""))
    assert settings.video.width == 1080
