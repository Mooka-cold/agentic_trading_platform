# AI Trading Platform

一个面向实盘与研究场景的多智能体交易平台，覆盖行情采集、新闻情绪、策略生成、风控审核、执行与复盘全链路。

## 你会得到什么

- 多智能体协同决策：Analyst / Bull / Bear / PM / Reviewer / Reflector
- 统一交易工作流：采集 → 研判 → 仲裁 → 风控 → 执行 → 复盘
- 前后端分离架构：Next.js 16 + FastAPI + 多存储分层
- 可审计输出：日志、artifact、历史会话、回放能力

## 项目结构

```text
ai_trading/
├── ai_engine/      # AI 工作流与 Agent 编排
├── backend/        # 业务 API、交易服务、数据接口
├── frontend/       # Web 控制台 (Next.js 16)
├── crawler/        # 新闻/数据抓取服务
├── scheduler/      # 调度与定时任务
├── shared/         # 跨服务共享配置与模型
└── docs/           # 产品、需求、架构、UI 文档
```

## 快速启动

### 前置条件

- Docker & Docker Compose
- Node.js 20.9+
- Python 3.10+

### 本地启动

```bash
git clone https://github.com/Mooka-cold/agentic_trading_platform.git
cd agentic_trading_platform
docker-compose up -d db-users db-market redis chromadb
```

```bash
cd backend
pip install -r requirements.txt
python main.py
```

```bash
cd frontend
npm install
npm run dev
```

## 文档入口

- [文档总览](docs/DOCS_INDEX.md)
- [需求文档](docs/REQUIREMENTS.md)
- [产品设计](docs/PRODUCT_DESIGN.md)
- [UI 规范](docs/UI_SPEC.md)
- [技术设计](docs/TECHNICAL_DESIGN.md)
- [系统架构 V2](docs/SYSTEM_ARCHITECTURE_V2.md)
- [运维与发布手册](docs/OPERATIONS_RUNBOOK.md)
- [远程部署指南](DEPLOY_GUIDE.md)

## 开发与发布基线

- 前端：Next.js 16 + ESLint 9 + webpack 模式
- 依赖安全：`frontend/package.json` 使用 `overrides` 锁定高风险传递依赖
- 发布前最小检查：

```bash
cd frontend
npm install
npm audit --omit=dev
npm run lint
npm run build
```

## 许可证

MIT
