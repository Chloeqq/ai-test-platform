from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.page_object import PageElement, PageElementLocator, PageObject
from app.repositories.page_object_repository import PageObjectRepository
from app.services import page_object_service, test_project_service
from shared_backend.case_ids import normalize_client_code
from shared_backend.type_utils import now_iso as _now_iso

_IMPORT_ROOT = (Path(__file__).resolve().parents[4] / "artifacts" / "page-object-imports").resolve()
_LANDED_SECTION_RE = re.compile(r"^##\s+3[.\s]")
_NEXT_SECTION_RE = re.compile(r"^##\s+4[.\s]")
_HEADING_RE = re.compile(r"^#{3,6}\s+(.+?)\s*$")
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_SOURCE_PATH_RE = re.compile(r"src/.+\.(?:vue|tsx?|jsx?)$")
_TEMPLATE_TOKEN_RE = re.compile(r"\$\{([^}]+)\}|<([^>]+)>")
_REGION_MARKERS = {
    "page",
    "form",
    "search",
    "operate",
    "table",
    "batch",
    "pagination",
    "dialog",
    "row",
    "edit",
    "add",
    "update",
    "detail",
    "sku",
    "close",
    "receiver",
    "money",
    "message",
    "mark",
    "deliver",
    "action",
    "select",
    "sort",
    "relation",
    "category",
    "link",
    "total",
    "overview",
    "statistics",
    "pending",
    "qrcode",
}
_CONTAINER_SUFFIXES = {
    "page",
    "form",
    "card",
    "table",
    "bar",
    "pagination",
    "panel",
    "steps",
    "tree",
    "widget",
    "dialog",
    "menu",
}
_ACTION_SUFFIXES = {
    "btn",
    "input",
    "select",
    "cascader",
    "picker",
    "radio",
    "switch",
    "checkbox",
    "upload",
    "editor",
    "dropdown",
    "avatar",
    "item",
}
_ROUTE_SHELL_PAGE_LABELS = {
    "product": "商品",
    "brand": "品牌",
    "coupon": "优惠券",
    "advertise": "广告",
    "product-cate": "商品分类",
    "product-attr": "商品属性",
    "menu": "菜单",
}
_SHARED_LAYOUT_PREFIXES = {"layout", "sidebar", "breadcrumb", "hamburger"}
_PAGE_NAME_BY_CODE = {
    "login": "登录页",
    "layout": "全局布局",
    "product": "商品列表页",
    "product-add": "商品新增页",
    "product-update": "商品编辑页",
    "order": "订单列表页",
    "user": "用户列表页",
    "menu": "菜单管理页",
    "role": "角色管理页",
}
_ELEMENT_EXACT_NAMES = {
    "login-page": "登录页容器",
    "login-form": "登录表单",
    "login-username-input": "用户名输入框",
    "login-password-input": "密码输入框",
    "login-submit-btn": "登录按钮",
    "login-trial-account-btn": "体验账号按钮",
    "layout-page": "全局布局容器",
    "layout-navbar": "顶部导航栏",
    "layout-navbar-breadcrumb": "顶部面包屑",
    "layout-sidebar-menu": "侧边栏菜单",
    "sidebar-menu-routename": "侧边栏菜单项",
    "sidebar-submenu-routename": "侧边栏父级子菜单",
    "sidebar-link-routename": "侧边栏外链菜单项",
    "breadcrumb-item-routename": "面包屑导航项",
    "hamburger-toggle-btn": "侧边栏折叠按钮",
}
_ELEMENT_TOKEN_LABELS = {
    "account": "账号",
    "action": "操作",
    "add": "新增",
    "avatar": "头像",
    "batch": "批量",
    "breadcrumb": "面包屑",
    "btn": "按钮",
    "button": "按钮",
    "card": "卡片",
    "category": "分类",
    "checkbox": "复选框",
    "close": "关闭",
    "confirm": "确认",
    "content": "内容",
    "coupon": "优惠券",
    "delete": "删除",
    "detail": "详情",
    "dialog": "弹窗",
    "edit": "编辑",
    "form": "表单",
    "hamburger": "折叠菜单",
    "input": "输入框",
    "keyword": "关键词",
    "layout": "全局布局",
    "link": "链接",
    "login": "登录",
    "menu": "菜单",
    "name": "名称",
    "navbar": "顶部导航",
    "order": "订单",
    "page": "页面容器",
    "pagination": "分页",
    "password": "密码",
    "picker": "选择器",
    "product": "商品",
    "radio": "单选",
    "receiver": "收货人",
    "reset": "重置",
    "role": "角色",
    "routename": "路由名",
    "row": "行",
    "search": "搜索",
    "select": "选择框",
    "sidebar": "侧边栏",
    "submit": "提交",
    "submenu": "父级子菜单",
    "switch": "开关",
    "table": "表格",
    "toggle": "折叠",
    "update": "编辑",
    "upload": "上传",
    "user": "用户",
    "username": "用户名",
}
_ELEMENT_SUFFIX_LABELS = {
    "btn": "按钮",
    "button": "按钮",
    "input": "输入框",
    "select": "选择框",
    "cascader": "级联选择",
    "picker": "时间选择",
    "switch": "开关",
    "radio": "单选",
    "checkbox": "复选框",
    "dialog": "弹窗",
    "table": "表格",
    "page": "页面容器",
    "form": "表单",
    "card": "卡片",
    "menu": "菜单",
    "link": "链接",
}

