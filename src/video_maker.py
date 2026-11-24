from pathlib import Path
import subprocess
from PIL import Image, ImageOps, ImageFilter
import numpy as np


WIDTH, HEIGHT, FPS = 1080, 1920, 30


def crop_panel(page_path: Path, crop: tuple[float, float, float, float]) -> Image.Image:
    image = Image.open(page_path).convert("RGB")
    x, y, w, h = crop
    left, top = round(x * image.width), round(y * image.height)
    right, bottom = round((x + w) * image.width), round((y + h) * image.height)
    right, bottom = max(left + 1, right), max(top + 1, bottom)
    return image.crop((left, top, right, bottom))


def make_panel_frame(panel_image: Image.Image, output_path: Path):
    # Cinematic portrait treatment: blurred full-frame background + sharp contained panel.
    background = ImageOps.fit(panel_image, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
    background = background.filter(ImageFilter.GaussianBlur(32))
    background = Image.blend(background, Image.new("RGB", background.size, (0, 0, 0)), 0.38)
    foreground = ImageOps.contain(panel_image, (WIDTH - 70, HEIGHT - 180), method=Image.Resampling.LANCZOS)
    x = (WIDTH - foreground.width) // 2
    y = (HEIGHT - foreground.height) // 2
    background.paste(foreground, (x, y))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    background.save(output_path, quality=94)


def render_clip(frame_path: Path, audio_path: Path, duration: float, output_path: Path):
    command = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(frame_path), "-i", str(audio_path),
        "-t", f"{duration:.3f}", "-r", str(FPS),
        "-vf", f"scale={WIDTH}:{HEIGHT},format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-shortest", str(output_path)
    ]
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def concatenate_clips(clips: list[Path], output_path: Path, work_dir: Path):
    manifest = work_dir / "concat.txt"
    manifest.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in clips), encoding="utf-8")
    command = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest),
        "-c", "copy", "-movflags", "+faststart", str(output_path)
    ]
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
