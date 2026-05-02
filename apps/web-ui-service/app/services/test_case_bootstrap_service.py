from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from datetime_compat import UTC
from shared_backend.case_ids import (
    build_case_metadata,
    infer_client_code,
    normalize_case_id,
)
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.models.test_case import (
    TestCase,
    TestCaseDefect,
    TestCaseExecution,
    TestCaseStep,
    TestCaseTreeNode,
    TestCaseVersion,
)
from app.models.test_point import TestPoint
from app.models.test_project import TestProject
from app.services.test_case_data_service import (
    normalize_status,
    normalize_test_case_type,
    normalize_text_list,
    render_test_steps_text,
)
from app.services.workbench_generation_api.repository import WorkbenchGenerationRepository

REPO_ROOT = Path(__file__).resolve().parents[4]
ASSETS_CASES_ROOT = REPO_ROOT / "assets" / "test-cases"
AI_CASES_ROOT = ASSETS_CASES_ROOT / "ai-generated"
DEFAULT_PROJECT_CODE = "mall"
DEFAULT_PROJECT_NAME = "Mall"
DEFAULT_PROJECT_SOURCE_TERMS = {
    "商品货号": "product_sn",
    "商品分类": "product_category",
    "商品品牌": "product_brand",
    "商品列表": "product_list",
    "商品菜单": "product_menu",
    "商品名称": "product_name",
    "手机通讯": "mobile_communication",
    "手机数码": "mobile_digital",
    "手机配件": "mobile_accessories",
    "商品": "product",
    "品牌": "brand",
    "分类": "category",
    "货号": "sn",
}


def _normalize_project_code(value: str) -> str:
    text = str(value or "").strip().lower()
    return text or DEFAULT_PROJECT_CODE


def _infer_source(*, creator: str, tags: list[str]) -> str:
    corpus = " ".join([str(creator or "").strip().lower(), *[str(item).strip().lower() for item in tags]])
    if "fallback" in corpus:
        return "fb"
    if "ai-generated" in corpus or "ai" in corpus:
        return "ai"
    return "mn"


def _infer_created_source(source: str) -> str:
    if source == "ai":
        return "ai"
    if source == "fb":
        return "workbench"
    if source == "imp":
        return "import"
    return "manual"


def _existing_asset_case_ids() -> list[str]:
    items: list[str] = []
    if not ASSETS_CASES_ROOT.exists():
        return items
    for path in ASSETS_CASES_ROOT.rglob("*.yaml"):
        items.append(path.stem)
    return items


def _stable_case_sort_key(case: TestCase) -> tuple[int, int]:
    created_at = case.created_at
    if isinstance(created_at, datetime):
        return (int(created_at.timestamp()), case.id)
    return (0, case.id)


def _resolve_case_metadata(case: TestCase) -> dict[str, str]:
    tags = list(case.tags or [])
    source = _infer_source(creator=case.creator, tags=tags)
    metadata = build_case_metadata(
        page=case.module or case.product_line or "common",
        module=case.module or case.product_line or "core",
        title=case.name,
        description=case.expected_result or case.notes or "",
        tags=tags,
        project=_normalize_project_code(case.project_code),
        client=case.client or infer_client_code(case.test_type, runner=case.pytest_path),
        source_hint=source,
        legacy=source == "imp",
    )
    metadata["source"] = case.source or metadata["source"] or source
    return metadata


