from __future__ import annotations

from pathlib import Path
from typing import Any


class LocalFileReadError(RuntimeError):
    """Raised when a local file cannot be safely loaded."""


def read_local_file(*, path: str, repo_root: Path) -> dict[str, Any]:
    raw_path = str(path or "").strip()
    if not raw_path:
        raise LocalFileReadError("path must not be empty")
    root = Path(repo_root).resolve()
    candidate = (Path(raw_path) if Path(raw_path).is_absolute() else (root / raw_path)).resolve()
    if root not in candidate.parents and candidate != root:
        raise LocalFileReadError("path is outside repository root")
    if not candidate.exists() or not candidate.is_file():
        raise LocalFileReadError("file not found")
    try:
        text = candidate.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise LocalFileReadError(str(exc)) from exc
    return {"path": str(candidate), "text": text}

