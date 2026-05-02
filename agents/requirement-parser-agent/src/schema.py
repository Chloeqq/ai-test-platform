from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RequirementSourceInput:
    source_id: str
    source_type: str
    content_preview: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RequirementEntity:
    name: str
    entity_type: str
    confidence: float = 0.7


@dataclass
class TestIntent:
    intent_id: str
    title: str
    intent_type: str
    priority: str
    precondition: str = ""
    steps: list[str] = field(default_factory=list)
    target: str = ""
    value: Any = None
    expected_result: str = ""
    scene_type: str = ""
    test_data_type: str = ""
    involved_elements: list[str] = field(default_factory=list)
    steps_hint: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)


@dataclass
class BusinessRule:
    rule_id: str
    rule_text: str
    rule_type: str
    confidence: float = 0.7


@dataclass
class AmbiguityItem:
    item_id: str
    text: str
    reason: str
    suggestion: str
    severity: str = "medium"


@dataclass
class RequirementSpec:
    version: str
    source_type: str
    page: str
    raw_requirement: str
    normalized_requirement: str
    source_inputs: list[RequirementSourceInput] = field(default_factory=list)
    entities: list[RequirementEntity] = field(default_factory=list)
    test_intents: list[TestIntent] = field(default_factory=list)
    coverage_matrix: list[dict[str, Any]] = field(default_factory=list)
    dependency_graph: list[dict[str, Any]] = field(default_factory=list)
    business_rules: list[BusinessRule] = field(default_factory=list)
    ambiguities: list[AmbiguityItem] = field(default_factory=list)
    change_impact: dict[str, Any] = field(default_factory=dict)
    historical_patterns: list[dict[str, Any]] = field(default_factory=list)
    priority: str = "P1"
    design_input: str = ""
    parse_confidence: float = 0.75
    parser_runtime: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
