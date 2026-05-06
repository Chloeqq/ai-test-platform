from __future__ import annotations

import logging
import subprocess
import threading
from collections.abc import Sequence
from typing import Any

from .logging import get_request_id, set_request_id, summarize_log_value


def _summarize_subprocess_output(text: str, *, max_length: int = 1200) -> str:
    return summarize_log_value(text, max_length=max_length)


def run_logged_subprocess(
    args: Sequence[str],
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int | float | None = None,
    logger: logging.Logger | None = None,
    log_prefix: str = "subprocess",
) -> subprocess.CompletedProcess[str]:
    logger = logger or logging.getLogger(__name__)
    captured_request_id = get_request_id()
    logger.info(
        "%s start args=%s cwd=%s timeout=%s request_id=%s",
        log_prefix,
        _summarize_subprocess_output(" ".join(list(args))),
        cwd or "-",
        timeout if timeout is not None else "-",
        captured_request_id or "-",
    )
    process = subprocess.Popen(
        list(args),
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
    )

    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    def _drain_stream(stream: Any, chunks: list[str], stream_name: str, level: int) -> None:
        set_request_id(captured_request_id)
        try:
            if stream is None:
                return
            for line in iter(stream.readline, ""):
                chunks.append(line)
                text = line.rstrip("\n")
                if text:
                    logger.log(level, "%s %s %s", log_prefix, stream_name, text)
        finally:
            try:
                if stream is not None:
                    stream.close()
            except Exception:
                pass

    threads: list[threading.Thread] = []
    if process.stdout is not None:
        stdout_thread = threading.Thread(
            target=_drain_stream,
            args=(process.stdout, stdout_chunks, "stdout", logging.INFO),
            daemon=True,
        )
        stdout_thread.start()
        threads.append(stdout_thread)
    if process.stderr is not None:
        stderr_thread = threading.Thread(
            target=_drain_stream,
            args=(process.stderr, stderr_chunks, "stderr", logging.WARNING),
            daemon=True,
        )
        stderr_thread.start()
        threads.append(stderr_thread)

    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            process.kill()
        except Exception:
            pass
        try:
            process.wait(timeout=5)
        except Exception:
            pass
        for thread in threads:
            thread.join(timeout=5)
        logger.warning(
            "%s timeout returncode=%s stdout_chars=%d stderr_chars=%d stdout_excerpt=%s stderr_excerpt=%s request_id=%s",
            log_prefix,
            getattr(process, "returncode", None),
            len("".join(stdout_chunks)),
            len("".join(stderr_chunks)),
            _summarize_subprocess_output("".join(stdout_chunks)),
            _summarize_subprocess_output("".join(stderr_chunks)),
            captured_request_id or "-",
        )
        raise subprocess.TimeoutExpired(
            args=list(args),
            timeout=timeout,
            output="".join(stdout_chunks),
            stderr="".join(stderr_chunks),
        ) from exc
    finally:
        for thread in threads:
            thread.join(timeout=5)

    completed = subprocess.CompletedProcess(
        args=list(args),
        returncode=returncode,
        stdout="".join(stdout_chunks),
        stderr="".join(stderr_chunks),
    )
    logger.info(
        "%s end returncode=%s stdout_chars=%d stderr_chars=%d stdout_excerpt=%s stderr_excerpt=%s request_id=%s",
        log_prefix,
        completed.returncode,
        len(completed.stdout or ""),
        len(completed.stderr or ""),
        _summarize_subprocess_output(completed.stdout or ""),
        _summarize_subprocess_output(completed.stderr or ""),
        captured_request_id or "-",
    )
    if completed.returncode != 0:
        logger.error(
            "%s nonzero returncode=%s stdout_excerpt=%s stderr_excerpt=%s request_id=%s",
            log_prefix,
            completed.returncode,
            _summarize_subprocess_output(completed.stdout or ""),
            _summarize_subprocess_output(completed.stderr or ""),
            captured_request_id or "-",
        )
    return completed
