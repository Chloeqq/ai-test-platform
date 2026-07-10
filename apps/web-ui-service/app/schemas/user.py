from datetime import datetime

from pydantic import BaseModel, Field, model_validator

ALLOWED_SELF_REGISTER_ROLES = frozenset({"viewer", "tester", "developer"})


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="viewer", min_length=3, max_length=40)

    @model_validator(mode="after")
    def _restrict_role(self) -> "UserCreate":
        normalized = self.role.strip().lower()
        if normalized not in ALLOWED_SELF_REGISTER_ROLES:
            raise ValueError(f"role must be one of {sorted(ALLOWED_SELF_REGISTER_ROLES)}, got '{normalized}'")
        self.role = normalized
        return self


class UserRead(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
