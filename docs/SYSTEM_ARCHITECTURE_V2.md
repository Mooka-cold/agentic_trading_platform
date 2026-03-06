# AI Trading Platform - System Architecture V2 (Enterprise Grade)

## 1. Executive Summary
This architecture is designed to support **10,000+ concurrent users**, decoupling data acquisition from strategy execution, and ensuring high availability and scalability.

**Key Design Principles:**
*   **Decoupling**: Market data crawlers and strategy engines are completely separated via Database/Message Queue.
*   **Statelessness**: Application servers are stateless to allow horizontal scaling (Kubernetes HPA).
*   **Persistence**: All critical data (Prompts, Strategies, Orders) is stored in enterprise-grade databases, not local files.
*   **Real-time**: Utilizing Redis Pub/Sub and TimescaleDB for millisecond-level latency.

---

## 2. Core Architecture Components

### 2.1 User & Identity Management (IAM)
*   **Service**: `User Service` (FastAPI)
*   **Database**: PostgreSQL (`users`, `roles`, `permissions`)
*   **Auth**: JWT (JSON Web Tokens) with refresh mechanism.
*   **Features**:
    *   User Registration/Login (Email/Social).
    *   API Key Management (Encrypted storage via AES-256).
    *   Subscription Plans (Free, Pro, Institutional).

### 2.2 Data Pipeline (The "Bloodstream")
The data flow follows a **Write-Heavy / Read-Heavy segregation** pattern.

1.  **Crawlers (Producers)**:
    *   Cluster of lightweight Python scripts (`ccxt`, `websockets`).
    *   Fetch K-lines, Order Books, and News (CryptoPanic/Twitter).
    *   **Write To**: 
        *   **Hot Data**: Redis Pub/Sub (Topic: `market.btc_usdt.kline.1m`) for real-time strategy triggers.
        *   **Cold Data**: TimescaleDB (Hypertable) for historical backtesting and persistence.
    
2.  **Database Layer**:
    *   **TimescaleDB**: Stores massive amounts of market data (Ticks, K-lines). Optimized for time-series queries.
    *   **ChromaDB**: Stores news embeddings for RAG (Retrieval-Augmented Generation).

### 2.3 Strategy Engine (The "Brain")
*   **Trigger**: Event-driven. Listens to Redis Pub/Sub or periodic Scheduler (Celery).
*   **Context Loading**: 
    *   Fetches User's Strategy Config & Prompts from **PostgreSQL**.
    *   Fetches Historical Data from **TimescaleDB**.
*   **Execution**: 
    *   Runs LLM Inference (DeepSeek/GPT-4).
    *   Generates Signals (`BUY`/`SELL`).
*   **Output**: Pushes Signal to `Order Queue` (RabbitMQ).

### 2.4 Execution System
*   **Service**: `Order Service`
*   **Input**: Consumes signals from `Order Queue`.
*   **Action**: 
    *   Risk Check (Pre-trade validation).
    *   Route to specific Exchange API (Binance/Okx) via User's API Key.
*   **Feedback**: Updates Order Status in PostgreSQL.

---

## 3. Database Schema Design

### 3.1 PostgreSQL (Business Data)
```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR UNIQUE,
    password_hash VARCHAR,
    tier VARCHAR DEFAULT 'free', -- 'free', 'pro'
    created_at TIMESTAMP
);

-- Strategies
CREATE TABLE strategies (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    name VARCHAR,
    prompt_template TEXT, -- The LLM Prompt
    config JSONB, -- { "symbols": ["BTC/USDT"], "timeframe": "1h", "risk": "medium" }
    status VARCHAR, -- 'active', 'paused', 'backtesting'
    created_at TIMESTAMP
);

-- Orders
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    strategy_id UUID REFERENCES strategies(id),
    symbol VARCHAR,
    side VARCHAR, -- 'BUY', 'SELL'
    price DECIMAL,
    amount DECIMAL,
    status VARCHAR, -- 'filled', 'pending', 'failed'
    exchange_order_id VARCHAR
);
```

### 3.2 TimescaleDB (Market Data)
```sql
-- K-Lines (Hypertable)
CREATE TABLE market_klines (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR NOT NULL,
    interval VARCHAR NOT NULL, -- '1m', '1h', '1d'
    open DECIMAL,
    high DECIMAL,
    low DECIMAL,
    close DECIMAL,
    volume DECIMAL,
    source VARCHAR, -- 'binance', 'coinbase'
    PRIMARY KEY (time, symbol, interval)
);
SELECT create_hypertable('market_klines', 'time');
```

---

## 4. Scaling to 10k Users

### 4.1 Bottlenecks & Solutions
1.  **LLM API Limits**: 
    *   *Solution*: Implement a **Token Bucket Rate Limiter** per user. Queue requests if global limit is reached.
2.  **Database Connections**:
    *   *Solution*: Use **PgBouncer** for connection pooling.
3.  **Crawler Latency**:
    *   *Solution*: Shard crawlers by symbol (Crawler A: BTC-ETH, Crawler B: SOL-AVAX).

### 4.2 Deployment Topology
*   **K8s Cluster**:
    *   `frontend-deployment`: 3 Replicas (Auto-scale to 10).
    *   `backend-api`: 5 Replicas.
    *   `strategy-worker`: 10+ Replicas (CPU Intensive).
    *   `crawler-worker`: StatefulSet (Partitioned by symbols).

---

## 5. Implementation Roadmap

### Phase 1: Foundation (Current - Mostly Completed)
*   [x] Basic Frontend UI (Dashboard, News Feed, Indicators).
*   [x] Setup PostgreSQL (User/Strategy) & TimescaleDB (Market Data) Docker containers.
*   [x] Implement Market Streamer with real-time indicator calculation.
*   [x] Implement News Crawler & Sentiment Analysis.
*   [x] Backfill historical market data.

### Phase 2: User System
*   [ ] Implement Auth (Login/Register).
*   [ ] Create "My Strategies" CRUD API.

### Phase 3: Data Decoupling
*   [ ] Build standalone `Crawler Service`.
*   [ ] Write market data to TimescaleDB.
*   [ ] Refactor Strategy Engine to read from DB instead of API.

### Phase 4: Scale
*   [ ] Introduce Redis Pub/Sub for live signals.
*   [ ] Deploy on Kubernetes.
