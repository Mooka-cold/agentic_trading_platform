# 项目全景与模块边界

## 1. 项目目标

本项目是一个面向交易研究与自动化执行的多智能体平台，覆盖数据采集、策略决策、风控审核、执行与复盘。

核心闭环：

`数据采集 → 状态构建 → 多智能体博弈 → 风控审查 → 执行/拒绝 → 复盘沉淀`

## 2. 目录与职责

- `ai_engine/`：多智能体工作流、Prompt 管理、SSE 运行日志、策略编排配置。
- `backend/`：统一业务 API、交易执行适配、会话与日志查询、系统配置。
- `crawler/`：行情/新闻/宏观/链上数据采集触发服务。
- `scheduler/`：定时触发 crawler、backend 与 ai_engine 的周期任务。
- `shared/`：跨服务共享配置、数据库会话、通用模型与符号规则。
- `frontend/`：Vite + React 控制台，展示 Swarm、会话、持仓、设置等页面。
- `docs/`：需求、产品、技术、架构、运维、数据规范文档。

## 3. 服务边界与调用关系

- `frontend -> backend`：通过 `/api/v1/*` 访问业务接口。
- `backend -> ai_engine`：调用分析与工作流接口，持久化信号/会话状态。
- `scheduler -> crawler/backend/ai_engine`：按周期触发抓取、聚合、复盘。
- `ai_engine -> redis/postgres/timescale`：读取运行态与数据快照，输出工作流结果。

## 4. 启动入口

### 4.1 Docker Compose（推荐）

```bash
docker compose up -d
```

默认访问：

- Frontend: `http://localhost:3200`
- Backend: `http://localhost:3201`
- AI Engine: `http://localhost:3202`

### 4.2 本地开发（分服务）

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
cd ai_engine
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
cd frontend
npm install
npm run dev
```

## 5. 当前工程约束

- 前端当前主线为 `frontend/`（Vite + React）。
- 工作流编排策略与数据路由策略通过系统配置动态生效。
- 文档更新需与当前代码行为保持一致，优先维护 `README.md` 与 `docs/DOCS_INDEX.md`。
