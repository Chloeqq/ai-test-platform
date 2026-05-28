import importlib.util
import json
import sys
import uuid
from pathlib import Path
from types import ModuleType
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = PROJECT_ROOT / "apps" / "ai-orchestrator" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _load_orchestrator_app_module() -> ModuleType:
    module_name = "_ai_orchestrator_app_test_endpoint"
    existing = sys.modules.get(module_name)
    if isinstance(existing, ModuleType):
        return existing
    spec = importlib.util.spec_from_file_location(module_name, SRC_ROOT / "main.py")
    if spec is None or spec.loader is None:
        raise ImportError("unable to load ai-orchestrator app module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_APP_MODULE = _load_orchestrator_app_module()
create_app = _APP_MODULE.create_app

from orchestrator_service import OrchestratorValidationError, RunnerExecutionError  # noqa: E402


pytestmark = [pytest.mark.integration]

_IN_MEMORY_CLIENTS = {}


class FakeService:
    def __init__(self):
        self.calls = []
        self.healing_calls = []
        self.requirement_parse_calls = []
        self.risk_evaluation_calls = []
        self.failure_triage_calls = []
        self.failure_clusters_calls = []
        self.failure_cluster_calls = []
        self.requirement_telemetry_calls = []
        self.error = None

    def orchestrate(
        self,
        requirement: str,
        page: str = "",
        execute: bool = False,
        source: str = "manual",
        mode: str = "generate_only",
        runner: str = "playwright",
        input_sources=None,
        openapi_spec=None,
        prd_text: str = "",
        prd_url: str = "",
        user_story: str = "",
        git_diff: str = "",
        git_diff_path: str = "",
        openapi_url: str = "",
        defect_ticket: str = "",
        runtime_logs: str = "",
    ):
        self.calls.append(
            {
                "requirement": requirement,
                "page": page,
                "execute": execute,
                "source": source,
                "mode": mode,
                "runner": runner,
                "input_sources": input_sources,
                "openapi_spec": openapi_spec,
                "prd_text": prd_text,
                "prd_url": prd_url,
                "user_story": user_story,
                "git_diff": git_diff,
                "git_diff_path": git_diff_path,
                "openapi_url": openapi_url,
                "defect_ticket": defect_ticket,
                "runtime_logs": runtime_logs,
            }
        )
        if self.error:
            raise self.error

        return {
            "requirement_spec": {
                "version": "RequirementSpecV1",
                "source_type": source,
                "requirement": requirement,
                "page": page,
                "raw_requirement": requirement,
                "normalized_requirement": requirement.strip(),
                "source_inputs": [
                    {
                        "source_id": "input.manual.001",
                        "source_type": source,
                        "content_preview": requirement[:120],
                        "metadata": {},
                    }
                ],
                "entities": [{"entity_type": "page", "name": page, "confidence": 1.0}],
                "test_intents": [
                    {
                        "intent_id": "intent-01",
                        "title": "验证核心功能",
                        "intent_type": "functional",
                        "priority": "P1",
                        "summary": "验证核心功能",
                        "precondition": "",
                        "steps": [],
                        "expected_result": "核心功能执行后返回正确结果。",
                        "scene_type": "",
                        "test_data_type": "",
                        "involved_elements": [],
                        "steps_hint": ["goto:/product", "assert_visible:product_list_title"],
                        "dependencies": [],
                    }
                ],
                "ambiguities": [],
                "business_rules": [
                    {
                        "rule_id": "rule-01",
                        "rule_type": "functional",
                        "rule_text": "验证核心功能",
                        "confidence": 1.0,
                    }
                ],
                "coverage_matrix": [
                    {
                        "requirement_id": "REQ-001",
                        "requirement_text": requirement,
                        "intent_ids": ["intent-01"],
                        "coverage_ratio": 1.0,
                        "traceability_status": "covered",
                    }
                ],
                "dependency_graph": [],
                "historical_patterns": [],
                "change_impact": {},
                "design_input": requirement,
                "parser_runtime": {
                    "agent": "requirement-parser-agent",
                    "prompt_version": "requirement-parser.prompt.test",
                    "model": "fake",
                    "instructions_version": "test",
                    "mode": "llm",
                    "source_summary": {
                        "source_count": 1,
                        "source_types": [source],
                        "has_multisource_inputs": False,
                    },
                    "llm_trace": {
                        "attempted": True,
                        "succeeded": True,
                        "reason_code": "llm_parse",
                        "latency_ms": 1,
                        "overlay_key_count": 1,
                        "total_tokens": None,
                    },
                    "page_resolution": {
                        "candidate_page": page,
                        "selected_page": page,
                        "source_types": [source],
                        "candidate_details": [],
                    },
                    "trace_id": "trace-001",
                    "ai_trace": {"trace_id": "trace-001"},
                },
                "priority": "P1",
                "parse_confidence": 0.9,
                "quality_gate": {
                    "version": "RequirementQualityGateV1",
                    "stage": "parse",
                    "gate_enabled": True,
                    "decision": "allow",
                    "metrics": {},
                    "blockers": [],
                },
            },
            "case": {
                "id": "tc-product-999",
                "title": "Fake case",
            },
            "generated_script": {
                "version": "GeneratedScriptV1",
                "framework": "playwright",
                "language": "python",
                "case_id": "tc-product-999",
                "page": "product",
                "filename": "fake.generated.py",
                "entrypoint": "test_fake_generated",
                "script_code": "def test_fake_generated():\n    assert True\n",
                "script_path": "/tmp/fake.generated.py",
                "metadata": {"generated_by": "fake-service"},
            },
            "execution_plan": {
                "version": "ExecutionPlanV1",
                "run_mode": "generate_and_run" if execute else "generate_only",
                "source": source,
                "priority": "P1",
                "environment": "test",
                "parallelism": 1,
                "retry_policy": {"enabled": execute, "max_retries": 1, "backoff_seconds": 5},
                "stages": [
                    {
                        "stage_id": "stage-prepare",
                        "stage_name": "prepare_artifacts",
                        "runner": "orchestrator",
                        "estimated_seconds": 10,
                        "retry_limit": 0,
                        "depends_on": [],
                    }
                ],
                "scheduling_hints": {"queue": "high", "expected_total_seconds": 10, "resource_profile": "default"},
            },
            "design_generation": {
                "generator": "test-design-agent",
            },
            "risk_report": {
                "version": "RiskReportV1",
                "risk_score": 42,
                "risk_level": "low",
                "gate_decision": "allow",
                "recommendation": "风险可控。",
                "factors": [{"factor": "fake", "score": 42, "reason": "integration-test"}],
                "metadata": {"source": "fake-service"},
            },
            "failure_triage": {
                "version": "FailureTriageV1",
                "triage_label": "case_design:assertion:medium:failed",
                "failure_class": "assertion",
                "severity": "S2",
                "owner_team": "qa-design",
                "queue": "case-design-review",
                "bucket_key": "case_design|assertion|product|click,login",
                "duplicate_of": "",
                "requires_manual_review": True,
                "confidence": 0.78,
                "signals": {"status": "failed", "risk_level": "medium", "page": "product", "failure_source": "case_design"},
                "actions": [
                    {
                        "action": "create_ticket:case-design-review",
                        "owner": "qa-design",
                        "reason": "按来源 case_design / 分类 assertion 进入 case-design-review 队列处理。",
                    }
                ],
                "metadata": {"source": "fake-service", "failure_source": "case_design"},
            },
            "agent_pipeline": [
                "requirement-parser-agent",
                "test-design-agent",
                "script-generation-agent",
                "execution-planner-agent",
                "risk-evaluation-agent",
                "failure-analysis-agent",
                "failure-triage-agent",
                "self-healing-advisor-agent",
            ],
            "test_points": {
                "page": "product",
                "requirement": [requirement],
                "points": [
                    {
                        "key": "product-01",
                        "point_type": "precondition",
                        "description": "Use the shared login entry step.",
                        "action": "login",
                    },
                    {
                        "key": "product-02",
                        "point_type": "navigation",
                        "description": "Navigate with target 'product_menu'.",
                        "action": "click",
                        "target": "product_menu",
                    },
                ],
            },
            "execution_record": {
                "run_id": "tc-product-999:2026-03-17T00:00:00+00:00",
                "case_id": "tc-product-999",
                "project": "default",
                "source": source,
                "mode": mode,
                "status": "passed" if execute else "generated",
                "started_at": "2026-03-17T00:00:00+00:00",
                "finished_at": "2026-03-17T00:00:01+00:00" if execute else "",
                "step_summary": {
                    "page": "product",
                    "requirement_count": 1,
                    "total_steps": 2,
                    "action_types": ["click", "login"],
                },
                "evidence_index": {
                    "total_files": 1 if execute else 0,
                    "artifact_categories": {
                        "screenshots": 0,
                        "html_pages": 0,
                        "meta_files": 0,
                        "analysis_files": 0,
                        "suggestion_files": 0,
                        "self_healing_result_files": 1 if execute else 0,
                        "videos": 0,
                        "other_files": 0,
                    },
                    "runner_exit_code": 0 if execute else None,
                    "execution_requested": execute,
                },
            },
            "case_path": "/tmp/tc-product-999.yaml",
            "execution_requested": execute,
            "runner_exit_code": 0 if execute else None,
            "runner_stdout": "ok" if execute else "",
            "runner_stderr": "",
            "report": {
                "status": "passed" if execute else "generated",
                "summary": "Fake report summary",
                "case_id": "tc-product-999",
                "case_title": "Fake case",
                "page": "product",
                "case_path": "/tmp/tc-product-999.yaml",
                "execution_requested": execute,
                "source": source,
                "request_context": {
                    "page": "product",
                    "mode": mode,
                    "source": source,
                    "execution_requested": execute,
                },
                "execution_record": {
                    "run_id": "tc-product-999:2026-03-17T00:00:00+00:00",
                    "case_id": "tc-product-999",
                    "project": "default",
                    "source": source,
                    "mode": mode,
                    "status": "passed" if execute else "generated",
                    "started_at": "2026-03-17T00:00:00+00:00",
                    "finished_at": "2026-03-17T00:00:01+00:00" if execute else "",
                    "step_summary": {
                        "page": "product",
                        "requirement_count": 1,
                        "total_steps": 2,
                        "action_types": ["click", "login"],
                    },
                    "evidence_index": {
                        "total_files": 1 if execute else 0,
                        "artifact_categories": {
                            "screenshots": 0,
                            "html_pages": 0,
                            "meta_files": 0,
                            "analysis_files": 0,
                            "suggestion_files": 0,
                            "self_healing_result_files": 1 if execute else 0,
                            "videos": 0,
                            "other_files": 0,
                        },
                        "runner_exit_code": 0 if execute else None,
                        "execution_requested": execute,
                    },
                },
                "started_at": "2026-03-17T00:00:00+00:00",
                "finished_at": "2026-03-17T00:00:01+00:00",
                "runner_exit_code": 0 if execute else None,
                "metrics": {"passed": 1 if execute else 0, "failed": 0, "skipped": 0, "errors": 0},
                "pytest_results": {
                    "collected": 1 if execute else None,
                    "passed": 1 if execute else 0,
                    "failed": 0,
                    "skipped": 0,
                    "errors": 0,
                    "runner_exit_code": 0 if execute else None,
                    "duration_seconds": 0.12 if execute else None,
                    "has_stderr": False,
                },
                "failure_reason": "",
                "self_healing_enabled": True,
                "self_healing_attempted": execute,
                "failure_analysis": {
                    "summary": "No failure analysis needed because the run did not fail.",
                    "failure_category": "unknown",
                    "likely_cause": "",
                    "risk_level": "low",
                    "recommended_action": "No immediate failure action is required.",
                    "confidence": 1.0,
                    "evidence_used": [],
                },
                "self_healing_advice": {
                    "summary": "No self-healing action is required because the run did not fail.",
                    "suggestion_type": "no_change",
                    "suggested_changes": ["Keep the current YAML and page-object unchanged."],
                    "rationale": "The run passed, so only a no-op advisory is returned.",
                    "confidence": 1.0,
                    "safe_to_apply_manually": True,
                },
                "self_healing_suggestion_preview": {
                    "summary": "No suggestion file preview available.",
                    "advice_type": "no_change",
                    "target": "",
                    "suggestion": "",
                    "confidence": 0.0,
                    "fix_candidates": [],
                },
                "self_healing_execution_preview": {
                    "status": "success",
                    "reason": "Patch applied and rerun succeeded.",
                    "attempts_used": 1,
                    "healed": True,
                    "rolled_back": False,
                    "confidence": 0.82,
                    "plan_path": "/tmp/self_healing_patch_plan.json",
                    "result_path": "/tmp/self_healing_result.json",
                },
                "evidence": {
                    "screenshots": [],
                    "html_pages": [],
                    "meta_files": [],
                    "analysis_files": [],
                    "suggestion_files": [],
                    "self_healing_result_files": ["/tmp/self_healing_result.json"],
                    "videos": [],
                    "other_files": [],
                    "total_files": 1,
                },
                "runner_stdout_excerpt": "ok" if execute else "",
                "runner_stderr_excerpt": "",
            },
            "report_json_path": "/tmp/tc-product-999.report.json",
            "report_markdown_path": "/tmp/tc-product-999.report.md",
            "report_summary_path": "/tmp/report_summary.txt" if execute else "",
        }

    @staticmethod
    def serialize_result(result):
        return result

    @staticmethod
    def list_runners():
        return {
            "default_runner": "playwright",
            "items": [
                {"runner": "playwright", "execution_supported": True, "framework": "playwright"},
                {"runner": "api", "execution_supported": False, "framework": "requests"},
                {"runner": "mobile", "execution_supported": False, "framework": "appium"},
            ],
        }

    def get_latest_report(self):
        return {
            "report": {
                "case_id": "tc-product-999",
                "status": "passed",
                "summary": "Latest fake report",
                "execution_record": {
                    "run_id": "tc-product-999:2026-03-17T00:00:00+00:00",
                    "case_id": "tc-product-999",
                    "project": "default",
                    "source": "manual",
                    "mode": "generate_and_run",
                    "status": "passed",
                    "started_at": "2026-03-17T00:00:00+00:00",
                    "finished_at": "2026-03-17T00:00:01+00:00",
                    "step_summary": {"page": "product", "requirement_count": 1, "total_steps": 2, "action_types": ["click", "login"]},
                    "evidence_index": {"total_files": 1, "artifact_categories": {"self_healing_result_files": 1}, "runner_exit_code": 0, "execution_requested": True},
                },
                "self_healing_enabled": True,
                "self_healing_attempted": True,
                "self_healing_execution_preview": {
                    "status": "success",
                    "reason": "Patch applied and rerun succeeded.",
                    "attempts_used": 1,
                    "healed": True,
                    "rolled_back": False,
                    "confidence": 0.82,
                    "plan_path": "/tmp/self_healing_patch_plan.json",
                    "result_path": "/tmp/self_healing_result.json",
                },
            },
            "execution_record": {
                "run_id": "tc-product-999:2026-03-17T00:00:00+00:00",
                "case_id": "tc-product-999",
                "project": "default",
                "source": "manual",
                "mode": "generate_and_run",
                "status": "passed",
                "started_at": "2026-03-17T00:00:00+00:00",
                "finished_at": "2026-03-17T00:00:01+00:00",
                "step_summary": {"page": "product", "requirement_count": 1, "total_steps": 2, "action_types": ["click", "login"]},
                "evidence_index": {"total_files": 1, "artifact_categories": {"self_healing_result_files": 1}, "runner_exit_code": 0, "execution_requested": True},
            },
            "report_json_path": "/tmp/tc-product-999.report.json",
            "report_markdown_path": "/tmp/tc-product-999.report.md",
            "report_summary_path": "/tmp/report_summary.txt",
            "report_summary_preview": {
                "total_failed_cases": 2,
                "environment_failures": 1,
                "business_failures": 1,
                "high_risk_failures": 1,
                "actionable_self_healing_cases": 1,
                "environment_failure_cases": ["TC-LOGIN-001"],
                "actionable_self_healing_case_details": [
                    {
                        "case_id": "tc-product-999",
                        "target": "product_list_title",
                        "advice_type": "assertion_update",
                    }
                ],
            },
        }

    def get_report(self, case_id: str):
        if case_id == "missing":
            raise OrchestratorValidationError("Execution report not found for case_id: missing")
        return {
            "report": {
                "case_id": case_id,
                "status": "passed",
                "summary": "Report by case id",
                "execution_record": {
                    "run_id": f"{case_id}:2026-03-17T00:00:00+00:00",
                    "case_id": case_id,
                    "project": "default",
                    "source": "manual",
                    "mode": "generate_and_run",
                    "status": "passed",
                    "started_at": "2026-03-17T00:00:00+00:00",
                    "finished_at": "2026-03-17T00:00:01+00:00",
                    "step_summary": {"page": "product", "requirement_count": 1, "total_steps": 2, "action_types": ["click", "login"]},
                    "evidence_index": {"total_files": 1, "artifact_categories": {"self_healing_result_files": 1}, "runner_exit_code": 0, "execution_requested": True},
                },
                "self_healing_enabled": True,
                "self_healing_attempted": True,
                "self_healing_execution_preview": {
                    "status": "success",
                    "reason": "Patch applied and rerun succeeded.",
                    "attempts_used": 1,
                    "healed": True,
                    "rolled_back": False,
                    "confidence": 0.82,
                    "plan_path": "/tmp/self_healing_patch_plan.json",
                    "result_path": "/tmp/self_healing_result.json",
                },
                "evidence": {
                    "self_healing_result_files": ["/tmp/self_healing_result.json"],
                },
            },
            "execution_record": {
                "run_id": f"{case_id}:2026-03-17T00:00:00+00:00",
                "case_id": case_id,
                "project": "default",
                "source": "manual",
                "mode": "generate_and_run",
                "status": "passed",
                "started_at": "2026-03-17T00:00:00+00:00",
                "finished_at": "2026-03-17T00:00:01+00:00",
                "step_summary": {"page": "product", "requirement_count": 1, "total_steps": 2, "action_types": ["click", "login"]},
                "evidence_index": {"total_files": 1, "artifact_categories": {"self_healing_result_files": 1}, "runner_exit_code": 0, "execution_requested": True},
            },
            "report_json_path": f"/tmp/{case_id}.report.json",
            "report_markdown_path": f"/tmp/{case_id}.report.md",
            "report_summary_path": "/tmp/report_summary.txt",
            "report_summary_preview": {
                "total_failed_cases": 2,
                "environment_failures": 1,
                "business_failures": 1,
                "high_risk_failures": 1,
                "actionable_self_healing_cases": 1,
                "environment_failure_cases": ["TC-LOGIN-001"],
                "actionable_self_healing_case_details": [
                    {
                        "case_id": "tc-product-999",
                        "target": "product_list_title",
                        "advice_type": "assertion_update",
                    }
                ],
            },
        }

    def get_failure_clusters(
        self,
        *,
        limit: int = 200,
        max_clusters: int = 20,
        queue: str = "",
        failure_class: str = "",
        severity: str = "",
    ):
        self.failure_clusters_calls.append(
            {
                "limit": limit,
                "max_clusters": max_clusters,
                "queue": queue,
                "failure_class": failure_class,
                "severity": severity,
            }
        )
        return {
            "generated_at": "2026-03-20T00:00:00+00:00",
            "total_failed_reports": 5,
            "total_clusters": 2,
            "clusters": [
                {
                    "cluster_id": "cluster-assertion-product",
                    "failure_class": "assertion",
                    "page": "product",
                    "queue": "product-regression",
                    "owner_team": "qa-automation",
                    "severity": "S2",
                    "bucket_key": "assertion|product|click,login",
                    "occurrence_count": 3,
                    "first_seen_at": "2026-03-18T00:00:00+00:00",
                    "last_seen_at": "2026-03-20T00:00:00+00:00",
                    "latest_case_id": "tc-product-003",
                    "requires_manual_review_count": 2,
                    "manual_review_ratio": 0.67,
                    "top_risk_level": "medium",
                    "risk_level_count": {"critical": 0, "high": 1, "medium": 2, "low": 0, "unknown": 0},
                    "sample_cases": [
                        {
                            "case_id": "tc-product-003",
                            "status": "failed",
                            "page": "product",
                            "started_at": "2026-03-20T00:00:00+00:00",
                            "risk_level": "medium",
                            "severity": "S2",
                            "queue": "product-regression",
                        }
                    ],
                },
                {
                    "cluster_id": "cluster-network-order",
                    "failure_class": "network",
                    "page": "order",
                    "queue": "infra-investigation",
                    "owner_team": "qa-infra",
                    "severity": "S1",
                    "bucket_key": "network|order|click,login",
                    "occurrence_count": 2,
                    "first_seen_at": "2026-03-19T00:00:00+00:00",
                    "last_seen_at": "2026-03-20T00:00:00+00:00",
                    "latest_case_id": "TC-ORDER-002",
                    "requires_manual_review_count": 2,
                    "manual_review_ratio": 1.0,
                    "top_risk_level": "high",
                    "risk_level_count": {"critical": 0, "high": 2, "medium": 0, "low": 0, "unknown": 0},
                    "sample_cases": [],
                },
            ],
            "queue_distribution": [
                {"queue": "product-regression", "count": 3},
                {"queue": "infra-investigation", "count": 2},
            ],
            "class_distribution": [
                {"failure_class": "assertion", "count": 3},
                {"failure_class": "network", "count": 2},
            ],
            "severity_distribution": [
                {"severity": "S1", "count": 2},
                {"severity": "S2", "count": 3},
            ],
            "filters": {
                "queue": queue.strip().lower(),
                "failure_class": failure_class.strip().lower(),
                "severity": severity.strip().upper(),
            },
        }

    def get_failure_cluster(self, *, cluster_id: str, limit: int = 200):
        self.failure_cluster_calls.append({"cluster_id": cluster_id, "limit": limit})
        if cluster_id == "missing":
            raise OrchestratorValidationError("Failure cluster not found: missing")
        return {
            "generated_at": "2026-03-20T00:00:00+00:00",
            "cluster": {
                "cluster_id": cluster_id,
                "failure_class": "assertion",
                "occurrence_count": 3,
                "severity": "S2",
            },
        }

    def preview_self_healing_advice(self, page: str, case=None, failure_reason: str = "", failure_analysis=None):
        self.healing_calls.append(
            {
                "page": page,
                "case": case,
                "failure_reason": failure_reason,
                "failure_analysis": failure_analysis,
            }
        )
        if not page.strip():
            raise OrchestratorValidationError("page must not be empty")
        return {
            "summary": "Preview a manual assertion update.",
            "suggestion_type": "assertion_update",
            "suggested_changes": [
                "Check whether product_list_title is still the correct stable assertion target."
            ],
            "rationale": "The preview endpoint only returns advice and does not modify files.",
            "confidence": 0.82,
            "safe_to_apply_manually": True,
        }

    def parse_requirement(
        self,
        *,
        requirement: str,
        page: str,
        source: str = "manual",
        input_sources=None,
        openapi_spec=None,
        prd_text: str = "",
        prd_url: str = "",
        user_story: str = "",
        git_diff: str = "",
        git_diff_path: str = "",
        openapi_url: str = "",
        defect_ticket: str = "",
        runtime_logs: str = "",
    ):
        self.requirement_parse_calls.append(
            {
                "requirement": requirement,
                "page": page,
                "source": source,
                "input_sources": input_sources,
                "openapi_spec": openapi_spec,
                "prd_text": prd_text,
                "prd_url": prd_url,
                "user_story": user_story,
                "git_diff": git_diff,
                "git_diff_path": git_diff_path,
                "openapi_url": openapi_url,
                "defect_ticket": defect_ticket,
                "runtime_logs": runtime_logs,
            }
        )
        return {
            "version": "RequirementSpecV1",
            "source_type": source,
            "requirement": requirement,
            "page": page,
            "raw_requirement": requirement,
            "normalized_requirement": requirement.strip(),
            "source_inputs": [
                {
                    "source_id": "input.manual.001",
                    "source_type": source,
                    "content_preview": requirement[:120],
                    "metadata": {},
                }
            ],
            "entities": [{"entity_type": "page", "name": page, "confidence": 1.0}],
            "test_intents": [
                {
                    "intent_id": "intent-01",
                    "title": "验证核心功能",
                    "intent_type": "functional",
                    "priority": "P1",
                    "summary": "验证核心功能",
                    "precondition": "",
                    "steps": [],
                    "expected_result": "核心功能执行后返回正确结果。",
                    "scene_type": "",
                    "test_data_type": "",
                    "involved_elements": [],
                    "steps_hint": ["goto:/product", "assert_visible:product_list_title"],
                    "dependencies": [],
                }
            ],
            "ambiguities": [],
            "business_rules": [
                {
                    "rule_id": "rule-01",
                    "rule_type": "functional",
                    "rule_text": "验证核心功能",
                    "confidence": 1.0,
                }
            ],
            "coverage_matrix": [
                {
                    "requirement_id": "REQ-001",
                    "requirement_text": requirement,
                    "intent_ids": ["intent-01"],
                    "coverage_ratio": 1.0,
                    "traceability_status": "covered",
                }
            ],
            "dependency_graph": [],
            "historical_patterns": [],
            "change_impact": {},
            "priority": "P1",
            "design_input": requirement,
            "parser_runtime": {
                "agent": "requirement-parser-agent",
                "prompt_version": "requirement-parser.prompt.test",
                "model": "fake",
                "instructions_version": "test",
                "mode": "llm",
                "source_summary": {
                    "source_count": 1,
                    "source_types": [source],
                    "has_multisource_inputs": False,
                },
                "llm_trace": {
                    "attempted": True,
                    "succeeded": True,
                    "reason_code": "llm_parse",
                    "latency_ms": 1,
                    "overlay_key_count": 1,
                    "total_tokens": None,
                },
                "page_resolution": {
                    "candidate_page": page,
                    "selected_page": page,
                    "source_types": [source],
                    "candidate_details": [],
                },
                "trace_id": "trace-001",
                "ai_trace": {"trace_id": "trace-001"},
            },
            "parse_confidence": 0.9,
            "quality_gate": {
                "version": "RequirementQualityGateV1",
                "stage": "parse",
                "gate_enabled": True,
                "decision": "allow",
                "metrics": {},
                "blockers": [],
            },
        }

    def evaluate_risk(
        self,
        *,
        requirement_spec: dict,
        execution_plan: dict,
        execution_record: dict,
        failure_analysis: dict,
        failure_triage: dict | None = None,
    ):
        self.risk_evaluation_calls.append(
            {
                "requirement_spec": requirement_spec,
                "execution_plan": execution_plan,
                "execution_record": execution_record,
                "failure_analysis": failure_analysis,
                "failure_triage": failure_triage or {},
            }
        )
        return {
            "version": "RiskReportV1",
            "risk_score": 42,
            "risk_level": "low",
            "gate_decision": "allow",
            "recommendation": "风险可控。",
            "factors": [{"factor": "fake", "score": 42, "reason": "integration-test"}],
            "metadata": {"source": "fake-service"},
        }

    def triage_failure(
        self,
        *,
        failure_analysis: dict,
        execution_record: dict,
        evidence_manifest: dict,
        report: dict | None = None,
    ):
        self.failure_triage_calls.append(
            {
                "failure_analysis": failure_analysis,
                "execution_record": execution_record,
                "evidence_manifest": evidence_manifest,
                "report": report or {},
            }
        )
        return {
            "version": "FailureTriageV1",
            "triage_label": "case_design:assertion:medium:failed",
            "failure_class": "assertion",
            "severity": "S2",
            "owner_team": "qa-design",
            "queue": "case-design-review",
            "bucket_key": "case_design|assertion|product|click,login",
            "duplicate_of": "",
            "requires_manual_review": True,
            "confidence": 0.78,
            "signals": {"status": "failed", "risk_level": "medium", "page": "product", "failure_source": "case_design"},
            "actions": [
                {
                    "action": "create_ticket:case-design-review",
                    "owner": "qa-design",
                    "reason": "按来源 case_design / 分类 assertion 进入 case-design-review 队列处理。",
                }
            ],
            "metadata": {"source": "fake-service", "failure_source": "case_design"},
        }

    def get_requirement_parse_telemetry_summary(
        self,
        *,
        limit: int = 500,
        prompt_version: str = "",
        model: str = "",
        mode: str = "",
        stage: str = "",
    ):
        self.requirement_telemetry_calls.append(
            {
                "limit": limit,
                "prompt_version": prompt_version,
                "model": model,
                "mode": mode,
                "stage": stage,
            }
        )
        return {
            "version": "RequirementParseTelemetrySummaryV1",
            "generated_at": "2026-03-20T00:00:00+00:00",
            "filters": {
                "limit": limit,
                "prompt_version": prompt_version,
                "model": model,
                "mode": mode,
                "stage": stage,
            },
            "total_events": 12,
            "allow_count": 10,
            "blocked_count": 2,
            "allow_rate": 0.833,
            "llm_attempted_count": 9,
            "llm_succeeded_count": 7,
            "groups": [
                {
                    "prompt_version": "requirement-parser.prompt.v1.0.0",
                    "model": "qwen3.5-plus",
                    "mode": "hybrid",
                    "total": 9,
                    "allow_count": 8,
                    "blocked_count": 1,
                    "llm_attempted_count": 9,
                    "llm_succeeded_count": 7,
                    "allow_rate": 0.889,
                }
            ],
        }


class FakeAssetService:
    def __init__(self):
        self.page_object_calls = []
        self.element_calls = []
        self.sync_calls = []
        self.scaffold_calls = []
        self.template_list_calls = 0
        self.template_detail_calls = []

    def create_page_object(self, page: str, description: str = ""):
        self.page_object_calls.append({"page": page, "description": description})
        return {
            "page_object": {"page": page, "description": description, "elements": {}},
            "path": f"/tmp/{page}.page-object.yaml",
        }

    def add_page_element(self, page: str, element_name: str, locator_type: str, locator_value: str, role=None, description=None):
        self.element_calls.append(
            {
                "page": page,
                "name": element_name,
                "locator_type": locator_type,
                "locator_value": locator_value,
                "role": role,
                "description": description,
            }
        )
        return {
            "page_object": {
                "page": page,
                "elements": {
                    element_name: {
                        "locator_type": locator_type,
                        "locator_value": locator_value,
                    }
                },
            },
            "path": f"/tmp/{page}.page-object.yaml",
        }

    def sync_test_case(self, file_path: str, menu_target=None, assert_target=None):
        self.sync_calls.append(
            {
                "file": file_path,
                "menu_target": menu_target,
                "assert_target": assert_target,
            }
        )
        return {
            "test_case": {
                "id": "tc-product-001",
                "execution": {"page": "product"},
            },
            "path": file_path,
        }

    def scaffold_page_assets(
        self,
        page: str,
        title: str,
        requirement: str,
        description: str = "",
        priority: str = "P1",
        menu_label=None,
        assert_label=None,
        template=None,
        elements=None,
    ):
        self.scaffold_calls.append(
            {
                "page": page,
                "title": title,
                "requirement": requirement,
                "description": description,
                "priority": priority,
                "menu_label": menu_label,
                "assert_label": assert_label,
                "template": template,
                "elements": elements,
            }
        )
        return {
            "page_object": {
                "page": page,
                "elements": {
                    "catalog_search_input": {
                        "locator_type": "css",
                        "locator_value": "input[name='keyword']",
                    }
                } if elements else {},
            },
            "page_object_path": f"/tmp/{page}.page-object.yaml",
            "test_case": {
                "id": f"TC-{page.upper()}-001",
                "title": title,
                "execution": {
                    "steps": [
                        {"action": "login"},
                        {"action": "click", "target": "catalog_search_entry"},
                        {"action": "wait_for", "target": "catalog_results_panel"},
                        {"action": "assert_visible", "target": "catalog_results_panel"},
                    ]
                },
            } if elements else {"id": f"TC-{page.upper()}-001", "title": title},
            "test_case_path": f"/tmp/TC-{page.upper()}-001.yaml",
        }

    def list_scaffold_templates(self):
        self.template_list_calls += 1
        return {
            "templates": [
                {
                    "name": "catalog",
                    "summary": "商品目录/搜索结果类页面骨架",
                    "page_type": "catalog",
                    "recommended_title": "商品目录",
                    "recommended_requirement": "商品目录页面展示",
                    "elements_count": 3,
                    "elements": [],
                }
            ]
        }

    def get_scaffold_template(self, template_name: str):
        if template_name == "unknown":
            raise OrchestratorValidationError("Unknown scaffold template: unknown")
        self.template_detail_calls.append(template_name)
        return {
            "template": {
                "name": template_name,
                "summary": "商品目录/搜索结果类页面骨架",
                "page_type": "catalog",
                "recommended_title": "商品目录",
                "recommended_requirement": "商品目录页面展示",
                "elements_count": 3,
                "elements": [
                    {
                        "name": "catalog_search_entry",
                        "locator_type": "role",
                        "role": "menuitem",
                        "locator_value": "商品目录查询",
                        "smoke_role": "menu",
                    }
                ],
            }
        }


@pytest.fixture
def orchestrator_server():
    fake_service = FakeService()
    fake_asset_service = FakeAssetService()
    app = create_app(service=fake_service, asset_service=fake_asset_service)
    client = TestClient(app)
    base_url = f"inmemory://{uuid.uuid4().hex}"
    _IN_MEMORY_CLIENTS[base_url] = client

    yield {
        "service": fake_service,
        "asset_service": fake_asset_service,
        "base_url": base_url,
    }

    _IN_MEMORY_CLIENTS.pop(base_url, None)


def _request_json(base_url: str, method: str, path: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    return _request_raw(
        base_url=base_url,
        method=method,
        path=path,
        body=body,
        content_type="application/json",
    )


def _request_raw(base_url: str, method: str, path: str, body: bytes, content_type: str):
    if base_url.startswith("inmemory://"):
        client = _IN_MEMORY_CLIENTS[base_url]
        response = client.request(
            method=method,
            url=path,
            content=body,
            headers={"Content-Type": content_type},
        )
        return response.status_code, response.json()
    request = Request(
        url=f"{base_url}{path}",
        data=body,
        headers={"Content-Type": content_type},
        method=method,
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _request_text(base_url: str, path: str):
    if base_url.startswith("inmemory://"):
        client = _IN_MEMORY_CLIENTS[base_url]
        response = client.get(path)
        return response.status_code, response.headers.get("Content-Type", ""), response.get_data(as_text=True)
    request = Request(url=f"{base_url}{path}", method="GET")
    with urlopen(request, timeout=5) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read().decode("utf-8")


def test_get_console_returns_html(orchestrator_server):
    status, content_type, body = _request_text(
        orchestrator_server["base_url"],
        "/console",
    )

    assert status == 200
    assert "text/html" in content_type
    assert "Scaffold Console" in body


def test_get_console_script_returns_javascript(orchestrator_server):
    status, content_type, body = _request_text(
        orchestrator_server["base_url"],
        "/console/app.js",
    )

    assert status == 200
    assert "application/javascript" in content_type
    assert "loadTemplates" in body


def test_post_orchestrate_returns_201_and_payload(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        {"requirement": "验证商品搜索功能", "page": "product", "execute": True},
    )

    assert status == 201
    assert payload["case"]["id"] == "tc-product-999"
    assert payload["test_points"]["page"] == "product"
    assert payload["test_points"]["points"][0]["action"] == "login"
    assert payload["execution_requested"] is True
    assert payload["execution_record"]["source"] == "manual"
    assert payload["execution_record"]["mode"] == "generate_and_run"
    assert payload["execution_record"]["step_summary"]["total_steps"] == 2
    assert payload["report"]["status"] == "passed"
    assert payload["report"]["source"] == "manual"
    assert payload["report"]["request_context"]["mode"] == "generate_and_run"
    assert payload["report"]["execution_record"]["status"] == "passed"
    assert payload["report"]["pytest_results"]["passed"] == 1
    assert payload["report"]["self_healing_advice"]["suggestion_type"] == "no_change"
    assert payload["report_json_path"].endswith(".report.json")
    assert payload["report_summary_path"].endswith("report_summary.txt")
    assert orchestrator_server["service"].calls[0]["page"] == "product"


def test_post_orchestrate_supports_source_field(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        {"requirement": "验证商品搜索功能", "page": "product", "source": "regression"},
    )

    assert status == 201
    assert payload["report"]["source"] == "regression"
    assert payload["report"]["request_context"]["source"] == "regression"
    assert payload["execution_record"]["source"] == "regression"
    assert orchestrator_server["service"].calls[-1]["source"] == "regression"


def test_post_orchestrate_forwards_multisource_payload(orchestrator_server):
    status, _payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        {
            "requirement": "",
            "page": "",
            "source": "manual",
            "input_sources": [{"source_type": "openapi", "content": "GET /api/order/list"}],
            "openapi_spec": {"info": {"title": "Order API"}, "paths": {"/api/order/list": {"get": {"summary": "查询订单列表"}}}},
            "prd_text": "订单列表查询响应时间应小于 1s",
            "user_story": "作为运营，我想快速筛选订单",
            "git_diff": "+++ b/apps/order/service.py",
            "defect_ticket": "BUG-1001 timeout in order list query",
            "runtime_logs": "ERROR timeout while querying order list",
        },
    )

    assert status == 201
    call = orchestrator_server["service"].calls[-1]
    assert call["input_sources"] == [{"source_type": "openapi", "content": "GET /api/order/list"}]
    assert call["openapi_spec"]["info"]["title"] == "Order API"
    assert call["git_diff"] == "+++ b/apps/order/service.py"
    assert call["defect_ticket"] == "BUG-1001 timeout in order list query"
    assert call["runtime_logs"] == "ERROR timeout while querying order list"


def test_post_orchestrate_forwards_runner(orchestrator_server):
    status, _payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        {"requirement": "验证移动端登录", "page": "login", "runner": "mobile"},
    )

    assert status == 201
    assert orchestrator_server["service"].calls[-1]["runner"] == "mobile"


def test_post_orchestrate_supports_explicit_generate_only_mode(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        {"requirement": "验证商品搜索功能", "page": "product", "execute": True, "mode": "generate_only"},
    )

    assert status == 201
    assert payload["execution_requested"] is False
    assert payload["test_points"]["page"] == "product"
    assert payload["report"]["request_context"]["mode"] == "generate_only"
    assert orchestrator_server["service"].calls[-1]["execute"] is False


def test_post_orchestrate_supports_explicit_generate_and_run_mode(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        {"requirement": "验证商品搜索功能", "page": "product", "execute": False, "mode": "generate_and_run"},
    )

    assert status == 201
    assert payload["execution_requested"] is True
    assert payload["report"]["request_context"]["mode"] == "generate_and_run"
    assert orchestrator_server["service"].calls[-1]["execute"] is True


def test_post_orchestrate_rejects_unknown_mode(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        {"requirement": "验证商品搜索功能", "page": "product", "mode": "rewrite_everything"},
    )

    assert status == 422
    assert payload["error"]["code"] == "validation_error"


def test_post_healing_preview_returns_200_and_payload(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/healing/preview",
        {
            "page": "product",
            "failure_reason": "expected product list title to be visible",
            "failure_analysis": {
                "summary": "UI assertion failed on product page.",
                "failure_category": "assertion",
                "likely_cause": "The expected product list title was not rendered.",
                "risk_level": "high",
                "recommended_action": "Review the stable assertion target manually.",
                "confidence": 0.84,
                "evidence_used": ["stdout"],
            },
        },
    )

    assert status == 200
    assert payload["self_healing_advice"]["suggestion_type"] == "assertion_update"
    assert payload["self_healing_advice"]["safe_to_apply_manually"] is True
    assert orchestrator_server["service"].healing_calls[0]["page"] == "product"


def test_post_healing_preview_maps_validation_errors(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/healing/preview",
        {"page": " "},
    )

    assert status == 422
    assert payload["error"]["code"] == "validation_error"


def test_post_requirements_parse_returns_201_and_payload(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/requirements/parse",
        {
            "requirement": "验证商品搜索功能",
            "page": "product",
            "source": "manual",
        },
    )

    assert status == 201
    assert payload["requirement_spec"]["version"] == "RequirementSpecV1"
    assert payload["requirement_spec"]["page"] == "product"
    assert "# 需求测试点分析" in payload["requirement_analysis_markdown"]
    assert payload["output_contract"]["machine_schema"] == "RequirementSpecV1"
    assert payload["output_contract"]["human_render"] == "RequirementAnalysisMarkdownV1"
    assert orchestrator_server["service"].requirement_parse_calls[-1]["requirement"] == "验证商品搜索功能"


def test_post_risk_evaluate_returns_201_and_payload(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/risk/evaluate",
        {
            "requirement_spec": {"priority": "P1"},
            "execution_plan": {"version": "ExecutionPlanV1"},
            "execution_record": {"status": "passed"},
            "failure_analysis": {"risk_level": "low"},
            "failure_triage": {"failure_class": "assertion"},
        },
    )

    assert status == 201
    assert payload["risk_report"]["version"] == "RiskReportV1"
    assert payload["risk_report"]["gate_decision"] == "allow"
    assert payload["output_contract"]["machine_schema"] == "RiskReportV1"
    assert payload["output_contract"]["human_render"] == "RiskReportMarkdownV1"
    assert orchestrator_server["service"].risk_evaluation_calls[-1]["execution_record"]["status"] == "passed"
    assert orchestrator_server["service"].risk_evaluation_calls[-1]["failure_triage"]["failure_class"] == "assertion"


def test_post_failures_triage_returns_201_and_payload(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/failures/triage",
        {
            "failure_analysis": {"failure_category": "assertion", "failure_source": "case_design", "risk_level": "medium"},
            "execution_record": {"status": "failed", "step_summary": {"page": "product", "action_types": ["login", "click"]}},
            "evidence_manifest": {"total_files": 3, "analysis_files": ["/tmp/a.txt"]},
            "report": {"case_id": "tc-product-001", "page": "product"},
        },
    )

    assert status == 201
    assert payload["failure_triage"]["version"] == "FailureTriageV1"
    assert payload["failure_triage"]["failure_class"] == "assertion"
    assert payload["failure_triage"]["owner_team"] == "qa-design"
    assert payload["failure_triage"]["queue"] == "case-design-review"
    assert payload["failure_triage"]["signals"]["failure_source"] == "case_design"
    assert payload["output_contract"]["machine_schema"] == "FailureTriageV1"
    assert payload["output_contract"]["human_render"] == "FailureTriageMarkdownV1"
    assert orchestrator_server["service"].failure_triage_calls[-1]["execution_record"]["status"] == "failed"


def test_get_requirement_telemetry_summary_returns_200(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/requirements/telemetry/summary?limit=321&prompt_version=requirement-parser.prompt.v1.0.0&model=qwen3.5-plus&mode=hybrid&stage=parse",
        body=b"",
        content_type="application/json",
    )

    assert status == 200
    assert payload["version"] == "RequirementParseTelemetrySummaryV1"
    assert payload["total_events"] == 12
    assert payload["groups"][0]["prompt_version"] == "requirement-parser.prompt.v1.0.0"
    assert orchestrator_server["service"].requirement_telemetry_calls[-1]["limit"] == 321
    assert orchestrator_server["service"].requirement_telemetry_calls[-1]["mode"] == "hybrid"


def test_post_orchestrate_rejects_invalid_json(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        body=b"{invalid",
        content_type="application/json",
    )

    assert status == 400
    assert payload["error"]["code"] == "invalid_json"


def test_post_orchestrate_requires_application_json(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        body=b"requirement=test",
        content_type="text/plain",
    )

    assert status == 415
    assert payload["error"]["code"] == "unsupported_media_type"


def test_post_orchestrate_maps_runner_failures_to_502(orchestrator_server):
    orchestrator_server["service"].error = RunnerExecutionError(
        "Runner execution failed",
        details={"runner_exit_code": 1},
    )

    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        {"requirement": "验证商品搜索功能", "page": "product"},
    )

    assert status == 502
    assert payload["error"]["code"] == "runner_failed"
    assert payload["error"]["details"]["runner_exit_code"] == 1