def _assign_case_defaults(
    case: TestCase,
    *,
    existing_case_ids: list[str],
    latest_report_urls: dict[int, str],
    case_id_repository: WorkbenchGenerationRepository,
) -> bool:
    changed = False
    metadata = _resolve_case_metadata(case)
    resolved_case_id = case_id_repository.allocate_case_id(
        requested_case_id=str(case.case_id or "").strip(),
        project=metadata["project"],
        page=case.module or case.product_line or metadata["page_code"],
        module=case.module or case.product_line or metadata["module_code"],
        ai_cases_root=AI_CASES_ROOT,
        existing_case_ids=existing_case_ids,
    )

    def assign(attr: str, value: Any) -> None:
        nonlocal changed
        if getattr(case, attr) != value:
            setattr(case, attr, value)
            changed = True

    assign("case_id", resolved_case_id)
    assign("project_code", _normalize_project_code(case.project_code or metadata["project"]))
    assign("client", case.client or metadata["client"])
    assign("page_code", case.page_code or metadata["page_code"])
    assign("page_name", case.page_name or metadata["page_name"])
    assign("module_code", case.module_code or metadata["module_code"])
    assign("module_name", case.module_name or metadata["module_name"])
    assign("case_type", case.case_type or metadata["case_type"])
    assign("source", case.source or metadata["source"])
    assign("chain_stage", case.chain_stage or "")
    assign("sut_service", case.sut_service or "")
    assign("related_services", normalize_text_list(case.related_services if isinstance(case.related_services, list) else []))
    assign("scenario_types", normalize_text_list(case.scenario_types if isinstance(case.scenario_types, list) else []))
    assign("trigger_entry", case.trigger_entry or ("API" if str(case.test_type or "").strip().lower() == "api" else "UI"))
    assign("fault_injection_type", case.fault_injection_type or "")
    assign("fault_injection_target", case.fault_injection_target or "")
    assign("fault_injection_params", case.fault_injection_params or "")
    assign("setup_sql", case.setup_sql or "")
    assign("precondition_state", case.precondition_state or "")
    normalized_steps = case.test_steps if isinstance(case.test_steps, list) else []
    assign("test_steps", normalized_steps)
    assign("test_steps_text", case.test_steps_text or render_test_steps_text(normalized_steps))
    assign("concurrency_model", case.concurrency_model or "")
    assign("retry_policy", case.retry_policy or "")
    assign("expected_result", case.expected_result or "")
    assign("assert_sql", case.assert_sql or "")
    assign("event_assertion", case.event_assertion or "")
    assign("metric_assertion", case.metric_assertion or "")
    assign("cleanup_script", case.cleanup_script or "")
    assign("artifact_links", normalize_text_list(case.artifact_links if isinstance(case.artifact_links, list) else []))
    assign("notes", case.notes or "")
    assign("assignee", case.assignee or "")
    assign("automation_status", case.automation_status or ("automated" if (case.pytest_path or case.script_code) else "manual"))
    assign("created_source", case.created_source or _infer_created_source(case.source or metadata["source"]))
    assign("source_ref", case.source_ref or "")
    assign("last_report_url", case.last_report_url or latest_report_urls.get(case.id, ""))
    if case.last_synced_at is None and str(case.created_source or "").strip().lower() in {"ai", "workbench"}:
        assign("last_synced_at", case.updated_at or case.created_at)
    return changed


