from pathlib import Path
import logging
import shutil
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cbz_reader import extract_pages
from src.narration_parser import parse_narration
from src.tts_engine import KokoroTTS
from src.video_maker import crop_panel, make_panel_frame, render_clip, concatenate_clips


def main():
    output = ROOT / "output"
    work = output / "work"
    output.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=output / "pipeline.log", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger().addHandler(console)

    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    input_dir = ROOT / "input"
    cbz_files = sorted(input_dir.glob("*.cbz"))
    txt_files = sorted(input_dir.glob("*.txt"))
    if len(cbz_files) != 1 or len(txt_files) != 1:
        raise RuntimeError(
            f"Expected exactly one .cbz and one narration .txt in input/. "
            f"Found {len(cbz_files)} CBZ and {len(txt_files)} TXT files."
        )

    logging.info("Reading CBZ: %s", cbz_files[0].name)
    pages = extract_pages(cbz_files[0], work / "pages")
    panels = parse_narration(txt_files[0])

    for panel in panels:
        if panel.page_number < 1 or panel.page_number > len(pages):
            raise ValueError(f"Page {panel.page_number} is outside the CBZ ({len(pages)} pages).")

    voice_cfg = config["voice"]
    tts = KokoroTTS(
        voice=voice_cfg["voice"], lang_code=voice_cfg["lang_code"],
        speed=float(voice_cfg.get("speed", 1.0))
    )

    clips = []
    for index, panel in enumerate(panels, 1):
        logging.info("Rendering panel %d/%d (page %d, panel %d)",
                     index, len(panels), panel.page_number, panel.panel_number)
        panel_image = crop_panel(pages[panel.page_number - 1], panel.crop)
        frame_path = work / "frames" / f"panel_{index:04d}.jpg"
        make_panel_frame(panel_image, frame_path)

        audio_path = work / "audio" / f"panel_{index:04d}.wav"
        duration = tts.synthesize(panel.narration, audio_path)
        duration += float(config["video"].get("tail_seconds", 0.35))

        clip_path = work / "clips" / f"clip_{index:04d}.mp4"
        render_clip(frame_path, audio_path, duration, clip_path)
        clips.append(clip_path)

    name = config["video"].get("output_filename", "narrated-manhwa.mp4")
    final_path = output / name
    concatenate_clips(clips, final_path, work)
    logging.info("Finished: %s", final_path)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Pipeline failed")
        raise
