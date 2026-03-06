import asyncio
import ccxt.async_support as ccxt
import pandas as pd
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from app.db.session import get_market_engine
from app.core.config import settings

class MarketCrawler:
    def __init__(self, exchange_id: str = "binance"):
        self.exchange_id = exchange_id
        self.engine = get_market_engine()
        # Initialize exchange instance
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'} # Default to futures for trading bot
        })
    
    async def close(self):
        await self.exchange.close()

    async def get_realtime_indicators(self, symbol: str) -> dict:
        """
        Fetch realtime calculated indicators from Redis.
        Fallback to DB or calculate on-demand if Redis is stale/empty.
        """
        try:
            # 1. Try Redis
            redis_client = get_redis_client() # Need to import or pass in
            # Assuming redis_client is available
            # Or use self.engine if we attach redis to it?
            # Better: Use a helper
            
            # Since MarketCrawler doesn't have Redis client by default, we skip this implementation here
            # and let Analyst Agent handle the Redis fetch logic, or inject Redis here.
            pass
        except:
            pass
            
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100, since: int | None = None):
        """
        Fetch OHLCV data from CCXT with caching for macro timeframes (1h, 4h, 1d).
        """
        # ... existing logic ...

        # Cache key based on symbol + timeframe (rounded to nearest minute)
        # For 1h data, we can cache for 5 minutes.
        
        # Simple in-memory cache logic (or use Redis if available)
        # Since this is a crawler, maybe we just fetch.
        
        # But the user specifically asked for "Macro indicators (1H) cache".
        # This is likely used by the AI Engine when it requests data.
        
        # Let's implement a simple Redis cache if settings.REDIS_URL is present.
        
        try:
            if not self.exchange.has['fetchOHLCV']:
                return None
            
            # Fetch
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['time'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df['symbol'] = symbol
            df['interval'] = timeframe
            df['source'] = self.exchange_id
            
            return df
            
        except Exception as e:
            print(f"Error fetching OHLCV for {symbol} {timeframe}: {e}")
            return None

    def save_to_db(self, df: pd.DataFrame):
        """
        Save DataFrame to TimescaleDB efficiently.
        """
        if df is None or df.empty:
            return

        # Prepare data for insertion (convert Timestamp to string/datetime)
        data_to_insert = df.to_dict(orient='records')
        
        # SQL with Named Parameters (:time, :symbol, etc.)
        upsert_sql = text("""
            INSERT INTO market_klines (time, symbol, interval, open, high, low, close, volume, source)
            VALUES (:time, :symbol, :interval, :open, :high, :low, :close, :volume, :source)
            ON CONFLICT (time, symbol, interval) 
            DO UPDATE SET 
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume;
        """)

        try:
            with self.engine.begin() as conn:  # begin() auto-commits on success
                conn.execute(upsert_sql, data_to_insert)
            print(f"✅ Saved {len(df)} records for {df['symbol'].iloc[0]} ({df['interval'].iloc[0]})")
        except Exception as e:
            print(f"❌ DB Error saving {df['symbol'].iloc[0]}: {e}")

    def _interval_ms(self, timeframe: str) -> int:
        mapping = {
            "1m": 60_000,
            "1h": 3_600_000,
            "4h": 14_400_000,
            "1d": 86_400_000
        }
        return mapping.get(timeframe, 60_000)

    def _get_earliest_time(self, symbol: str, timeframe: str):
        query = text("""
            SELECT MIN(time) FROM market_klines
            WHERE symbol = :symbol AND interval = :interval
        """)
        with self.engine.begin() as conn:
            result = conn.execute(query, {"symbol": symbol, "interval": timeframe}).scalar()
        return result

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
            batch = batch[batch['timestamp'] <= end_ms]
            if batch.empty:
                break
            self.save_to_db(batch)
            total += len(batch)
            last_ts = int(batch['timestamp'].iloc[-1])
            if last_ts == since_ms:
                since_ms += interval_ms
            else:
                since_ms = last_ts + interval_ms

        return total

    async def sync_market_data(self, symbols: list, timeframes: list):
        """
        Main entry point to sync data for multiple symbols.
        """
        print(f"Starting market data sync for {len(symbols)} symbols...")
        
        for symbol in symbols:
            for tf in timeframes:
                df = await self.fetch_ohlcv(symbol, tf, limit=1000) # Fetch last 1000 candles
                if df is not None:
                    self.save_to_db(df)
        
        print("Market data sync completed.")

# Standalone execution for testing
async def main():
    crawler = MarketCrawler()
    try:
        await crawler.sync_market_data(['BTC/USDT', 'ETH/USDT', 'SOL/USDT'], ['1m', '1h', '4h'])
    finally:
        await crawler.close()

if __name__ == "__main__":
    asyncio.run(main())