def ensure_test_cases_schema_compatibility(db: Session) -> None:
    inspector = inspect(db.get_bind())
    dialect_name = str(inspector.bind.dialect.name or "").strip().lower()
    column_details = {
        str(item.get("name", "")).strip(): item
        for item in inspector.get_columns("test_cases")
    }
    columns = set(column_details.keys())

    def ensure_column(column_name: str, ddl: str, fill_sql: str | None = None) -> None:
        nonlocal columns
        if column_name not in columns:
            db.execute(text(ddl))
            columns.add(column_name)
        if fill_sql:
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
    ensure_column("case_id", "ALTER TABLE test_cases ADD COLUMN case_id VARCHAR(64)")
    ensure_column("project_code", "ALTER TABLE test_cases ADD COLUMN project_code VARCHAR(20)")
    ensure_column("client", "ALTER TABLE test_cases ADD COLUMN client VARCHAR(10)")
    ensure_column("page_code", "ALTER TABLE test_cases ADD COLUMN page_code VARCHAR(20)")
    ensure_column("page_name", "ALTER TABLE test_cases ADD COLUMN page_name VARCHAR(100)")
    ensure_column("module_code", "ALTER TABLE test_cases ADD COLUMN module_code VARCHAR(20)")
    ensure_column("module_name", "ALTER TABLE test_cases ADD COLUMN module_name VARCHAR(100)")
    ensure_column("case_type", "ALTER TABLE test_cases ADD COLUMN case_type VARCHAR(10)")
    ensure_column("source", "ALTER TABLE test_cases ADD COLUMN source VARCHAR(10)")
    ensure_column("chain_stage", "ALTER TABLE test_cases ADD COLUMN chain_stage VARCHAR(120)")
    ensure_column("sut_service", "ALTER TABLE test_cases ADD COLUMN sut_service VARCHAR(120)")
    ensure_column("related_services", "ALTER TABLE test_cases ADD COLUMN related_services JSON")
    ensure_column("scenario_types", "ALTER TABLE test_cases ADD COLUMN scenario_types JSON")
    ensure_column("trigger_entry", "ALTER TABLE test_cases ADD COLUMN trigger_entry VARCHAR(40)")
    ensure_column("fault_injection_type", "ALTER TABLE test_cases ADD COLUMN fault_injection_type VARCHAR(80)")
    ensure_column("fault_injection_target", "ALTER TABLE test_cases ADD COLUMN fault_injection_target VARCHAR(255)")
    ensure_column("fault_injection_params", "ALTER TABLE test_cases ADD COLUMN fault_injection_params TEXT")
    ensure_column("setup_sql", "ALTER TABLE test_cases ADD COLUMN setup_sql TEXT")
    ensure_column("precondition_state", "ALTER TABLE test_cases ADD COLUMN precondition_state TEXT")
    ensure_column("test_steps", "ALTER TABLE test_cases ADD COLUMN test_steps JSON")
    ensure_column("test_steps_text", "ALTER TABLE test_cases ADD COLUMN test_steps_text TEXT")
    ensure_column("concurrency_model", "ALTER TABLE test_cases ADD COLUMN concurrency_model VARCHAR(120)")
    ensure_column("retry_policy", "ALTER TABLE test_cases ADD COLUMN retry_policy TEXT")
    ensure_column("expected_result", "ALTER TABLE test_cases ADD COLUMN expected_result TEXT")
    ensure_column("assert_sql", "ALTER TABLE test_cases ADD COLUMN assert_sql TEXT")
    ensure_column("event_assertion", "ALTER TABLE test_cases ADD COLUMN event_assertion TEXT")
    ensure_column("metric_assertion", "ALTER TABLE test_cases ADD COLUMN metric_assertion TEXT")
    ensure_column("cleanup_script", "ALTER TABLE test_cases ADD COLUMN cleanup_script TEXT")
    ensure_column("artifact_links", "ALTER TABLE test_cases ADD COLUMN artifact_links JSON")
    ensure_column("notes", "ALTER TABLE test_cases ADD COLUMN notes TEXT")
    ensure_column("assignee", "ALTER TABLE test_cases ADD COLUMN assignee VARCHAR(120)")
    ensure_column("automation_status", "ALTER TABLE test_cases ADD COLUMN automation_status VARCHAR(20)")
    ensure_column("created_source", "ALTER TABLE test_cases ADD COLUMN created_source VARCHAR(40)")
    ensure_column("source_ref", "ALTER TABLE test_cases ADD COLUMN source_ref VARCHAR(255)")
    ensure_column("last_report_url", "ALTER TABLE test_cases ADD COLUMN last_report_url TEXT")
    last_synced_at_type = "TIMESTAMP WITH TIME ZONE" if dialect_name == "postgresql" else "DATETIME"
    ensure_column("last_synced_at", f"ALTER TABLE test_cases ADD COLUMN last_synced_at {last_synced_at_type}")
    created_at_type = "TIMESTAMP WITH TIME ZONE" if dialect_name == "postgresql" else "DATETIME"
    ensure_column("created_at", f"ALTER TABLE test_cases ADD COLUMN created_at {created_at_type}")
    ensure_column("updated_at", f"ALTER TABLE test_cases ADD COLUMN updated_at {created_at_type}")

    if dialect_name == "postgresql":
        db.execute(
            text(
                "UPDATE test_cases "
                "SET created_at = COALESCE(created_at, NOW()), "
                "updated_at = COALESCE(updated_at, NOW()) "
                "WHERE created_at IS NULL OR updated_at IS NULL"
            )
        )
        created_at_default = str((column_details.get("created_at") or {}).get("default") or "").strip().lower()
        updated_at_default = str((column_details.get("updated_at") or {}).get("default") or "").strip().lower()
        if "now()" not in created_at_default and "current_timestamp" not in created_at_default:
            db.execute(text("ALTER TABLE test_cases ALTER COLUMN created_at SET DEFAULT NOW()"))
        if "now()" not in updated_at_default and "current_timestamp" not in updated_at_default:
            db.execute(text("ALTER TABLE test_cases ALTER COLUMN updated_at SET DEFAULT NOW()"))
        if bool((column_details.get("created_at") or {}).get("nullable")):
            db.execute(text("ALTER TABLE test_cases ALTER COLUMN created_at SET NOT NULL"))
        if bool((column_details.get("updated_at") or {}).get("nullable")):
            db.execute(text("ALTER TABLE test_cases ALTER COLUMN updated_at SET NOT NULL"))
    else:
        db.execute(
            text(
                "UPDATE test_cases "
                "SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP), "
                "updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP) "
                "WHERE created_at IS NULL OR updated_at IS NULL"
            )
        )
    db.commit()


