"""Error types and FFmpeg helpers shared by the pipeline."""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

LOGGER = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    """A failure with a message that is safe and useful to show the user."""


def require_binary(name: str) -> str:
    """Return the path of an external binary, or raise a readable error."""

    path = shutil.which(name)
    if path is None:
        raise PipelineError(
            f"'{name}' was not found on PATH. Install it (for example "
            "`sudo apt-get install ffmpeg espeak-ng libsndfile1`) and retry."
        )
    return path


def run_command(
    command: Sequence[str],
    *,
    description: str,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess and surface its stderr when it fails.

    ``subprocess.run(check=True)`` raises a bare ``CalledProcessError`` whose
    message is just "returned non-zero exit status", which hides the actual
    FFmpeg diagnostic from CI logs. Capture the output and re-raise with the
    tail of stderr attached.
    """

    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PipelineError(f"{description} timed out after {timeout} seconds.") from exc
    except OSError as exc:
        raise PipelineError(f"{description} could not be started: {exc}") from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip().splitlines()
        tail = "\n".join(stderr[-12:]) if stderr else "(no stderr output)"
        LOGGER.error("%s failed with exit code %d", description, result.returncode)
        LOGGER.error("Command: %s", " ".join(str(part) for part in command))
        LOGGER.error("Output:\n%s", tail)
        raise PipelineError(f"{description} failed (exit code {result.returncode}):\n{tail}")

    return result


def file_size_mb(path: Path) -> float:
    """Return a file's size in megabytes, or 0 when it does not exist."""

    try:
        return path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0
