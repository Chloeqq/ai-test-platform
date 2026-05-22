from runner.url_utils import normalize_url_for_runner


def test_normalize_url_keeps_absolute_loopback_target_by_default(monkeypatch):
    monkeypatch.delenv("RUNNER_LOOPBACK_HOST", raising=False)
    monkeypatch.delenv("RUNNER_URL_REWRITE_MAP", raising=False)
    assert (
        normalize_url_for_runner(
            "http://localhost:5174/#/login",
            base_url="http://localhost:8013/login#/login",
        )
        == "http://localhost:5174/#/login"
    )


def test_normalize_url_keeps_absolute_loopback_route_by_default(monkeypatch):
    monkeypatch.delenv("RUNNER_LOOPBACK_HOST", raising=False)
    monkeypatch.delenv("RUNNER_URL_REWRITE_MAP", raising=False)
    assert (
        normalize_url_for_runner(
            "http://localhost:5174/#/orders",
            base_url="http://localhost:8013/login#/login",
        )
        == "http://localhost:5174/#/orders"
    )


def test_normalize_url_supports_custom_runner_loopback_host(monkeypatch):
    monkeypatch.setenv("RUNNER_LOOPBACK_HOST", "gateway.internal")
    monkeypatch.delenv("RUNNER_URL_REWRITE_MAP", raising=False)
    assert (
        normalize_url_for_runner(
            "http://127.0.0.1:5174/#/login",
            base_url="http://localhost:8013/login#/login",
        )
        == "http://gateway.internal:5174/#/login"
    )


def test_normalize_url_supports_explicit_origin_rewrite_map(monkeypatch):
    monkeypatch.delenv("RUNNER_LOOPBACK_HOST", raising=False)
    monkeypatch.setenv(
        "RUNNER_URL_REWRITE_MAP",
        "http://localhost:5174=http://host.docker.internal:5174",
    )
    assert (
        normalize_url_for_runner(
            "http://localhost:5174/#/login",
            base_url="http://localhost:8013/login#/login",
        )
        == "http://host.docker.internal:5174/#/login"
    )


def test_normalize_url_keeps_external_absolute_url():
    assert (
        normalize_url_for_runner(
            "https://example.test/#/login",
            base_url="http://localhost:8013/login#/login",
        )
        == "https://example.test/#/login"
    )
