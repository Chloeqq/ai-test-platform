"""测试 _build_quality_report — warnings 数据源 + P0-1 candidate_step + P0-2 data_warnings。"""
from __future__ import annotations

from app.services.workbench_asset_views import _build_quality_report


def _make_asset(*, plan_points: list[dict] | None = None) -> dict:
    return {
        "plan": {
            "points": plan_points or [],
        },
        # 模拟 upsert 后的状态：顶层 warnings 为 []
        "warnings": [],
    }


def _make_point(intent_id: str, point_type: str = "functional", *, warnings: list[str] | None = None, steps: list[dict] | None = None) -> dict:
    p: dict = {
        "intent_id": intent_id,
        "point_type": point_type,
        "warnings": warnings or [],
        "steps": steps or [],
    }
    return p


def _make_step(action: str) -> dict:
    return {"action": action}


# ── point warnings 正常进入 quality_report ──

def test_point_warnings_enter_quality_report() -> None:
    """单 point 的 warnings 应出现在 quality_report 中。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", warnings=[
            "assertion_missing: 无可执行断言",
            "步骤仍需人工结构化：观察页面跳转",
        ]),
    ])
    qr = _build_quality_report(asset)
    assert len(qr["assertion_warnings"]) == 1
    assert "assertion_missing" in qr["assertion_warnings"][0]
    assert len(qr["other_warnings"]) == 1
    assert "仍需人工结构化" in qr["other_warnings"][0]


# ── 多 point warnings 聚合 ──

def test_multi_point_warnings_aggregation() -> None:
    """多个 point 的 warnings 应被聚合去重。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", warnings=["assertion_missing: 无断言"]),
        _make_point("intent-02", warnings=["缺少涉及元素。"]),
        _make_point("intent-03", warnings=["步骤仍需人工结构化：打开页面"]),
    ])
    qr = _build_quality_report(asset)
    assert len(qr["assertion_warnings"]) == 1
    assert len(qr["other_warnings"]) == 2
    assert qr["total_points"] == 3


# ── 去重 ──

def test_duplicate_warnings_deduped() -> None:
    """相同的 warning 出现在多个 point 中时只保留一条。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", warnings=["步骤仍需人工结构化：打开页面"]),
        _make_point("intent-02", warnings=["步骤仍需人工结构化：打开页面"]),
        _make_point("intent-03", warnings=["步骤仍需人工结构化：打开页面"]),
    ])
    qr = _build_quality_report(asset)
    assert len(qr["other_warnings"]) == 1


# ── 编辑保存后 warning 不丢失（即使顶层 warnings=[]）──

def test_warnings_survive_upsert() -> None:
    """模拟 upsert 后的资产（warnings=[]），warning 仍从 point 级读取。"""
    asset = {
        "plan": {
            "points": [
                _make_point("intent-01", warnings=[
                    "assertion_missing: 无可执行断言",
                    "缺少涉及元素。",
                ]),
                _make_point("intent-02", warnings=[
                    "用户名输入框 输入步骤缺少明确测试数据",
                ]),
            ],
        },
        "warnings": [],  # upsert 写入
    }
    qr = _build_quality_report(asset)
    assert len(qr["assertion_warnings"]) == 1
    assert len(qr["other_warnings"]) == 2
    assert qr["total_points"] == 2


# ── 空 warnings 兼容 ──

def test_empty_points_no_crash() -> None:
    """空 points 列表不应崩溃。"""
    asset = _make_asset(plan_points=[])
    qr = _build_quality_report(asset)
    assert qr["total_points"] == 0
    assert qr["assertion_warnings"] == []
    assert qr["other_warnings"] == []
    assert qr["score"] == 100
    assert qr["decision"] == "PASS"


# ── 无 warnings 的 point ──

def test_point_without_warnings_key() -> None:
    """point 字典无 warnings 键时不应崩溃。"""
    asset = _make_asset(plan_points=[
        {"intent_id": "intent-01", "point_type": "functional", "steps": []},
        {"intent_id": "intent-02", "point_type": "negative", "steps": []},
    ])
    qr = _build_quality_report(asset)
    assert qr["total_points"] == 2
    assert qr["assertion_warnings"] == []
    assert qr["other_warnings"] == []


# ── 断言步骤检测不受 warnings 影响 ──

def test_zero_assertion_detection() -> None:
    """零断言检测应从 steps 分析，不受 warnings 聚合影响。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", steps=[_make_step("input"), _make_step("click")], warnings=[
            "assertion_missing: 无可执行断言",
        ]),
        _make_point("intent-02", steps=[_make_step("input"), _make_step("assert_visible")], warnings=[]),
    ])
    qr = _build_quality_report(asset)
    assert qr["zero_assertion_count"] == 1  # 仅 intent-01
    assert len(qr["assertion_warnings"]) == 1
    per_point = {p["intent_id"]: p for p in qr["per_point"]}
    assert per_point["intent-01"]["has_assertion"] is False
    assert per_point["intent-02"]["has_assertion"] is True


