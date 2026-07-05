from __future__ import annotations

from pathlib import Path
import importlib.util

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.page_object import PageElement, PageObject


SCRIPT_PATH = Path(__file__).resolve().parents[4] / "scripts" / "tools" / "seed_page_objects.py"
SPEC = importlib.util.spec_from_file_location("seed_page_objects", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
seed_page_objects = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(seed_page_objects)


def test_parse_args_defaults_to_mall(monkeypatch) -> None:
    monkeypatch.delenv("PAGE_OBJECT_SEED_PROJECT", raising=False)
    monkeypatch.setattr("sys.argv", ["seed_page_objects.py"])

    args = seed_page_objects._parse_args()

    assert args.project == "mall"


def test_seed_one_creates_governed_approved_elements() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True)

    yaml_data = {
        "page": "login",
        "elements": {
            "username_input": {
                "locator_type": "placeholder",
                "locator_value": "请输入用户名",
                "element_name": "用户名输入框",
                "aliases": ["账号输入框", "用户名"],
            },
            "login_button": {
                "locator_type": "role",
                "role": "button",
                "locator_value": "登录",
                "element_name": "登录按钮",
                "aliases": ["登录"],
            },
        },
    }

    with session_factory() as db:
        result = seed_page_objects._seed_one(
            db,
            page_code="login",
            yaml_data=yaml_data,
            project_code="mall",
            client="web",
            force=True,
            dry_run=False,
        )
        db.commit()

        page_object = db.execute(select(PageObject)).scalar_one()
        elements = db.execute(select(PageElement).order_by(PageElement.element_code)).scalars().all()

    assert result == "  CREATED login: 2 elements (id=1)"
    assert page_object.project_code == "mall"
    assert page_object.governance_status == "approved"
    assert page_object.status == "published"
    assert page_object.element_count == 2
    assert page_object.approved_element_count == 2
    assert [item.element_code for item in elements] == ["login_button", "username_input"]
    assert elements[0].review_status == "approved"
    assert elements[0].stability_level == "high"
    assert elements[0].business_type == "button"
    assert elements[0].aliases_json == ["登录"]
    assert elements[1].business_type == "input"
    assert elements[1].aliases_json == ["账号输入框", "用户名"]
