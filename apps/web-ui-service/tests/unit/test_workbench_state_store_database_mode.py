from __future__ import annotations

import pathlib

from app.services import workbench_state_store as store


def _fail_on_file_write(*args, **kwargs):  # type: ignore[no-untyped-def]
    raise AssertionError("database mode must not write JSON snapshots")


def test_write_json_list_in_database_mode_does_not_touch_files(monkeypatch, tmp_path) -> None:
    path = tmp_path / "history.json"
    calls: list[tuple[pathlib.Path, list[dict[str, object]]]] = []

    monkeypatch.setattr(store, "_is_db_enabled_for_path", lambda _path: True)
    monkeypatch.setattr(store, "_replace_db_items", lambda target, items, db=None: calls.append((target, list(items))))
    monkeypatch.setattr(pathlib.Path, "write_text", _fail_on_file_write)

    store.write_json_list(path, [{"run_id": "run-1"}])

    assert calls == [(path, [{"run_id": "run-1"}])]


def test_append_history_in_database_mode_does_not_touch_files(monkeypatch) -> None:
    monkeypatch.setattr(store, "_is_db_enabled_for_path", lambda _path: True)
    monkeypatch.setattr(store, "_upsert_db_item", lambda *args, **kwargs: None)
    monkeypatch.setattr(pathlib.Path, "write_text", _fail_on_file_write)

    store.append_history({"run_id": "run-1", "action": "created"})


def test_append_runtime_run_and_update_runtime_run_in_database_mode_do_not_touch_files(monkeypatch) -> None:
    monkeypatch.setattr(store, "_is_db_enabled_for_path", lambda _path: True)
    monkeypatch.setattr(store, "_upsert_db_item", lambda *args, **kwargs: None)
    monkeypatch.setattr(store, "_read_db_items", lambda _path, db=None: [])
    monkeypatch.setattr(pathlib.Path, "write_text", _fail_on_file_write)

    store.append_runtime_run({"run_id": "run-1"})
    store.update_runtime_run("run-1", {"status": "running"})


def test_read_json_list_in_database_mode_does_not_fallback_to_file(monkeypatch, tmp_path) -> None:
    path = tmp_path / "history.json"
    path.write_text('[{"run_id":"run-1"}]\n', encoding="utf-8")

    monkeypatch.setattr(store, "_is_db_enabled_for_path", lambda _path: True)
    monkeypatch.setattr(store, "_read_db_items", lambda _path, db=None: [])
    monkeypatch.setattr(store, "_read_file_json_list", lambda _path: [{"run_id": "file-run"}])
    monkeypatch.setattr(store, "_replace_db_items", lambda target, items, db=None: _fail_on_file_write())

    assert store.read_json_list(path) == []
