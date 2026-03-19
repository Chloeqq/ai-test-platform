# test-design-agent

将需求或测试点转换为可执行测试用例，并支持企业级设计 bundle：

- `test_points`：测试点清单
- `case`：可执行用例
- `traceability`：测试点到用例步骤的追溯关系
- `review_summary`：置信度、待确认项、跳过建议

## 当前能力

- 基于 `requirement_spec.test_intents` 生成测试点
- 基于测试点生成稳定的 Playwright 用例
- 自动补充 `confidence / warnings / requires_review`
- 提供确定性 `design_bundle`，适合回归场景和人工确认

## 运行方式

```bash
python -m src.index --input /tmp/test-design-payload.json
python -m src.index --bundle --input /tmp/test-design-payload.json
```

`/tmp/test-design-payload.json` 可以包含：

```json
{
  "requirement": "商品列表页支持按名称搜索",
  "page": "product",
  "requirement_spec": {
    "page": "product",
    "design_input": "商品列表页支持按名称搜索",
    "priority": "P1",
    "test_intents": [
      {
        "intent_id": "intent-01",
        "title": "页面可访问",
        "intent_type": "functional",
        "priority": "P0",
        "steps_hint": ["login"]
      }
    ]
  }
}
```