@dataclass(frozen=True)
class ParsedTestIdElement:
    testid: str
    element_code: str
    page_code: str
    page_name: str
    source_path: str
    source_section: str
    business_type: str
    business_domain: str
    is_key_element: bool
    match_strategy: str
    semantic_tags: list[str]

def _hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def _import_path(import_id: str) -> Path:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "", str(import_id or "").strip())
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="import_id is required")
    return _IMPORT_ROOT / f"{normalized}.json"

def _read_import(import_id: str) -> dict[str, Any]:
    path = _import_path(import_id)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"page object import not found: {import_id}")
    return json.loads(path.read_text(encoding="utf-8"))

def _write_import(payload: dict[str, Any]) -> None:
    _IMPORT_ROOT.mkdir(parents=True, exist_ok=True)
    path = _import_path(str(payload.get("import_id") or ""))
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def _extract_source_path(text: str) -> str:
    for value in _BACKTICK_RE.findall(text):
        normalized = value.strip()
        if _SOURCE_PATH_RE.match(normalized):
            return normalized
    return ""

def _is_testid_token(value: str) -> bool:
    normalized = str(value or "").strip()
    if not normalized or _SOURCE_PATH_RE.match(normalized):
        return False
    if normalized in {"row.id", "scope.row.id", "index", "id", "memberLevelId"}:
        return False
    return "-" in normalized and not normalized.startswith(":data-testid")

def _title_without_source(value: str) -> str:
    return _BACKTICK_RE.sub("", str(value or "")).strip(" ：:")

def _source_name(source_path: str, fallback: str) -> str:
    title = _title_without_source(fallback)
    if title:
        return title[:120]
    if source_path:
        stem = Path(source_path).stem
        if stem:
            return stem[:120]
    return "页面对象"

def _route_shell_page_name(page_code: str, section: str) -> str:
    if "add/update" not in str(section or "").lower():
        return ""
    normalized = str(page_code or "").strip().lower()
    action_label = ""
    base = normalized
    if normalized.endswith("-add"):
        base = normalized[: -len("-add")]
        action_label = "新增"
    elif normalized.endswith("-update"):
        base = normalized[: -len("-update")]
        action_label = "编辑"
    if not base or not action_label:
        return ""
    label = _ROUTE_SHELL_PAGE_LABELS.get(base, "")
    return f"{label}{action_label}页" if label else ""

def _contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(value or "")))

def _should_replace_page_name(existing_name: str, next_name: str, page_code: str) -> bool:
    current = str(existing_name or "").strip()
    candidate = str(next_name or "").strip()
    if not candidate:
        return False
    if not current:
        return True
    if current == page_code:
        return True
    if not _contains_cjk(current) and _contains_cjk(candidate):
        return True
    return False

def _template_safe_code(testid: str) -> str:
    def replace(match: re.Match[str]) -> str:
        value = match.group(1) or match.group(2) or "var"
        value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
        return value or "var"

    return _TEMPLATE_TOKEN_RE.sub(replace, testid).strip("-")

def _derive_prefix(testid: str) -> str:
    safe = _template_safe_code(testid)
    if safe.endswith("-add-page") or safe.endswith("-update-page"):
        return safe[: -len("-page")]
    parts = [part for part in safe.split("-") if part]
    if len(parts) <= 1:
        return safe
    for index, part in enumerate(parts):
        if part in _REGION_MARKERS and index > 0:
            return "-".join(parts[:index])
    return parts[0]

