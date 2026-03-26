# 链上钱包情报接入规范（MVP v1）

## 1. 目标

本规范用于把“巨额资金钱包地址事件”安全接入 AI 决策上下文，并降低因数据不完整导致的误判风险。

目标不是追求单一数据源“绝对正确”，而是建立可解释、可降级、可审计的多源融合机制。

## 2. 设计原则

- 多源优先：行业数据源为主，自采数据为辅
- 置信度先行：先评估可信度，再决定是否影响交易动作
- 降级可控：数据不完整时自动降级，不允许放大风险敞口
- 全链路可追踪：事件、特征、决策引用关系都可回溯

## 3. 数据源策略

## 3.1 源分层

- Primary（主源）：行业公认地址标签/资金流 API
- Secondary（次源）：项目 crawler 自采事件
- Optional（可选）：交易所公告/链上浏览器补充校验

## 3.2 融合规则

- 同事件主次源都存在：以 Primary 为主，Secondary 仅用于补充字段
- 主源缺失但次源存在：写入 `coverage_gap=true`，降置信度
- 主次源冲突：标记 `conflict=true`，进入 `review_only` 模式

## 4. 数据模型

## 4.1 监控名单表（watchlist）

表名建议：`onchain_wallet_watchlist`

字段建议：
- `id`（主键）
- `chain`（ETH/BTC/TRON/SOL）
- `address`
- `label`
- `entity_type`（exchange/fund/market_maker/whale/other）
- `importance_weight`（0~1）
- `is_active`
- `created_at` / `updated_at`

唯一约束建议：`(chain, address)`

## 4.2 钱包事件表（event）

表名建议：`onchain_wallet_events`

字段建议：
- `id`（主键）
- `event_uid`（去重键）
- `tx_hash`
- `chain`
- `symbol`
- `token`
- `address`
- `counterparty`
- `direction`（in/out）
- `amount`
- `usd_value`
- `block_time`
- `source_name`
- `source_priority`（primary/secondary）
- `coverage_gap`（bool）
- `conflict`（bool）
- `raw_payload`（json/text）
- `created_at`

唯一约束建议：`event_uid`

去重键建议：
`sha256(chain + tx_hash + address + token + direction + block_time_rounded)`

## 4.3 聚合特征表（snapshot）

表名建议：`onchain_wallet_signal_snapshots`

字段建议：
- `symbol`
- `window_hours`
- `exchange_netflow_usd`
- `whale_buy_usd`
- `whale_sell_usd`
- `top_events_json`
- `coverage_ratio`
- `freshness_sec`
- `conflict_ratio`
- `signal_confidence`（0~1）
- `risk_flag`（normal/review_only/reduce_only）
- `generated_at`

## 5. 特征与评分

## 5.1 核心特征

- `exchange_netflow_usd`：交易所标签地址净流入（in-out）
- `whale_buy_sell_ratio`：巨鲸净买卖比
- `large_tx_count`：超阈值转账数
- `coverage_ratio`：监控地址覆盖率
- `freshness_sec`：最近事件新鲜度
- `conflict_ratio`：跨源冲突占比

## 5.2 置信度分数（建议）

`signal_confidence = Wc*coverage + Wf*freshness + Wk*(1-conflict) + Ws*source_quality`

建议初始权重：
- `Wc=0.35`
- `Wf=0.25`
- `Wk=0.25`
- `Ws=0.15`

分数区间与策略：
- `>=0.75`：可作为强信号参与仓位决策
- `0.5~0.75`：仅作辅助信号，限制加仓幅度
- `<0.5`：禁止作为开仓依据，只用于解释

## 6. 决策接入规则（AI Engine）

## 6.1 注入上下文结构

在 `onchain_report` 中新增：
- `wallet_signal_summary`
- `signal_confidence`
- `coverage_ratio`
- `freshness_sec`
- `conflict_ratio`
- `risk_flag`
- `top_events`

## 6.2 行为门禁

- `signal_confidence < 0.5`：强制 `review_only`
- `coverage_ratio < 0.6` 或 `conflict_ratio > 0.25`：强制 `review_only`
- `freshness_sec > 900`：降低信号权重，不允许单因子开仓

## 6.3 与现有风控联动

- 若系统已处于 `deleveraging_required/reduce_only`，钱包情报只能用于“减仓优先级排序”，不能用于新增风险敞口
- 钱包事件与技术面冲突时，默认交由 Reviewer 保守裁决

## 7. API 约定（建议）

## 7.1 Crawler

- `POST /api/v1/trigger/onchain/wallet-events`
- `POST /api/v1/sync/onchain/wallet-events`

请求参数建议：
- `symbol`
- `chains[]`
- `window_hours`
- `min_usd_value`

## 7.2 Backend

- `GET /api/v1/market/onchain/wallet-events`
- `GET /api/v1/market/onchain/wallet-summary`
- `POST /api/v1/market/onchain/watchlist`
- `DELETE /api/v1/market/onchain/watchlist/{id}`

## 7.3 AI Engine

- `GET /onchain/wallet-summary?symbol=BTC/USDT&hours=6`

## 8. 默认阈值（MVP）

- `min_usd_value`：100000
- `window_hours`：6
- `coverage_ratio_min`：0.6
- `freshness_sec_max`：900
- `conflict_ratio_max`：0.25

## 9. 观测与告警

必须监控：
- 每轮抓取事件数
- 覆盖率、冲突率、时效性
- 进入 `review_only/reduce_only` 次数
- 触发后收益归因（避免“看起来有效”但不可复现）

告警建议：
- 连续 3 轮 `coverage_ratio < 0.4`
- `source_error_rate > 20%`
- `signal_confidence` 突降超过 40%

## 10. MVP 落地顺序

第 1 周：
- 建表（watchlist/event/snapshot）
- 接入一个 Primary 数据源 + 当前自采
- 打通 Backend 查询接口

第 2 周：
- 接入 AI 上下文 + Reviewer 门禁降级
- 加 Dashboard 简版可视化（summary + top events）
- 输出回测期误判样本清单

第 3 周：
- 多链扩展（ETH/TRON 优先）
- 校准置信度权重与阈值
- 加入事件归因报表

## 11. 验收标准

- 能稳定生成 `wallet-summary`，并带 `signal_confidence`
- 数据缺失时自动进入 `review_only`，不会触发激进开仓
- 所有被引用事件都可追溯到 `event_uid` 与原始 payload
- 连续 7 天运行，无大规模重复入库或空结果误报
