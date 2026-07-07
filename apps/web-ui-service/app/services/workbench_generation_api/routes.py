"""API 路由路径常量。

router 和 preview_store 共用，避免路由路径在字符串中重复定义。
"""

PREVIEW_TEST_POINTS = "/api/workbench/preview-test-points"
PREVIEW_DIAGNOSTICS = "/api/workbench/preview-test-points/{preview_id}/diagnostics"
PREVIEW_INTENT_DETAIL = "/api/workbench/preview-test-points/{preview_id}/test-intents/{intent_id}"
PRECHECK_INTENTS = "/api/workbench/precheck-selected-intents"
SAVE_TEST_POINT_ASSETS = "/api/workbench/test-point-assets/save"
