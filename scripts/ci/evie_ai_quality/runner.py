"""Orchestration for the EvieAi zero-new-violations gate."""

from __future__ import annotations

import argparse
import os
import shutil
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
from .git_snapshots import (
    GitSnapshotError,
    merge_base,
    ref_snapshot,
    staged_snapshot,
    text_file_at_ref,
)
from .model import Comparison, Violation, compare_violations
from .scope import (
    PRODUCTION_TARGETS,
    GitScopeError,
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
        if arguments.staged:
            with staged_snapshot(root) as scan_root:
                return _run_gate(root, scan_root, python_bin, arguments)
        return _run_gate(root, root, python_bin, arguments)
    except (
        BaselineError,
        GitScopeError,
        GitSnapshotError,
        QualityToolError,
        subprocess.CalledProcessError,
        SyntaxError,
        UnicodeError,
    ) as exc:
        print(f"[evie-ai-quality] execution failure: {exc}", file=sys.stderr)
        return 2


def _run_gate(
    git_root: Path,
    scan_root: Path,
    python_bin: str,
    arguments: argparse.Namespace,
) -> int:
    current = _scan_baseline_scope(scan_root, python_bin)
    baseline = _trusted_baseline(
        git_root,
        scan_root,
        python_bin,
        arguments,
        head_violations=current,
    )
    changed = changed_quality_files(
        git_root,
        scan_root=scan_root,
        base_ref=arguments.base_ref,
        staged=arguments.staged,
    )
    current.extend(_scan_extra_changed(scan_root, changed, python_bin))
    comparison = compare_violations(current, list(baseline.violations))
    diff_violations = _git_diff_violations(
        git_root,
        base_ref=arguments.base_ref,
        staged=arguments.staged,
    )
    _print_report(baseline, current, changed, comparison, diff_violations)
    return 0 if comparison.passed and not diff_violations else 1


def _trusted_baseline(
    git_root: Path,
    scan_root: Path,
    python_bin: str,
    arguments: argparse.Namespace,
    *,
    head_violations: list[Violation],
) -> Baseline:
    relative_path = arguments.baseline
    current, current_text = _load_current_baseline(scan_root, relative_path)
    trusted_ref = _trusted_ref(git_root, arguments)
    trusted_text = text_file_at_ref(git_root, trusted_ref, relative_path)
    if trusted_text is None:
        return _bootstrap_baseline(
            git_root=git_root,
            trusted_ref=trusted_ref,
            relative_path=relative_path,
            current=current,
            python_bin=python_bin,
            staged=arguments.staged,
        )
    return _verify_existing_baseline(
        git_root=git_root,
        trusted_ref=trusted_ref,
        trusted_text=trusted_text,
        relative_path=relative_path,
        current=current,
        current_text=current_text,
        python_bin=python_bin,
        head_violations=head_violations,
    )


def _verify_existing_baseline(
    *,
    git_root: Path,
    trusted_ref: str,
    trusted_text: str,
    relative_path: str,
    current: Baseline,
    current_text: str,
    python_bin: str,
    head_violations: list[Violation],
) -> Baseline:
    trusted = Baseline.from_text(
        trusted_text,
        source=f"{trusted_ref}:{relative_path}",
    )
    with ref_snapshot(git_root, trusted_ref) as base_root:
        base_violations = _scan_baseline_scope(base_root, python_bin)
    removed = _validate_baseline_transition(
        trusted_ref=trusted_ref,
        trusted=trusted,
        current=current,
        trusted_text=trusted_text,
        current_text=current_text,
        base_violations=base_violations,
        head_violations=head_violations,
    )
    if removed:
        print(
            "[evie-ai-quality] safe baseline shrink verified against "
            f"{trusted_ref}: {len(trusted.violations)} -> "
            f"{len(current.violations)}"
        )
    else:
        print(f"[evie-ai-quality] unchanged baseline verified against {trusted_ref}")
    return current


def _bootstrap_baseline(
    *,
    git_root: Path,
    trusted_ref: str,
    relative_path: str,
    current: Baseline,
    python_bin: str,
    staged: bool,
) -> Baseline:
    if staged:
        raise BaselineError(f"Missing trusted baseline {relative_path} at HEAD")
    return _validate_bootstrap_baseline(
        git_root,
        trusted_ref,
        current,
        python_bin,
    )


def _trusted_ref(
    git_root: Path,
    arguments: argparse.Namespace,
) -> str:
    if arguments.staged:
        return "HEAD"
    return merge_base(git_root, arguments.base_ref)


def _load_current_baseline(
    scan_root: Path,
    relative_path: str,
) -> tuple[Baseline, str]:
    current_path = scan_root / relative_path
    return (
        Baseline.load(current_path),
        current_path.read_text(encoding="utf-8"),
    )


def _validate_bootstrap_baseline(
    git_root: Path,
    trusted_ref: str,
    current: Baseline,
    python_bin: str,
) -> Baseline:
    if current.source_commit != trusted_ref:
        raise BaselineError(
            "Bootstrap baseline source_commit must equal merge-base "
            f"{trusted_ref}; got {current.source_commit}"
        )
    with ref_snapshot(git_root, trusted_ref) as base_root:
        expected = _scan_baseline_scope(base_root, python_bin)
    comparison = compare_violations(
        list(current.violations),
        expected,
    )
    if not comparison.passed:
        raise BaselineError(
            "Bootstrap baseline does not match a fresh merge-base scan.\n"
            + _render_comparison(comparison)
        )
    print(
        "[evie-ai-quality] bootstrap baseline verified against merge-base "
        f"{trusted_ref}"
    )
    return current


def _validate_baseline_transition(
    *,
    trusted_ref: str,
    trusted: Baseline,
    current: Baseline,
    trusted_text: str,
    current_text: str,
    base_violations: list[Violation],
    head_violations: list[Violation],
) -> tuple[Violation, ...]:
    _require_snapshot_match(
        label="Base",
        ref=trusted_ref,
        baseline=trusted,
        scanned=base_violations,
    )

    if current_text == trusted_text:
        _require_snapshot_match(
            label="Head",
            ref="working snapshot",
            baseline=current,
            scanned=head_violations,
        )
        return ()

    return _validate_baseline_shrink(
        trusted_ref=trusted_ref,
        trusted=trusted,
        current=current,
        base_violations=base_violations,
        head_violations=head_violations,
    )


def _validate_baseline_shrink(
    *,
    trusted_ref: str,
    trusted: Baseline,
    current: Baseline,
    base_violations: list[Violation],
    head_violations: list[Violation],
) -> tuple[Violation, ...]:
    transition = compare_violations(
        list(current.violations),
        list(trusted.violations),
    )
    _require_strict_baseline_subset(
        trusted=trusted,
        current=current,
        transition=transition,
    )
    _require_removed_violations_absent(transition.resolved, head_violations)
    _require_snapshot_match(
        label="Head",
        ref="working snapshot",
        baseline=current,
        scanned=head_violations,
    )
    _require_no_new_head_violations(
        trusted_ref=trusted_ref,
        base_violations=base_violations,
        head_violations=head_violations,
    )
    return transition.resolved


def _require_strict_baseline_subset(
    *,
    trusted: Baseline,
    current: Baseline,
    transition: Comparison,
) -> None:
    if transition.new:
        raise BaselineError(
            "Baseline growth, replacement, reclassification, or fingerprint "
            "changes are forbidden.\n" + _render_comparison(transition)
        )
    if not transition.resolved:
        raise BaselineError(
            "Baseline metadata or serialization changed without a strict "
            "violation-set shrink"
        )
    if current.tools != trusted.tools:
        raise BaselineError("Baseline tool metadata changed during shrink")
    _require_retained_details(trusted, current)


def _require_no_new_head_violations(
    *,
    trusted_ref: str,
    base_violations: list[Violation],
    head_violations: list[Violation],
) -> None:
    head_change = compare_violations(head_violations, base_violations)
    if head_change.new:
        raise BaselineError(
            "Head scan contains violations that were not present in the "
            f"verified Base snapshot {trusted_ref}.\n" + _render_comparison(head_change)
        )


def _require_snapshot_match(
    *,
    label: str,
    ref: str,
    baseline: Baseline,
    scanned: list[Violation],
) -> None:
    comparison = compare_violations(scanned, list(baseline.violations))
    if not comparison.passed:
        raise BaselineError(
            f"{label} baseline does not match its actual scan at {ref}.\n"
            + _render_comparison(comparison)
        )
    _require_violation_details(
        label=label,
        baseline=list(baseline.violations),
        scanned=scanned,
    )


def _require_violation_details(
    *,
    label: str,
    baseline: list[Violation],
    scanned: list[Violation],
) -> None:
    baseline_details = Counter((item.key, item.fix) for item in baseline)
    scanned_details = Counter((item.key, item.fix) for item in scanned)
    if baseline_details != scanned_details:
        raise BaselineError(
            f"{label} baseline retained violation details or fingerprints "
            "do not match its actual scan"
        )


def _require_retained_details(
    trusted: Baseline,
    current: Baseline,
) -> None:
    trusted_details = Counter((item.key, item.fix) for item in trusted.violations)
    current_details = Counter((item.key, item.fix) for item in current.violations)
    changed = current_details - trusted_details
    if changed:
        raise BaselineError(
            "Retained baseline rule, path, classification, fingerprint, or "
            "repair direction changed"
        )


def _require_removed_violations_absent(
    removed: tuple[Violation, ...],
    head_violations: list[Violation],
) -> None:
    removed_keys = Counter(item.key for item in removed)
    still_present = [item for item in head_violations if removed_keys[item.key] > 0]
    if still_present:
        rendered = "\n".join(item.render() for item in still_present[:10])
        raise BaselineError(
            "Baseline entries may be removed only after their violations "
            f"disappear from the Head scan:\n{rendered}"
        )


def _render_comparison(comparison: Comparison) -> str:
    lines = [
        f"added exemptions: {len(comparison.new)}",
        f"removed exemptions: {len(comparison.resolved)}",
    ]
    lines.extend(f"+ {item.render()}" for item in comparison.new[:10])
    lines.extend(f"- {item.render()}" for item in comparison.resolved[:10])
    if not comparison.new and not comparison.resolved:
        lines.append("baseline metadata or serialization changed")
    return "\n".join(lines)


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
        try:
            result = subprocess.run(
                command,
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise GitSnapshotError(f"Unable to run git diff --check: {exc}") from exc
        parsed = _parse_git_diff_output(result.stdout + result.stderr)
        if result.returncode != 0 and not parsed:
            raise GitSnapshotError(
                f"git diff --check failed with exit {result.returncode} "
                "without diagnostics"
            )
        if result.returncode == 0 and parsed:
            raise GitSnapshotError("git diff --check returned success with diagnostics")
        violations.extend(parsed)
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
        candidate = Path(configured)
        if candidate.is_absolute():
            return str(candidate)
        if candidate.parent != Path("."):
            return str(_repository_root() / candidate)
        resolved = shutil.which(configured)
        return resolved or configured
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