def test_post_orchestrate_returns_404_for_unknown_route(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/unknown",
        {"requirement": "验证商品搜索功能", "page": "product"},
    )

    assert status == 404
    assert payload["error"]["code"] == "not_found"


def test_get_scaffold_templates_returns_200(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/assets/scaffold/templates",
        body=b"",
        content_type="application/json",
    )

    assert status == 200
    assert payload["templates"][0]["name"] == "catalog"
    assert orchestrator_server["asset_service"].template_list_calls == 1


def test_get_latest_report_returns_200(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/reports/latest",
        body=b"",
        content_type="application/json",
    )

    assert status == 200
    assert payload["report"]["case_id"] == "tc-product-999"
    assert payload["execution_record"]["case_id"] == "tc-product-999"
    assert payload["report_json_path"].endswith(".report.json")
    assert payload["report_summary_path"].endswith("report_summary.txt")
    assert payload["report_summary_preview"]["total_failed_cases"] == 2
    assert payload["report_summary_preview"]["actionable_self_healing_cases"] == 1
    assert payload["report_summary_preview"]["environment_failure_cases"] == ["TC-LOGIN-001"]
    assert payload["report_summary_preview"]["actionable_self_healing_case_details"][0]["target"] == "product_list_title"
    assert payload["report"]["self_healing_execution_preview"]["status"] == "success"
    assert payload["report"]["self_healing_enabled"] is True


