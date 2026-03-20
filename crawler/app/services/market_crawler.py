import ccxt.async_support as ccxt
import pandas as pd
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from shared.db.session import get_market_engine


class MarketCrawler:
    def __init__(self, exchange_id: str = "binance"):
        self.exchange_id = exchange_id
        self.engine = get_market_engine()
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class(
            {
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            }
        )

    async def close(self):
        await self.exchange.close()

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100, since: int | None = None):
        try:
            if not self.exchange.has["fetchOHLCV"]:
                return None

            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["time"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df["symbol"] = symbol
            df["interval"] = timeframe
            df["source"] = self.exchange_id
            return df
        except Exception as exc:
            print(f"Error fetching OHLCV for {symbol} {timeframe}: {exc}")
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
                volume = EXCLUDED.volume;
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
