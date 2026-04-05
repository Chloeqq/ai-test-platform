from __future__ import annotations

from datetime import datetime

from datetime_compat import UTC
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.models.test_case import (
    TestCase,
    TestCaseDefect,
    TestCaseExecution,
    TestCaseVersion,
)


def ensure_test_cases_schema_compatibility(db: Session) -> None:
    inspector = inspect(db.get_bind())
    columns = {str(item.get("name", "")).strip() for item in inspector.get_columns("test_cases")}

    def ensure_column(column_name: str, ddl: str, fill_sql: str) -> None:
        nonlocal columns
        if column_name not in columns:
            db.execute(text(ddl))
            columns.add(column_name)
        db.execute(text(fill_sql))

    ensure_column(
        "test_type",
        "ALTER TABLE test_cases ADD COLUMN test_type VARCHAR(50)",
        "UPDATE test_cases SET test_type = 'ui' WHERE test_type IS NULL OR test_type = ''",
    )
    ensure_column(
        "markers",
        "ALTER TABLE test_cases ADD COLUMN markers JSON",
        "UPDATE test_cases SET markers = '[]' WHERE markers IS NULL",
    )
    ensure_column(
        "pytest_path",
        "ALTER TABLE test_cases ADD COLUMN pytest_path VARCHAR(500)",
        "UPDATE test_cases SET pytest_path = '' WHERE pytest_path IS NULL",
    )
    ensure_column(
        "status",
        "ALTER TABLE test_cases ADD COLUMN status VARCHAR(20)",
        "UPDATE test_cases SET status = 'active' WHERE status IS NULL OR status = ''",
    )
    ensure_column(
        "data_config",
        "ALTER TABLE test_cases ADD COLUMN data_config JSON",
        "UPDATE test_cases SET data_config = '{}' WHERE data_config IS NULL",
    )
    db.commit()


def ensure_seed_data(db: Session) -> None:
    ensure_test_cases_schema_compatibility(db)
    existing_count = db.execute(select(func.count(TestCase.id))).scalar_one()
    if existing_count and existing_count > 0:
        return

    now = datetime.now(UTC)
    seed_cases = [
        TestCase(
            name="商品搜索结果展示",
            product_line="电商平台",
            module="商品中心",
            priority="P1",
            tags=["smoke", "search", "web"],
            creator="alice",
            script_code=(
                "def test_product_search(page):\n"
                "    page.goto('/products')\n"
                "    page.fill('#search', '耳机')\n"
                "    page.click('#search-btn')\n"
                "    assert page.locator('.result-item').count() > 0\n"
            ),
            last_execution_result="passed",
            created_at=now,
            updated_at=now,
        ),
        TestCase(
            name="订单创建基础流程",
            product_line="电商平台",
            module="订单中心",
            priority="P1",
            tags=["regression", "order"],
            creator="bob",
            script_code=(
                "def test_create_order(page):\n"
                "    page.goto('/cart')\n"
                "    page.click('#checkout')\n"
                "    page.fill('#address', '上海市浦东新区')\n"
                "    page.click('#submit-order')\n"
                "    assert page.locator('.order-success').is_visible()\n"
            ),
            last_execution_result="failed",
            created_at=now,
            updated_at=now,
        ),
        TestCase(
            name="登录态过期重定向",
            product_line="会员体系",
            module="认证服务",
            priority="P2",
            tags=["auth", "api", "security"],
            creator="carol",
            script_code=(
                "def test_auth_expired_redirect(page):\n"
                "    page.goto('/profile')\n"
                "    page.context.clear_cookies()\n"
                "    page.reload()\n"
                "    assert '/login' in page.url\n"
            ),
            last_execution_result="skipped",
            created_at=now,
            updated_at=now,
        ),
    ]
    db.add_all(seed_cases)
    db.commit()

    cases = db.execute(select(TestCase)).scalars().all()
    for case in cases:
        db.add(
            TestCaseVersion(
                case_id=case.id,
                version_no=1,
                script_code=case.script_code,
                changed_by=case.creator,
                change_summary="initial version",
                created_at=now,
            )
        )

    db.add_all(
        [
            TestCaseDefect(
                case_id=cases[1].id,
                defect_key="BUG-3421",
                defect_url="https://jira.local/BUG-3421",
            ),
            TestCaseDefect(
                case_id=cases[1].id,
                defect_key="BUG-3510",
                defect_url="https://jira.local/BUG-3510",
            ),
        ]
    )
    db.add_all(
        [
            TestCaseExecution(
                case_id=cases[0].id,
                status="passed",
                duration_ms=18240,
                report_url="/reports/101",
            ),
            TestCaseExecution(
                case_id=cases[0].id,
                status="passed",
                duration_ms=16900,
                report_url="/reports/102",
            ),
            TestCaseExecution(
                case_id=cases[1].id,
                status="failed",
                duration_ms=23100,
                report_url="/reports/201",
            ),
            TestCaseExecution(
                case_id=cases[1].id,
                status="passed",
                duration_ms=21090,
                report_url="/reports/202",
            ),
            TestCaseExecution(
                case_id=cases[2].id,
                status="skipped",
                duration_ms=0,
                report_url="/reports/301",
            ),
        ]
    )
    db.commit()


def get_module_tree_items(db: Session) -> list[dict[str, object]]:
    ensure_seed_data(db)
    cases = db.execute(
        select(TestCase.product_line, TestCase.module, func.count(TestCase.id))
        .group_by(TestCase.product_line, TestCase.module)
        .order_by(
            TestCase.product_line,
            TestCase.module,
        )
    ).all()
    grouped: dict[str, dict[str, object]] = {}
    for product_line, module, count in cases:
        bucket = grouped.setdefault(
            product_line,
            {"product_line": product_line, "count": 0, "modules": []},
        )
        existing_count = bucket.get("count", 0)
        current_count = int(existing_count) if isinstance(existing_count, (int, float, str)) else 0
        bucket["count"] = current_count + int(count or 0)
        modules = bucket["modules"]
        if isinstance(modules, list):
            modules.append({"module": module, "count": int(count or 0)})
    return sorted(grouped.values(), key=lambda item: str(item["product_line"]))
