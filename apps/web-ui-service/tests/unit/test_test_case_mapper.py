# ruff: noqa: E402
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))

from app.models.test_case import (
    TestCase as CaseModel,
    TestCaseDefect as CaseDefectModel,
    TestCaseExecution as CaseExecutionModel,
    TestCaseVersion as CaseVersionModel,
)
from app.services import test_case_mapper


def test_to_list_item_marks_data_config_enabled() -> None:
    case = CaseModel(
        id=7,
        name="商品查询",
        product_line="电商平台",
        module="商品中心",
        priority="P1",
        test_type="ui",
        tags=["smoke"],
        markers=["regression"],
        creator="qa",
        pytest_path="tests/ui/test_product.py",
        status="active",
        script_code="assert True",
        data_config={"enabled": True, "parameters": ["keyword"], "rows": [["耳机"]]},
        last_execution_result="passed",
    )

    item = test_case_mapper.to_list_item(case, latest_version_no=3)

    assert item["id"] == 7
    assert item["data_config_enabled"] is True
    assert item["markers"] == ["regression"]
    assert item["latest_version_no"] == 3


def test_build_case_detail_payload_formats_nested_sections() -> None:
    now = datetime(2026, 4, 3, 12, 0, 0)
    case = CaseModel(
        id=9,
        name="订单提交流程",
        product_line="电商平台",
        module="订单中心",
        priority="P1",
        test_type="ui",
        tags=["smoke"],
        markers=["p0"],
        creator="lead",
        pytest_path="tests/ui/test_order.py",
        status="active",
        script_code="def test_order():\n    assert True\n",
        data_config={"enabled": False, "parameters": [], "rows": []},
        last_execution_result="failed",
        created_at=now,
        updated_at=now,
    )
    defects = [CaseDefectModel(id=3, case_id=9, defect_key="BUG-9", defect_url="https://jira.local/BUG-9", created_at=now)]
    executions = [CaseExecutionModel(id=4, case_id=9, status="failed", duration_ms=3200, report_url="", executed_at=now)]
    versions = [CaseVersionModel(id=5, case_id=9, version_no=2, script_code="assert True", changed_by="lead", change_summary="script updated", created_at=now)]

    payload = test_case_mapper.build_case_detail_payload(
        case,
        defects,
        executions,
        versions,
        {"enabled": False, "parameters": [], "rows": []},
        normalize_report_url=lambda report_url, execution_id: report_url or f"/reports/{execution_id}",
    )

    basic = payload["basic"]
    execution_items = payload["executions"]
    defect_items = payload["defects"]
    version_items = payload["versions"]
    assert isinstance(basic, dict)
    assert isinstance(execution_items, list) and execution_items
    assert isinstance(defect_items, list) and defect_items
    assert isinstance(version_items, list) and version_items
    assert isinstance(execution_items[0], dict)
    assert isinstance(defect_items[0], dict)
    assert isinstance(version_items[0], dict)
    assert basic["id"] == 9
    assert execution_items[0]["report_url"] == "/reports/4"
    assert defect_items[0]["defect_key"] == "BUG-9"
    assert version_items[0]["version_no"] == 2
