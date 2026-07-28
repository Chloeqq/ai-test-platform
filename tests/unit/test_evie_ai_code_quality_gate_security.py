from __future__ import annotations

import json
import shutil
import subprocess
import sys
from argparse import Namespace
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.ci.evie_ai_quality import tool_rules
from scripts.ci.evie_ai_quality.ast_rules import scan_ast_rules
from scripts.ci.evie_ai_quality.baseline import Baseline, BaselineError
from scripts.ci.evie_ai_quality.git_snapshots import (
    GitSnapshotError,
    merge_base,
    staged_snapshot,
)
from scripts.ci.evie_ai_quality.model import Violation
from scripts.ci.evie_ai_quality.runner import (
    _trusted_baseline,
    _validate_baseline_transition,
)
from scripts.ci.evie_ai_quality.scope import (
    GitChange,
    _parse_name_status_z,
    changed_quality_files,
    discover_changes,
)
from scripts.ci.evie_ai_quality.tool_rules import (
    QualityToolError,
    ToolVersions,
    scan_format,
    scan_mypy,
    scan_ruff,
)

BASELINE_PATH = "scripts/ci/evie_ai_quality_baseline.json"


def test_trusted_baseline_rejects_added_exemption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _git_repository(tmp_path)
    baseline = _baseline((_violation(),))
    _write_baseline(root, baseline)
    _commit_all(root, "baseline")
    growing = replace(
        baseline,
        violations=(
            *baseline.violations,
            _violation(rule="EQA002", symbol="new_function"),
        ),
    )
    _write_baseline(root, growing)
    monkeypatch.setattr(
        "scripts.ci.evie_ai_quality.runner._scan_baseline_scope",
        lambda *_args: list(baseline.violations),
    )

    with pytest.raises(BaselineError, match="added exemptions: 1"):
        _trusted_baseline(
            root,
            root,
            sys.executable,
            _arguments(base_ref="HEAD"),
            head_violations=list(growing.violations),
        )


def test_trusted_baseline_rejects_metadata_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _git_repository(tmp_path)
    baseline = _baseline((_violation(),))
    _write_baseline(root, baseline)
    _commit_all(root, "baseline")
    _write_baseline(
        root,
        replace(baseline, generated_at="2026-07-29T00:00:00+00:00"),
    )
    monkeypatch.setattr(
        "scripts.ci.evie_ai_quality.runner._scan_baseline_scope",
        lambda *_args: list(baseline.violations),
    )

    with pytest.raises(BaselineError, match="metadata or serialization changed"):
        _trusted_baseline(
            root,
            root,
            sys.executable,
            _arguments(base_ref="HEAD"),
            head_violations=list(baseline.violations),
        )


def test_safe_baseline_shrink_77_to_50_passes() -> None:
    base_violations = tuple(
        _violation(symbol=f"violation_{index}") for index in range(77)
    )
    head_violations = base_violations[:50]
    removed = _validate_transition(
        trusted=_baseline(base_violations),
        current=_baseline(head_violations),
        base_scan=list(base_violations),
        head_scan=list(head_violations),
    )

    assert len(removed) == 27


def test_unchanged_baseline_passes() -> None:
    baseline = _baseline((_violation(),))

    removed = _validate_transition(
        trusted=baseline,
        current=baseline,
        base_scan=list(baseline.violations),
        head_scan=list(baseline.violations),
        changed=False,
    )

    assert removed == ()


def test_resolved_violation_can_be_removed() -> None:
    resolved = _violation(symbol="resolved")
    retained = _violation(symbol="retained")

    removed = _validate_transition(
        trusted=_baseline((resolved, retained)),
        current=_baseline((retained,)),
        base_scan=[resolved, retained],
        head_scan=[retained],
    )

    assert removed == (resolved,)


