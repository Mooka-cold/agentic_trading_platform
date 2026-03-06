import asyncio
import os
import sys
import ccxt.async_support as ccxt
import pandas as pd
from sqlalchemy import create_engine, text

# Local Config
DB_URL = "postgresql://market_admin:market_password@localhost:5434/ai_trading_market"
PROXY = "http://127.0.0.1:7890"  # Adjust if needed

async def fetch_and_save():
    print("🚀 Local Crawler (OKX) Starting...")
    
    # 1. Connect to DB
    engine = create_engine(DB_URL)
    
    # 2. Connect to Exchange (OKX)
    exchange = ccxt.okx({
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'}, # OKX swap
        # Uncomment if you need proxy
        # 'proxies': {
        #     'http': PROXY,
        #     'https': PROXY,
        # },
    })
    
    try:
        symbol = "BTC/USDT"
        timeframe = "1m"
        print(f"📥 Fetching {symbol} {timeframe} from OKX...")
        
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=100)
        if not ohlcv:
            print("❌ No data fetched")
            return

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['time'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df['symbol'] = symbol
        df['interval'] = timeframe
        df['source'] = 'okx'
        
        # Insert
        data = df.to_dict(orient='records')
        sql = text("""
            INSERT INTO market_klines (time, symbol, interval, open, high, low, close, volume, source)
            VALUES (:time, :symbol, :interval, :open, :high, :low, :close, :volume, :source)
            ON CONFLICT (time, symbol, interval) DO NOTHING
        """)
        
        with engine.begin() as conn:
            conn.execute(sql, data)
            print(f"✅ Saved {len(df)} records from OKX to DB!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(fetch_and_save())
