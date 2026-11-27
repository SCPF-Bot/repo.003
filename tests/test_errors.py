"""Tests for the FFmpeg invocation helper.

The whole point of ``run_command`` is that FFmpeg's diagnostic reaches the
person reading the CI log, so the failure path is what matters here.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest import mock

import pytest

from src.errors import PipelineError, file_size_mb, require_binary, run_command


def test_returns_completed_process_on_success():
    result = run_command(["true"], description="true")
    assert result.returncode == 0


def test_failure_includes_stderr_tail(caplog):
    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(PipelineError) as excinfo,
    ):
        run_command(
            ["sh", "-c", "echo 'No such file or directory' >&2; exit 254"],
            description="FFmpeg clip render",
        )

    message = str(excinfo.value)
    assert "FFmpeg clip render" in message
    assert "254" in message
    assert "No such file or directory" in message
    assert any("No such file or directory" in record.message for record in caplog.records)


def test_long_stderr_is_trimmed_to_the_tail():
    with pytest.raises(PipelineError) as excinfo:
        run_command(
            ["sh", "-c", "seq 1 100 >&2; exit 1"],
            description="noisy",
        )
    message = str(excinfo.value)
    assert "100" in message
    assert "\n1\n2\n3" not in message


def test_missing_binary_is_reported_as_pipeline_error():
    with pytest.raises(PipelineError, match="could not be started"):
        run_command(["definitely-not-a-real-binary-xyz"], description="missing")


def test_timeout_is_reported():
    with pytest.raises(PipelineError, match="timed out"):
        run_command(["sleep", "5"], description="slow step", timeout=0.05)


def test_require_binary_finds_common_tools():
    assert require_binary("sh").endswith("sh")


def test_require_binary_explains_what_to_install():
    with pytest.raises(PipelineError) as excinfo:
        require_binary("definitely-not-a-real-binary-xyz")
    assert "apt-get install" in str(excinfo.value)


def test_file_size_mb_handles_missing_file(tmp_path):
    assert file_size_mb(tmp_path / "absent") == 0.0


def test_file_size_mb_reads_real_file(tmp_path):
    path = tmp_path / "blob"
    path.write_bytes(b"x" * 2048)
    assert file_size_mb(path) == pytest.approx(2048 / (1024 * 1024))


def test_empty_stderr_still_produces_a_message():
    with mock.patch("subprocess.run") as fake:
        fake.return_value = mock.Mock(returncode=1, stderr="", stdout="")
        with pytest.raises(PipelineError, match="no stderr output"):
            run_command(["x"], description="silent failure")


def test_paths_are_not_shell_expanded():
    """Arguments are passed as a list, so filenames cannot inject shell syntax."""
    marker = Path("/tmp/should-not-exist-from-injection")
    marker.unlink(missing_ok=True)

    with pytest.raises(PipelineError):
        run_command(
            ["sh", "-c", "exit 1", ";", f"touch {marker}"],
            description="injection attempt",
        )
    assert not marker.exists()
