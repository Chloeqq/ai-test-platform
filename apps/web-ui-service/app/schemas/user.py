from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.id_gen import USER_PUBLIC_ID_PATTERN

ALLOWED_SELF_REGISTER_ROLES = frozenset({"viewer", "tester", "developer"})
FORBIDDEN_IDENTITY_OVERRIDE_FIELDS = frozenset(
    {
        "user_public_id",
        "actor_or_client_id",
    }
)


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="viewer", min_length=3, max_length=40)

    @model_validator(mode="before")
    @classmethod
    def _reject_identity_overrides(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value

        forbidden = sorted(FORBIDDEN_IDENTITY_OVERRIDE_FIELDS.intersection(value))
        if forbidden:
            joined = ", ".join(forbidden)
            raise ValueError(f"identity override fields are not allowed: {joined}")
        return value

    @model_validator(mode="after")
    def _restrict_role(self) -> "UserCreate":
        normalized = self.role.strip().lower()
        if normalized not in ALLOWED_SELF_REGISTER_ROLES:
            raise ValueError(f"role must be one of {sorted(ALLOWED_SELF_REGISTER_ROLES)}, got '{normalized}'")
        self.role = normalized
        return self


class UserRead(BaseModel):
    user_public_id: str = Field(pattern=USER_PUBLIC_ID_PATTERN)
    username: str
    role: str
    is_active: bool
    created_at: datetime | None = None

    model_config = ConfigDict(extra="forbid", from_attributes=True)