def test_removing_violation_that_still_exists_fails() -> None:
    resolved = _violation(symbol="resolved")
    retained = _violation(symbol="retained")

    with pytest.raises(BaselineError, match="only after their violations disappear"):
        _validate_transition(
            trusted=_baseline((resolved, retained)),
            current=_baseline((retained,)),
            base_scan=[resolved, retained],
            head_scan=[resolved, retained],
        )


def test_baseline_growth_fails() -> None:
    retained = _violation(symbol="retained")
    added = _violation(symbol="added")

    with pytest.raises(BaselineError, match="growth, replacement"):
        _validate_transition(
            trusted=_baseline((retained,)),
            current=_baseline((retained, added)),
            base_scan=[retained],
            head_scan=[retained, added],
        )


def test_replacing_old_exemption_fails() -> None:
    old = _violation(symbol="old")
    replacement = _violation(symbol="replacement")

    with pytest.raises(BaselineError, match="growth, replacement"):
        _validate_transition(
            trusted=_baseline((old,)),
            current=_baseline((replacement,)),
            base_scan=[old],
            head_scan=[replacement],
        )


def test_reclassifying_exemption_fails() -> None:
    original = _violation(rule="EQA001")
    reclassified = _violation(rule="EQA002")

    with pytest.raises(BaselineError, match="reclassification"):
        _validate_transition(
            trusted=_baseline((original,)),
            current=_baseline((reclassified,)),
            base_scan=[original],
            head_scan=[reclassified],
        )


def test_modifying_exemption_fingerprint_fails() -> None:
    original = _violation(symbol="original")
    tampered = _violation(symbol="tampered")

    with pytest.raises(BaselineError, match="fingerprint"):
        _validate_transition(
            trusted=_baseline((original,)),
            current=_baseline((tampered,)),
            base_scan=[original],
            head_scan=[tampered],
        )


def test_modifying_retained_repair_direction_fails() -> None:
    original = _violation()
    changed = replace(original, fix="hide the violation")
    resolved = _violation(symbol="resolved")

    with pytest.raises(BaselineError, match="repair direction changed"):
        _validate_transition(
            trusted=_baseline((original, resolved)),
            current=_baseline((changed,)),
            base_scan=[original, resolved],
            head_scan=[changed],
        )


def test_head_baseline_must_match_head_scan() -> None:
    violation = _violation()

    with pytest.raises(BaselineError, match="Head baseline does not match"):
        _validate_transition(
            trusted=_baseline((violation,)),
            current=_baseline((violation,)),
            base_scan=[violation],
            head_scan=[],
            changed=False,
        )


def test_base_baseline_must_match_base_scan() -> None:
    violation = _violation()

    with pytest.raises(BaselineError, match="Base baseline does not match"):
        _validate_transition(
            trusted=_baseline((violation,)),
            current=_baseline((violation,)),
            base_scan=[],
            head_scan=[violation],
            changed=False,
        )


def test_baseline_parser_failure_is_fail_closed() -> None:
    with pytest.raises(BaselineError, match="Invalid baseline JSON"):
        Baseline.from_text("{", source="broken-baseline.json")


def test_merge_base_failure_is_fail_closed(tmp_path: Path) -> None:
    root = _git_repository(tmp_path)

    with pytest.raises(GitSnapshotError, match="merge-base"):
        merge_base(root, "missing-base")


def test_staged_snapshot_scans_index_not_worktree(tmp_path: Path) -> None:
    root = _git_repository(tmp_path)
    relative = "apps/web-ui-service/app/services/evie_ai/staged sample.py"
    path = root / relative
    path.parent.mkdir(parents=True)
    path.write_text("VALUE: int = 1\n", encoding="utf-8")
    _commit_all(root, "initial")
    path.write_text(_violating_staged_source(), encoding="utf-8")
    _git(root, "add", "--", relative)
    path.write_text("VALUE: int = 2\n", encoding="utf-8")

    with staged_snapshot(root) as snapshot:
        staged_path = snapshot / relative
        changed = changed_quality_files(
            root,
            scan_root=snapshot,
            base_ref="HEAD",
            staged=True,
        )
        assert changed == [staged_path]
        assert "datetime.now()" in staged_path.read_text(encoding="utf-8")
        assert scan_ruff(snapshot, changed, python_bin=sys.executable)
        assert scan_format(snapshot, changed, python_bin=sys.executable)
        assert scan_mypy(
            snapshot,
            (relative,),
            python_bin=sys.executable,
        )
        rules = {item.rule for item in scan_ast_rules(snapshot, changed)}
        assert "EQA001" in rules

    assert path.read_text(encoding="utf-8") == "VALUE: int = 2\n"
    assert b"datetime.now()" in _git(root, "show", f":{relative}").stdout