def test_get_runner_catalog_returns_200(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/runners/catalog",
        body=b"",
        content_type="application/json",
    )

    assert status == 200
    assert payload["default_runner"] == "playwright"
    assert {item["runner"] for item in payload["items"]} == {"playwright", "api", "mobile"}


def test_get_report_by_case_id_returns_200(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/reports/tc-product-999",
        body=b"",
        content_type="application/json",
    )

    assert status == 200
    assert payload["report"]["case_id"] == "tc-product-999"
    assert payload["execution_record"]["mode"] == "generate_and_run"
    assert payload["report_summary_path"].endswith("report_summary.txt")
    assert payload["report_summary_preview"]["environment_failures"] == 1
    assert payload["report_summary_preview"]["actionable_self_healing_case_details"][0]["advice_type"] == "assertion_update"
    assert payload["report"]["evidence"]["self_healing_result_files"][0].endswith("self_healing_result.json")
    assert payload["report"]["self_healing_attempted"] is True


def test_get_report_by_case_id_maps_validation_errors(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/reports/missing",
        body=b"",
        content_type="application/json",
    )

    assert status == 422
    assert payload["error"]["code"] == "validation_error"


def test_get_failures_clusters_returns_200(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/failures/clusters?limit=120&max_clusters=10&queue=product-regression&failure_class=assertion&severity=S2",
        body=b"",
        content_type="application/json",
    )

    assert status == 200
    assert payload["total_clusters"] == 2
    assert payload["clusters"][0]["cluster_id"] == "cluster-assertion-product"
    assert orchestrator_server["service"].failure_clusters_calls[-1]["limit"] == 120
    assert orchestrator_server["service"].failure_clusters_calls[-1]["max_clusters"] == 10
    assert orchestrator_server["service"].failure_clusters_calls[-1]["queue"] == "product-regression"
    assert orchestrator_server["service"].failure_clusters_calls[-1]["failure_class"] == "assertion"
    assert orchestrator_server["service"].failure_clusters_calls[-1]["severity"] == "S2"


