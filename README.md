# 🤖 AI Crypto Trading Platform (AI 量化决策终端)

[![Status](https://img.shields.io/badge/Status-Active%20Development-green)](https://github.com/your-repo)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Stack](https://img.shields.io/badge/Tech-FastAPI%20%7C%20Next.js%20%7C%20TimescaleDB-orange)](docs/TECHNICAL_DESIGN.md)

> **Where Data Meets Cognitive Alpha.**  
> 一个不仅仅是展示行情，更能“读懂”新闻、感知情绪、并像资深交易员一样思考的 AI 决策平台。

---

## ✨ 核心亮点 (Why This Platform?)

传统的量化交易依赖于硬编码的逻辑（Logic-Driven），而本平台致力于实现 **数据驱动 (Data-Driven)** 与 **认知变现 (Cognitive Alpha)**。

*   **🧠 AI 决策大脑**: 利用 LLM (GPT-4/DeepSeek) + RAG 技术，结合历史行情与实时新闻，生成具备逻辑解释的交易建议。
*   **📰 智能情报网**: 实时聚合 CryptoPanic、Twitter 等多源信息，通过 NLP 模型自动计算情感得分（利好/利空），一眼看穿市场情绪。
*   **⚡ 毫秒级行情**: 基于 WebSocket 的实时数据流，配合 **TimescaleDB** 高性能时序数据库，秒级计算 RSI, MACD, Bollinger Bands 等核心指标。
*   **🔄 自我进化**: 独特的 "Reflector" Agent 机制，能对每一次交易进行复盘反思，不断优化策略逻辑。

## 🚀 最新更新 (What's New in v0.2.0)

*   **双数据库架构**: 将用户数据 (PostgreSQL) 与海量行情数据 (TimescaleDB) 彻底拆分，大幅提升并发读写性能。
*   **实时指标面板**: Dashboard 新增“最新指标卡”，实时展示 SMA, EMA, ATR 等技术指标，并精确标注计算基于的 K 线时间。
*   **数据回补 (Backfill)**: 支持一键从数据库最早记录向前回补历史数据，确保指标计算的连续性。
*   **增强型新闻流**: 修复了新闻源聚合问题，现在能更稳定地抓取并分析全球市场动态。

## 🛠️ 技术栈 (Tech Stack)

### Backend (The Brain)
*   **Core**: Python 3.10+, FastAPI
*   **AI**: LangChain, OpenAI/DeepSeek API, FinBERT (Sentiment)
*   **Data**: 
    *   **TimescaleDB** (Market Data & Indicators)
    *   **PostgreSQL** (User & Strategy Config)
    *   **ChromaDB** (Vector Memory for RAG)
    *   **Redis** (Real-time Pub/Sub & Caching)
*   **Task Queue**: Celery (Async Jobs)

### Frontend (The Face)
*   **Framework**: Next.js 16 (App Router), TypeScript
*   **UI**: Tailwind CSS, Shadcn/ui
*   **Charts**: Lightweight-charts (TradingView style)

## 📖 文档导航 (Documentation)

详细的设计文档位于 `docs/` 目录下：

*   [📚 需求文档 (REQUIREMENTS.md)](docs/REQUIREMENTS.md) - 核心功能列表与业务目标。
*   [🎨 产品设计 (PRODUCT_DESIGN.md)](docs/PRODUCT_DESIGN.md) - UI/UX 交互流程与界面设计。
*   [🏗️ 技术架构 (TECHNICAL_DESIGN.md)](docs/TECHNICAL_DESIGN.md) - 系统架构图与数据库设计。
*   [🏛️ 系统架构 V2 (SYSTEM_ARCHITECTURE_V2.md)](docs/SYSTEM_ARCHITECTURE_V2.md) - 面向万级并发的企业级架构演进。

## 📦 快速开始 (Getting Started)

### 前置要求
*   Docker & Docker Compose
*   Node.js 20.9+
*   Python 3.10+

### 安装步骤

1.  **克隆仓库**:
    ```bash
    git clone https://github.com/your-username/ai-crypto-trading.git
    cd ai-crypto-trading
    ```

2.  **启动基础服务** (DBs, Redis, Chroma):
    ```bash
    docker-compose up -d db-users db-market redis chromadb
    ```

3.  **启动后端**:
    ```bash
    cd backend
    pip install -r requirements.txt
    # 首次运行需初始化数据库
    python main.py
    ```

4.  **启动前端**:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

## 🔐 依赖安全策略 (Dependency Security)

前端已启用 `package.json -> overrides` 来强制覆盖高风险传递依赖版本，避免钱包生态下游包引入已知漏洞版本。

当前覆盖策略位于：

* `frontend/package.json` 的 `overrides`
* 典型覆盖项：`h3`、`hono`、`socket.io-parser`

建议在每次依赖升级后执行以下流程：

```bash
cd frontend
npm install
npm audit --omit=dev
npm run lint
npm run build
```

若升级后出现兼容问题，可回滚到上一个稳定锁文件版本（恢复 `package-lock.json`）后重新安装：

```bash
cd frontend
npm install
npm run lint
npm run build
```

## 🤝 贡献 (Contributing)
欢迎提交 Issue 和 Pull Request！让我们一起构建下一代 AI 交易终端。

## 📄 许可证 (License)
MIT License.
