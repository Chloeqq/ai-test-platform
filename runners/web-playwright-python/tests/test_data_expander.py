import pytest

from runner.data_expander import expand_test_case


def test_expand_test_case_supports_inline_pool_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DSL_DATA_POOL_JSON",
        '{"login_credentials":{"login_account_valid":"admin","login_password_valid":"macro"}}',
    )
    monkeypatch.setenv("TEST_BASE_URL", "http://localhost:5174/#/login")
    cases = expand_test_case(
        {
            "id": "mall-web-login-auth-fn-ai-0001",
            "data": {
                "username": {"source_type": "pool", "pool_name": "login_credentials", "key": "login_account_valid"},
                "password": {"source_type": "pool", "pool_name": "login_credentials", "key": "login_password_valid"},
                "base_url": {"source_type": "env", "key": "TEST_BASE_URL"},
                "code": {"source_type": "inline", "value": "P0"},
            },
        }
    )
    assert len(cases) == 1
    assert cases[0]["_data"] == {
        "username": "admin",
        "password": "macro",
        "base_url": "http://localhost:5174/#/login",
        "code": "P0",
    }


def test_expand_test_case_rejects_missing_pool_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DSL_DATA_POOL_JSON", '{"login_credentials":{"login_account_valid":"admin"}}')
    with pytest.raises(ValueError, match="runtime_data_source_resolve_failed"):
        expand_test_case(
            {
                "data": {
                    "password": {
                        "source_type": "pool",
                        "pool_name": "login_credentials",
                        "key": "login_password_valid",
                    }
                }
            }
        )


def test_expand_test_case_supports_legacy_inline_list() -> None:
    cases = expand_test_case(
        {
            "data": {
                "username": ["admin", "test001"],
                "password": ["macro", "123456"],
            }
        }
    )
    assert len(cases) == 2
    assert cases[0]["_data"] == {"username": "admin", "password": "macro"}
    assert cases[1]["_data"] == {"username": "test001", "password": "123456"}
