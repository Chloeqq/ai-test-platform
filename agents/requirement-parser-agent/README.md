# requirement-parser-agent

将自然语言需求解析为 `RequirementSpecV1`，用于后续测试设计与脚本生成。

## 快速使用

```bash
python -m src.index \
  --page returnapply \
  --requirement "在退货申请页面输入服务单号3后点击查询，验证显示退货申请列表"
```

## 输出要点

- `entities`: 识别到的页面/字段/动作实体
- `test_intents`: 结构化测试点（含优先级、依赖、步骤提示）
- `design_input`: 给测试设计 Agent 的规范化输入
- `coverage_matrix`: 需求与测试点关联
- `change_impact`: 变更影响面与回归建议
- `ambiguities`: 需求消歧提示
- `business_rules`: 提取到的业务规则

## 多源输入示例

```bash
python -m src.index --input /tmp/requirement-input.json
```

`/tmp/requirement-input.json` 示例：

```json
{
  "requirement": "退货申请页面支持按服务单号查询，普通用户只能查看自己的单据",
  "page": "",
  "source_type": "manual",
  "prd_text": "查询响应时间 P95 < 800ms",
  "git_diff": "diff --git a/apps/refund/service.py b/apps/refund/service.py\n+++ b/apps/refund/service.py\n+def check_permission(user):",
  "defect_ticket": "BUG-1023 unauthorized access severity=critical",
  "input_sources": [
    {
      "source_type": "openapi",
      "content": "GET /api/return-apply/list\nPOST /api/return-apply/{id}/approve"
    }
  ]
}
```