def ensure_project_seed(db: Session) -> None:
    TestProject.__table__.create(bind=db.get_bind(), checkfirst=True)
    existing = db.execute(
        select(TestProject).where(TestProject.project_code == DEFAULT_PROJECT_CODE)
    ).scalar_one_or_none()
    if existing:
        current_terms = dict(existing.source_terms_json or {})
        missing_terms = {
            phrase: code
            for phrase, code in DEFAULT_PROJECT_SOURCE_TERMS.items()
            if phrase not in current_terms
        }
        if missing_terms:
            existing.source_terms_json = {**DEFAULT_PROJECT_SOURCE_TERMS, **current_terms}
            db.add(existing)
            db.commit()
        return
    db.add(
        TestProject(
            project_code=DEFAULT_PROJECT_CODE,
            project_name=DEFAULT_PROJECT_NAME,
            description="默认平台项目，用于统一当前测试用例资产。",
            source_terms_json=DEFAULT_PROJECT_SOURCE_TERMS,
            status="active",
            created_by="system",
        )
    )
    db.commit()


def backfill_test_case_metadata(db: Session) -> None:
    cases = list(db.execute(select(TestCase).order_by(TestCase.id.asc())).scalars().all())
    if not cases:
        return
    case_id_repository = WorkbenchGenerationRepository(db)
    execution_rows = db.execute(
        select(
            TestCaseExecution.case_id,
            func.max(TestCaseExecution.id),
        ).group_by(TestCaseExecution.case_id)
    ).all()
    latest_execution_ids = [int(row[1]) for row in execution_rows if row[1] is not None]
    latest_report_urls: dict[int, str] = {}
    if latest_execution_ids:
        executions = db.execute(
            select(TestCaseExecution).where(TestCaseExecution.id.in_(latest_execution_ids))
        ).scalars().all()
        latest_report_urls = {int(item.case_id): str(item.report_url or "").strip() for item in executions}

    existing_case_ids = _existing_asset_case_ids()
    existing_case_ids.extend(
        [
            str(item).strip()
            for item in db.execute(select(TestCase.case_id)).scalars().all()
            if str(item or "").strip()
        ]
    )
    seen_case_ids: list[str] = []
    for raw in existing_case_ids:
        normalized = normalize_case_id(str(raw).strip(), fallback="").strip() if str(raw).strip() else ""
        if normalized and normalized not in seen_case_ids:
            seen_case_ids.append(normalized)

    changed = False
    for case in sorted(cases, key=_stable_case_sort_key):
        if str(case.case_id or "").strip():
            normalized = normalize_case_id(str(case.case_id).strip(), fallback="").strip()
            if normalized and normalized in seen_case_ids:
                seen_case_ids.remove(normalized)
        changed = _assign_case_defaults(
            case,
            existing_case_ids=seen_case_ids,
            latest_report_urls=latest_report_urls,
            case_id_repository=case_id_repository,
        ) or changed
        resolved_case_id = normalize_case_id(str(case.case_id or "").strip(), fallback="").strip()
        if resolved_case_id and resolved_case_id not in seen_case_ids:
            seen_case_ids.append(resolved_case_id)
        db.add(case)

    if changed:
        db.commit()

    db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_test_cases_case_id ON test_cases(case_id)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_test_cases_project_code ON test_cases(project_code)"))
    db.commit()


