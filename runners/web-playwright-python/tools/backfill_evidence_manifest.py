#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime_compat import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER_ROOT = REPO_ROOT / "runners" / "web-playwright-python"
DEFAULT_ARTIFACT_ROOTS = [
    RUNNER_ROOT / "artifacts",
]

try:
    from shared_backend.schemas import normalize_evidence_manifest_v1
except Exception:  # pragma: no cover
    normalize_evidence_manifest_v1 = None


MANIFEST_NAMES = {"evidence_manifest.json", "manifest.json"}


@dataclass
class BackfillResult:
    scanned_dirs: int = 0
    existing_manifest: int = 0
    generated_manifest: int = 0
    dry_run_candidates: int = 0
    skipped_empty: int = 0
    errors: int = 0


def _manifest_path_entry(path: Path, *, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path.resolve())


def _collect_case_dirs(artifact_root: Path) -> list[Path]:
    if not artifact_root.exists():
        return []
    case_dirs: list[Path] = []
    for child in sorted(artifact_root.iterdir()):
        if not child.is_dir():
            continue
        case_dirs.append(child)
    return case_dirs


def _resolve_existing_file(path: Path) -> Path | None:
    if path.exists() and path.is_file():
        return path.resolve()
    return None


def _build_manifest(case_dir: Path) -> dict[str, Any] | None:
    known_paths = {
        "screenshots": [case_dir / "failed.png"],
        "html_pages": [case_dir / "page.html"],
        "meta_files": [case_dir / "meta.txt"],
        "analysis_files": [case_dir / "analysis.txt"],
        "suggestion_files": [case_dir / "suggestion.json"],
        "execution_record_files": [case_dir / "execution_record.json"],
        "self_healing_result_files": [case_dir / "self_healing_result.json"],
        "videos": sorted(case_dir.glob("*.webm")),
    }

    categories: dict[str, list[str]] = {}
    seen: set[Path] = set()
    for key, candidates in known_paths.items():
        entries: list[str] = []
        for candidate in candidates:
            resolved = _resolve_existing_file(candidate)
            if resolved is None or resolved in seen:
                continue
            seen.add(resolved)
            entries.append(_manifest_path_entry(resolved, root=case_dir))
        categories[key] = entries

    other_files: list[str] = []
    for path in sorted(case_dir.iterdir()):
        if not path.is_file():
            continue
        if path.name in MANIFEST_NAMES:
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        other_files.append(_manifest_path_entry(resolved, root=case_dir))
    categories["other_files"] = other_files

    total_files = sum(len(items) for items in categories.values())
    if total_files == 0:
        return None

    payload = {
        "version": "EvidenceManifestV1",
        "schema_version": "evidence-manifest.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "artifact_root": str(case_dir.resolve()),
        **categories,
        "total_files": total_files,
    }
    if normalize_evidence_manifest_v1 is None:
        return payload
    try:
        normalized, _warnings = normalize_evidence_manifest_v1(payload, strict=False)
        return normalized
    except Exception:
        return payload


def _load_legacy_run_artifact_roots() -> list[Path]:
    runs_root = REPO_ROOT / "web-ui" / "state" / "runs"
    if not runs_root.exists():
        return []
    return sorted(path for path in runs_root.glob("*-artifacts") if path.is_dir())


def backfill_manifests(*, artifact_roots: list[Path], include_legacy_runs: bool, dry_run: bool) -> BackfillResult:
    result = BackfillResult()
    roots = list(artifact_roots)
    if include_legacy_runs:
        roots.extend(_load_legacy_run_artifact_roots())

    dedup_roots: list[Path] = []
    seen_roots: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved in seen_roots:
            continue
        seen_roots.add(resolved)
        dedup_roots.append(resolved)

    for artifact_root in dedup_roots:
        case_dirs = _collect_case_dirs(artifact_root)
        for case_dir in case_dirs:
            result.scanned_dirs += 1
            manifest_path = case_dir / "evidence_manifest.json"
            if manifest_path.exists():
                result.existing_manifest += 1
                continue
            payload = _build_manifest(case_dir)
            if payload is None:
                result.skipped_empty += 1
                continue
            if dry_run:
                result.dry_run_candidates += 1
                continue
            try:
                manifest_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                result.generated_manifest += 1
            except Exception:
                result.errors += 1
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill missing evidence_manifest.json for existing artifact dirs.")
    parser.add_argument(
        "--artifact-root",
        action="append",
        default=[],
        help="Artifact root directory (can pass multiple times). Defaults to runners/web-playwright-python/artifacts.",
    )
    parser.add_argument(
        "--include-legacy-runs",
        action="store_true",
        help="Also scan web-ui/state/runs/*-artifacts directories.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print candidates; do not write files.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    roots: list[Path]
    if args.artifact_root:
        roots = [Path(item).expanduser() for item in args.artifact_root]
    else:
        roots = list(DEFAULT_ARTIFACT_ROOTS)

    result = backfill_manifests(
        artifact_roots=roots,
        include_legacy_runs=bool(args.include_legacy_runs),
        dry_run=bool(args.dry_run),
    )

    summary = {
        "scanned_dirs": result.scanned_dirs,
        "existing_manifest": result.existing_manifest,
        "generated_manifest": result.generated_manifest,
        "dry_run_candidates": result.dry_run_candidates,
        "skipped_empty": result.skipped_empty,
        "errors": result.errors,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if result.errors > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
