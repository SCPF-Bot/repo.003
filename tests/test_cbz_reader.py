"""Tests for CBZ page extraction."""

from __future__ import annotations

import pytest

from src.cbz_reader import CbzError, extract_pages, natural_sort_key


def test_extracts_pages_in_natural_order(make_cbz, make_image, tmp_path):
    cbz = make_cbz(
        {
            "chapter/page1.jpg": make_image("white"),
            "chapter/page10.jpg": make_image("gray"),
            "chapter/page2.jpg": make_image("black"),
        }
    )
    pages = extract_pages(cbz, tmp_path / "pages")

    assert [page.source_name for page in pages] == [
        "chapter/page1.jpg",
        "chapter/page2.jpg",
        "chapter/page10.jpg",
    ]
    assert all(page.path.exists() for page in pages)
    assert [page.path.name for page in pages] == [
        "page_0001.png",
        "page_0002.png",
        "page_0003.png",
    ]


def test_ignores_macos_resource_forks(make_cbz, make_image, tmp_path):
    """macOS 'Compress' adds __MACOSX entries that used to abort the whole run."""
    cbz = make_cbz(
        {
            "chapter/page 01.jpg": make_image("white"),
            "chapter/page 02.jpg": make_image("gray"),
            "__MACOSX/chapter/._page 01.jpg": b"\x00\x05\x16\x07not-an-image",
        }
    )
    pages = extract_pages(cbz, tmp_path / "pages")
    assert len(pages) == 2


def test_ignores_dotfiles_and_non_images(make_cbz, make_image, tmp_path):
    cbz = make_cbz(
        {
            "001.jpg": make_image("white"),
            "ComicInfo.xml": b"<ComicInfo/>",
            ".hidden.jpg": make_image("gray"),
            "thumb.jpg.txt": b"not an image",
        }
    )
    pages = extract_pages(cbz, tmp_path / "pages")
    assert [page.source_name for page in pages] == ["001.jpg"]


def test_undecodable_entry_is_skipped_not_fatal(make_cbz, make_image, tmp_path):
    """One bad entry should cost that entry, not the chapter."""
    cbz = make_cbz({"001.jpg": make_image("white"), "002.jpg": b"garbage", "003.jpg": make_image("black")})
    pages = extract_pages(cbz, tmp_path / "pages")
    assert [page.source_name for page in pages] == ["001.jpg", "003.jpg"]


def test_cover_named_with_letters_sorts_before_numbered_pages(make_cbz, make_image, tmp_path):
    """Mixed alpha/numeric names used to raise TypeError from the sort key."""
    cbz = make_cbz({"cover.jpg": make_image("white"), "001.jpg": make_image("gray")})
    pages = extract_pages(cbz, tmp_path / "pages")
    assert [page.source_name for page in pages] == ["001.jpg", "cover.jpg"]


def test_empty_archive_is_rejected(make_cbz, tmp_path):
    cbz = make_cbz({"ComicInfo.xml": b"<ComicInfo/>"})
    with pytest.raises(CbzError, match="no supported page images"):
        extract_pages(cbz, tmp_path / "pages")


def test_non_zip_file_gives_actionable_error(tmp_path):
    path = tmp_path / "chapter.cbz"
    path.write_text("version https://git-lfs.github.com/spec/v1", encoding="utf-8")

    with pytest.raises(CbzError) as excinfo:
        extract_pages(path, tmp_path / "pages")
    assert "Git LFS" in str(excinfo.value)


def test_pages_are_written_as_lossless_png(make_cbz, make_image, tmp_path):
    from PIL import Image

    cbz = make_cbz({"001.jpg": make_image("white")})
    page = extract_pages(cbz, tmp_path / "pages")[0]
    with Image.open(page.path) as image:
        assert image.format == "PNG"


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (["page10.jpg", "page9.jpg"], ["page9.jpg", "page10.jpg"]),
        (["a1.jpg", "2.jpg"], ["2.jpg", "a1.jpg"]),
        (["PAGE2.JPG", "page1.jpg"], ["page1.jpg", "PAGE2.JPG"]),
    ],
)
def test_natural_sort_key(name_only, names, expected):
    assert sorted(names, key=natural_sort_key) == expected


@pytest.fixture
def name_only():
    return None
