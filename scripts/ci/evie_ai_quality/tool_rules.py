"""Adapters for Ruff, Ruff format, and Mypy."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .model import Violation

_MYPY_LINE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+): error: "
    r"(?P<message>.*?)(?:  \[(?P<code>[^\]]+)\])?$"
)
_FORMAT_LINE = re.compile(r"^Would reformat: (?P<path>.+)$")


class QualityToolError(RuntimeError):
    """Raised when an external quality tool cannot produce valid results."""


@dataclass(frozen=True, slots=True)
class ToolVersions:
    python: str
    ruff: str
    mypy: str


def scan_ruff(
    root: Path,
    files: list[Path],
    *,
    python_bin: str,
) -> list[Violation]:
    if not files:
        return []
    command = [
        python_bin,
        "-m",
        "ruff",
        "check",
        "--no-cache",
        "--output-format=json",
        *(_relative_paths(root, files)),
    ]
    result = _run(command, root)
    if result.returncode not in {0, 1}:
        raise QualityToolError(_tool_failure("Ruff", result))
    return _ruff_violations(root, result.stdout)


def scan_format(
    root: Path,
    files: list[Path],
    *,
    python_bin: str,
) -> list[Violation]:
    if not files:
        return []
    command = [
        python_bin,
        "-m",
        "ruff",
        "format",
        "--check",
        *(_relative_paths(root, files)),
    ]
    result = _run(command, root)
    if result.returncode not in {0, 1}:
        raise QualityToolError(_tool_failure("Ruff format", result))
    paths = _format_paths(result.stdout + result.stderr)
    return [_format_violation(root, path, python_bin=python_bin) for path in paths]


def scan_mypy(
    root: Path,
    targets: tuple[str, ...],
    *,
    python_bin: str,
) -> list[Violation]:
    existing = [target for target in targets if (root / target).exists()]
    if not existing:
        return []
    with tempfile.TemporaryDirectory(prefix="evie-ai-mypy-") as cache_dir:
        result = _run_mypy(
            root,
            existing,
            python_bin=python_bin,
            cache_dir=cache_dir,
        )
    if result.returncode not in {0, 1}:
        raise QualityToolError(_tool_failure("Mypy", result))
    return _mypy_violations(root, result.stdout + result.stderr)


def tool_versions(python_bin: str, root: Path) -> ToolVersions:
    python = _version((python_bin, "--version"), root)
    ruff = _version((python_bin, "-m", "ruff", "--version"), root)
    mypy = _version((python_bin, "-m", "mypy", "--version"), root)
    return ToolVersions(python=python, ruff=ruff, mypy=mypy)


def _run_mypy(
    root: Path,
    targets: list[str],
    *,
    python_bin: str,
    cache_dir: str,
) -> subprocess.CompletedProcess[str]:
    command = [
        python_bin,
        "-m",
        "mypy",
        "--follow-imports=silent",
        "--show-error-codes",
        "--no-error-summary",
        "--no-pretty",
        f"--cache-dir={cache_dir}",
        *targets,
    ]
    environment = os.environ.copy()
    environment["MYPYPATH"] = str(root / "apps/web-ui-service")
    return _run(command, root, environment=environment)


def _ruff_violations(root: Path, output: str) -> list[Violation]:
    payload = json.loads(output or "[]")
    violations: list[Violation] = []
    for item in payload:
        path = _normalize_path(root, str(item["filename"]))
        code = str(item["code"])
        line = int(item["location"]["row"])
        violations.append(
            Violation(
                rule=f"RUFF:{code}",
                path=path,
                line=line,
                message=str(item["message"]),
                fix=f"Run `ruff check --fix {path}` and review the change.",
                symbol=_ruff_fix_digest(item.get("fix")),
            )
        )
    return sorted(violations)


def _format_paths(output: str) -> list[str]:
    paths: list[str] = []
    for line in output.splitlines():
        match = _FORMAT_LINE.match(line.strip())
        if match:
            paths.append(match.group("path"))
    return sorted(set(paths))


def _format_violation(
    root: Path,
    path: str,
    *,
    python_bin: str,
) -> Violation:
    normalized = _normalize_path(root, path)
    result = _run(
        [python_bin, "-m", "ruff", "format", "--diff", normalized],
        root,
    )
    if result.returncode not in {0, 1}:
        raise QualityToolError(_tool_failure("Ruff format diff", result))
    output = result.stdout + result.stderr
    digest = hashlib.sha256(output.encode("utf-8")).hexdigest()[:16]
    return Violation(
        rule="FORMAT",
        path=normalized,
        line=1,
        message="file is not formatted by Ruff",
        fix=f"Run `ruff format {normalized}` and review the change.",
        symbol=digest,
    )


def _mypy_violations(root: Path, output: str) -> list[Violation]:
    violations: list[Violation] = []
    for line in output.splitlines():
        match = _MYPY_LINE.match(line.strip())
        if not match:
            continue
        path = _normalize_path(root, match.group("path"))
        code = match.group("code") or "error"
        violations.append(
            Violation(
                rule=f"MYPY:{code}",
                path=path,
                line=int(match.group("line")),
                message=match.group("message"),
                fix="Add explicit types or narrow the value without ignores.",
            )
        )
    return sorted(violations)


def _ruff_fix_digest(payload: object) -> str:
    if payload is None:
        return ""
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _relative_paths(root: Path, files: list[Path]) -> list[str]:
    return [path.relative_to(root).as_posix() for path in files]


def _normalize_path(root: Path, raw_path: str) -> str:
    path = Path(raw_path)
    if path.is_absolute():
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix()


def _run(
    command: list[str] | tuple[str, ...],
    root: Path,
    *,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def _version(command: tuple[str, ...], root: Path) -> str:
    result = _run(command, root)
    if result.returncode != 0:
        raise QualityToolError(_tool_failure(command[-1], result))
    return (result.stdout or result.stderr).strip()


def _tool_failure(
    name: str,
    result: subprocess.CompletedProcess[str],
) -> str:
    output = (result.stdout + result.stderr).strip()
    return f"{name} failed with exit {result.returncode}: {output}"
