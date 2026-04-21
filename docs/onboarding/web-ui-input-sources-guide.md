# Web UI 输入源使用说明（新手版）

> 迁移标注（2026-03-19）  
> `web-ui` 目录仅保留历史兼容语义，不再作为当前主链源码目录。
> 推荐使用 FastAPI 入口：
> `python -m uvicorn app.main:app --app-dir apps/web-ui-service --host 127.0.0.1 --port 8013`

这份文档是给第一次用 `web-ui` 生成功能的同学准备的。  
目标很简单：你只要照着做，就能把需求、Git Diff、缺陷信息、运行日志喂给系统，生成测试点和 YAML 用例。

---

## 1. 你会得到什么

在 `Generate` 页面或 API 中，系统现在支持多种输入源：

- `requirement`：自然语言需求
- `git_diff_text`：代码变更 diff
- `defect_text`：缺陷单信息
- `runtime_log_text`：运行日志/报错栈
- `input_sources`：高级用法，可传自定义来源列表

生成结果中会返回：

- `test_points.source_type`：本次测试点的来源类型（如 `requirement`、`git_diff`、`multi_source`）
- `input_sources`：来源明细（每类输入长度、预览、数量）
- `source_summary`：可读摘要（便于 UI 直接展示）

---

## 2. 先启动服务

在项目根目录执行：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
./.venv/bin/python -m uvicorn app.main:app --app-dir apps/web-ui-service --host 127.0.0.1 --port 8013
```

浏览器打开：

- [http://127.0.0.1:8013/generate](http://127.0.0.1:8013/generate)

---

## 3. 小白最快操作路径（页面版）

按下面 5 步操作即可：

1. 选择 `Project`（没有就先用 `default`）。
2. 填写 `Page`（例如 `product`、`login`）。
3. 在以下区域至少填写一个输入源：
   - `Requirement`
   - `Git Diff`
   - `Defect Context`
   - `Runtime Log`
4. 点击 `Generate And Save`。
5. 在右侧查看：
   - `Generated YAML`
   - `Test Points Preview`
   - `Input Sources` 摘要

注意：`Page` 不能为空；输入源至少要有一个非空内容。

---

## 4. 每种输入源怎么写（附可复制示例）

## 4.1 Requirement（最常用）

适用场景：你有明确业务需求描述。  
示例：

```text
验证商品页面可以登录后打开，并显示商品列表；点击商品后可进入详情页。
```

---

## 4.2 Git Diff（改动驱动回归）

适用场景：你要围绕本次代码改动生成测试点。  
示例：

```diff
diff --git a/runners/web-playwright-python/page_objects/product_page.py b/runners/web-playwright-python/page_objects/product_page.py
index 1234567..89abcde 100644
--- a/runners/web-playwright-python/page_objects/product_page.py
+++ b/runners/web-playwright-python/page_objects/product_page.py
@@ -18,6 +18,10 @@ class ProductPage:
     def wait_list(self):
         self.page.locator("#product-list").wait_for(state="visible")
+
+    def wait_empty_state(self):
+        self.page.locator(".empty-state").wait_for(state="visible")
```

建议：粘贴和本次改动最相关的 diff 片段，不需要整个仓库所有改动。

---

## 4.3 Defect Context（缺陷驱动补测）

适用场景：你要把历史 bug 风险覆盖进去。  
示例：

```text
BUG-3421: 商品列表偶现空白
复现步骤：
1) 登录后进入商品页
2) 快速切换筛选条件 3 次
3) 列表区域出现空白但无错误提示
影响范围：product 页列表渲染、筛选交互
```

---

## 4.4 Runtime Log（日志驱动定位）

适用场景：你有报错日志，想让生成内容更贴近真实故障点。  
示例：

```text
2026-03-18 10:21:03 ERROR TimeoutError: request /api/products timed out after 15000ms
2026-03-18 10:21:03 WARN retry_count=3 trace_id=6d9f0f...
```

---

## 5. 推荐组合（最实用）

- 组合 A：`requirement + git_diff_text`
  - 适合功能迭代回归，平衡业务目标和代码改动。
- 组合 B：`git_diff_text + defect_text`（requirement 可为空）
  - 适合修 bug 场景，重点覆盖改动和历史缺陷。
- 组合 C：`requirement + runtime_log_text`
  - 适合线上告警后补充自动化回归。
- 组合 D：`requirement + git_diff_text + defect_text + runtime_log_text`
  - 全量上下文，适合高风险发布前。

---

## 6. API 调用示例（可直接复制）

## 6.1 生成 YAML（`POST /api/generate`）

```bash
curl -X POST "http://127.0.0.1:8013/api/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "default",
    "page": "product",
    "requirement": "验证商品页基础流程",
    "git_diff_text": "diff --git a/product.ts b/product.ts\n+ add retry when list api timeout",
    "defect_text": "BUG-101: 商品列表偶现空白",
    "runtime_log_text": "TimeoutError: request /api/products"
  }'
```

成功后重点看响应字段：

- `case`：生成后的 YAML 结构
- `test_points`：结构化测试点
- `input_sources`：输入源明细
- `source_summary`：来源摘要

---

## 6.2 只生成测试点（`POST /api/test-points/generate`）

示例：`requirement` 为空，只用 Git Diff：

```bash
curl -X POST "http://127.0.0.1:8013/api/test-points/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "default",
    "page": "product",
    "requirement": "",
    "git_diff_text": "diff --git a/product.py b/product.py\n+ add guard for empty list",
    "asset_id": "TP-PRODUCT-GIT-001"
  }'
```

你会看到：

- `test_points.source_type = "git_diff"`
- `input_sources.source_type = "git_diff"`

---

## 6.3 高级输入（`input_sources`）

当你已有外部系统组装好的输入源，可直接传 `input_sources`：

```bash
curl -X POST "http://127.0.0.1:8013/api/test-points/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "default",
    "page": "product",
    "input_sources": {
      "sources": [
        {
          "kind": "git_diff",
          "name": "PR-289 diff",
          "ref": "https://git.example.com/repo/pull/289/files",
          "content": "diff --git a/product.ts b/product.ts\n+ add retry"
        },
        {
          "kind": "defect_ticket",
          "name": "BUG-3421",
          "ref": "https://jira.example.com/browse/BUG-3421",
          "content": "商品列表偶现空白，筛选切换后触发"
        }
      ]
    }
  }'
```

---

## 7. 常见报错与处理

## 报错 1：`page must not be empty`

原因：没有传 `page`。  
处理：传入页面名，建议与现有 page-object 一致（如 `product`、`login`）。

## 报错 2：`at least one input source is required`

原因：`requirement`、`git_diff_text`、`defect_text`、`runtime_log_text`、`input_sources` 都为空。  
处理：至少填写一个输入源。

## 报错 3：生成结果不够贴近实际改动

原因：输入过于泛化。  
处理：优先补充 `git_diff_text` 和 `defect_text`，并保留关键报错日志。

---

## 8. 新手检查清单（发布前 30 秒）

提交前快速看 5 项：

1. `Page` 是否填写并正确。
2. 是否至少有一个输入源非空。
3. `Input Sources` 摘要是否符合预期（比如 `multi_source`）。
4. `Test Points Preview` 是否覆盖了关键流程和关键断言。
5. 生成后是否进入 `Preview` 页面做一次人工确认再执行。