def _normalize_page_code_for_testid(page_code: str) -> str:
    normalized = str(page_code or "").strip().lower()
    return "layout" if normalized in _SHARED_LAYOUT_PREFIXES else normalized

def _dominant_page_code(tokens: list[str]) -> str:
    for token in tokens:
        safe = _template_safe_code(token)
        if safe.endswith("-page"):
            return _normalize_page_code_for_testid(safe[: -len("-page")])
    if tokens:
        return _normalize_page_code_for_testid(_derive_prefix(tokens[0]))
    return ""

def _business_type(testid: str) -> str:
    safe = _template_safe_code(testid)
    parts = safe.split("-")
    if safe.endswith("-btn") or safe.endswith("-button"):
        return "button"
    if safe.endswith("-input") or safe.endswith("-picker") or safe.endswith("-select") or safe.endswith("-cascader"):
        return "input"
    if safe.endswith("-switch"):
        return "switch"
    if safe.endswith("-radio"):
        return "radio"
    if safe.endswith("-checkbox") or safe.endswith("-checkbox-group"):
        return "checkbox"
    if safe.endswith("-dialog"):
        return "dialog"
    if safe.endswith("-table"):
        return "table"
    if safe.endswith("-menu") or "-menu-" in safe:
        return "menu"
    if safe.endswith("-item") or safe.endswith("-link"):
        return "link"
    if parts and parts[-1] in {"editor", "upload", "dropdown", "avatar"}:
        return "container"
    return "container"

def _business_domain(testid: str) -> str:
    safe = _template_safe_code(testid)
    if safe.startswith("login-"):
        return "auth"
    if safe.startswith(("layout-", "sidebar-", "breadcrumb-", "hamburger-")):
        return "navigation"
    if "-search-" in safe:
        return "search"
    if "-row-" in safe or safe.endswith("-table"):
        return "table"
    if "-detail-" in safe:
        return "detail"
    if "-form" in safe or "-dialog-" in safe:
        return "form"
    return "common"

def _is_key_element(testid: str, business_type: str) -> bool:
    safe = _template_safe_code(testid)
    if safe.endswith(tuple(f"-{suffix}" for suffix in _CONTAINER_SUFFIXES)):
        return False
    if business_type in {"button", "input", "switch", "radio", "checkbox", "link"}:
        return True
    return safe.endswith(tuple(f"-{suffix}" for suffix in _ACTION_SUFFIXES))

def parse_data_testid_guidelines(markdown_text: str, *, page_code_filter: str = "") -> list[ParsedTestIdElement]:
    in_landed_section = False
    current_section = ""
    current_source = ""
    block_tokens: list[tuple[str, str, str]] = []
    blocks: list[tuple[str, str, list[str]]] = []

    def flush_block() -> None:
        nonlocal block_tokens
        if not block_tokens:
            return
        source = current_source
        section = current_section
        tokens = [item[0] for item in block_tokens]
        blocks.append((section, source, tokens))
        block_tokens = []

    for raw_line in str(markdown_text or "").splitlines():
        line = raw_line.rstrip()
        if _LANDED_SECTION_RE.match(line):
            in_landed_section = True
            continue
        if in_landed_section and _NEXT_SECTION_RE.match(line):
            flush_block()
            break
        if not in_landed_section:
            continue
        heading = _HEADING_RE.match(line)
        if heading:
            flush_block()
            current_section = heading.group(1).strip()
            current_source = _extract_source_path(current_section)
            continue
        source_from_line = _extract_source_path(line)
        if source_from_line:
            flush_block()
            current_source = source_from_line
        tokens = [value.strip() for value in _BACKTICK_RE.findall(line) if _is_testid_token(value)]
        if not tokens:
            continue
        for token in tokens:
            block_tokens.append((token, current_section, current_source))
    else:
        if in_landed_section:
            flush_block()

    rows: list[ParsedTestIdElement] = []
    normalized_filter = str(page_code_filter or "").strip().lower()
    for section, source_path, tokens in blocks:
        dominant_page = _dominant_page_code(tokens)
        for token in tokens:
            is_template = bool(_TEMPLATE_TOKEN_RE.search(token))
            element_code = _template_safe_code(token) if is_template else token
            derived_page = _normalize_page_code_for_testid(_derive_prefix(token))
            page_code = dominant_page if dominant_page and element_code.startswith(f"{dominant_page}-") else derived_page
            if normalized_filter and page_code != normalized_filter:
                continue
            business_type = _business_type(token)
            page_name = _route_shell_page_name(page_code, section) or _PAGE_NAME_BY_CODE.get(page_code) or _source_name(source_path, section)
            semantic_tags = ["data-testid-import"]
            if page_code == "layout":
                semantic_tags.append("shared-layout")
            if is_template:
                semantic_tags.append("dynamic-row-template")
            if _template_safe_code(token).endswith(tuple(f"-{suffix}" for suffix in _CONTAINER_SUFFIXES)):
                semantic_tags.append("container")
            rows.append(
                ParsedTestIdElement(
                    testid=token,
                    element_code=element_code,
                    page_code=page_code,
                    page_name=page_name,
                    source_path=source_path,
                    source_section=_title_without_source(section),
                    business_type=business_type,
                    business_domain=_business_domain(token),
                    is_key_element=_is_key_element(token, business_type),
                    match_strategy="template" if is_template else "exact",
                    semantic_tags=semantic_tags,
                )
            )
    return rows


