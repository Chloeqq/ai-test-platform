import os
import json
from pathlib import Path
from datetime import datetime, timezone

try:
    from datetime import UTC
except ImportError:  # Python < 3.11
    UTC = timezone.utc
from urllib.parse import quote, urlsplit

import pytest
import yaml
from dotenv import load_dotenv
from playwright.sync_api import Page

try:
    import allure
except ImportError:  # pragma: no cover - optional dependency
    allure = None


ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ROOT_ENV)
PAGE_OBJECTS_ROOT = Path(__file__).resolve().parents[2] / "assets" / "page-objects" / "web"
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}
FALSY_ENV_VALUES = {"0", "false", "no", "off"}

try:
    from shared_backend.schemas import normalize_evidence_manifest_v1, normalize_execution_record_v1
except Exception:  # pragma: no cover - keep runner usable when shared package unavailable
    normalize_evidence_manifest_v1 = None
    normalize_execution_record_v1 = None

try:
    from shared_backend.case_ids import normalize_case_id
except Exception:  # pragma: no cover - keep runner usable when shared package unavailable
    normalize_case_id = None


def resolve_artifacts_dir() -> Path:
    raw_path = os.getenv("PLAYWRIGHT_ARTIFACTS_DIR", "").strip()
    if raw_path:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path
    else:
        path = Path(__file__).resolve().parent / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_video_dir() -> Path:
    raw_path = os.getenv("PLAYWRIGHT_VIDEO_DIR", "").strip()
    if raw_path:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / raw_path
    else:
        path = Path(__file__).resolve().parent / "test-results" / "videos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def env_flag(name: str, *, default: bool = False) -> bool:
    raw_value = os.getenv(name, "").strip().lower()
    if raw_value in TRUTHY_ENV_VALUES:
        return True
    if raw_value in FALSY_ENV_VALUES:
        return False
    return default


def sanitize_artifact_name(nodeid: str) -> str:
    sanitized = nodeid.replace("::", "__").replace("/", "_").replace("\\", "_").replace(" ", "_")
    return "".join(char if char.isalnum() or char in {"-", "_", "[", "]"} else "_" for char in sanitized)


def _normalize_execution_record_payload(payload: dict, *, strict: bool = False) -> dict:
    if normalize_execution_record_v1 is None:
        return payload if isinstance(payload, dict) else {}
    try:
        normalized, _warnings = normalize_execution_record_v1(payload, strict=strict)
        return normalized
    except Exception:
        return payload if isinstance(payload, dict) else {}


def _normalize_evidence_manifest_payload(payload: dict, *, strict: bool = False) -> dict:
    if normalize_evidence_manifest_v1 is None:
        return payload if isinstance(payload, dict) else {}
    try:
        normalized, _warnings = normalize_evidence_manifest_v1(payload, strict=strict)
        return normalized
    except Exception:
        return payload if isinstance(payload, dict) else {}


def extract_failure_message(report) -> str:
    if report is None:
        return ""

    longreprtext = getattr(report, "longreprtext", "")
    if isinstance(longreprtext, str) and longreprtext.strip():
        return longreprtext.strip()

    longrepr = getattr(report, "longrepr", None)
    if longrepr is None:
        return ""

    if hasattr(longrepr, "reprcrash") and getattr(longrepr, "reprcrash", None):
        message = getattr(longrepr.reprcrash, "message", "")
        if message:
            return str(message).strip()

    return str(longrepr).strip()


def build_failure_analysis_payload(
    *,
    error_message: str,
    page_html: str,
    current_url: str,
    page_title: str,
    screenshot_path: Path,
    html_path: Path,
    meta_path: Path,
    failure_context: dict | None = None,
) -> dict:
    normalized_context = normalize_failure_context(failure_context)
    return {
        "error": error_message,
        "current_url": current_url,
        "page_title": page_title,
        "page_html": page_html,
        "failed_step": normalized_context.get("failed_step", {}),
        "element_impact": normalized_context.get("element_impact", {}),
        "report": {
            "status": "failed",
            "runner_stdout_excerpt": "",
            "runner_stderr_excerpt": error_message,
            "evidence": {
                "screenshots": [str(screenshot_path)],
                "html_pages": [str(html_path)],
                "meta_files": [str(meta_path)],
                "videos": [],
                "other_files": [],
                "total_files": 3,
            },
        },
    }


def normalize_failure_context(value: dict | None) -> dict:
    source = value if isinstance(value, dict) else {}
    failed_step = source.get("failed_step") if isinstance(source.get("failed_step"), dict) else source
    failed_step = failed_step if isinstance(failed_step, dict) else {}
    element_code = str(
        failed_step.get("element_code")
        or failed_step.get("target")
        or ""
    ).strip()
    page_code = str(failed_step.get("page_code") or failed_step.get("page") or "").strip()
    project_code = str(
        source.get("project_code")
        or failed_step.get("project_code")
        or os.getenv("TEST_PROJECT", "mall")
        or "mall"
    ).strip() or "mall"
    normalized_step = {
        "step_index": failed_step.get("step_index"),
        "page_code": page_code,
        "action": str(failed_step.get("action") or "").strip(),
        "element_code": element_code,
        "target": element_code,
        "selector": str(failed_step.get("selector") or "").strip(),
        "locator_type": str(failed_step.get("locator_type") or "").strip(),
        "role": str(failed_step.get("role") or "").strip(),
        "intent_id": str(failed_step.get("intent_id") or "").strip(),
        "traceability": failed_step.get("traceability") if isinstance(failed_step.get("traceability"), dict) else {},
    }
    element_impact: dict = {}
    if element_code and page_code:
        element_impact = {
            "project_code": project_code,
            "page_code": page_code,
            "element_code": element_code,
            "locator_type": normalized_step["locator_type"],
            "locator_value": normalized_step["selector"],
            "role": normalized_step["role"],
            "governance_action": "review_element",
            "governance_href": (
                f"/assets/page-objects/{quote(page_code)}/elements/"
                f"{quote(element_code)}?project={quote(project_code)}"
            ),
        }
    has_step_context = any(
        str(value or "").strip()
        for value in normalized_step.values()
        if not isinstance(value, dict)
    )
    return {
        "failed_step": normalized_step if has_step_context else {},
        "element_impact": element_impact,
    }


