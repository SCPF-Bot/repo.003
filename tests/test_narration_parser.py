"""Tests for the narration TXT parser.

Each case here maps to a defect found in review; the docstring names the
behaviour that regressed.
"""

from __future__ import annotations

import pytest

from src.narration_parser import parse_narration, parse_narration_with_report

VALID = """\
# A comment line is allowed.
[PAGE 001]
[PANEL 001]
CROP: 0.00,0.00,0.50,0.33
NARRATION: The warrior opens his eyes.

[PANEL 002]
CROP: 0.50,0.00,0.50,0.33
NARRATION: A shadow moves behind him.

[PAGE 002]
[PANEL 001]
CROP: 0.00,0.00,1.00,1.00
NARRATION: The city awakens.
"""


def test_parses_valid_file(write_txt):
    panels = parse_narration(write_txt(VALID))

    assert [(p.page_number, p.panel_number) for p in panels] == [(1, 1), (1, 2), (2, 1)]
    assert panels[0].narration == "The warrior opens his eyes."
    assert panels[0].crop == (0.0, 0.0, 0.5, 0.33)


def test_panels_need_no_blank_line_between_them(write_txt):
    panels = parse_narration(
        write_txt(
            "[PAGE 001]\n[PANEL 001]\nCROP: 0,0,0.5,1\nNARRATION: One.\n"
            "[PANEL 002]\nCROP: 0,0,0.5,1\nNARRATION: Two.\n"
        )
    )
    assert [p.narration for p in panels] == ["One.", "Two."]


def test_directives_are_case_insensitive(write_txt):
    panels = parse_narration(
        write_txt("[page 001]\n[panel 001]\ncrop: 0,0,0.5,1\nnarration: Lower case works.\n")
    )
    assert panels[0].narration == "Lower case works."


def test_utf8_bom_and_crlf(write_txt, tmp_path):
    path = tmp_path / "bom.txt"
    path.write_bytes(
        "\ufeff[PAGE 001]\r\n[PANEL 001]\r\nCROP: 0,0,0.5,1\r\nNARRATION: Bom survives.\r\n".encode()
    )
    assert parse_narration(path)[0].narration == "Bom survives."


def test_multiline_narration_is_joined(write_txt):
    panels = parse_narration(
        write_txt(
            "[PAGE 001]\n[PANEL 001]\nCROP: 0,0,0.5,1\n"
            "NARRATION: First part of a long\nsentence continues here.\n"
        )
    )
    assert panels[0].narration == "First part of a long sentence continues here."


def test_mistyped_crop_is_reported_not_narrated(write_txt):
    """A 'CR0P' typo used to end up in the audio track."""
    with pytest.raises(ValueError, match="mistyped directive"):
        parse_narration(
            write_txt(
                "[PAGE 001]\n[PANEL 001]\nCR0P: 0,0,0.5,1\nNARRATION: Second panel.\n"
            )
        )


def test_space_before_colon_is_reported(write_txt):
    """'NARRATION : text' used to be spoken verbatim by the TTS engine."""
    with pytest.raises(ValueError, match="looks like a directive"):
        parse_narration(
            write_txt("[PAGE 001]\n[PANEL 001]\nCROP: 0,0,0.5,1\nNARRATION : A warrior.\n")
        )


def test_text_before_narration_is_rejected(write_txt):
    with pytest.raises(ValueError, match="before the NARRATION line"):
        parse_narration(
            write_txt("[PAGE 001]\n[PANEL 001]\nStray prose.\nCROP: 0,0,0.5,1\nNARRATION: X.\n")
        )


@pytest.mark.parametrize(
    ("crop", "message"),
    [
        ("1..0,0,0.5,1", "looks like a directive"),
        ("-0.1,0,0.5,1", "non-negative"),
        ("0.7,0,0.5,1", "extends past the page edge"),
        ("0,0,0,1", "positive width/height"),
        ("0,0,0.0001,1", "smaller than"),
        ("0,0,0.5,1 extra", "looks like a directive"),
    ],
)
def test_invalid_crops_are_rejected_with_context(write_txt, crop, message):
    with pytest.raises(ValueError, match=message) as excinfo:
        parse_narration(
            write_txt(f"[PAGE 001]\n[PANEL 001]\nCROP: {crop}\nNARRATION: X.\n")
        )
    assert "Line 3" in str(excinfo.value)


def test_malformed_number_does_not_leak_bare_float_error(write_txt):
    """float('1..0') used to escape as a context-free ValueError."""
    with pytest.raises(ValueError) as excinfo:
        parse_narration(
            write_txt("[PAGE 001]\n[PANEL 001]\nCROP: 1..0,0,0.5,1\nNARRATION: X.\n")
        )
    assert "could not convert string to float" not in str(excinfo.value)


@pytest.mark.parametrize("crop", ["0,0,1,1", "0.5,0.5,0.5,0.5", "0.49,0,0.51,1.0"])
def test_crop_edge_cases_are_accepted(write_txt, crop):
    assert parse_narration(
        write_txt(f"[PAGE 001]\n[PANEL 001]\nCROP: {crop}\nNARRATION: X.\n")
    )


