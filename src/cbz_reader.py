"""Extract page images from a CBZ (ZIP) archive."""

from __future__ import annotations

import logging
import re
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from src.models import Page

LOGGER = logging.getLogger(__name__)

#: Formats we accept. Pillow can decode more (AVIF, TIFF, ...) but silently
#: switching page sets between runs makes ``[PAGE n]`` unreliable, so the
#: list is explicit and reported when an entry is skipped.
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp"})

#: Archives written by macOS "Compress" contain resource-fork entries that
#: carry an image extension but are not images. They must never count as pages.
IGNORED_TOP_LEVEL = frozenset({"__MACOSX"})


class CbzError(ValueError):
    """Raised when a CBZ archive cannot be turned into pages."""


def natural_sort_key(name: str) -> list[object]:
    """Sort ``page2`` before ``page10`` without comparing ints to strings."""
    return [
        (0, int(part), "") if part.isdigit() else (1, 0, part.casefold())
        for part in re.split(r"(\d+)", name)
        if part
    ]


def _is_page_candidate(name: str) -> bool:
    if name.endswith("/"):
        return False
    path = Path(name)
    if any(part in IGNORED_TOP_LEVEL or part.startswith(".") for part in path.parts):
        return False
    return path.suffix.lower() in IMAGE_EXTENSIONS


def extract_pages(cbz_path: Path, work_dir: Path) -> list[Page]:
    """Write every page image in ``cbz_path`` to ``work_dir``.

    Pages are ordered by natural sort of their path inside the archive, so
    ``chapter/page9.jpg`` sorts before ``chapter/page10.jpg``.
    """

    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        archive = zipfile.ZipFile(cbz_path)
    except zipfile.BadZipFile as exc:
        raise CbzError(
            f"{cbz_path.name} is not a readable ZIP/CBZ archive ({exc}). "
            "If this file is tracked with Git LFS, make sure the workflow "
            "checks it out with 'lfs: true'."
        ) from exc

    pages: list[Page] = []
    skipped: list[str] = []

    with archive:
        names = sorted(
            (name for name in archive.namelist() if _is_page_candidate(name)),
            key=natural_sort_key,
        )

        for name in names:
            data = archive.read(name)
            try:
                with Image.open(BytesIO(data)) as image:
                    converted = image.convert("RGB")
            except (UnidentifiedImageError, OSError) as exc:
                # Do not abort the whole chapter for one odd entry; report it
                # loudly so the page mapping stays explainable.
                skipped.append(f"{name} ({exc})")
                continue

            index = len(pages) + 1
            target = work_dir / f"page_{index:04d}.png"
            converted.save(target, format="PNG")
            pages.append(Page(path=target, source_name=name))

    if skipped:
        LOGGER.warning(
            "Skipped %d archive entr%s that could not be decoded as images:\n  %s",
            len(skipped),
            "y" if len(skipped) == 1 else "ies",
            "\n  ".join(skipped),
        )

    if not pages:
        raise CbzError(
            f"{cbz_path.name} contains no supported page images "
            f"(looked for {', '.join(sorted(IMAGE_EXTENSIONS))})."
        )

    LOGGER.info("Extracted %d page(s) from %s:", len(pages), cbz_path.name)
    for page in pages:
        LOGGER.info("  page %3d <- %s", pages.index(page) + 1, page.source_name)

    return pages
