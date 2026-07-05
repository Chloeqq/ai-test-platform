from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))
existing_app = sys.modules.get("app")
if existing_app is not None and not getattr(existing_app, "__path__", None):
    sys.modules.pop("app", None)

from app.core.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.test_case import TestCase as CaseRecord  # noqa: E402


def _create_case(
    client: TestClient,
    *,
    name: str,
    script_code: str,
    data_config: dict,
    creator: str = "qa",
    product_line: str = "电商平台",
    module: str = "商品中心",
    status: str = "active",
    test_type: str = "ui",
) -> int:
    response = client.post(
        "/api/test-cases",
        json={
            "mode": "manual",
            "name": name,
            "product_line": product_line,
            "module": module,
            "priority": "P1",
            "test_type": test_type,
            "tags": ["ddt", "smoke"],
            "markers": ["smoke", "regression"],
            "creator": creator,
            "pytest_path": "tests/ui/oms/test_return_apply.py",
            "status": status,
            "script_code": script_code,
            "requirement": "",
            "data_config": data_config,
        },
    )
    assert response.status_code == 201, response.text
    item = response.json()["item"]
    return int(item["id"])


def _set_case_last_result(case_id: int, result: str) -> None:
    with SessionLocal() as db:
        case = db.get(CaseRecord, case_id)
        assert case is not None
        case.last_execution_result = result
        db.commit()


