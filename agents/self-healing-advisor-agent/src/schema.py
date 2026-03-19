from pydantic import BaseModel


class SelfHealingAdvice(BaseModel):
    summary: str
    suggestion_type: str
    suggested_changes: list[str]
    rationale: str
    confidence: float
    safe_to_apply_manually: bool
