import zipfile
from pathlib import Path
from PIL import Image
from io import BytesIO


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def extract_pages(cbz_path: Path, work_dir: Path) -> list[Path]:
    work_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    with zipfile.ZipFile(cbz_path) as archive:
        entries = sorted(
            (n for n in archive.namelist()
             if Path(n).suffix.lower() in IMAGE_EXTENSIONS and not n.endswith("/")),
            key=lambda s: [int(t) if t.isdigit() else t.lower()
                           for t in __import__("re").split(r"(\d+)", s)]
        )
        if not entries:
            raise ValueError("The CBZ archive contains no supported page images.")
        for index, name in enumerate(entries, 1):
            data = archive.read(name)
            try:
                image = Image.open(BytesIO(data)).convert("RGB")
            except Exception as exc:
                raise ValueError(f"Could not decode CBZ page {name}: {exc}") from exc
            target = work_dir / f"page_{index:04d}.jpg"
            image.save(target, quality=95)
            pages.append(target)
    return pages
