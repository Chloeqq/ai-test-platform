# Markdown 文档权限开放记录

**修改时间**: 2026-04-02 23:21  
**修改人**: 系统管理员  
**修改范围**: 项目所有 `.md` 文档

---

## 一、权限修改概述

| 项目 | 数值 |
|------|------|
| 修改文件总数 | **130 个** |
| 修改前权限 | 混合 (600/644) |
| 修改后权限 | **644** (`-rw-r--r--`) |
| 权限说明 | 所有者可读写，组用户和其他用户可读 |

---

## 二、目录分布

| 目录 | 文件数量 | 占比 |
|------|----------|------|
| `docs/` | ~60 | 46% |
| `agents/*/` | ~20 | 15% |
| `apps/*/` | ~25 | 19% |
| `runners/*/` | ~10 | 8% |
| 根目录及其他 | ~15 | 12% |

---

## 三、详细文件清单

### 3.1 根目录文档

| 文件 | 权限 |
|------|------|
| `README.md` | 644 |
| `CONTRIBUTING.md` | 644 |

### 3.2 Docs 目录文档

#### Architecture (`docs/architecture/`)
- `README.md`
- `agents-analysis.md`
- `backend-frontend-gap-analysis.md`
- `current-architecture-and-flows.md`
- `overview.md`
- `project-inventory-and-risk-audit-2026-03-21.md`
- `project-status-overview.md`
- `runners.md`
- 等共 **18** 个文档

#### Implementation Plan (`docs/implementation-plan/`)
- `README.md`
- `detailed-refactoring-plan.md`
- `failure-clustering-design.md`
- `test-point-layer-design.md`
- `2026-03-29-legacy-workbench-route-map.md`
- `2026-03-29-platform-verification-and-governance-plan.md`
- `2026-03-31-legacy-workbench-responsibility-inventory.md`
- `2026-04-02-agent-improvement-supplement.md`
- `2026-04-02-governance-acceptance-checklist.md`
- `2026-04-02-normal-task-list.md`
- `2026-04-02-platform-next-backlog.md`
- `2026-04-02-orchestrator-multisource-closure-backlog.md`
- `2026-04-02-service-contract-map.md`
- 等共 **15** 个文档

#### Product (`docs/product/`)
- `README.md`
- `console-scaffold-prd.md`
- `console-scaffold-ux-spec.md`
- `next-phase-roadmap.md`
- `platform-gap-analysis.md`
- `url-driven-oneclick-automation-plan-2026-03-20.md`
- `url-driven-oneclick-automation-progress-log-2026-03-20-to-2026-03-22.md`
- `url-driven-oneclick-automation-status-and-priority-plan-2026-03-20.md`
- `url-first-main-flow-daily-checklist-2026-03-26.md`
- `url-first-main-flow-execution-plan-2026-03-26.md`
- 等共 **12** 个文档

#### UI Optimization (`docs/ui-optimization/`)
- `dashboard-enhancement-guide.md`
- `workbench-generate-redesign.md`

#### Rule (`docs/rule/`)
- `ai_test_platform_governance_v1.0.md`
- `test_case_naming_spec_v1.0.md`

#### Testing (`docs/testing/`)
- `README.md`
- `console-scaffold-test-cases.md`
- `oms-order-setting-test-cases.md`
- `oms-return-apply-beginner-guide.md`
- `oms-return-apply-test-cases.md`
- `sms-coupon-brand-test-cases.md`

#### Onboarding (`docs/onboarding/`)
- `README.md`
- `2026-03-18-web-ui-report-worklog.md`
- `2026-03-18-web-ui-report-summary.md`
- `console-scaffold-guide.md`
- `testing.md`
- `web-ui-input-sources-guide.md`
- 等共 **8** 个文档

#### Conventions (`docs/conventions/`)
- `README.md`
- `stage8-self-healing-advisor-checklist.md`
- `web-playwright-python-stable-baseline.md`
- 等共 **5** 个文档

#### History (`docs/history/`)
- `README.md`
- `2026-03-19-orchestrator-integration-summary.md`
- `2026-03-20-url-first-scaffold-summary.md`
- `2026-03-21-platform-governance-kickoff.md`
- `2026-03-22-web-ui-service-bootstrap-summary.md`
- `2026-03-25-data-generation-agent-scaffold.md`
- `2026-03-26-url-first-main-flow-execution-summary.md`
- `2026-03-27-runner-asset-contract-cleanup-summary.md`
- `2026-03-28-test-case-entity-governance-summary.md`
- `2026-03-29-legacy-workbench-refactor-kickoff.md`
- `2026-03-30-e2e-test-governance-summary.md`
- `2026-03-31-legacy-workbench-route-inventory.md`
- 等共 **14** 个文档

#### API (`docs/api/`)
- `README.md`
- `console-scaffold-api-spec.md`
- `orchestrator-api-handoff-plan-2026-03-19.md`
- `orchestrator-handoff-implementation-plan-2026-03-19.md`
- `web-ui-service-api-design-2026-03-22.md`
- 等共 **5** 个文档

### 3.3 Agents 目录文档

