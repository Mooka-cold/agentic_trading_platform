# AI Crypto Trading Platform (AI 量化与决策平台)

[![Status](https://img.shields.io/badge/Status-In%20Progress-yellow)](https://github.com/your-repo)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

一个基于 AI 的一体化加密货币量化交易平台。集成了新闻聚合、实时行情、LLM 智能决策和自动化交易执行。

## 📖 文档导航 (Documentation)

*   [需求文档 (Requirements)](docs/REQUIREMENTS.md) - 项目核心目标与功能列表。
*   [产品设计 (Product Design)](docs/PRODUCT_DESIGN.md) - UI/UX 设计、功能模块与交互流程。
*   [技术架构 (Technical Design)](docs/TECHNICAL_DESIGN.md) - 系统架构、技术栈选型与数据库设计。

## 🚀 核心特性 (Key Features)

*   **智能信息流 (AI Observer)**: 实时聚合 CryptoPanic、Twitter 等多源新闻，利用 NLP (FinBERT/LLM) 自动进行情感打分，一目了然地展示市场利好/利空。
*   **AI 决策大脑 (AI Strategist)**: 基于 RAG (检索增强生成) 技术，结合历史新闻和技术指标 (RSI, MACD)，像资深交易员一样思考并给出买卖建议。
*   **自动化交易 (AI Trader)**: 无缝对接 Freqtrade 交易引擎，支持策略回测、参数优化和实盘自动执行。
*   **现代化仪表盘**: 基于 Next.js + Tailwind CSS + TradingView 图表库构建的专业级交易终端界面。

## 🛠️ 技术栈 (Tech Stack)

*   **Frontend**: Next.js 14, TypeScript, Tailwind CSS, Shadcn/ui, Lightweight-charts
*   **Backend**: Python, FastAPI, Celery
*   **Database**: TimescaleDB (Time-series), PostgreSQL (Relational), ChromaDB (Vector)
*   **AI & NLP**: LangChain, OpenAI GPT-4o / DeepSeek, FinBERT
*   **Trading Engine**: Freqtrade, CCXT Pro

## 📦 快速开始 (Getting Started)

### 前置要求
*   Docker & Docker Compose
*   Node.js 18+
*   Python 3.10+

### 安装步骤

1.  克隆仓库:
    ```bash
    git clone https://github.com/your-username/ai-crypto-trading.git
    cd ai-crypto-trading
    ```

2.  启动基础服务 (DB, Redis):
    ```bash
    docker-compose up -d db redis
    ```

3.  后端开发环境:
    ```bash
    cd backend
    pip install -r requirements.txt
    uvicorn main:app --reload
    ```

4.  前端开发环境:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

## 🤝 贡献 (Contributing)
欢迎提交 Issue 和 Pull Request！

## 📄 许可证 (License)
本项目采用 MIT 许可证。详情请见 [LICENSE](LICENSE) 文件。