def _inventory_business_type(raw_type: str, testid: str) -> str:
    """Map the inventory's emitted type to ATP's action-compatibility type."""
    normalized = str(raw_type or "").strip().lower()
    if normalized in {"error-message", "message-content", "message", "notification"}:
        return "text"
    if normalized in {"button", "input", "switch", "radio", "checkbox", "dialog", "table", "menu", "link"}:
        return normalized
    return _business_type(testid)


def parse_data_testid_inventory(markdown_text: str, *, page_code_filter: str = "") -> list[ParsedTestIdElement]:
    """Parse mall-admin-web's generated data-testid-inventory.md format.

    The inventory is organized by source-file headings and Markdown table rows,
    unlike the hand-maintained "已落地清单" used by the legacy importer.
    """
    blocks: list[tuple[str, str, list[tuple[str, str]]]] = []
    current_section = ""
    current_source = ""
    current_tokens: list[tuple[str, str]] = []

    def flush_block() -> None:
        nonlocal current_tokens
        if current_tokens:
            blocks.append((current_section, current_source, current_tokens))
        current_tokens = []

    for raw_line in str(markdown_text or "").splitlines():
        line = raw_line.rstrip()
        heading = _HEADING_RE.match(line)
        if heading:
            flush_block()
            current_section = heading.group(1).strip()
            current_source = ""
            continue
        source_from_line = _extract_source_path(line)
        if source_from_line:
            current_source = source_from_line
            continue
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        tokens = [value.strip() for value in _BACKTICK_RE.findall(cells[0]) if _is_testid_token(value)]
        for token in tokens:
            current_tokens.append((token, cells[1]))
    flush_block()

    rows: list[ParsedTestIdElement] = []
    normalized_filter = str(page_code_filter or "").strip().lower()
    for section, source_path, token_rows in blocks:
        tokens = [token for token, _ in token_rows]
        dominant_page = _dominant_page_code(tokens)
        for token, raw_type in token_rows:
            is_template = bool(_TEMPLATE_TOKEN_RE.search(token))
            element_code = _template_safe_code(token) if is_template else token
            derived_page = _normalize_page_code_for_testid(_derive_prefix(token))
            page_code = dominant_page if dominant_page and element_code.startswith(f"{dominant_page}-") else derived_page
            if normalized_filter and page_code != normalized_filter:
                continue
            business_type = _inventory_business_type(raw_type, token)
            page_name = _PAGE_NAME_BY_CODE.get(page_code) or _source_name(source_path, section)
            semantic_tags = ["data-testid-import", "inventory-export"]
            if page_code == "layout":
                semantic_tags.append("shared-layout")
            if is_template:
                semantic_tags.append("dynamic-row-template")
            rows.append(
                ParsedTestIdElement(
                    testid=token,
                    element_code=element_code,
                    page_code=page_code,
                    page_name=page_name,
                    source_path=source_path,
                    source_section=section,
                    business_type=business_type,
                    business_domain=_business_domain(token),
                    is_key_element=_is_key_element(token, business_type),
                    match_strategy="template" if is_template else "exact",
                    semantic_tags=semantic_tags,
                )
            )
    return rows