| Agent | 文档 |
|-------|------|
| `data-generation-agent/` | `README.md` |
| `execution-planner-agent/` | `README.md` |
| `failure-triage-agent/` | `README.md` |
| `requirement-parser-agent/` | `README.md`, `examples/login-prd-input.md`, `tests/fixtures/login-prd.md`, `tests/fixtures/refund-prd.md` |
| `risk-evaluation-agent/` | `README.md` |
| `script-generation-agent/` | `README.md` |
| `self-healing-advisor-agent/` | `README.md` |
| `test-design-agent/` | `README.md` |

### 3.4 Apps 目录文档

| 应用 | 文档 |
|------|------|
| `ai-orchestrator/` | `README.md` |
| `web-console/` | `README.md` |
| `web-ui-service/` | `README.md` |
| `shared_backend/` | `README.md` |

### 3.5 Runners 目录文档

| Runner | 文档 |
|--------|------|
| `web-playwright-python/` | `FEATURES_GUIDE.md`, `PROJECT_DOCS.md`, `README.md` |

### 3.6 其他文档

| 位置 | 文档 |
|------|------|
| `web-ui/` | `README.md` |
| `test-reports/` | `ui-test-summary.md` |
| `scripts/` | `README-3TASKS.md` |
| `.pytest_cache/` | `README.md` |

---

## 四、权限说明

### 4.1 权限码解释

```
644 = -rw-r--r--

所有者 (Owner):    读 + 写  (6 = 4 + 2)
组用户 (Group):    读       (4)
其他用户 (Other):  读       (4)
```

### 4.2 权限含义

| 角色 | 权限 | 说明 |
|------|------|------|
| 文件所有者 | 读 + 写 | 可以查看和编辑文件 |
| 同组用户 | 读 | 可以查看文件，不能编辑 |
| 其他用户 | 读 | 可以查看文件，不能编辑 |

### 4.3 为什么选择 644？

- ✅ **安全**: 防止未授权修改
- ✅ **协作**: 团队成员可以读取参考
- ✅ **标准**: Unix/Linux 系统默认文档权限
- ✅ **Git 友好**: 符合版本控制最佳实践

---

## 五、如何编辑文档

### 5.1 使用命令行

```bash
# 编辑文档
vim /Users/bettyhuang/PycharmProjects/ai-test-platform/docs/README.md

# 或使用其他编辑器
code /Users/bettyhuang/PycharmProjects/ai-test-platform/docs/README.md
```

### 5.2 使用 IDE

1. 打开 PyCharm/VSCode
2. 导航到目标 `.md` 文件
3. 直接编辑并保存

### 5.3 Git 工作流

```bash
# 1. 克隆仓库 (如果还没有)
git clone <repository-url>

# 2. 创建分支
git checkout -b docs/update-xxx-doc

# 3. 编辑文档
vim docs/README.md

# 4. 提交更改
git add docs/README.md
git commit -m "docs: 更新 XXX 文档"

# 5. 推送并创建 PR
git push origin docs/update-xxx-doc
```

---

## 六、文档编写规范

### 6.1 文件命名

```
格式：<主题>-<子主题>.md

示例:
- workbench-generate-redesign.md
- failure-clustering-design.md
- test-point-layer-design.md
```

### 6.2 文档结构

```markdown
# 文档标题

**元信息**: 时间/作者/版本

## 一、概述

## 二、详细内容

## 三、总结
```

### 6.3 更新频率

| 文档类型 | 更新频率 | 负责人 |
|----------|----------|--------|
| 架构文档 | 重大变更时 | 架构师 |
| 实施计划 | 每周 | 项目经理 |
| API 文档 | 接口变更时 | 开发人员 |
| 用户指南 | 功能更新时 | 技术写作 |

---

## 七、验证权限

### 7.1 验证命令

```bash
# 检查所有 md 文件权限
find /Users/bettyhuang/PycharmProjects/ai-test-platform -name "*.md" -type f -exec ls -la {} \;

# 统计权限分布
find /Users/bettyhuang/PycharmProjects/ai-test-platform -name "*.md" -type f -exec ls -la {} \; | awk '{print $1}' | sort | uniq -c
```

### 7.2 预期输出

```
-rw-r--r--  130 个文件 (100%)
```

---

## 八、后续维护

### 8.1 新增文档

创建新 `.md` 文档时，确保权限正确:

```bash
# 创建文档
touch docs/new-doc.md

# 设置权限
chmod 644 docs/new-doc.md
```

### 8.2 权限审计

建议每月进行一次权限审计:

```bash
# 检查是否有权限不正确的 md 文件
find /Users/bettyhuang/PycharmProjects/ai-test-platform -name "*.md" -type f -perm /022
```

### 8.3 批量修复

```bash
# 修复所有 md 文件权限
find /Users/bettyhuang/PycharmProjects/ai-test-platform -name "*.md" -type f -exec chmod 644 {} \;
```

---

## 九、常见问题

### Q1: 为什么我不能编辑某个 md 文件？

**A**: 检查文件所有权:
```bash
ls -la docs/xxx.md
```
如果不是你的用户，请联系文件所有者或管理员。

### Q2: 如何批量修改特定目录的 md 文件权限？

**A**: 
```bash
find /path/to/dir -name "*.md" -type f -exec chmod 644 {} \;
```

### Q3: Git 提交后权限会保留吗？

**A**: Git 不跟踪权限位变化 (除了执行位)，所以权限修改是本地操作。团队成员需要各自设置。

---

**记录版本**: 1.0  
**最后更新**: 2026-04-02 23:21  
**下次审计**: 2026-05-02