# ── P0-1: candidate_step 不计入 zero_assertion ──

def test_candidate_step_excluded_from_zero_assert() -> None:
    """candidate_step 且无断言的 point 不计入 zero_assert_count（本质是未结构化）。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", steps=[_make_step("candidate_step")], warnings=[
            "assertion_missing: 无可执行断言",
            "步骤仍需人工结构化：打开登录页",
        ]),
    ])
    qr = _build_quality_report(asset)
    assert qr["zero_assertion_count"] == 0  # 不计入
    assert qr["candidate_step_count"] == 1
    assert qr["unprocessed_count"] == 1
    assert qr["decision"] == "REVIEW"  # candidate_step → REVIEW，非 REJECT


def test_candidate_step_with_assertion_not_unprocessed() -> None:
    """candidate_step + 断言共存 → candidate_step_count+1，unprocessed_count 不增加。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", steps=[_make_step("candidate_step"), _make_step("assert_visible")], warnings=[
            "步骤仍需人工结构化：直接访问工作台首页",
        ]),
    ])
    qr = _build_quality_report(asset)
    assert qr["zero_assertion_count"] == 0  # 有断言，本就不计
    assert qr["candidate_step_count"] == 1
    assert qr["unprocessed_count"] == 0  # 有断言，不算未处理


def test_zero_assert_without_candidate_step_still_reject() -> None:
    """无 candidate_step 的零断言 point 仍计入 zero_assert → REJECT。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", steps=[_make_step("input"), _make_step("click")], warnings=[
            "assertion_missing: 无可执行断言",
        ]),
    ])
    qr = _build_quality_report(asset)
    assert qr["zero_assertion_count"] == 1
    assert qr["candidate_step_count"] == 0
    assert qr["decision"] == "REJECT"


# ── P0-2: data_warnings 不影响 decision ──

def test_data_warnings_not_in_quality_warnings() -> None:
    """数据补全提示归入 data_warnings，不进入 quality_warnings。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", steps=[_make_step("input"), _make_step("assert_text")], warnings=[
            "用户名输入框 的空格输入需要后续由 DSL 数据引用执行，当前 steps_hint 无法无损表达纯空格。",
            "用户名输入框 输入步骤缺少明确测试数据：在账号输入框输入空字符串",
        ]),
    ])
    qr = _build_quality_report(asset)
    assert len(qr["data_warnings"]) == 2
    assert len(qr["quality_warnings"]) == 0
    assert qr["decision"] == "PASS"  # 仅有 data_warnings → PASS


def test_mixed_warnings_separated() -> None:
    """质量 warning 和数据 warning 混合时应正确分类。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", steps=[_make_step("input"), _make_step("assert_visible")], warnings=[
            "步骤仍需人工结构化：直接访问工作台首页",
            "用户名输入框 的空格输入需要后续由 DSL 数据引用执行",
        ]),
    ])
    qr = _build_quality_report(asset)
    assert len(qr["data_warnings"]) == 1
    assert len(qr["quality_warnings"]) == 1
    assert "仍需人工结构化" in qr["quality_warnings"][0]
    assert "空格输入" in qr["data_warnings"][0]
    assert qr["decision"] == "REVIEW"  # quality_warning 触发


# ── P0-1 + P0-2 组合 ──

def test_candidate_step_with_data_warnings() -> None:
    """candidate_step(point) + data_warning → REVIEW（来自 candidate_step），data warning 不影响。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", steps=[_make_step("candidate_step")], warnings=[
            "用户名输入框 输入步骤缺少明确测试数据",
        ]),
    ])
    qr = _build_quality_report(asset)
    assert qr["candidate_step_count"] == 1
    assert qr["unprocessed_count"] == 1
    assert qr["zero_assertion_count"] == 0
    assert len(qr["data_warnings"]) == 1
    assert len(qr["quality_warnings"]) == 0
    assert qr["decision"] == "REVIEW"  # candidate_step → REVIEW，不是 REJECT
