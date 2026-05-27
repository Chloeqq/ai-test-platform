from __future__ import annotations

import ast
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shared_backend.case_ids import (
    DEFAULT_CASE_ID,
    build_case_id,
    build_case_metadata,
    infer_client_code,
    infer_case_type,
    infer_module_code,
    infer_page_code,
    infer_source_code,
    match_case_id,
    normalize_case_id,
    slugify_case_part,
    split_run_id,
)


ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = ROOT / "assets" / "test-cases"
AI_GENERATED_ROOT = ASSETS_ROOT / "ai-generated"
REPORTS_ROOT = ROOT / "reports" / "executions"
WEB_UI_STATE = ROOT / "web-ui" / "state"
TEST_POINT_STATE_ROOT = WEB_UI_STATE / "test-points" / "default"
DB_PATH = WEB_UI_STATE / "web-ui.db"
RUNS_ROOT = WEB_UI_STATE / "runs"
ALLURE_ROOTS = [
    ROOT / "runners" / "web-playwright-python" / "allure-results",
    ROOT / "runners" / "web-playwright-python" / "allure-report",
    ROOT / "runners" / "web-playwright-python" / "allure-report-snapshots",
]

TEXT_EXTENSIONS = {
    ".json",
    ".md",
    ".txt",
    ".html",
    ".htm",
    ".js",
    ".xml",
    ".csv",
    ".log",
    ".properties",
}


def _strict_case_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = normalize_case_id(text, fallback="").strip()
    if not normalized or normalized == DEFAULT_CASE_ID:
        return ""
    return normalized if match_case_id(normalized) else ""


def _extract_case_id_label(labels: Any) -> str:
    items = labels if isinstance(labels, list) else []
    for label in items:
        if not isinstance(label, dict):
            continue
        if str(label.get("name", "")).strip() == "case_id":
            return _strict_case_id(label.get("value"))
    return ""


def _extract_case_id_from_test_case_value(value: Any) -> str:
    payload = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        try:
            payload = ast.literal_eval(text)
        except Exception:
            payload = value
    if isinstance(payload, dict):
        return _strict_case_id(payload.get("id"))
    if isinstance(payload, str):
        text = payload.strip()
        markers = ["'id': '", '"id": "']
        for marker in markers:
            if marker not in text:
                continue
            suffix = text.split(marker, 1)[1]
            candidate = suffix.split("'" if marker.startswith("'") else '"', 1)[0].strip()
            if candidate:
                return _strict_case_id(candidate)
    return ""


