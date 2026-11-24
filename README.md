# Manhwa Narrator

Turn a CBZ chapter plus a manually prepared narration TXT into a cinematic,
portrait (9:16) narrated MP4 using GitHub Actions, Kokoro-82M, and FFmpeg.

**Important:** this repository does not analyze artwork or write narration.
Prepare the narration in ChatGPT first, then commit the CBZ and TXT input pair.

## Workflow

1. Upload a CBZ chapter to ChatGPT and ask for narration covering every panel.
2. Have ChatGPT produce a TXT file in the format below, including crop coordinates.
3. Put exactly one `.cbz` and one `.txt` file in `input/`.
4. Commit and push. GitHub Actions runs automatically when `input/**` changes.
5. Download `narrated-manhwa-video` from the successful Actions run's Artifacts.

You can also start a run from **Actions → Generate narrated manhwa video →
Run workflow**.

## Repository layout

```text
.github/workflows/generate-video.yml  GitHub Actions automation
input/                                Chapter CBZ + narration TXT go here
examples/narration-template.txt      TXT format example
src/cbz_reader.py                    CBZ page extraction
src/narration_parser.py               TXT validation and parsing
src/tts_engine.py                     Kokoro-82M narration audio
src/video_maker.py                    Portrait panel clips and MP4 assembly
scripts/run_pipeline.py                Pipeline entry point
config.yaml                            Voice and render settings
requirements.txt                       Python dependencies
output/                                Generated MP4 and log (ignored by Git)
```

## Narration TXT format

Every panel must have a page number, panel number, normalized crop rectangle,
and narration text:

```text
[PAGE 001]
[PANEL 001]
CROP: 0.00,0.00,0.50,0.33
NARRATION: The warrior opens his eyes.

[PANEL 002]
CROP: 0.50,0.00,0.50,0.33
NARRATION: A shadow moves behind him.
```

`CROP` is `x,y,width,height`, each from 0 to 1, measured relative to the
original page. The origin is the top-left corner. For example, `0,0,0.5,1`
selects the left half of a page. Coordinates must stay inside the page.

The sample file in `examples/narration-template.txt` is only a format example;
its narration and crops are not intended for your chapter. Panel crops must be
prepared for the actual artwork. Include every panel in the intended reading
order. The renderer does not perform panel detection.

## Settings

Edit `config.yaml`:

- `voice.voice`: Kokoro voice identifier (default `af_heart`)
- `voice.lang_code`: Kokoro language code (default `a`, American English)
- `voice.speed`: speech speed multiplier
- `video.tail_seconds`: brief visual hold after narration audio
- `video.output_filename`: output MP4 filename

The current renderer creates a blurred, darkened full-screen background from
each panel, with the complete panel fitted sharply in the center. This avoids
cropping off panel content in portrait output. Audio is generated per panel and
clips are concatenated in narration order.

## Local run (optional)

Requires Python 3.11+, FFmpeg, and espeak-ng.

```bash
sudo apt-get install ffmpeg espeak-ng libsndfile1
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_pipeline.py
```

The final video is written to `output/narrated-manhwa.mp4`.

## GitHub notes

- Use a **private repository** unless you have the rights to publish the CBZ.
- GitHub blocks ordinary Git files larger than 100 MB. Use Git LFS or another
  storage approach for large chapters; Git LFS usage may have separate quotas.
- GitHub-hosted runners are CPU-based. Kokoro model setup and synthesis can be
  slow for long chapters. The first run also downloads model assets.
- The workflow uploads the MP4 as a 14-day artifact and logs as a 7-day artifact.
- The workflow expects exactly one CBZ and one TXT in `input/` per run.

## Troubleshooting

Open the failed Actions run and inspect the `pipeline-logs` artifact. Common
input errors include missing page/panel headers, missing crop coordinates,
invalid normalized coordinates, a page number beyond the CBZ page count, or
more than one CBZ/TXT pair in `input/`.

## License and content

The code is MIT-licensed. That license does not grant rights to any manga,
manhwa, artwork, or narration text you add. Only upload or distribute content
you are authorized to use.
