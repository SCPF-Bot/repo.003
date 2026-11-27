#!/usr/bin/env python3
"""Render a narrated portrait video from a CBZ chapter and a narration TXT.

Usage::

    python scripts/run_pipeline.py              # full render
    python scripts/run_pipeline.py --validate   # validate inputs only

Exit codes: 0 on success, 1 on a pipeline error, 2 on invalid arguments.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cbz_reader import CbzError, extract_pages  # noqa: E402
from src.config import Settings, load_settings  # noqa: E402
from src.errors import PipelineError, require_binary  # noqa: E402
from src.input_locator import find_input_pair  # noqa: E402
from src.models import Page, Panel  # noqa: E402
from src.narration_parser import parse_narration_with_report  # noqa: E402
from src.video_maker import (  # noqa: E402
    DecodedPages,
    concatenate_clips,
    crop_panel,
    make_panel_frame,
    render_clip,
)

LOGGER = logging.getLogger("pipeline")

REQUIRED_BINARIES = ("ffmpeg", "ffprobe")


def configure_logging(output_dir: Path) -> Path:
    """Log to both the console and ``output/pipeline.log``.

    The file handler is attached first thing in ``main`` so that *any* later
    failure still leaves a diagnostic artifact behind.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "pipeline.log"
    formatter = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s")

    LOGGER.setLevel(logging.INFO)
    LOGGER.handlers.clear()

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    LOGGER.addHandler(file_handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    LOGGER.addHandler(console)

    return log_path


def check_panels_against_pages(panels: list[Panel], pages: list[Page]) -> None:
    """Fail before any expensive work if the TXT mentions pages that do not exist."""

    for panel in panels:
        if panel.page_number > len(pages):
            raise PipelineError(
                f"Line {panel.line_number}: {panel.label} refers to page "
                f"{panel.page_number}, but {len(pages)} page(s) were extracted "
                "from the archive. Page numbers in the TXT must match the "
                "extracted page order."
            )

    referenced = {panel.page_number for panel in panels}
    unused = [number for number in range(1, len(pages) + 1) if number not in referenced]
    if unused:
        LOGGER.warning(
            "The narration TXT never references page(s) %s of %d. "
            "Those pages will not appear in the video.",
            ", ".join(str(number) for number in unused),
            len(pages),
        )


def validate(settings: Settings, input_dir: Path) -> tuple[list[Page], list[Panel]]:
    """Check inputs and return the extracted pages and parsed panels."""

    for binary in REQUIRED_BINARIES:
        require_binary(binary)

    pair = find_input_pair(input_dir)
    pages = extract_pages(pair.cbz, input_dir.parent / "output" / "work" / "pages")

    report = parse_narration_with_report(pair.narration)
    for warning in report.warnings:
        LOGGER.warning("%s", warning)

    check_panels_against_pages(report.panels, pages)

    LOGGER.info(
        "Validation passed: %d page(s), %d panel(s), %.1f seconds of narration.",
        len(pages),
        len(report.panels),
        sum(len(panel.narration.split()) for panel in report.panels) / 2.5,
    )
    return pages, report.panels


def render(settings: Settings, pages: list[Page], panels: list[Panel], output_dir: Path) -> Path:
    """Render the video and return its path."""

    from src.tts_engine import KokoroTTS  # heavy import, only needed here

    work = output_dir / "work"
    for name in ("frames", "audio", "clips"):
        (work / name).mkdir(parents=True, exist_ok=True)

    tts = KokoroTTS(
        voice=settings.voice.voice,
        lang_code=settings.voice.lang_code,
        speed=settings.voice.speed,
    )

    decoded = DecodedPages()
    clips: list[Path] = []
    try:
        for index, panel in enumerate(panels, start=1):
            LOGGER.info(
                "[%d/%d] %s: %.0f words",
                index,
                len(panels),
                panel.label,
                len(panel.narration.split()),
            )

            page = decoded.get(pages[panel.page_number - 1].path)
            panel_image = crop_panel(page, panel.crop, label=panel.label)

            frame_path = make_panel_frame(
                panel_image, work / "frames" / f"panel_{index:04d}.png", settings.video
            )
            panel_image.close()

            audio_path = work / "audio" / f"panel_{index:04d}.wav"
            narration_seconds = tts.synthesize(panel.narration, audio_path)

            clip_duration = narration_seconds + settings.video.tail_seconds
            clip_path = render_clip(
                frame_path,
                audio_path,
                clip_duration,
                work / "clips" / f"clip_{index:04d}.mp4",
                settings.video,
            )
            clips.append(clip_path)
    finally:
        decoded.close()

    final_path = output_dir / settings.video.output_filename
    concatenate_clips(clips, final_path, work)

    from src.errors import file_size_mb

    LOGGER.info(
        "Wrote %s (%.1f MB, %d panel(s))",
        final_path,
        file_size_mb(final_path),
        len(clips),
    )
    return final_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--validate",
        action="store_true",
        help="check config and input files, then exit without rendering",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=ROOT / "input",
        help="directory holding exactly one .cbz and one .txt (default: ./input)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config.yaml",
        help="path to config.yaml (default: ./config.yaml)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    output_dir = ROOT / "output"
    log_path = configure_logging(output_dir)
    LOGGER.info("Logging to %s", log_path)

    try:
        settings = load_settings(args.config)
        pages, panels = validate(settings, args.input_dir)
        if args.validate:
            LOGGER.info("Validation-only run finished.")
            return 0
        render(settings, pages, panels, output_dir)
        LOGGER.info("Done.")
        return 0
    except (PipelineError, CbzError, ValueError) as exc:
        LOGGER.error("%s", exc)
        return 1
    except Exception:  # pragma: no cover - unexpected programming error
        LOGGER.exception("Unexpected failure")
        return 1


if __name__ == "__main__":
    sys.exit(main())
