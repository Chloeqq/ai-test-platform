# Onboarding

这一目录放新手上手、环境准备、首测、FAQ 和运行说明。

## 先分清入口

当前项目至少有两条不同的用户入口，第一次接手时先不要混：

- 主链入口：URL-first workbench
  - 关注页面分析、生成、执行、review、risk、gate、history
  - 相关页面通常在 `apps/web-ui-service` 下
- 并行入口：`Scaffold Console`
  - 关注模板驱动的 page object / smoke scaffold 创建
  - 相关页面是 `/console`

## 推荐阅读顺序

1. [local-setup.md](./local-setup.md)
2. [run-first-test.md](./run-first-test.md)
3. [testing.md](./testing.md)
4. [web-ui-input-sources-guide.md](./web-ui-input-sources-guide.md)
5. [faq.md](./faq.md)
6. [console-scaffold-guide.md](./console-scaffold-guide.md)

## 当前口径

- `local-setup.md` 和 `run-first-test.md` 是新手首选入口。
- 如果你要走主链，请优先看 `local-setup.md`、`run-first-test.md`、`web-ui-input-sources-guide.md`。
- 如果你只是要快速创建资产脚手架，再看 `console-scaffold-guide.md`。
- `web-ui-input-sources-guide.md` 解释了当前 Web UI 支持的输入源和使用方式。
- 带日期的 `report-summary` / `worklog` 已转入 `docs/history/`，避免和长期有效的上手材料混放。

## 最短路径

- 想理解当前主平台怎么跑：
  1. [local-setup.md](./local-setup.md)
  2. [run-first-test.md](./run-first-test.md)
  3. [web-ui-input-sources-guide.md](./web-ui-input-sources-guide.md)
- 想体验模板脚手架控制台：
  1. [console-scaffold-guide.md](./console-scaffold-guide.md)
