from __future__ import annotations

from collections.abc import Callable
from typing import Any

RunGenerate = Callable[..., dict[str, Any]]
RunParse = Callable[..., dict[str, Any]]
ExtractQualityGate = Callable[[Any], dict[str, Any] | None]
IsQualityGateBlocked = Callable[[Any], tuple[bool, dict[str, Any] | None]]
RenderRequirementSpecMarkdown = Callable[[dict[str, Any]], str]


class OrchestratorClient:
    def __init__(
        self,
        *,
        run_generate: RunGenerate,
        run_parse: RunParse,
        extract_quality_gate: ExtractQualityGate,
        is_quality_gate_blocked: IsQualityGateBlocked,
        render_requirement_spec_markdown: RenderRequirementSpecMarkdown,
    ) -> None:
        self._run_generate = run_generate
        self._run_parse = run_parse
        self._extract_quality_gate = extract_quality_gate
        self._is_quality_gate_blocked = is_quality_gate_blocked
        self._render_requirement_spec_markdown = render_requirement_spec_markdown

    def generate(self, **kwargs: Any) -> dict[str, Any]:
        return self._run_generate(**kwargs)

    def parse(self, **kwargs: Any) -> dict[str, Any]:
        return self._run_parse(**kwargs)

    def extract_quality_gate(self, payload: Any) -> dict[str, Any] | None:
        return self._extract_quality_gate(payload)

    def is_quality_gate_blocked(self, payload: Any) -> tuple[bool, dict[str, Any] | None]:
        return self._is_quality_gate_blocked(payload)

    def render_requirement_spec_markdown(self, requirement_spec: dict[str, Any]) -> str:
        return self._render_requirement_spec_markdown(requirement_spec)