def test_missing_crop_is_rejected(write_txt):
    with pytest.raises(ValueError, match="no CROP"):
        parse_narration(write_txt("[PAGE 001]\n[PANEL 001]\nNARRATION: X.\n"))


def test_missing_narration_is_rejected(write_txt):
    with pytest.raises(ValueError, match="no NARRATION"):
        parse_narration(write_txt("[PAGE 001]\n[PANEL 001]\nCROP: 0,0,1,1\n"))


def test_duplicate_crop_is_rejected(write_txt):
    with pytest.raises(ValueError, match="more than one CROP"):
        parse_narration(
            write_txt(
                "[PAGE 001]\n[PANEL 001]\nCROP: 0,0,0.5,1\nCROP: 0,0,0.5,1\nNARRATION: X.\n"
            )
        )


def test_panel_before_page_is_rejected(write_txt):
    with pytest.raises(ValueError, match=r"\[PAGE n\] header"):
        parse_narration(write_txt("[PANEL 001]\nCROP: 0,0,1,1\nNARRATION: X.\n"))


def test_panel_gaps_are_rejected(write_txt):
    with pytest.raises(ValueError, match="numbered sequentially"):
        parse_narration(
            write_txt(
                "[PAGE 001]\n[PANEL 001]\nCROP: 0,0,0.5,1\nNARRATION: One.\n"
                "[PANEL 003]\nCROP: 0,0,0.5,1\nNARRATION: Three.\n"
            )
        )


def test_duplicate_page_numbers_are_rejected(write_txt):
    with pytest.raises(ValueError, match="more than once"):
        parse_narration(
            write_txt(
                "[PAGE 001]\n[PANEL 001]\nCROP: 0,0,0.5,1\nNARRATION: One.\n"
                "[PAGE 001]\n[PANEL 001]\nCROP: 0,0,0.5,1\nNARRATION: Again.\n"
            )
        )


def test_out_of_order_pages_are_rejected(write_txt):
    """Panels used to render in file order even when pages were swapped."""
    with pytest.raises(ValueError, match="ascending order"):
        parse_narration(
            write_txt(
                "[PAGE 002]\n[PANEL 001]\nCROP: 0,0,0.5,1\nNARRATION: Two.\n"
                "[PAGE 001]\n[PANEL 001]\nCROP: 0,0,0.5,1\nNARRATION: One.\n"
            )
        )


def test_unicode_line_separator_does_not_split_narration(write_txt):
    """str.splitlines() splits on U+2028; that used to shred narration text."""
    panels = parse_narration(
        write_txt(
            "[PAGE 001]\n[PANEL 001]\nCROP: 0,0,0.5,1\n"
            "NARRATION: Before the break\u2028after the break.\n"
        )
    )
    assert panels[0].narration == "Before the break\u2028after the break."


def test_page_gap_produces_a_warning(write_txt):
    report = parse_narration_with_report(
        write_txt(
            "[PAGE 001]\n[PANEL 001]\nCROP: 0,0,0.5,1\nNARRATION: One.\n"
            "[PAGE 004]\n[PANEL 001]\nCROP: 0,0,0.5,1\nNARRATION: Four.\n"
        )
    )
    assert len(report.panels) == 2
    assert any("page(s) 2, 3" in warning for warning in report.warnings)


def test_empty_file_is_rejected(write_txt):
    with pytest.raises(ValueError, match="No panels found"):
        parse_narration(write_txt("# only a comment\n"))


def test_records_line_numbers_for_error_messages(write_txt):
    panels = parse_narration(write_txt(VALID))
    assert panels[0].line_number == 3
    assert panels[1].line_number == 7


def test_panel_zero_is_rejected(write_txt):
    with pytest.raises(ValueError, match="start at 1"):
        parse_narration(
            write_txt("[PAGE 001]\n[PANEL 000]\nCROP: 0,0,0.5,1\nNARRATION: X.\n")
        )


def test_page_zero_is_rejected(write_txt):
    with pytest.raises(ValueError, match="start at 1"):
        parse_narration(write_txt("[PAGE 000]\n[PANEL 001]\nCROP: 0,0,0.5,1\nNARRATION: X.\n"))


def test_crop_outside_a_panel_is_rejected(write_txt):
    with pytest.raises(ValueError, match=r"outside a \[PANEL"):
        parse_narration(write_txt("[PAGE 001]\nCROP: 0,0,0.5,1\n"))


def test_narration_outside_a_panel_is_rejected(write_txt):
    with pytest.raises(ValueError, match=r"outside a \[PANEL"):
        parse_narration(write_txt("[PAGE 001]\nNARRATION: orphan text\n"))


def test_stray_prose_outside_a_panel_is_rejected(write_txt):
    with pytest.raises(ValueError, match="outside any"):
        parse_narration(write_txt("[PAGE 001]\nsome prose\n"))
