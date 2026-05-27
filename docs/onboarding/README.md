# Onboarding — 新手上手

## 第一次运行

```bash
# 1. 安装依赖
make install-dev

# 2. 安装 pre-commit hooks（可选）
make install-hooks

# 3. 一键启动开发环境（需要 Docker + .env）
make dev
```

启动后访问：
- Web UI: http://localhost:8013（Swagger: `/docs`）
- Orchestrator: http://localhost:8000（Swagger: `/docs`）

## 推荐阅读顺序

1. **`README.md`**（项目根目录）—— 10 章完整架构 + 6 条业务链路 + 数据模型
2. **`CLAUDE.md`**（项目根目录）—— AI 开发规则 + 已知问题
3. **`Makefile`** —— 所有可用命令（`make help`）
4. **`web-ui/state/README.md`** —— 运行态缓存说明
5. **`docs/architecture/2026-05-27_重构执行记录.md`** —— 全部改动记录

## 运行测试

```bash
make test-unit          # 276 单元测试
make test-contracts     # 契约测试
make test               # 全部
make verify-core-chain  # 核心链路冒烟
```
- 带日期的 `report-summary` / `worklog` 已转入 `docs/history/`，避免和长期有效的上手材料混放。

## 最短路径

- 想理解当前主平台怎么跑：
  1. [local-setup.md](./local-setup.md)
  2. [run-first-test.md](./run-first-test.md)
  3. [web-ui-input-sources-guide.md](./web-ui-input-sources-guide.md)
- 想体验模板脚手架控制台：
  1. [console-scaffold-guide.md](./console-scaffold-guide.md)
