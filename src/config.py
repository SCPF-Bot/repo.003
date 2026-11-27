"""Load and validate ``config.yaml``."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.errors import PipelineError

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VoiceConfig:
    voice: str = "af_heart"
    lang_code: str = "a"
    speed: float = 1.0


@dataclass(frozen=True, slots=True)
class VideoConfig:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    tail_seconds: float = 0.35
    output_filename: str = "narrated-manhwa.mp4"
    #: Gaussian blur radius applied to the background plate.
    background_blur: float = 32.0
    #: How much black to blend into the background plate (0..1).
    background_darken: float = 0.38


@dataclass(frozen=True, slots=True)
class Settings:
    voice: VoiceConfig
    video: VideoConfig


def _require_mapping(value: object, name: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise PipelineError(f"config.yaml: '{name}' must be a mapping.")
    return value


def _positive_int(section: dict, key: str, default: int) -> int:
    raw = section.get(key, default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise PipelineError(f"config.yaml: video.{key} must be an integer.") from exc
    if value <= 0:
        raise PipelineError(f"config.yaml: video.{key} must be greater than zero.")
    return value


def _bounded_float(section: dict, name: str, default: float, low: float, high: float) -> float:
    raw = section.get(name.split(".")[-1], default)
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise PipelineError(f"config.yaml: {name} must be a number.") from exc
    if not low <= value <= high:
        raise PipelineError(f"config.yaml: {name} must be between {low} and {high}.")
    return value


def load_settings(path: Path) -> Settings:
    """Parse ``path`` into validated settings with helpful errors."""

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PipelineError(f"Missing configuration file: {path}") from exc
    except yaml.YAMLError as exc:
        raise PipelineError(f"{path.name} is not valid YAML: {exc}") from exc

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise PipelineError(f"{path.name} must contain a mapping at the top level.")

    voice_section = _require_mapping(raw.get("voice"), "voice")
    video_section = _require_mapping(raw.get("video"), "video")

    speed = _bounded_float(voice_section, "voice.speed", 1.0, 0.1, 5.0)

    width = _positive_int(video_section, "width", 1080)
    height = _positive_int(video_section, "height", 1920)
    if width % 2 or height % 2:
        raise PipelineError(
            "config.yaml: video.width and video.height must be even numbers "
            "for yuv420p output."
        )

    output_filename = str(video_section.get("output_filename", "narrated-manhwa.mp4"))
    if not output_filename.lower().endswith(".mp4"):
        raise PipelineError("config.yaml: video.output_filename must end with '.mp4'.")

    video = VideoConfig(
        width=width,
        height=height,
        fps=_positive_int(video_section, "fps", 30),
        tail_seconds=_bounded_float(video_section, "tail_seconds", 0.35, 0.0, 10.0),
        output_filename=output_filename,
        background_blur=_bounded_float(video_section, "background_blur", 32.0, 0.0, 200.0),
        background_darken=_bounded_float(video_section, "background_darken", 0.38, 0.0, 1.0),
    )

    voice = VoiceConfig(
        voice=str(voice_section.get("voice", "af_heart")),
        lang_code=str(voice_section.get("lang_code", "a")),
        speed=speed,
    )

    return Settings(voice=voice, video=video)
