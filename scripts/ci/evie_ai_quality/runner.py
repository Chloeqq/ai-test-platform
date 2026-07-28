"""Orchestration for the EvieAi zero-new-violations gate."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

from .ast_rules import scan_ast_rules
from .baseline import (
    Baseline,
    BaselineError,
    create_baseline,
    violation_counts,
    write_baseline,
)
from .model import Comparison, Violation, compare_violations
from .scope import (
    PRODUCTION_TARGETS,
    changed_quality_files,
    production_files,
    quality_scope_files,
)
from .tool_rules import (
    QualityToolError,
    scan_format,
    scan_mypy,
    scan_ruff,
    tool_versions,
)

DEFAULT_BASELINE = "scripts/ci/evie_ai_quality_baseline.json"


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    root = _repository_root()
    python_bin = _python_binary(arguments.python_bin)
    baseline_path = root / arguments.baseline
    try:
        _verify_base_ref(root, arguments.base_ref)
        if arguments.write_baseline:
            return _write_baseline(root, baseline_path, python_bin)
        return _run_gate(root, baseline_path, python_bin, arguments)
    except (BaselineError, QualityToolError, subprocess.CalledProcessError) as exc:
        print(f"[evie-ai-quality] configuration failure: {exc}", file=sys.stderr)
        return 2


def _run_gate(
    root: Path,
    baseline_path: Path,
    python_bin: str,
    arguments: argparse.Namespace,
) -> int:
    baseline = Baseline.load(baseline_path)
    current = _scan_baseline_scope(root, python_bin)
    changed = changed_quality_files(
        root,
        base_ref=arguments.base_ref,
        staged=arguments.staged,
    )
    current.extend(_scan_extra_changed(root, changed, python_bin))
    comparison = compare_violations(current, list(baseline.violations))
    diff_violations = _git_diff_violations(
        root,
        base_ref=arguments.base_ref,
        staged=arguments.staged,
    )
    _print_report(baseline, current, changed, comparison, diff_violations)
    return 0 if comparison.passed and not diff_violations else 1


def _write_baseline(
    root: Path,
    baseline_path: Path,
    python_bin: str,
) -> int:
    current = _scan_baseline_scope(root, python_bin)
    versions = tool_versions(python_bin, root)
    baseline = create_baseline(root, current, versions)
    existing = Baseline.load(baseline_path) if baseline_path.exists() else None
    write_baseline(baseline_path, baseline, existing=existing)
    print(
        f"[evie-ai-quality] wrote {len(current)} baseline violations to "
        f"{baseline_path.relative_to(root)}"
    )
    _print_counts(violation_counts(current))
    return 0


def _scan_baseline_scope(root: Path, python_bin: str) -> list[Violation]:
    all_files = quality_scope_files(root)
    production = production_files(root)
    violations = scan_ruff(root, all_files, python_bin=python_bin)
    violations.extend(scan_format(root, all_files, python_bin=python_bin))
    violations.extend(scan_mypy(root, PRODUCTION_TARGETS, python_bin=python_bin))
    violations.extend(scan_ast_rules(root, production))
    return sorted(violations)


def _scan_extra_changed(
    root: Path,
    changed: list[Path],
    python_bin: str,
) -> list[Violation]:
    baseline_paths = set(quality_scope_files(root))
    extra = [path for path in changed if path not in baseline_paths]
    violations = scan_ruff(root, extra, python_bin=python_bin)
    violations.extend(scan_format(root, extra, python_bin=python_bin))
    return sorted(violations)


def _git_diff_violations(
    root: Path,
    *,
    base_ref: str,
    staged: bool,
) -> list[Violation]:
    commands = (
        [("git", "diff", "--cached", "--check")]
        if staged
        else [
            ("git", "diff", "--check", f"{base_ref}...HEAD"),
            ("git", "diff", "--check"),
            ("git", "diff", "--cached", "--check"),
        ]
    )
    violations: list[Violation] = []
    for command in commands:
        result = subprocess.run(
            command,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        violations.extend(_parse_git_diff_output(result.stdout + result.stderr))
    return sorted(set(violations))


def _parse_git_diff_output(output: str) -> list[Violation]:
    violations: list[Violation] = []
    for raw_line in output.splitlines():
        path, line, message = _split_git_diff_line(raw_line)
        violations.append(
            Violation(
                rule="GITDIFF",
                path=path,
                line=line,
                message=message,
                fix="Remove whitespace errors and rerun `git diff --check`.",
            )
        )
    return violations


def _split_git_diff_line(raw_line: str) -> tuple[str, int, str]:
    parts = raw_line.split(":", 2)
    if len(parts) < 3 or not parts[1].isdigit():
        return ("<git-diff>", 0, raw_line)
    return (parts[0], int(parts[1]), parts[2].strip())


def _print_report(
    baseline: Baseline,
    current: list[Violation],
    changed: list[Path],
    comparison: Comparison,
    diff_violations: list[Violation],
) -> None:
    print("[evie-ai-quality] zero-new-violations report")
    print(f"  baseline commit: {baseline.source_commit}")
    print(f"  changed Python files checked: {len(changed)}")
    print(f"  baseline violations: {len(baseline.violations)}")
    print(f"  current violations: {len(current)}")
    _print_counts(violation_counts(current))
    _print_section("NEW VIOLATIONS", comparison.new)
    _print_section("RESOLVED BUT BASELINE NOT SHRUNK", comparison.resolved)
    _print_section("GIT DIFF VIOLATIONS", tuple(diff_violations))
    if comparison.passed and not diff_violations:
        print("[evie-ai-quality] PASS: no new violations")
    else:
        print("[evie-ai-quality] FAIL: update code or shrink the baseline")


def _print_counts(counts: Counter[str]) -> None:
    rendered = ", ".join(
        f"{category}={count}" for category, count in sorted(counts.items())
    )
    print(f"  counts: {rendered or 'none'}")


def _print_section(title: str, violations: tuple[Violation, ...]) -> None:
    if not violations:
        return
    print(f"\n{title}")
    for item in violations:
        print(f"  {item.render()}")


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enforce EvieAi zero-new code-quality violations."
    )
    parser.add_argument(
        "--base-ref",
        default=os.environ.get("BASE_REF", "origin/dev"),
    )
    parser.add_argument("--baseline", default=DEFAULT_BASELINE)
    parser.add_argument("--python-bin", default=os.environ.get("PYTHON_BIN"))
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--write-baseline", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.staged and arguments.write_baseline:
        parser.error("--staged and --write-baseline cannot be combined")
    return arguments


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _python_binary(configured: str | None) -> str:
    if configured:
        return configured
    candidate = _repository_root() / ".venv/bin/python"
    return str(candidate) if candidate.is_file() else sys.executable


def _verify_base_ref(root: Path, base_ref: str) -> None:
    subprocess.run(
        ("git", "rev-parse", "--verify", f"{base_ref}^{{commit}}"),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
