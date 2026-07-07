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


# ── MAX_CANDIDATES boundary tests ────────────────────────────────────────────

_CANDIDATE_TEMPLATE = {
    "intent_id": "intent-{:03d}",
    "title": "test candidate {:03d}",
    "steps": ["输入账号", "点击登录"],
    "expected_result": "跳转首页",
    "involved_elements": ["账号输入框", "登录按钮"],
}


def _make_context() -> SimpleNamespace:
    class MockHTTPException(Exception):
        def __init__(self, *args: object, **kwargs: object) -> None:
            detail = str(kwargs.get("detail", args[0] if args else ""))
            super().__init__(detail)
            self.detail = detail
            self.status_code = kwargs.get("status_code")

    return SimpleNamespace(
        candidate_normalizer=SimpleNamespace(normalize_candidates=lambda items: list(items)),
        runtime=SimpleNamespace(
            normalize_page_slug=lambda value: str(value or "").strip().lower(),
            HTTPException=MockHTTPException,
            status=SimpleNamespace(HTTP_422_UNPROCESSABLE_ENTITY=422),
        ),
    )


def _make_candidates(count: int) -> list[dict]:
    return [
        {**{k: v.format(i) if isinstance(v, str) and "{" in v else v for k, v in _CANDIDATE_TEMPLATE.items()}}
        for i in range(1, count + 1)
    ]


def test_max_candidates_accepts_20(monkeypatch) -> None:
    """Case 1: 20 个 intent — 应通过预校验。"""
    monkeypatch.setattr(
        "app.services.workbench_generation_api.precheck_selected_intents_service.resolve_page_object",
        lambda _project, _page: {"page": "login", "elements": {}},
    )
    service = PrecheckSelectedIntentsService(context=_make_context())
    candidates = _make_candidates(20)
    result = service.execute(
        SimpleNamespace(project="atp", page="login", selected_candidates=candidates)
    )
    assert result["summary"]["total"] == 20
    assert result["summary"]["block_count"] <= 20


def test_max_candidates_accepts_28(monkeypatch) -> None:
    """Case 2: 28 个 intent — 应通过预校验（20 限制已删除）。"""
    monkeypatch.setattr(
        "app.services.workbench_generation_api.precheck_selected_intents_service.resolve_page_object",
        lambda _project, _page: {"page": "login", "elements": {}},
    )
    service = PrecheckSelectedIntentsService(context=_make_context())
    candidates = _make_candidates(28)
    result = service.execute(
        SimpleNamespace(project="atp", page="login", selected_candidates=candidates)
    )
    assert result["summary"]["total"] == 28


def test_max_candidates_rejects_201(monkeypatch) -> None:
    """Case 3: 201 个 intent — 应返回明确的 max size 200 错误。"""
    monkeypatch.setattr(
        "app.services.workbench_generation_api.precheck_selected_intents_service.resolve_page_object",
        lambda _project, _page: {"page": "login", "elements": {}},
    )
    service = PrecheckSelectedIntentsService(context=_make_context())
    candidates = _make_candidates(201)
    try:
        service.execute(
            SimpleNamespace(project="atp", page="login", selected_candidates=candidates)
        )
        raise AssertionError("expected RuntimeError for 201 candidates")
    except Exception as exc:
        error_text = getattr(exc, "detail", "") or str(exc)
        assert "200" in error_text, f"expected max size 200 in error, got: {error_text!r}"