def resolve_project_code_from_request(request) -> str:
    node = getattr(request, "node", request)
    test_case = extract_test_case_from_node(node)
    if isinstance(test_case, dict):
        for key in ("project_code", "project"):
            value = str(test_case.get(key, "")).strip()
            if value:
                return value
        metadata = test_case.get("metadata")
        if isinstance(metadata, dict):
            for key in ("project_code", "project"):
                value = str(metadata.get(key, "")).strip()
                if value:
                    return value
    return str(os.getenv("TEST_PROJECT", "mall") or "mall").strip() or "mall"


def extract_test_case_from_node(node) -> dict:
    params = getattr(getattr(node, "callspec", None), "params", {})
    if not isinstance(params, dict):
        return {}
    for key in ("test_case", "case_param"):
        candidate = params.get(key)
        if isinstance(candidate, dict):
            return candidate
        payload = getattr(candidate, "payload", None)
        if isinstance(payload, dict):
            return payload
    return {}


def extract_failure_context_from_page(page: Page | None, *, project_code: str = "") -> dict:
    if page is None:
        return {}
    failed_step = getattr(page, "_ai_failed_step_context", None)
    if not isinstance(failed_step, dict):
        failed_step = getattr(page, "_ai_current_step_context", None)
    if not isinstance(failed_step, dict):
        return {}
    return normalize_failure_context({"failed_step": failed_step, "project_code": project_code})


def render_meta_text(
    *,
    nodeid: str,
    captured_at: str,
    current_url: str,
    page_title: str,
    screenshot_path: Path,
    html_path: Path,
    video_path: Path | None = None,
    suggestion_path: Path | None = None,
) -> str:
    lines = [
        f"NodeID: {nodeid}",
        f"CapturedAt: {captured_at}",
        f"URL: {current_url}",
        f"Title: {page_title}",
        f"Screenshot: {screenshot_path}",
        f"HTML: {html_path}",
    ]
    if video_path is not None:
        lines.append(f"Video: {video_path}")
    if suggestion_path is not None:
        lines.append(f"Suggestion: {suggestion_path}")
    return "\n".join(lines) + "\n"


def run_failure_analysis(payload: dict) -> dict:
    from analyze import FailureAnalysisAgent

    agent = FailureAnalysisAgent()
    return agent.analyze(payload)


def resolve_page_name_from_request(request) -> str:
    node = getattr(request, "node", request)
    test_case = extract_test_case_from_node(node)
    if not isinstance(test_case, dict):
        return ""
    execution = test_case.get("execution", {})
    if not isinstance(execution, dict):
        return ""
    return str(execution.get("page", "")).strip()


def resolve_case_id_from_request(request) -> str:
    node = getattr(request, "node", request)
    test_case = extract_test_case_from_node(node)
    if not isinstance(test_case, dict):
        return ""
    return str(test_case.get("id", "")).strip()


def build_execution_record(
    *,
    request,
    case_dir: Path,
    status: str,
    started_at: str,
    finished_at: str,
    duration_seconds: float,
    runner_exit_code: int | None,
    phase: str = "call",
) -> dict:
    node = getattr(request, "node", request)
    test_case = extract_test_case_from_node(node)
    execution = test_case.get("execution", {}) if isinstance(test_case, dict) else {}
    requirement = test_case.get("requirement", []) if isinstance(test_case, dict) else []
    if isinstance(requirement, str):
        requirement = [requirement]
    steps = execution.get("steps", []) if isinstance(execution, dict) else []
    evidence_paths = {
        "meta": case_dir / "meta.txt",
        "analysis": case_dir / "analysis.txt",
        "screenshot": case_dir / "failed.png",
        "html": case_dir / "page.html",
        "suggestion": case_dir / "suggestion.json",
        "self_healing_result": case_dir / "self_healing_result.json",
    }
    video_path = find_recent_video_file(resolve_video_dir(), since_timestamp=0.0)
    artifact_categories = {
        "screenshots": 1 if evidence_paths["screenshot"].exists() else 0,
        "html_pages": 1 if evidence_paths["html"].exists() else 0,
        "meta_files": 1 if evidence_paths["meta"].exists() else 0,
        "analysis_files": 1 if evidence_paths["analysis"].exists() else 0,
        "suggestion_files": 1 if evidence_paths["suggestion"].exists() else 0,
        "execution_record_files": 1,
        "self_healing_result_files": 1 if evidence_paths["self_healing_result"].exists() else 0,
        "videos": 1 if video_path is not None and video_path.exists() else 0,
        "other_files": 0,
    }
    total_files = sum(artifact_categories.values())
    raw_record = {
        "version": "ExecutionRecordV1",
        "schema_version": "execution-record.v1",
        "run_id": f"{resolve_case_id_from_request(node) or sanitize_artifact_name(node.nodeid)}:{started_at}",
        "case_id": resolve_case_id_from_request(request),
        "project": resolve_project_code_from_request(request),
        "source": os.getenv("RUN_SOURCE", "manual").strip() or "manual",
        "mode": "generate_and_run",
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "step_summary": {
            "page": str(execution.get("page", "")).strip(),
            "requirement_count": len([item for item in requirement if str(item).strip()]),
            "total_steps": len(steps) if isinstance(steps, list) else 0,
            "action_types": sorted(
                {str(step.get("action", "")).strip() for step in steps if isinstance(step, dict) and str(step.get("action", "")).strip()}
            ),
        },
        "evidence_index": {
            "total_files": total_files,
            "artifact_categories": artifact_categories,
            "runner_exit_code": runner_exit_code,
            "execution_requested": True,
        },
        "duration_seconds": round(duration_seconds, 3),
        "artifact_dir": str(case_dir),
        "metadata": {
            "pytest_phase": str(phase or "call").strip() or "call",
        },
    }
    failure_context_source = getattr(node, "_failure_context", {})
    if isinstance(failure_context_source, dict) and not str(failure_context_source.get("project_code", "")).strip():
        failure_context_source = {
            **failure_context_source,
            "project_code": resolve_project_code_from_request(node),
        }
    failure_context = normalize_failure_context(failure_context_source)
    if failure_context.get("failed_step"):
        raw_record["metadata"]["failed_step"] = failure_context["failed_step"]
    if failure_context.get("element_impact"):
        raw_record["metadata"]["element_impact"] = failure_context["element_impact"]
    return _normalize_execution_record_payload(raw_record)


