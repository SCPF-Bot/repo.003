"""Turn panel crops and narration audio into a portrait MP4."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from src.config import VideoConfig
from src.errors import PipelineError, run_command

LOGGER = logging.getLogger(__name__)

#: Only real newlines separate ffmpeg's concat list entries. Using
#: ``read_text().splitlines()`` semantics would be fine, but writing explicit
#: ``\n`` keeps Windows checkouts from producing ``\r`` that ffmpeg mis-reads.
_LINE_END = "\n"

#: Aspect-ratio sanity bound for a crop, in pixels, so a misplaced decimal
#: point cannot ask Pillow for a gigapixel intermediate.
_MAX_CROP_PIXELS = 80_000_000


class DecodedPages:
    """Small cache of decoded page images.

    A webtoon page can be 800x8000 and have a dozen panels; re-decoding it for
    every panel used to cost ~0.15s and a fresh multi-megabyte buffer each
    time. Holding only the page currently being sliced keeps memory bounded.
    """

    def __init__(self) -> None:
        self._path: Path | None = None
        self._image: Image.Image | None = None

    def get(self, page_path: Path) -> Image.Image:
        if self._path != page_path:
            self.close()
            with Image.open(page_path) as image:
                self._image = image.convert("RGB")
            self._path = page_path
        assert self._image is not None
        return self._image

    def close(self) -> None:
        if self._image is not None:
            self._image.close()
        self._image = None
        self._path = None


def crop_panel(
    page: Image.Image,
    crop: tuple[float, float, float, float],
    label: str = "panel",
) -> Image.Image:
    """Cut a normalized crop out of an already-decoded page."""

    x, y, width, height = crop
    left, top = round(x * page.width), round(y * page.height)
    right, bottom = round((x + width) * page.width), round((y + height) * page.height)

    # Normalized coordinates can round down to nothing on small pages.
    right = min(page.width, max(left + 1, right))
    bottom = min(page.height, max(top + 1, bottom))
    left = min(left, right - 1)
    top = min(top, bottom - 1)

    if (right - left) * (bottom - top) > _MAX_CROP_PIXELS:
        raise PipelineError(
            f"{label}: crop resolves to {(right - left) * (bottom - top):,} pixels, "
            f"which exceeds the {_MAX_CROP_PIXELS:,} safety limit."
        )
    return page.crop((left, top, right, bottom))


def make_panel_frame(panel_image: Image.Image, output_path: Path, video: VideoConfig) -> Path:
    """Render the cinematic portrait frame: blurred background + sharp panel.

    Written as ``.png`` so the frame is not JPEG-compressed a second time
    before H.264 encoding; line art shows those artifacts badly.
    """

    width, height = video.width, video.height
    background = ImageOps.fit(panel_image, (width, height), method=Image.Resampling.LANCZOS)
    if video.background_blur > 0:
        background = background.filter(ImageFilter.GaussianBlur(video.background_blur))
    if video.background_darken > 0:
        black = Image.new("RGB", background.size, (0, 0, 0))
        background = Image.blend(background, black, video.background_darken)

    inset_x = max(24, round(width * 0.032))
    inset_y = max(48, round(height * 0.047))
    foreground = ImageOps.contain(
        panel_image,
        (max(1, width - inset_x), max(1, height - inset_y)),
        method=Image.Resampling.LANCZOS,
    )

    offset = ((width - foreground.width) // 2, (height - foreground.height) // 2)
    background.paste(foreground, offset)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    background.save(output_path, format="PNG", optimize=True)
    background.close()
    foreground.close()
    return output_path


def render_clip(
    frame_path: Path,
    audio_path: Path,
    duration: float,
    output_path: Path,
    video: VideoConfig,
) -> Path:
    """Encode one panel: a still frame held for ``duration`` with its narration.

    Two details matter and were both wrong before:

    * ``-shortest`` is deliberately absent. It used to end the clip when the
      audio stream finished, silently discarding ``tail_seconds`` (and, with
      AAC priming at the tail, part of the narration too).
    * ``apad`` pads the audio to match the video length. Clips are stitched
      with stream copy, so unequal stream lengths would desynchronise every
      clip after the first.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(frame_path),
        "-i", str(audio_path),
        "-t", f"{duration:.3f}",
        "-r", str(video.fps), "-fps_mode", "cfr",
        "-vf", f"scale={video.width}:{video.height}:flags=lanczos,format=yuv420p",
        "-pix_fmt", "yuv420p",
        "-color_range", "tv",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-af", "apad",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "1",
        str(output_path),
    ]
    run_command(command, description=f"FFmpeg clip render ({output_path.name})")
    return output_path


def _concat_line(path: Path) -> str:
    """Escape a path for ffmpeg's concat demuxer.

    The demuxer uses single-quoted strings in which ``'`` must be written as
    ``'\\''``. Without this, a filename containing an apostrophe (very common:
    ``Ch. 1 - It's Over``) corrupts the manifest.
    """

    escaped = str(path.resolve()).replace("'", "'\\''")
    return f"file '{escaped}'{_LINE_END}"


def concatenate_clips(clips: list[Path], output_path: Path, work_dir: Path) -> Path:
    """Join the per-panel clips into the final MP4.

    Video is stream-copied (fast, no generation loss); audio is re-encoded
    because concatenating independently encoded AAC streams leaves
    non-monotonic timestamps that ffmpeg then "fixes" by corrupting them.
    """

    if not clips:
        raise PipelineError("No clips were rendered; nothing to concatenate.")

    manifest = work_dir / "concat.txt"
    manifest.write_text("".join(_concat_line(clip) for clip in clips), encoding="utf-8")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(manifest),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "1",
        "-movflags", "+faststart",
        str(output_path),
    ]
    run_command(command, description="FFmpeg final assembly")
    return output_path
