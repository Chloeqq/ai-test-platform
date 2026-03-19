# script-generation-agent

将结构化测试用例（YAML 对象）生成可执行脚本代码（当前 MVP：Playwright + Python）。

## 快速使用

```bash
python -m src.index --input /tmp/script_generation_payload.json
```

`/tmp/script_generation_payload.json` 示例：

```json
{
  "framework": "playwright",
  "language": "python",
  "case": {
    "id": "TC-PRODUCT-001",
    "execution": {
      "page": "product",
      "steps": [
        {"action": "login"},
        {"action": "click", "target": "product_menu"}
      ]
    }
  }
}
```
