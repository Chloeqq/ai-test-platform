from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from app.services.page_element_code_policy import suggest_business_element_code

SOURCE_ROOTS_ENV = "PAGE_OBJECT_SOURCE_ROOTS"
SOURCE_ROOTS_BY_PROJECT_ENV = "PAGE_OBJECT_SOURCE_ROOTS_BY_PROJECT"
SOURCE_ROOTS_PROJECT_ENV_PREFIX = "PAGE_OBJECT_SOURCE_ROOTS_"
SOURCE_FILE_SUFFIXES = {".vue", ".tsx", ".jsx", ".ts", ".js", ".html"}
MAX_SOURCE_FILES = 2000
MAX_FILE_BYTES = 512_000
SourceCatalogCacheKey: TypeAlias = tuple[
    str,
    str,
    str,
    tuple[str, ...],
    tuple[tuple[str, str], ...],
    int,
    int,
]
_SOURCE_CATALOG_CACHE: dict[SourceCatalogCacheKey, SourceSemanticCatalog] = {}
_SOURCE_CATALOG_CACHE_MAX_SIZE = 128
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceSemanticHint:
    code_seed: str
    name: str
    business_type: str
    business_domain: str
    source: str
    priority: int = 0


def _text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _normalize_match_text(value: str) -> str:
    text = _text(value).lower()
    return re.sub(r"[\s:：,，。.;；/\\|()（）【】\[\]{}<>_-]+", "", text)


def _snake(value: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value or "").strip())
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return re.sub(r"_+", "_", text)


def _business_domain(page_code: str, text: str) -> str:
    haystack = f"{page_code} {text}".lower()
    if re.search(r"(login|signin|auth|password|username|账号|密码|登录)", haystack):
        return "auth"
    if re.search(r"(menu|nav|sidebar|breadcrumb|导航|菜单)", haystack):
        return "navigation"
    if re.search(r"(search|query|filter|搜索|查询|筛选)", haystack):
        return "search"
    if re.search(r"(table|grid|list|表格|列表|column|列)", haystack):
        return "table"
    if re.search(r"(form|input|submit|save|表单|保存|提交)", haystack):
        return "form"
    if re.search(r"(dashboard|home|chart|metric|首页|统计|看板)", haystack):
        return "dashboard"
    return "common"


def _business_type_for_button(label: str) -> str:
    text = _text(label).lower()
    if re.search(r"(菜单|导航|首页|列表|详情|分类|资源|权限)", text):
        return "button"
    return "button"


def _button_code_seed(label: str) -> str:
    semantic = suggest_business_element_code(label, business_type="button")
    if semantic:
        return semantic
    normalized = _snake(label)
    return f"{normalized}_button" if normalized and not normalized.endswith("_button") else normalized


def _source_business_code_from_text(
    value: str,
    *,
    business_type: str = "",
    semantic_terms: dict[str, str] | None = None,
) -> str:
    compact = re.sub(r"[：:，,。.;；/\\|()（）【】\[\]{}<>\s]+", "", str(value or ""))
    if not compact:
        return ""
    phrases = [
        (str(phrase or "").strip(), str(code or "").strip())
        for phrase, code in dict(semantic_terms or {}).items()
        if str(phrase or "").strip() and str(code or "").strip()
    ]
    for phrase, code in phrases:
        if phrase in compact:
            suffix = str(business_type or "").strip().lower()
            if suffix and suffix not in {"container"} and not code.endswith(f"_{suffix}"):
                return f"{code}_{suffix}"
            return code
    return ""


