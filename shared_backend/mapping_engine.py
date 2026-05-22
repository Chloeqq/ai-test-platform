"""将 IR 中的 target 映射为页面对象 selector，供 Playwright 等执行层使用。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .ir_schema_validator import IRSchemaValidationError, IRSchemaValidator


class MappingEngineError(ValueError):
    """映射引擎基类异常。"""
    def __init__(self, code: str, message: str, *, detail: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = str(code).strip() or "mapping_engine_error"
        self.detail = dict(detail or {})

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": str(self)}
        if self.detail:
            payload["detail"] = self.detail
        return payload


class IRValidationError(MappingEngineError):
    pass


class PageObjectValidationError(MappingEngineError):
    pass


class TargetNotFoundError(MappingEngineError):
    pass


@dataclass(frozen=True)
class SelectorBinding:
    """target 解析后的 selector 与元素类型。"""
    target: str
    selector: str
    element_type: str = ""


def _normalize_selector_list(raw: Any) -> list[str]:
    if isinstance(raw, str):
        value = raw.strip()
        return [value] if value else []
    if isinstance(raw, list):
        normalized: list[str] = []
        for item in raw:
            value = str(item or "").strip()
            if value:
                normalized.append(value)
        return normalized
    return []


class PageObjectRegistry:
    """页面对象 target → SelectorBinding 注册表，支持嵌套 key。"""
    def __init__(self, page_object: Mapping[str, Any] | None = None) -> None:
        self._entries: dict[str, SelectorBinding] = {}
        if isinstance(page_object, Mapping):
            self.register_entries(page_object)

    def register_entries(self, page_object: Mapping[str, Any]) -> None:
        for raw_key, raw_entry in page_object.items():
            key = str(raw_key or "").strip()
            if not key:
                continue
            if isinstance(raw_entry, Mapping) and (
                "selector" in raw_entry or "type" in raw_entry
            ):
                self._entries[key] = self._normalize_entry(target=key, entry=raw_entry)
                continue
            if isinstance(raw_entry, Mapping):
                for nested_key, nested_entry in raw_entry.items():
                    child_key = str(nested_key or "").strip()
                    if not child_key:
                        continue
                    target = child_key if "." in child_key else f"{key}.{child_key}"
                    if not isinstance(nested_entry, Mapping):
                        raise PageObjectValidationError(
                            "invalid_page_object_entry",
                            f"page object entry for target `{target}` must be an object",
                            detail={"target": target},
                        )
                    self._entries[target] = self._normalize_entry(target=target, entry=nested_entry)
                continue
            raise PageObjectValidationError(
                "invalid_page_object_entry",
                f"page object entry for key `{key}` must be an object",
                detail={"target": key},
            )

    def resolve(self, target: str) -> SelectorBinding:
        """按 target 查找绑定，未注册则 TargetNotFoundError。"""
        normalized = str(target or "").strip()
        if not normalized:
            raise IRValidationError("missing_target", "step target is required")
        entry = self._entries.get(normalized)
        if entry is None:
            raise TargetNotFoundError(
                "target_not_found",
                f"target `{normalized}` not found in page object registry",
                detail={"target": normalized},
            )
        return entry

    @staticmethod
    def _normalize_entry(*, target: str, entry: Mapping[str, Any]) -> SelectorBinding:
        selector_candidates = _normalize_selector_list(entry.get("selector"))
        if not selector_candidates:
            raise PageObjectValidationError(
                "selector_missing",
                f"page object target `{target}` requires `selector`",
                detail={"target": target},
            )

        return SelectorBinding(
            target=target,
            selector=selector_candidates[0],
            element_type=str(entry.get("type", "") or "").strip(),
        )


class MappingEngine:
    """将 IR steps 的 target 绑定为 selector。"""
    def __init__(
        self,
        page_object: Mapping[str, Any],
        *,
        preserve_target: bool = False,
        schema_validator: IRSchemaValidator | None = None,
    ) -> None:
        self.registry = PageObjectRegistry(page_object=page_object)
        self.preserve_target = bool(preserve_target)
        self.schema_validator = schema_validator or IRSchemaValidator()

    def map_step(self, step: Mapping[str, Any], *, index: int | None = None) -> dict[str, Any]:
        """映射单步：target → selector，保留 value 与其它字段。"""
        try:
            normalized_step = self.schema_validator.validate_step(step, index=index)
        except IRSchemaValidationError as exc:
            raise IRValidationError(
                exc.code,
                str(exc),
                detail=exc.detail,
            ) from exc
        action = str(normalized_step.get("action", "") or "").strip()
        target = str(normalized_step.get("target", "") or "").strip()
        binding = self.registry.resolve(target)
        mapped: dict[str, Any] = {"action": action, "selector": binding.selector}
        if "value" in normalized_step:
            mapped["value"] = normalized_step.get("value")
        if binding.element_type:
            mapped["element_type"] = binding.element_type
        if self.preserve_target:
            mapped["target"] = target
        for key, value in normalized_step.items():
            if key in {"action", "target", "value"}:
                continue
            mapped[str(key)] = value
        return mapped

    def map_ir(self, ir: Mapping[str, Any]) -> dict[str, Any]:
        """映射 IR 中全部 steps。"""
        try:
            normalized_ir = self.schema_validator.validate_ir(ir)
        except IRSchemaValidationError as exc:
            raise IRValidationError(exc.code, str(exc), detail=exc.detail) from exc
        steps = normalized_ir.get("steps")
        if not isinstance(steps, list):
            raise IRValidationError("steps_missing", "ir.steps must be an array")
        mapped_steps = [self.map_step(step, index=index) for index, step in enumerate(steps)]
        mapped_ir = dict(normalized_ir)
        mapped_ir["steps"] = mapped_steps
        return mapped_ir


def map_ir_to_selectors(
    ir: Mapping[str, Any],
    page_object: Mapping[str, Any],
    *,
    preserve_target: bool = False,
) -> dict[str, Any]:
    """便捷函数：创建 MappingEngine 并映射整份 IR。"""
    engine = MappingEngine(page_object=page_object, preserve_target=preserve_target)
    return engine.map_ir(ir)


def _payload_value(payload: Any, key: str, default: Any = "") -> Any:
    if isinstance(payload, Mapping):
        return payload.get(key, default)
    return getattr(payload, key, default)


def build_preview_payload(payload: Any) -> dict[str, Any]:
    """从请求体（dict 或对象）提取预览管线所需的标准字段。"""
    input_sources = _payload_value(payload, "input_sources", [])
    return {
        "project": str(_payload_value(payload, "project", "") or "").strip(),
        "page": str(_payload_value(payload, "page", "") or "").strip(),
        "requirement": str(_payload_value(payload, "requirement", "") or "").strip(),
        "source": str(_payload_value(payload, "source", "") or "").strip(),
        "input_sources": [item for item in input_sources if isinstance(item, dict)] if isinstance(input_sources, list) else [],
        "openapi_spec": _payload_value(payload, "openapi_spec", {}) if isinstance(_payload_value(payload, "openapi_spec", {}), dict) else {},
        "prd_text": str(_payload_value(payload, "prd_text", "") or "").strip(),
        "prd_url": str(_payload_value(payload, "prd_url", "") or "").strip(),
        "user_story": str(_payload_value(payload, "user_story", "") or "").strip(),
        "git_diff": str(_payload_value(payload, "git_diff", "") or "").strip(),
        "git_diff_path": str(_payload_value(payload, "git_diff_path", "") or "").strip(),
        "openapi_url": str(_payload_value(payload, "openapi_url", "") or "").strip(),
        "defect_ticket": str(_payload_value(payload, "defect_ticket", "") or "").strip(),
        "runtime_logs": str(_payload_value(payload, "runtime_logs", "") or "").strip(),
    }