def test_name_status_parser_preserves_all_path_kinds() -> None:
    output = (
        b"A\0new file.py\0"
        b"M\0modified.py\0"
        b"D\0deleted.py\0"
        b"R100\0old name.py\0renamed \xe6\xb5\x8b\xe8\xaf\x95.py\0"
        b"C100\0source.py\0copied \xe6\x96\x87\xe4\xbb\xb6.py\0"
    )

    assert _parse_name_status_z(output) == (
        GitChange(status="A", paths=("new file.py",)),
        GitChange(status="M", paths=("modified.py",)),
        GitChange(status="D", paths=("deleted.py",)),
        GitChange(
            status="R100",
            paths=("old name.py", "renamed 测试.py"),
        ),
        GitChange(
            status="C100",
            paths=("source.py", "copied 文件.py"),
        ),
    )


def test_git_discovery_handles_rename_delete_copy_space_and_unicode(
    tmp_path: Path,
) -> None:
    root = _git_repository(tmp_path)
    directory = root / "apps/web-ui-service/app/services/evie_ai"
    directory.mkdir(parents=True)
    old_path = directory / "old name.py"
    deleted_path = directory / "删除 file.py"
    copy_source = directory / "copy source.py"
    old_path.write_text("RENAMED = True\n", encoding="utf-8")
    deleted_path.write_text("DELETED = True\n", encoding="utf-8")
    copy_source.write_text("COPIED = True\n", encoding="utf-8")
    _commit_all(root, "paths")
    renamed_path = directory / "重命名 file.py"
    copied_path = directory / "复制 file.py"
    _git(
        root, "mv", str(old_path.relative_to(root)), str(renamed_path.relative_to(root))
    )
    _git(root, "rm", "--", str(deleted_path.relative_to(root)))
    shutil.copyfile(copy_source, copied_path)
    _git(root, "add", "--", str(copied_path.relative_to(root)))

    changes = discover_changes(root, base_ref="HEAD", staged=True)
    all_paths = {path for change in changes for path in change.paths}
    statuses = {change.status[0] for change in changes}

    assert {"R", "D", "C"}.issubset(statuses)
    assert str(old_path.relative_to(root)) in all_paths
    assert str(renamed_path.relative_to(root)) in all_paths
    assert str(deleted_path.relative_to(root)) in all_paths
    assert str(copied_path.relative_to(root)) in all_paths


@pytest.mark.parametrize("output", ["", "not-json"])
def test_ruff_empty_or_malformed_output_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: str,
) -> None:
    path = _sample_file(tmp_path)
    monkeypatch.setattr(
        tool_rules,
        "_run",
        lambda *_args, **_kwargs: _completed(1, stdout=output),
    )

    with pytest.raises(QualityToolError):
        scan_ruff(tmp_path, [path], python_bin=sys.executable)


@pytest.mark.parametrize("output", ["", "unknown format diagnostic"])
def test_format_empty_or_malformed_output_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: str,
) -> None:
    path = _sample_file(tmp_path)
    monkeypatch.setattr(
        tool_rules,
        "_run",
        lambda *_args, **_kwargs: _completed(1, stdout=output),
    )

    with pytest.raises(QualityToolError):
        scan_format(tmp_path, [path], python_bin=sys.executable)


