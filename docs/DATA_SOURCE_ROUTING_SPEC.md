# 数据源路由与去重规范（Draft v1）

## 1. 目标

在不增加无效重复采集的前提下，提升数据覆盖率与稳定性。

核心原则：
- One Domain One Truth：每个数据域只允许一个主源驱动交易因子
- Fallback not Merge：备用源用于故障切换，不参与并行混算
- Unified Dedup：所有入库事件统一去重键与冲突标记

## 2. 数据域路由草案

建议把数据按四个域管理：`market`、`news`、`macro`、`onchain`。

```yaml
data_routing:
  market:
    primary: ccxt_binance_futures
    secondary:
      - ccxt_okx_swap
    mode: fallback_only
    sla:
      max_staleness_sec: 20
      max_error_rate_5m: 0.15

  news:
    primary:
      - cryptopanic
      - techflow
      - rss_crypto_tier1
    secondary:
      - newsapi
      - alpha_vantage_news
    mode: weighted_merge_primary_only
    sla:
      max_staleness_sec: 900
      max_error_rate_5m: 0.25

  macro:
    primary:
      - yfinance
      - defillama
      - alternative_fng
    secondary:
      - alpha_vantage
    mode: fallback_only
    sla:
      max_staleness_sec: 3600
      max_error_rate_5m: 0.2

  onchain:
    primary:
      - binance_derivatives_oi
      - binance_ls_ratio
      - wallet_tracker_internal
    secondary:
      - nansen_or_glassnode_or_cryptoquant
    mode: primary_plus_validation
    sla:
      max_staleness_sec: 600
      max_error_rate_5m: 0.2
```

## 3. 去重键定义

## 3.1 市场K线/行情

- `dedup_key = sha1(symbol + interval + venue + ts_ms)`
- Upsert 主键建议：`(time, symbol, interval, source)`

## 3.2 新闻

- 标题标准化：
  - lower
  - 去URL参数
  - 去emoji与多余空格
- `dedup_key = sha1(normalized_title + normalized_domain + published_minute_bucket)`

## 3.3 链上事件

- `dedup_key = sha1(chain + tx_hash + address + token + direction + minute_bucket)`
- 对同 tx 的多地址事件允许保留，不可跨地址误合并

## 3.4 宏观指标

- `dedup_key = sha1(metric_name + source + ts_bucket)`
- 高频指标按分钟桶，低频指标按小时桶

## 4. 冲突处理规则

- 同域同指标在同桶出现多值时：
  - 若主源存在：主源优先，次源写 `conflict_flag=true`
  - 若主源缺失：次源接管并标记 `coverage_gap=true`
- 冲突比率定义：
  - `conflict_ratio = conflict_records / total_records_in_window`
- 当 `conflict_ratio > 0.25` 时，策略侧切换 `review_only`

## 5. Fallback触发规则

## 5.1 基础触发

- 连续错误阈值：`3` 次
- 或窗口错误率：`error_rate_5m > domain.max_error_rate_5m`
- 或数据过期：`staleness > domain.max_staleness_sec`

## 5.2 切换行为

- 切换到 secondary 后设置：
  - `source_mode = "degraded"`
  - `degraded_reason = timeout | rate_limit | stale | parse_error`
- 恢复主源条件：
  - 连续健康检查通过 `N=5` 次

## 5.3 风险联动

- `market` 域 degraded：限制新开仓手数
- `news` 域 degraded：降低新闻因子权重，不单因子开仓
- `onchain` 域 degraded：禁止激进加仓，允许减仓
- 多域同时 degraded：强制 `review_only`

## 6. 评分与可观测性

每条数据建议带以下元字段：

- `source`
- `source_role`（primary/secondary）
- `confidence`
- `freshness_sec`
- `conflict_flag`
- `coverage_gap`
- `ingested_at`

每 5 分钟聚合输出：

- `domain_health_score`
- `error_rate_5m`
- `fallback_switch_count_1h`
- `conflict_ratio_1h`
- `coverage_ratio_1h`

## 7. 实施顺序（最小改造）

第一阶段：
- 为 `macro` 域引入 `yfinance -> alpha_vantage` fallback
- 为 `news` 域新增统一 `dedup_key`

第二阶段：
- 为 `onchain` 域引入 `primary+validation` 双通道
- 输出 `conflict_ratio` 与 `coverage_ratio`

第三阶段：
- 与 AI 风控联动：
  - `degraded`、`conflict_ratio`、`coverage_ratio` 注入 execution constraints

## 8. 验收标准

- 无新增重复写入激增
- fallback 自动切换可观察且可恢复
- 关键因子在单源故障时持续可用
- degraded 状态下无激进错误开仓