def write_execution_record(case_dir: Path, payload: dict) -> Path:
    path = case_dir / "execution_record.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _select_execution_report(item):
    rep_call = getattr(item, "rep_call", None)
    if rep_call is not None:
        return rep_call
    rep_setup = getattr(item, "rep_setup", None)
    if rep_setup is not None:
        return rep_setup
    return getattr(item, "rep_teardown", None)


def _report_status_and_exit_code(report) -> tuple[str, int | None]:
    if report is None:
        return "generated", None
    if bool(getattr(report, "failed", False)):
        return "failed", 1
    if bool(getattr(report, "skipped", False)):
        return "skipped", 0
    if bool(getattr(report, "passed", False)):
        return "passed", 0
    return "generated", None


def _manifest_path_entry(path: Path, *, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def build_evidence_manifest(
    *,
    case_dir: Path,
    execution_record_path: Path | None = None,
    video_path: Path | None = None,
) -> dict:
    known_paths = {
        "screenshots": [case_dir / "failed.png"],
        "html_pages": [case_dir / "page.html"],
        "meta_files": [case_dir / "meta.txt"],
        "analysis_files": [case_dir / "analysis.txt"],
        "suggestion_files": [case_dir / "suggestion.json"],
        "execution_record_files": [execution_record_path or (case_dir / "execution_record.json")],
        "self_healing_result_files": [case_dir / "self_healing_result.json"],
        "videos": [case_dir / "video.webm", case_dir / "failure.webm"],
    }
    if video_path is not None:
        known_paths["videos"].append(video_path)

    categories: dict[str, list[str]] = {}
    seen_resolved: set[Path] = set()
    for key, candidates in known_paths.items():
        existing_entries = []
        for candidate in candidates:
            if candidate is None:
                continue
            resolved = candidate.expanduser().resolve()
            if not resolved.exists() or resolved in seen_resolved:
                continue
            seen_resolved.add(resolved)
            existing_entries.append(_manifest_path_entry(resolved, root=case_dir))
        categories[key] = existing_entries

    excluded_names = {"evidence_manifest.json", "manifest.json"}
    other_files = []
    if case_dir.exists():
        for path in sorted(case_dir.iterdir()):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if path.name in excluded_names or resolved in seen_resolved:
                continue
            other_files.append(_manifest_path_entry(resolved, root=case_dir))
    categories["other_files"] = other_files

    total_files = sum(len(items) for items in categories.values())
    raw_manifest = {
        "version": "EvidenceManifestV1",
        "schema_version": "evidence-manifest.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "artifact_root": str(case_dir.resolve()),
        **categories,
        "total_files": total_files,
    }
    return _normalize_evidence_manifest_payload(raw_manifest)


def write_evidence_manifest(case_dir: Path, payload: dict) -> Path:
    path = case_dir / "evidence_manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_available_targets(page_name: str) -> list[str]:
    if not page_name:
        return []
    page_object_path = PAGE_OBJECTS_ROOT / f"{page_name}.page-object.yaml"
    if not page_object_path.exists():
        return []
    try:
        page_object = yaml.safe_load(page_object_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    elements = page_object.get("elements", {})
    if not isinstance(elements, dict):
        return []
    return [str(target).strip() for target in elements.keys() if str(target).strip()]


def build_self_healing_payload(
    *,
    page_name: str,
    failure_message: str,
    analysis_result: dict,
    available_targets: list[str],
) -> dict:
    return {
        "page": page_name,
        "failure_reason": failure_message,
        "failure_analysis": analysis_result if isinstance(analysis_result, dict) else {},
        "available_targets": available_targets,
    }


def run_self_healing_advisor(payload: dict) -> dict:
    from suggest import SelfHealingAdvisor

    agent = SelfHealingAdvisor()
    return agent.suggest(payload)


def is_self_healing_enabled() -> bool:
    return os.getenv("SELF_HEALING_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def get_self_healing_attempts() -> int:
    raw_value = os.getenv("SELF_HEALING_ATTEMPTS", "0").strip()
    try:
        return max(0, int(raw_value))
    except ValueError:
        return 0


def resolve_case_yaml_path(request) -> Path | None:
    env_case_path = os.getenv("TEST_CASE_PATH", "").strip()
    if env_case_path:
        return Path(env_case_path).expanduser().resolve()

    test_case = extract_test_case_from_node(request.node)
    if not isinstance(test_case, dict):
        return None
    case_id = str(test_case.get("id", "")).strip()
    if not case_id:
        return None
    assets_root = Path(__file__).resolve().parents[2] / "assets" / "test-cases"
    candidate_ids = [case_id]
    if callable(normalize_case_id):
        normalized_case_id = normalize_case_id(case_id)
        if normalized_case_id and normalized_case_id not in candidate_ids:
            candidate_ids.append(normalized_case_id)
    candidates: list[Path] = []
    for candidate_id in candidate_ids:
        candidates.append(assets_root / "ai-generated" / f"{candidate_id}.yaml")
        candidates.extend(sorted(assets_root.rglob(f"{candidate_id}.yaml")))
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def run_self_healing_cycle(*, artifact_dir: Path, case_path: Path, previous_attempts: int = 0) -> dict:
    from self_healing_orchestrator import SelfHealingOrchestrator

    orchestrator = SelfHealingOrchestrator()
    return orchestrator.run_from_artifacts(
        artifact_dir,
        case_path,
        previous_attempts=previous_attempts,
    )


def render_analysis_text(result: dict) -> str:
    evidence_used = result.get("evidence_used", [])
    if not isinstance(evidence_used, list):
        evidence_used = []
    source_evidence = result.get("source_evidence", [])
    if not isinstance(source_evidence, list):
        source_evidence = []
    failed_step = result.get("failed_step") if isinstance(result.get("failed_step"), dict) else {}
    element_impact = result.get("element_impact") if isinstance(result.get("element_impact"), dict) else {}
    return "\n".join(
        [
            f"Summary: {result.get('summary', '')}",
            f"Failure Category: {result.get('failure_category', '')}",
            f"Failure Source: {result.get('failure_source', '')}",
            f"Failure Source Reason: {result.get('failure_source_reason', '')}",
            f"Failure Source Confidence: {result.get('failure_source_confidence', '')}",
            f"Likely Cause: {result.get('likely_cause', '')}",
            f"Risk Level: {result.get('risk_level', '')}",
            f"Recommended Action: {result.get('recommended_action', '')}",
            f"Requires Manual Review: {result.get('requires_manual_review', False)}",
            f"Confidence: {result.get('confidence', '')}",
            f"Failed Step: {json.dumps(failed_step, ensure_ascii=False)}",
            f"Element Impact: {json.dumps(element_impact, ensure_ascii=False)}",
            f"Evidence Used: {', '.join(evidence_used)}",
            f"Source Evidence: {json.dumps(source_evidence, ensure_ascii=False)}",
            "",
            json.dumps(result, ensure_ascii=False, indent=2),
            "",
        ]
    )


def render_suggestion_text(result: dict) -> str:
    return "\n".join(
        [
            f"Summary: {result.get('summary', '')}",
            f"Advice Type: {result.get('advice_type', '')}",
            f"Target: {result.get('target', '')}",
            f"Suggestion: {result.get('suggestion', '')}",
            f"Confidence: {result.get('confidence', '')}",
            f"Fix Candidates: {', '.join(result.get('fix_candidates', []))}",
            "",
            json.dumps(result, ensure_ascii=False, indent=2),
            "",
        ]
    )


def parse_analysis_text(content: str) -> dict[str, str]:
    parsed = {
        "summary": "",
        "failure_category": "",
        "likely_cause": "",
        "risk_level": "",
        "recommended_action": "",
        "confidence": "",
    }
    key_map = {
        "Summary": "summary",
        "Failure Category": "failure_category",
        "Likely Cause": "likely_cause",
        "Risk Level": "risk_level",
        "Recommended Action": "recommended_action",
        "Confidence": "confidence",
    }
    for raw_line in content.splitlines():
        if ": " not in raw_line:
            continue
        prefix, value = raw_line.split(": ", 1)
        mapped_key = key_map.get(prefix.strip())
        if mapped_key:
            parsed[mapped_key] = value.strip()
    return parsed


def render_failure_overview(
    *,
    failure_message: str,
    analysis_result: dict,
    suggestion_result: dict,
    current_url: str,
    page_title: str,
    screenshot_path: Path,
    html_path: Path,
    analysis_path: Path,
    suggestion_path: Path,
    video_path: Path | None = None,
) -> str:
    lines = [
        "Failure Overview",
        "",
        f"Error: {failure_message or '-'}",
        f"URL: {current_url or '-'}",
        f"Title: {page_title or '-'}",
        "",
        "AI Failure Analysis:",
        f"- Summary: {analysis_result.get('summary', '-') if isinstance(analysis_result, dict) else '-'}",
        f"- Category: {analysis_result.get('failure_category', '-') if isinstance(analysis_result, dict) else '-'}",
        f"- Risk: {analysis_result.get('risk_level', '-') if isinstance(analysis_result, dict) else '-'}",
        f"- Likely Cause: {analysis_result.get('likely_cause', '-') if isinstance(analysis_result, dict) else '-'}",
        "",
        "Self-Healing Advice:",
        f"- Summary: {suggestion_result.get('summary', '-') if isinstance(suggestion_result, dict) else '-'}",
        f"- Advice Type: {suggestion_result.get('advice_type', '-') if isinstance(suggestion_result, dict) else '-'}",
        f"- Target: {suggestion_result.get('target', '-') if isinstance(suggestion_result, dict) else '-'}",
        f"- Confidence: {suggestion_result.get('confidence', '-') if isinstance(suggestion_result, dict) else '-'}",
        "",
        "Artifacts:",
        f"- Screenshot: {screenshot_path}",
        f"- HTML: {html_path}",
        f"- Analysis: {analysis_path}",
        f"- Suggestion: {suggestion_path}",
    ]
    if video_path is not None:
        lines.append(f"- Video: {video_path}")
    lines.append("")
    return "\n".join(lines)


def attach_allure_artifact(path: Path, *, name: str, attachment_type) -> bool:
    if allure is None or not path.exists():
        return False
    try:
        allure.attach.file(str(path), name=name, attachment_type=attachment_type)
        return True
    except Exception:
        return False


def attach_allure_text(content: str, *, name: str) -> bool:
    if allure is None or not content.strip():
        return False
    try:
        allure.attach(content, name=name, attachment_type=allure.attachment_type.TEXT)
        return True
    except Exception:
        return False


def find_recent_video_file(video_dir: Path, *, since_timestamp: float) -> Path | None:
    if not video_dir.exists():
        return None
    candidates = [
        path for path in video_dir.rglob("*.webm")
        if path.is_file() and path.stat().st_mtime >= since_timestamp
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def attach_allure_video_artifact(video_path: Path | None) -> bool:
    if video_path is None or allure is None or not video_path.exists():
        return False
    try:
        allure.attach.file(str(video_path), name="failure-video", attachment_type=allure.attachment_type.WEBM)
        return True
    except Exception:
        return False


def _normalize_requirement_metadata(requirement) -> dict[str, str]:
    if isinstance(requirement, dict):
        return {str(key): str(value).strip() for key, value in requirement.items() if str(value).strip()}
    lines: list[str] = []
    if isinstance(requirement, str):
        lines = requirement.splitlines()
    elif isinstance(requirement, list):
        for item in requirement:
            lines.extend(str(item or "").splitlines())
    output: dict[str, str] = {}
    mapping = {
        "测试点ID": "intent_id",
        "测试点标题": "title",
        "测试意图": "title",
        "测试类型": "type",
        "前置条件": "precondition",
        "来源资产": "source_asset_title",
        "来源资产ID": "source_asset_id",
    }
    for raw_line in lines:
        if "：" in raw_line:
            key, value = raw_line.split("：", 1)
        elif ": " in raw_line:
            key, value = raw_line.split(": ", 1)
        else:
            continue
        normalized_key = mapping.get(key.strip())
        if normalized_key and str(value).strip() and normalized_key not in output:
            output[normalized_key] = str(value).strip()
    return output


def extract_allure_test_metadata(request) -> dict[str, object]:
    test_case = extract_test_case_from_node(request.node)
    if not isinstance(test_case, dict):
        return {}

    execution = test_case.get("execution", {})
    title = str(test_case.get("title", "")).strip()
    case_id = str(test_case.get("id", "")).strip()
    project = str(test_case.get("project") or test_case.get("project_code") or os.getenv("TEST_PROJECT", "")).strip()
    priority = str(test_case.get("priority", "")).strip()
    requirement = _normalize_requirement_metadata(test_case.get("requirement"))
    page_name = str(execution.get("page", "")).strip()
    story_name = str(requirement.get("title") or title or case_id or request.node.name).strip()
    feature_name = _resolve_allure_feature_name(
        page_name=page_name,
        title=title,
        explicit=str(
            test_case.get("business_domain")
            or test_case.get("feature")
            or requirement.get("business_domain")
            or requirement.get("feature")
            or ""
        ).strip(),
    )
    tags = test_case.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    selected_intents = execution.get("selected_intent_ids")
    if not isinstance(selected_intents, list):
        selected_intents = []

    metadata: dict[str, object] = {
        "title": title or case_id or request.node.name,
        "case_id": case_id,
        "page": page_name,
        "feature": feature_name,
        "story": story_name,
        "tags": [str(tag).strip() for tag in tags if str(tag).strip()],
        "base_url": str(execution.get("page_url") or os.getenv("BASE_URL", "http://localhost:5173/login#/login")).strip(),
        "run_mode": os.getenv("RUN_MODE", "unspecified").strip() or "unspecified",
        "run_source": os.getenv("RUN_SOURCE", "manual").strip() or "manual",
    }
    optional_metadata = {
        "project": project,
        "priority": priority,
        "intent_type": str(requirement.get("type", "")).strip(),
        "intent_id": str(requirement.get("intent_id", "")).strip(),
        "source_asset_id": str(requirement.get("source_asset_id", "")).strip(),
        "source_asset_title": str(
            requirement.get("source_asset_title")
            or test_case.get("source_asset_title")
            or test_case.get("asset_title")
            or ""
        ).strip(),
        "case_version": str(test_case.get("case_version") or test_case.get("version") or "").strip(),
    }
    for key, value in optional_metadata.items():
        if value:
            metadata[key] = value
    selected_intent_values = [str(item).strip() for item in selected_intents if str(item).strip()]
    if selected_intent_values:
        metadata["selected_intent_ids"] = selected_intent_values
    return metadata


def apply_allure_test_metadata(metadata: dict[str, object]) -> bool:
    if allure is None or not metadata:
        return False
    try:
        title = str(metadata.get("title", "")).strip()
        case_title = str(metadata.get("case_title", "") or title).strip()
        case_id = str(metadata.get("case_id", "")).strip()
        project = str(metadata.get("project", "")).strip()
        page_name = str(metadata.get("page", "")).strip()
        feature_name = str(metadata.get("feature", "") or page_name).strip()
        story_name = str(metadata.get("story", "") or case_title or case_id).strip()
        priority = str(metadata.get("priority", "")).strip()
        intent_type = str(metadata.get("intent_type", "")).strip()
        intent_id = str(metadata.get("intent_id", "")).strip()
        source_asset_id = str(metadata.get("source_asset_id", "")).strip()
        source_asset_title = str(metadata.get("source_asset_title", "")).strip()
        case_version = str(metadata.get("case_version", "")).strip()
        base_url = str(metadata.get("base_url", "")).strip()
        run_mode = str(metadata.get("run_mode", "")).strip()
        run_source = str(metadata.get("run_source", "")).strip()
        tags = metadata.get("tags", [])
        selected_intent_ids = metadata.get("selected_intent_ids", [])

        if title:
            allure.dynamic.title(title)
        if project:
            allure.dynamic.epic(_project_display_name(project))
            allure.dynamic.label("project", project)
        if feature_name:
            allure.dynamic.feature(feature_name)
        if page_name:
            allure.dynamic.label("page", page_name)
        if story_name:
            allure.dynamic.story(story_name)
        _apply_allure_suite_labels(
            project=project,
            feature_name=feature_name,
            story_name=story_name,
        )
        if case_id:
            allure.dynamic.label("case_id", case_id)
        if case_title:
            allure.dynamic.label("case_title", case_title)
        if case_version:
            allure.dynamic.label("case_version", case_version)
        if priority:
            allure.dynamic.label("priority", priority)
            _apply_allure_severity(priority)
        if intent_type:
            allure.dynamic.label("intent_type", intent_type)
        if intent_id:
            allure.dynamic.label("intent_id", intent_id)
        if source_asset_id:
            allure.dynamic.label("source_asset_id", source_asset_id)
        if source_asset_title:
            allure.dynamic.label("source_asset", source_asset_title)
        if base_url:
            allure.dynamic.label("base_url", base_url)
        if run_mode:
            allure.dynamic.label("run_mode", run_mode)
        if run_source:
            allure.dynamic.label("run_source", run_source)
        if isinstance(selected_intent_ids, list):
            for intent in selected_intent_ids:
                if str(intent).strip():
                    allure.dynamic.label("selected_intent_id", str(intent).strip())
        if isinstance(tags, list):
            for tag in tags:
                if str(tag).strip():
                    allure.dynamic.tag(str(tag).strip())
        _apply_allure_safe_parameters(metadata)
        return True
    except Exception:
        return False


def _resolve_allure_feature_name(*, page_name: str, title: str = "", explicit: str = "") -> str:
    if explicit:
        return explicit
    normalized_page = str(page_name or "").strip().lower()
    if normalized_page in {"login", "auth", "authentication"}:
        return "登录与身份验证"
    return str(page_name or title or "").strip()


def _project_display_name(project: str) -> str:
    normalized = str(project or "").strip()
    display_names = {
        "mall": "商城后台 (mall)",
    }
    return display_names.get(normalized, normalized)


def _apply_allure_suite_labels(*, project: str, feature_name: str, story_name: str) -> None:
    dynamic = getattr(allure, "dynamic", None) if allure is not None else None
    if dynamic is None:
        return
    suite_calls = [
        ("parent_suite", _project_display_name(project) if project else ""),
        ("suite", feature_name),
        ("sub_suite", story_name),
    ]
    for method_name, value in suite_calls:
        if not value:
            continue
        method = getattr(dynamic, method_name, None)
        if callable(method):
            method(value)


def _apply_allure_safe_parameters(metadata: dict[str, object]) -> None:
    dynamic = getattr(allure, "dynamic", None) if allure is not None else None
    parameter = getattr(dynamic, "parameter", None)
    if not callable(parameter):
        return
    safe_value = str(metadata.get("case_id") or metadata.get("title") or "case").strip()
    if not safe_value:
        return
    hidden_mode = getattr(getattr(allure, "parameter_mode", None), "HIDDEN", None)
    for raw_name in ("test_case", "case_param"):
        try:
            parameter(raw_name, safe_value, excluded=True, mode=hidden_mode)
        except TypeError:
            try:
                parameter(raw_name, safe_value)
            except Exception:
                pass
        except Exception:
            pass
    for display_name, key in (
        ("用例编码", "case_id"),
        ("用例标题", "title"),
        ("页面", "page"),
        ("优先级", "priority"),
        ("来源资产", "source_asset_title"),
    ):
        value = str(metadata.get(key, "")).strip()
        if not value:
            continue
        try:
            parameter(display_name, value)
        except Exception:
            pass


def _apply_allure_severity(priority: str) -> None:
    if allure is None:
        return
    normalized = str(priority or "").strip().upper()
    severity = {
        "P0": allure.severity_level.BLOCKER,
        "P1": allure.severity_level.CRITICAL,
        "P2": allure.severity_level.NORMAL,
        "P3": allure.severity_level.MINOR,
    }.get(normalized)
    if severity is not None:
        allure.dynamic.severity(severity)


def attach_allure_failure_artifacts(case_dir: Path) -> dict[str, bool]:
    screenshot_path = case_dir / "failed.png"
    html_path = case_dir / "page.html"
    meta_path = case_dir / "meta.txt"
    analysis_path = case_dir / "analysis.txt"
    suggestion_path = case_dir / "suggestion.json"
    healing_result_path = case_dir / "self_healing_result.json"
    attached = {
        "screenshot": False,
        "page_html": False,
        "meta": False,
        "meta_text": False,
        "analysis": False,
        "analysis_text": False,
        "suggestion": False,
        "suggestion_text": False,
        "healing_result": False,
        "healing_result_text": False,
    }
    if allure is None:
        return attached

    attached["screenshot"] = attach_allure_artifact(
        screenshot_path,
        name="failure-screenshot",
        attachment_type=allure.attachment_type.PNG,
    )
    attached["page_html"] = attach_allure_artifact(
        html_path,
        name="page-html",
        attachment_type=allure.attachment_type.HTML,
    )
    attached["meta"] = attach_allure_artifact(
        meta_path,
        name="page-meta",
        attachment_type=allure.attachment_type.TEXT,
    )
    if meta_path.exists():
        attached["meta_text"] = attach_allure_text(
            meta_path.read_text(encoding="utf-8"),
            name="failure-context",
        )
    attached["analysis"] = attach_allure_artifact(
        analysis_path,
        name="failure-analysis",
        attachment_type=allure.attachment_type.TEXT,
    )
    if analysis_path.exists():
        attached["analysis_text"] = attach_allure_text(
            analysis_path.read_text(encoding="utf-8"),
            name="ai-failure-analysis",
        )
    attached["suggestion"] = attach_allure_artifact(
        suggestion_path,
        name="self-healing-suggestion",
        attachment_type=allure.attachment_type.JSON,
    )
    if suggestion_path.exists():
        attached["suggestion_text"] = attach_allure_text(
            suggestion_path.read_text(encoding="utf-8"),
            name="self-healing-advice",
        )
    attached["healing_result"] = attach_allure_artifact(
        healing_result_path,
        name="self-healing-result",
        attachment_type=allure.attachment_type.JSON,
    )
    if healing_result_path.exists():
        attached["healing_result_text"] = attach_allure_text(
            healing_result_path.read_text(encoding="utf-8"),
            name="self-healing-result-summary",
        )
    return attached


ARTIFACTS_DIR = resolve_artifacts_dir()

from check_base_url import check_base_url_reachable  # noqa: E402
from runner.url_utils import normalize_url_for_runner  # noqa: E402


def _extract_ai_case_preflight_url() -> str:
    case_path = os.getenv("TEST_CASE_PATH", "").strip()
    if not case_path:
        return ""
    path = Path(case_path).expanduser()
    if not path.exists() or not path.is_file():
        return ""
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    execution = payload.get("execution")
    if not isinstance(execution, dict):
        return ""
    page_url = str(execution.get("page_url") or "").strip()
    if page_url:
        return page_url
    steps = execution.get("steps")
    if not isinstance(steps, list):
        return ""
    for step in steps:
        if not isinstance(step, dict):
            continue
        if str(step.get("action") or "").strip().lower() != "goto":
            continue
        for key in ("url", "value", "target_url"):
            candidate = str(step.get(key) or "").strip()
            if candidate:
                return candidate
    return ""


def resolve_e2e_preflight_url(default_base_url: str) -> str:
    ai_case_url = _extract_ai_case_preflight_url()
    raw_url = ai_case_url or default_base_url
    return normalize_url_for_runner(raw_url, base_url=default_base_url)


@pytest.fixture(scope="session")
def base_url() -> str:
    value = os.getenv("BASE_URL", "").strip()
    if not value:
        raise RuntimeError("BASE_URL must be set for runner tests")
    return value


@pytest.fixture(scope="session")
def test_username() -> str:
    value = os.getenv("TEST_USERNAME", "").strip()
    if not value:
        raise RuntimeError("TEST_USERNAME must be set for runner tests")
    return value


@pytest.fixture(scope="session")
def test_password() -> str:
    value = os.getenv("TEST_PASSWORD", "").strip()
    if not value:
        raise RuntimeError("TEST_PASSWORD must be set for runner tests")
    return value


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """
    Docker 默认 /dev/shm 通常只有 64MB，Chromium 容易在 page.goto 时崩溃。
    这些参数只影响浏览器启动稳定性，不改变用例业务行为。
    """
    existing_args = list(browser_type_launch_args.get("args", []))
    docker_safe_args = [
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-gpu",
    ]
    return {
        **browser_type_launch_args,
        "args": [*existing_args, *[arg for arg in docker_safe_args if arg not in existing_args]],
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """
    给 Python 版补齐更接近 TS 版的运行能力：
    - 可选录制视频
    - 固定视口
    - 忽略 HTTPS 错误（可选）
    """
    context_args = {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
        "ignore_https_errors": True,
    }
    if env_flag("WORKBENCH_RECORD_VIDEO", default=True):
        video_dir = resolve_video_dir()
        context_args.update(
            {
                "record_video_dir": str(video_dir),
                "record_video_size": {"width": 1440, "height": 900},
            }
        )
    return context_args


@pytest.fixture(scope="session", autouse=True)
def ensure_e2e_base_url_reachable(request, base_url: str):
    if not any(item.get_closest_marker("e2e") for item in request.session.items):
        return

    preflight_url = resolve_e2e_preflight_url(base_url)
    try:
        check_base_url_reachable(preflight_url)
    except RuntimeError as exc:
        parsed = urlsplit(preflight_url)
        host = parsed.hostname or "unknown-host"
        port = parsed.port or ("443" if parsed.scheme == "https" else "80")
        source_hint = "TEST_CASE_PATH execution.page_url" if preflight_url != base_url else "BASE_URL"
        raise pytest.UsageError(
            f"E2E preflight failed: {exc}\n"
            f"Hint: check whether the target app is running on {host}:{port}; "
            f"preflight source={source_hint}. For Docker runs, set RUNNER_URL_REWRITE_MAP "
            "when the YAML target uses localhost on the host machine."
        ) from exc


@pytest.fixture(autouse=True)
def clear_auth_state(request):
    """
    每条用例前：
    - 清 cookie
    - 打开基础页面
    - 清 localStorage/sessionStorage
    """
    if request.node.get_closest_marker("e2e") is None:
        return

    page: Page = request.getfixturevalue("page")
    context = request.getfixturevalue("context")
    base_url: str = request.getfixturevalue("base_url")

    context.clear_cookies()
    if os.getenv("RUN_MODE", "").strip().lower() == "ai" and os.getenv("TEST_CASE_PATH", "").strip():
        page.goto("about:blank")
        return
    page.goto(base_url, wait_until="domcontentloaded", timeout=15000)
    page.evaluate(
        """
        () => {
          localStorage.clear();
          sessionStorage.clear();
        }
        """
    )


@pytest.fixture(autouse=True)
def apply_allure_metadata(request):
    apply_allure_test_metadata(extract_allure_test_metadata(request))
    yield


@pytest.fixture(autouse=True)
def capture_failure_artifacts(request):
    """
    用例失败时自动保存：
    - screenshot
    - page html
    - 当前 url
    """
    if request.node.get_closest_marker("e2e") is None:
        yield
        return

    request.node._failure_capture_started_at = datetime.now(UTC).timestamp()
    request.node._execution_record_started_at = datetime.now(UTC).isoformat()
    request.node._execution_case_dir = ARTIFACTS_DIR / sanitize_artifact_name(request.node.nodeid)
    request.node._execution_case_dir.mkdir(parents=True, exist_ok=True)
    page: Page = request.getfixturevalue("page")
    yield

    # 仅在测试实际执行阶段判断结果
    rep = getattr(request.node, "rep_call", None)
    if rep and rep.failed:
        case_dir = getattr(request.node, "_execution_case_dir")

        screenshot_path = case_dir / "failed.png"
        html_path = case_dir / "page.html"
        meta_path = case_dir / "meta.txt"
        analysis_path = case_dir / "analysis.txt"
        suggestion_path = case_dir / "suggestion.json"
        failure_message = extract_failure_message(rep)
        page_html = ""
        captured_at = datetime.now(UTC).isoformat()
        page_name = resolve_page_name_from_request(request)
        analysis_result = {}
        failure_context = extract_failure_context_from_page(
            page,
            project_code=resolve_project_code_from_request(request),
        )
        request.node._failure_context = failure_context

        try:
            page.screenshot(path=str(screenshot_path), full_page=True, timeout=3000)
        except Exception as e:
            print(f"[artifact] screenshot failed: {e}")

        try:
            page_html = page.content()
            html_path.write_text(page_html, encoding="utf-8")
        except Exception as e:
            print(f"[artifact] html dump failed: {e}")

        try:
            page_title = page.title()
        except Exception as e:
            page_title = f"<title unavailable: {e}>"

        try:
            meta_path.write_text(
                render_meta_text(
                    nodeid=request.node.nodeid,
                    captured_at=captured_at,
                    current_url=page.url,
                    page_title=page_title,
                    screenshot_path=screenshot_path,
                    html_path=html_path,
                    suggestion_path=suggestion_path if suggestion_path.exists() else None,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"[artifact] meta dump failed: {e}")

        try:
            analysis_result = run_failure_analysis(
                build_failure_analysis_payload(
                    error_message=failure_message,
                    page_html=page_html,
                    current_url=page.url,
                    page_title=page_title,
                    screenshot_path=screenshot_path,
                    html_path=html_path,
                    meta_path=meta_path,
                    failure_context=failure_context,
                )
            )
            if failure_context.get("failed_step"):
                analysis_result["failed_step"] = failure_context["failed_step"]
            if failure_context.get("element_impact"):
                analysis_result["element_impact"] = failure_context["element_impact"]
            analysis_path.write_text(render_analysis_text(analysis_result), encoding="utf-8")
        except Exception as e:
            print(f"[artifact] analysis generation failed: {e}")

        try:
            suggestion_result = run_self_healing_advisor(
                build_self_healing_payload(
                    page_name=page_name,
                    failure_message=failure_message,
                    analysis_result=analysis_result,
                    available_targets=load_available_targets(page_name),
                )
            )
            suggestion_path.write_text(json.dumps(suggestion_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as e:
            print(f"[artifact] self-healing suggestion failed: {e}")

        if is_self_healing_enabled():
            try:
                case_yaml_path = resolve_case_yaml_path(request)
                if case_yaml_path is not None:
                    healing_result = run_self_healing_cycle(
                        artifact_dir=case_dir,
                        case_path=case_yaml_path,
                        previous_attempts=get_self_healing_attempts(),
                    )
                    (case_dir / "self_healing_result.json").write_text(
                        json.dumps(healing_result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                else:
                    print("[artifact] self-healing skipped: unable to resolve case YAML path")
            except Exception as e:
                print(f"[artifact] self-healing cycle failed: {e}")

        try:
            meta_path.write_text(
                render_meta_text(
                    nodeid=request.node.nodeid,
                    captured_at=captured_at,
                    current_url=page.url,
                    page_title=page_title,
                    screenshot_path=screenshot_path,
                    html_path=html_path,
                    suggestion_path=suggestion_path if suggestion_path.exists() else None,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

        request.node._failure_case_dir = case_dir
        request.node._failure_meta_path = meta_path
        attach_allure_failure_artifacts(case_dir)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """
    让 fixture 里可以拿到测试结果状态：
    request.node.rep_call.failed
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item, nextitem):
    yield
    rep = _select_execution_report(item)
    case_dir = getattr(item, "_execution_case_dir", None)
    started_at_iso = getattr(item, "_execution_record_started_at", "")
    started_at_timestamp = getattr(item, "_failure_capture_started_at", None)

    if rep is not None and case_dir is not None:
        finished_at = datetime.now(UTC).isoformat()
        duration_seconds = 0.0
        if started_at_timestamp is not None:
            duration_seconds = max(0.0, datetime.now(UTC).timestamp() - float(started_at_timestamp))
        status, runner_exit_code = _report_status_and_exit_code(rep)
        execution_record_path = write_execution_record(
            case_dir,
            build_execution_record(
                request=item,
                case_dir=case_dir,
                status=status,
                started_at=started_at_iso or finished_at,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
                runner_exit_code=runner_exit_code,
                phase=str(getattr(rep, "when", "call") or "call"),
            ),
        )
        write_evidence_manifest(
            case_dir,
            build_evidence_manifest(
                case_dir=case_dir,
                execution_record_path=execution_record_path,
            ),
        )
        if rep.failed and allure is not None:
            attach_allure_artifact(
                execution_record_path,
                name="execution-record",
                attachment_type=allure.attachment_type.JSON,
            )

    case_dir = getattr(item, "_failure_case_dir", None)
    meta_path = getattr(item, "_failure_meta_path", None)
    started_at = getattr(item, "_failure_capture_started_at", None)

    if not rep or not rep.failed or case_dir is None or meta_path is None or started_at is None:
        return

    video_path = find_recent_video_file(resolve_video_dir(), since_timestamp=float(started_at))
    analysis_path = case_dir / "analysis.txt"
    suggestion_path = case_dir / "suggestion.json"
    analysis_result = {}
    suggestion_result = {}

    try:
        if analysis_path.exists():
            analysis_result = parse_analysis_text(analysis_path.read_text(encoding="utf-8"))
    except Exception:
        analysis_result = {}

    try:
        if suggestion_path.exists():
            suggestion_result = json.loads(suggestion_path.read_text(encoding="utf-8"))
    except Exception:
        suggestion_result = {}

    try:
        current_url = ""
        page_title = ""
        meta_lines = meta_path.read_text(encoding="utf-8").splitlines()
        for raw_line in meta_lines:
            if raw_line.startswith("URL: "):
                current_url = raw_line.replace("URL: ", "", 1).strip()
            elif raw_line.startswith("Title: "):
                page_title = raw_line.replace("Title: ", "", 1).strip()
        attach_allure_text(
            render_failure_overview(
                failure_message=extract_failure_message(rep),
                analysis_result=analysis_result,
                suggestion_result=suggestion_result,
                current_url=current_url,
                page_title=page_title,
                screenshot_path=case_dir / "failed.png",
                html_path=case_dir / "page.html",
                analysis_path=analysis_path,
                suggestion_path=suggestion_path,
                video_path=video_path,
            ),
            name="failure-overview",
        )
    except Exception:
        pass

    if video_path is None:
        return

    try:
        current_meta = meta_path.read_text(encoding="utf-8")
        if f"Video: {video_path}" not in current_meta:
            meta_path.write_text(current_meta + f"Video: {video_path}\n", encoding="utf-8")
    except Exception:
        pass

    attach_allure_video_artifact(video_path)
    write_evidence_manifest(
        case_dir,
        build_evidence_manifest(
            case_dir=case_dir,
            execution_record_path=case_dir / "execution_record.json",
            video_path=video_path,
        ),
    )
