"""save_test_point_assets_service 的硬编码常量集中管理。

警告：
- 跨模块共用的常量已迁入 shared_backend/step_fields.py 和 shared_backend/text_utils.py
- 本文件仅保留仅本模块使用的 token 列表和配置值
- 标记 @deprecated 的项在 Phase 2（页面对象驱动化）中将删除
"""
from __future__ import annotations

# ── 输入值提取（local: 中文 UI 文本匹配）────────────────────────────────────

EMPTY_INPUT_TOKENS: tuple[str, ...] = (
    "清空", "留空", "为空", "空值", "双空",
)

SPACE_INPUT_TOKEN = "空格"

# @deprecated — Phase 2 改为页面对象驱动，此正则仅匹配英文数字
INPUT_VALUE_PATTERN: str = (
    r"(?:输入|填写)(?:正确账号|正确密码|账号|密码|用户名)?\s*([A-Za-z0-9_@.\-]+)\s*$"
)


# ── 步骤动作识别（local: 中文关键词）────────────────────────────────────────

INPUT_ACTION_TOKENS: tuple[str, ...] = (
    "输入", "填写", "清空", "留空",
)

CLICK_ACTION_TOKEN = "点击"

GOTO_ACTION_TOKENS: tuple[str, ...] = (
    "刷新", "访问首页", "进入首页",
)

# @deprecated — Phase 2 从页面对象路由配置读取
GOTO_DEFAULT_ROUTE = "#/home"


# ── 断言生成（local: 按页面类型的 token 匹配，Phase 2 改为页面级配置）─────

ASSERT_VISIBLE_TOKENS: tuple[str, ...] = (
    "成功登录", "跳转到首页", "首页菜单可见", "进入首页",
)

ASSERT_TEXT_TOKENS: tuple[str, ...] = (
    "提示", "错误", "请输入", "失败",
)

ASSERT_URL_TOKENS: tuple[str, ...] = (
    "拦截", "登录页面", "登录页",
)

# @deprecated — Phase 2 从页面对象读取
ASSERT_URL_FALLBACK = "#/login"


# ── 前置条件推断（local: 中文关键词+模板文案）──────────────────────────────

LOGGED_IN_TOKENS: tuple[str, ...] = ("已登录",)

NOT_LOGGED_IN_TOKENS: tuple[str, ...] = ("未登录", "拦截")

LOGIN_PAGE_TOKENS: tuple[str, ...] = ("登录",)

DEFAULT_PRECONDITION_LOGGED_IN = "用户已登录并处于首页。"
DEFAULT_PRECONDITION_NOT_LOGGED_IN = "用户未登录。"
DEFAULT_PRECONDITION_LOGIN_PAGE = "用户未登录，处于登录页面。"
FALLBACK_PRECONDITION = "未维护。"

PRECONDITION_APPLICABLE_POINT_TYPES: frozenset[str] = frozenset({
    "functional", "negative", "boundary", "format", "interaction_exception",
})

# _build_point: 需要人工审核的测试点类型
REVIEW_POINT_TYPES: frozenset[str] = frozenset({"boundary", "negative", "abnormal"})

# 断言质量敏感类型: 必须使用强断言(assert_text)，不可降级为弱断言(assert_url)
STRONG_ASSERTION_REQUIRED_TYPES: frozenset[str] = frozenset(
    {"boundary", "negative", "abnormal", "format", "interaction_exception"},
)


# ── 密码可见性（local: 登录页专属，Phase 2 改为页面 hook）──────────────────

PASSWORD_VISIBILITY_TOKENS: tuple[str, ...] = (
    "已切换为", "已切换成", "已切回",
)

PLAINTEXT_TOKENS: tuple[str, ...] = ("可见", "显示密码")

MASKED_TOKENS: tuple[str, ...] = ("掩码", "隐藏密码")

# @deprecated — Phase 2 改为从数据池获取
DEFAULT_TEST_PASSWORD = "macro123"

