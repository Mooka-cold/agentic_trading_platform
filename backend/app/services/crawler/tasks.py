from app.services.crawler.market import MarketCrawler
from app.services.crawler.news import NewsCrawler
from app.services.monitor import PositionMonitorService
from app.db.session import get_user_db
import asyncio

# Removed APScheduler dependency
# This file now only defines the TASK logic, not the schedule.

market_crawler = MarketCrawler()
news_crawler = NewsCrawler()

# Initialize with default, but will update from DB
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]

def get_active_symbols():
    """Fetch active symbols from DB Strategies or Config"""
    # For now, we can fetch all unique symbols from active strategies
    # Or use a dedicated Watchlist table.
    # MVP: Stick to default list but allow extension via ENV or DB later.
    return SYMBOLS

async def job_sync_1m():
    symbols = get_active_symbols()
    print(f"⏰ [Task] Triggering 1m sync for {len(symbols)} symbols...")
    await market_crawler.sync_market_data(symbols, ['1m'])

async def job_sync_1h():
    symbols = get_active_symbols()
    print(f"⏰ [Task] Triggering 1h sync for {len(symbols)} symbols...")
    await market_crawler.sync_market_data(symbols, ['1h'])

async def job_sync_1d():
    symbols = get_active_symbols()
    print(f"⏰ [Task] Triggering 1d sync for {len(symbols)} symbols...")
    await market_crawler.sync_market_data(symbols, ['1d'])

async def job_sync_news():
    print("📰 [Task] Triggering News sync...")
    await news_crawler.sync_news()

def _run_monitor_sync():
    """Blocking function to run monitor"""
    db_gen = get_user_db()
    try:
        db = next(db_gen)
        service = PositionMonitorService(db)
        service.check_and_manage_positions()
    except Exception as e:
        print(f"Guardian Error: {e}")
    finally:
        # Generator cleanup
        try:
            db.close()
        except:
            pass

async def job_monitor_positions():
    print("🛡️ [Task] Guardian Active: Checking positions...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_monitor_sync)