def test_get_failure_cluster_by_id_returns_200(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/failures/clusters/cluster-assertion-product?limit=180",
        body=b"",
        content_type="application/json",
    )

    assert status == 200
    assert payload["cluster"]["cluster_id"] == "cluster-assertion-product"
    assert payload["cluster"]["failure_class"] == "assertion"
    assert orchestrator_server["service"].failure_cluster_calls[-1]["cluster_id"] == "cluster-assertion-product"
    assert orchestrator_server["service"].failure_cluster_calls[-1]["limit"] == 180


def test_get_failure_cluster_by_id_maps_validation_errors(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/failures/clusters/missing",
        body=b"",
        content_type="application/json",
    )

    assert status == 422
    assert payload["error"]["code"] == "validation_error"


def test_get_scaffold_template_detail_returns_200(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/assets/scaffold/templates/catalog",
        body=b"",
        content_type="application/json",
    )

    assert status == 200
    assert payload["template"]["name"] == "catalog"
    assert orchestrator_server["asset_service"].template_detail_calls == ["catalog"]


def test_get_scaffold_template_detail_maps_validation_errors(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/assets/scaffold/templates/unknown",
        body=b"",
        content_type="application/json",
    )

    assert status == 422
    assert payload["error"]["code"] == "validation_error"


