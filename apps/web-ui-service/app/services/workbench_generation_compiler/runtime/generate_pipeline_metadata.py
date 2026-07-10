"""V3.0 元数据常量和校验。多项目可扩展：新项目追加枚举值即可。"""

from __future__ import annotations

from shared_backend.execution_compiler import ExecutionCompilerError

_RISK_LEVELS: frozenset[str] = frozenset({"HIGH", "MEDIUM", "LOW"})
_ENVIRONMENTS: frozenset[str] = frozenset({"test", "staging", "production"})
_NETWORK_PROFILES: frozenset[str] = frozenset({"normal", "slow", "timeout", "offline"})
_ACTOR_ROLES: frozenset[str] = frozenset({"normal_user", "admin", "anonymous", "operator"})


def _validate_enum(value: str, allowed: frozenset[str], field_name: str) -> None:
    """校验枚举值，非法则抛出 ExecutionCompilerError。"""
    if value and value not in allowed:
        raise ExecutionCompilerError(
            code="v3_0_invalid_metadata",
            message=f"V3.0 metadata field '{field_name}' has invalid value '{value}'",
            reason=f"allowed values: {sorted(allowed)}",
            stage="v3_0_metadata_enrichment",
        )
