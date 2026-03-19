# Web 应用未运行问题排查报告

## 问题诊断

### 当前状态

1. **ai-test-platform 项目** - 这是一个测试平台项目，**本身不是 Web 应用**
   - 项目处于 0-1 初始化阶段
   - 大部分服务目录是空的（只有目录结构）
   - `docker-compose.yml` 是空文件
   - `package.json` 是空文件

2. **测试目标应用** - 应该是 `mall-admin-web`
   - 位置：`/Users/bettyhuang/IdeaProjects/mall-admin-web/`
   - 这是一个 Vue 3 + Vite 项目
   - 开发服务器运行在 `http://localhost:5173`
   - 后端 API 期望在 `http://localhost:8080`

3. **当前运行的服务**
   - Jenkins: `http://localhost:8080` (占用 API 端口)
   - mall-admin-web 当前应运行在 `http://localhost:5173`

## 解决方案

### 方案 1: 启动 mall-admin-web (推荐用于测试)

```bash
# 进入商城管理前端项目
cd /Users/bettyhuang/IdeaProjects/mall-admin-web

# 安装依赖 (如果还没安装)
npm install

# 启动开发服务器
npm run dev
```

启动后，前端将运行在 `http://localhost:5173`

**注意**: 后端 API (`localhost:8080`) 被 Jenkins 占用，你需要：
- 要么停止 Jenkins
- 要么修改 `.env` 中的 `VITE_BASE_SERVER_URL` 指向真实后端

### 方案 2: 使用其他测试环境

修改 ai-test-platform 的 `.env` 文件，指向已有的测试环境：

```bash
# 编辑配置文件
nano /Users/bettyhuang/PycharmProjects/ai-test-platform/.env

# 修改 BASE_URL 为实际环境
BASE_URL=http://your-test-env.com/login#/login
```

### 方案 3: 搭建完整测试环境 (长期方案)

ai-test-platform 项目需要：

1. **填写 docker-compose.yml** - 定义所有服务
2. **配置各微服务** - 目前都是空目录
3. **准备测试数据库** - MySQL/PostgreSQL
4. **启动 AI Orchestrator** - 核心编排服务

这是一个较大的工程，需要逐步完成。

## 建议

**短期**: 使用方案 1，先启动 mall-admin-web 来验证测试框架

**中期**: 配置一个稳定的测试环境（可以是测试服务器）

**长期**: 完善 ai-test-platform 项目的基础设施建设

## 快速验证命令

```bash
# 检查 5173 端口是否有服务
lsof -i :5173

# 检查 8080 端口占用
lsof -i :8080

# 查看 mall-admin-web 是否能启动
cd /Users/bettyhuang/IdeaProjects/mall-admin-web
npm run dev
```
