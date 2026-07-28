"""Repository scope and changed-file discovery."""

from __future__ import annotations

import subprocess
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
}


def production_files(root: Path) -> list[Path]:
    return _python_files(root, PRODUCTION_TARGETS)


def quality_scope_files(root: Path) -> list[Path]:
    targets = (*PRODUCTION_TARGETS, *TEST_TARGETS)
    return _python_files(root, targets)


def changed_quality_files(
    root: Path,
    *,
    base_ref: str,
    staged: bool,
) -> list[Path]:
    relative_paths = _changed_paths(root, base_ref=base_ref, staged=staged)
    return sorted(
        root / path
        for path in relative_paths
        if _is_quality_python_path(path) and (root / path).is_file()
    )


def _python_files(root: Path, targets: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        path = root / target
        if path.is_file() and path.suffix == ".py":
            files.append(path)
        elif path.is_dir():
            files.extend(path.rglob("*.py"))
    return sorted(path for path in files if "__pycache__" not in path.parts)


def _changed_paths(root: Path, *, base_ref: str, staged: bool) -> set[str]:
    if staged:
        return set(
            _git_lines(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR")
        )
    paths = set(
        _git_lines(
            root,
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            f"{base_ref}...HEAD",
        )
    )
    paths.update(_git_lines(root, "diff", "--name-only", "--diff-filter=ACMR"))
    paths.update(
        _git_lines(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR")
    )
    paths.update(_git_lines(root, "ls-files", "--others", "--exclude-standard"))
    return paths


def _git_lines(root: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ("git", *args),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _is_quality_python_path(path: str) -> bool:
    candidate = Path(path)
    if candidate.suffix != ".py":
        return False
    if path in EXTRA_CHANGED_PYTHON:
        return True
    if "evie_ai" in candidate.parts or candidate.name == "evie_ai.py":
        return True
    return path.startswith("scripts/ci/evie_ai_quality")
