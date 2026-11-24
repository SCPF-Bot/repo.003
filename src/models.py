from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Panel:
    page_number: int
    panel_number: int
    narration: str
    crop: tuple[float, float, float, float]  # normalized x, y, width, height
    image_path: Path | None = None
