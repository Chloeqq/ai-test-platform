# ATP 断言生成即刻修复方案（过渡版）

**日期**：2026-07-11
**目标**：消除硬编码 token，不等待完整断言模板系统
**原则**：最小改动，立即生效

---

## 修复范围

仅修改 `structurer.py` 的 `_build_expected_assertions()` 和 `constants.py`。

## 修复方案

### 修改 1：constants.py — token 改为页面级默认配置

```python
# 之前: 全局硬编码
ASSERT_VISIBLE_TOKENS = ("成功登录", "跳转到首页", ...)

# 之后: 从 PageObject 读取，无配置时用空列表（不匹配任何 token）
# 不再有全局默认 token
```

### 修改 2：structurer.py — 断言生成改为查 page_config

```python
# 之前:
def _build_expected_assertions(expected, involved_codes, ...):
    if any(token in expected_text for token in _c.ASSERT_VISIBLE_TOKENS):
        # 生成 assert_visible
    elif any(token in expected_text for token in _c.ASSERT_TEXT_TOKENS):
        # 生成 assert_text
    ...

# 之后:
def _build_expected_assertions(expected, involved_codes, page_config, ...):
    templates = page_config.assertion_templates  # 从 PageObject 读取
    
    if templates:
        for behavior in templates:
            if _match_behavior(expected_text, behavior):
                for assertion in behavior.assertions:
                    # 确定性地生成断言
                    generate_assertion(assertion)
    # 如果 page_config 没有 assertion_templates → 不生成断言
    # 让 Gate 拦截，提示用户在 PageObject 管理中配置断言模板
```

### 修改 3：page_config 扩展

```python
# PageObject 的 assertion_templates 字段结构
{
  "behaviors": [
    {
      "expected_behavior": "authenticated_and_redirected",
      "match_keywords": ["成功登录", "跳转", "首页"],
      "assertions": [
        {"action": "assert_url", "value": "/home"},
        {"action": "assert_visible", "target": "dashboard"}
      ]
    }
  ]
}
```

## 编译时校验

```text
如果 page_config 为 None 或 没有 assertion_templates:
  → warnings.append("PageObject 未配置断言模板，测试点可能零断言")
  → 不生成断言，让 Gate 拦截

如果 assertion_templates 存在:
  → 匹配 expected_behavior
  → 没匹配到 → warnings.append(f"预期行为 '{expected_text[:30]}' 未匹配到断言模板")
  → 匹配到了 → 生成对应断言
```

## 改动量

```text
constants.py: 删除全局 token，标记 @deprecated (仅保留注释)
structurer.py: ~40 行改动 (token匹配 → template 查找)
PageObject 模型: 已有 JSON 字段，无需新增
login PageObject: 写入 assertion_templates (手工/Docker SQL)
```

## 验证

```text
1. 删除 ASSERT_VISIBLE_TOKENS 后
2. login PageObject 有 assertion_templates → 20 个测试点正确生成断言
3. 其他 PageObject 无 assertion_templates → Gate 拦截，提示配置缺失
4. 116 个已有测试全部通过
```
