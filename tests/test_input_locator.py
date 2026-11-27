"""Tests for locating the single CBZ/TXT input pair."""

from __future__ import annotations

import pytest

from src.errors import PipelineError
from src.input_locator import find_input_pair


def _touch(directory, *names):
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_bytes(b"placeholder")


def test_finds_the_pair(tmp_path):
    _touch(tmp_path, "chapter.cbz", "chapter.txt")
    pair = find_input_pair(tmp_path)
    assert pair.cbz.name == "chapter.cbz"
    assert pair.narration.name == "chapter.txt"


def test_repository_readme_is_not_mistaken_for_narration(tmp_path):
    """input/README.txt used to make every run fail with 'Found 2 TXT files'."""
    _touch(tmp_path, "chapter.cbz", "chapter.txt", "README.txt", ".gitkeep")
    pair = find_input_pair(tmp_path)
    assert pair.narration.name == "chapter.txt"


@pytest.mark.parametrize("name", ["Chapter.CBZ", "Chapter.Cbz", "CHAPTER.cbz"])
def test_uppercase_archive_extension_is_accepted(tmp_path, name):
    """glob('*.cbz') is case-sensitive and missed what Windows produces."""
    _touch(tmp_path, name, "Chapter.TXT")
    pair = find_input_pair(tmp_path)
    assert pair.cbz.name == name
    assert pair.narration.name == "Chapter.TXT"


def test_zip_archive_is_accepted(tmp_path):
    _touch(tmp_path, "chapter.zip", "chapter.txt")
    assert find_input_pair(tmp_path).cbz.name == "chapter.zip"


def test_two_archives_are_rejected_and_named(tmp_path):
    _touch(tmp_path, "chapter-1.cbz", "chapter-2.cbz", "chapter.txt")
    with pytest.raises(PipelineError) as excinfo:
        find_input_pair(tmp_path)
    message = str(excinfo.value)
    assert "chapter-1.cbz" in message and "chapter-2.cbz" in message


def test_two_narrations_are_rejected(tmp_path):
    _touch(tmp_path, "chapter.cbz", "a.txt", "b.txt")
    with pytest.raises(PipelineError, match="exactly one"):
        find_input_pair(tmp_path)


def test_missing_files_are_reported_clearly(tmp_path):
    with pytest.raises(PipelineError, match="Found narration files: none"):
        find_input_pair(tmp_path)


def test_missing_directory_is_reported(tmp_path):
    with pytest.raises(PipelineError, match="does not exist"):
        find_input_pair(tmp_path / "nope")


def test_subdirectories_are_ignored(tmp_path):
    _touch(tmp_path, "chapter.cbz", "chapter.txt")
    (tmp_path / "archive.cbz").mkdir()
    assert find_input_pair(tmp_path).cbz.name == "chapter.cbz"
