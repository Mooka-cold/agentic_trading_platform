import asyncio
import os
import sys

# Add backend directory to sys.path to resolve app imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.crawler.market import MarketCrawler

async def test_crawler():
    print("🚀 Initializing MarketCrawler...")
    crawler = MarketCrawler()
    
    symbol = "BTC/USDT"
    timeframe = "1m"
    
    print(f"📥 Fetching {symbol} {timeframe} data from Binance...")
    df = await crawler.fetch_ohlcv(symbol, timeframe, limit=10)
    
    if df is not None and not df.empty:
        print(f"✅ Successfully fetched {len(df)} records!")
        print("\n--- Data Preview ---")
        print(df.head())
        print("--------------------\n")
        
        print("💾 Saving to TimescaleDB...")
        try:
            crawler.save_to_db(df)
            print("✅ Data successfully saved to DB!")
        except Exception as e:
            print(f"❌ Failed to save to DB: {e}")
    else:
        print("❌ Failed to fetch data (df is empty)")
    
    await crawler.close()

if __name__ == "__main__":
    asyncio.run(test_crawler())
