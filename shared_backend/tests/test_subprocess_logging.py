from __future__ import annotations

import logging
import sys

from shared_backend.observability import run_logged_subprocess


def test_run_logged_subprocess_captures_output(caplog) -> None:
    caplog.set_level(logging.INFO)
    completed = run_logged_subprocess(
        [
            sys.executable,
            "-c",
            "import sys; print('hello from stdout'); print('hello from stderr', file=sys.stderr)",
        ],
        logger=logging.getLogger("shared_backend.test"),
        log_prefix="agent",
    )

    assert completed.returncode == 0
    assert "hello from stdout" in completed.stdout
    assert "hello from stderr" in completed.stderr
    assert "agent stdout hello from stdout" in caplog.text
    assert "agent stderr hello from stderr" in caplog.text