def test_list_case_filters_expose_supported_structured_dimensions() -> None:
    client = TestClient(app)
    ui_case_id = _create_case(
        client,
        name=f"DDT-筛选-UI-{uuid4().hex[:8]}",
        script_code="def test_ui(page):\n    assert True\n",
        data_config={"enabled": False, "parameters": [], "rows": []},
        product_line="电商平台",
        module="商品中心",
        test_type="ui",
    )
    api_case_id = _create_case(
        client,
        name=f"DDT-筛选-API-{uuid4().hex[:8]}",
        script_code="def test_api(page):\n    assert True\n",
        data_config={"enabled": False, "parameters": [], "rows": []},
        product_line="会员体系",
        module="认证服务",
        test_type="api",
    )

    response = client.get(
        "/api/test-cases",
        params={"product_line": "会员体系", "module": "认证服务", "test_type": "api"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    item_ids = {item["id"] for item in payload["items"]}

    assert api_case_id in item_ids
    assert ui_case_id not in item_ids
    assert "会员体系" in payload["filters"]["product_lines"]
    assert "认证服务" in payload["filters"]["modules"]
    assert "api" in payload["filters"]["test_types"]
    assert any(item["id"] == api_case_id and item["latest_version_no"] for item in payload["items"])
    assert payload["search_context"]["product_line"] == "会员体系"
    assert payload["search_context"]["module"] == "认证服务"
    assert payload["search_context"]["test_type"] == "api"


def test_single_search_box_query_supports_structured_case_filters() -> None:
    client = TestClient(app)
    shared_token = uuid4().hex[:8]
    ui_case_id = _create_case(
        client,
        name=f"单搜索-{shared_token}-UI",
        script_code="def test_ui(page):\n    assert True\n",
        data_config={"enabled": False, "parameters": [], "rows": []},
        creator="owner-ui",
        product_line="电商平台",
        module="订单中心",
        status="inactive",
        test_type="ui",
    )
    api_case_id = _create_case(
        client,
        name=f"单搜索-{shared_token}-API",
        script_code="def test_api(page):\n    assert True\n",
        data_config={"enabled": False, "parameters": [], "rows": []},
        creator="qa-team",
        product_line="会员体系",
        module="认证服务",
        status="active",
        test_type="api",
    )
    _set_case_last_result(ui_case_id, "passed")
    _set_case_last_result(api_case_id, "failed")

    response = client.get(
        "/api/test-cases",
        params={"q": f"单搜索-{shared_token} 类型:api 状态:启用 创建人:qa 结果:失败"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    item_ids = {item["id"] for item in payload["items"]}

    assert api_case_id in item_ids
    assert ui_case_id not in item_ids
    assert any(item["id"] == api_case_id and item["status"] == "active" for item in payload["items"])
    assert payload["search_context"]["keyword"] == f"单搜索-{shared_token}"
    assert payload["search_context"]["test_type"] == "api"
    assert payload["search_context"]["status"] == "active"
    assert payload["search_context"]["creator"] == "qa"
    assert payload["search_context"]["last_result"] == "failed"


def test_module_tree_endpoint_returns_group_counts() -> None:
    client = TestClient(app)

    response = client.get("/api/test-cases/tree")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["items"]
    assert any(item["product_line"] == "电商平台" and item["count"] >= 1 for item in payload["items"])
    assert any(
        module["module"] == "订单中心" and module["count"] >= 1
        for item in payload["items"]
        for module in item["modules"]
    )


def test_create_case_persists_data_config() -> None:
    client = TestClient(app)
    case_name = f"DDT-创建-{uuid4().hex[:8]}"
    case_id = _create_case(
        client,
        name=case_name,
        script_code="def test_search(page):\n    assert True\n",
        data_config={
            "enabled": True,
            "parameters": ["keyword", "expected_count"],
            "rows": [["耳机", "3"], ["键盘", "2"]],
        },
    )

    detail = client.get(f"/api/test-cases/{case_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["basic"]["name"] == case_name
    assert body["basic"]["test_type"] == "ui"
    assert body["basic"]["pytest_path"] == "tests/ui/oms/test_return_apply.py"
    assert body["basic"]["markers"] == ["smoke", "regression"]
    assert body["basic"]["status"] == "active"
    assert body["basic"]["data_config_enabled"] is True
    assert body["data_config"]["enabled"] is True
    assert body["data_config"]["parameters"] == ["keyword", "expected_count"]
    assert len(body["data_config"]["rows"]) == 2

    listing = client.get("/api/test-cases")
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]
    assert any(item["id"] == case_id and item["data_config_enabled"] is True for item in items)

    exported = client.post("/api/test-cases/batch/export", json={"ids": [case_id], "format": "json"})
    assert exported.status_code == 200, exported.text
    assert '"data_config"' in exported.text


def test_update_case_data_config_refreshes_generated_script() -> None:
    client = TestClient(app)
    case_name = f"DDT-更新-{uuid4().hex[:8]}"
    case_id = _create_case(
        client,
        name=case_name,
        script_code="def test_original(page):\n    assert True\n",
        data_config={
            "enabled": True,
            "parameters": ["keyword"],
            "rows": [["耳机"]],
        },
    )

    update = client.put(
        f"/api/test-cases/{case_id}",
        json={
            "test_type": "api",
            "status": "inactive",
            "pytest_path": "tests/api/oms/test_return_apply_api.py",
            "markers": ["p0", "regression"],
            "data_config": {
                "enabled": True,
                "parameters": ["query", "expected_count"],
                "rows": [["键盘", "2"]],
            }
        },
    )
    assert update.status_code == 200, update.text
    update_body = update.json()
    assert update_body["item"]["test_type"] == "api"
    assert update_body["item"]["status"] == "inactive"
    assert update_body["item"]["pytest_path"] == "tests/api/oms/test_return_apply_api.py"
    assert update_body["item"]["markers"] == ["p0", "regression"]
    assert update_body["data_config"]["parameters"] == ["query", "expected_count"]
    assert update_body["data_config"]["enabled"] is True
    assert "DATA_CONFIG" in update_body["script_code"]
    assert '"query"' in update_body["script_code"]

    detail = client.get(f"/api/test-cases/{case_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["data_config"]["parameters"] == ["query", "expected_count"]
    assert body["basic"]["data_config_enabled"] is True

    exported = client.post("/api/test-cases/batch/export", json={"ids": [case_id], "format": "csv"})
    assert exported.status_code == 200, exported.text
    assert "data_config_enabled" in exported.text


def test_batch_update_status_marks_cases_as_deprecated() -> None:
    client = TestClient(app)
    case_name = f"DDT-状态-{uuid4().hex[:8]}"
    case_id = _create_case(
        client,
        name=case_name,
        script_code="def test_archive(page):\n    assert True\n",
        data_config={"enabled": False, "parameters": [], "rows": []},
    )

    response = client.post("/api/test-cases/batch/status", json={"ids": [case_id], "status": "deprecated"})
    assert response.status_code == 200, response.text
    assert response.json()["updated_count"] == 1

    detail = client.get(f"/api/test-cases/{case_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["basic"]["status"] == "deprecated"
    assert any("status updated to deprecated" in item["change_summary"] for item in body["versions"])