def _split_source_root_values(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _resolve_source_roots(raw_values: list[str]) -> list[Path]:
    roots: list[Path] = []
    for raw in raw_values:
        if not raw:
            continue
        for item in str(raw or "").split(","):
            item = item.strip()
            if not item:
                continue
            try:
                path = Path(item).expanduser().resolve()
            except OSError:
                continue
            if path.exists() and path.is_dir() and path not in roots:
                roots.append(path)
    return roots


def _project_env_suffix(project_code: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(project_code or "").strip().upper()).strip("_")


def _project_mapped_source_values(project_code: str) -> list[str] | None:
    normalized_project_code = str(project_code or "").strip().lower()
    if not normalized_project_code:
        return []

    mapped_values: list[str] = []
    raw_mapping = str(os.getenv(SOURCE_ROOTS_BY_PROJECT_ENV, "") or "").strip()
    if raw_mapping:
        try:
            mapping = json.loads(raw_mapping)
        except json.JSONDecodeError:
            logger.warning(
                "%s is malformed; source semantic enhancement is disabled for project %s",
                SOURCE_ROOTS_BY_PROJECT_ENV,
                normalized_project_code,
            )
            return None
        if isinstance(mapping, dict):
            for key, value in mapping.items():
                if str(key or "").strip().lower() == normalized_project_code:
                    mapped_values.extend(_split_source_root_values(value))

    suffix = _project_env_suffix(normalized_project_code)
    if suffix:
        mapped_values.extend(_split_source_root_values(os.getenv(f"{SOURCE_ROOTS_PROJECT_ENV_PREFIX}{suffix}", "")))
    return mapped_values


def _source_roots(project_code: str = "") -> list[Path]:
    normalized_project_code = str(project_code or "").strip().lower()
    project_values = _project_mapped_source_values(normalized_project_code)
    if project_values is None:
        return []
    project_roots = _resolve_source_roots(project_values)
    if normalized_project_code:
        return project_roots
    raw_values: list[str] = []
    for item in str(os.getenv(SOURCE_ROOTS_ENV, "")).split(","):
        raw = item.strip()
        if raw:
            raw_values.append(raw)
    return _resolve_source_roots(raw_values)


def _source_terms_from_env(project_code: str = "") -> dict[str, str] | None:
    raw = str(os.getenv("PAGE_OBJECT_SOURCE_TERMS_JSON", "") or "").strip()
    terms: dict[str, str] = {}
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            for key, value in parsed.items():
                if isinstance(value, dict):
                    if project_code and str(key or "").strip().lower() == str(project_code or "").strip().lower():
                        terms.update({str(k): str(v) for k, v in value.items()})
                else:
                    terms[str(key)] = str(value)
    return terms


def _normalize_semantic_terms(value: dict[str, str] | None, *, project_code: str = "") -> dict[str, str]:
    terms: dict[str, str] = {}
    env_terms = _source_terms_from_env(project_code=project_code)
    if env_terms:
        terms.update(env_terms)
    for key, raw_value in dict(value or {}).items():
        phrase = str(key or "").strip()
        code = str(raw_value or "").strip()
        if phrase and code:
            terms[phrase] = code
    return terms


def _iter_source_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        for path in root.rglob("*"):
            if len(files) >= MAX_SOURCE_FILES:
                return files
            if not path.is_file() or path.suffix.lower() not in SOURCE_FILE_SUFFIXES:
                continue
            if any(part in {"node_modules", "dist", "build", ".git"} for part in path.parts):
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            files.append(path)
    return files


def _source_files_fingerprint(files: list[Path]) -> tuple[int, int]:
    max_mtime_ns = 0
    for path in files:
        try:
            max_mtime_ns = max(max_mtime_ns, int(path.stat().st_mtime_ns))
        except OSError:
            continue
    return len(files), max_mtime_ns


def _route_tokens(route: str) -> set[str]:
    tokens = {
        _snake(part)
        for part in re.split(r"[/#?=&._-]+", str(route or ""))
        if len(str(part or "").strip()) >= 2
    }
    return {item for item in tokens if item}


def _file_score(path: Path, content: str, *, page_code: str, route: str) -> int:
    path_text = str(path).replace("\\", "/").lower()
    content_lower = content.lower()
    page_token = _snake(page_code)
    score = 0
    if page_token and page_token in _snake(path_text):
        score += 5
    if page_token and page_token in _snake(content_lower):
        score += 2
    for token in _route_tokens(route):
        if token and token in _snake(path_text):
            score += 3
        elif token and token in _snake(content_lower):
            score += 1
    if "router" in path_text and score > 0:
        score += 8
    return score


def _add_hint(
    hints: dict[str, list[SourceSemanticHint]],
    *,
    match_text: str,
    code_seed: str,
    name: str,
    business_type: str,
    business_domain: str,
    source: str,
    priority: int = 0,
) -> None:
    key = _normalize_match_text(match_text)
    if not key:
        return
    normalized_code_seed = _snake(code_seed)
    if not normalized_code_seed:
        normalized_code_seed = suggest_business_element_code(name, business_type=business_type)
    if not normalized_code_seed:
        return
    next_hint = SourceSemanticHint(
        code_seed=normalized_code_seed,
        name=_text(name) or _text(match_text),
        business_type=business_type,
        business_domain=business_domain,
        source=source,
        priority=priority,
    )
    bucket = hints.setdefault(key, [])
    if next_hint not in bucket:
        bucket.append(next_hint)


def _strip_template_expressions(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", str(value or ""))
    text = re.sub(r"{{.*?}}", "", text, flags=re.S)
    return _text(text)


def _extract_object_label_props(content: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for match in re.finditer(r"\{(?P<body>[^{}]{0,600})\}", content, re.S):
        body = str(match.group("body") or "")
        label_match = re.search(r"\blabel\s*:\s*['\"]([^'\"]+)['\"]", body)
        if not label_match:
            continue
        prop_match = re.search(r"\b(?:prop|key|field)\s*:\s*['\"]([^'\"]+)['\"]", body)
        if prop_match is None:
            continue
        pairs.append((_text(label_match.group(1)), _text(prop_match.group(1) if prop_match else "")))
    return pairs


def _extract_router_title_blocks(content: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for match in re.finditer(
        r"\bpath\s*:\s*['\"]([^'\"]+)['\"][^{}]{0,500}?\bmeta\s*:\s*\{[^{}]*?\btitle\s*:\s*['\"]([^'\"]+)['\"]",
        content,
        re.S,
    ):
        pairs.append((_text(match.group(1)), _text(match.group(2))))
    return pairs


def _extract_hints_from_content(
    content: str,
    *,
    page_code: str,
    source_name: str,
    semantic_terms: dict[str, str] | None = None,
) -> dict[str, list[SourceSemanticHint]]:
    hints: dict[str, list[SourceSemanticHint]] = {}

    for match in re.finditer(r'(<el-form-item[^>]*\blabel=["\']([^"\']+)["\'][^>]*>)(.*?)</el-form-item>', content, re.S):
        opening_tag = str(match.group(1) or "")
        label = _text(match.group(2))
        body = str(match.group(3) or "")
        placeholder_match = re.search(r'\bplaceholder=["\']([^"\']+)["\']', body)
        prop_match = re.search(r'\bprop=["\']([^"\']+)["\']', opening_tag)
        code_base = (
            _snake(prop_match.group(1) if prop_match else "")
            or _source_business_code_from_text(label, semantic_terms=semantic_terms)
            or suggest_business_element_code(label)
        )
        code_seed = f"{code_base}_input" if code_base and not code_base.endswith("_input") else code_base
        domain = _business_domain(page_code, label)
        _add_hint(hints, match_text=label, code_seed=code_seed, name=f"{label}输入框", business_type="input", business_domain=domain, source=source_name, priority=70)
        if placeholder_match:
            placeholder = _text(placeholder_match.group(1))
            placeholder_code = ""
            if prop_match is None:
                placeholder_code = _source_business_code_from_text(
                    placeholder,
                    business_type="input",
                    semantic_terms=semantic_terms,
                ) or suggest_business_element_code(placeholder, business_type="input")
            _add_hint(
                hints,
                match_text=placeholder,
                code_seed=placeholder_code or code_seed,
                name=f"{label if prop_match is not None else placeholder}输入框",
                business_type="input",
                business_domain=_business_domain(page_code, f"{label} {placeholder}"),
                source=source_name,
                priority=90,
            )

        if "show-password" in body or "showPassword" in body:
            _add_hint(
                hints,
                match_text=f"{label}显隐",
                code_seed="password_toggle",
                name="密码显隐切换",
                business_type="password_toggle",
                business_domain="auth",
                source=source_name,
                priority=70,
            )

    for match in re.finditer(r'\bplaceholder=["\']([^"\']+)["\']', content):
        placeholder = _text(match.group(1))
        code = _source_business_code_from_text(
            placeholder,
            business_type="input",
            semantic_terms=semantic_terms,
        ) or suggest_business_element_code(placeholder, business_type="input")
        _add_hint(hints, match_text=placeholder, code_seed=code, name=f"{placeholder}输入框", business_type="input", business_domain=_business_domain(page_code, placeholder), source=source_name, priority=50)

    for match in re.finditer(r'<el-button[^>]*>(.*?)</el-button>', content, re.S):
        label = _strip_template_expressions(match.group(1))
        code = _button_code_seed(label)
        _add_hint(hints, match_text=label, code_seed=code, name=f"{label}按钮", business_type=_business_type_for_button(label), business_domain=_business_domain(page_code, label), source=source_name, priority=70)

    for match in re.finditer(r'<el-table-column[^>]*\blabel=["\']([^"\']+)["\'][^>]*>', content):
        tag = match.group(0)
        label = _text(match.group(1))
        prop_match = re.search(r'\bprop=["\']([^"\']+)["\']', tag)
        code_base = (
            _snake(prop_match.group(1) if prop_match else "")
            or _source_business_code_from_text(label, semantic_terms=semantic_terms)
            or suggest_business_element_code(label)
        )
        code_seed = f"{code_base}_column" if code_base and not code_base.endswith("_column") else code_base
        _add_hint(hints, match_text=label, code_seed=code_seed, name=f"{label}列", business_type="container", business_domain="table", source=source_name, priority=95)

    for label, prop in _extract_object_label_props(content):
        code_base = _snake(prop) or _source_business_code_from_text(label, semantic_terms=semantic_terms) or suggest_business_element_code(label)
        if not code_base:
            continue
        column_seed = f"{code_base}_column" if not code_base.endswith("_column") else code_base
        _add_hint(hints, match_text=label, code_seed=column_seed, name=f"{label}列", business_type="container", business_domain="table", source=source_name, priority=85)

    for route, title in _extract_router_title_blocks(content):
        route_code = (
            suggest_business_element_code(route, business_type="menu")
            or _source_business_code_from_text(title, business_type="menu", semantic_terms=semantic_terms)
            or suggest_business_element_code(title, business_type="menu")
        )
        _add_hint(hints, match_text=title, code_seed=route_code, name=title, business_type="menu", business_domain="navigation", source=source_name, priority=60)
        _add_hint(hints, match_text=route, code_seed=route_code, name=title, business_type="menu", business_domain="navigation", source=source_name, priority=50)

    for match in re.finditer(r'<(?:el-menu-item|el-sub-menu|el-submenu)[^>]*>(.*?)</(?:el-menu-item|el-sub-menu|el-submenu)>', content, re.S):
        label = _strip_template_expressions(match.group(1))
        code = _source_business_code_from_text(label, business_type="menu", semantic_terms=semantic_terms) or suggest_business_element_code(label, business_type="menu")
        _add_hint(hints, match_text=label, code_seed=code, name=label, business_type="menu", business_domain="navigation", source=source_name, priority=55)

    for match in re.finditer(r'\btitle\s*:\s*["\']([^"\']+)["\']', content):
        title = _text(match.group(1))
        code = _source_business_code_from_text(title, business_type="menu", semantic_terms=semantic_terms) or suggest_business_element_code(title, business_type="menu")
        _add_hint(hints, match_text=title, code_seed=code, name=title, business_type="menu", business_domain="navigation", source=source_name, priority=35)

    return hints


class SourceSemanticCatalog:
    def __init__(self, hints: dict[str, list[SourceSemanticHint]] | None = None) -> None:
        self._hints = hints or {}

    def match(self, *, locator_type: str, locator_value: str, role: str = "") -> SourceSemanticHint | None:
        candidates = [_normalize_match_text(locator_value)]
        if locator_type == "role" and role:
            candidates.append(_normalize_match_text(f"{role} {locator_value}"))
        matches: list[SourceSemanticHint] = []
        for key in candidates:
            matches.extend(self._hints.get(key) or [])
        if not matches:
            return None
        return sorted(
            matches,
            key=lambda item: _contextual_hint_score(item, locator_type=locator_type, role=role),
            reverse=True,
        )[0]

    def find_by_business_type(self, business_type: str) -> SourceSemanticHint | None:
        normalized = str(business_type or "").strip().lower()
        matches = [
            hint
            for bucket in self._hints.values()
            for hint in bucket
            if str(hint.business_type or "").strip().lower() == normalized
        ]
        if not matches:
            return None
        return sorted(matches, key=lambda item: item.priority, reverse=True)[0]

    def __len__(self) -> int:
        return sum(len(bucket) for bucket in self._hints.values())


def _contextual_hint_score(hint: SourceSemanticHint, *, locator_type: str, role: str = "") -> int:
    score = int(hint.priority or 0)
    normalized_locator_type = str(locator_type or "").strip().lower()
    normalized_role = str(role or "").strip().lower()
    business_type = str(hint.business_type or "").strip().lower()
    business_domain = str(hint.business_domain or "").strip().lower()

    if normalized_locator_type == "placeholder":
        score += 100 if business_type == "input" else -50
    if normalized_locator_type == "role" and normalized_role == "button":
        score += 100 if business_type == "button" else -40
    if normalized_locator_type == "role" and normalized_role in {"menuitem", "menu"}:
        score += 100 if business_type == "menu" else -40
    if normalized_locator_type == "text":
        if business_domain == "table":
            score += 60
        if business_type in {"menu", "button", "container", "metric_label", "metric_value"}:
            score += 35
        if business_type == "input":
            score -= 25
    return score


def build_source_semantic_catalog(
    *,
    page_code: str,
    route: str = "",
    project_code: str = "",
    source_roots: list[str] | None = None,
    semantic_terms: dict[str, str] | None = None,
) -> SourceSemanticCatalog:
    roots = _resolve_source_roots(source_roots or []) if source_roots is not None else _source_roots(project_code=project_code)
    if not roots:
        return SourceSemanticCatalog()
    normalized_terms = _normalize_semantic_terms(semantic_terms, project_code=project_code)
    files = _iter_source_files(roots)
    file_count, max_mtime_ns = _source_files_fingerprint(files)
    cache_key: SourceCatalogCacheKey = (
        str(project_code or "").strip().lower(),
        str(page_code or "").strip(),
        str(route or "").strip(),
        tuple(str(root) for root in roots),
        tuple(sorted(normalized_terms.items())),
        file_count,
        max_mtime_ns,
    )
    cached = _SOURCE_CATALOG_CACHE.get(cache_key)
    if cached is not None:
        return cached
    hints: dict[str, list[SourceSemanticHint]] = {}
    scored_files: list[tuple[int, Path, str]] = []
    for path in files:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        score = _file_score(path, content, page_code=page_code, route=route)
        if score <= 0:
            continue
        scored_files.append((score, path, content))
    for _score, path, content in sorted(scored_files, key=lambda item: item[0], reverse=True)[:30]:
        source_name = str(path)
        for key, bucket in _extract_hints_from_content(
            content,
            page_code=page_code,
            source_name=source_name,
            semantic_terms=normalized_terms,
        ).items():
            hints.setdefault(key, []).extend(bucket)
    catalog = SourceSemanticCatalog(hints)
    if len(_SOURCE_CATALOG_CACHE) >= _SOURCE_CATALOG_CACHE_MAX_SIZE:
        _SOURCE_CATALOG_CACHE.clear()
    _SOURCE_CATALOG_CACHE[cache_key] = catalog
    return catalog
