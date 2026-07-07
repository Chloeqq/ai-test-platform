from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest


pytestmark = [pytest.mark.integration]


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = PROJECT_ROOT / "apps" / "ai-orchestrator" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def test_login_page_object_elements_and_preview_are_resolvable() -> None:
    from orchestrator_service import OrchestratorService
    from shared_backend.element_binding import build_element_alias_map, resolve_element_code
    from services.requirement_testpoint_support import _fetch_page_element_codes

    element_codes = _fetch_page_element_codes("login")
    assert element_codes is not None
    assert {"username_input", "password_input", "login_button", "home_menu"}.issubset(set(element_codes))
    alias_map = build_element_alias_map({"elements": element_codes})
    assert resolve_element_code("账号输入框", alias_map) == "username_input"
    assert resolve_element_code("密码输入框", alias_map) == "password_input"
    assert resolve_element_code("登录按钮", alias_map) == "login_button"

    home_codes = _fetch_page_element_codes("home")
    assert home_codes is not None
    home_alias_map = build_element_alias_map({"elements": home_codes})
    assert resolve_element_code("退出登录", home_alias_map) == "logout_option"

    service = OrchestratorService(repo_root=PROJECT_ROOT)
    page_object = service._resolve_page_object(project="atp", page="login")
    assert page_object["page"] == "login"
    assert {"username_input", "password_input", "login_button", "home_menu"}.issubset(set(page_object["elements"]))

    result = service._build_test_points_preview(
        case={
            "id": "case-1",
            "project": "atp",
            "execution": {"page": "login"},
            "requirement": "login requirement",
        },
        requirement_spec={
            "project": "atp",
            "page": "login",
            "raw_requirement": "login requirement",
            "design_input": "login requirement",
            "test_intents": [
                {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "intent_type": "functional",
                    "priority": "P0",
                    "expected_result": "跳转到首页",
                    "target": "home_menu",
                    "steps_hint": ["assert_visible:home_menu"],
                }
            ],
        },
    )

    assert result["points"][0]["intent_id"] == "login-00"
    assert result["points"][1]["intent_id"] == "intent-01"
    assert result["points"][1]["steps"]


def test_page_object_resolution_falls_back_to_yaml_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from orchestrator_service import OrchestratorService
    from shared_backend.element_binding import build_element_alias_map, resolve_element_code
    from services.requirement_testpoint_support import _fetch_page_element_codes

    db_path = tmp_path / "page_objects.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            create table page_objects (
                id integer primary key autoincrement,
                project_code text not null,
                client text not null,
                page_code text not null
            )
            """
        )
        conn.execute(
            """
            create table page_elements (
                id integer primary key autoincrement,
                page_object_id integer not null,
                element_code text not null,
                locator_type text not null,
                locator_value text not null,
                role text not null
            )
            """
        )
        conn.commit()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    element_codes = _fetch_page_element_codes("login")
    assert element_codes is not None
    assert {"username_input", "password_input", "login_button", "home_menu"}.issubset(set(element_codes))
    alias_map = build_element_alias_map({"elements": element_codes})
    assert resolve_element_code("首页", alias_map) == "home_menu"

    service = OrchestratorService(repo_root=PROJECT_ROOT)
    page_object = service._resolve_page_object(project="atp", page="login")
    assert page_object["page"] == "login"
    assert {"username_input", "password_input", "login_button"}.issubset(set(page_object["elements"]))