def test_post_create_page_object_returns_201(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/assets/page-objects",
        {"page": "catalog", "description": "商品目录页"},
    )

    assert status == 201
    assert payload["page_object"]["page"] == "catalog"
    assert orchestrator_server["asset_service"].page_object_calls[0]["page"] == "catalog"


def test_post_add_page_object_element_returns_201(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/assets/page-objects/catalog/elements",
        {
            "name": "catalog_menu",
            "locator_type": "role",
            "locator_value": "商品目录",
            "role": "menuitem",
        },
    )

    assert status == 201
    assert "catalog_menu" in payload["page_object"]["elements"]
    assert orchestrator_server["asset_service"].element_calls[0]["page"] == "catalog"


def test_post_sync_test_case_returns_200(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/assets/test-cases/sync",
        {"file": "assets/test-cases/smoke/product-smoke.yaml"},
    )

    assert status == 200
    assert payload["test_case"]["id"] == "tc-product-001"
    assert orchestrator_server["asset_service"].sync_calls[0]["file"] == "assets/test-cases/smoke/product-smoke.yaml"


def test_post_scaffold_assets_returns_201(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/assets/scaffold",
        {
            "page": "catalog",
            "title": "商品目录",
            "requirement": "商品目录页面展示",
            "description": "创建目录页骨架",
        },
    )

    assert status == 201
    assert payload["page_object"]["page"] == "catalog"
    assert payload["test_case"]["id"] == "TC-CATALOG-001"
    assert orchestrator_server["asset_service"].scaffold_calls[0]["page"] == "catalog"


