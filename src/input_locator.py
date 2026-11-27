"""Locate the CBZ/TXT input pair for a run."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from src.errors import PipelineError

LOGGER = logging.getLogger(__name__)

#: Files the repository itself keeps in ``input/``. They are documentation,
#: not chapter material, and must never be mistaken for the narration TXT.
HOUSEKEEPING_FILES = frozenset({"readme.txt", "readme.md", ".gitkeep", ".gitignore"})

#: Multiple archives are worth naming rather than counting, but only up to a
#: point; keep error messages readable for large accidental dumps.
_MAX_LISTED = 10


@dataclass(frozen=True, slots=True)
class InputPair:
    cbz: Path
    narration: Path


def _describe(paths: list[Path], root: Path) -> str:
    if not paths:
        return "none"
    shown = [str(path.relative_to(root)) for path in paths[:_MAX_LISTED]]
    if len(paths) > _MAX_LISTED:
        shown.append(f"... and {len(paths) - _MAX_LISTED} more")
    return ", ".join(shown)


def find_input_pair(input_dir: Path) -> InputPair:
    """Return the single CBZ/TXT pair in ``input_dir``.

    Matching is case-insensitive because ``Chapter.CBZ`` is what Windows and
    macOS users produce by default, while ``glob("*.cbz")`` would silently
    find nothing.
    """

    if not input_dir.is_dir():
        raise PipelineError(f"Input directory does not exist: {input_dir}")

    cbz_files: list[Path] = []
    txt_files: list[Path] = []
    for path in sorted(input_dir.iterdir()):
        if not path.is_file():
            continue
        if path.name.casefold() in HOUSEKEEPING_FILES:
            continue
        suffix = path.suffix.casefold()
        if suffix == ".cbz" or suffix == ".zip":
            cbz_files.append(path)
        elif suffix == ".txt":
            txt_files.append(path)

    if len(cbz_files) != 1 or len(txt_files) != 1:
        raise PipelineError(
            "Expected exactly one chapter archive (.cbz) and one narration "
            f"file (.txt) in {input_dir}.\n"
            f"  Found archives: {_describe(cbz_files, input_dir)}\n"
            f"  Found narration files: {_describe(txt_files, input_dir)}\n"
            "Remove the extras and push again."
        )

    pair = InputPair(cbz=cbz_files[0], narration=txt_files[0])
    LOGGER.info("Input archive: %s", pair.cbz.name)
    LOGGER.info("Input narration: %s", pair.narration.name)
    return pair
