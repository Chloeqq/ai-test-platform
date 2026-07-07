from __future__ import annotations

# ── 路径初始化：直接运行此文件时，项目根不在 sys.path ────────────────────
# pytest 有 pytest.ini 的 pythonpath 配置，跳过此逻辑。
import os as _os, sys as _sys

import shared_backend

_proj = _os.path.dirname(_os.path.abspath(__file__))
for _ in range(5):              # .../apps/web_ui_service/app/services/wg_api → project root
    _proj = _os.path.dirname(_proj)
if _proj not in _sys.path:
    _sys.path.insert(0, _proj)
_web_ui = _os.path.join(_proj, "apps", "web_ui_service")
if _web_ui not in _sys.path:
    _sys.path.insert(0, _web_ui)

import logging
from pathlib import Path
import re
from typing import Any

from shared_backend.case_ids import normalize_case_id

from shared_backend.type_utils import dict_value as _dict_value, str_value as _normalized_text

from app.services import workbench_asset_service, workbench_state_store

from .context import WorkbenchContext
from . import preview_store
from . import constants as _c

from shared_backend.text_utils import has_negation_before, extract_error_message
from shared_backend.step_fields import (
    ACTION_INPUT, ACTION_CLICK, ACTION_GOTO,
    ACTION_ASSERT_VISIBLE, ACTION_ASSERT_TEXT, ACTION_ASSERT_URL,
    HINT_SEP_ACTION, HINT_SEP_VALUE, HINT_INPUT_ACTIONS,
    format_steps_hint,
)



LOGGER = logging.getLogger(__name__)



