# AI Trading Platform

一个面向实盘与研究场景的多智能体交易系统，覆盖数据采集、策略博弈、风控审核、执行与复盘全链路。  
项目核心理念：`交易正确性优先`、`可审计`、`可持续演进`。

## 30 秒了解这个项目

- 这不是“单模型喊单器”，而是一个可审计的多智能体交易团队系统
- 决策链条完整：`采集 -> 辩论 -> 仲裁 -> 风控 -> 执行 -> 复盘`
- 工程上可落地：支持 Docker 一键启动、会话追踪、交易正确性 Harness、线上部署
- 目标是长期演进能力，而不是一次性策略模板

## 为什么与众不同

- 从“预测准确率”转向“决策质量 + 风险收益比 + 可执行性”
- 把风控前置为硬门禁，允许拒单并要求可解释修订
- 把复盘做成系统能力（而非手工总结），为策略迭代提供闭环
- 把交易正确性做成自动化闸门（`make harness-smoke`）

## 项目亮点

- 多智能体团队式决策：Analyst / Bull / Bear / PM / Reviewer / Reflector 分工协作
- 非模板化工作流：支持多轮磋商、拒绝修订、复盘演化，而非固定策略模板
- 强风控门禁：Reviewer 审核链路 + 执行层约束（滑点、手续费、行情新鲜度）
- 全链路可审计：Session 日志、Agent 轮次、执行记录、历史回放可追踪
- 交易正确性 Harness：`make harness-smoke` 一键校验关键交易路径
- K 线工程化能力：支持 `1s -> 1m -> 5m -> 15m -> 1h -> 4h -> 1d` 逐级固化与指标可用性保障

## 先进性体现

- 认知型 Alpha 架构：将“观点冲突 -> 仲裁 -> 风控否决 -> 修订 -> 复盘”作为标准机制
- 数据与决策解耦：采集、决策、执行、展示分层，支持独立扩展与替换
- 生产化治理能力：定时调度、健康检查、自愈回填、幂等约束、可回滚
- 文档与代码同版本演进：关键流程变更要求同提交更新文档并通过最小验证

## 架构总览

```text
ai_trading/
├── ai_engine/      # AI 工作流与 Agent 编排
├── backend/        # 业务 API、交易服务、数据接口
├── frontend/       # Web 控制台 (Vite + React + TS)
├── crawler/        # 新闻/数据抓取服务
├── scheduler/      # 调度与定时任务
├── shared/         # 跨服务共享配置与模型
├── harness/        # 交易正确性场景与验证执行器
└── docs/           # 产品、需求、架构、运维文档
```

## 快速开始

### 前置条件

- Docker + `docker compose`
- Node.js 20.9+
- Python 3.10+

### 一键启动（推荐）

```bash
git clone <your-repo-url>
cd ai_trading
docker compose up -d --build
```

默认访问：

- Frontend: `http://localhost:3200`
- Backend API: `http://localhost:3201`
- AI Engine: `http://localhost:3202`

### 交易正确性最小验证

```bash
make harness-smoke
```

## 适合人群

- 想做“团队化 AI 决策”而不是单 Agent Demo 的量化/交易开发者
- 关注风控可解释性、执行一致性、会话可追溯性的工程团队
- 希望在研究到生产之间建立统一流程的产品与技术负责人

## 开发基线

- 前端：Vite 5 + React 18 + TypeScript 5
- 后端：FastAPI + SQLAlchemy + 多存储分层（PostgreSQL / TimescaleDB / Redis / ChromaDB）
- 本地代理：`frontend/vite.config.ts` 通过 `/api` 代理 backend
- 发布前建议：

```bash
cd frontend
npm install
npm audit --omit=dev
npm run lint
npm run build
```

```bash
cd /Users/huangyong/Documents/Qell/ai_trading
make harness-smoke
```

## 文档入口

- [文档总览](docs/DOCS_INDEX.md)
- [项目全景](docs/PROJECT_OVERVIEW.md)
- [需求文档](docs/REQUIREMENTS.md)
- [产品设计](docs/PRODUCT_DESIGN.md)
- [UI 规范](docs/UI_SPEC.md)
- [技术设计](docs/TECHNICAL_DESIGN.md)
- [系统架构 V2](docs/SYSTEM_ARCHITECTURE_V2.md)
- [运维与发布手册](docs/OPERATIONS_RUNBOOK.md)
- [远程部署指南](DEPLOY_GUIDE.md)

## 许可证

MIT
