"""Shared data types for the narration pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Panel:
    """One narrated panel.

    ``crop`` is a normalized ``(x, y, width, height)`` rectangle in the
    ``0.0..1.0`` range, measured from the top-left of the source page.
    """

    page_number: int
    panel_number: int
    narration: str
    crop: tuple[float, float, float, float]
    line_number: int = 0

    @property
    def label(self) -> str:
        """Human-readable identifier used in log and error messages."""
        return f"page {self.page_number}, panel {self.panel_number}"


@dataclass(frozen=True, slots=True)
class Page:
    """An image extracted from a CBZ archive."""

    path: Path
    source_name: str
