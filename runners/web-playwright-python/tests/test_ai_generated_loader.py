from pathlib import Path

import pytest
import yaml

from runner.test_case_loader import load_ai_generated_test_cases, load_expanded_test_cases


pytestmark = [pytest.mark.contract]


@pytest.fixture(autouse=True)
def clear_auth_state():
    yield


@pytest.fixture(autouse=True)
def capture_failure_artifacts():
    yield


def test_ai_generated_loader_only_reads_ai_generated_directory(monkeypatch, tmp_path: Path):
    ai_case_path = tmp_path / "tc-ai-only.yaml"
    ai_case_path.write_text(
        yaml.safe_dump(
            {
                "version": "v1.1",
                "id": "tc-ai-only",
                "title": "AI only case",
                "module": "login",
                "priority": "P1",
                "tags": ["ai-generated"],
                "owner": "qa-team",
                "status": "automated",
                "description": "AI generated case",
                "requirement": {
                    "intent_id": "intent-01",
                    "title": "AI case",
                    "source_asset_id": "mall-web-login-auth-fn-ai-0021",
                },
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "login",
                    "selected_intent_ids": ["intent-01"],
                    "variables": {},
                    "steps": [
                        {"action": "goto", "value": "http://localhost:5174/#/login"},
                    ],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    from runner import test_case_loader

    original_root = test_case_loader.AI_GENERATED_CASES_ROOT
    test_case_loader.AI_GENERATED_CASES_ROOT = tmp_path
    try:
        test_cases = load_ai_generated_test_cases()
    finally:
        test_case_loader.AI_GENERATED_CASES_ROOT = original_root

    assert test_cases, "No ai-generated test cases found"
    assert all(case["id"] == case["id"].lower() for case in test_cases)
    assert all(len(case["id"].split("-")) >= 3 for case in test_cases)
    assert all(case["execution"]["page"] for case in test_cases)
    assert all("smoke" not in case.get("tags", []) for case in test_cases)


def test_ai_generated_loader_rejects_smoke_case_path():
    smoke_case_path = Path(__file__).resolve().parents[3] / "assets" / "test-cases" / "smoke" / "product-smoke.yaml"

    with pytest.raises(ValueError, match="TEST_CASE_PATH must stay under"):
        load_ai_generated_test_cases(case_path=str(smoke_case_path))


def test_ai_generated_loader_accepts_case_path_inside_ai_generated(tmp_path: Path):
    ai_case_path = tmp_path / "TC-AI-001.yaml"
    ai_case_path.write_text(
        yaml.safe_dump(
            {
                "version": "v4",
                "id": "TC-AI-001",
                "title": "AI only case",
                "module": "product",
                "priority": "P1",
                "tags": ["product"],
                "owner": "qa-team",
                "status": "automated",
                "description": "AI generated case",
                "requirement": {
                    "intent_id": "intent-01",
                    "title": "AI case",
                    "source_asset_id": "mall-web-login-auth-fn-ai-0021",
                },
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "product",
                    "selected_intent_ids": ["intent-01"],
                    "variables": {},
                    "steps": [
                        {"action": "login"},
                        {"action": "click", "target": "product_menu"},
                    ],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    from runner import test_case_loader

    original_root = test_case_loader.AI_GENERATED_CASES_ROOT
    test_case_loader.AI_GENERATED_CASES_ROOT = tmp_path
    try:
        test_cases = load_ai_generated_test_cases(case_path=str(ai_case_path))
    finally:
        test_case_loader.AI_GENERATED_CASES_ROOT = original_root

    assert len(test_cases) == 1
    assert test_cases[0]["id"] == "TC-AI-001"


def test_ai_generated_loader_accepts_runtime_case_path_from_extra_root(monkeypatch, tmp_path: Path):
    runtime_root = tmp_path / "runtime-cases" / "run-001"
    runtime_root.mkdir(parents=True)
    runtime_case_path = runtime_root / "TC-AI-RUNTIME.yaml"
    runtime_case_path.write_text(
        yaml.safe_dump(
            {
                "version": "v4",
                "id": "TC-AI-RUNTIME",
                "title": "Runtime case",
                "module": "login",
                "priority": "P1",
                "tags": ["login"],
                "owner": "qa-team",
                "status": "automated",
                "description": "Runtime case",
                "requirement": {
                    "intent_id": "intent-01",
                    "title": "Runtime case",
                    "source_asset_id": "mall-web-login-auth-fn-ai-0021",
                },
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "login",
                    "selected_intent_ids": ["intent-01"],
                    "variables": {},
                    "steps": [
                        {"action": "goto", "value": "http://localhost:5174/#/login"},
                    ],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_CASE_ALLOWED_ROOTS", str(runtime_root))

    test_cases = load_ai_generated_test_cases(case_path=str(runtime_case_path))

    assert len(test_cases) == 1
    assert test_cases[0]["id"] == "TC-AI-RUNTIME"


def test_ai_generated_loader_validates_explicit_case_path_schema(monkeypatch, tmp_path: Path):
    runtime_root = tmp_path / "runtime-cases" / "run-invalid"
    runtime_root.mkdir(parents=True)
    runtime_case_path = runtime_root / "TC-AI-INVALID.yaml"
    runtime_case_path.write_text(
        yaml.safe_dump(
            {
                "version": "v4",
                "id": "TC-AI-INVALID",
                "title": "Invalid runtime case",
                "module": "login",
                "priority": "P1",
                "tags": ["login"],
                "owner": "qa-team",
                "status": "automated",
                "description": "Missing execution steps",
                "requirement": ["Invalid runtime case"],
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "login",
                    "variables": {},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_CASE_ALLOWED_ROOTS", str(runtime_root))

    with pytest.raises(Exception, match="'steps' is a required property"):
        load_ai_generated_test_cases(case_path=str(runtime_case_path))


def test_ai_generated_loader_accepts_top_level_assertions(monkeypatch, tmp_path: Path):
    runtime_root = tmp_path / "runtime-cases" / "run-assertions"
    runtime_root.mkdir(parents=True)
    runtime_case_path = runtime_root / "TC-AI-ASSERTIONS.yaml"
    runtime_case_path.write_text(
        yaml.safe_dump(
            {
                "version": "v1",
                "id": "TC-AI-ASSERTIONS",
                "title": "Runtime case with executable assertions",
                "module": "login",
                "priority": "P1",
                "tags": ["ai-generated"],
                "owner": "qa-team",
                "status": "automated",
                "description": "Runtime case with assertions",
                "requirement": {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "type": "functional",
                    "source_asset_id": "mall-web-login-auth-fn-ai-0021",
                },
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "login",
                    "selected_intent_ids": ["intent-01"],
                    "variables": {},
                    "steps": [
                        {"action": "goto", "value": "http://localhost:5174/#/login"},
                    ],
                },
                "assertions": [
                    {
                        "action": "assert_url",
                        "value": "/#/home",
                        "expected_result": "登录后进入首页",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_CASE_ALLOWED_ROOTS", str(runtime_root))

    test_cases = load_ai_generated_test_cases(case_path=str(runtime_case_path))

    assert test_cases[0]["assertions"][0]["action"] == "assert_url"


def test_ai_generated_loader_accepts_assert_text(monkeypatch, tmp_path: Path):
    runtime_root = tmp_path / "runtime-cases" / "run-assert-text"
    runtime_root.mkdir(parents=True)
    runtime_case_path = runtime_root / "TC-AI-ASSERT-TEXT.yaml"
    runtime_case_path.write_text(
        yaml.safe_dump(
            {
                "version": "v1.1",
                "id": "TC-AI-ASSERT-TEXT",
                "title": "Runtime case with text assertion",
                "module": "login",
                "priority": "P1",
                "tags": ["ai-generated"],
                "owner": "qa-team",
                "status": "automated",
                "description": "Runtime case with assert_text",
                "requirement": {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "type": "functional",
                    "source_asset_id": "mall-web-login-auth-fn-ai-0021",
                },
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "login",
                    "selected_intent_ids": ["intent-01"],
                    "variables": {},
                    "steps": [
                        {"action": "goto", "value": "http://localhost:5174/#/login"},
                    ],
                },
                "assertions": [
                    {
                        "action": "assert_text",
                        "target": "element:login_error_message",
                        "locator_type": "css",
                        "locator_value": ".login-error",
                        "value": "用户名或密码错误",
                        "expected_result": "展示登录失败提示",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_CASE_ALLOWED_ROOTS", str(runtime_root))

    test_cases = load_ai_generated_test_cases(case_path=str(runtime_case_path))

    assert test_cases[0]["assertions"][0]["action"] == "assert_text"


def test_ai_generated_loader_rejects_assert_url_without_value(monkeypatch, tmp_path: Path):
    runtime_root = tmp_path / "runtime-cases" / "run-invalid-assertions"
    runtime_root.mkdir(parents=True)
    runtime_case_path = runtime_root / "TC-AI-ASSERTIONS-INVALID.yaml"
    runtime_case_path.write_text(
        yaml.safe_dump(
            {
                "version": "v1",
                "id": "TC-AI-ASSERTIONS-INVALID",
                "title": "Runtime case with invalid assertions",
                "module": "login",
                "priority": "P1",
                "tags": ["ai-generated"],
                "owner": "qa-team",
                "status": "automated",
                "description": "Runtime case with invalid assertions",
                "requirement": {
                    "intent_id": "intent-01",
                    "title": "Invalid assertion case",
                    "source_asset_id": "mall-web-login-auth-fn-ai-0021",
                },
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "login",
                    "selected_intent_ids": ["intent-01"],
                    "variables": {},
                    "steps": [
                        {"action": "goto", "value": "http://localhost:5174/#/login"},
                    ],
                },
                "assertions": [
                    {
                        "action": "assert_url",
                        "expected_result": "登录后进入首页",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_CASE_ALLOWED_ROOTS", str(runtime_root))

    with pytest.raises(Exception, match="'value' is a required property"):
        load_ai_generated_test_cases(case_path=str(runtime_case_path))


def test_ai_generated_loader_rejects_missing_source_asset_id(monkeypatch, tmp_path: Path):
    runtime_root = tmp_path / "runtime-cases" / "run-missing-source"
    runtime_root.mkdir(parents=True)
    runtime_case_path = runtime_root / "TC-AI-MISSING-SOURCE.yaml"
    runtime_case_path.write_text(
        yaml.safe_dump(
            {
                "version": "v1.1",
                "id": "TC-AI-MISSING-SOURCE",
                "title": "Runtime case missing source asset",
                "module": "login",
                "priority": "P1",
                "tags": ["ai-generated"],
                "owner": "qa-team",
                "status": "automated",
                "description": "正式 AI 用例必须来自测试点资产",
                "requirement": {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "type": "functional",
                },
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "login",
                    "selected_intent_ids": ["intent-01"],
                    "variables": {},
                    "steps": [
                        {"action": "goto", "value": "http://localhost:5174/#/login"},
                    ],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_CASE_ALLOWED_ROOTS", str(runtime_root))

    with pytest.raises(ValueError, match="Formal AI generated case requires requirement.source_asset_id"):
        load_ai_generated_test_cases(case_path=str(runtime_case_path))


def test_all_mode_skips_formal_ai_case_missing_source_asset_id(monkeypatch, tmp_path: Path):
    ai_root = tmp_path / "ai-generated"
    smoke_root = tmp_path / "smoke"
    ai_root.mkdir()
    smoke_root.mkdir()
    (smoke_root / "product-smoke.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "v1",
                "id": "product-smoke",
                "title": "Smoke case",
                "module": "product",
                "priority": "P1",
                "tags": ["smoke"],
                "owner": "qa-team",
                "status": "automated",
                "description": "Smoke case",
                "requirement": ["Smoke case"],
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "product",
                    "variables": {},
                    "steps": [{"action": "login"}],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (ai_root / "mall-web-login-auth-fn-ai-0001.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "v1.1",
                "id": "mall-web-login-auth-fn-ai-0001",
                "title": "首次登录成功",
                "module": "login",
                "priority": "P1",
                "tags": ["ai-generated"],
                "owner": "qa-team",
                "status": "automated",
                "description": "缺少来源资产的正式 AI 用例",
                "requirement": {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "type": "functional",
                },
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "login",
                    "selected_intent_ids": ["intent-01"],
                    "variables": {},
                    "steps": [{"action": "goto", "value": "http://localhost:5174/#/login"}],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    from runner import test_case_loader

    monkeypatch.setattr(test_case_loader, "AI_GENERATED_CASES_ROOT", ai_root)
    monkeypatch.setattr(test_case_loader, "SMOKE_TEST_CASES_ROOT", smoke_root)

    test_cases = load_expanded_test_cases("all")
    assert len(test_cases) == 1
    assert str(test_cases[0].get("id")) == "product-smoke"