# 登录页元素 code（密码可见性 hook 专属，Phase 2 移入页面 hook 模块）
LOGIN_PASSWORD_INPUT_CODE = "login-password-input"
LOGIN_PASSWORD_TOGGLE_CODE = "login-password-toggle-btn"

# 登录页元素展示名（从 element_naming 推导，Phase 2 移除）
LOGIN_PASSWORD_INPUT_NAME = "密码输入框"
LOGIN_PASSWORD_TOGGLE_NAME = "显示/隐藏眼睛图标"

# 密码可见性 data_ref
PASSWORD_DATA_REF = "password"
ASSERT_ATTR_TYPE = "type"
PASSWORD_VISIBILITY_TEXT = "text"
PASSWORD_VISIBILITY_PASSWORD = "password"

# 登录页前置条件步骤 raw_text
RAW_TEXT_PRERCOND_INPUT = "建立前置条件：先输入密码"
RAW_TEXT_PRERCOND_TOGGLE = "建立前置条件：点击眼睛图标切换为明文"

# 首页元素 code（断言生成中引用，Phase 2 移入页面对象配置）
HOME_ELEMENT_CODE = "home_menu"
HOME_ELEMENT_NAME = "首页菜单"


# ── 杂项（local: 本模块内部配置）───────────────────────────────────────────

CANDIDATE_SNAPSHOT_KEYS: tuple[str, ...] = (
    "intent_id",
    "title",
    "summary",
    "intent_type",
    "priority",
    "precondition",
    "steps",
    "steps_hint",
    "expected",
    "expected_result",
    "scene_type",
    "test_data_type",
    "involved_elements",
    "involved_element_codes",
    "tags",
    "review_status",
    "review_note",
    "reviewed_at",
    "reviewed_by",
    "data",
)

MAX_CANDIDATES = 200

DEFAULT_CONFIDENCE_WITH_STEPS = 0.8
DEFAULT_CONFIDENCE_WITHOUT_STEPS = 0.6

# ── DSL / 协议常量 ─────────────────────────────────────────────────────────

ELEMENT_PREFIX = "element:"
SOURCE_TYPE_INLINE = "inline"
DEFAULT_POINT_TYPE = "functional"
DEFAULT_PRIORITY = "P1"
SOURCE_TYPE_SELECTION_SAVE = "selection_save"

POINT_ACTION_CANDIDATE = "candidate"
POINT_ACTION_REVIEW = "review"

FALLBACK_DATA_KEY = "input_value"
LAST_ELEMENT_FALLBACK_CODE = "login-submit-btn"

# 警告 / 消息模板
MSG_STEPS_MISSING = "缺少结构化步骤。"
MSG_ELEMENTS_MISSING = "缺少涉及元素。"
MSG_NEEDS_MANUAL_STRUCTURING = "步骤仍需人工结构化："
MSG_NO_STRUCTURABLE_STEPS = "缺少可结构化步骤。"
MSG_SPACE_INPUT_STEPS_HINT_LIMITATION = "{element_name} 的空格输入需要后续由 DSL 数据引用执行，当前 steps_hint 无法无损表达纯空格。"
MSG_INPUT_STEP_MISSING_DATA = "{element_name} 输入步骤缺少明确测试数据：{step_text}"

# ── 断言 raw_text 回退文案 ─────────────────────────────────────────────────
ASSERT_VISIBLE_FALLBACK_TEXT = "校验首页菜单可见"
ASSERT_URL_FALLBACK_TEXT = "校验仍停留在登录页"
ASSERT_TEXT_FALLBACK_TEXT = "校验错误提示文案"

# ── 资产元数据 ─────────────────────────────────────────────────────────────
SAVED_BY = "web-ui-service"

# ── Asset 标题模板 ─────────────────────────────────────────────────────────

def asset_title_for_page(page: str) -> str:
    return f"{page} 页面测试点资产集" if page else "测试点资产集"
