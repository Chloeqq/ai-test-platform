# 新手上手指南

从零到跑通第一个 AI 生成的测试用例，**预计 15 分钟**。

---

## 前置条件

| 工具 | 版本要求 | 检查命令 |
|------|---------|----------|
| Python | ≥ 3.11 | `python3 --version` |
| Docker Desktop | 最新版 | `docker ps`（鲸鱼图标静止） |
| Node.js | ≥ 18 | `node --version` |
| Git | 任意 | `git --version` |

---

## 第一步：克隆并启动

```bash
git clone <repo-url> ai-quality-platform
cd ai-quality-platform

# 创建环境配置（首次需要）
cp .env.example .env

# 安装依赖 + 构建前端 + 启动服务
make dev
```

看到以下输出说明启动成功：

```
============================================
  Dev ready:
  Web UI:      http://localhost:8013
  Orchestrator: http://localhost:8000
============================================
```

> **常见问题**：如果 `make dev` 报 `ORCHESTRATOR_API_KEY` 错误，编辑 `.env` 文件，把 `your-orchestrator-key` 改成任意字符串（如 `dev-key`）。

---

## 第二步：打开 Web UI

浏览器访问 **http://localhost:8013**

你会看到三个核心模块：
- **页面对象**（Page Objects）— 管理被测页面的元素定义
- **用例中心**（Test Cases）— 管理测试用例
- **工作台**（Workbench）— AI 生成 + 执行 + 报告

---

## 第三步：创建你的第一个项目

1. 点击 **测试项目** → **新建项目**
2. 填写：
   - 项目编码：`demo`
   - 项目名称：`演示项目`
3. 点击保存

---

## 第四步：录制一个页面（Page Object）

页面对象是 AI 理解"页面上有什么元素"的基础。

1. 点击 **页面对象** → **新建录制**
2. 填写：
   - 项目：`demo`
   - 页面编码：`login`
   - 目标 URL：`http://你的测试页面地址`
3. 点击 **开始录制**
4. 浏览器会自动打开你的页面。点击页面上的元素（输入框、按钮等），Playwright 会记录它们的位置。
5. 完成后点击 **停止录制**

> **提示**：如果没有测试页面，可以先跳过录制，手动创建页面元素。

---

## 第五步：生成第一个 AI 测试用例

1. 点击 **工作台** → **测试点资产**
2. 点击 **新建测试点**
3. 填写需求描述，例如：
   ```
   页面：login
   需求：验证登录功能
   - 输入正确的用户名和密码，点击登录，应该跳转到首页
   - 输入错误的密码，应该提示"密码错误"
   ```
4. 点击 **生成用例**
5. AI 会自动解析需求、匹配页面元素、生成可执行的测试脚本

---

## 第六步：执行用例并查看报告

1. 在 **用例中心** 找到刚生成的用例
2. 点击 **执行**
3. 等待执行完成（通常 10-30 秒）
4. 点击 **查看报告** 查看 Allure 测试报告

报告中可以看到：
- 每一步的执行结果（通过/失败）
- 失败时的截图和日志
- 执行耗时

---

## 项目结构速览

```
ai-quality-platform/
├── apps/
│   ├── web-ui-service/        # Web UI + 核心业务逻辑
│   │   ├── app/
│   │   │   ├── routers/       # API 路由
│   │   │   ├── services/      # 业务 Service
│   │   │   └── repositories/  # 数据访问
│   │   └── frontend/          # React 前端
│   └── ai-orchestrator/       # AI 编排引擎
├── runners/
│   └── web-playwright-python/ # Playwright 执行器
├── shared_backend/            # 共享工具和 DSL 编译器
├── assets/                    # 测试用例 YAML 文件
├── Makefile                   # 所有命令入口
├── QUICKSTART.md              # 本文件
└── README.md                  # 架构详述
```

---

## 下一步

- 读 [README.md](README.md) 了解完整架构
- 在 **页面对象** 管理中补充更多元素，提高 AI 生成准确率
- 配置 **质量门**（Quality Gate）拦截低质量用例
- 接入你的 CI/CD 流水线

---

## 遇到问题？

| 症状 | 解决 |
|------|------|
| Docker 连不上 | 确保 Docker Desktop 鲸鱼图标静止（不再跳动） |
| 端口被占用 | `lsof -ti:8013 \| xargs kill -9` |
| 页面空白 | 运行 `make db-bootstrap` 初始化种子数据 |
| 前端白屏 | 运行 `make frontend-build` 重新构建 |
| 测试失败 | 运行 `make test-unit` 检查测试状态 |