@pytest.mark.parametrize("output", ["", "unknown mypy diagnostic"])
def test_mypy_empty_or_malformed_output_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: str,
) -> None:
    _sample_file(tmp_path)
    monkeypatch.setattr(
        tool_rules,
        "_run",
        lambda *_args, **_kwargs: _completed(1, stdout=output),
    )

    with pytest.raises(QualityToolError):
        scan_mypy(tmp_path, ("sample.py",), python_bin=sys.executable)


@pytest.mark.parametrize("scanner", ["ruff", "format", "mypy"])
def test_abnormal_tool_exit_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scanner: str,
) -> None:
    path = _sample_file(tmp_path)
    monkeypatch.setattr(
        tool_rules,
        "_run",
        lambda *_args, **_kwargs: _completed(2, stderr="tool crashed"),
    )

    with pytest.raises(QualityToolError, match="exit 2"):
        if scanner == "ruff":
            scan_ruff(tmp_path, [path], python_bin=sys.executable)
        elif scanner == "format":
            scan_format(tmp_path, [path], python_bin=sys.executable)
        else:
            scan_mypy(tmp_path, ("sample.py",), python_bin=sys.executable)


def test_missing_tool_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _sample_file(tmp_path)

    def missing_tool(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError("missing")

    monkeypatch.setattr(tool_rules.subprocess, "run", missing_tool)

    with pytest.raises(QualityToolError, match="Unable to start"):
        scan_ruff(tmp_path, [path], python_bin="/missing/python")


def _violating_staged_source() -> str:
    return (
        "import os\n"
        "from datetime import datetime\n\n"
        'value: int="wrong"\n\n'
        "def current_time() -> object:\n"
        "    return datetime.now()\n"
    )


def _sample_file(root: Path) -> Path:
    path = root / "sample.py"
    path.write_text("VALUE = 1\n", encoding="utf-8")
    return path


def _arguments(*, base_ref: str) -> Namespace:
    return Namespace(
        baseline=BASELINE_PATH,
        base_ref=base_ref,
        staged=False,
        write_baseline=False,
        python_bin=sys.executable,
    )


def _validate_transition(
    *,
    trusted: Baseline,
    current: Baseline,
    base_scan: list[Violation],
    head_scan: list[Violation],
    changed: bool = True,
) -> tuple[Violation, ...]:
    trusted_text = json.dumps(trusted.to_dict(), sort_keys=True)
    current_text = (
        json.dumps(current.to_dict(), sort_keys=True) if changed else trusted_text
    )
    return _validate_baseline_transition(
        trusted_ref="base-commit",
        trusted=trusted,
        current=current,
        trusted_text=trusted_text,
        current_text=current_text,
        base_violations=base_scan,
        head_violations=head_scan,
    )


def _write_baseline(root: Path, baseline: Baseline) -> None:
    path = root / BASELINE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(baseline.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )


def _baseline(violations: tuple[Violation, ...]) -> Baseline:
    return Baseline(
        source_commit="0" * 40,
        generated_at="2026-07-28T00:00:00+00:00",
        tools=ToolVersions(
            python="Python 3.13.2",
            ruff="ruff 0.15.9",
            mypy="mypy 1.20.0",
        ),
        violations=violations,
    )


def _violation(
    *,
    rule: str = "EQA001",
    symbol: str = "sample",
) -> Violation:
    return Violation(
        rule=rule,
        path="sample.py",
        line=10,
        message="sample violation",
        fix="fix the sample",
        symbol=symbol,
    )


def _git_repository(root: Path) -> Path:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "quality@example.test")
    _git(root, "config", "user.name", "Quality Gate")
    return root


def _commit_all(root: Path, message: str) -> None:
    _git(root, "add", "--all")
    _git(root, "commit", "-q", "-m", message)


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ("git", *arguments),
        cwd=root,
        check=True,
        capture_output=True,
    )


def _completed(
    returncode: int,
    *,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["tool"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