def _element_name(row: ParsedTestIdElement) -> str:
    safe = _template_safe_code(row.testid)
    exact_name = _ELEMENT_EXACT_NAMES.get(safe)
    if exact_name:
        return exact_name[:120]

    parts = [part for part in safe.split("-") if part]
    if parts and parts[0] in {row.page_code, *_SHARED_LAYOUT_PREFIXES}:
        parts = parts[1:]
    if parts and parts[0] in {"row"} and len(parts) > 1:
        parts = parts[1:]

    suffix = parts[-1] if parts else ""
    suffix_label = _ELEMENT_SUFFIX_LABELS.get(suffix, "")
    body_parts = parts[:-1] if suffix_label else parts
    labels: list[str] = []
    for part in body_parts:
        label = _ELEMENT_TOKEN_LABELS.get(part)
        if label and (not labels or labels[-1] != label):
            labels.append(label)
    if suffix_label:
        labels.append(suffix_label)
    if labels:
        return "".join(labels)[:120]
    return safe[:120]

def _should_replace_element_name(existing_name: str, next_name: str, element_code: str, testid: str) -> bool:
    current = str(existing_name or "").strip()
    candidate = str(next_name or "").strip()
    if not candidate:
        return False
    if not current:
        return True
    if current in {str(element_code or "").strip(), str(testid or "").strip(), _template_safe_code(testid)}:
        return True
    if not _contains_cjk(current) and _contains_cjk(candidate):
        return True
    return False

def _primary_locator_upsert(db: Session, *, element: PageElement, operator: str) -> None:
    locator_value = str(element.locator_value or "").strip()[:512]
    if not locator_value:
        return
    existing = PageObjectRepository(db).get_locator(
        element.id, element.locator_type, locator_value, str(element.role or "").strip()
    )
    if existing is None:
        db.add(
            PageElementLocator(
                page_element_id=element.id,
                locator_type=element.locator_type,
                locator_value=locator_value,
                role=str(element.role or "").strip(),
                locator_source=element.locator_source,
                priority=1,
                is_primary=True,
                health_status="unknown",
                verification_status="unknown",
                created_by=operator,
            )
        )
        return
    existing.priority = 1
    existing.is_primary = True
    existing.locator_source = element.locator_source
    db.add(existing)

def _cleanup_legacy_layout_pages(
    db: Session,
    *,
    project_code: str,
    client: str,
    layout_page: PageObject | None,
    operator: str,
) -> dict[str, int]:
    result = {
        "legacy_page_deleted_count": 0,
        "legacy_element_deleted_count": 0,
        "legacy_ref_migrated_count": 0,
        "legacy_element_skipped_count": 0,
    }
    if layout_page is None:
        return result
    for legacy_page_code in sorted(_SHARED_LAYOUT_PREFIXES - {"layout"}):
        legacy_page = PageObjectRepository(db).get_by_identity(project_code, client, legacy_page_code)
        if legacy_page is None:
            continue
        legacy_elements = PageObjectRepository(db).list_elements_by_page_object_id(legacy_page.id)
        deleted_element_ids: list[int] = []
        for legacy_element in legacy_elements:
            target = PageObjectRepository(db).get_element_by_code(layout_page.id, legacy_element.element_code)
            if target is None:
                result["legacy_element_skipped_count"] += 1
                continue
            refs = PageObjectRepository(db).list_refs_by_element_id(legacy_element.id)
            for ref in refs:
                duplicate = PageObjectRepository(db).get_ref(target.id, ref.reference_type, ref.reference_key)
                if duplicate is not None:
                    db.delete(ref)
                    continue
                ref.page_element_id = target.id
                ref.source = "import_migrated"
                db.add(ref)
                result["legacy_ref_migrated_count"] += 1
            page_object_service._write_governance_log(
                db,
                page_object=layout_page,
                entity_type="page_element",
                entity_key=target.element_code,
                action="import_legacy_layout_migrate",
                before_payload={
                    "legacy_page_code": legacy_page.page_code,
                    "legacy_element_id": legacy_element.id,
                    "legacy_element_code": legacy_element.element_code,
                },
                after_payload=page_object_service._element_governance_payload(target),
                operator=operator,
            )
            PageObjectRepository(db).delete_locators_by_element_ids([legacy_element.id])
            PageObjectRepository(db).delete_versions_by_element_ids([legacy_element.id])
            PageObjectRepository(db).delete_health_checks_by_element_ids([legacy_element.id])
            PageObjectRepository(db).delete_refs_by_element_ids([legacy_element.id])
            db.delete(legacy_element)
            deleted_element_ids.append(int(legacy_element.id))
            result["legacy_element_deleted_count"] += 1
        db.flush()
        remaining_count = PageObjectRepository(db).count_elements_by_page_object_id(legacy_page.id)
        if remaining_count == 0:
            db.delete(legacy_page)
            result["legacy_page_deleted_count"] += 1
        if deleted_element_ids:
            page_object_service._sync_page_object_metrics(db, page_object_id=layout_page.id)
    return result