def test_post_scaffold_assets_accepts_element_templates(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/assets/scaffold",
        {
            "page": "catalog",
            "title": "商品目录",
            "requirement": "商品目录页面展示",
            "elements": [
                {
                    "name": "catalog_search_input",
                    "locator_type": "css",
                    "locator_value": "input[name='keyword']",
                    "description": "搜索输入框",
                },
                {
                    "name": "catalog_search_entry",
                    "locator_type": "role",
                    "role": "menuitem",
                    "locator_value": "商品目录查询",
                    "smoke_role": "menu",
                },
                {
                    "name": "catalog_results_panel",
                    "locator_type": "css",
                    "locator_value": ".catalog-results",
                    "smoke_role": "assert",
                }
            ],
        },
    )

    assert status == 201
    assert "catalog_search_input" in payload["page_object"]["elements"]
    assert orchestrator_server["asset_service"].scaffold_calls[0]["elements"][0]["name"] == "catalog_search_input"
    assert payload["test_case"]["execution"]["steps"][1]["target"] == "catalog_search_entry"
    assert payload["test_case"]["execution"]["steps"][2]["target"] == "catalog_results_panel"


def test_post_scaffold_assets_accepts_template_name(orchestrator_server):
    status, _payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/assets/scaffold",
        {
            "page": "catalog",
            "title": "商品目录",
            "requirement": "商品目录页面展示",
            "template": "catalog",
        },
    )

    assert status == 201
    assert orchestrator_server["asset_service"].scaffold_calls[0]["template"] == "catalog"