def _list_text(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for raw in value:
        text = _normalized_text(raw)
        if text and text not in items:
            items.append(text)
    return items


def _existing_test_point_asset_ids(project: str) -> list[str]:
    state_root = workbench_state_store.WEB_UI_STATE_ROOT / "test-points"
    project_dir = workbench_asset_service.state_project_dir(project, state_root=state_root)
    ids: list[str] = []
    for folder in (project_dir, project_dir / "plans"):
        if not folder.exists():
            continue
        for path in folder.glob("*.json"):
            case_id = _normalized_text(path.stem)
            if case_id and case_id not in ids:
                ids.append(case_id)
    return ids


def _preview_requirement(preview_id: str) -> tuple[str, dict[str, Any]]:
    normalized_preview_id = _normalized_text(preview_id)
    if not normalized_preview_id:
        return "", {}
    snapshot = preview_store.load_preview_snapshot(normalized_preview_id)
    preview_payload = _dict_value(snapshot.get("preview_payload"))
    item = _dict_value(preview_payload.get("item"))
    requirement_spec = _dict_value(item.get("requirement_spec"))
    requirement = (
        _normalized_text(requirement_spec.get("normalized_requirement"))
        or _normalized_text(requirement_spec.get("raw_requirement"))
        or _normalized_text(item.get("normalized_requirement"))
        or _normalized_text(item.get("raw_requirement"))
        or _normalized_text(snapshot.get("effective_requirement"))
    )
    return requirement, requirement_spec


def _candidate_snapshot(candidate: dict[str, Any]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for key in _c.CANDIDATE_SNAPSHOT_KEYS:
        value = candidate.get(key)
        if isinstance(value, dict):
            if value:
                snapshot[key] = value
            continue
        if isinstance(value, list):
            rows = _list_text(value)
            if rows:
                snapshot[key] = rows
            continue
        text = _normalized_text(value)
        if text:
            snapshot[key] = text
    return snapshot


_LOGIN_ELEMENT_RULES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("login-username-input", "用户名输入框", "username", ("用户名输入框", "账号输入框", "用户名", "账号")),
    ("login-password-toggle-btn", "显示/隐藏眼睛图标", "", ("密码可见性切换", "密码显隐", "显示密码", "隐藏密码", "密码可见", "明文", "密文", "眼睛图标", "眼睛", "eyeIcon")),
    ("login-password-input", "密码输入框", "password", ("密码输入框", "密码")),
    ("login-submit-btn", "登录按钮", "", ("登录按钮", "登录")),
    ("home-page", "首页菜单", "", ("首页菜单", "首页", "工作台首页")),
)


def _login_element_from_text(text: str) -> tuple[str, str, str] | None:
    """从测试点自然语言中识别登录页元素，避免把候选步骤长期停留在 candidate_step。"""
    normalized = _normalized_text(text)
    for element_code, element_name, data_key, aliases in _LOGIN_ELEMENT_RULES:
        if any(alias in normalized for alias in aliases):
            return element_code, element_name, data_key
    return None


def _input_value_from_text(text: str) -> tuple[bool, Any]:
    """只提取步骤文本中明确写出的输入值；不在代码里猜账号、密码或边界值。"""
    normalized = _normalized_text(text)
    if any(token in normalized for token in _c.EMPTY_INPUT_TOKENS):
        return True, ""
    if _c.SPACE_INPUT_TOKEN in normalized:
        return True, " "
    quoted = re.search(shared_backend.text_utils.QUOTED_TEXT_PATTERN, normalized)
    if quoted is not None:
        return True, quoted.group(1)
    matched = re.search(_c.INPUT_VALUE_PATTERN, normalized)
    if matched is not None:
        return True, matched.group(1)
    return False, None


def _password_visibility_assertion_step(expected: str) -> dict[str, Any] | None:
    """密码可见性切换：根据预期文本推断切换方向，生成校验密码输入框 type 属性的断言步骤。

    明文(可见) → input[type=text]；密文(掩码) → input[type=password]。
    预期文本两个方向都没提到则无法判断方向，不生成断言（避免猜错）。
    """
    normalized = _normalized_text(expected)
    # "从明文变为密文"这类文本里明文/密文都会出现，目标状态是后出现的那个，
    # 取最后一次出现的位置判断，而不是简单"任一命中"（会被源状态词误判）。
    plain_pos = normalized.rfind("明文")
    masked_pos = normalized.rfind("密文")
    if plain_pos < 0 and masked_pos < 0:
        if any(token in normalized for token in ("可见", "显示密码")):
            expected_type = "text"
        elif any(token in normalized for token in ("掩码", "隐藏密码")):
            expected_type = "password"
        else:
            return None
    elif plain_pos > masked_pos:
        expected_type = "text"
    else:
        expected_type = "password"
    return {
        "action": "assert_attribute",
        "target": "element:login-password-input",
        "target_name": "密码输入框",
        "attribute": "type",
        "value": expected_type,
        "raw_text": expected,
    }


def _password_visibility_precondition_setup(precondition: str) -> list[dict[str, Any]]:
    """前置条件描述"密码已切换为明文/密文"时，补建立该 UI 态的步骤。

    这种前置条件本质是"先在本页面交互一次"，而不是登录/账号状态/SQL 这类
    跨会话状态，结构化前置条件编译器（generate_pipeline_precondition.py）
    无法表达。用例必须自包含执行（不依赖另一条用例先跑），所以在生成阶段
    直接把"输入密码 + 必要时点一次眼睛图标"补成本用例自己的步骤。
    """
    normalized = _normalized_text(precondition)
    if not any(token in normalized for token in _c.PASSWORD_VISIBILITY_TOKENS):
        return []
    plain_pos = max(normalized.rfind("明文"), normalized.rfind("可见"))
    masked_pos = max(normalized.rfind("密文"), normalized.rfind("隐藏"))
    if plain_pos < 0 and masked_pos < 0:
        return []
    target_state = "text" if plain_pos > masked_pos else "password"
    setup: list[dict[str, Any]] = [
        {
            "action": "input",
            "target": "element:login-password-input",
            "target_name": "密码输入框",
            "data_ref": "password",
            "value": _c.DEFAULT_TEST_PASSWORD,
            "raw_text": "建立前置条件：先输入密码",
        }
    ]
    # 密码输入框默认就是掩码态（type=password），只有目标前置态是"明文"
    # 时才需要先点一次眼睛图标；目标是"密文"则默认态已满足，不用多点。
    if target_state == "text":
        setup.append(
            {
                "action": "click",
                "target": "element:login-password-toggle-btn",
                "target_name": "显示/隐藏眼睛图标",
                "raw_text": "建立前置条件：点击眼睛图标切换为明文",
            }
        )
    return setup


def _data_ref_for_element(element_code: str, fallback_key: str) -> str:
    """element_code → data key，委托 element_naming 统一推导。"""
    from shared_backend.element_naming import element_data_key
    key = element_data_key(element_code)
    return key or _normalized_text(fallback_key).removesuffix("_input").removesuffix("-input") or "input_value"


def _append_unique(items: list[str], value: str) -> None:
    normalized = _normalized_text(value)
    if normalized and normalized not in items:
        items.append(normalized)


def _canonical_login_involved_elements(involved_elements: list[str], involved_codes: list[str]) -> list[str]:
    """登录页结构化后以 element_code 为准，中文元素名只作为识别输入，不再混入正式字段。"""
    canonical: list[str] = []
    for element_code in involved_codes:
        _append_unique(canonical, element_code)
    for raw_element in involved_elements:
        normalized = _normalized_text(raw_element)
        if not normalized or normalized in canonical:
            continue
        matched = _login_element_from_text(normalized)
        if matched is None:
            continue
        element_code = matched[0]
        if element_code not in canonical:
            canonical.append(element_code)
    return canonical


def _structured_steps_from_candidate(
    *,
    candidate: dict[str, Any],
    steps: list[str],
    expected: str,
) -> tuple[list[dict[str, Any]], list[str], dict[str, dict[str, Any]], list[str], list[str]]:
    """将候选测试点步骤治理成 DSL V1.1 可消费的结构化步骤、steps_hint 与 data。

    === 入参示例（intent-04 "账号为空点击登录"）===

    candidate = {
        "title": "账号为空点击登录",
        "intent_type": "negative",
        "precondition": "用户未登录，处于登录页",
        "steps": ["清空账号输入框", "在密码输入框输入任意密码", "点击登录按钮"],
        "steps_hint": ["input:username=", "input:password=123456", "click:loginButton"],
        "expected": '页面提示"请输入账号"',
        "involved_elements": ["username", "password", "loginButton"],
    }
    steps = ["清空账号输入框", "在密码输入框输入任意密码", "点击登录按钮"]
    expected = '页面提示"请输入账号"'

    === 处理流程 ===

    对每个自然语言 step_text，依次尝试匹配：
    1. input 分支：step_text 含("输入","填写","清空","留空") 且 _login_element_from_text 识别到元素
       → 调用 _input_value_from_text 提取输入值
       → has_value=True: 写入 step.value、data、steps_hint、involved_codes
       → has_value=False: 只写入 structured_steps（target+elem），不写 steps_hint/data
          ⚠ 已知问题(2026-07-05): "任意密码"等中文值无法被 _input_value_from_text
             的正则提取（正则只匹配 [A-Za-z0-9_@.\\-]+），导致密码步骤在 steps_hint
             和 data 中缺失
    2. click 分支：step_text 含"点击" 且 _login_element_from_text 识别到元素
       → 写入 steps_hint、involved_codes
       → 如果元素是 login-password-toggle-btn，额外生成 assert_attribute 步骤
    3. goto 分支：step_text 含("刷新","访问首页","进入首页")
       → 写入 goto:#/home
    4. 兜底：以上均不匹配 → 标记为 candidate_step（需人工处理）

    处理完所有 steps 后，根据 expected_text 的 token 匹配追加断言步骤：
    - "成功登录"/"跳转到首页"/"首页菜单可见"/"进入首页" → assert_visible
    - "提示"/"错误"/"请输入"/"失败" → assert_text（提取错误文案）
      ⚠ 已知问题(2026-07-05): assert_text 的 steps_hint 格式为
         "assert_text:<文案>"，缺少 "<target>=" 前缀，导致编译时 target 为空
    - "拦截"/"登录页面"/"登录页" → assert_url（需通过 _has_negation_before 排除否定语境）

    === 返回值 ===
    tuple[structured_steps, steps_hint, data, warnings, involved_codes]

    structured_steps: list[dict] — 结构化步骤列表，每项含 action/target/value/raw_text
        例: [
          {action:"input", target:"element:login-username-input", value:"", raw_text:"清空账号输入框"},
          {action:"input", target:"element:login-password-input", value:None, raw_text:"在密码输入框输入任意密码"},
          {action:"click", target:"element:login-submit-btn", raw_text:"点击登录按钮"},
          {action:"assert_text", value:"请输入账号", raw_text:'页面提示"请输入账号"'},  ← 缺 target 字段!
        ]
        注意: has_value=False 的步骤 value 字段不写入

    steps_hint: list[str] — 编译提示序列，格式为 "action:target=value"
        例: ["input:用户名输入框=", "click:登录按钮", "assert_text:请输入账号"]
        ⚠ 密码步骤缺失（has_value=False 时未写入）
        ⚠ assert_text 格式错误（缺 "target=" 前缀）

    data: dict — 变量数据字典，key 为 element_code 对应的 data_ref
        例: {"username": {"source_type":"inline", "value":""}}
        ⚠ 密码数据缺失

    warnings: list[str] — 编译过程中产生的警告信息
        例: ["密码输入框 输入步骤缺少明确测试数据：在密码输入框输入任意密码"]

    involved_codes: list[str] — 解析出的 element codes
        例: ["login-username-input", "login-submit-btn"]
        ⚠ login-password-input 缺失（has_value=False 时未写入 involved_codes）
    """
    hint_value_map: dict[str, str] = {}
    structured_steps: list[dict[str, Any]] = []
    steps_hint: list[str] = []
    data: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    involved_codes: list[str] = []

    precondition_setup = _password_visibility_precondition_setup(_normalized_text(candidate.get("precondition")))

    for setup_step in precondition_setup:
        structured_steps.append(setup_step)
        if setup_step["action"] == "input":
            data["password"] = {"source_type": "inline", "value": setup_step["value"]}
            _append_unique(steps_hint, f"input:{setup_step['target_name']}={setup_step['value']}")
        elif setup_step["action"] == "click":
            _append_unique(steps_hint, f"click:{setup_step['target_name']}")
        _append_unique(involved_codes, setup_step["target"].removeprefix("element:"))

        # 步骤 0（新增）：预解析 AI 的 steps_hint，提取 input 步骤的精确值。
        # 当 _input_value_from_text 对中文值（如"任意密码"）提取失败时，
        # 用这个 map 做兜底查找。
        # 输入: ["input:username=", "input:password=123456", "click:loginButton"]
        # 输出: {"username": "", "password": "123456"}
        hint_value_map: dict[str, str] = {}
        for hint in candidate.get("steps_hint") or []:
            hint_text = _normalized_text(hint)
            if not hint_text or ":" not in hint_text:
                continue
                # 拆分 "input:password=123456" → action="input", payload="password=123456"
            action_raw, _, payload = hint_text.partition(HINT_SEP_ACTION)
            # 只处理 input 类型的 hint（click/goto/assert 不需要值）
            if _normalized_text(action_raw) not in HINT_INPUT_ACTIONS:
                continue
                # 拆分 "password=123456" → target="password", value="123456"
            target, _, value = payload.partition(HINT_SEP_VALUE)
            target = _normalized_text(target)
            value = _normalized_text(value)
            if target:
                hint_value_map[target] = value

    for raw_step in steps:
        step_text = _normalized_text(raw_step)
        if not step_text:
            continue
        element = _login_element_from_text(step_text)
        if any(token in step_text for token in _c.INPUT_ACTION_TOKENS) and element is not None:
            element_code, element_name, data_key_hint = element
            has_value, value = _input_value_from_text(step_text)
            data_ref = _data_ref_for_element(element_code, data_key_hint)
            step: dict[str, Any] = {
                "action": "input",
                "target": f"element:{element_code}",
                "target_name": element_name,
                "data_ref": data_ref,
                "raw_text": step_text,
            }
            if has_value:
                step["value"] = value
                data[data_ref] = {"source_type": "inline", "value": value}
                # steps_hint 是当前直接编译器的稳定输入；空字符串可以表达，纯空格暂时不能安全表达。
                if value == " ":
                    warnings.append(f"{element_name} 的空格输入需要后续由 DSL 数据引用执行，当前 steps_hint 无法无损表达纯空格。")
                else:
                    _append_unique(steps_hint, f"input:{element_name}={value}")
            else:
                fallback_value = ""
                for hint_name, hint_val in hint_value_map.items():
                    hint_elem = _login_element_from_text(hint_name)
                    if hint_elem is not None and hint_elem[0] == element_code:
                        fallback_value = hint_val
                        break
                if fallback_value:
                    # 兜底成功：用 AI 给的精确值填充
                    step["value"] = fallback_value
                    data[data_ref] = {"source_type": "inline", "value": fallback_value}
                    # 写入 steps_hint（格式: "input:密码输入框=123456"）
                    _append_unique(steps_hint, f"input:{element_name}={fallback_value}")
                else:
                    # 兜底也失败：确实没有可用值，记录警告
                    warnings.append(f"{element_name} 输入步骤缺少明确测试数据：{step_text}")
            structured_steps.append(step)
            _append_unique(involved_codes, element_code)
            continue

        if _c.CLICK_ACTION_TOKEN in step_text and element is not None:
            element_code, element_name, _data_key = element
            structured_steps.append(
                {
                    "action": "click",
                    "target": f"element:{element_code}",
                    "target_name": element_name,
                    "raw_text": step_text,
                }
            )
            _append_unique(steps_hint, f"click:{element_name}")
            _append_unique(involved_codes, element_code)
            if element_code == "login-password-toggle-btn":
                expected_attribute_step = _password_visibility_assertion_step(expected)
                if expected_attribute_step is not None:
                    structured_steps.append(expected_attribute_step)
                    _append_unique(
                        steps_hint,
                        f"assert_attribute:{expected_attribute_step['target_name']}.type={expected_attribute_step['value']}",
                    )
                    _append_unique(involved_codes, "login-password-input")
            continue

        if any(token in step_text for token in _c.GOTO_ACTION_TOKENS):
            structured_steps.append(
                {
                    "action": "goto",
                    "value": _c.GOTO_DEFAULT_ROUTE,
                    "raw_text": step_text,
                }
            )
            _append_unique(steps_hint, format_steps_hint(ACTION_GOTO, _c.GOTO_DEFAULT_ROUTE))
            continue

        structured_steps.append(
            {
                "action": "candidate_step",
                "target": "",
                "value": step_text,
                "raw_text": step_text,
            }
        )
        warnings.append(f"步骤仍需人工结构化：{step_text}")

    expected_text = _normalized_text(expected)
    if any(token in expected_text for token in _c.ASSERT_VISIBLE_TOKENS):
        structured_steps.append(
            {
                "action": "assert_visible",
                "target": "element:home_menu",
                "target_name": "首页菜单",
                "raw_text": expected_text or "校验首页菜单可见",
            }
        )
        _append_unique(steps_hint, "assert:首页菜单")
        _append_unique(involved_codes, "home_menu")
    elif any(token in expected_text for token in _c.ASSERT_TEXT_TOKENS):
        # 错误提示场景：expected_text 描述了 UI 应展示的错误文案，
        # 如 "页面提示'请输入账号'"。此时必须用 assert_text 验证文案确实出现，
        # 不能用 assert_url（RULE_003 会拦截为"虚假通过风险"）。
        error_msg = extract_error_message(expected_text)
        structured_steps.append(
            {
                "action": "assert_text",
                "value": error_msg,
                "raw_text": expected_text or "校验错误提示文案",
            }
        )
        _append_unique(steps_hint, f"assert_text:{error_msg}")
    elif any(token in expected_text for token in _c.ASSERT_URL_TOKENS):
        # 跳转拦截场景：expected_text 说"自动跳转回登录页"。
        # 但必须排除否定语义——"未跳转回登录页"出现"登录页"但含义相反，
        # 此时不应加 assert_url，留给前链的 assert_visible 等步骤覆盖。
        if not has_negation_before(expected_text, ("登录页", "登录页面")):
            structured_steps.append(
                {
                    "action": "assert_url",
                    "value": _c.ASSERT_URL_FALLBACK,
                    "raw_text": expected_text or "校验仍停留在登录页",
                }
            )
            _append_unique(steps_hint, format_steps_hint(ACTION_ASSERT_URL, _c.ASSERT_URL_FALLBACK))

    if not structured_steps:
        fallback = _normalized_text(candidate.get("summary") or candidate.get("title"))
        if fallback:
            structured_steps.append({"action": "candidate_step", "target": "", "value": fallback, "raw_text": fallback})
            warnings.append("缺少可结构化步骤。")

    return structured_steps, steps_hint, data, warnings, involved_codes


def _fallback_precondition(candidate: dict[str, Any], *, point_type: str, expected: str) -> str:
    """补齐业务级前置条件；不补账号密码、不补环境地址。"""
    precondition = _normalized_text(candidate.get("precondition"))
    if precondition:
        return precondition
    merged = " ".join(
        _normalized_text(candidate.get(key))
        for key in ("title", "summary", "expected", "expected_result")
    )
    if any(token in merged for token in _c.LOGGED_IN_TOKENS):
        return _c.DEFAULT_PRECONDITION_LOGGED_IN
    if any(token in merged for token in _c.NOT_LOGGED_IN_TOKENS):
        return _c.DEFAULT_PRECONDITION_NOT_LOGGED_IN
    if point_type in _c.PRECONDITION_APPLICABLE_POINT_TYPES or "登录" in merged or expected:
        return _c.DEFAULT_PRECONDITION_LOGIN_PAGE
    return _c.FALLBACK_PRECONDITION


def _build_point(candidate: dict[str, Any], *, index: int) -> dict[str, Any]:
    """将单个候选测试点编译为可保存的 point 字典。

    === 入参（candidate）示例 ===
    来自 AI 生成的原始输出或前端传递的候选数据：
    {
        "intent_id": "intent-04",
        "title": "账号为空点击登录",
        "summary": "账号为空点击登录",
        "intent_type": "negative",
        "priority": "P1",
        "precondition": "用户未登录，处于登录页",
        "steps": ["清空账号输入框", "在密码输入框输入任意密码", "点击登录按钮"],
        "steps_hint": ["input:username=", "input:password=123456", "click:loginButton"],
        "expected": '页面提示"请输入账号"',
        "involved_elements": ["username", "password", "loginButton"],
        "involved_element_codes": None,  ← AI 通常不知道合法 code
    }
    index: 候选序号（从1开始），用于生成 fallback intent_id

    === 处理流程 ===
    1. 从 candidate 中提取基本字段（title, steps, expected, point_type 等）
    2. _fallback_precondition: 补齐缺失的前置条件
    3. point_type=negative/boundary → action="review"（需人工审核）
    4. _structured_steps_from_candidate: 自然语言步骤 → DSL 结构化步骤
    5. _canonical_login_involved_elements: 将中文元素名归一化为 element codes

    === 输出（point 字典）===
    写入 web-ui/state/test-points/{project}/mall-web-login-auth-fn-ai-0001.json
    的 plan.points 数组中。每个 point 包含：
    - key / intent_id: 唯一标识
    - point_type: "negative" | "functional" | "security" | ...
    - action: "review"（需审核）| "candidate"（待处理）
    - steps: 结构化步骤列表（来自 _structured_steps_from_candidate 的 structured_steps）
    - steps_hint: 编译提示列表（来自 _structured_steps_from_candidate 的 steps_hint）
      ⚠ steps 和 steps_hint 可能不同步：
         - 输入步骤 has_value=False 时，在 structured_steps 中存在但在 steps_hint 中缺失
         - assert_text 的 steps_hint 格式缺少 target 前缀
    - data: 变量数据引用（has_value=False 的步骤不会写入 data）
    - involved_elements: 最终的元素 code 列表（由 _canonical_login_involved_elements 合并）
    - warnings: 编译警告列表
    - requires_review: bool(warnings) — 有警告就标记需审核
    - expected_result: 预期结果原文
    - precondition: 补齐后的前置条件
    - metadata.candidate_snapshot: 原始 candidate 的快照（用于追溯）
    """
    intent_id = _normalized_text(candidate.get("intent_id")) or f"candidate-{index:02d}"
    title = _normalized_text(candidate.get("title")) or intent_id
    summary = _normalized_text(candidate.get("summary")) or title
    steps = _list_text(candidate.get("steps"))
    involved_elements = _list_text(candidate.get("involved_elements"))
    expected = _normalized_text(candidate.get("expected") or candidate.get("expected_result"))
    point_type = _normalized_text(candidate.get("intent_type")) or "functional"
    precondition = _fallback_precondition(candidate, point_type=point_type, expected=expected)
    action = "candidate"
    if point_type in {"boundary", "negative", "abnormal"}:
        action = "review"
    point_steps, steps_hint, data, structure_warnings, involved_codes = _structured_steps_from_candidate(
        candidate=candidate,
        steps=steps or [summary],
        expected=expected,
    )
    warnings: list[str] = []
    warnings.extend(structure_warnings)
    if not steps:
        warnings.append("缺少结构化步骤。")
    if not involved_elements:
        warnings.append("缺少涉及元素。")
    involved_elements = _canonical_login_involved_elements(involved_elements, involved_codes)
    return {
        "key": intent_id,
        "intent_id": intent_id,
        "point_type": point_type,
        "action": action,
        "description": summary,
        "step_index": index,
        "dependencies": [],
        "source_ids": [intent_id],
        "steps": point_steps,
        "steps_hint": steps_hint,
        "data": data,
        "warnings": warnings,
        "requires_review": bool(warnings),
        "involved_elements": involved_elements,
        "expected_result": expected,
        "precondition": precondition,
        "tags": _list_text(candidate.get("tags")),
        "priority": _normalized_text(candidate.get("priority")) or "P1",
        "confidence": _c.DEFAULT_CONFIDENCE_WITH_STEPS if steps else _c.DEFAULT_CONFIDENCE_WITHOUT_STEPS,
        "metadata": {
            "candidate_snapshot": _candidate_snapshot(candidate),
            "traceability": {
                "source_ids": [intent_id],
                "intent_ids": [intent_id],
            },
            "dsl_v1_1_structuring": {
                "data_keys": sorted(data.keys()),
                "steps_hint_count": len(steps_hint),
                "has_precondition": bool(precondition and precondition != "未维护。"),
            },
        },
    }


def _coverage_matrix_from_requirement_spec(
    requirement_spec: dict[str, Any],
    *,
    points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    point_by_intent = {
        _normalized_text(point.get("intent_id")): _normalized_text(point.get("key"))
        for point in points
        if isinstance(point, dict) and _normalized_text(point.get("intent_id")) and _normalized_text(point.get("key"))
    }
    raw_rows = requirement_spec.get("coverage_matrix")
    rows: list[dict[str, Any]] = []
    if isinstance(raw_rows, list):
        for index, raw_row in enumerate(raw_rows, start=1):
            if not isinstance(raw_row, dict):
                continue
            intent_ids = _list_text(raw_row.get("intent_ids"))
            point_keys = [point_by_intent[intent_id] for intent_id in intent_ids if point_by_intent.get(intent_id)]
            rows.append(
                {
                    "row_id": _normalized_text(raw_row.get("row_id")) or f"coverage-row-{index:02d}",
                    "traceability_status": _normalized_text(raw_row.get("traceability_status")) or "covered",
                    "source_ids": _list_text(raw_row.get("source_ids")),
                    "intent_ids": intent_ids,
                    "point_keys": point_keys,
                    "changed_areas": _list_text(raw_row.get("changed_areas")),
                    "explanation": _normalized_text(raw_row.get("explanation")),
                }
            )
    if rows:
        return rows
    intent_ids = _list_text(
        [
            str(point.get("intent_id", "")).strip()
            for point in points
            if isinstance(point, dict) and str(point.get("intent_id", "")).strip()
        ]
    )
    point_keys = _list_text(
        [
            str(point.get("key", "")).strip()
            for point in points
            if isinstance(point, dict) and str(point.get("key", "")).strip()
        ]
    )
    if not intent_ids and not point_keys:
        return []
    return [
        {
            "row_id": "selected-intents",
            "traceability_status": "covered",
            "source_ids": ["source-01"],
            "intent_ids": intent_ids,
            "point_keys": point_keys,
            "changed_areas": [],
            "explanation": "derived from selected test intents",
        }
    ]


def _intent_type_distribution(candidates: list[dict[str, Any]]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for candidate in candidates:
        intent_type = _normalized_text(candidate.get("intent_type")) or "functional"
        distribution[intent_type] = int(distribution.get(intent_type, 0) or 0) + 1
    return dict(sorted(distribution.items()))


def _find_existing_page_asset_for_upsert(project: str, page: str, existing_case_ids: list[str]) -> str:
    """在已有资产中查找同页面资产，返回其 case_id 以支持 upsert 而非重复创建。"""
    import re
    normalized_project = _normalized_text(project)
    normalized_page = _normalized_text(page)
    if not normalized_project or not normalized_page:
        return ""
    # case_id 格式: {project}-web-{page}-{type}-{source}-{seq}
    # 匹配同 project 同 page 的资产
    page_prefix = f"{normalized_project}-web-{normalized_page}-"
    for case_id in sorted(existing_case_ids, key=lambda cid: _normalized_text(cid)):
        if _normalized_text(case_id).startswith(page_prefix):
            return _normalized_text(case_id)
    return ""


def _first_candidate_title(candidates: list[dict[str, Any]], *, page: str) -> str:
    for candidate in candidates:
        title = _normalized_text(candidate.get("title")) or _normalized_text(candidate.get("summary"))
        if title:
            return title
    return f"{page} 测试点资产集" if page else "测试点资产集"


class SaveTestPointAssetsService:
    def __init__(self, *, context: WorkbenchContext) -> None:
        self._context = context

    def execute(self, payload: Any) -> dict[str, Any]:
        context = self._context
        runtime = context.runtime
        repository = context.repository
        runtime.ensure_dirs()

        project = _normalized_text(getattr(payload, "project", "")) or "mall"
        page = runtime.normalize_page_slug(_normalized_text(getattr(payload, "page", "")))
        if not page:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="page must not be empty",
            )

        requirement_text = _normalized_text(getattr(payload, "requirement", ""))
        input_sources = [item for item in (getattr(payload, "input_sources", None) or []) if isinstance(item, dict)]
        openapi_spec = getattr(payload, "openapi_spec", None)
        openapi_spec = openapi_spec if isinstance(openapi_spec, dict) else {}
        has_multisource_inputs = context.generation.has_multisource_inputs(
            input_sources=input_sources,
            openapi_spec=openapi_spec,
            prd_text=getattr(payload, "prd_text", ""),
            prd_url=getattr(payload, "prd_url", ""),
            user_story=getattr(payload, "user_story", ""),
            git_diff=getattr(payload, "git_diff", ""),
            git_diff_path=getattr(payload, "git_diff_path", ""),
            openapi_url=getattr(payload, "openapi_url", ""),
            defect_ticket=getattr(payload, "defect_ticket", ""),
            runtime_logs=getattr(payload, "runtime_logs", ""),
        )
        effective_requirement = context.generation.resolve_effective_requirement(
            requirement_text=requirement_text,
            normalized_page=page,
            multisource_enabled=has_multisource_inputs,
        )

        raw_candidates = [item for item in list(getattr(payload, "selected_candidates", []) or []) if isinstance(item, dict)]
        selected_intent_ids = [
            _normalized_text(item)
            for item in list(getattr(payload, "selected_intent_ids", []) or [])
            if _normalized_text(item)
        ]
        preview_id = _normalized_text(getattr(payload, "preview_id", ""))
        preview_requirement, requirement_spec = _preview_requirement(preview_id)
        if preview_requirement:
            effective_requirement = preview_requirement

        raw_candidates = preview_store.resolve_selected_candidates(
            preview_id=preview_id,
            selected_intent_ids=selected_intent_ids,
            fallback_candidates=raw_candidates,
        )
        batch_candidates = context.candidate_normalizer.normalize_candidates(raw_candidates)
        if len(batch_candidates) > _c.MAX_CANDIDATES:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="selected_candidates exceeds max size 200",
            )
        if not batch_candidates:
            return {
                "message": "no selected candidates to save",
                "count": 0,
                "items": [],
            }

        requested_case_id = _normalized_text(getattr(payload, "case_id", ""))
        existing_case_ids = repository.collect_existing_case_ids(assets_cases_root=runtime.AI_CASES_ROOT.parent)
        for case_id in _existing_test_point_asset_ids(project):
            if case_id not in existing_case_ids:
                existing_case_ids.append(case_id)
        # Reuse existing asset for the same page when no explicit case_id is requested
        if not requested_case_id:
            existing_page_asset_id = _find_existing_page_asset_for_upsert(project, page, existing_case_ids)
            if existing_page_asset_id:
                requested_case_id = existing_page_asset_id
        candidate_case_id = repository.allocate_case_id(
            requested_case_id=requested_case_id,
            project=project,
            page=page,
            module=page,
            ai_cases_root=runtime.AI_CASES_ROOT,
            existing_case_ids=existing_case_ids,
        )
        points = [_build_point(candidate, index=index) for index, candidate in enumerate(batch_candidates, start=1)]
        selected_ids = [
            _normalized_text(candidate.get("intent_id"))
            for candidate in batch_candidates
            if _normalized_text(candidate.get("intent_id"))
        ]
        involved_elements = _list_text(
            [
                element
                for point in points
                for element in _list_text(point.get("involved_elements"))
            ]
        )
        plan_title = _first_candidate_title(batch_candidates, page=page)
        asset_title = f"{page} 页面测试点资产集" if page else "测试点资产集"
        parse_confidence = requirement_spec.get("parse_confidence")
        try:
            confidence = float(parse_confidence) if parse_confidence is not None else 0.8
        except (TypeError, ValueError):
            confidence = 0.8
        plan = {
            "version": "TestPointPlanV1",
            "project": project,
            "case_id": candidate_case_id,
            "page": page,
            "title": plan_title,
            "priority": _normalized_text(requirement_spec.get("priority")) or _normalized_text(getattr(payload, "priority", "")) or "P1",
            "source_type": "selection_save",
            "requirement": [effective_requirement] if effective_requirement else [],
            "generated_at": runtime.now_iso(),
            "points": points,
            "coverage": {
                "status": "full",
                "coverage_ratio": 1.0 if points else 0.0,
                "generated_case_count": len(points),
                "expected_case_count": len(points),
                "missing_scenarios": [],
                "covered_scenarios": selected_ids,
            },
            "review_summary": {
                "total_points": len(points),
                "mainline_point_count": len(points),
                "design_only_point_count": 0,
                "technique_distribution": _intent_type_distribution(batch_candidates),
            },
            "metadata": {
                "saved_by": "web_ui_service",
                "origin": "selection_save",
                "preview_id": preview_id,
                "asset_title": asset_title,
                "selected_intent_ids": selected_ids,
                "selected_candidates": [_candidate_snapshot(candidate) for candidate in batch_candidates],
                "coverage_matrix": _coverage_matrix_from_requirement_spec(requirement_spec, points=points),
                "requirement_source": "preview.normalized_requirement" if preview_requirement else "payload.requirement",
                "normalized_requirement": effective_requirement,
                "parse_confidence": parse_confidence,
            },
            "involved_elements": involved_elements,
            "confidence": max(0.0, min(1.0, confidence)),
            "warnings": [],
            "requires_review": False,
        }
        plan_path = runtime.save_test_point_plan(
            project=project,
            case_id=candidate_case_id,
            page=page,
            page_url="",
            requirement=effective_requirement,
            plan=plan,
            # 保存“测试点资产”时必须写入 test-points 事实源目录。
            # runtime 默认绑定 generated-cases，是为了生成正式用例时不覆盖源资产；
            # 这里显式覆盖 state_root，避免详情页读取 TEST_POINTS_ROOT 时拿到空资产。
            state_root=workbench_state_store.WEB_UI_STATE_ROOT / "test-points",
        )
        asset_path = workbench_asset_service.state_case_file(
            project,
            candidate_case_id,
            state_root=workbench_state_store.WEB_UI_STATE_ROOT / "test-points",
        )
        asset = workbench_asset_service.load_test_point_asset_with_root(
            project,
            candidate_case_id,
            state_root=workbench_state_store.WEB_UI_STATE_ROOT / "test-points",
        )
        # Sync test points to DB (per-point records)
        try:
            db_synced = repository.sync_test_points(
                project_code=project,
                page_code=page,
                points=points,
            )
        except Exception:
            db_synced = 0
        # Sync asset bundle to DB (test_point_assets table)
        try:
            from app.services import test_point_asset_store
            if isinstance(asset, dict) and asset.get("asset_id"):
                test_point_asset_store.save_asset(repository.db, project=project, bundle=asset)
        except Exception:  # noqa: BLE001 - DB 写穿降级,不阻断保存
            LOGGER.warning("test point asset DB write-through failed for %s/%s", project, candidate_case_id, exc_info=True)
        runtime.append_history(
            {
                "timestamp": runtime.now_iso(),
                "action": "save_test_point_asset",
                "case_id": candidate_case_id,
                "page": page,
                "project": project,
                "path": str(asset_path.resolve()),
                "plan_path": str(Path(plan_path).resolve()),
                "intent_count": len(selected_ids) or len(points),
            }
        )

        return {
            "message": "saved 1 test point asset",
            "count": 1,
            "items": [
                {
                    "case_id": candidate_case_id,
                    "project": project,
                    "page": page,
                    "title": asset_title,
                    "intent_ids": selected_ids,
                    "intent_count": len(selected_ids) or len(points),
                    "plan_path": str(Path(plan_path).resolve()),
                    "asset_path": str(asset_path.resolve()),
                    "asset": asset,
                }
            ],
        }
