from __future__ import annotations

from types import SimpleNamespace

from app.services.workbench_generation_api.precheck_selected_intents_service import PrecheckSelectedIntentsService


def test_precheck_selected_intents_accepts_human_readable_login_elements(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.workbench_generation_api.precheck_selected_intents_service.resolve_page_object",
        lambda _project, _page: {
            "page": "login",
            "elements": {
                "login-role---1": {
                    "selector": "请输入用户名",
                    "type": "role",
                    "role": "textbox",
                    "name": "用户名输入框",
                    "aliases": ["账号输入框"],
                },
                "login-role---2": {
                    "selector": "请输入密码",
                    "type": "role",
                    "role": "textbox",
                    "name": "密码输入框",
                },
                "login-role---4": {
                    "selector": "登录",
                    "type": "role",
                    "role": "button",
                    "name": "登录按钮",
                    "aliases": ["登录"],
                },
            },
        },
    )

    context = SimpleNamespace(
        candidate_normalizer=SimpleNamespace(normalize_candidates=lambda items: list(items)),
        runtime=SimpleNamespace(
            normalize_page_slug=lambda value: str(value or "").strip().lower(),
            HTTPException=RuntimeError,
            status=SimpleNamespace(HTTP_422_UNPROCESSABLE_ENTITY=422),
        ),
    )
    service = PrecheckSelectedIntentsService(context=context)

    result = service.execute(
        SimpleNamespace(
            project="atp",
            page="login",
            selected_candidates=[
                {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "steps": ["输入账号", "输入密码", "点击登录"],
                    "expected_result": "跳转首页",
                    "involved_elements": ["账号输入框", "密码输入框", "登录按钮"],
                }
            ],
        )
    )

    item = result["items"][0]
    assert item["status"] == "ok"
    assert item["unknown_elements"] == []
    assert item["involved_element_codes"] == ["login-role---1", "login-role---2", "login-role---4"]


def test_precheck_selected_intents_ignores_non_dom_system_targets(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.workbench_generation_api.precheck_selected_intents_service.resolve_page_object",
        lambda _project, _page: {
            "page": "login",
            "elements": {},
        },
    )

    context = SimpleNamespace(
        candidate_normalizer=SimpleNamespace(normalize_candidates=lambda items: list(items)),
        runtime=SimpleNamespace(
            normalize_page_slug=lambda value: str(value or "").strip().lower(),
            HTTPException=RuntimeError,
            status=SimpleNamespace(HTTP_422_UNPROCESSABLE_ENTITY=422),
        ),
    )
    service = PrecheckSelectedIntentsService(context=context)

    result = service.execute(
        SimpleNamespace(
            project="mall",
            page="login",
            selected_candidates=[
                {
                    "intent_id": "intent-13",
                    "title": "未登录时直接访问工作台URL",
                    "steps": ["在浏览器地址栏输入工作台URL并访问"],
                    "expected_result": "跳转登录页",
                    "involved_elements": ["浏览器地址栏"],
                }
            ],
        )
    )

    item = result["items"][0]
    assert item["status"] == "ok"
    assert item["unknown_elements"] == []
    assert item["involved_element_codes"] == []
