"""Parse and validate a narration TXT file.

The file format is deliberately small::

    [PAGE 001]
    [PANEL 001]
    CROP: 0.00,0.00,0.50,0.33
    NARRATION: The warrior opens his eyes.

Every panel needs exactly one ``CROP`` and one ``NARRATION`` directive.
Directives are matched case-insensitively, but a line that *looks* like a
directive and does not parse is rejected with the line number instead of
being silently folded into the narration (which used to make TTS read
"CR0P: ..." out loud).

Narration may wrap across several lines; continuation lines are joined with
a single space.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.models import Panel

PAGE_RE = re.compile(r"^\[PAGE\s+(?P<number>\d+)\]$", re.IGNORECASE)
PANEL_RE = re.compile(r"^\[PANEL\s+(?P<number>\d+)\]$", re.IGNORECASE)
CROP_RE = re.compile(
    r"^CROP:\s*(?P<x>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
    r"\s*,\s*(?P<y>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
    r"\s*,\s*(?P<w>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
    r"\s*,\s*(?P<h>[+-]?(?:\d+(?:\.\d*)?|\.\d+))$",
    re.IGNORECASE,
)
NARRATION_RE = re.compile(r"^NARRATION:\s*(?P<text>.*)$", re.IGNORECASE)

#: Anything that starts with a directive keyword is suspicious enough to
#: report when it fails to parse exactly.
DIRECTIVE_LIKE_RE = re.compile(r"^\s*(?:PAGE|PANEL|CROP|NARRATION)\b", re.IGNORECASE)

#: A line shaped like ``KEYWORD: value`` where the keyword is shouting
#: (``CR0P:``, ``NARRATON:``, ``CROP :``) is almost certainly a mistyped
#: directive rather than prose. Ordinary narration does not start that way,
#: and letting it through means the TTS engine reads the directive aloud.
SHOUTED_KEYWORD_RE = re.compile(r"^[A-Z0-9][A-Z0-9_]{2,12}\s*:")

#: A crop smaller than this (as a fraction of the page) is almost certainly a
#: typo and would render as a smeared strip of a few pixels.
MIN_CROP_SIZE = 0.01

#: Floating point slack when checking that a crop stays inside the page.
_EPSILON = 1e-6


@dataclass
class ParseReport:
    """Parsed panels plus non-fatal observations worth surfacing."""

    panels: list[Panel]
    warnings: list[str]


def _error(line_number: int, message: str) -> ValueError:
    return ValueError(f"Line {line_number}: {message}")


def _parse_crop(line: str, line_number: int) -> tuple[float, float, float, float]:
    match = CROP_RE.match(line)
    if match is None:
        raise _error(
            line_number,
            f"malformed CROP line: {line!r}. "
            "Expected 'CROP: x,y,width,height' with plain decimal numbers.",
        )
    x, y, w, h = (float(match.group(name)) for name in ("x", "y", "w", "h"))

    if x < 0 or y < 0 or w <= 0 or h <= 0:
        raise _error(
            line_number,
            f"CROP must use a non-negative x/y and a positive width/height, got {line!r}.",
        )
    if x + w > 1 + _EPSILON or y + h > 1 + _EPSILON:
        raise _error(
            line_number,
            f"CROP extends past the page edge (x+width={x + w:.4f}, "
            f"y+height={y + h:.4f}; both must be <= 1.0).",
        )
    if w < MIN_CROP_SIZE or h < MIN_CROP_SIZE:
        raise _error(
            line_number,
            f"CROP is {w:.4f}x{h:.4f} of the page, smaller than the "
            f"{MIN_CROP_SIZE} minimum. Check for a misplaced decimal point.",
        )
    return (x, y, w, h)


def _read_lines(path: Path) -> list[str]:
    """Read the file and split on real newlines only.

    ``str.splitlines`` also splits on U+2028/U+2029/U+0085 and friends, which
    can appear inside narration text (copy/paste, LLM output) and would
    silently shred a line into fragments that may look like directives.
    """
    return path.read_text(encoding="utf-8-sig").split("\n")


def parse_narration(path: Path) -> list[Panel]:
    """Parse ``path`` and return its panels, ordered as they appear."""

    return parse_narration_with_report(path).panels


def parse_narration_with_report(path: Path) -> ParseReport:
    """Parse ``path``, returning panels and non-fatal warnings."""

    panels: list[Panel] = []
    warnings: list[str] = []

    page_number: int | None = None
    panel_number: int | None = None
    crop: tuple[float, float, float, float] | None = None
    narration_lines: list[str] = []
    narration_started = False
    panel_line = 0
    seen_pages: list[int] = []
    seen_panels_for_page: list[int] = []

    def flush() -> None:
        nonlocal panel_number, crop, narration_lines, narration_started, panel_line
        if panel_number is None:
            return
        narration = " ".join(part.strip() for part in narration_lines).strip()
        if crop is None:
            raise _error(panel_line, f"[PANEL {panel_number}] has no CROP line.")
        if not narration:
            raise _error(panel_line, f"[PANEL {panel_number}] has no NARRATION text.")
        panels.append(Panel(int(page_number), panel_number, narration, crop, panel_line))
        panel_number = None
        crop = None
        narration_lines = []
        narration_started = False
        panel_line = 0

    for index, raw in enumerate(_read_lines(path), start=1):
        line = raw.strip()

        if not line or line.startswith("#"):
            continue

        match = PAGE_RE.match(line)
        if match:
            flush()
            number = int(match.group("number"))
            if number < 1:
                raise _error(index, "[PAGE] numbers start at 1.")
            if seen_pages and number in seen_pages:
                raise _error(index, f"page {number} appears more than once.")
            if seen_pages and number < seen_pages[-1]:
                raise _error(
                    index,
                    f"page {number} appears after page {seen_pages[-1]}. "
                    "Pages must be listed in ascending order.",
                )
            seen_pages.append(number)
            page_number = number
            seen_panels_for_page = []
            continue

        match = PANEL_RE.match(line)
        if match:
            flush()
            if page_number is None:
                raise _error(index, "a [PAGE n] header must appear before any [PANEL n].")
            number = int(match.group("number"))
            if number < 1:
                raise _error(index, "[PANEL] numbers start at 1.")
            expected = (seen_panels_for_page[-1] + 1) if seen_panels_for_page else 1
            if number != expected:
                raise _error(
                    index,
                    f"expected [PANEL {expected:03d}] after "
                    f"[PANEL {seen_panels_for_page[-1]:03d}] on page {page_number}, "
                    f"found [PANEL {number:03d}]. Panels must be numbered "
                    "sequentially from 1 with no gaps.",
                )
            seen_panels_for_page.append(number)
            panel_number = number
            panel_line = index
            continue

        match = CROP_RE.match(line)
        if match:
            if panel_number is None:
                raise _error(index, "CROP line appears outside a [PANEL n] block.")
            if crop is not None:
                raise _error(index, f"[PANEL {panel_number}] has more than one CROP line.")
            crop = _parse_crop(line, index)
            continue

        match = NARRATION_RE.match(line)
        if match:
            if panel_number is None:
                raise _error(index, "NARRATION line appears outside a [PANEL n] block.")
            narration_lines.append(match.group("text"))
            narration_started = True
            continue

        if DIRECTIVE_LIKE_RE.match(line):
            raise _error(
                index,
                f"line looks like a directive but does not parse: {line!r}. "
                "Valid forms are '[PAGE 001]', '[PANEL 001]', "
                "'CROP: x,y,width,height' and 'NARRATION: text'. "
                "Check for a lowercase keyword, a space before the colon, "
                "or a mistyped character.",
            )

        if panel_number is None:
            raise _error(index, f"unexpected text outside any [PANEL n] block: {line!r}")

        # Check the more specific diagnostic first: a mistyped directive is
        # far more likely than stray prose, and saying so saves debugging time.
        if SHOUTED_KEYWORD_RE.match(line) and not narration_started:
            raise _error(
                index,
                f"line looks like a mistyped directive and would be read aloud "
                f"by the narrator: {line!r}. Valid forms are '[PAGE 001]', "
                "'[PANEL 001]', 'CROP: x,y,width,height' and 'NARRATION: text'.",
            )

        if not narration_started:
            raise _error(
                index,
                f"unexpected text before the NARRATION line of [PANEL {panel_number}]: "
                f"{line!r}. Every content line must follow NARRATION:.",
            )

        if SHOUTED_KEYWORD_RE.match(line):
            raise _error(
                index,
                f"line looks like a mistyped directive and would be read aloud "
                f"by the narrator: {line!r}. Valid forms are '[PAGE 001]', "
                "'[PANEL 001]', 'CROP: x,y,width,height' and 'NARRATION: text'.",
            )

        narration_lines.append(line)

    flush()

    if not panels:
        raise ValueError(f"No panels found in {path}. Check the TXT structure.")

    highest_page = max(panel.page_number for panel in panels)
    covered = {panel.page_number for panel in panels}
    missing = [number for number in range(1, highest_page + 1) if number not in covered]
    if missing:
        warnings.append(
            "narration TXT has no panels for page(s) "
            + ", ".join(str(number) for number in missing)
            + f" but references page {highest_page}."
        )

    return ParseReport(panels=panels, warnings=warnings)
