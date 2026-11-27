# Contributors

Run `ruff check .` and `pytest` before opening a pull request; CI runs both.

## Ground rules for this repo

- **Never read an input file twice when once will do.** Cropping re-decodes
  whole pages, so tall webtoon pages are the main cost driver.
- **Fail loudly on ambiguous input.** A narration typo that is silently
  narrated is worse than a failed run, because the error ends up in the video.
- **No new heavy imports at module scope.** `src/tts_engine.py` imports Torch
  lazily on purpose so `--validate` stays fast.
- **FFmpeg arguments are behaviour.** The `-shortest`, `apad` and concat
  choices in `src/video_maker.py` each fix a specific historical bug; the tests
  assert them. Read the comments before changing them.

## Adding a test

`tests/test_pipeline_smoke.py` renders a real (360x640) video with a stubbed
TTS and is the right place for anything that touches FFmpeg behaviour. Unit
tests should build their inputs in memory; see `tests/conftest.py`.
