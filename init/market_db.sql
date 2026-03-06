-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create Market K-Lines Table
CREATE TABLE IF NOT EXISTS market_klines (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    source TEXT,
    sma_7 DOUBLE PRECISION,
    sma_25 DOUBLE PRECISION,
    ema_7 DOUBLE PRECISION,
    ema_25 DOUBLE PRECISION,
    rsi_14 DOUBLE PRECISION,
    macd DOUBLE PRECISION,
    macd_signal DOUBLE PRECISION,
    macd_hist DOUBLE PRECISION,
    bb_upper DOUBLE PRECISION,
    bb_middle DOUBLE PRECISION,
    bb_lower DOUBLE PRECISION,
    atr_14 DOUBLE PRECISION,
    UNIQUE (time, symbol, interval)
);

-- Convert to Hypertable (Partition by time)
SELECT create_hypertable('market_klines', 'time', if_not_exists => TRUE);

-- Create Indexes for fast query
CREATE INDEX IF NOT EXISTS ix_symbol_time ON market_klines (symbol, time DESC);