def _build_preview(
    db: Session,
    *,
    project_code: str,
    client: str,
    rows: list[ParsedTestIdElement],
) -> dict[str, Any]:
    duplicate_counts: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row.page_code, row.element_code)
        duplicate_counts[key] = duplicate_counts.get(key, 0) + 1

    element_rows: list[dict[str, Any]] = []
    pages: dict[str, dict[str, Any]] = {}
    for row in rows:
        page = PageObjectRepository(db).get_by_identity(project_code, client, row.page_code)
        existing = None
        if page is not None:
            existing = PageObjectRepository(db).get_element_by_code(page.id, row.element_code)

        duplicate = duplicate_counts.get((row.page_code, row.element_code), 0) > 1
        if duplicate:
            action = "conflict"
            reason = "同一页面内 data-testid 重复出现"
        elif existing is None:
            action = "create"
            reason = ""
        elif str(existing.locator_type or "") != "data-testid" or str(existing.locator_value or "") != row.testid:
            action = "upgrade"
            reason = "已有元素将升级为 data-testid 定位"
        else:
            action = "skip"
            reason = "已是最新 data-testid 定位"
        next_element_name = _element_name(row)
        name_action = (
            "rename"
            if existing is not None
            and _should_replace_element_name(str(existing.element_name or ""), next_element_name, row.element_code, row.testid)
            else ""
        )

        page_summary = pages.setdefault(
            row.page_code,
            {
                "page_code": row.page_code,
                "normalized_page_code": row.page_code,
                "page_name": row.page_name,
                "source_path": row.source_path,
                "element_count": 0,
                "create_count": 0,
                "upgrade_count": 0,
                "skip_count": 0,
                "conflict_count": 0,
                "template_count": 0,
                "page_exists": page is not None,
            },
        )
        page_summary["element_count"] += 1
        page_summary[f"{action}_count"] += 1
        if row.match_strategy == "template":
            page_summary["template_count"] += 1
        element_rows.append(
            {
                **asdict(row),
                "normalized_page_code": row.page_code,
                "element_name": next_element_name,
                "name_action": name_action,
                "action": action,
                "reason": reason,
                "existing_locator_type": str(getattr(existing, "locator_type", "") or ""),
                "existing_locator_value": str(getattr(existing, "locator_value", "") or ""),
            }
        )

    return {
        "pages": list(pages.values()),
        "elements": element_rows,
        "summary": {
            "page_count": len(pages),
            "element_count": len(element_rows),
            "create_count": sum(1 for item in element_rows if item["action"] == "create"),
            "upgrade_count": sum(1 for item in element_rows if item["action"] == "upgrade"),
            "skip_count": sum(1 for item in element_rows if item["action"] == "skip"),
            "conflict_count": sum(1 for item in element_rows if item["action"] == "conflict"),
            "template_count": sum(1 for item in element_rows if item["match_strategy"] == "template"),
        },
    }

def create_import_preview(
    db: Session,
    *,
    project_code: str,
    client: str,
    source_type: str,
    data_testid_filename: str,
    data_testid_content: bytes,
    runtime_dom_filename: str = "",
    runtime_dom_content: bytes | None = None,
    page_code_filter: str = "",
) -> dict[str, Any]:
    if source_type not in {"data_testid_guidelines", "data_testid_inventory"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_type must be data_testid_guidelines or data_testid_inventory",
        )
    normalized_project_code = page_object_service._normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    normalized_client = normalize_client_code(client)
    if not data_testid_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="data-testid 导入文件为空，请重新选择有效的 Markdown 文件。",
        )
    try:
        markdown = data_testid_content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="data-testid 导入文件必须是 UTF-8 编码的 Markdown 文件。",
        ) from exc
    rows = (
        parse_data_testid_guidelines(markdown, page_code_filter=page_code_filter)
        if source_type == "data_testid_guidelines"
        else parse_data_testid_inventory(markdown, page_code_filter=page_code_filter)
    )
    if not rows:
        expected = "“已落地清单”章节" if source_type == "data_testid_guidelines" else "“按页面汇总”中的 data-testid 表格"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未解析到 {expected}，请确认上传了正确的导出文件。",
        )

    preview = _build_preview(db, project_code=normalized_project_code, client=normalized_client, rows=rows)
    import_id = uuid.uuid4().hex
    payload = {
        "import_id": import_id,
        "project_code": normalized_project_code,
        "client": normalized_client,
        "source_type": source_type,
        "status": "previewed",
        "created_at": _now_iso(),
        "applied_at": "",
        "files": {
            "data_testid_guidelines": {
                "filename": data_testid_filename,
                "sha256": _hash_bytes(data_testid_content),
                "size": len(data_testid_content),
            },
            "runtime_dom_selectors": {
                "filename": runtime_dom_filename,
                "sha256": _hash_bytes(runtime_dom_content or b"") if runtime_dom_content else "",
                "size": len(runtime_dom_content or b""),
                "used_as": "optional_validation_only" if runtime_dom_content else "",
            },
        },
        **preview,
        "apply_result": {},
    }
    _write_import(payload)
    return payload

