from __future__ import annotations

import pytest

from shared_backend.data_pool_resolver import PoolResolutionError, resolve_pool_reference


_SNAPSHOT = {
    "login": {
        "username_locked": "locked_user",
        "password_locked": "test123",
    }
}


def test_resolve_pool_reference_returns_scalar_value() -> None:
    value = resolve_pool_reference(
        field="username",
        pool_name="login",
        item_key="username_locked",
        pool_snapshot=_SNAPSHOT,
    )
    assert value == "locked_user"


def test_resolve_pool_reference_blank_ref_raises() -> None:
    with pytest.raises(PoolResolutionError, match="pool source requires"):
        resolve_pool_reference(
            field="username",
            pool_name="",
            item_key="username_locked",
            pool_snapshot=_SNAPSHOT,
        )


def test_resolve_pool_reference_missing_pool_raises() -> None:
    with pytest.raises(PoolResolutionError, match="not available"):
        resolve_pool_reference(
            field="username",
            pool_name="order",
            item_key="username_locked",
            pool_snapshot=_SNAPSHOT,
        )


def test_resolve_pool_reference_missing_key_raises() -> None:
    with pytest.raises(PoolResolutionError, match="not found"):
        resolve_pool_reference(
            field="username",
            pool_name="login",
            item_key="username_active",
            pool_snapshot=_SNAPSHOT,
        )
