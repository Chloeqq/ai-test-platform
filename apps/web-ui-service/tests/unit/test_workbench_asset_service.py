# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))

from app.services import workbench_asset_service as asset_service
from app.services import workbench_state_store as state_store
from shared_backend.case_ids import normalize_case_id


def test_save_and_load_test_point_asset(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(state_store, "WEB_UI_STATE_ROOT", tmp_path / "web-ui" / "state")
    def _normalize_plan(payload: dict[str, Any], strict: bool = False) -> dict[str, Any]:
        del strict
        return payload

    saved_path = asset_service.save_test_point_plan(
        project="default",
        case_id="TC-product-001",
        page="product",
        page_url="http://localhost/product",
        requirement="商品列表页",
        plan={
            "points": [{"key": "tp-1", "point_type": "assertion"}],
            "coverage": {"status": "full"},
            "review_summary": {"pending_review_count": 0},
            "confidence": 0.9,
            "warnings": ["check"],
            "requires_review": False,
        },
        now_iso_fn=lambda: "2026-03-22T17:06:51+00:00",
        normalize_test_point_plan_payload=_normalize_plan,
        upsert_test_point_asset_snapshot=lambda **kwargs: {"asset_id": kwargs["case_id"], "page": kwargs["page"]},
    )

    assert saved_path.exists()
    loaded = asset_service.load_test_point_asset("default", "TC-product-001")
    assert loaded["asset_id"] == normalize_case_id("TC-product-001")
    assert loaded["point_count"] == 1
    assert loaded["coverage"]["status"] == "full"


def test_upsert_test_point_asset_snapshot_merges_references(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(state_store, "WEB_UI_STATE_ROOT", tmp_path / "web-ui" / "state")

    plan_path = tmp_path / "plans" / "TC-001.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("{}", encoding="utf-8")
    page_object_path = tmp_path / "page-object.yaml"
    page_object_path.write_text("page: product\n", encoding="utf-8")

    asset = asset_service.upsert_test_point_asset_snapshot(
        project="default",
        case_id="TC-001",
        page="product",
        requirement="商品列表页",
        normalized_plan={
            "points": [{"key": "tp-1", "point_type": "assertion"}],
            "coverage": {"status": "partial"},
            "review_summary": {"pending_review_count": 1},
            "confidence": 0.75,
            "warnings": ["needs review"],
            "requires_review": True,
        },
        plan_path=plan_path,
        case_path=tmp_path / "case.yaml",
        page_object_path=page_object_path,
        now_iso_fn=lambda: "2026-03-22T17:06:51+00:00",
        count_test_point_types_fn=lambda _points: {"assertion_count": 1},
        build_test_point_asset_semantic_summary_fn=lambda page, _plan: {"page_type": page, "confidence": 0.8},
        build_test_point_asset_technique_summary_fn=lambda _plan: {"total_points": 1},
        merge_reference_items_fn=lambda existing, new: existing + new,
    )

    assert asset["asset_id"] == normalize_case_id("TC-001")
    assert asset["references"][0]["kind"] == "test_point_plan"
    assert asset["references"][1]["kind"] == "case_yaml"
    assert asset["references"][2]["kind"] == "page_object"
    assert asset["semantic_summary"]["page_type"] == "product"
