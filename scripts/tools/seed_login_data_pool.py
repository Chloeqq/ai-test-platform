"""Seed the per-field login credential pool consumed by the V2.0 precondition compiler.

背景（Option B）：生成管线的自动路由 `route_identity_data_to_pool` 会把锁定/禁用
账号的 username/password 改写为池引用，约定为：
    pool_name = {page}              （登录页 → "login"）
    item_key  = {field}_{state}     （如 username_locked / password_disabled）
而 Runner 的解析器 `_resolve_pool_value` 做精确 key 匹配并返回整条 item_value，
因此每个 item 必须是**单字段标量**（item_value = 一个用户名或一个密码字符串）。

本脚本按上述约定补齐 `login` 池的 4 个标量 item（locked / disabled 两种状态）。
幂等：池已存在则复用，item 已存在则更新（走 upsert）。不触碰任何现有数据池。

Usage:
    python scripts/tools/seed_login_data_pool.py
    python scripts/tools/seed_login_data_pool.py --dry-run
    python scripts/tools/seed_login_data_pool.py --pool order   # 其它页面的登录前置
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_UI_ROOT = REPO_ROOT / "apps" / "web-ui-service"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))

# (item_key, item_value) — 标量值，对应实际账号。来源：用户现有数据池中的
# locked / disabled 账号。active 账号保持 inline，不入池（自动路由不路由 active）。
_LOGIN_POOL_ITEMS: tuple[tuple[str, str], ...] = (
    ("username_locked", "locked_user"),
    ("password_locked", "test123"),
    ("username_disabled", "disabled_user"),
    ("password_disabled", "test123"),
)

_SEED_ACTOR = "seed_login_data_pool"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the per-field login credential data pool")
    parser.add_argument(
        "--pool",
        default="login",
        help="Pool name (default: login). 必须等于用例的 page 名，自动路由按此约定生成引用。",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing to DB")
    return parser.parse_args()


def _ensure_pool(db: "Session", pool_name: str) -> None:
    from fastapi import HTTPException

    from app.services import test_data_pool_service

    try:
        test_data_pool_service.create_data_pool(
            db,
            pool_name=pool_name,
            description="登录凭据（按字段拆分的标量 item，供 V2.0 前置自动路由消费）",
            status_value="active",
            created_by=_SEED_ACTOR,
        )
        print(f"  CREATED pool '{pool_name}'")
    except HTTPException as exc:
        if exc.status_code == 409:
            print(f"  EXISTS  pool '{pool_name}' (reuse)")
            return
        raise


def main() -> None:
    args = _parse_args()
    pool_name = args.pool.strip() or "login"

    print(f"Seeding login data pool '{pool_name}' with {len(_LOGIN_POOL_ITEMS)} scalar items")
    print(f"  dry_run={args.dry_run}")
    print()

    if args.dry_run:
        print(f"  DRY-RUN ensure pool '{pool_name}'")
        for item_key, item_value in _LOGIN_POOL_ITEMS:
            print(f"  DRY-RUN upsert {pool_name}.{item_key} = {item_value!r}")
        print("\nDry run complete. No database changes made.")
        return

    from app.core.database import SessionLocal
    from app.services import test_data_pool_service

    db = SessionLocal()
    try:
        _ensure_pool(db, pool_name)
        for item_key, item_value in _LOGIN_POOL_ITEMS:
            test_data_pool_service.upsert_data_pool_item(
                db,
                pool_name=pool_name,
                item_key=item_key,
                item_value=item_value,
                status_value="active",
                changed_by=_SEED_ACTOR,
                note="Option B: per-field scalar login credential",
            )
            print(f"  UPSERT  {pool_name}.{item_key} = {item_value!r}")
        print("\nSeed complete.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
