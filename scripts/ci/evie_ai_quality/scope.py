"""Repository scope and changed-file discovery."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

PRODUCTION_TARGETS = (
    "apps/web-ui-service/app/errors/evie_ai.py",
    "apps/web-ui-service/app/constants/evie_ai.py",
    "apps/web-ui-service/app/models/evie_ai",
    "apps/web-ui-service/app/schemas/evie_ai",
    "apps/web-ui-service/app/policies/evie_ai",
    "apps/web-ui-service/app/repositories/evie_ai",
    "apps/web-ui-service/app/services/evie_ai",
)
TEST_TARGETS = (
    "apps/web-ui-service/tests/unit/evie_ai",
    "apps/web-ui-service/tests/integration/evie_ai",
)
EXTRA_CHANGED_PYTHON = {
    "apps/web-ui-service/app/main.py",
    "apps/web-ui-service/app/core/id_gen.py",
    "tests/unit/test_evie_ai_code_quality_gate.py",
    "tests/unit/test_evie_ai_code_quality_gate_security.py",
}
GIT_STATUS_ADDED = "A"


class GitScopeError(RuntimeError):
    """Raised when Git cannot provide an unambiguous changed-file set."""


@dataclass(frozen=True, slots=True)
class GitChange:
    """One NUL-safe Git path change."""

    status: str
    paths: tuple[str, ...]


def production_files(root: Path) -> list[Path]:
    return _python_files(root, PRODUCTION_TARGETS)


def quality_scope_files(root: Path) -> list[Path]:
    targets = (*PRODUCTION_TARGETS, *TEST_TARGETS)
    return _python_files(root, targets)


def changed_quality_files(
    git_root: Path,
    *,
    scan_root: Path | None = None,
    base_ref: str,
    staged: bool,
) -> list[Path]:
    source_root = scan_root or git_root
    relative_paths = {
        path
        for change in discover_changes(
            git_root,
            base_ref=base_ref,
            staged=staged,
        )
        for path in change.paths
    }
    return sorted(
        source_root / path
        for path in relative_paths
        if _is_quality_python_path(path) and (source_root / path).is_file()
    )


def discover_changes(
    root: Path,
    *,
    base_ref: str,
    staged: bool,
) -> tuple[GitChange, ...]:
    if staged:
        return _git_diff_changes(root, "--cached")
    changes = [
        *_git_diff_changes(root, f"{base_ref}...HEAD"),
        *_git_diff_changes(root),
        *_git_diff_changes(root, "--cached"),
        *_untracked_changes(root),
    ]
    return tuple(sorted(set(changes), key=lambda item: (item.paths, item.status)))


def _python_files(root: Path, targets: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        path = root / target
        if path.is_file() and path.suffix == ".py":
            files.append(path)
        elif path.is_dir():
            files.extend(path.rglob("*.py"))
    return sorted(path for path in files if "__pycache__" not in path.parts)


def _git_diff_changes(root: Path, revision: str | None = None) -> tuple[GitChange, ...]:
    command = [
        "diff",
        "--name-status",
        "-z",
        "--find-renames",
        "--find-copies-harder",
        "--diff-filter=ACDMR",
    ]
    if revision is not None:
        command.append(revision)
    return _parse_name_status_z(_git_bytes(root, *command))


def _untracked_changes(root: Path) -> tuple[GitChange, ...]:
    output = _git_bytes(
        root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
    )
    paths = _decode_z_fields(output)
    return tuple(GitChange(status=GIT_STATUS_ADDED, paths=(path,)) for path in paths)


def _parse_name_status_z(output: bytes) -> tuple[GitChange, ...]:
    fields = _decode_z_fields(output)
    changes: list[GitChange] = []
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        path_count = 2 if status.startswith(("R", "C")) else 1
        end = index + path_count
        if end > len(fields):
            raise GitScopeError(f"Malformed Git name-status output at {status!r}")
        changes.append(GitChange(status=status, paths=tuple(fields[index:end])))
        index = end
    return tuple(changes)


def _decode_z_fields(output: bytes) -> list[str]:
    fields = output.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    if any(field == b"" for field in fields):
        raise GitScopeError("Malformed Git NUL-delimited path output")
    return [os.fsdecode(field) for field in fields]


def _git_bytes(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ("git", *args),
        cwd=root,
        check=True,
        capture_output=True,
    )
    return result.stdout


def _is_quality_python_path(path: str) -> bool:
    candidate = Path(path)
    if candidate.suffix != ".py":
        return False
    if path in EXTRA_CHANGED_PYTHON:
        return True
    if "evie_ai" in candidate.parts or candidate.name == "evie_ai.py":
        return True
    return path.startswith("scripts/ci/evie_ai_quality")
