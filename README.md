# Manhwa Narrator

Turn a CBZ chapter plus a prepared narration TXT into a cinematic portrait
(9:16) narrated MP4 using GitHub Actions, [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)
and FFmpeg.

**This repository does not analyze artwork or write narration.** Prepare the
narration first (see [AI prompt for generating narration](docs/narration-prompt.md)),
then drop the CBZ and TXT pair into `input/`.

## Workflow

1. Produce a narration TXT for your chapter. [docs/narration-prompt.md](docs/narration-prompt.md)
   contains a copy-paste prompt that makes a chat model return the right format.
2. Put exactly one `.cbz` and one `.txt` file in `input/`.
   `input/README.txt` is repository documentation and is ignored by the pipeline.
3. Commit and push. The workflow runs whenever `input/**`, `src/**`,
   `scripts/**`, `config.yaml` or `requirements.txt` change.
4. Watch the run: a fast **Lint and unit tests** job runs first, then
   **Render video**.
5. Download `narrated-manhwa-video` from the **Artifacts** section of the run.

You can also start a run from **Actions → Generate narrated manhwa video → Run workflow**.

### Keeping chapters out of Git

Large or copyrighted chapters do not have to be committed. Two supported options:

- **Git LFS** — track `input/*.cbz` with LFS. The workflow checks out LFS files
  automatically (`lfs: true`).
- **Never commit them** — run the workflow manually in an environment that
  already has the files, or add them to a private fork that is not published.

The repository default is to *not* ignore `input/`, so a committed chapter
pair is picked up as expected. See `.gitignore` if you prefer to keep chapters
local.

## Repository layout

```text
.github/workflows/generate-video.yml  GitHub Actions automation (lint, test, render)
config.yaml                          Voice and render settings
docs/narration-prompt.md             Prompt for generating a narration TXT
examples/narration-template.txt      TXT format example
input/                               Chapter CBZ + narration TXT go here
scripts/run_pipeline.py              Pipeline entry point (--validate supported)
src/cbz_reader.py                    CBZ page extraction
src/config.py                        config.yaml loading and validation
src/errors.py                        Error types and FFmpeg invocation helpers
src/input_locator.py                 Finds the single CBZ/TXT pair
src/narration_parser.py              TXT validation and parsing
src/tts_engine.py                    Kokoro-82M narration audio
src/video_maker.py                   Portrait panel frames and MP4 assembly
tests/                               Unit and end-to-end smoke tests
output/                              Generated MP4 and log (ignored by Git)
```

## Narration TXT format

Every panel needs a page number, panel number, normalized crop rectangle and
narration text:

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
selects the left half of a page.

Format rules the parser enforces:

- `[PAGE n]` numbers are sequential from 1 and appear in ascending order.
- `[PANEL n]` numbers are sequential from 1 within each page.
- Each panel has exactly one `CROP` and at least one `NARRATION` line.
- `x + width <= 1` and `y + height <= 1`; `width` and `height` must be at least
  `0.01` of the page.
- Directive keywords are case-insensitive, but a line that *looks* like a
  directive and does not parse (`CR0P: …`, `NARRATION : …`) is an error rather
  than being read out loud.
- Narration may wrap over several lines; continuation lines are joined with a
  space.

`[PAGE n]` refers to the **n-th image extracted from the archive**, in natural
sort order of the file names inside the CBZ. The run log prints the full page
map (`page 3 <- chapter/003.jpg`) so a mismatch is easy to spot.

The sample file in `examples/narration-template.txt` is only a format example.
The renderer does not perform panel detection.

## Settings

Edit `config.yaml`:

| Key | Default | Meaning |
| --- | --- | --- |
| `voice.voice` | `af_heart` | Kokoro voice identifier |
| `voice.lang_code` | `a` | Kokoro language code (`a` = American English, `b` = British) |
| `voice.speed` | `1.0` | Speech speed multiplier (0.1–5.0) |
| `video.width` | `1080` | Output width in pixels (must be even) |
| `video.height` | `1920` | Output height in pixels (must be even) |
| `video.fps` | `30` | Frames per second |
| `video.tail_seconds` | `0.35` | How long a panel holds after its narration ends |
| `video.background_blur` | `32` | Blur radius of the background plate |
| `video.background_darken` | `0.38` | How far to darken the background plate (0–1) |
| `video.output_filename` | `narrated-manhwa.mp4` | Final MP4 name in `output/` |

All of these are validated at startup; a malformed value fails immediately
with a message naming the key.

The renderer creates a blurred, darkened full-frame background from each panel
with the complete panel fitted sharply in the center, so portrait output never
crops panel content.

## Local run

Requires Python 3.10–3.12, FFmpeg and espeak-ng.

```bash
sudo apt-get install ffmpeg espeak-ng libsndfile1
python -m venv .venv
source .venv/bin/activate
pip install --index-url https://download.pytorch.org/whl/cpu torch
pip install -r requirements.txt
```

Then:

```bash
# Check config and inputs without rendering (fast, skips Torch import)
python scripts/run_pipeline.py --validate

# Full render
python scripts/run_pipeline.py

# Render a different batch
python scripts/run_pipeline.py --input-dir /path/to/batch --config my-config.yaml
```

The final video is written to `output/<video.output_filename>` and the log to
`output/pipeline.log`. Exit code 0 means success, 1 means a pipeline or input
error (the reason is printed and logged).

## Development

```bash
pip install -r requirements/dev.txt
ruff check .
pytest              # 82 tests, including an FFmpeg end-to-end smoke test
```

The test suite needs no model download: the smoke test replaces Kokoro with a
deterministic stub and only requires `ffmpeg` on `PATH`. Tests that need
FFmpeg are skipped automatically when it is missing.

## GitHub notes

- Use a **private repository** unless you have the rights to publish the source
  material.
- GitHub blocks ordinary Git files larger than 100 MB. Use Git LFS for large
  chapters; LFS has separate quota limits.
- Hosted runners are CPU-only. Kokoro synthesis is the slow part of a long
  chapter; the first run also downloads model assets, which are cached between
  runs.
- The MP4 is uploaded as a 14-day artifact and the log as a 7-day artifact.
  The log is uploaded even when the render fails, so a missing artifact means
  the run died before the pipeline started.
- The workflow installs CPU-only PyTorch wheels. Do not add a bare `torch` to
  `requirements.txt`: the default Linux wheels pull several gigabytes of CUDA
  libraries that a CPU runner cannot use.

## Troubleshooting

Open the failed run and read `pipeline-logs` in the artifacts. Common causes:

| Symptom | Cause |
| --- | --- |
| `Expected exactly one chapter archive...` | More than one `.cbz`/`.txt` (or none) in `input/`. The message lists what was found. |
| `is not a readable ZIP/CBZ archive` | The file is a Git LFS pointer or not a CBZ. |
| `refers to page N, but M page(s) were extracted` | TXT page numbers exceed the archive's page count. |
| `line looks like a mistyped directive` | A `CROP`/`NARRATION` line has a typo; the message names the line number. |
| `contains no supported page images` | The archive has no `.jpg/.jpeg/.png/.webp/.bmp` entries. |
| FFmpeg text in the log | The failing command and its stderr tail are now logged in full. |

## License and content

The code is MIT-licensed. That license does not grant rights to any manga,
manhwa, artwork or narration text you add. Only upload or distribute content
you are authorized to use.
