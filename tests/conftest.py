"""Shared fixtures: synthetic CBZ archives and narration TXTs."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def make_image() -> callable:
    """Return a factory producing in-memory JPEG bytes."""

    def _make(color: str = "white", size: tuple[int, int] = (400, 600)) -> bytes:
        buffer = io.BytesIO()
        Image.new("RGB", size, color).save(buffer, format="JPEG")
        return buffer.getvalue()

    return _make


@pytest.fixture
def make_cbz(tmp_path: Path, make_image: callable) -> callable:
    """Return a factory that writes a CBZ with the given entry names."""

    def _make(entries: dict[str, bytes], name: str = "chapter.cbz") -> Path:
        path = tmp_path / name
        with zipfile.ZipFile(path, "w") as archive:
            for entry_name, payload in entries.items():
                archive.writestr(entry_name, payload)
        return path

    return _make


@pytest.fixture
def write_txt(tmp_path: Path) -> callable:
    """Return a factory that writes a narration TXT."""

    def _write(text: str, name: str = "chapter.txt") -> Path:
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def sample_image_bytes(make_image: callable) -> bytes:
    return make_image()
