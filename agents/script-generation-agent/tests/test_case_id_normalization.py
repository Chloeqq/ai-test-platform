from __future__ import annotations
# ruff: noqa: E402

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_AGENT_ROOT = REPO_ROOT / "agents" / "script-generation-agent"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_AGENT_ROOT))

from shared_backend.case_ids import build_case_id, build_case_metadata, normalize_case_id
from src.agent import ScriptGenerationAgent


def test_generate_normalizes_legacy_case_id() -> None:
    result = ScriptGenerationAgent().generate(
        case={
            "id": "TC-SEARCH-001",
            "module": "search",
            "title": "搜索结果生成脚本",
            "execution": {"page": "search", "steps": []},
        }
    )

    assert result["case_id"] == normalize_case_id("TC-SEARCH-001")
    assert result["filename"].startswith("atp_web_")


def test_generate_builds_platform_case_id_when_missing() -> None:
    case = {
        "module": "returnapply",
        "title": "退货申请查询基础冒烟",
        "description": "验证退货申请查询入口可访问",
        "tags": ["ai-generated", "smoke"],
        "execution": {"page": "returnapply", "steps": []},
    }

    metadata = build_case_metadata(
        page="returnapply",
        module="returnapply",
        title="退货申请查询基础冒烟",
        description="验证退货申请查询入口可访问",
        tags=["ai-generated", "smoke"],
        source_hint="ai-generated",
    )
    expected_case_id = build_case_id(
        page="returnapply",
        module="returnapply",
        sequence=1,
        project=metadata["project"],
        client=metadata["client"],
        page_code=metadata["page_code"],
        module_code=metadata["module_code"],
        case_type=metadata["case_type"],
        source=metadata["source"],
    )

    result = ScriptGenerationAgent().generate(case=case)

    assert result["case_id"] == expected_case_id
    assert result["entrypoint"] == f"test_{result['filename'].removesuffix('.generated.py')}"
