import os
import sys
import json
from pathlib import Path
from datetime_compat import UTC
from datetime import datetime
from urllib.parse import urlsplit

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
APPS_ROOT = Path(__file__).resolve().parents[2] / "apps"
if str(APPS_ROOT) not in sys.path:
    sys.path.insert(0, str(APPS_ROOT))
FAILURE_ANALYSIS_AGENT_ROOT = Path(__file__).resolve().parents[2] / "agents" / "failure-analysis-agent"
SELF_HEALING_ADVISOR_AGENT_ROOT = Path(__file__).resolve().parents[2] / "agents" / "self-healing-advisor-agent"
PAGE_OBJECTS_ROOT = Path(__file__).resolve().parents[2] / "assets" / "page-objects" / "web"
RUNNER_TOOLS_ROOT = Path(__file__).resolve().parent / "tools"

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
) -> dict:
    return {
        "error": error_message,
        "current_url": current_url,
        "page_title": page_title,
        "page_html": page_html,
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
    if str(FAILURE_ANALYSIS_AGENT_ROOT) not in sys.path:
        sys.path.insert(0, str(FAILURE_ANALYSIS_AGENT_ROOT))

    from analyze import FailureAnalysisAgent

    agent = FailureAnalysisAgent()
    return agent.analyze(payload)


def resolve_page_name_from_request(request) -> str:
    node = getattr(request, "node", request)
    test_case = getattr(getattr(node, "callspec", None), "params", {}).get("test_case")
    if not isinstance(test_case, dict):
        return ""
    execution = test_case.get("execution", {})
    if not isinstance(execution, dict):
        return ""
    return str(execution.get("page", "")).strip()


def resolve_case_id_from_request(request) -> str:
    node = getattr(request, "node", request)
    test_case = getattr(getattr(node, "callspec", None), "params", {}).get("test_case")
    if not isinstance(test_case, dict):
        return ""
    raw = str(test_case.get("id", "")).strip()
    if callable(normalize_case_id):
        return normalize_case_id(raw)
    return raw


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
    test_case = getattr(getattr(node, "callspec", None), "params", {}).get("test_case")
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
        "project": os.getenv("TEST_PROJECT", "default"),
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
    if str(SELF_HEALING_ADVISOR_AGENT_ROOT) not in sys.path:
        sys.path.insert(0, str(SELF_HEALING_ADVISOR_AGENT_ROOT))

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

    test_case = getattr(getattr(request.node, "callspec", None), "params", {}).get("test_case")
    if not isinstance(test_case, dict):
        return None
    case_id = str(test_case.get("id", "")).strip()
    if not case_id:
        return None
    normalized_case_id = normalize_case_id(case_id) if callable(normalize_case_id) else case_id
    assets_root = Path(__file__).resolve().parents[2] / "assets" / "test-cases"
    for candidate in [assets_root / "ai-generated" / f"{normalized_case_id}.yaml", *sorted(assets_root.rglob(f"{normalized_case_id}.yaml"))]:
        if candidate.exists():
            return candidate.resolve()
    return None


def run_self_healing_cycle(*, artifact_dir: Path, case_path: Path, previous_attempts: int = 0) -> dict:
    if str(SELF_HEALING_ADVISOR_AGENT_ROOT) not in sys.path:
        sys.path.insert(0, str(SELF_HEALING_ADVISOR_AGENT_ROOT))

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


def extract_allure_test_metadata(request) -> dict[str, object]:
    test_case = getattr(getattr(request.node, "callspec", None), "params", {}).get("test_case")
    if not isinstance(test_case, dict):
        return {}

    execution = test_case.get("execution", {})
    title = str(test_case.get("title", "")).strip()
    case_id = str(test_case.get("id", "")).strip()
    normalized_case_id = normalize_case_id(case_id) if callable(normalize_case_id) and case_id else case_id
    page_name = str(execution.get("page", "")).strip()
    tags = test_case.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    metadata: dict[str, object] = {
        "title": normalized_case_id or title or request.node.name,
        "case_title": title,
        "case_id": normalized_case_id,
        "page": page_name,
        "tags": [str(tag).strip() for tag in tags if str(tag).strip()],
        "base_url": os.getenv("BASE_URL", "http://localhost:5173/login#/login"),
        "run_mode": os.getenv("RUN_MODE", "unspecified").strip() or "unspecified",
        "run_source": os.getenv("RUN_SOURCE", "manual").strip() or "manual",
    }
    return metadata


def apply_allure_test_metadata(metadata: dict[str, object]) -> bool:
    if allure is None or not metadata:
        return False
    try:
        title = str(metadata.get("title", "")).strip()
        case_title = str(metadata.get("case_title", "")).strip()
        case_id = str(metadata.get("case_id", "")).strip()
        page_name = str(metadata.get("page", "")).strip()
        base_url = str(metadata.get("base_url", "")).strip()
        run_mode = str(metadata.get("run_mode", "")).strip()
        run_source = str(metadata.get("run_source", "")).strip()
        tags = metadata.get("tags", [])

        if title:
            allure.dynamic.title(title)
        if page_name:
            allure.dynamic.feature(page_name)
        if case_id:
            allure.dynamic.story(case_id)
            allure.dynamic.label("case_id", case_id)
        if case_title:
            allure.dynamic.label("case_title", case_title)
        if base_url:
            allure.dynamic.label("base_url", base_url)
        if run_mode:
            allure.dynamic.label("run_mode", run_mode)
        if run_source:
            allure.dynamic.label("run_source", run_source)
        if isinstance(tags, list):
            for tag in tags:
                if str(tag).strip():
                    allure.dynamic.tag(str(tag).strip())
        return True
    except Exception:
        return False


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

if str(RUNNER_TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNNER_TOOLS_ROOT))

from check_base_url import check_base_url_reachable  # noqa: E402


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.getenv("BASE_URL", "http://localhost:5173/login#/login")


@pytest.fixture(scope="session")
def test_username() -> str:
    return os.getenv("TEST_USERNAME", "admin")


@pytest.fixture(scope="session")
def test_password() -> str:
    return os.getenv("TEST_PASSWORD", "macro123")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """
    给 Python 版补齐更接近 TS 版的运行能力：
    - 录制视频
    - 固定视口
    - 忽略 HTTPS 错误（可选）
    """
    video_dir = resolve_video_dir()

    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
        "ignore_https_errors": True,
        "record_video_dir": str(video_dir),
        "record_video_size": {"width": 1440, "height": 900},
    }


@pytest.fixture(scope="session", autouse=True)
def ensure_e2e_base_url_reachable(request, base_url: str):
    if not any(item.get_closest_marker("e2e") for item in request.session.items):
        return

    try:
        check_base_url_reachable(base_url)
    except RuntimeError as exc:
        parsed = urlsplit(base_url)
        host = parsed.hostname or "unknown-host"
        port = parsed.port or ("443" if parsed.scheme == "https" else "80")
        raise pytest.UsageError(
            f"E2E preflight failed: {exc}\n"
            f"Hint: check whether the target app is running on {host}:{port} or override BASE_URL."
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

        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
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
                )
            )
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
