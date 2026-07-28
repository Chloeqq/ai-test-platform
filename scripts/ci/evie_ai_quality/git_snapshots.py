"""Read-only Git snapshots used by the quality gate."""

from __future__ import annotations

import io
import os
import subprocess
import tarfile
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class GitSnapshotError(RuntimeError):
    """Raised when an isolated Git snapshot cannot be constructed."""


def merge_base(root: Path, base_ref: str) -> str:
    output = _run_git(root, "merge-base", base_ref, "HEAD")
    commit = output.decode("ascii").strip()
    if not commit:
        raise GitSnapshotError(f"No merge-base found for {base_ref!r} and HEAD")
    return commit


def text_file_at_ref(
    root: Path,
    ref: str,
    relative_path: str,
) -> str | None:
    listing = _run_git(
        root,
        "ls-tree",
        "-z",
        "--name-only",
        ref,
        "--",
        relative_path,
    )
    names = [os.fsdecode(item) for item in listing.split(b"\0") if item]
    if relative_path not in names:
        return None
    content = _run_git(root, "show", f"{ref}:{relative_path}")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GitSnapshotError(f"{relative_path} at {ref} is not valid UTF-8") from exc


@contextmanager
def staged_snapshot(root: Path) -> Iterator[Path]:
    """Materialize the exact Git index without touching worktree or index."""

    with tempfile.TemporaryDirectory(prefix="evie-ai-index-") as directory:
        destination = Path(directory)
        prefix = f"{destination}{os.sep}"
        _run_git(root, "checkout-index", "--all", f"--prefix={prefix}")
        yield destination


@contextmanager
def ref_snapshot(root: Path, ref: str) -> Iterator[Path]:
    """Materialize a committed ref without registering a Git worktree."""

    archive_bytes = _run_git(root, "archive", "--format=tar", ref)
    with tempfile.TemporaryDirectory(prefix="evie-ai-ref-") as directory:
        destination = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
            archive.extractall(destination, filter="data")
        yield destination


def _run_git(root: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(
            ("git", *arguments),
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise GitSnapshotError(f"Unable to start Git: {exc}") from exc
    if result.returncode != 0:
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        raise GitSnapshotError(
            f"Git {' '.join(arguments)} failed with exit "
            f"{result.returncode}: {output.strip()}"
        )
    return result.stdout