def ensure_seed_data(db: Session) -> None:
    TestCaseTreeNode.__table__.create(bind=db.get_bind(), checkfirst=True)
    TestCaseStep.__table__.create(bind=db.get_bind(), checkfirst=True)
    TestPoint.__table__.create(bind=db.get_bind(), checkfirst=True)
    ensure_test_cases_schema_compatibility(db)
    ensure_project_seed(db)
    case_id_repository = WorkbenchGenerationRepository(db)
    existing_count = db.execute(select(func.count(TestCase.id))).scalar_one()
    if existing_count and existing_count > 0:
        backfill_test_case_metadata(db)
        return

    now = datetime.now(UTC)
    seed_cases = [
        TestCase(
            case_id="",
            project_code=DEFAULT_PROJECT_CODE,
            client="web",
            page_code="",
            page_name="",
            module_code="",
            module_name="",
            case_type="fn",
            source="mn",
            name="商品搜索结果展示",
            product_line="电商平台",
            module="商品中心",
            chain_stage="商品/查询",
            sut_service="product-service",
            related_services=["search-service"],
            priority="P1",
            test_type="ui",
            scenario_types=["smoke", "search"],
            trigger_entry="UI",
            fault_injection_type="",
            fault_injection_target="",
            fault_injection_params="",
            setup_sql="",
            precondition_state="已完成登录，商品数据存在。",
            test_steps=[],
            test_steps_text="Step1 打开商品页面\nStep2 输入搜索词\nStep3 点击搜索\nStep4 校验结果列表存在",
            concurrency_model="N/A",
            retry_policy="N/A",
            expected_result="商品搜索结果正确展示。",
            assert_sql="",
            event_assertion="",
            metric_assertion="",
            cleanup_script="",
            artifact_links=[],
            notes="",
            tags=["smoke", "search", "web"],
            markers=[],
            creator="alice",
            assignee="alice",
            pytest_path="",
            status="active",
            automation_status="automated",
            created_source="manual",
            source_ref="",
            script_code=(
                "def test_product_search(page):\n"
                "    page.goto('/products')\n"
                "    page.fill('#search', '耳机')\n"
                "    page.click('#search-btn')\n"
                "    assert page.locator('.result-item').count() > 0\n"
            ),
            data_config={},
            last_execution_result="passed",
            last_report_url="",
            last_synced_at=None,
            created_at=now,
            updated_at=now,
        ),
        TestCase(
            case_id="",
            project_code=DEFAULT_PROJECT_CODE,
            client="web",
            page_code="",
            page_name="",
            module_code="",
            module_name="",
            case_type="fn",
            source="mn",
            name="订单创建基础流程",
            product_line="电商平台",
            module="订单中心",
            chain_stage="下单/订单",
            sut_service="order-service",
            related_services=["inventory-service", "payment-service"],
            priority="P1",
            test_type="ui",
            scenario_types=["regression"],
            trigger_entry="UI",
            fault_injection_type="",
            fault_injection_target="",
            fault_injection_params="",
            setup_sql="",
            precondition_state="购物车存在有效商品。",
            test_steps=[],
            test_steps_text="Step1 进入购物车\nStep2 提交订单\nStep3 填写地址\nStep4 校验下单成功",
            concurrency_model="N/A",
            retry_policy="N/A",
            expected_result="订单创建成功并展示成功提示。",
            assert_sql="",
            event_assertion="",
            metric_assertion="",
            cleanup_script="",
            artifact_links=[],
            notes="",
            tags=["regression", "order"],
            markers=[],
            creator="bob",
            assignee="bob",
            pytest_path="",
            status="active",
            automation_status="automated",
            created_source="manual",
            source_ref="",
            script_code=(
                "def test_create_order(page):\n"
                "    page.goto('/cart')\n"
                "    page.click('#checkout')\n"
                "    page.fill('#address', '上海市浦东新区')\n"
                "    page.click('#submit-order')\n"
                "    assert page.locator('.order-success').is_visible()\n"
            ),
            data_config={},
            last_execution_result="failed",
            last_report_url="",
            last_synced_at=None,
            created_at=now,
            updated_at=now,
        ),
        TestCase(
            case_id="",
            project_code=DEFAULT_PROJECT_CODE,
            client="web",
            page_code="",
            page_name="",
            module_code="",
            module_name="",
            case_type="fn",
            source="mn",
            name="登录态过期重定向",
            product_line="会员体系",
            module="认证服务",
            chain_stage="登录/认证",
            sut_service="auth-service",
            related_services=[],
            priority="P2",
            test_type="api",
            scenario_types=["security"],
            trigger_entry="API",
            fault_injection_type="",
            fault_injection_target="",
            fault_injection_params="",
            setup_sql="",
            precondition_state="存在已过期会话。",
            test_steps=[],
            test_steps_text="Step1 打开个人中心\nStep2 清理 Cookie\nStep3 刷新页面\nStep4 校验跳转登录页",
            concurrency_model="N/A",
            retry_policy="N/A",
            expected_result="用户会被重定向到登录页。",
            assert_sql="",
            event_assertion="",
            metric_assertion="",
            cleanup_script="",
            artifact_links=[],
            notes="",
            tags=["auth", "api", "security"],
            markers=[],
            creator="carol",
            assignee="carol",
            pytest_path="",
            status="active",
            automation_status="automated",
            created_source="manual",
            source_ref="",
            script_code=(
                "def test_auth_expired_redirect(page):\n"
                "    page.goto('/profile')\n"
                "    page.context.clear_cookies()\n"
                "    page.reload()\n"
                "    assert '/login' in page.url\n"
            ),
            data_config={},
            last_execution_result="skipped",
            last_report_url="",
            last_synced_at=None,
            created_at=now,
            updated_at=now,
        ),
    ]
    existing_case_ids = _existing_asset_case_ids()
    for case in seed_cases:
        _assign_case_defaults(
            case,
            existing_case_ids=existing_case_ids,
            latest_report_urls={},
            case_id_repository=case_id_repository,
        )
        normalized_case_id = normalize_case_id(str(case.case_id or "").strip(), fallback="").strip()
        if normalized_case_id and normalized_case_id not in existing_case_ids:
            existing_case_ids.append(normalized_case_id)
    db.add_all(seed_cases)
    db.commit()
    backfill_test_case_metadata(db)

    cases = db.execute(select(TestCase).order_by(TestCase.id.asc())).scalars().all()
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
                report_url="/execution/results/101",
            ),
            TestCaseExecution(
                case_id=cases[0].id,
                status="passed",
                duration_ms=16900,
                report_url="/execution/results/102",
            ),
            TestCaseExecution(
                case_id=cases[1].id,
                status="failed",
                duration_ms=23100,
                report_url="/execution/results/201",
            ),
            TestCaseExecution(
                case_id=cases[1].id,
                status="passed",
                duration_ms=21090,
                report_url="/execution/results/202",
            ),
            TestCaseExecution(
                case_id=cases[2].id,
                status="skipped",
                duration_ms=0,
                report_url="/execution/results/301",
            ),
        ]
    )
    db.commit()
    backfill_test_case_metadata(db)


