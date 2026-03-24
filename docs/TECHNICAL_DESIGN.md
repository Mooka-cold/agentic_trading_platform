# 技术设计文档

## 1. 架构概览

项目采用前后端分离 + 多服务协同架构，按职责拆分为四层：

- 数据层：行情、新闻、链上、宏观数据采集与存储
- 决策层：多智能体工作流与上下文编排
- 执行层：风控校验与下单执行
- 交互层：Web 控制台、历史会话与配置管理

核心流程：

`数据采集 → 状态构建 → 多智能体决策 → 风控审核 → 执行/拒绝 → 复盘沉淀`

## 2. 服务划分

### 2.1 ai_engine

- 负责工作流编排和 Agent 生命周期管理
- 负责 prompt 加载、LLM 调用与结构化输出解析
- 负责会话日志写入与运行状态同步

### 2.2 backend

- 提供统一 API 网关（交易、行情、历史、系统）
- 承载执行服务（paper/live 适配层）
- 管理工作流会话、日志查询与策略配置

### 2.3 frontend

- 基于 Next.js 16 App Router
- 展示实时状态、会话详情、策略配置与系统设置
- 通过 API Route 代理对接 ai_engine / backend

### 2.4 crawler / scheduler

- crawler：新闻与外部数据采集
- scheduler：定时任务与周期触发

### 2.5 shared

- 统一配置、常量、跨服务共享模型

## 3. 数据与存储

### 3.1 存储职责

- TimescaleDB：市场时序数据与指标
- PostgreSQL：用户、会话、订单、业务数据
- ChromaDB：向量检索与记忆
- Redis：实时事件流与缓存

### 3.2 数据原则

- 业务数据与市场数据分库，降低耦合
- 会话日志结构化保存，支持历史回放
- 关键输出必须保留 reject_code / checks / fix_suggestions

## 4. 工作流设计

### 4.1 主要角色

- Analyst：汇总技术面与上下文
- Bull / Bear Strategist：提出方向性提案
- Portfolio Manager：仲裁提案并输出最终策略
- Reviewer：执行风控规则与执行门禁
- Reflector：输出复盘与经验沉淀

### 4.2 修订机制

- Reviewer 拒绝后进入修订轮次
- PM 可消费 `review_feedback` 的结构化建议做参数修补
- 超过修订轮次后停止继续博弈并进入复盘

## 5. 前端工程基线

### 5.1 版本基线

- Next.js 16+
- Node.js 20.9+
- ESLint 9（flat config）
- TypeScript 5+

### 5.2 构建基线

- 当前项目使用 `--webpack` 显式构建模式
- API Route 使用 Next 16 约定签名
- Client Provider 与 Server Layout 分离，避免构建期 localStorage 问题

## 6. 依赖安全策略

前端通过 `package.json -> overrides` 锁定高风险传递依赖最低安全版本：

- h3: ^1.15.10
- hono: ^4.12.7
- socket.io-parser: ^4.2.6

依赖升级后必须执行：

```bash
cd frontend
npm install
npm audit --omit=dev
npm run lint
npm run build
```

## 7. 运维与发布约束

- 所有服务通过 Docker Compose 组织本地开发环境
- 发布前需完成前端 lint/build 与依赖审计
- 工作流关键路径必须可观测：会话状态、代理日志、拒绝原因

## 8. 关键接口示例

- `GET /api/v1/market/kline`：读取历史 K 线与指标
- `GET /api/v1/workflow/session/{id}`：读取会话详情与日志
- `GET /api/v1/workflow/history`：按条件查询历史会话
- `POST /api/v1/trade/execute`：执行交易指令
- `GET /api/v1/trade/positions`：读取当前持仓