def get_import(import_id: str) -> dict[str, Any]:
    return _read_import(import_id)

def apply_import(
    db: Session,
    *,
    import_id: str,
    operator: str = "admin",
    auto_approve: bool = True,
    upsert_policy: str = "upgrade_existing",
) -> dict[str, Any]:
    if not auto_approve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="auto_approve=false is not supported in v1")
    if upsert_policy != "upgrade_existing":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="upsert_policy must be upgrade_existing")

    payload = _read_import(import_id)
    project_code = str(payload.get("project_code") or "").strip()
    client = str(payload.get("client") or "").strip()
    test_project_service.ensure_project_active_for_write(db, project_code)
    created_pages = 0
    updated_pages = 0
    created_elements = 0
    upgraded_elements = 0
    skipped_elements = 0
    conflict_elements = 0
    touched_page_ids: set[int] = set()

    page_by_code: dict[str, PageObject] = {}
    for page_summary in payload.get("pages") or []:
        page_code = str(page_summary.get("page_code") or "").strip()
        if not page_code:
            continue
        page = PageObjectRepository(db).get_by_identity(project_code, client, page_code)
        if page is None:
            page = PageObject(
                project_code=project_code,
                client=client,
                page_code=page_code,
                page_name=str(page_summary.get("page_name") or page_code).strip()[:120],
                page_url="",
                route_pattern="",
                governance_status="active",
                testability_score=90,
                health_status=1,
                description=f"由 data-testid 清单导入：{page_summary.get('source_path') or '-'}",
                status="published",
                created_by=operator,
            )
            db.add(page)
            db.flush()
            created_pages += 1
        else:
            changed = False
            next_page_name = str(page_summary.get("page_name") or page_code).strip()[:120]
            if _should_replace_page_name(str(page.page_name or ""), next_page_name, page_code):
                page.page_name = next_page_name
                changed = True
            if not str(page.page_name or "").strip():
                page.page_name = str(page_summary.get("page_name") or page_code).strip()[:120]
                changed = True
            if str(page.status or "") != "published":
                page.status = "published"
                changed = True
            if str(page.governance_status or "") in {"", "draft"}:
                page.governance_status = "active"
                changed = True
            if changed:
                db.add(page)
                updated_pages += 1
        page_by_code[page_code] = page

    for item in payload.get("elements") or []:
        action = str(item.get("action") or "").strip()
        if action == "conflict":
            conflict_elements += 1
            continue
        page_code = str(item.get("page_code") or "").strip()
        page = page_by_code.get(page_code)
        if page is None:
            continue
        touched_page_ids.add(int(page.id))
        element_code = str(item.get("element_code") or "").strip()
        testid = str(item.get("testid") or "").strip()
        element = PageObjectRepository(db).get_element_by_code(page.id, element_code)
        semantic_tags = list(item.get("semantic_tags") or [])
        note = f"由 data-testid 清单导入；source_path={item.get('source_path') or '-'}"
        next_element_name = str(item.get("element_name") or "").strip() or _element_name(
            ParsedTestIdElement(
                testid=testid,
                element_code=element_code,
                page_code=page_code,
                page_name=str(item.get("page_name") or ""),
                source_path=str(item.get("source_path") or ""),
                source_section=str(item.get("source_section") or ""),
                business_type=str(item.get("business_type") or "container"),
                business_domain=str(item.get("business_domain") or ""),
                is_key_element=bool(item.get("is_key_element")),
                match_strategy=str(item.get("match_strategy") or "exact"),
                semantic_tags=semantic_tags,
            )
        )
        if element is None:
            element = PageElement(
                page_object_id=page.id,
                element_code=element_code,
                element_name=next_element_name,
                locator_type="data-testid",
                locator_value=testid,
                business_type=str(item.get("business_type") or "container"),
                business_domain=str(item.get("business_domain") or ""),
                aliases_json=[],
                semantic_tags_json=semantic_tags,
                locator_source="testid",
                match_strategy=str(item.get("match_strategy") or "exact"),
                stability_level="high",
                review_status="approved",
                route_scope="",
                anchor_required=False,
                is_key_element=bool(item.get("is_key_element")),
                testid_value=testid,
                governance_note=note,
                health_status=1,
                version=1,
                status="active",
                is_primary=True,
                owner=operator,
            )
            page_object_service._validate_formal_element_governance_qualification(element)
            db.add(element)
            db.flush()
            page_object_service._snapshot_element(
                db,
                element=element,
                changed_by=operator,
                change_summary=f"created from data-testid import {import_id}",
            )
            page_object_service._write_governance_log(
                db,
                page_object=page,
                entity_type="page_element",
                entity_key=element.element_code,
                action="import_create",
                before_payload={},
                after_payload=page_object_service._element_governance_payload(element),
                operator=operator,
            )
            _primary_locator_upsert(db, element=element, operator=operator)
            created_elements += 1
            continue

        before = page_object_service._element_governance_payload(element)
        changed = False
        updates = {
            "locator_type": "data-testid",
            "locator_value": testid,
            "locator_source": "testid",
            "match_strategy": str(item.get("match_strategy") or "exact"),
            "stability_level": "high",
            "review_status": "approved",
            "status": "active",
            "testid_value": testid,
            "business_type": str(item.get("business_type") or element.business_type or "container"),
            "business_domain": str(item.get("business_domain") or element.business_domain or ""),
            "is_key_element": bool(item.get("is_key_element")),
            "health_status": 1,
        }
        for field, value in updates.items():
            if getattr(element, field) != value:
                setattr(element, field, value)
                changed = True
        if _should_replace_element_name(str(element.element_name or ""), next_element_name, element_code, testid):
            element.element_name = next_element_name
            changed = True
        next_tags = sorted(set(page_object_service._json_list(element.semantic_tags_json)) | set(semantic_tags))
        if page_object_service._json_list(element.semantic_tags_json) != next_tags:
            element.semantic_tags_json = next_tags
            changed = True
        next_note = page_object_service._append_governance_note(str(element.governance_note or ""), note)
        if element.governance_note != next_note:
            element.governance_note = next_note
            changed = True
        if changed:
            page_object_service._validate_formal_element_governance_qualification(element)
            db.add(element)
            db.flush()
            page_object_service._snapshot_element(
                db,
                element=element,
                changed_by=operator,
                change_summary=f"upgraded from data-testid import {import_id}",
            )
            page_object_service._write_governance_log(
                db,
                page_object=page,
                entity_type="page_element",
                entity_key=element.element_code,
                action="import_upgrade",
                before_payload=before,
                after_payload=page_object_service._element_governance_payload(element),
                operator=operator,
            )
            _primary_locator_upsert(db, element=element, operator=operator)
            upgraded_elements += 1
        else:
            skipped_elements += 1

    legacy_cleanup = _cleanup_legacy_layout_pages(
        db,
        project_code=project_code,
        client=client,
        layout_page=page_by_code.get("layout"),
        operator=operator,
    )
    if page_by_code.get("layout") is not None:
        touched_page_ids.add(int(page_by_code["layout"].id))

    for page_id in touched_page_ids:
        page_object_service._sync_page_object_metrics(db, page_object_id=page_id)

    result = {
        "created_page_count": created_pages,
        "updated_page_count": updated_pages,
        "created_element_count": created_elements,
        "upgraded_element_count": upgraded_elements,
        "skipped_element_count": skipped_elements,
        "conflict_element_count": conflict_elements,
        **legacy_cleanup,
        "applied_at": _now_iso(),
        "operator": operator,
    }
    db.commit()
    payload["status"] = "applied"
    payload["applied_at"] = result["applied_at"]
    payload["apply_result"] = result
    _write_import(payload)
    return {**payload, "apply_result": result}