def get_module_tree_items(
    db: Session,
    *,
    q: str = "",
    project_code: str = "",
    source: str = "",
    tag: str = "",
    priority: str = "",
    status: str = "",
    creator: str = "",
    last_result: str = "",
    product_line: str = "",
    module: str = "",
    test_type: str = "",
) -> list[dict[str, object]]:
    ensure_seed_data(db)
    stmt = select(TestCase)
    keyword = str(q or "").strip()
    if project_code.strip():
        stmt = stmt.where(TestCase.project_code == _normalize_project_code(project_code))
    if keyword:
        term = f"%{keyword}%"
        stmt = stmt.where(
            (TestCase.case_id.like(term))
            | (TestCase.name.like(term))
            | (TestCase.module.like(term))
            | (TestCase.product_line.like(term))
            | (TestCase.creator.like(term))
        )
    source_filter = str(source or "").strip().lower()
    if source_filter in {"ai", "mn", "cv", "imp", "fb"}:
        stmt = stmt.where(TestCase.source == source_filter)
    priority_filter = str(priority or "").strip()
    if priority_filter:
        priority_values = [item.strip().upper() for item in priority_filter.split(",") if item.strip()]
        if len(priority_values) == 1:
            stmt = stmt.where(TestCase.priority == priority_values[0])
        elif priority_values:
            stmt = stmt.where(TestCase.priority.in_(priority_values))
    status_filter = str(status or "").strip()
    if status_filter:
        stmt = stmt.where(TestCase.status == normalize_status(status_filter))
    creator_filter = str(creator or "").strip()
    if creator_filter:
        stmt = stmt.where(TestCase.creator == creator_filter)
    last_result_filter = str(last_result or "").strip().lower()
    if last_result_filter:
        stmt = stmt.where(TestCase.last_execution_result == last_result_filter)
    product_line_filter = str(product_line or "").strip()
    if product_line_filter:
        stmt = stmt.where(TestCase.product_line == product_line_filter)
    module_filter = str(module or "").strip()
    if module_filter:
        stmt = stmt.where(TestCase.module == module_filter)
    test_type_filter = str(test_type or "").strip()
    if test_type_filter:
        stmt = stmt.where(TestCase.test_type == normalize_test_case_type(test_type_filter))

    case_rows = list(db.execute(stmt).scalars().all())
    tag_filter = str(tag or "").strip()
    if tag_filter:
        case_rows = [item for item in case_rows if tag_filter in (item.tags or [])]

    counters: dict[tuple[str, str, str], int] = {}
    for item in case_rows:
        key = (
            str(item.project_code or DEFAULT_PROJECT_CODE).strip() or DEFAULT_PROJECT_CODE,
            str(item.product_line or "").strip(),
            str(item.module or "").strip(),
        )
        if not key[1]:
            continue
        counters[key] = counters.get(key, 0) + 1

    grouped: dict[str, dict[str, object]] = {}
    for (item_project_code, item_product_line, item_module), count in counters.items():
        project_bucket = grouped.setdefault(
            item_project_code,
            {"project_code": item_project_code, "groups": []},
        )
        groups = project_bucket["groups"]
        if not isinstance(groups, list):
            continue
        bucket = next((item for item in groups if item.get("product_line") == item_product_line), None)
        if bucket is None:
            bucket = {"product_line": item_product_line, "count": 0, "modules": []}
            groups.append(bucket)
        current_count = int(bucket.get("count", 0) or 0)
        bucket["count"] = current_count + int(count)
        modules = bucket.get("modules")
        if isinstance(modules, list) and item_module:
            modules.append({"module": item_module, "count": int(count)})

    tree_nodes = list(
        db.execute(select(TestCaseTreeNode).order_by(TestCaseTreeNode.project_code, TestCaseTreeNode.product_line, TestCaseTreeNode.module)).scalars().all()
    )
    for node in tree_nodes:
        node_project_code = str(node.project_code or DEFAULT_PROJECT_CODE).strip() or DEFAULT_PROJECT_CODE
        node_product_line = str(node.product_line or "").strip()
        node_module = str(node.module or "").strip()
        if not node_product_line:
            continue
        if project_code.strip() and node_project_code != _normalize_project_code(project_code):
            continue
        if product_line_filter and node_product_line != product_line_filter:
            continue
        if module_filter and node_module and node_module != module_filter:
            continue
        project_bucket = grouped.setdefault(
            node_project_code,
            {"project_code": node_project_code, "groups": []},
        )
        groups = project_bucket["groups"]
        if not isinstance(groups, list):
            continue
        bucket = next((item for item in groups if item.get("product_line") == node_product_line), None)
        if bucket is None:
            bucket = {"product_line": node_product_line, "count": 0, "modules": []}
            groups.append(bucket)
        if node_module:
            modules = bucket.get("modules")
            if isinstance(modules, list):
                exists = next((item for item in modules if str(item.get("module", "")).strip() == node_module), None)
                if exists is None:
                    modules.append({"module": node_module, "count": 0})

    flattened: list[dict[str, object]] = []
    for project_code in sorted(grouped):
        groups = grouped[project_code].get("groups", [])
        if not isinstance(groups, list):
            continue
        for item in groups:
            item["project_code"] = project_code
            modules = item.get("modules")
            if isinstance(modules, list):
                item["modules"] = sorted(
                    modules,
                    key=lambda row: (
                        str(row.get("module", "")).strip().lower(),
                        int(row.get("count", 0) or 0),
                    ),
                )
            flattened.append(item)
    return flattened
