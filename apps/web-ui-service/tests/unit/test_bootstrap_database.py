from __future__ import annotations

from pathlib import Path
import importlib.util


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "bootstrap_database.py"
SPEC = importlib.util.spec_from_file_location("bootstrap_database", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
bootstrap_database = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap_database)


def test_bootstrap_database_stamps_head_when_revision_is_missing(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(bootstrap_database, "_read_alembic_revisions", lambda _url: ["20260328_110000"])
    monkeypatch.setattr(bootstrap_database, "_revision_exists", lambda _config, _revision: False)
    monkeypatch.setattr(bootstrap_database, "_ensure_alembic_version_capacity", lambda _url: None)
    monkeypatch.setattr(bootstrap_database, "_create_current_metadata", lambda _url: calls.append(("metadata", _url)))
    monkeypatch.setattr(bootstrap_database, "_current_head_revision", lambda _config: "20260408_100500_add_page_object_precondition_state")
    monkeypatch.setattr(bootstrap_database, "_stamp_database_head", lambda _url, revision: calls.append(("stamp", revision)))
    monkeypatch.setattr(bootstrap_database.command, "upgrade", lambda *_args, **_kwargs: calls.append(("upgrade", None)))

    bootstrap_database._bootstrap_database(object(), str(tmp_path / "legacy.db"))

    assert calls == [
        ("metadata", str(tmp_path / "legacy.db")),
        ("stamp", "20260408_100500_add_page_object_precondition_state"),
    ]
