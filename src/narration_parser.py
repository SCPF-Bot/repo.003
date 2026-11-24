import re
from pathlib import Path
from src.models import Panel

PAGE_RE = re.compile(r"^\[PAGE\s+(\d+)\]\s*$", re.I)
PANEL_RE = re.compile(r"^\[PANEL\s+(\d+)\]\s*$", re.I)
CROP_RE = re.compile(r"^CROP:\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*$", re.I)
NARRATION_RE = re.compile(r"^NARRATION:\s*(.*)$", re.I)


def parse_narration(path: Path) -> list[Panel]:
    text = path.read_text(encoding="utf-8-sig")
    panels = []
    page = panel_no = None
    crop = None
    narration_lines = []

    def flush():
        nonlocal crop, narration_lines, panel_no, page
        if panel_no is None:
            return
        narration = " ".join(line.strip() for line in narration_lines).strip()
        if not narration:
            raise ValueError(f"Page {page}, panel {panel_no}: missing NARRATION text.")
        if crop is None:
            raise ValueError(f"Page {page}, panel {panel_no}: missing CROP coordinates.")
        x, y, w, h = crop
        if any(v < 0 or v > 1 for v in crop) or w <= 0 or h <= 0 or x + w > 1.00001 or y + h > 1.00001:
            raise ValueError(f"Page {page}, panel {panel_no}: CROP must be normalized x,y,w,h in the 0..1 range.")
        panels.append(Panel(page, panel_no, narration, crop))
        crop, narration_lines, panel_no = None, [], None

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = PAGE_RE.match(line)
        if match:
            flush()
            page = int(match.group(1))
            continue
        match = PANEL_RE.match(line)
        if match:
            flush()
            if page is None:
                raise ValueError("A [PAGE NNN] header must appear before each panel.")
            panel_no = int(match.group(1))
            continue
        if panel_no is None:
            raise ValueError(f"Unexpected content outside a panel: {line}")
        match = CROP_RE.match(line)
        if match:
            crop = tuple(float(match.group(i)) for i in range(1, 5))
            continue
        match = NARRATION_RE.match(line)
        if match:
            narration_lines.append(match.group(1))
            continue
        narration_lines.append(line)

    flush()
    if not panels:
        raise ValueError("No panels were found in the narration TXT.")
    keys = [(p.page_number, p.panel_number) for p in panels]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate page/panel identifiers found.")
    return panels
