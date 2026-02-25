# 项目需求文档 (Requirements Document)

## 1. 项目概述
本项目旨在构建一个集成了**新闻聚合**、**行情工具**、**AI 决策**和**AI 交易**的一体化加密货币量化平台。
与传统量化交易（Logic-Driven）不同，本项目核心在于**Data-Driven（数据驱动）**与**Cognitive Alpha（认知变现）**。通过利用最新的 AI 技术（如 LLM、RAG、情感分析），实现从信息获取、认知分析、策略进化到交易执行的闭环系统。

## 2. 核心目标
1.  **认知变现 (Cognitive Alpha)**: 利用 AI 对非结构化数据（新闻、舆情）的理解能力，捕捉人类和传统量化模型无法发现的交易机会。
2.  **自我进化 (Self-Evolution)**: 构建具备反思机制的 Agent 系统，从每一次盈亏中学习，自动迭代优化策略逻辑，而非仅调整参数。
3.  **信息汇聚**: 提供一站式的加密货币市场信息（新闻 + 行情）。
4.  **自动化交易**: 支持基于 AI 信号的自动交易执行。
5.  **风险控制**: 在交易前提供策略回测和风险评估。

## 3. 功能需求

### 3.1 数据采集与聚合 (Data Aggregation)
*   **多源新闻抓取**:
    *   接入 CryptoPanic API、RSS Feeds (CoinDesk, Cointelegraph) 等主流新闻源。
    *   支持 Twitter (X) 等社交媒体数据的监控（可选）。
*   **实时行情数据**:
    *   接入主流交易所（Binance, OKX 等）的 WebSocket 数据。
    *   提供实时 K 线 (OHLCV)、深度图 (Orderbook) 和成交数据 (Trades)。
    *   计算常用技术指标 (RSI, MACD, Bollinger Bands 等)。
*   **非结构化数据清洗**:
    *   将新闻、舆情转化为向量 (Vector) 或情感分数 (Sentiment Score)。
*   **链上数据集成 (On-Chain Intelligence)**:
    *   监控主流交易所的 **Inflow/Outflow** (资金流向)。
    *   追踪已知 **Whale Wallets** (巨鲸钱包) 的大额异动。

### 3.2 AI 决策引擎 (AI Decision Engine) - 核心差异化
*   **情感分析 (Sentiment Analysis)**:
    *   利用 NLP 模型 (FinBERT, LLM) 对新闻和社交媒体数据进行情感打分 (-1 到 1)。
    *   生成每日/每小时的市场情绪指数 (Fear & Greed Index)。
*   **多 Agent 协同 (Multi-Agent Architecture)**:
    *   **Agent A (Strategist)**: 负责生成策略逻辑或代码。不仅仅是调整参数，而是能根据长期记忆库中的经验生成新的交易逻辑。
    *   **Agent B (Reviewer)**: 负责风险审查。具备“反直觉”能力，不仅看回测数据，还能发现逻辑漏洞（如过度拟合、伪相关性）。
    *   **Agent D (Backtester)**: 负责在沙盒环境中对 A 生成的策略进行历史回测，并引入对抗测试（Chaos Monkey）以验证鲁棒性。
*   **认知与记忆 (Cognition & Memory)**:
    *   **RAG (检索增强生成)**: 建立向量数据库，存储历史行情特征与对应的策略表现。
    *   **反思机制 (Reflection)**: 每次交易结束后，由 **Agent R (Reflector)** 生成复盘报告，分析“为什么亏/赚”，并写入长期记忆库。
*   **决策透明化 (Explainability)**:
    *   AI 必须输出决策权重和理由（如：“ETF 批准利好 + 巨鲸买入 > 技术面超买”）。

### 3.3 交易执行与管理 (Execution & Management)
*   **模拟/回测 (Backtesting)**:
    *   提供历史数据回测功能，验证 AI 策略的有效性。
    *   **真实环境模拟**: 强制计入滑点 (Slippage) 和手续费 (Fees)，拒绝“无摩擦”回测。
    *   支持参数优化和风险评估。
*   **实盘交易 (Live Trading)**:
    *   对接交易所 API，自动执行 AI 生成的交易信号。
    *   支持手动干预（一键跟单、一键停止）。
    *   提供实时的资产净值 (PNL) 监控。
*   **动态仓位管理 (Position Sizing)**:
    *   引入 **凯利公式** 或基于波动率 (ATR) 的仓位计算模型，而非固定手数。
*   **一键逃生 (Kill Switch)**:
    *   提供物理级熔断按钮，一键撤销所有挂单、市价平仓并停止所有 AI 进程。

### 3.4 用户界面 (User Interface)
*   **仪表盘 (Dashboard)**:
    *   左侧展示实时 K 线图表 (TradingView 风格)。
    *   右侧展示实时新闻流及情感评分。
    *   底部展示当前持仓、订单状态和 AI 建议日志。
*   **交互控制**:
    *   提供简单的聊天界面或按钮，允许用户向 AI 提问或下达指令。

## 4. 非功能需求
*   **性能**: 行情数据延迟需在毫秒级，新闻处理延迟在分钟级以内。
*   **扩展性**: 架构需支持模块化扩展，方便接入新的交易所或 AI 模型。
*   **稳定性**: 需具备断线重连、错误重试和异常报警机制。
*   **安全性**: API Key 等敏感信息需加密存储，交易操作需二次确认（可选）。

## 5. 约束条件
*   **开源复用**: 优先使用成熟的开源项目（如 CCXT, Freqtrade, LangChain, Next.js）。
*   **成本控制**: 尽量使用免费或低成本的数据源和 API。
