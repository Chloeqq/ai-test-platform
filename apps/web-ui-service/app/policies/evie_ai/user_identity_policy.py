"""Validation policy for stable user public identities."""

from __future__ import annotations

import re

from app.core.id_gen import USER_PUBLIC_ID_PATTERN


def is_valid_user_public_id(user_public_id: str | None) -> bool:
    if user_public_id is None:
        return False
    return re.fullmatch(USER_PUBLIC_ID_PATTERN, user_public_id) is not None
