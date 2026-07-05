from __future__ import annotations

import re
from typing import Any

from shared_backend.type_utils import dict_value as _dict_value, int_value as _int_value, list_value as _list_value


def dedup_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        key = str(item).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(key)
    return output


def clamp_confidence(value: float) -> float:
    try:
        numeric = float(value)
    except Exception:
        numeric = 0.0
    return round(max(0.0, min(1.0, numeric)), 2)


def safe_element_key(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return normalized or fallback


def requires_search_flow(requirement: str) -> bool:
    return any(token in str(requirement or "") for token in ["搜索", "查询", "筛选", "服务单号"])


def requires_dialog_flow(requirement: str) -> bool:
    return any(token in str(requirement or "") for token in ["弹窗", "对话框", "编辑", "审批", "审核", "确认", "提交"])


def build_surface_element_candidate(
    *,
    key: str,
    label: str,
    locator_type: str,
    locator_value: str,
    confidence: float,
    source: str,
    role: str = "",
    warnings: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    confidence_value = clamp_confidence(confidence)
    warning_list = [str(item).strip() for item in (warnings or []) if str(item).strip()]
    return {
        "key": key,
        "label": label,
        "locator_type": locator_type,
        "locator_value": locator_value,
        "role": role,
        "confidence": confidence_value,
        "warnings": warning_list,
        "requires_review": confidence_value < 0.75 or bool(warning_list),
        "source": source,
        "metadata": metadata or {},
    }


def build_surface_element_candidates(page: str, surface: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    load_state = _dict_value(surface.get("load_state"))
    auth_state = _dict_value(surface.get("auth_state"))
    route_mismatch = bool(load_state.get("route_mismatch"))
    login_failed = not bool(auth_state.get("login_success", True))
    stability = _dict_value(load_state.get("stability"))
    stability_status = str(stability.get("status", "")).strip().lower()

    def add_candidate(
        *,
        key: str,
        label: str,
        locator_type: str,
        locator_value: str,
        base_confidence: float,
        source: str,
        role: str = "",
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not str(locator_value).strip():
            return
        candidate_warnings = [str(item).strip() for item in (warnings or []) if str(item).strip()]
        confidence = base_confidence
        if route_mismatch:
            confidence -= 0.18
            candidate_warnings.append("页面最终停留路由与预期不一致。")
        if login_failed:
            confidence -= 0.12
            candidate_warnings.append("登录状态不稳定，元素识别可能受影响。")
        if stability_status in {"loading", "settling"}:
            confidence -= 0.08
            candidate_warnings.append("页面 DOM 尚未完全稳定。")
        candidates.append(
            build_surface_element_candidate(
                key=key,
                label=label,
                locator_type=locator_type,
                locator_value=locator_value,
                role=role,
                confidence=confidence,
                source=source,
                warnings=dedup_keep_order(candidate_warnings),
                metadata=metadata,
            )
        )

    page_title = str(surface.get("page_title", "")).strip()
    active_menu = str(surface.get("active_menu", "")).strip()
    search_placeholder = str(surface.get("search_placeholder", "")).strip()
    query_button_text = str(surface.get("query_button_text", "")).strip()
    primary_button_text = str(surface.get("primary_button_text", "")).strip()
    dialog_titles = [str(item).strip() for item in _list_value(surface.get("dialog_titles")) if str(item).strip()]
    frame_surface = _dict_value(surface.get("frame_surface"))
    frame_items = _list_value(frame_surface.get("frames"))

    add_candidate(
        key=f"{page}_menu",
        label="页面菜单",
        locator_type="role",
        role="menuitem",
        locator_value=active_menu or page_title,
        base_confidence=0.91 if active_menu else 0.76,
        source="active_menu" if active_menu else "page_title_fallback",
        warnings=[] if active_menu else ["菜单名称通过页面标题推断。"],
    )
    add_candidate(
        key=f"{page}_list_title",
        label="页面标题",
        locator_type="text",
        locator_value=page_title,
        base_confidence=0.89,
        source="page_title",
    )
    add_candidate(
        key="search_input",
        label="搜索输入框",
        locator_type="placeholder",
        locator_value=search_placeholder,
        base_confidence=0.94 if any(token in search_placeholder for token in ["搜索", "查询", "关键字", "商品", "订单", "服务单号"]) else 0.72,
        source="search_placeholder",
        warnings=[] if any(token in search_placeholder for token in ["搜索", "查询", "关键字", "商品", "订单", "服务单号"]) else ["搜索输入框由首个占位符推断。"],
    )
    add_candidate(
        key="search_button",
        label="查询按钮",
        locator_type="role",
        role="button",
        locator_value=query_button_text,
        base_confidence=0.93 if any(token in query_button_text for token in ["查询", "搜索"]) else 0.68,
        source="query_button_text",
        warnings=[] if any(token in query_button_text for token in ["查询", "搜索"]) else ["查询按钮文案不典型，建议确认。"],
    )
    if surface.get("has_table"):
        add_candidate(
            key=f"{page}_table",
            label="结果表格",
            locator_type="css",
            locator_value=".el-table",
            base_confidence=0.84,
            source="table_presence",
        )
    if surface.get("has_form"):
        add_candidate(
            key=f"{page}_form",
            label="表单区域",
            locator_type="css",
            locator_value=".el-form",
            base_confidence=0.83,
            source="form_presence",
        )
    add_candidate(
        key="save_button",
        label="主操作按钮",
        locator_type="role",
        role="button",
        locator_value=primary_button_text,
        base_confidence=0.87 if any(token in primary_button_text for token in ["保存", "提交", "确定", "确认"]) else 0.62,
        source="primary_button_text",
        warnings=[] if any(token in primary_button_text for token in ["保存", "提交", "确定", "确认"]) else ["主操作按钮文案不稳定或不典型。"],
    )
    if dialog_titles:
        add_candidate(
            key="dialog_title",
            label="弹窗标题",
            locator_type="text",
            locator_value=dialog_titles[0],
            base_confidence=0.78,
            source="dialog_title",
            warnings=["弹窗内容可能受操作上下文影响。"] if len(dialog_titles) > 1 else [],
        )

    for frame_index, frame in enumerate(frame_items[:2], start=1):
        if not isinstance(frame, dict):
            continue
        placeholders = [str(item).strip() for item in _list_value(frame.get("field_placeholders")) if str(item).strip()]
        buttons = [str(item).strip() for item in _list_value(frame.get("button_texts")) if str(item).strip()]
        if placeholders:
            add_candidate(
                key="frame_search_input" if frame_index == 1 else f"frame_{frame_index}_search_input",
                label=f"iframe {frame_index} 输入框",
                locator_type="placeholder",
                locator_value=placeholders[0],
                base_confidence=0.58,
                source="iframe_surface",
                warnings=["元素来自 iframe，建议人工确认。"],
            )
        if buttons:
            add_candidate(
                key="frame_primary_button" if frame_index == 1 else f"frame_{frame_index}_primary_button",
                label=f"iframe {frame_index} 按钮",
                locator_type="role",
                role="button",
                locator_value=buttons[0],
                base_confidence=0.54,
                source="iframe_surface",
                warnings=["元素来自 iframe，建议人工确认。"],
            )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in candidates:
        signature = (
            str(item.get("key", "")).strip(),
            str(item.get("locator_type", "")).strip(),
            str(item.get("locator_value", "")).strip(),
        )
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(item)
    return deduped


def surface_confidence_summary(surface: dict[str, Any]) -> dict[str, Any]:
    candidates = _list_value(surface.get("element_candidates"))
    confidences: list[float] = []
    low_confidence_items: list[dict[str, Any]] = []
    warnings = [str(item).strip() for item in surface.get("warnings", []) if str(item).strip()] if isinstance(surface.get("warnings"), list) else []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        confidence = clamp_confidence(item.get("confidence", 0))
        confidences.append(confidence)
        if confidence < 0.75 or bool(item.get("requires_review")):
            low_confidence_items.append(
                {
                    "key": str(item.get("key", "")).strip(),
                    "label": str(item.get("label", "")).strip() or str(item.get("key", "")).strip(),
                    "confidence": confidence,
                    "locator_type": str(item.get("locator_type", "")).strip(),
                    "locator_value": str(item.get("locator_value", "")).strip(),
                    "warnings": [str(entry).strip() for entry in item.get("warnings", []) if str(entry).strip()] if isinstance(item.get("warnings"), list) else [],
                }
            )
    confidence_value = clamp_confidence(sum(confidences) / len(confidences)) if confidences else 0.0
    requires_review = confidence_value < 0.75 or bool(low_confidence_items)
    return {
        "confidence": confidence_value,
        "warnings": dedup_keep_order(warnings),
        "low_confidence_items": low_confidence_items,
        "low_confidence_count": len(low_confidence_items),
        "requires_review": requires_review,
    }


def surface_inferred_elements(page: str, surface: dict[str, Any]) -> dict[str, dict[str, str]]:
    inferred: dict[str, dict[str, str]] = {}
    page_title_value = str(surface.get("page_title", "")).strip()
    menu_value = page_title_value or str(surface.get("active_menu", "")).strip()
    if menu_value:
        inferred[f"{page}_menu"] = {
            "locator_type": "role",
            "role": "menuitem",
            "locator_value": menu_value,
        }
    if page_title_value:
        inferred[f"{page}_list_title"] = {
            "locator_type": "text",
            "locator_value": page_title_value,
        }
    search_placeholder = str(surface.get("search_placeholder", "")).strip()
    if search_placeholder:
        inferred["search_input"] = {
            "locator_type": "placeholder",
            "locator_value": search_placeholder,
        }
    query_button_text = str(surface.get("query_button_text", "")).strip()
    if query_button_text:
        inferred["search_button"] = {
            "locator_type": "role",
            "role": "button",
            "locator_value": query_button_text,
        }
    if surface.get("has_table"):
        inferred[f"{page}_table"] = {
            "locator_type": "css",
            "locator_value": ".el-table",
        }
    if surface.get("has_form"):
        inferred[f"{page}_form"] = {
            "locator_type": "css",
            "locator_value": ".el-form",
        }
        primary_button_text = str(surface.get("primary_button_text", "")).strip()
        if primary_button_text:
            inferred["save_button"] = {
                "locator_type": "role",
                "role": "button",
                "locator_value": primary_button_text,
            }
    dialog_titles = [str(item).strip() for item in _list_value(surface.get("dialog_titles")) if str(item).strip()]
    if dialog_titles:
        dialog_title = dialog_titles[0]
        inferred["dialog_title"] = {
            "locator_type": "text",
            "locator_value": dialog_title,
        }
        primary_button_text = str(surface.get("primary_button_text", "")).strip()
        if primary_button_text:
            inferred["dialog_primary_button"] = {
                "locator_type": "role",
                "role": "button",
                "locator_value": primary_button_text,
            }
    frame_surface = _dict_value(surface.get("frame_surface"))
    frame_items = _list_value(frame_surface.get("frames"))
    for frame_index, frame in enumerate(frame_items[:3], start=1):
        if not isinstance(frame, dict):
            continue
        placeholders = [str(item).strip() for item in _list_value(frame.get("field_placeholders")) if str(item).strip()]
        buttons = [str(item).strip() for item in _list_value(frame.get("button_texts")) if str(item).strip()]
        titles = [str(item).strip() for item in _list_value(frame.get("title_candidates")) if str(item).strip()]
        if placeholders:
            placeholder = placeholders[0]
            element_key = "frame_search_input" if frame_index == 1 else f"frame_{frame_index}_search_input"
            inferred[element_key] = {
                "locator_type": "placeholder",
                "locator_value": placeholder,
            }
        if buttons:
            button_text = buttons[0]
            element_key = "frame_primary_button" if frame_index == 1 else f"frame_{frame_index}_primary_button"
            inferred[element_key] = {
                "locator_type": "role",
                "role": "button",
                "locator_value": button_text,
            }
        if titles:
            title_text = titles[0]
            key_prefix = safe_element_key(title_text, f"frame_{frame_index}_title")
            inferred[f"{key_prefix}_title"] = {
                "locator_type": "text",
                "locator_value": title_text,
            }
    return inferred


def _semantic_business_domain(page: str, surface: dict[str, Any]) -> str:
    page_key = str(page or "").strip().lower()
    title = f"{surface.get('page_title', '')} {surface.get('active_menu', '')}".lower()
    if page_key in {"product", "addproduct"} or "商品" in title:
        return "product"
    if page_key in {"order"} or "订单" in title:
        return "order"
    if page_key in {"returnapply"} or "退货" in title:
        return "aftersales"
    return "generic"


def _semantic_page_type(surface: dict[str, Any]) -> tuple[str, list[str]]:
    has_table = bool(surface.get("has_table"))
    has_form = bool(surface.get("has_form"))
    has_dialog = bool(surface.get("has_dialog"))
    reason_codes: list[str] = []
    if has_dialog:
        reason_codes.append("has_dialog")
    if has_table:
        reason_codes.append("has_table")
    if has_form:
        reason_codes.append("has_form")
    if has_dialog and has_form:
        return "dialog_form", reason_codes
    if has_table and has_form:
        return "hybrid", reason_codes
    if has_table:
        return "list", reason_codes
    if has_form:
        return "form", reason_codes
    if has_dialog:
        return "dialog", reason_codes
    return "unknown", reason_codes


def build_page_semantic_model(
    *,
    page: str,
    surface: dict[str, Any] | None,
    page_object: dict[str, Any] | None = None,
    requested_url: str = "",
) -> dict[str, Any]:
    normalized_surface = surface if isinstance(surface, dict) else {}
    normalized_page_object = page_object if isinstance(page_object, dict) else {}
    page_type, reason_codes = _semantic_page_type(normalized_surface)
    page_key = str(page or "").strip().lower()
    if page_type == "unknown":
        if page_key in {"product", "order", "returnapply"}:
            page_type = "list"
            reason_codes.append("page_slug_list_hint")
        elif page_key in {"addproduct"}:
            page_type = "form"
            reason_codes.append("page_slug_form_hint")
    business_domain = _semantic_business_domain(page, normalized_surface)

    search_placeholder = str(normalized_surface.get("search_placeholder", "")).strip()
    query_button_text = str(normalized_surface.get("query_button_text", "")).strip()
    primary_button_text = str(normalized_surface.get("primary_button_text", "")).strip()
    load_state = _dict_value(normalized_surface.get("load_state"))
    auth_state = _dict_value(normalized_surface.get("auth_state"))
    route_mismatch = bool(load_state.get("route_mismatch"))
    login_success = bool(auth_state.get("login_success", True))
    frame_surface = _dict_value(normalized_surface.get("frame_surface"))
    blocked_frame_count = _int_value(frame_surface.get("blocked_count", 0))
    stability = _dict_value(load_state.get("stability"))
    stability_status = str(stability.get("status", "")).strip().lower()

    primary_actions: list[str] = []
    if search_placeholder or query_button_text:
        primary_actions.append("search")
        reason_codes.append("search_flow")
    if normalized_surface.get("has_table"):
        primary_actions.append("view_results")
    if normalized_surface.get("has_form"):
        primary_actions.append("edit_form")
    if primary_button_text:
        primary_actions.append("submit")
        reason_codes.append("primary_action_button")
    if normalized_surface.get("has_dialog"):
        primary_actions.append("confirm_dialog")
    primary_actions = dedup_keep_order(primary_actions)

    if page_type in {"list", "hybrid"} and "search" in primary_actions:
        primary_goal = "query_and_browse"
    elif page_type in {"form", "dialog_form"} and "submit" in primary_actions:
        primary_goal = "edit_and_submit"
    elif page_type == "dialog":
        primary_goal = "review_and_confirm"
    elif page_type == "list":
        primary_goal = "browse_list"
    elif page_type == "form":
        primary_goal = "fill_form"
    else:
        primary_goal = "inspect_page"

    warnings: list[str] = []
    confidence = 0.9
    if page_type == "unknown":
        confidence -= 0.24
        warnings.append("页面类型信号不足，语义仅能粗略判断。")
        reason_codes.append("page_type_unknown")
    elif page_type == "hybrid":
        confidence -= 0.12
        warnings.append("页面同时包含列表和表单信号，语义边界偏模糊。")
        reason_codes.append("mixed_structure")
    if business_domain == "generic":
        confidence -= 0.10
        warnings.append("业务域未能从页面标识中稳定识别。")
        reason_codes.append("generic_domain")
    if route_mismatch:
        confidence -= 0.15
        warnings.append("当前页面路由与请求路由不一致。")
        reason_codes.append("route_mismatch")
    if not login_success:
        confidence -= 0.12
        warnings.append("登录状态不稳定，页面语义可能受重定向影响。")
        reason_codes.append("login_unstable")
    if blocked_frame_count > 0:
        confidence -= 0.08
        warnings.append("部分 iframe 无法访问，页面语义存在盲区。")
        reason_codes.append("iframe_blocked")
    if stability_status and stability_status != "stable":
        confidence -= 0.08
        warnings.append("页面 DOM 尚未稳定，语义判断需要谨慎。")
        reason_codes.append("surface_not_stable")
    if not primary_actions:
        confidence -= 0.06
        warnings.append("未提取到稳定的主交互动作。")
        reason_codes.append("no_primary_action")

    object_summary = _dict_value(normalized_page_object.get("summary"))
    missing_required = _int_value(object_summary.get("missing_required_count", 0))
    if missing_required > 0:
        confidence -= 0.06
        warnings.append(f"Page Object 仍缺少 {missing_required} 个必需元素，语义归类应谨慎使用。")
        reason_codes.append("page_object_gap")

    confidence = clamp_confidence(confidence)
    warnings = dedup_keep_order(warnings)
    reason_codes = dedup_keep_order(reason_codes)
    requires_review = confidence < 0.75 or bool(warnings)

    return {
        "version": "PageSemanticModelV1",
        "schema_version": "page-semantic-model.v1",
        "page": str(page or "").strip(),
        "requested_url": str(requested_url or normalized_surface.get("requested_url", "")).strip(),
        "page_type": page_type,
        "business_domain": business_domain,
        "primary_goal": primary_goal,
        "primary_actions": primary_actions,
        "reason_codes": reason_codes,
        "signals": {
            "has_table": bool(normalized_surface.get("has_table")),
            "has_form": bool(normalized_surface.get("has_form")),
            "has_dialog": bool(normalized_surface.get("has_dialog")),
            "has_search": bool(search_placeholder or query_button_text),
            "has_primary_action": bool(primary_button_text),
            "route_mismatch": route_mismatch,
        },
        "summary": {
            "page_type": page_type,
            "business_domain": business_domain,
            "primary_goal": primary_goal,
            "primary_actions": primary_actions,
            "reason_codes": reason_codes,
            "confidence": confidence,
            "warnings": warnings,
            "requires_review": requires_review,
        },
        "confidence": confidence,
        "warnings": warnings,
        "requires_review": requires_review,
        "metadata": {
            "generator": "page_analysis_rules.build_page_semantic_model",
            "semantic_stage": "rule_first",
        },
    }


def required_page_elements(page: str, requirement: str, surface: dict[str, Any]) -> list[str]:
    required = [
        "login_button",
        f"{page}_menu",
    ]
    if str(surface.get("page_title", "")).strip():
        required.append(f"{page}_list_title")
    if surface.get("has_table"):
        required.append(f"{page}_table")
    if requires_search_flow(requirement):
        required.extend(["search_input", "search_button"])
        frame_surface = _dict_value(surface.get("frame_surface"))
        if _int_value(frame_surface.get("accessible_count", 0)) > 0:
            required.append("frame_search_input")
    if page == "addproduct" or any(token in str(requirement or "") for token in ["添加", "新增", "保存", "提交"]):
        required.extend(["addproduct_form", "save_button"])
    if requires_dialog_flow(requirement) and any(str(item).strip() for item in _list_value(surface.get("dialog_titles")) if str(item).strip()):
        required.extend(["dialog_title", "dialog_primary_button"])
    return dedup_keep_order(required)


def _normalize_field_items(raw_fields: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    if not isinstance(raw_fields, list):
        return normalized
    for item in raw_fields:
        if not isinstance(item, dict):
            continue
        placeholder = str(item.get("placeholder", "")).strip()
        if not placeholder:
            continue
        normalized.append(
            {
                "placeholder": placeholder,
                "name": str(item.get("name", "")).strip(),
                "cls": str(item.get("cls", "")).strip(),
            }
        )
    return normalized


def _normalize_button_items(raw_buttons: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    if not isinstance(raw_buttons, list):
        return normalized
    for item in raw_buttons:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        normalized.append(
            {
                "text": text,
                "cls": str(item.get("cls", "")).strip(),
            }
        )
    return normalized


def _normalize_menu_items(raw_menus: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    if not isinstance(raw_menus, list):
        return normalized
    for item in raw_menus:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        normalized.append(
            {
                "text": text,
                "cls": str(item.get("cls", "")).strip(),
            }
        )
    return normalized


def _normalize_title_candidates(raw_titles: Any) -> list[str]:
    if not isinstance(raw_titles, list):
        return []
    return [str(item).strip() for item in raw_titles if str(item).strip()]


def pick_search_placeholder(fields: list[dict[str, str]]) -> str:
    for item in fields:
        placeholder = str(item.get("placeholder", "")).strip()
        if any(token in placeholder for token in ["服务单号", "搜索", "关键字", "关键词"]):
            return placeholder
    if fields:
        return str(fields[0].get("placeholder", "")).strip()
    return ""


def pick_query_button_text(buttons: list[dict[str, str]]) -> str:
    for item in buttons:
        text = str(item.get("text", "")).strip()
        if any(token in text for token in ["查询", "搜索"]):
            return text
    if buttons:
        return str(buttons[0].get("text", "")).strip()
    return ""


def pick_primary_button_text(buttons: list[dict[str, str]]) -> str:
    for item in buttons:
        text = str(item.get("text", "")).strip()
        if any(token in text for token in ["保存", "提交", "确定", "确认"]):
            return text
    return ""


def pick_page_title(titles: list[str]) -> str:
    page_title = ""
    for title in titles:
        normalized = str(title).strip()
        if normalized and normalized not in {"首页", "/"}:
            page_title = normalized
    if not page_title and titles:
        page_title = str(titles[-1]).strip()
    return page_title


def pick_active_menu(menu_items: list[dict[str, str]], page_title: str) -> str:
    active_menu = ""
    for item in menu_items:
        cls = str(item.get("cls", "")).strip()
        text = str(item.get("text", "")).strip()
        if "is-active" in cls and text:
            active_menu = text
            break
    if not active_menu and page_title:
        active_menu = page_title
    if not active_menu and menu_items:
        active_menu = str(menu_items[0].get("text", "")).strip()
    if active_menu:
        lines = [line.strip() for line in active_menu.splitlines() if line.strip()]
        if lines:
            active_menu = lines[-1]
    if page_title and page_title in active_menu:
        active_menu = page_title
    return active_menu


def build_surface_result_from_snapshot(
    *,
    page_url: str,
    payload: dict[str, Any],
    frame_surface: dict[str, Any] | None,
    login_url: str,
    login_attempted: bool,
    login_succeeded: bool,
    redirected_to_login: bool,
    login_network_idle_reached: bool,
    target_network_idle_reached: bool,
    marker_selector: str,
    selector_wait_status: str,
    requested_route: str,
    final_route: str,
    route_mismatch: bool,
    stability: dict[str, Any] | None,
) -> dict[str, Any]:
    snapshot = payload if isinstance(payload, dict) else {}
    frame_snapshot = frame_surface if isinstance(frame_surface, dict) else {"frames": [], "accessible_count": 0, "blocked_count": 0}
    stability_snapshot = stability if isinstance(stability, dict) else {"status": "unknown", "stable": False, "sample_count": 0}

    fields = _normalize_field_items(snapshot.get("fields"))
    buttons = _normalize_button_items(snapshot.get("buttons"))
    menu_items = _normalize_menu_items(snapshot.get("menuItems"))
    titles = _normalize_title_candidates(snapshot.get("titleCandidates"))

    frame_items = _list_value(frame_snapshot.get("frames"))
    accessible_frame_count = _int_value(frame_snapshot.get("accessible_count", 0))
    blocked_frame_count = _int_value(frame_snapshot.get("blocked_count", 0))

    for item in frame_items:
        if not isinstance(item, dict):
            continue
        for placeholder in _list_value(item.get("field_placeholders")):
            value = str(placeholder).strip()
            if value:
                fields.append({"placeholder": value, "name": "", "cls": "iframe-surface"})
        for button_text in _list_value(item.get("button_texts")):
            value = str(button_text).strip()
            if value:
                buttons.append({"text": value, "cls": "iframe-surface"})
        for title_text in _list_value(item.get("title_candidates")):
            value = str(title_text).strip()
            if value:
                titles.append(value)

    search_placeholder = pick_search_placeholder(fields)
    query_button_text = pick_query_button_text(buttons)
    primary_button_text = pick_primary_button_text(buttons)
    page_title = pick_page_title(titles)
    active_menu = pick_active_menu(menu_items, page_title)

    final_url = str(snapshot.get("url", "")).strip()
    warnings: list[str] = []
    if not login_succeeded:
        warnings.append("login_may_have_failed")
    if redirected_to_login:
        warnings.append("redirected_to_login")
    if not marker_selector:
        warnings.append("no_stable_marker_detected")
    if route_mismatch:
        warnings.append("route_mismatch")
    iframe_count = _int_value(snapshot.get("iframeCount", 0))
    if iframe_count > 0:
        warnings.append("iframe_detected")
    if blocked_frame_count > 0:
        warnings.append("iframe_access_limited")
    loading_mask_count = _int_value(snapshot.get("loadingMaskCount", 0))
    if loading_mask_count > 0:
        warnings.append("loading_indicator_present")
    stability_status = str(stability_snapshot.get("status", "unknown")).strip() or "unknown"
    if stability_status != "stable":
        warnings.append("surface_not_stable")

    dialog_titles = [str(item).strip() for item in _list_value(snapshot.get("dialogTitles")) if str(item).strip()][:10]

    top_level_warnings: list[str] = []
    if route_mismatch:
        top_level_warnings.append("页面最终停留路由与请求 URL 不一致。")
    if redirected_to_login:
        top_level_warnings.append("页面被重定向到登录页，当前页面元素可能不完整。")
    if loading_mask_count > 0:
        top_level_warnings.append("页面仍存在加载态遮罩，元素识别稳定性下降。")
    if blocked_frame_count > 0:
        top_level_warnings.append("部分 iframe 无法访问，页面分析存在盲区。")
    if stability_status != "stable":
        top_level_warnings.append("页面 DOM 尚未完全稳定。")

    return {
        "url": final_url,
        "title": str(snapshot.get("title", "")).strip(),
        "search_placeholder": search_placeholder,
        "query_button_text": query_button_text,
        "primary_button_text": primary_button_text,
        "page_title": page_title,
        "active_menu": active_menu,
        "has_table": bool(snapshot.get("hasTable", False)),
        "has_form": bool(snapshot.get("hasForm", False)),
        "has_dialog": bool(snapshot.get("hasDialog", False)),
        "dialog_titles": dialog_titles,
        "iframe_count": iframe_count,
        "frame_surface": {
            "accessible_count": accessible_frame_count,
            "blocked_count": blocked_frame_count,
            "frames": frame_items[:5],
        },
        "loading_mask_count": loading_mask_count,
        "body_text_length": _int_value(snapshot.get("bodyTextLength", 0)),
        "auth_state": {
            "login_url": login_url,
            "login_attempted": login_attempted,
            "login_success": login_succeeded,
            "redirected_to_login": redirected_to_login,
        },
        "load_state": {
            "login_network_idle_reached": login_network_idle_reached,
            "target_network_idle_reached": target_network_idle_reached,
            "marker_selector": marker_selector,
            "selector_wait_status": selector_wait_status,
            "requested_route": requested_route,
            "final_route": final_route,
            "route_mismatch": route_mismatch,
            "stability": stability_snapshot,
        },
        "analysis": {
            "field_count": len(fields),
            "button_count": len(buttons),
            "menu_count": len(menu_items),
            "title_candidate_count": len(titles),
            "dialog_count": len(dialog_titles),
            "iframe_count": iframe_count,
            "frame_accessible_count": accessible_frame_count,
            "frame_blocked_count": blocked_frame_count,
            "loading_mask_count": loading_mask_count,
            "stability_status": stability_status,
            "warnings": dedup_keep_order(warnings),
            "surface_health": "warn" if warnings else "ok",
        },
        "warnings": dedup_keep_order(top_level_warnings),
        "requested_url": str(page_url).strip(),
    }