def _extract_case_id_from_parameters(parameters: Any) -> str:
    items = parameters if isinstance(parameters, list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if name == "case_id":
            candidate = _strict_case_id(item.get("value"))
            if candidate:
                return candidate
        if name == "test_case":
            candidate = _extract_case_id_from_test_case_value(item.get("value"))
            if candidate:
                return candidate
    return ""


def _derive_allure_case_id(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""
    direct_value = _strict_case_id(payload.get("case_id"))
    if direct_value:
        return direct_value
    label_value = _extract_case_id_label(payload.get("labels"))
    if label_value:
        return label_value
    parameter_value = _extract_case_id_from_parameters(payload.get("parameters"))
    if parameter_value:
        return parameter_value
    return ""


def _ensure_allure_case_id_label(payload: dict[str, Any], case_id: str) -> None:
    labels = payload.get("labels")
    if not isinstance(labels, list):
        payload["labels"] = [{"name": "case_id", "value": case_id}]
        return
    for label in labels:
        if not isinstance(label, dict):
            continue
        if str(label.get("name", "")).strip() == "case_id":
            label["value"] = case_id
            return
    labels.append({"name": "case_id", "value": case_id})


def _normalize_allure_result_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    case_id = _derive_allure_case_id(payload)
    if not case_id:
        return payload
    _ensure_allure_case_id_label(payload, case_id)
    value = str(payload.get("name", "")).strip()
    if "test_yaml_" in value and "[" in value and "]" in value:
        prefix = value.split("[", 1)[0]
        payload["name"] = f"{prefix}[{case_id}]"
    return payload


def _build_allure_name_replacements(root: Path) -> dict[str, str]:
    replacements: dict[str, str] = {}
    if not root.exists():
        return replacements
    for path in root.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        stack: list[Any] = [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                case_id = _derive_allure_case_id(current)
                name = str(current.get("name", "")).strip()
                if case_id and "test_yaml_" in name and "[" in name and "]" in name:
                    prefix = name.split("[", 1)[0]
                    normalized = f"{prefix}[{case_id}]"
                    if normalized != name:
                        replacements[name] = normalized
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)
    return replacements


@dataclass
class CaseDoc:
    path: Path
    old_id: str
    page: str
    module: str
    title: str
    description: str
    tags: list[str]
    runner: str
    is_ai_generated: bool


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


def _slug(value: str, fallback: str) -> str:
    return slugify_case_part(str(value or "").strip(), fallback=fallback)


def _collect_cases() -> list[CaseDoc]:
    docs: list[CaseDoc] = []
    for path in sorted(ASSETS_ROOT.rglob("*.yaml")):
        payload = _read_yaml(path)
        old_id = str(payload.get("id", path.stem)).strip() or path.stem
        execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
        page = _slug(str(execution.get("page", "")).strip() or str(payload.get("page", "")).strip(), "page")
        module = _slug(str(payload.get("module", "")).strip() or page, "module")
        tags = [str(item).strip() for item in (payload.get("tags") or []) if str(item).strip()]
        docs.append(
            CaseDoc(
                path=path,
                old_id=old_id,
                page=page,
                module=module,
                title=str(payload.get("title", "")).strip(),
                description=str(payload.get("description", "")).strip(),
                tags=tags,
                runner=str(execution.get("runner", "")).strip() or "playwright",
                is_ai_generated=AI_GENERATED_ROOT in path.parents,
            )
        )
    return docs


def _iter_text_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS]


def _scan_referenced_case_ids(case_ids: list[str]) -> set[str]:
    referenced: set[str] = set()
    text_files: list[Path] = []
    for root in [WEB_UI_STATE, REPORTS_ROOT, *ALLURE_ROOTS]:
        text_files.extend(_iter_text_files(root))
    for path in text_files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for case_id in case_ids:
            if case_id and case_id in text:
                referenced.add(case_id)

    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        try:
            tables = [row[0] for row in conn.execute("select name from sqlite_master where type='table'")]
            for table in tables:
                columns = [row[1] for row in conn.execute(f"pragma table_info({table})")]
                if not columns:
                    continue
                rows = conn.execute(f"select * from {table}").fetchall()
                for row in rows:
                    for value in row:
                        if not isinstance(value, str):
                            continue
                        for case_id in case_ids:
                            if case_id and case_id in value:
                                referenced.add(case_id)
        finally:
            conn.close()
    return referenced


def _build_mapping(kept_cases: list[CaseDoc]) -> dict[str, str]:
    grouped: dict[tuple[str, str, str, str, str, str], list[CaseDoc]] = defaultdict(list)
    for doc in kept_cases:
        project = "ATP"
        client = infer_client_code(doc.runner)
        page_code = infer_page_code(doc.page, title=doc.title, tags=doc.tags)
        module_code = infer_module_code(
            page=doc.page,
            module=doc.module,
            title=doc.title,
            tags=doc.tags,
        )
        case_type = infer_case_type(title=doc.title, description=doc.description, tags=doc.tags)
        source = infer_source_code(tags=doc.tags, source_hint="ai-generated" if doc.is_ai_generated else "", legacy=not doc.is_ai_generated)
        grouped[(project, client, page_code, module_code, case_type, source)].append(doc)

    mapping: dict[str, str] = {}
    for key in sorted(grouped):
        docs = sorted(grouped[key], key=lambda item: (item.path.as_posix(), item.old_id))
        for index, doc in enumerate(docs, start=1):
            mapping[doc.old_id] = build_case_id(
                project=key[0],
                client=key[1],
                page_code=key[2],
                module_code=key[3],
                case_type=key[4],
                source=key[5],
                sequence=index,
            )
    return mapping


def _replace_case_ids_in_string(value: str, replacements: dict[str, str]) -> str:
    text = str(value)
    updated = text
    for old_value, new_value in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        if old_value == new_value:
            continue
        updated = updated.replace(f"{old_value}:", f"{new_value}:")
        updated = updated.replace(old_value, new_value)
    return updated


def _replace_in_obj(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_in_obj(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_in_obj(item, replacements) for item in value]
    if isinstance(value, str):
        return _replace_case_ids_in_string(value, replacements)
    return value


def _rewrite_json_file(path: Path, replacements: dict[str, str]) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        text = path.read_text(encoding="utf-8", errors="ignore")
        updated = _replace_case_ids_in_string(text, replacements)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
        return
    updated = _replace_in_obj(payload, replacements)
    if isinstance(updated, dict):
        updated = _normalize_allure_result_payload(updated)
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")


def _rewrite_text_file(path: Path, replacements: dict[str, str]) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    updated = _replace_case_ids_in_string(text, replacements)
    if updated != text:
        path.write_text(updated, encoding="utf-8")


def _rename_case_file(path: Path, new_id: str) -> Path:
    new_path = path.with_name(f"{new_id}{path.suffix}")
    if new_path == path:
        return path
    new_path.parent.mkdir(parents=True, exist_ok=True)
    path.rename(new_path)
    return new_path


def _rewrite_yaml_cases(kept_cases: list[CaseDoc], mapping: dict[str, str]) -> dict[str, str]:
    path_mapping: dict[str, str] = {}
    for doc in kept_cases:
        payload = _read_yaml(doc.path)
        new_id = mapping[doc.old_id]
        metadata = build_case_metadata(
            page=doc.page,
            module=doc.module,
            title=doc.title,
            description=doc.description,
            tags=doc.tags,
            client=infer_client_code(doc.runner),
            source_hint="ai-generated" if doc.is_ai_generated else "",
            legacy=not doc.is_ai_generated,
        )
        if doc.old_id != new_id:
            payload["legacy_case_id"] = doc.old_id
        payload["project"] = metadata["project"]
        payload["client"] = metadata["client"]
        payload["page_code"] = metadata["page_code"]
        payload["page_name"] = metadata["page_name"]
        payload["module_code"] = metadata["module_code"]
        payload["module_name"] = metadata["module_name"]
        payload["case_type"] = metadata["case_type"]
        payload["case_type_name"] = metadata["case_type_name"]
        payload["source"] = metadata["source"]
        payload["source_name"] = metadata["source_name"]
        payload["id"] = new_id
        if isinstance(payload.get("module"), str):
            payload["module"] = doc.module
        execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
        if execution:
            execution["page"] = doc.page
            payload["execution"] = execution
        _write_yaml(doc.path, payload)
        new_path = _rename_case_file(doc.path, new_id)
        path_mapping[str(doc.path.resolve())] = str(new_path.resolve())
        if str(doc.path) != str(new_path):
            path_mapping[str(doc.path)] = str(new_path)
            path_mapping[doc.path.name] = new_path.name
    return path_mapping


def _rewrite_sqlite(replacements: dict[str, str]) -> None:
    if not DB_PATH.exists():
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        tables = [row[0] for row in conn.execute("select name from sqlite_master where type='table'")]
        for table in tables:
            cols = [row[1] for row in conn.execute(f"pragma table_info({table})")]
            if not cols:
                continue
            rows = conn.execute(f"select rowid, * from {table}").fetchall()
            for row in rows:
                rowid = row[0]
                values = list(row[1:])
                updated_values: list[Any] = []
                changed = False
                for value in values:
                    updated = value
                    if isinstance(value, str):
                        updated = _replace_case_ids_in_string(value, replacements)
                    updated_values.append(updated)
                    changed = changed or (updated != value)
                if changed:
                    assignments = ", ".join([f"{col}=?" for col in cols])
                    conn.execute(f"update {table} set {assignments} where rowid=?", (*updated_values, rowid))
        conn.commit()
    finally:
        conn.close()


def _rename_path_if_needed(path: Path, mapping: dict[str, str]) -> Path:
    new_name = mapping.get(path.stem)
    if not new_name:
        return path
    new_path = path.with_name(f"{new_name}{path.suffix}")
    if new_path == path:
        return path
    new_path.parent.mkdir(parents=True, exist_ok=True)
    if new_path.exists():
        new_path.unlink()
    path.rename(new_path)
    return new_path


def _rewrite_test_point_state(
    replacements: dict[str, str], mapping: dict[str, str], deleted_ids: set[str], valid_ids: set[str]
) -> None:
    if not TEST_POINT_STATE_ROOT.exists():
        return
    for path in sorted(TEST_POINT_STATE_ROOT.glob("*.json")):
        if path.stem in deleted_ids or path.stem not in valid_ids:
            path.unlink(missing_ok=True)
            continue
        _rewrite_json_file(path, replacements)
        _rename_path_if_needed(path, mapping)
    plans_root = TEST_POINT_STATE_ROOT / "plans"
    if plans_root.exists():
        for path in sorted(plans_root.glob("*.json")):
            if path.stem in deleted_ids or path.stem not in valid_ids:
                path.unlink(missing_ok=True)
                continue
            _rewrite_json_file(path, replacements)
            _rename_path_if_needed(path, mapping)
    versions_root = TEST_POINT_STATE_ROOT / "versions"
    if versions_root.exists():
        for case_dir in sorted([item for item in versions_root.iterdir() if item.is_dir()]):
            if case_dir.name in deleted_ids or case_dir.name not in valid_ids:
                for child in case_dir.rglob("*"):
                    if child.is_file():
                        child.unlink()
                for child_dir in sorted([item for item in case_dir.rglob("*") if item.is_dir()], reverse=True):
                    child_dir.rmdir()
                case_dir.rmdir()
                continue
            for path in sorted(case_dir.glob("*.json")):
                _rewrite_json_file(path, replacements)
            new_name = mapping.get(case_dir.name)
            if new_name and new_name != case_dir.name:
                new_dir = case_dir.with_name(new_name)
                if new_dir.exists():
                    for child in new_dir.rglob("*"):
                        if child.is_file():
                            child.unlink()
                    new_dir.rmdir()
                case_dir.rename(new_dir)


def _rewrite_reports(replacements: dict[str, str], mapping: dict[str, str], deleted_ids: set[str], valid_ids: set[str]) -> None:
    if REPORTS_ROOT.exists():
        for path in sorted(REPORTS_ROOT.glob("*")):
            if not path.is_file():
                continue
            stem = path.name.split(".report", 1)[0]
            if stem in deleted_ids or stem not in valid_ids:
                path.unlink(missing_ok=True)
                continue
            _rewrite_text_file(path, replacements)
            for old_id, new_id in mapping.items():
                prefix = f"{old_id}.report"
                if path.name.startswith(prefix):
                    new_path = path.with_name(path.name.replace(prefix, f"{new_id}.report", 1))
                    if new_path != path:
                        if new_path.exists():
                            new_path.unlink()
                        path.rename(new_path)
                    break
    for root in ALLURE_ROOTS:
        if not root.exists():
            continue
        allure_name_replacements = _build_allure_name_replacements(root)
        combined_replacements = dict(replacements)
        combined_replacements.update(allure_name_replacements)
        for path in _iter_text_files(root):
            if path.suffix.lower() == ".json":
                _rewrite_json_file(path, combined_replacements)
            else:
                _rewrite_text_file(path, combined_replacements)


def _rewrite_run_artifacts(replacements: dict[str, str]) -> None:
    if not RUNS_ROOT.exists():
        return
    for path in _iter_text_files(RUNS_ROOT):
        if path.suffix.lower() == ".json":
            _rewrite_json_file(path, replacements)
        else:
            _rewrite_text_file(path, replacements)


def _rewrite_runtime_state(replacements: dict[str, str], valid_ids: set[str]) -> None:
    runtime_runs_path = WEB_UI_STATE / "default" / "runtime-runs.json"
    if runtime_runs_path.exists():
        _rewrite_json_file(runtime_runs_path, replacements)
    history_path = WEB_UI_STATE / "default" / "history.json"
    if history_path.exists():
        _rewrite_json_file(history_path, replacements)
        try:
            payload = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:
            payload = []
        if isinstance(payload, list):
            filtered: list[dict[str, Any]] = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                case_id = str(item.get("case_id", "")).strip()
                run_case_id, _ = split_run_id(str(item.get("run_id", "")).strip())
                effective_case_id = case_id or run_case_id
                if effective_case_id and effective_case_id not in valid_ids:
                    continue
                filtered.append(item)
            history_path.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")
    for path in [WEB_UI_STATE / "reporting" / "failure-source-calibrations.json",
                 WEB_UI_STATE / "reporting" / "execution-gate-decisions.json",
                 WEB_UI_STATE / "reporting" / "defect-links.json",
                 WEB_UI_STATE / "reporting" / "review-decisions.json"]:
        if path.exists():
            _rewrite_json_file(path, replacements)


def _delete_unused_ai_cases(cases: list[CaseDoc], referenced_ids: set[str]) -> set[str]:
    deleted_ids: set[str] = set()
    for doc in cases:
        if not doc.is_ai_generated:
            continue
        if doc.old_id in referenced_ids:
            continue
        deleted_ids.add(doc.old_id)
        doc.path.unlink(missing_ok=True)
    return deleted_ids


def _write_summary(summary: dict[str, Any]) -> None:
    target = WEB_UI_STATE / "reporting" / "case-id-migration-summary.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    cases = _collect_cases()
    referenced_ids = _scan_referenced_case_ids([doc.old_id for doc in cases])
    deleted_ids = _delete_unused_ai_cases(cases, referenced_ids)
    kept_cases = [doc for doc in cases if doc.old_id not in deleted_ids]
    mapping = _build_mapping(kept_cases)
    valid_ids = set(mapping.values())
    path_mapping = _rewrite_yaml_cases(kept_cases, mapping)
    combined_mapping = dict(mapping)
    for old_path, new_path in path_mapping.items():
        combined_mapping[old_path] = new_path
    _rewrite_runtime_state(combined_mapping, valid_ids)
    _rewrite_test_point_state(combined_mapping, mapping, deleted_ids, valid_ids)
    _rewrite_sqlite(combined_mapping)
    _rewrite_run_artifacts(combined_mapping)
    _rewrite_reports(combined_mapping, mapping, deleted_ids, valid_ids)
    summary = {
        "total_cases_before": len(cases),
        "deleted_unused_ai_cases": len(deleted_ids),
        "total_cases_after": len(kept_cases),
        "deleted_case_ids": sorted(deleted_ids),
        "mappings": [{"old_id": old_id, "new_id": new_id} for old_id, new_id in sorted(mapping.items())],
    }
    _write_summary(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
