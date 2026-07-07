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

DEFAULT_PRECONDITION_LOGGED_IN = "用户已登录并处于首页。"
DEFAULT_PRECONDITION_NOT_LOGGED_IN = "用户未登录。"
DEFAULT_PRECONDITION_LOGIN_PAGE = "用户未登录，处于登录页面。"
FALLBACK_PRECONDITION = "未维护。"

PRECONDITION_APPLICABLE_POINT_TYPES: frozenset[str] = frozenset({
    "functional", "negative", "boundary", "format", "interaction_exception",
})


# ── 密码可见性（local: 登录页专属，Phase 2 改为页面 hook）──────────────────

PASSWORD_VISIBILITY_TOKENS: tuple[str, ...] = (
    "已切换为", "已切换成", "已切回",
)

PLAINTEXT_TOKENS: tuple[str, ...] = ("可见", "显示密码")

MASKED_TOKENS: tuple[str, ...] = ("掩码", "隐藏密码")

DEFAULT_TEST_PASSWORD = "macro123"


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
