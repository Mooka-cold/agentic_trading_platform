# 系统架构 V2（可扩展版）

## 1. 目标

V2 架构的目标是让系统在复杂业务下保持：

- 可扩展：服务可按职责水平扩容
- 可观测：会话、日志、执行状态可追踪
- 可恢复：失败可重试、可降级、可回滚

## 2. 架构原则

- 解耦：采集、决策、执行、展示分层清晰
- 无状态：应用节点尽量无状态，状态落库
- 事件驱动：通过消息与日志驱动工作流推进
- 安全优先：依赖安全与配置安全纳入发布基线

## 3. 组件拓扑

### 3.1 交互层

- Frontend（Next.js 16）
  - Dashboard / History / Strategy / Settings
  - API Route 代理与展示编排

### 3.2 应用层

- backend（FastAPI）
  - 统一对外 API
  - 交易执行服务与会话查询
- ai_engine
  - 多智能体工作流
  - 状态构建、仲裁、风控、复盘

### 3.3 数据层

- TimescaleDB：行情与技术指标
- PostgreSQL：会话、订单、业务配置
- Redis：实时流与缓存
- ChromaDB：向量检索

### 3.4 采集与调度层

- crawler：新闻与外部情报采集
- scheduler：周期触发与任务编排

## 4. 关键数据流

1. crawler/streamer 写入行情与新闻数据
2. ai_engine 构建会话状态并触发多智能体流程
3. reviewer 输出风控结论与修复建议
4. execution 执行交易并回写状态
5. reflector 沉淀复盘并写入历史可查询记录

## 5. 扩展策略（10k+ 用户）

### 5.1 应用扩展

- frontend、backend、ai_engine 可独立扩容
- 计算密集型工作负载与 API 节点分离

### 5.2 数据扩展

- 时序写入与业务写入分库
- 连接池与限流并行治理
- 热数据缓存与冷数据分层查询

### 5.3 工作流扩展

- 按 symbol / session 维度并发隔离
- 失败重试与超时熔断策略标准化

## 6. 依赖与发布安全基线

### 6.1 运行时基线

- Next.js 16+
- Node.js 20.9+

### 6.2 前端依赖安全覆盖

通过 `frontend/package.json -> overrides` 固定高风险传递依赖最低安全版本：

- h3: ^1.15.10
- hono: ^4.12.7
- socket.io-parser: ^4.2.6

### 6.3 发布校验 SOP

```bash
cd frontend
npm install
npm audit --omit=dev
npm run lint
npm run build
```

### 6.4 回滚 SOP

```bash
cd frontend
npm install
npm run lint
npm run build
```

## 7. 演进路线

### 阶段 A：稳定性

- 强化会话状态机与错误分类
- 完善审计日志和历史检索能力

### 阶段 B：扩展性

- 引入更细粒度队列与优先级调度
- 拆分更多可独立扩容的执行单元

### 阶段 C：企业化

- 多租户隔离与权限治理
- 灰度发布与自动回滚能力
