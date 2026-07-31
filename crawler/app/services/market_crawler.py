import ccxt.async_support as ccxt
import pandas as pd
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from shared.db.session import get_market_engine
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import asyncio


class MarketCrawler:
    """
    K线爬虫：支持多交易所 failover + 指数退避重试。

    改进点：
    - 按 EXCHANGES 顺序自动 failover：Binance → Coinbase → OKX
    - 每次请求最多 3 次指数退避重试
    - 单次 failover 失败不影响整体
    """
    EXCHANGES = ["binance", "coinbase", "okx"]  # 顺序尝试

    def __init__(self, exchange_id: str = "binance"):
        self.exchange_id = exchange_id
        self.engine = get_market_engine()
        self._exchanges = {}  # lazy init

    def _get_exchange(self, exchange_id: str):
        if exchange_id in self._exchanges:
            return self._exchanges[exchange_id]
        exchange_class = getattr(ccxt, exchange_id)
        options = {"enableRateLimit": True}
        # 不使用 futures 模式，因为 Binance futures API 在部分网络区域被屏蔽。
        # 现货 API 通常可达，且对于 K 线数据足够。
        instance = exchange_class(options)
        self._exchanges[exchange_id] = instance
        return instance

    async def close(self):
        for inst in self._exchanges.values():
            try:
                await inst.close()
            except Exception:
                pass
        self._exchanges.clear()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ccxt.NetworkError, ccxt.ExchangeNotAvailable)),
        reraise=True,
    )
    async def _fetch_from_exchange(self, exchange_id: str, symbol: str, timeframe: str, limit: int, since: int | None):
        exchange = self._get_exchange(exchange_id)
        if not exchange.has["fetchOHLCV"]:
            raise ccxt.ExchangeError(f"{exchange_id} does not support fetchOHLCV")
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        return ohlcv

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100, since: int | None = None):
        """Try each exchange in EXCHANGES order until one succeeds."""
        last_exc = None
        for exchange_id in self.EXCHANGES:
            try:
                ohlcv = await self._fetch_from_exchange(exchange_id, symbol, timeframe, limit, since)
                if not ohlcv:
                    continue
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["time"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
                df["symbol"] = symbol
                df["interval"] = timeframe
                df["source"] = exchange_id
                return df
            except Exception as exc:
                last_exc = exc
                print(f"[failover] {exchange_id} failed for {symbol} {timeframe}: {exc}")
                continue
        print(f"[failover] ALL exchanges failed for {symbol} {timeframe}. Last error: {last_exc}")
        return None

    def save_to_db(self, df: pd.DataFrame):
        if df is None or df.empty:
            return

        data_to_insert = df.to_dict(orient="records")
        upsert_sql = text(
            """
            INSERT INTO market_klines (time, symbol, interval, open, high, low, close, volume, source)
            VALUES (:time, :symbol, :interval, :open, :high, :low, :close, :volume, :source)
            ON CONFLICT (time, symbol, interval)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                source = EXCLUDED.source;
            """
        )
        with self.engine.begin() as conn:
            conn.execute(upsert_sql, data_to_insert)

    def _interval_ms(self, timeframe: str) -> int:
        mapping = {"1m": 60_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
        return mapping.get(timeframe, 60_000)

    def _get_earliest_time(self, symbol: str, timeframe: str):
        query = text(
            """
            SELECT MIN(time) FROM market_klines
            WHERE symbol = :symbol AND interval = :interval
            """
        )
        with self.engine.begin() as conn:
            return conn.execute(query, {"symbol": symbol, "interval": timeframe}).scalar()

    async def backfill_ohlcv(self, symbol: str, timeframe: str, hours: int = 24) -> int:
        interval_ms = self._interval_ms(timeframe)
        earliest = self._get_earliest_time(symbol, timeframe)
        now = datetime.now(timezone.utc)
        end_time = (earliest - timedelta(milliseconds=interval_ms)) if earliest else now
        start_time = end_time - timedelta(hours=hours)
        since_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        total = 0
        while since_ms <= end_ms:
            batch = await self.fetch_ohlcv(symbol, timeframe, limit=1000, since=since_ms)
            if batch is None or batch.empty:
                break
            batch = batch[batch["timestamp"] <= end_ms]
            if batch.empty:
                break
            self.save_to_db(batch)
            total += len(batch)
            last_ts = int(batch["timestamp"].iloc[-1])
            since_ms = last_ts + interval_ms if last_ts != since_ms else since_ms + interval_ms
        return total

    async def sync_market_data(self, symbols: list[str], timeframes: list[str]):
        for symbol in symbols:
            for tf in timeframes:
                df = await self.fetch_ohlcv(symbol, tf, limit=1000)
                if df is not None:
                    self.save_to_db(df)
