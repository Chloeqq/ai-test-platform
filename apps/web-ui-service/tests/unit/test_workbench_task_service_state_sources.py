from __future__ import annotations

from pathlib import Path

from app.services import workbench_task_service as task_service


def test_collect_execution_records_with_meta_does_not_re_read_runtime_file(tmp_path) -> None:
    runtime_runs_file = tmp_path / "runtime-runs.json"
    runtime_runs_file.write_text('[{"run_id":"run-from-file","execution_record":{"run_id":"run-from-file","status":"queued"}}]\n', encoding="utf-8")

    read_calls = {"count": 0}

    def _read_json_list(path: Path) -> list[dict[str, object]]:
        read_calls["count"] += 1
        if read_calls["count"] == 1:
            return []
        raise AssertionError("collect_execution_records_with_meta must not re-read runtime-runs.json as fallback")

    rows, meta = task_service.collect_execution_records_with_meta(
        limit=100,
        compat_scan_enabled=True,
        artifact_roots=[],
        logger=type("Logger", (), {"warning": staticmethod(lambda *args, **kwargs: None)})(),
        normalize_evidence_manifest_payload=lambda payload: payload if isinstance(payload, dict) else {},
        resolve_manifest_entries=lambda entries, root: [],
        load_execution_record_payload=lambda path: {},
        execution_record_time_value=task_service.execution_record_time_value,
        runtime_jobs=[],
        runtime_runs_file=runtime_runs_file,
        runtime_view_from_entry=lambda entry: entry if isinstance(entry, dict) else {},
        read_json_list=_read_json_list,
        normalize_execution_record_payload=lambda payload: payload if isinstance(payload, dict) else {},
    )

    assert rows == []
    assert read_calls["count"] == 1
