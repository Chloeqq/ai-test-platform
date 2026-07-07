from __future__ import annotations

import os


class FeatureFlags:
    def __init__(self, env: dict[str, str] | None = None) -> None:
        self._env = env if isinstance(env, dict) else os.environ

    def get(self, name: str, default: bool) -> bool:
        raw = self._env.get(name)
        if raw is None:
            return default
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    def testpoint_filter_enabled(self) -> bool:
        return self.get("TESTPOINT_FILTER_ENABLED", True)

    def scene_auto_classify_enabled(self) -> bool:
        return self.get("SCENE_AUTO_CLASSIFY_ENABLED", True)

    def page_object_auto_bind_enabled(self) -> bool:
        return self.get("PAGE_OBJECT_AUTO_BIND", True)
