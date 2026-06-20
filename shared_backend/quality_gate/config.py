"""RuleConfigLoader — 规则配置加载。

从 YAML/JSON 加载规则降级配置，支持按环境覆盖。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .models import RuleConfig, Severity
from .registry import get_registry

LOGGER = logging.getLogger(__name__)


class RuleConfigLoader:
    """从配置文件加载规则配置并应用到 RuleRegistry。"""

    @staticmethod
    def load_from_dict(configs: list[dict[str, Any]]) -> list[RuleConfig]:
        result: list[RuleConfig] = []
        for item in configs:
            severity = item.get("severity")
            if isinstance(severity, str):
                severity = Severity(severity)
            result.append(
                RuleConfig(
                    rule_id=item["rule_id"],
                    enabled=item.get("enabled", True),
                    severity=severity,
                )
            )
        return result

    @staticmethod
    def load_from_json(path: str | Path) -> list[RuleConfig]:
        path = Path(path)
        if not path.exists():
            LOGGER.warning("Rule config file not found: %s", path)
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return RuleConfigLoader.load_from_dict(raw)
        # 支持按环境: {"production": [...], "development": [...]}
        if isinstance(raw, dict):
            import os
            env = os.getenv("APP_ENV", "development")
            env_configs = raw.get(env, raw.get("development", []))
            return RuleConfigLoader.load_from_dict(env_configs)
        return []

    @staticmethod
    def apply_to_registry(configs: list[RuleConfig]) -> None:
        registry = get_registry()
        registry.apply_configs(configs)
        LOGGER.info("Applied %d rule configs to registry", len(configs))
