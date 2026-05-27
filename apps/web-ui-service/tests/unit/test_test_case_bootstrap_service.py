# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))

from app.core.database import Base
from app.models import test_case as test_case_models
from app.services import test_case_bootstrap_service


def test_get_module_tree_items_seeds_once_and_groups_modules() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        first_tree = test_case_bootstrap_service.get_module_tree_items(db)
        second_tree = test_case_bootstrap_service.get_module_tree_items(db)
        total_cases = db.execute(select(test_case_models.TestCase)).scalars().all()

    assert len(total_cases) == 3
    assert first_tree == second_tree
    assert first_tree == [
        {
            "product_line": "会员体系",
            "count": 1,
            "modules": [{"module": "认证服务", "count": 1}],
        },
        {
            "product_line": "电商平台",
            "count": 2,
            "modules": [
                {"module": "商品中心", "count": 1},
                {"module": "订单中心", "count": 1},
            ],
        },
    ]
