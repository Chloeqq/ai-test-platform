"""测试夹具：不依赖 DB 的轻量级 fake 对象。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeEvalItem:
    """模拟 QualityEvalItem，只包含 Evaluator 实际访问的字段。"""

    requirement_text: str = ""
    expected_coverage: list[str] = field(default_factory=list)
    expected_assertions: list[dict[str, str]] = field(default_factory=list)
    expected_page_codes: list[str] = field(default_factory=list)
    perturbed_requirement: str = ""
    known_issues: list[str] = field(default_factory=list)
    category: str = ""
    item_id: str = "it-001"
    dataset_id: str = "de-test"


def make_item(**kwargs: Any) -> FakeEvalItem:
    """快捷创建 FakeEvalItem。"""
    return FakeEvalItem(**kwargs)
